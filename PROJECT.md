# Project: TitanPDF Comprehensive Upgrade (Stealth License RBAC, Google Sheets/Drive Persistence & Anti-Crash)

## Architecture
- **Overview**: A multi-faceted architectural upgrade transforming TitanPDF into a resilient, memory-optimized, stateless cloud-first application on Render (`https://tinh-of-2m9j.onrender.com/`).
- **R1: Stealth License Tab & RBAC Architecture**:
  - Hidden by default: `#nav-tab-license` is completely absent from DOM for unauthenticated guests (`display: none !important; aria-hidden="true"`), and `#license-manager-view` is an empty uninitialized shell.
  - Dual Secret Triggers: Global `Ctrl + Shift + L` (and `Cmd + Shift + L` on macOS) OR 5 consecutive clicks on the brand logo within 3 seconds opens `#admin-auth-modal`.
  - Master Admin Authentication: `POST /api/admin/auth/login` validating against `os.getenv("ADMIN_MASTER_KEY", "258079")`. Upon success, issues session token stored in `sessionStorage.getItem("luv_admin_token")` and mounts License Tab in navbar.
  - Admin Logout: Clears token, invalidates session on server, and removes tab and view from DOM.
  - API RBAC Middleware: `require_admin` dependency applied to `/api/admin/*`, `/api/admin/licenses/*`, and administrative `/api/license/*` routes. Unauthenticated or guest calls rejected with `401 Unauthorized` or `403 Forbidden`. External verification endpoint `/api/license/verify` remains public for client apps.
  - Pastel Glassmorphism UI: Modern redesign with 4 KPI cards (Total Licenses, Active Devices, Cloud Sync Status, Revenue/Tier breakdown), key issuance form with package selection (Enterprise, Lifetime, Pro, Trial), search filter, and action buttons (Copy, Handover, Reset Machine, Revoke, Delete).
- **R2: Persistent Cloud Storage via Google Sheets & Google Drive (GAS)**:
  - Eliminates "Render Ephemeral Reset": The 13 seed chemicals in git-committed `data/msds_chemical_inventory.db` no longer revive after restart.
  - Google Sheets as SSOT: 38-column schema `CIL_Chemical_Inventory` synchronized via Google Apps Script Webhook API (`gas_msds_drive_sync.gs`).
  - Permanent Deletion: Deleting a chemical or clicking "Delete All" immediately issues `deleteChemical` / `deleteAllChemicals` to Google Sheet (`sheet.deleteRow`) and purges local cache. On server startup, TitanPDF reconciles with Google Sheets so deleted chemicals never revive.
  - Google Drive Offloading: Uploaded original MSDS PDFs, exported Word/PDF files, and GHS label images are streamed directly to user's Google Drive (`LUV_PDF_Exports/MSDS_Originals`) via GAS `uploadFile`, returning public Drive file ID and view/download URLs.
  - Settings UI: Modern modal in MSDS tab with GAS Webhook URL input, secret token, Test Connection button, and live sync status.
- **R3: Memory Optimization & Anti-Crash Architecture**:
  - Smart Pagination: `/api/msds/list` upgraded with `page` and `page_size` (20 / 50 / 100), SQLite `LIMIT/OFFSET`, and batch composition lookup to eliminate N+1 queries.
  - Frontend Pagination HUD: In `static/index.html` and `static/ai_studio.js`, renders only the active page of 20/50/100 records with instant search and filtering by chemical name, CAS, and GHS hazard class.
  - Instant Temp Cleanup: Middleware automatically tracks and unlinks temporary upload files post-request.
  - Background Task Cleanup: `BackgroundTask(safe_remove_file)` attached to `/api/download/{filename}`.
  - Watchdog Temp Cleaner: Periodic cleaner running every 10 minutes purges orphaned files in `temp/` and `output/` older than 15 minutes and executes explicit `gc.collect()`.
  - Memory Budget: Keeps Python process RAM strictly < 200MB (safe ceiling < 300MB on Render's 512MB limit), eliminating OOM crashes (502 Bad Gateway).

---

## Code Layout
- `core/auth_rbac.py` — Role extraction, `require_owner`, and `require_admin` dependency.
- `core/license_manager.py` — License key generation, verification, and database management.
- `core/msds_gas_sync.py` — FastAPI service proxy for Google Apps Script Webhook API (Sheets CRUD & Drive offload).
- `core/msds_intelligence.py` — MSDS extraction engine, SQLite local cache, and paginated query helper.
- `server.py` — FastAPI application, API routes, RBAC protection, file cleanup middleware, and temp cleaner daemon.
- `gas_msds_drive_sync.gs` — Production Google Apps Script Webhook for Google Sheets & Google Drive.
- `static/index.html` — Navbar stealth, Admin Auth Modal, Pastel Glassmorphism License tab, MSDS Pagination HUD, and GAS Settings Modal.
- `static/app.js` — Dual secret triggers (`Ctrl+Shift+L` + 5-click logo), Admin session manager, and API token interceptor.
- `static/ai_studio.js` — MSDS client state, smart pagination controller, permanent delete handler, and GAS settings controller.
- `static/license_manager.css` — Modern Glassmorphism / Pastel Kawaii Pro styling for License Manager.
- `tests/test_upgrade_orch19_suite.py` — Comprehensive unit and integration test suite (Tiers 1-4).
- `tests/test_playwright_stealth_rbac.py` — Playwright E2E browser test verifying DOM stealth, secret triggers, and UI interactions.

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Navbar & DOM Stealth | Tab `#nav-tab-license` completely hidden from unauthenticated guests (`display: none !important`) | M1 | ORIGINAL_REQUEST §R1 |
| 2 | Secret Trigger Keyboard | `Ctrl + Shift + L` (and `Cmd + Shift + L`) opens Admin Login Modal | M1 | ORIGINAL_REQUEST §R1 |
| 3 | Secret Trigger Logo Click | 5 consecutive clicks on brand logo within 3 seconds opens Admin Login Modal | M1 | ORIGINAL_REQUEST §R1 |
| 4 | Admin Master Auth Endpoint | `POST /api/admin/auth/login` validates against `ADMIN_MASTER_KEY` / `258079` | M1 | ORIGINAL_REQUEST §R1 |
| 5 | Admin Session & Logout | Session token storage in client and Admin Logout button to instantly re-hide tab | M1 | ORIGINAL_REQUEST §R1 |
| 6 | API RBAC Protection | `require_admin` middleware rejects unauthorized `/api/admin/*` calls with 401/403 | M1 | ORIGINAL_REQUEST §R1 |
| 7 | Pastel Glassmorphism UI | Modern UI redesign with 4 KPI cards, status badges, and search filtering | M1 | ORIGINAL_REQUEST §R1 |
| 8 | License Key Issuance Form | Form with package selection (Enterprise, Lifetime, Pro, Trial), duration, and device limits | M1 | ORIGINAL_REQUEST §R1 |
| 9 | License Action Buttons | Copy, Handover, Reset Machine, Revoke, and Delete actions with live feedback | M1 | ORIGINAL_REQUEST §R1 |
| 10 | Google Apps Script Script | `gas_msds_drive_sync.gs` handling Google Sheets CRUD + Google Drive file upload | M2 | ORIGINAL_REQUEST §R2 |
| 11 | Google Sheets 38-Col SSOT | 38-column `CIL_Chemical_Inventory` schema covering all 16 GHS sections and CAS | M2 | ORIGINAL_REQUEST §R2 |
| 12 | Two-Way Sync Backend Proxy | `core/msds_gas_sync.py` proxying requests between FastAPI and GAS Webhook | M2 | ORIGINAL_REQUEST §R2 |
| 13 | Permanent Deletion Protocol | Deletion removes row from Google Sheet and purges cache; restart never revives deleted items | M2 | ORIGINAL_REQUEST §R2 |
| 14 | Create/Update Sheet Sync | New chemicals or edits immediately append/update rows on Google Sheet | M2 | ORIGINAL_REQUEST §R2 |
| 15 | Google Drive File Offload | Original MSDS files and exports uploaded to `LUV_PDF_Exports/MSDS_Originals` in Drive | M2 | ORIGINAL_REQUEST §R2 |
| 16 | MSDS Cloud Settings Modal | Modal in MSDS tab: GAS Webhook URL, Secret Token, Test Connection, sync status | M2 | ORIGINAL_REQUEST §R2 |
| 17 | Smart Backend Pagination | `/api/msds/list` supports `page` and `page_size` (20/50/100) with SQLite LIMIT/OFFSET | M3 | ORIGINAL_REQUEST §R3 |
| 18 | Batch Composition Resolver | Single batch query for compositions, eliminating N+1 database queries | M3 | ORIGINAL_REQUEST §R3 |
| 19 | Frontend Pagination HUD | Pagination bar in MSDS tab rendering only current page of 20/50/100 items | M3 | ORIGINAL_REQUEST §R3 |
| 20 | Instant Search & Filter | Client/server instant search by name, CAS, and GHS classification on paginated data | M3 | ORIGINAL_REQUEST §R3 |
| 21 | Upload Temp Cleaner | Middleware tracking upload files and unlinking immediately post-request | M3 | ORIGINAL_REQUEST §R3 |
| 22 | Download Cleanup Task | `BackgroundTask` cleaning served files from `output/` after download | M3 | ORIGINAL_REQUEST §R3 |
| 23 | Periodic Watchdog Cleaner | Daemon task purging orphaned files > 15 mins in `temp/` and `output/` every 10 mins | M3 | ORIGINAL_REQUEST §R3 |
| 24 | Explicit Garbage Collection | Invoking `gc.collect()` and closing PyMuPDF contexts to keep RAM < 200MB | M3 | ORIGINAL_REQUEST §R3 |
| 25 | Tier 1-4 Automated Test Suite | Comprehensive unit, integration, and E2E tests verifying all requirements | M4 | ORIGINAL_REQUEST §AC |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Stealth RBAC & License Tab Redesign | Features 1–9: Navbar/DOM stealth, dual triggers, Admin auth, API middleware, Pastel Glassmorphism UI | none | DONE |
| 2 | M2: Google Sheets & Drive Persistence (GAS) | Features 10–16: `gas_msds_drive_sync.gs`, 38-col Sheet SSOT, permanent delete, Drive offload, settings UI | none | IN_PROGRESS |
| 3 | M3: Memory Optimization & Anti-Crash | Features 17–24: Smart pagination (20/50/100), N+1 query elimination, temp cleaners, RAM < 200MB | none | PLANNED |
| 4 | M4: Dual-Track E2E Test Pass & Hardening | Feature 25: Tiers 1-4 automated test suite, E2E browser tests, zero regressions | M1, M2, M3 | PLANNED |

---

## Interface Contracts

### M1: Admin Authentication & License RBAC
- `POST /api/admin/auth/login`:
  - Request: `{"master_key": string}`
  - Response: `{"success": true, "token": string, "role": "admin"}` or `401 Unauthorized`
- `POST /api/admin/auth/logout`:
  - Headers: `Authorization: Bearer <token>`
  - Response: `{"success": true}`
- `GET /api/admin/licenses/list`:
  - Headers: `Authorization: Bearer <token>`
  - Response: `{"success": true, "licenses": [...], "stats": {"total": int, "active": int, "online": int}}`
  - Rejection: `401 Unauthorized` / `403 Forbidden` if missing or invalid token.

### M2: Google Apps Script Webhook API (`gas_msds_drive_sync.gs`)
- `POST <gas_webhook_url>`:
  - Header/Body: `{"token": string, "action": string, ...}`
  - Actions supported:
    - `ping`: Returns `{"status": "ok", "sheet_id": string, "total_rows": int}`
    - `getAllChemicals`: Returns `{"status": "ok", "chemicals": [...]}`
    - `saveChemical`: Accepts chemical object, upserts row into `CIL_Chemical_Inventory`.
    - `deleteChemical`: Accepts `{"chemical_id": string}`, deletes matching row from Google Sheet.
    - `deleteAllChemicals`: Clears all data rows (retaining header row).
    - `uploadFile`: Accepts `{"filename": string, "base64Data": string, "mimeType": string}`, saves to `LUV_PDF_Exports/MSDS_Originals`, returns `{"fileId": string, "viewUrl": string, "downloadUrl": string}`.

### M3: Smart Paginated MSDS API
- `GET /api/msds/list`:
  - Query params: `page: int = 1`, `page_size: int = 20` (or `50`, `100`, `all`), `q: Optional[str] = None`, `item_type: Optional[str] = None`, `ghs_filter: Optional[str] = None`.
  - Response:
    ```json
    {
      "success": true,
      "data": [...],
      "pagination": {
        "page": 1,
        "page_size": 20,
        "total_records": 150,
        "total_pages": 8
      }
    }
    ```
