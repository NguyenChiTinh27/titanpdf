import os
import sys
import time
import threading
import requests
import unittest

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8888"

def stress_test_concurrency():
    print("Testing rapid concurrent history write and delete...")
    errors = []
    
    def worker_add(idx):
        for i in range(10):
            try:
                fname = f"concurrent_add_{idx}_{i}.pdf"
                r = requests.post(f"{BASE_URL}/api/history/record", json={
                    "tool_id": "compress",
                    "tool_title": "Nén PDF",
                    "source_files": [f"src_{idx}_{i}.pdf"],
                    "output_filename": fname,
                    "status": "success",
                    "details": "Concurrent test"
                }, timeout=5)
                if r.status_code != 200 or not r.json().get("success"):
                    errors.append(f"Add failed: {r.text}")
            except Exception as e:
                errors.append(f"Add exc: {e}")

    def worker_delete(idx):
        for i in range(10):
            try:
                fname = f"concurrent_add_{idx}_{i}.pdf"
                r = requests.post(f"{BASE_URL}/api/history/delete", json={
                    "filename": fname
                }, timeout=5)
                if r.status_code != 200 or not r.json().get("success"):
                    errors.append(f"Delete failed: {r.text}")
            except Exception as e:
                errors.append(f"Delete exc: {e}")

    threads = []
    for t_idx in range(5):
        t1 = threading.Thread(target=worker_add, args=(t_idx,))
        t2 = threading.Thread(target=worker_delete, args=(t_idx,))
        threads.extend([t1, t2])

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(f"Concurrent test completed. Total errors: {len(errors)}")
    if errors:
        print("Sample errors:", errors[:5])
    return len(errors) == 0

if __name__ == "__main__":
    stress_test_concurrency()
