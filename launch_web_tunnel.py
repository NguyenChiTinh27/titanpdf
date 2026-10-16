import subprocess
import re
import sys
import time

cmd = [r".\cloudflared.exe", "tunnel", "--url", "http://127.0.0.1:8888"]
print("Dang khoi chay Cloudflare Web Tunnel cho TitanPDF...")

proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

url_found = None
start_time = time.time()

while True:
    line = proc.stdout.readline()
    if not line:
        break
    sys.stdout.write(line)
    sys.stdout.flush()
    m = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", line)
    if m and not url_found:
        url_found = m.group(0)
        print("\n" + "="*60)
        print("TITANPDF WEB URL LIVE:")
        print(url_found)
        print("="*60 + "\n")
        with open("tunnel_url.txt", "w", encoding="utf-8") as f:
            f.write(url_found)
        break

# Keep process alive
proc.wait()
