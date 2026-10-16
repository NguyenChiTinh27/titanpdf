# -*- coding: utf-8 -*-
"""
Audit and verification suite for TitanPDF AI & Chemical Tools.
"""

import os
import sys
import time
import json
import io
import requests

# Fix stdout encoding for Windows CP1258
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8888"
RESULTS = []

def record(test_name, passed, duration, details):
    RESULTS.append({
        "name": test_name,
        "passed": passed,
        "duration": round(duration, 2),
        "details": details
    })
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {test_name} ({round(duration, 2)}s): {details}", flush=True)

print("=" * 75, flush=True)
print("STARTING AUDIT: TitanPDF Comprehensive AI & Chemical Suite Verification", flush=True)
print("=" * 75, flush=True)

# 1. Health check
t0 = time.time()
try:
    r = requests.get(f"{BASE_URL}/api/health", timeout=5)
    record("1. Health Check", r.status_code == 200, time.time() - t0, f"Status {r.status_code}")
except Exception as e:
    record("1. Health Check", False, time.time() - t0, str(e))

# 2. License Status
t0 = time.time()
try:
    r = requests.get(f"{BASE_URL}/api/license/status", timeout=5)
    data = r.json()
    passed = r.status_code == 200 and data.get("is_valid") is True
    record("2. License Gate (Enterprise)", passed, time.time() - t0, f"Valid: {data.get('is_valid')}, Type: {data.get('license_type')}")
except Exception as e:
    record("2. License Gate (Enterprise)", False, time.time() - t0, str(e))

# 3. AI Translate (Tool 29)
t0 = time.time()
try:
    data = {
        "text": "Hazard statements: Causes serious eye irritation. Toxic to aquatic life with long lasting effects.",
        "source_lang": "auto",
        "target_lang": "vi",
        "engine": "google"
    }
    r = requests.post(f"{BASE_URL}/api/process/ai-translate", data=data, timeout=10)
    res = r.json()
    trans_text = res.get("translated_text", "")
    passed = r.status_code == 200 and len(trans_text) > 0 and "mắt" in trans_text.lower()
    record("3. AI Translate (Tool 29)", passed, time.time() - t0, f"Output: '{trans_text}'")
except Exception as e:
    record("3. AI Translate (Tool 29)", False, time.time() - t0, str(e))

# 4. AI Summarize (Tool 30)
t0 = time.time()
try:
    content = b"TitanPDF is an enterprise document intelligence and chemical safety management suite. It provides automated 16-section MSDS parsing, Chemical Inventory List (CIL) generation, and field inspection reporting."
    files = {"file": ("test_doc.txt", io.BytesIO(content), "text/plain")}
    data = {"mode": "executive", "length": "short", "engine": "google"}
    r = requests.post(f"{BASE_URL}/api/process/ai-summarize", files=files, data=data, timeout=15)
    res = r.json()
    passed = r.status_code == 200 and res.get("success") is True and len(res.get("summary_text", "")) > 0
    record("4. AI Summarize (Tool 30)", passed, time.time() - t0, f"Generated docx: {res.get('filename')}")
except Exception as e:
    record("4. AI Summarize (Tool 30)", False, time.time() - t0, str(e))

# 5. HSE Report Studio - Checklist Schema (Tool 33)
t0 = time.time()
try:
    r = requests.get(f"{BASE_URL}/api/hse/checklist_schema", timeout=10)
    data = r.json()
    sections = data.get("sections", [])
    total_items = data.get("total_items", 0)
    passed = r.status_code == 200 and len(sections) > 0 and total_items > 0
    record("5. HSE Studio - Checklist Schema (Tool 33)", passed, time.time() - t0, f"{len(sections)} sections, {total_items} items")
except Exception as e:
    record("5. HSE Studio - Checklist Schema (Tool 33)", False, time.time() - t0, str(e))

# 6. HSE Report Studio - DOCX Generation (Tool 33)
t0 = time.time()
try:
    payload = {
        "mode": "inspection",
        "metadata": {
            "date": "2026-10-15",
            "inspectors": "Nguyễn Thành Công",
            "company": "ZhanChen New Materials",
            "title": "Báo Cáo Kiểm Tra Hiện Trường HSE Tháng 10/2026",
            "department": "Xưởng Sản Xuất"
        },
        "checklist": [],
        "findings": [
            {
                "id": "F1",
                "departmentKey": "san-xuat",
                "departmentVi": "Sản xuất",
                "departmentZh": "生产部",
                "issueVi": "Bình chữa cháy CO2 bị che khuất bởi kiện hàng.",
                "issueZh": "二氧化碳灭火器被货物遮挡。",
                "suggestion": "Di chuyển kiện hàng giải phóng lối đi."
            }
        ]
    }
    r = requests.post(f"{BASE_URL}/api/hse/generate_docx", json=payload, timeout=20)
    passed = r.status_code == 200 and len(r.content) > 100000
    record("6. HSE Studio - Generate DOCX (Tool 33)", passed, time.time() - t0, f"Generated DOCX size: {len(r.content):,} bytes")
except Exception as e:
    record("6. HSE Studio - Generate DOCX (Tool 33)", False, time.time() - t0, str(e))

# 7. MSDS & CIL System - Google Drive Status (Tool 32)
t0 = time.time()
try:
    r = requests.get(f"{BASE_URL}/api/msds/gdrive/status", timeout=10)
    data = r.json()
    passed = r.status_code == 200 and data.get("available") is True
    record("7. MSDS & CIL - Google Drive Status (Tool 32)", passed, time.time() - t0, f"Target: {data.get('target_dir')}, Synced files: {data.get('files_count')}")
except Exception as e:
    record("7. MSDS & CIL - Google Drive Status (Tool 32)", False, time.time() - t0, str(e))

# 8. MSDS & CIL System - Export CIL Excel (Tool 32)
t0 = time.time()
try:
    r = requests.get(f"{BASE_URL}/api/msds/export-cil", timeout=15)
    passed = r.status_code == 200 and len(r.content) > 1000
    record("8. MSDS & CIL - Export CIL Excel (Tool 32)", passed, time.time() - t0, f"Excel size: {len(r.content):,} bytes")
except Exception as e:
    record("8. MSDS & CIL - Export CIL Excel (Tool 32)", False, time.time() - t0, str(e))

# 9. MSDS & CIL System - Google Drive Sync (Tool 32)
t0 = time.time()
try:
    r = requests.post(f"{BASE_URL}/api/msds/gdrive/sync", timeout=30)
    data = r.json()
    passed = r.status_code == 200 and data.get("success") is True
    record("9. MSDS & CIL - Google Drive Sync (Tool 32)", passed, time.time() - t0, f"Synced {data.get('synced_files')} files to {data.get('gdrive_folder')}")
except Exception as e:
    record("9. MSDS & CIL - Google Drive Sync (Tool 32)", False, time.time() - t0, str(e))

# 10. DOC-TRAN (Tool 27): Full Translation of F5603-Talc powder-MSDS-EN.doc
t0 = time.time()
doc_path = "temp/0564dd69d38a49b0906cfdae7dce8fda_F5603-Talc powder-MSDS-EN.doc"
if not os.path.exists(doc_path):
    for f in os.listdir("temp"):
        if f.endswith(".doc") and "F5603" in f:
            doc_path = os.path.join("temp", f)
            break

try:
    print(f"Testing DOC-TRAN with {doc_path} (103 items, large paragraphs)...", flush=True)
    with open(doc_path, "rb") as f:
        files = {"file": ("F5603-Talc powder-MSDS-EN.doc", f, "application/msword")}
        data = {
            "source_lang": "en",
            "target_lang": "vi",
            "provider": "google",
            "api_key": ""
        }
        r = requests.post(f"{BASE_URL}/api/process/interlinear-translate", files=files, data=data, timeout=90)
    
    res = r.json()
    filename = res.get("filename", "")
    out_path = os.path.join("output", filename)
    file_exists = os.path.exists(out_path)
    file_size = os.path.getsize(out_path) if file_exists else 0
    
    passed = r.status_code == 200 and file_exists and file_size > 5000
    record("10. DOC-TRAN - Interlinear Translation (Tool 27)", passed, time.time() - t0, f"Generated: {filename} ({file_size:,} bytes) in {round(time.time() - t0, 1)}s")
except Exception as e:
    record("10. DOC-TRAN - Interlinear Translation (Tool 27)", False, time.time() - t0, str(e))

print("=" * 75, flush=True)
print("AUDIT SUMMARY REPORT:", flush=True)
total = len(RESULTS)
passed_cnt = sum(1 for r in RESULTS if r["passed"])
failed_cnt = total - passed_cnt
print(f"Total Tests Executed: {total} | Passed: {passed_cnt} | Failed: {failed_cnt}", flush=True)
success_rate = round((passed_cnt / total) * 100, 1)
print(f"Overall Success Rate: {success_rate}%", flush=True)
print("=" * 75, flush=True)

# Write audit report to JSON
with open("output/audit_report.json", "w", encoding="utf-8") as f:
    json.dump({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "passed": passed_cnt,
        "failed": failed_cnt,
        "success_rate": success_rate,
        "results": RESULTS
    }, f, ensure_ascii=False, indent=2)
print("Audit report written to output/audit_report.json", flush=True)
