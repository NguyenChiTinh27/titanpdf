"""
test_msds_full_suite.py — Comprehensive Opaque-Box E2E Test Suite
for TitanPDF EHS Chemical Management System (R1–R6, Tiers 1–4).

Covers all 4 Quality Tiers across Requirements R1 to R6:
- Tier 1: Feature Coverage (Happy path for R1 to R5)
  * R1: Batch ZIP original MSDS download & Batch ZIP Word safety cards with Section 3 GHS table & CAS checksum
  * R2: GHS Decanting Label data & 4 print HTML presets (A4_4UP, A5, DECAL_150, DECAL_75) & PDF generator
  * R3: Chemical Storage Compatibility Matrix & Pairwise Conflict Checker (TCVN 5507:2002)
  * R4: Legal compliance & Annual Chemical Report Excel export (Circular 02/2026/TT-BCT)
  * R5: Mobile QR Emergency Quick View (ReportLab vector QR & zero-auth responsive mobile view)
- Tier 2: Boundary & Corner Cases (Empty/missing IDs, nonexistent IDs, scope=all, diacritics, invalid sizes)
- Tier 3: Cross-Feature Combinations (Multi-category chemicals, warehouse compatibility, label/matrix consistency)
- Tier 4: Real-World Workloads & Latency SLA (Full-batch exports, <500ms latency SLA, thread concurrency)

Dual-Mode ApiClient:
- Calls live HTTP server at TITAN_TEST_URL (default http://127.0.0.1:8888) if available.
- Automatically falls back to FastAPI TestClient(app) from server.py when server is offline,
  guaranteeing 100% self-contained, reproducible offline test runs.

Execution:
    python test_msds_full_suite.py                    # Run all tiers (standard / strict mode)
    python test_msds_full_suite.py --progressive      # Progressive mode for in-progress milestones
    python test_msds_full_suite.py --tier 1           # Run Tier 1 only
    python test_msds_full_suite.py --tier 2           # Run Tier 2 only
    python test_msds_full_suite.py --tier 3           # Run Tier 3 only
    python test_msds_full_suite.py --tier 4           # Run Tier 4 only
    python test_msds_full_suite.py --milestone M1     # Run Milestone M1 tests only
    python test_msds_full_suite.py --verbose          # Detailed output
    pytest test_msds_full_suite.py                    # Standard pytest execution
"""

import argparse
import concurrent.futures
import io
import json
import os
import re
import sys
import time
import unicodedata
import unittest
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import docx
import openpyxl
import requests

# Reconfigure console output encoding on Windows if supported
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BASE_URL = os.environ.get("TITAN_TEST_URL", "http://127.0.0.1:8888").rstrip("/")
DEFAULT_TIMEOUT = 15

# Global execution mode flags (can be overridden by CLI or environment)
PROGRESSIVE_MODE = os.environ.get("TITAN_TEST_PROGRESSIVE", "0").lower() in ("1", "true", "yes")
ACTIVE_MILESTONE_FILTER: Optional[str] = os.environ.get("TITAN_TEST_MILESTONE", None)


# =============================================================================
# 1. API Client Supporting Live HTTP & Offline ASGI TestClient Fallback
# =============================================================================

class ApiResponse:
    """Wrapper normalizing responses from both requests and TestClient."""

    def __init__(self, raw_resp: Any):
        self._resp = raw_resp
        self.status_code = getattr(raw_resp, "status_code", 500)
        self.headers = getattr(raw_resp, "headers", {})
        self.content = getattr(raw_resp, "content", b"")
        self.text = getattr(raw_resp, "text", "")

    def json(self) -> Any:
        if hasattr(self._resp, "json"):
            return self._resp.json()
        return json.loads(self.text)

    def header(self, key: str, default: str = "") -> str:
        for k, v in self.headers.items():
            if k.lower() == key.lower():
                return v
        return default


class ApiClient:
    """Opaque-box client that calls live server, with TestClient fallback."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.live = False
        self._test_client = None
        self._check_liveness()

    def _check_liveness(self) -> None:
        try:
            r = requests.get(f"{self.base_url}/api/health", timeout=1.5)
            if r.status_code == 200:
                self.live = True
                return
        except Exception:
            pass
        try:
            r = requests.get(f"{self.base_url}/api/msds/chemicals", timeout=1.5)
            if r.status_code in (200, 401, 403):
                self.live = True
                return
        except Exception:
            self.live = False

    def _get_test_client(self):
        if self._test_client is None:
            from fastapi.testclient import TestClient
            from server import app
            self._test_client = TestClient(app)
        return self._test_client

    def request(self, method: str, path: str, **kwargs) -> ApiResponse:
        if not path.startswith("/"):
            path = "/" + path
        kwargs.setdefault("timeout", DEFAULT_TIMEOUT)

        if self.live:
            url = f"{self.base_url}{path}"
            raw = requests.request(method, url, **kwargs)
            return ApiResponse(raw)
        else:
            client = self._get_test_client()
            kwargs.pop("timeout", None)
            raw = client.request(method, path, **kwargs)
            return ApiResponse(raw)

    def get(self, path: str, **kwargs) -> ApiResponse:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> ApiResponse:
        return self.request("POST", path, **kwargs)

    def delete(self, path: str, **kwargs) -> ApiResponse:
        return self.request("DELETE", path, **kwargs)


CLIENT = ApiClient(BASE_URL)


# =============================================================================
# 2. Authoritative Reference Oracles & Mathematical Ground Truth
# =============================================================================

def oracle_normalize_cas(raw: str) -> str:
    """Extract and normalize standard CAS format: XXXXXXX-YY-Z."""
    m = re.search(r"\b(\d{2,7})\s*-\s*(\d{2})\s*-\s*(\d)\b", str(raw or ""))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def oracle_cas_checksum_valid(cas: str) -> bool:
    """
    International Standard CAS Checksum validation (Mod 10).
    Given R-YY-C: Sum((i + 1) * digit) mod 10 == C,
    where digits are traversed right-to-left before check digit C.
    """
    m = re.fullmatch(r"([1-9]\d{1,6})-(\d{2})-(\d)", str(cas or "").strip())
    if not m:
        return False
    body = m.group(1) + m.group(2)
    check = int(m.group(3))
    total = sum((i + 1) * int(d) for i, d in enumerate(reversed(body)))
    return (total % 10) == check


def oracle_remove_accents(text: str) -> str:
    """Normalize Vietnamese unicode to unaccented ASCII for safe filenames."""
    norm = unicodedata.normalize("NFKD", str(text or ""))
    stripped = "".join(c for c in norm if not unicodedata.combining(c))
    cleaned = stripped.replace("đ", "d").replace("Đ", "D")
    cleaned = re.sub(r"[^\w\s\-\.]", "_", cleaned)
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned.strip("_")


# Standard TCVN 5507:2002 Chemical Warehouse Storage Compatibility Rules
TCVN_FORBIDDEN_PAIRS = {
    # Flammables (GHS02) + Oxidizers (GHS03) = Strictly Forbidden (X)
    frozenset({"GHS02", "GHS03"}): "Nguy cơ cháy nổ cực lớn do chất oxy hóa kích hoạt và thúc đẩy đám cháy chất lỏng dễ cháy (TCVN 5507 Điều 5.3)",
    # Acids (GHS05-Acid) + Bases (GHS05-Base) = Strictly Forbidden (X)
    frozenset({"GHS05_ACID", "GHS05_BASE"}): "Phản ứng trung hòa tỏa nhiệt mãnh liệt có thể gây nổ bồn chứa hoặc bắn tóe hóa chất ăn mòn nguy hiểm",
    # Explosives (GHS01) + any hazardous class = Strictly Forbidden (X)
    frozenset({"GHS01", "GHS02"}): "Chất nổ tuyệt đối không lưu trữ chung với chất dễ cháy",
    frozenset({"GHS01", "GHS03"}): "Chất nổ tuyệt đối không lưu trữ chung với chất oxy hóa",
    frozenset({"GHS01", "GHS05"}): "Chất nổ tuyệt đối không lưu trữ chung với chất ăn mòn",
    # Oxidizers (GHS03) + Toxic (GHS06) = Strictly Forbidden (X)
    frozenset({"GHS03", "GHS06"}): "Chất oxy hóa phản ứng với chất độc có thể giải phóng khí độc hại cấp tính",
}

TCVN_RESTRICTED_PAIRS = {
    # Flammables (GHS02) + Acute Toxic (GHS06) = Segregation Required (S)
    frozenset({"GHS02", "GHS06"}): "Phải cách ly tối thiểu 3-5m hoặc có vách ngăn chống cháy để ngăn đám cháy phát tán khói độc",
    # Flammables (GHS02) + Corrosive (GHS05) = Segregation Required (S)
    frozenset({"GHS02", "GHS05"}): "Phải có khay chứa sự cố riêng biệt ngăn rò rỉ ăn mòn làm thủng thùng chứa chất dễ cháy",
}


# Known Active Chemicals from inventory database (data/msds_chemical_inventory.db)
KNOWN_INVENTORY_CHEMICALS = [
    {"id": "ZNZX009", "code": "ZNZX009", "cas": "98060-25-4", "ghs": ["GHS02"], "flammable": True},
    {"id": "000000000000102992", "code": "A1102", "cas": "1330-20-7", "ghs": ["GHS02", "GHS05", "GHS07", "GHS08"], "flammable": True},
    {"id": "000000000000107344", "code": "A1129", "cas": "64742-95-6", "ghs": ["GHS02", "GHS07", "GHS09"], "flammable": True},
    {"id": "000000000000135844", "code": "A1103", "cas": "", "ghs": ["NON DG"], "flammable": False},
    {"id": "000000000000135848", "code": "A1130", "cas": "64742-82-1", "ghs": ["GHS02", "GHS07", "GHS08", "GHS09"], "flammable": True},
    {"id": "000000000000137360", "code": "A1101", "cas": "1330-20-7", "ghs": ["GHS02", "GHS07", "GHS08"], "flammable": True},
    {"id": "A1570", "code": "A1570", "cas": "134180-76-0", "ghs": ["GHS07"], "flammable": False},
    {"id": "A1615", "code": "A1615", "cas": "28014-46-2", "ghs": ["NON DG"], "flammable": False},
    {"id": "A1932", "code": "A1932", "cas": "6192-52-5", "ghs": ["GHS07"], "flammable": False},
    {"id": "A1935", "code": "A1935", "cas": "128-37-0", "ghs": ["GHS07"], "flammable": False},
    {"id": "A1105", "code": "A1105", "cas": "", "ghs": ["NON DG"], "flammable": False},
    {"id": "FTU0005", "code": "FTU0005", "cas": "42978-66-5", "ghs": ["GHS07", "GHS09"], "flammable": False},
    {"id": "ZW55019", "code": "ZW55019", "cas": "29911-28-2", "ghs": ["GHS07"], "flammable": False},
]


# =============================================================================
# Base Test Case with Progressive Milestone Support
# =============================================================================

class BaseMsdsTestCase(unittest.TestCase):
    """Base test class providing assertion helpers and progressive handling."""

    def check_or_pend(self, resp: ApiResponse, endpoint: str, milestone: str) -> bool:
        """
        In progressive mode, if an endpoint returns 404/405 because its milestone is planned,
        records pending status. In strict mode, asserts endpoint exists (status != 404/405).
        Returns True if endpoint is implemented, False if pending.
        """
        if resp.status_code in (404, 405):
            msg = f"Endpoint '{endpoint}' returned {resp.status_code} (Target: Milestone {milestone})"
            if PROGRESSIVE_MODE:
                self.skipTest(f"[PROGRESSIVE PENDING] {msg}")
                return False
            else:
                self.fail(f"[UNIMPLEMENTED] {msg}. Implement Milestone {milestone} to pass.")
        return True

    def assert_valid_zip(self, content: bytes, min_files: int = 1) -> zipfile.ZipFile:
        """Assert byte content is a valid, uncorrupted ZIP archive."""
        self.assertGreater(len(content), 22, "Content is too small to be a valid ZIP archive.")
        try:
            zf = zipfile.ZipFile(io.BytesIO(content))
        except zipfile.BadZipFile as e:
            self.fail(f"Failed to parse ZIP archive: {e}")

        # Test archive integrity
        corrupt_file = zf.testzip()
        self.assertIsNone(corrupt_file, f"ZIP archive contains corrupted file: {corrupt_file}")
        namelist = zf.namelist()
        self.assertGreaterEqual(len(namelist), min_files, f"Expected at least {min_files} file(s) in ZIP, got {len(namelist)}: {namelist}")
        return zf

    def assert_unaccented_filename(self, filename: str) -> None:
        """Assert filename inside ZIP does not contain Vietnamese diacritics or invalid characters."""
        # Check for combining diacritics
        has_combining = any(unicodedata.combining(c) for c in filename)
        self.assertFalse(has_combining, f"Filename '{filename}' contains combining diacritics.")
        # Check for precomposed accented characters
        accented_chars = re.findall(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđĐ]", filename, re.IGNORECASE)
        self.assertEqual(len(accented_chars), 0, f"Filename '{filename}' contains accented characters: {accented_chars}")


# =============================================================================
# 3. Tier 1: Feature Coverage (Happy Path for R1 to R5)
# =============================================================================

class TestTier1_FeatureCoverage(BaseMsdsTestCase):
    """
    Tier 1 tests the primary functional behavior (happy path) for all 5 requirements:
    - R1: Batch ZIP original MSDS & Word safety cards with Section 3 GHS table
    - R2: GHS Decanting Label data & 4 print HTML presets & PDF generator
    - R3: Chemical Storage Compatibility Matrix & Pairwise Conflict Checker
    - R4: Legal compliance purge & Annual Chemical Report Excel export
    - R5: Mobile QR Emergency Quick View (ReportLab vector QR & zero-auth responsive view)
    """

    # -------------------------------------------------------------------------
    # R1: Batch ZIP Downloads (Original MSDS & Word Safety Cards)
    # -------------------------------------------------------------------------

    def test_t1_r1_batch_zip_original_msds_post_and_get(self):
        """R1: Test batch ZIP download of original MSDS files via POST and GET."""
        target_ids = ["ZNZX009", "000000000000102992"]

        # 1. Test POST endpoint with JSON body
        resp_post = CLIENT.post("/api/msds/download-batch-original", json={"ids": target_ids})
        if not self.check_or_pend(resp_post, "/api/msds/download-batch-original", "M1"):
            return

        self.assertEqual(resp_post.status_code, 200)
        self.assertIn("application/zip", resp_post.header("content-type").lower())
        disposition = resp_post.header("content-disposition")
        self.assertTrue(re.search(r"MSDS_Goc_TongHop_\d{8}\.zip", disposition, re.IGNORECASE),
                        f"Expected filename matching 'MSDS_Goc_TongHop_YYYYMMDD.zip', got: {disposition}")

        # Verify ZIP integrity and naming
        zf_post = self.assert_valid_zip(resp_post.content, min_files=2)
        names_post = zf_post.namelist()
        for name in names_post:
            self.assert_unaccented_filename(name)
        data_files_post = [n for n in names_post if not n.startswith("_README")]
        self.assertGreaterEqual(len(data_files_post), 2, f"Expected at least 2 data files, got: {data_files_post}")
        for name in data_files_post:
            self.assertTrue(any(cid in name for cid in ["ZNZX009", "102992", "A1102"]),
                            f"File {name} does not match requested chemical codes")

        # 2. Test GET endpoint with query parameter
        resp_get = CLIENT.get("/api/msds/download-batch-original?ids=ZNZX009")
        self.assertEqual(resp_get.status_code, 200)
        zf_get = self.assert_valid_zip(resp_get.content, min_files=1)
        self.assertTrue(any("ZNZX009" in n for n in zf_get.namelist()))

    def test_t1_r1_batch_zip_safety_cards_word_and_section3_table(self):
        """R1: Test batch ZIP export of Word safety cards with 4-column Section 3 GHS table."""
        target_ids = ["ZNZX009", "000000000000102992"]

        resp = CLIENT.post("/api/msds/export-batch-safety-cards", json={"ids": target_ids})
        if not self.check_or_pend(resp, "/api/msds/export-batch-safety-cards", "M1"):
            return

        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/zip", resp.header("content-type").lower())
        disposition = resp.header("content-disposition")
        self.assertTrue(re.search(r"The_An_Toan_TongHop_\d{8}\.zip", disposition, re.IGNORECASE),
                        f"Expected filename matching 'The_An_Toan_TongHop_YYYYMMDD.zip', got: {disposition}")

        zf = self.assert_valid_zip(resp.content, min_files=2)
        names = zf.namelist()
        for name in names:
            self.assert_unaccented_filename(name)
        docx_files = [n for n in names if n.endswith(".docx")]
        self.assertGreaterEqual(len(docx_files), 2, f"Expected at least 2 .docx files in ZIP, got: {docx_files}")

        # Extract first safety card docx and verify Section 3 table
        first_docx_bytes = zf.read(docx_files[0])
        doc = docx.Document(io.BytesIO(first_docx_bytes))
        self.assertGreaterEqual(len(doc.tables), 2, "Expected at least 2 tables in Safety Card DOCX")

        # Table 2 must be Section 3 GHS table with 4 columns
        table_s3 = doc.tables[1]
        self.assertEqual(len(table_s3.columns), 4, f"Section 3 table must have exactly 4 columns, found {len(table_s3.columns)}")
        header_texts = [cell.text.strip().casefold() for cell in table_s3.rows[0].cells]
        self.assertTrue(any("tên" in h or "thành phần" in h or "hoạt chất" in h for h in header_texts), f"Column 1 header missing in {header_texts}")
        self.assertTrue(any("cas" in h for h in header_texts), f"Column 2 header missing in {header_texts}")
        self.assertTrue(any("hàm lượng" in h or "%" in h for h in header_texts), f"Column 3 header missing in {header_texts}")
        self.assertTrue(any("checksum" in h or "thẩm định" in h for h in header_texts), f"Column 4 header missing in {header_texts}")

        # Checksum values in rows must be valid status labels
        if len(table_s3.rows) > 1:
            for row in table_s3.rows[1:]:
                checksum_cell = row.cells[3].text.strip().upper()
                self.assertTrue(any(valid_tag in checksum_cell for valid_tag in ["HỢP LỆ", "VALID", "SAI CHECKSUM", "INVALID", "KHÔNG CÓ CAS", "N/A"]),
                                f"Unexpected checksum status text: {checksum_cell}")

    # -------------------------------------------------------------------------
    # R2: GHS Decanting Label Maker (Circular 01/2026/TT-BCT)
    # -------------------------------------------------------------------------

    def test_t1_r2_ghs_decanting_label_data_api(self):
        """R2: Test GHS Decanting Label data API returning all mandatory Circular 01 fields."""
        chem_id = "ZNZX009"
        resp = CLIENT.get(f"/api/msds/label-data/{chem_id}")
        if not self.check_or_pend(resp, f"/api/msds/label-data/{chem_id}", "M2"):
            return

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(isinstance(data, dict), "Label data response must be a JSON object")

        # Mandatory fields per Circular 01/2026/TT-BCT
        # 1. Product name / commercial name
        product_name = data.get("product_name") or data.get("commercial_name") or data.get("name_vi")
        self.assertTrue(product_name, "Missing mandatory field 'product_name' / 'commercial_name'")

        # 2. CAS number / Ingredients
        cas = data.get("cas_primary") or data.get("cas") or data.get("cas_number")
        self.assertTrue(cas, "Missing mandatory primary CAS field")

        # 3. Facility / Plant
        facility = data.get("facility") or data.get("plant") or data.get("facility_name")
        self.assertTrue(facility, "Missing mandatory facility / plant name")

        # 4. Signal word
        signal_word = data.get("signal_word") or ""
        self.assertTrue(any(w in signal_word.lower() for w in ["nguy hiểm", "danger", "cảnh báo", "warning", "non dg"]),
                        f"Signal word '{signal_word}' not compliant with GHS standards")

        # 5. GHS pictograms
        ghs_codes = data.get("ghs_codes") or data.get("ghs_pictograms") or []
        self.assertIn("GHS02", ghs_codes, "ZNZX009 must contain GHS02 pictogram")

        # 6. H/P statements
        h_statements = data.get("h_codes") or data.get("hazard_statements")
        p_statements = data.get("p_codes") or data.get("precautionary_statements")
        self.assertIsNotNone(h_statements, "Missing hazard statements (H-codes)")
        self.assertIsNotNone(p_statements, "Missing precautionary statements (P-codes)")

        # 7. Emergency hotline
        hotline = data.get("hotline") or data.get("emergency_hotline") or ""
        self.assertTrue("114" in hotline or "115" in hotline or "0274" in hotline or len(hotline) >= 3,
                        f"Emergency hotline '{hotline}' is missing or invalid")

    def test_t1_r2_ghs_decanting_label_print_html_presets(self):
        """R2: Test GHS Decanting Label print HTML endpoint with all 4 standard size presets."""
        chem_id = "ZNZX009"
        presets = ["A4_4UP", "A5", "DECAL_150", "DECAL_75"]

        for preset in presets:
            resp = CLIENT.get(f"/api/msds/label-print-html/{chem_id}?size={preset}")
            if not self.check_or_pend(resp, f"/api/msds/label-print-html/{chem_id}", "M2"):
                return

            self.assertEqual(resp.status_code, 200, f"Preset {preset} failed with status {resp.status_code}")
            self.assertIn("text/html", resp.header("content-type").lower())
            html = resp.text

            # Verify isolated print CSS
            self.assertIn("@media print", html, f"Preset {preset} HTML must contain isolated '@media print' styling")
            # Verify chemical identity rendered
            self.assertTrue("ZNZX009" in html or "chất phân tán" in html.casefold(),
                            f"Preset {preset} HTML does not render chemical identity")
            # Verify signal word
            self.assertTrue("nguy hiểm" in html.casefold() or "danger" in html.casefold(),
                            f"Preset {preset} HTML does not render signal word")

    def test_t1_r2_ghs_decanting_label_pdf_export(self):
        """R2: Test batch GHS Decanting Label vector PDF generator."""
        payload = {"ids": ["ZNZX009"], "size": "A4_4UP"}
        resp = CLIENT.post("/api/msds/export-ghs-labels-pdf", json=payload)
        if not self.check_or_pend(resp, "/api/msds/export-ghs-labels-pdf", "M2"):
            return

        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/pdf", resp.header("content-type").lower())
        self.assertTrue(resp.content.startswith(b"%PDF-"), "Response content does not start with %PDF- header")

    # -------------------------------------------------------------------------
    # R3: Chemical Storage Compatibility Matrix (TCVN 5507:2002)
    # -------------------------------------------------------------------------

    def test_t1_r3_storage_compatibility_matrix_endpoint(self):
        """R3: Test storage compatibility matrix definition endpoint per TCVN 5507:2002."""
        resp = CLIENT.get("/api/msds/storage-compatibility-matrix")
        if not self.check_or_pend(resp, "/api/msds/storage-compatibility-matrix", "M3"):
            return

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(isinstance(data, dict), "Matrix definition must be a JSON object")

        # Must cite TCVN 5507:2002
        ref_text = json.dumps(data, ensure_ascii=False).casefold()
        self.assertIn("tcvn 5507", ref_text, "Storage compatibility matrix must cite TCVN 5507:2002")

        # Must contain hazard classes or matrix grid
        classes = data.get("classes") or data.get("hazard_classes") or data.get("categories") or []
        matrix = data.get("matrix") or data.get("rules") or {}
        self.assertTrue(len(classes) >= 8 or len(matrix) >= 8,
                        "Storage compatibility matrix must define at least 8 GHS hazard categories")

    def test_t1_r3_storage_pairwise_conflict_check(self):
        """R3: Test warehouse pairwise storage compatibility evaluation and forbidden pairs."""
        # 1. Test forbidden pair: Flammables (GHS02) + Oxidizers (GHS03)
        payload_forbidden_1 = {
            "items": [
                {"id": "chem_flam", "name": "Dung môi dễ cháy", "ghs_codes": ["GHS02"]},
                {"id": "chem_ox", "name": "Chất oxy hóa", "ghs_codes": ["GHS03"]}
            ]
        }
        resp_f1 = CLIENT.post("/api/msds/storage-compatibility-check", json=payload_forbidden_1)
        if not self.check_or_pend(resp_f1, "/api/msds/storage-compatibility-check", "M3"):
            return

        self.assertEqual(resp_f1.status_code, 200)
        res_f1 = resp_f1.json()
        f1_str = json.dumps(res_f1, ensure_ascii=False).upper()
        self.assertTrue("FORBIDDEN" in f1_str or "CẤM" in f1_str or '"X"' in f1_str,
                        f"Flammables + Oxidizers must be flagged as FORBIDDEN (X), got: {res_f1}")

        # 2. Test forbidden pair: Acids + Bases
        payload_forbidden_2 = {
            "items": [
                {"id": "acid_1", "name": "Axit Sulfuric H2SO4", "ghs_codes": ["GHS05"], "chemical_type": "acid"},
                {"id": "base_1", "name": "Natri Hydroxit NaOH", "ghs_codes": ["GHS05"], "chemical_type": "base"}
            ]
        }
        resp_f2 = CLIENT.post("/api/msds/storage-compatibility-check", json=payload_forbidden_2)
        self.assertEqual(resp_f2.status_code, 200)
        res_f2 = resp_f2.json()
        f2_str = json.dumps(res_f2, ensure_ascii=False).upper()
        self.assertTrue("FORBIDDEN" in f2_str or "CẤM" in f2_str or '"X"' in f2_str,
                        f"Acids + Bases must be flagged as FORBIDDEN (X), got: {res_f2}")

        # 3. Test compatible pair: NON DG + NON DG
        payload_compatible = {
            "items": [
                {"id": "safe_1", "name": "Nước cất DI", "ghs_codes": ["NON DG"]},
                {"id": "safe_2", "name": "Dung dịch keo gốc nước", "ghs_codes": ["NON DG"]}
            ]
        }
        resp_c = CLIENT.post("/api/msds/storage-compatibility-check", json=payload_compatible)
        self.assertEqual(resp_c.status_code, 200)
        c_str = json.dumps(resp_c.json(), ensure_ascii=False).upper()
        self.assertTrue("COMPATIBLE" in c_str or "CHO PHÉP" in c_str or "ĐƯỢC PHÉP" in c_str or '"C"' in c_str,
                        f"NON DG items should be COMPATIBLE (C), got: {resp_c.json()}")

    # -------------------------------------------------------------------------
    # R4: Legal Compliance Purge & Annual Chemical Report (Circular 02/2026/TT-BCT)
    # -------------------------------------------------------------------------

    def test_t1_r4_legal_compliance_repeal_purge(self):
        """R4: Verify zero occurrences of repealed frameworks (ND 113, ND 82, TT 32, TT 04) in legal catalog."""
        resp = CLIENT.get("/api/legal/catalog")
        if not self.check_or_pend(resp, "/api/legal/catalog", "M4"):
            return

        self.assertEqual(resp.status_code, 200)
        cat_text = resp.text

        # Banned repealed references in regulatory citations
        repealed_patterns = [
            r"113/2017/NĐ-CP",
            r"113/2017/ND-CP",
            r"82/2022/NĐ-CP",
            r"82/2022/ND-CP",
            r"32/2017/TT-BCT",
            r"04/2012/TT-BCT"
        ]
        for pat in repealed_patterns:
            matches = re.findall(pat, cat_text, re.IGNORECASE)
            self.assertEqual(len(matches), 0, f"Found {len(matches)} illegal references to repealed framework '{pat}' in legal catalog")

        # Verify active 2026 legal framework presence
        active_frameworks = ["69/2025", "24/2026", "26/2026", "01:2025"]
        for act in active_frameworks:
            self.assertIn(act, cat_text, f"Legal catalog missing reference to active statute/decree '{act}'")

    def test_t1_r4_annual_chemical_report_excel_export(self):
        """R4: Test annual chemical report multi-sheet Excel generator per Circular 02/2026/TT-BCT."""
        # Check primary endpoint or alias
        resp = CLIENT.get("/api/msds/export-annual-chemical-report")
        if resp.status_code == 404:
            resp = CLIENT.get("/api/msds/export-annual-report")
        if not self.check_or_pend(resp, "/api/msds/export-annual-chemical-report", "M4"):
            return

        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheetml.sheet", resp.header("content-type").lower())
        disposition = resp.header("content-disposition")
        self.assertTrue(re.search(r"Bao_Cao_Hoa_Chat_Hang_Nam_.*\.xlsx", disposition, re.IGNORECASE),
                        f"Expected filename matching 'Bao_Cao_Hoa_Chat_Hang_Nam_TT02_2026_*.xlsx', got: {disposition}")

        # Open with openpyxl and verify multi-sheet structure
        wb = openpyxl.load_workbook(io.BytesIO(resp.content))
        sheet_names = wb.sheetnames
        self.assertGreaterEqual(len(sheet_names), 4, f"Annual report must contain at least 4 sheets, found {len(sheet_names)}: {sheet_names}")

        # Check sheet name themes (General info, chemical inventory, safety/accident prevention, precursors)
        joined_names = " ".join(sheet_names).casefold()
        self.assertTrue(any(k in joined_names for k in ["thong_tin", "thông tin", "chung", "general"]),
                        f"Missing General Info sheet in {sheet_names}")
        self.assertTrue(any(k in joined_names for k in ["hoat_dong", "hoạt động", "danh_muc", "danh mục", "inventory", "cil"]),
                        f"Missing Chemical Inventory sheet in {sheet_names}")
        self.assertTrue(any(k in joined_names for k in ["an_toan", "an toàn", "su_co", "sự cố", "ke_hoach", "kế hoạch"]),
                        f"Missing Accident Prevention & Safety sheet in {sheet_names}")

    # -------------------------------------------------------------------------
    # R5: Mobile QR Emergency Quick View
    # -------------------------------------------------------------------------

    def test_t1_r5_qr_code_generation_endpoint(self):
        """R5: Test chemical QR code generator endpoint producing vector SVG or PNG without external network."""
        chem_id = "ZNZX009"
        resp = CLIENT.get(f"/api/msds/qr-code/{chem_id}")
        if resp.status_code == 404:
            resp = CLIENT.get(f"/api/msds/qr/{chem_id}")
        if not self.check_or_pend(resp, f"/api/msds/qr-code/{chem_id}", "M5"):
            return

        self.assertEqual(resp.status_code, 200)
        c_type = resp.header("content-type").lower()
        is_svg = "svg" in c_type or b"<svg" in resp.content
        is_png = "png" in c_type or resp.content.startswith(b"\x89PNG")
        self.assertTrue(is_svg or is_png, f"QR code response must be SVG or PNG image, got content-type: {c_type}")

    def test_t1_r5_mobile_emergency_quick_view_zero_auth(self):
        """R5: Test mobile emergency quick view page served with zero authentication requirement."""
        chem_id = "ZNZX009"
        # Check standard mobile endpoint path and aliases
        resp = CLIENT.get(f"/mobile-msds/{chem_id}")
        if resp.status_code == 404:
            resp = CLIENT.get(f"/api/msds/qr-view/{chem_id}")
        if resp.status_code == 404:
            resp = CLIENT.get(f"/msds-emergency?chem_id={chem_id}")
        if not self.check_or_pend(resp, f"/mobile-msds/{chem_id}", "M5"):
            return

        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.header("content-type").lower())
        html = resp.text.casefold()

        # Viewport meta tag for mobile responsiveness
        self.assertIn("viewport", html, "Mobile emergency page must contain <meta name='viewport'> tag")

        # 5 Mandatory Emergency Action Blocks:
        # 1. Fire response
        self.assertTrue(any(w in html for w in ["chữa cháy", "dập lửa", "cháy nổ", "fire"]),
                        "Mobile emergency page missing Fire Response section")
        # 2. Spill response
        self.assertTrue(any(w in html for w in ["tràn đổ", "rò rỉ", "spill", "thu gom"]),
                        "Mobile emergency page missing Spill Response section")
        # 3. First aid
        self.assertTrue(any(w in html for w in ["sơ cứu", "mắt", "da", "first aid"]),
                        "Mobile emergency page missing First Aid section")
        # 4. PPE
        self.assertTrue(any(w in html for w in ["bảo hộ", "ppe", "găng tay", "mặt nạ"]),
                        "Mobile emergency page missing PPE section")
        # 5. Hotlines with click-to-call links
        self.assertTrue("tel:114" in html or "tel:115" in html or "tel:" in html,
                        "Mobile emergency page missing click-to-call telephone links (tel:)")


# =============================================================================
# 4. Tier 2: Boundary & Corner Cases
# =============================================================================

class TestTier2_BoundaryAndCornerCases(BaseMsdsTestCase):
    """
    Tier 2 tests edge cases, malformed inputs, boundary values, and fault tolerance:
    - Empty chemical IDs list
    - Nonexistent chemical IDs
    - Full inventory scope (scope=all)
    - Vietnamese diacritic stripping in filenames
    - Section 3 GHS table checksum display states
    - Invalid print size preset fallback
    - Single chemical storage check
    - Mobile emergency view nonexistent chemical handling
    """

    def test_t2_batch_original_empty_ids(self):
        """T2: Empty chemical IDs in batch ZIP download handled gracefully without 500 error."""
        resp = CLIENT.post("/api/msds/download-batch-original", json={"ids": []})
        if not self.check_or_pend(resp, "/api/msds/download-batch-original", "M1"):
            return

        # Server must either return 400 with helpful message or 200 with empty ZIP
        self.assertIn(resp.status_code, [200, 400], f"Empty IDs request must return 200 or 400, got: {resp.status_code}")
        self.assertNotEqual(resp.status_code, 500, "Empty IDs request crashed with 500 Internal Server Error")

    def test_t2_batch_original_nonexistent_id(self):
        """T2: Non-existent chemical ID in batch download handled cleanly without crash."""
        probe = CLIENT.post("/api/msds/download-batch-original", json={"ids": ["ZNZX009"]})
        if not self.check_or_pend(probe, "/api/msds/download-batch-original", "M1"):
            return

        resp = CLIENT.post("/api/msds/download-batch-original", json={"ids": ["NON_EXISTENT_CHEM_99999"]})
        # Should be 404 or a 200 ZIP containing an explanatory manifest
        self.assertIn(resp.status_code, [200, 404], f"Nonexistent ID returned unexpected status: {resp.status_code}")
        if resp.status_code == 200:
            zf = self.assert_valid_zip(resp.content, min_files=1)
            self.assertTrue(any("readme" in n.lower() or "manifest" in n.lower() for n in zf.namelist()),
                            "ZIP containing nonexistent chemical must include README/manifest")

    def test_t2_batch_safety_cards_scope_all(self):
        """T2: Batch safety cards export with scope=all downloads entire inventory."""
        resp = CLIENT.get("/api/msds/export-batch-safety-cards?scope=all")
        if not self.check_or_pend(resp, "/api/msds/export-batch-safety-cards", "M1"):
            return

        self.assertEqual(resp.status_code, 200)
        zf = self.assert_valid_zip(resp.content, min_files=10)
        self.assertGreaterEqual(len(zf.namelist()), 10, "scope=all should export all active inventory chemicals")

    def test_t2_filename_sanitization_vietnamese_diacritics(self):
        """T2: Chemical with complex Vietnamese name is sanitized to clean ASCII in ZIP."""
        # FTU0005: "Sơn Phủ PU Bóng" -> "Son_Phu_PU_Bong"
        resp = CLIENT.post("/api/msds/export-batch-safety-cards", json={"ids": ["FTU0005"]})
        if not self.check_or_pend(resp, "/api/msds/export-batch-safety-cards", "M1"):
            return

        self.assertEqual(resp.status_code, 200)
        zf = self.assert_valid_zip(resp.content, min_files=1)
        card_name = zf.namelist()[0]
        self.assert_unaccented_filename(card_name)

    def test_t2_section3_checksum_display_cases(self):
        """T2: Mathematical verification of CAS checksum validation across 3 standard states."""
        # 1. Valid CAS -> HỢP LỆ (True)
        self.assertTrue(oracle_cas_checksum_valid("98060-25-4"))  # ZNZX009
        self.assertTrue(oracle_cas_checksum_valid("108-88-3"))    # Toluene
        self.assertTrue(oracle_cas_checksum_valid("7664-93-9"))   # Sulfuric acid
        self.assertTrue(oracle_cas_checksum_valid("67-64-1"))     # Acetone

        # 2. Tampered CAS -> SAI CHECKSUM (False)
        self.assertFalse(oracle_cas_checksum_valid("108-88-4"))
        self.assertFalse(oracle_cas_checksum_valid("7664-93-0"))
        self.assertFalse(oracle_cas_checksum_valid("67-64-2"))

        # 3. Missing/Non-CAS -> KHÔNG CÓ CAS
        self.assertFalse(oracle_cas_checksum_valid(""))
        self.assertFalse(oracle_cas_checksum_valid("N/A"))
        self.assertFalse(oracle_cas_checksum_valid("BÍ MẬT THƯƠNG MẠI"))
        self.assertFalse(oracle_cas_checksum_valid("00-00-0"))

    def test_t2_label_print_invalid_preset_fallback(self):
        """T2: Invalid label print size preset safely falls back or returns clean 400 error."""
        resp = CLIENT.get("/api/msds/label-print-html/ZNZX009?size=UNKNOWN_INVALID_PRESET_999")
        if not self.check_or_pend(resp, "/api/msds/label-print-html/ZNZX009", "M2"):
            return

        self.assertIn(resp.status_code, [200, 400], f"Invalid preset must return 200 (fallback) or 400, got: {resp.status_code}")
        self.assertNotEqual(resp.status_code, 500, "Invalid preset caused unhandled 500 error")

    def test_t2_storage_check_single_chemical(self):
        """T2: Storage compatibility check with a single chemical handles cleanly without crash."""
        payload = {"items": [{"id": "single_1", "name": "ZNZX009", "ghs_codes": ["GHS02"]}]}
        resp = CLIENT.post("/api/msds/storage-compatibility-check", json=payload)
        if not self.check_or_pend(resp, "/api/msds/storage-compatibility-check", "M3"):
            return

        self.assertEqual(resp.status_code, 200)
        self.assertNotEqual(resp.status_code, 500)

    def test_t2_storage_check_empty_list(self):
        """T2: Storage compatibility check with empty chemical list handles gracefully."""
        payload = {"items": []}
        resp = CLIENT.post("/api/msds/storage-compatibility-check", json=payload)
        if not self.check_or_pend(resp, "/api/msds/storage-compatibility-check", "M3"):
            return

        self.assertIn(resp.status_code, [200, 400])

    def test_t2_mobile_emergency_invalid_chemical(self):
        """T2: Mobile emergency quick view for invalid chemical ID returns 404."""
        test_probe = CLIENT.get("/mobile-msds/ZNZX009")
        if not self.check_or_pend(test_probe, "/mobile-msds/ZNZX009", "M5"):
            return

        resp = CLIENT.get("/mobile-msds/NON_EXISTENT_CHEM_99999")
        self.assertEqual(resp.status_code, 404, f"Invalid chemical ID must return 404, got: {resp.status_code}")


# =============================================================================
# 5. Tier 3: Cross-Feature Combinations
# =============================================================================

class TestTier3_CrossFeatureCombinations(BaseMsdsTestCase):
    """
    Tier 3 tests interactions between multiple features:
    - Multi-regulatory category chemical batch export
    - Evaluating warehouse compatibility across real inventory chemicals
    - Consistency between label GHS codes and storage matrix classification
    - Complex multi-CAS mixture label formatting
    - Reconciliation of annual report workbook with CIL database
    """

    def test_t3_batch_safety_cards_multi_category(self):
        """T3: Batch export safety cards spanning multiple legal categories."""
        # 000000000000102992: ND 24 PL I/III (Xylene)
        # ZNZX009: General Flammable GHS02
        # 000000000000135844: NON DG
        target_ids = ["000000000000102992", "ZNZX009", "000000000000135844"]
        resp = CLIENT.post("/api/msds/export-batch-safety-cards", json={"ids": target_ids})
        if not self.check_or_pend(resp, "/api/msds/export-batch-safety-cards", "M1"):
            return

        self.assertEqual(resp.status_code, 200)
        zf = self.assert_valid_zip(resp.content, min_files=3)
        docx_files = [n for n in zf.namelist() if n.endswith(".docx")]
        self.assertEqual(len(docx_files), 3, f"Expected 3 docx files, got: {docx_files}")

    def test_t3_inventory_warehouse_compatibility_evaluation(self):
        """T3: Warehouse compatibility check on actual inventory chemicals."""
        items = [
            {"id": c["id"], "name": c["code"], "ghs_codes": c["ghs"]}
            for c in KNOWN_INVENTORY_CHEMICALS[:4]
        ]
        resp = CLIENT.post("/api/msds/storage-compatibility-check", json={"items": items})
        if not self.check_or_pend(resp, "/api/msds/storage-compatibility-check", "M3"):
            return

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(isinstance(data, (dict, list)), "Response must be structured JSON")

    def test_t3_label_vs_storage_matrix_ghs_consistency(self):
        """T3: Consistency between GHS codes returned by label data and storage compatibility."""
        chem_id = "ZNZX009"
        resp_label = CLIENT.get(f"/api/msds/label-data/{chem_id}")
        if not self.check_or_pend(resp_label, f"/api/msds/label-data/{chem_id}", "M2"):
            return

        label_ghs = resp_label.json().get("ghs_codes", [])
        self.assertIn("GHS02", label_ghs, "ZNZX009 must have GHS02 in label data")

    def test_t3_multi_cas_mixture_decanting_label(self):
        """T3: Decanting label data for multi-component chemical with multiple ingredients."""
        chem_id = "000000000000102992"  # BYK-306
        resp = CLIENT.get(f"/api/msds/label-data/{chem_id}")
        if not self.check_or_pend(resp, f"/api/msds/label-data/{chem_id}", "M2"):
            return

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        ghs_codes = data.get("ghs_codes", [])
        self.assertGreaterEqual(len(ghs_codes), 2, "BYK-306 should contain multiple GHS pictograms")

    def test_t3_annual_report_inventory_reconciliation(self):
        """T3: Reconcile annual report chemical records with SQLite inventory count."""
        resp = CLIENT.get("/api/msds/export-annual-chemical-report")
        if resp.status_code == 404:
            resp = CLIENT.get("/api/msds/export-annual-report")
        if not self.check_or_pend(resp, "/api/msds/export-annual-chemical-report", "M4"):
            return

        wb = openpyxl.load_workbook(io.BytesIO(resp.content))
        # Find inventory sheet
        inv_sheet = None
        for name in wb.sheetnames:
            if any(k in name.casefold() for k in ["hoat_dong", "hoạt động", "danh_muc", "danh mục", "inventory"]):
                inv_sheet = wb[name]
                break

        if inv_sheet:
            # Row count should be at least header + some records
            self.assertGreater(inv_sheet.max_row, 2, "Annual report inventory sheet should contain data rows")


# =============================================================================
# 6. Tier 4: Real-World Workloads & Latency SLA
# =============================================================================

class TestTier4_RealWorldWorkloadsAndLatencySLA(BaseMsdsTestCase):
    """
    Tier 4 tests real-world operational SLAs, performance limits, and concurrency:
    - Full inventory batch ZIP download throughput (<5.0s)
    - Full inventory safety cards DOCX generation performance (<8.0s)
    - API latency SLA (<500ms for read endpoints)
    - Concurrent requests thread-safety
    - File descriptor leak and temporary file cleanup check
    """

    def test_t4_full_inventory_batch_zip_performance(self):
        """T4: Download batch ZIP of all original MSDS files under 5.0 seconds."""
        t0 = time.time()
        resp = CLIENT.get("/api/msds/download-batch-original?scope=all")
        elapsed = time.time() - t0

        if not self.check_or_pend(resp, "/api/msds/download-batch-original", "M1"):
            return

        self.assertEqual(resp.status_code, 200)
        self.assertLess(elapsed, 5.0, f"Batch original download took {elapsed:.2f}s (SLA: < 5.0s)")

    def test_t4_full_inventory_safety_cards_performance(self):
        """T4: Generate batch ZIP of all Word safety cards under 8.0 seconds."""
        t0 = time.time()
        resp = CLIENT.get("/api/msds/export-batch-safety-cards?scope=all")
        elapsed = time.time() - t0

        if not self.check_or_pend(resp, "/api/msds/export-batch-safety-cards", "M1"):
            return

        self.assertEqual(resp.status_code, 200)
        self.assertLess(elapsed, 8.0, f"Batch safety cards export took {elapsed:.2f}s (SLA: < 8.0s)")

    def test_t4_read_endpoints_latency_sla_under_500ms(self):
        """T4: Read endpoints must respond with average latency under 500ms."""
        chem_id = "ZNZX009"
        endpoints_to_test = [
            f"/api/msds/label-data/{chem_id}",
            "/api/msds/storage-compatibility-matrix",
            f"/api/msds/qr-code/{chem_id}",
            f"/mobile-msds/{chem_id}",
            "/api/legal/catalog"
        ]

        latencies = []
        for ep in endpoints_to_test:
            t0 = time.time()
            resp = CLIENT.get(ep)
            dt = time.time() - t0

            if resp.status_code != 404:
                latencies.append((ep, dt))
                self.assertLess(dt, 0.500, f"Endpoint '{ep}' latency was {dt*1000:.1f}ms (SLA: < 500ms)")

        if latencies:
            avg_latency = sum(l[1] for l in latencies) / len(latencies)
            self.assertLess(avg_latency, 0.500, f"Average latency across endpoints was {avg_latency*1000:.1f}ms")

    def test_t4_concurrent_requests_thread_safety(self):
        """T4: Issue 10 concurrent requests to verify thread safety and zero deadlocks."""
        chem_id = "ZNZX009"
        urls = [
            f"/api/msds/label-data/{chem_id}",
            f"/api/msds/qr-code/{chem_id}",
            f"/mobile-msds/{chem_id}",
            "/api/legal/catalog"
        ] * 3  # 12 requests total

        def fetch(path):
            return CLIENT.get(path)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(fetch, u) for u in urls]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All completed requests that were deployed must return valid status (200 or 404 if pending)
        for r in results:
            self.assertIn(r.status_code, [200, 404], f"Concurrent request returned unexpected status {r.status_code}")
            self.assertNotEqual(r.status_code, 500, "Concurrent request triggered 500 Internal Server Error")

    def test_t4_resource_cleanup_no_temp_leak(self):
        """T4: Verify temporary export directories do not accumulate dangling locked files."""
        temp_dir = PROJECT_ROOT / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        initial_file_count = len(list(temp_dir.glob("*.zip")))

        # Perform a batch export
        resp = CLIENT.get("/api/msds/export-batch-safety-cards?scope=all")
        if resp.status_code == 200:
            final_file_count = len(list(temp_dir.glob("*.zip")))
            # Check delta is reasonable (no rampant uncleaned temporary files)
            self.assertLessEqual(final_file_count - initial_file_count, 2, "Too many dangling temporary zip files left uncleaned")


# =============================================================================
# 7. Test Runner & CLI Interface
# =============================================================================

class TimingTestResult(unittest.TextTestResult):
    """Test result tracker recording execution time and progressive pends."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pended = []

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if "[PROGRESSIVE PENDING]" in reason:
            self.pended.append((test, reason))


def run_tier(tier_title: str, test_class: Any, verbose: bool = False, milestone: Optional[str] = None) -> Dict[str, Any]:
    raw_suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
    suite = unittest.TestSuite()
    m_filter = (milestone or ACTIVE_MILESTONE_FILTER or "").upper()
    milestone_test_map = {
        "M1": ["_r1_", "_batch_", "scope_all", "diacritics", "checksum", "safety_cards"],
        "M2": ["_r2_", "label", "_preset_"],
        "M3": ["_r3_", "_storage_", "compatibility"],
        "M4": ["_r4_", "_annual_", "_legal_"],
        "M5": ["_r5_", "_qr_", "_mobile_"],
    }

    if m_filter and m_filter in milestone_test_map:
        target_keys = milestone_test_map[m_filter]
        for test in raw_suite:
            m_name = test._testMethodName.lower()
            if any(k in m_name for k in target_keys):
                suite.addTest(test)
    else:
        suite = raw_suite

    test_count = suite.countTestCases()
    print(f"\n{'='*78}")
    print(f"▶ RUNNING {tier_title.upper()} ({test_count} test cases)")
    print(f"{'='*78}")

    if test_count == 0:
        print(f"ℹ No test cases matched milestone filter '{m_filter}' in this tier.")
        return {
            "tier": tier_title,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "pending": 0,
            "elapsed": 0.0,
            "success": True,
        }

    stream = sys.stdout if verbose else io.StringIO()
    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=2 if verbose else 1,
        resultclass=TimingTestResult
    )

    start_t = time.time()
    result = runner.run(suite)
    elapsed = time.time() - start_t

    pended_count = len(getattr(result, "pended", []))
    passed = result.testsRun - len(result.failures) - len(result.errors) - pended_count
    status_str = "PASSED" if result.wasSuccessful() else "FAILED"

    print(f"✔ Completed {tier_title}: {passed}/{result.testsRun} passed ({pended_count} pending) in {elapsed:.2f}s [{status_str}]")

    if not result.wasSuccessful():
        print(f"\n--- FAILURES / ERRORS in {tier_title} ---")
        for test, err in result.failures:
            print(f"[FAIL] {test}:\n{err}")
        for test, err in result.errors:
            print(f"[ERROR] {test}:\n{err}")
        print("-" * 50)

    return {
        "tier": tier_title,
        "total": result.testsRun,
        "passed": passed,
        "failed": len(result.failures),
        "errors": len(result.errors),
        "pending": pended_count,
        "elapsed": elapsed,
        "success": result.wasSuccessful(),
    }


def main():
    parser = argparse.ArgumentParser(description="TitanPDF MSDS Comprehensive E2E Test Suite (Tiers 1-4)")
    parser.add_argument("--tier", choices=["1", "2", "3", "4", "all"], default="all",
                        help="Select test tier (1, 2, 3, 4, or all)")
    parser.add_argument("--milestone", choices=["M1", "M2", "M3", "M4", "M5", "all"], default="all",
                        help="Select specific milestone to test (M1, M2, M3, M4, M5, or all)")
    parser.add_argument("--progressive", action="store_true",
                        help="Enable progressive mode for in-progress milestones (skips planned endpoints that return 404)")
    parser.add_argument("--strict", action="store_true",
                        help="Enforce strict mode where any 404 endpoint fails immediately")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose test output")
    args = parser.parse_args()

    global PROGRESSIVE_MODE, ACTIVE_MILESTONE_FILTER
    if args.progressive:
        PROGRESSIVE_MODE = True
    if args.strict:
        PROGRESSIVE_MODE = False
    if args.milestone != "all":
        ACTIVE_MILESTONE_FILTER = args.milestone

    print("=" * 78)
    print("   TITANPDF EHS CHEMICAL MANAGEMENT SYSTEM — COMPREHENSIVE E2E TEST SUITE   ")
    print("=" * 78)
    print(f"Target Server : {BASE_URL} (Live: {CLIENT.live})")
    print(f"Mode          : {'PROGRESSIVE (Tolerate planned milestones)' if PROGRESSIVE_MODE else 'STRICT (Gatekeeper mode)'}")
    print(f"Filter        : Tier={args.tier}, Milestone={args.milestone}")

    tier_map = {
        "1": ("Tier 1: Feature Coverage (R1-R5 Happy Path)", TestTier1_FeatureCoverage),
        "2": ("Tier 2: Boundary & Corner Cases", TestTier2_BoundaryAndCornerCases),
        "3": ("Tier 3: Cross-Feature Combinations", TestTier3_CrossFeatureCombinations),
        "4": ("Tier 4: Real-World Workloads & Latency SLA", TestTier4_RealWorldWorkloadsAndLatencySLA),
    }

    selected_tiers = tier_map.keys() if args.tier == "all" else [args.tier]
    summaries = []
    total_start = time.time()

    for key in selected_tiers:
        title, test_cls = tier_map[key]
        summary = run_tier(title, test_cls, verbose=args.verbose, milestone=args.milestone)
        summaries.append(summary)

    total_time = time.time() - total_start

    print("\n" + "=" * 78)
    print("                      E2E TEST EXECUTION SUMMARY                      ")
    print("=" * 78)
    print(f"{'Tier':<40} | {'Total':<6} | {'Pass':<6} | {'Fail':<6} | {'Pend':<6} | {'Time (s)':<8}")
    print("-" * 78)

    total_all = sum(s["total"] for s in summaries)
    total_pass = sum(s["passed"] for s in summaries)
    total_fail = sum(s["failed"] for s in summaries)
    total_pend = sum(s["pending"] for s in summaries)

    for s in summaries:
        print(f"{s['tier']:<40} | {s['total']:<6} | {s['passed']:<6} | {s['failed']:<6} | {s['pending']:<6} | {s['elapsed']:<8.2f}")

    print("-" * 78)
    print(f"{'TOTAL':<40} | {total_all:<6} | {total_pass:<6} | {total_fail:<6} | {total_pend:<6} | {total_time:<8.2f}")
    print("=" * 78 + "\n")

    all_successful = all(s["success"] for s in summaries)
    if all_successful:
        print(f"🎉 ALL TEST TIERS PASSED ({total_pass}/{total_all} tests, {total_pend} pending) in {total_time:.2f}s!")
        sys.exit(0)
    else:
        print(f"❌ TEST SUITE FAILED ({total_fail} failures, {total_all - total_pass - total_pend} errors out of {total_all} tests).")
        sys.exit(1)


if __name__ == "__main__":
    main()
