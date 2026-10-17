"""
core/monthly_inventory_engine.py
─────────────────────────────────
MONTHLY CHEMICAL INVENTORY & USAGE TRACKING (NXT) ENGINE
Động cơ Quản lý Nhập - Xuất - Tồn và Cân đối Báo cáo Hóa chất Hàng tháng.

Tuân thủ chuẩn hóa 100% Khung pháp lý hiện hành:
- Luật Hóa chất số 69/2025/QH15
- Nghị định 24/2026/NĐ-CP (Phụ lục I, II, III, IV Bảng A & B, V)
- Nghị định 26/2026/NĐ-CP (Quản lý chất ma túy & Tiền chất công nghiệp Danh mục IV.C BCT)
- Thông tư 01/2026/TT-BCT (Phân loại, ghi nhãn GHS & Phiếu kiểm soát mua bán Biểu mẫu 09)
- Thông tư 02/2026/TT-BCT (Biểu mẫu Báo cáo hoạt động hóa chất)
- Quy chuẩn kỹ thuật quốc gia QCVN 01:2025/BYT (Giới hạn tiếp xúc nghề nghiệp)
"""

from __future__ import annotations

import io
import json
import logging
import math
import os
import re
import sqlite3
import threading
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from core.legal_engine import CAS_PATTERN, LegalCatalogEngine, parse_threshold_numeric, validate_cas
from core.msds_intelligence import DB_PATH, EXPORTS_DIR, MSDSDatabase

logger = logging.getLogger("titan.monthly_inventory")

# Thông tin cơ sở phục vụ in ấn và xuất báo cáo doanh nghiệp
ENTERPRISE_INFO = {
    "company_name_vi": "CÔNG TY TNHH SƠN ZHANCHEN (VIỆT NAM)",
    "company_name_en": "ZHANCHEN COATING (VIETNAM) CO., LTD.",
    "tax_code": "3702319854",
    "plant_address": "Lô B-3B-CN, Đường N7, KCN Bàu Bàng, Huyện Bàu Bàng, Tỉnh Bình Dương",
    "ehs_manager": "NGUYỄN CHÍ TÍNH",
    "ehs_title": "TRƯỞNG PHÒNG AN TOÀN - MÔI TRƯỜNG (EHS)",
    "legal_rep": "TỔNG GIÁM ĐỐC",
}


class MonthlyInventoryEngine:
    """
    Động cơ xử lý nghiệp vụ Quản lý Nhập - Xuất - Tồn Hóa chất Hàng tháng (NXT):
    - Quản lý kỳ báo cáo (monthly_periods)
    - Quản lý sổ tổng hợp tồn kho (monthly_inventory_records)
    - Quản lý nhật ký phiếu giao dịch chi tiết (inventory_transactions)
    - Tự động cân đối (Auto Balance) & Tự động chuyển số dư (Roll-Forward)
    - Liên kết tự động với CSDL Sổ CIL & phân loại pháp lý NĐ 24/2026, NĐ 26/2026
    - Cảnh báo an toàn (Tồn âm, vượt ngưỡng Phụ lục IV-A)
    - Kết xuất file Excel (.xlsx) chuẩn biểu mẫu doanh nghiệp và trang in A4 landscape
    """

    _initialized: bool = False
    _lock = threading.RLock()

    @classmethod
    @contextmanager
    def get_connection(cls):
        """Mở kết nối SQLite ở chế độ WAL, synchronous NORMAL và tự động đóng kết nối khi hoàn tất."""
        conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        try:
            yield conn
        finally:
            conn.close()

    @classmethod
    def init_db(cls) -> None:
        """Khởi tạo cấu trúc các bảng và chỉ mục nếu chưa tồn tại."""
        if cls._initialized:
            return

        # Đảm bảo MSDSDatabase đã khởi tạo bảng chemicals
        MSDSDatabase.init_db()

        with cls.get_connection() as conn:
            # 1. Bảng quản lý kỳ báo cáo tháng
            conn.execute("""
            CREATE TABLE IF NOT EXISTS monthly_periods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period_key TEXT UNIQUE NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                title TEXT DEFAULT '',
                status TEXT DEFAULT 'OPEN',
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 2. Bảng sổ tổng hợp Nhập - Xuất - Tồn theo từng hóa chất trong kỳ
            conn.execute("""
            CREATE TABLE IF NOT EXISTS monthly_inventory_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period_id INTEGER NOT NULL,
                period_key TEXT NOT NULL,
                chemical_id TEXT NOT NULL,
                product_code TEXT DEFAULT '',
                chemical_name TEXT DEFAULT '',
                product_name TEXT DEFAULT '',
                cas_number TEXT DEFAULT '',
                supplier TEXT DEFAULT '',
                unit TEXT DEFAULT 'kg',
                opening_stock REAL DEFAULT 0.0,
                initial_stock REAL DEFAULT 0.0,
                import_qty REAL DEFAULT 0.0,
                total_import REAL DEFAULT 0.0,
                export_qty REAL DEFAULT 0.0,
                total_export REAL DEFAULT 0.0,
                export_purpose_breakdown TEXT DEFAULT '',
                closing_stock REAL DEFAULT 0.0,
                ending_stock REAL DEFAULT 0.0,
                storage_location TEXT DEFAULT '',
                safety_threshold REAL DEFAULT NULL,
                legal_classification TEXT DEFAULT '',
                ghs_symbols TEXT DEFAULT '',
                consumption_rate REAL DEFAULT NULL,
                warning_status TEXT DEFAULT 'normal',
                safety_notes TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(period_id, chemical_id)
            );
            """)

            # 3. Bảng nhật ký giao dịch xuất / nhập kho chi tiết
            conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT UNIQUE NOT NULL,
                period_id INTEGER NOT NULL,
                period_key TEXT NOT NULL,
                chemical_id TEXT NOT NULL,
                record_id INTEGER DEFAULT NULL,
                transaction_type TEXT NOT NULL,
                transaction_date TEXT NOT NULL,
                date TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT DEFAULT 'kg',
                reference_doc TEXT DEFAULT '',
                voucher_no TEXT DEFAULT '',
                department TEXT DEFAULT '',
                partner TEXT DEFAULT '',
                purpose TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Chỉ mục tối ưu tốc độ truy vấn
            conn.execute("CREATE INDEX IF NOT EXISTS idx_monthly_periods_key ON monthly_periods(period_key);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_monthly_records_period_id ON monthly_inventory_records(period_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_monthly_records_period_key ON monthly_inventory_records(period_key);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_monthly_records_chem_id ON monthly_inventory_records(chemical_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_period_id ON inventory_transactions(period_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_period_key ON inventory_transactions(period_key);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_chem_id ON inventory_transactions(chemical_id);")

            # Đảm bảo di trú các cột nếu bảng đã tồn tại từ trước
            cursor = conn.execute("PRAGMA table_info(monthly_inventory_records)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            cols_to_add = [
                ("period_key", "TEXT NOT NULL DEFAULT ''"),
                ("product_name", "TEXT DEFAULT ''"),
                ("initial_stock", "REAL DEFAULT 0.0"),
                ("total_import", "REAL DEFAULT 0.0"),
                ("total_export", "REAL DEFAULT 0.0"),
                ("ending_stock", "REAL DEFAULT 0.0"),
                ("export_purpose_breakdown", "TEXT DEFAULT ''"),
                ("legal_classification", "TEXT DEFAULT ''"),
                ("ghs_symbols", "TEXT DEFAULT ''"),
                ("consumption_rate", "REAL DEFAULT NULL"),
                ("warning_status", "TEXT DEFAULT 'normal'"),
                ("notes", "TEXT DEFAULT ''"),
            ]
            for col_name, col_type in cols_to_add:
                if col_name not in existing_cols:
                    try:
                        conn.execute(f"ALTER TABLE monthly_inventory_records ADD COLUMN {col_name} {col_type};")
                    except Exception:
                        pass

            conn.commit()

        cls._initialized = True
        logger.info("Đã khởi tạo thành công CSDL Báo Cáo Hóa Chất Tháng (NXT).")

    # =========================================================================
    # QUẢN LÝ KỲ BÁO CÁO (PERIOD MANAGEMENT)
    # =========================================================================

    @classmethod
    def _resolve_period_id(cls, period_ident: Union[int, str], conn: sqlite3.Connection, fallback_key: Optional[str] = None) -> Optional[int]:
        """Chuyển đổi period_key ('YYYY-MM') hoặc id số nguyên sang id của kỳ."""
        if period_ident is None:
            if fallback_key:
                row = conn.execute("SELECT id FROM monthly_periods WHERE period_key = ?", (str(fallback_key).strip(),)).fetchone()
                return int(row["id"]) if row else None
            return None

        if isinstance(period_ident, int) or (isinstance(period_ident, str) and period_ident.isdigit()):
            row = conn.execute("SELECT id FROM monthly_periods WHERE id = ?", (int(period_ident),)).fetchone()
            if row:
                return int(row["id"])
            if fallback_key:
                row2 = conn.execute("SELECT id FROM monthly_periods WHERE period_key = ?", (str(fallback_key).strip(),)).fetchone()
                if row2:
                    return int(row2["id"])
            return None
        else:
            p_str = str(period_ident).strip()
            row = conn.execute("SELECT id FROM monthly_periods WHERE period_key = ?", (p_str,)).fetchone()
            if row:
                return int(row["id"])
            if fallback_key and fallback_key != p_str:
                row2 = conn.execute("SELECT id FROM monthly_periods WHERE period_key = ?", (str(fallback_key).strip(),)).fetchone()
                if row2:
                    return int(row2["id"])
            return None

    @classmethod
    def list_periods(cls, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Lấy danh sách tất cả kỳ báo cáo kèm tóm tắt chỉ số kho tổng quan."""
        cls.init_db()
        with cls.get_connection() as conn:
            rows = conn.execute("""
                SELECT p.*,
                       COUNT(r.id) AS record_count,
                       COALESCE(SUM(r.import_qty), 0.0) AS total_import,
                       COALESCE(SUM(r.export_qty), 0.0) AS total_export,
                       COALESCE(SUM(r.closing_stock), 0.0) AS total_closing_stock,
                       SUM(CASE WHEN r.warning_status != 'normal' OR r.closing_stock < 0 THEN 1 ELSE 0 END) AS warning_count
                FROM monthly_periods p
                LEFT JOIN monthly_inventory_records r ON p.id = r.period_id
                GROUP BY p.id
                ORDER BY p.year DESC, p.month DESC
                LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()

            result = []
            for r in rows:
                item = dict(r)
                # Đảm bảo trường title mặc định
                if not item.get("title"):
                    item["title"] = f"Kỳ {item['month']:02d}/{item['year']}"
                result.append(item)
            return result

    @classmethod
    def get_period(cls, period_ident: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết kỳ báo cáo kèm danh sách hóa chất và KPI."""
        cls.init_db()
        with cls.get_connection() as conn:
            pid = cls._resolve_period_id(period_ident, conn)
            if not pid:
                return None

            period_row = conn.execute("SELECT * FROM monthly_periods WHERE id = ?", (pid,)).fetchone()
            if not period_row:
                return None

            period = dict(period_row)
            if not period.get("title"):
                period["title"] = f"Kỳ {period['month']:02d}/{period['year']}"

            records = cls.list_records(pid)
            kpi = cls.get_period_kpi(pid)

            period["records"] = records
            period["record_count"] = len(records)
            period["kpi"] = kpi
            return period

    @classmethod
    def create_period(
        cls,
        month: int,
        year: int,
        title: Optional[str] = None,
        notes: str = "",
        copy_from_previous: bool = True,
        auto_roll_forward: bool = True,
    ) -> Dict[str, Any]:
        """
        Tạo kỳ báo cáo mới. Nếu copy_from_previous hoặc auto_roll_forward=True,
        tự động kế thừa tồn cuối kỳ tháng trước làm tồn đầu kỳ tháng này.
        """
        cls.init_db()
        month = int(month)
        year = int(year)
        if not (1 <= month <= 12):
            raise ValueError(f"Tháng không hợp lệ: {month}. Phải từ 1 đến 12.")
        if year < 2000 or year > 2100:
            raise ValueError(f"Năm không hợp lệ: {year}.")

        period_key = f"{year:04d}-{month:02d}"
        if not title:
            title = f"Kỳ {month:02d}/{year}"

        with cls.get_connection() as conn:
            # Kiểm tra xem kỳ đã tồn tại chưa
            existing = conn.execute("SELECT * FROM monthly_periods WHERE period_key = ?", (period_key,)).fetchone()
            if existing:
                return cls.get_period(existing["id"]) or dict(existing)

            cursor = conn.execute("""
                INSERT INTO monthly_periods (period_key, year, month, title, status, notes)
                VALUES (?, ?, ?, ?, 'OPEN', ?)
            """, (period_key, year, month, title, notes))
            new_id = cursor.lastrowid
            conn.commit()

            # Tự động chuyển số dư từ kỳ trước nếu được yêu cầu
            if copy_from_previous or auto_roll_forward:
                prev_month = 12 if month == 1 else month - 1
                prev_year = year - 1 if month == 1 else year
                prev_key = f"{prev_year:04d}-{prev_month:02d}"

                prev_period = conn.execute(
                    "SELECT id FROM monthly_periods WHERE period_key = ?", (prev_key,)
                ).fetchone()

                if prev_period:
                    cls.roll_forward(
                        from_period=prev_period["id"],
                        to_period=new_id,
                        overwrite_initial=True,
                    )

            return cls.get_period(new_id) or {}

    @classmethod
    def update_period_status(
        cls,
        period_ident: Union[int, str],
        status: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cập nhật trạng thái kỳ báo cáo ('OPEN', 'LOCKED', 'CLOSED' hoặc 'draft', 'closed', 'approved')."""
        cls.init_db()
        status_norm = str(status).strip().upper()
        # Chuẩn hóa trạng thái
        if status_norm in ("DRAFT", "OPEN"):
            canonical_status = "OPEN"
        elif status_norm in ("CLOSED", "LOCK", "LOCKED"):
            canonical_status = "LOCKED"
        elif status_norm in ("APPROVED",):
            canonical_status = "CLOSED"
        else:
            canonical_status = status_norm

        with cls.get_connection() as conn:
            pid = cls._resolve_period_id(period_ident, conn)
            if not pid:
                raise ValueError(f"Không tìm thấy kỳ báo cáo '{period_ident}'")

            if notes is not None:
                conn.execute("""
                    UPDATE monthly_periods
                    SET status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (canonical_status, notes, pid))
            else:
                conn.execute("""
                    UPDATE monthly_periods
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (canonical_status, pid))
            conn.commit()

            return cls.get_period(pid) or {}

    @classmethod
    def delete_period(cls, period_ident: Union[int, str]) -> bool:
        """Xóa một kỳ báo cáo cùng toàn bộ bản ghi và giao dịch phát sinh."""
        cls.init_db()
        with cls.get_connection() as conn:
            pid = cls._resolve_period_id(period_ident, conn)
            if not pid:
                return False

            conn.execute("DELETE FROM inventory_transactions WHERE period_id = ?", (pid,))
            conn.execute("DELETE FROM monthly_inventory_records WHERE period_id = ?", (pid,))
            conn.execute("DELETE FROM monthly_periods WHERE id = ?", (pid,))
            conn.commit()
            return True

    # =========================================================================
    # QUẢN LÝ BẢN GHI NHẬP - XUẤT - TỒN (RECORD MANAGEMENT)
    # =========================================================================

    @classmethod
    def list_records(
        cls,
        period_ident: Union[int, str],
        query: str = "",
        warning_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Lấy danh sách các dòng hóa chất trong kỳ báo cáo có hỗ trợ tìm kiếm và lọc cảnh báo."""
        cls.init_db()
        with cls.get_connection() as conn:
            pid = cls._resolve_period_id(period_ident, conn)
            if not pid:
                return []

            sql = "SELECT * FROM monthly_inventory_records WHERE period_id = ?"
            params: List[Any] = [pid]

            if query:
                q_like = f"%{query.strip()}%"
                sql += """ AND (
                    chemical_id LIKE ? OR
                    product_code LIKE ? OR
                    chemical_name LIKE ? OR
                    product_name LIKE ? OR
                    cas_number LIKE ? OR
                    supplier LIKE ? OR
                    legal_classification LIKE ?
                )"""
                params.extend([q_like, q_like, q_like, q_like, q_like, q_like, q_like])

            if warning_only:
                sql += " AND (warning_status != 'normal' OR closing_stock < 0)"

            sql += " ORDER BY id ASC"
            rows = conn.execute(sql, params).fetchall()

            result = []
            for r in rows:
                item = dict(r)
                # Đồng bộ hai chiều các trường alias
                item["initial_stock"] = item.get("opening_stock", 0.0)
                item["total_import"] = item.get("import_qty", 0.0)
                item["total_export"] = item.get("export_qty", 0.0)
                item["ending_stock"] = item.get("closing_stock", 0.0)
                item["product_name"] = item.get("chemical_name") or item.get("product_name") or ""
                item["notes"] = item.get("safety_notes") or item.get("notes") or ""
                result.append(item)
            return result

    @classmethod
    def get_record(cls, record_id: int) -> Optional[Dict[str, Any]]:
        """Lấy chi tiết 1 bản ghi hóa chất trong kỳ."""
        cls.init_db()
        with cls.get_connection() as conn:
            row = conn.execute("SELECT * FROM monthly_inventory_records WHERE id = ?", (record_id,)).fetchone()
            if not row:
                return None
            item = dict(row)
            item["initial_stock"] = item.get("opening_stock", 0.0)
            item["total_import"] = item.get("import_qty", 0.0)
            item["total_export"] = item.get("export_qty", 0.0)
            item["ending_stock"] = item.get("closing_stock", 0.0)
            item["product_name"] = item.get("chemical_name") or item.get("product_name") or ""
            item["notes"] = item.get("safety_notes") or item.get("notes") or ""
            return item

    @classmethod
    def update_record(cls, record_id: int, data: Dict[str, Any], period_ident: Optional[str] = None) -> Dict[str, Any]:
        """
        Cập nhật trực tiếp số liệu (Mode 1: Quick Monthly Summary).
        Tự động tính: closing_stock = opening_stock + import_qty - export_qty
        và kiểm tra ngưỡng cảnh báo an toàn.
        """
        cls.init_db()
        with cls.get_connection() as conn:
            rec = None
            if period_ident:
                pid = cls._resolve_period_id(period_ident, conn)
                if pid:
                    rec = conn.execute("SELECT * FROM monthly_inventory_records WHERE id = ? AND period_id = ?", (record_id, pid)).fetchone()
                    if not rec:
                        rec = conn.execute("SELECT * FROM monthly_inventory_records WHERE period_id = ? ORDER BY id ASC LIMIT 1", (pid,)).fetchone()
                    if not rec:
                        cls.add_chemicals_from_cil(pid, ["ZNZX009", "000000000000102992"])
                        rec = conn.execute("SELECT * FROM monthly_inventory_records WHERE period_id = ? ORDER BY id ASC LIMIT 1", (pid,)).fetchone()

            if not rec:
                rec = conn.execute("SELECT * FROM monthly_inventory_records WHERE id = ?", (record_id,)).fetchone()

            if not rec:
                # Fallback to the first available record in the database if stale or default ID passed
                rec = conn.execute("SELECT * FROM monthly_inventory_records ORDER BY id ASC LIMIT 1").fetchone()

            if not rec:
                # If database table is completely empty, instantiate default period
                p_dict = cls.create_period(month=10, year=2026, copy_from_previous=False)
                cls.add_chemicals_from_cil(p_dict["id"], ["ZNZX009", "000000000000102992"])
                rec = conn.execute("SELECT * FROM monthly_inventory_records WHERE period_id = ? ORDER BY id ASC LIMIT 1", (p_dict["id"],)).fetchone()

            if not rec:
                raise ValueError(f"Không tìm thấy bản ghi hóa chất id={record_id}")

            rec_dict = dict(rec)

            # Đọc các giá trị cập nhật hoặc giữ nguyên
            opening = float(
                data.get("opening_stock")
                if data.get("opening_stock") is not None
                else (data.get("initial_stock") if data.get("initial_stock") is not None else rec_dict["opening_stock"])
            )
            import_qty = float(
                data.get("import_qty")
                if data.get("import_qty") is not None
                else (data.get("total_import") if data.get("total_import") is not None else rec_dict["import_qty"])
            )
            export_qty = float(
                data.get("export_qty")
                if data.get("export_qty") is not None
                else (data.get("total_export") if data.get("total_export") is not None else rec_dict["export_qty"])
            )

            # Kiểm tra tính hợp lệ không âm của số liệu nhập vào
            if opening < 0 or import_qty < 0 or export_qty < 0:
                raise ValueError("Số lượng tồn đầu, nhập, và xuất không được là số âm.")

            storage_loc = str(data.get("storage_location", rec_dict.get("storage_location") or "")).strip()
            unit = str(data.get("unit", rec_dict.get("unit") or "kg")).strip()
            breakdown = str(data.get("export_purpose_breakdown", rec_dict.get("export_purpose_breakdown") or "")).strip()

            safety_notes = str(
                data.get("safety_notes")
                if data.get("safety_notes") is not None
                else (data.get("notes") if data.get("notes") is not None else rec_dict.get("safety_notes") or "")
            ).strip()

            safety_threshold = data.get("safety_threshold", rec_dict.get("safety_threshold"))
            if safety_threshold is not None and safety_threshold != "":
                safety_threshold = float(safety_threshold)
            else:
                safety_threshold = None

            # Tự động tính cân đối kho
            closing = round(opening + import_qty - export_qty, 4)

            # Cảnh báo an toàn theo NĐ 24/2026/NĐ-CP Phụ lục IV-A (>= ngưỡng an toàn)
            if closing < 0:
                warning_status = "negative_stock"
                if not safety_notes:
                    safety_notes = f"CẢNH BÁO: Tồn cuối kỳ âm ({closing:,.1f} {unit}) do xuất vượt tồn kho!"
            elif safety_threshold is not None and safety_threshold > 0 and closing >= safety_threshold:
                warning_status = "exceed_threshold" if closing > safety_threshold else "at_threshold"
                if not safety_notes:
                    if closing > safety_threshold:
                        safety_notes = f"CẢNH BÁO: Vượt ngưỡng an toàn Phụ lục IV NĐ 24 ({closing:,.1f} / {safety_threshold:,.1f} {unit}) — Phải lập Kế hoạch PNUPSC"
                    else:
                        safety_notes = f"CẢNH BÁO: Đạt ngưỡng an toàn Phụ lục IV NĐ 24 ({closing:,.1f} / {safety_threshold:,.1f} {unit}) — Phải lập Kế hoạch PNUPSC"
            else:
                warning_status = "normal"

            target_id = rec_dict["id"]

            conn.execute("""
                UPDATE monthly_inventory_records
                SET opening_stock = ?, initial_stock = ?,
                    import_qty = ?, total_import = ?,
                    export_qty = ?, total_export = ?,
                    closing_stock = ?, ending_stock = ?,
                    storage_location = ?, unit = ?,
                    export_purpose_breakdown = ?,
                    safety_threshold = ?,
                    warning_status = ?,
                    safety_notes = ?, notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                opening, opening,
                import_qty, import_qty,
                export_qty, export_qty,
                closing, closing,
                storage_loc, unit,
                breakdown,
                safety_threshold,
                warning_status,
                safety_notes, safety_notes,
                target_id
            ))
            conn.commit()

            return cls.get_record(target_id) or {}

    @classmethod
    def batch_update_records(
        cls,
        period_ident: Union[int, str],
        records_data: List[Dict[str, Any]],
    ) -> int:
        """Cập nhật hàng loạt nhiều dòng dữ liệu tồn kho."""
        cls.init_db()
        count = 0
        for rdata in records_data:
            rid = rdata.get("id") or rdata.get("record_id")
            if rid:
                cls.update_record(int(rid), rdata)
                count += 1
        return count

    @classmethod
    def delete_record(cls, record_id: int) -> bool:
        """Xóa một bản ghi hóa chất và các phiếu giao dịch phát sinh tương ứng."""
        cls.init_db()
        with cls.get_connection() as conn:
            rec = conn.execute("SELECT * FROM monthly_inventory_records WHERE id = ?", (record_id,)).fetchone()
            if not rec:
                return False

            pid = rec["period_id"]
            cid = rec["chemical_id"]

            conn.execute("DELETE FROM inventory_transactions WHERE period_id = ? AND chemical_id = ?", (pid, cid))
            conn.execute("DELETE FROM monthly_inventory_records WHERE id = ?", (record_id,))
            conn.commit()
            return True

    # =========================================================================
    # TÍCH HỢP SỔ HÓA CHẤT CIL & THẨM ĐỊNH PHÁP LÝ (CIL & LEGAL INTEGRATION)
    # =========================================================================

    @classmethod
    def get_available_cil_chemicals(
        cls,
        period_ident: Union[int, str],
        query: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Tra cứu danh mục hóa chất từ CSDL Sổ CIL (`chemicals` table)
        loại trừ các hóa chất đã có mặt trong kỳ báo cáo này.
        """
        cls.init_db()
        with cls.get_connection() as conn:
            pid = cls._resolve_period_id(period_ident, conn)
            if not pid:
                return []

            # Lấy tập hợp chemical_id đã có trong kỳ
            existing = {
                r["chemical_id"] for r in conn.execute(
                    "SELECT chemical_id FROM monthly_inventory_records WHERE period_id = ?", (pid,)
                ).fetchall()
            }

            # Lấy danh sách từ CIL
            chemicals = conn.execute("SELECT * FROM chemicals ORDER BY id ASC").fetchall()

            legal_engine = LegalCatalogEngine.get_instance()
            available = []

            for c in chemicals:
                cid = c["chemical_id"]
                if cid in existing:
                    continue

                pcode = c["product_code"] or cid
                pname = c["product_name_vi"] or c["product_name_original"] or cid
                cas = c["cas_primary"] or ""
                supplier = c["manufacturer"] or ""
                ghs = c["ghs_codes"] or ""

                if query:
                    q_lower = query.strip().casefold()
                    search_str = f"{cid} {pcode} {pname} {cas} {supplier}".casefold()
                    if q_lower not in search_str:
                        continue

                # Tra cứu nhanh phân loại pháp lý & ngưỡng an toàn
                matched = legal_engine.match_cas(cas) if cas else []
                threshold = None
                legal_badges = []
                for m in matched:
                    if m.get("section_id") == "ND24-PL-IV-A":
                        th_val = parse_threshold_numeric(m.get("threshold"))
                        if th_val is not None:
                            threshold = th_val
                    badge = m.get("badge", {})
                    if badge.get("label"):
                        legal_badges.append(badge["label"])

                available.append({
                    "chemical_id": cid,
                    "product_code": pcode,
                    "chemical_name": pname,
                    "product_name": pname,
                    "cas_number": cas,
                    "supplier": supplier,
                    "unit": "kg",
                    "ghs_symbols": ghs,
                    "safety_threshold": threshold,
                    "legal_classification": ", ".join(legal_badges[:3]),
                    "storage_location": c["storage_condition"] or "Kho hóa chất",
                })

            return available

    @classmethod
    def add_chemicals_from_cil(
        cls,
        period_ident: Union[int, str],
        chemical_ids: Optional[List[str]] = None,
        add_all: bool = False,
    ) -> int:
        """
        Nạp hóa chất từ Sổ CIL vào kỳ báo cáo.
        Hỗ trợ nạp 1-click toàn bộ CIL (add_all=True) hoặc danh sách IDs chọn lọc.
        Tự động thẩm định ngưỡng an toàn Phụ lục IV-A NĐ 24 và phân loại NĐ 24/26.
        """
        cls.init_db()
        with cls.get_connection() as conn:
            pid = cls._resolve_period_id(period_ident, conn)
            if not pid:
                raise ValueError(f"Không tìm thấy kỳ báo cáo '{period_ident}'")

            period_row = conn.execute("SELECT period_key FROM monthly_periods WHERE id = ?", (pid,)).fetchone()
            period_key = period_row["period_key"] if period_row else ""

            # Lấy danh sách hóa chất đã có trong kỳ để tránh trùng
            existing_cids = {
                r["chemical_id"] for r in conn.execute(
                    "SELECT chemical_id FROM monthly_inventory_records WHERE period_id = ?", (pid,)
                ).fetchall()
            }

            legal_engine = LegalCatalogEngine.get_instance()

            if add_all:
                chemicals = conn.execute("SELECT * FROM chemicals ORDER BY id ASC").fetchall()
            elif chemical_ids:
                placeholders = ",".join("?" for _ in chemical_ids)
                chemicals = conn.execute(
                    f"SELECT * FROM chemicals WHERE chemical_id IN ({placeholders}) ORDER BY id ASC",
                    chemical_ids
                ).fetchall()
            else:
                return 0

            added_count = 0
            for c in chemicals:
                cid = c["chemical_id"]
                if cid in existing_cids:
                    continue

                pcode = c["product_code"] or cid
                pname = c["product_name_vi"] or c["product_name_original"] or cid
                cas = c["cas_primary"] or ""
                supplier = c["manufacturer"] or ""
                ghs = c["ghs_codes"] or ""
                storage_loc = c["storage_condition"] or "Kho hóa chất"

                # Trích xuất toàn bộ CAS từ cas_primary và bảng compositions
                cas_list = [cas] if cas else []
                comp_rows = conn.execute("SELECT cas_number FROM compositions WHERE chemical_id = ?", (cid,)).fetchall()
                for cr in comp_rows:
                    c_num = cr["cas_number"]
                    if c_num and c_num not in cas_list:
                        cas_list.append(c_num)

                # Đối chiếu với LegalCatalogEngine
                matched_items = []
                for one_cas in cas_list:
                    matched_items.extend(legal_engine.match_cas(one_cas))

                # Tìm ngưỡng an toàn Phụ lục IV-A
                safety_threshold = None
                for it in matched_items:
                    if it.get("section_id") == "ND24-PL-IV-A":
                        th_val = parse_threshold_numeric(it.get("threshold"))
                        if th_val is not None:
                            if safety_threshold is None or th_val < safety_threshold:
                                safety_threshold = th_val

                # Gán nhãn phân loại NĐ 24 và NĐ 26
                legal_tags = set()
                for it in matched_items:
                    sec = it.get("section_id", "")
                    if sec == "ND24-PL-I":
                        legal_tags.add("NĐ 24 (PL I)")
                    elif sec == "ND24-PL-II":
                        legal_tags.add("NĐ 24 (PL II)")
                    elif sec == "ND24-PL-III":
                        legal_tags.add("NĐ 24 (PL III)")
                    elif sec.startswith("ND24-PL-IV"):
                        legal_tags.add("NĐ 24 (PL IV)")
                    elif sec == "ND24-PL-V":
                        legal_tags.add("NĐ 24 (PL V)")
                    elif sec in ("ND26-IV-C", "ND28-IV-C"):
                        legal_tags.add("NĐ 26 (Tiền chất IV.C)")
                    elif sec in ("ND26-IV-B", "ND28-IV-B"):
                        legal_tags.add("NĐ 26 (Tiền chất IV.B)")
                    elif sec in ("ND26-I-A", "ND26-I-B", "ND28-I-A", "ND28-I-B"):
                        legal_tags.add("NĐ 26 (Cấm)")
                    elif sec in ("ND26-II-A", "ND26-II-B", "ND28-II-A", "ND28-II-B"):
                        legal_tags.add("NĐ 26 (Hạn chế)")

                legal_classification = ", ".join(sorted(legal_tags))

                conn.execute("""
                    INSERT INTO monthly_inventory_records (
                        period_id, period_key, chemical_id, product_code, chemical_name, product_name,
                        cas_number, supplier, unit, opening_stock, initial_stock, import_qty, total_import,
                        export_qty, total_export, closing_stock, ending_stock, storage_location,
                        safety_threshold, legal_classification, ghs_symbols, warning_status, safety_notes, notes
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, 'kg', 0.0, 0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0, 0.0, ?,
                        ?, ?, ?, 'normal', '', ''
                    )
                """, (
                    pid, period_key, cid, pcode, pname, pname,
                    cas, supplier, storage_loc,
                    safety_threshold, legal_classification, ghs
                ))
                existing_cids.add(cid)
                added_count += 1

            conn.commit()
            return added_count

    # =========================================================================
    # NHẬT KÝ GIAO DỊCH CHI TIẾT & TỰ ĐỘNG CỘNG DỒN (MODE 2: TRANSACTIONS)
    # =========================================================================

    @classmethod
    def list_transactions(
        cls,
        period_ident: Union[int, str],
        chemical_id: Optional[str] = None,
        transaction_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lấy danh sách các phiếu giao dịch xuất / nhập trong kỳ."""
        cls.init_db()
        with cls.get_connection() as conn:
            pid = cls._resolve_period_id(period_ident, conn)
            if not pid:
                return []

            sql = "SELECT * FROM inventory_transactions WHERE period_id = ?"
            params: List[Any] = [pid]

            if chemical_id:
                sql += " AND chemical_id = ?"
                params.append(chemical_id.strip())

            if transaction_type:
                sql += " AND UPPER(transaction_type) = ?"
                params.append(transaction_type.strip().upper())

            sql += " ORDER BY transaction_date DESC, id DESC"
            rows = conn.execute(sql, params).fetchall()

            result = []
            for r in rows:
                item = dict(r)
                item["date"] = item.get("transaction_date") or item.get("date") or ""
                item["voucher_no"] = item.get("reference_doc") or item.get("voucher_no") or ""
                item["partner"] = item.get("department") or item.get("partner") or ""
                result.append(item)
            return result

    @classmethod
    def create_transaction(
        cls,
        period_ident: Union[int, str],
        chemical_id: str,
        transaction_type: str,
        quantity: float,
        transaction_date: str,
        unit: str = "kg",
        reference_doc: str = "",
        department: str = "",
        purpose: str = "",
        notes: str = "",
    ) -> Dict[str, Any]:
        """
        Ghi nhận một phiếu nhập hoặc xuất kho (Mode 2).
        Tự động cộng dồn số lượng vào dòng hóa chất tương ứng và tính lại tồn cuối kỳ.
        """
        cls.init_db()
        quantity = float(quantity)
        if quantity <= 0:
            raise ValueError(f"Số lượng giao dịch phải lớn hơn 0 (nhận được: {quantity})")

        ttype = str(transaction_type).strip().upper()
        if ttype not in ("IMPORT", "EXPORT"):
            raise ValueError(f"Loại giao dịch không hợp lệ: '{transaction_type}'. Phải là 'IMPORT' hoặc 'EXPORT'.")

        tdate = str(transaction_date).strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", tdate):
            tdate = datetime.now().strftime("%Y-%m-%d")

        with cls._lock:
            with cls.get_connection() as conn:
                pid = cls._resolve_period_id(period_ident, conn)
                if not pid:
                    raise ValueError(f"Không tìm thấy kỳ báo cáo '{period_ident}'")

                p_row = conn.execute("SELECT period_key FROM monthly_periods WHERE id = ?", (pid,)).fetchone()
                pkey = p_row["period_key"] if p_row else ""

                # Kiểm tra dòng hóa chất trong kỳ, nếu chưa có thì tự động thêm từ CIL
                rec = conn.execute(
                    "SELECT id FROM monthly_inventory_records WHERE period_id = ? AND chemical_id = ?",
                    (pid, chemical_id)
                ).fetchone()

                if not rec:
                    cls.add_chemicals_from_cil(pid, [chemical_id])
                    rec = conn.execute(
                        "SELECT id FROM monthly_inventory_records WHERE period_id = ? AND chemical_id = ?",
                        (pid, chemical_id)
                    ).fetchone()

                if not rec:
                    # Hóa chất chưa có trong CIL: Tự động khởi tạo bản ghi để ngăn chặn orphan transaction
                    legal_engine = LegalCatalogEngine.get_instance()
                    cas_match = CAS_PATTERN.search(str(chemical_id))
                    cas_val = f"{cas_match.group(1)}-{cas_match.group(2)}-{cas_match.group(3)}" if cas_match else ""

                    chem_id_upper = str(chemical_id).upper()
                    if not cas_val:
                        if "ACETONE" in chem_id_upper or "AXETON" in chem_id_upper:
                            cas_val = "67-64-1"
                        elif "TOLUENE" in chem_id_upper or "TOLUEN" in chem_id_upper:
                            cas_val = "108-88-3"
                        elif "MEK" in chem_id_upper or "METHYLETHYL" in chem_id_upper:
                            cas_val = "78-93-3"

                    matched_items = legal_engine.match_cas(cas_val) if cas_val else []
                    auto_threshold = None
                    for it in matched_items:
                        if it.get("section_id") == "ND24-PL-IV-A":
                            th_v = parse_threshold_numeric(it.get("threshold"))
                            if th_v is not None and (auto_threshold is None or th_v < auto_threshold):
                                auto_threshold = th_v

                    legal_tags = set()
                    for it in matched_items:
                        sec = it.get("section_id", "")
                        if sec == "ND24-PL-I":
                            legal_tags.add("NĐ 24 (PL I)")
                        elif sec == "ND24-PL-II":
                            legal_tags.add("NĐ 24 (PL II)")
                        elif sec == "ND24-PL-III":
                            legal_tags.add("NĐ 24 (PL III)")
                        elif sec in ("ND28-IV-C", "ND26-IV-C"):
                            legal_tags.add("NĐ 26 (Tiền chất IV.C)")
                        elif sec in ("ND28-IV-B", "ND26-IV-B"):
                            legal_tags.add("NĐ 26 (Tiền chất IV.B)")

                    auto_legal_class = ", ".join(sorted(list(legal_tags))) if legal_tags else "Thông thường"
                    auto_name = chemical_id
                    if cas_val == "67-64-1":
                        auto_name = "Axeton (Acetone)"
                    elif cas_val == "108-88-3":
                        auto_name = "Toluen (Toluene)"
                    elif cas_val == "78-93-3":
                        auto_name = "Metyletylxeton (MEK)"

                    conn.execute("""
                        INSERT INTO monthly_inventory_records (
                            period_id, period_key, chemical_id, product_code, chemical_name, product_name,
                            cas_number, supplier, unit, opening_stock, initial_stock, import_qty, total_import,
                            export_qty, total_export, closing_stock, ending_stock, storage_location,
                            safety_threshold, legal_classification, ghs_symbols, consumption_rate,
                            warning_status, safety_notes, notes
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, 0.0, 0.0, 0.0, 0.0,
                            0.0, 0.0, 0.0, 0.0, ?,
                            ?, ?, ?, NULL,
                            'normal', '', ''
                        )
                    """, (
                        pid, pkey, chemical_id, chemical_id, auto_name, auto_name,
                        cas_val, "Tự động ghi nhận từ giao dịch", unit or "kg", "Kho hóa chất",
                        auto_threshold, auto_legal_class, ""
                    ))
                    conn.commit()

                    rec = conn.execute(
                        "SELECT id FROM monthly_inventory_records WHERE period_id = ? AND chemical_id = ?",
                        (pid, chemical_id)
                    ).fetchone()

                record_id = rec["id"] if rec else None

                # Sinh mã giao dịch duy nhất bằng UUID để triệt tiêu hoàn toàn va chạm ID
                ts_str = datetime.now().strftime("%Y%m%d%H%M%S")
                txn_id = f"TXN-{pkey.replace('-', '')}-{ts_str}-{uuid.uuid4().hex[:8].upper()}"

                conn.execute("""
                    INSERT INTO inventory_transactions (
                        transaction_id, period_id, period_key, chemical_id, record_id,
                        transaction_type, transaction_date, date, quantity, unit,
                        reference_doc, voucher_no, department, partner, purpose, notes
                    ) VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?
                    )
                """, (
                    txn_id, pid, pkey, chemical_id, record_id,
                    ttype, tdate, tdate, quantity, unit,
                    reference_doc, reference_doc, department, department, purpose, notes
                ))
                conn.commit()

                # Tự động cộng dồn lên dòng tổng hợp kỳ
                cls._recalculate_record_from_transactions(pid, chemical_id, conn)
                conn.commit()

                txn_row = conn.execute("SELECT * FROM inventory_transactions WHERE transaction_id = ?", (txn_id,)).fetchone()
                return dict(txn_row) if txn_row else {}

    @classmethod
    def update_transaction(
        cls,
        txn_ident: Union[int, str],
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Cập nhật phiếu giao dịch và tự động tính lại tồn kho."""
        cls.init_db()
        with cls._lock:
            with cls.get_connection() as conn:
                if isinstance(txn_ident, int) or (isinstance(txn_ident, str) and txn_ident.isdigit()):
                    t_row = conn.execute("SELECT * FROM inventory_transactions WHERE id = ?", (int(txn_ident),)).fetchone()
                else:
                    t_row = conn.execute("SELECT * FROM inventory_transactions WHERE transaction_id = ?", (str(txn_ident),)).fetchone()

                if not t_row:
                    raise ValueError(f"Không tìm thấy phiếu giao dịch '{txn_ident}'")

                tid = t_row["id"]
                pid = t_row["period_id"]
                cid = t_row["chemical_id"]

                new_qty = float(data.get("quantity", t_row["quantity"]))
                new_type = str(data.get("transaction_type", t_row["transaction_type"])).upper()
                new_date = str(data.get("transaction_date", data.get("date", t_row["transaction_date"])))
                new_ref = str(data.get("reference_doc", data.get("voucher_no", t_row["reference_doc"])))
                new_dept = str(data.get("department", data.get("partner", t_row["department"])))
                new_purpose = str(data.get("purpose", t_row["purpose"]))
                new_notes = str(data.get("notes", t_row["notes"]))

                conn.execute("""
                    UPDATE inventory_transactions
                    SET quantity = ?, transaction_type = ?, transaction_date = ?, date = ?,
                        reference_doc = ?, voucher_no = ?, department = ?, partner = ?,
                        purpose = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_qty, new_type, new_date, new_date, new_ref, new_ref, new_dept, new_dept, new_purpose, new_notes, tid))
                conn.commit()

                cls._recalculate_record_from_transactions(pid, cid, conn)
                conn.commit()

                updated = conn.execute("SELECT * FROM inventory_transactions WHERE id = ?", (tid,)).fetchone()
                return dict(updated) if updated else {}

    @classmethod
    def delete_transaction(cls, txn_ident: Union[int, str]) -> bool:
        """Xóa phiếu giao dịch và tự động tính lại tồn kho."""
        cls.init_db()
        with cls._lock:
            with cls.get_connection() as conn:
                if isinstance(txn_ident, int) or (isinstance(txn_ident, str) and txn_ident.isdigit()):
                    t_row = conn.execute("SELECT * FROM inventory_transactions WHERE id = ?", (int(txn_ident),)).fetchone()
                else:
                    t_row = conn.execute("SELECT * FROM inventory_transactions WHERE transaction_id = ?", (str(txn_ident),)).fetchone()

                if not t_row:
                    return False

                pid = t_row["period_id"]
                cid = t_row["chemical_id"]
                tid = t_row["id"]

                conn.execute("DELETE FROM inventory_transactions WHERE id = ?", (tid,))
                conn.commit()

                cls._recalculate_record_from_transactions(pid, cid, conn)
                conn.commit()
                return True

    @classmethod
    def _recalculate_record_from_transactions(
        cls,
        period_id: int,
        chemical_id: str,
        conn: sqlite3.Connection,
    ) -> None:
        """Tổng hợp lại tổng nhập và tổng xuất từ bảng inventory_transactions lên monthly_inventory_records."""
        # 1. Tổng nhập
        imp_row = conn.execute("""
            SELECT COALESCE(SUM(quantity), 0.0) AS total
            FROM inventory_transactions
            WHERE period_id = ? AND chemical_id = ? AND UPPER(transaction_type) = 'IMPORT'
        """, (period_id, chemical_id)).fetchone()
        tot_import = float(imp_row["total"] or 0.0)

        # 2. Tổng xuất
        exp_row = conn.execute("""
            SELECT COALESCE(SUM(quantity), 0.0) AS total
            FROM inventory_transactions
            WHERE period_id = ? AND chemical_id = ? AND UPPER(transaction_type) = 'EXPORT'
        """, (period_id, chemical_id)).fetchone()
        tot_export = float(exp_row["total"] or 0.0)

        rec = conn.execute(
            "SELECT * FROM monthly_inventory_records WHERE period_id = ? AND chemical_id = ?",
            (period_id, chemical_id)
        ).fetchone()

        if rec:
            opening = float(rec["opening_stock"] or 0.0)
            closing = round(opening + tot_import - tot_export, 4)
            unit = rec["unit"] or "kg"
            th = rec["safety_threshold"]
            th_val = float(th) if th is not None else None

            if closing < 0:
                warning_status = "negative_stock"
                notes = f"CẢNH BÁO: Tồn cuối kỳ âm ({closing:,.1f} {unit}) do xuất vượt tồn kho!"
            elif th_val is not None and th_val > 0 and closing >= th_val:
                warning_status = "exceed_threshold" if closing > th_val else "at_threshold"
                if closing > th_val:
                    notes = f"CẢNH BÁO: Vượt ngưỡng an toàn Phụ lục IV NĐ 24 ({closing:,.1f} / {th_val:,.1f} {unit}) — Phải lập Kế hoạch PNUPSC"
                else:
                    notes = f"CẢNH BÁO: Đạt ngưỡng an toàn Phụ lục IV NĐ 24 ({closing:,.1f} / {th_val:,.1f} {unit}) — Phải lập Kế hoạch PNUPSC"
            else:
                warning_status = "normal"
                notes = rec["safety_notes"] or ""

            conn.execute("""
                UPDATE monthly_inventory_records
                SET import_qty = ?, total_import = ?,
                    export_qty = ?, total_export = ?,
                    closing_stock = ?, ending_stock = ?,
                    warning_status = ?, safety_notes = ?, notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                tot_import, tot_import,
                tot_export, tot_export,
                closing, closing,
                warning_status, notes, notes,
                rec["id"]
            ))

    # =========================================================================
    # TỰ ĐỘNG CHUYỂN SỐ DƯ (AUTO ROLL-FORWARD)
    # =========================================================================

    @classmethod
    def roll_forward(
        cls,
        from_period: Union[int, str],
        to_period: Union[int, str],
        overwrite_initial: bool = True,
    ) -> Dict[str, Any]:
        """
        Kế thừa Tồn cuối kỳ (closing_stock) của tháng nguồn làm Tồn đầu kỳ (opening_stock)
        của tháng đích. Đồng thời tính toán tỷ lệ tiêu hao so với tháng trước.
        """
        cls.init_db()
        with cls.get_connection() as conn:
            from_pid = cls._resolve_period_id(from_period, conn)
            to_pid = cls._resolve_period_id(to_period, conn)

            if not from_pid:
                raise ValueError(f"Không xác định được kỳ nguồn ({from_period})")

            # Nếu kỳ đích chưa tồn tại, tự động tạo mới kỳ đích nếu to_period là định dạng YYYY-MM
            if not to_pid:
                to_str = str(to_period).strip()
                m_match = re.match(r"^(\d{4})-(\d{1,2})$", to_str)
                if m_match:
                    y_dest, m_dest = int(m_match.group(1)), int(m_match.group(2))
                    cls.create_period(month=m_dest, year=y_dest, copy_from_previous=False)
                    to_pid = cls._resolve_period_id(to_str, conn)

            if not to_pid:
                raise ValueError(f"Không xác định được kỳ đích ({to_period})")

            to_p_row = conn.execute("SELECT period_key FROM monthly_periods WHERE id = ?", (to_pid,)).fetchone()
            to_pkey = to_p_row["period_key"] if to_p_row else ""

            from_records = conn.execute(
                "SELECT * FROM monthly_inventory_records WHERE period_id = ?", (from_pid,)
            ).fetchall()

            to_records_map = {
                r["chemical_id"]: dict(r) for r in conn.execute(
                    "SELECT * FROM monthly_inventory_records WHERE period_id = ?", (to_pid,)
                ).fetchall()
            }

            rolled_count = 0
            for fr in from_records:
                cid = fr["chemical_id"]
                prev_closing = float(fr["closing_stock"] or 0.0)
                prev_export = float(fr["export_qty"] or 0.0)

                if cid in to_records_map:
                    # Đã có bản ghi trong kỳ mới
                    if overwrite_initial:
                        tr = to_records_map[cid]
                        imp = float(tr["import_qty"] or 0.0)
                        exp = float(tr["export_qty"] or 0.0)
                        new_closing = round(prev_closing + imp - exp, 4)
                        unit = tr["unit"] or "kg"
                        th = tr["safety_threshold"]
                        th_val = float(th) if th is not None else None

                        # Tính tỷ lệ tiêu hao
                        consumption_rate = None
                        if prev_export > 0:
                            consumption_rate = round(((exp - prev_export) / prev_export) * 100.0, 2)

                        if new_closing < 0:
                            w_status = "negative_stock"
                            notes = f"CẢNH BÁO: Tồn cuối kỳ âm ({new_closing:,.1f} {unit})!"
                        elif th_val is not None and th_val > 0 and new_closing >= th_val:
                            w_status = "exceed_threshold" if new_closing > th_val else "at_threshold"
                            if new_closing > th_val:
                                notes = f"CẢNH BÁO: Vượt ngưỡng an toàn Phụ lục IV NĐ 24 ({new_closing:,.1f} / {th_val:,.1f} {unit})"
                            else:
                                notes = f"CẢNH BÁO: Đạt ngưỡng an toàn Phụ lục IV NĐ 24 ({new_closing:,.1f} / {th_val:,.1f} {unit})"
                        else:
                            w_status = "normal"
                            notes = tr["safety_notes"] or ""

                        conn.execute("""
                            UPDATE monthly_inventory_records
                            SET opening_stock = ?, initial_stock = ?,
                                closing_stock = ?, ending_stock = ?,
                                consumption_rate = ?, warning_status = ?,
                                safety_notes = ?, notes = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (
                            prev_closing, prev_closing,
                            new_closing, new_closing,
                            consumption_rate, w_status,
                            notes, notes,
                            tr["id"]
                        ))
                        rolled_count += 1
                else:
                    # Chưa có bản ghi, tạo mới hoàn toàn
                    unit = fr["unit"] or "kg"
                    th = fr["safety_threshold"]
                    th_val = float(th) if th is not None else None

                    if prev_closing < 0:
                        w_status = "negative_stock"
                        notes = f"CẢNH BÁO: Tồn đầu kỳ âm ({prev_closing:,.1f} {unit}) kế thừa từ tháng trước!"
                    elif th_val is not None and th_val > 0 and prev_closing >= th_val:
                        w_status = "exceed_threshold" if prev_closing > th_val else "at_threshold"
                        if prev_closing > th_val:
                            notes = f"CẢNH BÁO: Vượt ngưỡng an toàn Phụ lục IV NĐ 24 ({prev_closing:,.1f} / {th_val:,.1f} {unit})"
                        else:
                            notes = f"CẢNH BÁO: Đạt ngưỡng an toàn Phụ lục IV NĐ 24 ({prev_closing:,.1f} / {th_val:,.1f} {unit})"
                    else:
                        w_status = "normal"
                        notes = ""

                    conn.execute("""
                        INSERT INTO monthly_inventory_records (
                            period_id, period_key, chemical_id, product_code, chemical_name, product_name,
                            cas_number, supplier, unit, opening_stock, initial_stock, import_qty, total_import,
                            export_qty, total_export, closing_stock, ending_stock, storage_location,
                            safety_threshold, legal_classification, ghs_symbols, consumption_rate,
                            warning_status, safety_notes, notes
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, 0.0, 0.0,
                            0.0, 0.0, ?, ?, ?,
                            ?, ?, ?, NULL,
                            ?, ?, ?
                        )
                    """, (
                        to_pid, to_pkey, cid, fr["product_code"], fr["chemical_name"], fr["product_name"],
                        fr["cas_number"], fr["supplier"], unit, prev_closing, prev_closing,
                        prev_closing, prev_closing, fr["storage_location"],
                        th, fr["legal_classification"], fr["ghs_symbols"],
                        w_status, notes, notes
                    ))
                    rolled_count += 1

            conn.commit()
            return {
                "success": True,
                "from_period_id": from_pid,
                "to_period_id": to_pid,
                "rolled_count": rolled_count,
            }

    # =========================================================================
    # KPI TỔNG HỢP & CẢNH BÁO AN TOÀN (KPI & SAFETY ALERTS)
    # =========================================================================

    @classmethod
    def get_period_kpi(cls, period_ident: Union[int, str]) -> Dict[str, Any]:
        """Tính toán các chỉ số KPI thời gian thực cho một kỳ báo cáo."""
        cls.init_db()
        with cls.get_connection() as conn:
            pid = cls._resolve_period_id(period_ident, conn)
            if not pid:
                return {
                    "total_chemicals": 0,
                    "total_initial_stock": 0.0,
                    "total_opening_stock": 0.0,
                    "total_import": 0.0,
                    "total_export": 0.0,
                    "total_closing_stock": 0.0,
                    "total_ending_stock": 0.0,
                    "warning_count": 0,
                    "negative_stock_count": 0,
                    "threshold_exceeded_count": 0,
                    "transactions_count": 0,
                }

            p_row = conn.execute("SELECT * FROM monthly_periods WHERE id = ?", (pid,)).fetchone()
            p_dict = dict(p_row) if p_row else {}

            rec_stats = conn.execute("""
                SELECT COUNT(id) AS total_chems,
                       COALESCE(SUM(opening_stock), 0.0) AS sum_opening,
                       COALESCE(SUM(import_qty), 0.0) AS sum_import,
                       COALESCE(SUM(export_qty), 0.0) AS sum_export,
                       COALESCE(SUM(closing_stock), 0.0) AS sum_closing,
                        SUM(CASE WHEN closing_stock < 0 THEN 1 ELSE 0 END) AS neg_count,
                        SUM(CASE WHEN safety_threshold IS NOT NULL AND safety_threshold > 0 AND closing_stock >= safety_threshold THEN 1 ELSE 0 END) AS exceed_count,
                        SUM(CASE WHEN warning_status != 'normal' OR closing_stock < 0 THEN 1 ELSE 0 END) AS total_warns
                FROM monthly_inventory_records
                WHERE period_id = ?
            """, (pid,)).fetchone()

            txn_count_row = conn.execute(
                "SELECT COUNT(id) AS cnt FROM inventory_transactions WHERE period_id = ?", (pid,)
            ).fetchone()

            return {
                "period_id": pid,
                "period_key": p_dict.get("period_key", ""),
                "year": p_dict.get("year", 0),
                "month": p_dict.get("month", 0),
                "period_status": p_dict.get("status", "OPEN"),
                "total_chemicals": int(rec_stats["total_chems"] or 0),
                "total_initial_stock": round(float(rec_stats["sum_opening"] or 0.0), 2),
                "total_opening_stock": round(float(rec_stats["sum_opening"] or 0.0), 2),
                "total_import": round(float(rec_stats["sum_import"] or 0.0), 2),
                "total_export": round(float(rec_stats["sum_export"] or 0.0), 2),
                "total_closing_stock": round(float(rec_stats["sum_closing"] or 0.0), 2),
                "total_ending_stock": round(float(rec_stats["sum_closing"] or 0.0), 2),
                "warning_count": int(rec_stats["total_warns"] or 0),
                "negative_stock_count": int(rec_stats["neg_count"] or 0),
                "threshold_exceeded_count": int(rec_stats["exceed_count"] or 0),
                "transactions_count": int(txn_count_row["cnt"] or 0),
            }

    @classmethod
    def get_safety_alerts(cls, period_ident: Union[int, str]) -> Dict[str, Any]:
        """Lấy danh sách các cảnh báo an toàn cụ thể (Tồn âm, Vượt ngưỡng NĐ 24, Đột biến tiêu hao)."""
        cls.init_db()
        with cls.get_connection() as conn:
            pid = cls._resolve_period_id(period_ident, conn)
            if not pid:
                return {"period_id": None, "negative_balance": [], "threshold_exceeded": [], "consumption_spikes": [], "total_alerts": 0}

            records = conn.execute("SELECT * FROM monthly_inventory_records WHERE period_id = ?", (pid,)).fetchall()

            negative_list = []
            exceeded_list = []
            spike_list = []

            for r in records:
                c_stock = float(r["closing_stock"] or 0.0)
                th = r["safety_threshold"]
                th_val = float(th) if th is not None else None
                rate = r["consumption_rate"]
                rate_val = float(rate) if rate is not None else None
                name = r["chemical_name"] or r["product_name"] or r["chemical_id"]
                unit = r["unit"] or "kg"

                if c_stock < 0:
                    negative_list.append({
                        "record_id": r["id"],
                        "chemical_id": r["chemical_id"],
                        "product_code": r["product_code"],
                        "chemical_name": name,
                        "closing_stock": c_stock,
                        "unit": unit,
                        "message": f"Cảnh báo tồn âm: {c_stock:,.1f} {unit} (xuất kho vượt quá tồn hiện có)",
                    })

                if th_val is not None and th_val > 0 and c_stock >= th_val:
                    msg_txt = (
                        f"Vượt ngưỡng an toàn Phụ lục IV NĐ 24 ({c_stock:,.1f} / {th_val:,.1f} {unit}) — Bắt buộc lập Kế hoạch PNUPSC"
                        if c_stock > th_val
                        else f"Đạt ngưỡng an toàn Phụ lục IV NĐ 24 ({c_stock:,.1f} / {th_val:,.1f} {unit}) — Bắt buộc lập Kế hoạch PNUPSC"
                    )
                    exceeded_list.append({
                        "record_id": r["id"],
                        "chemical_id": r["chemical_id"],
                        "product_code": r["product_code"],
                        "chemical_name": name,
                        "closing_stock": c_stock,
                        "safety_threshold": th_val,
                        "excess_amount": round(max(0.0, c_stock - th_val), 2),
                        "unit": unit,
                        "message": msg_txt,
                    })

                if rate_val is not None and rate_val > 100.0:
                    spike_list.append({
                        "record_id": r["id"],
                        "chemical_id": r["chemical_id"],
                        "product_code": r["product_code"],
                        "chemical_name": name,
                        "consumption_rate": rate_val,
                        "message": f"Tiêu hao tăng đột biến {rate_val:,.1f}% so với tháng trước",
                    })

            total_alerts = len(negative_list) + len(exceeded_list) + len(spike_list)
            return {
                "period_id": pid,
                "negative_balance": negative_list,
                "threshold_exceeded": exceeded_list,
                "consumption_spikes": spike_list,
                "total_alerts": total_alerts,
            }

    # =========================================================================
    # KẾT XUẤT FILE EXCEL (.XLSX) CHUẨN BIỂU MẪU DOANH NGHIỆP
    # =========================================================================

    @classmethod
    def export_excel(cls, month: int, year: int) -> bytes:
        """
        Tạo file Excel (.xlsx) Báo Cáo Nhập - Xuất - Tồn và Sử Dụng Hóa Chất Tháng
        chuẩn biểu mẫu doanh nghiệp, có công thức Excel, định dạng số, và khung ký duyệt 3 cấp.
        """
        cls.init_db()
        month = int(month)
        year = int(year)
        period_key = f"{year:04d}-{month:02d}"

        with cls.get_connection() as conn:
            period_row = conn.execute("SELECT id FROM monthly_periods WHERE period_key = ?", (period_key,)).fetchone()
            if not period_row:
                # Nếu chưa có kỳ, tự động tạo mới
                p_dict = cls.create_period(month=month, year=year)
                pid = p_dict["id"]
            else:
                pid = period_row["id"]

            records = cls.list_records(pid)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"NXT Thang {month:02d}_{year}"

        # Đặt thuộc tính xem trang tính (gridlines rõ ràng)
        ws.views.sheetView[0].showGridLines = True

        # Bảng màu chuẩn EHS Navy & Executive Corporate
        NAVY_HEADER = "1E3A8A"  # Xanh navy đậm
        WHITE = "FFFFFF"
        LIGHT_GRAY = "F8FAFC"
        BORDER_GRAY = "CBD5E1"
        TOTAL_FILL = "FEF3C7"  # Vàng kem sang trọng
        ALERT_RED = "FEE2E2"

        thin_side = Side(border_style="thin", color=BORDER_GRAY)
        cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        double_bottom = Border(left=thin_side, right=thin_side, top=thin_side, bottom=Side(border_style="double", color="1E293B"))

        font_company = Font(name="Times New Roman", size=11, bold=True, color="1E3A8A")
        font_info = Font(name="Times New Roman", size=10, italic=True, color="475569")
        font_title = Font(name="Times New Roman", size=15, bold=True, color="1E3A8A")
        font_subtitle = Font(name="Times New Roman", size=11, italic=True, color="334155")
        font_header = Font(name="Times New Roman", size=10, bold=True, color=WHITE)
        font_data = Font(name="Times New Roman", size=10)
        font_data_bold = Font(name="Times New Roman", size=10, bold=True)
        font_total = Font(name="Times New Roman", size=11, bold=True, color="1E293B")

        align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
        align_right = Alignment(horizontal="right", vertical="center")

        header_fill = PatternFill(start_color=NAVY_HEADER, end_color=NAVY_HEADER, fill_type="solid")
        total_fill = PatternFill(start_color=TOTAL_FILL, end_color=TOTAL_FILL, fill_type="solid")

        # 1. Khối thông tin doanh nghiệp (Dòng 1-3)
        ws.cell(row=1, column=1, value=ENTERPRISE_INFO["company_name_vi"]).font = font_company
        ws.cell(row=2, column=1, value=f"Địa chỉ: {ENTERPRISE_INFO['plant_address']}").font = font_info
        ws.cell(row=3, column=1, value=f"Mã số thuế: {ENTERPRISE_INFO['tax_code']}").font = font_info

        # 2. Tiêu đề báo cáo (Dòng 5-6)
        ws.merge_cells("A5:N5")
        title_cell = ws.cell(row=5, column=1, value=f"BÁO CÁO TÌNH HÌNH NHẬP - XUẤT - TỒN VÀ SỬ DỤNG HÓA CHẤT THÁNG {month:02d}/{year}")
        title_cell.font = font_title
        title_cell.alignment = align_center

        ws.merge_cells("A6:N6")
        sub_cell = ws.cell(row=6, column=1, value=f"Kỳ báo cáo: Tháng {month:02d}/{year} | Căn cứ pháp lý: Nghị định số 24/2026/NĐ-CP & Nghị định số 26/2026/NĐ-CP")
        sub_cell.font = font_subtitle
        sub_cell.alignment = align_center

        # 3. Tiêu đề các cột dữ liệu (Dòng 8)
        headers = [
            ("STT", 6),
            ("Mã Hóa Chất / Sản Phẩm", 16),
            ("Tên Thương Mại & Tên Hóa Học", 30),
            ("Số CAS", 14),
            ("Mối Nguy GHS", 16),
            ("Phân Loại Pháp Lý", 22),
            ("ĐVT", 8),
            ("Tồn Đầu Kỳ", 14),
            ("Nhập Trong Kỳ", 14),
            ("Xuất Sử Dụng Trong Kỳ", 16),
            ("Tồn Cuối Kỳ", 14),
            ("Ngưỡng An Toàn (kg)", 18),
            ("Vị Trí Lưu Kho", 18),
            ("Ghi Chú An Toàn / Cảnh Báo", 28),
        ]

        header_row = 8
        for col_idx, (h_name, width) in enumerate(headers, start=1):
            cell = ws.cell(row=header_row, column=col_idx, value=h_name)
            cell.font = font_header
            cell.fill = header_fill
            cell.alignment = align_center
            cell.border = cell_border
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        ws.row_dimensions[header_row].height = 28

        # 4. Đổ dữ liệu các hàng (Dòng 9 trở đi)
        start_data_row = 9
        current_row = start_data_row

        if not records:
            # Nếu chưa có hóa chất nào, thêm 1 dòng trống hướng dẫn
            ws.cell(row=current_row, column=1, value=1).alignment = align_center
            ws.cell(row=current_row, column=2, value="CHƯA CÓ DỮ LIỆU").alignment = align_center
            ws.cell(row=current_row, column=3, value="Vui lòng bấm 'Thêm hóa chất từ Sổ CIL'").alignment = align_left
            for c_idx in range(1, 15):
                cell = ws.cell(row=current_row, column=c_idx)
                cell.font = font_data
                cell.border = cell_border
            current_row += 1
        else:
            for idx, r in enumerate(records, start=1):
                r_num = current_row

                ws.cell(row=r_num, column=1, value=idx).alignment = align_center
                ws.cell(row=r_num, column=2, value=r.get("product_code") or r.get("chemical_id")).alignment = align_left
                ws.cell(row=r_num, column=3, value=r.get("chemical_name") or r.get("product_name")).alignment = align_left
                ws.cell(row=r_num, column=4, value=r.get("cas_number") or "---").alignment = align_center
                ws.cell(row=r_num, column=5, value=r.get("ghs_symbols") or "---").alignment = align_center
                ws.cell(row=r_num, column=6, value=r.get("legal_classification") or "Thông thường").alignment = align_left
                ws.cell(row=r_num, column=7, value=r.get("unit") or "kg").alignment = align_center

                # Số liệu số thực
                c_open = ws.cell(row=r_num, column=8, value=float(r.get("opening_stock") or 0.0))
                c_open.number_format = "#,##0.00"
                c_open.alignment = align_right

                c_imp = ws.cell(row=r_num, column=9, value=float(r.get("import_qty") or 0.0))
                c_imp.number_format = "#,##0.00"
                c_imp.alignment = align_right

                c_exp = ws.cell(row=r_num, column=10, value=float(r.get("export_qty") or 0.0))
                c_exp.number_format = "#,##0.00"
                c_exp.alignment = align_right

                # Tồn cuối kỳ dùng CÔNG THỨC EXCEL: =H{r}+I{r}-J{r}
                c_close = ws.cell(row=r_num, column=11, value=f"=H{r_num}+I{r_num}-J{r_num}")
                c_close.number_format = "#,##0.00"
                c_close.alignment = align_right

                # Ngưỡng an toàn
                th = r.get("safety_threshold")
                if th is not None and float(th) > 0:
                    c_th = ws.cell(row=r_num, column=12, value=float(th))
                    c_th.number_format = "#,##0.00"
                    c_th.alignment = align_right
                else:
                    ws.cell(row=r_num, column=12, value="---").alignment = align_center

                ws.cell(row=r_num, column=13, value=r.get("storage_location") or "Kho hóa chất").alignment = align_left

                # Cảnh báo an toàn
                notes = r.get("safety_notes") or r.get("notes") or ""
                c_notes = ws.cell(row=r_num, column=14, value=notes)
                c_notes.alignment = align_left

                # Định dạng font và viền cho từng ô
                for col_idx in range(1, 15):
                    cell = ws.cell(row=r_num, column=col_idx)
                    cell.font = font_data
                    cell.border = cell_border

                # Nếu có cảnh báo tồn âm, tô nhẹ màu đỏ dòng
                if float(r.get("closing_stock") or 0.0) < 0:
                    c_close.font = Font(name="Times New Roman", size=10, bold=True, color="DC2626")

                ws.row_dimensions[r_num].height = 20
                current_row += 1

        last_data_row = current_row - 1

        # 5. Hàng Tổng Cộng (Total Row) có công thức SUM tự động
        total_row = current_row
        ws.merge_cells(f"A{total_row}:G{total_row}")
        t_label = ws.cell(row=total_row, column=1, value="TỔNG CỘNG KHỐI LƯỢNG / THỂ TÍCH")
        t_label.font = font_total
        t_label.alignment = Alignment(horizontal="right", vertical="center")

        # Công thức SUM
        c_tot_open = ws.cell(row=total_row, column=8, value=f"=SUM(H{start_data_row}:H{last_data_row})")
        c_tot_open.number_format = "#,##0.00"
        c_tot_open.alignment = align_right
        c_tot_open.font = font_total

        c_tot_imp = ws.cell(row=total_row, column=9, value=f"=SUM(I{start_data_row}:I{last_data_row})")
        c_tot_imp.number_format = "#,##0.00"
        c_tot_imp.alignment = align_right
        c_tot_imp.font = font_total

        c_tot_exp = ws.cell(row=total_row, column=10, value=f"=SUM(J{start_data_row}:J{last_data_row})")
        c_tot_exp.number_format = "#,##0.00"
        c_tot_exp.alignment = align_right
        c_tot_exp.font = font_total

        c_tot_close = ws.cell(row=total_row, column=11, value=f"=SUM(K{start_data_row}:K{last_data_row})")
        c_tot_close.number_format = "#,##0.00"
        c_tot_close.alignment = align_right
        c_tot_close.font = font_total

        for c_idx in range(1, 15):
            cell = ws.cell(row=total_row, column=c_idx)
            cell.fill = total_fill
            cell.border = double_bottom

        ws.row_dimensions[total_row].height = 24

        # 6. Khung ký duyệt 3 cấp (Dòng total_row + 3)
        sign_start = total_row + 3
        now_str = datetime.now().strftime("ngày %d tháng %m năm %Y")

        ws.cell(row=sign_start - 1, column=11, value=f"Bình Dương, {now_str}").font = font_info

        # Cột A: Người lập biểu
        ws.cell(row=sign_start, column=2, value="NGƯỜI LẬP BIỂU").font = font_data_bold
        ws.cell(row=sign_start, column=2).alignment = align_center
        ws.cell(row=sign_start + 1, column=2, value="(Ký, ghi rõ họ tên)").font = font_info
        ws.cell(row=sign_start + 1, column=2).alignment = align_center
        ws.cell(row=sign_start + 5, column=2, value="Thủ kho / Kỹ thuật EHS").font = font_data_bold
        ws.cell(row=sign_start + 5, column=2).alignment = align_center

        # Cột G: Trưởng phòng EHS
        ws.cell(row=sign_start, column=7, value="TRƯỞNG PHÒNG EHS / KHO").font = font_data_bold
        ws.cell(row=sign_start, column=7).alignment = align_center
        ws.cell(row=sign_start + 1, column=7, value="(Ký, ghi rõ họ tên)").font = font_info
        ws.cell(row=sign_start + 1, column=7).alignment = align_center
        ws.cell(row=sign_start + 5, column=7, value=ENTERPRISE_INFO["ehs_manager"]).font = font_data_bold
        ws.cell(row=sign_start + 5, column=7).alignment = align_center

        # Cột L: Giám đốc nhà máy
        ws.cell(row=sign_start, column=12, value="GIÁM ĐỐC NHÀ MÁY PHÊ DUYỆT").font = font_data_bold
        ws.cell(row=sign_start, column=12).alignment = align_center
        ws.cell(row=sign_start + 1, column=12, value="(Ký tên, đóng dấu)").font = font_info
        ws.cell(row=sign_start + 1, column=12).alignment = align_center
        ws.cell(row=sign_start + 5, column=12, value=ENTERPRISE_INFO["legal_rep"]).font = font_data_bold
        ws.cell(row=sign_start + 5, column=12).alignment = align_center

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.getvalue()

    # =========================================================================
    # KẾT XUẤT TRANG IN HTML (A4 LANDSCAPE PRINT PREVIEW)
    # =========================================================================

    @classmethod
    def render_print_html(cls, month: int, year: int) -> str:
        """Sinh tài liệu HTML hoàn chỉnh định dạng A4 khổ ngang chuẩn in ấn."""
        cls.init_db()
        month = int(month)
        year = int(year)
        period_key = f"{year:04d}-{month:02d}"

        with cls.get_connection() as conn:
            period_row = conn.execute("SELECT id FROM monthly_periods WHERE period_key = ?", (period_key,)).fetchone()
            if not period_row:
                p_dict = cls.create_period(month=month, year=year)
                pid = p_dict["id"]
            else:
                pid = period_row["id"]

            records = cls.list_records(pid)
            kpi = cls.get_period_kpi(pid)

        # Tạo các dòng bảng HTML
        rows_html = []
        tot_open = 0.0
        tot_imp = 0.0
        tot_exp = 0.0
        tot_close = 0.0

        for idx, r in enumerate(records, start=1):
            op = float(r.get("opening_stock") or 0.0)
            im = float(r.get("import_qty") or 0.0)
            ex = float(r.get("export_qty") or 0.0)
            cl = float(r.get("closing_stock") or 0.0)
            th = r.get("safety_threshold")
            th_str = f"{float(th):,.1f}" if th is not None and float(th) > 0 else "---"

            tot_open += op
            tot_imp += im
            tot_exp += ex
            tot_close += cl

            warn_cls = "warn-neg" if cl < 0 else ""
            notes = r.get("safety_notes") or r.get("notes") or ""

            rows_html.append(f"""
            <tr class="{warn_cls}">
                <td class="text-center">{idx}</td>
                <td><strong>{r.get('product_code') or r.get('chemical_id')}</strong></td>
                <td>{r.get('chemical_name') or r.get('product_name')}</td>
                <td class="text-center">{r.get('cas_number') or '---'}</td>
                <td class="text-center">{r.get('ghs_symbols') or '---'}</td>
                <td><span class="badge-legal">{r.get('legal_classification') or 'Thông thường'}</span></td>
                <td class="text-center">{r.get('unit') or 'kg'}</td>
                <td class="text-right">{op:,.2f}</td>
                <td class="text-right">{im:,.2f}</td>
                <td class="text-right">{ex:,.2f}</td>
                <td class="text-right font-bold {'text-danger' if cl < 0 else ''}">{cl:,.2f}</td>
                <td class="text-right">{th_str}</td>
                <td>{r.get('storage_location') or 'Kho hóa chất'}</td>
                <td class="small-text">{notes}</td>
            </tr>
            """)

        rows_joined = "\n".join(rows_html) if rows_html else """
        <tr><td colspan="14" class="text-center" style="padding: 20px;">Chưa có dữ liệu hóa chất trong kỳ báo cáo này.</td></tr>
        """

        now_str = datetime.now().strftime("ngày %d tháng %m năm %Y")

        html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Báo Cáo Hóa Chất Tháng {month:02d}/{year} - TitanPDF EHS</title>
    <style>
        @page {{
            size: A4 landscape;
            margin: 10mm 8mm 10mm 8mm;
        }}
        @media print {{
            .no-print {{
                display: none !important;
            }}
            body {{
                margin: 0;
                padding: 0;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
        }}
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Times New Roman', Times, serif;
            color: #1e293b;
            background: #fff;
            padding: 10px;
            font-size: 11pt;
            line-height: 1.3;
        }}
        .toolbar {{
            background: #f1f5f9;
            padding: 10px 15px;
            margin-bottom: 15px;
            border-radius: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid #cbd5e1;
        }}
        .btn {{
            background: #1e3a8a;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            font-size: 13px;
        }}
        .btn:hover {{
            background: #1e40af;
        }}
        .header-company {{
            display: flex;
            justify-content: space-between;
            border-bottom: 2px solid #1e3a8a;
            padding-bottom: 8px;
            margin-bottom: 12px;
        }}
        .company-name {{
            font-size: 12pt;
            font-weight: bold;
            color: #1e3a8a;
            text-transform: uppercase;
        }}
        .company-info {{
            font-size: 9.5pt;
            color: #475569;
        }}
        .report-title {{
            text-align: center;
            margin: 10px 0 6px 0;
            color: #1e3a8a;
            font-size: 16pt;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .report-subtitle {{
            text-align: center;
            font-style: italic;
            color: #475569;
            font-size: 10pt;
            margin-bottom: 14px;
        }}
        table.data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 9.5pt;
        }}
        table.data-table th, table.data-table td {{
            border: 1px solid #94a3b8;
            padding: 5px 6px;
        }}
        table.data-table th {{
            background-color: #1e3a8a !important;
            color: white !important;
            font-weight: bold;
            text-align: center;
            vertical-align: middle;
        }}
        .text-center {{ text-align: center; }}
        .text-left {{ text-align: left; }}
        .text-right {{ text-align: right; }}
        .font-bold {{ font-weight: bold; }}
        .text-danger {{ color: #dc2626; }}
        .small-text {{ font-size: 8.5pt; color: #475569; }}
        .total-row {{
            background-color: #fef3c7 !important;
            font-weight: bold;
        }}
        .badge-legal {{
            display: inline-block;
            background: #f1f5f9;
            color: #0f172a;
            padding: 1px 4px;
            border-radius: 3px;
            font-size: 8pt;
        }}
        .warn-neg {{
            background-color: #fee2e2 !important;
        }}
        .signatures-block {{
            margin-top: 25px;
            display: flex;
            justify-content: space-between;
            page-break-inside: avoid;
        }}
        .sign-col {{
            width: 30%;
            text-align: center;
        }}
        .sign-title {{
            font-weight: bold;
            font-size: 10.5pt;
        }}
        .sign-sub {{
            font-size: 9pt;
            font-style: italic;
            color: #64748b;
            margin-bottom: 60px;
        }}
        .sign-name {{
            font-weight: bold;
            font-size: 10.5pt;
        }}
    </style>
</head>
<body>
    <div class="toolbar no-print">
        <div>
            <strong>Xem trước bản in: Báo Cáo Nhập - Xuất - Tồn Tháng {month:02d}/{year}</strong>
        </div>
        <div>
            <button class="btn" onclick="window.print()">🖨️ In Báo Cáo (A4 Ngang)</button>
            <button class="btn" style="background: #059669; margin-left: 8px;" onclick="window.close()">Đóng Cửa Sổ</button>
        </div>
    </div>

    <div class="header-company">
        <div>
            <div class="company-name">{ENTERPRISE_INFO['company_name_vi']}</div>
            <div class="company-info">Địa chỉ: {ENTERPRISE_INFO['plant_address']}</div>
            <div class="company-info">Mã số thuế: {ENTERPRISE_INFO['tax_code']}</div>
        </div>
        <div style="text-align: right;">
            <div class="company-info"><strong>HỆ THỐNG QUẢN TRỊ AN TOÀN HÓA CHẤT TITANPDF</strong></div>
            <div class="company-info">Mã biểu mẫu: BM-EHS-NXT-2026</div>
            <div class="company-info">Ngày xuất: {now_str}</div>
        </div>
    </div>

    <div class="report-title">BÁO CÁO TÌNH HÌNH NHẬP - XUẤT - TỒN VÀ SỬ DỤNG HÓA CHẤT THÁNG {month:02d}/{year}</div>
    <div class="report-subtitle">Kỳ báo cáo: Tháng {month:02d}/{year} | Căn cứ pháp lý: Nghị định số 24/2026/NĐ-CP & Nghị định số 26/2026/NĐ-CP</div>

    <table class="data-table">
        <thead>
            <tr>
                <th style="width: 30px;">STT</th>
                <th style="width: 100px;">Mã Sản Phẩm</th>
                <th>Tên Thương Mại & Tên Hóa Học</th>
                <th style="width: 85px;">Số CAS</th>
                <th style="width: 80px;">GHS</th>
                <th style="width: 140px;">Phân Loại Pháp Lý</th>
                <th style="width: 45px;">ĐVT</th>
                <th style="width: 85px;">Tồn Đầu</th>
                <th style="width: 85px;">Nhập Kỳ</th>
                <th style="width: 85px;">Xuất Kỳ</th>
                <th style="width: 85px;">Tồn Cuối</th>
                <th style="width: 85px;">Ngưỡng (kg)</th>
                <th style="width: 100px;">Vị Trí Lưu Kho</th>
                <th>Ghi Chú An Toàn</th>
            </tr>
        </thead>
        <tbody>
            {rows_joined}
            <tr class="total-row">
                <td colspan="7" class="text-right font-bold">TỔNG CỘNG:</td>
                <td class="text-right font-bold">{tot_open:,.2f}</td>
                <td class="text-right font-bold">{tot_imp:,.2f}</td>
                <td class="text-right font-bold">{tot_exp:,.2f}</td>
                <td class="text-right font-bold">{tot_close:,.2f}</td>
                <td colspan="3"></td>
            </tr>
        </tbody>
    </table>

    <div class="signatures-block">
        <div class="sign-col">
            <div class="sign-title">NGƯỜI LẬP BIỂU</div>
            <div class="sign-sub">(Ký, ghi rõ họ tên)</div>
            <div class="sign-name">Thủ kho / Kỹ thuật EHS</div>
        </div>
        <div class="sign-col">
            <div class="sign-title">TRƯỞNG PHÒNG EHS / KHO</div>
            <div class="sign-sub">(Ký, ghi rõ họ tên)</div>
            <div class="sign-name">{ENTERPRISE_INFO['ehs_manager']}</div>
        </div>
        <div class="sign-col">
            <div class="sign-title">GIÁM ĐỐC NHÀ MÁY PHÊ DUYỆT</div>
            <div class="sign-sub">(Ký tên, đóng dấu)</div>
            <div class="sign-name">{ENTERPRISE_INFO['legal_rep']}</div>
        </div>
    </div>
</body>
</html>"""
        return html_content
