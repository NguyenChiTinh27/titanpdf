# Project: TitanPDF EHS Chemical Management System Overhaul

## Architecture
- **Language & Runtime**: Python 3.13 / FastAPI / Uvicorn backend + Pure Vanilla JS & Modern CSS frontend.
- **Data Stores**:
  - `data/msds_chemical_inventory.db` (SQLite 3 relational chemical inventory, 13 active records).
  - `data/msds_files/` (Physical repository of original MSDS `.pdf`, `.doc`, `.docx` files).
  - `core/data/legal_catalog.json` (Indexed legal database with 2,191 entries across ND 24, ND 26, QCVN 01).
- **Core Modules**:
  - `server.py`: API route dispatching, static mounting, auth handling.
  - `core/msds_intelligence.py`: MSDS extraction, SQLite CRUD, CIL Excel exporter, Word safety card exporter.
  - `core/legal_engine.py`: Regulatory matcher, CAS Mod 10 validator, item type classification (`raw_material` vs `finished_product`).
  - `core/ghs_label_engine.py`: Decanting label data formatting, vector PDF / HTML print generation.
  - `core/storage_compatibility_engine.py`: TCVN 5507:2002 storage compatibility matrix & pairwise conflict checking.
  - `core/annual_report_exporter.py`: Circular 02/2026/TT-BCT 4-sheet/5-sheet annual chemical report Excel generator.
- **Frontend Components**:
  - `static/index.html`: Main SPA structure, `#msds-studio-view`, `#msds-batch-action-bar`, modals.
  - `static/ai_studio.js`: Client-side logic for CIL table, batch operations, modal bindings.
  - `static/style.css`: Modern Bento / glass UI styling + isolated `@media print` rules for label printing.
  - `static/msds_emergency.html`: Dedicated mobile-responsive emergency quick view template.

## Code Layout
- Backend Source:
  - `server.py`
  - `core/msds_intelligence.py`
  - `core/legal_engine.py`
  - `core/ghs_label_engine.py`
  - `core/storage_compatibility_engine.py`
  - `core/annual_report_exporter.py`
  - `core/ghs_templates/`
- Frontend Source:
  - `static/index.html`
  - `static/ai_studio.js`
  - `static/style.css`
  - `static/msds_emergency.html`
- Test Suites:
  - `test_msds_full_suite.py` (Root comprehensive E2E test suite)
  - `tests/verify_legal_integration.py` (Legal catalog regression suite)
  - `test_image_ghs_integration.py` (Pure Python OLE2/Docx GHS binary regression suite)
  - `tests/verify_m2_frontend_msds.py` (DOM & JS regression suite)

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Batch ZIP Original MSDS | Download selected or all original MSDS files as ZIP with unaccented names | M1 | ORIGINAL_REQUEST §R1 |
| 2 | Batch ZIP Safety Cards Word | Generate and download Word (.docx) safety cards with 4-column composition table as ZIP | M1 | ORIGINAL_REQUEST §R1 |
| 3 | Batch Action Bar Buttons | UI buttons on `#msds-batch-action-bar` for downloading selected MSDS & cards | M1 | ORIGINAL_REQUEST §R1 |
| 4 | CIL Toolbar Full Export | Left panel toolbar buttons for downloading full chemical inventory ZIPs | M1 | ORIGINAL_REQUEST §R1 |
| 5 | GHS Decanting Label Data API | API returning formatted data, GHS pictograms, and H/P statements for decanting labels | M2 | ORIGINAL_REQUEST §R2 |
| 6 | GHS Label HTML Print & PDF | Printable HTML & server-side PDF generator for secondary GHS labels | M2 | ORIGINAL_REQUEST §R2 |
| 7 | Decanting Label Modal UI | High-contrast modal with live 2-way preview, form binding, and chemical selector | M2 | ORIGINAL_REQUEST §R2 |
| 8 | 4 Print Size Presets | A4 (4-up), A5 (1-up), Decal 100x150mm, Decal 100x75mm with isolated `@media print` CSS | M2 | ORIGINAL_REQUEST §R2 |
| 9 | Storage Compatibility Engine | TCVN 5507:2002 11-class compatibility matrix and conflict detector (C, S, X) | M3 | ORIGINAL_REQUEST §R3 |
| 10 | Storage Matrix API | Endpoints returning 2D matrix definitions and evaluating chemical list compatibility | M3 | ORIGINAL_REQUEST §R3 |
| 11 | Storage Matrix Modal UI | Interactive 9x9 2D matrix view with color coding and hazard mechanism popovers | M3 | ORIGINAL_REQUEST §R3 |
| 12 | Warehouse Pairwise Checker | Interactive tool in modal to select 2 chemicals and evaluate storage co-location | M3 | ORIGINAL_REQUEST §R3 |
| 13 | 2026 Legal Framework Purge | Replace obsolete ND 113, ND 82, TT 32, TT 04, ND 28 with Law 69, ND 24/25/26, TT 01/02 | M4 | ORIGINAL_REQUEST §R4 |
| 14 | Annual Chemical Report Exporter | Generate official multi-sheet Excel report per Circular 02/2026/TT-BCT | M4 | ORIGINAL_REQUEST §R4 |
| 15 | Annual Report UI Button | UI button on toolbar triggering Sở Công Thương annual report export | M4 | ORIGINAL_REQUEST §R4 |
| 16 | Chemical QR Code API | ReportLab vector SVG/PNG QR code generator pointing to `/mobile-msds/{id}` | M5 | ORIGINAL_REQUEST §R5 |
| 17 | Mobile Emergency Quick View | Zero-auth mobile page (`static/msds_emergency.html`) with 5 emergency blocks & 1-tap call | M5 | ORIGINAL_REQUEST §R5 |
| 18 | QR Code Modal & Stickers | Modal to view QR code, select sticker sizes (50mm, 70mm, 100mm) and print/download | M5 | ORIGINAL_REQUEST §R5 |
| 19 | E2E Test Suite | Comprehensive automated test harness `test_msds_full_suite.py` with 100% pass | M_TEST / FINAL | ORIGINAL_REQUEST §R6 |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Batch ZIP Downloads | R1: Backend ZIP endpoints (`/api/msds/download-batch-original`, `/api/msds/export-batch-safety-cards`) + Frontend batch action bar & toolbar buttons + Section 3 GHS table | none | DONE |
| M2 | GHS Decanting Label Maker | R2: `core/ghs_label_engine.py` + Label print HTML & PDF endpoints + Modal UI + 4 print presets (A4 4-up, A5, Decal 100x150, Decal 100x75) + `@media print` CSS | M1 | DONE |
| M3 | Storage Compatibility Matrix | R3: `core/storage_compatibility_engine.py` (TCVN 5507:2002) + Matrix API + Interactive 9x9 Modal UI + Pairwise Warehouse Checker | M1 | DONE |
| M4 | Legal Overhaul & Annual Report | R4: Canonicalize ND 26/ND 24/Law 69/TT 01/TT 02/QCVN 01 + `core/annual_report_exporter.py` (multi-sheet xlsx) + UI buttons & badges | M1 | DONE |
| M5 | Mobile Emergency QR System | R5: ReportLab QR endpoint (`/api/msds/qr-code/{id}`) + `static/msds_emergency.html` + QR sticker modal + 1-tap emergency call | M1 | DONE |
| M_TEST | E2E Testing Suite Track | R6: Requirements-driven `test_msds_full_suite.py` testing Tiers 1-4 with TestClient fallback and SLA checks | none (parallel) | DONE |
| M_FINAL | Full Integration & Gate | Run full test suite, regression checks, forensic audit, verify 100% pass rate | M1-M5, M_TEST | DONE |

---

## Interface Contracts

### M1 ↔ Frontend
- `POST /api/msds/download-batch-original` (JSON `{"ids": ["id1", "id2"]}` or query `?scope=all`): Returns `FileResponse(media_type="application/zip", filename="MSDS_Goc_TongHop_YYYYMMDD.zip")`.
- `POST /api/msds/export-batch-safety-cards` (JSON `{"ids": ["id1", "id2"]}` or query `?scope=all`): Returns `FileResponse(media_type="application/zip", filename="The_An_Toan_TongHop_YYYYMMDD.zip")`.

### M2 ↔ Frontend
- `GET /api/msds/label-data/{chem_id}`: Returns JSON with product details, active CAS, facility, signal word, GHS icons, H-codes, P-codes, and hotline.
- `GET /api/msds/label-print-html/{chem_id}?size=A4_4UP|A5|DECAL_150|DECAL_75`: Returns standalone printable HTML.
- `POST /api/msds/export-ghs-labels-pdf`: Accepts `{"ids": [...], "size": "..."}`, returns PDF stream.

### M3 ↔ Frontend
- `GET /api/msds/storage-compatibility-matrix`: Returns 11x11 matrix rules, class descriptions, color codes, and TCVN 5507:2002 references.
- `POST /api/msds/storage-compatibility-check`: Accepts `{"ids": [...]}` or defaults to all; returns pairwise conflict alerts list and compatibility status.

### M4 ↔ Frontend
- `GET /api/msds/export-annual-chemical-report`: Returns `FileResponse(media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="Bao_Cao_Hoa_Chat_Hang_Nam_TT02_2026_YYYYMMDD.xlsx")`.

### M5 ↔ Frontend & Mobile
- `GET /api/msds/qr-code/{chem_id}`: Returns SVG/PNG image of QR code pointing to `/mobile-msds/{chem_id}`.
- `GET /mobile-msds/{chem_id}` (and alias `/api/msds/qr-view/{chem_id}`): Serves responsive HTML `static/msds_emergency.html` with zero authentication requirement.
