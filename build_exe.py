import os
import sys
import subprocess
import shutil

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def build():
    print("=" * 64)
    print("  DONG GOI UNG DUNG LUV-PDF THANH FILE .EXE (PyInstaller)")
    print("=" * 64)

    # Clean previous build & dist
    for d in ["build", "dist"]:
        path = os.path.join(BASE_DIR, d)
        if os.path.exists(path):
            print(f"[*] Don dep thu muc cu: {d}/")
            shutil.rmtree(path, ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=LUV-PDF",
        "--onedir",
        "--noconfirm",
        f"--add-data={os.path.join(BASE_DIR, 'static')};static",
        f"--add-data={os.path.join(BASE_DIR, 'core')};core",
        "--hidden-import=uvicorn",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=multipart",
        "--hidden-import=fitz",
        "--hidden-import=openpyxl",
        "--hidden-import=docx",
        "--hidden-import=pptx",
        "--hidden-import=pdf2docx",
        os.path.join(BASE_DIR, "app_launcher.py")
    ]

    print("[*] Dang chay PyInstaller...")
    result = subprocess.run(cmd, cwd=BASE_DIR)
    if result.returncode == 0:
        exe_path = os.path.join(BASE_DIR, "dist", "LUV-PDF", "LUV-PDF.exe")
        print("=" * 64)
        print("DONG GOI THANH CONG!")
        print(f"[*] Tep thuc thi Windows: {exe_path}")
        print("=" * 64)
    else:
        print("Loi khi dong goi PyInstaller. Ma loi:", result.returncode)

if __name__ == "__main__":
    build()
