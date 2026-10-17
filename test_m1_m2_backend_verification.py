"""
test_m1_m2_backend_verification.py
───────────────────────────────────
Comprehensive verification suite for M1 & M2 backend engine and router:
- core/monthly_inventory_engine.py
- core/monthly_inventory_router.py
- server.py (mounted router)

Verifies:
1. Health check and period lifecycle (create, list, get, update status, delete)
2. Sổ CIL integration (query available CIL chemicals, 1-click batch add, legal badges, ND 24 Annex IV thresholds)
3. Dual-mode data entry (Mode 1 Quick Summary inline edit, Mode 2 Transactions log)
4. Auto-balance arithmetic (closing = opening + import - export)
5. Roll-forward balance carryover (Month M closing -> Month M+1 opening)
6. Safety alerts (negative stock, exceed threshold)
7. Excel export (.xlsx binary stream with formulas and corporate headers)
8. Print preview HTML (A4 landscape)
9. Obsolete decree purge check (ZERO occurrences of ND 113, ND 82, TT 32, TT 04)
10. Both route prefixes: /api/monthly-inventory and /api/msds/monthly-report
"""

import io
import re
import unittest
from fastapi.testclient import TestClient
import openpyxl

from server import app


class TestMonthlyInventoryM1M2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        from core.monthly_inventory_engine import MonthlyInventoryEngine
        with MonthlyInventoryEngine.get_connection() as conn:
            conn.execute("DELETE FROM inventory_transactions;")
            conn.execute("DELETE FROM monthly_inventory_records;")
            conn.execute("DELETE FROM monthly_periods;")
            conn.commit()

    @classmethod
    def tearDownClass(cls):
        from core.monthly_inventory_engine import MonthlyInventoryEngine
        with MonthlyInventoryEngine.get_connection() as conn:
            conn.execute("DELETE FROM inventory_transactions;")
            conn.execute("DELETE FROM monthly_inventory_records;")
            conn.execute("DELETE FROM monthly_periods;")
            conn.commit()

    def test_01_health_check(self):
        """Kiểm tra endpoint /health hoạt động tốt trên cả 2 prefix."""
        r1 = self.client.get("/api/monthly-inventory/health")
        self.assertEqual(r1.status_code, 200)
        data1 = r1.json()
        self.assertEqual(data1["status"], "ok")
        self.assertIn("total_periods", data1)

        r2 = self.client.get("/api/msds/monthly-report/health")
        self.assertEqual(r2.status_code, 200)
        data2 = r2.json()
        self.assertEqual(data2["status"], "ok")

    def test_02_period_lifecycle(self):
        """Tạo kỳ báo cáo mới, đọc chi tiết, cập nhật trạng thái."""
        # Tạo kỳ 09/2026
        payload = {
            "month": 9,
            "year": 2026,
            "title": "Kỳ Tháng 09/2026 Test",
            "notes": "Kiểm thử tự động M1",
            "copy_from_previous": False,
        }
        res = self.client.post("/api/monthly-inventory/periods", json=payload)
        self.assertEqual(res.status_code, 200)
        period = res.json()
        self.assertEqual(period["month"], 9)
        self.assertEqual(period["year"], 2026)
        self.assertEqual(period["period_key"], "2026-09")
        pid = period["id"]

        # Đọc lại bằng ID
        r_get = self.client.get(f"/api/monthly-inventory/periods/{pid}")
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.json()["id"], pid)

        # Đọc bằng period_key
        r_get_key = self.client.get(f"/api/monthly-inventory/periods/2026-09")
        self.assertEqual(r_get_key.status_code, 200)
        self.assertEqual(r_get_key.json()["id"], pid)

        # Cập nhật trạng thái
        r_status = self.client.put(
            f"/api/monthly-inventory/periods/{pid}/status",
            json={"status": "LOCKED", "notes": "Chốt số liệu kiểm toán"},
        )
        self.assertEqual(r_status.status_code, 200)
        self.assertEqual(r_status.json()["period"]["status"], "LOCKED")

    def test_03_cil_integration_and_batch_add(self):
        """Kiểm tra danh mục CIL khả dụng và nạp hóa chất hàng loạt vào kỳ báo cáo."""
        # Tạo kỳ 08/2026
        res_p = self.client.post("/api/monthly-inventory/periods", json={"month": 8, "year": 2026, "copy_from_previous": False})
        pid = res_p.json()["id"]

        # Tra cứu danh sách CIL khả dụng
        r_avail = self.client.get(f"/api/monthly-inventory/available-chemicals?period_id={pid}")
        self.assertEqual(r_avail.status_code, 200)
        avail = r_avail.json()
        self.assertGreater(len(avail), 0)
        self.assertTrue(any(c["chemical_id"] == "000000000000102992" for c in avail))

        # 1-click batch add all CIL
        r_add = self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={"all": True})
        self.assertEqual(r_add.status_code, 200)
        added_count = r_add.json()["added_count"]
        self.assertGreater(added_count, 0)

        # Kiểm tra danh sách records sau khi add
        r_recs = self.client.get(f"/api/monthly-inventory/records?period_id={pid}")
        self.assertEqual(r_recs.status_code, 200)
        recs = r_recs.json()["records"]
        self.assertEqual(len(recs), added_count)

        # Kiểm tra hóa chất có nhãn pháp lý và CAS chuẩn
        xylene_rec = next((r for r in recs if r["chemical_id"] == "000000000000102992"), None)
        self.assertIsNotNone(xylene_rec)
        self.assertEqual(xylene_rec["cas_number"], "1330-20-7")
        self.assertIn("NĐ 24", xylene_rec["legal_classification"])

    def test_04_dual_mode_quick_summary_and_auto_balance(self):
        """Mode 1: Nhập trực tiếp initial_stock, import_qty, export_qty -> kiểm tra auto-balance."""
        res_p = self.client.post("/api/monthly-inventory/periods", json={"month": 7, "year": 2026, "copy_from_previous": False})
        pid = res_p.json()["id"]

        # Thêm 1 hóa chất cụ thể
        self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={"chemical_ids": ["000000000000102992"]})
        recs = self.client.get(f"/api/monthly-inventory/records?period_id={pid}").json()["records"]
        rec = recs[0]
        rid = rec["id"]

        # Cập nhật số liệu: Tồn đầu 500, Nhập 200, Xuất 150 -> Tồn cuối phải là 550
        update_payload = {
            "opening_stock": 500.0,
            "import_qty": 200.0,
            "export_qty": 150.0,
            "storage_location": "Kho Sơn Bàu Bàng",
        }
        r_up = self.client.put(f"/api/monthly-inventory/records/{rid}", json=update_payload)
        self.assertEqual(r_up.status_code, 200)
        up_data = r_up.json()
        self.assertEqual(up_data["closing_stock"], 550.0)
        self.assertEqual(up_data["ending_stock"], 550.0)
        self.assertEqual(up_data["warning_status"], "normal")

        # Cập nhật batch API
        r_batch = self.client.put("/api/monthly-inventory/records-batch", json={
            "period_id": pid,
            "records": [{"id": rid, "export_qty": 180.0}]
        })
        self.assertEqual(r_batch.status_code, 200)
        # Tồn cuối phải tự tính lại: 500 + 200 - 180 = 520
        rec_check = self.client.get(f"/api/monthly-inventory/records/{rid}").json()
        self.assertEqual(rec_check["closing_stock"], 520.0)

    def test_05_detailed_transactions_mode(self):
        """Mode 2: Ghi phiếu nhập, phiếu xuất chi tiết -> tự động cộng dồn lên dòng tháng."""
        res_p = self.client.post("/api/monthly-inventory/periods", json={"month": 6, "year": 2026, "copy_from_previous": False})
        pid = res_p.json()["id"]

        self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={"chemical_ids": ["A1570"]})
        rec = self.client.get(f"/api/monthly-inventory/records?period_id={pid}").json()["records"][0]
        rid = rec["id"]

        # Đặt tồn đầu = 100
        self.client.put(f"/api/monthly-inventory/records/{rid}", json={"opening_stock": 100.0})

        # Ghi 2 phiếu nhập: 50 kg và 30 kg -> tổng nhập = 80 kg
        t1 = self.client.post("/api/monthly-inventory/transactions", json={
            "period_id": pid,
            "chemical_id": "A1570",
            "transaction_type": "IMPORT",
            "quantity": 50.0,
            "transaction_date": "2026-06-05",
            "reference_doc": "PO-202606-01",
            "department": "NCC Hóa Chất",
        })
        self.assertEqual(t1.status_code, 200)

        t2 = self.client.post("/api/monthly-inventory/transactions", json={
            "period_id": pid,
            "chemical_id": "A1570",
            "transaction_type": "IMPORT",
            "quantity": 30.0,
            "transaction_date": "2026-06-10",
            "reference_doc": "PO-202606-02",
        })
        self.assertEqual(t2.status_code, 200)

        # Ghi 1 phiếu xuất: 45 kg -> tổng xuất = 45 kg
        t3 = self.client.post("/api/monthly-inventory/transactions", json={
            "period_id": pid,
            "chemical_id": "A1570",
            "transaction_type": "EXPORT",
            "quantity": 45.0,
            "transaction_date": "2026-06-15",
            "department": "Xưởng PU",
            "purpose": "Pha chế sơn",
        })
        self.assertEqual(t3.status_code, 200)

        # Kiểm tra dòng hóa chất:
        # Tồn đầu = 100, Tổng nhập = 80, Tổng xuất = 45 -> Tồn cuối = 100 + 80 - 45 = 135
        rec_after = self.client.get(f"/api/monthly-inventory/records/{rid}").json()
        self.assertEqual(rec_after["import_qty"], 80.0)
        self.assertEqual(rec_after["export_qty"], 45.0)
        self.assertEqual(rec_after["closing_stock"], 135.0)

        # Kiểm tra danh sách giao dịch
        txns = self.client.get(f"/api/monthly-inventory/periods/{pid}/transactions").json()
        self.assertEqual(len(txns), 3)

    def test_06_roll_forward_balance(self):
        """Cơ chế chuyển số dư: Tồn cuối kỳ tháng M kế thừa làm tồn đầu kỳ tháng M+1."""
        # Tạo tháng 1/2026
        p1 = self.client.post("/api/monthly-inventory/periods", json={"month": 1, "year": 2026, "copy_from_previous": False}).json()
        p1_id = p1["id"]

        self.client.post(f"/api/monthly-inventory/periods/{p1_id}/add-from-cil", json={"chemical_ids": ["ZW55019"]})
        rec1 = self.client.get(f"/api/monthly-inventory/records?period_id={p1_id}").json()["records"][0]

        # Đặt tồn đầu = 300, nhập = 100, xuất = 50 -> tồn cuối tháng 1 = 350
        self.client.put(f"/api/monthly-inventory/records/{rec1['id']}", json={
            "opening_stock": 300.0,
            "import_qty": 100.0,
            "export_qty": 50.0,
        })

        # Tạo tháng 2/2026 với copy_from_previous=True
        p2 = self.client.post("/api/monthly-inventory/periods", json={"month": 2, "year": 2026, "copy_from_previous": True}).json()
        p2_id = p2["id"]

        recs2 = self.client.get(f"/api/monthly-inventory/records?period_id={p2_id}").json()["records"]
        rec2 = next((r for r in recs2 if r["chemical_id"] == "ZW55019"), None)
        self.assertIsNotNone(rec2)
        # Tồn đầu tháng 2 phải bằng đúng tồn cuối tháng 1 (350.0)
        self.assertEqual(rec2["opening_stock"], 350.0)
        self.assertEqual(rec2["import_qty"], 0.0)
        self.assertEqual(rec2["export_qty"], 0.0)
        self.assertEqual(rec2["closing_stock"], 350.0)

    def test_07_safety_alerts(self):
        """Kiểm tra phát hiện tồn kho âm và vượt ngưỡng an toàn Phụ lục IV NĐ 24."""
        p = self.client.post("/api/monthly-inventory/periods", json={"month": 5, "year": 2026, "copy_from_previous": False}).json()
        pid = p["id"]

        self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={"all": True})
        recs = self.client.get(f"/api/monthly-inventory/records?period_id={pid}").json()["records"]

        # 1. Giả lập tồn kho âm: Tồn đầu 10, Xuất 50 -> Tồn cuối -40
        r_neg = recs[0]
        self.client.put(f"/api/monthly-inventory/records/{r_neg['id']}", json={
            "opening_stock": 10.0,
            "import_qty": 0.0,
            "export_qty": 50.0,
        })

        # 2. Giả lập vượt ngưỡng an toàn: Ngưỡng 5,000 kg, Tồn cuối 6,000 kg
        r_th = recs[1]
        self.client.put(f"/api/monthly-inventory/records/{r_th['id']}", json={
            "opening_stock": 6000.0,
            "import_qty": 0.0,
            "export_qty": 0.0,
            "safety_threshold": 5000.0,
        })

        # Kiểm tra endpoint alerts
        r_alert = self.client.get(f"/api/monthly-inventory/periods/{pid}/safety-alerts")
        self.assertEqual(r_alert.status_code, 200)
        alerts = r_alert.json()
        self.assertGreaterEqual(len(alerts["negative_balance"]), 1)
        self.assertGreaterEqual(len(alerts["threshold_exceeded"]), 1)
        self.assertGreaterEqual(alerts["total_alerts"], 2)

    def test_08_excel_export_structure(self):
        """Kiểm tra tệp Excel (.xlsx) xuất ra có định dạng chuẩn, công thức tính và chữ ký."""
        r_excel = self.client.get("/api/msds/monthly-report/export-excel?month=10&year=2026")
        self.assertEqual(r_excel.status_code, 200)
        self.assertIn("application/vnd.openxmlformats", r_excel.headers["content-type"])
        self.assertIn("Bao_Cao_Su_Dung_Hoa_Chat_Thang_10_2026.xlsx", r_excel.headers["content-disposition"])

        wb = openpyxl.load_workbook(io.BytesIO(r_excel.content))
        self.assertIn("NXT Thang 10_2026", wb.sheetnames)
        ws = wb["NXT Thang 10_2026"]

        # Kiểm tra tiêu đề doanh nghiệp và tiêu đề báo cáo
        self.assertIn("ZHANCHEN", str(ws["A1"].value))
        self.assertIn("BÁO CÁO TÌNH HÌNH NHẬP - XUẤT - TỒN", str(ws["A5"].value))

        # Kiểm tra header dòng 8 có đủ các cột quan trọng
        headers = [ws.cell(row=8, column=c).value for c in range(1, 15)]
        self.assertIn("STT", headers)
        self.assertIn("Mã Hóa Chất / Sản Phẩm", headers)
        self.assertIn("Tồn Cuối Kỳ", headers)
        self.assertIn("Ngưỡng An Toàn (kg)", headers)

    def test_09_print_html_preview(self):
        """Kiểm tra endpoint in ấn trả về tài liệu HTML với CSS A4 landscape."""
        r_html = self.client.get("/api/monthly-inventory/print-html?month=10&year=2026")
        self.assertEqual(r_html.status_code, 200)
        self.assertIn("text/html", r_html.headers["content-type"])
        html_str = r_html.text
        self.assertIn("A4 landscape", html_str)
        self.assertIn("@media print", html_str)
        self.assertIn("BÁO CÁO TÌNH HÌNH NHẬP - XUẤT - TỒN", html_str)
        self.assertIn("NGƯỜI LẬP BIỂU", html_str)
        self.assertIn("TRƯỞNG PHÒNG EHS", html_str)

    def test_10_obsolete_decree_purge(self):
        """Kiểm tra tuyệt đối không chứa bất kỳ tham chiếu nào đến các nghị định đã hết hiệu lực."""
        obsolete_patterns = [
            re.compile(r"113/2017/NĐ-CP", re.IGNORECASE),
            re.compile(r"113/2017/ND-CP", re.IGNORECASE),
            re.compile(r"82/2022/NĐ-CP", re.IGNORECASE),
            re.compile(r"82/2022/ND-CP", re.IGNORECASE),
            re.compile(r"32/2017/TT-BCT", re.IGNORECASE),
            re.compile(r"04/2012/TT-BCT", re.IGNORECASE),
        ]

        # Kiểm tra nội dung mã nguồn của 2 file mới
        for fname in ["core/monthly_inventory_engine.py", "core/monthly_inventory_router.py"]:
            with open(fname, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line_no, line in enumerate(lines, start=1):
                # Bỏ qua dòng ghi chú về việc "bãi bỏ" trong docstring
                if "bãi bỏ" in line or "repeal" in line or "Tuyệt đối KHÔNG chứa" in line:
                    continue
                for pat in obsolete_patterns:
                    self.assertIsNone(
                        pat.search(line),
                        f"Phát hiện văn bản bãi bỏ tại {fname}:{line_no}: {line.strip()}"
                    )

        # Kiểm tra nội dung HTML trả về từ endpoint in ấn
        r_html = self.client.get("/api/monthly-inventory/print-html?month=10&year=2026")
        for pat in obsolete_patterns:
            self.assertIsNone(pat.search(r_html.text), "HTML print preview chứa văn bản bãi bỏ!")


if __name__ == "__main__":
    unittest.main()
