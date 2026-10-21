"""
core/plant_registry.py
──────────────────────
QUẢN TRỊ THỰC THỂ CHI NHÁNH & NHÀ MÁY (TITANPDF MULTI-PLANT ENTERPRISE)
Cung cấp:
- Quản lý danh mục cơ sở / nhà máy (plants) trên SQLite WAL tập trung
- Khởi tạo seed data 3 cơ sở chuẩn: BD (Bình Dương - HQ), DN (Đồng Nai), HP (Hải Phòng)
- CRUD và Toggle trạng thái hoạt động của từng chi nhánh
- Migration tự động gắn nhãn plant_code & plant_name vào các bảng:
  chemicals, monthly_periods, monthly_inventory_records, inventory_transactions, gatepass_slips
- Giải quyết ngữ cảnh chi nhánh theo thứ bậc (Query -> Header -> User Role/Assigned -> Default)
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("titan.plant_registry")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_DB_PATH = DATA_DIR / "msds_chemical_inventory.db"

_lock = threading.RLock()

# Dữ liệu 3 cơ sở sản xuất chuẩn của doanh nghiệp
DEFAULT_PLANTS = [
    {
        "plant_code": "BD",
        "plant_name": "Nhà máy Bình Dương",
        "short_name": "Bình Dương (HQ)",
        "plant_role": "HQ",
        "address": "Lô B-3B-CN, Đường N7, KCN Bàu Bàng, Huyện Bàu Bàng, Tỉnh Bình Dương",
        "province": "Bình Dương",
        "tax_code": "3702319854",
        "contact_person": "Nguyễn Chí Tính",
        "contact_phone": "0274.376.8888",
        "contact_email": "ehs@zhanchen.vn",
        "license_info": "GCN số 48/GCN-SCT cấp ngày 15/03/2026 bởi Sở Công Thương Tỉnh Bình Dương",
        "plan_approval_no": "QD-48/UBND-BD",
        "is_hq": 1,
        "is_active": 1,
        "sort_order": 1,
    },
    {
        "plant_code": "DN",
        "plant_name": "Nhà máy Đồng Nai",
        "short_name": "Đồng Nai",
        "plant_role": "FACTORY",
        "address": "KCN Long Đức, Xã Long Đức, Huyện Long Thành, Tỉnh Đồng Nai",
        "province": "Đồng Nai",
        "tax_code": "3702319854",
        "contact_person": "Quản đốc Xưởng Sản Xuất Đồng Nai",
        "contact_phone": "0251.389.1234",
        "contact_email": "warehouse.dn@zhanchen.vn",
        "license_info": "GCN số 19/GCN-SCT cấp bởi Sở Công Thương Tỉnh Đồng Nai",
        "plan_approval_no": "QD-19/UBND-DN",
        "is_hq": 0,
        "is_active": 1,
        "sort_order": 2,
    },
    {
        "plant_code": "HP",
        "plant_name": "Chi nhánh Hải Phòng",
        "short_name": "Hải Phòng",
        "plant_role": "HUB",
        "address": "KCN Đình Vũ, Phường Đông Hải 2, Quận Hải An, TP. Hải Phòng",
        "province": "Hải Phòng",
        "tax_code": "3702319854",
        "contact_person": "Trưởng Kho Trung Chuyển Hải Phòng",
        "contact_phone": "0225.385.6789",
        "contact_email": "warehouse.hp@zhanchen.vn",
        "license_info": "GCN số 08/GCN-SCT cấp bởi Sở Công Thương TP. Hải Phòng",
        "plan_approval_no": "QD-08/UBND-HP",
        "is_hq": 0,
        "is_active": 1,
        "sort_order": 3,
    },
]

KNOWN_PLANT_NAMES = {
    "BD": "Nhà máy Bình Dương",
    "DN": "Nhà máy Đồng Nai",
    "HP": "Chi nhánh Hải Phòng",
    "ALL": "Tất cả chi nhánh (HQ View)",
}


class PlantRegistry:
    """Quản trị danh mục nhà máy & chi nhánh trong hệ sinh thái TitanPDF."""

    _initialized: bool = False

    @classmethod
    def get_connection(cls, db_path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
        path = Path(db_path) if db_path else DEFAULT_DB_PATH
        conn = sqlite3.connect(str(path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        return conn

    @classmethod
    def init_db(cls, db_path: Optional[Union[str, Path]] = None) -> None:
        """Khởi tạo bảng plants, nạp dữ liệu seed chuẩn và chạy migration các bảng liên quan."""
        with _lock:
            with cls.get_connection(db_path) as conn:
                # 1. Bảng plants
                conn.execute("""
                CREATE TABLE IF NOT EXISTS plants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plant_code TEXT UNIQUE NOT NULL,
                    plant_name TEXT NOT NULL,
                    short_name TEXT DEFAULT '',
                    plant_role TEXT DEFAULT 'FACTORY',
                    address TEXT NOT NULL,
                    province TEXT DEFAULT '',
                    tax_code TEXT DEFAULT '3702319854',
                    contact_person TEXT DEFAULT '',
                    contact_phone TEXT DEFAULT '',
                    contact_email TEXT DEFAULT '',
                    license_info TEXT DEFAULT '',
                    plan_approval_no TEXT DEFAULT '',
                    is_hq INTEGER DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """)
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_plants_code ON plants(plant_code);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_plants_active ON plants(is_active);")

                # Kiểm tra các cột bảng plants
                cursor = conn.execute("PRAGMA table_info(plants)")
                cols = {row[1] for row in cursor.fetchall()}
                plant_cols_to_add = [
                    ("short_name", "TEXT DEFAULT ''"),
                    ("plant_role", "TEXT DEFAULT 'FACTORY'"),
                    ("province", "TEXT DEFAULT ''"),
                    ("tax_code", "TEXT DEFAULT '3702319854'"),
                    ("contact_person", "TEXT DEFAULT ''"),
                    ("contact_phone", "TEXT DEFAULT ''"),
                    ("contact_email", "TEXT DEFAULT ''"),
                    ("license_info", "TEXT DEFAULT ''"),
                    ("plan_approval_no", "TEXT DEFAULT ''"),
                    ("is_hq", "INTEGER DEFAULT 0"),
                    ("sort_order", "INTEGER DEFAULT 0"),
                ]
                for col_name, col_def in plant_cols_to_add:
                    if col_name not in cols:
                        try:
                            conn.execute(f"ALTER TABLE plants ADD COLUMN {col_name} {col_def};")
                        except Exception:
                            pass

                # 2. Tự động nạp default seed plants nếu chưa có
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for p in DEFAULT_PLANTS:
                    existing = conn.execute(
                        "SELECT id FROM plants WHERE UPPER(plant_code) = UPPER(?)", (p["plant_code"],)
                    ).fetchone()
                    if not existing:
                        conn.execute("""
                        INSERT INTO plants (
                            plant_code, plant_name, short_name, plant_role, address, province,
                            tax_code, contact_person, contact_phone, contact_email, license_info,
                            plan_approval_no, is_hq, is_active, sort_order, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            p["plant_code"], p["plant_name"], p.get("short_name", ""), p.get("plant_role", "FACTORY"),
                            p["address"], p.get("province", ""), p.get("tax_code", "3702319854"),
                            p.get("contact_person", ""), p.get("contact_phone", ""), p.get("contact_email", ""),
                            p.get("license_info", ""), p.get("plan_approval_no", ""), p.get("is_hq", 0),
                            p.get("is_active", 1), p.get("sort_order", 0), now_str, now_str
                        ))
                conn.commit()

            # 3. Chạy migration các bảng liên quan
            cls.migrate_database_schema(db_path)
            cls._initialized = True
            logger.info("PlantRegistry đã khởi tạo thành công với các chi nhánh chuẩn.")

    @classmethod
    def migrate_database_schema(cls, db_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Di trú cấu trúc SQLite, thêm plant_code và plant_name vào các bảng:
        chemicals, monthly_periods, monthly_inventory_records, inventory_transactions, gatepass_slips.
        Tự động backfill dữ liệu cũ sang 'BD' / 'Nhà máy Bình Dương'.
        """
        target_tables = [
            "chemicals",
            "monthly_periods",
            "monthly_inventory_records",
            "inventory_transactions",
            "gatepass_slips"
        ]
        migrated: Dict[str, List[str]] = {}

        with _lock:
            with cls.get_connection(db_path) as conn:
                for table in target_tables:
                    # Kiểm tra bảng có tồn tại trong sqlite_master không
                    t_exists = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
                    ).fetchone()
                    if not t_exists:
                        continue

                    cursor = conn.execute(f"PRAGMA table_info({table})")
                    existing_cols = {row[1] for row in cursor.fetchall()}
                    added_cols = []

                    if "plant_code" not in existing_cols:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN plant_code TEXT DEFAULT 'BD';")
                        added_cols.append("plant_code")
                    if "plant_name" not in existing_cols:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN plant_name TEXT DEFAULT 'Nhà máy Bình Dương';")
                        added_cols.append("plant_name")

                    # Backfill các hàng null hoặc rỗng
                    conn.execute(f"""
                        UPDATE {table}
                        SET plant_code = 'BD'
                        WHERE plant_code IS NULL OR TRIM(plant_code) = '';
                    """)
                    conn.execute(f"""
                        UPDATE {table}
                        SET plant_name = 'Nhà máy Bình Dương'
                        WHERE plant_name IS NULL OR TRIM(plant_name) = '';
                    """)

                    migrated[table] = added_cols

                # Tạo chỉ mục tối ưu truy vấn
                conn.execute("CREATE INDEX IF NOT EXISTS idx_chemicals_plant_code ON chemicals(plant_code);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_monthly_periods_plant ON monthly_periods(plant_code);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_monthly_records_plant ON monthly_inventory_records(plant_code);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_plant ON inventory_transactions(plant_code);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gp_slips_plant ON gatepass_slips(plant_code);")
                conn.commit()

        return {"success": True, "migrated": migrated}

    @classmethod
    def get_all_plants(cls, include_inactive: bool = False, db_path: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
        """Lấy danh sách tất cả các chi nhánh / nhà máy."""
        cls.init_db(db_path)
        with cls.get_connection(db_path) as conn:
            if include_inactive:
                sql = "SELECT * FROM plants ORDER BY sort_order ASC, id ASC"
                rows = conn.execute(sql).fetchall()
            else:
                sql = "SELECT * FROM plants WHERE is_active = 1 ORDER BY sort_order ASC, id ASC"
                rows = conn.execute(sql).fetchall()
            return [dict(r) for r in rows]

    @classmethod
    def get_plant(cls, code: str, db_path: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết một nhà máy theo mã (không phân biệt hoa thường)."""
        cls.init_db(db_path)
        if not code:
            return None
        clean_code = str(code).strip().upper()
        with cls.get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM plants WHERE UPPER(plant_code) = UPPER(?) LIMIT 1", (clean_code,)
            ).fetchone()
            return dict(row) if row else None

    @classmethod
    def create_plant(cls, data: Dict[str, Any], db_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """Tạo mới một chi nhánh / nhà máy trong hệ thống."""
        cls.init_db(db_path)
        raw_code = str(data.get("plant_code") or "").strip().upper()
        name = str(data.get("plant_name") or "").strip()
        address = str(data.get("address") or "").strip()

        if not raw_code:
            raise ValueError("Mã chi nhánh (plant_code) không được để trống!")
        if len(raw_code) < 2 or len(raw_code) > 20:
            raise ValueError("Mã chi nhánh (plant_code) phải có độ dài từ 2 đến 20 ký tự!")
        if not name:
            raise ValueError("Tên chi nhánh (plant_name) không được để trống!")
        if not address:
            raise ValueError("Địa chỉ chi nhánh (address) không được để trống!")

        existing = cls.get_plant(raw_code, db_path)
        if existing:
            raise ValueError(f"Mã chi nhánh '{raw_code}' đã tồn tại trong hệ thống!")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        short_name = str(data.get("short_name") or name).strip()
        plant_role = str(data.get("plant_role") or "FACTORY").strip()
        province = str(data.get("province") or "").strip()
        tax_code = str(data.get("tax_code") or "3702319854").strip()
        contact_person = str(data.get("contact_person") or "").strip()
        contact_phone = str(data.get("contact_phone") or "").strip()
        contact_email = str(data.get("contact_email") or "").strip()
        license_info = str(data.get("license_info") or "").strip()
        plan_approval_no = str(data.get("plan_approval_no") or "").strip()
        is_hq = int(bool(data.get("is_hq", 0)))
        is_active = int(bool(data.get("is_active", 1)))
        sort_order = int(data.get("sort_order", 10))

        with _lock:
            with cls.get_connection(db_path) as conn:
                conn.execute("""
                INSERT INTO plants (
                    plant_code, plant_name, short_name, plant_role, address, province,
                    tax_code, contact_person, contact_phone, contact_email, license_info,
                    plan_approval_no, is_hq, is_active, sort_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    raw_code, name, short_name, plant_role, address, province,
                    tax_code, contact_person, contact_phone, contact_email, license_info,
                    plan_approval_no, is_hq, is_active, sort_order, now_str, now_str
                ))
                conn.commit()

        # Update in-memory lookup cache
        KNOWN_PLANT_NAMES[raw_code] = name
        return cls.get_plant(raw_code, db_path) or {}

    @classmethod
    def update_plant(cls, code: str, data: Dict[str, Any], db_path: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
        """Cập nhật thông tin chi nhánh / nhà máy."""
        cls.init_db(db_path)
        existing = cls.get_plant(code, db_path)
        if not existing:
            return None

        clean_code = existing["plant_code"]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        plant_name = str(data.get("plant_name", existing["plant_name"])).strip() or existing["plant_name"]
        short_name = str(data.get("short_name", existing.get("short_name", ""))).strip()
        plant_role = str(data.get("plant_role", existing.get("plant_role", "FACTORY"))).strip()
        address = str(data.get("address", existing["address"])).strip() or existing["address"]
        province = str(data.get("province", existing.get("province", ""))).strip()
        tax_code = str(data.get("tax_code", existing.get("tax_code", "3702319854"))).strip()
        contact_person = str(data.get("contact_person", existing.get("contact_person", ""))).strip()
        contact_phone = str(data.get("contact_phone", existing.get("contact_phone", ""))).strip()
        contact_email = str(data.get("contact_email", existing.get("contact_email", ""))).strip()
        license_info = str(data.get("license_info", existing.get("license_info", ""))).strip()
        plan_approval_no = str(data.get("plan_approval_no", existing.get("plan_approval_no", ""))).strip()
        sort_order = int(data.get("sort_order", existing.get("sort_order", 0)))

        with _lock:
            with cls.get_connection(db_path) as conn:
                conn.execute("""
                UPDATE plants SET
                    plant_name = ?, short_name = ?, plant_role = ?, address = ?,
                    province = ?, tax_code = ?, contact_person = ?, contact_phone = ?,
                    contact_email = ?, license_info = ?, plan_approval_no = ?,
                    sort_order = ?, updated_at = ?
                WHERE UPPER(plant_code) = UPPER(?)
                """, (
                    plant_name, short_name, plant_role, address,
                    province, tax_code, contact_person, contact_phone,
                    contact_email, license_info, plan_approval_no,
                    sort_order, now_str, clean_code
                ))
                conn.commit()

        KNOWN_PLANT_NAMES[clean_code] = plant_name
        return cls.get_plant(clean_code, db_path)

    @classmethod
    def toggle_plant_active(
        cls,
        code: str,
        is_active: Optional[Union[bool, int]] = None,
        db_path: Optional[Union[str, Path]] = None
    ) -> Optional[Dict[str, Any]]:
        """Kích hoạt hoặc vô hiệu hóa một chi nhánh. Không cho phép tắt Trụ sở chính (HQ)."""
        cls.init_db(db_path)
        existing = cls.get_plant(code, db_path)
        if not existing:
            return None

        clean_code = existing["plant_code"]
        current_active = bool(existing.get("is_active", 1))

        if is_active is None:
            new_active = not current_active
        else:
            new_active = bool(is_active)

        # Chặn không cho vô hiệu hóa HQ
        if existing.get("is_hq") == 1 and not new_active:
            raise ValueError("Không thể vô hiệu hóa Trụ sở chính / Kho trung tâm (HQ)!")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with _lock:
            with cls.get_connection(db_path) as conn:
                conn.execute("""
                UPDATE plants
                SET is_active = ?, updated_at = ?
                WHERE UPPER(plant_code) = UPPER(?)
                """, (1 if new_active else 0, now_str, clean_code))
                conn.commit()

        return cls.get_plant(clean_code, db_path)

    @classmethod
    def get_plant_name(cls, code: Optional[str], default: str = "Nhà máy Bình Dương", db_path: Optional[Union[str, Path]] = None) -> str:
        """Tra cứu nhanh tên chi nhánh từ mã code."""
        if not code:
            return default
        clean = str(code).strip().upper()
        if clean in KNOWN_PLANT_NAMES:
            return KNOWN_PLANT_NAMES[clean]
        p = cls.get_plant(clean, db_path)
        if p and p.get("plant_name"):
            KNOWN_PLANT_NAMES[clean] = p["plant_name"]
            return p["plant_name"]
        return default

    @classmethod
    def resolve_plant_context(
        cls,
        query_plant: Optional[str] = None,
        header_plant: Optional[str] = None,
        header_alt: Optional[str] = None,
        user_role: Optional[str] = None,
        assigned_plant: Optional[str] = None,
        default_code: Optional[str] = None,
        return_tuple: bool = False
    ) -> Union[Optional[str], Tuple[str, str]]:
        """
        Giải quyết ngữ cảnh chi nhánh theo thứ bậc:
        1. Query param (`plant_code`)
        2. HTTP Header (`X-Titan-Plant` hoặc `X-Plant-Code`)
        3. Phân quyền người dùng (Nếu là operator -> khóa ở assigned_plant)
        4. Mặc định (default_code nếu có)
        """
        # Nếu là nhân viên chi nhánh bị khóa
        if user_role == "operator" and assigned_plant:
            clean = str(assigned_plant).strip().upper()
            return (clean, cls.get_plant_name(clean)) if return_tuple else clean

        candidate = (query_plant or "").strip() or (header_plant or "").strip() or (header_alt or "").strip()
        if candidate:
            clean = candidate.upper()
            if clean in ("ALL", "HQ"):
                return ("ALL", "Tất cả chi nhánh (HQ View)") if return_tuple else "ALL"
            return (clean, cls.get_plant_name(clean)) if return_tuple else clean

        if default_code:
            fallback = str(default_code).strip().upper()
            return (fallback, cls.get_plant_name(fallback)) if return_tuple else fallback

        return ("", "") if return_tuple else None


# =============================================================================
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# =============================================================================

def init_db(db_path: Optional[Union[str, Path]] = None) -> None:
    PlantRegistry.init_db(db_path)


def migrate_database_schema(db_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    return PlantRegistry.migrate_database_schema(db_path)


def get_all_plants(include_inactive: bool = False, db_path: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    return PlantRegistry.get_all_plants(include_inactive=include_inactive, db_path=db_path)


def get_plant(code: str, db_path: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
    return PlantRegistry.get_plant(code, db_path=db_path)


def create_plant(data: Dict[str, Any], db_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    return PlantRegistry.create_plant(data, db_path=db_path)


def update_plant(code: str, data: Dict[str, Any], db_path: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
    return PlantRegistry.update_plant(code, data, db_path=db_path)


def toggle_plant_active(code: str, is_active: Optional[Union[bool, int]] = None, db_path: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
    return PlantRegistry.toggle_plant_active(code, is_active=is_active, db_path=db_path)


def get_plant_name(code: Optional[str], default: str = "Nhà máy Bình Dương", db_path: Optional[Union[str, Path]] = None) -> str:
    return PlantRegistry.get_plant_name(code, default=default, db_path=db_path)


def resolve_plant_context(
    query_plant: Optional[str] = None,
    header_plant: Optional[str] = None,
    header_alt: Optional[str] = None,
    user_role: Optional[str] = None,
    assigned_plant: Optional[str] = None,
    default_code: Optional[str] = None,
    return_tuple: bool = False
) -> Union[Optional[str], Tuple[str, str]]:
    return PlantRegistry.resolve_plant_context(
        query_plant=query_plant,
        header_plant=header_plant,
        header_alt=header_alt,
        user_role=user_role,
        assigned_plant=assigned_plant,
        default_code=default_code,
        return_tuple=return_tuple
    )
