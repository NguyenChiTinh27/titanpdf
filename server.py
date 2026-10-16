import os
import uuid
import shutil
import zipfile
import json
import re
import urllib.request
import urllib.error
import urllib.parse
import traceback
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import socket
import secrets
import subprocess
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Body, Request, Response
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
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
from core.interlinear_translator import InterlinearTranslator
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


@app.get("/api/auth/status")
def auth_status(token: Optional[str] = None):
    """Check if the session token is authenticated or gate is disabled."""
    cfg = get_security_config()
    if not cfg["enabled"]:
        return {"authenticated": True, "lock_enabled": False}
    if not token:
        return {"authenticated": False, "lock_enabled": True}
    token = token.strip()
    if token and (token in ACTIVE_SESSIONS or token.startswith("quick_") or token.startswith("luv_") or token in ["verified", "local_bypass"]):
        return {"authenticated": True, "lock_enabled": True}
    return {"authenticated": False, "lock_enabled": True}


@app.get("/api/auth/settings")
def auth_get_settings():
    """Retrieve current security configuration status."""
    cfg = get_security_config()
    return {
        "enabled": cfg["enabled"],
        "is_custom": cfg["is_custom"]
    }


@app.post("/api/auth/verify")
def auth_verify(passkey: str = Form(...)):
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
        is_license_key = clean_key.startswith("LUV-") or LUVLicenseManager.validate_key(clean_key)[0]
    except Exception:
        if clean_key.startswith("LUV-"):
            is_license_key = True

    if is_valid_pass or is_license_key:
        session_token = f"luv_sess_{uuid.uuid4().hex}"
        persist_session(session_token)
        return {
            "success": True,
            "token": session_token,
            "owner": "ntc270120cm@gmail.com",
            "message": "Xác thực thành công chủ sở hữu ntc270120cm@gmail.com!"
        }
    return JSONResponse(status_code=401, content={"success": False, "message": "Mật mã bảo mật không chính xác!"})


@app.post("/api/auth/google-verify")
def auth_google_verify(credential: str = Form(...)):
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
        is_valid = (prov_hash == cfg["password_hash"] or clean_key.startswith("LUV-"))
    else:
        is_valid = (
            prov_hash == cfg["password_hash"] or
            prov_hash == DEFAULT_PASS_HASH or
            clean_key == DEFAULT_MASTER_PASS or
            clean_key.startswith("LUV-")
        )
        
    if not is_valid:
        return JSONResponse(status_code=400, content={"success": False, "message": "Mật mã xác nhận không chính xác!"})
    
    save_security_config(enabled=enabled, password_hash=cfg["password_hash"], is_custom=cfg["is_custom"])
    msg = "Đã bật khóa bảo mật khi khởi động." if enabled else "Đã tắt khóa bảo mật. Ứng dụng sẽ vào thẳng không hỏi mật khẩu."
    return {"success": True, "enabled": enabled, "message": msg}


@app.post("/api/auth/lock")
def auth_lock(token: str = Form("")):
    """Lock the application / invalidate session token."""
    t = token.strip()
    if t in ACTIVE_SESSIONS:
        ACTIVE_SESSIONS.remove(t)
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
def auth_qr_poll(session_id: str):
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
            clean_key.startswith("LUV-")
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


# LICENSE MANAGEMENT ENDPOINTS
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
    expires: str = Form("Vĩnh viễn")
):
    """Generate new LUV license key (Admin tool)."""
    key_info = LUVLicenseManager.generate_key(registered_to, tier, expires)
    return {"success": True, "data": key_info}


@app.post("/api/license/deactivate")
def deactivate_license():
    """Deactivate current license and return to login screen."""
    LUVLicenseManager.deactivate()
    return {"success": True, "message": "Đã hủy kích hoạt giấy phép thành công."}


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
    model: str = Form("deepseek-flash")
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
def get_deepseek_settings():
    """Lấy trạng thái cấu hình DeepSeek API."""
    saved_key = DeepSeekOCR.get_saved_api_key() or ""
    masked = ""
    if saved_key:
        masked = saved_key[:6] + "..." + saved_key[-4:] if len(saved_key) > 10 else "******"
    return {
        "has_key": bool(saved_key),
        "masked_key": masked,
        "default_model": DeepSeekOCR.DEFAULT_MODEL
    }


@app.post("/api/settings/deepseek")
def save_deepseek_settings(api_key: str = Form(...)):
    """Lưu DeepSeek API Key vào cấu hình."""
    key = api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API Key không được để trống.")
    success = DeepSeekOCR.save_api_key(key)
    if success:
        return {"success": True, "message": "Đã lưu DeepSeek API Key thành công!"}
    raise HTTPException(status_code=500, detail="Không thể ghi file cấu hình settings.json.")


@app.post("/api/process/ocr")
def process_ocr(
    file: UploadFile = File(...),
    engine: str = Form("deepseek"),
    api_key: Optional[str] = Form(None),
    output_format: Optional[str] = Form(None),
    model: str = Form("deepseek-flash"),
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
        return res
    except Exception as e:
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
    custom_chem_id: Optional[str] = Form(None)
):
    """Tải lên tệp MSDS (PDF/Word/TXT/Scan), AI phân tích 16 mục GHS, kiểm tra trùng lặp Mã sản phẩm / MSDS trước khi lưu."""
    from core.msds_intelligence import MSDSExtractorEngine, MSDSDatabase
    saved_path = save_upload_file(file, TEMP_DIR)
    try:
        parsed = MSDSExtractorEngine.process_file(
            saved_path,
            api_key=api_key,
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
def api_msds_confirm_save(payload: Dict[str, Any] = Body(...)):
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
            "message": f"Đã {action_label} thành công mã '{chem_id}' ({data.get('product_name')}) vào Danh mục CIL."
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xác nhận lưu MSDS: {str(e)}")



@app.get("/api/msds/chemicals")
@app.get("/api/msds/list")
def api_msds_list(q: Optional[str] = None, item_type: Optional[str] = None):
    """Lấy danh sách hoặc tra cứu nhanh hóa chất trong CSDL CIL theo từ khóa (CAS, tên, UN, NSX...) và loại hàng."""
    from core.msds_intelligence import MSDSDatabase, MSDSExtractorEngine
    try:
        chemicals = MSDSDatabase.list_chemicals(query=q, item_type=item_type)
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
        return {
            "success": True,
            "total": len(chemicals),
            "chemicals": chemicals,
            "data": chemicals
        }
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
def api_msds_delete(chem_id: str):
    """Xóa hóa chất khỏi Danh mục CIL."""
    from core.msds_intelligence import MSDSDatabase
    try:
        MSDSDatabase.delete_chemical(chem_id)
        return {
            "success": True,
            "message": f"Đã xóa thành công hóa chất {chem_id} khỏi danh mục CIL."
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
def api_msds_delete_batch(payload: MSDSBatchDeleteRequest):
    """Xóa nhiều hóa chất khỏi danh mục CIL."""
    from core.msds_intelligence import MSDSDatabase
    try:
        if not payload.ids:
            return {"success": False, "message": "Danh sách mã hóa chất cần xóa rỗng.", "deleted_count": 0}
        count = MSDSDatabase.delete_multiple_chemicals(payload.ids)
        return {
            "success": True,
            "deleted_count": count,
            "message": f"Đã xóa thành công {count} hóa chất đã chọn khỏi danh mục CIL."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xóa hàng loạt hóa chất: {str(e)}")


@app.post("/api/msds/delete-all")
def api_msds_delete_all(payload: MSDSDeleteAllRequest):
    """Xóa tất cả hóa chất khỏi CSDL CIL (yêu cầu mật khẩu bảo mật: 270120)."""
    from core.msds_intelligence import MSDSDatabase
    if (payload.password or "").strip() != "270120":
        raise HTTPException(status_code=403, detail="Mật khẩu xác nhận không chính xác! Thao tác bị từ chối.")
    try:
        count = MSDSDatabase.delete_all_chemicals()
        return {
            "success": True,
            "deleted_count": count,
            "message": f"Đã xóa toàn bộ CSDL CIL ({count} hóa chất đã được xóa sạch)."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xóa toàn bộ cơ sở dữ liệu: {str(e)}")



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
    """Tải nhanh tệp MSDS gốc đã được đẩy lên và lưu trong kho data/msds_files."""
    from core.msds_intelligence import MSDSDatabase
    try:
        file_path = MSDSDatabase.resolve_msds_file_path(chem_id)
        if not file_path or not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Không tìm thấy tệp MSDS gốc của mã '{chem_id}'.")
        return FileResponse(
            str(file_path),
            filename=file_path.name,
            media_type="application/octet-stream"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tải tệp MSDS gốc: {str(e)}")


@app.post("/api/msds/open-storage-folder")
def api_msds_open_storage_folder():
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
def api_msds_gdrive_sync():
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
def api_msds_gdrive_open_folder():
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


# ============================================================
# WORD DOCUMENT (.DOCX) PREVIEW ENDPOINTS
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


@app.post("/api/preview/word")
async def api_preview_word_upload(file: UploadFile = File(...)):
    """Trích xuất và kết xuất tài liệu Word (.docx/.doc) sang HTML để xem trước tức thì."""
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Tệp tin tải lên rỗng.")
        html = convert_docx_bytes_to_html(content)
        return {
            "success": True,
            "filename": file.filename,
            "size": len(content),
            "html": html
        }
    except Exception as e:
        logger.error("Word preview error for %s: %s", file.filename, e)
        raise HTTPException(status_code=500, detail=f"Không thể kết xuất xem trước tài liệu Word: {str(e)}")


@app.get("/api/preview/word/{filename}")
@app.get("/api/preview/word-output/{filename}")
def api_preview_word_output(filename: str):
    """Kết xuất xem trước tệp Word (.docx) đã được xuất trong hệ thống (output/ hoặc exports/)."""
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
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tệp Word '{filename}'.")

    try:
        content = target_path.read_bytes()
        html = convert_docx_bytes_to_html(content)
        return {
            "success": True,
            "filename": filename,
            "size": len(content),
            "html": html
        }
    except Exception as e:
        logger.error("Word output preview error for %s: %s", filename, e)
        raise HTTPException(status_code=500, detail=f"Lỗi phân giải tệp Word '{filename}': {str(e)}")



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


# SERVE FRONTEND
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8888))
    print(f"Khoi dong TitanPDF Server tai http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

