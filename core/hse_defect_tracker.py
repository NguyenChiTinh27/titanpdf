"""
core/hse_defect_tracker.py
──────────────────────────
TRUNG TÂM THEO DÕI & QUẢN LÝ KHẮC PHỤC LỖI TOÀN THỜI GIAN (MASTER DEFECT TRACKER)
Tự động tổng hợp dữ liệu 2 chiều từ:
1. Các đợt kiểm tra trong tab HSE Report (danh sách báo cáo JSON & storage).
2. Dữ liệu Báo Cáo Tháng & baseline defects (extracted_defects.json).
3. Google Apps Script Web App / Google Drive.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import sys
import tempfile
import urllib.parse
import uuid
import zipfile
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.chart import BarChart, DoughnutChart, Reference
from openpyxl.worksheet.datavalidation import DataValidation
from pydantic import BaseModel, Field

from core.cell_image_packager import package_cell_images

logger = logging.getLogger("titanpdf.hse_defect_tracker")

# Project paths
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
HSE_REPORTS_DIR = DATA_DIR / "hse_reports"
OVERRIDES_FILE = DATA_DIR / "hse_defect_tracker_overrides.json"
MASTER_DEFECTS_FILE = DATA_DIR / "hse_master_defects.json"

TRACKER_STATE_FILE = DATA_DIR / "hse_tracker_state.json"
BASE_HSE_DIR = Path(__file__).resolve().parent / "data" / "hse"
EXTRACTED_DEFECTS_JSON = BASE_HSE_DIR / "extracted_defects.json"
EXTRACTED_IMAGES_DIR = BASE_HSE_DIR / "extracted_images"
GAS_CONFIG_FILE = DATA_DIR / "msds_gas_config.json"

DEFAULT_GAS_URL = "https://script.google.com/macros/s/AKfycbzc2q-vTj-8xCykJqEiH8a7rkfaLLpkpl6bOUuvJOBv86a5QpeqzT46twZuuyQkePg/exec"


class DefectUpdatePayload(BaseModel):
    defectId: str
    improved: Optional[bool] = False
    status: Optional[str] = None
    improveDate: Optional[str] = ""
    improve_date: Optional[str] = ""
    note: Optional[str] = ""
    afterImageData: Optional[str] = ""
    date: Optional[str] = ""
    department: Optional[str] = ""
    zh_issue: Optional[str] = ""
    vn_issue: Optional[str] = ""
    img_before: Optional[str] = ""


TOMBSTONES_FILE = DATA_DIR / "hse_tombstones.json"


class HSETombstoneManager:
    """Quản lý các bản ghi đã xóa (Tombstones) để chống phục hồi lại từ file cũ/Git/cache/GAS."""

    @staticmethod
    def load_tombstones() -> Dict[str, Any]:
        if TOMBSTONES_FILE.exists():
            try:
                with open(TOMBSTONES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "deleted_report_ids": [],
            "deleted_report_filenames": [],
            "deleted_defect_ids": [],
            "deleted_source_item_keys": [],
            "cleared_all_defects": False,
            "cleared_all_defects_at": None
        }

    @staticmethod
    def save_tombstones(data: Dict[str, Any]):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(TOMBSTONES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Could not save tombstones: {e}")

    @classmethod
    def add_deleted_report(cls, report_id: str, filename: str = ""):
        tb = cls.load_tombstones()
        rep_ids = set(tb.get("deleted_report_ids", []))
        rep_files = set(tb.get("deleted_report_filenames", []))
        if report_id:
            rep_ids.add(str(report_id).strip())
        if filename:
            rep_files.add(str(filename).strip())
        tb["deleted_report_ids"] = list(rep_ids)
        tb["deleted_report_filenames"] = list(rep_files)
        cls.save_tombstones(tb)

    @classmethod
    def is_report_deleted(cls, report_id: str = "", filename: str = "") -> bool:
        tb = cls.load_tombstones()
        del_ids = [str(x).strip().lower() for x in tb.get("deleted_report_ids", [])]
        del_files = [str(x).strip().lower() for x in tb.get("deleted_report_filenames", [])]
        r_id = str(report_id).strip().lower() if report_id else ""
        f_name = str(filename).strip().lower() if filename else ""
        if r_id and (r_id in del_ids or any(r_id in df for df in del_files)):
            return True
        if f_name and (f_name in del_files or any(f_name in df for df in del_files)):
            return True
        return False

    @classmethod
    def add_deleted_defect(cls, defect_id: str, source_item_key: str = ""):
        tb = cls.load_tombstones()
        def_ids = set(tb.get("deleted_defect_ids", []))
        src_keys = set(tb.get("deleted_source_item_keys", []))
        if defect_id:
            def_ids.add(str(defect_id).strip().upper())
        if source_item_key:
            src_keys.add(str(source_item_key).strip())
        tb["deleted_defect_ids"] = list(def_ids)
        tb["deleted_source_item_keys"] = list(src_keys)
        cls.save_tombstones(tb)

    @classmethod
    def is_defect_deleted(cls, defect_id: str = "", source_item_key: str = "", source_report_id: str = "") -> bool:
        tb = cls.load_tombstones()
        if tb.get("cleared_all_defects") is True:
            return True
        del_def_ids = [str(x).strip().upper() for x in tb.get("deleted_defect_ids", [])]
        if defect_id and str(defect_id).strip().upper() in del_def_ids:
            return True
        if source_item_key and str(source_item_key).strip() in tb.get("deleted_source_item_keys", []):
            return True
        if source_report_id and cls.is_report_deleted(source_report_id):
            return True
        return False

    @classmethod
    def record_clear_all_defects(cls):
        tb = cls.load_tombstones()
        tb["cleared_all_defects"] = True
        tb["cleared_all_defects_at"] = datetime.now().isoformat()
        cls.save_tombstones(tb)

    @classmethod
    def reset_clear_all_for_new_report(cls):
        tb = cls.load_tombstones()
        tb["cleared_all_defects"] = False
        tb["deleted_defect_ids"] = []
        cls.save_tombstones(tb)
        try:
            with open(TRACKER_STATE_FILE, "w", encoding="utf-8") as sf:
                json.dump({"cleared": False, "reset_at": datetime.now().isoformat()}, sf, indent=2)
        except Exception:
            pass


class DefectAggregatorService:
    """Master defect aggregator with 2-way sync, tombstone filtering and persistent caching."""

    @staticmethod
    def get_gas_url() -> str:
        env_url = (os.environ.get("GAS_WEB_APP_URL") or os.environ.get("HSE_GAS_URL") or os.environ.get("MSDS_GAS_URL") or "").strip()
        if env_url and "script.google.com" in env_url:
            return env_url
        if GAS_CONFIG_FILE.exists():
            try:
                with open(GAS_CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    url = cfg.get("webhook_url") or cfg.get("gas_url") or cfg.get("url")
                    if url and "script.google.com" in url and "AKtest" not in url:
                        return url.strip()
            except Exception:
                pass
        return DEFAULT_GAS_URL

    @staticmethod
    def load_overrides() -> Dict[str, Any]:
        if OVERRIDES_FILE.exists():
            try:
                with open(OVERRIDES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not read tracker overrides: {e}")
        return {}

    @staticmethod
    def save_overrides(data: Dict[str, Any]):
        try:
            with open(OVERRIDES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Could not save tracker overrides: {e}")

    @staticmethod
    def clean_text(text: Optional[str]) -> str:
        if not text:
            return ""
        s = str(text).replace("\r", " ").replace("\n", " ")
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @staticmethod
    def normalize_department(dept_zh: str = "", dept_vi: str = "") -> Tuple[str, str, str]:
        s = f"{dept_zh} {dept_vi}".lower()
        if any(k in s for k in ["sản xuất", "san-xuat", "sanxuat", "生产", "xưởng"]):
            return "生产部 / Sản xuất", "san-xuat", "🏭"
        if any(k in s for k in ["kỹ thuật", "ky-thuat", "kythuat", "技术", "lab", "r&d", "rd"]):
            return "技术部 / Kỹ thuật", "ky-thuat", "🔬"
        if any(k in s for k in ["kho", "vận chuyển", "仓储", "kho hàng", "kho-hang", "khovan"]):
            return "仓储部 / Kho hàng", "kho", "📦"
        if any(k in s for k in ["bán hàng", "ban-hang", "kinh doanh", "营业"]):
            return "营业部 / Bán hàng", "ban-hang", "🛒"
        if any(k in s for k in ["bảo trì", "bao-tri", "维修", "cơ điện"]):
            return "维修部 / Bảo trì", "bao-tri", "🔧"
        if any(k in s for k in ["hành chính", "hanh-chinh", "nhân sự", "行政"]):
            return "行政部 / Hành chính", "hanh-chinh", "🏢"
        if any(k in s for k in ["qc", "qa", "chất lượng", "品保"]):
            return "品保部 / QC", "qc", "🔍"
        
        name_zh = dept_zh.strip() or "综合部"
        name_vi = dept_vi.strip() or "Tổng hợp"
        return f"{name_zh} / {name_vi}", "tong-hop", "📋"

    @staticmethod
    def categorize_hse(text: str) -> str:
        t = text.lower()
        if any(k in t for k in ["pccc", "chữa cháy", "bình chữa cháy", "cứu hỏa", "thoát hiểm", "cháy", "消防", "灭火", "疏散"]):
            return "PCCC & Thoát hiểm (消防与疏散)"
        if any(k in t for k in ["hóa chất", "dung môi", "chất thải", "khay tràn", "msds", "sds", "nguy hại", "rò rỉ", "khí độc", "化学品", "危废", "泄漏"]):
            return "An toàn hóa chất & Môi trường (化学品与环保)"
        if any(k in t for k in ["điện", "tủ điện", "dây điện", "ổ cắm", "tiếp địa", "hở điện", "电气", "电线", "配电", "接地"]):
            return "An toàn điện (电气安全)"
        if any(k in t for k in ["che chắn", "curoa", "truyền động", "bảo hộ", "kính", "găng tay", "máy móc", "cơ khí", "机械", "防护", "劳保", "防护罩"]):
            return "Thiết bị cơ khí & Bảo hộ (机械防护与劳保)"
        return "Vệ sinh 5S & Sắp xếp xưởng (现场卫生与5S)"

    @staticmethod
    def normalize_date(raw_date: Any, fallback_filename: str = "") -> Tuple[str, str]:
        """Chuẩn hóa mọi định dạng ngày nhập vào về chuẩn (YYYY-MM-DD, YYYY-MM)."""
        if raw_date:
            s = str(raw_date).split("T")[0].strip()
            m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$", s)
            if m:
                clean = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                return clean, clean[:7]
            m = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$", s)
            if m:
                clean = f"{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
                return clean, clean[:7]
            try:
                ts = float(s)
                if ts > 1000000000000:
                    ts /= 1000.0
                dt = datetime.fromtimestamp(ts)
                clean = dt.strftime("%Y-%m-%d")
                return clean, clean[:7]
            except Exception:
                pass

        if fallback_filename:
            m = re.search(r"(\d{4})[-_](\d{2})[-_](\d{2})", fallback_filename)
            if m:
                clean = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                return clean, clean[:7]
            m = re.search(r"hse_(\d{10,13})", fallback_filename)
            if m:
                try:
                    ts = float(m.group(1))
                    if ts > 1000000000000:
                        ts /= 1000.0
                    dt = datetime.fromtimestamp(ts)
                    clean = dt.strftime("%Y-%m-%d")
                    return clean, clean[:7]
                except Exception:
                    pass

        today = datetime.now().strftime("%Y-%m-%d")
        return today, today[:7]

    @staticmethod
    def clean_image_uri(raw_img: Optional[str]) -> str:
        """Đảm bảo chuỗi ảnh hợp lệ cho thẻ <img> trình duyệt."""
        if not raw_img:
            return ""
        s = str(raw_img).strip()
        if s.startswith("http://") or s.startswith("https://") or s.startswith("/api/"):
            return s
        if s.startswith("data:image/"):
            return s
        if len(s) > 50:
            return f"data:image/jpeg;base64,{s}"
        return s

    @classmethod
    def reconcile_all_reports_to_tracker(cls) -> Dict[str, Any]:
        """Quét và hòa giải toàn bộ vi phạm từ data/hse_reports vào Tracker (tôn trọng tombstones)."""
        logger.info("[HSE_TRACKER] Chạy quét & hòa giải báo cáo vào Defect Tracker...")
        data = cls.aggregate_all_defects(force_reconcile=True)
        return {
            "success": True,
            "total_defects": data.get("total", 0),
            "kpis": data.get("kpis", {}),
            "available_months": data.get("available_months", []),
            "message": f"Đã hòa giải thành công {data.get('total', 0)} sự cố hợp lệ."
        }

    @classmethod
    def sync_report_to_defect_tracker(cls, report_data: Dict[str, Any], filename: str = "") -> Dict[str, Any]:
        """Tự động đồng bộ tức thì khi lưu hoặc cập nhật báo cáo trong HSE Report Studio."""
        # Khi lưu báo cáo mới, gỡ cờ cleared để sự cố của báo cáo mới được hiển thị
        HSETombstoneManager.reset_clear_all_for_new_report()

        rep_mode = report_data.get("reportType") or report_data.get("mode", "inspection")
        rep_id = report_data.get("id") or (filename.replace(".json", "") if filename else "")

        # Xử lý báo cáo Phục Tra Cải Thiện
        if rep_mode == "improvement":
            meta = report_data.get("metadata", {})
            orig_id = meta.get("originalReportId") or report_data.get("originalReportId")
            raw_d = meta.get("date") or report_data.get("date")
            clean_d, _ = cls.normalize_date(raw_d, filename)

            overrides = cls.load_overrides()
            findings = report_data.get("findings", [])
            for f_idx, f in enumerate(findings, 1):
                if f.get("improved") or f.get("imageAfterData"):
                    orig_f_id = f.get("originalFindingId") or f.get("id") or f"finding_{f_idx}"
                    if orig_id:
                        target_key = f"{orig_id}_{orig_f_id}"
                        ov = overrides.setdefault(target_key, {})
                        ov["improved"] = True
                        ov["improve_date"] = clean_d
                        if f.get("imageAfterData"):
                            ov["img_after"] = cls.clean_image_uri(f.get("imageAfterData"))
                        if f.get("note") or f.get("suggestion"):
                            ov["note"] = f.get("note") or f.get("suggestion")
            cls.save_overrides(overrides)

        return cls.aggregate_all_defects(force_reconcile=True)

    @classmethod
    def remove_report_from_defect_tracker(cls, report_identifier: str) -> Dict[str, Any]:
        """Gỡ bỏ các sự cố thuộc báo cáo bị xóa khỏi Defect Tracker và ghi nhận Tombstone."""
        rep_stem = report_identifier.replace(".json", "")
        HSETombstoneManager.add_deleted_report(rep_stem, report_identifier)

        # Xóa các overrides liên quan
        overrides = cls.load_overrides()
        keys_to_remove = [k for k in overrides if rep_stem in k]
        for k in keys_to_remove:
            del overrides[k]
        if keys_to_remove:
            cls.save_overrides(overrides)

        return cls.aggregate_all_defects(force_reconcile=True)

    @classmethod
    def delete_single_defect(cls, defect_id: str) -> Dict[str, Any]:
        """Xóa vĩnh viễn 1 sự cố khỏi Master Defect Tracker, Overrides và Google Sheet."""
        code = str(defect_id).strip()
        all_data = cls.aggregate_all_defects(force_reconcile=True)
        matched = next((d for d in all_data["defects"] if d.get("code") == code or d.get("id") == code), None)

        src_key = matched.get("source_item_key", "") if matched else ""
        HSETombstoneManager.add_deleted_defect(code, src_key)

        # Xóa override
        overrides = cls.load_overrides()
        changed = False
        if code in overrides:
            del overrides[code]
            changed = True
        if src_key and src_key in overrides:
            del overrides[src_key]
            changed = True
        if changed:
            cls.save_overrides(overrides)

        # Xóa khỏi MASTER_DEFECTS_FILE nếu có
        if MASTER_DEFECTS_FILE.exists():
            try:
                with open(MASTER_DEFECTS_FILE, "r", encoding="utf-8") as mf:
                    m_list = json.load(mf)
                m_list = [d for d in m_list if d.get("code") != code and d.get("id") != code and d.get("source_item_key") != src_key]
                with open(MASTER_DEFECTS_FILE, "w", encoding="utf-8") as mf:
                    json.dump(m_list, mf, ensure_ascii=False, indent=2)
            except Exception as ex:
                logger.warning(f"Error removing defect from master file: {ex}")

        # Gửi lệnh xóa lên Google Apps Script
        gas_url = cls.get_gas_url()
        try:
            gas_payload = {
                "action": "deleteDefect",
                "defectId": code,
                "code": code,
                "timestamp": datetime.now().isoformat()
            }
            requests.post(
                gas_url,
                data=json.dumps(gas_payload, ensure_ascii=False),
                headers={"Content-Type": "text/plain;charset=utf-8"},
                allow_redirects=True,
                timeout=5.0
            )
        except Exception:
            pass

        return cls.aggregate_all_defects(force_reconcile=True)

    @classmethod
    def clear_all_defects(cls) -> Dict[str, Any]:
        """Xóa vĩnh viễn toàn bộ sự cố lỗi HSE Tracker, lưu Tombstone và xóa Google Sheet."""
        # 1. Đặt cờ cleared trong Tombstones và Tracker State
        HSETombstoneManager.record_clear_all_defects()
        try:
            with open(TRACKER_STATE_FILE, "w", encoding="utf-8") as sf:
                json.dump({"cleared": True, "cleared_at": datetime.now().isoformat()}, sf, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Could not write tracker state file: {e}")

        # 2. Xóa sạch file overrides & master defects
        try:
            with open(OVERRIDES_FILE, "w", encoding="utf-8") as of:
                json.dump({}, of, ensure_ascii=False, indent=2)
            if MASTER_DEFECTS_FILE.exists():
                with open(MASTER_DEFECTS_FILE, "w", encoding="utf-8") as mf:
                    json.dump([], mf, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Could not clear overrides/master file: {e}")

        # 3. Gửi lệnh xóa sạch lên Google Apps Script (hỗ trợ cả script mới lẫn script cũ)
        gas_url = cls.get_gas_url()
        for act in ["clearAllDefects", "clearAll"]:
            try:
                gas_payload = {
                    "action": act,
                    "timestamp": datetime.now().isoformat()
                }
                requests.post(
                    gas_url,
                    data=json.dumps(gas_payload, ensure_ascii=False),
                    headers={"Content-Type": "text/plain;charset=utf-8"},
                    allow_redirects=True,
                    timeout=5.0
                )
            except Exception:
                pass

        return {
            "success": True,
            "message": "Đã xóa sạch toàn bộ sự cố HSE Tracker thành công!",
            "cleared": True,
            "total": 0,
            "defects": [],
            "available_months": [],
            "available_departments": [],
            "kpis": {"total": 0, "improved": 0, "pending": 0, "rate": 0.0}
        }

    @classmethod
    def aggregate_all_defects(
        cls,
        month_filter: Optional[str] = None,
        dept_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        force_reconcile: bool = False
    ) -> Dict[str, Any]:
        """Tổng hợp danh sách sự cố Master Defect Tracker (tôn trọng 100% Tombstones)."""
        tb = HSETombstoneManager.load_tombstones()

        # Nếu người dùng đã xóa tất cả, trả về rỗng TUYỆT ĐỐI không tự ý phục hồi
        if tb.get("cleared_all_defects") is True:
            cleared_at = tb.get("cleared_all_defects_at") or ""
            has_new_reports = False
            for f in HSE_REPORTS_DIR.glob("*.json"):
                if HSETombstoneManager.is_report_deleted(f.stem, f.name):
                    continue
                try:
                    f_mtime = datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                    if not cleared_at or f_mtime > cleared_at:
                        has_new_reports = True
                        break
                except Exception:
                    pass

            if not has_new_reports:
                return {
                    "total": 0,
                    "defects": [],
                    "available_months": [],
                    "available_departments": [],
                    "kpis": {"total": 0, "improved": 0, "pending": 0, "rate": 0.0}
                }

        overrides = cls.load_overrides()
        baseline_defects: List[Dict[str, Any]] = []

        # Nguồn 1: Sự cố nền tháng 09/2026 (chỉ nạp nếu chưa bị xóa)
        if not tb.get("cleared_all_defects") and EXTRACTED_DEFECTS_JSON.exists():
            try:
                with open(EXTRACTED_DEFECTS_JSON, "r", encoding="utf-8") as jf:
                    extracted = json.load(jf)

                img_map = [
                    "p5_img2_IM48.jpg", "p5_img3_IM49.jpg", "p6_img2_IM52.jpg", "p6_img3_IM53.jpg",
                    "p7_img2_IM56.jpg", "p7_img3_IM57.jpg", "p8_img2_IM60.jpg", "p8_img3_IM61.jpg",
                    "p9_img2_IM64.jpg", "p9_img3_IM65.jpg", "p10_img2_IM68.jpg", "p10_img3_IM69.jpg",
                    "p11_img2_IM72.jpg", "p11_img3_IM73.jpg", "p12_img2_IM76.jpg", "p12_img3_IM77.jpg",
                    "p13_img2_IM80.jpg"
                ]

                for idx, item in enumerate(extracted, 1):
                    code = f"DEF-202609-{idx:02d}"
                    src_key = f"baseline_202609_{idx}"
                    if HSETombstoneManager.is_defect_deleted(code, src_key, "hse_report_2026_09"):
                        continue

                    dept_full, dept_k, dept_icon = cls.normalize_department(item.get("zh_dept", ""), item.get("vn_dept", ""))
                    zh_issue = cls.clean_text(item.get("zh_issue", ""))
                    vn_issue = cls.clean_text(item.get("vn_issue", ""))
                    cat = cls.categorize_hse(f"{zh_issue} {vn_issue}")

                    img_name = img_map[idx - 1] if idx - 1 < len(img_map) else ""
                    img_path = f"/api/hse/defect_image/2026-09/{img_name}" if img_name else ""

                    is_improved = (idx == 1)
                    improve_d = "2026-10-21" if is_improved else ""
                    note_val = "Đã dọn dẹp và sắp xếp gọn gàng mẫu thí nghiệm đúng nơi quy định" if is_improved else ""

                    defect_obj = {
                        "id": code,
                        "code": code,
                        "date": item.get("date", "2026-09-30"),
                        "month": "2026-09",
                        "department": dept_full,
                        "dept_key": dept_k,
                        "dept_icon": dept_icon,
                        "category": cat,
                        "zh_issue": zh_issue,
                        "vn_issue": vn_issue,
                        "status": "Cải thiện / 已改善" if is_improved else "Chưa cải thiện / 未改善",
                        "improved": is_improved,
                        "improve_date": improve_d,
                        "note": note_val,
                        "img_before": img_path,
                        "img_after": "",
                        "drive_direct_url": "",
                        "drive_view_url": "",
                        "source_type": "baseline",
                        "source_file": "extracted_defects.json",
                        "source_report_id": "hse_report_2026_09",
                        "source_item_key": src_key,
                        "report_id": "hse_report_2026_09"
                    }
                    baseline_defects.append(defect_obj)
            except Exception as e:
                logger.warning(f"Error loading extracted baseline defects: {e}")

        # Nguồn 2: Toàn bộ báo cáo đã lưu trong data/hse_reports/*.json
        inspection_findings: List[Dict[str, Any]] = []
        improvement_records: List[Tuple[str, Dict[str, Any]]] = []

        if HSE_REPORTS_DIR.exists():
            for report_file in sorted(HSE_REPORTS_DIR.glob("*.json")):
                if HSETombstoneManager.is_report_deleted(report_file.stem, report_file.name):
                    continue

                try:
                    with open(report_file, "r", encoding="utf-8") as rf:
                        rep = json.load(rf)

                    rep_id = rep.get("id") or report_file.stem
                    if HSETombstoneManager.is_report_deleted(rep_id, report_file.name):
                        continue

                    rep_mode = rep.get("reportType") or rep.get("mode", "inspection")
                    if rep_mode == "improvement":
                        improvement_records.append((report_file.name, rep))
                        continue

                    meta = rep.get("metadata", {})
                    raw_date = meta.get("date") or rep.get("date")
                    rep_date, rep_month = cls.normalize_date(raw_date, report_file.name)

                    # Bóc tách hạng mục vi phạm từ findings
                    findings = rep.get("findings", [])
                    for f_idx, f in enumerate(findings, 1):
                        f_id = f.get("id") or f"finding_{f_idx}"
                        source_item_key = f"{rep_id}_{f_id}"

                        if HSETombstoneManager.is_defect_deleted("", source_item_key, rep_id):
                            continue

                        zh_issue = cls.clean_text(f.get("issueZh") or f.get("suggestion") or "")
                        vn_issue = cls.clean_text(f.get("issueVi") or "")
                        img_b = cls.clean_image_uri(f.get("imageData") or f.get("driveDirectUrl") or f.get("driveViewUrl") or "")
                        img_a = cls.clean_image_uri(f.get("imageAfterData") or f.get("afterDriveDirectUrl") or f.get("afterDriveViewUrl") or "")

                        if not zh_issue and not vn_issue and not img_b:
                            continue

                        dept_full, dept_k, dept_icon = cls.normalize_department(
                            f.get("departmentZh", "") or meta.get("departmentZh", ""),
                            f.get("departmentVi", "") or meta.get("departmentVi", "")
                        )
                        cat = cls.categorize_hse(f"{zh_issue} {vn_issue}")
                        is_improved = bool(f.get("improved", False))

                        finding_obj = {
                            "source_report_id": rep_id,
                            "source_item_key": source_item_key,
                            "date": rep_date,
                            "month": rep_month,
                            "f_idx": f_idx,
                            "finding_id": f_id,
                            "department": dept_full,
                            "dept_key": dept_k,
                            "dept_icon": dept_icon,
                            "category": cat,
                            "zh_issue": zh_issue,
                            "vn_issue": vn_issue,
                            "status": "Cải thiện / 已改善" if is_improved else "Chưa cải thiện / 未改善",
                            "improved": is_improved,
                            "improve_date": f.get("recheckDate") or (rep_date if is_improved else ""),
                            "note": f.get("note") or f.get("suggestion") or "",
                            "img_before": img_b,
                            "img_after": img_a,
                            "drive_direct_url": f.get("driveDirectUrl") or "",
                            "drive_view_url": f.get("driveViewUrl") or "",
                            "after_drive_direct_url": f.get("afterDriveDirectUrl") or "",
                            "after_drive_view_url": f.get("afterDriveViewUrl") or "",
                            "source_type": "hse_report",
                            "source_file": report_file.name,
                            "report_id": rep_id,
                            "mtime": report_file.stat().st_mtime
                        }
                        inspection_findings.append(finding_obj)
                except Exception as e:
                    logger.warning(f"Error parsing report {report_file}: {e}")

        # Hòa giải các báo cáo Phục Tra Cải Thiện
        for imp_filename, imp_rep in improvement_records:
            if HSETombstoneManager.is_report_deleted(imp_rep.get("id", ""), imp_filename):
                continue
            imp_meta = imp_rep.get("metadata", {})
            orig_id = imp_meta.get("originalReportId") or imp_rep.get("originalReportId")
            imp_raw_date = imp_meta.get("date") or imp_rep.get("date")
            imp_date, _ = cls.normalize_date(imp_raw_date, imp_filename)

            for imp_f in imp_rep.get("findings", []):
                if imp_f.get("improved") or imp_f.get("imageAfterData"):
                    matched_defect = None
                    if orig_id:
                        matched_defect = next((
                            d for d in inspection_findings
                            if d["source_report_id"] == orig_id and (
                                d["finding_id"] == imp_f.get("originalFindingId") or
                                d["finding_id"] == imp_f.get("id")
                            )
                        ), None)
                    if not matched_defect:
                        v_txt = cls.clean_text(imp_f.get("issueVi") or "")
                        z_txt = cls.clean_text(imp_f.get("issueZh") or "")
                        matched_defect = next((
                            d for d in inspection_findings
                            if (v_txt and d["vn_issue"] == v_txt) or (z_txt and d["zh_issue"] == z_txt)
                        ), None)

                    if matched_defect:
                        matched_defect["improved"] = True
                        matched_defect["status"] = "Cải thiện / 已改善"
                        if imp_f.get("imageAfterData"):
                            matched_defect["img_after"] = cls.clean_image_uri(imp_f.get("imageAfterData"))
                        matched_defect["improve_date"] = imp_date
                        if imp_f.get("note"):
                            matched_defect["note"] = imp_f["note"]

        # Đánh mã DEF-YYYYMM-XX tuần tự, chuẩn hóa theo từng tháng
        by_month: Dict[str, List[Dict[str, Any]]] = {}
        for d in inspection_findings:
            m = d["month"]
            by_month.setdefault(m, []).append(d)

        coded_report_defects: List[Dict[str, Any]] = []
        for m, d_list in sorted(by_month.items()):
            d_list.sort(key=lambda x: (x["date"], x["source_report_id"], x["f_idx"]))
            month_compact = m.replace("-", "")
            for seq, item in enumerate(d_list, 1):
                code = f"DEF-{month_compact}-{seq:02d}"
                item["id"] = code
                item["code"] = code
                if not HSETombstoneManager.is_defect_deleted(code, item.get("source_item_key"), item.get("source_report_id")):
                    coded_report_defects.append(item)

        # Nguồn 0: Master Defects từ file Tổng hợp lỗi (MASTER_DEFECTS_FILE)
        master_defects: List[Dict[str, Any]] = []
        if not tb.get("cleared_all_defects") and MASTER_DEFECTS_FILE.exists():
            try:
                with open(MASTER_DEFECTS_FILE, "r", encoding="utf-8") as mf:
                    raw_master = json.load(mf)
                for item in raw_master:
                    code = item.get("code") or item.get("id")
                    if not HSETombstoneManager.is_defect_deleted(code, item.get("source_item_key", ""), item.get("source_report_id", "")):
                        master_defects.append(dict(item))
            except Exception as e:
                logger.warning(f"Error loading master defects from {MASTER_DEFECTS_FILE}: {e}")

        if master_defects:
            master_months = {d.get("month") for d in master_defects if d.get("month")}
            non_master_report_defects = [d for d in coded_report_defects if d.get("month") not in master_months]
            raw_defects = master_defects + non_master_report_defects
        else:
            has_september_report = any(d.get("month") == "2026-09" for d in coded_report_defects)
            if has_september_report:
                raw_defects = coded_report_defects
            else:
                raw_defects = baseline_defects + coded_report_defects

        # Lọc lại lần cuối theo Tombstones
        final_defects: List[Dict[str, Any]] = []
        for d in raw_defects:
            c = d.get("code") or d.get("id")
            sk = d.get("source_item_key", "")
            s_rep = d.get("source_report_id", "")
            if not HSETombstoneManager.is_defect_deleted(c, sk, s_rep):
                final_defects.append(d)

        raw_defects = final_defects

        # Áp dụng ghi đè người dùng (Overrides) theo source_item_key và code
        for d in raw_defects:
            ov = overrides.get(d.get("source_item_key")) or overrides.get(d.get("code"))
            if ov:
                if "improved" in ov:
                    d["improved"] = bool(ov["improved"])
                if ov.get("status"):
                    d["status"] = "Cải thiện" if "cải thiện" in str(ov["status"]).lower() and "chưa" not in str(ov["status"]).lower() else "Chưa cải thiện"
                else:
                    d["status"] = "Cải thiện" if d.get("improved") else "Chưa cải thiện"
                if ov.get("improve_date") is not None:
                    d["improve_date"] = ov["improve_date"]
                if ov.get("note") is not None:
                    d["note"] = ov["note"]
                if ov.get("img_after"):
                    d["img_after"] = cls.clean_image_uri(ov["img_after"])
                if ov.get("img_before"):
                    d["img_before"] = cls.clean_image_uri(ov["img_before"])
                if ov.get("vn_issue"):
                    d["vn_issue"] = ov["vn_issue"]
                if ov.get("zh_issue"):
                    d["zh_issue"] = ov["zh_issue"]
                if ov.get("department"):
                    d["department"] = ov["department"]
            else:
                d["status"] = "Cải thiện" if d.get("improved") else "Chưa cải thiện"

        # Sắp xếp danh sách: Tháng mới nhất lên đầu, trong cùng tháng mã tăng dần (DEF-YYYYMM-01, 02...)
        raw_defects.sort(key=lambda x: (
            -int((x.get("month") or "2026-09").replace("-", "") or 0),
            x.get("order_idx") if x.get("order_idx") is not None else 999,
            x.get("code") or ""
        ))

        # Thu thập danh mục tháng & bộ phận khả dụng
        available_months = sorted(list({d.get("month") for d in raw_defects if d.get("month")}), reverse=True)
        available_depts = sorted(list({d.get("department") for d in raw_defects if d.get("department")}))

        # Lọc danh sách theo yêu cầu
        filtered = raw_defects
        if month_filter and month_filter != "all":
            filtered = [d for d in filtered if d.get("month") == month_filter]
        if dept_filter and dept_filter != "all":
            filtered = [d for d in filtered if d.get("department") == dept_filter or d.get("dept_key") == dept_filter]
        if status_filter and status_filter != "all":
            if status_filter in ["improved", "done", "da-cai-thien"]:
                filtered = [d for d in filtered if d.get("improved")]
            elif status_filter in ["pending", "cho-xu-ly"]:
                filtered = [d for d in filtered if not d.get("improved")]
        if search_query and search_query.strip():
            sq = search_query.strip().lower()
            filtered = [
                d for d in filtered
                if sq in d.get("code", "").lower()
                or sq in d.get("zh_issue", "").lower()
                or sq in d.get("vn_issue", "").lower()
                or sq in d.get("department", "").lower()
                or sq in d.get("category", "").lower()
            ]

        # Tính toán KPIs
        total_items = len(filtered)
        improved_items = sum(1 for d in filtered if d.get("improved"))
        pending_items = total_items - improved_items
        completion_rate = round((improved_items / total_items) * 100, 1) if total_items > 0 else 0.0

        return {
            "defects": filtered,
            "total": total_items,
            "kpis": {
                "total": total_items,
                "improved": improved_items,
                "pending": pending_items,
                "rate": completion_rate
            },
            "available_months": available_months,
            "available_departments": available_depts,
            "global_counts": {
                "all": len(raw_defects),
                "improved": sum(1 for d in raw_defects if d.get("improved")),
                "pending": sum(1 for d in raw_defects if not d.get("improved")),
                "rate": round((sum(1 for d in raw_defects if d.get("improved")) / len(raw_defects) * 100), 1) if raw_defects else 0.0
            }
        }

    @classmethod
    def add_defect(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Thêm mới một sự cố HSE vào hệ thống Master Tracker."""
        raw_date = str(payload.get("date") or datetime.now().strftime("%Y-%m-%d")).strip()
        month = raw_date[:7] if len(raw_date) >= 7 else datetime.now().strftime("%Y-%m")
        month_compact = month.replace("-", "")

        # Tải danh sách hiện tại để xác định index tiếp theo
        current_data = cls.aggregate_all_defects()
        existing_defects = current_data.get("defects", [])
        month_defects = [d for d in existing_defects if d.get("month") == month]
        next_seq = len(month_defects) + 1

        code = f"DEF-{month_compact}-{next_seq:02d}"
        all_codes = {d.get("code") for d in existing_defects}
        while code in all_codes:
            next_seq += 1
            code = f"DEF-{month_compact}-{next_seq:02d}"

        dept_val = str(payload.get("department") or "HSE / An toàn Môi trường").strip()
        dept_full, dept_k, dept_icon = cls.normalize_department(dept_val, dept_val)
        zh_issue = cls.clean_text(payload.get("zh_issue") or "")
        vn_issue = cls.clean_text(payload.get("vn_issue") or "")
        img_b = cls.clean_image_uri(payload.get("img_before") or payload.get("imageData") or "")
        status_val = str(payload.get("status") or "Chưa cải thiện").strip()
        is_improved = ("cải thiện" in status_val.lower() and "chưa" not in status_val.lower()) or bool(payload.get("improved"))
        improve_date = payload.get("improve_date") or (datetime.now().strftime("%Y-%m-%d") if is_improved else "")

        new_defect = {
            "id": code,
            "code": code,
            "date": raw_date,
            "month": month,
            "department": dept_full,
            "dept_key": dept_k,
            "dept_icon": dept_icon,
            "category": cls.categorize_hse(f"{zh_issue} {vn_issue}"),
            "zh_issue": zh_issue,
            "vn_issue": vn_issue,
            "status": "Cải thiện" if is_improved else "Chưa cải thiện",
            "improved": is_improved,
            "improve_date": improve_date if is_improved else "",
            "img_before": img_b,
            "img_after": "",
            "source_type": "user_created",
            "order_idx": next_seq
        }

        # Lưu vào MASTER_DEFECTS_FILE
        master_list = []
        if MASTER_DEFECTS_FILE.exists():
            try:
                with open(MASTER_DEFECTS_FILE, "r", encoding="utf-8") as mf:
                    master_list = json.load(mf)
            except Exception:
                master_list = []
        master_list.append(new_defect)
        with open(MASTER_DEFECTS_FILE, "w", encoding="utf-8") as mf:
            json.dump(master_list, mf, ensure_ascii=False, indent=2)

        return {"success": True, "defect": new_defect, "message": f"Đã thêm thành công sự cố {code}!"}

    @classmethod
    def update_defect(cls, payload: DefectUpdatePayload) -> Dict[str, Any]:
        """Cập nhật trạng thái sự cố và đồng bộ 2 chiều ngược về file báo cáo gốc & Google Apps Script."""
        code = payload.defectId
        is_imp = bool(payload.improved)
        if payload.status:
            is_imp = ("cải thiện" in str(payload.status).lower() and "chưa" not in str(payload.status).lower())
        
        now_str = payload.improveDate or payload.improve_date or (datetime.now().strftime("%Y-%m-%d") if is_imp else "")

        # 1. Tra cứu thông tin sự cố hiện tại
        all_data = cls.aggregate_all_defects(force_reconcile=True)
        matched = next((d for d in all_data["defects"] if d.get("code") == code or d.get("id") == code or d.get("source_item_key") == code), None)

        # 2. Cập nhật persistent overrides cache (lưu cả code lẫn source_item_key)
        overrides = cls.load_overrides()
        keys_to_update = [code]
        if matched and matched.get("source_item_key"):
            keys_to_update.append(matched["source_item_key"])

        for k in keys_to_update:
            item_ov = overrides.get(k, {})
            item_ov["improved"] = is_imp
            item_ov["status"] = "Cải thiện" if is_imp else "Chưa cải thiện"
            item_ov["improve_date"] = now_str if is_imp else ""
            if payload.note is not None:
                item_ov["note"] = payload.note
            if payload.afterImageData:
                item_ov["img_after"] = cls.clean_image_uri(payload.afterImageData)
            if payload.vn_issue:
                item_ov["vn_issue"] = payload.vn_issue
            if payload.zh_issue:
                item_ov["zh_issue"] = payload.zh_issue
            if payload.department:
                item_ov["department"] = payload.department
            if payload.date:
                item_ov["date"] = payload.date
            if payload.img_before:
                item_ov["img_before"] = cls.clean_image_uri(payload.img_before)
            overrides[k] = item_ov

        cls.save_overrides(overrides)

        # Cập nhật trực tiếp vào MASTER_DEFECTS_FILE nếu có
        if MASTER_DEFECTS_FILE.exists():
            try:
                with open(MASTER_DEFECTS_FILE, "r", encoding="utf-8") as mf:
                    m_list = json.load(mf)
                m_changed = False
                for item in m_list:
                    if item.get("code") == code or item.get("id") == code:
                        item["improved"] = is_imp
                        item["status"] = "Cải thiện" if is_imp else "Chưa cải thiện"
                        item["improve_date"] = now_str if is_imp else ""
                        if payload.note is not None:
                            item["note"] = payload.note
                        if payload.afterImageData:
                            item["img_after"] = cls.clean_image_uri(payload.afterImageData)
                        if payload.vn_issue:
                            item["vn_issue"] = payload.vn_issue
                        if payload.zh_issue:
                            item["zh_issue"] = payload.zh_issue
                        if payload.department:
                            dept_f, dept_k, dept_ic = cls.normalize_department(payload.department, payload.department)
                            item["department"] = dept_f
                            item["dept_key"] = dept_k
                            item["dept_icon"] = dept_ic
                        if payload.date:
                            item["date"] = payload.date
                            item["month"] = payload.date[:7] if len(payload.date) >= 7 else item.get("month", "2026-09")
                        if payload.img_before:
                            item["img_before"] = cls.clean_image_uri(payload.img_before)
                        m_changed = True
                        break
                if m_changed:
                    with open(MASTER_DEFECTS_FILE, "w", encoding="utf-8") as mf:
                        json.dump(m_list, mf, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"Error updating master defect file: {e}")

        # 3. Đồng bộ ngược vào file JSON báo cáo gốc nếu sự cố bắt nguồn từ báo cáo
        if matched and matched.get("source_file"):
            source_file_path = HSE_REPORTS_DIR / matched["source_file"]
            if source_file_path.exists():
                try:
                    with open(source_file_path, "r", encoding="utf-8") as jf:
                        rep_data = json.load(jf)

                    changed = False
                    finding_id = matched.get("finding_id")
                    if "findings" in rep_data:
                        for f_idx, f in enumerate(rep_data["findings"], 1):
                            if f.get("id") == finding_id or f_idx == matched.get("f_idx"):
                                f["improved"] = payload.improved
                                f["recheckDate"] = now_str if payload.improved else ""
                                if payload.note is not None:
                                    f["note"] = payload.note
                                if payload.afterImageData:
                                    f["imageAfterData"] = payload.afterImageData
                                changed = True
                                break

                    if changed:
                        with open(source_file_path, "w", encoding="utf-8") as jf:
                            json.dump(rep_data, jf, ensure_ascii=False, indent=2)
                        logger.info(f"[HSE_TRACKER] Đã đồng bộ ngược trạng thái cải thiện vào {matched['source_file']}")
                except Exception as sync_err:
                    logger.warning(f"Lỗi khi đồng bộ ngược vào báo cáo gốc: {sync_err}")

        # 4. Gửi tín hiệu đẩy lên Google Apps Script Web App
        gas_synced = False
        gas_url = cls.get_gas_url()
        try:
            gas_payload = {
                "action": "updateDefect",
                "defectId": code,
                "improved": payload.improved,
                "improveDate": now_str if payload.improved else "",
                "note": payload.note or "",
                "timestamp": datetime.now().isoformat()
            }
            res = requests.post(
                gas_url,
                data=json.dumps(gas_payload, ensure_ascii=False),
                headers={"Content-Type": "text/plain;charset=utf-8"},
                allow_redirects=True,
                timeout=5.0
            )
            if res.ok:
                gas_synced = True
        except Exception:
            pass

        return {
            "success": True,
            "defectId": code,
            "improved": payload.improved,
            "improveDate": now_str if payload.improved else "",
            "gas_synced": gas_synced
        }

    @classmethod
    def sync_with_gas(cls, custom_gas_url: Optional[str] = None) -> Dict[str, Any]:
        """Manually triggers two-way sync with Google Apps Script Web App."""
        gas_url = (custom_gas_url or "").strip() or cls.get_gas_url()
        remote_count = 0
        status_msg = "Chưa kết nối GAS"
        is_html = False

        headers = {
            "Accept": "application/json",
            "User-Agent": "TitanPDF-HSE-Tracker/1.0"
        }

        try:
            r = requests.get(f"{gas_url}?action=getAllDefects", headers=headers, timeout=12.0)
            if r.ok:
                content_type = r.headers.get("Content-Type", "")
                text_preview = (r.text or "").strip()
                if "html" in content_type.lower() or text_preview.startswith("<!doctype html") or "<html" in text_preview[:200].lower():
                    is_html = True
                    status_msg = "Google Apps Script phản hồi HTML (Yêu cầu đăng nhập). Vui lòng Deploy Web App với quyền 'Who has access' (Ai có quyền truy cập) là 'Anyone' (Bất kỳ ai)."
                else:
                    try:
                        data = r.json()
                        if isinstance(data, dict) and "defects" in data:
                            items = data["defects"]
                            remote_count = len(items)
                            status_msg = f"Đã đồng bộ thành công {remote_count} lỗi từ Google Apps Script!"
                        elif isinstance(data, list):
                            remote_count = len(data)
                            status_msg = f"Đã đồng bộ thành công {remote_count} lỗi từ Google Apps Script!"
                        elif isinstance(data, dict) and data.get("status") == "error":
                            status_msg = f"Lỗi GAS: {data.get('error', 'Lỗi không xác định')}"
                        elif isinstance(data, dict) and data.get("status") == "ok":
                            status_msg = f"Đã kết nối thành công với Google Apps Script Web App! Cổng API hoạt động chuẩn xác."
                    except Exception:
                        status_msg = "Google Apps Script không trả về định dạng JSON hợp lệ."
            else:
                status_msg = f"Mã phản hồi từ Google Apps Script: {r.status_code}"
        except Exception as e:
            status_msg = f"Lỗi kết nối GAS: {str(e)}"

        tb = HSETombstoneManager.load_tombstones()
        if tb.get("cleared_all_defects") is True:
            # Nếu hệ thống đang ở trạng thái đã xóa sạch, lập tức đè lệnh xóa lên GAS
            try:
                for act in ["clearAllDefects", "clearAll"]:
                    requests.post(
                        gas_url,
                        data=json.dumps({"action": act, "timestamp": datetime.now().isoformat()}, ensure_ascii=False),
                        headers={"Content-Type": "text/plain;charset=utf-8"},
                        allow_redirects=True,
                        timeout=5.0
                    )
            except Exception:
                pass
            return {
                "success": not is_html,
                "message": "Đã đồng bộ GAS: Hệ thống đang ở trạng thái đã xóa sạch (0 lỗi).",
                "is_html": is_html,
                "gas_url": gas_url,
                "remote_defects_count": 0,
                "total_local_defects": 0,
                "kpis": {"total": 0, "improved": 0, "pending": 0, "rate": 0.0}
            }

        all_defects = cls.aggregate_all_defects(force_reconcile=False)
        return {
            "success": not is_html and remote_count >= 0,
            "message": status_msg,
            "is_html": is_html,
            "gas_url": gas_url,
            "remote_defects_count": remote_count,
            "total_local_defects": all_defects["total"],
            "kpis": all_defects["kpis"]
        }

    @classmethod
    def import_master_excel(cls, file_bytes: bytes) -> Dict[str, Any]:
        """
        Nhập và đồng bộ dữ liệu từ tệp Master Excel (ví dụ Tổng hợp lỗi tháng 9 2026.xlsx) lên hệ thống:
        - Bóc tách 100% ảnh nhúng từ xl/cellimages.xml (WPS _xlfn.DISPIMG) và drawings.
        - Đọc chính xác 7 cột từ Row 5 trở đi theo đúng thứ tự bản ghi.
        - Lưu vào MASTER_DEFECTS_FILE và đồng bộ.
        """
        import openpyxl
        buf = io.BytesIO(file_bytes)
        wb = openpyxl.load_workbook(buf, data_only=True)

        target_sheet = None
        for sname in wb.sheetnames:
            if any(k in sname.lower() for k in ["tổng hợp", "tong hop", "tat ca", "all", "lỗi", "sheet1"]):
                target_sheet = wb[sname]
                break
        if not target_sheet:
            target_sheet = wb.active

        # Trích xuất ảnh nhúng từ cellimages.xml nếu có
        cell_images_map: Dict[str, str] = {}
        try:
            buf.seek(0)
            with zipfile.ZipFile(buf, 'r') as z:
                if 'xl/cellimages.xml' in z.namelist() and 'xl/_rels/cellimages.xml.rels' in z.namelist():
                    rels_xml = z.read('xl/_rels/cellimages.xml.rels').decode('utf-8', errors='ignore')
                    rid_to_media = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels_xml))
                    cell_xml = z.read('xl/cellimages.xml').decode('utf-8', errors='ignore')
                    name_embed = re.findall(r'<xdr:cNvPr[^>]*name="([^"]+)".*?<a:blip[^>]*r:embed="([^"]+)"', cell_xml, re.DOTALL)
                    uuid_to_rid = dict(name_embed)

                    sheet_filenames = [n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
                    for s_fn in sheet_filenames:
                        sheet_xml = z.read(s_fn).decode('utf-8', errors='ignore')
                        for cell_coord, formula in re.findall(r'<c\s+r="([A-Z0-9]+)"[^>]*>.*?<f>(?:_xlfn\.)?DISPIMG\(&quot;([^&]+)&quot;,1\)</f>', sheet_xml):
                            rid = uuid_to_rid.get(formula)
                            if rid:
                                target_media = rid_to_media.get(rid)
                                if target_media:
                                    if not target_media.startswith('xl/'):
                                        target_media = 'xl/' + target_media.lstrip('/')
                                    if target_media in z.namelist():
                                        media_bytes = z.read(target_media)
                                        b64 = base64.b64encode(media_bytes).decode('utf-8')
                                        ext = "png" if target_media.endswith(".png") else "jpeg"
                                        cell_images_map[cell_coord] = f"data:image/{ext};base64,{b64}"
        except Exception as ex:
            logger.warning(f"Could not extract cell images during import: {ex}")

        # Hỗ trợ ảnh drawing nếu có
        try:
            if hasattr(target_sheet, '_images'):
                for img in target_sheet._images:
                    row = getattr(img.anchor._from, 'row', None)
                    col = getattr(img.anchor._from, 'col', None)
                    if row is not None and col is not None:
                        cell_coord = f"{openpyxl.utils.get_column_letter(col+1)}{row+1}"
                        if cell_coord not in cell_images_map and hasattr(img, '_data'):
                            img_b = img._data()
                            b64 = base64.b64encode(img_b).decode('utf-8')
                            cell_images_map[cell_coord] = f"data:image/jpeg;base64,{b64}"
        except Exception as ex:
            logger.warning(f"Could not extract drawing images: {ex}")

        new_defects = []
        for r in range(5, target_sheet.max_row + 1):
            date_val = str(target_sheet.cell(r, 1).value or "").strip()
            dept_val = str(target_sheet.cell(r, 2).value or "").strip()
            zh_val = str(target_sheet.cell(r, 3).value or "").strip()
            vn_val = str(target_sheet.cell(r, 4).value or "").strip()
            img_formula = str(target_sheet.cell(r, 5).value or "").strip()
            status_val = str(target_sheet.cell(r, 6).value or "").strip()
            improve_date_val = str(target_sheet.cell(r, 7).value or "").strip()

            if not vn_val and not zh_val and not date_val:
                continue

            idx = r - 4
            month_val = date_val[:7] if len(date_val) >= 7 else "2026-09"
            month_compact = month_val.replace("-", "")
            code = f"DEF-{month_compact}-{idx:02d}"

            img_b64 = cell_images_map.get(f"E{r}", "")
            if not img_b64 and 'DISPIMG' in img_formula:
                m = re.search(r'"([^"]+)"', img_formula)
                if m:
                    for c_coord, c_b64 in cell_images_map.items():
                        if c_coord.endswith(str(r)):
                            img_b64 = c_b64
                            break

            is_improved = False
            s_lower = status_val.lower()
            if any(k in s_lower for k in ["cải thiện", "đã cải thiện", "hoàn thành", "已改善", "完成"]):
                if not any(k in s_lower for k in ["chưa", "chờ", "未", "待"]):
                    is_improved = True
            if improve_date_val and improve_date_val.lower() not in ["none", "---", "", "null"]:
                is_improved = True

            clean_status = "Cải thiện" if is_improved else "Chưa cải thiện"
            clean_improve_date = improve_date_val if (is_improved and improve_date_val.lower() not in ["none", "---", "", "null"]) else ""

            dept_full, dept_k, dept_icon = cls.normalize_department(dept_val, dept_val)

            defect_item = {
                "id": code,
                "code": code,
                "date": date_val or "2026-09-30",
                "month": month_val,
                "department": dept_full,
                "dept_key": dept_k,
                "dept_icon": dept_icon,
                "category": cls.categorize_hse(f"{zh_val} {vn_val}"),
                "zh_issue": zh_val,
                "vn_issue": vn_val,
                "status": clean_status,
                "improved": is_improved,
                "improve_date": clean_improve_date,
                "img_before": img_b64,
                "img_after": "",
                "source_type": "imported_master",
                "source_file": "imported.xlsx",
                "order_idx": idx
            }
            new_defects.append(defect_item)

        if new_defects:
            with open(MASTER_DEFECTS_FILE, "w", encoding="utf-8") as mf:
                json.dump(new_defects, mf, ensure_ascii=False, indent=2)
            HSETombstoneManager.reset_clear_all_for_new_report()

        return {
            "success": True,
            "updated_count": len(new_defects),
            "total_rows": len(new_defects),
            "message": f"Đã đồng bộ thành công {len(new_defects)} sự cố và toàn bộ hình ảnh hiện trường từ file Master Excel lên hệ thống!"
        }


# =============================================================================
# Master HSE Excel Exporter (100% Fidelity Matching Reference Template)
# =============================================================================

class MasterHSEExcelExporter:
    """Generates the enterprise master defect tracking spreadsheet matching 100% of the reference template."""

    def __init__(self, font_family: str = "Arial"):
        self.font_family = font_family
        self.thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1")
        )
        self.images_by_cell: Dict[str, Dict[str, Any]] = {}

    def export_master_workbook(self, defects: Optional[List[Dict[str, Any]]] = None) -> openpyxl.Workbook:
        if defects is None:
            data = DefectAggregatorService.aggregate_all_defects()
            defects = data["defects"]

        self.images_by_cell = {}
        wb = openpyxl.Workbook()

        total_items = len(defects)

        # =====================================================================
        # SHEET 1: 📋 Tổng Hợp Tất Cả Lỗi (ACTIVE FORM MATCHING DESKTOP MASTER)
        # =====================================================================
        ws_all = wb.active
        ws_all.title = "📋 Tổng Hợp Tất Cả Lỗi"
        ws_all.sheet_properties.tabColor = "10B981"
        ws_all.views.sheetView[0].showGridLines = True

        # Sheet 1 Banners
        ws_all.merge_cells("A1:G1")
        h1 = ws_all["A1"]
        h1.value = "BẢNG TỔNG HỢP LỖI HSE TOÀN CÔNG TY - 全公司HSE隐患跟踪汇总表"
        h1.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        h1.font = Font(name=self.font_family, size=14, bold=True, color="FFFFFF")
        h1.alignment = Alignment(horizontal="center", vertical="center")
        ws_all.row_dimensions[1].height = 36.0

        ws_all.merge_cells("A2:G2")
        h2 = ws_all["A2"]
        h2.value = "CÔNG TY TNHH VISION NEW MATERIALS VIỆT NAM / 威逊新材料（越南）有限公司"
        h2.fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        h2.font = Font(name=self.font_family, size=10, italic=False, color="FFFFFF")
        h2.alignment = Alignment(horizontal="center", vertical="center")
        ws_all.row_dimensions[2].height = 22.0
        ws_all.row_dimensions[3].height = 10.0

        # Exact 7 Column Headers (Col A..G)
        headers = [
            ("A", "Ngày ghi nhận\n记录日期", 14.0),
            ("B", "Bộ phận\n部门", 24.0),
            ("C", "Mô tả chi tiết (Tiếng Trung)\n详细描述 (中文)", 48.0),
            ("D", "Mô tả chi tiết (Tiếng Việt)\n详细描述 (越南语)", 48.0),
            ("E", "Xem ảnh\n图片预览", 20.0),
            ("F", "Trạng thái\n状态", 18.0),
            ("G", "Ngày cải thiện\n改善日期", 16.0)
        ]

        ws_all.row_dimensions[4].height = 36.0
        for col_l, col_name, width in headers:
            c = ws_all[f"{col_l}4"]
            c.value = col_name
            c.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
            c.font = Font(name=self.font_family, size=10, bold=True, color="FFFFFF")
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border = self.thin_border
            ws_all.column_dimensions[col_l].width = width

        fill_done = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
        font_done = Font(name=self.font_family, size=9.5, bold=True, color="166534")
        fill_pending = PatternFill(start_color="FFEDD5", end_color="FFEDD5", fill_type="solid")
        font_pending = Font(name=self.font_family, size=9.5, bold=True, color="9A3412")

        for idx, item in enumerate(defects, 1):
            r = 4 + idx
            ws_all.row_dimensions[r].height = 75.0

            ws_all[f"A{r}"] = str(item.get("date") or "2026-09-30").strip()
            ws_all[f"B{r}"] = str(item.get("department") or "").strip()

            zh = str(item.get("zh_issue") or "").strip()
            zh = re.sub(r'^(?:问题|隐患|Vấn đề)[:：\s]*', '', zh).strip()
            vn = str(item.get("vn_issue") or "").strip()
            vn = re.sub(r'^(?:Vấn đề|Lỗi|Sự cố)[:：\s]*', '', vn).strip()

            ws_all[f"C{r}"] = zh
            ws_all[f"D{r}"] = vn

            is_improved = bool(item.get("improved")) or (str(item.get("status") or "").strip().lower() in ["cải thiện", "đã cải thiện", "hoàn thành", "已改善"])
            status_text = "Cải thiện" if is_improved else "Chưa cải thiện"
            ws_all[f"F{r}"] = status_text
            ws_all[f"G{r}"] = str(item.get("improve_date") or "").strip()

            # Embedded image in Col E
            img_b = item.get("img_before") or ""
            if img_b and img_b.startswith("data:image"):
                try:
                    header, b64 = img_b.split(",", 1)
                    ext = "png" if "png" in header.lower() else "jpeg"
                    raw_bytes = base64.b64decode(b64)
                    img_uuid = f"ID_{uuid.uuid4().hex.upper()}"
                    self.images_by_cell[f"E{r}"] = {
                        "id": img_uuid,
                        "bytes": raw_bytes,
                        "ext": ext
                    }
                    ws_all[f"E{r}"] = f'=_xlfn.DISPIMG("{img_uuid}",1)'
                except Exception as ex:
                    logger.warning(f"Error decoding img_before for defect {item.get('code')}: {ex}")
                    ws_all[f"E{r}"] = ""
            elif img_b and os.path.exists(img_b):
                try:
                    with open(img_b, "rb") as f_img:
                        raw_bytes = f_img.read()
                    ext = "png" if img_b.lower().endswith(".png") else "jpeg"
                    img_uuid = f"ID_{uuid.uuid4().hex.upper()}"
                    self.images_by_cell[f"E{r}"] = {
                        "id": img_uuid,
                        "bytes": raw_bytes,
                        "ext": ext
                    }
                    ws_all[f"E{r}"] = f'=_xlfn.DISPIMG("{img_uuid}",1)'
                except Exception:
                    ws_all[f"E{r}"] = ""
            else:
                ws_all[f"E{r}"] = ""

            for col_l, _, _ in headers:
                cell = ws_all[f"{col_l}{r}"]
                cell.font = Font(name=self.font_family, size=9.5)
                cell.border = self.thin_border
                if col_l in ["A", "G"]:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif col_l == "B":
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                elif col_l in ["C", "D"]:
                    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                elif col_l == "F":
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    cell.font = Font(name=self.font_family, size=9.5, bold=True)
                    if is_improved:
                        cell.fill = fill_done
                        cell.font = font_done
                    else:
                        cell.fill = fill_pending
                        cell.font = font_pending
                elif col_l == "E":
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # Data Validation on Col F (Trạng thái)
        dv = DataValidation(type="list", formula1='"Cải thiện,Chưa cải thiện"', allow_blank=True)
        dv.error = 'Vui lòng chọn từ danh sách: Cải thiện hoặc Chưa cải thiện'
        dv.errorTitle = 'Lựa chọn không hợp lệ'
        dv.prompt = 'Chọn trạng thái: Cải thiện / Chưa cải thiện'
        dv.promptTitle = 'Trạng thái xử lý'
        ws_all.add_data_validation(dv)
        dv.add(f"F5:F{max(4 + total_items + 50, 100)}")

        ws_all.freeze_panes = "A5"
        ws_all.auto_filter.ref = f"A4:G{4 + total_items}"

        return wb

    def export_master_bytes(self, defects: Optional[List[Dict[str, Any]]] = None) -> bytes:
        wb = self.export_master_workbook(defects)
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        if self.images_by_cell:
            try:
                return package_cell_images(out, self.images_by_cell)
            except Exception as e:
                logger.warning(f"Error packaging cell images: {e}")
                out.seek(0)
                return out.getvalue()
        return out.getvalue()
