"""
test_stress_statutory_precursors.py
───────────────────────────────────
Independent Empirical Stress Test Harness by Challenger 2 (teamwork_preview_challenger)
for TitanPDF Monthly Chemical Inventory & Usage Tracking (NXT) Engine & Router.

Focus Areas:
1. Decree 24/2026/NĐ-CP Phụ lục IV-A boundary conditions:
   - Exactly at threshold (50,000.0 kg vs 49,999.9 kg vs 50,000.1 kg)
   - Differentiation of safe, at threshold, and exceeded alert flags
2. Negative balance detection & negative export/import validation:
   - Mode 1 inline edit negative closing
   - Mode 2 transaction export exceeding stock
   - Negative values in inputs (negative opening, negative import, negative export)
3. Decree 26/2026/NĐ-CP industrial precursor solvents tracking & isolation:
   - Toluene (108-88-3), Acetone (67-64-1), MEK (78-93-3)
   - CIL composition inheritance and isolation filtering
   - Handling of pure precursors not in pre-seeded CIL table
4. Edge conditions & Malformed inputs:
   - Zero stock balance
   - Duplicate addition prevention and concurrency robustness
   - Non-existent chemical IDs (orphan transaction risk)
   - Empty period handling (KPI, Excel, Print HTML)
   - Invalid month/year/format handling
"""

from __future__ import annotations

import io
import json
import logging
import math
import os
import sqlite3
import sys
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Reconfigure console output encoding on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi.testclient import TestClient
from server import app
from core.monthly_inventory_engine import MonthlyInventoryEngine
from core.legal_engine import LegalCatalogEngine, parse_threshold_numeric
from core.msds_intelligence import DB_PATH

# Authoritative Statutory Thresholds under Decree 24/2026/NĐ-CP Phụ lục IV-A (kg)
STATUTORY_DECREE_24_THRESHOLDS = {
    "108-88-3": 50000.0,    # Toluen (50 tấn)
    "67-64-1": 50000.0,     # Axeton (50 tấn)
    "7664-41-7": 5000.0,    # Amoniac (5 tấn)
    "7647-01-0": 50000.0,   # Axit clohydric (50 tấn)
    "7664-93-9": 50000.0,   # Axit sunfuric (50 tấn)
    "1330-20-7": 50000.0,   # Xylen (50 tấn)
    "26471-62-5": 10000.0,  # TDI (10 tấn)
    "7782-50-5": 5000.0,    # Clo (5 tấn)
}

# Authoritative Industrial Precursors under Decree 26/2026/NĐ-CP Danh mục IV.C
STATUTORY_PRECURSORS_ND26_IV_C = {
    "108-88-3": "Toluen",
    "67-64-1": "Axeton",
    "78-93-3": "Metyletylxeton (MEK)",
    "7664-93-9": "Axit sunfuric",
    "7647-01-0": "Axit clohydric",
}


class EmpiricalHarnessResults:
    results: List[Dict[str, Any]] = []

    @classmethod
    def record(cls, test_id: str, area: str, description: str, passed: bool, evidence: str, severity: str = "INFO"):
        cls.results.append({
            "test_id": test_id,
            "area": area,
            "description": description,
            "passed": passed,
            "evidence": evidence,
            "severity": severity,
        })


class TestStressStatutoryAndPrecursors(unittest.TestCase):
    client: TestClient

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        MonthlyInventoryEngine.init_db()

    def setUp(self):
        # Tạo test period riêng cho mỗi test để tránh cross-contamination
        pass

    # =========================================================================
    # AREA 1: DECREE 24 ANNEX IV-A BOUNDARY CONDITIONS
    # =========================================================================

    def test_01_boundary_toluene_below_threshold(self):
        """Case 1.1: 49,999.9 kg Toluene (Ngưỡng 50,000 kg) -> Dưới ngưỡng 0.1 kg (Phải an toàn: normal)."""
        p = self.client.post("/api/monthly-inventory/periods", json={"month": 1, "year": 2030, "copy_from_previous": False}).json()
        pid = p["id"]

        # Thêm 1 hóa chất và set threshold = 50000.0
        self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={"chemical_ids": ["000000000000102992"]})
        recs = self.client.get(f"/api/monthly-inventory/records?period_id={pid}").json()["records"]
        rid = recs[0]["id"]

        r_up = self.client.put(f"/api/monthly-inventory/records/{rid}", json={
            "opening_stock": 49999.9,
            "import_qty": 0.0,
            "export_qty": 0.0,
            "safety_threshold": 50000.0,
        })
        self.assertEqual(r_up.status_code, 200)
        data = r_up.json()

        # Dưới ngưỡng: warning_status phải là 'normal'
        is_normal = data["warning_status"] == "normal"
        EmpiricalHarnessResults.record(
            "STRESS-01-BELOW",
            "Decree 24 Annex IV-A",
            "Stock 49,999.9 kg vs 50,000.0 kg threshold: must be safe (normal)",
            is_normal,
            f"Observed warning_status='{data['warning_status']}', closing={data['closing_stock']}",
            "HIGH" if not is_normal else "INFO"
        )
        self.assertEqual(data["warning_status"], "normal")

    def test_02_boundary_toluene_exactly_at_threshold(self):
        """
        Case 1.2: Exactly at threshold 50,000.0 kg (Ngưỡng 50,000.0 kg).
        Theo Luật Hóa chất 69/2025/QH15 & NĐ 24/2026/NĐ-CP Phụ lục IV-A:
        Khối lượng tồn trữ >= ngưỡng quy định là ĐÃ KÍCH HOẠT NGHĨA VỤ LẬP KẾ HOẠCH PNUPSC.
        Kiểm tra xem hệ thống có nhận diện đúng mức tại ngưỡng (>=) hay bỏ sót thành 'normal'.
        """
        p = self.client.post("/api/monthly-inventory/periods", json={"month": 2, "year": 2030, "copy_from_previous": False}).json()
        pid = p["id"]

        self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={"chemical_ids": ["000000000000102992"]})
        recs = self.client.get(f"/api/monthly-inventory/records?period_id={pid}").json()["records"]
        rid = recs[0]["id"]

        r_up = self.client.put(f"/api/monthly-inventory/records/{rid}", json={
            "opening_stock": 50000.0,
            "import_qty": 0.0,
            "export_qty": 0.0,
            "safety_threshold": 50000.0,
        })
        self.assertEqual(r_up.status_code, 200)
        data = r_up.json()

        # Kiểm tra API safety-alerts
        alerts = self.client.get(f"/api/monthly-inventory/periods/{pid}/safety-alerts").json()
        exceeded_in_alerts = any(a["record_id"] == rid for a in alerts.get("threshold_exceeded", []))

        # Kiểm tra KPI threshold_exceeded_count
        kpi = self.client.get(f"/api/monthly-inventory/summary?period_id={pid}").json()
        kpi_count = kpi.get("threshold_exceeded_count", 0)

        # Statutory check: Under Law 69 & Decree 24, >= threshold triggers statutory obligation
        # Let's see if system flagged it or treated as 'normal'
        flagged_at_threshold = (data["warning_status"] in ("exceed_threshold", "at_threshold")) or exceeded_in_alerts or (kpi_count > 0)
        
        evidence_msg = (
            f"closing_stock={data['closing_stock']}, threshold=50000.0; "
            f"record.warning_status='{data['warning_status']}'; "
            f"exceeded_in_alerts={exceeded_in_alerts}; kpi.threshold_exceeded_count={kpi_count}."
        )

        EmpiricalHarnessResults.record(
            "STRESS-02-EXACT-AT-THRESHOLD",
            "Decree 24 Annex IV-A",
            "Stock 50,000.0 kg exactly at 50,000.0 kg threshold: statutory >= threshold obligation check",
            flagged_at_threshold,
            evidence_msg,
            "CRITICAL" if not flagged_at_threshold else "INFO"
        )
        # Note: We record empirical finding whether it passed or failed.

    def test_03_boundary_toluene_above_threshold(self):
        """Case 1.3: 50,000.1 kg Toluene (Ngưỡng 50,000.0 kg) -> Vượt ngưỡng 0.1 kg (Phải cảnh báo exceed_threshold)."""
        p = self.client.post("/api/monthly-inventory/periods", json={"month": 3, "year": 2030, "copy_from_previous": False}).json()
        pid = p["id"]

        self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={"chemical_ids": ["000000000000102992"]})
        recs = self.client.get(f"/api/monthly-inventory/records?period_id={pid}").json()["records"]
        rid = recs[0]["id"]

        r_up = self.client.put(f"/api/monthly-inventory/records/{rid}", json={
            "opening_stock": 50000.1,
            "import_qty": 0.0,
            "export_qty": 0.0,
            "safety_threshold": 50000.0,
        })
        self.assertEqual(r_up.status_code, 200)
        data = r_up.json()

        is_exceeded = data["warning_status"] == "exceed_threshold"
        alerts = self.client.get(f"/api/monthly-inventory/periods/{pid}/safety-alerts").json()
        in_alerts = len(alerts.get("threshold_exceeded", [])) == 1

        EmpiricalHarnessResults.record(
            "STRESS-03-ABOVE",
            "Decree 24 Annex IV-A",
            "Stock 50,000.1 kg vs 50,000.0 kg threshold: must trigger exceed_threshold alert",
            is_exceeded and in_alerts,
            f"warning_status='{data['warning_status']}', alerts_count={len(alerts.get('threshold_exceeded', []))}",
            "HIGH" if not (is_exceeded and in_alerts) else "INFO"
        )
        self.assertEqual(data["warning_status"], "exceed_threshold")
        self.assertTrue(in_alerts)

    def test_04_differentiation_of_alert_states(self):
        """
        Case 1.4: Tri-state differentiation test:
        Does the engine clearly differentiate between:
        - SAFE (closing < threshold)
        - AT THRESHOLD (closing == threshold)
        - EXCEEDED (closing > threshold)?
        """
        p = self.client.post("/api/monthly-inventory/periods", json={"month": 4, "year": 2030, "copy_from_previous": False}).json()
        pid = p["id"]

        # Add 3 chemicals from CIL
        self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={"all": True})
        recs = self.client.get(f"/api/monthly-inventory/records?period_id={pid}").json()["records"]
        self.assertGreaterEqual(len(recs), 3)

        r_safe, r_at, r_above = recs[0], recs[1], recs[2]

        self.client.put(f"/api/monthly-inventory/records/{r_safe['id']}", json={"opening_stock": 49999.0, "safety_threshold": 50000.0})
        self.client.put(f"/api/monthly-inventory/records/{r_at['id']}", json={"opening_stock": 50000.0, "safety_threshold": 50000.0})
        self.client.put(f"/api/monthly-inventory/records/{r_above['id']}", json={"opening_stock": 50001.0, "safety_threshold": 50000.0})

        rec_safe = self.client.get(f"/api/monthly-inventory/records/{r_safe['id']}").json()
        rec_at = self.client.get(f"/api/monthly-inventory/records/{r_at['id']}").json()
        rec_above = self.client.get(f"/api/monthly-inventory/records/{r_above['id']}").json()

        differentiates_all_three = (
            rec_safe["warning_status"] != rec_at["warning_status"] and
            rec_at["warning_status"] != rec_above["warning_status"]
        )
        
        evidence = (
            f"rec_safe={rec_safe['warning_status']}, "
            f"rec_at={rec_at['warning_status']}, "
            f"rec_above={rec_above['warning_status']}"
        )

        EmpiricalHarnessResults.record(
            "STRESS-04-TRI-STATE",
            "Decree 24 Annex IV-A",
            "Verify distinct alert flags accurately differentiate safe (<), at threshold (==), and exceeded (>)",
            differentiates_all_three,
            evidence,
            "MEDIUM" if not differentiates_all_three else "INFO"
        )

    # =========================================================================
    # AREA 2: NEGATIVE BALANCE DETECTION & INPUT VALIDATION
    # =========================================================================

    def test_05_negative_balance_inline_mode(self):
        """Case 2.1: Mode 1 inline edit with excess export: 100 + 50 - 200 = -50 kg."""
        p = self.client.post("/api/monthly-inventory/periods", json={"month": 5, "year": 2030, "copy_from_previous": False}).json()
        pid = p["id"]

        self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={"chemical_ids": ["000000000000102992"]})
        rec = self.client.get(f"/api/monthly-inventory/records?period_id={pid}").json()["records"][0]

        r_up = self.client.put(f"/api/monthly-inventory/records/{rec['id']}", json={
            "opening_stock": 100.0,
            "import_qty": 50.0,
            "export_qty": 200.0,
        })
        self.assertEqual(r_up.status_code, 200)
        data = r_up.json()

        is_neg = data["closing_stock"] == -50.0 and data["warning_status"] == "negative_stock"
        alerts = self.client.get(f"/api/monthly-inventory/periods/{pid}/safety-alerts").json()
        has_alert = any(a["record_id"] == rec["id"] for a in alerts.get("negative_balance", []))

        EmpiricalHarnessResults.record(
            "STRESS-05-NEG-INLINE",
            "Negative Balance Detection",
            "Inline edit excess export (closing = -50 kg) correctly triggers negative_stock warning and alert list",
            is_neg and has_alert,
            f"closing={data['closing_stock']}, warning_status='{data['warning_status']}', in_alerts={has_alert}",
            "HIGH" if not (is_neg and has_alert) else "INFO"
        )
        self.assertTrue(is_neg)
        self.assertTrue(has_alert)

    def test_06_negative_balance_transaction_mode(self):
        """Case 2.2: Mode 2 transactions: initial stock 50 kg, export transaction 120 kg -> closing = -70 kg."""
        p = self.client.post("/api/monthly-inventory/periods", json={"month": 6, "year": 2030, "copy_from_previous": False}).json()
        pid = p["id"]

        self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={"chemical_ids": ["A1570"]})
        rec = self.client.get(f"/api/monthly-inventory/records?period_id={pid}").json()["records"][0]
        self.client.put(f"/api/monthly-inventory/records/{rec['id']}", json={"opening_stock": 50.0})

        # Tạo phiếu xuất 120 kg
        t_resp = self.client.post("/api/monthly-inventory/transactions", json={
            "period_id": pid,
            "chemical_id": "A1570",
            "transaction_type": "EXPORT",
            "quantity": 120.0,
            "transaction_date": "2030-06-15",
            "purpose": "Xuất thử nghiệm vượt tồn kho",
        })
        self.assertEqual(t_resp.status_code, 200)

        # Kiểm tra record sau transaction
        rec_after = self.client.get(f"/api/monthly-inventory/records/{rec['id']}").json()
        is_neg = rec_after["closing_stock"] == -70.0 and rec_after["warning_status"] == "negative_stock"

        EmpiricalHarnessResults.record(
            "STRESS-06-NEG-TXN",
            "Negative Balance Detection",
            "Transaction excess export (50 - 120 = -70 kg) recalculates record and flags negative_stock",
            is_neg,
            f"closing={rec_after['closing_stock']}, warning_status='{rec_after['warning_status']}'",
            "HIGH" if not is_neg else "INFO"
        )
        self.assertTrue(is_neg)

    def test_07_malformed_negative_inputs_validation(self):
        """
        Case 2.3: Malformed negative inputs to inline edit:
        What if user inputs negative quantity directly (e.g. import_qty = -100 or export_qty = -200)?
        Should the system reject invalid negative inputs, or does it accept and corrupt inventory math?
        """
        p = self.client.post("/api/monthly-inventory/periods", json={"month": 7, "year": 2030, "copy_from_previous": False}).json()
        pid = p["id"]

        self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={"chemical_ids": ["000000000000102992"]})
        rec = self.client.get(f"/api/monthly-inventory/records?period_id={pid}").json()["records"][0]

        # Test A: Negative export quantity (-50 kg)
        # If accepted, closing = opening + import - (-50) = opening + import + 50 (paradoxical stock creation!)
        r_neg_exp = self.client.put(f"/api/monthly-inventory/records/{rec['id']}", json={
            "opening_stock": 100.0,
            "import_qty": 0.0,
            "export_qty": -50.0,
        })
        
        # Test B: Negative transaction quantity (-50 kg) in Mode 2
        r_neg_txn = self.client.post("/api/monthly-inventory/transactions", json={
            "period_id": pid,
            "chemical_id": "000000000000102992",
            "transaction_type": "IMPORT",
            "quantity": -50.0,
            "transaction_date": "2030-07-10",
        })

        # Expected: Transaction mode should reject negative quantity (HTTP 400 or 422)
        txn_rejected = r_neg_txn.status_code in (400, 422)

        # Inline edit mode: Does it reject or accept negative export?
        inline_rejected = r_neg_exp.status_code in (400, 422)
        inline_data = r_neg_exp.json() if r_neg_exp.status_code == 200 else {}
        paradoxical_stock = inline_data.get("closing_stock") == 150.0

        evidence = (
            f"Transaction negative qty status={r_neg_txn.status_code} (rejected={txn_rejected}); "
            f"Inline negative export status={r_neg_exp.status_code}, closing_stock={inline_data.get('closing_stock')}, "
            f"paradoxical_stock_creation={paradoxical_stock}"
        )

        passed = txn_rejected and (inline_rejected or not paradoxical_stock)
        EmpiricalHarnessResults.record(
            "STRESS-07-MALFORMED-NEG-INPUTS",
            "Negative Balance Detection",
            "Validation of negative input quantities in transactions and inline edit",
            passed,
            evidence,
            "MEDIUM" if not passed else "INFO"
        )

    # =========================================================================
    # AREA 3: DECREE 26/2026/NĐ-CP PRECURSOR SOLVENTS TRACKING & ISOLATION
    # =========================================================================

    def test_08_precursor_catalog_mapping(self):
        """Case 3.1: Statutory identification of Toluene, Acetone, MEK in LegalCatalogEngine under ND 26."""
        engine = LegalCatalogEngine.get_instance()
        
        precursor_cases = [
            ("108-88-3", "Toluen"),
            ("67-64-1", "Axeton"),
            ("78-93-3", "MEK"),
        ]
        
        all_found = True
        evidence_list = []
        for cas, name in precursor_cases:
            matches = engine.match_cas(cas)
            has_nd26_iv_c = any(
                m.get("section_id") in ("ND26-IV-C", "ND28-IV-C") or
                "IV.C" in str(m.get("badge", {}).get("label", ""))
                for m in matches
            )
            evidence_list.append(f"{name} ({cas}): matches={len(matches)}, has_nd26_iv_c={has_nd26_iv_c}")
            if not has_nd26_iv_c:
                all_found = False

        EmpiricalHarnessResults.record(
            "STRESS-08-PRECURSOR-CATALOG",
            "Decree 26 Precursors",
            "Statutory identification of Toluene, Acetone, MEK in LegalCatalogEngine",
            all_found,
            "; ".join(evidence_list),
            "HIGH" if not all_found else "INFO"
        )
        self.assertTrue(all_found)

    def test_09_cil_composition_precursor_inheritance_and_isolation(self):
        """
        Case 3.2: CIL mixture composition inheritance:
        Chemical '000000000000102992' contains Toluene (108-88-3) in compositions table.
        When added to period, must inherit legal tag 'NĐ 26 (Tiền chất IV.C)' and be isolatable via filter.
        """
        p = self.client.post("/api/monthly-inventory/periods", json={"month": 8, "year": 2030, "copy_from_previous": False}).json()
        pid = p["id"]

        self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={"chemical_ids": ["000000000000102992"]})
        recs = self.client.get(f"/api/monthly-inventory/records?period_id={pid}").json()["records"]
        self.assertEqual(len(recs), 1)
        rec = recs[0]

        has_tag = "Tiền chất" in rec["legal_classification"] or "NĐ 26" in rec["legal_classification"]

        # Isolation test: Query /records with search term "Tiền chất" or "NĐ 26"
        res_filter = self.client.get(f"/api/monthly-inventory/records?period_id={pid}&q=Tiền chất").json()
        isolated_count = res_filter.get("total", 0)

        passed = has_tag and isolated_count >= 1
        EmpiricalHarnessResults.record(
            "STRESS-09-PRECURSOR-INHERIT-ISOLATE",
            "Decree 26 Precursors",
            "CIL composition precursor inheritance (Toluene in Xylene) and search isolation",
            passed,
            f"legal_classification='{rec['legal_classification']}', isolated_count={isolated_count}",
            "HIGH" if not passed else "INFO"
        )
        self.assertTrue(has_tag)
        self.assertGreaterEqual(isolated_count, 1)

    def test_10_pure_precursor_not_in_preseeded_cil_table(self):
        """
        Case 3.3: Pure industrial precursor solvent (e.g. pure Acetone 67-64-1 or pure MEK 78-93-3)
        not pre-seeded in ZhanChen CIL table:
        What happens if a transaction is recorded for this chemical? Does it become an orphan transaction?
        """
        p = self.client.post("/api/monthly-inventory/periods", json={"month": 9, "year": 2030, "copy_from_previous": False}).json()
        pid = p["id"]

        # Attempt to create transaction for a pure precursor not in CIL table
        r_txn = self.client.post("/api/monthly-inventory/transactions", json={
            "period_id": pid,
            "chemical_id": "PRECURSOR_ACETONE_PURE",
            "transaction_type": "IMPORT",
            "quantity": 250.0,
            "transaction_date": "2030-09-10",
            "purpose": "Nhập dung môi axeton tẩy rửa",
        })

        # Check if transaction succeeded
        txn_created = r_txn.status_code == 200
        txn_data = r_txn.json() if txn_created else {}

        # Check if it was added to monthly_inventory_records
        recs = self.client.get(f"/api/monthly-inventory/records?period_id={pid}").json().get("records", [])
        found_in_records = any(r["chemical_id"] == "PRECURSOR_ACETONE_PURE" for r in recs)

        evidence = (
            f"Transaction status={r_txn.status_code}, record_id in txn={txn_data.get('record_id')}; "
            f"found_in_records={found_in_records}, total_records={len(recs)}"
        )

        # If transaction was accepted, but chemical was NOT created in monthly records,
        # it is an orphan transaction that causes silent data discrepancy!
        is_consistent = (not txn_created) or (found_in_records)
        EmpiricalHarnessResults.record(
            "STRESS-10-PRECURSOR-ORPHAN-TXN",
            "Decree 26 Precursors",
            "Recording transaction for chemical ID not in CIL: verify record consistency (no orphan transactions)",
            is_consistent,
            evidence,
            "CRITICAL" if not is_consistent else "INFO"
        )

    # =========================================================================
    # AREA 4: EDGE CONDITIONS & MALFORMED INPUTS
    # =========================================================================

    def test_11_zero_stock_handling(self):
        """Case 4.1: Chemical with opening=0, import=0, export=0 -> closing=0, warning_status=normal."""
        p = self.client.post("/api/monthly-inventory/periods", json={"month": 10, "year": 2030, "copy_from_previous": False}).json()
        pid = p["id"]

        self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={"chemical_ids": ["ZW55019"]})
        rec = self.client.get(f"/api/monthly-inventory/records?period_id={pid}").json()["records"][0]

        r_up = self.client.put(f"/api/monthly-inventory/records/{rec['id']}", json={
            "opening_stock": 0.0,
            "import_qty": 0.0,
            "export_qty": 0.0,
            "safety_threshold": 5000.0,
        })
        self.assertEqual(r_up.status_code, 200)
        data = r_up.json()

        is_zero_normal = data["closing_stock"] == 0.0 and data["warning_status"] == "normal"
        EmpiricalHarnessResults.record(
            "STRESS-11-ZERO-STOCK",
            "Edge Conditions",
            "Zero stock (0 + 0 - 0 = 0) maintains normal status without warnings",
            is_zero_normal,
            f"closing={data['closing_stock']}, warning_status='{data['warning_status']}'",
            "INFO"
        )
        self.assertTrue(is_zero_normal)

    def test_12_duplicate_chemical_addition_prevention(self):
        """Case 4.2: Add same chemical twice to same period -> must not duplicate records."""
        p = self.client.post("/api/monthly-inventory/periods", json={"month": 11, "year": 2030, "copy_from_previous": False}).json()
        pid = p["id"]

        r1 = self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={"chemical_ids": ["ZNZX009"]})
        self.assertEqual(r1.status_code, 200)
        added_1 = r1.json()["added_count"]

        # Call again with same chemical
        r2 = self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={"chemical_ids": ["ZNZX009"]})
        self.assertEqual(r2.status_code, 200)
        added_2 = r2.json()["added_count"]

        recs = self.client.get(f"/api/monthly-inventory/records?period_id={pid}").json()["records"]
        znzx_count = sum(1 for r in recs if r["chemical_id"] == "ZNZX009")

        is_prevented = (added_1 == 1) and (added_2 == 0) and (znzx_count == 1)
        EmpiricalHarnessResults.record(
            "STRESS-12-DUPLICATE-PREVENTION",
            "Edge Conditions",
            "Duplicate chemical addition prevention: second addition adds 0 and leaves exactly 1 record",
            is_prevented,
            f"first_add={added_1}, second_add={added_2}, total_matching_records={znzx_count}",
            "HIGH" if not is_prevented else "INFO"
        )
        self.assertTrue(is_prevented)

    def test_13_non_existent_chemical_ids_in_batch_add(self):
        """Case 4.3: Non-existent chemical IDs in batch add -> handled gracefully (return added_count = 0)."""
        p = self.client.post("/api/monthly-inventory/periods", json={"month": 12, "year": 2030, "copy_from_previous": False}).json()
        pid = p["id"]

        r_add = self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={
            "chemical_ids": ["NON_EXISTENT_CHEM_99999", "INVALID_XYZ_FOOBAR"]
        })
        self.assertEqual(r_add.status_code, 200)
        data = r_add.json()
        added = data.get("added_count", -1)

        is_graceful = added == 0
        EmpiricalHarnessResults.record(
            "STRESS-13-NONEXISTENT-CHEM",
            "Edge Conditions",
            "Batch add with non-existent chemical IDs handles gracefully without crash (added_count = 0)",
            is_graceful,
            f"status={r_add.status_code}, added_count={added}",
            "MEDIUM" if not is_graceful else "INFO"
        )
        self.assertEqual(added, 0)

    def test_14_empty_period_robustness(self):
        """Case 4.4: Empty period handling across all lifecycle endpoints (KPI, alerts, Excel, HTML print)."""
        p = self.client.post("/api/monthly-inventory/periods", json={"month": 1, "year": 2031, "copy_from_previous": False}).json()
        pid = p["id"]

        # 1. List records on empty period
        r_recs = self.client.get(f"/api/monthly-inventory/records?period_id={pid}")
        recs_ok = r_recs.status_code == 200 and len(r_recs.json()["records"]) == 0

        # 2. KPI on empty period
        r_kpi = self.client.get(f"/api/monthly-inventory/summary?period_id={pid}")
        kpi_ok = r_kpi.status_code == 200 and r_kpi.json()["total_chemicals"] == 0

        # 3. Alerts on empty period
        r_alerts = self.client.get(f"/api/monthly-inventory/periods/{pid}/safety-alerts")
        alerts_ok = r_alerts.status_code == 200 and r_alerts.json()["total_alerts"] == 0

        # 4. Excel export on empty period
        r_excel = self.client.get(f"/api/monthly-inventory/export-excel?period_id={pid}&month=1&year=2031")
        excel_ok = r_excel.status_code == 200 and len(r_excel.content) > 1000

        # 5. HTML print on empty period
        r_html = self.client.get(f"/api/monthly-inventory/print-html?period_id={pid}&month=1&year=2031")
        html_ok = r_html.status_code == 200 and "BÁO CÁO TÌNH HÌNH NHẬP - XUẤT - TỒN" in r_html.text

        all_ok = recs_ok and kpi_ok and alerts_ok and excel_ok and html_ok
        EmpiricalHarnessResults.record(
            "STRESS-14-EMPTY-PERIOD",
            "Edge Conditions",
            "Empty period stability across records, KPI, alerts, Excel export, and HTML print preview",
            all_ok,
            f"recs_ok={recs_ok}, kpi_ok={kpi_ok}, alerts_ok={alerts_ok}, excel_ok={excel_ok}, html_ok={html_ok}",
            "HIGH" if not all_ok else "INFO"
        )
        self.assertTrue(all_ok)

    def test_15_malformed_period_date_validation(self):
        """Case 4.5: Malformed month / year values when creating period (e.g. month=13, year=1800)."""
        r_m13 = self.client.post("/api/monthly-inventory/periods", json={"month": 13, "year": 2026})
        r_m0 = self.client.post("/api/monthly-inventory/periods", json={"month": 0, "year": 2026})
        r_y1800 = self.client.post("/api/monthly-inventory/periods", json={"month": 6, "year": 1800})
        r_y3000 = self.client.post("/api/monthly-inventory/periods", json={"month": 6, "year": 3000})

        rejected_all = all(r.status_code in (400, 422) for r in (r_m13, r_m0, r_y1800, r_y3000))
        evidence = f"m=13: {r_m13.status_code}, m=0: {r_m0.status_code}, y=1800: {r_y1800.status_code}, y=3000: {r_y3000.status_code}"

        EmpiricalHarnessResults.record(
            "STRESS-15-MALFORMED-PERIOD",
            "Edge Conditions",
            "Rejection of invalid month (0, 13) and out-of-range year (<2000, >2100)",
            rejected_all,
            evidence,
            "HIGH" if not rejected_all else "INFO"
        )
        self.assertTrue(rejected_all)

    def test_16_high_decimal_precision_rounding(self):
        """Case 4.6: High decimal precision quantities: opening=10.12345, import=0.00004, export=2.12340 -> closing=8.0001."""
        p = self.client.post("/api/monthly-inventory/periods", json={"month": 2, "year": 2031, "copy_from_previous": False}).json()
        pid = p["id"]

        self.client.post(f"/api/monthly-inventory/periods/{pid}/add-from-cil", json={"chemical_ids": ["000000000000102992"]})
        rec = self.client.get(f"/api/monthly-inventory/records?period_id={pid}").json()["records"][0]

        r_up = self.client.put(f"/api/monthly-inventory/records/{rec['id']}", json={
            "opening_stock": 10.12345,
            "import_qty": 0.00004,
            "export_qty": 2.12340,
        })
        self.assertEqual(r_up.status_code, 200)
        data = r_up.json()

        # Expected: 10.12345 + 0.00004 - 2.12340 = 8.00009 -> rounded to 4 decimals = 8.0001
        expected = round(10.12345 + 0.00004 - 2.12340, 4)
        passed = abs(data["closing_stock"] - expected) < 1e-6

        EmpiricalHarnessResults.record(
            "STRESS-16-DECIMAL-PRECISION",
            "Boundary Values",
            "High decimal precision arithmetic and 4-decimal rounding integrity",
            passed,
            f"closing={data['closing_stock']}, expected={expected}",
            "MEDIUM" if not passed else "INFO"
        )
        self.assertTrue(passed)


def run_stress_suite() -> Dict[str, Any]:
    print("=" * 80)
    print("TITAN MONTHLY CHEMICAL INVENTORY (NXT) EMPIRICAL STRESS TEST HARNESS")
    print("=" * 80)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestStressStatutoryAndPrecursors)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total - failures - errors

    print("\n" + "=" * 80)
    print(f"STRESS TEST SUMMARY: {passed}/{total} Passed, {failures} Failures, {errors} Errors")
    print("=" * 80)

    # Print empirical findings matrix
    print("\nEMPIRICAL FINDINGS MATRIX:")
    print(f"{'ID':<28} | {'Area':<22} | {'Status':<6} | {'Severity':<8} | Evidence")
    print("-" * 100)
    for res in EmpiricalHarnessResults.results:
        status_str = "PASS" if res["passed"] else "FAIL"
        print(f"{res['test_id']:<28} | {res['area']:<22} | {status_str:<6} | {res['severity']:<8} | {res['evidence']}")

    return {
        "total": total,
        "passed": passed,
        "failures": failures,
        "errors": errors,
        "details": EmpiricalHarnessResults.results,
    }


if __name__ == "__main__":
    run_stress_suite()
