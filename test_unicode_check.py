import sys, os, time, requests

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8888"

def test_unicode_and_spaces():
    print("Testing Unicode Vietnamese filenames & Explorer actions...")
    fname = "Báo cáo tài chính quý 3 (2026) - Đã ký.pdf"
    fpath = os.path.join("output", fname)
    with open(fpath, "wb") as f:
        f.write(b"%PDF-1.4 test")

    # 1. Record in history
    r = requests.post(f"{BASE_URL}/api/history/record", json={
        "tool_id": "compress",
        "tool_title": "Nén PDF",
        "source_files": ["Bản thảo gốc.pdf"],
        "output_filename": fname,
        "status": "success",
        "details": "Kiểm thử tiếng Việt có dấu và khoảng trắng"
    })
    print("Record status:", r.status_code, r.json().get("success"))

    # 2. Search with Vietnamese text
    r_search = requests.get(f"{BASE_URL}/api/history?search=tài chính")
    print("Search status:", r_search.status_code, "Found:", len(r_search.json().get("history", [])))

    # 3. Open location
    r_loc = requests.post(f"{BASE_URL}/api/history/open-location", json={"filename": fname})
    print("Open location status:", r_loc.status_code, r_loc.json())

    # 4. Open location with path traversal attempt
    r_trav = requests.post(f"{BASE_URL}/api/history/open-location", json={"filename": "../../server.py"})
    print("Path traversal open location:", r_trav.status_code, r_trav.json())

    # 5. Delete entry with path traversal attempt
    r_del_trav = requests.post(f"{BASE_URL}/api/history/delete", json={"filename": "../../requirements.txt"})
    print("Path traversal delete attempt:", r_del_trav.status_code, r_del_trav.json())

    # 6. Delete clean entry
    r_del = requests.post(f"{BASE_URL}/api/history/delete", json={"filename": fname})
    print("Clean delete status:", r_del.status_code, r_del.json().get("success"))

if __name__ == "__main__":
    test_unicode_and_spaces()
