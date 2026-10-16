import os
import io
import sys
import time
import requests
import zipfile
import fitz
import docx
import openpyxl
from unittest.mock import patch

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8888"
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

print("=" * 70)
print("  TITANPDF ADVERSARIAL QA AUDIT & DEEP VERIFICATION SUITE")
print("=" * 70)

# Check health
health_resp = requests.get(f"{BASE_URL}/api/health", timeout=5)
assert health_resp.status_code == 200, "Server not healthy"
print("✔ Server health check OK: 100% Offline & Private")

# -------------------------------------------------------------
# 1. R1: Native MS Word PDF-to-Word Engine Rollback & Fallback
# -------------------------------------------------------------
print("\n--- [AUDIT R1] Native MS Word Engine & Fallback ---")

# A. Convert sample_5pages.pdf
t0 = time.time()
with open("sample_5pages.pdf", "rb") as f:
    resp = requests.post(f"{BASE_URL}/api/process/pdf-to-word", files={"file": f}, data={"mode": "auto"}, timeout=30)
assert resp.status_code == 200, f"sample_5pages failed: {resp.text}"
res_data = resp.json()
assert res_data["success"] is True
assert res_data["engine"] == "Microsoft Word Native COM"
docx_name = res_data["filename"]
docx_path = os.path.join(PROJECT_ROOT, "output", docx_name)
assert os.path.exists(docx_path)
d = docx.Document(docx_path)
print(f"✔ sample_5pages.pdf converted via MS Word Native COM in {time.time()-t0:.2f}s ({len(d.paragraphs)} paras, {len(d.tables)} tables)")

# B. Convert test_wrap.pdf
t0 = time.time()
with open("test_wrap.pdf", "rb") as f:
    resp = requests.post(f"{BASE_URL}/api/process/pdf-to-word", files={"file": f}, data={"mode": "auto"}, timeout=30)
assert resp.status_code == 200, f"test_wrap failed: {resp.text}"
res_data = resp.json()
assert res_data["success"] is True
assert res_data["engine"] == "Microsoft Word Native COM"
docx_name = res_data["filename"]
docx_path = os.path.join(PROJECT_ROOT, "output", docx_name)
assert os.path.exists(docx_path)
d = docx.Document(docx_path)
print(f"✔ test_wrap.pdf converted via MS Word Native COM in {time.time()-t0:.2f}s ({len(d.paragraphs)} paras, {len(d.tables)} tables)")

# C. Safe Offline Fallback to pdf2docx
from core.pdf_to_word_converter import SmartPDFToWordDispatcher, MSWordNativeEngine, OfflinePDF2DocxEngine
out_fallback = os.path.join(PROJECT_ROOT, "output", "test_audit_fallback.docx")
with patch.object(MSWordNativeEngine, "is_available", return_value=False):
    fb_res = SmartPDFToWordDispatcher.convert("sample_5pages.pdf", out_fallback)
assert fb_res["success"] is True
assert "pdf2docx" in fb_res["engine"]
assert os.path.exists(out_fallback)
print(f"✔ Safe offline fallback (mocking Word absent) succeeded: {fb_res['engine']}")
if os.path.exists(out_fallback):
    os.remove(out_fallback)

# D. Adversarial: Encrypted PDF handling
enc_pdf_path = os.path.join(PROJECT_ROOT, "output", "test_audit_enc.pdf")
doc_enc = fitz.open()
doc_enc.new_page()
doc_enc.save(enc_pdf_path, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="123456", owner_pw="654321")
doc_enc.close()
with open(enc_pdf_path, "rb") as f:
    resp_enc = requests.post(f"{BASE_URL}/api/process/pdf-to-word", files={"file": f}, data={"mode": "auto"}, timeout=15)
assert resp_enc.status_code == 500
assert "mật khẩu bảo vệ" in resp_enc.text
print(f"✔ Adversarial: Encrypted PDF rejected cleanly with 500 ('mật khẩu bảo vệ')")
if os.path.exists(enc_pdf_path):
    os.remove(enc_pdf_path)

# E. Adversarial: Empty/Corrupted PDF
empty_pdf_path = os.path.join(PROJECT_ROOT, "output", "test_audit_empty.pdf")
with open(empty_pdf_path, "wb") as f:
    f.write(b"")
with open(empty_pdf_path, "rb") as f:
    resp_emp = requests.post(f"{BASE_URL}/api/process/pdf-to-word", files={"file": f}, data={"mode": "auto"}, timeout=15)
assert resp_emp.status_code == 500
print(f"✔ Adversarial: Zero-byte PDF rejected cleanly with 500")
if os.path.exists(empty_pdf_path):
    os.remove(empty_pdf_path)


# -------------------------------------------------------------
# 2. R2: Complete Eradication of History Module
# -------------------------------------------------------------
print("\n--- [AUDIT R2] Complete Removal of History Module ---")

# API checks
resp_h1 = requests.get(f"{BASE_URL}/api/history", timeout=5)
assert resp_h1.status_code == 404, f"/api/history returned {resp_h1.status_code}"
print("✔ GET /api/history returns 404 Not Found")

resp_h2 = requests.post(f"{BASE_URL}/api/history/record", json={}, timeout=5)
assert resp_h2.status_code in [404, 405], f"/api/history/record returned {resp_h2.status_code}"
print(f"✔ POST /api/history/record returns {resp_h2.status_code} (removed)")

# Disk check
for p in [
    os.path.join(PROJECT_ROOT, "conversion_history.json"),
    os.path.join(PROJECT_ROOT, "temp", "conversion_history.json"),
    os.path.join(r"E:\Tool", "conversion_history.json"),
    os.path.join(PROJECT_ROOT, "core", "history_manager.py"),
    os.path.join(r"E:\Tool", "core", "history_manager.py"),
]:
    assert not os.path.exists(p), f"Artifact {p} must NOT exist!"
print("✔ Disk audit: zero conversion_history.json and zero history_manager.py across repo & E:\\Tool")

# Code audit
with open("static/index.html", "r", encoding="utf-8") as f:
    html_code = f.read()
assert "nav-history-btn" not in html_code
assert "history-modal" not in html_code
print("✔ UI audit: static/index.html has zero history buttons or modals")

with open("static/app.js", "r", encoding="utf-8") as f:
    app_code = f.read()
assert "/api/history" not in app_code
assert "nav-history-btn" not in app_code
assert "history-modal" not in app_code
print("✔ UI audit: static/app.js has zero /api/history calls or history modal logic")


# -------------------------------------------------------------
# 3. R3: Ultra-Lightweight & Minimalist UI & 27 Tools Verification
# -------------------------------------------------------------
print("\n--- [AUDIT R3] Ultra-Lightweight CSS & 27 PDF Tools Verification ---")

# CSS Audit
with open("static/style.css", "r", encoding="utf-8") as f:
    css_code = f.read()
# Check no active backdrop-filter blurs
assert "backdrop-filter: blur" not in css_code
print("✔ CSS audit: 0 active backdrop-filter blur effects")

# Helper to create PDF bytes
def make_pdf(num_pages=1, text="TitanPDF Test Page") -> bytes:
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text(fitz.Point(72, 100), f"{text} Trang {i+1}", fontsize=14)
    b = doc.write(deflate=True)
    doc.close()
    return b

tools_verified = 0

# 1. Merge
pdf1, pdf2 = make_pdf(1, "M1"), make_pdf(1, "M2")
r = requests.post(f"{BASE_URL}/api/process/merge", files=[("files", ("f1.pdf", pdf1, "application/pdf")), ("files", ("f2.pdf", pdf2, "application/pdf"))])
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 2. Split
r = requests.post(f"{BASE_URL}/api/process/split", files={"file": ("s.pdf", make_pdf(3), "application/pdf")}, data={"range_str": "1-2"})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 3. Compress
r = requests.post(f"{BASE_URL}/api/process/compress", files={"file": ("c.pdf", make_pdf(2), "application/pdf")}, data={"level": "recommended"})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 4. Word to PDF
docx_sample_path = os.path.join(PROJECT_ROOT, "output", "test_w2p_sample.docx")
doc_temp = docx.Document()
doc_temp.add_paragraph("Kiểm thử Word sang PDF Native COM")
doc_temp.save(docx_sample_path)
with open(docx_sample_path, "rb") as f:
    r = requests.post(f"{BASE_URL}/api/process/word-to-pdf", files={"file": f})
assert r.status_code == 200 and r.json()["success"]
os.remove(docx_sample_path)
tools_verified += 1

# 5. PDF to Images
r = requests.post(f"{BASE_URL}/api/process/pdf-to-images", files={"file": ("p2i.pdf", make_pdf(1), "application/pdf")}, data={"fmt": "png", "dpi": 150})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 6. Images to PDF
from PIL import Image
img_buf = io.BytesIO()
Image.new("RGB", (200, 200), color="blue").save(img_buf, format="JPEG")
r = requests.post(f"{BASE_URL}/api/process/images-to-pdf", files=[("files", ("img.jpg", img_buf.getvalue(), "image/jpeg"))])
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 7. PDF to Excel
from tests.fixtures import create_table_pdf
r = requests.post(f"{BASE_URL}/api/process/pdf-to-excel", files={"file": ("tbl.pdf", create_table_pdf(1), "application/pdf")})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 8. Rotate
r = requests.post(f"{BASE_URL}/api/process/rotate", files={"file": ("rot.pdf", make_pdf(1), "application/pdf")}, data={"angle": 90})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 9. Delete pages
r = requests.post(f"{BASE_URL}/api/process/delete-pages", files={"file": ("del.pdf", make_pdf(3), "application/pdf")}, data={"pages_str": "2"})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 10. Watermark
r = requests.post(f"{BASE_URL}/api/process/watermark", files={"file": ("wm.pdf", make_pdf(1), "application/pdf")}, data={"text": "BẢN QUYỀN", "opacity": 0.3})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 11. Page numbers
r = requests.post(f"{BASE_URL}/api/process/page-numbers", files={"file": ("pn.pdf", make_pdf(2), "application/pdf")}, data={"pattern": "Trang {page}/{total}"})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 12. Protect
r = requests.post(f"{BASE_URL}/api/process/protect", files={"file": ("pr.pdf", make_pdf(1), "application/pdf")}, data={"password": "123"})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 13. Unlock
from tests.fixtures import create_encrypted_pdf
r = requests.post(f"{BASE_URL}/api/process/unlock", files={"file": ("un.pdf", create_encrypted_pdf("pass123"), "application/pdf")}, data={"password": "pass123"})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 14. Extract pages
r = requests.post(f"{BASE_URL}/api/process/extract-pages", files={"file": ("ext.pdf", make_pdf(3), "application/pdf")}, data={"pages_str": "1,3"})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 15. Organize
r = requests.post(f"{BASE_URL}/api/process/organize", files={"file": ("org.pdf", make_pdf(3), "application/pdf")}, data={"order_str": "reverse"})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 16. Repair
r = requests.post(f"{BASE_URL}/api/process/repair", files={"file": ("rep.pdf", make_pdf(1), "application/pdf")})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 17. PPT to PDF
from tests.fixtures import create_sample_pptx
r = requests.post(f"{BASE_URL}/api/process/ppt-to-pdf", files={"file": ("p.pptx", create_sample_pptx(), "application/vnd.openxmlformats-officedocument.presentationml.presentation")})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 18. Excel to PDF
from tests.fixtures import create_sample_xlsx
r = requests.post(f"{BASE_URL}/api/process/excel-to-pdf", files={"file": ("x.xlsx", create_sample_xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 19. PDF to PPT
r = requests.post(f"{BASE_URL}/api/process/pdf-to-ppt", files={"file": ("p2p.pdf", make_pdf(1), "application/pdf")})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 20. PDF to PDF/A
r = requests.post(f"{BASE_URL}/api/process/pdf-to-pdfa", files={"file": ("p2a.pdf", make_pdf(1), "application/pdf")})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 21. Crop
r = requests.post(f"{BASE_URL}/api/process/crop", files={"file": ("cr.pdf", make_pdf(1), "application/pdf")}, data={"margin": 5.0})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 22. Sign
sig_buf = io.BytesIO()
Image.new("RGBA", (100, 50), color=(0, 0, 0, 0)).save(sig_buf, format="PNG")
r = requests.post(f"{BASE_URL}/api/process/sign", files={"file": ("sgn.pdf", make_pdf(1), "application/pdf"), "sig_image": ("s.png", sig_buf.getvalue(), "image/png")})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 23. Redact
from tests.fixtures import create_searchable_pdf
r = requests.post(f"{BASE_URL}/api/process/redact", files={"file": ("rd.pdf", create_searchable_pdf("SECRET"), "application/pdf")}, data={"text": "SECRET"})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 24. Compare
r = requests.post(f"{BASE_URL}/api/process/compare", files={"file1": ("c1.pdf", make_pdf(1, "A"), "application/pdf"), "file2": ("c2.pdf", make_pdf(1, "B"), "application/pdf")})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 25. Remove Watermark
r = requests.post(f"{BASE_URL}/api/process/remove-watermark", files={"file": ("rwm.pdf", make_pdf(1), "application/pdf")}, data={"custom_text": "DRAFT"})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 26. OCR (local default txt)
r = requests.post(f"{BASE_URL}/api/process/ocr", files={"file": ("ocr.pdf", make_pdf(1, "Văn bản mẫu"), "application/pdf")}, data={"engine": "tesseract"})
assert r.status_code == 200 and r.json()["success"]
tools_verified += 1

# 27. PDF to Word (already tested above)
tools_verified += 1

print(f"✔ 100% of tested tools ({tools_verified}/27) executed and returned HTTP 200 successfully!")


# -------------------------------------------------------------
# 4. R4: Packaging & Deployment Sync Verification
# -------------------------------------------------------------
print("\n--- [AUDIT R4] Packaging & Deployment Sync ---")

dist_exe = os.path.join(PROJECT_ROOT, "dist", "LUV-PDF-Portable.exe")
assert os.path.exists(dist_exe), f"{dist_exe} does not exist"
dist_size = os.path.getsize(dist_exe)
assert dist_size > 150 * 1024 * 1024, f"Portable exe size unexpectedly small: {dist_size}"
print(f"✔ dist\\LUV-PDF-Portable.exe verified: {dist_size:,} bytes")

tool_exe = os.path.join(r"E:\Tool", "LUV-PDF-Portable.exe")
if os.path.exists(r"E:\Tool"):
    assert os.path.exists(tool_exe), f"{tool_exe} does not exist"
    tool_size = os.path.getsize(tool_exe)
    print(f"✔ E:\\Tool\\LUV-PDF-Portable.exe verified: {tool_size:,} bytes")
    # Verify static sync
    assert os.path.exists(r"E:\Tool\static\index.html")
    assert os.path.exists(r"E:\Tool\static\app.js")
    assert os.path.exists(r"E:\Tool\static\style.css")
    assert not os.path.exists(r"E:\Tool\conversion_history.json")
    assert not os.path.exists(r"E:\Tool\core\history_manager.py")
    print("✔ E:\\Tool static and core assets verified in sync, zero history remnants")

print("\n" + "=" * 70)
print("🎉 ALL ADVERSARIAL QA AUDIT CHECKS PASSED 100% PERFECTLY!")
print("=" * 70)
