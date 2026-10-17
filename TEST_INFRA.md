# TEST INFRASTRUCTURE & HARNESS MANUAL

**Project**: TitanPDF EHS Chemical Management System Overhaul  
**Primary Test Suite**: `test_msds_full_suite.py`  
**Location**: `c:\Users\ntc27\OneDrive\文件\TitanPDF\test_msds_full_suite.py`  
**Author**: `test_writer_test_track_1`  
**Milestone Scope**: R1–R6 (M1–M5, M_TEST, M_FINAL)  

---

## 1. Architectural Overview

`test_msds_full_suite.py` is an opaque-box End-to-End (E2E) testing harness engineered to validate all functional, boundary, regulatory, and performance requirements for the TitanPDF chemical management system overhaul without requiring manual intervention.

### Dual-Mode ApiClient Pattern
The suite utilizes a self-healing `ApiClient` pattern supporting dual execution contexts:
1. **Live HTTP Mode**: When a live Uvicorn server is running at `TITAN_TEST_URL` (default `http://127.0.0.1:8888`), requests are dispatched via standard HTTP calls using `requests`.
2. **Offline ASGI TestClient Fallback**: When no live server is listening, `ApiClient` automatically mounts FastAPI's in-memory `TestClient(app)` from `server.py`, ensuring 100% offline test execution without network dependency, socket errors, or port conflicts.

```
+--------------------------------------------------------------------+
|                      test_msds_full_suite.py                       |
|        (Tiers 1-4: Feature, Boundary, Combinations, SLA)          |
+---------------------------------+----------------------------------+
                                  |
                                  v
+--------------------------------------------------------------------+
|                             ApiClient                              |
|       - Automatic Liveness Probing (/api/health, /api/msds/*)      |
|       - Uniform Response Wrapper (status_code, json, content)      |
+---------------------------------+----------------------------------+
                |                                   |
                v (If Server Online)                v (If Server Offline)
+-------------------------------+   +--------------------------------+
|  Live HTTP Requests (requests)|   | FastAPI TestClient(server.app) |
|      http://127.0.0.1:8888    |   | Direct ASGI In-Memory Dispatch |
+-------------------------------+   +--------------------------------+
```

---

## 2. The 4 Quality Tiers

The test suite divides test coverage into four progressive quality tiers:

| Tier | Focus | Test Count | Objectives & Scope |
|---|---|---|---|
| **Tier 1** | Feature Coverage (Happy Path) | 11 | Covers primary functional contracts for R1–R5: Batch ZIP original MSDS, Word safety cards with Section 3 GHS table, Decanting label API, 4 print presets (A4_4UP, A5, DECAL_150, DECAL_75), Decanting label PDF, TCVN 5507:2002 storage matrix, warehouse pairwise check, legal purge, annual report Excel, ReportLab QR, zero-auth mobile view. |
| **Tier 2** | Boundary & Corner Cases | 9 | Tests edge cases, missing data, fault tolerance: Empty chemical IDs, nonexistent IDs, full inventory scope (`scope=all`), unaccented Vietnamese diacritics stripping in ZIP, CAS checksum validation states (`HỢP LỆ`, `SAI CHECKSUM`, `KHÔNG CÓ CAS`), invalid print preset fallback, single chemical storage check. |
| **Tier 3** | Cross-Feature Combinations | 5 | Tests integration across features: Multi-category chemical batch card export (ND 24 PL I/III, ND 26 Precursors, General GHS02, NON DG), real inventory warehouse compatibility, GHS consistency between label and storage matrix, multi-component chemical labels, annual report reconciliation with SQLite database. |
| **Tier 4** | Real-World Workloads & Latency SLA | 5 | Tests production SLAs: Full-batch ZIP download throughput (<5.0s), batch Word safety cards generation (<8.0s), API read latency SLA (<500ms), concurrent thread-safety (10 parallel requests), file descriptor and temporary file cleanup. |

---

## 3. Authoritative Reference Oracles

Every test case derives its assertions from documented statutory or mathematical oracles:

1. **CAS Mod 10 Checksum Algorithm**:
   - International standard CAS verification: $\sum_{i=1}^{k} (i \cdot d_i) \pmod{10} == C$.
   - Tested across known valid CAS (`98060-25-4`, `108-88-3`, `7664-93-9`), invalid checksums (`108-88-4`), and proprietary/missing cases (`N/A`).
2. **TCVN 5507:2002 Chemical Storage Compatibility Matrix**:
   - 11 hazard classes: GHS01 (Explosives), GHS02 (Flammables), GHS03 (Oxidizers), GHS04 (Compressed gases), GHS05-Acid, GHS05-Base, GHS06 (Acute Toxic), GHS07/08 (Health hazards), GHS09 (Environmental), NON_DG.
   - Prohibited co-storage pairs: GHS02 + GHS03 (Red / Forbidden), GHS05-Acid + GHS05-Base (Red / Forbidden), GHS01 + any (Red / Forbidden).
   - Segregated co-storage pairs: GHS02 + GHS06 (Yellow / Segregated).
3. **Vietnamese Unaccented Filename Sanitizer**:
   - Strips Unicode NFKD combining diacritics and replaces precomposed Vietnamese vowels to ASCII: `[MaSP]_[TenHoaChat].[ext]`.
4. **Circular 01/2026/TT-BCT Decanting Label Standards**:
   - Mandatory elements: Product name, Product code / CAS, Facility name (ZhanChen), Signal word (`Nguy hiểm` / `Cảnh báo`), GHS hazard pictograms, H-codes, P-codes, Emergency hotlines (`114`, `115`).
   - Print Presets: `A4_4UP` (4 labels/sheet for 5L–20L cans), `A5` (1 label/sheet for 200L drums/IBC totes), `DECAL_150` (100mm × 150mm), `DECAL_75` (100mm × 75mm).
5. **Circular 02/2026/TT-BCT Annual Chemical Report Structure**:
   - Multi-sheet Excel workbook (`.xlsx`) containing at least 4 sheets: General enterprise info, Chemical activities ledger, Accident prevention & emergency drill records, Precursor & controlled chemicals tracking.
6. **Regulatory Repeal Purge**:
   - Zero occurrences in active catalog of repealed legal acts: Decree 113/2017/NĐ-CP, Decree 82/2022/NĐ-CP, Circular 32/2017/TT-BCT, Circular 04/2012/TT-BCT. Canonical compliance with Law 69/2025/QH15, Decree 24/2026/NĐ-CP, Decree 25/2026/NĐ-CP, Decree 26/2026/NĐ-CP, Circular 01/2026/TT-BCT, Circular 02/2026/TT-BCT, QCVN 01:2025/BYT.

---

## 4. Execution Guide & CLI Commands

### 4.1 Quick Execution Commands

```powershell
# 1. Run Milestone M1 tests only (100% PASS for Batch ZIP original & safety cards)
python test_msds_full_suite.py --milestone M1

# 2. Run progressive E2E suite (Tolerates planned M2-M5 milestones while verifying M1 & baseline)
python test_msds_full_suite.py --progressive

# 3. Run individual Quality Tiers
python test_msds_full_suite.py --progressive --tier 1
python test_msds_full_suite.py --progressive --tier 2
python test_msds_full_suite.py --progressive --tier 3
python test_msds_full_suite.py --progressive --tier 4

# 4. Run with verbose test-by-test logging
python test_msds_full_suite.py --progressive --verbose

# 5. Run Strict Gatekeeper Mode (used for Milestone M_FINAL integration gate)
python test_msds_full_suite.py --strict
```

### 4.2 CLI Argument Reference

| Flag | Argument | Description |
|---|---|---|
| `--tier` | `1`, `2`, `3`, `4`, `all` | Filters execution to a single Quality Tier or all tiers. |
| `--milestone` | `M1`, `M2`, `M3`, `M4`, `M5`, `all` | Filters execution to test cases relevant to a specific milestone. |
| `--progressive` | *(flag)* | Enables progressive testability: skips endpoints returning 404/405 for planned milestones, while enforcing pass on implemented milestones. |
| `--strict` | *(flag)* | Enforces strict gatekeeper mode: any 404/405 endpoint fails immediately (used at `M_FINAL`). |
| `--verbose` / `-v` | *(flag)* | Prints full execution traceback and individual test case status. |

---

## 5. Verification Scorecard Baseline

Current baseline execution results (`python test_msds_full_suite.py --progressive`):

```
==============================================================================
                      E2E TEST EXECUTION SUMMARY                      
==============================================================================
Tier                                     | Total  | Pass   | Fail   | Pend   | Time (s)
------------------------------------------------------------------------------
Tier 1: Feature Coverage (R1-R5 Happy Path) | 11     | 3      | 0      | 8      | 3.02    
Tier 2: Boundary & Corner Cases          | 9      | 5      | 0      | 4      | 3.41    
Tier 3: Cross-Feature Combinations       | 5      | 1      | 0      | 4      | 0.32    
Tier 4: Real-World Workloads & Latency SLA | 5      | 5      | 0      | 0      | 3.09    
------------------------------------------------------------------------------
TOTAL                                    | 30     | 14     | 0      | 16     | 9.84    
==============================================================================

🎉 ALL TEST TIERS PASSED (14/30 tests, 16 pending) in 9.84s!
```

When Milestone M1 is verified in isolation (`python test_msds_full_suite.py --milestone M1`):
```
==============================================================================
                      E2E TEST EXECUTION SUMMARY                      
==============================================================================
Tier                                     | Total  | Pass   | Fail   | Pend   | Time (s)
------------------------------------------------------------------------------
Tier 1: Feature Coverage (R1-R5 Happy Path) | 2      | 2      | 0      | 0      | 3.01    
Tier 2: Boundary & Corner Cases          | 5      | 5      | 0      | 0      | 3.55    
Tier 3: Cross-Feature Combinations       | 1      | 1      | 0      | 0      | 0.27    
Tier 4: Real-World Workloads & Latency SLA | 2      | 2      | 0      | 0      | 1.54    
------------------------------------------------------------------------------
TOTAL                                    | 10     | 10     | 0      | 0      | 8.36    
==============================================================================

🎉 ALL TEST TIERS PASSED (10/10 tests, 0 pending) in 8.36s!
```
