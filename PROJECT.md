# Project: TitanPDF EHS Monthly Chemical Inventory & Usage Tracking (NXT)

## Architecture
- **Language & Runtime**: Python 3.13 / FastAPI / Uvicorn backend + Pure Vanilla JS & Modern Responsive CSS frontend.
- **Database & Persistence**:
  - `data/msds_chemical_inventory.db`: SQLite database in WAL mode (`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;`).
  - Tables:
    - Existing: `chemicals` (13 active CIL records), `compositions`, `sections`.
    - New: `monthly_periods` (id, month, year, title, status, created_at, updated_at).
    - New: `monthly_inventory_records` (id, period_id, chemical_id, product_code, chemical_name, cas_number, supplier, unit, opening_stock, import_qty, export_qty, export_purpose_breakdown, closing_stock, storage_location, safety_threshold, safety_notes, created_at, updated_at).
    - New: `inventory_transactions` (id, period_id, chemical_id, record_id, transaction_type ['IMPORT', 'EXPORT'], transaction_date, quantity, unit, reference_doc, department, purpose, notes, created_at).
- **Core Modules**:
  - `core/monthly_inventory_engine.py`: SQLite schema initialization, CRUD operations, auto-balance math (`closing = opening + import - export`), roll-forward logic, transaction aggregations, openpyxl Excel exporter, printable HTML generator.
  - `core/monthly_inventory_router.py`: FastAPI APIRouter exposing REST endpoints mounted at `/api/msds/monthly-report` and `/api/monthly-inventory`.
  - `core/legal_engine.py` & `core/data/legal_catalog.json`: Regulatory classification under Decree 24/2026/NĐ-CP (Phụ lục IV-A thresholds, Phụ lục I, II, III, V) and Decree 26/2026/NĐ-CP (industrial precursors).
  - `core/msds_intelligence.py`: CIL chemical catalog integration.
- **Frontend Source**:
  - `static/index.html`: Header nav tab button `<button id="nav-tab-inventory">`, main view `<div id="monthly-inventory-view">`, KPI summary cards, data grid, transaction log modal, CIL selector modal.
  - `static/vip_editor.js`: Tab switching logic integration in `switchMainTab('inventory')`.
  - `static/monthly_inventory.js`: Modular IIFE controller managing state, reactive filtering, inline quick edit debouncing, modal interactions, API requests.
  - `static/monthly_inventory_style.css`: Clean SaaS & Vibrant Pop scoped stylesheets, `@media print` print layout.

## Code Layout
- Backend Source:
  - `server.py`
  - `core/monthly_inventory_engine.py`
  - `core/monthly_inventory_router.py`
  - `core/msds_intelligence.py`
  - `core/legal_engine.py`
  - `core/annual_report_exporter.py`
- Frontend Source:
  - `static/index.html`
  - `static/vip_editor.js`
  - `static/monthly_inventory.js`
  - `static/monthly_inventory_style.css`
  - `static/style.css`
- Test Suites:
  - `test_monthly_inventory_suite.py` (New comprehensive E2E test suite for NXT)
  - `test_msds_full_suite.py` (Existing 30-test suite must maintain 100% PASS)

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Tab Navigation & View Container | Independent Nav Tab "📊 BÁO CÁO HÓA CHẤT THÁNG (NXT)", view container, dual-theme support | M4 | ORIGINAL_REQUEST §R1 |
| 2 | Month/Year Reporting Period Selector | Interactive selector with prev/next buttons and new period creation | M4 | ORIGINAL_REQUEST §R1 |
| 3 | Real-time KPI Summary Cards | 4 cards: Total chemicals, total imported, total exported, safety alert count | M4 | ORIGINAL_REQUEST §R1 |
| 4 | Professional Searchable Data Grid | Data grid with quick search by code, name, CAS, supplier | M4 | ORIGINAL_REQUEST §R1 |
| 5 | Dual-Mode Data Entry Engine | Quick monthly summary inline editing + Detailed transactions log modal | M1 | ORIGINAL_REQUEST §R2 |
| 6 | Auto-Balance Calculation | Ending = Initial + Import - Export balance computation | M1 | ORIGINAL_REQUEST §R2 |
| 7 | Auto Roll-Forward Balance | Auto carry-over previous month ending balance to next month initial balance | M1 | ORIGINAL_REQUEST §R2 |
| 8 | Persistent SQLite Storage | Relational tables in `data/msds_chemical_inventory.db` with WAL mode | M1 | ORIGINAL_REQUEST §R2 |
| 9 | CIL Chemical Linkage & Auto-Fill | Query CIL database, auto-fill GHS, CAS, legal status (NĐ 24, NĐ 26) | M2 | ORIGINAL_REQUEST §R3 |
| 10 | 1-Click Batch Add from CIL | Multi-select and add multiple CIL chemicals to monthly report in one action | M2 | ORIGINAL_REQUEST §R3 |
| 11 | Professional Excel Exporter (.xlsx) | Official EHS corporate report with formulas, formatting, 3-tier signatures | M3 | ORIGINAL_REQUEST §R4 |
| 12 | Print Preview & A4 Landscape Direct Print | Browser print preview and direct printing without layout clipping | M3 | ORIGINAL_REQUEST §R4 |
| 13 | Safety Threshold Alerts (NĐ 24 Annex IV) | Alert if stock exceeds safety threshold under NĐ 24/2026/NĐ-CP Phụ lục IV | M5 | ORIGINAL_REQUEST §R5 |
| 14 | Negative Balance & Consumption Rate Alert | Error alert on negative ending stock and consumption rate comparison | M5 | ORIGINAL_REQUEST §R5 |
| 15 | E2E Automated Test Suite & Zero Regression | Full test suite for new endpoints + 100% pass (30/30) on existing tests | M_TEST / FINAL | ORIGINAL_REQUEST §R6 |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Backend Ledger Engine & Persistence | R2: `core/monthly_inventory_engine.py`, `core/monthly_inventory_router.py`, SQLite schema (`monthly_periods`, `monthly_inventory_records`, `inventory_transactions`), REST APIs for periods, records, transactions, dual-mode entry, roll-forward, auto-balance | none | PLANNED |
| M2 | Sổ CIL Integration & Batch Population | R3: Linkage to CIL database (`core/msds_intelligence.py`), auto-populate chemical metadata (CAS, trade name, GHS, ND 24/ND 26 legal badges), 1-click batch add API | M1 | PLANNED |
| M3 | Professional Excel (.xlsx) & Print Engine | R4: `/api/msds/monthly-report/export-excel`, openpyxl corporate template (ZhanChen info, 3-tier signatures, SUM/balance formulas), A4 landscape print preview HTML / CSS | M1, M2 | PLANNED |
| M4 | Modern Frontend Tab UI (NXT Studio) | R1: Tab in `static/index.html`, `static/vip_editor.js` integration, `static/monthly_inventory.js`, `static/monthly_inventory_style.css`, real-time KPI cards, searchable grid, modals | M1, M2 | PLANNED |
| M5 | Safety Thresholds & Warning Engine | R5: Decree 24/2026 Annex IV storage threshold checking, negative balance warnings, monthly consumption rate tracking | M1, M2 | PLANNED |
| M_TEST | E2E Testing Suite Track | R6: Design and implement `test_monthly_inventory_suite.py` covering Tiers 1-4, test all R1-R6 features, verify 30/30 existing tests pass | none (parallel) | PLANNED |
| M_FINAL | Full Integration Gate & Verification | 100% E2E test pass, adversarial challenger verification, forensic audit pass, zero regression sign-off | M1-M5, M_TEST | PLANNED |

---

## Interface Contracts

### M1 (Backend Ledger) ↔ Frontend & Other Modules
- `GET /api/monthly-inventory/periods`: Returns list of reporting periods `[{"id": 1, "month": 10, "year": 2026, "title": "Kỳ 10/2026", "record_count": 13, "status": "OPEN"}]`.
- `POST /api/monthly-inventory/periods`: Accepts `{"month": int, "year": int, "copy_from_previous": bool}`. Automatically performs roll-forward if `copy_from_previous=True`.
- `GET /api/monthly-inventory/periods/{period_id}`: Returns period details, list of chemical records, and summary KPI stats.
- `PUT /api/monthly-inventory/records/{record_id}`: Accepts `{"opening_stock": float, "import_qty": float, "export_qty": float, "storage_location": str, "safety_notes": str}`. Automatically recomputes closing stock and checks thresholds.
- `POST /api/monthly-inventory/transactions`: Accepts `{"period_id": int, "chemical_id": int, "transaction_type": "IMPORT"|"EXPORT", "quantity": float, "department": str, "purpose": str, "reference_doc": str, "transaction_date": str}`. Automatically aggregates quantity to record.
- `GET /api/monthly-inventory/periods/{period_id}/transactions`: Returns all detailed transaction logs for the period.

### M2 (CIL Linkage) ↔ Backend & Frontend
- `POST /api/monthly-inventory/periods/{period_id}/add-from-cil`: Accepts `{"chemical_ids": [int, ...]}` or `{"all": true}`. Populates records using existing CIL chemical attributes and legal badges.

### M3 (Excel & Print) ↔ Frontend & API
- `GET /api/msds/monthly-report/export-excel?month={month}&year={year}`: Returns `FileResponse(media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="Bao_Cao_Su_Dung_Hoa_Chat_Thang_{month}_{year}.xlsx")`.
- `GET /api/monthly-inventory/periods/{period_id}/print-preview`: Returns standalone HTML formatted for A4 landscape print with 3-tier signature block.

### M5 (Safety Engine) ↔ Backend & Frontend
- `GET /api/monthly-inventory/periods/{period_id}/safety-alerts`: Returns `{"negative_balance": [...], "threshold_exceeded": [...], "consumption_spikes": [...]}`.
