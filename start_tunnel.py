import subprocess
import time
import os
import re

log_file = os.path.abspath("cloudflare.log")
if os.path.exists(log_file):
    try:
        os.remove(log_file)
    except Exception:
        pass

cmd = [os.path.abspath("cloudflared.exe"), "tunnel", "--url", "http://127.0.0.1:8888", "--logfile", log_file]
proc = subprocess.Popen(cmd)
print("cloudflared started with PID", proc.pid)

url = None
for _ in range(30):
    time.sleep(1)
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            m = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", content)
            if m:
                url = m.group(0)
                break

if url:
    print("=== LIVE WEB URL ===")
    print(url)
    with open("tunnel_url.txt", "w", encoding="utf-8") as f:
        f.write(url)
    try:
        desktop_url = os.path.expanduser(r"C:\Users\ntc27\OneDrive\Desktop\LINK_TRUY_CAP_WEB.url")
        with open(desktop_url, "w", encoding="utf-8") as f:
            f.write(f"[InternetShortcut]\nURL={url}\nIconIndex=0\nIconFile=C:\\Windows\\System32\\shell32.dll\n")
    except Exception as e:
        pass
else:
    print("Timeout waiting for tunnel URL")

proc.wait()
