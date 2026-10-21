# E2E Test Infra: TitanPDF Comprehensive Upgrade

## Test Philosophy
- Requirement-driven, opaque-box and end-to-end verification.
- Validates the three major pillars:
  1. R1: Stealth License RBAC & Admin Gatekeeper
  2. R2: Google Sheets & Google Drive Persistence via GAS Webhook
  3. R3: Memory Optimization, Smart Pagination & Container Anti-Crash
- Methodology: Category-Partition + Boundary Value Analysis + Pairwise Interaction + Real-World Workload Testing.

---

## Feature Inventory & Test Tier Mapping
| # | Feature | Requirement Source | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---------|-------------------|:------:|:------:|:------:|:------:|
| 1 | Navbar & DOM Stealth | ORIGINAL_REQUEST §R1 | ✓ | ✓ | ✓ | ✓ |
| 2 | Secret Trigger Keyboard (`Ctrl+Shift+L`) | ORIGINAL_REQUEST §R1 | ✓ | ✓ | ✓ | ✓ |
| 3 | Secret Trigger Logo (5 clicks) | ORIGINAL_REQUEST §R1 | ✓ | ✓ | ✓ | ✓ |
| 4 | Master Admin Auth & PIN Validation | ORIGINAL_REQUEST §R1 | ✓ | ✓ | ✓ | ✓ |
| 5 | Admin Session & Logout | ORIGINAL_REQUEST §R1 | ✓ | ✓ | ✓ | ✓ |
| 6 | API RBAC Middleware Protection (401/403) | ORIGINAL_REQUEST §R1 | ✓ | ✓ | ✓ | ✓ |
| 7 | Pastel Glassmorphism UI & KPI Cards | ORIGINAL_REQUEST §R1 | ✓ | ✓ | ✓ | ✓ |
| 8 | License Key Issuance Form & Packages | ORIGINAL_REQUEST §R1 | ✓ | ✓ | ✓ | ✓ |
| 9 | License Actions (Copy, Handover, Reset, Revoke, Delete) | ORIGINAL_REQUEST §R1 | ✓ | ✓ | ✓ | ✓ |
| 10 | Google Apps Script Script (`gas_msds_drive_sync.gs`) | ORIGINAL_REQUEST §R2 | ✓ | ✓ | ✓ | ✓ |
| 11 | Google Sheets 38-Col CIL SSOT | ORIGINAL_REQUEST §R2 | ✓ | ✓ | ✓ | ✓ |
| 12 | Two-Way Sync Backend Proxy Service | ORIGINAL_REQUEST §R2 | ✓ | ✓ | ✓ | ✓ |
| 13 | Permanent Deletion (Zero Revival on Restart) | ORIGINAL_REQUEST §R2 | ✓ | ✓ | ✓ | ✓ |
| 14 | Create/Update Sheet Synchronization | ORIGINAL_REQUEST §R2 | ✓ | ✓ | ✓ | ✓ |
| 15 | Google Drive File Offloading (`LUV_PDF_Exports`) | ORIGINAL_REQUEST §R2 | ✓ | ✓ | ✓ | ✓ |
| 16 | MSDS Cloud Settings Modal (URL, Token, Test Conn) | ORIGINAL_REQUEST §R2 | ✓ | ✓ | ✓ | ✓ |
| 17 | Smart Backend Pagination (`page`, `page_size`) | ORIGINAL_REQUEST §R3 | ✓ | ✓ | ✓ | ✓ |
| 18 | Batch Composition Query (N+1 Elimination) | ORIGINAL_REQUEST §R3 | ✓ | ✓ | ✓ | ✓ |
| 19 | Frontend Pagination HUD (20/50/100) | ORIGINAL_REQUEST §R3 | ✓ | ✓ | ✓ | ✓ |
| 20 | Instant Search & Filter by Name / CAS / GHS | ORIGINAL_REQUEST §R3 | ✓ | ✓ | ✓ | ✓ |
| 21 | Upload Temp File Immediate Cleanup | ORIGINAL_REQUEST §R3 | ✓ | ✓ | ✓ | ✓ |
| 22 | Download Route Background Task Cleanup | ORIGINAL_REQUEST §R3 | ✓ | ✓ | ✓ | ✓ |
| 23 | Watchdog Cleaner Daemon (10m interval) | ORIGINAL_REQUEST §R3 | ✓ | ✓ | ✓ | ✓ |
| 24 | Explicit Garbage Collection & RAM < 200MB | ORIGINAL_REQUEST §R3 | ✓ | ✓ | ✓ | ✓ |

---

## Test Architecture
- **Backend Test Runner**: `pytest tests/test_upgrade_orch19_suite.py -v`
- **Frontend E2E Runner**: `pytest tests/test_playwright_stealth_rbac.py -v` (Playwright)
- **Full Regression Runner**: `python tests/test_runner.py --tier 1` and `python tests/verify_suite.py`
- **Output Formats**: Standard TAP/JUnit and structured JSON reporting.

---

## Test Tiers Definition

### Tier 1: Feature Coverage (Isolation & Equivalence Classes)
- Verify each feature in strict isolation:
  - Stealth tab element is hidden from unauthenticated guests (`display: none !important; aria-hidden="true"`).
  - Admin login rejects incorrect PIN with `401 Unauthorized` and accepts `ADMIN_MASTER_KEY` (`258079`).
  - All `/api/admin/licenses*` endpoints reject requests without admin token with `401 Unauthorized` or `403 Forbidden`.
  - `/api/license/verify` accepts public requests without admin token.
  - GAS proxy service serializes chemical attributes to 38-column format.
  - `/api/msds/list` returns paginated structure with `page=1, page_size=20`.
  - Upload temp cleaner successfully unlinks files upon request completion.

### Tier 2: Boundary & Corner Cases
- Admin PIN with special characters, empty string, or whitespace.
- 5-click logo trigger with slow clicks (>3s) does not trigger login modal; rapid 5 clicks triggers modal.
- Pagination bounds: `page=0`, `page=-1`, `page=999999`, `page_size=20/50/100/all`.
- Deleting already deleted chemical ID returns graceful response, no unhandled exception.
- Simulating Render restart (wiping local SQLite database) and verifying that chemicals previously deleted on Google Sheet do NOT revive.
- Heavy upload payload handling and memory spikes during concurrent processing.

### Tier 3: Cross-Feature Combinations (Pairwise Coverage)
- Admin Login -> Issue New Enterprise License -> Copy Key -> Verify Key via `/api/license/verify` -> Revoke License -> Re-verify (Key now revoked).
- Add new chemical via MSDS -> Verify Google Sheet sync row added -> Delete chemical -> Verify Google Sheet row removed -> Simulate container restart -> Verify chemical remains absent.
- Upload chemical with multiple compositions -> Verify batch composition query returns all compositions without N+1 overhead -> Verify pagination HUD shows correct counts.
- Search chemical while on Page 3 -> Filter immediately updates result set and resets to Page 1.

### Tier 4: Real-World Application Scenarios
- **Scenario 1 (Guest Sneak-In Attempt)**: Guest user inspects DOM, attempts to call `/api/admin/licenses/create` and `/api/admin/licenses/list`, both strictly fail with 401/403. Guest attempts to execute `switchMainTab('license')`, view remains unmounted.
- **Scenario 2 (Admin Operations Flow)**: Owner uses `Ctrl+Shift+L`, enters master key `258079`, accesses redesigned Pastel Glassmorphism tab, inspects 4 KPI cards, issues 1-year Pro license for 3 devices, copies key, clicks Admin Logout, verifies tab is immediately unmounted and session cleared.
- **Scenario 3 (Render Ephemeral Restart Resiliency)**: Admin configures GAS Webhook in MSDS Settings. Clears all default sample chemicals. Restarts container / server process. Opens MSDS tab: chemical inventory is completely empty, 13 seed chemicals are permanently gone.
- **Scenario 4 (High-Volume Chemical Pagination & Memory Under Pressure)**: Seed 100 chemicals. Query page 1 (20 items). Memory remains flat (<190MB). Search "Toluen" (CAS 108-88-3) across pages; table instantly filters. Post-upload temp files are automatically deleted, keeping `temp/` file count from growing.

---

## Coverage Thresholds
- Tier 1: 100% pass on all individual feature tests.
- Tier 2: 100% pass on all boundary conditions.
- Tier 3: 100% pass on cross-feature integration flows.
- Tier 4: 100% pass on all 4 real-world operational scenarios.
- Regression: 100% pass on existing test suites (`test_runner.py`, `verify_suite.py`, `verify_legal_integration.py`).
