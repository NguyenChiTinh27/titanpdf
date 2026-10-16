"""
app_launcher.py
───────────────
LUV-PDF Private Suite — Native Desktop Application Launcher
Cửa sổ Ứng dụng Máy tính Cục bộ Độc lập (Desktop Native Window Mode)
- 100% Cục bộ & Riêng tư.
- Kiến trúc Đơn tiến trình (Single-instance): tự động kết nối và mở giao diện tức thì nếu máy chủ đang chạy.
- Máy chủ uvicorn luôn hoạt động bền bỉ, không tự ngắt kết nối.
"""

import os
import sys
import time
import socket
import urllib.request
import threading
import subprocess
import webbrowser

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    DATA_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = BASE_DIR

LOGS_DIR = os.path.join(DATA_DIR, "temp")
os.makedirs(LOGS_DIR, exist_ok=True)
LAUNCHER_LOG = os.path.join(LOGS_DIR, "launcher.log")

try:
    log_fp = open(LAUNCHER_LOG, "a", encoding="utf-8", buffering=1)
except Exception:
    log_fp = open(os.devnull, "w", encoding="utf-8")

if sys.stdout is None:
    sys.stdout = log_fp
elif hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

if sys.stderr is None:
    sys.stderr = log_fp
elif hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def is_server_ready(port: int = 8888) -> bool:
    """Kiểm tra máy chủ LUV-PDF cục bộ có phản hồi hay không."""
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/health",
            headers={'User-Agent': 'LUV-Desktop-Launcher'}
        )
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            return resp.status == 200
    except Exception:
        return False


def is_port_in_use(port: int = 8888) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def free_port_if_stale(port: int = 8888):
    """Giải phóng cổng 8888 nếu bị chiếm dụng bởi tiến trình treo không phản hồi."""
    if is_port_in_use(port) and not is_server_ready(port):
        try:
            cmd = f'netstat -ano | findstr :{port}'
            output = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
            for line in output.splitlines():
                if "LISTENING" in line:
                    parts = line.strip().split()
                    if parts:
                        pid = parts[-1]
                        if pid.isdigit() and int(pid) != os.getpid():
                            subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
            time.sleep(0.3)
        except Exception:
            pass


def find_desktop_browser():
    """Tìm trình duyệt Microsoft Edge hoặc Chrome để chạy chế độ Cửa sổ Ứng dụng (App Window)."""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe")
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None


def launch_native_desktop_window(url: str, browser_exe: str):
    """Khởi chạy cửa sổ ứng dụng desktop độc lập với profile riêng."""
    profile_dir = os.path.join(os.getenv("LOCALAPPDATA", os.path.expanduser("~")), "LUV-PDF", "desktop_profile")
    os.makedirs(profile_dir, exist_ok=True)

    cmd = [
        browser_exe,
        f"--app={url}",
        "--window-size=1440,900",
        "--window-position=center",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=Translate,OptimizationHints,MediaRouter",
        "--disable-sync",
        "--disable-extensions",
        "--app-auto-launched"
    ]

    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 1  # SW_SHOWNORMAL

    try:
        subprocess.Popen(cmd, startupinfo=startupinfo)
    except Exception:
        webbrowser.open(url)


def main():
    port = 8888
    url = f"http://127.0.0.1:{port}"
    browser_exe = find_desktop_browser()

    # 1. Dọn dẹp cổng nếu bị treo bởi tiến trình chết
    free_port_if_stale(port)

    # 2. Kiểm tra phiên đang chạy (Single-Instance):
    # Nếu máy chủ đã chạy sẵn, lập tức mở giao diện và thoát ngay tiến trình launcher trùng lặp!
    if is_server_ready(port):
        if browser_exe:
            launch_native_desktop_window(url, browser_exe)
        else:
            webbrowser.open(url)
        sys.exit(0)

    # 3. Mở trực tiếp cửa sổ ứng dụng khi máy chủ sẵn sàng (Không dùng ảnh GIF chờ khởi động)
    def _open_window_when_ready():
        for _ in range(60):
            if is_server_ready(port):
                break
            time.sleep(0.1)
        if browser_exe:
            launch_native_desktop_window(url, browser_exe)
        else:
            webbrowser.open(url)
    threading.Thread(target=_open_window_when_ready, daemon=True).start()

    # 4. CHẠY MÁY CHỦ UVICORN TRÊN LUỒNG CHÍNH — KHÔNG BAO GIỜ TỰ ĐỘNG THOÁT
    try:
        from server import app
        import uvicorn
        config = uvicorn.Config(
            app=app,
            host="127.0.0.1",
            port=port,
            log_level="error",
            loop="asyncio",
            timeout_keep_alive=30
        )
        server = uvicorn.Server(config)
        server.run()
    except Exception as e:
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
