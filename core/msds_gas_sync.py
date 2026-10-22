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
5. Hòa giải khởi động (Startup Reconciliation): Khi máy chủ khởi động, kéo dữ liệu từ Google Sheet về SQLite
   với cơ chế Exponential Backoff Retry (2s, 4s, 8s) và tự động nhận diện Secret Token đa tầng.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
import time
import urllib.parse
from datetime import datetime
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

# Các mã Secret Token hợp lệ trong hệ thống LUV-PDF & TitanPDF
PRIMARY_SECRET_TOKEN = "LUV_PDF_SYNC_KEY_2026"
ALT_SECRET_TOKEN = "LUV_MSDS_SECURE_TOKEN_2026"
LEGACY_DEV_TOKEN = "mytoken123"

# Token mặc định ưu tiên khớp với phiên bản Apps Script đang hoạt động
DEFAULT_SECRET_TOKEN = ALT_SECRET_TOKEN

DEFAULT_GAS_URL = "https://script.google.com/macros/s/AKfycbzc2q-vTj-8xCykJqEiH8a7rkfaLLpkpl6bOUuvJOBv86a5QpeqzT46twZuuyQkePg/exec"
DEFAULT_TIMEOUT = 15.0  # Google Apps Script redirection latency tolerance

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

# ==============================================================================
# BỘ NHỚ TRẠNG THÁI TOÀN CỤC (GLOBAL SYNC STATE OBSERVABILITY)
# ==============================================================================
GAS_SYNC_STATE: Dict[str, Any] = {
    "last_sync_status": "uninitialized",  # "uninitialized" | "reconciled_sync" | "reconciled_empty" | "auth_failed" | "network_error" | "skipped" | "error"
    "last_sync_time": None,
    "last_sync_error": None,
    "sqlite_chemical_count": 0,
    "token_configured": False,
    "token_source": "none",
    "retry_count": 0
}


def clean_token(val: Any) -> str:
    """Loại bỏ khoảng trắng và dấu nháy bao bọc (' hoặc \") của token."""
    if val is None:
        return ""
    s = str(val).strip()
    return s.strip('"\'').strip()


def mask_token(token: str) -> str:
    """Che giấu một phần token khi ghi log để đảm bảo an toàn thông tin."""
    if not token:
        return "<EMPTY>"
    if len(token) <= 4:
        return "***"
    return f"{token[:2]}***{token[-2:]}"


class MSDSGASSyncService:
    """Dịch vụ kết nối Google Apps Script Webhook API cho MSDS Studio & Sổ CIL."""

    _cached_config: Optional[Dict[str, Any]] = None

    @classmethod
    def _resolve_token_and_source(cls) -> Tuple[str, str, bool]:
        """
        Xác định Secret Token theo thứ tự ưu tiên chặt chẽ:
        1. Biến môi trường hệ thống (Render Dashboard / OS):
           GAS_SECRET_TOKEN -> SECRET_TOKEN -> MSDS_GAS_TOKEN -> HSE_SECRET_TOKEN
        2. Tệp cấu hình cục bộ (data/msds_gas_config.json)
        3. Giá trị mặc định chuẩn hệ thống (DEFAULT_SECRET_TOKEN = 'LUV_MSDS_SECURE_TOKEN_2026')

        Trả về: (token, source_name, is_env_configured)
        """
        # 1. Kiểm tra các biến môi trường
        env_candidates = [
            ("GAS_SECRET_TOKEN", os.getenv("GAS_SECRET_TOKEN")),
            ("SECRET_TOKEN", os.getenv("SECRET_TOKEN")),
            ("MSDS_GAS_TOKEN", os.getenv("MSDS_GAS_TOKEN")),
            ("HSE_SECRET_TOKEN", os.getenv("HSE_SECRET_TOKEN")),
        ]
        for name, val in env_candidates:
            if val is not None and clean_token(val):
                cleaned = clean_token(val)
                return cleaned, f"ENV:{name}", True

        # 2. Kiểm tra tệp cấu hình data/msds_gas_config.json
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        f_token = clean_token(saved.get("secret_token"))
                        if f_token and f_token not in ("******", "••••••••••••••••") and "•" not in f_token:
                            return f_token, "CONFIG_FILE", False
            except Exception as e:
                logger.warning("Không thể đọc tệp cấu hình %s: %s", CONFIG_FILE, e)

        # 3. Fallback mặc định
        return DEFAULT_SECRET_TOKEN, "DEFAULT_FALLBACK", False

    @classmethod
    def _resolve_url_and_source(cls) -> Tuple[str, str]:
        """
        Xác định Webhook URL theo thứ tự ưu tiên:
        1. Biến môi trường: GAS_WEB_APP_URL -> GAS_WEBHOOK_URL -> MSDS_GAS_WEBHOOK_URL -> MSDS_GAS_URL -> HSE_GAS_URL
        2. Tệp cấu hình data/msds_gas_config.json
        3. Fallback mặc định DEFAULT_GAS_URL
        """
        env_candidates = [
            ("GAS_WEB_APP_URL", os.getenv("GAS_WEB_APP_URL")),
            ("GAS_WEBHOOK_URL", os.getenv("GAS_WEBHOOK_URL")),
            ("MSDS_GAS_WEBHOOK_URL", os.getenv("MSDS_GAS_WEBHOOK_URL")),
            ("MSDS_GAS_URL", os.getenv("MSDS_GAS_URL")),
            ("HSE_GAS_URL", os.getenv("HSE_GAS_URL")),
        ]
        for name, val in env_candidates:
            if val is not None and str(val).strip():
                return str(val).strip().strip('"\''), f"ENV:{name}"

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        f_url = str(saved.get("webhook_url") or saved.get("gas_url") or "").strip()
                        if f_url:
                            return f_url.strip('"\''), "CONFIG_FILE"
            except Exception:
                pass

        return DEFAULT_GAS_URL, "DEFAULT_FALLBACK"

    @classmethod
    def is_token_configured_from_env(cls) -> bool:
        """Kiểm tra xem biến môi trường Secret Token có được cấu hình trên Render không."""
        _, _, is_env = cls._resolve_token_and_source()
        return is_env

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """Đọc cấu hình Webhook URL và Secret Token từ biến môi trường hoặc tệp json."""
        if cls._cached_config is not None:
            return cls._cached_config

        url, url_source = cls._resolve_url_and_source()
        token, token_source, is_env = cls._resolve_token_and_source()

        auto_sync = os.getenv("MSDS_GAS_AUTO_SYNC", "true").lower() in ("true", "1", "yes")
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict) and "auto_sync" in saved:
                        auto_sync = bool(saved["auto_sync"])
            except Exception:
                pass

        config = {
            "webhook_url": url,
            "url_source": url_source,
            "secret_token": token,
            "token_source": token_source,
            "token_configured_env": is_env,
            "auto_sync": auto_sync,
            "drive_folder": "LUV_PDF_Exports/MSDS_Originals"
        }

        cls._cached_config = config
        return config

    @classmethod
    def save_config(cls, webhook_url: str, secret_token: Optional[str] = None, auto_sync: bool = True) -> Dict[str, Any]:
        """Lưu cấu hình Webhook URL và Secret Token vào data/msds_gas_config.json."""
        current = cls.get_config()
        clean_url = str(webhook_url or "").strip().strip('"\'')
        incoming_token = clean_token(secret_token)
        if not incoming_token or incoming_token in ("******", "••••••••••••••••") or "•" in incoming_token:
            clean_tok = current.get("secret_token") or DEFAULT_SECRET_TOKEN
            if not clean_tok or clean_tok in ("******", "••••••••••••••••") or "•" in clean_tok:
                clean_tok = DEFAULT_SECRET_TOKEN
        else:
            clean_tok = incoming_token

        cfg_to_save = {
            "webhook_url": clean_url,
            "secret_token": clean_tok,
            "auto_sync": bool(auto_sync),
            "drive_folder": "LUV_PDF_Exports/MSDS_Originals"
        }

        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg_to_save, f, ensure_ascii=False, indent=2)
            cls._cached_config = None  # Xóa cache để lần gọi tiếp theo nạp lại cấu hình mới
        except Exception as e:
            logger.error("Lỗi khi lưu cấu hình GAS %s: %s", CONFIG_FILE, e)
            raise RuntimeError(f"Không thể lưu cấu hình Google Apps Script: {e}")

        return cls.get_config()

    @classmethod
    def is_configured(cls) -> bool:
        """Kiểm tra xem hệ thống đã thiết lập Webhook URL hay chưa."""
        cfg = cls.get_config()
        return bool(cfg.get("webhook_url"))

    @classmethod
    def _send_request(
        cls,
        payload: Dict[str, Any],
        custom_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        allow_failover: bool = True
    ) -> Dict[str, Any]:
        """
        Gửi yêu cầu POST an toàn tới Google Apps Script Webhook:
        - Tự động gắn action và token vào query params để bảo toàn qua HTTP 302 Redirect của Google.
        - Tự động Failover sang token dự phòng (ALT_SECRET_TOKEN) nếu gặp lỗi Sai Secret Token.
        - Ghi log chẩn đoán an toàn (masked token).
        """
        cfg = cls.get_config()
        url = (custom_url or cfg.get("webhook_url") or "").strip()
        if not url:
            return {"status": "error", "error": "Chưa cấu hình Google Apps Script Webhook URL."}

        raw_token = payload.get("token") or cfg.get("secret_token") or DEFAULT_SECRET_TOKEN
        token = clean_token(raw_token)
        if not token or token in ("******", "••••••••••••••••") or "•" in str(token):
            token = DEFAULT_SECRET_TOKEN
        payload["token"] = token

        action = str(payload.get("action") or "").strip()

        # Log chẩn đoán an toàn trước khi gọi
        token_src = cfg.get("token_source", "UNKNOWN")
        logger.debug(
            "[GAS_REQ] action=%s | token_source=%s | len=%d | masked=%s",
            action, token_src, len(token), mask_token(token)
        )

        # Đính kèm token và action vào URL query string để chống mất dữ liệu khi Google Redirect 302
        query_params = {}
        if action:
            query_params["action"] = action
        if token:
            query_params["token"] = token
        query_params["_t"] = str(int(time.time() * 1000))

        try:
            resp = requests.post(
                url,
                params=query_params,
                data=json.dumps(payload, ensure_ascii=False),
                timeout=timeout,
                allow_redirects=True,
                headers={"Content-Type": "text/plain;charset=utf-8"}
            )
            text = (resp.text or "").strip()

            # Kiểm tra xem có bị Google chặn chuyển hướng đăng nhập HTML không
            if "<!doctype" in text.lower() or "<html" in text.lower():
                return {
                    "status": "error",
                    "success": False,
                    "is_html": True,
                    "error": (
                        "Google Apps Script phản hồi HTML (Yêu cầu đăng nhập hoặc quyền truy cập). "
                        "Vui lòng mở Google Apps Script (Code.gs), Deploy lại Web App với quyền: "
                        "'Who has access' (Ai có quyền truy cập) là 'Anyone' (Bất kỳ ai)."
                    )
                }

            if resp.status_code == 200:
                try:
                    res_json = resp.json()
                except Exception:
                    return {"status": "ok", "success": True, "raw_response": text[:500]}

                # Nếu phản hồi báo lỗi Secret Token và còn quyền failover
                err_msg = str(res_json.get("error") or "")
                if ("Sai Secret Token" in err_msg or "Sai mã Secret Token" in err_msg) and allow_failover:
                    # Thử tự động đổi sang token dự phòng đối ứng
                    alt_token = PRIMARY_SECRET_TOKEN if token == ALT_SECRET_TOKEN else ALT_SECRET_TOKEN
                    logger.warning(
                        "[GAS_AUTH_FAILOVER] Token '%s' không khớp. Tự động thử lại với token đối ứng '%s'...",
                        mask_token(token), mask_token(alt_token)
                    )
                    payload_alt = dict(payload)
                    payload_alt["token"] = alt_token
                    res_alt = cls._send_request(payload_alt, custom_url=custom_url, timeout=timeout, allow_failover=False)
                    if res_alt.get("status") in ("ok", "success") or res_alt.get("success") is True:
                        logger.info("[GAS_AUTH_FAILOVER_SUCCESS] Đã kết nối thành công với Token đối ứng!")
                        return res_alt

                return res_json
            elif resp.status_code == 403:
                return {
                    "status": "error",
                    "auth_failed": True,
                    "success": False,
                    "error": f"Xác thực thất bại: Sai Secret Token! (HTTP 403: {text[:200]})",
                    "http_status": 403
                }
            else:
                return {
                    "status": "error",
                    "success": False,
                    "error": f"GAS trả về mã HTTP {resp.status_code}: {text[:300]}",
                    "http_status": resp.status_code
                }
        except requests.exceptions.Timeout:
            logger.warning("Google Apps Script Webhook timeout (>%ss) cho action=%s", timeout, action)
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
        target_token = clean_token(raw_token) or DEFAULT_SECRET_TOKEN

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
        res = cls._send_request(payload, custom_url=target_url, timeout=12.0)

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
        chems, _ = cls.fetch_all_with_diagnostics()
        return chems

    @classmethod
    def fetch_all_with_diagnostics(cls) -> Tuple[Optional[List[Dict[str, Any]]], Dict[str, Any]]:
        """
        Lấy danh sách hóa chất kèm thông tin chẩn đoán chi tiết:
        - Ưu tiên GET request (siêu nhanh, không bị vướng LockService trên Google Apps Script).
        - Tự động failover sang POST request nếu GET gặp lỗi.
        Trả về: (chemicals_list_or_None, diagnostic_dict)
        """
        if not cls.is_configured():
            return None, {"status": "skipped", "error": "Chưa cấu hình GAS"}

        cfg = cls.get_config()
        url = (cfg.get("webhook_url") or "").strip()
        raw_token = cfg.get("secret_token") or DEFAULT_SECRET_TOKEN
        token = clean_token(raw_token) or DEFAULT_SECRET_TOKEN

        # 1. Thử GET request trước (1-3 giây, không bị khóa LockService)
        token_candidates = [token]
        alt_tok = PRIMARY_SECRET_TOKEN if token == ALT_SECRET_TOKEN else ALT_SECRET_TOKEN
        if alt_tok not in token_candidates:
            token_candidates.append(alt_tok)

        for trial_token in token_candidates:
            try:
                get_params = {
                    "action": "getAllChemicals",
                    "token": trial_token,
                    "_t": str(int(time.time() * 1000))
                }
                r = requests.get(url, params=get_params, timeout=12.0, allow_redirects=True, headers={"Accept": "application/json"})
                text = (r.text or "").strip()
                if r.status_code == 200 and not ("<!doctype" in text.lower() or "<html" in text.lower()):
                    try:
                        res_json = r.json()
                        err_msg = str(res_json.get("error") or "")
                        if "Sai Secret Token" in err_msg or "Sai mã Secret Token" in err_msg:
                            continue  # Thử token kế tiếp
                        chems = res_json.get("chemicals") if isinstance(res_json.get("chemicals"), list) else res_json.get("data")
                        if isinstance(chems, list):
                            return chems, res_json
                    except Exception:
                        pass
            except Exception as get_err:
                logger.debug("[GAS_GET_FALLBACK] GET lỗi (%s), chuyển sang POST...", get_err)
                break

        # 2. POST request dự phòng
        payload = {
            "action": "getAllChemicals"
        }
        res = cls._send_request(payload, timeout=25.0)
        if res.get("status") in ("ok", "success") or res.get("success") is True:
            chems = res.get("chemicals") if isinstance(res.get("chemicals"), list) else res.get("data")
            if isinstance(chems, list):
                return chems, res

        err_str = str(res.get("error") or res.get("message") or "Unknown error")
        logger.warning("Không thể lấy danh sách hóa chất từ Google Sheet: %s", err_str)
        return None, res

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
    # KÈM EXPONENTIAL BACKOFF RETRY VÀ CHẨN ĐOÁN XÁC THỰC NHANH
    # ==========================================================================

    @classmethod
    def reconcile_on_startup(cls, max_retries: int = 3) -> Dict[str, Any]:
        """
        Hòa giải dữ liệu SQLite với Google Sheets khi máy chủ khởi động:
        1. Google Sheets làm Single Source of Truth (SSOT).
        2. Nếu Google Sheet trống (đã bị xóa sạch trước đó): Xóa sạch SQLite cục bộ!
           Triệt tiêu 100% lỗi 13 hóa chất mẫu git hồi sinh sau Render container restart.
        3. Nếu Google Sheet có dữ liệu: Đồng bộ vào SQLite cache cục bộ.
        4. Tích hợp Exponential Backoff Retry (2s, 4s, 8s) khi gặp sự cố mạng tạm thời.
        5. Nếu gặp lỗi xác thực 'Sai Secret Token!', dừng ngay lập tức (Fail Fast) và báo degraded.
        """
        global GAS_SYNC_STATE

        # Xóa cache để luôn nạp giá trị môi trường mới nhất
        cls._cached_config = None
        cfg = cls.get_config()

        token = cfg.get("secret_token") or DEFAULT_SECRET_TOKEN
        token_src = cfg.get("token_source", "UNKNOWN")
        is_env = cfg.get("token_configured_env", False)

        GAS_SYNC_STATE["last_sync_time"] = datetime.now().isoformat()
        GAS_SYNC_STATE["token_configured"] = is_env
        GAS_SYNC_STATE["token_source"] = token_src
        GAS_SYNC_STATE["retry_count"] = 0

        logger.info(
            "[GAS_STARTUP] Bắt đầu hòa giải khởi động Google Sheets... (Token Source: %s, Masked: %s)",
            token_src, mask_token(token)
        )

        if token_src == "DEFAULT_FALLBACK":
            logger.warning(
                "[GAS_STARTUP_WARN] Đang sử dụng token mặc định hệ thống ('%s'). "
                "Nếu bạn đã cấu hình trên Render, hãy đảm bảo đặt tên biến môi trường là GAS_SECRET_TOKEN.",
                mask_token(token)
            )

        if not cls.is_configured():
            logger.info("MSDS GAS Webhook chưa được cấu hình. Giữ nguyên bộ đệm SQLite.")
            GAS_SYNC_STATE["last_sync_status"] = "skipped"
            GAS_SYNC_STATE["last_sync_error"] = "Webhook URL chưa được cấu hình"
            return {"status": "skipped", "message": "GAS chưa được cấu hình."}

        try:
            from core.msds_intelligence import MSDSDatabase
            MSDSDatabase.init_db()

            delays = [2.0, 4.0, 8.0]
            sheet_chems = None
            last_diag = {}

            for attempt in range(max_retries):
                GAS_SYNC_STATE["retry_count"] = attempt
                logger.info("[GAS_STARTUP] Lần thử hòa giải %d/%d...", attempt + 1, max_retries)

                sheet_chems, last_diag = cls.fetch_all_with_diagnostics()

                if sheet_chems is not None:
                    # Tải thành công danh sách hóa chất từ Google Sheet
                    break

                # Kiểm tra xem có phải lỗi xác thực (Auth Failed) không
                err_msg = str(last_diag.get("error") or "")
                if "Sai Secret Token" in err_msg or "Sai mã Secret Token" in err_msg or last_diag.get("auth_failed"):
                    logger.error(
                        "[GAS_STARTUP_FATAL] Xác thực thất bại: Sai Secret Token! (Token nguồn: %s, Giá trị che: %s). "
                        "Dừng retry ngay lập tức.",
                        token_src, mask_token(token)
                    )
                    GAS_SYNC_STATE["last_sync_status"] = "auth_failed"
                    GAS_SYNC_STATE["last_sync_error"] = f"Xác thực thất bại: Sai Secret Token! ({err_msg})"
                    return {
                        "status": "auth_failed",
                        "token_source": token_src,
                        "token_masked": mask_token(token),
                        "error": "Xác thực thất bại: Sai Secret Token! Vui lòng kiểm tra lại GAS_SECRET_TOKEN trên Render Dashboard.",
                        "details": last_diag
                    }

                # Nếu là lỗi mạng tạm thời hoặc timeout, chờ theo exponential backoff rồi thử lại
                if attempt < max_retries - 1:
                    wait_sec = delays[attempt] if attempt < len(delays) else 5.0
                    logger.warning(
                        "[GAS_STARTUP_RETRY] Lỗi kết nối tạm thời (%s). Chờ %.1fs trước khi thử lại lần %d...",
                        err_msg, wait_sec, attempt + 2
                    )
                    time.sleep(wait_sec)

            if sheet_chems is None:
                err_text = str(last_diag.get("error") or "Không thể kết nối tới Google Sheet sau 3 lần thử.")
                logger.warning(
                    "[GAS_STARTUP_NETWORK] Không thể tải dữ liệu từ Google Sheet sau %d lần thử. "
                    "Giữ nguyên SQLite cục bộ (Network Failure Isolation).",
                    max_retries
                )
                GAS_SYNC_STATE["last_sync_status"] = "network_error"
                GAS_SYNC_STATE["last_sync_error"] = err_text
                return {
                    "status": "skipped",
                    "reason": "network_error",
                    "message": "Không thể kết nối tới Google Sheet; giữ nguyên dữ liệu SQLite cục bộ.",
                    "details": last_diag
                }

            # Trường hợp 1: Google Sheet trống (Người dùng đã xóa toàn bộ trước khi restart)
            if isinstance(sheet_chems, list) and len(sheet_chems) == 0:
                logger.info("[GAS_STARTUP] Google Sheet trống (0 hóa chất). Xóa sạch SQLite cục bộ để chống hồi sinh dữ liệu đã xóa.")
                deleted_count = MSDSDatabase.delete_all_chemicals()
                GAS_SYNC_STATE["last_sync_status"] = "reconciled_empty"
                GAS_SYNC_STATE["last_sync_error"] = None
                GAS_SYNC_STATE["sqlite_chemical_count"] = 0
                return {
                    "status": "reconciled_empty",
                    "total_sheet_records": 0,
                    "cleared_sqlite_records": deleted_count,
                    "message": "Đã làm sạch SQLite cục bộ theo trạng thái trống trên Google Sheet."
                }

            # Trường hợp 2: Google Sheet có dữ liệu
            if isinstance(sheet_chems, list) and len(sheet_chems) > 0:
                logger.info("[GAS_STARTUP] Google Sheet có %d hóa chất. Tiến hành hòa giải SQLite cục bộ...", len(sheet_chems))

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

                local_count = len(MSDSDatabase.list_chemicals())
                GAS_SYNC_STATE["last_sync_status"] = "reconciled_sync"
                GAS_SYNC_STATE["last_sync_error"] = None
                GAS_SYNC_STATE["sqlite_chemical_count"] = local_count

                logger.info("Hoàn tất hòa giải khởi động: %d hóa chất được nạp vào SQLite.", upsert_count)
                return {
                    "status": "reconciled_sync",
                    "total_sheet_records": len(sheet_chems),
                    "upsert_count": upsert_count,
                    "stale_removed": len(stale_ids),
                    "local_db_records": local_count,
                    "message": f"Đã hòa giải thành công {upsert_count} hóa chất từ Google Sheet vào SQLite."
                }

        except Exception as e:
            logger.error("Lỗi trong quá trình hòa giải khởi động Google Sheet: %s", e)
            GAS_SYNC_STATE["last_sync_status"] = "error"
            GAS_SYNC_STATE["last_sync_error"] = str(e)
            return {"status": "error", "error": str(e)}

        return {"status": "ok"}
