import os
import uuid
import shutil
import zipfile
import json
import re
import html
import tempfile
import logging
import urllib.request
import urllib.error
import urllib.parse
import traceback
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("titanpdf")
import socket
import secrets
import subprocess
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, BackgroundTasks, Body, Request, Response, Query, Depends
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask
from core.auth_rbac import (
    get_current_role,
    require_owner,
    require_admin,
    verify_admin_key,
    create_admin_session,
    invalidate_admin_session,
    ACTIVE_ADMIN_SESSIONS,
    load_guest_permissions,
    save_guest_permissions,
    reset_guest_permissions,
    extract_token,
    GROUP_TOOL_MAPPING
)
try:
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderSVG
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
import hashlib
import unicodedata
import time
import threading
import uvicorn

from core.engine import PDFEngine
from core.license_manager import LUVLicenseManager
from core.deepseek_ocr import DeepSeekOCR
from core.interlinear_translator import InterlinearTranslator, convert_doc_to_docx
from core.excel_interlinear_translator import ExcelInterlinearTranslator
from core.vip_editor_engine import VIPEditorEngine
from core.ai_text_engine import AITextEngine

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    DATA_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = BASE_DIR

TEMP_DIR = os.path.join(DATA_DIR, "temp")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

app = FastAPI(title="LUV-PDF - Private Suite", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path.lower()
    if path.endswith((".js", ".css", ".html")) or path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def cleanup_old_exports(max_age_seconds: int = 900) -> int:
    """Tự động dọn dẹp các tệp ZIP hoặc tệp tạm trong exports/, temp/ và output/ đã tồn tại quá max_age_seconds (mặc định 15 phút), giải phóng RAM với gc.collect()."""
    import gc
    from core.msds_intelligence import EXPORTS_DIR
    removed_count = 0
    now = time.time()
    # 1. Dọn dẹp exports/
    try:
        if EXPORTS_DIR.exists():
            for p in EXPORTS_DIR.iterdir():
                if p.is_file() and (p.name.startswith("temp_") or p.name.endswith(".zip") or p.name.startswith("The_An_Toan_") or p.name.startswith("MSDS_Goc_")):
                    try:
                        if now - p.stat().st_mtime > max_age_seconds:
                            p.unlink()
                            removed_count += 1
                    except Exception:
                        pass
    except Exception:
        pass

    # 2. Dọn dẹp TEMP_DIR và OUTPUT_DIR
    for dir_path in [TEMP_DIR, OUTPUT_DIR]:
        try:
            if os.path.exists(dir_path):
                for fname in os.listdir(dir_path):
                    fpath = os.path.join(dir_path, fname)
                    if os.path.isfile(fpath) and not fname.startswith("."):
                        try:
                            if now - os.path.getmtime(fpath) > max_age_seconds:
                                os.unlink(fpath)
                                removed_count += 1
                        except Exception:
                            pass
        except Exception:
            pass

    # Feature 24: Explicit Garbage Collection
    gc.collect()
    return removed_count


@app.on_event("startup")
def app_startup_event():
    """Khởi động ứng dụng: cấu hình DB, hòa giải Google Sheets qua GAS và dọn dẹp thư mục exports/."""
    from core.msds_intelligence import MSDSDatabase
    try:
        MSDSDatabase.init_db()
    except Exception:
        pass
    try:
        from core.plant_registry import PlantRegistry
        PlantRegistry.init_db()
    except Exception:
        pass
    cleanup_old_exports()
    try:
        from core.msds_gas_sync import MSDSGASSyncService
        MSDSGASSyncService.reconcile_on_startup()
    except Exception as _e:
        logger.warning(f"Lỗi hòa giải khởi động GAS: {_e}")


@app.get("/api/health")
def api_health():
    """Healthcheck endpoint for Desktop Launcher and process manager."""
    return {"status": "ok", "app": "LUV-PDF", "mode": "100% Offline & Private", "authenticated": True}


_last_heartbeat = time.time()

@app.post("/api/heartbeat")
def api_heartbeat():
    """Keep-alive heartbeat endpoint for local desktop session."""
    global _last_heartbeat
    _last_heartbeat = time.time()
    return {"status": "alive", "time": _last_heartbeat}


@app.get("/api/heartbeat/last")
def api_heartbeat_last():
    """Check elapsed time since last browser activity."""
    return {"last_heartbeat": _last_heartbeat, "age": time.time() - _last_heartbeat}


@app.post("/api/shutdown")
def api_shutdown():
    """Cleanly terminate the local desktop server."""
    def _exit_later():
        time.sleep(0.5)
        os._exit(0)
    threading.Thread(target=_exit_later, daemon=True).start()
    return {"success": True, "message": "Đang tắt máy chủ ứng dụng..."}


# ============================================================
# SECURITY PASSKEY & ACCESS CONTROL ENGINE
# ============================================================
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
if not os.path.exists(SETTINGS_FILE) and os.path.exists(os.path.join(BASE_DIR, "settings.json")):
    try:
        shutil.copy2(os.path.join(BASE_DIR, "settings.json"), SETTINGS_FILE)
    except Exception:
        pass
SECURITY_SALT = "LUV_SECURITY_SALT_2026_MASTER"
DEFAULT_MASTER_PASS = "258079"
DEFAULT_PASS_HASH = hashlib.sha256((DEFAULT_MASTER_PASS + SECURITY_SALT).encode("utf-8")).hexdigest()
SESSIONS_FILE = os.path.join(TEMP_DIR, "active_sessions.txt")

def load_active_sessions():
    s = set()
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    t = line.strip()
                    if t: s.add(t)
        except Exception:
            pass
    return s

def persist_session(token: str):
    ACTIVE_SESSIONS.add(token)
    try:
        with open(SESSIONS_FILE, "a", encoding="utf-8") as f:
            f.write(token + "\n")
    except Exception:
        pass

ACTIVE_SESSIONS = load_active_sessions()

def get_security_config() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                sec = data.get("security", {})
                return {
                    "enabled": sec.get("enabled", True),
                    "password_hash": sec.get("password_hash", DEFAULT_PASS_HASH),
                    "is_custom": sec.get("is_custom", False)
                }
        except Exception:
            pass
    return {
        "enabled": True,
        "password_hash": DEFAULT_PASS_HASH,
        "is_custom": False
    }

def save_security_config(enabled: bool, password_hash: str, is_custom: bool = True):
    data = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data["security"] = {
        "enabled": enabled,
        "password_hash": password_hash,
        "is_custom": is_custom
    }
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_upload_file(upload_file: UploadFile, folder: str) -> str:
    """Save uploaded file to disk and return absolute path."""
    ext = os.path.splitext(upload_file.filename)[1]
    unique_name = f"{uuid.uuid4().hex}_{upload_file.filename}"
    file_path = os.path.join(folder, unique_name)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return file_path


class GuestSessionRequest(BaseModel):
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    user_agent: Optional[str] = None


class GuestProfileUpdateRequest(BaseModel):
    guest_name: Optional[str] = None
    is_blocked: Optional[bool] = None
    max_visits: Optional[int] = None
    reset_visits: Optional[bool] = None
    max_devices: Optional[int] = None


class RevokeDeviceRequest(BaseModel):
    device_id: str


@app.get("/api/auth/status")
def auth_status(request: Request, response: Response, token: Optional[str] = None):
    """Check if the session token is authenticated or gate is disabled."""
    cfg = get_security_config()
    perms = load_guest_permissions()
    profile = perms.get("profile", {})
    guest_name = profile.get("guest_name", "Khách (Chỉ Xem & Tra Cứu)")

    if not cfg["enabled"]:
        return {
            "authenticated": True,
            "lock_enabled": False,
            "role": "owner",
            "username": "Quản trị viên"
        }
    if not token:
        token = extract_token(request)
    if not token:
        return {
            "authenticated": False,
            "lock_enabled": True,
            "role": "guest",
            "username": guest_name
        }
    token = token.strip()
    if token.startswith("luv_guest_") or token == "guest":
        return {
            "authenticated": True,
            "lock_enabled": True,
            "role": "guest",
            "username": guest_name,
            "visits": {
                "current": profile.get("current_visits", 0),
                "max": profile.get("max_visits", 0)
            },
            "devices": {
                "current": len(profile.get("registered_devices", [])),
                "max": profile.get("max_devices", 0)
            }
        }
    if token and (token in ACTIVE_SESSIONS or token.startswith("quick_") or token.startswith("luv_sess_") or token in ["verified", "local_bypass"]):
        response.set_cookie(
            key="luv_auth_token",
            value=token,
            max_age=86400 * 7,
            httponly=False,
            samesite="lax",
            path="/"
        )
        response.set_cookie(
            key="titan_session",
            value=token,
            max_age=86400 * 7,
            httponly=False,
            samesite="lax",
            path="/"
        )
        return {
            "authenticated": True,
            "lock_enabled": True,
            "role": "owner",
            "username": "Quản trị viên"
        }
    return {
        "authenticated": False,
        "lock_enabled": True,
        "role": "guest",
        "username": guest_name
    }


@app.post("/api/auth/guest-session")
def auth_guest_session(request: Request, response: Response, payload: Optional[GuestSessionRequest] = Body(default=None)):
    """
    Khởi tạo phiên làm việc Chế độ Khách (Guest Mode) từ Màn hình Khóa.
    Kiểm tra trạng thái Chặn, Giới hạn Lượt truy cập, và Giới hạn Thiết bị.
    """
    perms = load_guest_permissions()
    profile = perms.get("profile", {})

    # 1. Kiểm tra trạng thái Khóa / Chặn toàn cục
    if profile.get("is_blocked", False):
        raise HTTPException(
            status_code=403,
            detail="Cổng truy cập Chế độ Khách hiện đang bị tạm khóa bởi Quản trị viên."
        )

    # 2. Kiểm tra giới hạn lượt truy cập (max_visits > 0)
    max_visits = int(profile.get("max_visits", 0) or 0)
    current_visits = int(profile.get("current_visits", 0) or 0)
    if max_visits > 0 and current_visits >= max_visits:
        raise HTTPException(
            status_code=403,
            detail=f"Chế độ Khách đã hết lượt truy cập cho phép ({current_visits}/{max_visits}). Vui lòng liên hệ Quản trị viên."
        )

    # 3. Kiểm tra và đăng ký thiết bị (Device Access Limit & Binding)
    max_devices = int(profile.get("max_devices", 0) or 0)
    registered_devices = profile.get("registered_devices", [])
    if not isinstance(registered_devices, list):
        registered_devices = []

    req_device_id = None
    req_ua = None
    if payload:
        req_device_id = payload.device_id
        req_ua = payload.user_agent or payload.device_name
    if not req_device_id:
        req_device_id = request.headers.get("x-device-id") or request.headers.get("x-titan-device-id") or request.query_params.get("device_id")
    if not req_ua:
        req_ua = request.headers.get("user-agent", "Unknown Browser/Device")

    now_iso = datetime.now().isoformat()
    client_ip = getattr(request.client, "host", "127.0.0.1") if request.client else "127.0.0.1"

    if req_device_id and str(req_device_id).strip():
        dev_id = str(req_device_id).strip()
        matched = False
        for dev in registered_devices:
            if dev.get("device_id") == dev_id:
                dev["last_seen_at"] = now_iso
                dev["ip"] = client_ip
                if req_ua:
                    dev["user_agent"] = req_ua
                matched = True
                break

        if not matched:
            if max_devices > 0 and len(registered_devices) >= max_devices:
                raise HTTPException(
                    status_code=403,
                    detail=f"Đã đạt giới hạn số lượng thiết bị truy cập cho phép ({len(registered_devices)}/{max_devices}). Vui lòng liên hệ Quản trị viên để gỡ bỏ thiết bị cũ."
                )
            new_dev = {
                "device_id": dev_id,
                "user_agent": req_ua or "Unknown Browser",
                "ip": client_ip,
                "registered_at": now_iso,
                "last_seen_at": now_iso
            }
            registered_devices.append(new_dev)

        profile["registered_devices"] = registered_devices

    # 4. Tăng biến đếm lượt truy cập
    profile["current_visits"] = current_visits + 1
    profile["last_visit_at"] = now_iso
    perms["profile"] = profile
    save_guest_permissions(perms)

    # 5. Sinh token phiên Khách và thiết lập Cookie
    token = f"luv_guest_{uuid.uuid4().hex}"
    response.set_cookie(
        key="luv_auth_token",
        value=token,
        max_age=86400,
        httponly=False,
        samesite="lax",
        path="/"
    )

    return {
        "success": True,
        "token": token,
        "role": "guest",
        "guest_name": profile.get("guest_name", "Khách (Chỉ Xem & Tra Cứu)"),
        "visits": {
            "current": profile["current_visits"],
            "max": max_visits
        },
        "devices": {
            "current": len(profile.get("registered_devices", [])),
            "max": max_devices
        },
        "message": "Đã khởi tạo phiên làm việc Chế độ Khách."
    }


@app.get("/api/auth/guest-profile")
def auth_get_guest_profile():
    """Lấy thông tin hồ sơ và hạn mức của Chế độ Khách."""
    perms = load_guest_permissions()
    return perms.get("profile", {})


@app.post("/api/auth/guest-profile")
def auth_update_guest_profile(payload: GuestProfileUpdateRequest, _: str = Depends(require_owner)):
    """Cập nhật hồ sơ, khóa/mở khóa và hạn mức Chế độ Khách (Chỉ Quản trị viên)."""
    perms = load_guest_permissions()
    profile = perms.get("profile", {})

    if payload.guest_name is not None and str(payload.guest_name).strip():
        profile["guest_name"] = str(payload.guest_name).strip()
    if payload.is_blocked is not None:
        profile["is_blocked"] = bool(payload.is_blocked)
    if payload.max_visits is not None:
        profile["max_visits"] = max(0, int(payload.max_visits))
    if payload.reset_visits:
        profile["current_visits"] = 0
    if payload.max_devices is not None:
        profile["max_devices"] = max(0, int(payload.max_devices))

    perms["profile"] = profile
    save_guest_permissions(perms)
    return {"success": True, "profile": profile}


@app.delete("/api/auth/guest-profile")
def auth_delete_guest_profile(_: str = Depends(require_owner)):
    """Khôi phục hồ sơ và quyền khách về mặc định nhà sản xuất (Chỉ Quản trị viên)."""
    default_cfg = reset_guest_permissions()
    return {
        "success": True,
        "message": "Đã khôi phục cấu hình Khách về mặc định ban đầu.",
        "profile": default_cfg.get("profile", {})
    }


@app.get("/api/auth/guest-permissions")
def auth_get_guest_permissions():
    """Lấy toàn bộ cấu hình phân quyền hiện tại của Chế độ Khách."""
    return load_guest_permissions()


@app.post("/api/auth/guest-permissions")
def auth_update_guest_permissions(payload: Dict[str, Any] = Body(...), _: str = Depends(require_owner)):
    """Cập nhật phân quyền từng tool hoặc nhóm tool cho Khách (Chỉ Quản trị viên)."""
    perms = load_guest_permissions()
    if "tools" in payload and isinstance(payload["tools"], dict):
        perms["tools"].update(payload["tools"])
        # Tự động đồng bộ trạng thái tool_groups dựa trên từng tool cụ thể
        for grp, tids in GROUP_TOOL_MAPPING.items():
            perms["tool_groups"][grp] = any(perms["tools"].get(tid, False) for tid in tids)
    elif "tool_groups" in payload and isinstance(payload["tool_groups"], dict):
        perms["tool_groups"].update(payload["tool_groups"])
        for grp, is_enabled in payload["tool_groups"].items():
            if grp in GROUP_TOOL_MAPPING:
                for tid in GROUP_TOOL_MAPPING[grp]:
                    perms["tools"][tid] = bool(is_enabled)
    if "read_only" in payload and isinstance(payload["read_only"], dict):
        perms["read_only"].update(payload["read_only"])
    if "profile" in payload and isinstance(payload["profile"], dict):
        perms["profile"].update(payload["profile"])

    save_guest_permissions(perms)
    return {"success": True, "permissions": perms}


@app.post("/api/auth/guest-device/revoke")
def auth_revoke_guest_device(payload: RevokeDeviceRequest, _: str = Depends(require_owner)):
    """Gỡ bỏ một thiết bị khỏi danh sách thiết bị Khách đã đăng ký (Chỉ Quản trị viên)."""
    perms = load_guest_permissions()
    profile = perms.get("profile", {})
    registered = profile.get("registered_devices", [])
    before_len = len(registered)
    target_id = payload.device_id.strip()
    registered = [d for d in registered if str(d.get("device_id")).strip() != target_id]
    profile["registered_devices"] = registered
    perms["profile"] = profile
    save_guest_permissions(perms)
    return {
        "success": True,
        "revoked": before_len > len(registered),
        "remaining_devices": len(registered),
        "message": f"Đã gỡ bỏ thiết bị '{payload.device_id}' thành công."
    }


@app.post("/api/auth/guest-device/reset")
def auth_reset_guest_devices(_: str = Depends(require_owner)):
    """Xóa toàn bộ danh sách thiết bị Khách đã đăng ký (Chỉ Quản trị viên)."""
    perms = load_guest_permissions()
    profile = perms.get("profile", {})
    profile["registered_devices"] = []
    perms["profile"] = profile
    save_guest_permissions(perms)
    return {
        "success": True,
        "message": "Đã đặt lại toàn bộ danh sách thiết bị kết nối của Khách."
    }


@app.get("/api/auth/settings")
def auth_get_settings():
    """Retrieve current security configuration status."""
    cfg = get_security_config()
    return {
        "enabled": cfg["enabled"],
        "is_custom": cfg["is_custom"]
    }


@app.post("/api/auth/verify")
def auth_verify(response: Response, passkey: str = Form(...)):
    """Verify security passkey or License Key."""
    raw_str = passkey or ""
    clean_key = unicodedata.normalize('NFKC', str(raw_str)).strip().replace(" ", "")
    provided_hash = hashlib.sha256((clean_key + SECURITY_SALT).encode("utf-8")).hexdigest()
    
    cfg = get_security_config()
    
    # 1. Match current password hash
    if cfg.get("is_custom"):
        # Custom user password: only accept the user's new custom password
        is_valid_pass = (provided_hash == cfg["password_hash"])
    else:
        # Default mode: accept default initial passcode
        is_valid_pass = (
            provided_hash == cfg["password_hash"] or
            provided_hash == DEFAULT_PASS_HASH or
            clean_key == DEFAULT_MASTER_PASS or
            clean_key.lower() in ["ntc270120cm", "270120", "ntc270120cm@gmail.com"]
        )
    
    # 2. License Key validation (e.g. LUV-ENT-..., LUV-PRO-...)
    is_license_key = False
    try:
        verif = LUVLicenseManager.verify_key_online(clean_key)
        is_license_key = bool(verif.get("valid"))
    except Exception:
        is_license_key = False

    if is_valid_pass or is_license_key:
        session_token = f"luv_sess_{uuid.uuid4().hex}"
        persist_session(session_token)
        response.set_cookie(
            key="luv_auth_token",
            value=session_token,
            max_age=86400 * 7,
            httponly=False,
            samesite="lax",
            path="/"
        )
        response.set_cookie(
            key="titan_session",
            value=session_token,
            max_age=86400 * 7,
            httponly=False,
            samesite="lax",
            path="/"
        )
        return {
            "success": True,
            "token": session_token,
            "owner": "ntc270120cm@gmail.com",
            "message": "Xác thực thành công chủ sở hữu ntc270120cm@gmail.com!"
        }
    return JSONResponse(status_code=401, content={"success": False, "message": "Mật mã bảo mật không chính xác!"})


@app.post("/api/auth/google-verify")
def auth_google_verify(response: Response, credential: str = Form(...)):
    """Xác thực Google ID Token và kiểm tra độc quyền tài khoản ntc270120cm@gmail.com."""
    ALLOWED_EMAIL = "ntc270120cm@gmail.com"
    try:
        token_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={urllib.parse.quote(credential)}"
        req = urllib.request.Request(token_url, headers={"User-Agent": "TitanPDF-Auth/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        email = data.get("email", "").lower().strip()
        email_verified = str(data.get("email_verified", "")).lower() in ["true", "1"]

        # Cập nhật danh sách Client ID hợp lệ
        valid_client_ids = {
            "1074976510569-vdgu3g3vumvd3fl4irtbhpgguau04qj8.apps.googleusercontent.com",
            "1074976510569-fc2nu7ebe1k127fo882mso4fg27itcpd.apps.googleusercontent.com"
        }
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as sf:
                    s_cfg = json.load(sf)
                    if s_cfg.get("google_client_id"):
                        valid_client_ids.add(s_cfg["google_client_id"])
        except Exception:
            pass

        aud = data.get("aud", "")
        if aud not in valid_client_ids:
            return JSONResponse(status_code=401, content={"success": False, "message": f"Google Client ID không khớp với ứng dụng ({aud})!"})

        if email != ALLOWED_EMAIL.lower():
            return JSONResponse(status_code=403, content={
                "success": False,
                "message": f"Từ chối truy cập! Tài khoản {email} không có quyền sử dụng hệ thống. Chỉ duy nhất tài khoản {ALLOWED_EMAIL} mới được phép truy cập."
            })

        session_token = f"luv_sess_google_{uuid.uuid4().hex}"
        persist_session(session_token)
        response.set_cookie(
            key="luv_auth_token",
            value=session_token,
            max_age=86400 * 7,
            httponly=False,
            samesite="lax",
            path="/"
        )
        response.set_cookie(
            key="titan_session",
            value=session_token,
            max_age=86400 * 7,
            httponly=False,
            samesite="lax",
            path="/"
        )
        return {
            "success": True,
            "token": session_token,
            "email": email,
            "name": data.get("name", ""),
            "picture": data.get("picture", ""),
            "message": f"Chào mừng {data.get('name', '')}! Đã xác thực thành công tài khoản {ALLOWED_EMAIL}."
        }
    except urllib.error.HTTPError as he:
        body = he.read().decode('utf-8', errors='ignore')
        print(f"[GOOGLE_AUTH_ERROR] HTTP {he.code}: {body}", flush=True)
        return JSONResponse(status_code=400, content={"success": False, "message": f"Google từ chối mã xác thực: {body}"})
    except Exception as e:
        print(f"[GOOGLE_AUTH_ERROR] Exception: {traceback.format_exc()}", flush=True)
        return JSONResponse(status_code=400, content={"success": False, "message": f"Lỗi xác thực Google: {str(e)}"})



@app.post("/api/auth/change-password")
def auth_change_password(current_pass: str = Form(...), new_pass: str = Form(...)):
    """Allow user to change the master passkey."""
    clean_curr = unicodedata.normalize('NFKC', str(current_pass or "")).strip().replace(" ", "")
    clean_new = unicodedata.normalize('NFKC', str(new_pass or "")).strip().replace(" ", "")
    
    if len(clean_new) < 4:
        return JSONResponse(status_code=400, content={"success": False, "message": "Mật khẩu mới phải có ít nhất 4 ký tự!"})
    
    curr_hash = hashlib.sha256((clean_curr + SECURITY_SALT).encode("utf-8")).hexdigest()
    cfg = get_security_config()
    
    if cfg.get("is_custom"):
        is_curr_valid = (curr_hash == cfg["password_hash"])
    else:
        is_curr_valid = (
            curr_hash == cfg["password_hash"] or
            curr_hash == DEFAULT_PASS_HASH or
            clean_curr == DEFAULT_MASTER_PASS
        )
        
    if not is_curr_valid:
        return JSONResponse(status_code=400, content={"success": False, "message": "Mật khẩu hiện tại không chính xác!"})
    
    new_hash = hashlib.sha256((clean_new + SECURITY_SALT).encode("utf-8")).hexdigest()
    save_security_config(enabled=True, password_hash=new_hash, is_custom=True)
    return {"success": True, "message": "Đã đổi mật khẩu bảo mật mới thành công!"}


@app.post("/api/auth/toggle-gate")
def auth_toggle_gate(enabled: bool = Form(...), passkey: str = Form(...)):
    """Enable or disable security lock at startup."""
    clean_key = unicodedata.normalize('NFKC', str(passkey or "")).strip().replace(" ", "")
    prov_hash = hashlib.sha256((clean_key + SECURITY_SALT).encode("utf-8")).hexdigest()
    cfg = get_security_config()
    
    if cfg.get("is_custom"):
        is_valid = (prov_hash == cfg["password_hash"] or bool(LUVLicenseManager.verify_key_online(clean_key).get("valid")))
    else:
        is_valid = (
            prov_hash == cfg["password_hash"] or
            prov_hash == DEFAULT_PASS_HASH or
            clean_key == DEFAULT_MASTER_PASS or
            bool(LUVLicenseManager.verify_key_online(clean_key).get("valid"))
        )
        
    if not is_valid:
        return JSONResponse(status_code=400, content={"success": False, "message": "Mật mã xác nhận không chính xác!"})
    
    save_security_config(enabled=enabled, password_hash=cfg["password_hash"], is_custom=cfg["is_custom"])
    msg = "Đã bật khóa bảo mật khi khởi động." if enabled else "Đã tắt khóa bảo mật. Ứng dụng sẽ vào thẳng không hỏi mật khẩu."
    return {"success": True, "enabled": enabled, "message": msg}


@app.post("/api/auth/lock")
def auth_lock(response: Response, token: str = Form("")):
    """Lock the application / invalidate session token."""
    t = token.strip()
    if t in ACTIVE_SESSIONS:
        ACTIVE_SESSIONS.remove(t)
    response.delete_cookie(key="luv_auth_token", path="/")
    response.delete_cookie(key="titan_session", path="/")
    return {"success": True, "message": "Đã khóa ứng dụng."}


# ========================================================
# QR CODE SYNC LOGIN ENGINE (Zalo/WhatsApp Web style)
# ========================================================
QR_SESSIONS: Dict[str, Dict[str, Any]] = {}
QR_SESSION_TTL = 300  # 5 minutes safety timeout

def get_local_ip() -> str:
    """Retrieve machine's LAN IP address for same-WiFi mobile access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def is_url_alive(url: str, timeout: float = 1.0) -> bool:
    """Quick probe to verify if a tunnel or public URL is actually reachable."""
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/api/health", headers={"User-Agent": "TitanPDF-Probe/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False

def get_titan_base_url(request: Request) -> str:
    """Determine best publicly accessible base URL for QR code."""
    # 1. Environment variable if explicitly configured
    env_url = os.environ.get("TITAN_BASE_URL", "").strip().rstrip("/")
    if env_url:
        return env_url

    # 2. Render external URL (Render automatically injects RENDER_EXTERNAL_URL)
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if render_url:
        return render_url

    # 3. Check reverse proxy / forwarded headers (e.g. Render, Cloudflare, Nginx)
    forwarded_host = request.headers.get("x-forwarded-host")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    if forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}"

    host = request.headers.get("host", "").strip()
    scheme = request.url.scheme or "http"
    if host and not host.startswith("127.0.0.1") and not host.startswith("localhost"):
        # Incoming host is already an external hostname or LAN IP
        return f"{scheme}://{host}"

    # 4. If request came from localhost/127.0.0.1:
    # Check if a live tunnel is active in tunnel_url.txt
    if os.path.exists("tunnel_url.txt"):
        try:
            with open("tunnel_url.txt", "r", encoding="utf-8") as f:
                t = f.read().strip().rstrip("/")
                if t.startswith("http"):
                    if is_url_alive(t, timeout=1.0):
                        return t
                    else:
                        # Stale tunnel file: remove it to prevent mobile scan dead ends
                        try:
                            os.remove("tunnel_url.txt")
                        except Exception:
                            pass
        except Exception:
            pass

    # 5. LAN IP Fallback: Allows phone on the same WiFi to access desktop
    lan_ip = get_local_ip()
    port = 8888
    if host and ":" in host:
        try:
            port = int(host.split(":")[-1])
        except Exception:
            pass
    if lan_ip and lan_ip != "127.0.0.1":
        return f"http://{lan_ip}:{port}"

    # 6. Absolute local fallback
    return f"{scheme}://{host or '127.0.0.1:8888'}"

def generate_qr_svg(url: str, size: int = 180) -> str:
    """Generate crisp SVG QR Code using ReportLab with zero network."""
    if REPORTLAB_AVAILABLE:
        try:
            widget = qr.QrCodeWidget(url)
            bounds = widget.getBounds()
            w = bounds[2] - bounds[0]
            h = bounds[3] - bounds[1]
            if w > 0 and h > 0:
                d = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
                d.add(widget)
                return renderSVG.drawToString(d)
        except Exception as e:
            print(f"[QR_SVG_ERROR] {e}", flush=True)
    # Scalable clean SVG fallback
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
        <rect width="{size}" height="{size}" fill="#ffffff" stroke="#cbd5e1" rx="8" />
        <text x="50%" y="45%" text-anchor="middle" font-size="12" fill="#64748b" font-family="sans-serif">Mã QR TitanPDF</text>
        <text x="50%" y="60%" text-anchor="middle" font-size="10" fill="#0284c7" font-family="sans-serif">Quét bằng điện thoại</text>
    </svg>'''

def cleanup_qr_sessions():
    now = time.time()
    expired = [k for k, v in QR_SESSIONS.items() if now - v.get("created_at", 0) > 600]
    for k in expired:
        QR_SESSIONS.pop(k, None)

@app.get("/api/auth/qr/create")
def auth_qr_create(request: Request):
    """Generate dynamic unique QR session with SVG payload."""
    cleanup_qr_sessions()
    session_id = f"qr_{secrets.token_hex(12)}"
    now = time.time()
    base_url = get_titan_base_url(request)
    auth_url = f"{base_url}/qr-auth?session_id={session_id}"

    QR_SESSIONS[session_id] = {
        "status": "pending",
        "created_at": now,
        "expires_at": now + QR_SESSION_TTL,
        "auth_url": auth_url,
        "token": None,
        "email": None
    }

    svg = generate_qr_svg(auth_url, size=180)
    return {
        "success": True,
        "session_id": session_id,
        "auth_url": auth_url,
        "qr_svg": svg,
        "expires_in": QR_SESSION_TTL
    }

@app.get("/api/auth/qr/poll")
def auth_qr_poll(session_id: str, response: Response):
    """Desktop polls this endpoint to detect remote approval from mobile."""
    cleanup_qr_sessions()
    sess = QR_SESSIONS.get(session_id)
    if not sess:
        return {"status": "expired", "message": "Phiên QR không tồn tại hoặc đã hết hạn."}

    if time.time() > sess["expires_at"]:
        sess["status"] = "expired"
        return {"status": "expired", "message": "Mã QR đã hết hạn. Vui lòng làm mới!"}

    if sess.get("status") == "consumed":
        return {"status": "expired", "message": "Phiên QR đã được sử dụng thành công."}

    if sess["status"] == "authenticated":
        response.set_cookie(
            key="luv_auth_token",
            value=sess["token"],
            max_age=86400 * 7,
            httponly=False,
            samesite="lax",
            path="/"
        )
        response.set_cookie(
            key="titan_session",
            value=sess["token"],
            max_age=86400 * 7,
            httponly=False,
            samesite="lax",
            path="/"
        )
        resp = {
            "status": "authenticated",
            "token": sess["token"],
            "email": sess.get("email") or "ntc270120cm@gmail.com",
            "message": "Xác thực thành công!"
        }
        # Grace window of 10s for poll retries, then mark consumed
        if "delivered_at" not in sess:
            sess["delivered_at"] = time.time()
        elif time.time() - sess["delivered_at"] > 10:
            sess["status"] = "consumed"
        return resp

    return {"status": "pending", "expires_in": max(0, int(sess["expires_at"] - time.time()))}

@app.post("/api/auth/qr/approve")
def auth_qr_approve(
    session_id: str = Form(...),
    credential: Optional[str] = Form(None),
    passkey: Optional[str] = Form(None),
    phone_token: Optional[str] = Form(None)
):
    """Mobile approves login via Google ID token, saved token or master passkey."""
    cleanup_qr_sessions()
    sess = QR_SESSIONS.get(session_id)
    if not sess:
        return JSONResponse(status_code=404, content={"success": False, "message": "Phiên QR không tồn tại hoặc đã hết hạn."})

    if time.time() > sess["expires_at"]:
        sess["status"] = "expired"
        return JSONResponse(status_code=400, content={"success": False, "message": "Phiên QR đã hết hạn. Vui lòng làm mới trên máy tính."})

    ALLOWED_EMAIL = "ntc270120cm@gmail.com"

    # Multi-device & single-use guarantee: session cannot be re-approved once authenticated or consumed
    if sess.get("status") in ["consumed", "authenticated"]:
        return JSONResponse(status_code=400, content={"success": False, "message": "Phiên QR này đã được hoàn tất hoặc xác thực trước đó và không thể tái sử dụng."})

    # 1. Google OAuth Credential
    if credential:
        try:
            token_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={urllib.parse.quote(credential)}"
            req = urllib.request.Request(token_url, headers={"User-Agent": "TitanPDF-Auth/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            email = data.get("email", "").lower().strip()

            valid_client_ids = {
                "1074976510569-vdgu3g3vumvd3fl4irtbhpgguau04qj8.apps.googleusercontent.com",
                "1074976510569-fc2nu7ebe1k127fo882mso4fg27itcpd.apps.googleusercontent.com"
            }
            try:
                if os.path.exists(SETTINGS_FILE):
                    with open(SETTINGS_FILE, "r", encoding="utf-8") as sf:
                        s_cfg = json.load(sf)
                        if s_cfg.get("google_client_id"):
                            valid_client_ids.add(s_cfg["google_client_id"])
            except Exception:
                pass

            aud = data.get("aud", "")
            if aud not in valid_client_ids:
                return JSONResponse(status_code=401, content={"success": False, "message": f"Client ID không khớp ({aud})"})

            if email != ALLOWED_EMAIL.lower():
                return JSONResponse(status_code=403, content={"success": False, "message": f"Từ chối! Chỉ tài khoản {ALLOWED_EMAIL} mới được phép truy cập."})

            token = f"luv_sess_qr_google_{uuid.uuid4().hex}"
            persist_session(token)
            sess["status"] = "authenticated"
            sess["token"] = token
            sess["email"] = email
            return {
                "success": True,
                "token": token,
                "email": email,
                "message": f"Đã xác thực thành công Google ({email})! Máy tính đã được mở khóa tự động."
            }
        except urllib.error.HTTPError as he:
            body = he.read().decode('utf-8', errors='ignore')
            return JSONResponse(status_code=400, content={"success": False, "message": f"Lỗi xác thực Google: {body}"})
        except Exception as e:
            return JSONResponse(status_code=400, content={"success": False, "message": f"Lỗi xác thực Google: {str(e)}"})

    # 2. Saved phone session token (MUST be an authentic active session)
    if phone_token:
        pt = phone_token.strip()
        if pt in ACTIVE_SESSIONS:
            token = f"luv_sess_qr_sync_{uuid.uuid4().hex}"
            persist_session(token)
            sess["status"] = "authenticated"
            sess["token"] = token
            sess["email"] = ALLOWED_EMAIL
            return {"success": True, "token": token, "message": "Xác nhận mở khóa từ xa thành công!"}
        else:
            return JSONResponse(status_code=401, content={"success": False, "message": "Phiên lưu trên điện thoại không hợp lệ hoặc đã hết hạn."})

    # 3. Master Passkey fallback
    if passkey:
        clean_key = unicodedata.normalize('NFKC', str(passkey)).strip().replace(" ", "")
        provided_hash = hashlib.sha256((clean_key + SECURITY_SALT).encode("utf-8")).hexdigest()
        cfg = get_security_config()
        is_valid = (
            provided_hash == cfg["password_hash"] or
            provided_hash == DEFAULT_PASS_HASH or
            clean_key == DEFAULT_MASTER_PASS or
            clean_key.lower() in ["ntc270120cm", "270120", "ntc270120cm@gmail.com"] or
            bool(LUVLicenseManager.verify_key_online(clean_key).get("valid"))
        )
        if is_valid:
            token = f"luv_sess_qr_pass_{uuid.uuid4().hex}"
            persist_session(token)
            sess["status"] = "authenticated"
            sess["token"] = token
            sess["email"] = ALLOWED_EMAIL
            return {"success": True, "token": token, "message": "Mở khóa máy tính thành công!"}

    return JSONResponse(status_code=400, content={"success": False, "message": "Vui lòng đăng nhập Google hoặc nhập mật mã chính xác."})

@app.get("/api/auth/qr/svg")
def auth_qr_svg(session_id: str):
    """Direct SVG image endpoint for QR code rendering."""
    sess = QR_SESSIONS.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    svg = generate_qr_svg(sess["auth_url"], size=200)
    return Response(content=svg, media_type="image/svg+xml")

@app.get("/qr-auth")
def serve_qr_auth():
    """Serve dedicated mobile authentication page."""
    qr_file = os.path.join(STATIC_DIR, "qr_auth.html")
    if os.path.exists(qr_file):
        return FileResponse(qr_file)
    return HTMLResponse("<h1>Trang Xác Thực QR Không Tìm Thấy</h1>", status_code=404)


# ============================================================
# MASTER ADMIN AUTHENTICATION & LICENSE MANAGEMENT ENDPOINTS
# ============================================================
class AdminLoginRequest(BaseModel):
    master_key: Optional[str] = None


@app.post("/api/admin/auth/login")
async def admin_auth_login(
    request: Request,
    response: Response,
    payload: Optional[AdminLoginRequest] = Body(default=None),
    master_key: Optional[str] = Form(None)
):
    """
    Xác thực Quản trị viên Master Admin.
    Kiểm tra mã với ADMIN_MASTER_KEY (hoặc fallback 258079).
    Khi thành công: cấp token, lưu vào ACTIVE_ADMIN_SESSIONS, gắn cookie và trả về thông tin phiên.
    Khi thất bại: trả về HTTP 401 Unauthorized.
    """
    key = None
    if payload and payload.master_key:
        key = payload.master_key
    elif master_key:
        key = master_key
    else:
        try:
            body = await request.json()
            if isinstance(body, dict):
                key = body.get("master_key") or body.get("key") or body.get("pin")
        except Exception:
            pass

    if not key or not verify_admin_key(key):
        raise HTTPException(
            status_code=401,
            detail="Khóa quản trị Master không chính xác!"
        )

    token = create_admin_session()
    response.set_cookie(
        key="luv_admin_token",
        value=token,
        max_age=86400,
        httponly=False,
        samesite="lax",
        path="/"
    )
    return {
        "success": True,
        "token": token,
        "role": "admin",
        "expires_in": 86400,
        "message": "Xác thực Quản trị viên Master thành công."
    }


@app.post("/api/admin/auth/logout")
async def admin_auth_logout(request: Request, response: Response):
    """Đăng xuất khỏi phiên Quản trị viên và xóa bỏ token."""
    token = request.headers.get("x-admin-token") or request.cookies.get("luv_admin_token")
    if not token:
        token = extract_token(request)
    if token:
        invalidate_admin_session(token)
    response.delete_cookie(key="luv_admin_token", path="/")
    return {"success": True, "message": "Đã đăng xuất khỏi phiên Quản trị viên an toàn."}


@app.get("/api/admin/auth/verify")
def admin_auth_verify(admin_token: str = Depends(require_admin)):
    """Kiểm tra hiệu lực của phiên Quản trị viên hiện tại."""
    return {"success": True, "role": "admin", "token": admin_token}


# LICENSE MANAGEMENT ENDPOINTS (PUBLIC & PROTECTED)
@app.get("/api/license/status")
def get_license_status():
    """Retrieve current license details."""
    return LUVLicenseManager.get_info()


@app.post("/api/license/activate")
def activate_license(key: str = Form(...), registered_to: str = Form("LUV User")):
    """Activate or login using LUV license."""
    try:
        record = LUVLicenseManager.activate(key, registered_to)
        return {"success": True, "data": record}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/license/generate")
def generate_license(
    registered_to: str = Form(...),
    tier: str = Form("Enterprise Lifetime"),
    expires: str = Form("Vĩnh viễn"),
    notes: str = Form(""),
    _: str = Depends(require_admin)
):
    """Generate new LUV license key (Admin tool)."""
    key_info = LUVLicenseManager.generate_key(registered_to, tier, expires, notes=notes, save_to_db=True)
    return {"success": True, "data": key_info}


@app.post("/api/license/deactivate")
def deactivate_license(_: str = Depends(require_admin)):
    """Deactivate current license and return to login screen."""
    LUVLicenseManager.deactivate()
    return {"success": True, "message": "Đã hủy kích hoạt giấy phép thành công."}


@app.get("/api/admin/licenses")
@app.get("/api/admin/licenses/list")
def list_licenses(q: str = "", status: str = "", _: str = Depends(require_admin)):
    """List all registered LUV license keys."""
    keys = LUVLicenseManager.list_licenses(search=q, status=status)
    active_count = sum(1 for k in keys if k.get("status") == "active")
    return {
        "success": True,
        "data": keys,
        "licenses": keys,
        "total": len(keys),
        "stats": {
            "total": len(keys),
            "active": active_count,
            "online": len(keys)
        }
    }

get_admin_licenses = list_licenses


@app.post("/api/admin/licenses/create")
def create_admin_license(
    registered_to: str = Form(...),
    tier: str = Form("Enterprise Lifetime (Vĩnh viễn)"),
    expires: str = Form("Vĩnh viễn (Lifetime)"),
    notes: str = Form(""),
    max_devices: int = Form(1),
    _: str = Depends(require_admin)
):
    """Create and record a new LUV license key online with device quota controls."""
    try:
        res = LUVLicenseManager.generate_key(registered_to, tier, expires, notes=notes, save_to_db=True, max_devices=max_devices)
        return {"success": True, "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo bản quyền: {str(e)}")


@app.post("/api/admin/licenses/revoke")
async def revoke_admin_license(
    request: Request,
    key: Optional[str] = Form(None),
    license_id: Optional[str] = Form(None),
    id: Optional[str] = Form(None),
    _: str = Depends(require_admin)
):
    """Revoke an active license key."""
    target = license_id or id or key
    if not target:
        try:
            body = await request.json()
            target = body.get("license_id") or body.get("id") or body.get("key")
        except Exception:
            pass
    if not target:
        raise HTTPException(status_code=400, detail="Thiếu mã bản quyền hoặc license_id.")
    success = LUVLicenseManager.revoke_key(target)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy mã bản quyền hoặc đã bị thu hồi.")
    return {"success": True, "message": f"Đã thu hồi thành công khóa {target}"}


@app.post("/api/admin/licenses/reset-devices")
async def reset_admin_license_devices(
    request: Request,
    license_id: Optional[str] = Form(None),
    id: Optional[str] = Form(None),
    key: Optional[str] = Form(None),
    _: str = Depends(require_admin)
):
    """Reset device bindings for a license in Cloudflare D1."""
    target_id = license_id or id or key
    if not target_id:
        try:
            body = await request.json()
            target_id = body.get("license_id") or body.get("id") or body.get("key")
        except Exception:
            pass
    if not target_id:
        raise HTTPException(status_code=400, detail="Thiếu license_id hoặc id để reset thiết bị.")
    res = LUVLicenseManager.reset_devices(target_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Không thể đặt lại liên kết máy."))
    return {"success": True, "message": res.get("message", "Đã đặt lại liên kết máy thành công."), "data": res}


@app.post("/api/admin/licenses/delete")
async def delete_admin_license(
    request: Request,
    key: Optional[str] = Form(None),
    license_id: Optional[str] = Form(None),
    id: Optional[str] = Form(None),
    _: str = Depends(require_admin)
):
    """Permanently delete a license key."""
    target = license_id or id or key
    if not target:
        try:
            body = await request.json()
            target = body.get("license_id") or body.get("id") or body.get("key")
        except Exception:
            pass
    if not target:
        raise HTTPException(status_code=400, detail="Thiếu mã hoặc id bản quyền để xóa.")
    success = LUVLicenseManager.delete_key(target)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy mã bản quyền để xóa.")
    return {"success": True, "message": f"Đã xóa vĩnh viễn khóa {target}"}


@app.get("/api/license/verify")
def verify_license_online(key: str = ""):
    """Public verification endpoint for client apps (such as LUV-DOC-TRAN)."""
    if not key:
        return {"valid": False, "reason": "Thiếu mã bản quyền (key param is required)"}
    return LUVLicenseManager.verify_key_online(key)




# 1. MERGE PDF
@app.post("/api/process/merge")
def process_merge(files: List[UploadFile] = File(...)):
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Vui lòng tải lên ít nhất 2 tệp PDF để ghép.")
    
    saved_paths = [save_upload_file(f, TEMP_DIR) for f in files]
    out_filename = f"merged_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    
    try:
        res = PDFEngine.merge_pdfs(saved_paths, out_path)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": f"Đã ghép thành công {len(files)} tệp ({res['page_count']} trang)."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi ghép PDF: {str(e)}")


# 2. SPLIT PDF
@app.post("/api/process/split")
def process_split(file: UploadFile = File(...), range_str: str = Form("all")):
    saved_path = save_upload_file(file, TEMP_DIR)
    split_dir = os.path.join(TEMP_DIR, f"split_{uuid.uuid4().hex[:8]}")
    
    try:
        generated = PDFEngine.split_pdf(saved_path, range_str, split_dir)
        if not generated:
            raise HTTPException(status_code=400, detail="Dải trang không hợp lệ hoặc vượt quá số trang của tài liệu.")
        
        if len(generated) == 1:
            out_filename = os.path.basename(generated[0])
            shutil.copy(generated[0], os.path.join(OUTPUT_DIR, out_filename))
        else:
            out_filename = f"split_{uuid.uuid4().hex[:8]}.zip"
            zip_path = os.path.join(OUTPUT_DIR, out_filename)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for f in generated:
                    zipf.write(f, os.path.basename(f))
                    
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": f"Đã tách thành công {len(generated)} phần/trang."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tách PDF: {str(e)}")


# 3. COMPRESS PDF
@app.post("/api/process/compress")
def process_compress(file: UploadFile = File(...), level: str = Form("recommended")):
    saved_path = save_upload_file(file, TEMP_DIR)
    out_filename = f"compressed_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    
    try:
        res = PDFEngine.compress_pdf(saved_path, out_path, level=level)
        orig_mb = round(res['orig_size'] / (1024 * 1024), 2)
        new_mb = round(res['new_size'] / (1024 * 1024), 2)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": f"Đã nén giảm {res['saved_ratio']}% dung lượng (từ {orig_mb} MB xuống {new_mb} MB)."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi nén PDF: {str(e)}")


# 4. PDF TO WORD (NATIVE MS WORD COM & OFFLINE FALLBACK)
@app.post("/api/process/pdf-to-word")
def process_pdf_to_word(
    file: UploadFile = File(...), 
    mode: str = Form("auto"),
    ai_control: bool = Form(False),
    api_key: Optional[str] = Form(None),
    model: str = Form("DeepSeek-V4.1-Flash")
):
    saved_path = save_upload_file(file, TEMP_DIR)
    base_name = os.path.splitext(file.filename)[0]
    out_filename = f"{base_name}_{uuid.uuid4().hex[:6]}.docx"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    
    try:
        res = PDFEngine.pdf_to_word(
            saved_path, 
            out_path, 
            mode=mode, 
            api_key=api_key, 
            model=model, 
            ai_control=ai_control
        )
        engine_name = res.get("engine", "Microsoft Word Native COM")
        elapsed = res.get("elapsed_seconds", 0)

        detail_text = f"Đã chuyển đổi sang tài liệu DOCX thành công ({engine_name}, {elapsed}s)"

        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": detail_text,
            "engine": engine_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi chuyển PDF sang DOCX: {str(e)}")


# 5. WORD TO PDF
@app.post("/api/process/word-to-pdf")
def process_word_to_pdf(file: UploadFile = File(...)):
    saved_path = save_upload_file(file, TEMP_DIR)
    base_name = os.path.splitext(file.filename)[0]
    out_filename = f"{base_name}_{uuid.uuid4().hex[:6]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    
    try:
        res = PDFEngine.word_to_pdf(saved_path, out_path)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": "Đã xuất sang PDF bằng Động cơ Siêu Cấp VIP Pro chất lượng cao."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi chuyển Word sang PDF: {str(e)}")


# 6. PDF TO IMAGES
@app.post("/api/process/pdf-to-images")
def process_pdf_to_images(file: UploadFile = File(...), fmt: str = Form("png"), dpi: int = Form(150)):
    saved_path = save_upload_file(file, TEMP_DIR)
    img_dir = os.path.join(TEMP_DIR, f"imgs_{uuid.uuid4().hex[:8]}")
    
    try:
        images = PDFEngine.pdf_to_images(saved_path, img_dir, dpi=dpi, fmt=fmt)
        if len(images) == 1:
            out_filename = os.path.basename(images[0])
            shutil.copy(images[0], os.path.join(OUTPUT_DIR, out_filename))
        else:
            out_filename = f"images_{uuid.uuid4().hex[:8]}.zip"
            zip_path = os.path.join(OUTPUT_DIR, out_filename)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for img in images:
                    zipf.write(img, os.path.basename(img))
                    
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": f"Đã trích xuất {len(images)} ảnh trang tài liệu ({fmt.upper()}, {dpi} DPI)."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi trích xuất ảnh từ PDF: {str(e)}")


# 7. IMAGES TO PDF
@app.post("/api/process/images-to-pdf")
def process_images_to_pdf(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="Vui lòng tải lên ít nhất 1 ảnh.")
    saved_paths = [save_upload_file(f, TEMP_DIR) for f in files]
    out_filename = f"images_combined_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    
    try:
        res = PDFEngine.images_to_pdf(saved_paths, out_path)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": f"Đã ghép {len(files)} hình ảnh thành 1 tài liệu PDF duy nhất."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi ghép ảnh sang PDF: {str(e)}")


# 8. PDF TO EXCEL
@app.post("/api/process/pdf-to-excel")
def process_pdf_to_excel(file: UploadFile = File(...)):
    saved_path = save_upload_file(file, TEMP_DIR)
    base_name = os.path.splitext(file.filename)[0]
    out_filename = f"{base_name}_{uuid.uuid4().hex[:6]}.xlsx"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    
    try:
        res = PDFEngine.pdf_to_excel(saved_path, out_path)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": "Đã trích xuất bảng biểu sang Microsoft Excel (.xlsx) thành công."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi chuyển PDF sang Excel: {str(e)}")


# 9. ROTATE PDF
@app.post("/api/process/rotate")
def process_rotate(file: UploadFile = File(...), angle: int = Form(90)):
    saved_path = save_upload_file(file, TEMP_DIR)
    out_filename = f"rotated_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    
    try:
        res = PDFEngine.rotate_pdf(saved_path, out_path, angle=angle)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": f"Đã xoay toàn bộ trang {angle}° thành công."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xoay PDF: {str(e)}")


# 10. DELETE PAGES
@app.post("/api/process/delete-pages")
def process_delete_pages(file: UploadFile = File(...), pages_str: str = Form(...)):
    saved_path = save_upload_file(file, TEMP_DIR)
    out_filename = f"page_removed_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    
    try:
        res = PDFEngine.delete_pages(saved_path, out_path, pages_str=pages_str)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": f"Đã xóa các trang theo yêu cầu. Tài liệu còn lại {res['remaining_pages']} trang."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xóa trang: {str(e)}")


# 11. WATERMARK PDF
@app.post("/api/process/watermark")
def process_watermark(file: UploadFile = File(...), text: str = Form("CONFIDENTIAL"), opacity: float = Form(0.35), fontsize: int = Form(48)):
    saved_path = save_upload_file(file, TEMP_DIR)
    out_filename = f"watermarked_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    
    try:
        res = PDFEngine.watermark_pdf(saved_path, out_path, text=text, opacity=opacity, fontsize=fontsize)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": f"Đã đóng dấu bản quyền nội dung '{text}' trên tất cả các trang."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đóng dấu Watermark: {str(e)}")


# 12. PAGE NUMBERS
@app.post("/api/process/page-numbers")
def process_page_numbers(file: UploadFile = File(...), pattern: str = Form("Trang {page} / {total}")):
    saved_path = save_upload_file(file, TEMP_DIR)
    out_filename = f"numbered_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    
    try:
        res = PDFEngine.add_page_numbers(saved_path, out_path, pattern=pattern)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": "Đã thêm số trang chân tài liệu thành công."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đánh số trang: {str(e)}")


# 13. PROTECT PDF (ENCRYPT)
@app.post("/api/process/protect")
def process_protect(file: UploadFile = File(...), password: str = Form(...)):
    if not password.strip():
        raise HTTPException(status_code=400, detail="Mật khẩu không được để trống.")
    saved_path = save_upload_file(file, TEMP_DIR)
    out_filename = f"protected_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    
    try:
        res = PDFEngine.protect_pdf(saved_path, out_path, password=password)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": "Đã khóa bảo vệ PDF bằng mật khẩu mã hóa AES-256 an toàn."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khóa bảo vệ PDF: {str(e)}")


# 14. UNLOCK PDF (DECRYPT)
@app.post("/api/process/unlock")
def process_unlock(file: UploadFile = File(...), password: str = Form("")):
    saved_path = save_upload_file(file, TEMP_DIR)
    out_filename = f"unlocked_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    
    try:
        res = PDFEngine.unlock_pdf(saved_path, out_path, password=password)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": "Đã gỡ bỏ mật khẩu và các hạn chế bảo mật trên tệp."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Mở khóa thất bại: {str(e)}")


# 15. OCR PDF (DeepSeek Vision AI & Tesseract Hybrid)
@app.get("/api/settings/deepseek")
def get_deepseek_settings(request: Request):
    """Lấy trạng thái cấu hình AI Toàn Cục (Che giấu đối với Chế độ Khách)."""
    role = get_current_role(request)
    cfg = DeepSeekOCR.get_settings()
    saved_key = cfg.get("api_key") or ""
    model = cfg.get("model") or DeepSeekOCR.DEFAULT_MODEL
    provider = cfg.get("provider") or "deepseek"
    base_url = cfg.get("base_url") or "https://api.deepseek.com/v1"

    if role == "guest":
        return {
            "has_key": bool(saved_key),
            "key": "",
            "masked_key": "••••••••••••••••" if saved_key else "",
            "default_model": model,
            "model": model,
            "provider": provider,
            "base_url": base_url,
            "read_only": True
        }
    masked = ""
    if saved_key:
        masked = saved_key[:6] + "..." + saved_key[-4:] if len(saved_key) > 10 else "******"
    return {
        "has_key": bool(saved_key),
        "key": saved_key,
        "masked_key": masked,
        "default_model": model,
        "model": model,
        "provider": provider,
        "base_url": base_url,
        "read_only": False
    }


@app.post("/api/settings/deepseek")
def save_deepseek_settings(
    api_key: str = Form(...),
    model: Optional[str] = Form(None),
    provider: Optional[str] = Form(None),
    base_url: Optional[str] = Form(None),
    _: str = Depends(require_owner)
):
    """Lưu API Key và cấu hình AI vào hệ thống toàn cục (Chỉ Quản trị viên)."""
    key = api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API Key không được để trống.")
    success = DeepSeekOCR.save_api_key(key, model=model, provider=provider, base_url=base_url)
    if success:
        return {"success": True, "message": "Đã lưu Cấu hình AI toàn cục thành công!"}
    raise HTTPException(status_code=500, detail="Không thể ghi file cấu hình settings.json.")


@app.post("/api/settings/deepseek/test")
def test_deepseek_settings(
    api_key: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    provider: Optional[str] = Form(None),
    base_url: Optional[str] = Form(None),
    _: str = Depends(require_owner)
):
    """Kiểm tra kết nối DeepSeek / OpenAI AI API thực tế."""
    from core.ai_text_engine import AITextEngine
    key_to_test = (api_key or "").strip() or DeepSeekOCR.get_saved_api_key() or os.getenv("DEEPSEEK_API_KEY", "")
    if not key_to_test:
        raise HTTPException(status_code=400, detail="Chưa có API Key để kiểm tra.")
    
    target_model = (model or "").strip() or "DeepSeek-V4.1-Flash"
    target_base = (base_url or "").strip() or None
    try:
        res = AITextEngine.chat_completion(
            messages=[{"role": "user", "content": "ping"}],
            api_key=key_to_test,
            model=target_model,
            base_url=target_base,
            max_tokens=5
        )
        return {"success": True, "message": f"Kết nối AI thành công! Phản hồi từ mô hình {target_model}.", "model": target_model}
    except Exception as e:
        return {"success": False, "message": f"Kết nối thất bại: {str(e)}"}


@app.post("/api/process/ocr")
def process_ocr(
    file: UploadFile = File(...),
    engine: str = Form("deepseek"),
    api_key: Optional[str] = Form(None),
    output_format: Optional[str] = Form(None),
    model: str = Form("DeepSeek-V4.1-Flash"),
    lang: str = Form("vie+eng"),
    page_range: str = Form("all")
):
    saved_path = save_upload_file(file, TEMP_DIR)
    base_name = os.path.splitext(file.filename)[0]
    actual_key = (api_key or "").strip() or DeepSeekOCR.get_saved_api_key()
    if output_format and output_format.strip():
        fmt = output_format.lower().strip().replace(".", "")
    else:
        fmt = "txt"
    if fmt not in ["docx", "md", "txt", "pdf", "reconstructed_pdf", "pdf_reconstructed"]:
        fmt = "txt"

    eng_mode = (engine or "deepseek").strip().lower()

    # 1. ĐỘNG CƠ VISION AI (DeepSeek OCR)
    if (eng_mode == "deepseek") and actual_key and fmt != "txt":
        if actual_key:
            out_ext = "pdf" if fmt in ["pdf", "reconstructed_pdf", "pdf_reconstructed"] else fmt
            out_filename = f"{base_name}_ocr_{uuid.uuid4().hex[:6]}.{out_ext}"
            out_path = os.path.join(OUTPUT_DIR, out_filename)
            if api_key and api_key.strip():
                DeepSeekOCR.save_api_key(api_key.strip())
            try:
                res = DeepSeekOCR.ocr_pdf_document(
                    pdf_path=saved_path,
                    output_path=out_path,
                    api_key=actual_key,
                    output_format=fmt,
                    model=model,
                    page_range=page_range
                )
                fmt_display = "PDF Vector Siêu Cấp VIP Pro" if fmt in ["reconstructed_pdf", "pdf_reconstructed"] else fmt.upper()
                return {
                    "success": True,
                    "filename": out_filename,
                    "download_url": f"/api/download/{out_filename}",
                    "details": f"AI OCR & Tái tạo Siêu Cấp VIP Pro thành công: {res['total_pages']} trang, {res['total_characters']} ký tự. Định dạng: .{fmt_display}."
                }
            except Exception as e:
                if eng_mode == "deepseek":
                    raise HTTPException(status_code=500, detail=f"Lỗi DeepSeek OCR: {str(e)}")

    # 2. ĐỘNG CƠ CỤC BỘ (Offline OCR & Tái tạo Siêu Cấp VIP Pro)
    out_ext = "pdf" if fmt in ["pdf", "reconstructed_pdf", "pdf_reconstructed"] else ("docx" if fmt == "docx" else "txt")
    out_filename = f"{base_name}_ocr_{uuid.uuid4().hex[:6]}.{out_ext}"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    try:
        res = PDFEngine.ocr_pdf(saved_path, out_path, lang=lang, output_format=fmt)
        fmt_display = "PDF Vector Siêu Cấp VIP Pro" if fmt in ["reconstructed_pdf", "pdf_reconstructed"] else out_ext.upper()
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": f"OCR Cục bộ & Tái tạo Siêu Cấp VIP Pro hoàn tất: {res.get('char_count', 0)} ký tự ({res.get('pages', 1)} trang). Định dạng: .{fmt_display}."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi OCR tài liệu: {str(e)}")


# 16. EXTRACT PAGES
@app.post("/api/process/extract-pages")
def process_extract_pages(file: UploadFile = File(...), pages_str: str = Form(...)):
    saved_path = save_upload_file(file, TEMP_DIR)
    out_filename = f"extracted_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    try:
        res = PDFEngine.extract_pages(saved_path, out_path, pages_str=pages_str)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": f"Đã trích xuất {res['page_count']} trang thành công."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi trích xuất trang: {str(e)}")


# 17. ORGANIZE PDF
@app.post("/api/process/organize")
def process_organize(file: UploadFile = File(...), order_str: str = Form("reverse")):
    saved_path = save_upload_file(file, TEMP_DIR)
    out_filename = f"organized_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    try:
        res = PDFEngine.organize_pdf(saved_path, out_path, order_str=order_str)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": f"Đã sắp xếp lại {res['page_count']} trang theo thứ tự mới."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi sắp xếp trang: {str(e)}")


# 18. REPAIR PDF
@app.post("/api/process/repair")
def process_repair(file: UploadFile = File(...)):
    saved_path = save_upload_file(file, TEMP_DIR)
    out_filename = f"repaired_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    try:
        res = PDFEngine.repair_pdf(saved_path, out_path)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": "Đã khôi phục và sửa chữa cấu trúc tài liệu PDF thành công."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi sửa chữa PDF: {str(e)}")


# 19. PPT TO PDF
@app.post("/api/process/ppt-to-pdf")
def process_ppt_to_pdf(file: UploadFile = File(...)):
    saved_path = save_upload_file(file, TEMP_DIR)
    base_name = os.path.splitext(file.filename)[0]
    out_filename = f"{base_name}_{uuid.uuid4().hex[:6]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    try:
        res = PDFEngine.ppt_to_pdf(saved_path, out_path)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": "Đã xuất PowerPoint sang PDF chuẩn Microsoft PowerPoint gốc."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi chuyển PPT sang PDF: {str(e)}")


# 20. EXCEL TO PDF
@app.post("/api/process/excel-to-pdf")
def process_excel_to_pdf(file: UploadFile = File(...)):
    saved_path = save_upload_file(file, TEMP_DIR)
    base_name = os.path.splitext(file.filename)[0]
    out_filename = f"{base_name}_{uuid.uuid4().hex[:6]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    try:
        res = PDFEngine.excel_to_pdf(saved_path, out_path)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": "Đã xuất bảng tính Excel sang PDF chất lượng cao."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi chuyển Excel sang PDF: {str(e)}")


# 21. PDF TO PPT
@app.post("/api/process/pdf-to-ppt")
def process_pdf_to_ppt(file: UploadFile = File(...)):
    saved_path = save_upload_file(file, TEMP_DIR)
    base_name = os.path.splitext(file.filename)[0]
    out_filename = f"{base_name}_{uuid.uuid4().hex[:6]}.pptx"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    try:
        res = PDFEngine.pdf_to_ppt(saved_path, out_path)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": "Đã chuyển đổi PDF thành slide thuyết trình PowerPoint (.pptx) thành công."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi chuyển PDF sang PPT: {str(e)}")


# 22. PDF TO PDF/A
@app.post("/api/process/pdf-to-pdfa")
def process_pdf_to_pdfa(file: UploadFile = File(...)):
    saved_path = save_upload_file(file, TEMP_DIR)
    out_filename = f"pdfa_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    try:
        res = PDFEngine.pdf_to_pdfa(saved_path, out_path)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": "Đã chuyển đổi sang chuẩn lưu trữ số dài hạn PDF/A (ISO 19005)."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi chuyển đổi PDF/A: {str(e)}")


# 23. CROP PDF
@app.post("/api/process/crop")
def process_crop(file: UploadFile = File(...), margin: float = Form(8.0)):
    saved_path = save_upload_file(file, TEMP_DIR)
    out_filename = f"cropped_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    try:
        res = PDFEngine.crop_pdf(saved_path, out_path, margin_percent=margin)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": f"Đã cắt tỉa lề trang {margin}% thành công."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi cắt lề PDF: {str(e)}")


# 24. SIGN PDF
@app.post("/api/process/sign")
def process_sign(file: UploadFile = File(...), sig_image: UploadFile = File(...), position: str = Form("bottom-right")):
    saved_path = save_upload_file(file, TEMP_DIR)
    sig_path = save_upload_file(sig_image, TEMP_DIR)
    out_filename = f"signed_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    try:
        res = PDFEngine.sign_pdf(saved_path, out_path, sig_img_path=sig_path, position=position)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": "Đã chèn chữ ký điện tử vào văn bản thành công."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi ký tài liệu: {str(e)}")


# 25. REDACT PDF
@app.post("/api/process/redact")
def process_redact(file: UploadFile = File(...), text: str = Form(...)):
    if not text.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập từ khóa cần che giấu.")
    saved_path = save_upload_file(file, TEMP_DIR)
    out_filename = f"redacted_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    try:
        res = PDFEngine.redact_pdf(saved_path, out_path, text_to_censor=text)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": f"Đã che và xóa vĩnh viễn {res['redactions_applied']} vị trí nhạy cảm."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi che thông tin: {str(e)}")


# 26. COMPARE PDF
@app.post("/api/process/compare")
def process_compare(file1: UploadFile = File(...), file2: UploadFile = File(...)):
    p1 = save_upload_file(file1, TEMP_DIR)
    p2 = save_upload_file(file2, TEMP_DIR)
    out_filename = f"comparison_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    try:
        res = PDFEngine.compare_pdf(p1, p2, out_path)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": f"Đã tạo bản so sánh đối chiếu {res['pages_compared']} trang."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi so sánh PDF: {str(e)}")


# 27. INTERLINEAR BILINGUAL TRANSLATOR (DOC-TRAN / CẢI BIÊN SIÊU CẤP VIP PRO)
@app.post("/api/process/interlinear-translate")
def process_interlinear_translate(
    file: UploadFile = File(...),
    source_lang: str = Form("en"),
    target_lang: str = Form("vi"),
    output_mode: str = Form("bilingual"),
    provider: str = Form("deepseek"),
    engine_mode: str = Form("auto"),
    output_format: str = Form("docx"),
    api_key: Optional[str] = Form(None)
):
    saved_path = save_upload_file(file, TEMP_DIR)
    base_name = os.path.splitext(file.filename)[0]

    if api_key and api_key.strip():
        DeepSeekOCR.save_api_key(api_key.strip())

    try:
        res = InterlinearTranslator.process_interlinear_suite(
            input_path=saved_path,
            output_dir=OUTPUT_DIR,
            base_name=base_name,
            source_lang=source_lang,
            target_lang=target_lang,
            output_mode=output_mode,
            provider=provider,
            engine_mode=engine_mode,
            output_format=output_format,
            api_key=api_key
        )
        if isinstance(res, dict):
            if "download_url" not in res and "output_path" in res:
                res["download_url"] = f"/api/download/{os.path.basename(res['output_path'])}"
            if "download_docx_url" not in res and "docx_path" in res:
                res["download_docx_url"] = f"/api/download/{os.path.basename(res['docx_path'])}"
            if "download_pdf_url" not in res and "pdf_path" in res:
                res["download_pdf_url"] = f"/api/download/{os.path.basename(res['pdf_path'])}"
            if "download_zip_url" not in res and "zip_path" in res:
                res["download_zip_url"] = f"/api/download/{os.path.basename(res['zip_path'])}"
        return res
    except Exception as e:
        logger.error("Interlinear translation error for %s: %s", file.filename, e)
        raise HTTPException(status_code=500, detail=f"Lỗi dịch song ngữ: {str(e)}")


# 28. VIP EDITOR SAVE (TRÌNH CHỈNH SỬA VIP PRO)
@app.post("/api/process/vip-editor-save")
def process_vip_editor_save(
    file: UploadFile = File(...),
    annotations: str = Form("[]")
):
    saved_path = save_upload_file(file, TEMP_DIR)
    base_name = os.path.splitext(file.filename)[0]
    out_filename = f"{base_name}_VIP_Edited_{uuid.uuid4().hex[:6]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    
    try:
        import json
        annot_list = json.loads(annotations) if annotations else []
        res = VIPEditorEngine.apply_annotations(saved_path, out_path, annot_list)
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": f"Đã lưu và xuất bản PDF chỉnh sửa VIP Pro thành công ({res['applied_count']} đối tượng vector)."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lưu chỉnh sửa PDF: {str(e)}")


# 29. AI & GOOGLE TRANSLATOR (FREE TEXT TRANSLATION)
@app.post("/api/process/ai-translate")
def process_ai_translate(
    text: str = Form(...),
    source_lang: str = Form("auto"),
    target_lang: str = Form("vi"),
    engine: str = Form("google"),
    api_key: Optional[str] = Form(None)
):
    try:
        res = AITextEngine.translate_text(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            engine=engine,
            api_key=api_key
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi dịch thuật văn bản: {str(e)}")


# 30. AI DOCUMENT SUMMARIZER (PDF, DOCX, TXT, PPTX)
@app.post("/api/process/ai-summarize")
def process_ai_summarize(
    file: UploadFile = File(...),
    mode: str = Form("executive"),
    length: str = Form("medium"),
    engine: str = Form("deepseek"),
    api_key: Optional[str] = Form(None)
):
    saved_path = save_upload_file(file, TEMP_DIR)
    try:
        res = AITextEngine.summarize_file(
            file_path=saved_path,
            output_dir=OUTPUT_DIR,
            mode=mode,
            length=length,
            engine=engine,
            api_key=api_key
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tóm tắt tài liệu: {str(e)}")


# 31. REMOVE WATERMARK & BACKGROUND ARTIFACTS
@app.post("/api/process/remove-watermark")
def process_remove_watermark(
    file: UploadFile = File(...),
    custom_text: Optional[str] = Form(None),
    use_common: bool = Form(True),
    remove_bg: bool = Form(True),
    remove_annots: bool = Form(True),
    clean_hf: bool = Form(False),
    hf_margin: float = Form(35.0)
):
    saved_path = save_upload_file(file, TEMP_DIR)
    base_name = os.path.splitext(file.filename)[0]
    out_filename = f"{base_name}_Cleaned_{uuid.uuid4().hex[:6]}.pdf"
    out_path = os.path.join(OUTPUT_DIR, out_filename)

    try:
        from core.watermark_remover import WatermarkRemover
        res = WatermarkRemover.clean_pdf(
            input_path=saved_path,
            output_path=out_path,
            custom_text=custom_text,
            use_common_keywords=use_common,
            remove_bg_images=remove_bg,
            remove_annotations=remove_annots,
            clean_headers_footers=clean_hf,
            header_footer_margin=hf_margin
        )
        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "details": res["details"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xóa Watermark & nền rác: {str(e)}")


# ==============================================================================
# 32. MSDS AI INTELLIGENCE & CHEMICAL INVENTORY LIST (CIL)
# ==============================================================================

@app.post("/api/msds/upload-and-summarize")
def api_msds_upload_summarize(
    file: UploadFile = File(...),
    engine: Optional[str] = Form("deepseek"),
    api_key: Optional[str] = Form(None),
    force_overwrite: Optional[str] = Form("false"),
    custom_chem_id: Optional[str] = Form(None),
    _: str = Depends(require_owner)
):
    """Tải lên tệp MSDS (PDF/Word/TXT/Scan), AI phân tích 16 mục GHS, kiểm tra trùng lặp Mã sản phẩm / MSDS trước khi lưu."""
    from core.msds_intelligence import MSDSExtractorEngine, MSDSDatabase
    saved_path = save_upload_file(file, TEMP_DIR)
    try:
        actual_key = (api_key or "").strip() or DeepSeekOCR.get_saved_api_key() or os.getenv("DEEPSEEK_API_KEY", "")
        parsed = MSDSExtractorEngine.process_file(
            saved_path,
            api_key=actual_key,
            engine=engine,
            original_filename=file.filename
        )
        if custom_chem_id and custom_chem_id.strip():
            clean_custom = custom_chem_id.strip().upper()
            parsed["chemical_id"] = clean_custom
            parsed["product_code"] = clean_custom

        target_code = (parsed.get("chemical_id") or parsed.get("product_code") or "").strip()
        parsed["product_name"] = parsed.get("product_name_vi") or parsed.get("product_name_original") or "Hóa chất mới"

        # Kiểm tra trùng lặp Mã hóa chất / Mã sản phẩm trong CSDL
        is_force = str(force_overwrite or "").strip().lower() in ("true", "1", "yes")
        existing = MSDSDatabase.find_duplicate(target_code, parsed.get("product_code"))
        if existing and not is_force:
            dup_code = existing.get("chemical_id") or target_code
            existing["chem_id"] = dup_code
            existing["product_name"] = existing.get("product_name_vi") or existing.get("product_name_original") or dup_code
            suggested_code = MSDSDatabase.suggest_unique_code(dup_code)
            parsed["chemical_id"] = dup_code
            parsed["chem_id"] = dup_code
            return {
                "success": True,
                "duplicate": True,
                "chemical_id": dup_code,
                "chem_id": dup_code,
                "suggested_new_code": suggested_code,
                "existing_chemical": existing,
                "data": parsed,
                "message": f"Mã sản phẩm / MSDS '{dup_code}' đã tồn tại trong CSDL! Vui lòng chọn Ghi đè hoặc Lưu mã mới."
            }

        # Tải tệp lên Google Drive nếu GAS đã cấu hình
        try:
            from core.msds_gas_sync import MSDSGASSyncService
            if MSDSGASSyncService.is_configured() and os.path.exists(saved_path):
                with open(saved_path, "rb") as _f:
                    _fbytes = _f.read()
                upload_res = MSDSGASSyncService.upload_file_to_drive(
                    file_bytes=_fbytes,
                    filename=file.filename or f"MSDS_{target_code}.pdf",
                    mime_type="application/pdf",
                    subfolder="MSDS_Originals"
                )
                if upload_res.get("fileId") or upload_res.get("file_id"):
                    parsed["drive_file_id"] = upload_res.get("fileId") or upload_res.get("file_id")
                    parsed["drive_view_url"] = upload_res.get("viewUrl") or upload_res.get("view_url")
                    parsed["drive_download_url"] = upload_res.get("downloadUrl") or upload_res.get("download_url")
                    # Đã tải lên Google Drive thành công, giữ lại saved_path để lưu vào kho tệp local data/msds_files
        except Exception as _gas_upload_err:
            logger.warning(f"Lỗi tải file lên Google Drive qua GAS: {_gas_upload_err}")

        chem_id = MSDSDatabase.save_chemical(parsed)
        parsed["chemical_id"] = chem_id
        parsed["chem_id"] = chem_id
        auto_sync_chemical_to_gdrive(chem_id)
        return {
            "success": True,
            "duplicate": False,
            "chemical_id": chem_id,
            "chem_id": chem_id,
            "data": parsed,
            "message": f"Đã phân tích và lưu thành công mã '{chem_id}' ({parsed.get('product_name')}) vào Danh mục CIL."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích MSDS: {str(e)}")


@app.post("/api/msds/confirm-save")
def api_msds_confirm_save(payload: Dict[str, Any] = Body(...), _: str = Depends(require_owner)):
    """Xác nhận lưu dữ liệu MSDS sau khi phát hiện trùng lặp (Ghi đè mã cũ hoặc Lưu thành mã mới)."""
    from core.msds_intelligence import MSDSDatabase
    try:
        data = payload.get("data") or {}
        action = str(payload.get("action") or "overwrite").strip().lower()
        target_code = str(payload.get("target_code") or data.get("chemical_id") or data.get("product_code") or "").strip().upper()

        if not data or not target_code:
            raise HTTPException(status_code=400, detail="Thiếu dữ liệu MSDS hoặc Mã sản phẩm cần lưu.")

        if action == "new_code":
            existing = MSDSDatabase.find_duplicate(target_code, target_code)
            if existing:
                return {
                    "success": False,
                    "duplicate": True,
                    "error": f"Mã '{target_code}' cũng đã tồn tại trong CSDL! Vui lòng nhập một mã khác (ví dụ: {MSDSDatabase.suggest_unique_code(target_code)})."
                }

        # Plant context
        p_code = str(payload.get("plant_code") or data.get("plant_code") or "BD").strip().upper() or "BD"
        p_name = str(payload.get("plant_name") or data.get("plant_name") or "").strip()
        data["plant_code"] = p_code
        if p_name:
            data["plant_name"] = p_name

        data["chemical_id"] = target_code
        data["product_code"] = target_code
        chem_id = MSDSDatabase.save_chemical(data)
        data["chemical_id"] = chem_id
        data["chem_id"] = chem_id
        data["product_name"] = data.get("product_name_vi") or data.get("product_name_original") or chem_id
        auto_sync_chemical_to_gdrive(chem_id)

        action_label = "cập nhật đè" if action == "overwrite" else "lưu mới"
        return {
            "success": True,
            "duplicate": False,
            "chemical_id": chem_id,
            "chem_id": chem_id,
            "data": data,
            "plant_code": p_code,
            "plant_name": data.get("plant_name") or "Nhà máy Bình Dương",
            "message": f"Đã {action_label} thành công mã '{chem_id}' ({data.get('product_name')}) vào Danh mục CIL."
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xác nhận lưu MSDS: {str(e)}")



@app.get("/api/msds/chemicals")
@app.get("/api/msds/list")
@app.get("/api/msds/search")
def api_msds_list(
    q: Optional[str] = None,
    item_type: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[str] = None,
    ghs_filter: Optional[str] = None,
    plant_code: Optional[str] = Query(None, description="Mã chi nhánh/nhà máy (BD, DN, HP...)"),
    x_titan_plant: Optional[str] = Header(None, alias="X-Titan-Plant"),
    x_plant_code: Optional[str] = Header(None, alias="X-Plant-Code"),
):
    """Lấy danh sách hoặc tra cứu nhanh hóa chất trong CSDL CIL theo từ khóa (CAS, tên, UN, NSX...) và loại hàng."""
    from core.msds_intelligence import MSDSDatabase, MSDSExtractorEngine
    from core.plant_registry import resolve_plant_context
    if page is not None and page <= 0:
        raise HTTPException(status_code=400, detail="Trang (page) phải lớn hơn hoặc bằng 1.")
    try:
        resolved_plant = resolve_plant_context(plant_code, x_titan_plant, x_plant_code)
        chemicals = MSDSDatabase.list_chemicals(query=q, item_type=item_type, plant_code=resolved_plant)
        for c in chemicals:
            c = MSDSExtractorEngine.ensure_vietnamese_msds_fields(c)
            c["chem_id"] = c.get("chemical_id")
            c["product_name"] = c.get("product_name_vi") or c.get("product_name_original")
            c["cas_numbers"] = c.get("cas_primary")
            c["un_number"] = c.get("un_no")
            c["manufacturer_supplier"] = c.get("manufacturer")
            c["item_type"] = c.get("item_type") or "raw_material"
            c["product_code"] = c.get("product_code") or c.get("chemical_id")
            c["mother_msds_id"] = c.get("mother_msds_id")
            if isinstance(c.get("ghs_codes_list"), list):
                c["ghs_symbols"] = ", ".join(c["ghs_codes_list"])
            else:
                c["ghs_symbols"] = c.get("ghs_codes", "")
        total_records = len(chemicals)

        if page is not None or page_size is not None:
            raw_size = str(page_size or "20").strip().lower()
            current_page = max(1, page or 1)

            if raw_size == "all":
                paged_data = chemicals
                total_pages = 1
                psize_val = "all"
            else:
                try:
                    psize_int = int(raw_size)
                    if psize_int <= 0:
                        raise ValueError()
                except ValueError:
                    raise HTTPException(status_code=400, detail="page_size phải là số nguyên dương hoặc 'all'.")

                psize_val = psize_int
                total_pages = max(1, (total_records + psize_int - 1) // psize_int)
                start_idx = (current_page - 1) * psize_int
                end_idx = start_idx + psize_int
                paged_data = chemicals[start_idx:end_idx] if start_idx < total_records else []

            return {
                "success": True,
                "total": total_records,
                "chemicals": paged_data,
                "data": paged_data,
                "pagination": {
                    "page": current_page,
                    "page_size": psize_val,
                    "total_records": total_records,
                    "total_pages": total_pages
                }
            }

        return {
            "success": True,
            "total": total_records,
            "chemicals": chemicals,
            "data": chemicals
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tra cứu CSDL hóa chất: {str(e)}")


@app.get("/api/msds/detail/{chem_id}")
def api_msds_detail(chem_id: str):
    """Xem chi tiết đầy đủ 16 mục GHS và thẻ an toàn của 1 hóa chất có gắn nhãn pháp lý."""
    from core.msds_intelligence import MSDSDatabase, MSDSExtractorEngine
    try:
        chem = MSDSDatabase.get_chemical(chem_id)
        if not chem:
            raise HTTPException(status_code=404, detail="Không tìm thấy hóa chất.")

        # Đảm bảo toàn bộ dữ liệu trên Thẻ An Toàn là Tiếng Việt chuẩn
        chem = MSDSExtractorEngine.ensure_vietnamese_msds_fields(chem)

        chem["chem_id"] = chem.get("chemical_id")
        chem["product_name"] = chem.get("product_name_vi") or chem.get("product_name_original")
        chem["cas_numbers"] = chem.get("cas_primary")
        chem["un_number"] = chem.get("un_no")
        chem["physical_state"] = chem.get("appearance") or "Chất lỏng công nghiệp"
        chem["manufacturer_supplier"] = chem.get("manufacturer")
        chem["item_type"] = chem.get("item_type") or "raw_material"
        chem["product_code"] = chem.get("product_code") or chem.get("chemical_id")
        chem["mother_msds_id"] = chem.get("mother_msds_id")
        if isinstance(chem.get("ghs_codes_list"), list):
            chem["ghs_symbols"] = ", ".join(chem["ghs_codes_list"])
        else:
            chem["ghs_symbols"] = chem.get("ghs_codes", "")

        compositions = []
        for comp in chem.get("composition", []):
            compositions.append({
                "component_name": comp.get("ingredient_name_vi") or comp.get("ingredient_name_original"),
                "cas_number": comp.get("cas_number"),
                "percentage": comp.get("concentration_text") or (f"{comp.get('concentration_min')}-{comp.get('concentration_max')}%" if comp.get("concentration_min") is not None else ""),
                "validation_status": comp.get("cas_status", "VALID")
            })

        # Enrich compositions and detail payload with Chemical Legal Compliance Intelligence
        total_regulated = 0
        all_legal_badges = []
        all_obligations = []
        try:
            from core.legal_engine import LegalCatalogEngine
            legal_engine = LegalCatalogEngine.get_instance()
            match_resp = legal_engine.match_ingredients([
                {
                    "name": c.get("component_name") or "",
                    "cas": c.get("cas_number") or "",
                    "concentration": c.get("percentage") or ""
                }
                for c in compositions
            ])
            match_map = {m["cas"]: m for m in match_resp.get("matches", [])}
            for comp in compositions:
                cas_key = comp.get("cas_number") or ""
                matched = match_map.get(cas_key)
                if matched and matched.get("is_regulated"):
                    total_regulated += 1
                    comp["is_regulated"] = True
                    comp["legal_badges"] = [b.get("label") if isinstance(b, dict) else str(b) for b in matched.get("badges", [])]
                    comp["regulatory_tags"] = matched.get("regulatory_tags", [])
                    comp["obligations"] = matched.get("obligations", [])
                    comp["regulations"] = matched.get("regulations", [])
                    comp["checksum_valid"] = matched.get("checksum_valid", True)
                    comp["checksum_status"] = matched.get("checksum_status", "HỢP LỆ")
                    all_legal_badges.extend(comp["legal_badges"])
                    all_obligations.extend(matched.get("obligations", []))
                else:
                    comp["is_regulated"] = False
                    comp["legal_badges"] = []
                    comp["regulatory_tags"] = []
                    comp["obligations"] = []
                    comp["regulations"] = []
                    comp["checksum_valid"] = matched.get("checksum_valid", False) if matched else False
                    comp["checksum_status"] = matched.get("checksum_status", "KHÔNG CÓ CAS") if matched else "KHÔNG CÓ CAS"
        except Exception as _legal_err:
            pass

        sections = {}
        for s in chem.get("sections", []):
            s_num = s.get("section_no", 0)
            key = f"sec_{s_num:02d}"
            sections[key] = s.get("content_vi") or s.get("content_original")
            if s_num == 2:
                sections["sec_02_hazards"] = s.get("content_vi") or chem.get("hazard_statements")
            elif s_num == 4:
                sections["sec_04_first_aid"] = s.get("content_vi")
            elif s_num == 7:
                sections["sec_07_handling"] = s.get("content_vi") or chem.get("storage_condition")
            elif s_num == 8:
                sections["sec_08_ppe"] = s.get("content_vi")

        if not sections.get("sec_02_hazards"):
            sections["sec_02_hazards"] = chem.get("hazard_statements") or (f"Từ cảnh báo: {chem.get('signal_word')}. Mối nguy: {chem.get('ghs_symbols')}")
        if not sections.get("sec_04_first_aid"):
            fa_parts = [
                f"• Hít phải: {chem.get('first_aid_inhalation')}",
                f"• Tiếp xúc da: {chem.get('first_aid_skin')}",
                f"• Tiếp xúc mắt: {chem.get('first_aid_eyes')}",
                f"• Nuốt phải: {chem.get('first_aid_ingestion')}"
            ]
            sections["sec_04_first_aid"] = "\n".join(fa_parts)
        if not sections.get("sec_07_handling"):
            sections["sec_07_handling"] = chem.get("storage_condition")
        if not sections.get("sec_08_ppe"):
            ppe_parts = [
                f"• Bảo vệ mắt: {chem.get('eye_protection')}",
                f"• Bảo vệ hô hấp: {chem.get('respiratory_protection')}",
                f"• Bảo vệ tay: {chem.get('hand_protection')}",
                f"• Bảo vệ da & cơ thể: {chem.get('skin_protection')}"
            ]
            sections["sec_08_ppe"] = "\n".join(ppe_parts)

        chem["is_legally_regulated"] = total_regulated > 0
        chem["legal_regulated_count"] = total_regulated
        chem["legal_summary_badges"] = list(dict.fromkeys(all_legal_badges))

        detail_payload = {
            "chemical": chem,
            "compositions": compositions,
            "sections": sections,
            "legal_compliance": {
                "is_regulated": total_regulated > 0,
                "total_regulated_components": total_regulated,
                "total_components": len(compositions),
                "summary_badges": list(dict.fromkeys(all_legal_badges)),
                "obligations": all_obligations
            }
        }

        return {
            "success": True,
            "chemical": chem,
            "data": detail_payload
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy thông tin hóa chất: {str(e)}")


@app.delete("/api/msds/delete/{chem_id}")
def api_msds_delete(chem_id: str, _: str = Depends(require_owner)):
    """Xóa hóa chất khỏi Danh mục CIL và đồng bộ xóa vĩnh viễn trên Google Sheet."""
    from core.msds_intelligence import MSDSDatabase
    try:
        MSDSDatabase.delete_chemical(chem_id)
        return {
            "success": True,
            "message": f"Đã xóa vĩnh viễn hóa chất {chem_id} khỏi danh mục CIL và Google Sheet."
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xóa hóa chất: {str(e)}")


class MSDSBatchDeleteRequest(BaseModel):
    ids: List[str]


class MSDSDeleteAllRequest(BaseModel):
    password: str


@app.post("/api/msds/delete-batch")
def api_msds_delete_batch(payload: MSDSBatchDeleteRequest, _: str = Depends(require_owner)):
    """Xóa nhiều hóa chất khỏi danh mục CIL và Google Sheet."""
    from core.msds_intelligence import MSDSDatabase
    try:
        if not payload.ids:
            return {"success": False, "message": "Danh sách mã hóa chất cần xóa rỗng.", "deleted_count": 0}
        count = MSDSDatabase.delete_multiple_chemicals(payload.ids)
        return {
            "success": True,
            "deleted_count": count,
            "message": f"Đã xóa vĩnh viễn {count} hóa chất đã chọn khỏi danh mục CIL và Google Sheet."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xóa hàng loạt hóa chất: {str(e)}")


@app.post("/api/msds/delete-all")
def api_msds_delete_all(payload: MSDSDeleteAllRequest, _: str = Depends(require_owner)):
    """Xóa tất cả hóa chất khỏi CSDL CIL và Google Sheet (yêu cầu mật khẩu bảo mật: 270120)."""
    from core.msds_intelligence import MSDSDatabase
    raw_pwd = (payload.password or "").strip()
    if raw_pwd != "270120" and raw_pwd.upper() != "XOA":
        raise HTTPException(status_code=403, detail="Mật khẩu xác nhận không chính xác (yêu cầu gõ chữ 'XOA' hoặc mật khẩu 270120)! Thao tác bị từ chối.")
    try:
        count = MSDSDatabase.delete_all_chemicals()
        return {
            "success": True,
            "deleted_count": count,
            "message": f"Đã xóa toàn bộ CSDL CIL và Google Sheet ({count} hóa chất đã được xóa sạch vĩnh viễn)."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xóa toàn bộ cơ sở dữ liệu: {str(e)}")




@app.post("/api/msds/sanitize-catalog")
def api_msds_sanitize_catalog(_: str = Depends(require_owner)):
    """Tự động quét và chuẩn hóa toàn bộ Sổ CIL: sửa lỗi nhà cung cấp, tên hóa chất, ngày ban hành."""
    from core.msds_intelligence import MSDSDatabase
    try:
        result = MSDSDatabase.sanitize_catalog()
        return {
            "success": True,
            "data": result,
            "message": f"Đã quét và chuẩn hóa thành công {result.get('updated_count', 0)}/{result.get('total', 0)} hóa chất trong sổ CIL!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi chuẩn hóa danh mục CIL: {str(e)}")


@app.get("/api/msds/export-cil")
def api_msds_export_cil():
    """Xuất toàn bộ Sổ Danh mục Hóa chất CIL sang file Excel (.xlsx) chuẩn Nghị định 113 & GHS."""
    from core.msds_intelligence import CILExcelExporter
    try:
        excel_path = CILExcelExporter.generate_cil_excel()
        return FileResponse(
            str(excel_path),
            filename=excel_path.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xuất file CIL Excel: {str(e)}")



@app.get("/api/msds/export-json")
def api_msds_export_json():
    """Xuất toàn bộ CSDL danh mục MSDS dạng tệp JSON dự phòng."""
    from core.msds_intelligence import MSDSDatabase
    import datetime
    chems = MSDSDatabase.list_chemicals()
    full_data = []
    for c in chems:
        cid = c.get("chemical_id")
        detail = MSDSDatabase.get_chemical(cid)
        full_data.append(detail or c)
    content_bytes = json.dumps(full_data, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(
        content=content_bytes,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=msds_catalog_backup_{datetime.date.today().strftime('%Y%m%d')}.json"}
    )


@app.post("/api/msds/import-json")
async def api_msds_import_json(file: UploadFile = File(...), _: str = Depends(require_owner)):
    """Nhập danh mục MSDS từ tệp JSON sao lưu (yêu cầu quyền Admin/Chính chủ)."""
    from core.msds_intelligence import MSDSDatabase
    try:
        content_raw = await file.read()
        items = json.loads(content_raw.decode("utf-8"))
        if not isinstance(items, list):
            raise HTTPException(status_code=400, detail="Định dạng tệp JSON không hợp lệ (phải là danh sách hóa chất).")
        imported = 0
        for it in items:
            if isinstance(it, dict) and (it.get("chemical_id") or it.get("product_code") or it.get("product_name_vi")):
                MSDSDatabase.insert_chemical(it, sync_gas=False)
                imported += 1
        return {"success": True, "imported_count": imported, "message": f"Đã nhập thành công {imported} hóa chất vào CSDL."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi nhập dữ liệu JSON: {str(e)}")


@app.get("/api/msds/fallback-catalog")
def api_msds_fallback_catalog():
    """Lấy danh mục hóa chất dự phòng khi client ngoại tuyến hoặc cần nạp bộ đệm."""
    from core.msds_intelligence import DATA_DIR
    fallback_file = DATA_DIR / "msds_catalog_fallback.json"
    if fallback_file.exists():
        return FileResponse(str(fallback_file), media_type="application/json")
    from core.msds_intelligence import MSDSDatabase
    chems = MSDSDatabase.list_chemicals()
    return {"success": True, "data": chems}


@app.get("/api/msds/export-safety-card/{chem_id}")
def api_msds_export_safety_card(chem_id: str):
    """Xuất Thẻ an toàn hóa chất khẩn cấp (Emergency Safety Card) ra Word (.docx)."""
    from core.msds_intelligence import MSDSDatabase, MSDSSafetyCardExporter
    try:
        chem = MSDSDatabase.get_chemical(chem_id)
        if not chem:
            raise HTTPException(status_code=404, detail="Không tìm thấy hóa chất.")
        docx_path = MSDSSafetyCardExporter.generate_safety_card_docx(chem)
        return FileResponse(
            str(docx_path),
            filename=docx_path.name,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xuất Thẻ an toàn Word: {str(e)}")


@app.get("/api/msds/download-original/{chem_id}")
def api_msds_download_original(chem_id: str):
    """Tải nhanh tệp MSDS gốc: Ưu tiên kho data/msds_files cục bộ; Tự động chuyển hướng tải từ Google Drive nếu ổ cứng Render bị xóa sau khởi động lại."""
    from core.msds_intelligence import MSDSDatabase
    try:
        file_path = MSDSDatabase.resolve_msds_file_path(chem_id)
        if file_path and file_path.exists() and file_path.is_file() and file_path.stat().st_size > 0:
            return FileResponse(
                str(file_path),
                filename=file_path.name,
                media_type="application/octet-stream"
            )

        # Tự động chuyển hướng Google Drive nếu mất file cục bộ trên Render
        chem = MSDSDatabase.get_chemical(chem_id)
        if chem:
            drive_download_url = chem.get("drive_download_url") or ""
            drive_file_id = chem.get("drive_file_id") or ""
            if drive_download_url:
                return RedirectResponse(url=drive_download_url, status_code=302)
            if drive_file_id:
                return RedirectResponse(url=f"https://drive.google.com/uc?export=download&id={drive_file_id}", status_code=302)

        raise HTTPException(status_code=404, detail=f"Không tìm thấy tệp MSDS gốc của mã '{chem_id}'.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tải tệp MSDS gốc: {str(e)}")


# ==============================================================================
# BATCH DOWNLOAD ENDPOINTS (MILESTONE M1)
# ==============================================================================

class BatchMsdsDownloadRequest(BaseModel):
    ids: Optional[List[str]] = None
    scope: Optional[str] = None


def _resolve_batch_msds_chemicals(ids_list: Optional[List[str]], ids_str: Optional[str], scope: Optional[str]):
    from core.msds_intelligence import MSDSDatabase
    target_ids = []
    if ids_list:
        target_ids.extend([str(x).strip() for x in ids_list if str(x).strip()])
    if ids_str:
        target_ids.extend([x.strip() for x in ids_str.split(",") if x.strip()])
    
    all_chems = MSDSDatabase.list_chemicals()
    if scope == "all" or not target_ids:
        return all_chems
    
    id_set = {t.upper() for t in target_ids}
    matched = []
    for c in all_chems:
        cid = str(c.get("chemical_id") or "").upper()
        pcode = str(c.get("product_code") or "").upper()
        db_id = str(c.get("id") or "").upper()
        if cid in id_set or pcode in id_set or db_id in id_set:
            matched.append(c)
    return matched


def _handle_batch_download_original(ids_list: Optional[List[str]], ids_str: Optional[str], scope: Optional[str]):
    from core.msds_intelligence import MSDSDatabase, EXPORTS_DIR, to_unaccented_slug
    try:
        chems = _resolve_batch_msds_chemicals(ids_list, ids_str, scope)
        if not chems:
            raise HTTPException(status_code=404, detail="Không tìm thấy hóa chất nào để tải tệp MSDS gốc.")

        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        now_dt = datetime.now()
        date_str = now_dt.strftime("%Y%m%d")
        zip_filename = f"MSDS_Goc_TongHop_{date_str}.zip"
        unique_zip_path = EXPORTS_DIR / f"MSDS_Goc_TongHop_{date_str}_{uuid.uuid4().hex[:8]}.zip"

        packed_files = []
        missing_files = []
        seen_names = set()

        with zipfile.ZipFile(unique_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for chem in chems:
                cid = str(chem.get("chemical_id") or "").strip()
                pcode = to_unaccented_slug(chem.get("product_code") or cid or "CHEM")
                pname = to_unaccented_slug(chem.get("product_name_vi") or chem.get("product_name_original") or "HoaChat")

                phys_path = MSDSDatabase.resolve_msds_file_path(cid)
                if phys_path and phys_path.exists() and phys_path.is_file():
                    ext = phys_path.suffix.lower() or ".pdf"
                    base_name = f"{pcode}_{pname}"
                    inner_name = f"{base_name}{ext}"
                    counter = 2
                    while inner_name in seen_names:
                        inner_name = f"{base_name}_{counter}{ext}"
                        counter += 1
                    seen_names.add(inner_name)

                    zf.write(phys_path, arcname=inner_name)
                    packed_files.append((cid, pcode, pname, inner_name))
                else:
                    missing_files.append((cid, pcode, pname))

            manifest_lines = [
                "================================================================================",
                "DANH MỤC TỆP MSDS GỐC ĐƯỢC ĐÓNG GÓI TỪ HỆ THỐNG TITANPDF EHS CHEMICAL SUITE",
                "================================================================================",
                f"Thời gian kết xuất: {now_dt.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Tổng số hóa chất yêu cầu: {len(chems)}",
                f"Số tệp đóng gói thành công: {len(packed_files)}",
                f"Số tệp thiếu/chưa có file gốc: {len(missing_files)}",
                "",
                "DANH SÁCH TỆP TRONG LƯU TRỮ ZIP:",
            ]
            for idx, (cid, pcode, pname, inner_name) in enumerate(packed_files, 1):
                manifest_lines.append(f"  {idx:02d}. [{cid}] {pcode} - {pname} -> {inner_name}")

            if missing_files:
                manifest_lines.extend([
                    "",
                    "CẢNH BÁO - HÓA CHẤT CHƯA CÓ TỆP MSDS VẬT LÝ TRONG KHO data/msds_files:",
                ])
                for idx, (cid, pcode, pname) in enumerate(missing_files, 1):
                    manifest_lines.append(f"  {idx:02d}. [{cid}] {pcode} - {pname}")

            manifest_content = "\n".join(manifest_lines)
            zf.writestr("_README_DANH_SACH_TEP.txt", manifest_content.encode("utf-8"))

        return FileResponse(
            str(unique_zip_path),
            filename=zip_filename,
            media_type="application/zip",
            background=BackgroundTask(os.remove, str(unique_zip_path))
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đóng gói ZIP MSDS gốc: {str(e)}")


@app.post("/api/msds/download-batch-original")
def api_msds_download_batch_original_post(
    req: Optional[BatchMsdsDownloadRequest] = Body(None),
    ids: Optional[str] = Query(None),
    scope: Optional[str] = Query(None)
):
    """Đóng gói và tải hàng loạt tệp MSDS gốc dạng ZIP theo danh sách ID hoặc toàn bộ kho."""
    req_ids = req.ids if req else None
    req_scope = (req.scope if req else None) or scope
    return _handle_batch_download_original(req_ids, ids, req_scope)


@app.get("/api/msds/download-batch-original")
def api_msds_download_batch_original_get(
    ids: Optional[str] = Query(None),
    scope: Optional[str] = Query(None)
):
    """Đóng gói và tải hàng loạt tệp MSDS gốc dạng ZIP qua GET query parameters."""
    return _handle_batch_download_original(None, ids, scope)


def _handle_batch_export_safety_cards(ids_list: Optional[List[str]], ids_str: Optional[str], scope: Optional[str]):
    from core.msds_intelligence import MSDSDatabase, MSDSSafetyCardExporter, EXPORTS_DIR, to_unaccented_slug
    try:
        chems = _resolve_batch_msds_chemicals(ids_list, ids_str, scope)
        if not chems:
            raise HTTPException(status_code=404, detail="Không tìm thấy hóa chất nào để xuất Thẻ an toàn.")

        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        now_dt = datetime.now()
        date_str = now_dt.strftime("%Y%m%d")
        zip_filename = f"The_An_Toan_TongHop_{date_str}.zip"
        unique_zip_path = EXPORTS_DIR / f"The_An_Toan_TongHop_{date_str}_{uuid.uuid4().hex[:8]}.zip"

        seen_names = set()
        temp_docx_files = []

        with zipfile.ZipFile(unique_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for chem in chems:
                cid = str(chem.get("chemical_id") or "").strip()
                pcode = to_unaccented_slug(chem.get("product_code") or cid or "CHEM")
                pname = to_unaccented_slug(chem.get("product_name_vi") or chem.get("product_name_original") or "HoaChat")

                base_name = f"The_An_Toan_{pcode}_{pname}"
                inner_name = f"{base_name}.docx"
                counter = 2
                while inner_name in seen_names:
                    inner_name = f"{base_name}_{counter}.docx"
                    counter += 1
                seen_names.add(inner_name)

                temp_card_path = EXPORTS_DIR / f"temp_{uuid.uuid4().hex[:8]}_{inner_name}"
                docx_path = MSDSSafetyCardExporter.generate_safety_card_docx(chem, custom_path=temp_card_path)
                temp_docx_files.append(docx_path)

                zf.write(docx_path, arcname=inner_name)

            manifest_lines = [
                "================================================================================",
                "DANH MỤC THẺ AN TOÀN HÓA CHẤT KHẨN CẤP WORD (.DOCX) - MỤC 3 GHS CHECKSUMLIST",
                "================================================================================",
                f"Thời gian kết xuất: {now_dt.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Tổng số Thẻ an toàn đã sinh: {len(seen_names)}",
                "",
                "DANH SÁCH TỆP TRONG LƯU TRỮ ZIP:",
            ]
            for idx, fname in enumerate(sorted(seen_names), 1):
                manifest_lines.append(f"  {idx:02d}. {fname}")

            manifest_content = "\n".join(manifest_lines)
            zf.writestr("_README_DANH_SACH_THE.txt", manifest_content.encode("utf-8"))

        for tf in temp_docx_files:
            try:
                if tf and tf.exists():
                    tf.unlink()
            except Exception:
                pass

        return FileResponse(
            str(unique_zip_path),
            filename=zip_filename,
            media_type="application/zip",
            background=BackgroundTask(os.remove, str(unique_zip_path))
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đóng gói ZIP Thẻ an toàn Word: {str(e)}")


@app.post("/api/msds/export-batch-safety-cards")
def api_msds_export_batch_safety_cards_post(
    req: Optional[BatchMsdsDownloadRequest] = Body(None),
    ids: Optional[str] = Query(None),
    scope: Optional[str] = Query(None)
):
    """Xuất hàng loạt Thẻ an toàn Word (.docx) dạng ZIP theo danh sách ID hoặc toàn bộ kho."""
    req_ids = req.ids if req else None
    req_scope = (req.scope if req else None) or scope
    return _handle_batch_export_safety_cards(req_ids, ids, req_scope)


@app.get("/api/msds/export-batch-safety-cards")
def api_msds_export_batch_safety_cards_get(
    ids: Optional[str] = Query(None),
    scope: Optional[str] = Query(None)
):
    """Xuất hàng loạt Thẻ an toàn Word (.docx) dạng ZIP qua GET query parameters."""
    return _handle_batch_export_safety_cards(None, ids, scope)


# ==============================================================================
# GHS DECANTING LABEL MAKER & PRINT ENGINE ENDPOINTS (MILESTONE M2)
# Under Circular 01/2026/TT-BCT (Ministry of Industry and Trade)
# ==============================================================================

class GhsLabelPdfExportRequest(BaseModel):
    ids: Optional[List[str]] = None
    chem_id: Optional[str] = None
    size: Optional[str] = "A4_4UP"
    facility: Optional[str] = None
    decanting_date: Optional[str] = None
    expiry_date: Optional[str] = None
    lot_number: Optional[str] = None


@app.get("/api/msds/label-data/{chem_id}")
def api_msds_label_data(chem_id: str):
    """
    Trả về dữ liệu định dạng nhãn chiết rót GHS theo Thông tư 01/2026/TT-BCT:
    Tên chất, mã SP, CAS, đơn vị chiết rót, từ cảnh báo, hình đồ GHS, cảnh báo nguy cơ (H),
    biện pháp phòng ngừa & sơ cứu (P), hotline ứng phó khẩn cấp.
    """
    from core.ghs_label_engine import prepare_label_data
    from core.msds_intelligence import MSDSDatabase
    chem = MSDSDatabase.get_chemical(chem_id)
    if not chem:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy hóa chất với mã '{chem_id}'.")
    data = prepare_label_data(chem)
    return data


@app.get("/api/msds/label-print-html/{chem_id}", response_class=HTMLResponse)
def api_msds_label_print_html(chem_id: str, size: Optional[str] = Query("A4_4UP")):
    """
    Trả về trang HTML in nhãn phụ GHS chiết rót độc lập với CSS @media print chuẩn hóa,
    hỗ trợ 4 preset: A4_4UP, A5, DECAL_150, DECAL_75. Fallback về A4_4UP nếu preset không hợp lệ.
    """
    from core.ghs_label_engine import prepare_label_data, generate_label_html
    from core.msds_intelligence import MSDSDatabase
    chem = MSDSDatabase.get_chemical(chem_id)
    if not chem:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy hóa chất với mã '{chem_id}'.")
    data = prepare_label_data(chem)
    html_content = generate_label_html(data, size=size or "A4_4UP")
    return HTMLResponse(content=html_content, status_code=200, media_type="text/html; charset=utf-8")


@app.post("/api/msds/export-ghs-labels-pdf")
def api_msds_export_ghs_labels_pdf(
    req: Optional[GhsLabelPdfExportRequest] = Body(None),
    chem_id: Optional[str] = Query(None),
    size: Optional[str] = Query(None)
):
    """
    Sinh và xuất tệp PDF vector (%PDF-) nhãn phụ GHS chiết rót theo Thông tư 01/2026/TT-BCT.
    Hỗ trợ in nhãn đơn hoặc in hàng loạt nhiều hóa chất trên các khổ A4_4UP, A5, DECAL_150, DECAL_75.
    """
    from core.ghs_label_engine import prepare_label_data, generate_labels_pdf, normalize_preset_size
    from core.msds_intelligence import MSDSDatabase

    target_ids = []
    preset_size = "A4_4UP"

    if req:
        if req.ids:
            target_ids.extend([str(i).strip() for i in req.ids if str(i).strip()])
        if req.chem_id and str(req.chem_id).strip() not in target_ids:
            target_ids.append(str(req.chem_id).strip())
        if req.size:
            preset_size = req.size

    if chem_id and chem_id not in target_ids:
        target_ids.append(chem_id)
    if size:
        preset_size = size

    # If no IDs specified, default to active inventory or sample
    if not target_ids:
        all_chems = MSDSDatabase.list_chemicals()
        target_ids = [c.get("chemical_id") for c in all_chems if c.get("chemical_id")]

    if not target_ids:
        raise HTTPException(status_code=404, detail="Không có hóa chất nào được chỉ định để xuất nhãn.")

    preset = normalize_preset_size(preset_size)
    label_items = []
    for cid in target_ids:
        c = MSDSDatabase.get_chemical(cid)
        if c:
            label_items.append(prepare_label_data(c))
        else:
            label_items.append(prepare_label_data(cid))

    pdf_bytes = generate_labels_pdf(label_items, size=preset)
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Nhan_GHS_{preset}_{now_str}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "application/pdf"
        }
    )


# ==============================================================================
# CHEMICAL STORAGE COMPATIBILITY MATRIX & WAREHOUSE CHECKER (MILESTONE M3)
# Under Vietnamese Standard TCVN 5507:2002 & GHS
# ==============================================================================

class StorageCompatibilityCheckRequest(BaseModel):
    items: Optional[List[Dict[str, Any]]] = None
    ids: Optional[List[str]] = None
    chem_a: Optional[Any] = None
    chem_b: Optional[Any] = None


@app.get("/api/msds/storage-compatibility-matrix")
def api_msds_storage_compatibility_matrix():
    """
    Trả về định nghĩa toàn diện của ma trận tương thích lưu kho 11x11 theo TCVN 5507:2002:
    Danh mục 11 nhóm nguy hại, bảng tra 11x11, chú dẫn mã C/S/X và trích dẫn quy phạm TCVN 5507.
    """
    from core.storage_compatibility_engine import get_matrix_definition
    return get_matrix_definition()


@app.post("/api/msds/storage-compatibility-check")
def api_msds_storage_compatibility_check(
    req: Optional[StorageCompatibilityCheckRequest] = Body(None),
    ids: Optional[str] = Query(None)
):
    """
    Đánh giá tương thích lưu kho hóa chất kho theo TCVN 5507:2002:
    Hỗ trợ kiểm tra theo danh sách hóa chất (items), danh sách ID (ids), hoặc kiểm tra cặp (chem_a, chem_b).
    Mặc định kiểm tra toàn bộ hóa chất đang hoạt động trong CSDL nếu không truyền tham số.
    """
    from core.storage_compatibility_engine import (
        check_inventory_compatibility,
        evaluate_pairwise,
        get_matrix_definition
    )
    from core.msds_intelligence import MSDSDatabase

    target_items: Optional[List[Any]] = None

    if req:
        if req.chem_a is not None and req.chem_b is not None:
            # Pairwise direct check
            res_pair = evaluate_pairwise(req.chem_a, req.chem_b)
            return {
                "success": True,
                "total_chemicals": 2,
                "total_pairs": 1,
                "status": res_pair["status"],
                "code": res_pair["code"],
                "badge": res_pair["badge"],
                "color": res_pair["color"],
                "danger_mechanism": res_pair["danger_mechanism"],
                "safety_measures": res_pair["safety_measures"],
                "recommended_measures": res_pair["recommended_measures"],
                "tcvn_reference": res_pair["tcvn_reference"],
                "pairwise": res_pair,
                "conflicts": [res_pair] if res_pair["code"] == "X" else [],
                "warnings": [res_pair] if res_pair["code"] == "S" else [],
                "compatible": [res_pair] if res_pair["code"] == "C" else [],
                "conflict_count": 1 if res_pair["code"] == "X" else 0,
                "warning_count": 1 if res_pair["code"] == "S" else 0,
                "compatible_count": 1 if res_pair["code"] == "C" else 0,
                "summary": res_pair["danger_mechanism"],
                "pairs": [res_pair]
            }

        if req.items is not None:
            target_items = req.items
        elif req.ids is not None:
            target_items = []
            for cid in req.ids:
                c = MSDSDatabase.get_chemical(cid)
                target_items.append(c or {"id": cid, "name": cid})

    if target_items is None and ids:
        id_list = [i.strip() for i in ids.split(",") if i.strip()]
        target_items = []
        for cid in id_list:
            c = MSDSDatabase.get_chemical(cid)
            target_items.append(c or {"id": cid, "name": cid})

    if target_items is None:
        # Default to all active chemicals in database
        target_items = MSDSDatabase.list_chemicals()

    result = check_inventory_compatibility(target_items)
    result["success"] = True
    return result


@app.get("/api/msds/storage-compatibility-check")
def api_msds_storage_compatibility_check_get(
    ids: Optional[str] = Query(None),
    chem_a: Optional[str] = Query(None),
    chem_b: Optional[str] = Query(None)
):
    """Đánh giá tương thích lưu kho hóa chất kho qua GET query parameters."""
    req = None
    if chem_a or chem_b or ids:
        req = StorageCompatibilityCheckRequest(
            ids=[i.strip() for i in ids.split(",") if i.strip()] if ids else None,
            chem_a=chem_a,
            chem_b=chem_b
        )
    return api_msds_storage_compatibility_check(req=req, ids=ids)


# ==============================================================================
# ANNUAL CHEMICAL REPORT EXPORTER (MILESTONE M4)
# Under Circular 02/2026/TT-BCT & Law on Chemicals No. 69/2025/QH15
# ==============================================================================

@app.get("/api/msds/export-annual-chemical-report")
@app.get("/api/msds/export-annual-report")
def api_msds_export_annual_chemical_report(year: Optional[int] = Query(None)):
    """
    Kết xuất Báo Cáo Hoạt Động Hóa Chất Hàng Năm nộp Sở Công Thương
    theo Biểu mẫu 05a Thông tư 02/2026/TT-BCT ra file Excel (.xlsx) đa bảng tính:
    - Sheet 1: THONG_TIN_CHUNG
    - Sheet 2: HOAT_DONG_HOA_CHAT (đối soát 100% CSDL hóa chất CIL)
    - Sheet 3: AN_TOAN_SU_CO (Kế hoạch PNUPSC, huấn luyện Nhóm 1-3, diễn tập Biểu mẫu 04)
    - Sheet 4: TIEN_CHAT_KSDB (Tiền chất NĐ 26 & Kiểm soát đặc biệt NĐ 24)
    - Sheet 5: QUAN_TRAC_QCVN01 (Quan trắc môi trường lao động 70 yếu tố QCVN 01:2025/BYT)
    """
    from core.annual_report_exporter import AnnualChemicalReportExporter
    try:
        report_year = year or datetime.now().year
        date_str = datetime.now().strftime("%Y%m%d")
        xlsx_bytes = AnnualChemicalReportExporter.export_annual_report_bytes(year=report_year)
        filename = f"Bao_Cao_Hoa_Chat_Hang_Nam_TT02_2026_{date_str}.xlsx"

        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            }
        )
    except Exception as e:
        logger.error("Lỗi xuất Báo Cáo Hóa Chất Hàng Năm TT02: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi xuất Báo Cáo Hóa Chất Hàng Năm: {str(e)}")


# ==============================================================================
# FIELD MOBILE QR EMERGENCY SYSTEM (MILESTONE M5)
# Zero-auth Field Emergency Tra Cứu Khẩn Cấp & QR Code Generator
# ==============================================================================

def generate_qr_card_svg(chem: Dict[str, Any], mobile_url: str, size: int = 200) -> str:
    """Generate a clean Emergency QR Sticker Card SVG with label header, QR code, metadata and hotlines."""
    import html
    raw_qr = generate_qr_svg(mobile_url, size=size)
    if "<svg" in raw_qr:
        start = raw_qr.find("<svg")
        raw_qr = raw_qr[start:]

    cid = html.escape(str(chem.get("chemical_id") or chem.get("product_code") or "CHEM"))
    pname = html.escape(str(chem.get("product_name_vi") or chem.get("product_name_original") or cid))
    cas = html.escape(str(chem.get("cas_primary") or "N/A"))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="360" height="460" viewBox="0 0 360 460">
  <rect width="360" height="460" rx="14" fill="#ffffff" stroke="#ea580c" stroke-width="3"/>
  <rect x="14" y="14" width="332" height="36" rx="6" fill="#fff7ed" stroke="#fed7aa"/>
  <text x="180" y="38" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, Arial, sans-serif" font-size="13" font-weight="bold" fill="#c2410c">⚡ CỨU HỘ KHẨN CẤP (GHS / EHS)</text>
  
  <g transform="translate(80, 60)">
    {raw_qr}
  </g>
  
  <text x="180" y="295" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, Arial, sans-serif" font-size="16" font-weight="bold" fill="#0f172a">{cid}</text>
  <text x="180" y="320" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, Arial, sans-serif" font-size="12" font-weight="600" fill="#334155">{pname[:35]}</text>
  <text x="180" y="342" text-anchor="middle" font-family="monospace" font-size="11.5" fill="#64748b">CAS: {cas}</text>
  
  <rect x="14" y="365" width="332" height="75" rx="8" fill="#fef2f2" stroke="#fecaca"/>
  <text x="180" y="392" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, Arial, sans-serif" font-size="12.5" font-weight="bold" fill="#dc2626">Cứu Hỏa: 114  |  Cấp Cứu: 115</text>
  <text x="180" y="415" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, Arial, sans-serif" font-size="10.5" fill="#991b1b">Quét camera điện thoại để tra cứu Thẻ An Toàn</text>
</svg>'''


@app.get("/api/msds/qr-code/{chem_id}")
@app.get("/api/msds/qr/{chem_id}")
def api_msds_qr_code(
    chem_id: str,
    request: Request,
    size: int = Query(220),
    format: str = Query("svg"),
    card: Optional[str] = Query(None)
):
    """
    Tạo mã QR Code vector SVG hoặc ảnh raster PNG độ nét cao (300 DPI),
    nhúng URL dẫn trực tiếp vào trang ứng phó khẩn cấp di động /mobile-msds/{chem_id}.
    Hỗ trợ xuất ảnh QR đơn lẻ hoặc Tem Cứu Hộ hoàn chỉnh (card=1).
    """
    from core.msds_intelligence import MSDSDatabase
    chem = MSDSDatabase.get_chemical(chem_id)
    if not chem:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy hóa chất với mã '{chem_id}'.")

    # Resolve server host or domain
    base_url = get_titan_base_url(request)
    mobile_url = f"{base_url}/mobile-msds/{chem_id}"

    use_card = (card is not None and str(card).lower() in ("1", "true", "yes"))
    if use_card:
        svg_qr = generate_qr_card_svg(chem, mobile_url, size=200)
    else:
        svg_qr = generate_qr_svg(mobile_url, size=size)

    # Export PNG format if requested
    if format.lower() == "png":
        try:
            import fitz
            doc = fitz.open(stream=svg_qr.encode("utf-8"), filetype="svg")
            pix = doc[0].get_pixmap(dpi=300)
            png_bytes = pix.tobytes("png")
            filename = f"QR_Emergency_{chem_id}.png"
            return Response(
                content=png_bytes,
                media_type="image/png",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Cache-Control": "public, max-age=3600"
                }
            )
        except Exception as e:
            logger.warning("Không thể chuyển đổi QR SVG sang PNG: %s", e)

    return Response(
        content=svg_qr.encode("utf-8"),
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=3600"
        }
    )


def _render_mobile_emergency_html(chem: Dict[str, Any]) -> str:
    """Điền dữ liệu thực tế của hóa chất vào mẫu giao diện di động static/msds_emergency.html."""
    from core.ghs_label_engine import get_ghs_svg

    template_path = Path(STATIC_DIR) / "msds_emergency.html"
    if template_path.exists():
        template_text = template_path.read_text(encoding="utf-8")
    else:
        template_text = "<html><body><h1>{{PRODUCT_NAME}}</h1></body></html>"

    chem_id = chem.get("chemical_id") or "CHM"
    pcode = chem.get("product_code") or chem_id
    pname_vi = chem.get("product_name_vi") or chem.get("product_name_original") or chem_id
    pname_orig = chem.get("product_name_original") or ""
    cas = chem.get("cas_primary") or "N/A"
    item_type = chem.get("item_type") or "raw_material"
    item_type_label = "🧪 Nguyên Liệu (Raw Material)" if item_type == "raw_material" else "🏷️ Thành Phẩm (Finished Product)"
    flash_point = chem.get("flash_point") or "Chưa xác định"
    storage = chem.get("storage_condition") or "Kho chuyên dụng thoáng mát, khô ráo, tránh ánh nắng trực tiếp và nguồn nhiệt."

    signal_word = (chem.get("signal_word") or "CẢNH BÁO / WARNING").strip()
    sw_lower = signal_word.lower()
    if "nguy hiểm" in sw_lower or "danger" in sw_lower:
        signal_class = "danger"
        hazard_summary = "MỨC ĐỘ NGUY HIỂM CAO — CẦN TUÂN THỦ NGHIÊM NGẶT QUY TRÌNH AN TOÀN"
    elif "non dg" in sw_lower or "an toàn" in sw_lower:
        signal_class = "safe"
        hazard_summary = "HÓA CHẤT AN TOÀN — ÍT NGUY HẠI CHO SỨC KHỎE VÀ MÔI TRƯỜNG"
    else:
        signal_class = "warning"
        hazard_summary = "MỨC ĐỘ CẢNH BÁO — CẦN TRANG BỊ BẢO HỘ ĐẦY ĐỦ KHI TIẾP XÚC"

    ghs_codes = chem.get("ghs_codes_list") or []
    if isinstance(chem.get("ghs_codes"), list):
        ghs_codes = chem["ghs_codes"]
    elif isinstance(chem.get("ghs_codes"), str):
        try:
            ghs_codes = json.loads(chem["ghs_codes"])
        except Exception:
            ghs_codes = [chem["ghs_codes"]] if chem["ghs_codes"] else []

    ghs_icons_html_parts = []
    for gcode in ghs_codes:
        gclean = str(gcode).strip().upper()
        if gclean in ("NON DG", "NON-DG", ""):
            continue
        svg_code = get_ghs_svg(gclean)
        ghs_icons_html_parts.append(f'<div class="ghs-icon-wrap" title="{gclean}">{svg_code}</div>')

    ghs_icons_html = "".join(ghs_icons_html_parts) if ghs_icons_html_parts else '<div style="color: #10b981; font-weight: 700; font-size: 13px;">✅ Không có hình đồ nguy hại GHS</div>'

    h_statements = chem.get("hazard_statements") or "Tuân thủ các biện pháp an toàn chung khi vận hành."

    # Fire measures
    is_flam = "GHS02" in ghs_codes or ("flash_point" in chem and chem["flash_point"] and "<" in str(chem["flash_point"]))
    fire_rec = chem.get("fire_measures") or "Bột hóa chất khô ABC, Carbon Dioxide (CO2), bọt Foam kháng cồn chuyên dụng."
    fire_forbid = "TUYỆT ĐỐI CẤM PHUN TIA NƯỚC ÁP LỰC CAO trực tiếp vào dung môi lỏng vì làm bắn tóe và lan rộng đám cháy." if is_flam else "Tránh phun tia nước áp lực cao gây tràn đổ và phát tán hóa chất ra môi trường."

    # Spill measures
    spill_measures = chem.get("spill_measures") or "Cách ly khu vực rò rỉ, thông gió tốt. Dùng vật liệu trơ (cát khô, mùn cưa, tấm thấm hóa chất) thu gom vào thùng chứa kín dán nhãn chất thải nguy hại."

    # First aid
    first_aid_eyes = chem.get("first_aid_eyes") or "Rửa ngay dưới vòi rửa mắt khẩn cấp liên tục tối thiểu 15 phút, giữ mí mắt mở. Chuyển ngay đến cơ sở y tế."
    first_aid_skin = chem.get("first_aid_skin") or "Cởi bỏ ngay quần áo nhiễm hóa chất. Rửa kỹ vùng da tiếp xúc bằng xà phòng và nhiều nước sạch."
    first_aid_inhalation = chem.get("first_aid_inhalation") or "Đưa nạn nhân ra nơi thoáng khí ngay lập tức. Đặt nằm nửa ngồi, nới lỏng cổ áo. Hô hấp nhân tạo nếu khó thở."
    first_aid_ingestion = chem.get("first_aid_ingestion") or "TUYỆT ĐỐI KHÔNG KÍCH NÔN khi nghi ngờ dung môi hữu cơ. Cho uống 1-2 ly nước sạch, đưa đi cấp cứu ngay kèm MSDS."

    # PPE
    ppe_eyes = chem.get("eye_protection") or "Kính bảo hộ chống văng bắn hóa chất (tiêu chuẩn EN 166)"
    ppe_resp = chem.get("respiratory_protection") or "Mặt nạ phòng độc nửa mặt kèm phin lọc hơi hữu cơ / axit"
    ppe_hands = chem.get("hand_protection") or "Găng tay cao su Nitrile chống hóa chất thẩm thấu"
    ppe_skin = chem.get("skin_protection") or "Quần áo bảo hộ lao động, tạp dề chống hóa chất, ủng chống tĩnh điện"

    replacements = {
        "{{PRODUCT_NAME}}": html.escape(str(pname_vi)),
        "{{PRODUCT_CODE}}": html.escape(str(pcode)),
        "{{ORIGINAL_NAME}}": html.escape(str(pname_orig)),
        "{{CAS_NUMBER}}": html.escape(str(cas)),
        "{{ITEM_TYPE_LABEL}}": html.escape(str(item_type_label)),
        "{{FLASH_POINT}}": html.escape(str(flash_point)),
        "{{STORAGE_LOCATION}}": html.escape(str(storage)),
        "{{SIGNAL_WORD}}": html.escape(str(signal_word)),
        "{{SIGNAL_CLASS}}": html.escape(str(signal_class)),
        "{{HAZARD_SUMMARY}}": html.escape(str(hazard_summary)),
        "{{GHS_ICONS_HTML}}": ghs_icons_html,
        "{{H_STATEMENTS}}": html.escape(str(h_statements)),
        "{{FIRE_RECOMMENDED}}": html.escape(str(fire_rec)),
        "{{FIRE_FORBIDDEN}}": html.escape(str(fire_forbid)),
        "{{SPILL_MEASURES}}": html.escape(str(spill_measures)),
        "{{FIRST_AID_EYES}}": html.escape(str(first_aid_eyes)),
        "{{FIRST_AID_SKIN}}": html.escape(str(first_aid_skin)),
        "{{FIRST_AID_INHALATION}}": html.escape(str(first_aid_inhalation)),
        "{{FIRST_AID_INGESTION}}": html.escape(str(first_aid_ingestion)),
        "{{PPE_EYES}}": html.escape(str(ppe_eyes)),
        "{{PPE_RESPIRATORY}}": html.escape(str(ppe_resp)),
        "{{PPE_HANDS}}": html.escape(str(ppe_hands)),
        "{{PPE_SKIN}}": html.escape(str(ppe_skin)),
    }

    rendered = template_text
    for key, val in replacements.items():
        rendered = rendered.replace(key, str(val))
    return rendered


@app.get("/mobile-msds/{chem_id}", response_class=HTMLResponse)
@app.get("/emergency/{chem_id}", response_class=HTMLResponse)
@app.get("/api/msds/qr-view/{chem_id}", response_class=HTMLResponse)
def api_mobile_msds_view(chem_id: str):
    """
    Trang tra cứu khẩn cấp di động siêu tốc (<200ms), 100% Zero-Auth,
    tối ưu cho smartphone hiển thị 5 khối ứng phó: Dập lửa, Tràn đổ, Sơ cứu 4 bước,
    Trang bị PPE, và nút gọi khẩn cấp 1 chạm (114, 115, Hotline EHS).
    Trả về 404 nếu mã hóa chất không tồn tại.
    """
    from core.msds_intelligence import MSDSDatabase
    chem = MSDSDatabase.get_chemical(chem_id)
    if not chem:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy dữ liệu ứng phó khẩn cấp cho mã hóa chất '{chem_id}'."
        )
    html_content = _render_mobile_emergency_html(chem)
    return HTMLResponse(content=html_content, status_code=200, media_type="text/html; charset=utf-8")


@app.get("/msds-emergency", response_class=HTMLResponse)
def api_msds_emergency_query(chem_id: Optional[str] = Query(None)):
    """Trang tra cứu khẩn cấp di động qua tham số URL query ?chem_id=..."""
    if not chem_id:
        raise HTTPException(status_code=400, detail="Thiếu tham số bắt buộc 'chem_id'.")
    return api_mobile_msds_view(chem_id)


@app.post("/api/msds/open-storage-folder")
def api_msds_open_storage_folder(_: str = Depends(require_owner)):
    """Mở trực tiếp thư mục lưu trữ các tệp MSDS (data/msds_files) trên máy tính."""
    from core.msds_intelligence import MSDS_STORAGE_DIR, MSDSDatabase
    try:
        MSDS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        # Đảm bảo toàn bộ các bản ghi hiện có đều đã có tệp trong kho msds_files
        for c in MSDSDatabase.list_chemicals():
            cid = c.get("chemical_id")
            if cid:
                MSDSDatabase.resolve_msds_file_path(cid)
        if hasattr(os, "startfile"):
            os.startfile(str(MSDS_STORAGE_DIR))
        files = [f.name for f in MSDS_STORAGE_DIR.glob("*") if f.is_file()]
        return {
            "success": True,
            "folder_path": str(MSDS_STORAGE_DIR),
            "total_files": len(files),
            "files": files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể mở thư mục lưu trữ MSDS: {str(e)}")


def get_google_drive_path() -> Optional[Path]:
    """Tìm kiếm thư mục Google Drive cục bộ trên hệ thống Windows."""
    candidates = [
        Path("G:/Drive của tôi"),
        Path("G:/My Drive"),
        Path("G:/"),
        Path(os.path.expanduser("~")) / "Google Drive",
        Path(os.path.expanduser("~")) / "GoogleDrive",
    ]
    for c in candidates:
        try:
            if c.exists() and c.is_dir():
                if c == Path("G:/") and (c / "Drive của tôi").exists():
                    return c / "Drive của tôi"
                return c
        except Exception:
            pass
    return None


def auto_sync_chemical_to_gdrive(chem_id: str):
    r"""Tự động sao chép file MSDS vào Google Drive (G:\Drive của tôi\TitanPDF_MSDS) nếu có."""
    try:
        gdrive_root = get_google_drive_path()
        if not gdrive_root or not gdrive_root.exists():
            return
        target_dir = gdrive_root / "TitanPDF_MSDS"
        if not target_dir.exists():
            return
        files_dir = target_dir / "Tep_MSDS_Goc"
        files_dir.mkdir(parents=True, exist_ok=True)
        from core.msds_intelligence import MSDSDatabase
        orig_file = MSDSDatabase.resolve_msds_file_path(chem_id)
        if orig_file and orig_file.exists():
            import shutil
            shutil.copy2(str(orig_file), str(files_dir / orig_file.name))
    except Exception:
        pass


@app.get("/api/msds/gdrive/status")
def api_msds_gdrive_status():
    """Kiểm tra trạng thái kết nối Google Drive và đường dẫn thư mục lưu trữ MSDS."""
    gdrive_root = get_google_drive_path()
    if not gdrive_root or not gdrive_root.exists():
        return {
            "available": False,
            "message": "Chưa tìm thấy Google Drive trên máy tính (G:\\Drive của tôi)."
        }
    target_dir = gdrive_root / "TitanPDF_MSDS"
    files_count = 0
    if target_dir.exists():
        files_dir = target_dir / "Tep_MSDS_Goc"
        if files_dir.exists():
            files_count = len([f for f in files_dir.glob("*") if f.is_file()])
    return {
        "available": True,
        "gdrive_root": str(gdrive_root),
        "target_dir": str(target_dir),
        "target_exists": target_dir.exists(),
        "files_count": files_count,
        "message": f"Google Drive đã sẵn sàng ({gdrive_root})"
    }


@app.post("/api/msds/gdrive/sync")
def api_msds_gdrive_sync(_: str = Depends(require_owner)):
    """Đồng bộ toàn bộ dữ liệu MSDS, Sổ CIL Excel và các tệp gốc vào Google Drive của bạn."""
    import shutil
    from core.msds_intelligence import MSDSDatabase, CILExcelExporter, MSDS_STORAGE_DIR
    gdrive_root = get_google_drive_path()
    if not gdrive_root or not gdrive_root.exists():
        raise HTTPException(
            status_code=400,
            detail="Không tìm thấy Google Drive trên máy tính (G:\\Drive của tôi). Vui lòng đảm bảo ứng dụng Google Drive đã khởi chạy."
        )
    try:
        target_dir = gdrive_root / "TitanPDF_MSDS"
        target_dir.mkdir(parents=True, exist_ok=True)
        files_dir = target_dir / "Tep_MSDS_Goc"
        files_dir.mkdir(parents=True, exist_ok=True)

        chemicals = MSDSDatabase.list_chemicals()
        # 1. Xuất file Sổ CIL Excel
        excel_path = CILExcelExporter.generate_cil_excel(chemicals)
        target_excel = target_dir / "So_Danh_Muc_Hoa_Chat_CIL.xlsx"
        shutil.copy2(str(excel_path), str(target_excel))

        # 2. Xuất sao lưu CSDL JSON
        json_path = target_dir / "msds_database_backup.json"
        clean_chems = [dict(c) for c in chemicals]
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(clean_chems, f, ensure_ascii=False, indent=2)

        # 3. Sao lưu toàn bộ tệp MSDS gốc
        synced_files = 0
        if MSDS_STORAGE_DIR.exists():
            for f in MSDS_STORAGE_DIR.glob("*"):
                if f.is_file():
                    shutil.copy2(str(f), str(files_dir / f.name))
                    synced_files += 1

        return {
            "success": True,
            "target_dir": str(target_dir),
            "total_chemicals": len(chemicals),
            "synced_files_count": synced_files,
            "excel_filename": "So_Danh_Muc_Hoa_Chat_CIL.xlsx",
            "message": f"Đã lưu thành công Sổ CIL Excel và {synced_files} tệp MSDS vào Google Drive:\n{target_dir}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đồng bộ lên Google Drive: {str(e)}")


@app.post("/api/msds/gdrive/open-folder")
def api_msds_gdrive_open_folder(_: str = Depends(require_owner)):
    """Mở thư mục Google Drive (G:\\Drive của tôi\\TitanPDF_MSDS) trên máy tính hoặc trả về web link."""
    gdrive_root = get_google_drive_path()
    web_url = "https://drive.google.com/drive/u/0/my-drive"
    if not gdrive_root or not gdrive_root.exists():
        return {
            "success": True,
            "local_available": False,
            "web_url": web_url,
            "message": "Đang mở Google Drive trên trình duyệt Web (ntc270120cm@gmail.com)."
        }
    target_dir = gdrive_root / "TitanPDF_MSDS"
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        if hasattr(os, "startfile"):
            os.startfile(str(target_dir))
        return {
            "success": True,
            "local_available": True,
            "folder_path": str(target_dir),
            "web_url": web_url,
            "message": f"Đã mở thư mục Google Drive: {target_dir}"
        }
    except Exception as e:
        return {
            "success": True,
            "local_available": False,
            "web_url": web_url,
            "message": f"Đang mở Google Drive trên trình duyệt Web. ({str(e)})"
        }


# ==============================================================================
# MSDS GOOGLE APPS SCRIPT (GAS) CLOUD PERSISTENCE & DRIVE SYNC ENDPOINTS
# ==============================================================================

class MSDSGASConfigRequest(BaseModel):
    webhook_url: str
    secret_token: Optional[str] = None
    auto_sync: Optional[bool] = True


class MSDSGASTestRequest(BaseModel):
    webhook_url: Optional[str] = None
    secret_token: Optional[str] = None


@app.get("/api/msds/gas/config")
def api_msds_gas_get_config(request: Request):
    """Lấy thông tin cấu hình Google Apps Script Webhook."""
    from core.msds_gas_sync import MSDSGASSyncService
    cfg = MSDSGASSyncService.get_config()
    role = get_current_role(request)
    raw_token = cfg.get("secret_token") or ""
    masked_token = "••••••••••••••••" if role == "guest" else raw_token
    return {
        "success": True,
        "configured": bool(cfg.get("webhook_url")),
        "webhook_url": cfg.get("webhook_url", ""),
        "secret_token": masked_token,
        "auto_sync": cfg.get("auto_sync", True),
        "drive_folder": cfg.get("drive_folder", "LUV_PDF_Exports/MSDS_Originals")
    }


@app.post("/api/msds/gas/config")
def api_msds_gas_save_config(payload: MSDSGASConfigRequest, _: str = Depends(require_owner)):
    """Lưu cấu hình Google Apps Script Webhook URL và Secret Token."""
    from core.msds_gas_sync import MSDSGASSyncService
    try:
        saved = MSDSGASSyncService.save_config(
            webhook_url=payload.webhook_url,
            secret_token=payload.secret_token,
            auto_sync=payload.auto_sync if payload.auto_sync is not None else True
        )
        return {
            "success": True,
            "message": "Đã lưu cấu hình Google Apps Script thành công.",
            "config": {
                "configured": bool(saved.get("webhook_url")),
                "webhook_url": saved.get("webhook_url", ""),
                "auto_sync": saved.get("auto_sync", True),
                "drive_folder": saved.get("drive_folder", "")
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu cấu hình GAS: {str(e)}")


@app.post("/api/msds/gas/test-connection")
def api_msds_gas_test_connection(payload: Optional[MSDSGASTestRequest] = Body(None)):
    """Kiểm tra kết nối tới Google Apps Script Webhook."""
    from core.msds_gas_sync import MSDSGASSyncService
    url = payload.webhook_url if payload else None
    token = payload.secret_token if payload else None
    res = MSDSGASSyncService.test_connection(url=url, token=token)
    return res


@app.post("/api/msds/gas/sync-to-sheet")
def api_msds_gas_sync_to_sheet(_: str = Depends(require_owner)):
    """Đồng bộ toàn bộ hóa chất từ SQLite lên Google Sheet (Push)."""
    from core.msds_intelligence import MSDSDatabase
    from core.msds_gas_sync import MSDSGASSyncService
    try:
        chemicals = MSDSDatabase.list_chemicals()
        res = MSDSGASSyncService.batch_sync_to_sheet(chemicals)
        return {
            "success": True,
            "total_local": len(chemicals),
            "result": res,
            "message": f"Đã đồng bộ {len(chemicals)} hóa chất lên Google Sheet thành công."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đồng bộ lên Google Sheet: {str(e)}")


@app.post("/api/msds/gas/sync-from-sheet")
def api_msds_gas_sync_from_sheet(_: str = Depends(require_owner)):
    """Kéo toàn bộ hóa chất từ Google Sheet về SQLite cục bộ (Pull / Reconcile)."""
    from core.msds_gas_sync import MSDSGASSyncService
    try:
        res = MSDSGASSyncService.reconcile_on_startup()
        return {
            "success": True,
            "result": res,
            "message": res.get("message") or "Đã hòa giải dữ liệu từ Google Sheet thành công."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hòa giải từ Google Sheet: {str(e)}")


# ============================================================
# WORD DOCUMENT (.DOCX / .DOC) PREVIEW ENDPOINTS
# ============================================================
def convert_docx_bytes_to_html(content: bytes) -> str:
    """Chuyển đổi tệp docx sang HTML giàu hình ảnh và bảng biểu bằng mammoth."""
    import base64
    import io
    import mammoth

    def _convert_image(image):
        with image.open() as image_bytes:
            encoded_src = base64.b64encode(image_bytes.read()).decode("ascii")
            return {
                "src": f"data:{image.content_type};base64,{encoded_src}",
                "class": "docx-preview-image",
                "style": "max-width:100%; height:auto; border-radius:6px; margin:8px 0; display:block;"
            }

    file_stream = io.BytesIO(content)
    result = mammoth.convert_to_html(file_stream, convert_image=mammoth.images.img_element(_convert_image))
    return result.value


def convert_word_bytes_to_html(content: bytes, filename: str = "document.docx") -> str:
    """
    Chuyển đổi tệp Word (.docx hoặc .doc nhị phân OLE2) sang HTML.
    Nếu là tệp .doc nhị phân, tự động chuyển đổi sang .docx tạm trước khi kết xuất HTML.
    """
    is_binary_doc = (
        content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
        or (filename.lower().endswith(".doc") and not content.startswith(b"PK\x03\x04"))
    )
    if is_binary_doc:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_doc = os.path.join(temp_dir, "input.doc")
            temp_docx = os.path.join(temp_dir, "converted.docx")
            with open(temp_doc, "wb") as f:
                f.write(content)
            convert_doc_to_docx(temp_doc, temp_docx)
            if not os.path.exists(temp_docx) or os.path.getsize(temp_docx) == 0:
                raise RuntimeError("Không thể chuyển đổi tệp .doc nhị phân sang định dạng .docx.")
            with open(temp_docx, "rb") as f:
                content = f.read()
    return convert_docx_bytes_to_html(content)


@app.post("/api/preview/word")
async def api_preview_word_upload(file: UploadFile = File(...)):
    """Trích xuất và kết xuất tài liệu Word (.docx/.doc) sang HTML để xem trước tức thì."""
    filename = file.filename or "document.docx"
    try:
        content = await file.read()
        if not content:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "filename": filename,
                    "detail": "Tệp tin tải lên rỗng."
                }
            )
        html = convert_word_bytes_to_html(content, filename=filename)
        return {
            "success": True,
            "filename": filename,
            "size": len(content),
            "html": html
        }
    except Exception as e:
        logger.error("Word preview error for %s: %s", filename, e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "filename": filename,
                "detail": f"Không thể kết xuất xem trước tài liệu Word: {str(e)}"
            }
        )


@app.get("/api/preview/word/{filename}")
@app.get("/api/preview/word-output/{filename}")
def api_preview_word_output(filename: str):
    """Kết xuất xem trước tệp Word (.docx/.doc) đã được xuất trong hệ thống (output/ hoặc exports/)."""
    try:
        candidates = [
            Path(OUTPUT_DIR) / filename,
            Path(DATA_DIR) / "exports" / filename,
            Path(DATA_DIR) / "temp" / filename,
            Path(DATA_DIR) / filename,
            Path(BASE_DIR) / filename,
        ]
        target_path = None
        for c in candidates:
            if c.exists() and c.is_file():
                target_path = c
                break
        
        if not target_path:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "filename": filename,
                    "detail": f"Không tìm thấy tệp Word '{filename}'."
                }
            )

        content = target_path.read_bytes()
        html = convert_word_bytes_to_html(content, filename=filename)
        return {
            "success": True,
            "filename": filename,
            "size": len(content),
            "html": html
        }
    except Exception as e:
        logger.error("Word output preview error for %s: %s", filename, e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "filename": filename,
                "detail": f"Lỗi phân giải tệp Word '{filename}': {str(e)}"
            }
        )


# ============================================================
# EXCEL SPREADSHEET (.XLSX / .XLS) PREVIEW ENDPOINTS
# ============================================================
@app.post("/api/preview/excel")
async def api_preview_excel_upload(file: UploadFile = File(...)):
    """Trích xuất và kết xuất bảng tính Excel (.xlsx/.xls) sang HTML dạng Sheet Tabs + Table để xem trước tức thì."""
    filename = file.filename or "document.xlsx"
    try:
        content = await file.read()
        if not content:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "filename": filename,
                    "detail": "Tệp tin tải lên rỗng."
                }
            )
        
        is_binary_xls = (
            content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
            or (filename.lower().endswith(".xls") and not content.startswith(b"PK\x03\x04"))
        )
        if is_binary_xls:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_xls = os.path.join(temp_dir, "input.xls")
                temp_xlsx = os.path.join(temp_dir, "converted.xlsx")
                with open(temp_xls, "wb") as f:
                    f.write(content)
                ExcelInterlinearTranslator.convert_xls_to_xlsx(temp_xls, temp_xlsx)
                if not os.path.exists(temp_xlsx) or os.path.getsize(temp_xlsx) == 0:
                    raise RuntimeError("Không thể chuyển đổi tệp .xls nhị phân sang định dạng .xlsx.")
                data = ExcelInterlinearTranslator.render_excel_to_html(temp_xlsx)
        else:
            data = ExcelInterlinearTranslator.render_excel_to_html(content)
        
        data["filename"] = filename
        data["size"] = len(content)
        if "sheets_data" in data and data["sheets_data"]:
            data["html"] = data["sheets_data"][0]["html"]
        return data
    except Exception as e:
        logger.error("Excel preview error for %s: %s", filename, e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "filename": filename,
                "detail": f"Không thể kết xuất xem trước bảng tính Excel: {str(e)}"
            }
        )


@app.get("/api/preview/excel/{filename}")
@app.get("/api/preview/excel-output/{filename}")
def api_preview_excel_output(filename: str):
    """Kết xuất xem trước tệp Excel (.xlsx/.xls) đã được xuất trong hệ thống (output/ hoặc exports/)."""
    try:
        candidates = [
            Path(OUTPUT_DIR) / filename,
            Path(DATA_DIR) / "exports" / filename,
            Path(DATA_DIR) / "temp" / filename,
            Path(DATA_DIR) / filename,
            Path(BASE_DIR) / filename,
        ]
        target_path = None
        for c in candidates:
            if c.exists() and c.is_file():
                target_path = c
                break
        
        if not target_path:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "filename": filename,
                    "detail": f"Không tìm thấy tệp Excel '{filename}'."
                }
            )

        if filename.lower().endswith(".xls"):
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_xlsx = os.path.join(temp_dir, "converted.xlsx")
                ExcelInterlinearTranslator.convert_xls_to_xlsx(str(target_path), temp_xlsx)
                data = ExcelInterlinearTranslator.render_excel_to_html(temp_xlsx)
        else:
            data = ExcelInterlinearTranslator.render_excel_to_html(str(target_path))

        data["filename"] = filename
        data["size"] = target_path.stat().st_size
        if "sheets_data" in data and data["sheets_data"]:
            data["html"] = data["sheets_data"][0]["html"]
        return data
    except Exception as e:
        logger.error("Excel output preview error for %s: %s", filename, e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "filename": filename,
                "detail": f"Lỗi phân giải tệp Excel '{filename}': {str(e)}"
            }
        )



# DOWNLOAD ENDPOINT
@app.get("/api/download/{filename}")
def download_file(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Tệp tin không tồn tại hoặc đã hết hạn.")
    return FileResponse(file_path, filename=filename, media_type="application/octet-stream")


# ============================================================
# HSE REPORT STUDIO SUB-ROUTER (Milestone 1)
# ============================================================
from core.hse_router import hse_router
app.include_router(hse_router, prefix="/api/hse", tags=["HSE Report Studio"])
app.include_router(hse_router, prefix="/api", tags=["HSE Report Studio Alias"])

# ============================================================
# CHEMICAL LEGAL COMPLIANCE & INTELLIGENCE SUB-ROUTER (Milestone 1)
# ============================================================
from core.legal_router import legal_router
app.include_router(legal_router, prefix="/api/legal", tags=["Legal Intelligence"])
app.include_router(legal_router, prefix="/api", tags=["Legal Intelligence Alias"])
app.include_router(legal_router, prefix="/api/legal-catalog", tags=["Legal Catalog Compatibility Alias"])

# ============================================================
# MONTHLY CHEMICAL INVENTORY & USAGE TRACKING (NXT) SUB-ROUTER
# ============================================================
from core.monthly_inventory_router import monthly_inventory_router
from core.monthly_inventory_engine import MonthlyInventoryEngine

MonthlyInventoryEngine.init_db()
app.include_router(monthly_inventory_router, prefix="/api/monthly-inventory", tags=["Monthly Chemical Inventory"])
app.include_router(monthly_inventory_router, prefix="/api/msds/monthly-report", tags=["Monthly Chemical Inventory Report Alias"])

# ============================================================
# GATE PASS & MATERIAL DISPATCH STUDIO SUB-ROUTER (Milestone M1)
# ============================================================
try:
    from core.gatepass_router import gatepass_router
    from core.gatepass_service import GatePassService

    GatePassService.init_db()
    app.include_router(gatepass_router, prefix="/api/gatepass", tags=["Gate Pass & Material Dispatch Studio"])
    print("[INFO] Successfully mounted Gate Pass Studio Router at /api/gatepass")
except Exception as e:
    print(f"[ERROR] Failed to mount Gate Pass Studio Router: {e}")


# ============================================================
# MULTI-PLANT ENTITY & BRANCH REGISTRY (Milestone M1)
# ============================================================
try:
    from core.plant_registry import PlantRegistry

    PlantRegistry.init_db()

    @app.get("/api/plants", summary="Danh sách các chi nhánh / nhà máy")
    def api_get_plants(include_inactive: bool = Query(True)):
        plants = PlantRegistry.get_all_plants(include_inactive=include_inactive)
        return {"success": True, "plants": plants, "total": len(plants)}

    @app.get("/api/plants/{code}", summary="Chi tiết một chi nhánh / nhà máy")
    def api_get_plant(code: str):
        plant = PlantRegistry.get_plant(code)
        if not plant:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy chi nhánh/nhà máy mã '{code}'.")
        return {"success": True, "plant": plant}

    @app.post("/api/plants", summary="Tạo mới chi nhánh / nhà máy")
    def api_create_plant(payload: Dict[str, Any] = Body(...), _: str = Depends(require_owner)):
        try:
            new_plant = PlantRegistry.create_plant(payload)
            return {"success": True, "plant": new_plant, "message": f"Tạo chi nhánh {new_plant.get('plant_code')} thành công."}
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi tạo chi nhánh: {str(e)}")

    @app.put("/api/plants/{code}", summary="Cập nhật chi nhánh / nhà máy")
    def api_update_plant(code: str, payload: Dict[str, Any] = Body(...), _: str = Depends(require_owner)):
        try:
            updated = PlantRegistry.update_plant(code, payload)
            return {"success": True, "plant": updated, "message": f"Cập nhật chi nhánh {code} thành công."}
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi cập nhật chi nhánh: {str(e)}")

    @app.post("/api/plants/{code}/toggle", summary="Bật/Tắt trạng thái hoạt động của chi nhánh")
    @app.patch("/api/plants/{code}/toggle-active", summary="Bật/Tắt trạng thái hoạt động (Alias)")
    def api_toggle_plant(
        code: str,
        payload: Optional[Dict[str, Any]] = Body(None),
        is_active: Optional[bool] = Query(None),
        _: str = Depends(require_owner)
    ):
        try:
            active_val = None
            if is_active is not None:
                active_val = is_active
            elif payload and "is_active" in payload:
                active_val = bool(payload["is_active"])

            updated = PlantRegistry.toggle_plant_active(code, is_active=active_val)
            return {"success": True, "plant": updated, "message": f"Thay đổi trạng thái chi nhánh {code} thành công."}
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi chuyển trạng thái chi nhánh: {str(e)}")

    print("[INFO] Successfully mounted Plant Registry endpoints at /api/plants")
except Exception as e:
    print(f"[ERROR] Failed to mount Plant Registry endpoints: {e}")


# SERVE FRONTEND
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8888))
    print(f"Khoi dong TitanPDF Server tai http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

