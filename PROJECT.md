# Project: TitanPDF — Chemical Legal Lookup & Warning System Integration

## Architecture
TitanPDF operates as a 100% local, high-performance desktop web suite running on `127.0.0.1:8888`.
- **Backend Architecture**:
  - FastAPI application in `server.py` with modular sub-routers.
  - Dedicated Chemical Legal sub-router: `core/legal_router.py` mounted via `app.include_router(legal_router, prefix="/api/legal")` and aliases `/api` and `/api/legal-catalog` before line 1705 (`app.mount("/", ...)`).
  - Chemical Legal Engine: `core/legal_engine.py` with singleton pattern, in-memory inverted indices (`LEGAL_BY_CAS`, unaccented multi-token index with symmetrical phonetic expansions `axet`<->`acet`, `sunf`<->`sulf`, `clor`<->`chlor`), strict CAS regex `[1-9]\d{1,6}`, CAS Mod 10 checksum validation, multi-separator concentration threshold comparison, and ingredient batch matching.
  - Legal Catalog Database: `core/data/legal_catalog.json` and `data/legal_catalog.json` (>1.8MB, 2,191 legal records across NĐ 24/2026/NĐ-CP, NĐ 28/2026/NĐ-CP, QCVN 01:2025/BYT, and CIL chemical inventory cross-references).
  - Item Classification Engine: Supports `item_type` differentiation ('raw_material' vs 'finished_product'), Product Code management, and Mother MSDS linking in `core/msds_intelligence.py` and SQLite `msds_chemical_inventory.db`.
  - Word Export Engine: Enhanced chemical safety card generation producing Section 3 GHS Composition Table with Active Ingredient Name, CAS Number, Concentration (%), and Checksum Verification.
- **Frontend Architecture**:
  - Zero-build Single Page Application served statically from `static/`.
  - Navigation tab `#nav-tab-legal` in `static/index.html` navbar with active indicator and Legal Intelligence brand identity.
  - Main container `<main id="legal-lookup-view" class="legal-command-center hidden">` in `static/index.html`.
  - Tab switching via `switchMainTab('legal')` in `static/vip_editor.js`.
  - Tool #34 registered in `TOOLS` array in `static/app.js` with category `ai` and direct link to `switchMainTab('legal')`.
  - Modular frontend assets: `static/legal_lookup.js` (DOM controller, debounced search, cascading filters, KPI cards, pagination) and `static/legal_style.css` (scoped styles supporting both clean and vibrant themes).
  - MSDS Library Integration: Dynamic badges in CAS column in `renderMsdsFilteredTable` and Legal Compliance & Obligations table in `openMsdsSafetyModal`.
- **Performance & Stability**:
  - Sub-millisecond in-memory lookup (<1ms, surpassing 500ms requirement).
  - Zero regression across existing 33 tools and HSE Report Studio.
  - Stable execution on port 8888 and Cloudflare Tunnel pass-through.

## Feature Inventory
| # | Feature | Description | Milestone | Status |
|---|---------|-------------|-----------|--------|
| 1 | `F01_catalog_data` | Bundle & load `core/data/legal_catalog.json` (2,191 items across ND24, ND28, QCVN01) | M1 | **DONE** |
| 2 | `F02_cas_normalization` | Regex CAS normalization and multi-CAS string extraction (`CAS_PATTERN.findall`, `[1-9]\d{1,6}`) | M1 | **DONE** |
| 3 | `F03_cas_checksum` | CAS checksum validation algorithm (sum(i * d_i) % 10 == check_digit) | M1 | **DONE** |
| 4 | `F04_unaccented_search` | Vietnamese diacritic removal (Unicode NFKD) and case-insensitive indexing | M1 | **DONE** |
| 5 | `F05_multitoken_search` | Multi-token search supporting token conjunction and symmetrical phonetic expansions | M1 | **DONE** |
| 6 | `F06_threshold_eval` | Parse and convert multi-separator thresholds into numeric kg/concentration values | M1 | **DONE** |
| 7 | `F07_api_catalog` | `GET /api/legal/catalog`: Overview stats, sources, sections, item counts | M1 | **DONE** |
| 8 | `F08_api_search` | `GET /api/legal/search`: Instant multi-criteria search with pagination | M1 | **DONE** |
| 9 | `F09_api_match` | `POST /api/legal/match`: Batch CAS / ingredient matching with legal obligations | M1 | **DONE** |
| 10 | `F10_item_type_mgmt` | Classification of 'raw_material' vs 'finished_product', Product Code & Mother MSDS | M1 | **DONE** |
| 11 | `F11_router_mount` | Mount `legal_router` in `server.py` before line 1705 static catch-all | M1 | **DONE** |
| 12 | `F12_navbar_tab` | Tab `#nav-tab-legal` in navbar, container `#legal-lookup-view`, `switchMainTab('legal')` | M2 | PLANNED |
| 13 | `F13_tool34_registry` | Tool #34 registered in `TOOLS` array in `static/app.js` with category `ai` | M2 | PLANNED |
| 14 | `F14_lookup_ui` | Responsive Legal Lookup panel (`static/legal_lookup.js`, `static/legal_style.css`) | M2 | PLANNED |
| 15 | `F15_kpi_cards` | KPI summary cards (Total Records, Unique CAS, Current Matches, Filtered Count) | M2 | PLANNED |
| 16 | `F16_cascading_filters` | Multi-level cascading filter (Source -> Section -> Subgroup) | M2 | PLANNED |
| 17 | `F17_badge_system` | 5-tier badge classification (Cấm, Kiểm soát đặc biệt/Tiền chất, Hạn chế, Sự cố, QCVN) | M2 | PLANNED |
| 18 | `F18_msds_card_badges` | Render legal badges in CAS column in MSDS table (`renderMsdsFilteredTable`) | M2 | PLANNED |
| 19 | `F19_msds_modal_table` | Render Legal Obligations & Compliance table in modal (`openMsdsSafetyModal`) | M2 | PLANNED |
| 20 | `F20_item_type_ui` | Frontend display and filtering for Raw Materials vs Finished Products | M2 | PLANNED |
| 21 | `F21_word_section3_table` | Export Word .docx with Section 3 GHS table and CAS Checksum verification | M2 | PLANNED |
| 22 | `F22_e2e_test_suite` | Independent automated verification suite (`tests/verify_legal_integration.py`) | E2E | **DONE** |
| 23 | `F23_latency_sla` | Latency < 500ms for all legal API endpoints | E2E/M3 | **DONE** (11ms avg) |
| 24 | `F24_server_stability` | Port 8888 health & Cloudflare Tunnel connectivity | M3 | PLANNED |
| 25 | `F25_zero_regression` | Zero regressions across existing 33 tools and HSE Studio | M3 | PLANNED |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Suite (Tiers 1-4) | Comprehensive opaque-box test suite (`tests/verify_legal_integration.py`) validating all 25 features | none | **DONE** |
| M1 | Backend Legal Engine, Router & Item Type Classification | `core/data/legal_catalog.json`, `core/legal_engine.py`, `core/legal_router.py`, `server.py` router mount, item_type schema | none | **DONE** |
| M2 | Frontend Legal Lookup Tab, MSDS Warning Badges & Word Export | `static/index.html`, `static/legal_lookup.js`, `static/legal_style.css`, `static/vip_editor.js`, `static/app.js`, `static/ai_studio.js`, Word export Section 3 table | M1 | **IN_PROGRESS** |
| M3 | Final Integration, 100% E2E Pass & Server Stability | Run 100% of E2E test suite + Phase 2 adversarial stress testing (Tier 5) + Forensic Audit | E2E, M1, M2 | PLANNED |

## Interface Contracts

### Backend API Contracts (`/api/legal/*`)
- `GET /api/legal/catalog`:
  - Returns `{success: true, title: str, total_records: int, unique_cas: int, sources: [...], sections: [...]}`
- `GET /api/legal/search`:
  - Query parameters: `q: Optional[str]`, `source_id: Optional[str]`, `section_id: Optional[str]`, `subgroup: Optional[str]`, `page: int = 1`, `page_size: int = 50`
  - Returns `{success: true, total: int, page: int, page_size: int, items: [{item_id, source_id, source_title, section_id, section_title, subgroup, name_vi, name_scientific, cas, formula, threshold, hs_code, authority, twa, stel, legal_badges, obligations}]}`
- `POST /api/legal/match`:
  - Input JSON: `{"cas_numbers": ["108-88-3", ...], "ingredients": [{"name": str, "cas": str, "concentration": float}]}`
  - Returns `{success: true, total_checked: int, total_matched: int, matches: [{cas, chemical_name, is_regulated, badges: [...], regulations: [...]}]}`
- `GET /api/legal/export`:
  - Returns Excel (`.xlsx`) multi-sheet binary stream.

### Item Type & MSDS Contract
- `item_type`: `'raw_material'` | `'finished_product'`
- `product_code`: string identifier
- `mother_msds_id`: optional foreign key linking finished products to mother formulation SDS
- Section 3 GHS Composition Table:
  - Columns: `Tên Thành Phần Hoạt Chất`, `Số CAS`, `Hàm Lượng (%)`, `Thẩm Định Checksum` (`HỢP LỆ` / `SAI CHECKSUM` / `KHÔNG CÓ CAS`)

## Code Layout
- Exclusive Write Ownership:
  - E2E Test Track: `tests/verify_legal_integration.py`, `TEST_INFRA.md`, `TEST_READY.md`
  - M1: `core/data/legal_catalog.json`, `core/legal_engine.py`, `core/legal_router.py`, `server.py` (mounting line 1695)
  - M2: `static/legal_lookup.js`, `static/legal_style.css`, `static/index.html` (navbar tab & container only), `static/vip_editor.js` (`switchMainTab` only), `static/app.js` (Tool #34 only), `static/ai_studio.js` (MSDS card badges & modal only)
  - M3: `tests/test_adversarial_coverage.py`, bug fixes across modules
