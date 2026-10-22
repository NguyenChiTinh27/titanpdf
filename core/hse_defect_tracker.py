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

logger = logging.getLogger("titanpdf.hse_defect_tracker")

# Project paths
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
HSE_REPORTS_DIR = DATA_DIR / "hse_reports"
OVERRIDES_FILE = DATA_DIR / "hse_defect_tracker_overrides.json"

TRACKER_STATE_FILE = DATA_DIR / "hse_tracker_state.json"
BASE_HSE_DIR = Path(__file__).resolve().parent / "data" / "hse"
EXTRACTED_DEFECTS_JSON = BASE_HSE_DIR / "extracted_defects.json"
EXTRACTED_IMAGES_DIR = BASE_HSE_DIR / "extracted_images"
GAS_CONFIG_FILE = DATA_DIR / "msds_gas_config.json"

DEFAULT_GAS_URL = "https://script.google.com/macros/s/AKfycbzc2q-vTj-8xCykJqEiH8a7rkfaLLpkpl6bOUuvJOBv86a5QpeqzT46twZuuyQkePg/exec"


class DefectUpdatePayload(BaseModel):
    defectId: str
    improved: bool = False
    improveDate: Optional[str] = ""
    note: Optional[str] = ""
    afterImageData: Optional[str] = ""
    date: Optional[str] = ""


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

        # 2. Xóa sạch file overrides
        try:
            with open(OVERRIDES_FILE, "w", encoding="utf-8") as of:
                json.dump({}, of, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Could not clear overrides file: {e}")

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
                        "status": "Đã cải thiện / 已改善" if is_improved else "Chờ xử lý / 待处理",
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
                            "status": "Đã cải thiện / 已改善" if is_improved else "Chờ xử lý / 待处理",
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
                        matched_defect["status"] = "Đã cải thiện / 已改善"
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
                    d["status"] = "Đã cải thiện / 已改善" if d["improved"] else "Chờ xử lý / 待处理"
                if ov.get("improve_date"):
                    d["improve_date"] = ov["improve_date"]
                if ov.get("note"):
                    d["note"] = ov["note"]
                if ov.get("img_after"):
                    d["img_after"] = cls.clean_image_uri(ov["img_after"])

        # Sắp xếp danh sách: Ngày giảm dần, Mã giảm dần
        raw_defects.sort(key=lambda x: (x.get("date", ""), x.get("code", "")), reverse=True)

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
    def update_defect(cls, payload: DefectUpdatePayload) -> Dict[str, Any]:
        """Cập nhật trạng thái sự cố và đồng bộ 2 chiều ngược về file báo cáo gốc & Google Apps Script."""
        code = payload.defectId
        now_str = payload.improveDate or datetime.now().strftime("%Y-%m-%d %H:%M")

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
            item_ov["improved"] = payload.improved
            item_ov["improve_date"] = now_str if payload.improved else ""
            if payload.note is not None:
                item_ov["note"] = payload.note
            if payload.afterImageData:
                item_ov["img_after"] = cls.clean_image_uri(payload.afterImageData)
            overrides[k] = item_ov

        cls.save_overrides(overrides)

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


# =============================================================================
# Master Multi-Month Excel Exporter
# =============================================================================

class MasterHSEExcelExporter:
    """Generates the enterprise multi-month master defect tracking spreadsheet."""

    def __init__(self, font_family: str = "Segoe UI"):
        self.font_family = font_family
        self.thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1")
        )
        self.header_border = Border(
            left=Side(style="thin", color="3B82F6"),
            right=Side(style="thin", color="3B82F6"),
            top=Side(style="medium", color="1E3A8A"),
            bottom=Side(style="medium", color="1E3A8A")
        )

    def export_master_workbook(self, defects: Optional[List[Dict[str, Any]]] = None) -> openpyxl.Workbook:
        if defects is None:
            data = DefectAggregatorService.aggregate_all_defects()
            defects = data["defects"]

        wb = openpyxl.Workbook()

        total_items = len(defects)
        improved_items = sum(1 for d in defects if d.get("improved"))
        pending_items = total_items - improved_items
        rate_val = (improved_items / total_items) if total_items > 0 else 0.0

        # Discover months & departments
        months = sorted(list({d.get("month") for d in defects if d.get("month")}), reverse=True)
        departments = sorted(list({d.get("department") for d in defects if d.get("department")}))
        categories = sorted(list({d.get("category") for d in defects if d.get("category")}))

        # =====================================================================
        # SHEET 1: 📊 DASHBOARD TỔNG THỂ
        # =====================================================================
        ws_dash = wb.active
        ws_dash.title = "📊 DASHBOARD TỔNG THỂ"
        ws_dash.sheet_properties.tabColor = "1E40AF"
        ws_dash.views.sheetView[0].showGridLines = False

        # Top Banner
        ws_dash.merge_cells("B2:M2")
        b2 = ws_dash["B2"]
        b2.value = "HỆ THỐNG THEO DÕI & KHẮC PHỤC LỖI HSE TOÀN CÔNG TY (MASTER DEFECT TRACKER)"
        b2.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        b2.font = Font(name=self.font_family, size=15, bold=True, color="FFFFFF")
        b2.alignment = Alignment(horizontal="center", vertical="center")
        ws_dash.row_dimensions[2].height = 42

        # Sub Banner
        ws_dash.merge_cells("B3:M3")
        b3 = ws_dash["B3"]
        b3.value = f"Tổng hợp dữ liệu toàn diện qua tất cả các tháng ({len(months)} tháng) — Cập nhật ngày {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        b3.fill = PatternFill(start_color="3B82F6", end_color="3B82F6", fill_type="solid")
        b3.font = Font(name=self.font_family, size=10, italic=True, color="FFFFFF")
        b3.alignment = Alignment(horizontal="center", vertical="center")
        ws_dash.row_dimensions[3].height = 24
        ws_dash.row_dimensions[4].height = 12

        # 4 KPI Cards
        kpi_cards = [
            ("B", "D", "TỔNG SỐ LỖI PHÁT HIỆN\n总缺陷数", total_items, "2563EB", "EFF6FF", "1E40AF", "0"),
            ("E", "G", "ĐÃ KHẮC PHỤC CẢI THIỆN\n已改善完成", improved_items, "16A34A", "F0FDF4", "15803D", "0"),
            ("H", "J", "CÒN TỒN ĐỌNG CHỜ XỬ LÝ\n待处理隐患", pending_items, "EA580C", "FFF7ED", "C2410C", "0"),
            ("K", "M", "TỶ LỆ HOÀN THÀNH\n综合改善率", rate_val, "7C3AED", "FAF5FF", "6D28D9", "0.0%")
        ]

        for sc, ec, title, val, border_c, bg_c, text_c, num_fmt in kpi_cards:
            ws_dash.merge_cells(f"{sc}5:{ec}5")
            ws_dash.merge_cells(f"{sc}6:{ec}6")
            
            c_top = ws_dash[f"{sc}5"]
            c_top.value = title
            c_top.fill = PatternFill(start_color=bg_c, end_color=bg_c, fill_type="solid")
            c_top.font = Font(name=self.font_family, size=9, bold=True, color="475569")
            c_top.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            c_val = ws_dash[f"{sc}6"]
            c_val.value = val
            c_val.fill = PatternFill(start_color=bg_c, end_color=bg_c, fill_type="solid")
            c_val.font = Font(name=self.font_family, size=22, bold=True, color=text_c)
            c_val.alignment = Alignment(horizontal="center", vertical="center")
            c_val.number_format = num_fmt

        ws_dash.row_dimensions[5].height = 32
        ws_dash.row_dimensions[6].height = 42
        ws_dash.row_dimensions[7].height = 14

        # Table 1: Progress by Month
        ws_dash.merge_cells("B8:F8")
        h_m = ws_dash["B8"]
        h_m.value = "1. TIẾN ĐỘ THEO DÕI THEO TỪNG THÁNG (按月份统计趋势)"
        h_m.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        h_m.font = Font(name=self.font_family, size=11, bold=True, color="FFFFFF")
        h_m.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws_dash.row_dimensions[8].height = 26

        m_cols = [("B", "Tháng\n月份"), ("C", "Tổng lỗi\n总数"), ("D", "Đã xử lý\n已改善"), ("E", "Tồn đọng\n待处理"), ("F", "Tỷ lệ %\n改善率")]
        ws_dash.row_dimensions[9].height = 26
        for col_l, name in m_cols:
            c = ws_dash[f"{col_l}9"]
            c.value = name
            c.fill = PatternFill(start_color="3B82F6", end_color="3B82F6", fill_type="solid")
            c.font = Font(name=self.font_family, size=9.5, bold=True, color="FFFFFF")
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        m_row = 10
        for m in months:
            m_items = [d for d in defects if d.get("month") == m]
            m_tot = len(m_items)
            m_imp = sum(1 for d in m_items if d.get("improved"))
            m_pnd = m_tot - m_imp
            m_rate = (m_imp / m_tot) if m_tot > 0 else 0.0

            ws_dash.row_dimensions[m_row].height = 22
            ws_dash[f"B{m_row}"] = m
            ws_dash[f"C{m_row}"] = m_tot
            ws_dash[f"D{m_row}"] = m_imp
            ws_dash[f"E{m_row}"] = m_pnd
            ws_dash[f"F{m_row}"] = m_rate
            ws_dash[f"F{m_row}"].number_format = "0.0%"

            for col_l, _ in m_cols:
                cell = ws_dash[f"{col_l}{m_row}"]
                cell.font = Font(name=self.font_family, size=9.5)
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = self.thin_border
            m_row += 1

        # Table 2: Breakdown by Department
        ws_dash.merge_cells("H8:M8")
        h_d = ws_dash["H8"]
        h_d.value = "2. TIẾN ĐỘ THEO DÕI THEO BỘ PHẬN (按责任部门统计)"
        h_d.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        h_d.font = Font(name=self.font_family, size=11, bold=True, color="FFFFFF")
        h_d.alignment = Alignment(horizontal="left", vertical="center", indent=1)

        d_cols = [("H", "Bộ phận\n部门"), ("I", "Tổng lỗi\n总数"), ("J", "Đã xử lý\n已改善"), ("K", "Tồn đọng\n待处理"), ("L", "Tỷ lệ %\n改善率")]
        for col_l, name in d_cols:
            c = ws_dash[f"{col_l}9"]
            c.value = name
            c.fill = PatternFill(start_color="3B82F6", end_color="3B82F6", fill_type="solid")
            c.font = Font(name=self.font_family, size=9.5, bold=True, color="FFFFFF")
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        d_row = 10
        for d_name in departments:
            d_items = [d for d in defects if d.get("department") == d_name]
            d_tot = len(d_items)
            d_imp = sum(1 for d in d_items if d.get("improved"))
            d_pnd = d_tot - d_imp
            d_rate = (d_imp / d_tot) if d_tot > 0 else 0.0

            ws_dash.row_dimensions[d_row].height = 22
            ws_dash[f"H{d_row}"] = d_name
            ws_dash[f"I{d_row}"] = d_tot
            ws_dash[f"J{d_row}"] = d_imp
            ws_dash[f"K{d_row}"] = d_pnd
            ws_dash[f"L{d_row}"] = d_rate
            ws_dash[f"L{d_row}"].number_format = "0.0%"

            for col_l, _ in d_cols:
                cell = ws_dash[f"{col_l}{d_row}"]
                cell.font = Font(name=self.font_family, size=9.5)
                cell.alignment = Alignment(horizontal="center" if col_l != "H" else "left", vertical="center")
                cell.border = self.thin_border
            d_row += 1

        # Chart: Progress by Department
        chart_row = max(m_row, d_row) + 2
        try:
            chart = BarChart()
            chart.type = "col"
            chart.grouping = "stacked"
            chart.overlap = 100
            chart.title = "TIẾN ĐỘ KHẮC PHỤC LỖI TOÀN CÔNG TY (按部门改善进度对比)"
            chart.style = 10
            c_data = Reference(ws_dash, min_col=10, min_row=9, max_col=11, max_row=d_row - 1)
            c_cats = Reference(ws_dash, min_col=8, min_row=10, max_row=d_row - 1)
            chart.add_data(c_data, titles_from_data=True)
            chart.set_categories(c_cats)
            chart.height = 14
            chart.width = 22
            chart.x_axis.title = "Bộ phận / 部门"
            chart.y_axis.title = "Số lượng lỗi / 隐患数"
            ws_dash.add_chart(chart, f"B{chart_row}")
        except Exception as e:
            logger.warning(f"Could not add master dashboard chart: {e}")

        # Column widths for Sheet 1
        dash_widths = {
            "A": 3, "B": 24, "C": 12, "D": 12, "E": 12, "F": 12, "G": 4,
            "H": 28, "I": 10, "J": 10, "K": 10, "L": 10, "M": 3
        }
        for cl, w in dash_widths.items():
            ws_dash.column_dimensions[cl].width = w

        # =====================================================================
        # SHEET 2: 📋 Tổng Hợp Tất Cả Lỗi
        # =====================================================================
        ws_all = wb.create_sheet(title="📋 Tổng Hợp Tất Cả Lỗi")
        ws_all.sheet_properties.tabColor = "10B981"

        data_headers = [
            ("A", "Mã lỗi\n编号", 16),
            ("B", "Ngày ghi nhận\n记录日期", 14),
            ("C", "Tháng\n月份", 12),
            ("D", "Bộ phận\n部门", 24),
            ("E", "Nhóm lỗi HSE\n隐患类别", 28),
            ("F", "Mô tả chi tiết (Tiếng Trung)\n详细描述 (中文)", 48),
            ("G", "Mô tả chi tiết (Tiếng Việt)\n详细描述 (越南语)", 48),
            ("H", "Hình ảnh hiện trường\n现场图片", 24),
            ("I", "Trạng thái\n状态", 20),
            ("J", "Ngày cải thiện\n改善日期", 16),
            ("K", "Ghi chú & Đối sách\n备注与改善对策", 28)
        ]

        # Sheet 2 Banners
        ws_all.merge_cells("A1:K1")
        h1 = ws_all["A1"]
        h1.value = "DANH SÁCH TỔNG HỢP THEO DÕI SỰ CỐ & TIẾN ĐỘ KHẮC PHỤC HSE TOÀN CÔNG TY"
        h1.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        h1.font = Font(name=self.font_family, size=14, bold=True, color="FFFFFF")
        h1.alignment = Alignment(horizontal="center", vertical="center")
        ws_all.row_dimensions[1].height = 36

        ws_all.merge_cells("A2:K2")
        h2 = ws_all["A2"]
        h2.value = f"Tổng số {len(defects)} sự cố ghi nhận qua các đợt kiểm tra — Trạng thái đồng bộ thời gian thực"
        h2.fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        h2.font = Font(name=self.font_family, size=10, italic=True, color="FFFFFF")
        h2.alignment = Alignment(horizontal="center", vertical="center")
        ws_all.row_dimensions[2].height = 22
        ws_all.row_dimensions[3].height = 10

        # Data Headers Row 4
        ws_all.row_dimensions[4].height = 36
        for col_l, col_name, width in data_headers:
            c = ws_all[f"{col_l}4"]
            c.value = col_name
            if col_l == "H":
                c.fill = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
                c.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
            else:
                c.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
                c.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border = self.header_border
            ws_all.column_dimensions[col_l].width = width

        # Status fills
        fill_done = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
        font_done = Font(name=self.font_family, size=9.5, bold=True, color="065F46")
        fill_pending = PatternFill(start_color="FFEDD5", end_color="FFEDD5", fill_type="solid")
        font_pending = Font(name=self.font_family, size=9.5, bold=True, color="9A3412")

        # Fill Data Rows
        ws_all.auto_filter.ref = f"A4:K{4 + len(defects)}"
        for idx, item in enumerate(defects, 1):
            r_num = 4 + idx
            ws_all.row_dimensions[r_num].height = 85

            ws_all[f"A{r_num}"] = item.get("code")
            ws_all[f"B{r_num}"] = item.get("date")
            ws_all[f"C{r_num}"] = item.get("month")
            ws_all[f"D{r_num}"] = item.get("department")
            ws_all[f"E{r_num}"] = item.get("category")
            ws_all[f"F{r_num}"] = item.get("zh_issue")
            ws_all[f"G{r_num}"] = item.get("vn_issue")
            ws_all[f"I{r_num}"] = item.get("status")
            ws_all[f"J{r_num}"] = item.get("improve_date")
            ws_all[f"K{r_num}"] = item.get("note")

            # Column H: Photo link or embedded image (Zero #REF!)
            month_tag = item.get("month") or "HSE"
            drive_url = item.get("drive_view_url") or item.get("drive_direct_url") or ""
            img_b = item.get("img_before") or ""

            if drive_url:
                ws_all[f"H{r_num}"] = f"🔗 Xem ảnh Drive ({month_tag})"
                ws_all[f"H{r_num}"].hyperlink = drive_url
            elif img_b and img_b.startswith("http"):
                ws_all[f"H{r_num}"] = f"🔗 Mở ảnh ({month_tag})"
                ws_all[f"H{r_num}"].hyperlink = img_b
            elif img_b and (img_b.startswith("data:image") or os.path.exists(img_b)):
                ws_all[f"H{r_num}"] = f"📸 Có ảnh ({month_tag})"
            else:
                ws_all[f"H{r_num}"] = "Không có ảnh\n无图片"

            for col_l, _, _ in data_headers:
                cell = ws_all[f"{col_l}{r_num}"]
                cell.font = Font(name=self.font_family, size=9.5)
                cell.border = self.thin_border

                if col_l == "H":
                    if "Xem ảnh" in str(ws_all[f"H{r_num}"].value) or "Mở ảnh" in str(ws_all[f"H{r_num}"].value):
                        cell.font = Font(name=self.font_family, size=9, bold=True, color="2563EB", underline="single")
                    else:
                        cell.font = Font(name=self.font_family, size=8.5, italic=True, color="94A3B8")
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif col_l in ["A", "B", "C", "J"]:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif col_l in ["D", "E"]:
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                elif col_l in ["F", "G", "K"]:
                    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                elif col_l == "I":
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    if item.get("improved"):
                        cell.fill = fill_done
                        cell.font = font_done
                    else:
                        cell.fill = fill_pending
                        cell.font = font_pending

        ws_all.freeze_panes = "A5"
        ws_all.auto_filter.ref = f"A4:K{4 + total_items}"

        # =====================================================================
        # SHEETS 3+: TÁCH RIÊNG TỪNG BỘ PHẬN (MULTI-SHEET PER DEPARTMENT)
        # =====================================================================
        for d_idx, d_name in enumerate(departments, 1):
            d_items = [d for d in defects if d.get("department") == d_name]
            if not d_items:
                continue

            # Clean sheet title (max 31 chars, forbidden characters removed)
            safe_title = re.sub(r'[\\/*?:\[\]]', '', d_name)
            safe_title = re.sub(r'\s+', ' ', safe_title).strip()[:30]
            if not safe_title:
                safe_title = f"BoPhan_{d_idx}"

            ws_dept = wb.create_sheet(title=safe_title)
            ws_dept.sheet_properties.tabColor = "3B82F6"

            ws_dept.merge_cells("A1:K1")
            d_h1 = ws_dept["A1"]
            d_h1.value = f"SỔ THEO DÕI SỰ CỐ AN TOÀN — {d_name.upper()}"
            d_h1.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
            d_h1.font = Font(name=self.font_family, size=13, bold=True, color="FFFFFF")
            d_h1.alignment = Alignment(horizontal="center", vertical="center")
            ws_dept.row_dimensions[1].height = 36

            ws_dept.merge_cells("A2:K2")
            d_h2 = ws_dept["A2"]
            d_imp_cnt = sum(1 for x in d_items if x.get("improved"))
            d_h2.value = f"Trích xuất riêng cho bộ phận (Tổng số: {len(d_items)} lỗi · Đã cải thiện: {d_imp_cnt} · Tồn đọng: {len(d_items)-d_imp_cnt})"
            d_h2.fill = PatternFill(start_color="3B82F6", end_color="3B82F6", fill_type="solid")
            d_h2.font = Font(name=self.font_family, size=10, italic=True, color="FFFFFF")
            d_h2.alignment = Alignment(horizontal="center", vertical="center")
            ws_dept.row_dimensions[2].height = 22
            ws_dept.row_dimensions[3].height = 10

            # Headers
            ws_dept.row_dimensions[4].height = 36
            for col_l, col_name, width in data_headers:
                c = ws_dept[f"{col_l}4"]
                c.value = col_name
                c.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
                c.font = Font(name=self.font_family, size=9.5, bold=True, color="FFFFFF")
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                c.border = self.header_border
                ws_dept.column_dimensions[col_l].width = width

            for i_sub, item in enumerate(d_items, 1):
                r_num = 4 + i_sub
                ws_dept.row_dimensions[r_num].height = 70

                ws_dept[f"A{r_num}"] = item.get("code")
                ws_dept[f"B{r_num}"] = item.get("date")
                ws_dept[f"C{r_num}"] = item.get("month")
                ws_dept[f"D{r_num}"] = item.get("department")
                ws_dept[f"E{r_num}"] = item.get("category")
                ws_dept[f"F{r_num}"] = item.get("zh_issue")
                ws_dept[f"G{r_num}"] = item.get("vn_issue")
                ws_dept[f"I{r_num}"] = item.get("status")
                ws_dept[f"J{r_num}"] = item.get("improve_date")
                ws_dept[f"K{r_num}"] = item.get("note")

                month_tag = item.get("month") or "HSE"
                drive_url = item.get("drive_view_url") or item.get("drive_direct_url") or ""
                img_b = item.get("img_before") or ""

                if drive_url:
                    ws_dept[f"H{r_num}"] = f"🔗 Xem ảnh Drive ({month_tag})"
                    ws_dept[f"H{r_num}"].hyperlink = drive_url
                elif img_b and img_b.startswith("http"):
                    ws_dept[f"H{r_num}"] = f"🔗 Mở ảnh ({month_tag})"
                    ws_dept[f"H{r_num}"].hyperlink = img_b
                elif img_b and (img_b.startswith("data:image") or os.path.exists(img_b)):
                    ws_dept[f"H{r_num}"] = f"📸 Có ảnh ({month_tag})"
                else:
                    ws_dept[f"H{r_num}"] = "Không có ảnh\n无图片"

                for col_l, _, _ in data_headers:
                    cell = ws_dept[f"{col_l}{r_num}"]
                    cell.font = Font(name=self.font_family, size=9.5)
                    cell.border = self.thin_border

                    if col_l == "H":
                        if "Xem ảnh" in str(ws_dept[f"H{r_num}"].value) or "Mở ảnh" in str(ws_dept[f"H{r_num}"].value):
                            cell.font = Font(name=self.font_family, size=9, bold=True, color="2563EB", underline="single")
                        else:
                            cell.font = Font(name=self.font_family, size=8.5, italic=True, color="94A3B8")
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    elif col_l in ["A", "B", "C", "J"]:
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    elif col_l in ["D", "E"]:
                        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    elif col_l in ["F", "G", "K"]:
                        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                    elif col_l == "I":
                        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                        if item.get("improved"):
                            cell.fill = fill_done
                            cell.font = font_done
                        else:
                            cell.fill = fill_pending
                            cell.font = font_pending

            ws_dept.freeze_panes = "A5"
            ws_dept.auto_filter.ref = f"A4:K{4 + len(d_items)}"

        return wb

    def export_master_bytes(self, defects: Optional[List[Dict[str, Any]]] = None) -> bytes:
        wb = self.export_master_workbook(defects)
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return out.getvalue()
