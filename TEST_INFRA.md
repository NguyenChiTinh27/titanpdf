# E2E Test Infra: TitanPDF Monthly Chemical Inventory & Usage Tracking (NXT)

## Test Philosophy
- Opaque-box, requirement-driven derived strictly from `ORIGINAL_REQUEST.md` (lines 773-851).
- Methodology: Category-Partition + Boundary Value Analysis (BVA) + Pairwise Combinations + Real-World Workloads.
- Zero-Regression Invariant: All 30 existing test cases in `test_msds_full_suite.py` must maintain 100% PASS rate.
- Absolute Ban on Repealed Decrees: Zero occurrences of NĐ 113/2017, NĐ 82/2022, TT 32/2017, TT 04/2012.

## Feature Inventory & Test Mapping
| # | Feature | Requirement | Tier 1 (Happy Path) | Tier 2 (Boundary/Edge) | Tier 3 (Cross-Feature) | Tier 4 (Workload/E2E) |
|---|---------|-------------|:-------------------:|:----------------------:|:----------------------:|:---------------------:|
| 1 | Tab Navigation & View | R1 | T1_01: Tab switch & load | T2_01: Theme switch & layout | T3_01: Nav + Filter state | T4_01: Full user workflow |
| 2 | Period Selection & Roll-Forward | R1, R2 | T1_02: Create period & pick | T2_02: Leap year / year wrap | T3_02: Multi-month roll-forward | T4_02: 12-month audit trail |
| 3 | KPI Real-time Cards | R1 | T1_03: KPI calculation | T2_03: Zero stock / large qty | T3_03: Trans + KPI sync | T4_03: Bulk transaction KPI |
| 4 | Searchable Data Grid | R1 | T1_04: Search & filter | T2_04: Unicode / special CAS | T3_04: Search + Quick Edit | T4_04: Production grid stress |
| 5 | Dual-Mode Data Entry | R2 | T1_05: Quick edit & Trans log | T2_05: Decimal precision | T3_05: Dual-mode balance sync | T4_05: Concurrent entry |
| 6 | Auto-Balance Formula | R2 | T1_06: Ending = In + Imp - Exp | T2_06: Floating point precision | T3_06: Trans delta balance | T4_06: Complex journal audit |
| 7 | CIL Chemical Linkage | R3 | T1_07: Select from CIL | T2_07: Missing GHS / Non-CAS | T3_07: CIL update sync | T4_07: All 13 CIL chemicals |
| 8 | 1-Click Batch Add | R3 | T1_08: Batch add 13 chems | T2_08: Duplicate prevention | T3_08: Batch add + Roll-forward | T4_08: Large batch import |
| 9 | Professional Excel (.xlsx) | R4 | T1_09: Export valid xlsx | T2_09: Long text / special char | T3_09: Formulas SUM / balance | T4_09: Openpyxl byte stream |
| 10 | Print Preview & A4 Layout | R4 | T1_10: Print HTML render | T2_10: Multi-page pagination | T3_10: Print CSS isolation | T4_10: High-density print |
| 11 | Safety Thresholds (NĐ 24 IV) | R5 | T1_11: Exceed threshold alert | T2_11: Exact boundary threshold | T3_11: Multiple alerts filter | T4_11: Factory safety audit |
| 12 | Negative Balance Alert | R5 | T1_12: Negative stock warning | T2_12: Zero stock vs -0.001 | T3_12: Roll-forward neg warning | T4_12: Production sanity test |

## Test Architecture
- **Test Runner**: Python test runner invoking FastAPI `TestClient(app)` with both offline fallback and live HTTP capabilities.
- **Test Suite Location**: `test_monthly_inventory_suite.py` at project root.
- **Pass/Fail Semantics**: 100% assertions pass, zero pending, zero regression on existing 30 tests.
- **Temporary Resource Discipline**: Zero file leaks in `temp/` or `data/` after test execution.

## Coverage Thresholds
- Tier 1: 12 test cases covering all 12 core features (Happy path)
- Tier 2: 12 test cases covering boundary conditions, zero values, unicode, and extreme quantities
- Tier 3: 6 test cases covering cross-feature interactions (Roll-forward + CIL + Transactions + Excel)
- Tier 4: 5 realistic factory workload scenarios (full monthly closing cycle, 12-month chain, annual reconciliation)
- **Total: 35 comprehensive test cases**.
