# Test Suite Readiness Declaration (TEST_READY.md)
*TitanPDF Chemical Legal Lookup & Warning System — Comprehensive E2E Verification Suite*

**Date:** 2026-10-15  
**Author:** E2E Test Suite Creator (`test_writer_e2e`)  
**Status:** READY FOR MILESTONE IMPLEMENTATION VERIFICATION  
**Target Suite:** `tests/verify_legal_integration.py`  
**Infrastructure Spec:** `TEST_INFRA.md`  

---

## 1. Executive Summary

The end-to-end testing suite for the Chemical Legal Lookup & Warning system in TitanPDF has been successfully authored, syntax-verified, and benchmarked. It implements **49 comprehensive opaque-box test cases** organized into 4 strict testing tiers:
- **Tier 1 (Feature Coverage)**: 19 test cases
- **Tier 2 (Boundary & Corner Cases)**: 13 test cases
- **Tier 3 (Cross-Feature Combinations)**: 9 test cases
- **Tier 4 (Real-World Workloads & Latency SLA)**: 8 test cases

The suite operates as an independent test oracle, requiring no mocks for legal data. It issues real network requests against `http://127.0.0.1:8888` (or uses `TestClient` in headless environments), asserts strict mathematical oracles (CAS checksums, Vietnamese dotted threshold parsing, Unicode NFKD diacritics removal), and validates OOXML Word documents for the Section 3 GHS table.

---

## 2. Test Catalog & Feature Mapping

### Tier 1: Feature Coverage (19 Tests)
| Test Identifier | Method / Feature | Scope |
|---|---|---|
| `test_01_catalog_overview_stats` | `GET /api/legal/catalog` | Total records == 2,191; unique CAS >= 1,700 |
| `test_02_catalog_sources_complete` | `GET /api/legal/catalog` | Sources include `ND24`, `ND28`, `QCVN01` with positive counts |
| `test_03_catalog_sections_and_subgroups` | `GET /api/legal/catalog` | All 14 statutory annexes and appendices present |
| `test_04_cas_search_toluene` | `GET /api/legal/search?q=108-88-3` | Toluene matched in ND24 and ND28 |
| `test_05_cas_search_acetone` | `GET /api/legal/search?q=67-64-1` | Acetone matched in ND24 and ND28 |
| `test_06_cas_search_sulfuric_acid` | `GET /api/legal/search?q=7664-93-9` | Sulfuric acid matched in ND24 and ND28 |
| `test_07_cas_search_methanol` | `GET /api/legal/search?q=67-56-1` | Methanol matched across 3 ND24 annexes |
| `test_08_search_chemical_name_vietnamese` | `GET /api/legal/search?q=Toluene` | Name query matches CAS 108-88-3 |
| `test_09_search_chemical_name_english` | `GET /api/legal/search?q=Methyl benzene` | Scientific name matches CAS 108-88-3 |
| `test_10_unaccented_search_thuy_ngan` | `GET /api/legal/search?q=thuy ngan` | Stripped diacritics query matches "Thủy ngân" |
| `test_11_unaccented_search_axit_sunfuric` | `GET /api/legal/search?q=axit sunfuric` | Unaccented query matches CAS 7664-93-9 |
| `test_12_multitoken_search_conjunction` | `GET /api/legal/search?q=toluen nd24` | Token conjunction returns only ND24 records |
| `test_13_batch_match_cas_numbers` | `POST /api/legal/match` | Batch CAS list `["108-88-3", "67-64-1", "7664-93-9"]` |
| `test_14_batch_match_ingredients` | `POST /api/legal/match` | Full formulation list with names, CAS, concentrations |
| `test_15_item_type_raw_material_filter` | `GET /api/msds/chemicals?item_type=raw_material` | Filters inventory for Raw Materials only |
| `test_16_item_type_finished_product_filter` | `GET /api/msds/chemicals?item_type=finished_product` | Filters inventory for Finished Products only |
| `test_17_word_docx_section3_table_presence` | `MSDSSafetyCardExporter.generate_safety_card_docx` | Output Word file contains "MỤC 3 GHS" table |
| `test_18_word_docx_section3_four_columns` | `MSDSSafetyCardExporter.generate_safety_card_docx` | 4 exact columns: Name, CAS, %, Checksum Status |
| `test_19_legal_catalog_export_excel` | `GET /api/legal/export` | Generates valid .xlsx binary spreadsheet |

### Tier 2: Boundary & Corner Cases (13 Tests)
| Test Identifier | Boundary Condition Tested |
|---|---|
| `test_20_multi_cas_extraction_raw_string` | Multiple CAS numbers in string (`20654-88-0 7637-07-2`) |
| `test_21_multi_cas_mixed_isomers` | Complex isomer strings (`528-29-0 (o-) 99-65-0 (m-) ...`) |
| `test_22_cas_whitespace_normalization` | Internal whitespace around hyphens (`25547- 51-7`, ` 108 - 88 - 3 `) |
| `test_23_cas_checksum_valid_oracle` | International CAS checksum validation across 8 authentic chemicals |
| `test_24_cas_checksum_invalid_oracle` | Checksum rejection on 6 single-digit corrupted CAS numbers |
| `test_25_cas_checksum_malformed_inputs` | Malformed strings (`not-a-cas`, `123-45`, `ABC`, `""`) |
| `test_26_unknown_nonexistent_cas_search` | Unknown CAS (`99999-99-9`) returns empty list cleanly with HTTP 200 |
| `test_27_empty_search_query` | Query `q=""` returns standard paginated catalog without 500 |
| `test_28_whitespace_search_query` | Query `q="   "` returns standard paginated catalog without 500 |
| `test_29_special_chars_sql_and_regex_injection` | SQL injection and ReDoS strings handled securely |
| `test_30_threshold_conversion_dotted_thousands` | Dotted thousands parsing (`5.000` -> 5000.0, `50.000` -> 50000.0) |
| `test_31_threshold_conversion_millions_and_small` | Large and small thresholds (`5.000.000` -> 5,000,000.0, `200` -> 200.0) |
| `test_32_diacritics_variations_case_and_accents` | Uppercase, lowercase, accented, unaccented return consistent results |

### Tier 3: Cross-Feature Combinations (9 Tests)
| Test Identifier | Cross-Feature Interaction |
|---|---|
| `test_33_multi_filter_source_and_section` | `q=toluen` combined with `source_id=ND24` and `section_id=ND24-PL-I` |
| `test_34_source_filter_strict_exclusion` | `source_id=QCVN01` strictly excludes ND24 and ND28 records |
| `test_35_section_filter_strict_exclusion` | `section_id=ND28-IV-C` strictly returns Industrial Precursor Group 2 |
| `test_36_mixed_regulated_unregulated_match` | Batch input with both regulated (Toluene, Sulfuric acid) and unregulated (Water) |
| `test_37_mixed_match_counts_and_flags` | Batch output accurately sets `total_checked` and `is_regulated` |
| `test_38_pagination_disjoint_pages` | Page 1 and Page 2 contain mutually disjoint subsets of items |
| `test_39_pagination_out_of_bounds` | Out-of-bounds page (`page=99999`) returns empty array with HTTP 200 |
| `test_40_msds_inventory_item_type_separation` | Strict disjointness between Raw Materials and Finished Products |
| `test_41_msds_detail_legal_compliance_overlay` | Chemical detail includes composition items with legal compliance data |

### Tier 4: Real-World Workloads & Latency SLA (8 Tests)
| Test Identifier | Real-World Workload / Benchmark |
|---|---|
| `test_42_key_chemical_toluene_statutory_profile` | Toluen (108-88-3) spanning NĐ 24 (PL I, III) and NĐ 28 (PL IV-C) |
| `test_43_key_chemical_sulfuric_acid_statutory_profile` | Axit sunfuric (7664-93-9) spanning NĐ 24 (PL I, III) and NĐ 28 (PL IV-C) |
| `test_44_key_chemical_acetone_statutory_profile` | Axeton (67-64-1) spanning NĐ 24 (PL III) and NĐ 28 (PL IV-C) |
| `test_45_key_chemical_methanol_statutory_profile` | Metanol (67-56-1) spanning NĐ 24 (PL I, III, IV-A) |
| `test_46_real_world_thinner_formulation_match` | Real 5-component industrial NC Thinner solvent formulation |
| `test_47_latency_sla_search_50_iterations` | 50 consecutive search calls, assert latency < 500ms |
| `test_48_latency_sla_match_50_iterations` | 50 consecutive match calls, assert latency < 500ms |
| `test_49_concurrent_stress_10_threads` | 10 concurrent threads query catalog and match simultaneously |

---

## 3. Initial Baseline Run Results

At initial baseline run (before Milestone 1 implementation):
- **Total Tests:** 49
- **Passing:** 13 (algorithmic CAS normalizers, international CAS checksum validators, dotted threshold parsers, and Word Section 3 GHS table generator)
- **Failing (Expected TDD Baseline):** 36 (failing with HTTP 404/405 due to unmounted `/api/legal/*` router in `server.py` and missing `item_type` filter in MSDS list)
- **Runtime Errors:** 0

---

## 4. Instructions for Milestone Agents

### For Milestone 1 (Backend Legal Engine & Router):
1. Bundle `legal_catalog.json` into `core/data/legal_catalog.json`.
2. Implement `core/legal_engine.py` and `core/legal_router.py`.
3. Mount `legal_router` in `server.py` with prefix `/api/legal` and alias `/api`.
4. Support `item_type` query filter in `/api/msds/chemicals` and `/api/msds/list`.
5. Run the test suite:
   ```powershell
   python tests/verify_legal_integration.py
   ```
   All Tier 1, Tier 2, Tier 3, and Tier 4 backend tests must turn GREEN.

### For Milestone 2 (Frontend Legal UI & Badges):
1. Connect the frontend tab to `/api/legal/catalog`, `/api/legal/search`, and `/api/legal/match`.
2. Verify Word Export Section 3 GHS Table.

### For Milestone 3 (Final Verification & Delivery):
1. Run full test suite:
   ```powershell
   python tests/verify_legal_integration.py
   ```
2. Verify exit code is `0` with 49/49 passed.
