# Project: Gate Pass & Material Dispatch Studio (Quản Lý Phiếu Xuất Hàng & Vật Tư)

## Architecture
- **Overview**: A professional Gate Pass & Material Dispatch Studio integrated as a first-class tab into TitanPDF (`#gatepass-studio`, `nav-tab-gatepass`).
- **Frontend Layer**:
  - Main tab on navbar: `nav-tab-gatepass` (`static/index.html`, `static/vip_editor.js:switchMainTab`).
  - Viewport container: `#gatepass-studio-view` containing 4 functional areas:
    1. KPI Dashboard & Analytics (`#gp-dashboard-section`): Metric cards (Total slips, Total KG, Cartons/Packages, Clients/Vehicles) and Chart.js visualizations (Timeline area/bar chart and Customer doughnut chart).
    2. Scan & Vision AI Studio (`#gp-scan-studio-section`): Dual-column layout. Left: Interactive canvas with zoom, pan, rotate (0/90/180/270), queue strip, and proof drawer. Right: Dispatch type selector, metadata form, and dynamic bilingual CN-VN item table with inline editing and auto-summation.
    3. Audit & Match Engine (`#gp-audit-section`): Upload proof photos (vehicle, license plate, packages) and run AI cross-matching (plate matching, signature validation).
    4. History & Export (`#gp-history-section`): Filterable history table, Split-view detail modal with zoomable slip preview, A4/A5 formatted printing, and Google Drive open links.
  - Offline-first vendored Chart.js library: `static/libs/chart.umd.min.js`.
  - Dedicated modular styling: `static/gatepass_studio.css`.
  - Dedicated controller script: `static/gatepass_studio.js`.
- **Backend Layer**:
  - REST Router: `core/gatepass_router.py` mounted at `/api/gatepass` in `server.py`.
  - Service Layer: `core/gatepass_service.py` handling:
    1. DeepSeek Vision OCR extraction (`DeepSeek-V4.1-Flash` with `deepseek-chat` fallback, `temperature: 0.1`).
    2. Proof audit and cross-matching logic.
    3. Local-First SQLite WAL cache (`data/gatepass_slips.db`) for instant queries (<15ms).
    4. Secure proxy bridge to Google Apps Script Web App (`AKfycbzo5YQiI5DM0KEDRpTIbxDDY_2Nwfs4NP1Vfa5MyuJPNqb8x4EkhVzZD5pso7ueAWiS5w`) syncing to Google Sheet (`15Z3HA7Lm2pJU3GmfzdDq4ZfOKVYJoYJ_SYIT3pAM_ug`) and Google Drive storage.
- **Security & RBAC Layer**:
  - Registered as Tool #36 in `data/guest_permissions.json`, `core/auth_rbac.py`, `static/index.html` (Security Modal Tab 3, Group 6), and `static/app.js`.
  - Guest mode: Read-only access to Dashboard, History, Split Detail Modal, and Print. Mutation actions (Scan, Save, Edit, Delete, Sync) disabled and protected with `require_owner` (HTTP 403). API Key masked (`••••••••••••••••`).
  - Owner mode: Unrestricted access.

## Code Layout
- `core/gatepass_service.py` - Core business logic, SQLite cache, DeepSeek Vision OCR, and GAS proxy.
- `core/gatepass_router.py` - FastAPI endpoints for Gate Pass Studio.
- `static/gatepass_studio.css` - Custom styling for Gate Pass UI, dual-column studio, HUD, and print media.
- `static/gatepass_studio.js` - Client-side state manager, CanvasRotator, QueueManager, Chart.js binder, and inline editor.
- `static/libs/chart.umd.min.js` - Vendored Chart.js library for offline operation.
- `data/gatepass_slips.db` - SQLite WAL cache for instant dashboard and history responses.
- `tests/test_gatepass_service_suite.py` - Python backend unit and integration test suite.
- `tests/test_gatepass_e2e_suite.py` - Playwright browser E2E test suite.
- Modified existing files:
  - `server.py`: Mount `/api/gatepass` router.
  - `core/auth_rbac.py`: Register tool `gatepass-studio` in `DEFAULT_GUEST_PERMISSIONS`.
  - `data/guest_permissions.json`: Register tool `gatepass-studio` as tool #36.
  - `static/index.html`: Add `#nav-tab-gatepass`, `#gatepass-studio-view`, and Tool #36 checkbox in Security Modal Tab 3.
  - `static/vip_editor.js`: Support tab switching for `gatepass` / `gatepass-studio` and hash routing.
  - `static/app.js`: Register in `TOOLS` array, canonical map, and guest permissions styling.
  - `tests/test_frontend_rbac_suite.py`: Update assertion `assert tool_count == 36`.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Navigation Bar Tab | `#nav-tab-gatepass` with icon, label `Phiếu Xuất & Vật Tư`, badge `#nav-gatepass-count-badge` | M3 | survey |
| 2 | Hash Router & Switching | `switchMainTab('gatepass')` showing `#gatepass-studio-view` and `#gatepass-studio` URL hash bridge | M3 | survey |
| 3 | KPI Dashboard Cards | Total slips, total weight KG, cartons/packages, active clients & vehicles | M3 | survey |
| 4 | KPI Chart.js Visualizations | Timeline area/bar chart (KG/Passes/Units modes) & Customer doughnut chart | M3 | survey |
| 5 | Dual-Column Scan Studio | Split-screen: Left interactive canvas & Queue strip, Right metadata form & items table | M3 | survey |
| 6 | Interactive Canvas HUD | Zoom in/out/reset, rotate (0/90/180/270), high-contrast text filter, clipboard paste | M3 | survey |
| 7 | Multi-Slip Queue Strip | Horizontal scroll strip with thumbnail previews, status badges, and sequential navigation | M3 | survey |
| 8 | Proof Photos Drawer | Attach vehicle, license plate, and cargo proof photos with preview | M3 | survey |
| 9 | Dispatch Type Selector | "Xuất hàng thành phẩm" vs "Xuất vật tư ra công" with automatic rule adjustment | M3 | survey |
| 10 | Bilingual CN-VN Items Table | STT, bilingual item name, specs, packages/boxes, notes with inline edit and row addition/deletion | M3 | survey |
| 11 | Auto-Summation Engine | Dynamic recalculation of total KG, total cartons/packages, and live formula display | M3 | survey |
| 12 | DeepSeek Vision OCR Engine | Structured JSON extraction of header, footer signatures, and bilingual items table (`DeepSeek-V4.1-Flash`) | M2 | survey |
| 13 | Audit & Match Engine | AI verification of signature validity and license plate matching between proof image and slip | M2 | survey |
| 14 | SQLite WAL Local Cache | Instant responses (<15ms) for dashboard KPI and history queries in `data/gatepass_slips.db` | M1 | survey |
| 15 | Google Apps Script Bridge | Secure FastAPI proxy to GAS Web App (`AKfycbzo...`) with timeout and error handling | M1 | survey |
| 16 | Google Sheet Synchronization | Sync 19 standard columns to Google Sheet `15Z3HA7Lm2pJU3GmfzdDq4ZfOKVYJoYJ_SYIT3pAM_ug` | M1 | survey |
| 17 | Google Drive Image Upload | Upload original slip and proof images to dedicated Drive folder and store URLs | M1 | survey |
| 18 | History Table & Filters | Date presets (Today, 7 days, Month, Custom), instant search by slip number, plate, or customer | M3 | survey |
| 19 | Split-View Detail Modal | Modal showing zoomable slip photo on left and full metadata/items on right with fullscreen mode | M3 | survey |
| 20 | A4/A5 Print Engine | Clean print window / `@media print` formatting for A4 dispatch slips and A5 material pass | M3 | survey |
| 21 | Granular RBAC Registration | Tool #36 in `data/guest_permissions.json`, `auth_rbac.py`, and Security Modal Tab 3 | M4 | survey |
| 22 | Guest Mode Protection | Read-only access to Dashboard/History/Detail/Print; mutation actions locked; API key masked | M4 | survey |
| 23 | Owner Mode Privileges | Full permissions to scan, edit, delete, and sync with cloud | M4 | survey |
| 24 | Automated E2E & Unit Test Suite | Comprehensive Playwright E2E and Python test suites (Tiers 1-5) verifying full lifecycle | M5 | survey |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Backend Service & Cloud Proxy | `core/gatepass_service.py`, `core/gatepass_router.py`, SQLite WAL cache, GAS Web App proxy, Sheet sync | none | DONE |
| 2 | M2: DeepSeek Vision AI Engine | Header/footer extraction, bilingual CN-VN table parser, proof audit & plate cross-matching | M1 | PLANNED |
| 3 | M3: Gate Pass Studio Frontend UI | `#nav-tab-gatepass`, `#gatepass-studio-view`, CSS, JS controller, Chart.js, Split-screen, print engine | M1, M2 | PLANNED |
| 4 | M4: RBAC & Guest Mode Integration | Register Tool #36 in RBAC files, enforce Guest read-only vs Owner full access, update tests | M1, M3 | PLANNED |
| 5 | M5: Automated Verification & E2E Testing | Playwright E2E test suite + Python integration tests, 100% PASS on all suites | M1, M2, M3, M4 | PLANNED |

## Interface Contracts
### `core/gatepass_service.py` ↔ `core/gatepass_router.py`
- `GatePassService.get_dashboard_stats(period: Optional[str] = None) -> Dict[str, Any]`
- `GatePassService.list_passes(filter_query: Optional[str], date_from: Optional[str], date_to: Optional[str], page: int = 1, page_size: int = 50) -> Dict[str, Any]`
- `GatePassService.get_pass_detail(so_phieu: str) -> Optional[Dict[str, Any]]`
- `GatePassService.save_pass(pass_data: Dict[str, Any], sync_cloud: bool = True) -> Dict[str, Any]`
- `GatePassService.delete_pass(so_phieu: str) -> bool`
- `GatePassService.extract_from_image(image_bytes: bytes, filename: str) -> Dict[str, Any]`
- `GatePassService.audit_proof_match(slip_data: Dict[str, Any], proof_images: List[bytes]) -> Dict[str, Any]`
- `GatePassService.sync_to_google_sheet(pass_data: Dict[str, Any]) -> Dict[str, Any]`
- `GatePassService.upload_image_to_drive(image_bytes: bytes, filename: str) -> str`

### Backend REST API ↔ Frontend JavaScript
- `GET /api/gatepass/dashboard`: Returns summary stats (`total_passes`, `total_weight_kg`, `total_packages`, `total_cartons`, `active_customers`, `active_vehicles`) and Chart.js datasets (`timeline`, `top_customers`).
- `GET /api/gatepass/history`: Returns paginated list of dispatch slips with search and date filters.
- `GET /api/gatepass/detail/{so_phieu}`: Returns full slip details, line items, audit logs, and image URLs.
- `POST /api/gatepass/ocr-scan`: Accepts multipart image file, returns extracted JSON structure.
- `POST /api/gatepass/audit-match`: Accepts slip metadata + proof image files, returns match evaluation.
- `POST /api/gatepass/save`: Accepts complete slip object, writes to SQLite WAL cache and dispatches GAS sync. Protected by `require_owner` for mutations.
- `DELETE /api/gatepass/{so_phieu}`: Deletes slip from local cache and syncs deletion. Protected by `require_owner`.
- `GET /api/gatepass/print/{so_phieu}`: Returns optimized printable HTML view (A4/A5).
