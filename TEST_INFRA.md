# Test Infrastructure Documentation (TEST_INFRA.md)
*TitanPDF Chemical Legal Lookup & Warning System — Automated E2E Test Suite*

## 1. Overview & Architecture

The TitanPDF Chemical Legal Lookup & Warning system testing infrastructure provides independent, opaque-box end-to-end verification across four rigorous test tiers (Tiers 1–4). It verifies all 25 features identified in `PROJECT.md`, adhering to the principle of opaque-box execution: the test runner tests system behavior via public HTTP REST APIs, SQLite inventory state, and generated Word (.docx) binary artifacts.

### Key Architectural Characteristics
- **Opaque-Box Network Protocol**: Direct HTTP client (`ApiClient` backed by `requests`) issuing requests against `http://127.0.0.1:8888` (configurable via `TITAN_TEST_URL`).
- **Resilient Fallback Mode**: When the live server process is not running, `ApiClient` automatically falls back to Starlette/FastAPI's in-process `TestClient(app)`, allowing the suite to run in headless CI environments without external daemon management.
- **Strict Oracles**: Ground-truth assertions are derived from statutory law definitions (NĐ 24/2026/NĐ-CP, NĐ 28/2026/NĐ-CP, QCVN 01:2025/BYT), mathematical checksum algorithms (CAS Checksum Rule `sum(i * d_i) % 10`), and international Unicode normalization standards (NFKD).
- **Latency SLA Guarantees**: Strict per-request latency checks (< 500ms) executed over 50 iterations for search and batch matching, plus multi-threaded concurrency stress.

---

## 2. 4-Tier Testing Hierarchy

| Tier | Name | Target Capabilities | Features Covered | Test Count |
|------|------|---------------------|------------------|------------|
| **Tier 1** | **Feature Coverage** | Catalog overview stats, sources, sections, CAS search, unaccented search, multi-token search, batch match endpoint, item_type filtering, Word Section 3 GHS table | F01–F11, F21 | 19 tests |
| **Tier 2** | **Boundary & Corner Cases** | Multi-CAS strings, unnormalized whitespace around hyphens, CAS checksum validity & rejection, unknown CAS, empty/whitespace queries, SQL/regex injection resilience, threshold conversions | F02, F03, F04, F06, F08, F09 | 13 tests |
| **Tier 3** | **Cross-Feature Combinations** | Multi-level cascading filter (Source + Section + Query), mixed regulated vs unregulated batch matching, pagination boundaries, item_type inventory separation | F07, F08, F09, F10, F16, F20 | 9 tests |
| **Tier 4** | **Real-World Workloads & SLA** | Statutory profiles for flagship chemicals (Toluene, Sulfuric Acid, Acetone, Methanol), real-world 5-ingredient NC Thinner SDS formulation, latency SLA (<500ms across 50 iterations), 10-thread concurrency | F08, F09, F23, F24, F25 | 8 tests |
| **Total** | | **Comprehensive E2E Suite** | **All 25 Features** | **49 tests** |

---

## 3. Authoritative Oracles & Ground Truth

### 3.1 CAS Number Checksum Algorithm
For any CAS Registry Number in standard format `A-B-C` where `A` is 2 to 7 digits, `B` is 2 digits, and `C` is a 1-digit check number:
$$\text{Checksum} = \left(\sum_{k=1}^{N} k \times d_k\right) \bmod 10$$
Where $d_1$ is the last digit of $B$, $d_2$ is the first digit of $B$, $d_3$ is the last digit of $A$, and so forth from right to left.
- Valid Examples: `108-88-3` (Toluene), `7664-93-9` (Sulfuric acid), `67-64-1` (Acetone), `67-56-1` (Methanol), `7732-18-5` (Water), `1330-20-7` (Xylene).
- Corrupted Examples: `108-88-9`, `7664-93-0`, `67-64-8`, `67-56-2`.

### 3.2 Vietnamese Threshold Number Conversion
Vietnamese regulatory texts denote thousands with dots (`.`):
- `'5.000'` $\rightarrow 5000.0\text{ kg}$
- `'50.000'` $\rightarrow 50000.0\text{ kg}$
- `'5.000.000'` $\rightarrow 5000000.0\text{ kg}$
- `'200'` $\rightarrow 200.0\text{ kg}$
- Empty string / `'Không quy định'` $\rightarrow \text{None}$

### 3.3 Word (.docx) Section 3 GHS Composition Table
Every exported Emergency Safety Card Word document (`MSDSSafetyCardExporter.generate_safety_card_docx`) must include:
- Table header: `🧪 BẢNG THÀNH PHẦN HÓA HỌC & SỐ CAS (MỤC 3 GHS)`
- Required 4 columns:
  1. `Tên Thành Phần Hoạt Chất`
  2. `Số CAS`
  3. `Hàm Lượng (%)`
  4. `Thẩm Định Checksum`

---

## 4. Execution Commands

### 4.1 Run Entire Test Suite (Tiers 1–4)
```powershell
python tests/verify_legal_integration.py
```

### 4.2 Run Specific Tier
```powershell
python tests/verify_legal_integration.py --tier 1
python tests/verify_legal_integration.py --tier 2
python tests/verify_legal_integration.py --tier 3
python tests/verify_legal_integration.py --tier 4
```

### 4.3 Run with Verbose Reporting
```powershell
python tests/verify_legal_integration.py --verbose
```

### 4.4 Run via Standard Python unittest
```powershell
python -m unittest tests/verify_legal_integration.py
```

---

## 5. Environment & Dependencies

- Python 3.10+ (Standard Library: `unittest`, `re`, `json`, `time`, `concurrent.futures`, `io`)
- Third-party packages:
  - `requests`: HTTP client communications
  - `python-docx`: OOXML Word document inspection
  - `fastapi` & `starlette`: In-process ASGI test execution fallback
- Target Server: `127.0.0.1:8888` (default) or environment variable `TITAN_TEST_URL`.
