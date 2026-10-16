"""
core/legal_router.py
────────────────────
FastAPI APIRouter cho Phân hệ Pháp lý Hóa chất TitanPDF.
Cung cấp các endpoint:
- GET  /api/legal/catalog: Thống kê và siêu dữ liệu danh mục (NĐ 24, NĐ 28, QCVN 01)
- GET  /api/legal/search: Tra cứu đa tiêu chí, không dấu, phân trang
- POST /api/legal/match: Đối soát tự động danh sách số CAS / hoạt chất
- GET  /api/legal/match: Tra cứu nhanh 1 số CAS qua query parameter
- GET  /api/legal/matches: Đối chiếu tự động CSDL CIL nội bộ (SQLite)
- GET  /api/legal/export: Xuất tệp Excel (.xlsx) danh mục hoặc dòng trùng CIL
- GET  /api/legal/health: Kiểm tra trạng thái hoạt động của phân hệ
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from core.legal_engine import LegalCatalogEngine, LegalEngine, validate_cas, normalize_cas, extract_all_cas

logger = logging.getLogger("titan.legal_router")

# Đường dẫn thư mục xuất tệp
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
    DATA_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR

OUTPUT_DIR = DATA_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

legal_router = APIRouter(tags=["Chemical Legal Intelligence"])


# =============================================================================
# PYDANTIC SCHEMAS (Pydantic v2 Compatible)
# =============================================================================

class LegalSourceModel(BaseModel):
    source_id: str = Field(..., description="Mã văn bản (ND24, ND28, QCVN01)")
    source_title: str = Field(..., description="Tiêu đề chính thức của văn bản")
    source_date: Optional[str] = Field(default="", description="Ngày ban hành")
    law_basis: Optional[str] = Field(default="", description="Căn cứ pháp lý")
    count: int = Field(default=0, description="Tổng số bản ghi trong văn bản")


class LegalSectionModel(BaseModel):
    section_id: str = Field(..., description="Mã mục/phụ lục (e.g. ND24-PL-I)")
    source_id: str = Field(..., description="Mã văn bản cha")
    section_title: str = Field(..., description="Tiêu đề mục/phụ lục")
    count: int = Field(default=0, description="Số bản ghi trong mục")
    subgroups: List[str] = Field(default_factory=list, description="Danh sách phân nhóm")


class LegalCatalogStatsResponse(BaseModel):
    success: bool = Field(default=True)
    title: str = Field(default="Danh mục pháp lý hóa chất")
    scope_note: Optional[str] = Field(default="")
    total_records: int = Field(..., description="Tổng số bản ghi pháp lý")
    unique_cas: int = Field(..., description="Tổng số CAS duy nhất")
    cil_matched_records: Optional[int] = Field(default=0)
    sources: List[LegalSourceModel] = Field(default_factory=list)
    sections: List[LegalSectionModel] = Field(default_factory=list)


class LegalItemModel(BaseModel):
    item_id: str = Field(..., description="Mã định danh bản ghi")
    source_id: str = Field(...)
    source_title: str = Field(...)
    law_basis: Optional[str] = Field(default="")
    section_id: str = Field(...)
    section_title: str = Field(...)
    subgroup: Optional[str] = Field(default="")
    serial: Optional[Union[int, str]] = Field(default="")
    name_vi: str = Field(..., description="Tên hóa chất tiếng Việt")
    name_scientific: Optional[str] = Field(default="")
    cas_raw: Optional[str] = Field(default="")
    cas: Optional[str] = Field(default="")
    formula: Optional[str] = Field(default="")
    threshold: Optional[Union[float, str]] = Field(default="")
    hs_code: Optional[str] = Field(default="")
    authority: Optional[str] = Field(default="")
    twa: Optional[str] = Field(default="")
    stel: Optional[str] = Field(default="")
    badge: Optional[Dict[str, Any]] = Field(default=None)
    legal_badges: List[str] = Field(default_factory=list)
    obligation: Optional[str] = Field(default="")
    obligations: Optional[Union[str, List[Dict[str, Any]]]] = Field(default="")


class LegalSearchResponse(BaseModel):
    success: bool = Field(default=True)
    total: int = Field(..., description="Tổng số bản ghi tìm thấy")
    page: int = Field(default=1)
    page_size: int = Field(default=50)
    items: List[Dict[str, Any]] = Field(default_factory=list)


class IngredientInput(BaseModel):
    name: Optional[str] = Field(default="", description="Tên hoạt chất")
    cas: str = Field(..., description="Số CAS")
    concentration: Optional[Union[float, str]] = Field(default=None, description="Hàm lượng (%)")
    unit: Optional[str] = Field(default="%", description="Đơn vị")


class LegalMatchRequest(BaseModel):
    cas_numbers: Optional[List[str]] = Field(default_factory=list, description="Danh sách số CAS")
    ingredients: Optional[List[IngredientInput]] = Field(default_factory=list, description="Danh sách thành phần")
    chemical_id: Optional[str] = Field(default=None, description="Mã hóa chất CIL SQLite cần tra cứu")
    text: Optional[str] = Field(default="", description="Văn bản tự do chứa số CAS")


# =============================================================================
# HELPER: ENGINE ACCESS
# =============================================================================

def get_engine() -> LegalCatalogEngine:
    """Truy xuất Singleton LegalCatalogEngine."""
    return LegalCatalogEngine.get_instance()


# =============================================================================
# ROUTE HANDLERS
# =============================================================================

@legal_router.get("/catalog")
@legal_router.get("/meta")
@legal_router.get("/legal-catalog/meta")
@legal_router.get("/legal/catalog")
def get_catalog_stats():
    """
    Tra cứu tổng quan cấu trúc danh mục pháp lý hóa chất (NĐ 24, NĐ 28, QCVN 01).
    Phản hồi tức thì < 1ms.
    """
    engine = get_engine()
    stats = engine.get_catalog_stats()
    return {"success": True, **stats}


@legal_router.get("/search")
@legal_router.get("/legal-catalog")
@legal_router.get("/legal/search")
@legal_router.get("/")
def search_legal_catalog(
    q: Optional[str] = Query(default="", description="Từ khóa tra cứu (CAS, tên Việt/Anh, công thức, mã HS)"),
    source_id: Optional[str] = Query(default="", description="Bộ lọc văn bản (ND24, ND28, QCVN01)"),
    section_id: Optional[str] = Query(default="", description="Bộ lọc phụ lục/mục cụ thể"),
    subgroup: Optional[str] = Query(default="", description="Bộ lọc phân nhóm"),
    page: int = Query(default=1, ge=1, description="Số thứ tự trang"),
    page_size: int = Query(default=50, ge=1, le=500, description="Số lượng bản ghi mỗi trang"),
):
    """
    Tìm kiếm đa tiêu chí siêu tốc trên 2,191 bản ghi pháp lý.
    Hỗ trợ tìm kiếm tiếng Việt không dấu (Unicode NFKD) và liên kết đa từ khóa.
    """
    engine = get_engine()
    results = engine.search(
        q=q or "",
        source_id=source_id or "",
        section_id=section_id or "",
        subgroup=subgroup or "",
        page=page,
        page_size=page_size
    )
    return results


@legal_router.post("/match")
@legal_router.post("/legal/match")
def match_legal_chemicals(req: LegalMatchRequest):
    """
    Đối soát tự động danh sách hóa chất / hoạt chất SDS với toàn bộ quy định pháp luật.
    Trả về điều khoản bắt buộc, ngưỡng nồng độ, cảnh báo cấm/kiểm soát đặc biệt/tiền chất.
    """
    engine = get_engine()
    ingredients_to_check: List[Dict[str, Any]] = []

    # 1. Thu thập từ ingredients có cấu trúc
    if req.ingredients:
        for ing in req.ingredients:
            ingredients_to_check.append({
                "name": ing.name or "",
                "cas": ing.cas or "",
                "concentration": ing.concentration
            })

    # 2. Thu thập từ cas_numbers trực tiếp
    if req.cas_numbers:
        for cas in req.cas_numbers:
            ingredients_to_check.append({
                "name": "",
                "cas": cas,
                "concentration": None
            })

    # 3. Thu thập từ chemical_id (nếu yêu cầu nạp từ CSDL SQLite)
    if req.chemical_id:
        try:
            from core.msds_intelligence import MSDSDatabase
            chem = MSDSDatabase.get_chemical(req.chemical_id)
            if chem:
                for c in chem.get("composition", []):
                    ingredients_to_check.append({
                        "name": c.get("ingredient_name_vi") or c.get("ingredient_name_original") or "",
                        "cas": c.get("cas_number") or "",
                        "concentration": c.get("concentration_text") or c.get("concentration_min")
                    })
        except Exception as e:
            logger.warning("Could not fetch chemical_id %s: %s", req.chemical_id, e)

    # 4. Trích xuất từ free text nếu được gửi
    if req.text and req.text.strip():
        extracted = extract_all_cas(req.text)
        for cas in extracted:
            ingredients_to_check.append({
                "name": "",
                "cas": cas,
                "concentration": None
            })

    if not ingredients_to_check:
        return {
            "success": True,
            "total_checked": 0,
            "total_matched": 0,
            "matches": []
        }

    match_result = engine.match_ingredients(ingredients_to_check)
    return match_result


@legal_router.get("/match")
@legal_router.get("/legal/match")
def match_single_cas(cas: str = Query(..., description="Số CAS cần đối soát nhanh (ví dụ: 108-88-3)")):
    """Endpoint GET kiểm tra nhanh 1 số CAS từ URL/trình duyệt."""
    engine = get_engine()
    match_result = engine.match_ingredients([{"cas": cas, "name": ""}])
    return {
        "success": True,
        "cas": cas,
        "result": match_result["matches"][0] if match_result.get("matches") else None
    }


@legal_router.get("/matches")
@legal_router.get("/legal-catalog/matches")
@legal_router.get("/legal/matches")
def list_inventory_legal_matches(
    source_id: str = Query(default="", description="Lọc theo văn bản"),
    section_id: str = Query(default="", description="Lọc theo phụ lục"),
    subgroup: str = Query(default="", description="Lọc theo phân nhóm"),
    item_type: str = Query(default="", description="Lọc loại hàng: 'raw_material' hoặc 'finished_product'"),
    q: str = Query(default="", description="Từ khóa tra cứu"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
):
    """
    Đối soát chéo danh mục pháp lý với kho hóa chất hiện hành trong CIL (SQLite).
    Hỗ trợ phân loại rõ ràng 'Nguyên liệu' (raw_material) và 'Thành phẩm' (finished_product).
    """
    engine = get_engine()
    results = engine.match_inventory_cil(
        source_id=source_id,
        section_id=section_id,
        subgroup=subgroup,
        item_type=item_type,
        q=q,
        page=page,
        page_size=page_size
    )
    return results


@legal_router.get("/export")
@legal_router.get("/legal-catalog/export")
@legal_router.get("/legal/export")
def export_legal_catalog(
    mode: str = Query(default="catalog", description="'catalog' để xuất danh mục, 'matches' để xuất các chất trùng CIL"),
    source_id: str = Query(default=""),
    section_id: str = Query(default=""),
    subgroup: str = Query(default=""),
    item_type: str = Query(default=""),
    q: str = Query(default=""),
):
    """Xuất báo cáo pháp lý sang định dạng Excel (.xlsx) đa bảng tính chuyên nghiệp."""
    mode_clean = (mode or "catalog").strip().lower()
    if mode_clean not in {"catalog", "matches"}:
        raise HTTPException(status_code=400, detail="Chế độ xuất không hợp lệ ('catalog' hoặc 'matches').")

    engine = get_engine()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"DANH_MUC_PHAP_LY_{'TRUNG_CIL_' if mode_clean == 'matches' else ''}{timestamp}.xlsx"
    output_path = OUTPUT_DIR / filename

    try:
        engine.export_to_excel(
            output_path=output_path,
            mode=mode_clean,
            source_id=source_id,
            section_id=section_id,
            subgroup=subgroup,
            item_type=item_type,
            q=q
        )
    except Exception as e:
        logger.error("Lỗi xuất Excel pháp lý: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi kết xuất Excel pháp lý: {str(e)}")

    if not output_path.exists():
        raise HTTPException(status_code=500, detail="Không thể tạo tệp Excel xuất bản.")

    return FileResponse(
        str(output_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@legal_router.get("/health")
@legal_router.get("/legal/health")
def legal_router_health():
    """Kiểm tra trạng thái hoạt động của phân hệ Pháp lý Hóa chất."""
    engine = get_engine()
    stats = engine.get_catalog_stats()
    return {
        "status": "ok",
        "module": "Chemical Legal Compliance & Intelligence",
        "total_records": stats.get("total_records", 0),
        "unique_cas": stats.get("unique_cas", 0),
        "engine_ready": True
    }
