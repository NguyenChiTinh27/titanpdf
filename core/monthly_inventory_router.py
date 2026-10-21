"""
core/monthly_inventory_router.py
─────────────────────────────────
FASTAPI REST API ROUTER CHO PHÂN HỆ QUẢN LÝ NHẬP - XUẤT - TỒN HÓA CHẤT (NXT)

Được gắn kết vào server.py với các tiền tố:
- /api/monthly-inventory
- /api/msds/monthly-report

Tuân thủ chuẩn hóa 100% Khung pháp lý hiện hành:
- Luật Hóa chất số 69/2025/QH15
- Nghị định 24/2026/NĐ-CP (Phụ lục I, II, III, IV Bảng A & B, V)
- Nghị định 26/2026/NĐ-CP (Quản lý chất ma túy & Tiền chất công nghiệp Danh mục IV.C BCT)
- Thông tư 01/2026/TT-BCT & Thông tư 02/2026/TT-BCT
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Body, Depends, File, Form, Header, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from core.auth_rbac import require_owner
from core.monthly_inventory_engine import MonthlyInventoryEngine
from core.plant_registry import resolve_plant_context

logger = logging.getLogger("titan.monthly_inventory_router")

monthly_inventory_router = APIRouter(tags=["Monthly Chemical Inventory & Usage Tracking"])


# =============================================================================
# PYDANTIC SCHEMAS (PYDANTIC V1 & V2 COMPATIBLE)
# =============================================================================

class PeriodCreateRequest(BaseModel):
    month: int = Field(..., ge=1, le=12, description="Tháng báo cáo (1..12)")
    year: int = Field(..., ge=2000, le=2100, description="Năm báo cáo (>= 2000)")
    title: Optional[str] = Field(default=None, description="Tiêu đề kỳ báo cáo")
    notes: Optional[str] = Field(default="", description="Ghi chú kỳ báo cáo")
    copy_from_previous: Optional[bool] = Field(default=True, description="Kế thừa tồn tháng trước")
    auto_roll_forward: Optional[bool] = Field(default=True, description="Tự động chuyển số dư")
    plant_code: Optional[str] = Field(default=None, description="Mã chi nhánh/nhà máy (BD, DN, HP...)")
    plant_name: Optional[str] = Field(default=None, description="Tên chi nhánh/nhà máy")


class PeriodStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Trạng thái: OPEN, LOCKED, CLOSED, draft, closed, approved")
    notes: Optional[str] = Field(default=None, description="Ghi chú cập nhật")


class UpdateRecordItemModel(BaseModel):
    id: Optional[int] = Field(default=None, description="ID dòng trong monthly_inventory_records")
    record_id: Optional[int] = Field(default=None, description="Alias cho id dòng")
    opening_stock: Optional[float] = Field(default=None, ge=0, description="Tồn đầu kỳ")
    initial_stock: Optional[float] = Field(default=None, ge=0, description="Alias cho opening_stock")
    import_qty: Optional[float] = Field(default=None, ge=0, description="Tổng nhập trong tháng")
    total_import: Optional[float] = Field(default=None, ge=0, description="Alias cho import_qty")
    export_qty: Optional[float] = Field(default=None, ge=0, description="Tổng xuất dùng trong tháng")
    total_export: Optional[float] = Field(default=None, ge=0, description="Alias cho export_qty")
    storage_location: Optional[str] = Field(default=None, description="Vị trí lưu kho")
    unit: Optional[str] = Field(default=None, description="Đơn vị tính")
    safety_threshold: Optional[float] = Field(default=None, ge=0, description="Ngưỡng an toàn (kg)")
    export_purpose_breakdown: Optional[str] = Field(default=None, description="Phân bổ mục đích sử dụng")
    safety_notes: Optional[str] = Field(default=None, description="Ghi chú an toàn")
    notes: Optional[str] = Field(default=None, description="Alias cho safety_notes")


class BatchUpdateRecordsRequest(BaseModel):
    period_id: Optional[int] = Field(default=None, description="ID kỳ báo cáo")
    period_key: Optional[str] = Field(default=None, description="Khóa kỳ báo cáo (YYYY-MM)")
    records: List[UpdateRecordItemModel] = Field(..., min_length=1, description="Danh sách các dòng cập nhật")


class AddChemicalsRequest(BaseModel):
    period_id: Optional[int] = Field(default=None, description="ID kỳ báo cáo")
    period_key: Optional[str] = Field(default=None, description="Khóa kỳ báo cáo (YYYY-MM)")
    chemical_ids: Optional[List[str]] = Field(default=None, description="Danh sách chemical_id từ Sổ CIL")
    all: Optional[bool] = Field(default=False, description="Cờ thêm toàn bộ hóa chất CIL")


class CreateTransactionRequest(BaseModel):
    period_id: Optional[int] = Field(default=None, description="ID kỳ báo cáo")
    period_key: Optional[str] = Field(default=None, description="Khóa kỳ báo cáo (YYYY-MM)")
    chemical_id: str = Field(..., description="Mã hóa chất CIL (liên kết chemicals.chemical_id)")
    transaction_type: str = Field(..., description="Loại giao dịch: 'IMPORT' hoặc 'EXPORT'")
    quantity: float = Field(..., gt=0, description="Số lượng giao dịch (> 0)")
    transaction_date: Optional[str] = Field(default=None, description="Ngày giao dịch (YYYY-MM-DD)")
    date: Optional[str] = Field(default=None, description="Alias cho transaction_date")
    unit: Optional[str] = Field(default="kg", description="Đơn vị tính")
    reference_doc: Optional[str] = Field(default="", description="Số chứng từ (Hóa đơn, PO, PXK)")
    voucher_no: Optional[str] = Field(default="", description="Alias cho reference_doc")
    department: Optional[str] = Field(default="", description="Phân xưởng nhận hoặc NCC giao")
    partner: Optional[str] = Field(default="", description="Alias cho department")
    purpose: Optional[str] = Field(default="", description="Mục đích sử dụng")
    notes: Optional[str] = Field(default="", description="Ghi chú giao dịch")
    plant_code: Optional[str] = Field(default=None, description="Mã chi nhánh/nhà máy")
    plant_name: Optional[str] = Field(default=None, description="Tên chi nhánh/nhà máy")


class UpdateTransactionRequest(BaseModel):
    quantity: Optional[float] = Field(default=None, gt=0, description="Số lượng giao dịch")
    transaction_type: Optional[str] = Field(default=None, description="Loại giao dịch")
    transaction_date: Optional[str] = Field(default=None, description="Ngày giao dịch")
    date: Optional[str] = Field(default=None, description="Alias cho transaction_date")
    reference_doc: Optional[str] = Field(default=None, description="Số chứng từ")
    voucher_no: Optional[str] = Field(default=None, description="Alias cho reference_doc")
    department: Optional[str] = Field(default=None, description="Phân xưởng / Đối tác")
    partner: Optional[str] = Field(default=None, description="Alias cho department")
    purpose: Optional[str] = Field(default=None, description="Mục đích")
    notes: Optional[str] = Field(default=None, description="Ghi chú")


class RollForwardRequest(BaseModel):
    from_period: Optional[str] = Field(default=None, description="Kỳ nguồn (YYYY-MM hoặc id)")
    to_period: Optional[str] = Field(default=None, description="Kỳ đích (YYYY-MM hoặc id)")
    from_period_id: Optional[int] = Field(default=None, description="ID kỳ nguồn")
    to_period_id: Optional[int] = Field(default=None, description="ID kỳ đích")
    overwrite_initial: Optional[bool] = Field(default=True, description="Ghi đè tồn đầu kỳ nếu đã có")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _determine_period_ident(
    period_id: Optional[int] = None,
    period_key: Optional[str] = None,
    period: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> Union[int, str]:
    """Xác định định danh kỳ báo cáo từ nhiều nguồn tham số query/path/body."""
    pkey = (period_key or period or "").strip()
    # Nếu có period_key hợp lệ định dạng YYYY-MM
    if pkey and re.match(r"^\d{4}-\d{2}$", pkey):
        # Nếu đồng thời có period_id, kiểm tra xem period_id có thực sự tồn tại trong CSDL không
        if period_id is not None:
            try:
                with MonthlyInventoryEngine.get_connection() as conn:
                    row = conn.execute("SELECT id FROM monthly_periods WHERE id = ?", (int(period_id),)).fetchone()
                    if row:
                        return int(row["id"])
            except Exception:
                pass
        # Nếu period_id không tồn tại hoặc stale, ưu tiên fallback sang period_key hợp lệ
        return pkey

    # Nếu chỉ có period_id hoặc period_key không theo định dạng chuẩn
    if period_id is not None:
        try:
            with MonthlyInventoryEngine.get_connection() as conn:
                row = conn.execute("SELECT id FROM monthly_periods WHERE id = ?", (int(period_id),)).fetchone()
                if row:
                    return int(row["id"])
        except Exception:
            pass
        if pkey:
            return pkey
        return period_id

    if pkey:
        return pkey
    if month is not None and year is not None:
        return f"{int(year):04d}-{int(month):02d}"

    # Mặc định lấy kỳ tháng hiện tại
    now = datetime.now()
    return f"{now.year:04d}-{now.month:02d}"


# =============================================================================
# 1. PERIODS ENDPOINTS
# =============================================================================

@monthly_inventory_router.get("/periods", summary="Danh sách các kỳ báo cáo")
def list_periods(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    plant_code: Optional[str] = Query(None, description="Lọc theo mã chi nhánh/nhà máy (BD, DN, HP...)"),
    x_titan_plant: Optional[str] = Header(None, alias="X-Titan-Plant"),
    x_plant_code: Optional[str] = Header(None, alias="X-Plant-Code"),
):
    """Lấy danh sách tất cả các kỳ báo cáo kèm chỉ số tổng quan."""
    try:
        resolved_plant = resolve_plant_context(plant_code, x_titan_plant, x_plant_code)
        periods = MonthlyInventoryEngine.list_periods(limit=limit, offset=offset, plant_code=resolved_plant)
        return periods
    except Exception as e:
        logger.error("Lỗi list_periods: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi truy vấn danh sách kỳ báo cáo: {str(e)}")


@monthly_inventory_router.post("/periods", summary="Tạo kỳ báo cáo mới")
def create_period(payload: PeriodCreateRequest, _: str = Depends(require_owner)):
    """
    Tạo một kỳ báo cáo mới (hoặc trả về kỳ đã có).
    Nếu copy_from_previous=True hoặc auto_roll_forward=True, tự động kế thừa tồn kho tháng trước.
    """
    try:
        copy_prev = payload.copy_from_previous if payload.copy_from_previous is not None else payload.auto_roll_forward
        period = MonthlyInventoryEngine.create_period(
            month=payload.month,
            year=payload.year,
            title=payload.title,
            notes=payload.notes or "",
            copy_from_previous=bool(copy_prev),
            auto_roll_forward=bool(copy_prev),
            plant_code=payload.plant_code,
            plant_name=payload.plant_name,
        )
        return period
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Lỗi create_period: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi khởi tạo kỳ báo cáo: {str(e)}")


@monthly_inventory_router.get("/periods/{period_ident}", summary="Chi tiết một kỳ báo cáo")
def get_period(period_ident: str):
    """Lấy thông tin chi tiết một kỳ báo cáo kèm danh sách hóa chất và KPI."""
    period = MonthlyInventoryEngine.get_period(period_ident)
    if not period:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy kỳ báo cáo '{period_ident}'")
    return period


@monthly_inventory_router.put("/periods/{period_ident}/status", summary="Cập nhật trạng thái kỳ báo cáo")
def update_period_status(period_ident: str, payload: PeriodStatusUpdateRequest, _: str = Depends(require_owner)):
    """Cập nhật trạng thái kỳ báo cáo ('OPEN', 'LOCKED', 'CLOSED' hoặc 'draft', 'closed', 'approved')."""
    try:
        updated = MonthlyInventoryEngine.update_period_status(
            period_ident=period_ident,
            status=payload.status,
            notes=payload.notes,
        )
        return {"success": True, "period": updated}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error("Lỗi update_period_status: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi cập nhật trạng thái: {str(e)}")


@monthly_inventory_router.delete("/periods/{period_ident}", summary="Xóa một kỳ báo cáo")
def delete_period(period_ident: str, _: str = Depends(require_owner)):
    """Xóa một kỳ báo cáo cùng toàn bộ bản ghi và nhật ký giao dịch phát sinh."""
    ok = MonthlyInventoryEngine.delete_period(period_ident)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy kỳ báo cáo '{period_ident}' để xóa.")
    return {"success": True, "message": f"Đã xóa thành công kỳ báo cáo '{period_ident}'"}


# =============================================================================
# 2. KPI SUMMARY & SAFETY ALERTS
# =============================================================================

@monthly_inventory_router.get("/summary", summary="Lấy chỉ số KPI tổng quan thời gian thực")
@monthly_inventory_router.get("/kpi", summary="Lấy chỉ số KPI tổng quan thời gian thực (Alias)")
def get_summary(
    period_id: Optional[int] = Query(None),
    period_key: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    plant_code: Optional[str] = Query(None, description="Mã chi nhánh/nhà máy (BD, DN, HP...)"),
    x_titan_plant: Optional[str] = Header(None, alias="X-Titan-Plant"),
    x_plant_code: Optional[str] = Header(None, alias="X-Plant-Code"),
):
    """Trả về KPI thời gian thực của kỳ báo cáo: tổng hóa chất, tổng tồn, nhập, xuất, số cảnh báo."""
    ident = _determine_period_ident(period_id, period_key, period, month, year)
    resolved_plant = resolve_plant_context(plant_code, x_titan_plant, x_plant_code)
    kpi = MonthlyInventoryEngine.get_period_kpi(ident, plant_code=resolved_plant)
    return kpi


@monthly_inventory_router.get("/periods/{period_ident}/safety-alerts", summary="Danh sách cảnh báo an toàn của kỳ")
def get_safety_alerts(period_ident: str):
    """Lấy danh sách chi tiết các trường hợp tồn kho âm hoặc vượt ngưỡng an toàn Phụ lục IV NĐ 24."""
    alerts = MonthlyInventoryEngine.get_safety_alerts(period_ident)
    return alerts


# =============================================================================
# 3. RECORDS ENDPOINTS (QUICK SUMMARY INLINE EDIT)
# =============================================================================

@monthly_inventory_router.get("/records", summary="Lưới dữ liệu Nhập - Xuất - Tồn của kỳ")
def list_records(
    period_id: Optional[int] = Query(None),
    period_key: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
    warning_only: bool = Query(False),
    plant_code: Optional[str] = Query(None, description="Lọc theo mã chi nhánh/nhà máy (BD, DN, HP...)"),
    x_titan_plant: Optional[str] = Header(None, alias="X-Titan-Plant"),
    x_plant_code: Optional[str] = Header(None, alias="X-Plant-Code"),
):
    """Lấy danh sách các dòng dữ liệu Nhập - Xuất - Tồn trong kỳ báo cáo."""
    ident = _determine_period_ident(period_id, period_key, period, month, year)
    resolved_plant = resolve_plant_context(plant_code, x_titan_plant, x_plant_code)
    records = MonthlyInventoryEngine.list_records(
        period_ident=ident,
        query=q or "",
        warning_only=warning_only,
        plant_code=resolved_plant,
    )
    kpi = MonthlyInventoryEngine.get_period_kpi(ident, plant_code=resolved_plant)
    return {
        "success": True,
        "period_ident": ident,
        "plant_code": resolved_plant,
        "total": len(records),
        "records": records,
        "kpi": kpi,
    }


@monthly_inventory_router.get("/records/{record_id}", summary="Xem chi tiết 1 dòng hóa chất")
def get_record(record_id: int):
    """Lấy chi tiết 1 dòng bản ghi trong kỳ báo cáo."""
    rec = MonthlyInventoryEngine.get_record(record_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy bản ghi hóa chất id={record_id}")
    return rec


@monthly_inventory_router.put("/records/{record_id}", summary="Cập nhật nhanh số liệu dòng hóa chất (Mode 1)")
@monthly_inventory_router.patch("/records/{record_id}", summary="Cập nhật nhanh số liệu dòng hóa chất (Mode 1 - PATCH)")
@monthly_inventory_router.put("/periods/{period_ident}/records/{record_id}", summary="Cập nhật nhanh số liệu dòng hóa chất (Mode 1 - alias)")
@monthly_inventory_router.patch("/periods/{period_ident}/records/{record_id}", summary="Cập nhật nhanh số liệu dòng hóa chất (Mode 1 - alias PATCH)")
def update_record(record_id: int, payload: UpdateRecordItemModel, period_ident: Optional[str] = None, _: str = Depends(require_owner)):
    """
    Cập nhật trực tiếp số liệu (Mode 1: Quick Monthly Summary).
    Tự động tính: Tồn cuối kỳ = Tồn đầu kỳ + Tổng nhập - Tổng xuất
    và tự động kiểm tra cảnh báo an toàn.
    """
    try:
        data = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
        updated = MonthlyInventoryEngine.update_record(record_id, data, period_ident=period_ident)
        return updated
    except ValueError as ve:
        err_msg = str(ve)
        if "Không tìm thấy" in err_msg:
            raise HTTPException(status_code=404, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)
    except Exception as e:
        logger.error("Lỗi update_record: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi cập nhật dòng hóa chất: {str(e)}")


@monthly_inventory_router.put("/records-batch", summary="Cập nhật hàng loạt nhiều dòng dữ liệu")
def batch_update_records(payload: Union[BatchUpdateRecordsRequest, List[UpdateRecordItemModel]] = Body(...), _: str = Depends(require_owner)):
    """Cập nhật đồng loạt nhiều dòng hóa chất trên lưới dữ liệu."""
    try:
        if isinstance(payload, list):
            items = [item.model_dump(exclude_unset=True) if hasattr(item, "model_dump") else item.dict(exclude_unset=True) for item in payload]
            pid = items[0].get("period_id") or 1 if items else 1
        else:
            pid = payload.period_id or payload.period_key or 1
            items = [r.model_dump(exclude_unset=True) if hasattr(r, "model_dump") else r.dict(exclude_unset=True) for r in payload.records]

        count = MonthlyInventoryEngine.batch_update_records(pid, items)
        return {"success": True, "updated_count": count}
    except Exception as e:
        logger.error("Lỗi batch_update_records: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi cập nhật hàng loạt: {str(e)}")


@monthly_inventory_router.delete("/records/{record_id}", summary="Xóa hóa chất khỏi kỳ báo cáo")
def delete_record(record_id: int, _: str = Depends(require_owner)):
    """Xóa một hóa chất khỏi kỳ báo cáo hiện tại kèm các phiếu giao dịch phát sinh."""
    ok = MonthlyInventoryEngine.delete_record(record_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy bản ghi hóa chất id={record_id} để xóa.")
    return {"success": True, "message": f"Đã xóa thành công hóa chất id={record_id} khỏi kỳ báo cáo."}


# =============================================================================
# 4. SỔ CIL LINKAGE & BATCH ADD
# =============================================================================

@monthly_inventory_router.get("/available-chemicals", summary="Danh sách hóa chất CIL có thể nạp vào kỳ")
def get_available_chemicals(
    period_id: Optional[int] = Query(None),
    period_key: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
):
    """Lấy danh sách hóa chất từ Sổ CIL chưa có mặt trong kỳ báo cáo này."""
    ident = _determine_period_ident(period_id, period_key, period, month, year)
    available = MonthlyInventoryEngine.get_available_cil_chemicals(ident, query=q or "")
    return available


@monthly_inventory_router.post("/periods/{period_ident}/add-from-cil", summary="Thêm hóa chất từ CIL vào kỳ")
def add_chemicals_from_cil_path(period_ident: str, payload: AddChemicalsRequest, _: str = Depends(require_owner)):
    """Nạp một hoặc hàng loạt hóa chất từ Sổ CIL vào kỳ báo cáo qua path param."""
    try:
        added_count = MonthlyInventoryEngine.add_chemicals_from_cil(
            period_ident=period_ident,
            chemical_ids=payload.chemical_ids,
            add_all=bool(payload.all),
        )
        return {"success": True, "period_ident": period_ident, "added_count": added_count}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error("Lỗi add_chemicals_from_cil: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi nạp hóa chất từ CIL: {str(e)}")


@monthly_inventory_router.post("/add-chemicals", summary="Thêm hóa chất từ CIL vào kỳ (Body param)")
@monthly_inventory_router.post("/chemicals", summary="Thêm hóa chất từ CIL vào kỳ (Alias)")
def add_chemicals_general(payload: AddChemicalsRequest, _: str = Depends(require_owner)):
    """Nạp một hoặc hàng loạt hóa chất từ Sổ CIL vào kỳ báo cáo qua request body."""
    ident = _determine_period_ident(payload.period_id, payload.period_key)
    try:
        added_count = MonthlyInventoryEngine.add_chemicals_from_cil(
            period_ident=ident,
            chemical_ids=payload.chemical_ids,
            add_all=bool(payload.all),
        )
        return {"success": True, "period_ident": ident, "added_count": added_count}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error("Lỗi add_chemicals_general: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi nạp hóa chất từ CIL: {str(e)}")


# =============================================================================
# 5. DETAILED TRANSACTIONS LOG (MODE 2)
# =============================================================================

@monthly_inventory_router.get("/periods/{period_ident}/transactions", summary="Danh sách phiếu giao dịch của kỳ")
def list_transactions_by_period(
    period_ident: str,
    chemical_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    transaction_type: Optional[str] = Query(None),
    plant_code: Optional[str] = Query(None, description="Mã chi nhánh/nhà máy (BD, DN, HP...)"),
    x_titan_plant: Optional[str] = Header(None, alias="X-Titan-Plant"),
    x_plant_code: Optional[str] = Header(None, alias="X-Plant-Code"),
):
    """Lấy danh sách các phiếu xuất/nhập chi tiết trong kỳ."""
    ttype = type or transaction_type
    resolved_plant = resolve_plant_context(plant_code, x_titan_plant, x_plant_code)
    txns = MonthlyInventoryEngine.list_transactions(
        period_ident=period_ident,
        chemical_id=chemical_id,
        transaction_type=ttype,
        plant_code=resolved_plant,
    )
    return txns


@monthly_inventory_router.get("/transactions", summary="Danh sách phiếu giao dịch (Query param)")
def list_transactions(
    period_id: Optional[int] = Query(None),
    period_key: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    chemical_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    transaction_type: Optional[str] = Query(None),
    plant_code: Optional[str] = Query(None, description="Mã chi nhánh/nhà máy (BD, DN, HP...)"),
    x_titan_plant: Optional[str] = Header(None, alias="X-Titan-Plant"),
    x_plant_code: Optional[str] = Header(None, alias="X-Plant-Code"),
):
    """Lấy danh sách các phiếu xuất/nhập chi tiết."""
    ident = _determine_period_ident(period_id, period_key, period)
    ttype = type or transaction_type
    resolved_plant = resolve_plant_context(plant_code, x_titan_plant, x_plant_code)
    txns = MonthlyInventoryEngine.list_transactions(
        period_ident=ident,
        chemical_id=chemical_id,
        transaction_type=ttype,
        plant_code=resolved_plant,
    )
    return txns


@monthly_inventory_router.post("/transactions", summary="Ghi nhận phiếu nhập/xuất kho (Mode 2)")
def create_transaction(payload: CreateTransactionRequest, _: str = Depends(require_owner)):
    """
    Ghi nhận một phiếu nhập hoặc xuất kho (Mode 2).
    Hệ thống tự động cộng dồn số lượng lên dòng tổng hợp tương ứng và tính lại tồn cuối kỳ.
    """
    ident = _determine_period_ident(payload.period_id, payload.period_key)
    tdate = payload.transaction_date or payload.date or datetime.now().strftime("%Y-%m-%d")
    ref = payload.reference_doc or payload.voucher_no or ""
    dept = payload.department or payload.partner or ""

    try:
        txn = MonthlyInventoryEngine.create_transaction(
            period_ident=ident,
            chemical_id=payload.chemical_id,
            transaction_type=payload.transaction_type,
            quantity=payload.quantity,
            transaction_date=tdate,
            unit=payload.unit or "kg",
            reference_doc=ref,
            department=dept,
            purpose=payload.purpose or "",
            notes=payload.notes or "",
            plant_code=payload.plant_code,
            plant_name=payload.plant_name,
        )
        return txn
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Lỗi create_transaction: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi tạo phiếu giao dịch: {str(e)}")


@monthly_inventory_router.put("/transactions/{txn_ident}", summary="Chỉnh sửa phiếu giao dịch")
def update_transaction(txn_ident: str, payload: UpdateTransactionRequest, _: str = Depends(require_owner)):
    """Chỉnh sửa phiếu giao dịch và tự động tính lại tổng kho."""
    try:
        data = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
        updated = MonthlyInventoryEngine.update_transaction(txn_ident, data)
        return updated
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error("Lỗi update_transaction: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi cập nhật phiếu giao dịch: {str(e)}")


@monthly_inventory_router.delete("/transactions/{txn_ident}", summary="Xóa phiếu giao dịch")
def delete_transaction(txn_ident: str, _: str = Depends(require_owner)):
    """Xóa phiếu giao dịch và tự động trừ khỏi tổng kho."""
    ok = MonthlyInventoryEngine.delete_transaction(txn_ident)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy phiếu giao dịch '{txn_ident}' để xóa.")
    return {"success": True, "message": f"Đã xóa thành công phiếu giao dịch '{txn_ident}'."}


# =============================================================================
# 6. ROLL-FORWARD ENDPOINT
# =============================================================================

@monthly_inventory_router.post("/roll-forward", summary="Thực hiện chuyển số dư tồn cuối kỳ qua tháng mới")
@monthly_inventory_router.post("/periods/roll-forward", summary="Thực hiện chuyển số dư tồn cuối kỳ qua tháng mới (alias)")
def roll_forward(payload: RollForwardRequest, _: str = Depends(require_owner)):
    """
    Chuyển số dư Tồn cuối kỳ của tháng nguồn làm Tồn đầu kỳ của tháng đích.
    Hỗ trợ tham số from_period/to_period hoặc from_period_id/to_period_id.
    """
    from_p = payload.from_period or payload.from_period_id
    to_p = payload.to_period or payload.to_period_id

    if not from_p or not to_p:
        raise HTTPException(status_code=400, detail="Cần cung cấp cả kỳ nguồn (from_period) và kỳ đích (to_period).")

    try:
        res = MonthlyInventoryEngine.roll_forward(
            from_period=from_p,
            to_period=to_p,
            overwrite_initial=bool(payload.overwrite_initial),
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error("Lỗi roll_forward: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi chuyển số dư tồn kho: {str(e)}")


# =============================================================================
# 7. EXCEL EXPORT & PRINT PREVIEW
# =============================================================================

@monthly_inventory_router.get("/export-excel", summary="Kết xuất tệp Báo cáo Excel (.xlsx)")
def export_excel(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    period_id: Optional[int] = Query(None),
    period_key: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
):
    """
    Kết xuất tệp Báo Cáo Nhập - Xuất - Tồn và Sử Dụng Hóa Chất Tháng ra định dạng Excel (.xlsx)
    chuẩn biểu mẫu doanh nghiệp, có công thức tính tổng tự động và khung ký duyệt 3 cấp.
    """
    target_month = month
    target_year = year

    # Nếu truyền period_key 'YYYY-MM'
    p_str = period_key or period
    if p_str and "-" in p_str:
        parts = p_str.split("-")
        try:
            target_year = int(parts[0])
            target_month = int(parts[1])
        except Exception:
            pass

    if target_month is None or target_year is None:
        now = datetime.now()
        target_month = target_month or now.month
        target_year = target_year or now.year

    try:
        excel_bytes = MonthlyInventoryEngine.export_excel(month=target_month, year=target_year)
        filename = f"Bao_Cao_Su_Dung_Hoa_Chat_Thang_{target_month:02d}_{target_year}.xlsx"

        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    except Exception as e:
        logger.error("Lỗi export_excel: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi kết xuất Excel báo cáo tháng: {str(e)}")


@monthly_inventory_router.get("/print-html", summary="Xem trước bản in HTML định dạng A4 khổ ngang")
def print_html(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    period_id: Optional[int] = Query(None),
    period_key: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
):
    """Trả về trang HTML định dạng chuẩn in ấn A4 khổ ngang sẵn sàng in trực tiếp từ trình duyệt."""
    target_month = month
    target_year = year

    p_str = period_key or period
    if p_str and "-" in p_str:
        parts = p_str.split("-")
        try:
            target_year = int(parts[0])
            target_month = int(parts[1])
        except Exception:
            pass

    if target_month is None or target_year is None:
        now = datetime.now()
        target_month = target_month or now.month
        target_year = target_year or now.year

    try:
        html = MonthlyInventoryEngine.render_print_html(month=target_month, year=target_year)
        return HTMLResponse(content=html, status_code=200)
    except Exception as e:
        logger.error("Lỗi print_html: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi tạo bản in HTML: {str(e)}")


@monthly_inventory_router.get("/periods/{period_ident}/print-preview", summary="Xem trước bản in HTML qua period path")
def print_preview_by_period(period_ident: str):
    """Xem trước bản in HTML của kỳ báo cáo qua path param."""
    period = MonthlyInventoryEngine.get_period(period_ident)
    if not period:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy kỳ báo cáo '{period_ident}'")

    m = period["month"]
    y = period["year"]
    html = MonthlyInventoryEngine.render_print_html(month=m, year=y)
    return HTMLResponse(content=html, status_code=200)


@monthly_inventory_router.get("/export-pdf", summary="Kết xuất tệp Báo cáo PDF (.pdf)")
def export_pdf(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    period_id: Optional[int] = Query(None),
    period_key: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
):
    """
    Kết xuất tệp Báo Cáo Nhập - Xuất - Tồn Hóa Chất Tháng ra tệp PDF khổ A4 ngang chính thức,
    chuẩn hóa đồ họa vector, có đầy đủ bảng số liệu và khung ký duyệt 3 bên.
    """
    target_month = month
    target_year = year

    p_str = period_key or period
    if p_str and "-" in p_str:
        parts = p_str.split("-")
        try:
            target_year = int(parts[0])
            target_month = int(parts[1])
        except Exception:
            pass

    if target_month is None or target_year is None:
        now = datetime.now()
        target_month = target_month or now.month
        target_year = target_year or now.year

    try:
        pdf_bytes = MonthlyInventoryEngine.export_pdf(month=target_month, year=target_year)
        filename = f"Bao_Cao_Su_Dung_Hoa_Chat_Thang_{target_month:02d}_{target_year}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    except Exception as e:
        logger.error("Lỗi export_pdf: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi kết xuất PDF báo cáo tháng: {str(e)}")


@monthly_inventory_router.get("/download-template", summary="Tải tệp Excel mẫu để nhập dữ liệu kho (.xlsx)")
def download_template():
    """Tải tệp Excel mẫu với đầy đủ tiêu đề cột và hướng dẫn để người dùng điền số liệu nhập kho hàng loạt."""
    try:
        tmpl_bytes = MonthlyInventoryEngine.generate_excel_template()
        filename = "Bieu_Mau_Nhap_Xuat_Ton_Kho_Template.xlsx"
        return Response(
            content=tmpl_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    except Exception as e:
        logger.error("Lỗi download_template: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi tạo tệp mẫu: {str(e)}")


@monthly_inventory_router.post("/import-excel", summary="Nhập dữ liệu hàng loạt từ file Excel kho (.xlsx)")
async def import_excel(
    file: UploadFile = File(..., description="Tệp Excel (.xlsx) danh sách hóa chất kho"),
    period_key: Optional[str] = Form(None),
    period_id: Optional[int] = Form(None),
    _: str = Depends(require_owner),
):
    """
    Đọc và nạp dữ liệu hàng loạt từ tệp Excel thực tế của kho vào kỳ báo cáo được chỉ định.
    Tự động khớp hóa chất với Sổ CIL và cập nhật Tồn đầu, Nhập, Xuất.
    """
    ident = _determine_period_ident(period_id=period_id, period_key=period_key)
    try:
        content = await file.read()
        res = MonthlyInventoryEngine.import_excel(
            period_ident=ident,
            file_bytes=content,
            filename=file.filename or "upload.xlsx",
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Lỗi import_excel: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi nhập dữ liệu từ Excel: {str(e)}")


# =============================================================================
# 8. HEALTH CHECK
# =============================================================================

@monthly_inventory_router.get("/health", summary="Kiểm tra trạng thái hoạt động phân hệ NXT")
def health_check():
    """Kiểm tra tình trạng hoạt động và số lượng kỳ báo cáo trong hệ thống."""
    try:
        MonthlyInventoryEngine.init_db()
        periods = MonthlyInventoryEngine.list_periods(limit=1000)
        return {
            "status": "ok",
            "module": "Monthly Chemical Inventory & Usage Tracking (NXT)",
            "version": "2026.1",
            "total_periods": len(periods),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
