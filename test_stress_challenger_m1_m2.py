"""
test_stress_challenger_m1_m2.py
────────────────────────────────
Adversarial Stress Test Harness by Empirical Challenger.
Stress tests:
1. Multi-transaction concurrency and race conditions (50 parallel transactions)
2. Mathematical balance equations across 1,000 randomized operations
3. 13-month multi-year roll-forward continuity (including 2026-12 -> 2027-01)
4. Extreme boundary conditions, database locking, and transaction ID collision

Outputs detailed evidence to stdout and structured metrics.
"""

from __future__ import annotations

import concurrent.futures
import math
import random
import sys
import time
import unittest
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from fastapi.testclient import TestClient
from server import app
from core.monthly_inventory_engine import MonthlyInventoryEngine


class StressTestResults:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.findings: List[Dict[str, Any]] = []

    def record_finding(self, severity: str, title: str, details: str, evidence: Any):
        self.findings.append({
            "severity": severity,
            "title": title,
            "details": details,
            "evidence": evidence,
        })


RESULTS = StressTestResults()


class TestChallengerStressSuite(unittest.TestCase):
    def setUp(self):
        MonthlyInventoryEngine.init_db()
        self.client = TestClient(app)
        # Clear inventory tables before EACH test to guarantee complete test isolation
        with MonthlyInventoryEngine.get_connection() as conn:
            conn.execute("DELETE FROM inventory_transactions;")
            conn.execute("DELETE FROM monthly_inventory_records;")
            conn.execute("DELETE FROM monthly_periods;")
            conn.commit()

    def tearDown(self):
        pass

    # =========================================================================
    # CHALLENGE 1: MULTI-TRANSACTION CONCURRENCY & RACE CONDITIONS
    # =========================================================================

    def test_01_concurrency_50_parallel_engine_transactions(self):
        """
        Adversarial Test 1A: Fire 50 concurrent create_transaction calls directly
        against MonthlyInventoryEngine using ThreadPoolExecutor(max_workers=50).
        Evaluates:
        - Transaction ID uniqueness collisions (due to millisecond timestamp slicing)
        - SQLite database lock contention (OperationalError: database is locked)
        - Aggregate sum consistency: sum(transactions) == records.import/export_qty
        - Lost updates in summary recalculation
        """
        RESULTS.tests_run += 1
        p_dict = MonthlyInventoryEngine.create_period(month=5, year=2026, copy_from_previous=False)
        pid = p_dict["id"]
        chem_id = "000000000000102992"  # Xylene

        # Setup chemical record with initial opening stock = 5000.0
        MonthlyInventoryEngine.add_chemicals_from_cil(pid, [chem_id])
        recs = MonthlyInventoryEngine.list_records(pid)
        rec = next(r for r in recs if r["chemical_id"] == chem_id)
        MonthlyInventoryEngine.update_record(rec["id"], {"opening_stock": 5000.0})

        num_txns = 50
        # 25 imports of 10.25 kg, 25 exports of 4.75 kg
        txns_to_run = []
        for i in range(num_txns):
            ttype = "IMPORT" if i % 2 == 0 else "EXPORT"
            qty = 10.25 if ttype == "IMPORT" else 4.75
            txns_to_run.append({
                "idx": i,
                "period_ident": pid,
                "chemical_id": chem_id,
                "transaction_type": ttype,
                "quantity": qty,
                "transaction_date": "2026-05-15",
                "reference_doc": f"DOC-CONC-{i:03d}",
                "department": f"Dept-{i%5}",
                "purpose": f"Concurrency Test {i}",
            })

        expected_total_import = 25 * 10.25  # 256.25
        expected_total_export = 25 * 4.75   # 118.75
        expected_closing = round(5000.0 + expected_total_import - expected_total_export, 4)  # 5137.5

        successes = 0
        failures = []

        def worker(txn_args):
            try:
                res = MonthlyInventoryEngine.create_transaction(
                    period_ident=txn_args["period_ident"],
                    chemical_id=txn_args["chemical_id"],
                    transaction_type=txn_args["transaction_type"],
                    quantity=txn_args["quantity"],
                    transaction_date=txn_args["transaction_date"],
                    reference_doc=txn_args["reference_doc"],
                    department=txn_args["department"],
                    purpose=txn_args["purpose"],
                )
                return True, res
            except Exception as e:
                return False, str(e)

        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            future_results = list(executor.map(worker, txns_to_run))
        duration = time.time() - start_time

        for success, res in future_results:
            if success:
                successes += 1
            else:
                failures.append(res)

        # Check database final state
        with MonthlyInventoryEngine.get_connection() as conn:
            tx_rows = conn.execute(
                "SELECT COUNT(*), SUM(CASE WHEN UPPER(transaction_type)='IMPORT' THEN quantity ELSE 0 END) as imp, "
                "SUM(CASE WHEN UPPER(transaction_type)='EXPORT' THEN quantity ELSE 0 END) as exp "
                "FROM inventory_transactions WHERE period_id = ? AND chemical_id = ?",
                (pid, chem_id)
            ).fetchone()
            actual_tx_count = tx_rows[0]
            actual_tx_imp = float(tx_rows[1] or 0.0)
            actual_tx_exp = float(tx_rows[2] or 0.0)

        updated_rec = MonthlyInventoryEngine.get_record(rec["id"])
        ledger_imp = float(updated_rec["import_qty"] or 0.0)
        ledger_exp = float(updated_rec["export_qty"] or 0.0)
        ledger_closing = float(updated_rec["closing_stock"] or 0.0)

        print(f"\n--- Concurrency Test 1A (50 parallel engine calls) ---")
        print(f"Duration: {duration:.3f}s | Successes: {successes}/50 | Failures: {len(failures)}")
        print(f"Transactions in DB: {actual_tx_count}/50 | DB Import Sum: {actual_tx_imp} | DB Export Sum: {actual_tx_exp}")
        print(f"Ledger Record: Import={ledger_imp} (exp: {expected_total_import}), Export={ledger_exp} (exp: {expected_total_export}), Closing={ledger_closing} (exp: {expected_closing})")

        if failures:
            print(f"Failure samples: {failures[:5]}")
            RESULTS.record_finding(
                severity="HIGH",
                title="Parallel Transaction Concurrency Failure",
                details=f"{len(failures)}/50 parallel create_transaction calls failed under concurrency.",
                evidence={"duration": duration, "failures": failures[:10]}
            )

        if ledger_imp != actual_tx_imp or ledger_exp != actual_tx_exp or ledger_closing != expected_closing:
            RESULTS.record_finding(
                severity="CRITICAL",
                title="Lost Update / Inconsistent Summary Ledger under Concurrency",
                details="Race condition in summary recalculation: ledger record import/export does not match transaction table sums.",
                evidence={
                    "actual_tx_imp": actual_tx_imp,
                    "ledger_imp": ledger_imp,
                    "actual_tx_exp": actual_tx_exp,
                    "ledger_exp": ledger_exp,
                    "actual_closing": ledger_closing,
                    "expected_closing": expected_closing,
                }
            )

        # Assertions
        self.assertEqual(len(failures), 0, f"Expected 0 failures in 50 concurrent transactions, got {len(failures)}: {failures[:3]}")
        self.assertEqual(actual_tx_count, 50, f"Expected 50 transactions inserted, got {actual_tx_count}")
        self.assertAlmostEqual(actual_tx_imp, expected_total_import, places=4)
        self.assertAlmostEqual(actual_tx_exp, expected_total_export, places=4)
        self.assertAlmostEqual(ledger_imp, expected_total_import, places=4, msg="Ledger import sum lost update detected!")
        self.assertAlmostEqual(ledger_exp, expected_total_export, places=4, msg="Ledger export sum lost update detected!")
        self.assertAlmostEqual(ledger_closing, expected_closing, places=4, msg="Ledger closing stock inconsistent!")
        RESULTS.tests_passed += 1

    def test_02_concurrency_50_parallel_api_requests(self):
        """
        Adversarial Test 1B: Fire 50 concurrent POST /api/monthly-inventory/transactions
        via TestClient across 25 worker threads.
        """
        RESULTS.tests_run += 1
        p_dict = MonthlyInventoryEngine.create_period(month=4, year=2026, copy_from_previous=False)
        pid = p_dict["id"]
        chem_id = "A1570"

        MonthlyInventoryEngine.add_chemicals_from_cil(pid, [chem_id])
        recs = MonthlyInventoryEngine.list_records(pid)
        rec = next(r for r in recs if r["chemical_id"] == chem_id)
        MonthlyInventoryEngine.update_record(rec["id"], {"opening_stock": 2000.0})

        num_txns = 50
        expected_import = 25 * 5.5
        expected_export = 25 * 2.2
        expected_closing = round(2000.0 + expected_import - expected_export, 4)

        def api_worker(i):
            ttype = "IMPORT" if i % 2 == 0 else "EXPORT"
            qty = 5.5 if ttype == "IMPORT" else 2.2
            resp = self.client.post("/api/monthly-inventory/transactions", json={
                "period_id": pid,
                "chemical_id": chem_id,
                "transaction_type": ttype,
                "quantity": qty,
                "transaction_date": "2026-04-10",
                "reference_doc": f"API-TXN-{i:03d}",
                "department": "Production",
                "purpose": "Adversarial Test",
            })
            return resp.status_code, resp.text

        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            api_results = list(executor.map(api_worker, range(num_txns)))
        duration = time.time() - start_time

        status_counts = {}
        error_msgs = []
        for status_code, body in api_results:
            status_counts[status_code] = status_counts.get(status_code, 0) + 1
            if status_code != 200:
                error_msgs.append((status_code, body))

        rec_after = MonthlyInventoryEngine.get_record(rec["id"])
        print(f"\n--- Concurrency Test 1B (50 parallel API calls) ---")
        print(f"Duration: {duration:.3f}s | Status counts: {status_counts}")
        print(f"Final Ledger: Import={rec_after['import_qty']}, Export={rec_after['export_qty']}, Closing={rec_after['closing_stock']} (exp: {expected_closing})")

        if error_msgs:
            RESULTS.record_finding(
                severity="HIGH",
                title="Parallel API Transactions Contention",
                details=f"{len(error_msgs)} API calls failed with non-200 code.",
                evidence={"status_counts": status_counts, "sample_errors": error_msgs[:5]}
            )

        self.assertEqual(status_counts.get(200, 0), 50, f"Expected 50 200 OK responses, got {status_counts}")
        self.assertAlmostEqual(rec_after["import_qty"], expected_import, places=4)
        self.assertAlmostEqual(rec_after["export_qty"], expected_export, places=4)
        self.assertAlmostEqual(rec_after["closing_stock"], expected_closing, places=4)
        RESULTS.tests_passed += 1

    # =========================================================================
    # CHALLENGE 2: MATHEMATICAL BALANCE EQUATION (1,000 RANDOMIZED OPERATIONS)
    # =========================================================================

    def test_03_balance_equation_1000_randomized_operations(self):
        """
        Adversarial Test 2A: Verify the invariant:
        closing_stock == round(opening_stock + import_qty - export_qty, 4)
        across 1,000 randomized operations with extreme floats, decimals, zeros,
        tiny fractions (0.0001), huge stocks (1,000,000), and negative stocks.
        """
        RESULTS.tests_run += 1
        p_dict = MonthlyInventoryEngine.create_period(month=3, year=2026, copy_from_previous=False)
        pid = p_dict["id"]
        chem_id = "000000000000102992"
        MonthlyInventoryEngine.add_chemicals_from_cil(pid, [chem_id])
        recs = MonthlyInventoryEngine.list_records(pid)
        rec_id = recs[0]["id"]

        random.seed(42)  # Deterministic repeatability
        violations = []
        max_delta = 0.0

        for i in range(1000):
            # Generate varying orders of magnitude and precision
            case_type = i % 5
            if case_type == 0:
                # Standard factory quantities
                opening = round(random.uniform(0.0, 10000.0), random.randint(1, 4))
                imp = round(random.uniform(0.0, 5000.0), random.randint(1, 4))
                exp = round(random.uniform(0.0, 5000.0), random.randint(1, 4))
            elif case_type == 1:
                # Extreme small fractional amounts (precision stress)
                opening = round(random.uniform(0.0001, 1.0), 6)
                imp = round(random.uniform(0.0001, 0.5), 6)
                exp = round(random.uniform(0.0001, 0.5), 6)
            elif case_type == 2:
                # Boundary zeros
                opening = 0.0 if i % 2 == 0 else round(random.uniform(0.0, 500.0), 2)
                imp = 0.0 if i % 3 == 0 else round(random.uniform(0.0, 500.0), 2)
                exp = 0.0 if i % 4 == 0 else round(random.uniform(0.0, 500.0), 2)
            elif case_type == 3:
                # Negative stock stress (export > opening + imp)
                opening = round(random.uniform(10.0, 100.0), 2)
                imp = round(random.uniform(10.0, 50.0), 2)
                exp = round(opening + imp + random.uniform(1.0, 200.0), 2)
            else:
                # Massive stock scale (100k - 1M kg)
                opening = round(random.uniform(100000.0, 1000000.0), 3)
                imp = round(random.uniform(10000.0, 50000.0), 3)
                exp = round(random.uniform(10000.0, 50000.0), 3)

            # Oracle calculation
            oracle_closing = round(opening + imp - exp, 4)

            # Execution
            updated = MonthlyInventoryEngine.update_record(rec_id, {
                "opening_stock": opening,
                "import_qty": imp,
                "export_qty": exp,
            })

            actual_closing = updated["closing_stock"]
            actual_ending = updated["ending_stock"]
            delta = abs(actual_closing - oracle_closing)
            if delta > max_delta:
                max_delta = delta

            # Validate invariant
            if delta > 1e-4:
                violations.append({
                    "iteration": i,
                    "opening": opening,
                    "import": imp,
                    "export": exp,
                    "oracle": oracle_closing,
                    "actual": actual_closing,
                    "delta": delta,
                })

            # Check warning status invariant
            if oracle_closing < 0:
                if updated["warning_status"] != "negative_stock":
                    violations.append({
                        "iteration": i,
                        "type": "warning_status_mismatch",
                        "expected": "negative_stock",
                        "actual": updated["warning_status"],
                        "closing": actual_closing,
                    })

        print(f"\n--- Balance Equation Test 2A (1,000 randomized operations) ---")
        print(f"Total operations: 1,000 | Violations: {len(violations)} | Max Delta: {max_delta:.8f}")

        if violations:
            RESULTS.record_finding(
                severity="HIGH",
                title="Mathematical Invariant Violation in update_record",
                details=f"{len(violations)} out of 1,000 randomized balance calculations deviated from oracle.",
                evidence={"violations_count": len(violations), "samples": violations[:5]}
            )

        self.assertEqual(len(violations), 0, f"Found {len(violations)} invariant violations in 1,000 operations")
        self.assertLessEqual(max_delta, 1e-4)
        RESULTS.tests_passed += 1

    def test_04_chained_1000_sequential_transactions_drift_check(self):
        """
        Adversarial Test 2B: 1,000 sequential transactions on a single chemical.
        Verifies whether iterative aggregation accumulates floating-point drift:
        Final closing == Initial opening + sum(1,000 imports) - sum(1,000 exports).
        """
        RESULTS.tests_run += 1
        p_dict = MonthlyInventoryEngine.create_period(month=2, year=2026, copy_from_previous=False)
        pid = p_dict["id"]
        chem_id = "000000000000107344"  # Solvesso 100

        MonthlyInventoryEngine.add_chemicals_from_cil(pid, [chem_id])
        recs = MonthlyInventoryEngine.list_records(pid)
        rec_id = recs[0]["id"]

        initial_stock = 50000.0
        MonthlyInventoryEngine.update_record(rec_id, {"opening_stock": initial_stock})

        random.seed(12345)
        sum_imp_dec = Decimal("0.0")
        sum_exp_dec = Decimal("0.0")

        # Fast sequential inserts
        for i in range(1000):
            ttype = "IMPORT" if i % 2 == 0 else "EXPORT"
            # Random decimal quantity between 0.1234 and 50.9876
            qty_val = round(random.uniform(0.1234, 50.9876), 4)
            d_qty = Decimal(str(qty_val))
            if ttype == "IMPORT":
                sum_imp_dec += d_qty
            else:
                sum_exp_dec += d_qty

            MonthlyInventoryEngine.create_transaction(
                period_ident=pid,
                chemical_id=chem_id,
                transaction_type=ttype,
                quantity=qty_val,
                transaction_date="2026-02-15",
                reference_doc=f"SEQ-{i:04d}",
            )

        expected_import = float(sum_imp_dec)
        expected_export = float(sum_exp_dec)
        expected_closing = round(float(Decimal(str(initial_stock)) + sum_imp_dec - sum_exp_dec), 4)

        updated_rec = MonthlyInventoryEngine.get_record(rec_id)
        actual_import = float(updated_rec["import_qty"] or 0.0)
        actual_export = float(updated_rec["export_qty"] or 0.0)
        actual_closing = float(updated_rec["closing_stock"] or 0.0)

        import_drift = abs(actual_import - expected_import)
        export_drift = abs(actual_export - expected_export)
        closing_drift = abs(actual_closing - expected_closing)

        print(f"\n--- Chained 1,000 Transactions Test 2B ---")
        print(f"Total transactions: 1,000")
        print(f"Import: Actual={actual_import:.4f}, Expected={expected_import:.4f}, Drift={import_drift:.6f}")
        print(f"Export: Actual={actual_export:.4f}, Expected={expected_export:.4f}, Drift={export_drift:.6f}")
        print(f"Closing: Actual={actual_closing:.4f}, Expected={expected_closing:.4f}, Drift={closing_drift:.6f}")

        # Check drift
        self.assertLessEqual(import_drift, 0.01, f"Import drift too large: {import_drift}")
        self.assertLessEqual(export_drift, 0.01, f"Export drift too large: {export_drift}")
        self.assertLessEqual(closing_drift, 0.01, f"Closing stock drift too large: {closing_drift}")
        RESULTS.tests_passed += 1

    # =========================================================================
    # CHALLENGE 3: MULTI-MONTH ROLL-FORWARD CONTINUITY (13 CONSECUTIVE MONTHS)
    # =========================================================================

    def test_05_13_month_roll_forward_chain_and_year_rollover(self):
        """
        Adversarial Test 3: Continuous 13-month chain from 2026-01 through 2027-01.
        Tests:
        1. Year rollover boundary: 2026-12 -> 2027-01
        2. Exact balance continuity: opening_stock(M) == closing_stock(M-1) for all M
        3. Global mass conservation across the entire year:
           closing(M13) == opening(M1) + sum(imports 1..13) - sum(exports 1..13)
        4. Multi-chemical consistency across 5 distinct chemicals
        """
        RESULTS.tests_run += 1
        chem_ids = [
            "ZNZX009",
            "000000000000102992",
            "A1570",
            "A1615",
            "ZW55019",
        ]

        # 13 consecutive months: (year, month)
        timeline = []
        for m in range(1, 13):
            timeline.append((2026, m))
        timeline.append((2027, 1))  # 13th month: Year boundary crossing!

        # Initial opening stocks in 2026-01
        initial_stocks = {
            "ZNZX009": 1500.0,
            "000000000000102992": 12000.0,
            "A1570": 450.0,
            "A1615": 800.0,
            "ZW55019": 3500.0,
        }

        # Track cumulative flows per chemical
        cumulative_imports = {cid: 0.0 for cid in chem_ids}
        cumulative_exports = {cid: 0.0 for cid in chem_ids}

        previous_month_closings = {}
        continuity_checks_count = 0
        continuity_failures = []

        random.seed(999)

        for step, (yr, mo) in enumerate(timeline):
            # Create period with auto_roll_forward=True
            p_dict = MonthlyInventoryEngine.create_period(
                month=mo,
                year=yr,
                title=f"Kỳ {mo:02d}/{yr}",
                copy_from_previous=True,
                auto_roll_forward=True,
            )
            pid = p_dict["id"]
            pkey = p_dict["period_key"]

            if step == 0:
                # First month (2026-01): seed chemicals and initial opening stocks
                MonthlyInventoryEngine.add_chemicals_from_cil(pid, chem_ids)
                recs = MonthlyInventoryEngine.list_records(pid)
                for r in recs:
                    cid = r["chemical_id"]
                    if cid in initial_stocks:
                        MonthlyInventoryEngine.update_record(r["id"], {"opening_stock": initial_stocks[cid]})
            else:
                # Month M (M >= 2): Verify continuity with Month M-1
                recs = MonthlyInventoryEngine.list_records(pid)
                rec_map = {r["chemical_id"]: r for r in recs}

                for cid in chem_ids:
                    continuity_checks_count += 1
                    exp_opening = previous_month_closings.get(cid)
                    act_record = rec_map.get(cid)

                    if not act_record:
                        continuity_failures.append({
                            "period": pkey,
                            "chemical": cid,
                            "error": "Chemical missing after roll-forward",
                        })
                        continue

                    act_opening = act_record["opening_stock"]
                    if abs(act_opening - exp_opening) > 1e-4:
                        continuity_failures.append({
                            "period": pkey,
                            "chemical": cid,
                            "expected_opening": exp_opening,
                            "actual_opening": act_opening,
                            "delta": abs(act_opening - exp_opening),
                        })

            # In this month, simulate transactions for each chemical
            recs_now = MonthlyInventoryEngine.list_records(pid)
            for r in recs_now:
                cid = r["chemical_id"]
                if cid not in chem_ids:
                    continue

                # Generate random monthly import and export
                mo_imp = round(random.uniform(50.0, 500.0), 2)
                mo_exp = round(random.uniform(40.0, 450.0), 2)

                # Post transactions
                MonthlyInventoryEngine.create_transaction(
                    period_ident=pid,
                    chemical_id=cid,
                    transaction_type="IMPORT",
                    quantity=mo_imp,
                    transaction_date=f"{yr:04d}-{mo:02d}-05",
                )
                MonthlyInventoryEngine.create_transaction(
                    period_ident=pid,
                    chemical_id=cid,
                    transaction_type="EXPORT",
                    quantity=mo_exp,
                    transaction_date=f"{yr:04d}-{mo:02d}-20",
                )

                cumulative_imports[cid] += mo_imp
                cumulative_exports[cid] += mo_exp

            # Save closing stocks of this month for next month's roll-forward verification
            recs_after = MonthlyInventoryEngine.list_records(pid)
            for r in recs_after:
                cid = r["chemical_id"]
                if cid in chem_ids:
                    previous_month_closings[cid] = r["closing_stock"]

        print(f"\n--- 13-Month Roll-Forward Chain Test 3 ---")
        print(f"Timeline: 2026-01 -> 2027-01 ({len(timeline)} months)")
        print(f"Total continuity checks: {continuity_checks_count} | Failures: {len(continuity_failures)}")

        if continuity_failures:
            RESULTS.record_finding(
                severity="CRITICAL",
                title="Roll-Forward Chain Discontinuity",
                details=f"Roll-forward failed to maintain opening_stock(M) == closing_stock(M-1) across months.",
                evidence={"failures": continuity_failures[:5]}
            )

        self.assertEqual(len(continuity_failures), 0, f"Found {len(continuity_failures)} roll-forward continuity breaks: {continuity_failures[:3]}")

        # Final Verification: Global Conservation of Mass in Month 13 (2027-01)
        p13 = MonthlyInventoryEngine.get_period("2027-01")
        p13_recs = {r["chemical_id"]: r for r in p13["records"]}

        conservation_failures = []
        for cid in chem_ids:
            expected_final_closing = round(initial_stocks[cid] + cumulative_imports[cid] - cumulative_exports[cid], 4)
            actual_final_closing = p13_recs[cid]["closing_stock"]
            delta = abs(actual_final_closing - expected_final_closing)
            print(f"Chemical {cid:18s} | Initial: {initial_stocks[cid]:8.1f} | +Imp: {cumulative_imports[cid]:8.1f} | -Exp: {cumulative_exports[cid]:8.1f} | Final Closing: {actual_final_closing:8.2f} (exp: {expected_final_closing:8.2f}) | Delta: {delta:.4f}")

            if delta > 0.05:
                conservation_failures.append({
                    "chemical": cid,
                    "initial": initial_stocks[cid],
                    "total_imports": cumulative_imports[cid],
                    "total_exports": cumulative_exports[cid],
                    "actual_final_closing": actual_final_closing,
                    "expected_final_closing": expected_final_closing,
                    "delta": delta,
                })

        self.assertEqual(len(conservation_failures), 0, f"Mass conservation failed in 13-month chain: {conservation_failures}")
        RESULTS.tests_passed += 1

    # =========================================================================
    # CHALLENGE 4: TRANSACTION IDENTIFIER COLLISION UNDER RAPID BATCH
    # =========================================================================

    def test_06_rapid_transaction_id_collision_stress(self):
        """
        Adversarial Test 4: Rapid generation of 100 transactions in tight loop (<10ms).
        Tests whether the transaction_id format:
        `f"TXN-{pkey.replace('-', '')}-{ts_str[-6:]}"`
        collides due to millisecond slicing.
        """
        RESULTS.tests_run += 1
        p_dict = MonthlyInventoryEngine.create_period(month=11, year=2026, copy_from_previous=False)
        pid = p_dict["id"]
        chem_id = "ZW55019"
        MonthlyInventoryEngine.add_chemicals_from_cil(pid, [chem_id])

        rapid_count = 100
        generated_ids = []
        collisions = 0
        exceptions = []

        for i in range(rapid_count):
            try:
                txn = MonthlyInventoryEngine.create_transaction(
                    period_ident=pid,
                    chemical_id=chem_id,
                    transaction_type="IMPORT",
                    quantity=1.0,
                    transaction_date="2026-11-10",
                    reference_doc=f"RAPID-{i}",
                )
                tid = txn["transaction_id"]
                if tid in generated_ids:
                    collisions += 1
                generated_ids.append(tid)
            except Exception as e:
                exceptions.append((i, str(e)))

        print(f"\n--- Rapid Transaction ID Collision Test 4 ---")
        print(f"Attempts: {rapid_count} | Collisions: {collisions} | Exceptions: {len(exceptions)}")
        if exceptions:
            print(f"Sample exceptions: {exceptions[:3]}")
            RESULTS.record_finding(
                severity="CRITICAL",
                title="Transaction ID Collision under Rapid Execution",
                details=f"Rapid insertion caused {len(exceptions)} crashes due to non-unique transaction_id generation.",
                evidence={"collisions": collisions, "exceptions": exceptions[:5]}
            )

        self.assertEqual(len(exceptions), 0, f"Encountered {len(exceptions)} exceptions during rapid transactions: {exceptions[:2]}")
        self.assertEqual(collisions, 0, f"Found {collisions} duplicate transaction IDs generated")
        RESULTS.tests_passed += 1


if __name__ == "__main__":
    unittest.main()
