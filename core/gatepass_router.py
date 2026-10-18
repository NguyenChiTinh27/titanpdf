"""
core/gatepass_router.py
───────────────────────
FASTAPI ROUTER CHO PHÂN HỆ QUẢN LÝ PHIẾU XUẤT HÀNG & VẬT TƯ (GATE PASS & MATERIAL DISPATCH STUDIO)

Endpoints:
1. GET  /api/gatepass/dashboard           - Thống kê KPI & Biểu đồ Chart.js (Read-only)
2. GET  /api/gatepass/history             - Tra cứu lịch sử phiếu xuất kho (Read-only)
3. GET  /api/gatepass/detail/{so_phieu}   - Xem chi tiết phiếu và danh mục hàng (Read-only)
4. POST /api/gatepass/save                - Lưu phiếu xuất vào CSDL & Cloud (RBAC require_owner)
5. DELETE /api/gatepass/{so_phieu}        - Xóa phiếu xuất khỏi hệ thống (RBAC require_owner)
6. POST /api/gatepass/sync-all            - Đồng bộ tất cả phiếu pending lên Sheet (RBAC require_owner)
7. POST /api/gatepass/sync-headers        - Chuẩn hóa 19 cột tiêu đề Google Sheet (RBAC require_owner)
8. GET  /api/gatepass/print/{so_phieu}    - Xuất trang in phiếu chuẩn A4/A5 (Read-only)
"""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.auth_rbac import require_owner
from core.gatepass_service import GatePassService

logger = logging.getLogger("titan.gatepass_router")

gatepass_router = APIRouter(tags=["Gate Pass & Material Dispatch Studio"])

# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class GatePassScanJsonRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    image_b64: Optional[str] = Field(default=None, description="Base64 encoded slip image")
    image: Optional[str] = Field(default=None, description="Alias for image_b64")
    file_data: Optional[str] = Field(default=None, description="Alias for image_b64")
    slip_image_b64: Optional[str] = Field(default=None, description="Alias for image_b64")
    base64: Optional[str] = Field(default=None, description="Alias for image_b64")
    filename: Optional[str] = Field(default="scanned_slip.jpg", description="Original filename")
    mime_type: Optional[str] = Field(default="image/jpeg", description="MIME type")
    api_key: Optional[str] = Field(default=None, description="Optional DeepSeek API Key override")


class GatePassAuditProofJsonRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    slip_data: Optional[Dict[str, Any]] = Field(default=None, description="Extracted slip metadata")
    slip: Optional[Dict[str, Any]] = Field(default=None, description="Alias for slip_data")
    proof_images: Optional[Union[List[str], str]] = Field(default_factory=list, description="Base64 encoded proof images")
    proof_b64_list: Optional[Union[List[str], str]] = Field(default=None, description="Alias for proof_images")
    images: Optional[Union[List[str], str]] = Field(default=None, description="Alias for proof_images")
    api_key: Optional[str] = Field(default=None, description="Optional DeepSeek API Key override")


class GatePassItemInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    stt: Optional[int] = Field(default=1, description="Số thứ tự mặt hàng")
    loai_hang_hoa: str = Field(..., description="Tên mặt hàng song ngữ Trung - Việt")
    ten_hang: Optional[str] = Field(default=None, description="Alias cho loai_hang_hoa")
    quy_cach: Optional[str] = Field(default="", description="Quy cách đóng gói (vd: 25kg/bao)")
    sl_kien: Union[int, float, str] = Field(default=0, description="Số lượng kiện")
    sl_thung: Union[int, float, str] = Field(default=0, description="Số lượng thùng")
    trong_luong_kg: Optional[Union[float, str]] = Field(default=0.0, description="Trọng lượng (KG)")
    khoi_luong_kg: Optional[Union[float, str]] = Field(default=0.0, description="Trọng lượng (KG) alias")
    ghi_chu: Optional[str] = Field(default="", description="Ghi chú kỹ thuật / RoHS / COA")


class GatePassSaveRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @model_validator(mode="before")
    @classmethod
    def unpack_nested_slip(cls, data: Any) -> Any:
        if isinstance(data, dict):
            slip_data = data.get("slip")
            if isinstance(slip_data, dict):
                merged = {**slip_data, **data}
                return merged
        return data

    so_phieu: str = Field(..., min_length=1, max_length=50, description="Mã số phiếu xuất kho")
    ngay_thang: Optional[str] = Field(default=None, description="Ngày xuất kho (DD/MM/YYYY hoặc YYYY-MM-DD)")
    loai_xuat: str = Field(default="Xuất hàng thành phẩm", description="Loại xuất: Xuất hàng thành phẩm | Xuất vật tư ra công | Xuất trả hàng")
    don_vi_van_chuyen: Optional[str] = Field(default="", description="Đơn vị / đội xe vận chuyển")
    so_xe: Optional[str] = Field(default="", description="Biển số xe chuyên chở")
    don_vi_dat_hang: Optional[str] = Field(default="", description="Khách hàng / Đơn vị đặt hàng")
    khach_hang: Optional[str] = Field(default="", description="Alias cho don_vi_dat_hang")
    so_don_hang: Optional[str] = Field(default="", description="Số đơn hàng / PO")
    so_po: Optional[str] = Field(default="", description="Alias cho so_don_hang")
    tong_cong_kg: Optional[Union[float, str]] = Field(default=0.0, description="Tổng khối lượng (KG)")
    tong_cong_kg_display: Optional[str] = Field(default=None, description="Chuỗi hiển thị khối lượng")
    tong_thung_kien: Optional[str] = Field(default="", description="Chuỗi mô tả tổng thùng kiện")
    tong_ghi_chu: Optional[str] = Field(default="", description="Ghi chú chung của phiếu")
    ghi_chu: Optional[str] = Field(default="", description="Ghi chú chung alias")
    bo_phan_ky_ten: Optional[str] = Field(default="", description="Bộ phận ký tên / Kho xuất")
    phe_duyet: Optional[str] = Field(default="", description="Người phê duyệt / Quản lý kho")
    nguoi_lap_phieu: Optional[str] = Field(default="", description="Người lập phiếu xuất")
    nguoi_lap: Optional[str] = Field(default="", description="Alias người lập phiếu")
    thu_kho: Optional[str] = Field(default="", description="Thủ kho ký tên")
    nguoi_nhan_hang: Optional[str] = Field(default="", description="Lái xe / người nhận hàng")
    nguoi_nhan: Optional[str] = Field(default="", description="Alias người nhận hàng")
    audit_summary: Optional[str] = Field(default="", description="Đánh giá kiểm toán chữ ký AI")
    audit_status: Optional[str] = Field(default="pending", description="Trạng thái kiểm toán")
    match_summary: Optional[str] = Field(default="", description="Đánh giá đối chiếu biển số xe AI")
    match_status: Optional[str] = Field(default="none", description="Trạng thái đối chiếu xe")
    main_file_url: Optional[str] = Field(default="", description="URL ảnh phiếu xuất gốc trên Google Drive")
    main_file_name: Optional[str] = Field(default="", description="Tên file ảnh gốc")
    main_image_b64: Optional[str] = Field(default="", description="Base64 ảnh phiếu xuất")
    slip_image_b64: Optional[str] = Field(default=None, description="Alias base64 ảnh phiếu")
    proof_urls: Optional[Union[List[str], str]] = Field(default_factory=list, description="Danh sách URL ảnh bằng chứng")
    items: List[GatePassItemInput] = Field(default_factory=list, description="Danh mục các dòng hàng hóa")
    danh_sach_hang_hoa: Optional[List[GatePassItemInput]] = Field(default=None, description="Alias cho items")
    sync_cloud: bool = Field(default=True, description="Đồng bộ ngay với Google Sheet & Drive")


class GatePassSyncAllRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    force: bool = Field(default=False, description="Bắt buộc đồng bộ lại tất cả phiếu kể cả đã SYNCED")
    limit: int = Field(default=100, ge=1, le=500, description="Số lượng tối đa phiếu xử lý")


class GatePassSyncHeadersRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    sheet_id: Optional[str] = Field(default=None, description="Tùy chọn Google Sheet ID ghi đè")


# =============================================================================
# ENDPOINT IMPLEMENTATIONS
# =============================================================================

# 1. GET /api/gatepass/dashboard (Read-only: Guest & Owner)
@gatepass_router.get("/dashboard", summary="Thống kê KPI và Biểu đồ Chart.js")
def get_dashboard(
    period: Optional[str] = Query(default=None, description="Khoảng thời gian: today | 7days | month | all | custom"),
    date_filter: Optional[str] = Query(default=None, description="Alias cho period"),
    date_from: Optional[str] = Query(default=None, description="Từ ngày (YYYY-MM-DD hoặc DD/MM/YYYY)"),
    date_to: Optional[str] = Query(default=None, description="Đến ngày (YYYY-MM-DD hoặc DD/MM/YYYY)")
):
    try:
        data = GatePassService.get_dashboard_metrics(
            period=period or date_filter,
            date_from=date_from,
            date_to=date_to
        )
        return data
    except Exception as e:
        logger.error("Lỗi lấy dữ liệu dashboard Gate Pass: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi truy xuất dashboard: {str(e)}")


# 2. GET /api/gatepass/history (Read-only: Guest & Owner)
@gatepass_router.get("/history", summary="Tra cứu lịch sử phiếu xuất kho")
def get_history(
    search: Optional[str] = Query(default="", description="Từ khóa: số phiếu, số xe, khách hàng, PO"),
    date_from: Optional[str] = Query(default=None, description="Từ ngày"),
    date_to: Optional[str] = Query(default=None, description="Đến ngày"),
    loai_xuat: Optional[str] = Query(default=None, description="Bộ lọc loại xuất"),
    page: int = Query(default=1, ge=1, description="Trang hiện tại"),
    page_size: int = Query(default=50, ge=1, le=500, description="Kích thước trang"),
    limit: Optional[int] = Query(default=None, description="Alias cho page_size"),
    offset: Optional[int] = Query(default=None, description="Alias cho offset phân trang")
):
    try:
        actual_page_size = limit if limit is not None else page_size
        actual_page = page
        if offset is not None and actual_page_size > 0:
            actual_page = (offset // actual_page_size) + 1

        result = GatePassService.list_slips(
            search=search or "",
            date_from=date_from,
            date_to=date_to,
            loai_xuat=loai_xuat,
            page=actual_page,
            page_size=actual_page_size,
            limit=limit,
            offset=offset
        )
        return result
    except Exception as e:
        logger.error("Lỗi tra cứu lịch sử Gate Pass: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi tra cứu lịch sử: {str(e)}")


# 3. GET /api/gatepass/detail/{so_phieu} (Read-only: Guest & Owner)
@gatepass_router.get("/detail/{so_phieu}", summary="Xem chi tiết phiếu xuất và danh mục hàng")
def get_slip_detail(so_phieu: str):
    slip = GatePassService.get_slip(so_phieu)
    if not slip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phiếu xuất mang mã '{so_phieu}'."
        )
    return {"status": "success", "data": slip}


# 4. POST /api/gatepass/save (MUTATION - Protected by require_owner)
@gatepass_router.post("/save", summary="Lưu phiếu xuất vào CSDL SQLite & Đồng bộ Cloud")
def save_slip(
    payload: GatePassSaveRequest,
    _: str = Depends(require_owner)
):
    try:
        slip_dict = payload.model_dump(by_alias=True)

        # Normalize aliases
        khach_hang_val = payload.khach_hang or payload.don_vi_dat_hang or ""
        so_po_val = payload.so_po or payload.so_don_hang or ""
        slip_dict["don_vi_dat_hang"] = khach_hang_val
        slip_dict["khach_hang"] = khach_hang_val
        slip_dict["so_don_hang"] = so_po_val
        slip_dict["so_po"] = so_po_val

        # Items list
        items_list = slip_dict.get("items") or slip_dict.get("danh_sach_hang_hoa") or []

        saved_info = GatePassService.save_slip(
            pass_data=slip_dict,
            items=items_list,
            sync_cloud=payload.sync_cloud
        )
        return {
            "status": "success",
            "message": f"Đã lưu phiếu {payload.so_phieu} thành công!",
            "so_phieu": payload.so_phieu,
            "sync_status": saved_info.get("sync_status", "pending"),
            "synced_cloud": saved_info.get("synced_cloud", False),
            "main_file_url": saved_info.get("main_file_url", ""),
            "sheet_row": saved_info.get("sheet_row")
        }
    except Exception as e:
        logger.error("Lỗi lưu phiếu xuất %s: %s", payload.so_phieu, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Không thể lưu phiếu xuất: {str(e)}")


# 5. DELETE /api/gatepass/{so_phieu} (MUTATION - Protected by require_owner)
@gatepass_router.delete("/{so_phieu}", summary="Xóa phiếu xuất khỏi hệ thống")
def delete_slip(
    so_phieu: str,
    _: str = Depends(require_owner)
):
    existing = GatePassService.get_slip(so_phieu)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phiếu xuất '{so_phieu}' để xóa."
        )
    success = GatePassService.delete_slip(so_phieu)
    if not success:
        raise HTTPException(status_code=500, detail=f"Không thể xóa phiếu xuất '{so_phieu}'.")
    return {
        "status": "success",
        "message": f"Đã xóa hoàn toàn phiếu xuất '{so_phieu}'.",
        "so_phieu": so_phieu
    }


# 6. POST /api/gatepass/sync-all (MUTATION - Protected by require_owner)
@gatepass_router.post("/sync-all", summary="Đồng bộ tất cả phiếu pending lên Google Sheet")
def sync_all_slips(
    payload: Optional[GatePassSyncAllRequest] = None,
    _: str = Depends(require_owner)
):
    force_sync = payload.force if payload else False
    limit_count = payload.limit if payload else 100
    try:
        result = GatePassService.sync_pending_slips(force=force_sync, limit=limit_count)
        return result
    except Exception as e:
        logger.error("Lỗi đồng bộ hàng loạt phiếu lên Google Sheet: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi đồng bộ Google Sheet: {str(e)}")


# 7. POST /api/gatepass/sync-headers (MUTATION - Protected by require_owner)
@gatepass_router.post("/sync-headers", summary="Chuẩn hóa 19 cột tiêu đề trên Google Sheet")
def sync_headers(
    payload: Optional[GatePassSyncHeadersRequest] = None,
    _: str = Depends(require_owner)
):
    try:
        sheet_id = payload.sheet_id if payload else None
        res = GatePassService.manual_sync_headers(sheet_id=sheet_id)
        return {
            "status": "success",
            "message": "Đã kiểm tra và chuẩn hóa 19 cột tiêu đề Google Sheet!",
            "sheet_id": res.get("sheet_id", "15Z3HA7Lm2pJU3GmfzdDq4ZfOKVYJoYJ_SYIT3pAM_ug"),
            "columns_verified": 19
        }
    except Exception as e:
        logger.error("Lỗi chuẩn hóa tiêu đề Google Sheet: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi chuẩn hóa Google Sheet: {str(e)}")


# 8. GET /api/gatepass/print/{so_phieu} (Read-only: Guest & Owner)
@gatepass_router.get("/print/{so_phieu}", response_class=HTMLResponse, summary="Xuất trang in phiếu chuẩn A4/A5")
def print_slip(
    so_phieu: str,
    paper_size: str = Query(default="A4", pattern="^(A4|A5|a4|a5)$", description="Khổ giấy in: A4 hoặc A5")
):
    slip = GatePassService.get_slip(so_phieu)
    if not slip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phiếu xuất '{so_phieu}' để in."
        )
    html_content = GatePassService.render_print_html(slip, paper_size=paper_size.upper())
    return HTMLResponse(content=html_content, status_code=200)


# =============================================================================
# 9. POST /api/gatepass/scan (and alias /ocr-scan)
# Protected by require_owner (Guest -> 403 Forbidden)
# =============================================================================
@gatepass_router.post("/scan", summary="Quét và bóc tách phiếu xuất kho bằng Vision AI")
@gatepass_router.post("/ocr-scan", summary="Alias cho /scan")
async def scan_dispatch_slip(
    request: Request,
    _: str = Depends(require_owner)
):
    """
    POST /api/gatepass/scan (hoặc /api/gatepass/ocr-scan)
    -----------------------------------------------------
    - Chấp nhận:
      * multipart/form-data: tệp UploadFile ('file' hoặc 'image')
      * application/json: chuỗi Base64 ('image_b64', 'file_data', 'slip_image_b64')
    - Trả về: Cấu trúc JSON phiếu xuất bóc tách hoàn chỉnh và danh mục hàng hóa
    - Quyền hạn: Quản trị viên (require_owner). Chế độ Khách trả về 403 Forbidden.
    """
    content_type = (request.headers.get("content-type") or "").lower()
    file_bytes: Optional[bytes] = None
    filename: str = "scanned_slip.jpg"
    api_key: Optional[str] = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        upload_file: Optional[UploadFile] = (
            form.get("file")
            or form.get("image")
            or form.get("image_file")
            or form.get("upload_file")
        )
        if upload_file is not None and hasattr(upload_file, "read"):
            file_bytes = await upload_file.read()
            filename = upload_file.filename or filename
        api_key = form.get("api_key")
    else:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Dữ liệu JSON không hợp lệ.")

        b64_str = (
            body.get("image_b64")
            or body.get("image")
            or body.get("file_data")
            or body.get("slip_image_b64")
            or body.get("base64")
        )
        filename = body.get("filename") or filename
        api_key = body.get("api_key")

        if b64_str:
            b64_clean = str(b64_str).strip()
            if "," in b64_clean:
                b64_clean = b64_clean.split(",", 1)[1]
            try:
                file_bytes = base64.b64decode(b64_clean, validate=True)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Dữ liệu Base64 không hợp lệ: {str(exc)}")

    if not file_bytes or len(file_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail="Không tìm thấy dữ liệu ảnh. Vui lòng tải lên tệp ảnh qua multipart (file/image) hoặc gửi JSON chứa image_b64."
        )

    try:
        extracted = GatePassService.extract_with_vision(
            image_bytes=file_bytes,
            filename=filename,
            api_key=api_key
        )
        return {
            "status": "success",
            "message": f"AI đã trích xuất thành công phiếu xuất từ {filename}!",
            "filename": filename,
            "data": extracted
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Lỗi trích xuất Vision AI phiếu xuất: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý DeepSeek Vision OCR: {str(e)}")


# =============================================================================
# 10. POST /api/gatepass/audit-proof (and alias /audit-match)
# Protected by require_owner (Guest -> 403 Forbidden)
# =============================================================================
@gatepass_router.post("/audit-proof", summary="Kiểm toán và đối soát ảnh bằng chứng bằng AI")
@gatepass_router.post("/audit-match", summary="Alias cho /audit-proof")
async def audit_proof_endpoint(
    request: Request,
    _: str = Depends(require_owner)
):
    """
    POST /api/gatepass/audit-proof (hoặc /api/gatepass/audit-match)
    --------------------------------------------------------------
    - Chấp nhận:
      * multipart/form-data: danh sách UploadFile ('files', 'proof_files', 'images') + 'slip_data'
      * application/json: danh sách Base64 ('proof_images', 'images') + 'slip_data'
    - Trả về: Đánh giá khớp biển số xe, chữ ký chứng từ, điểm số (score) và nhận xét
    - Quyền hạn: Quản trị viên (require_owner). Chế độ Khách trả về 403 Forbidden.
    """
    content_type = (request.headers.get("content-type") or "").lower()
    slip_data: Dict[str, Any] = {}
    proof_images_bytes: List[bytes] = []
    proof_images_b64: List[str] = []
    api_key: Optional[str] = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        slip_raw = form.get("slip_data") or form.get("slip")
        if slip_raw:
            try:
                slip_data = json.loads(slip_raw) if isinstance(slip_raw, str) else dict(slip_raw)
            except Exception:
                slip_data = {}
        else:
            slip_data = {
                "so_phieu": form.get("so_phieu") or "",
                "so_xe": form.get("so_xe") or "",
                "don_vi_dat_hang": form.get("don_vi_dat_hang") or form.get("khach_hang") or ""
            }

        api_key = form.get("api_key")

        uploaded_files = []
        for key in ["files", "proof_files", "proof_images", "images"]:
            flist = form.getlist(key)
            if flist:
                uploaded_files.extend(flist)
        single_f = form.get("file") or form.get("image")
        if single_f and single_f not in uploaded_files:
            uploaded_files.append(single_f)

        for uf in uploaded_files:
            if hasattr(uf, "read"):
                b = await uf.read()
                if b and len(b) > 0:
                    proof_images_bytes.append(b)
                    proof_images_b64.append(base64.b64encode(b).decode("utf-8"))
    else:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Dữ liệu JSON không hợp lệ.")

        slip_data = body.get("slip_data") or body.get("slip") or body
        api_key = body.get("api_key")
        raw_b64_list = (
            body.get("proof_images")
            or body.get("proof_b64_list")
            or body.get("proof_images_b64")
            or body.get("images")
            or []
        )
        if isinstance(raw_b64_list, str):
            raw_b64_list = [raw_b64_list]

        for b64_item in raw_b64_list:
            if not b64_item:
                continue
            cur = str(b64_item).strip()
            if not cur:
                continue
            if "," in cur:
                cur = cur.split(",", 1)[1]
            try:
                decoded = base64.b64decode(cur, validate=True)
                if decoded and len(decoded) > 0:
                    proof_images_bytes.append(decoded)
                    proof_images_b64.append(cur)
            except Exception as exc:
                logger.warning("Bỏ qua ảnh bằng chứng base64 lỗi: %s", exc)

    if not proof_images_bytes and not proof_images_b64:
        raise HTTPException(
            status_code=400,
            detail="Không tìm thấy ảnh bằng chứng nào. Vui lòng cung cấp ít nhất 1 ảnh chụp xe/biển số/kiện hàng."
        )

    try:
        evaluation = GatePassService.audit_and_cross_match(
            slip_data=slip_data,
            proof_images_b64_list=proof_images_b64,
            api_key=api_key
        )
        return {
            "status": "success",
            "message": "Đã hoàn thành kiểm toán và đối soát ảnh bằng chứng bằng AI!",
            "data": evaluation
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Lỗi đối soát bằng chứng Gate Pass: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi kiểm toán ảnh bằng chứng: {str(e)}")

