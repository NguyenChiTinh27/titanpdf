# E2E Test Infra: Gate Pass & Material Dispatch Studio

## Test Philosophy
- Opaque-box, requirement-driven. Derived strictly from `ORIGINAL_REQUEST.md` and user-facing specifications.
- Methodology: Category-Partition + Boundary Value Analysis (BVA) + Pairwise Combinatorial Testing + Real-World Workload Testing + Adversarial Hardening.

## Feature Inventory
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 |
|---|---------|---------------------|:------:|:------:|:------:|
| 1 | Navbar Tab & Routing (`#gatepass-studio`) | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ |
| 2 | KPI Dashboard Metrics & Calculations | ORIGINAL_REQUEST §R1.a | 5 | 5 | ✓ |
| 3 | KPI Chart.js Data Visualizations | ORIGINAL_REQUEST §R1.a | 5 | 5 | ✓ |
| 4 | Scan Studio Split-screen & Canvas HUD | ORIGINAL_REQUEST §R1.b | 5 | 5 | ✓ |
| 5 | Multi-file Queue Strip Management | ORIGINAL_REQUEST §R1.b | 5 | 5 | ✓ |
| 6 | Bilingual CN-VN Items Table & Inline Editing | ORIGINAL_REQUEST §R1.b | 5 | 5 | ✓ |
| 7 | Auto-Summation & Formula Engine | ORIGINAL_REQUEST §R1.b | 5 | 5 | ✓ |
| 8 | DeepSeek Vision OCR Extraction | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ |
| 9 | Audit & Proof Match Engine | ORIGINAL_REQUEST §R1.c | 5 | 5 | ✓ |
| 10 | History Search & Date Filters | ORIGINAL_REQUEST §R1.d | 5 | 5 | ✓ |
| 11 | Split-view Detail Modal & Zoom | ORIGINAL_REQUEST §R1.d | 5 | 5 | ✓ |
| 12 | A4 / A5 Print Engine | ORIGINAL_REQUEST §R1.d | 5 | 5 | ✓ |
| 13 | FastAPI Backend & SQLite WAL Cache | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ |
| 14 | Google Apps Script Bridge & Drive Upload | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ |
| 15 | Google Sheet 19-Column Sync | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ |
| 16 | Granular RBAC (Tool #36 Registration) | ORIGINAL_REQUEST §R4 | 5 | 5 | ✓ |
| 17 | Guest Mode Read-Only Protection & Masking | ORIGINAL_REQUEST §R4 | 5 | 5 | ✓ |

## Test Architecture
- **Test Runners**:
  - Python Backend Runner: `pytest` / `unittest` on `tests/test_gatepass_service_suite.py` with Dual-Mode ApiClient (Live 8888 + in-process ASGI TestClient).
  - Playwright E2E Runner: `pytest` / `async_playwright` on `tests/test_gatepass_e2e_suite.py` verifying real browser interaction, canvas manipulation, modal switching, and RBAC locking.
- **Pass/Fail Semantics**: 100% PASS, zero HTTP 500 errors, zero unhandled JavaScript console exceptions, exit code 0.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Full Finished Goods Dispatch Lifecycle | F1, F4, F5, F6, F7, F8, F13, F14, F15 | High |
| 2 | Material Outwork Processing with A5 Print | F6, F7, F9, F11, F12, F13 | High |
| 3 | Mismatched Plate & Unsigned Slip Audit Alert | F8, F9, F11, F13 | Medium |
| 4 | Offline Caching & Background Cloud Resync | F2, F10, F13, F14, F15 | High |
| 5 | Guest Mode Unauthorized Mutation Lockout | F1, F2, F10, F11, F16, F17 | High |

## Coverage Thresholds
- Tier 1: ≥5 per feature (≥85 test cases)
- Tier 2: ≥5 per feature where boundaries exist (≥85 test cases)
- Tier 3: Pairwise coverage of major feature interactions (≥17 test cases)
- Tier 4: ≥5 realistic factory application scenarios
- Tier 5: Adversarial white-box gap hardening
