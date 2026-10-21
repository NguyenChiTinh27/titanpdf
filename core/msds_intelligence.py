"""
core/msds_intelligence.py
─────────────────────────
HỆ THỐNG TRÍ TUỆ NHÂN TẠO CHUYÊN SÂU MSDS / SDS & QUẢN TRỊ DANH MỤC HÓA CHẤT CIL
(AI MSDS INTELLIGENCE ENGINE & CHEMICAL INVENTORY LIST MANAGER)
100% Độc lập - Lưu trữ CSDL SQLite Cục bộ - Tra cứu Siêu tốc - Xuất Báo cáo CIL Excel Chuẩn Quốc tế

Tính năng cốt lõi:
1. AI MSDS Extraction & Summarizer:
   - Đọc hiểu chuyên sâu tệp MSDS/SDS (PDF text, PDF scan OCR, Word .docx/.doc, TXT).
   - Phân giải cấu trúc chuẩn 16 mục GHS quốc tế.
   - Bóc tách tự động: Tên thương mại, Tên hóa học, Số CAS, Mã UN, Phân loại GHS,
     Biểu trưng nguy hại, Từ cảnh báo (Danger/Warning), Mã H/P, Điểm chớp cháy, Tỷ trọng,
     Trang bị bảo hộ cá nhân (PPE), Biện pháp sơ cứu 4 đường phơi nhiễm, Điều kiện bảo quản.
   - Xác thực thuật toán Checksum số CAS (CAS Checksum Validation).
   - Tích hợp AI DeepSeek thông minh (kèm Heuristic Rule Engine ngoại tuyến 100%).

2. Local Chemical Database (CSDL Cục bộ SQLite):
   - Lưu trữ bền vững, chống mất dữ liệu, tốc độ truy xuất tức thì.
   - Quản lý bảng: chemicals, compositions, sections.

3. Quick Lookup & Emergency Safety Card:
   - Tra cứu nhanh tức thì theo: Tên hóa chất, Số CAS, Mã UN, Nhà sản xuất, Mối nguy GHS.
   - Xuất Thẻ an toàn khẩn cấp (Emergency Quick Card) hỗ trợ sơ cứu và ứng phó sự cố.

4. CIL Excel Generator (Chemical Inventory List):
   - Xuất bản tệp Excel (.xlsx) đa sheet chuẩn Luật Hóa chất số 69/2025/QH15, Nghị định 24/2026/NĐ-CP, Thông tư 02/2026/TT-BCT & tiêu chuẩn GHS:
     + Sheet 00: Dashboard Tổng quan
     + Sheet 01: Sổ Danh mục Hóa chất CIL chính thức
     + Sheet 02: Bảng chi tiết Hoạt chất & Số CAS
     + Sheet 03: Hướng dẫn Sơ cứu & Ứng phó sự cố khẩn cấp
"""

import os
import sys
import re
import json
import time
import shutil
import hashlib
import sqlite3
import datetime
import unicodedata
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

import fitz  # PyMuPDF
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ==============================================================================
# HẰNG SỐ & ĐƯỜNG DẪN DỮ LIỆU
# ==============================================================================
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
MSDS_STORAGE_DIR = DATA_DIR / "msds_files"
MSDS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "msds_chemical_inventory.db"
EXPORTS_DIR = PROJECT_ROOT / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

CAS_REGEX = re.compile(r"\b([1-9]\d{1,6})\s*-\s*(\d{2})\s*-\s*(\d)\b")
UN_REGEX = re.compile(r"\b(?:UN|U\.N\.)\s*([0-9]{4})\b", re.IGNORECASE)

GHS_MAP = {
    "GHS01": {"name_vi": "Chất nổ (Explosive)", "symbol": "💥"},
    "GHS02": {"name_vi": "Dễ cháy (Flammable)", "symbol": "🔥"},
    "GHS03": {"name_vi": "Oxy hóa (Oxidizing)", "symbol": "⭕"},
    "GHS04": {"name_vi": "Khí nén (Compressed Gas)", "symbol": "🧴"},
    "GHS05": {"name_vi": "Ăn mòn (Corrosive)", "symbol": "🧪"},
    "GHS06": {"name_vi": "Độc hại cấp tính (Acute Toxic)", "symbol": "☠️"},
    "GHS07": {"name_vi": "Độc hại/Kích ứng (Harmful/Irritant)", "symbol": "⚠️"},
    "GHS08": {"name_vi": "Nguy hại sức khỏe lâu dài (Health Hazard)", "symbol": "🫁"},
    "GHS09": {"name_vi": "Nguy hại môi trường (Environmental)", "symbol": "🐟"},
    "NON DG": {"name_vi": "Không phân loại nguy hại (Non-Hazardous)", "symbol": "✅"}
}


def cas_checksum_valid(cas: str) -> bool:
    """Kiểm tra tính hợp lệ của số CAS bằng thuật toán checksum chuẩn quốc tế."""
    m = CAS_REGEX.fullmatch(str(cas or "").strip())
    if not m:
        return False
    body = m.group(1) + m.group(2)
    check = int(m.group(3))
    total = sum((i + 1) * int(ch) for i, ch in enumerate(reversed(body)))
    return total % 10 == check


def normalize_str(s: Any) -> str:
    if s is None:
        return ""
    t = str(s).replace("\u00a0", " ").replace("\u200b", "").strip()
    return unicodedata.normalize("NFC", t)


# ==============================================================================
# 1. CƠ SỞ DỮ LIỆU SQLITE MSDS CHEMICAL INVENTORY
# ==============================================================================

class MSDSDatabase:
    """Quản trị cơ sở dữ liệu SQLite MSDS & Chemical Inventory List."""

    _initialized: bool = False

    @classmethod
    def get_connection(cls) -> sqlite3.Connection:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    @classmethod
    def init_db(cls) -> None:
        """Khởi tạo cấu trúc các bảng trong SQLite nếu chưa tồn tại."""
        if cls._initialized:
            return
        with cls.get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS chemicals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chemical_id TEXT UNIQUE NOT NULL,
                product_code TEXT,
                product_name_vi TEXT,
                product_name_original TEXT,
                intended_use TEXT,
                manufacturer TEXT,
                revision_date TEXT,
                cas_primary TEXT,
                un_no TEXT,
                transport_class TEXT,
                packing_group TEXT,
                signal_word TEXT,
                ghs_codes TEXT,
                hazard_statements TEXT,
                precautionary_statements TEXT,
                flash_point TEXT,
                density TEXT,
                appearance TEXT,
                storage_condition TEXT,
                respiratory_protection TEXT,
                hand_protection TEXT,
                eye_protection TEXT,
                skin_protection TEXT,
                first_aid_inhalation TEXT,
                first_aid_skin TEXT,
                first_aid_eyes TEXT,
                first_aid_ingestion TEXT,
                fire_measures TEXT,
                spill_measures TEXT,
                source_file TEXT,
                sha256 TEXT,
                raw_summary_ai TEXT,
                item_type TEXT DEFAULT 'raw_material',
                mother_msds_id TEXT DEFAULT NULL,
                drive_file_id TEXT DEFAULT NULL,
                drive_view_url TEXT DEFAULT NULL,
                drive_download_url TEXT DEFAULT NULL,
                sync_status TEXT DEFAULT 'synced',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Tự động di trú cho các CSDL đã tồn tại
            cursor = conn.execute("PRAGMA table_info(chemicals)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "product_code" not in existing_cols:
                conn.execute("ALTER TABLE chemicals ADD COLUMN product_code TEXT DEFAULT NULL")
            if "item_type" not in existing_cols:
                conn.execute("ALTER TABLE chemicals ADD COLUMN item_type TEXT DEFAULT 'raw_material'")
            if "mother_msds_id" not in existing_cols:
                conn.execute("ALTER TABLE chemicals ADD COLUMN mother_msds_id TEXT DEFAULT NULL")
            if "drive_file_id" not in existing_cols:
                conn.execute("ALTER TABLE chemicals ADD COLUMN drive_file_id TEXT DEFAULT NULL")
            if "drive_view_url" not in existing_cols:
                conn.execute("ALTER TABLE chemicals ADD COLUMN drive_view_url TEXT DEFAULT NULL")
            if "drive_download_url" not in existing_cols:
                conn.execute("ALTER TABLE chemicals ADD COLUMN drive_download_url TEXT DEFAULT NULL")
            if "sync_status" not in existing_cols:
                conn.execute("ALTER TABLE chemicals ADD COLUMN sync_status TEXT DEFAULT 'synced'")

            # Tự động phân loại heuristic cho các hóa chất hiện hữu
            try:
                unclassified = conn.execute(
                    "SELECT chemical_id, product_name_vi, product_code FROM chemicals WHERE item_type IS NULL OR item_type = ''"
                ).fetchall()
                if unclassified:
                    from core.legal_engine import LegalCatalogEngine
                    for uc in unclassified:
                        cid = uc["chemical_id"]
                        comps = conn.execute("SELECT * FROM compositions WHERE chemical_id = ?", (cid,)).fetchall()
                        comps_list = [dict(c) for c in comps]
                        itype = LegalCatalogEngine.classify_item_type(
                            product_name=uc["product_name_vi"] or "",
                            compositions=comps_list,
                            product_code=uc["product_code"] or cid
                        )
                        conn.execute("UPDATE chemicals SET item_type = ? WHERE chemical_id = ?", (itype, cid))
            except Exception:
                pass

            conn.execute("""
            CREATE TABLE IF NOT EXISTS compositions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chemical_id TEXT NOT NULL,
                ingredient_name_vi TEXT,
                ingredient_name_original TEXT,
                cas_number TEXT,
                cas_status TEXT,
                concentration_text TEXT,
                concentration_min REAL,
                concentration_max REAL,
                unit TEXT,
                FOREIGN KEY (chemical_id) REFERENCES chemicals(chemical_id) ON DELETE CASCADE
            );
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chemical_id TEXT NOT NULL,
                section_no INTEGER,
                title_original TEXT,
                title_vi TEXT,
                content_original TEXT,
                content_vi TEXT,
                FOREIGN KEY (chemical_id) REFERENCES chemicals(chemical_id) ON DELETE CASCADE
            );
            """)
            conn.commit()
        cls._initialized = True

    @classmethod
    def next_chemical_id(cls) -> str:
        """Sinh mã hóa chất tự động dự phòng khi tài liệu không có mã sản phẩm: CHM-0001, CHM-0002..."""
        cls.init_db()
        with cls.get_connection() as conn:
            rows = conn.execute("SELECT chemical_id FROM chemicals WHERE chemical_id LIKE 'CHM-%' ORDER BY id DESC").fetchall()
            max_num = 0
            for r in rows:
                m = re.search(r"CHM-(\d+)$", str(r["chemical_id"]), re.IGNORECASE)
                if m:
                    max_num = max(max_num, int(m.group(1)))
            return f"CHM-{max_num + 1:04d}"

    @classmethod
    def find_duplicate(cls, chem_id: str, product_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Kiểm tra trùng lặp theo mã hóa chất (chemical_id) hoặc mã sản phẩm (product_code)."""
        cls.init_db()
        cid = (chem_id or "").strip()
        pcode = (product_code or cid).strip()
        if not cid and not pcode:
            return None

        with cls.get_connection() as conn:
            row = conn.execute("""
                SELECT chemical_id FROM chemicals
                WHERE (UPPER(chemical_id) = UPPER(?) AND ? != '')
                   OR (UPPER(product_code) = UPPER(?) AND ? != '')
                   OR (UPPER(chemical_id) = UPPER(?) AND ? != '')
                LIMIT 1
            """, (cid, cid, pcode, pcode, pcode, pcode)).fetchone()
            if row and row["chemical_id"]:
                return cls.get_chemical(row["chemical_id"])
        return None

    @classmethod
    def suggest_unique_code(cls, base_code: str) -> str:
        """Gợi ý mã mới chưa từng tồn tại trong CSDL (ví dụ: FTU0005-V2, FTU0005-V3)."""
        cls.init_db()
        clean_base = (base_code or "CHM").strip().upper()
        for idx in range(2, 100):
            candidate = f"{clean_base}-V{idx}"
            if not cls.find_duplicate(candidate, candidate):
                return candidate
        return f"{clean_base}-{int(time.time()) % 10000}"

    @classmethod
    def store_msds_file(cls, src_path: str, chem_id: str, original_filename: Optional[str] = None) -> str:
        """Lưu trữ tệp MSDS gốc được tải lên vào thư mục cố định data/msds_files/ để tải nhanh."""
        MSDS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        src = Path(src_path) if src_path else None
        if not src or not src.exists():
            return original_filename or ""

        orig_name = (original_filename or src.name).strip()
        # Loại bỏ tiền tố hex 32 ký tự nếu lấy từ thư mục temp
        orig_name = re.sub(r"^[0-9a-f]{32}_", "", orig_name, flags=re.IGNORECASE)
        safe_orig = re.sub(r'[<>:"/\\|?*]', "_", orig_name).strip() or f"{chem_id}.pdf"
        clean_cid = re.sub(r'[<>:"/\\|?*]', "_", (chem_id or "MSDS").strip().upper())

        if clean_cid.lower() in safe_orig.lower():
            stored_name = safe_orig
        else:
            stored_name = f"{clean_cid}_{safe_orig}"

        dest = MSDS_STORAGE_DIR / stored_name
        try:
            if src.resolve() != dest.resolve():
                shutil.copy2(str(src), str(dest))
        except Exception:
            pass
        return stored_name

    @classmethod
    def resolve_msds_file_path(cls, chem_id: str) -> Optional[Path]:
        """Tìm đường dẫn thực tế của tệp MSDS gốc trong kho lưu trữ data/msds_files (hoặc tự động khôi phục từ temp)."""
        MSDS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        chem = cls.get_chemical(chem_id)
        if not chem:
            return None

        cid = str(chem.get("chemical_id") or chem_id).strip()
        src_name = str(chem.get("source_file") or "").strip()

        # 1. Kiểm tra trực tiếp trong MSDS_STORAGE_DIR theo source_file
        if src_name:
            cand1 = MSDS_STORAGE_DIR / src_name
            if cand1.exists() and cand1.is_file():
                return cand1
            cand2 = MSDS_STORAGE_DIR / f"{cid}_{src_name}"
            if cand2.exists() and cand2.is_file():
                return cand2

        # 2. Tìm bất kỳ tệp nào trong MSDS_STORAGE_DIR chứa mã hóa chất
        for f in MSDS_STORAGE_DIR.glob("*"):
            if f.is_file() and cid.upper() in f.name.upper():
                return f

        # 3. Tìm trong thư mục temp (nếu tệp được tải lên trước khi có kho lưu trữ) và copy sang MSDS_STORAGE_DIR
        temp_dir = PROJECT_ROOT / "temp"
        if temp_dir.exists():
            for f in sorted(temp_dir.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
                if not f.is_file():
                    continue
                fname_clean = re.sub(r"^[0-9a-f]{32}_", "", f.name, flags=re.IGNORECASE)
                if (src_name and fname_clean.lower() == src_name.lower()) or (cid and cid.upper() in fname_clean.upper()):
                    stored = cls.store_msds_file(str(f), cid, src_name or fname_clean)
                    with cls.get_connection() as conn:
                        conn.execute("UPDATE chemicals SET source_file = ? WHERE UPPER(chemical_id) = UPPER(?)", (stored, cid))
                        conn.commit()
                    return MSDS_STORAGE_DIR / stored

        # 4. Nếu là bản ghi cũ chưa có file gốc vật lý, tự động kết xuất bản MSDS/Safety Card chuẩn vào kho msds_files
        fallback_path = MSDSSafetyCardExporter.generate_safety_card_docx(chem)
        if fallback_path and fallback_path.exists():
            stored = cls.store_msds_file(str(fallback_path), cid, f"MSDS-{cid}.docx")
            with cls.get_connection() as conn:
                conn.execute("UPDATE chemicals SET source_file = ? WHERE UPPER(chemical_id) = UPPER(?)", (stored, cid))
                conn.commit()
            return MSDS_STORAGE_DIR / stored

        return None

    @classmethod
    def save_chemical(cls, data: Dict[str, Any], sync_gas: bool = True) -> str:
        """Lưu hoặc cập nhật thông tin hóa chất vào CSDL (ưu tiên lấy Mã sản phẩm làm Mã hóa chất & Mã MSDS)."""
        cls.init_db()
        raw_code = (data.get("chemical_id") or data.get("product_code") or "").strip()
        chem_id = raw_code if raw_code else cls.next_chemical_id()
        product_code = (data.get("product_code") or chem_id).strip()

        # Tự động lưu tệp MSDS gốc vào thư mục data/msds_files/ nếu có đường dẫn tệp tải lên
        temp_uploaded_path = data.get("temp_uploaded_path") or ""
        if temp_uploaded_path and Path(temp_uploaded_path).exists():
            stored_filename = cls.store_msds_file(temp_uploaded_path, chem_id, data.get("source_file"))
            if stored_filename:
                data["source_file"] = stored_filename

        ghs_codes_str = json.dumps(data.get("ghs_codes", []), ensure_ascii=False) if isinstance(data.get("ghs_codes"), list) else str(data.get("ghs_codes", ""))

        raw_item_type = data.get("item_type")
        if not raw_item_type:
            try:
                from core.legal_engine import LegalCatalogEngine
                raw_item_type = LegalCatalogEngine.classify_item_type(
                    product_name=data.get("product_name_vi") or data.get("product_name_original") or "",
                    compositions=data.get("composition", []),
                    product_code=product_code
                )
            except Exception:
                raw_item_type = "raw_material"
        mother_msds_id = data.get("mother_msds_id") or None

        with cls.get_connection() as conn:
            # Kiểm tra xem mã hóa chất đã có chưa (không phân biệt hoa thường)
            existing = conn.execute(
                "SELECT id, chemical_id FROM chemicals WHERE UPPER(chemical_id) = UPPER(?)",
                (chem_id,)
            ).fetchone()
            if existing:
                chem_id = existing["chemical_id"]
                conn.execute("""
                UPDATE chemicals SET
                    product_code = ?, product_name_vi = ?, product_name_original = ?, intended_use = ?,
                    manufacturer = ?, revision_date = ?, cas_primary = ?, un_no = ?, transport_class = ?,
                    packing_group = ?, signal_word = ?, ghs_codes = ?, hazard_statements = ?,
                    precautionary_statements = ?, flash_point = ?, density = ?, appearance = ?,
                    storage_condition = ?, respiratory_protection = ?, hand_protection = ?,
                    eye_protection = ?, skin_protection = ?, first_aid_inhalation = ?, first_aid_skin = ?,
                    first_aid_eyes = ?, first_aid_ingestion = ?, fire_measures = ?, spill_measures = ?,
                    source_file = ?, sha256 = ?, raw_summary_ai = ?, item_type = ?, mother_msds_id = ?,
                    drive_file_id = ?, drive_view_url = ?, drive_download_url = ?, sync_status = ?
                WHERE chemical_id = ?
                """, (
                    product_code, data.get("product_name_vi", ""), data.get("product_name_original", ""), data.get("intended_use", ""),
                    data.get("manufacturer", ""), data.get("revision_date", ""), data.get("cas_primary", ""), data.get("un_no", ""), data.get("transport_class", ""),
                    data.get("packing_group", ""), data.get("signal_word", ""), ghs_codes_str, data.get("hazard_statements", ""),
                    data.get("precautionary_statements", ""), data.get("flash_point", ""), data.get("density", ""), data.get("appearance", ""),
                    data.get("storage_condition", ""), data.get("respiratory_protection", ""), data.get("hand_protection", ""),
                    data.get("eye_protection", ""), data.get("skin_protection", ""), data.get("first_aid_inhalation", ""), data.get("first_aid_skin", ""),
                    data.get("first_aid_eyes", ""), data.get("first_aid_ingestion", ""), data.get("fire_measures", ""), data.get("spill_measures", ""),
                    data.get("source_file", ""), data.get("sha256", ""), data.get("raw_summary_ai", "") or data.get("summary", ""),
                    raw_item_type, mother_msds_id,
                    data.get("drive_file_id", ""), data.get("drive_view_url", ""), data.get("drive_download_url", ""), data.get("sync_status", "synced"),
                    chem_id
                ))
                # Xóa compositions và sections cũ để ghi lại mới
                conn.execute("DELETE FROM compositions WHERE chemical_id = ?", (chem_id,))
                conn.execute("DELETE FROM sections WHERE chemical_id = ?", (chem_id,))
            else:
                conn.execute("""
                INSERT INTO chemicals (
                    chemical_id, product_code, product_name_vi, product_name_original, intended_use,
                    manufacturer, revision_date, cas_primary, un_no, transport_class,
                    packing_group, signal_word, ghs_codes, hazard_statements,
                    precautionary_statements, flash_point, density, appearance,
                    storage_condition, respiratory_protection, hand_protection,
                    eye_protection, skin_protection, first_aid_inhalation, first_aid_skin,
                    first_aid_eyes, first_aid_ingestion, fire_measures, spill_measures,
                    source_file, sha256, raw_summary_ai, item_type, mother_msds_id,
                    drive_file_id, drive_view_url, drive_download_url, sync_status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    chem_id, product_code, data.get("product_name_vi", ""), data.get("product_name_original", ""), data.get("intended_use", ""),
                    data.get("manufacturer", ""), data.get("revision_date", ""), data.get("cas_primary", ""), data.get("un_no", ""), data.get("transport_class", ""),
                    data.get("packing_group", ""), data.get("signal_word", ""), ghs_codes_str, data.get("hazard_statements", ""),
                    data.get("precautionary_statements", ""), data.get("flash_point", ""), data.get("density", ""), data.get("appearance", ""),
                    data.get("storage_condition", ""), data.get("respiratory_protection", ""), data.get("hand_protection", ""),
                    data.get("eye_protection", ""), data.get("skin_protection", ""), data.get("first_aid_inhalation", ""), data.get("first_aid_skin", ""),
                    data.get("first_aid_eyes", ""), data.get("first_aid_ingestion", ""), data.get("fire_measures", ""), data.get("spill_measures", ""),
                    data.get("source_file", ""), data.get("sha256", ""), data.get("raw_summary_ai", "") or data.get("summary", ""),
                    raw_item_type, mother_msds_id,
                    data.get("drive_file_id", ""), data.get("drive_view_url", ""), data.get("drive_download_url", ""), data.get("sync_status", "synced")
                ))

            # Lưu danh sách thành phần / CAS
            compositions = data.get("composition", [])
            for c in compositions:
                conn.execute("""
                INSERT INTO compositions (
                    chemical_id, ingredient_name_vi, ingredient_name_original, cas_number,
                    cas_status, concentration_text, concentration_min, concentration_max, unit
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """, (
                    chem_id, c.get("ingredient_name_vi", ""), c.get("ingredient_name_original", ""),
                    c.get("cas_number", ""), c.get("cas_status", "VALID"),
                    c.get("concentration_text", ""), c.get("concentration_min"), c.get("concentration_max"),
                    c.get("unit", "%")
                ))

            # Lưu 16 mục GHS
            sections = data.get("sections", [])
            for s in sections:
                conn.execute("""
                INSERT INTO sections (
                    chemical_id, section_no, title_original, title_vi, content_original, content_vi
                ) VALUES (?,?,?,?,?,?)
                """, (
                    chem_id, s.get("section_no", 1), s.get("title_original", ""), s.get("title_vi", ""),
                    s.get("content_original", ""), s.get("content_vi", "")
                ))

            conn.commit()

        # Cloud persistence via GAS Webhook
        if sync_gas:
            try:
                from core.msds_gas_sync import MSDSGASSyncService
                if MSDSGASSyncService.is_configured():
                    full_chem = cls.get_chemical(chem_id) or data
                    MSDSGASSyncService.sync_to_sheet(full_chem)
            except Exception as _gas_err:
                pass

        return chem_id

    @classmethod
    def insert_chemical(cls, data: Dict[str, Any], sync_gas: bool = True) -> str:
        """Thêm hoặc cập nhật hóa chất, hỗ trợ cờ sync_gas để ngăn chặn vòng lặp N+1 đồng bộ."""
        return cls.save_chemical(data, sync_gas=sync_gas)

    @classmethod
    def list_chemicals(cls, query: Optional[str] = None, item_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lấy danh sách hoặc tìm kiếm toàn diện hóa chất có hỗ trợ lọc theo item_type."""
        with cls.get_connection() as conn:
            where_clauses = []
            params = []

            if query and query.strip():
                q = f"%{query.strip().lower()}%"
                where_clauses.append("""(
                    lower(c.chemical_id) LIKE ?
                    OR lower(c.product_name_vi) LIKE ?
                    OR lower(c.product_name_original) LIKE ?
                    OR lower(c.product_code) LIKE ?
                    OR lower(c.cas_primary) LIKE ?
                    OR lower(c.un_no) LIKE ?
                    OR lower(c.manufacturer) LIKE ?
                    OR lower(c.signal_word) LIKE ?
                    OR lower(comp.ingredient_name_vi) LIKE ?
                    OR lower(comp.ingredient_name_original) LIKE ?
                    OR lower(comp.cas_number) LIKE ?
                )""")
                params.extend([q] * 11)

            if item_type and item_type.strip().lower() not in ("all", ""):
                where_clauses.append("LOWER(COALESCE(c.item_type, 'raw_material')) = LOWER(?)")
                params.append(item_type.strip())

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            sql = f"""
                SELECT DISTINCT c.* FROM chemicals c
                LEFT JOIN compositions comp ON c.chemical_id = comp.chemical_id
                {where_sql}
                ORDER BY c.id DESC
            """
            rows = conn.execute(sql, tuple(params)).fetchall()

            result = []
            chem_ids = []
            for r in rows:
                item = dict(r)
                item["item_type"] = item.get("item_type") or "raw_material"
                item["product_code"] = item.get("product_code") or item.get("chemical_id")
                item["mother_msds_id"] = item.get("mother_msds_id")
                chem_ids.append(item["chemical_id"])
                # Parse GHS codes
                try:
                    item["ghs_codes_list"] = json.loads(item["ghs_codes"]) if item["ghs_codes"] else []
                except Exception:
                    item["ghs_codes_list"] = [item["ghs_codes"]] if item["ghs_codes"] else []
                result.append(item)

            # Feature 18: Batch Composition Resolver (Single batch query eliminating N+1)
            if chem_ids:
                comps_by_id = {}
                chunk_size = 500
                for i in range(0, len(chem_ids), chunk_size):
                    chunk = chem_ids[i:i + chunk_size]
                    placeholders = ",".join("?" for _ in chunk)
                    c_rows = conn.execute(
                        f"SELECT * FROM compositions WHERE chemical_id IN ({placeholders})",
                        tuple(chunk)
                    ).fetchall()
                    for cr in c_rows:
                        comps_by_id.setdefault(cr["chemical_id"], []).append(dict(cr))
                for item in result:
                    item["composition"] = comps_by_id.get(item["chemical_id"], [])
            else:
                for item in result:
                    item["composition"] = []

            return result

    @classmethod
    def get_chemical(cls, chem_id: str) -> Optional[Dict[str, Any]]:
        """Lấy chi tiết đầy đủ 1 hóa chất bao gồm thành phần và 16 mục GHS."""
        with cls.get_connection() as conn:
            row = conn.execute("SELECT * FROM chemicals WHERE UPPER(chemical_id) = UPPER(?)", (chem_id,)).fetchone()
            if not row:
                return None
            actual_id = row["chemical_id"]
            item = dict(row)
            item["item_type"] = item.get("item_type") or "raw_material"
            item["product_code"] = item.get("product_code") or item.get("chemical_id")
            item["mother_msds_id"] = item.get("mother_msds_id")
            comps = conn.execute("SELECT * FROM compositions WHERE chemical_id = ?", (actual_id,)).fetchall()
            item["composition"] = [dict(c) for c in comps]
            sects = conn.execute("SELECT * FROM sections WHERE chemical_id = ? ORDER BY section_no ASC", (actual_id,)).fetchall()
            item["sections"] = [dict(s) for s in sects]
            try:
                item["ghs_codes_list"] = json.loads(item["ghs_codes"]) if item["ghs_codes"] else []
            except Exception:
                item["ghs_codes_list"] = [item["ghs_codes"]] if item["ghs_codes"] else []
            return item

    @classmethod
    def delete_chemical(cls, chem_id: str) -> bool:
        """Xóa hóa chất khỏi CSDL và đồng bộ xóa vĩnh viễn trên Google Sheet."""
        cls.init_db()
        with cls.get_connection() as conn:
            row = conn.execute("SELECT chemical_id FROM chemicals WHERE UPPER(chemical_id) = UPPER(?)", (chem_id,)).fetchone()
            target_id = row["chemical_id"] if row else chem_id
            conn.execute("DELETE FROM chemicals WHERE chemical_id = ?", (target_id,))
            conn.execute("DELETE FROM compositions WHERE chemical_id = ?", (target_id,))
            conn.execute("DELETE FROM sections WHERE chemical_id = ?", (target_id,))
            conn.commit()

        # Đồng bộ xóa vĩnh viễn trên Google Sheet
        try:
            from core.msds_gas_sync import MSDSGASSyncService
            if MSDSGASSyncService.is_configured():
                MSDSGASSyncService.delete_from_sheet(target_id)
        except Exception:
            pass

        return True

    @classmethod
    def delete_multiple_chemicals(cls, chem_ids: list[str]) -> int:
        """Xóa hàng loạt hóa chất theo danh sách mã ID và đồng bộ xóa trên Google Sheet."""
        cls.init_db()
        if not chem_ids:
            return 0
        deleted_count = 0
        deleted_targets = []
        with cls.get_connection() as conn:
            for chem_id in chem_ids:
                row = conn.execute("SELECT chemical_id FROM chemicals WHERE UPPER(chemical_id) = UPPER(?)", (chem_id,)).fetchone()
                target_id = row["chemical_id"] if row else chem_id
                cursor = conn.execute("DELETE FROM chemicals WHERE chemical_id = ?", (target_id,))
                conn.execute("DELETE FROM compositions WHERE chemical_id = ?", (target_id,))
                conn.execute("DELETE FROM sections WHERE chemical_id = ?", (target_id,))
                if cursor.rowcount > 0:
                    deleted_count += cursor.rowcount
                    deleted_targets.append(target_id)
            conn.commit()

        # Đồng bộ xóa vĩnh viễn trên Google Sheet
        try:
            from core.msds_gas_sync import MSDSGASSyncService
            if MSDSGASSyncService.is_configured() and deleted_targets:
                MSDSGASSyncService.delete_multiple_from_sheet(deleted_targets)
        except Exception:
            pass

        return deleted_count

    @classmethod
    def delete_all_chemicals(cls) -> int:
        """Xóa toàn bộ hóa chất và dữ liệu liên quan khỏi CSDL CIL và Google Sheet."""
        cls.init_db()
        with cls.get_connection() as conn:
            cursor = conn.execute("DELETE FROM chemicals")
            deleted_count = cursor.rowcount
            conn.execute("DELETE FROM compositions")
            conn.execute("DELETE FROM sections")
            conn.commit()

        # Đồng bộ xóa sạch toàn bộ trên Google Sheet
        try:
            from core.msds_gas_sync import MSDSGASSyncService
            if MSDSGASSyncService.is_configured():
                MSDSGASSyncService.delete_all_from_sheet()
        except Exception:
            pass

        return deleted_count



# ==============================================================================
# 2. ĐỘNG CƠ BÓC TÁCH VÀ TÓM TẮT MSDS BẰNG AI & HEURISTIC
# ==============================================================================

class MSDSExtractorEngine:
    """Động cơ đọc hiểu, trích xuất 16 mục GHS và phân tích sâu dữ liệu MSDS."""

    @classmethod
    def _extract_text_from_docx_object(cls, doc_path: str) -> str:
        """Đọc toàn bộ đoạn văn và bảng biểu từ tệp DOCX theo đúng thứ tự xuất hiện trên tài liệu."""
        d = docx.Document(doc_path)
        full_text = []

        try:
            from docx.text.paragraph import Paragraph
            from docx.table import Table
            for child in d.element.body.iterchildren():
                if child.tag.endswith('p'):
                    para = Paragraph(child, d)
                    t = para.text.strip()
                    if t:
                        full_text.append(t)
                elif child.tag.endswith('tbl'):
                    table = Table(child, d)
                    for row in table.rows:
                        row_vals = []
                        for c in row.cells:
                            cell_txt = " ".join(line.strip() for line in c.text.splitlines() if line.strip())
                            if cell_txt:
                                row_vals.append(cell_txt)
                        if row_vals:
                            dedup = []
                            for v in row_vals:
                                if not dedup or v != dedup[-1]:
                                    dedup.append(v)
                            if dedup:
                                full_text.append(" | ".join(dedup))
        except Exception:
            for para in d.paragraphs:
                if para.text.strip():
                    full_text.append(para.text.strip())
            for table in d.tables:
                for row in table.rows:
                    row_vals = [c.text.strip() for c in row.cells if c.text.strip()]
                    if row_vals:
                        dedup = []
                        for v in row_vals:
                            if not dedup or v != dedup[-1]:
                                dedup.append(v)
                        if dedup:
                            full_text.append(" | ".join(dedup))

        combined = "\n".join(full_text).strip()
        # Kiểm tra nếu DOCX chủ yếu là ảnh scan (như MSDS.docx)
        if len(combined) < 100 and hasattr(d, 'part') and hasattr(d.part, 'rels'):
            try:
                import pytesseract
                from PIL import Image
                import io
                ocr_images = []
                for rel in d.part.rels.values():
                    if "image" in rel.target_ref:
                        img_part = rel.target_part
                        img_data = img_part.blob
                        img = Image.open(io.BytesIO(img_data))
                        t_ocr = pytesseract.image_to_string(img, lang="vie+eng").strip()
                        if t_ocr:
                            ocr_images.append(t_ocr)
                if ocr_images:
                    combined = "\n\n".join(ocr_images).strip()
            except Exception:
                pass
        return combined

    @classmethod
    def extract_text_from_file(cls, file_path: str) -> str:
        """Trích xuất toàn bộ văn bản từ tệp PDF, DOCX, TXT (hỗ trợ OCR nếu là ảnh)."""
        p = Path(file_path)
        ext = p.suffix.lower()
        full_text = []

        if ext == ".pdf":
            doc = fitz.open(file_path)
            for page in doc:
                t = page.get_text("text")
                if t:
                    full_text.append(t)
            combined = "\n\n".join(full_text).strip()
            # Nếu PDF scan không có text layer, thử OCR
            if len(combined) < 100:
                try:
                    import pytesseract
                    from PIL import Image
                    import io
                    ocr_lines = []
                    for i in range(min(15, len(doc))):
                        pix = doc[i].get_pixmap(dpi=180)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        t_ocr = pytesseract.image_to_string(img, lang="vie+eng+chi_sim").strip()
                        if t_ocr:
                            ocr_lines.append(t_ocr)
                    if ocr_lines:
                        combined = "\n\n".join(ocr_lines).strip()
                except Exception:
                    pass
            doc.close()
            return combined

        elif ext in (".docx", ".doc"):
            # 1. Kiểm tra nhận dạng tệp nhị phân .doc cũ (OLE2)
            is_binary_doc = False
            try:
                with open(file_path, "rb") as f:
                    sig = f.read(8)
                    if sig.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
                        is_binary_doc = True
            except Exception:
                pass

            if is_binary_doc or ext == ".doc":
                # Chuyển đổi .doc sang .docx tạm thời qua Word COM Automation
                temp_docx_path = str(p.parent / f"temp_{uuid.uuid4().hex[:8]}_{p.stem}.docx")
                try:
                    from core.interlinear_translator import convert_doc_to_docx
                    conv_path = convert_doc_to_docx(file_path, temp_docx_path)
                    combined = cls._extract_text_from_docx_object(conv_path)
                    try:
                        os.remove(conv_path)
                    except Exception:
                        pass
                    if combined and len(combined.strip()) > 30:
                        return combined
                except Exception as doc_conv_err:
                    print(f"Warning: convert_doc_to_docx failed: {doc_conv_err}")

                # Dự phòng nếu Word COM không khả dụng: Đọc chuỗi ký tự UTF-16LE từ luồng OLE
                try:
                    raw_bytes = p.read_bytes()
                    utf16_blocks = re.findall(rb'(?:[\x20-\x7e\x00-\xff]\x00){4,}', raw_bytes)
                    extracted_blocks = []
                    for b in utf16_blocks:
                        try:
                            s = b.decode('utf-16le', errors='ignore').strip()
                            if len(s) > 3 and not s.startswith("__"):
                                extracted_blocks.append(s)
                        except Exception:
                            pass
                    if extracted_blocks:
                        return "\n".join(extracted_blocks)
                except Exception:
                    pass

            # 2. Xử lý .docx chuẩn bằng python-docx
            try:
                return cls._extract_text_from_docx_object(file_path)
            except Exception as e:
                # Nếu python-docx lỗi (có thể do tệp .doc đổi đuôi thành .docx), thử Word COM
                try:
                    from core.interlinear_translator import convert_doc_to_docx
                    temp_docx_path = str(p.parent / f"temp_{uuid.uuid4().hex[:8]}_{p.stem}.docx")
                    conv_path = convert_doc_to_docx(file_path, temp_docx_path)
                    combined = cls._extract_text_from_docx_object(conv_path)
                    try:
                        os.remove(conv_path)
                    except Exception:
                        pass
                    return combined
                except Exception:
                    return f"Lỗi đọc file Word: {e}"

        elif ext == ".txt":
            for enc in ("utf-8", "utf-8-sig", "cp1258", "latin1"):
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        return f.read()
                except Exception:
                    continue
        return ""

    @classmethod
    def _parse_key_value_line(cls, line: str) -> Tuple[str, str]:
        """Tách cặp (Key, Value) từ dòng bảng 'Key | : | Value', 'Key | Value' hoặc 'Key : Value'."""
        s = line.strip()
        if not s:
            return "", ""
        if "|" in s:
            cells = [c.strip() for c in s.split("|") if c.strip() and c.strip() not in (":", "：", "-")]
            if len(cells) >= 2:
                k = re.sub(r"[:：]\s*$", "", cells[0]).strip()
                v = re.sub(r"^[:：]\s*", "", " | ".join(cells[1:])).strip()
                return k, v
        if ":" in s or "：" in s:
            parts = re.split(r"[:：]", s, maxsplit=1)
            if len(parts) == 2:
                return parts[0].strip(), parts[1].strip()
        return "", ""

    @classmethod
    def _clean_product_code_candidate(cls, raw_val: str) -> str:
        """Làm sạch chuỗi mã sản phẩm (ví dụ: 'FTU0005', 'ZW55019', 'A1105')."""
        if not raw_val:
            return ""
        first_part = raw_val.split("|")[0].strip()
        first_part = re.sub(r"^[:：\-\s]+", "", first_part).strip()
        invalid_words = {
            "GHS01", "GHS02", "GHS03", "GHS04", "GHS05", "GHS06", "GHS07", "GHS08", "GHS09",
            "DATA", "NONE", "NULL", "UNKNOWN", "NA", "N/A", "NOT", "AVAILABLE", "SHEET",
            "SAFETY", "MSDS", "SDS", "NON", "NONDG"
        }
        # Tìm mã có chữ và số hoặc chuỗi số mã sản phẩm (vd: FTU0005, ZW55019, A1105, 000000000000135844)
        m = re.search(r"\b([A-Za-z]{0,8}[-_]?[0-9]{3,20}[A-Za-z0-9\-_]*)\b", first_part)
        if m:
            cand = m.group(1).upper().strip("-_")
            if cand not in invalid_words and any(ch.isdigit() for ch in cand):
                return cand
        # Nếu là mã ngắn gọn không khoảng trắng và có ít nhất 1 chữ số
        if 2 <= len(first_part) <= 24 and " " not in first_part:
            cand_up = first_part.upper().strip("-_")
            if cand_up not in invalid_words and any(ch.isdigit() for ch in cand_up):
                return cand_up
        return ""

    @classmethod
    def extract_product_code(cls, text: str, filename: str = "") -> str:
        """Trích xuất chính xác Mã sản phẩm / Mã MSDS (vd: FTU0005, ZW55019) từ nội dung và tên file."""
        text_code = ""
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

        code_keys = [
            "mã sản phẩm", "mã hóa chất", "mã msds", "mã sds", "mã hàng", "mã hiệu", "mã số sản phẩm",
            "product code", "product number", "product no", "item code", "item no",
            "material code", "catalog no", "catalogue no", "sds no", "msds no",
            "产品编号", "产品代码", "化学品编号", "型号", "货号"
        ]

        for line in lines[:80]:
            k, v = cls._parse_key_value_line(line)
            if k and v:
                kl = k.lower()
                if any(ck == kl or ck in kl for ck in code_keys):
                    cand = cls._clean_product_code_candidate(v)
                    if cand:
                        text_code = cand
                        break

        # Dự phòng quét regex trực tiếp trên văn bản nếu chưa bắt được qua bảng
        if not text_code:
            m_inline = re.search(
                r"(?:Mã\s*sản\s*phẩm|Product\s*Code|Product\s*Number|Product\s*No\.?|Mã\s*hóa\s*chất|产品编号|产品代码)"
                r"[\s|:\-：]+([A-Za-z0-9][A-Za-z0-9\-_]{2,20})",
                text,
                re.IGNORECASE
            )
            if m_inline:
                text_code = cls._clean_product_code_candidate(m_inline.group(1))

        # Trích xuất mã sản phẩm từ tên file gốc (vd: MSDS-FTU0005-EN.doc -> FTU0005, A1105-TEGO... -> A1105)
        file_code = ""
        if filename:
            stem = Path(filename).stem
            stem = re.sub(r"^(?:temp_[0-9a-fA-F]{6,10}_|[0-9a-fA-F]{8,32}_|0{5,20}[0-9]*_|DATA_)", "", stem, flags=re.IGNORECASE)
            tokens = re.split(r"[\s\-_.,()\[\]]+", stem)
            ignore_tokens = {
                "MSDS", "SDS", "TDS", "COA", "EN", "VN", "VI", "CN", "ZH", "CH",
                "ENG", "VIE", "BILINGUAL", "SONGNGA", "FINAL", "NEW", "COPY", "VER", "REV", "DATA"
            }
            for tok in tokens:
                t_up = tok.strip().upper()
                if not t_up or t_up in ignore_tokens:
                    continue
                if re.match(r"^[A-Z]{1,6}[0-9]{2,8}[A-Z0-9]*$", t_up):
                    file_code = t_up
                    break

        if text_code and file_code:
            if re.match(r"^0{4,}", text_code) and not re.match(r"^0{4,}", file_code):
                return file_code
            if text_code.endswith("X") and file_code.startswith(text_code[:-1]):
                return file_code
            return text_code
        if text_code and re.match(r"^0{4,}", text_code) and file_code:
            return file_code
        return text_code or file_code

    @classmethod
    def extract_section_2_text(cls, text: str) -> str:
        """
        Cô lập riêng nội dung Phần 2 (Nhận dạng đặc tính nguy hiểm / Hazards Identification)
        của tài liệu MSDS/SDS để phân loại mã GHS chính xác 100%, tuyệt đối không bị nhiễu bởi Mục 3-16.
        """
        if not text:
            return ""

        if "THẺ AN TOÀN HÓA CHẤT KHẨN CẤP" in text[:400]:
            card_lines = []
            for ln in text.splitlines():
                if any(k in ln for k in ["Từ Cảnh Báo & Hình Đồ GHS", "Cảnh Báo Nguy Cơ & Phòng Ngừa"]):
                    card_lines.append(ln)
            if card_lines:
                return "\n".join(card_lines)

        sec2_patterns = [
            r"(?:^|\n)\s*(?:SECTION\s*0?2|PHẦN\s*0?2|MỤC\s*0?2|第\s*[2二]\s*部分)\b[^\n]*",
            r"(?:^|\n)\s*0?2\.?\s*(?:\n\s*)?(?:NHẬN\s+DẠNG\s+ĐẶC\s+TÍNH\s+NGUY\s+HIỂM|NHẬN\s+DẠNG\s+MỐI\s+NGUY|HAZARDS?\s+IDENTIFICATION|HAZARDS?\s+SUMMARIZING|HAZARD\(S\)\s+IDENTIFICATION|危险性概述)",
            r"(?:^|\n)\s*2\.1\.?\s*(?:\n\s*)?(?:Classification\s+of\s+the\s+substance|Phân\s+loại\s+theo\s+GHS|Phân\s+loại\s+chất)",
        ]
        start_idx = -1
        for pat in sec2_patterns:
            m2 = re.search(pat, text, re.IGNORECASE)
            if m2:
                start_idx = m2.start()
                break

        if start_idx < 0:
            return text[:3000]

        sub_text = text[start_idx:]

        sec3_patterns = [
            r"(?:^|\n)\s*(?:SECTION\s*0?3|PHẦN\s*0?3|MỤC\s*0?3|第\s*[3三]\s*部分)\b[^\n]*",
            r"(?:^|\n)\s*0?3\.?\s*(?:\n\s*)?(?:THÔNG\s+TIN\s+VỀ\s+THÀNH\s+PHẦN|THÀNH\s+PHẦN\s+CẤU\s+TẠO|COMPOSITION\s*[\/AND]+\s*INFORMATION|COMPOSITION\b|成分\s*[\/／]\s*组成信息)",
            r"(?:^|\n)\s*3\.1\.?\s*(?:\n\s*)?(?:Substances|Mixtures|Đơn\s+chất|Hỗn\s+hợp)",
        ]
        end_offset = len(sub_text)
        for pat in sec3_patterns:
            m3 = re.search(pat, sub_text[30:], re.IGNORECASE)
            if m3:
                cand_end = 30 + m3.start()
                if cand_end < end_offset:
                    end_offset = cand_end

        return sub_text[:min(end_offset, 5500)].strip()

    @classmethod
    def classify_ghs_from_section_2(cls, text: str) -> Dict[str, Any]:
        """
        Xác định chính xác mã GHS (GHS01..GHS09) hoặc 'NON DG' CHỈ TỪ PHẦN 2 của MSDS
        theo chuẩn UN GHS / CLP (EC 1272/2008). Nếu Phần 2 không có mối nguy GHS nào -> trả về ['NON DG'].
        """
        sec2 = cls.extract_section_2_text(text)
        if not sec2:
            return {"is_non_dg": True, "ghs_codes": ["NON DG"], "signal_word": "NON DG", "h_codes": []}

        # Tách Phần 2 thành khối 'Yếu tố nhãn' (Label elements) và khối 'Phân loại lý thuyết' (Theoretical classification)
        m_label = re.search(
            r"(?:^|\n)[^\n]*?(?:label\s+elements?|yếu\s+tố\s+nhãn|thành\s+phần\s+nhãn|nhãn\s+ghs|标签要素)[^\n]*",
            sec2,
            re.IGNORECASE
        )
        if m_label:
            label_block = sec2[m_label.start():]
            theory_block = sec2[:m_label.start()]
            has_label_block = True
        else:
            label_block = sec2
            theory_block = ""
            has_label_block = False

        # 1. Tìm mã H-codes (H200..H413) và mã GHS01..GHS09 tường minh trong Phần 2
        raw_h = re.findall(r"\b(H[234]\d{2}[A-Za-z]*)\b", label_block, re.IGNORECASE)
        if not raw_h and not has_label_block:
            raw_h = re.findall(r"\b(H[234]\d{2}[A-Za-z]*)\b", sec2, re.IGNORECASE)
        h_base = sorted(list(set(c[:4].upper() for c in raw_h)))

        explicit_ghs = set(g.upper() for g in re.findall(r"\b(GHS0[1-9])\b", label_block, re.IGNORECASE))
        if not explicit_ghs and not has_label_block:
            explicit_ghs = set(g.upper() for g in re.findall(r"\b(GHS0[1-9])\b", sec2, re.IGNORECASE))

        # 2. Kiểm tra tuyên bố Không Nguy Hại (NON DG) tường minh trong Phần 2
        non_dg_patterns = [
            r"không\s+phải\s+là\s+chất\s+(?:hay|hoặc)\s+hỗn\s+hợp\s+nguy\s+hại",
            r"không\s+(?:được\s+)?phân\s+loại\s+(?:là\s+)?(?:chất\s+|hỗn\s+hợp\s+)?nguy\s+hại",
            r"không\s+thuộc\s+danh\s+mục\s+nguy\s+hại",
            r"not\s+a\s+hazardous\s+substance\s+or\s+mixture",
            r"not\s+hazardous\s+per\s+the\s+globally\s+harmonized\s+system",
            r"this\s+product\s+is\s+not\s+hazardous",
            r"not\s+classified\s+as\s+hazardous",
            r"not\s+a\s+dangerous\s+substance\s+or\s+mixture",
            r"classification\s+according\s+to\s+ghs[\s\n:：]*not\s+classified",
            r"hazard\s+symbol[\s\n:：]*no\s+symbol",
            r"非危险化学品",
            r"不属于危险化学品",
            r"无危险性分类",
            r"\bnon[\s\-]*dg\b",
        ]
        is_explicit_non_dg = any(re.search(p, sec2, re.IGNORECASE) for p in non_dg_patterns)

        # Kiểm tra tính dễ cháy toàn tài liệu / Phần 2
        has_flam = bool(re.search(
            r"\b(?:flammable(?:\s+(?:liquid|gas|solid|aerosol))?|chất\s+(?:lỏng|khí|rắn)\s+dễ\s+cháy|hơi\s+và\s+chất\s+lỏng\s+dễ\s+cháy|dễ\s+cháy|chất\s+dễ\s+cháy|chất\s+lỏng\s+có\s+thể\s+cháy|H22[0-8]|chớp\s+cháy\s*(?:<|nhỏ\s+hơn)?\s*(?:[1-5]?[0-9]|60)\s*°?C|flash\s*point\s*(?:<|below)?\s*(?:[1-5]?[0-9]|60)\s*°?C|易燃)\b",
            sec2,
            re.IGNORECASE
        ))
        if has_flam:
            is_explicit_non_dg = False

        if is_explicit_non_dg and not h_base and not explicit_ghs:
            return {
                "is_non_dg": True,
                "ghs_codes": ["NON DG"],
                "signal_word": "NON DG",
                "h_codes": []
            }

        ghs_found = set(explicit_ghs)

        # 3. Ánh xạ chuẩn xác từ bảng mã H-codes (UN GHS / CLP) trong Phần 2 sang Hình đồ GHS01-GHS09
        h_to_ghs = {
            "GHS01": {"H200", "H201", "H202", "H203", "H204", "H205", "H240", "H241"},
            "GHS02": {"H220", "H221", "H222", "H223", "H224", "H225", "H226", "H228", "H230", "H231", "H241", "H242", "H250", "H251", "H252", "H260", "H261"},
            "GHS03": {"H270", "H271", "H272"},
            "GHS04": {"H280", "H281"},
            "GHS05": {"H290", "H314", "H318"},
            "GHS06": {"H300", "H301", "H310", "H311", "H330", "H331"},
            "GHS07": {"H302", "H312", "H332", "H315", "H319", "H317", "H335", "H336"},
            "GHS08": {"H304", "H334", "H340", "H341", "H350", "H351", "H360", "H361", "H370", "H371", "H372", "H373"},
            "GHS09": {"H400", "H410", "H411"},  # H412 (Cat 3) và H413 (Cat 4) không có biểu trưng GHS09
        }
        for g_code, h_set in h_to_ghs.items():
            if any(h in h_set for h in h_base):
                ghs_found.add(g_code)

        # 4. Kiểm tra tên hình đồ / biểu trưng được mô tả trong khối Yếu tố nhãn
        if has_label_block:
            pic_line_m = re.search(
                r"(?:hazard\s+pictograms?|hình\s+đồ\s+(?:cảnh\s+báo|nguy\s+hiểm)|biểu\s+trưng\s+(?:cảnh\s+báo|nguy\s+hại)|象形图)[\s|:\-：\n]{1,30}([^\n]+)",
                label_block,
                re.IGNORECASE
            )
            if pic_line_m:
                pic_text = pic_line_m.group(1).lower()
                if any(k in pic_text for k in ("flame", "ngọn lửa", "ngon lua", "火焰")) and "circle" not in pic_text:
                    ghs_found.add("GHS02")
                if any(k in pic_text for k in ("corrosion", "ăn mòn", "an mon", "腐蚀")):
                    ghs_found.add("GHS05")
                if any(k in pic_text for k in ("skull", "đầu lâu", "dau lau", "骷髅")):
                    ghs_found.add("GHS06")
                if any(k in pic_text for k in ("exclamation", "chấm than", "cham than", "感叹")):
                    ghs_found.add("GHS07")
                if any(k in pic_text for k in ("health hazard", "nguy hại sức khỏe", "suc khoe", "健康危害")):
                    ghs_found.add("GHS08")
                if any(k in pic_text for k in ("environment", "môi trường", "moi truong", "环境")):
                    ghs_found.add("GHS09")
                if any(k in pic_text for k in ("bomb", "nổ", "no", "爆炸")):
                    ghs_found.add("GHS01")

        # 5. Phân tích cụm từ khi không có mã H-code và chưa có hình đồ
        if not h_base and not ghs_found:
            # QUY TẮC TỐI THƯỢNG: Nếu có khối Yếu tố nhãn, CHỈ phân tích trong khối nhãn đó,
            # TUYỆT ĐỐI KHÔNG quét đoạn phân loại lý thuyết GB 30000 để tránh bơm dư hình đồ ảo.
            target_text = label_block if has_label_block else sec2

            if re.search(r"\b(?:flammable(?:\s+(?:liquid|gas|solid|aerosol))?|chất\s+(?:lỏng|khí|rắn)\s+dễ\s+cháy|hơi\s+và\s+chất\s+lỏng\s+dễ\s+cháy|dễ\s+cháy|chất\s+dễ\s+cháy|chất\s+lỏng\s+có\s+thể\s+cháy|cháy\s+được|flash\s*point|điểm\s+chớp\s+cháy|易燃)\b", target_text, re.IGNORECASE):
                ghs_found.add("GHS02")

            # Nếu KHÔNG có khối nhãn riêng (tài liệu kiểu cũ không phân tách nhãn), mới quét từ target_text
            if not has_label_block:
                if re.search(r"\b(?:oxidizing|oxidizer|chất\s+oxy\s+hóa|氧化性)\b", target_text, re.IGNORECASE):
                    ghs_found.add("GHS03")
                if re.search(r"\b(?:gas(?:es)?\s+under\s+pressure|compressed\s+gas|khí\s+dưới\s+áp\s+suất|khí\s+nén|加压气体)\b", target_text, re.IGNORECASE):
                    ghs_found.add("GHS04")
                if (
                    re.search(r"\b(?:corrosive\s+to\s+metals|ăn\s+mòn\s+kim\s+loại|causes\s+severe\s+skin\s+burns|causes\s+serious\s+eye\s+damage|gây\s+bỏng\s+da\s+nghiêm\s+trọng)\b", target_text, re.IGNORECASE)
                    or re.search(r"(?:skin\s+corrosion|ăn\s+mòn(?:/kích\s+ứng)?\s+da|serious\s+eye\s+damage|tổn\s+thương\s+mắt\s+nghiêm\s+trọng)[^.\n]{0,35}?(?:category|cat\.?|cấp|loại)\s*1[ABC]?\b", target_text, re.IGNORECASE)
                ):
                    ghs_found.add("GHS05")
                if (
                    re.search(r"(?:acute\s+toxicity|độc\s+cấp\s+tính)[^.\n]{0,40}?(?:category|cat\.?|cấp|loại)\s*[123]\b", target_text, re.IGNORECASE)
                    or re.search(r"\b(?:fatal|toxic)\s+if\s+(?:swallowed|inhaled)\b|\b(?:fatal|toxic)\s+in\s+contact\s+with\s+skin\b", target_text, re.IGNORECASE)
                ):
                    ghs_found.add("GHS06")
                if (
                    re.search(r"(?:acute\s+toxicity|độc\s+cấp\s+tính)[^.\n]{0,40}?(?:category|cat\.?|cấp|loại)\s*4\b", target_text, re.IGNORECASE)
                    or re.search(r"(?:corrosion/irritation|skin\s+irritation|ăn\s+mòn/kích\s+ứng\s+da|kích\s+ứng\s+da)[^.\n]{0,35}?(?:category|cat\.?|cấp|loại)\s*2\b", target_text, re.IGNORECASE)
                    or re.search(r"(?:eye\s+damage/eye\s+irritation|eye\s+irritation|kích\s+ứng\s+mắt)[^.\n]{0,35}?(?:category|cat\.?|cấp|loại)\s*2[AB]?\b", target_text, re.IGNORECASE)
                    or re.search(r"\b(?:harmful\s+if\s+(?:swallowed|inhaled)|harmful\s+in\s+contact\s+with\s+skin|causes\s+skin\s+irritation|causes\s+serious\s+eye\s+irritation|may\s+cause\s+respiratory\s+irritation|may\s+cause\s+drowsiness|may\s+cause\s+an\s+allergic\s+skin\s+reaction|gây\s+kích\s+ứng\s+(?:da|mắt|hô\s+hấp))\b", target_text, re.IGNORECASE)
                ):
                    ghs_found.add("GHS07")
                if (
                    re.search(r"\b(?:aspiration\s+hazard|nguy\s+hại\s+hô\s+hấp|carcinogenicity|reproductive\s+toxicity|độc\s+tính\s+sinh\s+sản|germ\s+cell\s+mutagenicity|respiratory\s+sensiti[sz]ation|may\s+be\s+fatal\s+if\s+swallowed\s+and\s+enters\s+airways|cause[sd]?\s+damage\s+to\s+organs)\b", target_text, re.IGNORECASE)
                    or re.search(r"(?:specific\s+target\s+organ\s+toxicity|độc\s+tính\s+đến\s+cơ\s+quan\s+cụ\s+thể)[^.\n]{0,55}?(?:repeated\s+exposure|lặp\s+lại|(?:category|cat\.?|cấp)\s*[12]\b)", target_text, re.IGNORECASE)
                ):
                    ghs_found.add("GHS08")
                if (
                    re.search(r"(?:aquatic\s+hazard|aquatic\s+toxicity|môi\s+trường\s+thủy\s+sinh|môi\s+trường\s+thuỷ\s+sinh)[^.\n]{0,45}?(?:category|cat\.?|cấp|loại)\s*[12]\b", target_text, re.IGNORECASE)
                    or re.search(r"\b(?:very\s+)?toxic\s+to\s+aquatic\s+life\b|\b(?:rất\s+)?độc\s+đối\s+với\s+sinh\s+vật\s+thu[ỷy]\s+sinh\b", target_text, re.IGNORECASE)
                ):
                    ghs_found.add("GHS09")

        # 6. Nếu Mục 2 bị cắt hụt do cấu trúc bảng Word, kiểm tra đối soát toàn văn bản có chỉ báo dễ cháy/nguy hại không
        if not ghs_found:
            flammable_match = re.search(
                r"\b(?:flammable(?:\s+(?:liquid|gas|solid|aerosol))?|chất\s+(?:lỏng|khí|rắn)\s+dễ\s+cháy|hơi\s+và\s+chất\s+lỏng\s+dễ\s+cháy|dễ\s+cháy|chất\s+dễ\s+cháy|chất\s+lỏng\s+có\s+thể\s+cháy|H22[0-8]|chớp\s+cháy\s*(?:<|nhỏ\s+hơn)?\s*(?:[1-5]?[0-9]|60)\s*°?C|flash\s*point\s*(?:<|below)?\s*(?:[1-5]?[0-9]|60)\s*°?C|易燃)\b",
                text,
                re.IGNORECASE
            )
            if flammable_match:
                ghs_found.add("GHS02")

        # 6. Nếu hoàn toàn không có mã GHS nào -> Gán là NON DG
        if not ghs_found:
            return {
                "is_non_dg": True,
                "ghs_codes": ["NON DG"],
                "signal_word": "NON DG",
                "h_codes": h_base
            }

        # 6. Xác định Từ cảnh báo (Signal Word) chuẩn xác trong Phần 2
        signal_word = ""
        m_sig = re.search(
            r"(?:signal\s*words?|warning\s*words?|từ\s*cảnh\s*báo|từ\s*tín\s*hiệu|信号词|警示词)"
            r"[\s|:\-：\n]{1,20}(no\s+signal\s+word|none|không\s+có|danger|nguy\s+hiểm|warning|cảnh\s+báo|危险|警告)",
            sec2,
            re.IGNORECASE
        )
        if m_sig:
            val_sig = m_sig.group(1).strip().lower()
            if any(x in val_sig for x in ["danger", "nguy hiểm", "危险"]):
                signal_word = "Nguy hiểm (Danger)"
            elif any(x in val_sig for x in ["warning", "cảnh báo", "警告"]):
                signal_word = "Cảnh báo (Warning)"

        if not signal_word:
            danger_h = {"H200", "H201", "H202", "H203", "H220", "H222", "H224", "H225", "H240", "H241", "H250", "H260", "H270", "H271", "H300", "H301", "H304", "H310", "H311", "H314", "H318", "H330", "H331", "H334", "H340", "H350", "H360", "H370", "H372"}
            if any(g in ghs_found for g in ("GHS01", "GHS05", "GHS06")) or any(h in danger_h for h in h_base):
                signal_word = "Nguy hiểm (Danger)"
            else:
                signal_word = "Cảnh báo (Warning)"

        return {
            "is_non_dg": False,
            "ghs_codes": sorted(list(ghs_found)),
            "signal_word": signal_word,
            "h_codes": h_base
        }

    @classmethod
    def parse_with_deepseek(cls, text: str, api_key: Optional[str] = None, visual_ghs_hint: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Sử dụng AI DeepSeek-V4.1-Flash để trích xuất 16 mục GHS và dữ liệu có cấu trúc từ MSDS."""
        from core.ai_text_engine import AITextEngine
        actual_key = AITextEngine.get_deepseek_key(api_key)
        if not actual_key or len(text.strip()) < 50:
            return None

        sample_text = text[:18000]
        if len(text) > 18000:
            sample_text += "\n\n[... CẮT BỚT VĂN BẢN Ở GIỮA ...]\n\n" + text[-7000:]

        ghs_visual_instruction = ""
        if visual_ghs_hint:
            ghs_visual_instruction = (
                f"\nQUY TẮC ĐẶC BIỆT TỪ QUÉT ẢNH THỊ GIÁC TRỰC TIẾP TRÊN TÀI LIỆU:\n"
                f"- Hệ thống đã quét và nhận diện chính xác các hình đồ GHS vật lý được in trên nhãn Mục 2 của tài liệu: {visual_ghs_hint}.\n"
                f"- BẮT BUỘC chỉ trả về trường 'ghs_codes': {visual_ghs_hint}.\n"
                f"- TUYỆT ĐỐI KHÔNG tự ý suy diễn hoặc thêm bớt các mã GHS khác từ câu chữ (ví dụ: tài liệu chỉ in hình đồ GHS02 thì chỉ có GHS02, không được thêm GHS05, GHS06, GHS08).\n"
            )

        system_prompt = (
            "Bạn là chuyên gia phân tích an toàn hóa chất (EHS / MSDS Specialist) hàng đầu thế giới. "
            "Nhiệm vụ của bạn là đọc hiểu toàn văn bản MSDS/SDS được cung cấp và trích xuất dữ liệu chuẩn 16 mục GHS thành định dạng JSON hợp lệ duy nhất.\n"
            "QUY TẮC BẮT BUỘC TỐI THƯỢNG (TUYỆT ĐỐI TUÂN THỦ THEO YÊU CẦU NGƯỜI DÙNG):\n"
            "1. Trong file ở Mục 2 có hiển thị hình đồ GHS thì hiển thị lại đúng hình đồ cảnh báo GHS đó, TUYỆT ĐỐI KHÔNG HIỂN THỊ DƯ. Tuyệt đối không tự ý suy diễn hoặc gán thêm bất kỳ hình đồ nào khác từ câu chữ mô tả nguy cơ hay các phép thử phân loại (ví dụ: file ở Mục 2 chỉ có hình đồ ngọn lửa thì trường 'ghs_codes' CHỈ ĐƯỢC CHỨA ['GHS02'], TUYỆT ĐỐI KHÔNG hiển thị dư GHS05, GHS06, GHS07, GHS08).\n"
            "2. Trường 'ghs_codes' và 'signal_word' CHỈ ĐƯỢC XÁC ĐỊNH DỰA TRÊN MỤC 2 (Nhận dạng đặc tính nguy hiểm / Section 2: Hazards Identification) của MSDS áp dụng cho SẢN PHẨM CHÍNH (dựa trên hàng Yếu tố nhãn / Hình đồ cảnh báo). TUYỆT ĐỐI KHÔNG suy diễn hoặc lấy nhầm mã GHS của từng chất phụ gia/thành phần ở Mục 3.\n"
            "3. NẾU SẢN PHẨM CÓ TÍNH DỄ CHÁY (Flammable liquid/gas/solid, H220-H228, Dễ cháy, Điểm chớp cháy <= 60°C), BẮT BUỘC PHẢI CÓ MÃ GHS02 TRONG 'ghs_codes'. TUYỆT ĐỐI KHÔNG TRẢ VỀ NON DG KHI SẢN PHẨM CÓ ĐẶC TÍNH DỄ CHÁY HOẶC NGUY HIỂM.\n"
            "4. Nếu ở Mục 2 ghi rõ 'Không phải là chất hay hỗn hợp nguy hại', 'Not classified as hazardous', 'Not a hazardous substance or mixture', 'No symbol', và hoàn toàn không có bất kỳ mối nguy hại nào, BẮT BUỘC trả về: \"ghs_codes\": [\"NON DG\"] và \"signal_word\": \"NON DG\".\n"
            f"{ghs_visual_instruction}"
            "5. Toàn bộ các trường mô tả an toàn, tên tiếng Việt, công dụng, ngoại quan, cảnh báo nguy hại, sơ cứu 4 đường, trang bị bảo hộ PPE, điều kiện bảo quản, chữa cháy PHẢI ĐƯỢC VIẾT HOẶC DỊCH SANG TIẾNG VIỆT CHUẨN CHUYÊN NGÀNH HÓA CHẤT.\n"
            "Yêu cầu các trường dữ liệu:\n"
            "{\n"
            '  "product_code": "Mã sản phẩm hoặc mã hiệu hóa chất (vd: FTU0005, ZW55019)",\n'
            '  "product_name_vi": "Tên tiếng Việt hoặc mô tả sản phẩm bằng tiếng Việt (vd: Sơn màu tia cực tím UV, Phụ gia bề mặt BYK-333)",\n'
            '  "product_name_original": "Tên gốc của hóa chất trên tài liệu",\n'
            '  "intended_use": "Mục đích sử dụng / Công dụng bằng tiếng Việt (vd: Sơn phủ gỗ công nghiệp)",\n'
            '  "manufacturer": "Tên công ty sản xuất / Nhà cung ứng",\n'
            '  "revision_date": "Ngày sửa đổi / Ngày phát hành SDS (YYYY-MM-DD hoặc DD-MM-YYYY)",\n'
            '  "cas_primary": "Số CAS chính (vd: 67-64-1)",\n'
            '  "un_no": "Mã số UN (vd: UN 1263, UN 1090)",\n'
            '  "transport_class": "Nhóm nguy hiểm vận chuyển (vd: 3, 8)",\n'
            '  "packing_group": "Nhóm đóng gói (vd: II, III)",\n'
            '  "signal_word": "Từ cảnh báo ở Phần 2 (Nguy hiểm (Danger) / Cảnh báo (Warning) / NON DG)",\n'
            '  "ghs_codes": ["GHS02"] hoặc ["NON DG"] nếu Mục 2 không có mối nguy GHS,\n'
            '  "hazard_statements": "Mã và nội dung cảnh báo nguy hại ở Phần 2 bằng tiếng Việt",\n'
            '  "precautionary_statements": "Mã và nội dung phòng ngừa bằng tiếng Việt",\n'
            '  "flash_point": "Điểm chớp cháy (kèm đơn vị °C)",\n'
            '  "density": "Tỷ trọng / Khối lượng riêng",\n'
            '  "appearance": "Ngoại quan bằng tiếng Việt (trạng thái, màu sắc, mùi)",\n'
            '  "storage_condition": "Điều kiện bảo quản bằng tiếng Việt",\n'
            '  "respiratory_protection": "Trang bị bảo vệ hô hấp bằng tiếng Việt",\n'
            '  "hand_protection": "Bảo vệ tay bằng tiếng Việt",\n'
            '  "eye_protection": "Bảo vệ mắt bằng tiếng Việt",\n'
            '  "skin_protection": "Bảo vệ da/thân bằng tiếng Việt",\n'
            '  "first_aid_inhalation": "Sơ cứu khi hít phải (bằng tiếng Việt)",\n'
            '  "first_aid_skin": "Sơ cứu khi tiếp xúc với da (bằng tiếng Việt)",\n'
            '  "first_aid_eyes": "Sơ cứu khi tiếp xúc với mắt (bằng tiếng Việt)",\n'
            '  "first_aid_ingestion": "Sơ cứu khi nuốt phải (bằng tiếng Việt)",\n'
            '  "fire_measures": "Biện pháp chữa cháy bằng tiếng Việt",\n'
            '  "spill_measures": "Biện pháp xử lý tràn đổ / rò rỉ bằng tiếng Việt",\n'
            '  "composition": [\n'
            '    {\n'
            '      "ingredient_name_vi": "Tên hoạt chất tiếng Việt",\n'
            '      "ingredient_name_original": "Tên hoạt chất gốc",\n'
            '      "cas_number": "Số CAS",\n'
            '      "concentration_text": "Nồng độ (vd: 30 - 50%)",\n'
            '      "concentration_min": 30,\n'
            '      "concentration_max": 50,\n'
            '      "unit": "%"\n'
            '    }\n'
            '  ],\n'
            '  "summary": "Tóm tắt an toàn điều hành ngắn gọn bằng tiếng Việt (3-5 câu cốt lõi)"\n'
            "}\n"
            "CHỈ TRẢ VỀ DUY NHẤT CHUỖI JSON HỢP LỆ, KHÔNG KÈM THEO BẤT KỲ VĂN BẢN HAY GIẢI THÍCH NÀO KHÁC."
        )

        try:
            data = AITextEngine.call_deepseek_api(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": sample_text}
                ],
                api_key=actual_key,
                model="DeepSeek-V4.1-Flash",
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout=90
            )
            content = data["choices"][0]["message"]["content"].strip()
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
            parsed = json.loads(content)
            return parsed
        except Exception as e:
            print(f"[DEEPSEEK_MSDS_PARSE_ERROR] {e}", flush=True)
            return None

    @staticmethod
    def _has_vietnamese(text: str) -> bool:
        """Kiểm tra xem chuỗi đã có dấu tiếng Việt chưa."""
        if not text:
            return False
        return bool(re.search(r"[ăâđêôơưáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]", text, re.IGNORECASE))

    @classmethod
    def _offline_ehs_vi_translate(cls, text: str) -> str:
        """Từ điển chuyển ngữ chuyên ngành An toàn Hóa chất (EHS) Offline sang Tiếng Việt."""
        if not text or not text.strip():
            return ""
        s = text.strip()
        if cls._has_vietnamese(s):
            return s

        exact_map = {
            "uv color paint": "Sơn màu tia cực tím (UV)",
            "water-based clear topcoat": "Sơn phủ bóng hệ nước",
            "waterborne clear topcoat": "Sơn phủ bóng hệ nước",
            "wood coatings": "Sơn phủ gỗ công nghiệp",
            "wood coating": "Sơn phủ gỗ công nghiệp",
            "industrial coating": "Sơn phủ công nghiệp",
            "liquid": "Chất lỏng",
            "clear liquid": "Chất lỏng trong suốt",
            "viscous liquid": "Chất lỏng sệt",
            "colorless liquid": "Chất lỏng không màu",
            "white liquid": "Chất lỏng màu trắng",
            "milky white liquid": "Chất lỏng màu trắng sữa",
            "trgs 510": "Bảo quản an toàn theo quy chuẩn lưu trữ hóa chất TRGS 510.",
            "wear a gas mask": "Đeo mặt nạ phòng độc / khẩu trang lọc hơi hữu cơ đạt chuẩn.",
            "wear safety glasses and chemical splash goggles.": "Đeo kính an toàn và kính bảo hộ chống văng bắn hóa chất.",
            "wear safety glasses and chemical splash goggles": "Đeo kính an toàn và kính bảo hộ chống văng bắn hóa chất.",
            "wear appropriate protective gloves to prevent skin exposure.": "Đeo găng tay bảo hộ chống hóa chất chuyên dụng (cao su Nitrile/Butyl) để ngăn ngừa tiếp xúc da.",
            "wear appropriate protective gloves to prevent skin exposure": "Đeo găng tay bảo hộ chống hóa chất chuyên dụng (cao su Nitrile/Butyl) để ngăn ngừa tiếp xúc da.",
            "wear appropriate protective clothing to prevent skin contact. wear gloves as standard industrial handling practice.": "Mặc quần áo bảo hộ lao động chống thấm hóa chất để ngăn ngừa tiếp xúc da; mang găng tay và giày bảo hộ theo quy chuẩn công nghiệp.",
            "store in a cool, dry, ventilated place. store safely in upright containers to prevent leaks.": "Bảo quản ở nơi khô ráo, thoáng mát, thông gió tốt. Lưu trữ an toàn trong thùng chứa đặt thẳng đứng, đậy kín nắp để ngăn ngừa rò rỉ.",
            "wash skin thoroughly with soap and water. take off contaminated clothing and wash before use again. if irritation persists, seek medical attention": "Rửa kỹ vùng da tiếp xúc bằng xà phòng và nhiều nước sạch. Cởi bỏ quần áo bị nhiễm hóa chất và giặt sạch trước khi dùng lại. Nếu kích ứng kéo dài, đưa đến cơ sở y tế.",
            "wash skin thoroughly with soap and water. take off contaminated clothing and wash before use again. if irritation persists, seek medical attention.": "Rửa kỹ vùng da tiếp xúc bằng xà phòng và nhiều nước sạch. Cởi bỏ quần áo bị nhiễm hóa chất và giặt sạch trước khi dùng lại. Nếu kích ứng kéo dài, đưa đến cơ sở y tế.",
            "flush eyes with plenty of water for at least 15 minutes, occasionally lifting upper and lower eyelids. seek medical treatment.": "Xối rửa mắt ngay lập tức bằng nhiều nước sạch trong ít nhất 15 phút, thỉnh thoảng nâng mí mắt trên và dưới. Đưa ngay đến cơ sở y tế.",
            "flush eyes with plenty of water for at least 15 minutes, occasionally lifting upper and lower eyelids. seek medical treatment": "Xối rửa mắt ngay lập tức bằng nhiều nước sạch trong ít nhất 15 phút, thỉnh thoảng nâng mí mắt trên và dưới. Đưa ngay đến cơ sở y tế.",
        }
        low = s.lower()
        if low in exact_map:
            return exact_map[low]

        replacements = [
            (r"\bwash skin thoroughly with soap and water\b", "Rửa kỹ vùng da tiếp xúc bằng xà phòng và nhiều nước sạch"),
            (r"\btake off contaminated clothing and wash before use again\b", "cởi bỏ quần áo nhiễm bẩn và giặt sạch trước khi dùng lại"),
            (r"\bif irritation persists,?\s*seek medical attention\b", "nếu kích ứng kéo dài, cần đưa đến cơ sở y tế"),
            (r"\bflush eyes with plenty of water for at least 15 minutes\b", "Xối rửa mắt ngay bằng nhiều nước sạch trong ít nhất 15 phút"),
            (r"\boccasionally lifting upper and lower eyelids\b", "thỉnh thoảng nâng mí mắt trên và dưới"),
            (r"\bseek medical (?:attention|treatment|advice)\b", "đưa đến cơ sở y tế để kiểm tra"),
            (r"\bmove (?:victim )?to fresh air\b", "Đưa nạn nhân ra nơi thoáng khí"),
            (r"\bremove to fresh air\b", "Đưa ngay nạn nhân ra nơi thoáng khí"),
            (r"\bif not breathing,?\s*give artificial respiration\b", "nếu ngừng thở, thực hiện hô hấp nhân tạo"),
            (r"\bdo not induce vomiting\b", "Tuyệt đối không tự ý gây nôn"),
            (r"\brinse mouth with water\b", "Súc miệng kỹ bằng nước sạch"),
            (r"\bwear safety glasses\b", "Đeo kính bảo hộ an toàn"),
            (r"\bchemical splash goggles\b", "kính chắn giọt bắn hóa chất"),
            (r"\bprotective gloves\b", "găng tay bảo hộ chống hóa chất"),
            (r"\bprotective clothing\b", "quần áo bảo hộ chống hóa chất"),
            (r"\bgas mask\b", "mặt nạ phòng độc"),
            (r"\bstore in a cool,?\s*dry,?\s*well-ventilated place\b", "Bảo quản ở nơi khô ráo, thoáng mát, thông gió tốt"),
            (r"\bstore in a cool,?\s*dry,?\s*ventilated place\b", "Bảo quản ở nơi khô ráo, thoáng mát, thông gió tốt"),
            (r"\bkeep container tightly closed\b", "Đậy thật kín nắp thùng chứa"),
            (r"\bkeep away from heat,?\s*sparks,?\s*open flames\b", "Tránh xa nguồn nhiệt, tia lửa và ngọn lửa trần"),
        ]
        out = s
        for pat, rep in replacements:
            out = re.sub(pat, rep, out, flags=re.IGNORECASE)
        return out

    @classmethod
    def ensure_vietnamese_msds_fields(cls, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Đảm bảo 100% các trường thông tin trên Thẻ An Toàn & Danh mục CIL đều bằng Tiếng Việt chuẩn."""
        if not parsed:
            return parsed

        translatable_fields = [
            "product_name_vi",
            "intended_use",
            "appearance",
            "hazard_statements",
            "precautionary_statements",
            "first_aid_inhalation",
            "first_aid_skin",
            "first_aid_eyes",
            "first_aid_ingestion",
            "respiratory_protection",
            "hand_protection",
            "eye_protection",
            "skin_protection",
            "storage_condition",
            "fire_measures",
            "spill_measures"
        ]

        # Bước 1: Áp dụng từ điển chuyên ngành EHS Offline trước (siêu tốc 0ms)
        fields_needing_api = []
        for f in translatable_fields:
            val = str(parsed.get(f) or "").strip()
            if val and not cls._has_vietnamese(val):
                mapped = cls._offline_ehs_vi_translate(val)
                parsed[f] = mapped
                if not cls._has_vietnamese(mapped):
                    fields_needing_api.append(f)

        # Bước 2: Dịch hàng loạt qua Google Translate cho các câu tiếng Anh/Trung còn lại
        if fields_needing_api:
            try:
                from core.ai_text_engine import AITextEngine
                sep = "\n ||| \n"
                batch_src = sep.join(str(parsed.get(f) or "") for f in fields_needing_api)
                batch_vi = AITextEngine.translate_google(batch_src, source_lang="auto", target_lang="vi")
                if batch_vi:
                    parts = [p.strip() for p in re.split(r"\s*\|\|\|\s*", batch_vi)]
                    if len(parts) == len(fields_needing_api):
                        for f, vi_val in zip(fields_needing_api, parts):
                            if vi_val:
                                parsed[f] = vi_val
            except Exception:
                pass

        # Bước 3: Chuẩn hóa danh sách GHS và kiểm tra trạng thái NON DG
        ghs_raw = parsed.get("ghs_codes") or parsed.get("ghs_codes_list") or []
        if isinstance(ghs_raw, str):
            try:
                ghs_list = json.loads(ghs_raw)
            except Exception:
                if "NON DG" in ghs_raw.upper() or "NONDG" in ghs_raw.upper():
                    ghs_list = ["NON DG"]
                else:
                    ghs_list = [g.strip() for g in re.split(r"[,;]+", ghs_raw) if g.strip()]
        elif isinstance(ghs_raw, list):
            ghs_list = [str(g).strip() for g in ghs_raw if str(g).strip()]
        else:
            ghs_list = []

        valid_ghs = sorted(list(set(g.upper() for g in ghs_list if re.fullmatch(r"GHS0[1-9]", g.upper()))))
        hz_text_low = str(parsed.get("hazard_statements") or "").lower()
        sig_text_low = str(parsed.get("signal_word") or "").lower()
        is_non_dg = (
            not valid_ghs
            or any("non dg" in g.lower() or "nondg" in g.lower() or "none" == g.lower() for g in ghs_list)
            or "không phải là chất hay hỗn hợp nguy hại" in hz_text_low
            or "không phân loại nguy hại" in hz_text_low
            or "non dg" in sig_text_low
            or "không có từ cảnh báo" in sig_text_low
        ) and not valid_ghs

        if is_non_dg:
            parsed["ghs_codes"] = ["NON DG"]
            parsed["ghs_codes_list"] = ["NON DG"]
            parsed["signal_word"] = "NON DG"
            if (
                not parsed.get("hazard_statements")
                or not cls._has_vietnamese(str(parsed.get("hazard_statements", "")))
                or "có thể gây kích ứng da, mắt" in hz_text_low
                or "not applicable" in hz_text_low
            ):
                parsed["hazard_statements"] = "NON DG — Không phải là chất hay hỗn hợp nguy hại theo phân loại GHS (Phần 2)."
        else:
            parsed["ghs_codes"] = valid_ghs
            parsed["ghs_codes_list"] = valid_ghs
            if not parsed.get("hazard_statements") or not cls._has_vietnamese(str(parsed.get("hazard_statements", ""))):
                hz_desc = []
                for g in valid_ghs:
                    if g in GHS_MAP:
                        hz_desc.append(f"{g} ({GHS_MAP[g]['name_vi']})")
                if hz_desc:
                    parsed["hazard_statements"] = "Phân loại nguy hại GHS: " + ", ".join(hz_desc) + ". Cần tuân thủ nghiêm ngặt quy trình an toàn hóa chất khi tiếp xúc."
                else:
                    parsed["hazard_statements"] = "NON DG — Không phải là chất hay hỗn hợp nguy hại theo phân loại GHS (Phần 2)."

        if not parsed.get("intended_use"):
            parsed["intended_use"] = "Sử dụng trong sản xuất công nghiệp"
        if not parsed.get("appearance"):
            parsed["appearance"] = "Chất lỏng công nghiệp"

        # 4 Bước sơ cứu khẩn cấp (Bắt buộc đủ cả 4 đường phơi nhiễm bằng tiếng Việt)
        if not parsed.get("first_aid_inhalation"):
            parsed["first_aid_inhalation"] = "Đưa ngay nạn nhân ra nơi thoáng khí, giữ ấm và để nghỉ ngơi ở tư thế dễ thở. Nếu khó thở hoặc ngưng thở, cho thở oxy / hô hấp nhân tạo và đưa đến cơ sở y tế."
        if not parsed.get("first_aid_skin"):
            parsed["first_aid_skin"] = "Cởi bỏ ngay quần áo, giày dép bị dính hóa chất. Rửa kỹ vùng da tiếp xúc bằng xà phòng và nhiều nước sạch ít nhất 15 phút. Nếu kích ứng da kéo dài, cần khám y tế."
        if not parsed.get("first_aid_eyes"):
            parsed["first_aid_eyes"] = "Xối rửa mắt ngay lập tức bằng nhiều nước sạch chảy nhẹ trong ít nhất 15 phút, đồng thời nâng mở mí mắt trên và dưới (tháo kính áp tròng nếu có). Đưa ngay đến cơ sở y tế."
        if not parsed.get("first_aid_ingestion"):
            parsed["first_aid_ingestion"] = "Súc miệng kỹ bằng nước sạch. Không tự ý gây nôn trừ khi có chỉ định của bác sĩ. Đưa ngay nạn nhân kèm theo phiếu an toàn MSDS đến cơ sở y tế gần nhất."

        # 4 Trang bị bảo hộ cá nhân PPE (Bắt buộc đủ 4 mục bằng tiếng Việt)
        if not parsed.get("eye_protection"):
            parsed["eye_protection"] = "Đeo kính an toàn và kính bảo hộ chống văng bắn hóa chất đạt chuẩn."
        if not parsed.get("respiratory_protection"):
            parsed["respiratory_protection"] = "Đeo khẩu trang than hoạt tính hoặc mặt nạ phòng độc lọc hơi hữu cơ khi làm việc nơi thông gió kém."
        if not parsed.get("hand_protection"):
            parsed["hand_protection"] = "Đeo găng tay bảo hộ chống hóa chất chuyên dụng (cao su Nitrile, Neoprene hoặc Butyl)."
        if not parsed.get("skin_protection"):
            parsed["skin_protection"] = "Mặc quần áo bảo hộ lao động dài tay chống thấm hóa chất, tạp dề và đi giày bảo hộ an toàn."

        # Điều kiện lưu trữ & Chữa cháy
        if not parsed.get("storage_condition"):
            parsed["storage_condition"] = "Bảo quản ở nơi khô ráo, thoáng mát, thông gió tốt. Đậy kín nắp thùng chứa, đặt thẳng đứng để tránh rò rỉ. Tránh xa nguồn nhiệt, tia lửa và ánh nắng trực tiếp."
        if not parsed.get("fire_measures"):
            parsed["fire_measures"] = "Sử dụng bọt kháng cồn, bột khô, khí CO2 hoặc phun sương nước để dập lửa. Không dùng tia nước áp lực cao phun trực tiếp."
        if not parsed.get("spill_measures"):
            parsed["spill_measures"] = "Cách ly khu vực rò rỉ, thông gió tốt. Dùng vật liệu trơ (cát khô, đất sét, tấm thấm hóa chất) để thu gom vào thùng chứa kín và xử lý theo quy định chất thải nguy hại."

        parsed["summary"] = (
            f"Mã SP/MSDS: {parsed.get('product_code') or parsed.get('chemical_id') or 'N/A'} — {parsed.get('product_name_vi', '')} "
            f"(CAS chính: {parsed.get('cas_primary') or 'Hỗn hợp'}). "
            f"Công dụng: {parsed.get('intended_use')}. "
            f"Phân loại GHS: {', '.join(parsed.get('ghs_codes', ['NON DG']))} ({parsed.get('signal_word') or 'NON DG'}). "
            f"Nhà sản xuất: {parsed.get('manufacturer') or 'N/A'}."
        )
        return parsed

    @classmethod
    def parse_with_heuristic(cls, text: str, filename: str = "") -> Dict[str, Any]:
        """Động cơ bóc tách Heuristic Rule Engine 100% Offline (hỗ trợ đa định dạng bảng & văn bản)."""
        product_code = cls.extract_product_code(text, filename)
        data: Dict[str, Any] = {
            "chemical_id": product_code,
            "product_code": product_code,
            "product_name_vi": "",
            "product_name_original": "",
            "intended_use": "",
            "manufacturer": "",
            "revision_date": "",
            "cas_primary": "",
            "un_no": "",
            "transport_class": "",
            "packing_group": "",
            "signal_word": "",
            "ghs_codes": [],
            "hazard_statements": "",
            "precautionary_statements": "",
            "flash_point": "",
            "density": "",
            "appearance": "",
            "storage_condition": "",
            "respiratory_protection": "",
            "hand_protection": "",
            "eye_protection": "",
            "skin_protection": "",
            "first_aid_inhalation": "",
            "first_aid_skin": "",
            "first_aid_eyes": "",
            "first_aid_ingestion": "",
            "fire_measures": "",
            "spill_measures": "",
            "composition": [],
            "sections": [],
            "summary": ""
        }

        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # 1. Quét các cặp Key - Value trên toàn bộ văn bản
        name_primary = ""
        name_desc = ""
        for line in lines:
            k, v = cls._parse_key_value_line(line)
            if not k or not v or len(v) < 2:
                continue
            kl = k.lower()
            v_clean = v.split("|")[0].strip()

            # Tên sản phẩm / Mô tả sản phẩm
            if any(w == kl or w in kl for w in ["tên sản phẩm", "tên thương mại", "tên hóa chất", "product name", "trade name", "chemical name", "产品名称", "化学品名称"]):
                if not name_primary and v_clean.lower() not in ("n/a", "none", ":"):
                    name_primary = v_clean
            elif any(w == kl or w in kl for w in ["mô tả sản phẩm", "product description", "mô tả", "产品描述"]):
                if not name_desc and v_clean.lower() not in ("n/a", "none", ":"):
                    name_desc = v_clean

            # Mục đích sử dụng
            elif any(w in kl for w in ["mục đích sử dụng", "công dụng", "intended use", "recommended use", "用途", "推荐用途"]):
                if not data["intended_use"]:
                    data["intended_use"] = v_clean

            # Ngày sửa đổi / phát hành
            elif any(w in kl for w in ["ngày sửa đổi", "ngày phát hành", "ngày hiệu đính", "revision date", "issue date", "date of issue", "修订日期", "编制日期"]):
                if not data["revision_date"]:
                    data["revision_date"] = v_clean

            # Nhà sản xuất / Nhà cung cấp / Công ty
            elif any(w in kl for w in [
                "tên công ty", "nhà sản xuất", "nhà cung cấp", "đơn vị cung cấp", "tên đơn vị",
                "company name", "company", "manufacturer", "supplier", "distributor",
                "企业名称", "公司名称", "制造商", "供应商", "生产企业"
            ]):
                if not data["manufacturer"] and len(v_clean) > 2:
                    data["manufacturer"] = v_clean[:120]

            # Sơ cứu 4 đường phơi nhiễm (Mục 4)
            elif any(w in kl for w in ["tiếp xúc với da", "dính vào da", "skin exposure", "skin contact", "after skin contact", "皮肤接触"]):
                if not data["first_aid_skin"]:
                    data["first_aid_skin"] = v_clean
            elif any(w in kl for w in ["tiếp xúc với mắt", "dính vào mắt", "eye exposure", "eye contact", "after eye contact", "眼睛接触"]):
                if not data["first_aid_eyes"]:
                    data["first_aid_eyes"] = v_clean
            elif any(w in kl for w in ["đường hô hấp", "hít phải", "inhalation exposure", "inhalation", "if inhaled", "吸入"]):
                if not data["first_aid_inhalation"] and "protection" not in kl and "bảo vệ" not in kl:
                    data["first_aid_inhalation"] = v_clean
            elif any(w in kl for w in ["đường tiêu hóa", "nuốt phải", "oral exposure", "ingestion", "if swallowed", "食入", "误吞"]):
                if not data["first_aid_ingestion"]:
                    data["first_aid_ingestion"] = v_clean

            # Chữa cháy (Mục 5) & Tràn đổ (Mục 6) & Bảo quản (Mục 7)
            elif any(w in kl for w in ["chất chữa cháy", "phương tiện chữa cháy", "extinguishing media", "suitable extinguishing", "灭火方法", "灭火剂"]):
                if not data["fire_measures"]:
                    data["fire_measures"] = v_clean
            elif any(w in kl for w in ["xử lý tràn đổ", "thu gom", "làm sạch", "clean-up", "cleaning up", "spill", "泄漏应急"]):
                if not data["spill_measures"]:
                    data["spill_measures"] = v_clean
            elif any(w in kl for w in ["điều kiện bảo quản", "lưu trữ", "bảo quản", "storage", "safe storage", "储存"]):
                if not data["storage_condition"] and len(v_clean) > 5:
                    data["storage_condition"] = v_clean

            # Bảo hộ cá nhân PPE (Mục 8)
            elif any(w in kl for w in ["bảo vệ hô hấp", "respiratory protection", "呼吸系统防护"]):
                if not data["respiratory_protection"]:
                    data["respiratory_protection"] = v_clean
            elif any(w in kl for w in ["bảo vệ tay", "hand protection", "手防护"]):
                if not data["hand_protection"]:
                    data["hand_protection"] = v_clean
            elif any(w in kl for w in ["bảo vệ mắt", "eye protection", "眼睛防护"]):
                if not data["eye_protection"]:
                    data["eye_protection"] = v_clean
            elif any(w in kl for w in ["bảo vệ da", "bảo vệ cơ thể", "skin and body protection", "body protection", "身体防护"]):
                if not data["skin_protection"]:
                    data["skin_protection"] = v_clean

            # Tính chất lý hóa (Mục 9)
            elif any(w in kl for w in ["ngoại quan", "trạng thái vật lý", "hình thái", "appearance", "physical state", "外观与性状"]):
                if not data["appearance"]:
                    data["appearance"] = v_clean
            elif any(w in kl for w in ["điểm chớp cháy", "flash point", "闪点"]):
                if not data["flash_point"]:
                    data["flash_point"] = v_clean
            elif any(w in kl for w in ["tỷ trọng", "khối lượng riêng", "mật độ", "density", "specific gravity", "相对密度", "密度"]):
                if not data["density"]:
                    data["density"] = v_clean

            # Vận chuyển (Mục 14)
            elif any(w in kl for w in ["số un", "mã un", "mã số un", "un number", "un no", "联合国危险货物编号"]):
                if not data["un_no"] and re.search(r"\d{4}", v_clean):
                    m_un_d = re.search(r"(\d{4})", v_clean)
                    data["un_no"] = f"UN {m_un_d.group(1)}"
            elif any(w in kl for w in ["nhóm đóng gói", "packing group", "包装类别"]):
                if not data["packing_group"]:
                    data["packing_group"] = v_clean
            elif any(w in kl for w in ["loại nguy hiểm", "nhóm nguy hiểm", "transport hazard class", "hazard class", "危险货物类别"]):
                if not data["transport_class"] and len(v_clean) <= 20:
                    data["transport_class"] = v_clean

            # Cảnh báo nguy hại (Mục 2)
            elif any(w in kl for w in ["cảnh báo nguy cơ", "công bố nguy cơ", "hazard statements", "hazard statement", "危险性说明"]):
                if not data["hazard_statements"]:
                    data["hazard_statements"] = v_clean
            elif any(w in kl for w in ["cảnh báo phòng ngừa", "biện pháp phòng ngừa", "precautionary statements", "防范说明"]):
                if not data["precautionary_statements"]:
                    data["precautionary_statements"] = v_clean

        chosen_name = name_primary or name_desc
        if chosen_name:
            data["product_name_original"] = chosen_name
            data["product_name_vi"] = chosen_name
        elif product_code:
            data["product_name_original"] = f"Hóa chất {product_code}"
            data["product_name_vi"] = f"Hóa chất {product_code}"
        elif lines:
            data["product_name_original"] = lines[0][:80]
            data["product_name_vi"] = lines[0][:80]

        # 2. Bóc tách bảng Thành phần & Số CAS (Mục 3)
        parsed_cas_set = set()
        for line in lines:
            if "|" in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if len(cells) >= 2:
                    cas_idx = -1
                    cas_val = ""
                    for idx, c in enumerate(cells):
                        m_cas = CAS_REGEX.search(c)
                        if m_cas:
                            cand = f"{m_cas.group(1)}-{m_cas.group(2)}-{m_cas.group(3)}"
                            if cas_checksum_valid(cand):
                                cas_idx = idx
                                cas_val = cand
                                break
                    if cas_idx >= 0 and cas_val not in parsed_cas_set:
                        parsed_cas_set.add(cas_val)
                        ing_name = ""
                        for prev_i in range(cas_idx - 1, -1, -1):
                            if not re.fullmatch(r"\d+\.?", cells[prev_i]):
                                ing_name = cells[prev_i]
                                break
                        if not ing_name:
                            ing_name = f"Hợp chất CAS {cas_val}"
                        conc_txt = ""
                        c_min, c_max = None, None
                        if cas_idx + 1 < len(cells):
                            conc_txt = cells[cas_idx + 1]
                            m_range = re.search(r"(\d+(?:\.\d+)?)\s*[-~–]\s*(\d+(?:\.\d+)?)", conc_txt)
                            if m_range:
                                c_min = float(m_range.group(1))
                                c_max = float(m_range.group(2))
                                if "%" not in conc_txt:
                                    conc_txt = f"{conc_txt}%"
                            else:
                                m_single = re.search(r"(\d+(?:\.\d+)?)", conc_txt)
                                if m_single:
                                    c_min = float(m_single.group(1))
                                    c_max = c_min
                                    if "%" not in conc_txt:
                                        conc_txt = f"{conc_txt}%"
                        data["composition"].append({
                            "ingredient_name_vi": ing_name,
                            "ingredient_name_original": ing_name,
                            "cas_number": cas_val,
                            "cas_status": "VALID",
                            "concentration_text": conc_txt or "Xem chi tiết MSDS",
                            "concentration_min": c_min,
                            "concentration_max": c_max,
                            "unit": "%"
                        })

        # Quét bổ sung mọi số CAS hợp lệ còn lại trong văn bản
        cas_matches = CAS_REGEX.findall(text)
        valid_cases = [c["cas_number"] for c in data["composition"] if c.get("cas_number")]
        for m in cas_matches:
            cas_cand = f"{m[0]}-{m[1]}-{m[2]}"
            if cas_checksum_valid(cas_cand) and cas_cand not in valid_cases:
                valid_cases.append(cas_cand)
                data["composition"].append({
                    "ingredient_name_vi": f"Hợp chất CAS {cas_cand}",
                    "ingredient_name_original": f"Chemical Substance {cas_cand}",
                    "cas_number": cas_cand,
                    "cas_status": "VALID",
                    "concentration_text": "Xem chi tiết MSDS",
                    "concentration_min": None,
                    "concentration_max": None,
                    "unit": "%"
                })

        if valid_cases:
            data["cas_primary"] = valid_cases[0]

        # 3. Tìm số UN (nếu chưa bắt được qua bảng)
        if not data["un_no"]:
            un_m = UN_REGEX.search(text)
            if un_m:
                data["un_no"] = f"UN {un_m.group(1)}"

        # 4 & 5. Phân loại Mã GHS và Từ cảnh báo CHỈ TỪ PHẦN 2 (Nếu Phần 2 không có mối nguy -> NON DG)
        sec2_ghs = cls.classify_ghs_from_section_2(text)
        data["ghs_codes"] = sec2_ghs["ghs_codes"]
        data["signal_word"] = sec2_ghs["signal_word"]
        if sec2_ghs["is_non_dg"]:
            data["hazard_statements"] = "NON DG — Không phải là chất hay hỗn hợp nguy hại theo phân loại GHS (Phần 2)."

        # 6. Tìm điểm chớp cháy (nếu chưa có)
        if not data["flash_point"]:
            fp_m = re.search(r"(?:flash\s*point|điểm\s*chớp\s*cháy)[^\n\d]*([<>]?\s*-?\d+(?:\.\d+)?\s*(?:°?C|°?F))", text, re.IGNORECASE)
            if fp_m:
                data["flash_point"] = fp_m.group(1).strip()

        # 7. Tìm nhà cung cấp / nhà sản xuất (nếu chưa có)
        if not data["manufacturer"]:
            mfg_m = re.search(
                r"(?:manufacturer|supplier|company\s*name|company|nhà\s*sản\s*xuất|nhà\s*cung\s*cấp|tên\s*công\s*ty|đơn\s*vị\s*cung\s*cấp|企业名称|公司名称|供应商|制造商)[^\n:：]*[:：]\s*([^\n|]+)",
                text,
                re.IGNORECASE
            )
            if mfg_m:
                data["manufacturer"] = mfg_m.group(1).strip()[:120]
        if not data["manufacturer"]:
            for ln in lines[:45]:
                clean_ln = ln.replace("|", " ").strip()
                if re.search(r"\b(?:Co\.,?\s*Ltd|Company\s+Limited|GmbH|Industries\s+AG|Specialty\s+Chemicals|TNHH|Cổ\s+phần|Corporation|Inc\.)\b", clean_ln, re.IGNORECASE):
                    if len(clean_ln) <= 120:
                        data["manufacturer"] = clean_ln
                        break

        # Chuẩn hóa và dịch toàn bộ các trường sang Tiếng Việt
        data = cls.ensure_vietnamese_msds_fields(data)
        return data

    @classmethod
    def process_file(
        cls,
        file_path: str,
        api_key: Optional[str] = None,
        engine: Optional[str] = "deepseek",
        original_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Quy trình trích xuất hoàn chỉnh: Visual GHS Scan -> Text Extract -> Heuristic Baseline + DeepSeek AI -> Chuẩn hóa Tiếng Việt & Checksum."""
        text = cls.extract_text_from_file(file_path)
        p = Path(file_path)
        eff_filename = original_filename or p.name

        # 0. QUY TẮC NHẬN DIỆN HÌNH ĐỒ GHS TRỰC TIẾP TỪ ẢNH TRONG TÀI LIỆU (THEO YÊU CẦU NGƯỜI DÙNG)
        # Nhận diện chính xác dựa theo các hình đồ GHS thực tế mà tệp đang có (ở Mục 2),
        # KHÔNG dựa vào các mã/câu chữ phân loại để suy diễn thêm hình đồ.
        image_ghs = []
        try:
            from core.ghs_image_detector import GHSImageDetector
            image_ghs = GHSImageDetector.detect_ghs_pictograms_from_file(file_path)
        except Exception as img_err:
            print(f"[GHS_IMAGE_DETECT_WARN] {img_err}", flush=True)

        # Luôn chạy Heuristic để lấy chuẩn xác Mã sản phẩm, Phần 2 GHS (hoặc NON DG) và các trường bảng biểu
        heuristic_data = cls.parse_with_heuristic(text, filename=eff_filename)
        sec2_ghs = cls.classify_ghs_from_section_2(text)

        # Nếu có hình đồ thực tế từ ảnh, áp dụng ngay vào heuristic_data
        if image_ghs:
            heuristic_data["ghs_codes"] = list(image_ghs)
            heuristic_data["ghs_codes_list"] = list(image_ghs)
            if any(g in image_ghs for g in ("GHS01", "GHS02", "GHS05", "GHS06")):
                heuristic_data["signal_word"] = "Nguy hiểm (Danger)"
            elif any(g in image_ghs for g in ("GHS07", "GHS09")):
                heuristic_data["signal_word"] = "Cảnh báo (Warning)"
            else:
                heuristic_data["signal_word"] = "NON DG"

        parsed = None
        if engine != "heuristic":
            parsed = cls.parse_with_deepseek(text, api_key, visual_ghs_hint=image_ghs)

        if parsed and isinstance(parsed, dict):
            for k, v in heuristic_data.items():
                if not parsed.get(k) and v:
                    parsed[k] = v
            if heuristic_data.get("product_code"):
                parsed["product_code"] = heuristic_data["product_code"]

            # ƯU TIÊN TUYỆT ĐỐI HÌNH ĐỒ THỰC TẾ TRÊN TÀI LIỆU:
            # Nếu tệp vật lý có chứa hình đồ GHS ở Mục 2 (ví dụ: ZNZX009 chỉ có GHS02):
            # Bộ hình đồ nhận diện từ ảnh là DUY NHẤT và CHI PHỐI KẾT QUẢ,
            # TUYỆT ĐỐI KHÔNG thêm bất kỳ mã GHS nào từ câu chữ mô tả nguy cơ (loại bỏ hoàn toàn hình đồ từa lưa).
            if image_ghs:
                parsed["ghs_codes"] = list(image_ghs)
                parsed["ghs_codes_list"] = list(image_ghs)
                if any(g in image_ghs for g in ("GHS01", "GHS02", "GHS05", "GHS06")):
                    parsed["signal_word"] = "Nguy hiểm (Danger)"
                elif any(g in image_ghs for g in ("GHS07", "GHS09")):
                    parsed["signal_word"] = "Cảnh báo (Warning)"
                else:
                    parsed["signal_word"] = "NON DG"
            else:
                # Kiểm tra tuyên bố NON DG tường minh ở Mục 2
                is_explicit_non_dg = bool(sec2_ghs.get("is_non_dg"))

                # Kiểm tra đặc tính dễ cháy toàn tài liệu (bảo vệ chống gán nhầm NON DG)
                has_flam_h = bool(re.search(r"\bH22[0-8]\b", text, re.IGNORECASE))
                has_flam_phrase = bool(re.search(
                    r"\b(?:chất\s+(?:lỏng|khí|rắn)\s+dễ\s+cháy|hơi\s+và\s+chất\s+lỏng\s+(?:rất\s+)?dễ\s+cháy|flammable\s+(?:liquid|gas|solid|aerosol)|highly\s+flammable|extremely\s+flammable|易燃液体|易燃气体|易燃固体)\b",
                    text,
                    re.IGNORECASE
                ))
                fp_m = re.search(r"(?:flash\s*point|điểm\s*chớp\s*cháy)[^\n\d]*([<>]?\s*-?\d+(?:\.\d+)?)\s*°?C", text, re.IGNORECASE)
                has_low_fp = False
                if fp_m:
                    try:
                        fp_val = float(re.sub(r"[^\d.-]", "", fp_m.group(1)))
                        if fp_val <= 60.0:
                            has_low_fp = True
                    except Exception:
                        pass

                is_doc_flammable = bool(has_flam_h or has_flam_phrase or has_low_fp)
                if is_doc_flammable:
                    is_explicit_non_dg = False

                if is_explicit_non_dg and not is_doc_flammable:
                    selected_ghs = ["NON DG"]
                else:
                    sec2_text = cls.extract_section_2_text(text)
                    # Lấy danh sách GHS thô từ AI và từ Heuristic Mục 2
                    raw_ai_ghs = [str(c).strip().upper() for c in (parsed.get("ghs_codes") or []) if str(c).strip()]
                    raw_heu_ghs = [str(c).strip().upper() for c in (sec2_ghs.get("ghs_codes") or []) if str(c).strip()]
                    valid_ai_ghs = [g for g in raw_ai_ghs if g in GHS_MAP and g != "NON DG"]
                    valid_heu_ghs = [g for g in raw_heu_ghs if g in GHS_MAP and g != "NON DG"]

                    # Tuân thủ mệnh lệnh người dùng: "trong file ở mục 2 có hiển thị hình đồ GHS thì hiển thị lại đúng hình đồ cảnh báo GHS đó, không hiển thị Dư"
                    if valid_ai_ghs:
                        # Cross-validate AI codes against Section 2 / heuristic findings / text support
                        pruned_ai_ghs = []
                        for g in valid_ai_ghs:
                            if g in valid_heu_ghs:
                                pruned_ai_ghs.append(g)
                            else:
                                # Check if document Section 2 actually supports this specific code
                                g_support = False
                                if g == "GHS02" and is_doc_flammable:
                                    g_support = True
                                elif g == "GHS07" and re.search(r"\b(?:H302|H312|H332|H315|H319|H317|H335|H336|kích ứng|irritat)\b", sec2_text, re.I):
                                    g_support = True
                                elif g == "GHS05" and re.search(r"\b(?:H290|H314|H318|ăn mòn|corrosive)\b", sec2_text, re.I):
                                    g_support = True
                                elif g == "GHS06" and re.search(r"\b(?:H300|H301|H310|H311|H330|H331|độc cấp tính|toxic|fatal)\b", sec2_text, re.I):
                                    g_support = True
                                elif g == "GHS08" and re.search(r"\b(?:H304|H334|H340|H341|H350|H351|H360|H361|H370|H371|H372|H373)\b", sec2_text, re.I):
                                    g_support = True
                                elif g == "GHS09" and re.search(r"\b(?:H400|H410|H411|môi trường thủy sinh|aquatic)\b", sec2_text, re.I):
                                    g_support = True
                                if g_support:
                                    pruned_ai_ghs.append(g)
                        selected_ghs = pruned_ai_ghs if pruned_ai_ghs else list(valid_heu_ghs)
                    elif valid_heu_ghs:
                        selected_ghs = list(valid_heu_ghs)
                    else:
                        selected_ghs = []

                    # Nếu tài liệu có đặc tính dễ cháy rõ ràng, bắt buộc bổ sung GHS02 nếu chưa có
                    if is_doc_flammable and "GHS02" not in selected_ghs:
                        selected_ghs.append("GHS02")

                    if not selected_ghs:
                        if is_doc_flammable:
                            selected_ghs = ["GHS02"]
                        else:
                            selected_ghs = ["NON DG"]

                parsed["ghs_codes"] = sorted(list(set(selected_ghs)))
                if "NON DG" in parsed["ghs_codes"] and len(parsed["ghs_codes"]) > 1:
                    parsed["ghs_codes"] = [g for g in parsed["ghs_codes"] if g != "NON DG"]

                # Đồng bộ Từ cảnh báo (Signal Word) và Cảnh báo nguy hại tương ứng
                if "GHS02" in parsed["ghs_codes"] or any(g in parsed["ghs_codes"] for g in ("GHS01", "GHS05", "GHS06")):
                    if not parsed.get("signal_word") or parsed.get("signal_word") == "NON DG":
                        parsed["signal_word"] = "Nguy hiểm (Danger)"
                elif any(g in parsed["ghs_codes"] for g in ("GHS07", "GHS09")):
                    if not parsed.get("signal_word") or parsed.get("signal_word") == "NON DG":
                        parsed["signal_word"] = "Cảnh báo (Warning)"
                elif parsed["ghs_codes"] == ["NON DG"]:
                    parsed["signal_word"] = "NON DG"
                    parsed["hazard_statements"] = "NON DG — Không phải là chất hay hỗn hợp nguy hại theo phân loại GHS."
        else:
            parsed = heuristic_data
            if image_ghs:
                parsed["ghs_codes"] = list(image_ghs)
                parsed["ghs_codes_list"] = list(image_ghs)
                if any(g in image_ghs for g in ("GHS01", "GHS02", "GHS05", "GHS06")):
                    parsed["signal_word"] = "Nguy hiểm (Danger)"
                elif any(g in image_ghs for g in ("GHS07", "GHS09")):
                    parsed["signal_word"] = "Cảnh báo (Warning)"
                else:
                    parsed["signal_word"] = "NON DG"
            else:
                is_explicit_non_dg = bool(sec2_ghs.get("is_non_dg"))
                has_flam_h = bool(re.search(r"\bH22[0-8]\b", text, re.IGNORECASE))
                has_flam_phrase = bool(re.search(
                    r"\b(?:chất\s+(?:lỏng|khí|rắn)\s+dễ\s+cháy|hơi\s+và\s+chất\s+lỏng\s+(?:rất\s+)?dễ\s+cháy|flammable\s+(?:liquid|gas|solid|aerosol)|highly\s+flammable|extremely\s+flammable|易燃液体|易燃气体|易燃固体)\b",
                    text,
                    re.IGNORECASE
                ))
                fp_m = re.search(r"(?:flash\s*point|điểm\s*chớp\s*cháy)[^\n\d]*([<>]?\s*-?\d+(?:\.\d+)?)\s*°?C", text, re.IGNORECASE)
                has_low_fp = False
                if fp_m:
                    try:
                        fp_val = float(re.sub(r"[^\d.-]", "", fp_m.group(1)))
                        if fp_val <= 60.0:
                            has_low_fp = True
                    except Exception:
                        pass
                is_doc_flammable = bool(has_flam_h or has_flam_phrase or has_low_fp)
                if is_doc_flammable:
                    is_explicit_non_dg = False

                if is_explicit_non_dg:
                    parsed["ghs_codes"] = ["NON DG"]
                    parsed["signal_word"] = "NON DG"
                    parsed["hazard_statements"] = "NON DG — Không phải là chất hay hỗn hợp nguy hại theo phân loại GHS."
                else:
                    raw_heu_ghs = [str(c).strip().upper() for c in (sec2_ghs.get("ghs_codes") or []) if str(c).strip()]
                    selected_ghs = [g for g in raw_heu_ghs if g in GHS_MAP and g != "NON DG"]
                    if is_doc_flammable and "GHS02" not in selected_ghs:
                        selected_ghs.append("GHS02")
                    if not selected_ghs:
                        selected_ghs = ["GHS02"] if is_doc_flammable else ["NON DG"]
                    parsed["ghs_codes"] = sorted(list(set(selected_ghs)))
                    if "GHS02" in parsed["ghs_codes"] or any(g in parsed["ghs_codes"] for g in ("GHS01", "GHS05", "GHS06")):
                        if not parsed.get("signal_word") or parsed.get("signal_word") == "NON DG":
                            parsed["signal_word"] = "Nguy hiểm (Danger)"
                    elif any(g in parsed["ghs_codes"] for g in ("GHS07", "GHS09")):
                        if not parsed.get("signal_word") or parsed.get("signal_word") == "NON DG":
                            parsed["signal_word"] = "Cảnh báo (Warning)"
                    elif parsed["ghs_codes"] == ["NON DG"]:
                        parsed["signal_word"] = "NON DG"

        # Quy tắc bắt buộc: Mã hóa chất và Mã MSDS lấy theo Mã sản phẩm (ví dụ: FTU0005)
        final_code = cls._clean_product_code_candidate(str(parsed.get("product_code") or "")) or heuristic_data.get("product_code") or ""
        if final_code:
            parsed["product_code"] = final_code
            parsed["chemical_id"] = final_code
        else:
            parsed["chemical_id"] = parsed.get("chemical_id") or MSDSDatabase.next_chemical_id()
            parsed["product_code"] = parsed.get("product_code") or parsed["chemical_id"]

        # Đảm bảo 100% các trường thông tin an toàn đều bằng Tiếng Việt
        parsed = cls.ensure_vietnamese_msds_fields(parsed)

        parsed["source_file"] = eff_filename
        parsed["temp_uploaded_path"] = str(p.resolve()) if p.exists() else ""
        parsed["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""

        # Kiểm tra tính hợp lệ của toàn bộ các số CAS trong composition
        for comp in parsed.get("composition", []):
            cas_str = comp.get("cas_number", "")
            if cas_str:
                comp["cas_status"] = "VALID" if cas_checksum_valid(cas_str) else "REVIEW_REQUIRED"
            else:
                comp["cas_status"] = "NO_CAS_DATA"

        return parsed


# ==============================================================================
# 3. BỘ XUẤT BẢN FILE CIL EXCEL (CHEMICAL INVENTORY LIST) CHUẨN QUỐC TẾ
# ==============================================================================

class CILExcelExporter:
    """Bộ tạo và định dạng tệp Sổ Danh mục Hóa chất CIL Excel (.xlsx) chuyên nghiệp."""

    @classmethod
    def generate_cil_excel(cls, chemicals: Optional[List[Dict[str, Any]]] = None) -> Path:
        """Tạo file Excel CIL đa sheet với thiết kế chuẩn hóa an toàn EHS."""
        if chemicals is None:
            chemicals = MSDSDatabase.list_chemicals()
        chemicals = [MSDSExtractorEngine.ensure_vietnamese_msds_fields(dict(c)) for c in chemicals]

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = EXPORTS_DIR / f"Chemical_Inventory_List_CIL_{timestamp}.xlsx"

        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # Xóa sheet mặc định

        # Bảng màu chuẩn nhận diện Doanh nghiệp EHS
        NAVY_HEADER = "1B365D"
        EMERALD_SUB = "0F5C78"
        SLATE_BG = "F8FAFC"
        WHITE = "FFFFFF"
        BORDER_COLOR = "CBD5E1"

        font_title = Font(name="Calibri", size=16, bold=True, color=WHITE)
        font_header = Font(name="Calibri", size=11, bold=True, color=WHITE)
        font_data = Font(name="Calibri", size=10, color="0F172A")
        font_bold = Font(name="Calibri", size=10, bold=True, color="0F172A")
        font_danger = Font(name="Calibri", size=10, bold=True, color="DC2626")

        fill_title = PatternFill(start_color=NAVY_HEADER, end_color=NAVY_HEADER, fill_type="solid")
        fill_header = PatternFill(start_color=EMERALD_SUB, end_color=EMERALD_SUB, fill_type="solid")
        fill_zebra = PatternFill(start_color=SLATE_BG, end_color=SLATE_BG, fill_type="solid")
        fill_white = PatternFill(start_color=WHITE, end_color=WHITE, fill_type="solid")

        thin_border = Border(
            left=Side(style='thin', color=BORDER_COLOR),
            right=Side(style='thin', color=BORDER_COLOR),
            top=Side(style='thin', color=BORDER_COLOR),
            bottom=Side(style='thin', color=BORDER_COLOR)
        )

        align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
        align_left = Alignment(horizontal='left', vertical='center', wrap_text=True)

        # ----------------------------------------------------------------------
        # SHEET 1: 00_TỔNG_QUAN (DASHBOARD)
        # ----------------------------------------------------------------------
        ws0 = wb.create_sheet(title="00_TỔNG_QUAN")
        ws0.views.sheetView[0].showGridLines = True
        ws0.merge_cells("A1:G2")
        title_cell = ws0["A1"]
        title_cell.value = "SỔ QUẢN LÝ DANH MỤC HÓA CHẤT (CHEMICAL INVENTORY LIST - CIL)"
        title_cell.font = font_title
        title_cell.fill = fill_title
        title_cell.alignment = align_center

        ws0["A4"] = "CHỈ SỐ THỐNG KÊ"
        ws0["A4"].font = font_header
        ws0["A4"].fill = fill_header
        ws0["B4"] = "GIÁ TRỊ"
        ws0["B4"].font = font_header
        ws0["B4"].fill = fill_header

        total_chems = len(chemicals)
        total_cas = sum(len(c.get("composition", [])) for c in chemicals)
        flammable_count = sum(1 for c in chemicals if "GHS02" in str(c.get("ghs_codes", "")))
        toxic_count = sum(1 for c in chemicals if any(g in str(c.get("ghs_codes", "")) for g in ["GHS06", "GHS08"]))
        danger_count = sum(1 for c in chemicals if "danger" in str(c.get("signal_word", "")).lower() or "nguy hiểm" in str(c.get("signal_word", "")).lower())

        metrics = [
            ("Tổng số lượng hóa chất trong kho", total_chems),
            ("Tổng số lượng thành phần hoạt chất / Số CAS", total_cas),
            ("Số hóa chất thuộc nhóm Dễ Cháy (GHS02)", flammable_count),
            ("Số hóa chất thuộc nhóm Độc Hại / Nguy Hại Sức Khỏe", toxic_count),
            ("Số hóa chất có Từ Cảnh Báo 'Nguy Hiểm' (Danger)", danger_count),
            ("Thời điểm kết xuất báo cáo", datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
            ("Quy chuẩn áp dụng", "Luật Hóa chất số 69/2025/QH15, NĐ 24/2026/NĐ-CP, NĐ 25/2026/NĐ-CP, NĐ 26/2026/NĐ-CP, TT 01/2026/TT-BCT, TT 02/2026/TT-BCT & GHS")
        ]

        for idx, (label, val) in enumerate(metrics, start=5):
            ws0[f"A{idx}"] = label
            ws0[f"A{idx}"].font = font_data
            ws0[f"A{idx}"].border = thin_border
            ws0[f"B{idx}"] = val
            ws0[f"B{idx}"].font = font_bold
            ws0[f"B{idx}"].border = thin_border
            ws0[f"B{idx}"].alignment = align_center

        ws0.column_dimensions["A"].width = 45
        ws0.column_dimensions["B"].width = 30

        # ----------------------------------------------------------------------
        # SHEET 2: 01_DANH_MỤC_CIL (CHÍNH THỨC)
        # ----------------------------------------------------------------------
        ws1 = wb.create_sheet(title="01_DANH_MỤC_CIL")
        ws1.views.sheetView[0].showGridLines = True
        ws1.freeze_panes = "C3"

        ws1.merge_cells("A1:P1")
        w1_title = ws1["A1"]
        w1_title.value = "DANH MỤC HÓA CHẤT THEO DÕI NGUY HẠI (CHEMICAL INVENTORY LIST - CIL)"
        w1_title.font = font_title
        w1_title.fill = fill_title
        w1_title.alignment = align_center

        headers_c1 = [
            "STT", "Mã SP / MSDS", "Mã Sản Phẩm", "Tên Hóa Chất (Tiếng Việt)", "Tên Gốc (English / Trade)",
            "Số CAS Chính", "Nhà Cung Cấp / Sản Xuất", "Phân Loại GHS", "Từ Cảnh Báo", "Điểm Chớp Cháy",
            "Tỷ Trọng", "Vị Trí / Điều Kiện Bảo Quản", "Bảo Hộ Lao Động (PPE)",
            "Sơ Cứu Khẩn Cấp", "Mục Đích Sử Dụng", "Tệp MSDS Gốc"
        ]

        for col_idx, h in enumerate(headers_c1, 1):
            cell = ws1.cell(row=2, column=col_idx, value=h)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = align_center
            cell.border = thin_border

        for row_idx, c in enumerate(chemicals, 3):
            fill_current = fill_white if row_idx % 2 != 0 else fill_zebra
            ghs_str = ", ".join(c.get("ghs_codes_list", [])) if c.get("ghs_codes_list") else str(c.get("ghs_codes", ""))

            ppe_parts = []
            if c.get("respiratory_protection"): ppe_parts.append(f"Hô hấp: {c['respiratory_protection']}")
            if c.get("hand_protection"): ppe_parts.append(f"Tay: {c['hand_protection']}")
            if c.get("eye_protection"): ppe_parts.append(f"Mắt: {c['eye_protection']}")
            ppe_str = " | ".join(ppe_parts) or "Trang bị PPE tiêu chuẩn"

            first_aid_parts = []
            if c.get("first_aid_eyes"): first_aid_parts.append(f"Mắt: {c['first_aid_eyes']}")
            if c.get("first_aid_inhalation"): first_aid_parts.append(f"Hít: {c['first_aid_inhalation']}")
            first_aid_str = " | ".join(first_aid_parts) or "Rửa sạch với nước, đưa đi y tế nếu cần."

            row_data = [
                row_idx - 2,
                c.get("chemical_id", ""),
                c.get("product_code", ""),
                c.get("product_name_vi", ""),
                c.get("product_name_original", ""),
                c.get("cas_primary", ""),
                c.get("manufacturer", ""),
                ghs_str,
                c.get("signal_word", ""),
                c.get("flash_point", ""),
                c.get("density", ""),
                c.get("storage_condition", ""),
                ppe_str,
                first_aid_str,
                c.get("intended_use", ""),
                c.get("source_file", "")
            ]

            for col_idx, val in enumerate(row_data, 1):
                cell = ws1.cell(row=row_idx, column=col_idx, value=val)
                cell.font = font_danger if col_idx == 9 and "danger" in str(val).lower() else font_data
                cell.fill = fill_current
                cell.border = thin_border
                cell.alignment = align_center if col_idx in (1, 2, 3, 6, 9, 10, 11) else align_left

        # Tự động căn chỉnh độ rộng cột sheet 1
        for col in ws1.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws1.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 40)

        # ----------------------------------------------------------------------
        # SHEET 3: 02_CHI_TIẾT_CAS_THÀNH_PHẦN
        # ----------------------------------------------------------------------
        ws2 = wb.create_sheet(title="02_CHI_TIẾT_CAS")
        ws2.views.sheetView[0].showGridLines = True
        ws2.freeze_panes = "C3"

        ws2.merge_cells("A1:I1")
        w2_title = ws2["A1"]
        w2_title.value = "DANH SÁCH CHI TIẾT THÀNH PHẦN HOẠT CHẤT & SỐ CAS (INGREDIENT BREAKDOWN)"
        w2_title.font = font_title
        w2_title.fill = fill_title
        w2_title.alignment = align_center

        headers_c2 = [
            "STT", "Mã Hóa Chất", "Tên Hóa Chất Thương Mại", "Tên Thành Phần Hoạt Chất",
            "Số CAS Chuẩn", "Tính Hợp Lệ Checksum", "Hàm Lượng %", "Ngưỡng Min %", "Ngưỡng Max %"
        ]

        for col_idx, h in enumerate(headers_c2, 1):
            cell = ws2.cell(row=2, column=col_idx, value=h)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = align_center
            cell.border = thin_border

        curr_r = 3
        stt_cas = 1
        for c in chemicals:
            comps = c.get("composition", [])
            for cp in comps:
                fill_current = fill_white if curr_r % 2 != 0 else fill_zebra
                cas_val = cp.get("cas_number", "")
                is_valid = cas_checksum_valid(cas_val) if cas_val else False
                status_str = "HỢP LỆ (VALID)" if is_valid else ("CHƯA RÕ" if not cas_val else "CẦN RÀ SOÁT")

                row_vals = [
                    stt_cas,
                    c.get("chemical_id", ""),
                    c.get("product_name_vi", ""),
                    cp.get("ingredient_name_vi") or cp.get("ingredient_name_original", ""),
                    cas_val,
                    status_str,
                    cp.get("concentration_text", ""),
                    cp.get("concentration_min", ""),
                    cp.get("concentration_max", "")
                ]

                for col_idx, val in enumerate(row_vals, 1):
                    cell = ws2.cell(row=curr_r, column=col_idx, value=val)
                    cell.font = font_data
                    cell.fill = fill_current
                    cell.border = thin_border
                    cell.alignment = align_center if col_idx in (1, 2, 5, 6, 8, 9) else align_left

                curr_r += 1
                stt_cas += 1

        for col in ws2.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws2.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 36)

        # ----------------------------------------------------------------------
        # SHEET 4: 03_THẺ_SƠ_CỨU_KHẨN_CẤP
        # ----------------------------------------------------------------------
        ws3 = wb.create_sheet(title="03_SƠ_CỨU_KHẨN_CẤP")
        ws3.views.sheetView[0].showGridLines = True
        ws3.freeze_panes = "C3"

        ws3.merge_cells("A1:H1")
        w3_title = ws3["A1"]
        w3_title.value = "HƯỚNG DẪN ỨNG PHÓ SỰ CỐ & SƠ CỨU KHẨN CẤP (EMERGENCY RESPONSE PROTOCOL)"
        w3_title.font = font_title
        w3_title.fill = fill_title
        w3_title.alignment = align_center

        headers_c3 = [
            "STT", "Mã Hóa Chất", "Tên Hóa Chất", "Sơ Cứu Hít Phải", "Sơ Cứu Dính Da",
            "Sơ Cứu Dính Mắt", "Sơ Cứu Nuốt Phải", "Biện Pháp Dập Lửa"
        ]

        for col_idx, h in enumerate(headers_c3, 1):
            cell = ws3.cell(row=2, column=col_idx, value=h)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = align_center
            cell.border = thin_border

        for row_idx, c in enumerate(chemicals, 3):
            fill_current = fill_white if row_idx % 2 != 0 else fill_zebra
            row_data = [
                row_idx - 2,
                c.get("chemical_id", ""),
                c.get("product_name_vi", ""),
                c.get("first_aid_inhalation", "Đưa ra nơi thoáng khí, thở oxy nếu cần."),
                c.get("first_aid_skin", "Cởi bỏ quần áo dính hóa chất, rửa bằng xà phòng và nước."),
                c.get("first_aid_eyes", "Xối nước rửa mắt liên tục ít nhất 15 phút."),
                c.get("first_aid_ingestion", "Súc miệng, không gây nôn, đưa ngay đi cấp cứu."),
                c.get("fire_measures", "Bọt chữa cháy, CO2, cát khô. Không dùng tia nước áp lực cao.")
            ]

            for col_idx, val in enumerate(row_data, 1):
                cell = ws3.cell(row=row_idx, column=col_idx, value=val)
                cell.font = font_data
                cell.fill = fill_current
                cell.border = thin_border
                cell.alignment = align_center if col_idx in (1, 2) else align_left

        for col in ws3.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws3.column_dimensions[col_letter].width = min(max(max_len + 3, 15), 50)

        wb.save(str(out_path))
        return out_path


# ==============================================================================
# 4. BỘ XUẤT THẺ AN TOÀN KHẨN CẤP (EMERGENCY CARD) WORD DOCX
# ==============================================================================

def to_unaccented_slug(text: Any) -> str:
    """Chuyển đổi chuỗi tiếng Việt có dấu sang định dạng không dấu chuẩn ASCII an toàn cho tên tệp."""
    if not text:
        return ""
    text_str = str(text).replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFKD", text_str)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    clean = re.sub(r"[^\w\-]+", "_", ascii_text, flags=re.ASCII)
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean


class MSDSSafetyCardExporter:
    """Xuất thẻ tóm tắt an toàn hóa chất khẩn cấp ra Word (.docx)."""

    GHS_VI_LABELS = {
        "GHS01": "♦ GHS01 (Chất nổ)",
        "GHS02": "♦ GHS02 (Chất dễ cháy)",
        "GHS03": "♦ GHS03 (Chất oxy hóa)",
        "GHS04": "♦ GHS04 (Khí nén áp suất)",
        "GHS05": "♦ GHS05 (Chất ăn mòn)",
        "GHS06": "♦ GHS06 (Độc cấp tính)",
        "GHS07": "♦ GHS07 (Kích ứng / Cảnh báo)",
        "GHS08": "♦ GHS08 (Nguy hại sức khỏe)",
        "GHS09": "♦ GHS09 (Nguy hại môi trường)",
        "NON DG": "✓ NON DG (Không phân loại nguy hại theo Phần 2 GHS)",
    }

    @classmethod
    def generate_safety_card_docx(cls, chem_data: Dict[str, Any], custom_path: Optional[Path] = None) -> Path:
        from core.legal_engine import validate_cas
        chem_data = MSDSExtractorEngine.ensure_vietnamese_msds_fields(dict(chem_data))
        doc = docx.Document()

        # Cài đặt lề trang A4 nhỏ gọn
        for s in doc.sections:
            s.top_margin = Inches(0.5)
            s.bottom_margin = Inches(0.5)
            s.left_margin = Inches(0.5)
            s.right_margin = Inches(0.5)

        # Tiêu đề Thẻ An Toàn
        p_title = doc.add_paragraph()
        p_title.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER
        run = p_title.add_run("THẺ AN TOÀN HÓA CHẤT KHẨN CẤP")
        run.bold = True
        run.font.size = Pt(16)
        run.font.color.rgb = RGBColor(27, 54, 93)

        p_sub = doc.add_paragraph()
        p_sub.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER
        item_type_label = chem_data.get('item_type') or ('Thành phẩm' if chem_data.get('product_code') else 'Nguyên liệu')
        run_sub = p_sub.add_run(
            f"Hóa chất: {chem_data.get('product_name_vi', '')} | Phân loại: [{item_type_label}] | Mã SP/MSDS: {chem_data.get('chemical_id', '')} | CAS: {chem_data.get('cas_primary', 'Chưa xác định')}"
        )
        run_sub.bold = True
        run_sub.font.size = Pt(11)

        ghs_list = chem_data.get("ghs_codes_list") or [g.strip() for g in str(chem_data.get("ghs_codes", "")).split(",") if g.strip()]
        ghs_vi_str = " | ".join(cls.GHS_VI_LABELS.get(g.upper(), g) for g in ghs_list) if ghs_list else "✓ NON DG (Không phân loại nguy hại theo Phần 2 GHS)"

        # Bảng tóm tắt thông tin nhanh
        table = doc.add_table(rows=9, cols=2)
        table.style = 'Table Grid'

        fields = [
            ("Nhà Cung Cấp / Sản Xuất", chem_data.get('manufacturer') or 'Theo hồ sơ MSDS của nhà cung cấp'),
            ("Từ Cảnh Báo & Hình Đồ GHS", f"{chem_data.get('signal_word', '')}\n{ghs_vi_str}"),
            ("Cảnh Báo Nguy Cơ & Phòng Ngừa", f"Nguy cơ: {chem_data.get('hazard_statements', '')}\nPhòng ngừa: {chem_data.get('precautionary_statements', '')}"),
            ("Điểm Chớp Cháy & Ngoại Quan", f"Chớp cháy: {chem_data.get('flash_point', 'Không áp dụng')} | Ngoại quan: {chem_data.get('appearance', '')}"),
            ("Trang Bị Bảo Hộ Cá Nhân (PPE)", f"Mắt: {chem_data.get('eye_protection', '')}\nHô hấp: {chem_data.get('respiratory_protection', '')}\nTay: {chem_data.get('hand_protection', '')}\nDa & Thân: {chem_data.get('skin_protection', '')}"),
            ("Biện Pháp Sơ Cứu (Hít / Da)", f"Hít phải: {chem_data.get('first_aid_inhalation', '')}\nTiếp xúc da: {chem_data.get('first_aid_skin', '')}"),
            ("Biện Pháp Sơ Cứu (Mắt / Nuốt)", f"Tiếp xúc mắt: {chem_data.get('first_aid_eyes', '')}\nNuốt phải: {chem_data.get('first_aid_ingestion', '')}"),
            ("Ứng Phó Cháy Nổ", chem_data.get('fire_measures', 'Dùng bột khô, bọt chữa cháy, khí CO2 hoặc phun sương nước.')),
            ("Điều Kiện Lưu Trữ & Bảo Quản", chem_data.get('storage_condition', 'Đậy kín thùng chứa, bảo quản nơi khô ráo, thoáng mát.'))
        ]

        for i, (k, v) in enumerate(fields):
            row = table.rows[i]
            row.cells[0].text = k
            row.cells[1].text = v
            row.cells[0].paragraphs[0].runs[0].bold = True
            row.cells[0].width = Inches(2.2)
            row.cells[1].width = Inches(5.0)

        # -------------------------------------------------------------
        # 🧪 BẢNG THÀNH PHẦN HÓA HỌC & SỐ CAS (MỤC 3 GHS)
        # -------------------------------------------------------------
        doc.add_paragraph()  # Đoạn đệm giãn dòng
        p_comp_title = doc.add_paragraph()
        run_comp_title = p_comp_title.add_run("🧪 BẢNG THÀNH PHẦN HÓA HỌC & SỐ CAS (MỤC 3 GHS)")
        run_comp_title.bold = True
        run_comp_title.font.size = Pt(12)
        run_comp_title.font.color.rgb = RGBColor(27, 54, 93)

        # Lấy danh sách thành phần
        compositions = chem_data.get("composition") or []
        if not compositions and chem_data.get("chemical_id"):
            try:
                db_chem = MSDSDatabase.get_chemical(chem_data["chemical_id"])
                if db_chem and db_chem.get("composition"):
                    compositions = db_chem["composition"]
            except Exception:
                pass

        # Đảm bảo bảng Mục 3 GHS luôn có ít nhất 1 dòng thành phần hợp lệ
        if not compositions:
            cas_p = str(chem_data.get("cas_primary") or "").strip()
            name_p = chem_data.get("product_name_vi") or chem_data.get("product_name_original") or "Thành phần theo công bố nhà sản xuất"
            val_p = validate_cas(cas_p) if cas_p else {"status": "KHÔNG CÓ CAS"}
            compositions = [{
                "ingredient_name_vi": name_p,
                "cas_number": cas_p or "Bí mật thương mại",
                "concentration_text": "100%" if cas_p else "Xem MSDS",
                "cas_status": val_p.get("status", "HỢP LỆ")
            }]

        comp_table = doc.add_table(rows=len(compositions) + 1, cols=4)
        comp_table.style = 'Table Grid'

        headers = ["Tên Thành Phần Hoạt Chất", "Số CAS", "Hàm Lượng (%)", "Thẩm Định Checksum"]
        col_widths = [Inches(2.8), Inches(1.5), Inches(1.4), Inches(1.5)]

        # Tiêu đề bảng
        hdr_row = comp_table.rows[0]
        for j, h_text in enumerate(headers):
            cell = hdr_row.cells[j]
            cell.text = h_text
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if p.runs:
                p.runs[0].bold = True
                p.runs[0].font.size = Pt(9.5)
                p.runs[0].font.color.rgb = RGBColor(27, 54, 93)
            cell.width = col_widths[j]
            shd = parse_xml(r'<w:shd {} w:fill="EBF3FB"/>'.format(nsdecls('w')))
            cell._tc.get_or_add_tcPr().append(shd)

        # Dòng dữ liệu thành phần
        for i, comp in enumerate(compositions, start=1):
            row = comp_table.rows[i]
            c_name = comp.get("ingredient_name_vi") or comp.get("ingredient_name_original") or "Chưa rõ tên"
            c_cas = comp.get("cas_number") or comp.get("cas_no") or "Bí mật thương mại"
            c_conc = comp.get("concentration_text") or (
                f"{comp.get('concentration_min', 0)} - {comp.get('concentration_max', 0)}%"
                if comp.get('concentration_min') is not None else "Xem MSDS"
            )
            c_status = comp.get("cas_status")
            if not c_status or str(c_status).upper() in ("VALID", "HOP_LE", "HỢP LỆ", "TRUE", "1"):
                v_res = validate_cas(c_cas)
                c_status = v_res.get("status", "HỢP LỆ")
            elif "SAI" in str(c_status).upper() or "INVALID" in str(c_status).upper():
                c_status = "SAI CHECKSUM"
            elif "KHÔNG" in str(c_status).upper() or "NONE" in str(c_status).upper():
                c_status = "KHÔNG CÓ CAS"

            vals = [c_name, c_cas, c_conc, c_status]
            aligns = [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.CENTER]

            for j, (val, aln) in enumerate(zip(vals, aligns)):
                cell = row.cells[j]
                cell.text = str(val)
                p = cell.paragraphs[0]
                p.alignment = aln
                if p.runs:
                    p.runs[0].font.size = Pt(9.0)
                    if j == 3 and ("CẦN" in str(val).upper() or "SAI" in str(val).upper()):
                        p.runs[0].font.color.rgb = RGBColor(217, 119, 6)
                    elif j == 3 and "HỢP" in str(val).upper():
                        p.runs[0].font.color.rgb = RGBColor(22, 163, 74)
                    elif j == 3:
                        p.runs[0].font.color.rgb = RGBColor(100, 116, 139)
                cell.width = col_widths[j]

                if i % 2 == 0:
                    shd = parse_xml(r'<w:shd {} w:fill="F8FAFC"/>'.format(nsdecls('w')))
                    cell._tc.get_or_add_tcPr().append(shd)

        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        if custom_path:
            out_path = Path(custom_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            chem_code = chem_data.get('chemical_id', 'CHEM').replace("-", "_")
            out_path = EXPORTS_DIR / f"Safety_Card_{chem_code}_{timestamp}.docx"
        doc.save(str(out_path))
        return out_path

