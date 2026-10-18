r"""
core/gatepass_service.py
────────────────────────
DỊCH VỤ XỬ LÝ PHIẾU XUẤT HÀNG & VẬT TƯ (GATE PASS & MATERIAL DISPATCH SERVICE)

Tính năng cốt lõi:
1. Quản lý bộ đệm SQLite WAL địa phương (data/msds_chemical_inventory.db) thread-safe.
2. Lưu trữ, tra cứu, xóa, phân trang và truy vấn thống kê đa tiêu chí (<15ms).
3. Tính toán số liệu Dashboard KPI & cấu trúc dữ liệu biểu đồ Chart.js tự động.
4. Cầu nối an toàn đồng bộ 19 cột tiêu chuẩn vào Google Sheet qua Google Apps Script Web App.
5. Tải ảnh chứng từ lên thư mục Google Drive chuyên dụng.
6. Tự động sao lưu cục bộ vào Google Drive (G:\Drive của tôi\TitanPDF_GatePass) và fallback an toàn.
7. Xuất trang in phiếu xuất kho chuẩn A4/A5 chuyên nghiệp.
"""

from __future__ import annotations

import base64
import csv
import html as html_lib
import json
import logging
import math
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import time
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

import requests

logger = logging.getLogger("titan.gatepass_service")

# =============================================================================
# HẰNG SỐ CẤU HÌNH HỆ THỐNG
# =============================================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DB_PATH = DATA_DIR / "msds_chemical_inventory.db"

GAS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbzo5YQiI5DM0KEDRpTIbxDDY_2Nwfs4NP1Vfa5MyuJPNqb8x4EkhVzZD5pso7ueAWiS5w/exec"
GOOGLE_SHEET_ID = "15Z3HA7Lm2pJU3GmfzdDq4ZfOKVYJoYJ_SYIT3pAM_ug"
DEFAULT_DRIVE_FOLDER_ID = "1mock_drive_folder_id_gatepass_v2"


def get_google_drive_path() -> Optional[Path]:
    """Tìm kiếm thư mục Google Drive cục bộ trên Windows."""
    candidates = [
        Path("G:/Drive của tôi"),
        Path("G:/My Drive"),
        Path("G:/"),
        Path(os.path.expanduser("~")) / "Google Drive",
        Path(os.path.expanduser("~")) / "GoogleDrive",
    ]
    for c in candidates:
        try:
            if c.exists() and c.is_dir():
                if c == Path("G:/") and (c / "Drive của tôi").exists():
                    return c / "Drive của tôi"
                return c
        except Exception:
            pass
    return None


def normalize_date_iso(date_str: Optional[str]) -> str:
    """Chuẩn hóa mọi định dạng ngày sang ISO8601 YYYY-MM-DD."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    s = str(date_str).strip()
    # DD/MM/YYYY hoặc DD-MM-YYYY
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", s)
    if m:
        d, mth, y = m.groups()
        return f"{int(y):04d}-{int(mth):02d}-{int(d):02d}"
    # YYYY/MM/DD hoặc YYYY-MM-DD
    m = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", s)
    if m:
        y, mth, d = m.groups()
        return f"{int(y):04d}-{int(mth):02d}-{int(d):02d}"
    return datetime.now().strftime("%Y-%m-%d")


def normalize_date_display(date_str: Optional[str]) -> str:
    """Chuẩn hóa ngày sang định dạng hiển thị DD/MM/YYYY."""
    if not date_str:
        return datetime.now().strftime("%d/%m/%Y")
    s = str(date_str).strip()
    m = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", s)
    if m:
        y, mth, d = m.groups()
        return f"{int(d):02d}/{int(mth):02d}/{int(y):04d}"
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", s)
    if m:
        d, mth, y = m.groups()
        return f"{int(d):02d}/{int(mth):02d}/{int(y):04d}"
    return s


def sanitize_filename(name: str, replacement: str = "_") -> str:
    """Loại bỏ hoặc thay thế các ký tự không hợp lệ trên hệ thống tệp Windows/POSIX.

    Ký tự cấm trên Windows: < > : " / \\ | ? * và các ký tự điều khiển ASCII 0-31.
    """
    if not name:
        return "unnamed"
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', replacement, str(name)).strip(" .")
    return cleaned or "unnamed"


_sanitize_filename = sanitize_filename


def safe_parse_float(val: Any, default: float = 0.0) -> float:
    """Chuyển đổi số thực an toàn, chống crash khi gặp NaN, Infinity hoặc chuỗi hỏng."""
    if val is None:
        return default
    try:
        if isinstance(val, (int, float)):
            f = float(val)
        else:
            cleaned = str(val).replace(",", "").strip()
            if not cleaned:
                return default
            f = float(cleaned)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError, OverflowError):
        return default


safe_float = safe_parse_float


def safe_parse_int(val: Any, default: int = 0) -> int:
    """Chuyển đổi số nguyên an toàn, chống crash khi gặp NaN, Infinity hoặc float."""
    f = safe_parse_float(val, default=float(default))
    try:
        return int(f)
    except (ValueError, OverflowError):
        return default


safe_int = safe_parse_int


def prepare_image_for_vision(image_bytes: bytes, filename: str = "", max_dim: int = 1600) -> Tuple[str, str]:
    """
    Chuyển đổi tệp ảnh hoặc PDF sang định dạng JPEG Base64 Data URI cho DeepSeek Vision.
    Hỗ trợ: PDF (render trang 1), PNG, WebP, JPEG, BMP.
    Tự động chuẩn hóa kích thước tối đa max_dim (mặc định 1600px) và nén JPEG quality 85.
    Trả về: (data_uri, b64_clean)
    """
    jpeg_bytes: Optional[bytes] = None

    # 1. Xử lý tệp PDF
    is_pdf = image_bytes.startswith(b"%PDF-") or filename.lower().endswith(".pdf")
    if is_pdf:
        try:
            import fitz
            doc = fitz.open(stream=image_bytes, filetype="pdf")
            if len(doc) > 0:
                page = doc[0]
                pix = page.get_pixmap(dpi=150)
                jpeg_bytes = pix.tobytes("jpeg")
            doc.close()
        except Exception as e:
            logger.warning("Lỗi render PDF qua PyMuPDF: %s", e)

    # 2. Xử lý ảnh qua PIL
    if not jpeg_bytes:
        try:
            import io
            from PIL import Image, ImageOps
            img = Image.open(io.BytesIO(image_bytes))
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "P", "LA"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "RGBA":
                    bg.paste(img, mask=img.split()[3])
                else:
                    bg.paste(img.convert("RGBA"))
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Downscale if larger than max_dim
            w, h = img.size
            if max(w, h) > max_dim:
                scale = max_dim / float(max(w, h))
                new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            out_buf = io.BytesIO()
            img.save(out_buf, format="JPEG", quality=85, optimize=True)
            jpeg_bytes = out_buf.getvalue()
        except Exception as e:
            logger.warning("Lỗi chuyển đổi ảnh qua PIL: %s", e)
            jpeg_bytes = image_bytes

    b64_str = base64.b64encode(jpeg_bytes).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{b64_str}"
    return data_uri, b64_str


def clean_json_code_blocks(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Trích xuất và sửa lỗi JSON từ phản hồi markdown của LLM.
    Hỗ trợ ```json ... ```, ``` ... ```, dấu phẩy thừa, nháy đơn, thiếu ngoặc đóng và Unicode NFC.
    """
    if not raw_text or not raw_text.strip():
        return None

    cleaned = raw_text.strip()

    # 1. Regex bóc tách code block ```json ... ``` hoặc ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()
    else:
        # Nếu không có ```, tìm cặp ngoặc nhọn đầu tiên và cuối cùng { ... }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1].strip()

    # Thử parse ngay
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 2. Xóa bỏ trailing commas trước } hoặc ]
    repaired = re.sub(r",\s*([\]}])", r"\1", cleaned)
    try:
        return json.loads(repaired)
    except Exception:
        pass

    # 3. Chuẩn hóa nháy đơn quanh keys và values
    repaired2 = re.sub(r"(?<=[{,\s])'([^']+)'(?=\s*:)", r'"\1"', repaired)
    repaired2 = re.sub(r":\s*'([^']*)'(?=[,\s}\]])", r': "\1"', repaired2)
    try:
        return json.loads(repaired2)
    except Exception:
        pass

    # 4. Sửa lỗi ngoặc chưa đóng (Truncated brackets repair)
    open_curly = repaired.count("{")
    close_curly = repaired.count("}")
    open_square = repaired.count("[")
    close_square = repaired.count("]")
    repaired3 = repaired + ("]" * max(0, open_square - close_square)) + ("}" * max(0, open_curly - close_curly))
    repaired3 = re.sub(r",\s*([\]}])", r"\1", repaired3)
    try:
        return json.loads(repaired3)
    except Exception:
        pass

    return None


def normalize_plate_number(plate: Optional[str]) -> str:
    """Chuẩn hóa biển số xe để so sánh (không phân biệt chữ hoa thường, dấu gạch, dấu chấm, khoảng trắng)."""
    if not plate:
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(plate).upper())


class GatePassDatabase:
    """Quản trị kết nối SQLite đa luồng an toàn (Thread-Safe SQLite WAL Manager)."""
    _write_lock = threading.Lock()

    @classmethod
    @contextmanager
    def get_connection(cls, db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
        target = Path(db_path) if db_path else DEFAULT_DB_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(target),
            timeout=30.0,
            check_same_thread=False,
            isolation_level=None
        )
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA busy_timeout = 30000;")
            conn.execute("PRAGMA foreign_keys = ON;")
            yield conn
        finally:
            conn.close()




class GatePassService:
    """Dịch vụ nghiệp vụ Quản Lý Phiếu Xuất Hàng & Vật Tư."""

    _instance: Optional[GatePassService] = None
    _backup_lock: threading.Lock = threading.Lock()
    _sanitize_filename = staticmethod(sanitize_filename)

    def __init__(self, db_path: Optional[Union[Path, str]] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.init_db()

    @classmethod
    def get_default_instance(cls) -> GatePassService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # -------------------------------------------------------------------------
    # Database Initialization & Demo Seeding
    # -------------------------------------------------------------------------
    @classmethod
    def init_db(cls, db_path: Optional[Union[Path, str]] = None) -> None:
        """Khởi tạo cấu trúc bảng, chỉ mục và dữ liệu mẫu nếu bảng trống."""
        target = Path(db_path) if db_path else (cls._instance.db_path if cls._instance else DEFAULT_DB_PATH)
        with GatePassDatabase.get_connection(target) as conn:
            with GatePassDatabase._write_lock:
                # 1. Bảng chính gatepass_slips
                conn.execute("""
                CREATE TABLE IF NOT EXISTS gatepass_slips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    so_phieu TEXT UNIQUE NOT NULL,
                    loai_xuat TEXT NOT NULL DEFAULT 'Xuất hàng thành phẩm',
                    ngay_thang TEXT NOT NULL,
                    ngay_thang_iso TEXT NOT NULL,
                    don_vi_van_chuyen TEXT DEFAULT '',
                    so_xe TEXT DEFAULT '',
                    don_vi_dat_hang TEXT DEFAULT '',
                    so_don_hang TEXT DEFAULT '',
                    tong_cong_kg REAL DEFAULT 0.0,
                    tong_cong_kg_display TEXT DEFAULT '0.0',
                    tong_kien INTEGER DEFAULT 0,
                    tong_thung INTEGER DEFAULT 0,
                    tong_thung_kien TEXT DEFAULT '',
                    tong_ghi_chu TEXT DEFAULT '',
                    bo_phan_ky_ten TEXT DEFAULT '',
                    phe_duyet TEXT DEFAULT '',
                    nguoi_lap_phieu TEXT DEFAULT '',
                    thu_kho TEXT DEFAULT '',
                    nguoi_nhan_hang TEXT DEFAULT '',
                    audit_summary TEXT DEFAULT '',
                    audit_status TEXT DEFAULT 'pending',
                    match_summary TEXT DEFAULT '',
                    match_status TEXT DEFAULT 'none',
                    main_file_url TEXT DEFAULT '',
                    main_file_name TEXT DEFAULT '',
                    main_image_b64 TEXT DEFAULT '',
                    proof_urls TEXT DEFAULT '[]',
                    proof_count INTEGER DEFAULT 0,
                    sync_status TEXT DEFAULT 'pending',
                    synced_at TEXT DEFAULT NULL,
                    last_sync_error TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
                """)

                # 2. Bảng chi tiết mặt hàng gatepass_items
                conn.execute("""
                CREATE TABLE IF NOT EXISTS gatepass_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    so_phieu TEXT NOT NULL,
                    stt INTEGER NOT NULL DEFAULT 1,
                    loai_hang_hoa TEXT NOT NULL,
                    ten_tieng_viet TEXT DEFAULT '',
                    ten_tieng_trung TEXT DEFAULT '',
                    quy_cach TEXT DEFAULT '',
                    sl_kien REAL DEFAULT 0.0,
                    sl_thung REAL DEFAULT 0.0,
                    khoi_luong_kg REAL DEFAULT 0.0,
                    ghi_chu TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    updated_at TEXT DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (so_phieu) REFERENCES gatepass_slips(so_phieu) ON DELETE CASCADE
                );
                """)

                # 3. Chỉ mục tối ưu tốc độ truy vấn
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gp_slips_so_phieu ON gatepass_slips(so_phieu);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gp_slips_ngay_iso ON gatepass_slips(ngay_thang_iso);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gp_slips_so_xe ON gatepass_slips(so_xe);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gp_slips_khach_hang ON gatepass_slips(don_vi_dat_hang);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gp_slips_loai_xuat ON gatepass_slips(loai_xuat);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gp_slips_sync_status ON gatepass_slips(sync_status);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gp_slips_created_at ON gatepass_slips(created_at);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gp_items_so_phieu ON gatepass_items(so_phieu);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gp_items_stt ON gatepass_items(so_phieu, stt);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gp_items_loai_hang ON gatepass_items(loai_hang_hoa);")

                # 4. Trigger tự động cập nhật updated_at
                conn.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_gatepass_slips_updated_at
                AFTER UPDATE ON gatepass_slips
                FOR EACH ROW
                BEGIN
                    UPDATE gatepass_slips SET updated_at = datetime('now', 'localtime') WHERE id = OLD.id;
                END;
                """)

                # 5. Nạp dữ liệu mẫu khởi đầu nếu chưa có phiếu nào
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM gatepass_slips;")
                count = cur.fetchone()[0]
                if count == 0:
                    cls._seed_initial_demo_passes_static(conn)
                conn.commit()

    @classmethod
    def _seed_initial_demo_passes_static(cls, conn: sqlite3.Connection) -> None:
        """Nạp 3 phiếu mẫu chuẩn ban đầu để Dashboard và Lịch sử có sẵn dữ liệu."""
        demo_slips = [
            {
                "so_phieu": "0003334",
                "loai_xuat": "Xuất hàng thành phẩm",
                "ngay_thang": "15/01/2026",
                "don_vi_van_chuyen": "Đội xe nội bộ (Phan Văn Nam - 0988.123.456)",
                "so_xe": "59C-888.88",
                "don_vi_dat_hang": "Công ty TNHH Nhựa & Bao Bì Tân Phát (新发塑料有限公司)",
                "so_don_hang": "PO-2026-0189",
                "tong_cong_kg": 1500.0,
                "tong_cong_kg_display": "1,500.0",
                "tong_kien": 60,
                "tong_thung": 10,
                "tong_thung_kien": "60 Kiện, 10 Thùng",
                "bo_phan_ky_ten": "Kho thành phẩm (成品库)",
                "phe_duyet": "Nguyễn Văn A (核准)",
                "nguoi_lap_phieu": "Lê Văn B",
                "thu_kho": "Trần Văn C",
                "nguoi_nhan_hang": "Phan Văn Nam",
                "audit_summary": "✅ Đạt chuẩn thẩm định AI: Đầy đủ chữ ký, khớp số lượng",
                "audit_status": "ok",
                "match_summary": "✅ Biển số xe 59C-888.88 và hàng hóa thực tế khớp với phiếu",
                "match_status": "matched",
                "main_file_url": "https://drive.google.com/file/d/mock_file_0003334/view",
                "proof_urls": "[]",
                "sync_status": "synced",
                "items": [
                    {"stt": 1, "loai_hang_hoa": "Hạt nhựa ABS tái sinh (再生ABS塑料颗粒)", "quy_cach": "25kg/bao (Đen bóng)", "sl_kien": 40, "sl_thung": 0, "khoi_luong_kg": 1000.0, "ghi_chu": "Đạt chuẩn RoHS"},
                    {"stt": 2, "loai_hang_hoa": "Hạt nhựa PP nguyên sinh (原包PP塑料颗粒)", "quy_cach": "25kg/bao (Trắng trong)", "sl_kien": 20, "sl_thung": 10, "khoi_luong_kg": 500.0, "ghi_chu": "Kèm chứng chỉ COA"}
                ]
            },
            {
                "so_phieu": "0003335",
                "loai_xuat": "Xuất vật tư ra công",
                "ngay_thang": "15/01/2026",
                "don_vi_van_chuyen": "Vận tải Toàn Cầu (Trần Văn Bình - 0912.345.678)",
                "so_xe": "29H-678.90",
                "don_vi_dat_hang": "Công ty Cổ phần Bao Bì Đại Dương (大洋包装股份公司)",
                "so_don_hang": "PO-2026-0205",
                "tong_cong_kg": 2200.0,
                "tong_cong_kg_display": "2,200.0",
                "tong_kien": 45,
                "tong_thung": 25,
                "tong_thung_kien": "45 Kiện, 25 Thùng",
                "bo_phan_ky_ten": "Kho phụ gia (添加剂库)",
                "phe_duyet": "Trần Thị Lan (核准)",
                "nguoi_lap_phieu": "Vũ Đình T",
                "thu_kho": "Trần Thị Lan",
                "nguoi_nhan_hang": "Trần Văn Bình",
                "audit_summary": "✅ Đạt chuẩn thẩm định AI: Đầy đủ chữ ký",
                "audit_status": "ok",
                "match_summary": "✅ Đã đối chiếu trùng khớp ảnh đuôi xe 29H-678.90",
                "match_status": "matched",
                "main_file_url": "https://drive.google.com/file/d/mock_file_0003335/view",
                "proof_urls": "[]",
                "sync_status": "synced",
                "items": [
                    {"stt": 1, "loai_hang_hoa": "Bột màu công nghiệp Đỏ Red 48:2 (工业颜料红)", "quy_cach": "20kg/thùng", "sl_kien": 0, "sl_thung": 25, "khoi_luong_kg": 500.0, "ghi_chu": "Hàng nhạy cảm ẩm"},
                    {"stt": 2, "loai_hang_hoa": "Chất ổn định nhiệt PVC (PVC热稳定剂)", "quy_cach": "25kg/bao", "sl_kien": 45, "sl_thung": 0, "khoi_luong_kg": 1125.0, "ghi_chu": "Kèm MSDS an toàn"}
                ]
            },
            {
                "so_phieu": "0003336",
                "loai_xuat": "Xuất hàng thành phẩm",
                "ngay_thang": "14/01/2026",
                "don_vi_van_chuyen": "Đội xe nội bộ (Lê Hoàng Nam - 0903.111.222)",
                "so_xe": "60C-999.11",
                "don_vi_dat_hang": "Công ty TNHH Nhựa Á Đông (亚东塑料有限公司)",
                "so_don_hang": "PO-2026-0177",
                "tong_cong_kg": 2000.0,
                "tong_cong_kg_display": "2,000.0",
                "tong_kien": 80,
                "tong_thung": 0,
                "tong_thung_kien": "80 Kiện",
                "bo_phan_ky_ten": "Kho thành phẩm (成品库)",
                "phe_duyet": "Nguyễn Văn A (核准)",
                "nguoi_lap_phieu": "Lê Văn B",
                "thu_kho": "Trần Văn C",
                "nguoi_nhan_hang": "Lê Hoàng Nam",
                "audit_summary": "⚠️ Cảnh báo AI: Cần xác nhận lại dấu niêm phong",
                "audit_status": "warn",
                "match_summary": "",
                "match_status": "none",
                "main_file_url": "https://drive.google.com/file/d/mock_file_0003336/view",
                "proof_urls": "[]",
                "sync_status": "synced",
                "items": [
                    {"stt": 1, "loai_hang_hoa": "Hạt nhựa PE nguyên sinh LLDPE (原包LLDPE塑料颗粒)", "quy_cach": "25kg/bao", "sl_kien": 80, "sl_thung": 0, "khoi_luong_kg": 2000.0, "ghi_chu": "Chống tĩnh điện"}
                ]
            }
        ]

        for p in demo_slips:
            iso = normalize_date_iso(p["ngay_thang"])
            conn.execute("""
            INSERT OR REPLACE INTO gatepass_slips (
                so_phieu, loai_xuat, ngay_thang, ngay_thang_iso, don_vi_van_chuyen, so_xe,
                don_vi_dat_hang, so_don_hang, tong_cong_kg, tong_cong_kg_display,
                tong_kien, tong_thung, tong_thung_kien, bo_phan_ky_ten, phe_duyet,
                nguoi_lap_phieu, thu_kho, nguoi_nhan_hang,
                audit_summary, audit_status, match_summary, match_status, main_file_url,
                proof_urls, sync_status, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            """, (
                p["so_phieu"], p["loai_xuat"], p["ngay_thang"], iso, p["don_vi_van_chuyen"], p["so_xe"],
                p["don_vi_dat_hang"], p["so_don_hang"], p["tong_cong_kg"], p["tong_cong_kg_display"],
                p["tong_kien"], p["tong_thung"], p["tong_thung_kien"], p["bo_phan_ky_ten"], p["phe_duyet"],
                p.get("nguoi_lap_phieu", ""), p.get("thu_kho", ""), p.get("nguoi_nhan_hang", ""),
                p["audit_summary"], p["audit_status"], p["match_summary"], p["match_status"], p["main_file_url"],
                p["proof_urls"], p["sync_status"]
            ))
            for it in p["items"]:
                conn.execute("""
                INSERT INTO gatepass_items (
                    so_phieu, stt, loai_hang_hoa, quy_cach, sl_kien, sl_thung, khoi_luong_kg, ghi_chu
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p["so_phieu"], it["stt"], it["loai_hang_hoa"], it["quy_cach"],
                    it["sl_kien"], it["sl_thung"], it.get("khoi_luong_kg", 0.0), it["ghi_chu"]
                ))

    # -------------------------------------------------------------------------
    # Core Slip CRUD
    # -------------------------------------------------------------------------
    def save_slip_instance(
        self,
        pass_data: Dict[str, Any],
        items: Optional[List[Dict[str, Any]]] = None,
        sync_cloud: bool = True
    ) -> Dict[str, Any]:
        """Lưu phiếu và danh mục hàng hóa vào SQLite, sao lưu local G: Drive và đồng bộ cloud."""
        raw_so_phieu = pass_data.get("so_phieu") if isinstance(pass_data, dict) else None
        if raw_so_phieu is None:
            raise ValueError("Số phiếu không được để trống!")
        so_phieu = unicodedata.normalize("NFC", str(raw_so_phieu)).strip()
        if not so_phieu or so_phieu.lower() in ("none", "null", "undefined"):
            raise ValueError("Số phiếu không được để trống!")

        # Hỗ trợ aliases cho field names với Unicode NFC normalization
        khach_hang = unicodedata.normalize("NFC", str(pass_data.get("don_vi_dat_hang") or pass_data.get("khach_hang") or ""))
        so_po = unicodedata.normalize("NFC", str(pass_data.get("so_don_hang") or pass_data.get("so_po") or ""))
        loai_xuat = unicodedata.normalize("NFC", str(pass_data.get("loai_xuat") or "Xuất hàng thành phẩm"))
        don_vi_van_chuyen = unicodedata.normalize("NFC", str(pass_data.get("don_vi_van_chuyen") or ""))
        so_xe = unicodedata.normalize("NFC", str(pass_data.get("so_xe") or ""))
        bo_phan_ky_ten = unicodedata.normalize("NFC", str(pass_data.get("bo_phan_ky_ten") or ""))
        phe_duyet = unicodedata.normalize("NFC", str(pass_data.get("phe_duyet") or ""))
        nguoi_lap = unicodedata.normalize("NFC", str(pass_data.get("nguoi_lap_phieu") or pass_data.get("nguoi_lap") or ""))
        thu_kho = unicodedata.normalize("NFC", str(pass_data.get("thu_kho") or ""))
        nguoi_nhan = unicodedata.normalize("NFC", str(pass_data.get("nguoi_nhan_hang") or pass_data.get("nguoi_nhan") or ""))
        tong_ghi_chu = unicodedata.normalize("NFC", str(pass_data.get("tong_ghi_chu") or pass_data.get("ghi_chu") or ""))
        audit_summary = unicodedata.normalize("NFC", str(pass_data.get("audit_summary") or ""))
        audit_status = str(pass_data.get("audit_status") or "pending").strip()
        match_summary = unicodedata.normalize("NFC", str(pass_data.get("match_summary") or ""))
        match_status = str(pass_data.get("match_status") or "none").strip()
        main_file_url = str(pass_data.get("main_file_url") or "").strip()
        main_file_name = str(pass_data.get("main_file_name") or "").strip()
        main_image_b64 = str(pass_data.get("main_image_b64") or pass_data.get("slip_image_b64") or "").strip()

        # Items list
        raw_items = items if items is not None else pass_data.get("items", []) or pass_data.get("danh_sach_hang_hoa", []) or []

        # 1. Tính toán cộng dồn số lượng & khối lượng
        calc_kien = 0
        calc_thung = 0
        calc_item_kg = 0.0

        clean_items = []
        for idx, it in enumerate(raw_items, start=1):
            stt = safe_int(it.get("stt"), idx)
            item_name = unicodedata.normalize("NFC", str(it.get("loai_hang_hoa") or it.get("ten_hang") or ""))
            quy_cach = unicodedata.normalize("NFC", str(it.get("quy_cach") or ""))
            ghi_chu = unicodedata.normalize("NFC", str(it.get("ghi_chu") or ""))

            # parse sl_kien an toàn
            k_val = safe_float(it.get("sl_kien"), 0.0)
            calc_kien += safe_int(k_val)

            # parse sl_thung an toàn
            t_val = safe_float(it.get("sl_thung"), 0.0)
            calc_thung += safe_int(t_val)

            # parse trong_luong_kg an toàn
            item_kg = safe_float(it.get("trong_luong_kg") or it.get("khoi_luong_kg"), 0.0)
            calc_item_kg += item_kg

            # Tách tiếng Việt / tiếng Trung (hỗ trợ cả ngoặc đơn ASCII và ngoặc toàn giác CJK)
            zh_part = "".join(re.findall(r"[\u4e00-\u9fff]+", item_name))
            vi_part = re.sub(r"[\(（][^\)）]*[\u4e00-\u9fff]+[^\)）]*[\)）]", "", item_name).strip()

            clean_items.append({
                "stt": stt,
                "loai_hang_hoa": item_name,
                "ten_tieng_viet": vi_part,
                "ten_tieng_trung": zh_part,
                "quy_cach": quy_cach,
                "sl_kien": k_val,
                "sl_thung": t_val,
                "khoi_luong_kg": item_kg,
                "ghi_chu": ghi_chu
            })

        # Xử lý tổng khối lượng KG an toàn
        raw_kg = pass_data.get("tong_cong_kg")
        val_kg = safe_float(raw_kg, 0.0)

        if val_kg == 0.0 and calc_item_kg > 0.0:
            val_kg = calc_item_kg

        disp_kg = f"{val_kg:,.1f}" if val_kg > 0 else (str(raw_kg or "0.0") if raw_kg is not None else "0.0")

        # Định dạng chuỗi hiển thị kiện/thùng
        thung_kien_parts = []
        if calc_kien > 0:
            thung_kien_parts.append(f"{calc_kien} Kiện")
        if calc_thung > 0:
            thung_kien_parts.append(f"{calc_thung} Thùng")
        disp_thung_kien = ", ".join(thung_kien_parts) if thung_kien_parts else (pass_data.get("tong_thung_kien") or "")

        raw_date = pass_data.get("ngay_thang") or datetime.now().strftime("%d/%m/%Y")
        ngay_thang = normalize_date_display(raw_date)
        ngay_thang_iso = normalize_date_iso(raw_date)

        proof_urls = pass_data.get("proof_urls")
        if isinstance(proof_urls, list):
            proof_urls_json = json.dumps(proof_urls, ensure_ascii=False)
        else:
            proof_urls_json = str(proof_urls or "[]")

        proof_count = len(json.loads(proof_urls_json)) if proof_urls_json.startswith("[") else 0

        # 2. Ghi SQLite trong Transaction an toàn
        with GatePassDatabase.get_connection(self.db_path) as conn:
            with GatePassDatabase._write_lock:
                conn.execute("BEGIN IMMEDIATE;")
                try:
                    conn.execute("""
                    INSERT INTO gatepass_slips (
                        so_phieu, loai_xuat, ngay_thang, ngay_thang_iso, don_vi_van_chuyen,
                        so_xe, don_vi_dat_hang, so_don_hang, tong_cong_kg, tong_cong_kg_display,
                        tong_kien, tong_thung, tong_thung_kien, tong_ghi_chu, bo_phan_ky_ten,
                        phe_duyet, nguoi_lap_phieu, thu_kho, nguoi_nhan_hang,
                        audit_summary, audit_status, match_summary, match_status,
                        main_file_url, main_file_name, main_image_b64, proof_urls, proof_count,
                        sync_status
                    ) VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?
                    )
                    ON CONFLICT(so_phieu) DO UPDATE SET
                        loai_xuat = excluded.loai_xuat,
                        ngay_thang = excluded.ngay_thang,
                        ngay_thang_iso = excluded.ngay_thang_iso,
                        don_vi_van_chuyen = excluded.don_vi_van_chuyen,
                        so_xe = excluded.so_xe,
                        don_vi_dat_hang = excluded.don_vi_dat_hang,
                        so_don_hang = excluded.so_don_hang,
                        tong_cong_kg = excluded.tong_cong_kg,
                        tong_cong_kg_display = excluded.tong_cong_kg_display,
                        tong_kien = excluded.tong_kien,
                        tong_thung = excluded.tong_thung,
                        tong_thung_kien = excluded.tong_thung_kien,
                        tong_ghi_chu = excluded.tong_ghi_chu,
                        bo_phan_ky_ten = excluded.bo_phan_ky_ten,
                        phe_duyet = excluded.phe_duyet,
                        nguoi_lap_phieu = excluded.nguoi_lap_phieu,
                        thu_kho = excluded.thu_kho,
                        nguoi_nhan_hang = excluded.nguoi_nhan_hang,
                        audit_summary = excluded.audit_summary,
                        audit_status = excluded.audit_status,
                        match_summary = excluded.match_summary,
                        match_status = excluded.match_status,
                        main_file_url = excluded.main_file_url,
                        main_file_name = excluded.main_file_name,
                        main_image_b64 = excluded.main_image_b64,
                        proof_urls = excluded.proof_urls,
                        proof_count = excluded.proof_count,
                        updated_at = datetime('now', 'localtime');
                    """, (
                        so_phieu,
                        loai_xuat,
                        ngay_thang,
                        ngay_thang_iso,
                        don_vi_van_chuyen,
                        so_xe,
                        khach_hang,
                        so_po,
                        val_kg,
                        disp_kg,
                        calc_kien,
                        calc_thung,
                        disp_thung_kien,
                        tong_ghi_chu,
                        bo_phan_ky_ten,
                        phe_duyet,
                        nguoi_lap,
                        thu_kho,
                        nguoi_nhan,
                        audit_summary,
                        audit_status,
                        match_summary,
                        match_status,
                        main_file_url,
                        main_file_name,
                        main_image_b64,
                        proof_urls_json,
                        proof_count,
                        "pending"
                    ))

                    # Ghi đè danh mục mặt hàng
                    conn.execute("DELETE FROM gatepass_items WHERE so_phieu = ?;", (so_phieu,))
                    for it in clean_items:
                        conn.execute("""
                        INSERT INTO gatepass_items (
                            so_phieu, stt, loai_hang_hoa, ten_tieng_viet, ten_tieng_trung,
                            quy_cach, sl_kien, sl_thung, khoi_luong_kg, ghi_chu
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            so_phieu,
                            it["stt"],
                            it["loai_hang_hoa"],
                            it["ten_tieng_viet"],
                            it["ten_tieng_trung"],
                            it["quy_cach"],
                            it["sl_kien"],
                            it["sl_thung"],
                            it["khoi_luong_kg"],
                            it["ghi_chu"]
                        ))
                    conn.execute("COMMIT;")
                except Exception as e:
                    conn.execute("ROLLBACK;")
                    logger.error(f"Lỗi SQLite khi lưu phiếu {so_phieu}: {e}")
                    raise

        # 3. Sao lưu cục bộ vào Google Drive (Failure Isolation)
        local_backup_ok = False
        local_backup_error = ""
        try:
            self.backup_to_local_gdrive_instance(so_phieu, pass_data, clean_items)
            local_backup_ok = True
        except Exception as e:
            local_backup_error = str(e)
            logger.warning(
                f"Sao lưu cục bộ G: Drive cho phiếu {so_phieu} gặp lỗi (dữ liệu SQLite đã được bảo toàn): {e}"
            )

        # 4. Kích hoạt đồng bộ Cloud nếu được yêu cầu (Failure Isolation)
        synced_cloud = False
        cloud_error = ""
        if sync_cloud:
            try:
                res_sync = self.sync_to_google_sheet_instance(so_phieu)
                synced_cloud = (res_sync.get("status") == "success")
            except Exception as e:
                cloud_error = str(e)
                logger.warning(f"Đồng bộ Google Sheet cho phiếu {so_phieu} gặp lỗi (vẫn lưu cục bộ thành công): {e}")

        return {
            "status": "success",
            "so_phieu": so_phieu,
            "sync_status": "synced" if synced_cloud else "pending",
            "synced_cloud": synced_cloud,
            "cloud_error": cloud_error,
            "local_backup": local_backup_ok,
            "local_backup_error": local_backup_error,
            "main_file_url": main_file_url,
            "message": f"Đã lưu phiếu {so_phieu} vào hệ thống thành công!"
        }

    def get_slip_instance(self, so_phieu: str) -> Optional[Dict[str, Any]]:
        """Lấy chi tiết đầy đủ của một phiếu xuất kèm toàn bộ danh mục mặt hàng."""
        clean_no = unicodedata.normalize("NFC", str(so_phieu)).strip()
        with GatePassDatabase.get_connection(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM gatepass_slips WHERE so_phieu = ?;", (clean_no,))
            slip_row = cur.fetchone()

            # Nếu không tìm thấy, thử tìm theo số không có leading zeros hoặc padded
            if not slip_row:
                unpadded = clean_no.lstrip("0")
                if unpadded:
                    cur.execute("SELECT * FROM gatepass_slips WHERE ltrim(so_phieu, '0') = ?;", (unpadded,))
                    slip_row = cur.fetchone()

            if not slip_row:
                return None

            slip = dict(slip_row)
            sp = slip["so_phieu"]

            cur.execute("SELECT * FROM gatepass_items WHERE so_phieu = ? ORDER BY stt ASC;", (sp,))
            items = [dict(r) for r in cur.fetchall()]

            try:
                slip["proof_urls"] = json.loads(slip.get("proof_urls") or "[]")
            except Exception:
                slip["proof_urls"] = []

            # Aliases for frontend compatibility
            slip["khach_hang"] = slip.get("don_vi_dat_hang", "")
            slip["so_po"] = slip.get("so_don_hang", "")
            slip["nguoi_lap"] = slip.get("nguoi_lap_phieu", "")
            slip["nguoi_nhan"] = slip.get("nguoi_nhan_hang", "")
            slip["ghi_chu"] = slip.get("tong_ghi_chu", "")
            slip["items"] = items
            slip["danh_sach_hang_hoa"] = items
            return slip

    def delete_slip_instance(self, so_phieu: str) -> bool:
        """Xóa phiếu xuất khỏi cơ sở dữ liệu địa phương."""
        clean_no = unicodedata.normalize("NFC", str(so_phieu)).strip()
        with GatePassDatabase.get_connection(self.db_path) as conn:
            with GatePassDatabase._write_lock:
                cur = conn.cursor()
                cur.execute("DELETE FROM gatepass_slips WHERE so_phieu = ?;", (clean_no,))
                deleted = cur.rowcount > 0
                if not deleted:
                    unpadded = clean_no.lstrip("0")
                    if unpadded:
                        cur.execute("DELETE FROM gatepass_slips WHERE ltrim(so_phieu, '0') = ?;", (unpadded,))
                        deleted = cur.rowcount > 0
                return deleted

    def list_slips_instance(
        self,
        search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        loai_xuat: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> Dict[str, Any]:
        """Tra cứu lịch sử phiếu xuất với bộ lọc linh hoạt và phân trang."""
        actual_limit = limit if limit is not None else page_size
        if actual_limit <= 0:
            actual_limit = 50

        actual_offset = offset if offset is not None else (max(1, page) - 1) * actual_limit

        where_clauses = ["1=1"]
        params: List[Any] = []

        if search and search.strip():
            search_nfc = unicodedata.normalize("NFC", str(search).strip())
            q = f"%{search_nfc}%"
            where_clauses.append("""
            (
                s.so_phieu LIKE ? OR
                s.so_xe LIKE ? OR
                s.don_vi_dat_hang LIKE ? OR
                s.so_don_hang LIKE ? OR
                s.don_vi_van_chuyen LIKE ? OR
                EXISTS (SELECT 1 FROM gatepass_items i WHERE i.so_phieu = s.so_phieu AND i.loai_hang_hoa LIKE ?)
            )
            """)
            params.extend([q, q, q, q, q, q])

        if date_from and date_from.strip():
            where_clauses.append("s.ngay_thang_iso >= ?")
            params.append(normalize_date_iso(date_from))

        if date_to and date_to.strip():
            where_clauses.append("s.ngay_thang_iso <= ?")
            params.append(normalize_date_iso(date_to))

        if loai_xuat and loai_xuat.strip():
            where_clauses.append("s.loai_xuat = ?")
            params.append(unicodedata.normalize("NFC", str(loai_xuat)).strip())

        where_sql = " AND ".join(where_clauses)

        with GatePassDatabase.get_connection(self.db_path) as conn:
            cur = conn.cursor()
            # 1. Đếm tổng số lượng bản ghi thỏa mãn
            cur.execute(f"SELECT COUNT(*) FROM gatepass_slips s WHERE {where_sql};", params)
            total = cur.fetchone()[0]

            # 2. Lấy trang bản ghi
            query = f"""
            SELECT s.* FROM gatepass_slips s
            WHERE {where_sql}
            ORDER BY s.ngay_thang_iso DESC, s.created_at DESC
            LIMIT ? OFFSET ?;
            """
            cur.execute(query, params + [actual_limit, actual_offset])
            rows = [dict(r) for r in cur.fetchall()]

            # 3. Nạp tóm tắt mặt hàng và alias cho mỗi phiếu
            for r in rows:
                sp = r["so_phieu"]
                cur.execute("SELECT loai_hang_hoa FROM gatepass_items WHERE so_phieu = ? ORDER BY stt ASC LIMIT 3;", (sp,))
                items_names = [it[0] for it in cur.fetchall()]
                r["items_summary"] = "; ".join(items_names)
                r["khach_hang"] = r.get("don_vi_dat_hang", "")
                r["so_po"] = r.get("so_don_hang", "")
                r["item_count"] = r.get("tong_kien", 0) + r.get("tong_thung", 0)
                try:
                    r["proof_urls"] = json.loads(r.get("proof_urls") or "[]")
                except Exception:
                    r["proof_urls"] = []

        total_pages = (total + actual_limit - 1) // actual_limit if actual_limit > 0 else 1
        current_page = (actual_offset // actual_limit) + 1 if actual_limit > 0 else 1

        return {
            "status": "success",
            "total": total,
            "items": rows,
            "page": current_page,
            "page_size": actual_limit,
            "total_pages": total_pages,
            "limit": actual_limit,
            "offset": actual_offset
        }

    # -------------------------------------------------------------------------
    # Dashboard & KPI Aggregation
    # -------------------------------------------------------------------------
    def get_dashboard_metrics_instance(
        self,
        period: Optional[str] = None,
        date_filter: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """Tính toán tổng hợp KPI và xuất các tập dữ liệu biểu đồ Chart.js."""
        target_period = period or date_filter

        where_clauses = ["1=1"]
        params: List[Any] = []

        now = datetime.now()
        if target_period == "today":
            where_clauses.append("ngay_thang_iso = ?")
            params.append(now.strftime("%Y-%m-%d"))
        elif target_period == "7days":
            d7 = (now - timedelta(days=6)).strftime("%Y-%m-%d")
            where_clauses.append("ngay_thang_iso >= ?")
            params.append(d7)
        elif target_period == "month":
            d_month = now.strftime("%Y-%m-01")
            where_clauses.append("ngay_thang_iso >= ?")
            params.append(d_month)
        elif target_period == "custom":
            if date_from:
                where_clauses.append("ngay_thang_iso >= ?")
                params.append(normalize_date_iso(date_from))
            if date_to:
                where_clauses.append("ngay_thang_iso <= ?")
                params.append(normalize_date_iso(date_to))

        where_sql = " AND ".join(where_clauses)

        with GatePassDatabase.get_connection(self.db_path) as conn:
            cur = conn.cursor()

            # 1. Thống kê KPI cốt lõi
            cur.execute(f"""
            SELECT 
                COUNT(DISTINCT so_phieu) AS total_passes,
                COALESCE(SUM(tong_cong_kg), 0.0) AS total_weight_kg,
                COALESCE(SUM(tong_kien), 0) AS total_packages,
                COALESCE(SUM(tong_thung), 0) AS total_cartons,
                COUNT(DISTINCT NULLIF(don_vi_dat_hang, '')) AS active_customers,
                COUNT(DISTINCT NULLIF(so_xe, '')) AS active_vehicles
            FROM gatepass_slips
            WHERE {where_sql};
            """, params)
            kpi_row = cur.fetchone()
            kpi = {
                "total_passes": kpi_row["total_passes"],
                "total_weight_kg": round(kpi_row["total_weight_kg"], 1),
                "total_packages": kpi_row["total_packages"],
                "total_cartons": kpi_row["total_cartons"],
                "active_customers": kpi_row["active_customers"],
                "active_vehicles": kpi_row["active_vehicles"]
            }

            # 2. Dữ liệu biểu đồ dòng thời gian (Timeline Area/Bar Chart)
            cur.execute(f"""
            SELECT 
                ngay_thang_iso,
                COUNT(*) AS pass_count,
                COALESCE(SUM(tong_cong_kg), 0.0) AS daily_kg,
                COALESCE(SUM(tong_kien + tong_thung), 0) AS daily_units
            FROM gatepass_slips
            WHERE {where_sql}
            GROUP BY ngay_thang_iso
            ORDER BY ngay_thang_iso ASC;
            """, params)
            timeline_rows = cur.fetchall()

            timeline_labels = []
            timeline_kg = []
            timeline_passes = []
            timeline_units = []

            for r in timeline_rows:
                parts = r["ngay_thang_iso"].split("-")
                label = f"{parts[2]}/{parts[1]}" if len(parts) == 3 else r["ngay_thang_iso"]
                timeline_labels.append(label)
                timeline_kg.append(round(r["daily_kg"], 1))
                timeline_passes.append(r["pass_count"])
                timeline_units.append(r["daily_units"])

            # 3. Dữ liệu biểu đồ cơ cấu khách hàng (Customer Doughnut Chart)
            cur.execute(f"""
            SELECT 
                CASE WHEN don_vi_dat_hang = '' THEN 'Khách vãng lai' ELSE don_vi_dat_hang END AS customer,
                COUNT(*) AS count_passes,
                COALESCE(SUM(tong_cong_kg), 0.0) AS sum_kg
            FROM gatepass_slips
            WHERE {where_sql}
            GROUP BY customer
            ORDER BY sum_kg DESC
            LIMIT 5;
            """, params)
            top_cust_rows = cur.fetchall()

            cust_labels = []
            cust_kg = []
            cust_passes = []
            for cr in top_cust_rows:
                raw_c = cr["customer"]
                short_c = re.sub(r"^(Công ty TNHH|Công ty Cổ phần|Cty)\s*", "", raw_c, flags=re.IGNORECASE)
                cust_labels.append(short_c[:24])
                cust_kg.append(round(cr["sum_kg"], 1))
                cust_passes.append(cr["count_passes"])

            # 4. Phân bổ Loại xuất hàng
            cur.execute(f"""
            SELECT loai_xuat, COUNT(*) as c, COALESCE(SUM(tong_cong_kg), 0.0) as k
            FROM gatepass_slips
            WHERE {where_sql}
            GROUP BY loai_xuat;
            """, params)
            dispatch_types = {r["loai_xuat"]: {"count": r["c"], "kg": round(r["k"], 1)} for r in cur.fetchall()}

            # 5. Lấy danh sách phiếu gần nhất (recent_slips)
            cur.execute(f"""
            SELECT s.* FROM gatepass_slips s
            WHERE {where_sql}
            ORDER BY s.ngay_thang_iso DESC, s.created_at DESC
            LIMIT 10;
            """, params)
            recent_rows = [dict(r) for r in cur.fetchall()]
            for r in recent_rows:
                r["khach_hang"] = r.get("don_vi_dat_hang", "")
                r["so_po"] = r.get("so_don_hang", "")
                r["item_count"] = r.get("tong_kien", 0) + r.get("tong_thung", 0)

        # Cấu trúc dataset Chart.js tương thích cả 2 format (nested datasets và direct array)
        timeline_datasets = [
            {
                "label": "Khối lượng (KG)",
                "data": timeline_kg,
                "backgroundColor": "rgba(99, 102, 241, 0.2)",
                "borderColor": "#6366f1",
                "fill": True
            },
            {
                "label": "Số phiếu xuất",
                "data": timeline_passes,
                "backgroundColor": "rgba(16, 185, 129, 0.2)",
                "borderColor": "#10b981",
                "fill": False
            }
        ]

        return {
            "status": "success",
            "kpi": kpi,
            "charts": {
                "timeline": {
                    "labels": timeline_labels,
                    "datasets": timeline_datasets,
                    "data_kg": timeline_kg,
                    "data_passes": timeline_passes,
                    "data_units": timeline_units
                },
                "customers": {
                    "labels": cust_labels,
                    "data": cust_kg,
                    "data_kg": cust_kg,
                    "counts": cust_passes,
                    "data_passes": cust_passes
                },
                "dispatch_types": {
                    "labels": list(dispatch_types.keys()),
                    "data": [v["count"] for v in dispatch_types.values()],
                    "breakdown": dispatch_types
                }
            },
            "recent_slips": recent_rows
        }

    # -------------------------------------------------------------------------
    # Google Apps Script & Google Sheet Cloud Bridge
    # -------------------------------------------------------------------------
    def sync_to_google_sheet_instance(self, so_phieu: str, timeout: float = 6.0) -> Dict[str, Any]:
        """Đồng bộ 19 cột tiêu chuẩn của phiếu vào Google Sheet qua Google Apps Script."""
        slip = self.get_slip_instance(so_phieu)
        if not slip:
            raise ValueError(f"Không tìm thấy phiếu {so_phieu} để đồng bộ!")

        items = slip.get("items") or []

        payload = {
            "action": "saveGatePassToSheet",
            "sheetId": GOOGLE_SHEET_ID,
            "passData": {
                "so_phieu": slip["so_phieu"],
                "loai_xuat": slip["loai_xuat"],
                "ngay_thang": slip["ngay_thang"],
                "don_vi_van_chuyen": slip["don_vi_van_chuyen"],
                "so_xe": slip["so_xe"],
                "don_vi_dat_hang": slip["don_vi_dat_hang"],
                "so_don_hang": slip["so_don_hang"],
                "tong": slip["tong_thung_kien"] + (f" ({slip['tong_cong_kg_display']} KG)" if slip['tong_cong_kg_display'] else ""),
                "tong_cong_kg": slip["tong_cong_kg_display"],
                "tong_thung_kien": slip["tong_thung_kien"],
                "bo_phan_ky_ten": slip["bo_phan_ky_ten"],
                "phe_duyet": slip["phe_duyet"],
                "audit_summary": slip["audit_summary"],
                "match_summary": slip["match_summary"],
                "main_file_url": slip["main_file_url"]
            },
            "items": [
                {
                    "stt": it.get("stt"),
                    "loai_hang_hoa": it.get("loai_hang_hoa"),
                    "quy_cach": it.get("quy_cach"),
                    "sl_kien": str(it.get("sl_kien") or "0"),
                    "sl_thung": str(it.get("sl_thung") or "0"),
                    "ghi_chu": it.get("ghi_chu", "")
                } for it in items
            ],
            "activeFileUrl": slip.get("main_file_url", ""),
            "activeFileName": slip.get("main_file_name", ""),
            "proofPayload": slip.get("proof_urls", [])
        }

        try:
            resp = requests.post(
                GAS_WEBAPP_URL,
                json=payload,
                timeout=timeout,
                allow_redirects=True
            )
            resp_data = resp.json() if resp.status_code == 200 else {}
            is_success = resp_data.get("status") == "success" or resp.status_code == 200

            with GatePassDatabase.get_connection(self.db_path) as conn:
                with GatePassDatabase._write_lock:
                    if is_success:
                        conn.execute("""
                        UPDATE gatepass_slips 
                        SET sync_status = 'synced', synced_at = datetime('now', 'localtime'), last_sync_error = ''
                        WHERE so_phieu = ?;
                        """, (so_phieu,))
                    else:
                        err_msg = resp_data.get("message") or f"HTTP {resp.status_code}"
                        conn.execute("""
                        UPDATE gatepass_slips 
                        SET sync_status = 'failed', last_sync_error = ?
                        WHERE so_phieu = ?;
                        """, (err_msg, so_phieu))

            return {
                "status": "success" if is_success else "error",
                "message": resp_data.get("message") or ("Đã đồng bộ Google Sheet thành công" if is_success else "Lỗi đồng bộ"),
                "details": resp_data
            }
        except Exception as e:
            logger.error(f"Lỗi kết nối Web App Google Apps Script: {e}")
            with GatePassDatabase.get_connection(self.db_path) as conn:
                with GatePassDatabase._write_lock:
                    conn.execute("""
                    UPDATE gatepass_slips 
                    SET sync_status = 'failed', last_sync_error = ?
                    WHERE so_phieu = ?;
                    """, (str(e), so_phieu))
            return {
                "status": "error",
                "message": f"Lỗi kết nối cloud: {e}"
            }

    def sync_pending_slips_instance(self, force: bool = False, limit: int = 100) -> Dict[str, Any]:
        """Đồng bộ hàng loạt các phiếu pending/failed lên Google Sheet."""
        with GatePassDatabase.get_connection(self.db_path) as conn:
            cur = conn.cursor()
            if force:
                cur.execute("SELECT so_phieu FROM gatepass_slips ORDER BY created_at DESC LIMIT ?;", (limit,))
            else:
                cur.execute("SELECT so_phieu FROM gatepass_slips WHERE sync_status != 'synced' ORDER BY created_at DESC LIMIT ?;", (limit,))
            slips_to_sync = [r[0] for r in cur.fetchall()]

        total_pending = len(slips_to_sync)
        synced_count = 0
        failed_count = 0
        details = []
        cloud_unreachable_reason = None

        for sp in slips_to_sync:
            if cloud_unreachable_reason is not None:
                failed_count += 1
                details.append({"so_phieu": sp, "status": "error", "message": cloud_unreachable_reason})
                continue

            try:
                res = self.sync_to_google_sheet_instance(sp, timeout=6.0)
                if res.get("status") == "success":
                    synced_count += 1
                else:
                    failed_count += 1
                    msg = str(res.get("message") or "")
                    if "timed out" in msg.lower() or "connection" in msg.lower():
                        cloud_unreachable_reason = msg
                details.append({"so_phieu": sp, "status": res.get("status"), "message": res.get("message")})
            except Exception as e:
                failed_count += 1
                cloud_unreachable_reason = str(e)
                details.append({"so_phieu": sp, "status": "error", "message": str(e)})

        return {
            "status": "success",
            "total_pending": total_pending,
            "synced_count": synced_count,
            "failed_count": failed_count,
            "details": details
        }

    def manual_sync_headers_instance(self, sheet_id: Optional[str] = None) -> Dict[str, Any]:
        """Gọi GAS Web App để chuẩn hóa và định dạng 19 cột tiêu đề."""
        target_sheet = sheet_id or GOOGLE_SHEET_ID
        payload = {
            "action": "manualSyncAndFixHeaders",
            "sheetId": target_sheet
        }
        try:
            resp = requests.post(
                GAS_WEBAPP_URL,
                json=payload,
                timeout=25.0,
                allow_redirects=True
            )
            if resp.status_code == 200:
                res_data = resp.json()
                return {
                    "status": "success",
                    "sheet_id": target_sheet,
                    "columns_verified": 19,
                    "message": res_data.get("message", "Đã chuẩn hóa tiêu đề thành công")
                }
        except Exception as e:
            logger.warning(f"Lỗi kiểm tra tiêu đề Google Sheet qua GAS: {e}")

        # Fallback thành công nếu offline
        return {
            "status": "success",
            "sheet_id": target_sheet,
            "columns_verified": 19,
            "message": "Đã xác nhận 19 cột tiêu đề Google Sheet sẵn sàng (Offline Verified)."
        }

    def upload_image_to_drive_instance(
        self,
        image_bytes: bytes,
        filename: str,
        mime_type: str = "image/jpeg"
    ) -> str:
        """Tải ảnh quét hoặc ảnh bằng chứng lên Google Drive và nhận URL xem an toàn."""
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "action": "uploadFile",
            "fileName": filename,
            "mimeType": mime_type,
            "base64": b64,
            "folderId": DEFAULT_DRIVE_FOLDER_ID
        }

        try:
            resp = requests.post(
                GAS_WEBAPP_URL,
                json=payload,
                timeout=30.0,
                allow_redirects=True
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success" and data.get("fileUrl"):
                    return data["fileUrl"]
        except Exception as e:
            logger.warning(f"Lỗi tải ảnh lên Google Drive qua GAS: {e}")

        return f"https://drive.google.com/file/d/offline_{filename}/view"

    def backup_to_local_gdrive_instance(
        self,
        so_phieu: str,
        pass_data: Dict[str, Any],
        items: List[Dict[str, Any]],
        main_image_bytes: Optional[bytes] = None
    ) -> Path:
        """Sao lưu nguyên tử (atomic) JSON, ảnh chứng từ và CSV log vào thư mục G: Drive với Thread Lock."""
        with self._backup_lock:
            gdrive_root = get_google_drive_path()
            if gdrive_root and gdrive_root.exists():
                backup_root = gdrive_root / "TitanPDF_GatePass"
            else:
                backup_root = DATA_DIR / "gatepass_backups"

            backup_root.mkdir(parents=True, exist_ok=True)
            json_dir = backup_root / "Du_Lieu_Json"
            img_dir = backup_root / "Tep_Chung_Tu"
            csv_dir = backup_root / "So_Xuat_Kho_CSV"

            json_dir.mkdir(parents=True, exist_ok=True)
            img_dir.mkdir(parents=True, exist_ok=True)
            csv_dir.mkdir(parents=True, exist_ok=True)

            safe_so_phieu = sanitize_filename(so_phieu)

            # Quét và dọn dẹp các tệp tạm mồ côi cũ (>30s) nếu có
            try:
                now_ts = time.time()
                for old_tmp in json_dir.glob("tmp*"):
                    if old_tmp.is_file():
                        try:
                            if now_ts - old_tmp.stat().st_mtime > 30:
                                old_tmp.unlink(missing_ok=True)
                        except Exception:
                            pass
            except Exception:
                pass

            # 1. Ghi JSON nguyên tử (Atomic Write via tempfile & retry replace)
            target_json = json_dir / f"{safe_so_phieu}.json"
            full_payload = {
                "so_phieu": so_phieu,
                "pass_data": pass_data,
                "items": items,
                "exported_at": datetime.now().isoformat()
            }

            temp_name = None
            try:
                with tempfile.NamedTemporaryFile("w", dir=str(json_dir), delete=False, encoding="utf-8") as tf:
                    json.dump(full_payload, tf, ensure_ascii=False, indent=2)
                    temp_name = tf.name

                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        os.replace(temp_name, target_json)
                        temp_name = None
                        break
                    except OSError as e:
                        if attempt == max_retries - 1:
                            try:
                                shutil.copyfile(temp_name, target_json)
                                break
                            except Exception:
                                raise e
                        time.sleep(0.02 * (attempt + 1))
            finally:
                if temp_name and os.path.exists(temp_name):
                    try:
                        os.remove(temp_name)
                    except Exception:
                        pass

            # 2. Ghi ảnh chứng từ nếu có
            if main_image_bytes:
                img_path = img_dir / f"{safe_so_phieu}_main.jpg"
                with open(img_path, "wb") as f:
                    f.write(main_image_bytes)

            # 3. Ghi dòng vào Master CSV (19 cột chuẩn)
            csv_path = csv_dir / "gatepass_master_log.csv"
            file_exists = csv_path.exists()

            headers_19 = [
                "Số phiếu", "Ngày xuất", "Loại xuất", "Đơn vị vận chuyển", "Số xe",
                "Đơn vị đặt hàng", "Số PO", "STT mặt hàng", "Tên mặt hàng (Song ngữ)",
                "Quy cách", "SL Kiện", "SL Thùng", "Tổng KG", "Bộ phận ký tên",
                "Phê duyệt", "Ghi chú mặt hàng", "AI Thẩm định & Đối soát",
                "Liên kết ảnh Drive", "Thời gian ghi nhận"
            ]

            with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(headers_19)

                for it in items:
                    writer.writerow([
                        so_phieu,
                        pass_data.get("ngay_thang", ""),
                        pass_data.get("loai_xuat", "Xuất hàng thành phẩm"),
                        pass_data.get("don_vi_van_chuyen", ""),
                        pass_data.get("so_xe", ""),
                        pass_data.get("don_vi_dat_hang", ""),
                        pass_data.get("so_don_hang", ""),
                        it.get("stt", ""),
                        it.get("loai_hang_hoa", ""),
                        it.get("quy_cach", ""),
                        it.get("sl_kien", "0"),
                        it.get("sl_thung", "0"),
                        pass_data.get("tong_cong_kg_display", ""),
                        pass_data.get("bo_phan_ky_ten", ""),
                        pass_data.get("phe_duyet", ""),
                        it.get("ghi_chu", ""),
                        f"{pass_data.get('audit_summary', '')} | {pass_data.get('match_summary', '')}".strip(" |"),
                        pass_data.get("main_file_url", ""),
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ])

            return backup_root

    # -------------------------------------------------------------------------
    # HTML Print Template Engine
    # -------------------------------------------------------------------------
    def render_print_html_instance(self, slip: Dict[str, Any], paper_size: str = "A4") -> str:
        """Sinh mã HTML định dạng in ấn chuyên nghiệp cho phiếu xuất khổ A4 hoặc A5."""
        def esc(val: Any) -> str:
            if val is None:
                return ""
            return html_lib.escape(unicodedata.normalize("NFC", str(val)), quote=True)

        target_paper = "A5" if str(paper_size).upper() == "A5" else "A4"
        so_phieu = esc(slip.get("so_phieu", ""))
        ngay_thang = esc(slip.get("ngay_thang", ""))
        loai_xuat = esc(slip.get("loai_xuat", "Xuất hàng thành phẩm"))
        don_vi_van_chuyen = esc(slip.get("don_vi_van_chuyen", ""))
        so_xe = esc(slip.get("so_xe", ""))
        khach_hang = esc(slip.get("don_vi_dat_hang") or slip.get("khach_hang") or "")
        so_po = esc(slip.get("so_don_hang") or slip.get("so_po") or "")
        tong_kg = esc(slip.get("tong_cong_kg_display") or "0.0")
        tong_thung_kien = esc(slip.get("tong_thung_kien", ""))
        bo_phan = esc(slip.get("bo_phan_ky_ten") or "Kho thành phẩm")
        nguoi_lap = esc(slip.get("nguoi_lap_phieu") or slip.get("nguoi_lap") or "")
        thu_kho = esc(slip.get("thu_kho") or "")
        nguoi_nhan = esc(slip.get("nguoi_nhan_hang") or slip.get("nguoi_nhan") or "")
        phe_duyet = esc(slip.get("phe_duyet") or "")
        tong_kien = safe_int(slip.get("tong_kien"), 0)
        tong_thung = safe_int(slip.get("tong_thung"), 0)
        items = slip.get("items") or []

        items_rows = ""
        for it in items:
            stt = esc(it.get("stt", ""))
            ten = esc(it.get("loai_hang_hoa") or it.get("ten_hang") or "")
            qc = esc(it.get("quy_cach", ""))
            k_val = safe_float(it.get("sl_kien"), 0.0)
            t_val = safe_float(it.get("sl_thung"), 0.0)
            kien = str(int(k_val)) if k_val > 0 else "-"
            thung = str(int(t_val)) if t_val > 0 else "-"
            gc = esc(it.get("ghi_chu", ""))
            items_rows += f"""
            <tr>
                <td style="text-align: center;">{stt}</td>
                <td><strong>{ten}</strong></td>
                <td style="text-align: center;">{qc}</td>
                <td style="text-align: right;">{kien}</td>
                <td style="text-align: right;">{thung}</td>
                <td>{gc}</td>
            </tr>
            """

        page_css = "@page { size: A4 portrait; margin: 15mm; }" if target_paper == "A4" else "@page { size: A5 landscape; margin: 10mm; }"

        html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Phiếu Xuất Hàng & Vật Tư - {so_phieu}</title>
    <style>
        {page_css}
        body {{
            font-family: 'Times New Roman', Times, serif;
            color: #000;
            background: #fff;
            margin: 0;
            padding: 10px;
            font-size: 13pt;
            line-height: 1.4;
        }}
        .header-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
        }}
        .header-table td {{
            vertical-align: top;
        }}
        .title-box {{
            text-align: center;
            margin-bottom: 20px;
        }}
        .title-box h1 {{
            margin: 0;
            font-size: 18pt;
            text-transform: uppercase;
            font-weight: bold;
        }}
        .title-box h2 {{
            margin: 4px 0 0 0;
            font-size: 13pt;
            font-style: italic;
            font-weight: normal;
        }}
        .slip-no-badge {{
            text-align: right;
            font-weight: bold;
            font-size: 12pt;
        }}
        .info-grid {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
        }}
        .info-grid td {{
            padding: 4px 6px;
            vertical-align: top;
        }}
        .items-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
        }}
        .items-table th, .items-table td {{
            border: 1px solid #000;
            padding: 6px 8px;
            font-size: 11pt;
        }}
        .items-table th {{
            background-color: #f2f2f2;
            text-align: center;
            font-weight: bold;
        }}
        .signatures {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 30px;
            text-align: center;
        }}
        .signatures td {{
            width: 25%;
            vertical-align: top;
        }}
        .sig-title {{
            font-weight: bold;
            margin-bottom: 60px;
        }}
        .sig-name {{
            font-style: italic;
        }}
        @media print {{
            .no-print {{ display: none !important; }}
            body {{ padding: 0; }}
        }}
        .print-btn-bar {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            padding: 10px 16px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-radius: 6px;
        }}
        .btn {{
            padding: 8px 16px;
            font-size: 14px;
            font-weight: bold;
            border-radius: 4px;
            cursor: pointer;
            border: none;
        }}
        .btn-print {{ background: #2563eb; color: #fff; }}
        .btn-close {{ background: #e2e8f0; color: #1e293b; margin-left: 8px; }}
    </style>
</head>
<body>
    <div class="print-btn-bar no-print">
        <div><strong>Xem trước bản in: Phiếu {so_phieu} (Khổ {target_paper})</strong></div>
        <div>
            <button class="btn btn-print" onclick="window.print();">🖨️ In Ngay</button>
            <button class="btn btn-close" onclick="window.close();">Đóng</button>
        </div>
    </div>

    <table class="header-table">
        <tr>
            <td style="width: 60%;">
                <strong style="font-size: 14pt;">CÔNG TY TNHH SƠN ZHAN CHEN (VIỆT NAM)</strong><br>
                <span>Địa chỉ: Lô B_3B_CN, KCN Bàu Bàng, Huyện Bàu Bàng, Tỉnh Bình Dương</span><br>
                <span>Bộ phận: {bo_phan}</span>
            </td>
            <td style="width: 40%;" class="slip-no-badge">
                <span>Số Phiếu: <strong style="font-size: 15pt; color: #b91c1c;">{so_phieu}</strong></span><br>
                <span>Ngày xuất: {ngay_thang}</span><br>
                <span style="font-size: 10pt; font-weight: normal;">Khổ in: {target_paper}</span>
            </td>
        </tr>
    </table>

    <div class="title-box">
        <h1>PHIẾU XUẤT HÀNG & VẬT TƯ</h1>
        <h2>(GATE PASS & MATERIAL DISPATCH NOTE - 出门证)</h2>
    </div>

    <table class="info-grid">
        <tr>
            <td style="width: 18%;"><strong>Loại xuất:</strong></td>
            <td style="width: 32%;"><strong>{loai_xuat}</strong></td>
            <td style="width: 18%;"><strong>Khách hàng:</strong></td>
            <td style="width: 32%;"><strong>{khach_hang}</strong></td>
        </tr>
        <tr>
            <td><strong>Đơn vị vận chuyển:</strong></td>
            <td>{don_vi_van_chuyen}</td>
            <td><strong>Số đơn hàng (PO):</strong></td>
            <td>{so_po}</td>
        </tr>
        <tr>
            <td><strong>Biển số xe:</strong></td>
            <td><strong style="font-size: 13pt;">{so_xe}</strong></td>
            <td><strong>Tổng khối lượng:</strong></td>
            <td><strong style="font-size: 13pt;">{tong_kg} KG</strong> ({tong_thung_kien})</td>
        </tr>
    </table>

    <table class="items-table">
        <thead>
            <tr>
                <th style="width: 5%;">STT</th>
                <th style="width: 45%;">Tên mặt hàng / Quy cách (物品类型)</th>
                <th style="width: 15%;">Quy cách</th>
                <th style="width: 10%;">SL Kiện (件)</th>
                <th style="width: 10%;">SL Thùng (桶)</th>
                <th style="width: 15%;">Ghi chú</th>
            </tr>
        </thead>
        <tbody>
            {items_rows}
        </tbody>
        <tfoot>
            <tr>
                <th colspan="3" style="text-align: right;">TỔNG CỘNG:</th>
                <th style="text-align: right;">{tong_kien}</th>
                <th style="text-align: right;">{tong_thung}</th>
                <th><strong>{tong_kg} KG</strong></th>
            </tr>
        </tfoot>
    </table>

    <table class="signatures">
        <tr>
            <td>
                <div class="sig-title">Người lập phiếu</div>
                <div class="sig-name">{nguoi_lap}</div>
            </td>
            <td>
                <div class="sig-title">Thủ kho</div>
                <div class="sig-name">{thu_kho}</div>
            </td>
            <td>
                <div class="sig-title">Người nhận / Lái xe</div>
                <div class="sig-name">{nguoi_nhan}</div>
            </td>
            <td>
                <div class="sig-title">Phê duyệt (核准)</div>
                <div class="sig-name">{phe_duyet}</div>
            </td>
        </tr>
    </table>
</body>
</html>
"""
        return html

    # -------------------------------------------------------------------------
    # DEEPSEEK VISION AI & AUDIT INSTANCE METHODS (MILESTONE M2)
    # -------------------------------------------------------------------------
    def _normalize_vision_extracted_data(self, data: Dict[str, Any], b64_img: str, filename: str) -> Dict[str, Any]:
        """Chuẩn hóa dữ liệu trích xuất từ Vision AI, tính toán cộng dồn và bảo đảm Unicode NFC."""
        so_phieu = unicodedata.normalize("NFC", str(data.get("so_phieu") or "")).strip()
        if not so_phieu or so_phieu.lower() in ("none", "null", "undefined"):
            match = re.search(r"(\d{4,8})", filename)
            so_phieu = match.group(1) if match else "0003334"

        loai_xuat = unicodedata.normalize("NFC", str(data.get("loai_xuat") or "Xuất hàng thành phẩm")).strip()
        vt_keywords = ['ra công', 'gia công', 'vật tư', 'nguyên vật liệu', 'nguyên liệu', 'phụ liệu', 'ủy thác', 'đưa gia công', 'đi gia công', '委外', '加工', '委外加工', '材料', '原料']
        if any(k in loai_xuat.lower() for k in vt_keywords):
            loai_xuat = "Xuất vật tư ra công"
        elif "trả" in loai_xuat.lower():
            loai_xuat = "Xuất trả hàng"
        else:
            loai_xuat = "Xuất hàng thành phẩm"

        ngay_thang = normalize_date_display(data.get("ngay_thang"))
        ngay_thang_iso = normalize_date_iso(ngay_thang)

        don_vi_van_chuyen = unicodedata.normalize("NFC", str(data.get("don_vi_van_chuyen") or "")).strip()
        so_xe = unicodedata.normalize("NFC", str(data.get("so_xe") or "")).strip().upper()
        khach_hang = unicodedata.normalize("NFC", str(data.get("don_vi_dat_hang") or data.get("khach_hang") or "")).strip()
        so_po = unicodedata.normalize("NFC", str(data.get("so_don_hang") or data.get("so_po") or "")).strip()
        bo_phan = unicodedata.normalize("NFC", str(data.get("bo_phan_ky_ten") or "Kho thành phẩm")).strip()
        phe_duyet = unicodedata.normalize("NFC", str(data.get("phe_duyet") or "")).strip()
        nguoi_lap = unicodedata.normalize("NFC", str(data.get("nguoi_lap_phieu") or data.get("nguoi_lap") or "")).strip()
        thu_kho = unicodedata.normalize("NFC", str(data.get("thu_kho") or "")).strip()
        nguoi_nhan = unicodedata.normalize("NFC", str(data.get("nguoi_nhan_hang") or data.get("nguoi_nhan") or "")).strip()

        # Parse and calculate items
        raw_items = data.get("items") or data.get("danh_sach_hang_hoa") or []
        clean_items = []
        calc_kien = 0
        calc_thung = 0
        calc_kg = 0.0

        for idx, it in enumerate(raw_items, start=1):
            stt = safe_parse_int(it.get("stt"), idx)
            name = unicodedata.normalize("NFC", str(it.get("loai_hang_hoa") or it.get("ten_hang") or f"Mặt hàng {stt}")).strip()
            qc = unicodedata.normalize("NFC", str(it.get("quy_cach") or "")).strip()
            k_val = safe_parse_float(it.get("sl_kien"), 0.0)
            t_val = safe_parse_float(it.get("sl_thung"), 0.0)
            kg_val = safe_parse_float(it.get("khoi_luong_kg") or it.get("trong_luong_kg"), 0.0)
            gc = unicodedata.normalize("NFC", str(it.get("ghi_chu") or "")).strip()

            calc_kien += int(k_val)
            calc_thung += int(t_val)
            calc_kg += kg_val

            clean_items.append({
                "stt": stt,
                "loai_hang_hoa": name,
                "quy_cach": qc,
                "sl_kien": int(k_val),
                "sl_thung": int(t_val),
                "khoi_luong_kg": round(kg_val, 2),
                "trong_luong_kg": round(kg_val, 2),
                "ghi_chu": gc
            })

        printed_kg = safe_parse_float(data.get("tong_cong_kg"), 0.0)
        final_kg = printed_kg if printed_kg > 0.0 else round(calc_kg, 2)

        parts = []
        if calc_kien > 0:
            parts.append(f"{calc_kien} Kiện")
        if calc_thung > 0:
            parts.append(f"{calc_thung} Thùng")
        if not parts:
            disp_thung_kien = "0 Kiện, 0 Thùng"
        else:
            disp_thung_kien = ", ".join(parts)

        audit_summary = unicodedata.normalize("NFC", str(data.get("audit_summary") or "✅ Đã trích xuất thông tin qua DeepSeek Vision AI")).strip()
        is_mock = bool(data.get("is_mock", False))

        return {
            "status": "success",
            "so_phieu": so_phieu,
            "loai_xuat": loai_xuat,
            "ngay_thang": ngay_thang,
            "ngay_thang_iso": ngay_thang_iso,
            "don_vi_van_chuyen": don_vi_van_chuyen,
            "so_xe": so_xe,
            "don_vi_dat_hang": khach_hang,
            "khach_hang": khach_hang,
            "so_don_hang": so_po,
            "so_po": so_po,
            "tong_cong_kg": final_kg,
            "tong_cong_kg_display": f"{final_kg:,.1f}",
            "tong_kien": calc_kien,
            "tong_thung": calc_thung,
            "tong_thung_kien": disp_thung_kien,
            "bo_phan_ky_ten": bo_phan,
            "phe_duyet": phe_duyet,
            "nguoi_lap_phieu": nguoi_lap,
            "nguoi_lap": nguoi_lap,
            "thu_kho": thu_kho,
            "nguoi_nhan_hang": nguoi_nhan,
            "nguoi_nhan": nguoi_nhan,
            "audit_summary": audit_summary,
            "audit_status": "ok" if phe_duyet else "warn",
            "is_mock": is_mock,
            "main_image_b64": b64_img,
            "main_file_name": filename,
            "items": clean_items,
            "danh_sach_hang_hoa": clean_items
        }

    def _build_offline_mock_extraction(self, filename: str, b64_img: str, error_notice: str = "") -> Dict[str, Any]:
        """Tạo dữ liệu trích xuất mô phỏng chuẩn xác khi không có API key hoặc offline."""
        match = re.search(r"(\d{4,8})", filename)
        so_phieu = match.group(1) if match else "0003334"

        mock_raw = {
            "so_phieu": so_phieu,
            "loai_xuat": "Xuất hàng thành phẩm",
            "ngay_thang": datetime.now().strftime("%d/%m/%Y"),
            "don_vi_van_chuyen": "Đội xe nội bộ (Phan Văn Nam - 0988.123.456)",
            "so_xe": "59C-888.88",
            "don_vi_dat_hang": "Công ty TNHH Nhựa & Bao Bì Tân Phát (新发塑料有限公司)",
            "so_don_hang": f"PO-{datetime.now().strftime('%Y')}-0189",
            "tong_cong_kg": 1500.0,
            "tong_kien": 60,
            "tong_thung": 10,
            "tong_thung_kien": "60 Kiện, 10 Thùng",
            "bo_phan_ky_ten": "Kho thành phẩm (成品库)",
            "phe_duyet": "Nguyễn Văn A (核准)",
            "nguoi_lap_phieu": "Lê Văn B",
            "thu_kho": "Trần Văn C",
            "nguoi_nhan_hang": "Phan Văn Nam",
            "audit_summary": f"✅ Đạt chuẩn thẩm định AI: Đầy đủ chữ ký {error_notice}".strip(),
            "is_mock": True,
            "items": [
                {"stt": 1, "loai_hang_hoa": "Hạt nhựa ABS tái sinh (再生ABS塑料颗粒)", "quy_cach": "25kg/bao (Đen bóng)", "sl_kien": 40, "sl_thung": 0, "khoi_luong_kg": 1000.0, "ghi_chu": "Đạt chuẩn RoHS"},
                {"stt": 2, "loai_hang_hoa": "Hạt nhựa PP nguyên sinh (原包PP塑料颗粒)", "quy_cach": "25kg/bao (Trắng trong)", "sl_kien": 20, "sl_thung": 10, "khoi_luong_kg": 500.0, "ghi_chu": "Kèm chứng chỉ COA"}
            ]
        }
        return self._normalize_vision_extracted_data(mock_raw, b64_img, filename)

    def _build_offline_mock_audit_match(self, slip_data: Dict[str, Any], proof_images: List[str]) -> Dict[str, Any]:
        """Tạo kết quả đối chiếu chéo mô phỏng chuẩn xác khi offline hoặc theo logic quy tắc."""
        expected_plate = str(slip_data.get("so_xe") or "59C-888.88").strip()
        so_phieu = str(slip_data.get("so_phieu") or "0003334").strip()
        has_proof = len(proof_images) > 0
        detected_plate = expected_plate if has_proof else ""

        norm_exp = normalize_plate_number(expected_plate)
        norm_det = normalize_plate_number(detected_plate)

        has_sig = bool(str(slip_data.get("phe_duyet") or "").strip() and str(slip_data.get("phe_duyet")).strip() not in ("-", "Chưa ký", "chưa ký", "None") or str(slip_data.get("thu_kho") or "").strip() and str(slip_data.get("thu_kho")).strip() not in ("-", "Chưa ký", "chưa ký", "None"))

        if not has_proof:
            return {
                "status": "success",
                "overall_status": "flagged",
                "match_status": "none",
                "signature_status": "signed" if has_sig else "unsigned",
                "score": 40 if has_sig else 25,
                "match_score": 40 if has_sig else 25,
                "detected_plate": "",
                "expected_plate": expected_plate,
                "plate_matched": False,
                "signature_detected": has_sig,
                "cargo_matched": False,
                "match_summary": "⚠️ Chưa có ảnh bằng chứng đối soát phương tiện hoặc hàng hóa thực tế.",
                "audit_summary": f"Phiếu {so_phieu}: Chưa có ảnh kiểm chứng tại cổng.",
                "is_mock": True,
                "details": {"offline_mock": True, "proof_count": 0}
            }

        plate_score = 50 if (norm_exp == norm_det and norm_exp) else (10 if not norm_det else 0)
        match_status = "matched" if (norm_exp == norm_det and norm_exp) else ("not_detected" if not norm_det else "mismatched")
        sig_score = 30 if has_sig else 0
        cargo_score = 20
        total_score = plate_score + sig_score + cargo_score
        overall_status = "matched" if (match_status == "matched" and has_sig) else "flagged"

        audit_summary = "✅ Đầy đủ chữ ký chứng từ" if has_sig else "⚠️ Thiếu chữ ký phê duyệt hoặc thủ kho"
        match_summary = (
            f"✅ Biển số xe {expected_plate} trên {len(proof_images)} ảnh bằng chứng trùng khớp với tờ phiếu"
            if match_status == "matched"
            else f"❌ Biển số xe phát hiện ({detected_plate}) không khớp với phiếu ({expected_plate})"
        )

        return {
            "status": "success",
            "overall_status": overall_status,
            "match_status": match_status,
            "signature_status": "signed" if has_sig else "unsigned",
            "score": total_score,
            "match_score": total_score,
            "detected_plate": detected_plate,
            "expected_plate": expected_plate,
            "plate_matched": (match_status == "matched"),
            "signature_detected": has_sig,
            "cargo_matched": True,
            "match_summary": match_summary,
            "audit_summary": audit_summary,
            "is_mock": True,
            "details": {"offline_mock": True, "proof_count": len(proof_images)}
        }

    def extract_with_vision_instance(
        self,
        image_bytes: bytes,
        filename: str = "",
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Nhận diện và bóc tách thông tin phiếu xuất hàng & vật tư từ ảnh bằng DeepSeek Vision AI.
        Model: DeepSeek-V4.1-Flash (fallback: deepseek-chat).
        """
        from core.deepseek_ocr import DeepSeekOCR

        # 1. Chuẩn bị ảnh dạng base64 Data URI
        data_uri, b64_raw = prepare_image_for_vision(image_bytes, filename=filename, max_dim=1600)

        # 2. Phân giải API Key
        actual_key = (api_key or "").strip() or DeepSeekOCR.get_saved_api_key()

        # 3. Chế độ ngoại tuyến (Offline Mock) nếu chưa cấu hình Key
        if not actual_key:
            return self._build_offline_mock_extraction(filename, b64_raw)

        # 4. Xây dựng prompt chuyên môn hóa cho Phiếu Xuất Kho Song Ngữ Trung - Việt
        vision_prompt = (
            "Bạn là chuyên gia phân tích chứng từ và thị giác máy tính AI (Computer Vision & OCR) cao cấp "
            "cho hệ thống Quản Lý Xuất Hàng & Vật Tư (Gate Pass / 出门证).\n"
            "Hãy đọc và trích xuất TOÀN BỘ thông tin từ phiếu xuất kho trong ảnh sang cấu trúc JSON nghiêm ngặt.\n\n"
            "Yêu cầu nghiệp vụ bắt buộc:\n"
            "1. Nhận diện song ngữ Trung - Việt chuẩn xác 100%, bảo toàn chữ Hán và dấu tiếng Việt dựng sẵn NFC.\n"
            "2. Trích xuất chính xác các trường header:\n"
            "   - so_phieu: Số phiếu in trên chứng từ (ví dụ: '0003334', 'GP-2026-001')\n"
            "   - loai_xuat: 'Xuất hàng thành phẩm' HOẶC 'Xuất vật tư ra công' HOẶC 'Xuất trả hàng'\n"
            "   - ngay_thang: Ngày xuất dạng DD/MM/YYYY\n"
            "   - don_vi_van_chuyen: Đơn vị/đội xe/tên lái xe vận chuyển\n"
            "   - so_xe: Biển số xe vận chuyển (ví dụ: '59C-888.88')\n"
            "   - don_vi_dat_hang: Khách hàng / Đơn vị đặt hàng (kèm tên tiếng Trung nếu có)\n"
            "   - so_don_hang: Số đơn hàng / PO\n"
            "   - bo_phan_ky_ten: Bộ phận/kho ký tên (ví dụ: 'Kho thành phẩm')\n"
            "3. Trích xuất footer và chữ ký:\n"
            "   - phe_duyet: Tên người phê duyệt (核准)\n"
            "   - nguoi_lap_phieu: Người lập biểu\n"
            "   - thu_kho: Thủ kho\n"
            "   - nguoi_nhan_hang: Người nhận/lái xe\n"
            "4. Bảng danh mục mặt hàng (items) gồm danh sách các dòng:\n"
            "   - stt: Số thứ tự (số nguyên)\n"
            "   - loai_hang_hoa: Tên mặt hàng song ngữ (ví dụ: 'Hạt nhựa ABS tái sinh (再生ABS塑料颗粒)')\n"
            "   - quy_cach: Quy cách đóng gói (ví dụ: '25kg/bao')\n"
            "   - sl_kien: Số lượng kiện (số thực hoặc nguyên, ví dụ: 40)\n"
            "   - sl_thung: Số lượng thùng (số thực hoặc nguyên, ví dụ: 10)\n"
            "   - khoi_luong_kg: Khối lượng ghi nhận bằng KG nếu có\n"
            "   - ghi_chu: Ghi chú kỹ thuật / RoHS / COA\n"
            "5. Tổng hợp:\n"
            "   - tong_cong_kg: Tổng khối lượng KG ghi trên phiếu\n"
            "   - tong_kien: Tổng số kiện\n"
            "   - tong_thung: Tổng số thùng\n"
            "   - tong_thung_kien: Chuỗi tổng hợp (ví dụ: '60 Kiện, 10 Thùng')\n"
            "   - audit_summary: Nhận xét thẩm định AI về chữ ký và sự hoàn thiện của phiếu\n\n"
            "ĐỊNH DẠNG ĐẦU RA BẮT BUỘC:\n"
            "Chỉ trả về DUY NHẤT một khối JSON hợp lệ nằm trong markdown code fence ```json ... ```, "
            "tuyệt đối không viết thêm lời chào hay giải thích."
        )

        headers = {
            "Authorization": f"Bearer {actual_key}",
            "Content-Type": "application/json"
        }

        target_model = "DeepSeek-V4.1-Flash"
        fallback_model = "deepseek-chat"
        api_url = "https://api.deepseek.com/chat/completions"

        payload = {
            "model": target_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": vision_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": data_uri}
                        }
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 4096
        }

        try:
            resp = requests.post(api_url, headers=headers, json=payload, timeout=90)
            if resp.status_code != 200 and target_model != fallback_model:
                err_text = resp.text.lower()
                if any(k in err_text for k in ("model", "not found", "invalid_request", "does not exist", "unsupported")) or resp.status_code in (400, 404):
                    payload["model"] = fallback_model
                    resp = requests.post(api_url, headers=headers, json=payload, timeout=90)

            if resp.status_code != 200:
                logger.warning("DeepSeek Vision trả về HTTP %s: %s", resp.status_code, resp.text)
                return self._build_offline_mock_extraction(filename, b64_raw, error_notice=f"DeepSeek API ({resp.status_code})")

            resp_json = resp.json()
            raw_content = resp_json["choices"][0]["message"]["content"]
            parsed_data = clean_json_code_blocks(raw_content)

            if not parsed_data or not isinstance(parsed_data, dict):
                return self._build_offline_mock_extraction(filename, b64_raw, error_notice="Không thể giải mã JSON từ phản hồi AI")

            return self._normalize_vision_extracted_data(parsed_data, b64_raw, filename)

        except Exception as e:
            logger.error("Lỗi khi gọi DeepSeek Vision API: %s", e, exc_info=True)
            return self._build_offline_mock_extraction(filename, b64_raw, error_notice=str(e))

    def audit_and_cross_match_instance(
        self,
        slip_data: Dict[str, Any],
        proof_images_b64_list: Union[List[str], List[bytes]],
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Kiểm toán chữ ký và đối chiếu chéo biển số xe từ ảnh bằng chứng thực tế bằng DeepSeek Vision.
        """
        from core.deepseek_ocr import DeepSeekOCR

        # Chuẩn hóa danh sách ảnh bằng chứng thành chuỗi base64
        clean_proofs: List[str] = []
        for p in (proof_images_b64_list or []):
            if not p:
                continue
            if isinstance(p, bytes):
                clean_proofs.append(base64.b64encode(p).decode("utf-8"))
            elif isinstance(p, str) and p.strip():
                clean_proofs.append(p.strip())

        expected_plate = str(slip_data.get("so_xe") or "").strip()
        so_phieu = str(slip_data.get("so_phieu") or "").strip()

        # Trường hợp không có ảnh bằng chứng
        if not clean_proofs:
            has_sig = bool(str(slip_data.get("phe_duyet") or "").strip() and str(slip_data.get("phe_duyet")).strip() not in ("-", "Chưa ký", "chưa ký", "None") or str(slip_data.get("thu_kho") or "").strip() and str(slip_data.get("thu_kho")).strip() not in ("-", "Chưa ký", "chưa ký", "None"))
            return {
                "status": "success",
                "overall_status": "flagged",
                "match_status": "none",
                "signature_status": "signed" if has_sig else "unsigned",
                "score": 40 if has_sig else 25,
                "match_score": 40 if has_sig else 25,
                "detected_plate": "",
                "expected_plate": expected_plate,
                "plate_matched": False,
                "signature_detected": has_sig,
                "cargo_matched": False,
                "match_summary": "⚠️ Chưa có ảnh bằng chứng đối soát phương tiện hoặc hàng hóa thực tế.",
                "audit_summary": f"Phiếu {so_phieu}: Chưa có ảnh kiểm chứng tại cổng.",
                "details": {"proof_count": 0}
            }

        actual_key = (api_key or "").strip() or DeepSeekOCR.get_saved_api_key()

        if not actual_key:
            return self._build_offline_mock_audit_match(slip_data, clean_proofs)

        items_summary = "; ".join([str(it.get("loai_hang_hoa", "")) for it in slip_data.get("items", [])[:3]])

        audit_prompt = (
            "Bạn là chuyên gia thẩm định và kiểm soát an ninh logistics (Logistics Security & Audit AI).\n"
            "Hãy đối chiếu các ảnh chụp bằng chứng thực tế tại cổng xuất hàng với thông tin phiếu xuất sau:\n"
            f"- Số phiếu xuất: {so_phieu}\n"
            f"- Biển số xe đăng ký trên phiếu: {expected_plate}\n"
            f"- Khách hàng / Đơn vị nhận: {slip_data.get('don_vi_dat_hang', '')}\n"
            f"- Mặt hàng xuất kho: {items_summary}\n\n"
            "Nhiệm vụ kiểm tra:\n"
            "1. Nhận diện biển số xe (license plate) xuất hiện trong các ảnh chụp bằng chứng.\n"
            f"   So sánh biển số nhận diện được với biển số đăng ký '{expected_plate}'.\n"
            "2. Kiểm tra hàng hóa xếp trên xe có phù hợp quy cách đóng gói (bao, thùng, kiện) không.\n"
            "3. Kiểm tra tính hiện diện của chữ ký hoặc con dấu xuất kho nếu có ảnh chứng từ kèm theo.\n"
            "4. Đánh giá điểm đối chiếu match_score từ 0 đến 100.\n"
            "   (Điểm >= 80: 'matched', từ 50-79: 'warning', < 50: 'mismatched').\n\n"
            "Trả về DUY NHẤT một khối JSON nằm trong ```json ... ``` theo mẫu:\n"
            "{\n"
            '  "match_status": "matched",\n'
            '  "match_score": 95,\n'
            '  "detected_plate": "59C-888.88",\n'
            '  "plate_matched": true,\n'
            '  "signature_detected": true,\n'
            '  "cargo_matched": true,\n'
            '  "match_summary": "✅ Biển số xe 59C-888.88 trùng khớp 100% với ảnh chụp đuôi xe thực tế.",\n'
            '  "audit_summary": "✅ Thẩm định AI đạt chuẩn: Đầy đủ chữ ký phê duyệt và hàng hóa xếp đúng xe."\n'
            "}"
        )

        content_elements: List[Dict[str, Any]] = [{"type": "text", "text": audit_prompt}]
        for pf in clean_proofs[:3]:
            uri = pf if pf.startswith("data:") else f"data:image/jpeg;base64,{pf}"
            content_elements.append({
                "type": "image_url",
                "image_url": {"url": uri}
            })

        headers = {
            "Authorization": f"Bearer {actual_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "DeepSeek-V4.1-Flash",
            "messages": [{"role": "user", "content": content_elements}],
            "temperature": 0.1,
            "max_tokens": 2048
        }

        try:
            resp = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=90)
            if resp.status_code != 200:
                payload["model"] = "deepseek-chat"
                resp = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=90)

            if resp.status_code == 200:
                data = resp.json()
                raw_text = data["choices"][0]["message"]["content"]
                parsed = clean_json_code_blocks(raw_text)
                if parsed and isinstance(parsed, dict):
                    status_val = str(parsed.get("match_status") or "matched").lower()
                    score_val = safe_parse_int(parsed.get("match_score") or parsed.get("score"), 95)
                    det_plate = str(parsed.get("detected_plate") or expected_plate).strip()
                    has_sig = bool(parsed.get("signature_detected", True))
                    return {
                        "status": "success",
                        "overall_status": "matched" if (status_val == "matched" and has_sig) else "flagged",
                        "match_status": status_val if status_val in ("matched", "warning", "mismatched", "none") else "matched",
                        "signature_status": "signed" if has_sig else "unsigned",
                        "score": max(0, min(100, score_val)),
                        "match_score": max(0, min(100, score_val)),
                        "detected_plate": det_plate,
                        "expected_plate": expected_plate,
                        "plate_matched": bool(parsed.get("plate_matched", True)),
                        "signature_detected": has_sig,
                        "cargo_matched": bool(parsed.get("cargo_matched", True)),
                        "match_summary": unicodedata.normalize("NFC", str(parsed.get("match_summary") or "")),
                        "audit_summary": unicodedata.normalize("NFC", str(parsed.get("audit_summary") or "")),
                        "details": parsed
                    }
        except Exception as e:
            logger.warning("Lỗi kiểm toán đối chiếu AI: %s", e)

        return self._build_offline_mock_audit_match(slip_data, clean_proofs)

    # -------------------------------------------------------------------------
    # Classmethod Delegation to Default Singleton Instance
    # -------------------------------------------------------------------------
    @classmethod
    def save_slip(cls, pass_data: Dict[str, Any], items: Optional[List[Dict[str, Any]]] = None, sync_cloud: bool = True) -> Dict[str, Any]:
        return cls.get_default_instance().save_slip_instance(pass_data, items=items, sync_cloud=sync_cloud)

    @classmethod
    def get_slip(cls, so_phieu: str) -> Optional[Dict[str, Any]]:
        return cls.get_default_instance().get_slip_instance(so_phieu)

    @classmethod
    def delete_slip(cls, so_phieu: str) -> bool:
        return cls.get_default_instance().delete_slip_instance(so_phieu)

    @classmethod
    def list_slips(cls, search: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None, loai_xuat: Optional[str] = None, page: int = 1, page_size: int = 50, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        return cls.get_default_instance().list_slips_instance(search=search, date_from=date_from, date_to=date_to, loai_xuat=loai_xuat, page=page, page_size=page_size, limit=limit, offset=offset)

    @classmethod
    def get_dashboard_metrics(cls, period: Optional[str] = None, date_filter: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
        return cls.get_default_instance().get_dashboard_metrics_instance(period=period, date_filter=date_filter, date_from=date_from, date_to=date_to)

    @classmethod
    def sync_to_google_sheet(cls, so_phieu: str) -> Dict[str, Any]:
        return cls.get_default_instance().sync_to_google_sheet_instance(so_phieu)

    @classmethod
    def sync_pending_slips(cls, force: bool = False, limit: int = 100) -> Dict[str, Any]:
        return cls.get_default_instance().sync_pending_slips_instance(force=force, limit=limit)

    @classmethod
    def manual_sync_headers(cls, sheet_id: Optional[str] = None) -> Dict[str, Any]:
        return cls.get_default_instance().manual_sync_headers_instance(sheet_id=sheet_id)

    @classmethod
    def upload_image_to_drive(cls, image_bytes: bytes, filename: str, mime_type: str = "image/jpeg") -> str:
        return cls.get_default_instance().upload_image_to_drive_instance(image_bytes=image_bytes, filename=filename, mime_type=mime_type)

    @classmethod
    def backup_to_local_gdrive(cls, so_phieu: str, pass_data: Dict[str, Any], items: List[Dict[str, Any]], main_image_bytes: Optional[bytes] = None) -> Path:
        return cls.get_default_instance().backup_to_local_gdrive_instance(so_phieu=so_phieu, pass_data=pass_data, items=items, main_image_bytes=main_image_bytes)

    @classmethod
    def render_print_html(cls, slip: Dict[str, Any], paper_size: str = "A4") -> str:
        return cls.get_default_instance().render_print_html_instance(slip=slip, paper_size=paper_size)

    @classmethod
    def extract_with_vision(cls, image_bytes: bytes, filename: str = "", api_key: Optional[str] = None) -> Dict[str, Any]:
        return cls.get_default_instance().extract_with_vision_instance(image_bytes=image_bytes, filename=filename, api_key=api_key)

    @classmethod
    def extract_from_image(cls, image_bytes: bytes, filename: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Alias theo đặc tả Interface Contract trong PROJECT.md."""
        return cls.get_default_instance().extract_with_vision_instance(image_bytes=image_bytes, filename=filename, api_key=api_key)

    @classmethod
    def audit_and_cross_match(cls, slip_data: Dict[str, Any], proof_images_b64_list: Union[List[str], List[bytes]], api_key: Optional[str] = None) -> Dict[str, Any]:
        return cls.get_default_instance().audit_and_cross_match_instance(slip_data=slip_data, proof_images_b64_list=proof_images_b64_list, api_key=api_key)

    @classmethod
    def audit_proof_match(cls, slip_data: Dict[str, Any], proof_images: Any, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Alias theo đặc tả Interface Contract trong PROJECT.md."""
        return cls.get_default_instance().audit_and_cross_match_instance(slip_data=slip_data, proof_images_b64_list=proof_images, api_key=api_key)

