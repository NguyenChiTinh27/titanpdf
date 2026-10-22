"""
core/msds_gas_sync.py
─────────────────────
DỊCH VỤ ĐỒNG BỘ HAI CHIỀU GOOGLE SHEETS & GOOGLE DRIVE QUA GOOGLE APPS SCRIPT (GAS)
(TitanPDF MSDS & Chemical Inventory List - Cloud Persistence & Drive Offloader)

Mục tiêu cốt lõi:
1. Google Sheets làm Chân Lý Lưu Trữ Đơn Nhất (Single Source of Truth - SSOT) cho danh mục CIL 38 cột.
2. Khắc phục triệt để lỗi "Render Ephemeral Reset" (hồi sinh 13 hóa chất mẫu sau khi container restart).
3. Tải tệp PDF MSDS gốc, tài liệu Word/PDF xuất ra thẳng lên Google Drive (thư mục LUV_PDF_Exports/MSDS_Originals).
4. Xóa vĩnh viễn: Khi xóa lẻ hoặc xóa toàn bộ trên Web, xóa lập tức trên Google Sheet và dọn bộ nhớ đệm.
5. Hòa giải khởi động (Startup Reconciliation): Khi máy chủ khởi động, kéo dữ liệu từ Google Sheet về SQLite.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

logger = logging.getLogger("titanpdf.msds_gas_sync")

# ==============================================================================
# HẰNG SỐ & ĐƯỜNG DẪN CẤU HÌNH
# ==============================================================================
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "msds_gas_config.json"

DEFAULT_SECRET_TOKEN = "LUV_PDF_SYNC_KEY_2026"
ALT_SECRET_TOKEN = "LUV_MSDS_SECURE_TOKEN_2026"
DEFAULT_TIMEOUT = 12.0  # Google Apps Script redirection latency tolerance

# 38 Tiêu đề cột chuẩn hóa đồng nhất với Google Apps Script và test suite
CIL_38_COLUMNS = [
    "chemical_id", "product_code", "product_name_vi", "product_name_original",
    "item_type", "mother_msds_id", "cas_primary", "un_no", "transport_class",
    "packing_group", "signal_word", "ghs_codes", "hazard_statements",
    "precautionary_statements", "flash_point", "density", "appearance",
    "storage_condition", "respiratory_protection", "hand_protection",
    "eye_protection", "skin_protection", "first_aid_inhalation",
    "first_aid_skin", "first_aid_eyes", "first_aid_ingestion",
    "fire_measures", "spill_measures", "compositions_json", "source_file",
    "drive_file_id", "drive_view_url", "drive_download_url", "sha256",
    "sync_status", "created_at", "updated_at", "deleted_at"
]


class MSDSGASSyncService:
    """Dịch vụ kết nối Google Apps Script Webhook API cho MSDS Studio & Sổ CIL."""

    _cached_config: Optional[Dict[str, Any]] = None

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """Đọc cấu hình Webhook URL và Secret Token từ file json hoặc biến môi trường."""
        if cls._cached_config is not None:
            return cls._cached_config

        config = {
            "webhook_url": os.getenv("MSDS_GAS_WEBHOOK_URL", "").strip(),
            "secret_token": os.getenv("MSDS_GAS_TOKEN", DEFAULT_SECRET_TOKEN).strip(),
            "auto_sync": os.getenv("MSDS_GAS_AUTO_SYNC", "true").lower() in ("true", "1", "yes"),
            "drive_folder": "LUV_PDF_Exports/MSDS_Originals"
        }

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        if saved.get("webhook_url"):
                            config["webhook_url"] = str(saved["webhook_url"]).strip()
                        if saved.get("secret_token") is not None:
                            config["secret_token"] = str(saved["secret_token"]).strip()
                        if "auto_sync" in saved:
                            config["auto_sync"] = bool(saved["auto_sync"])
                        if saved.get("drive_folder"):
                            config["drive_folder"] = str(saved["drive_folder"]).strip()
            except Exception as e:
                logger.warning("Không thể đọc file cấu hình GAS %s: %s", CONFIG_FILE, e)

        cls._cached_config = config
        return config

    @classmethod
    def save_config(cls, webhook_url: str, secret_token: Optional[str] = None, auto_sync: bool = True) -> Dict[str, Any]:
        """Lưu cấu hình Webhook URL và Secret Token vào data/msds_gas_config.json."""
        current = cls.get_config()
        clean_url = str(webhook_url or "").strip()
        incoming_token = str(secret_token if secret_token is not None else "").strip()
        if not incoming_token or incoming_token in ("******", "••••••••••••••••") or "•" in incoming_token:
            clean_token = current.get("secret_token") or DEFAULT_SECRET_TOKEN
            if not clean_token or clean_token in ("******", "••••••••••••••••") or "•" in clean_token:
                clean_token = DEFAULT_SECRET_TOKEN
        else:
            clean_token = incoming_token

        cfg_to_save = {
            "webhook_url": clean_url,
            "secret_token": clean_token,
            "auto_sync": bool(auto_sync),
            "drive_folder": "LUV_PDF_Exports/MSDS_Originals"
        }

        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg_to_save, f, ensure_ascii=False, indent=2)
            cls._cached_config = cfg_to_save
        except Exception as e:
            logger.error("Lỗi khi lưu cấu hình GAS %s: %s", CONFIG_FILE, e)
            raise RuntimeError(f"Không thể lưu cấu hình Google Apps Script: {e}")

        return cfg_to_save

    @classmethod
    def is_configured(cls) -> bool:
        """Kiểm tra xem hệ thống đã thiết lập Webhook URL hay chưa."""
        cfg = cls.get_config()
        return bool(cfg.get("webhook_url"))

    @classmethod
    def _send_request(cls, payload: Dict[str, Any], custom_url: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        """Gửi yêu cầu POST an toàn tới Google Apps Script Webhook (kèm allow_redirects=True)."""
        cfg = cls.get_config()
        url = (custom_url or cfg.get("webhook_url") or "").strip()
        if not url:
            return {"status": "error", "error": "Chưa cấu hình Google Apps Script Webhook URL."}

        raw_token = payload.get("token") or cfg.get("secret_token") or DEFAULT_SECRET_TOKEN
        if not raw_token or raw_token in ("******", "••••••••••••••••") or "•" in str(raw_token):
            token = DEFAULT_SECRET_TOKEN
        else:
            token = str(raw_token).strip()
        payload["token"] = token

        try:
            resp = requests.post(
                url,
                data=json.dumps(payload, ensure_ascii=False),
                timeout=timeout,
                allow_redirects=True,
                headers={"Content-Type": "text/plain;charset=utf-8"}
            )
            text = resp.text or ""
            if "<!DOCTYPE" in text or "<html" in text.lower():
                return {
                    "status": "error",
                    "success": False,
                    "is_html": True,
                    "error": "Google Apps Script phản hồi HTML (Yêu cầu đăng nhập hoặc quyền truy cập). Vui lòng mở Google Apps Script (Code.gs), Deploy lại Web App với quyền: 'Who has access' (Ai có quyền truy cập) là 'Anyone' (Bất kỳ ai)."
                }
            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception:
                    return {"status": "ok", "success": True, "raw_response": text[:500]}
            else:
                return {
                    "status": "error",
                    "success": False,
                    "error": f"GAS trả về mã HTTP {resp.status_code}: {text[:300]}",
                    "http_status": resp.status_code
                }
        except requests.exceptions.Timeout:
            logger.warning("Google Apps Script Webhook timeout (>%ss) cho action=%s", timeout, payload.get("action"))
            return {"status": "error", "error": f"Hết thời gian chờ phản hồi ({timeout}s) từ Google Apps Script."}
        except Exception as e:
            logger.error("Lỗi kết nối tới GAS Webhook: %s", e)
            return {"status": "error", "error": str(e)}

    # ==========================================================================
    # CÁC PHƯƠNG THỨC NGHIỆP VỤ CRUD & GOOGLE DRIVE
    # ==========================================================================

    @classmethod
    def test_connection(cls, url: Optional[str] = None, token: Optional[str] = None) -> Dict[str, Any]:
        """Kiểm tra kết nối tới Google Apps Script Webhook."""
        cfg = cls.get_config()
        target_url = (url or cfg.get("webhook_url") or "").strip()
        raw_token = token or cfg.get("secret_token") or DEFAULT_SECRET_TOKEN
        if not raw_token or raw_token in ("******", "••••••••••••••••") or "•" in str(raw_token):
            target_token = DEFAULT_SECRET_TOKEN
        else:
            target_token = str(raw_token).strip()

        if not target_url:
            return {
                "success": False,
                "status": "error",
                "message": "Vui lòng nhập Webhook URL của Google Apps Script."
            }

        payload = {
            "action": "ping",
            "token": target_token
        }
        res = cls._send_request(payload, custom_url=target_url, timeout=10.0)

        is_ok = (res.get("status") in ("ok", "success") or res.get("success") is True)
        if is_ok:
            return {
                "success": True,
                "status": "ok",
                "message": res.get("message") or "Kết nối Google Apps Script & Google Drive thành công!",
                "sheet_name": res.get("sheetName") or res.get("sheet_name") or "CIL_Chemical_Inventory",
                "total_rows": res.get("total_rows", res.get("totalChemicalsInSheet", 0)),
                "details": res
            }
        else:
            return {
                "success": False,
                "status": "error",
                "message": res.get("error") or res.get("message") or "Không thể kết nối tới Google Apps Script.",
                "details": res
            }

    @classmethod
    def sync_to_sheet(cls, chemical: Dict[str, Any]) -> Dict[str, Any]:
        """Đồng bộ một hóa chất (thêm mới hoặc cập nhật) lên Google Sheet."""
        if not cls.is_configured():
            return {"status": "skipped", "message": "Chưa cấu hình Google Apps Script Webhook."}

        payload = {
            "action": "saveChemical",
            "chemical": chemical
        }
        return cls._send_request(payload)

    @classmethod
    def batch_sync_to_sheet(cls, chemicals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Đồng bộ hàng loạt hóa chất lên Google Sheet."""
        if not cls.is_configured():
            return {"status": "skipped", "message": "Chưa cấu hình Google Apps Script Webhook."}

        payload = {
            "action": "batchSaveChemicals",
            "chemicals": chemicals
        }
        return cls._send_request(payload, timeout=25.0)

    @classmethod
    def delete_from_sheet(cls, chemical_id: str) -> Dict[str, Any]:
        """Xóa vĩnh viễn một hóa chất khỏi Google Sheet."""
        if not cls.is_configured():
            return {"status": "skipped", "message": "Chưa cấu hình Google Apps Script Webhook."}

        payload = {
            "action": "deleteChemical",
            "chemical_id": chemical_id
        }
        return cls._send_request(payload)

    @classmethod
    def delete_multiple_from_sheet(cls, ids: List[str]) -> Dict[str, Any]:
        """Xóa vĩnh viễn nhiều hóa chất khỏi Google Sheet."""
        if not cls.is_configured():
            return {"status": "skipped", "message": "Chưa cấu hình Google Apps Script Webhook."}

        payload = {
            "action": "deleteMultipleChemicals",
            "ids": ids
        }
        return cls._send_request(payload, timeout=20.0)

    @classmethod
    def delete_all_from_sheet(cls) -> Dict[str, Any]:
        """Xóa toàn bộ dữ liệu hóa chất trên Google Sheet (giữ nguyên dòng tiêu đề)."""
        if not cls.is_configured():
            return {"status": "skipped", "message": "Chưa cấu hình Google Apps Script Webhook."}

        payload = {
            "action": "deleteAllChemicals"
        }
        return cls._send_request(payload, timeout=20.0)

    @classmethod
    def fetch_all_from_sheet(cls) -> Optional[List[Dict[str, Any]]]:
        """Lấy toàn bộ danh sách hóa chất từ Google Sheet CIL_Chemical_Inventory."""
        if not cls.is_configured():
            return None

        payload = {
            "action": "getAllChemicals"
        }
        res = cls._send_request(payload, timeout=20.0)
        if res.get("status") in ("ok", "success") or res.get("success") is True:
            chems = res.get("chemicals")
            if isinstance(chems, list):
                return chems
        logger.warning("Không thể lấy danh sách hóa chất từ Google Sheet: %s", res.get("error"))
        return None

    @classmethod
    def upload_file_to_drive(
        cls,
        file_bytes: bytes,
        filename: Optional[str] = None,
        mime_type: str = "application/pdf",
        subfolder: str = "MSDS_Originals",
        file_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Tải tệp tin (PDF MSDS gốc, tài liệu Word/PDF, ảnh) lên thư mục Google Drive.
        Trả về: { status: "success", fileId, fileName, viewUrl, downloadUrl, sizeBytes }
        """
        if not cls.is_configured():
            return {
                "status": "skipped",
                "success": False,
                "message": "Chưa cấu hình Google Apps Script Webhook để tải lên Drive."
            }

        resolved_filename = filename or file_name or "document.pdf"
        b64_content = base64.b64encode(file_bytes).decode("utf-8")
        payload = {
            "action": "uploadFile",
            "fileName": resolved_filename,
            "filename": resolved_filename,
            "mimeType": mime_type,
            "base64": b64_content,
            "base64Data": b64_content,
            "subFolder": subfolder,
            "subfolder": subfolder
        }
        res = cls._send_request(payload, timeout=30.0)
        if isinstance(res, dict):
            if res.get("fileId") and not res.get("file_id"):
                res["file_id"] = res["fileId"]
            if res.get("viewUrl") and not res.get("view_url"):
                res["view_url"] = res["viewUrl"]
            if res.get("downloadUrl") and not res.get("download_url"):
                res["download_url"] = res["downloadUrl"]
        return res

    @classmethod
    def get_or_create_monthly_folder(cls, year_month: str) -> Dict[str, Any]:
        """Tạo hoặc lấy thư mục tháng YYYY-MM trong HSE_Report_Images trên Google Drive."""
        if not cls.is_configured():
            return {
                "status": "skipped",
                "success": False,
                "message": "Chưa cấu hình Google Apps Script Webhook."
            }
        payload = {
            "action": "getOrCreateMonthlyFolder",
            "yearMonth": year_month
        }
        res = cls._send_request(payload, timeout=20.0)
        return res if isinstance(res, dict) else {"status": "error", "success": False}

    # ==========================================================================
    # CƠ CHẾ HÒA GIẢI KHỞI ĐỘNG (STARTUP RECONCILIATION - FIX EPHEMERAL RESET)
    # ==========================================================================

    @classmethod
    def reconcile_on_startup(cls) -> Dict[str, Any]:
        """
        Hòa giải dữ liệu SQLite với Google Sheets khi máy chủ khởi động:
        - Nếu Google Sheet đã kết nối:
          + Nếu Google Sheet trống (đã bị xóa sạch trước đó): Xóa sạch SQLite cục bộ!
            Triệt tiêu 100% lỗi 13 hóa chất mẫu git hồi sinh sau Render restart.
          + Nếu Google Sheet có dữ liệu: Đồng bộ vào SQLite cache cục bộ.
        - Nếu chưa kết nối hoặc mất mạng: Giữ nguyên SQLite cục bộ (Failure Isolation).
        """
        if not cls.is_configured():
            logger.info("MSDS GAS Webhook chưa được cấu hình. Giữ nguyên bộ đệm SQLite.")
            return {"status": "skipped", "message": "GAS chưa được cấu hình."}

        try:
            from core.msds_intelligence import MSDSDatabase
            MSDSDatabase.init_db()

            logger.info("Bắt đầu hòa giải dữ liệu khởi động từ Google Sheets qua GAS...")
            sheet_chems = cls.fetch_all_from_sheet()

            if sheet_chems is None:
                logger.warning("Không thể kết nối hoặc tải dữ liệu từ Google Sheet khi khởi động. Giữ nguyên SQLite cục bộ (Network Failure Isolation).")
                return {
                    "status": "skipped",
                    "reason": "network_error",
                    "message": "Không thể kết nối tới Google Sheet; giữ nguyên dữ liệu SQLite cục bộ."
                }

            # Trường hợp 1: Google Sheet trống (Người dùng đã xóa toàn bộ trước khi restart)
            if isinstance(sheet_chems, list) and len(sheet_chems) == 0:
                logger.info("Google Sheet trống (0 hóa chất). Xóa sạch SQLite cục bộ để chống hồi sinh dữ liệu đã xóa.")
                deleted_count = MSDSDatabase.delete_all_chemicals()
                return {
                    "status": "reconciled_empty",
                    "total_sheet_records": 0,
                    "cleared_sqlite_records": deleted_count,
                    "message": "Đã làm sạch SQLite cục bộ theo trạng thái trống trên Google Sheet."
                }

            # Trường hợp 2: Google Sheet có dữ liệu
            if isinstance(sheet_chems, list) and len(sheet_chems) > 0:
                logger.info("Google Sheet có %d hóa chất. Tiến hành hòa giải SQLite cục bộ...", len(sheet_chems))

                # Thu thập tập mã ID hợp lệ từ Google Sheet
                sheet_id_set = {
                    str(c.get("chemical_id") or c.get("product_code") or "").strip().upper()
                    for c in sheet_chems if (c.get("chemical_id") or c.get("product_code"))
                }

                # Xóa các bản ghi cục bộ không còn tồn tại trên Google Sheet
                local_chems = MSDSDatabase.list_chemicals()
                stale_ids = []
                for lc in local_chems:
                    cid = str(lc.get("chemical_id") or "").strip().upper()
                    pcode = str(lc.get("product_code") or "").strip().upper()
                    if cid not in sheet_id_set and pcode not in sheet_id_set:
                        stale_ids.append(lc.get("chemical_id"))

                if stale_ids:
                    MSDSDatabase.delete_multiple_chemicals(stale_ids)
                    logger.info("Đã xóa %d hóa chất lỗi thời khỏi SQLite (không tồn tại trên Google Sheet).", len(stale_ids))

                # Cập nhật hoặc thêm mới các bản ghi từ Google Sheet vào SQLite
                upsert_count = 0
                for c in sheet_chems:
                    try:
                        MSDSDatabase.insert_chemical(c, sync_gas=False)
                        upsert_count += 1
                    except Exception as err:
                        logger.warning("Lỗi khi lưu hóa chất %s vào SQLite: %s", c.get("chemical_id"), err)

                logger.info("Hoàn tất hòa giải khởi động: %d hóa chất được nạp vào SQLite.", upsert_count)
                return {
                    "status": "reconciled_sync",
                    "total_sheet_records": len(sheet_chems),
                    "upsert_count": upsert_count,
                    "stale_removed": len(stale_ids),
                    "message": f"Đã hòa giải thành công {upsert_count} hóa chất từ Google Sheet vào SQLite."
                }

        except Exception as e:
            logger.error("Lỗi trong quá trình hòa giải khởi động Google Sheet: %s", e)
            return {"status": "error", "error": str(e)}

        return {"status": "ok"}
