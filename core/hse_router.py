"""
core/hse_router.py — FastAPI APIRouter for HSE Report Studio.

Mounted under prefix `/api/hse` with aliases for `/api/*` compatibility.
Handles:
- Checklist schema query (26 items, 5 categories).
- DOCX report generation & export with Windows file lock resolver (X-Drive-Locked header).
- DOCX report preview.
- Prior-month DOCX decompiler (import_docx).
- AI drafting, batch analysis, polish text assistant, translation.
- DeepSeek AI configuration (masked key).
- Report library persistence (save, list, load, open folder).
- Google Drive detection and synchronization.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from core.auth_rbac import get_current_role, require_owner

# Dynamic path resolution matching server.py
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
    DATA_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = BASE_DIR

REPORTS_DIR = Path(DATA_DIR) / "data" / "hse_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = Path(DATA_DIR) / "settings.json"

hse_router = APIRouter(tags=["HSE Report Studio"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class ReportMetadata(BaseModel):
    date: Optional[str] = Field(default="", description="Inspection date (YYYY-MM-DD)")
    prevDate: Optional[str] = Field(default="", description="Previous inspection date")
    inspectors: Optional[str] = Field(default="", description="Inspector names")
    company: Optional[str] = Field(default="越南展辰新材料有限公司", description="Company name")
    title: Optional[str] = Field(default="", description="Report title")
    department: Optional[str] = Field(default="", description="Factory department")


class ChecklistItem(BaseModel):
    row: int = Field(..., description="Checklist row index (3..32)")
    category: Optional[str] = Field(default="")
    content: Optional[str] = Field(default="")
    method: Optional[str] = Field(default="")
    status: Optional[str] = Field(default="pass")
    issueVi: Optional[str] = Field(default="")
    issueZh: Optional[str] = Field(default="")
    improved: Optional[bool] = Field(default=False)


class FindingItem(BaseModel):
    id: Optional[str] = Field(default="")
    departmentKey: Optional[str] = Field(default="san-xuat")
    departmentVi: Optional[str] = Field(default="Sản xuất")
    departmentZh: Optional[str] = Field(default="生产部")
    aiHint: Optional[str] = Field(default="")
    issueVi: Optional[str] = Field(default="")
    issueZh: Optional[str] = Field(default="")
    suggestion: Optional[str] = Field(default="")
    imageData: Optional[str] = Field(default="")
    imageName: Optional[str] = Field(default="")
    improved: Optional[bool] = Field(default=False)
    imageAfterData: Optional[str] = Field(default="")
    imageAfterName: Optional[str] = Field(default="")
    date: Optional[str] = Field(default="")
    recheckDate: Optional[str] = Field(default="")
    note: Optional[str] = Field(default="")
    driveFileId: Optional[str] = Field(default="")
    driveDirectUrl: Optional[str] = Field(default="")
    driveViewUrl: Optional[str] = Field(default="")
    driveFolderId: Optional[str] = Field(default="")
    driveFolderUrl: Optional[str] = Field(default="")
    driveStatus: Optional[str] = Field(default="")
    afterDriveFileId: Optional[str] = Field(default="")
    afterDriveDirectUrl: Optional[str] = Field(default="")
    afterDriveViewUrl: Optional[str] = Field(default="")
    afterDriveStatus: Optional[str] = Field(default="")


class GenerateReportRequest(BaseModel):
    id: Optional[str] = Field(default="")
    mode: Optional[str] = Field(default="inspection")
    reportType: Optional[str] = Field(default=None)
    globalAiHint: Optional[str] = Field(default="")
    metadata: ReportMetadata = Field(default_factory=ReportMetadata)
    checklist: List[ChecklistItem] = Field(default_factory=list)
    findings: List[FindingItem] = Field(default_factory=list)

    def get_effective_mode(self) -> str:
        if self.reportType and self.reportType in ("inspection", "improvement"):
            return self.reportType
        if self.mode and self.mode in ("inspection", "improvement"):
            return self.mode
        return "inspection"


class SaveReportRequest(GenerateReportRequest):
    save_docx: Optional[bool] = Field(default=True)
    folder: Optional[str] = Field(default="")


class AIAnalyzeRequest(BaseModel):
    image: Optional[str] = Field(default="")
    imageData: Optional[str] = Field(default="")
    hint: Optional[str] = Field(default="")
    aiHint: Optional[str] = Field(default="")
    model: Optional[str] = Field(default="DeepSeek-V4.1-Flash")
    context: Optional[str] = Field(default="")

    def get_image_data(self) -> str:
        return self.imageData or self.image or ""

    def get_hint(self) -> str:
        return self.aiHint or self.hint or ""


class AIBatchItem(BaseModel):
    id: Optional[str] = Field(default="")
    image: Optional[str] = Field(default="")
    imageData: Optional[str] = Field(default="")
    hint: Optional[str] = Field(default="")
    aiHint: Optional[str] = Field(default="")

    def get_image_data(self) -> str:
        return self.imageData or self.image or ""

    def get_hint(self) -> str:
        return self.aiHint or self.hint or ""


class AIBatchAnalyzeRequest(BaseModel):
    items: List[AIBatchItem] = Field(default_factory=list)


class PolishRequest(BaseModel):
    text: str = Field(...)


class TranslateRequest(BaseModel):
    text: str = Field(...)
    kind: Optional[str] = Field(default="text")


class AIConfigModel(BaseModel):
    api_key: Optional[str] = Field(default="")
    base_url: Optional[str] = Field(default="https://api.deepseek.com/v1")
    model: Optional[str] = Field(default="DeepSeek-V4.1-Flash")


class UploadImageRequest(BaseModel):
    imageData: str
    date: Optional[str] = ""
    departmentVi: Optional[str] = "Sản xuất"
    departmentKey: Optional[str] = "san-xuat"
    itemType: Optional[str] = "finding"
    row: Optional[int] = None
    findingIndex: Optional[int] = 1
    photoKind: Optional[str] = "before"
    customFilename: Optional[str] = None


class OpenFolderRequest(BaseModel):
    path: Optional[str] = Field(default="")
    month: Optional[str] = Field(default="")


class OpenFileRequest(BaseModel):
    path: str = Field(...)


class DriveConfigRequest(BaseModel):
    custom_path: Optional[str] = Field(default=None)
    auto_backup_on_export: Optional[bool] = Field(default=None)


# =============================================================================
# Drive Detection Helper
# =============================================================================

def detect_google_drive() -> Optional[Path]:
    custom_path = None
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                custom_path = cfg.get("hse_drive_path")
        except Exception:
            pass
    if custom_path and Path(custom_path).exists():
        return Path(custom_path)
    candidates = [
        Path("G:/Drive của tôi/HSE_ZhanChen_Storage"),
        Path("G:/My Drive/HSE_ZhanChen_Storage"),
        Path("G:/Drive của tôi/HSE_BaoCao"),
        Path("G:/Drive của tôi"),
        Path("G:/My Drive/HSE_BaoCao"),
        Path("G:/My Drive"),
        Path("G:/Drive của tôi/HSE_NhatKy_HienTruong/BaoCaoThang"),
        Path("G:/My Drive/HSE_NhatKy_HienTruong/BaoCaoThang"),
        Path("G:/"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


_monthly_drive_urls: Dict[str, str] = {}


class HSEStorageManager:
    """Manages HSE_ZhanChen_Storage local & Google Drive directory hierarchies."""

    @staticmethod
    def normalize_department_slug(dept_vi: str = "", dept_key: str = "") -> str:
        s = f"{dept_vi} {dept_key}".lower()
        if any(k in s for k in ["sản xuất", "san-xuat", "sanxuat", "xưởng"]):
            return "SanXuat"
        if any(k in s for k in ["kỹ thuật", "ky-thuat", "kythuat", "lab", "rd", "r&d"]):
            return "KyThuat"
        if any(k in s for k in ["kho", "vận chuyển", "kho-hang", "khovan", "kho hàng"]):
            return "KhoVan"
        if any(k in s for k in ["bán hàng", "ban-hang", "kinh doanh"]):
            return "BanHang"
        if any(k in s for k in ["bảo trì", "bao-tri", "cơ điện"]):
            return "BaoTri"
        if any(k in s for k in ["hành chính", "hanh-chinh", "nhân sự"]):
            return "HanhChinh"
        if any(k in s for k in ["qc", "qa", "chất lượng"]):
            return "QC"
        clean = re.sub(r'[^a-zA-Z0-9]', '', dept_vi)
        return clean or "BoPhan"

    @staticmethod
    def get_storage_root() -> Path:
        """Returns the base storage root directory: GDrive mounted path or local data dir."""
        gdrive = detect_google_drive()
        if gdrive and gdrive.exists():
            root = gdrive if gdrive.name == "HSE_ZhanChen_Storage" else (gdrive / "HSE_ZhanChen_Storage")
        else:
            root = Path(DATA_DIR) / "data" / "HSE_ZhanChen_Storage"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def get_or_create_monthly_folder(year_month: str) -> Tuple[Path, Path]:
        """
        Creates/returns:
        (hinh_anh_dir, bao_cao_dir) under HSE_ZhanChen_Storage/{year_month}/
        """
        clean_ym = year_month.strip() if year_month else ""
        if not re.match(r'^\d{4}-\d{2}$', clean_ym):
            clean_ym = date.today().strftime("%Y-%m")

        root = HSEStorageManager.get_storage_root()
        month_dir = root / clean_ym
        img_dir = month_dir / "Hinh_Anh_Hien_Truong"
        rpt_dir = month_dir / "Bao_Cao_Xuat_File"

        img_dir.mkdir(parents=True, exist_ok=True)
        rpt_dir.mkdir(parents=True, exist_ok=True)

        # Also ensure local app cache exists if root is on G:
        local_cache_img = Path(DATA_DIR) / "data" / "HSE_ZhanChen_Storage" / clean_ym / "Hinh_Anh_Hien_Truong"
        local_cache_rpt = Path(DATA_DIR) / "data" / "HSE_ZhanChen_Storage" / clean_ym / "Bao_Cao_Xuat_File"
        local_cache_img.mkdir(parents=True, exist_ok=True)
        local_cache_rpt.mkdir(parents=True, exist_ok=True)

        # Cloud Drive monthly folder sync via GAS
        try:
            from core.msds_gas_sync import MSDSGASSyncService
            if MSDSGASSyncService.is_configured() and clean_ym not in _monthly_drive_urls:
                res = MSDSGASSyncService.get_or_create_monthly_folder(clean_ym)
                if res and (res.get("folderUrl") or res.get("folder_url")):
                    _monthly_drive_urls[clean_ym] = res.get("folderUrl") or res.get("folder_url")
        except Exception:
            pass

        return img_dir, rpt_dir

    @staticmethod
    def build_standard_image_filename(
        date_str: str,
        dept_vi: str = "Sản xuất",
        dept_key: str = "san-xuat",
        item_type: str = "finding",
        row: Optional[int] = None,
        finding_index: int = 1,
        photo_kind: str = "before"
    ) -> str:
        """
        Generates standard name:
        [YYYYMMDD]_[BoPhan]_[DongChecklist/Loi]_[Truoc/SauCaiThien].jpg
        """
        clean_date = (date_str or date.today().isoformat()).split("T")[0].replace("-", "")[:8]
        dept_slug = HSEStorageManager.normalize_department_slug(dept_vi, dept_key)

        if item_type == "checklist" and row:
            item_tag = f"Dong{row}"
        else:
            item_tag = f"Loi_{finding_index:02d}"

        kind_tag = "SauCaiThien" if (photo_kind in ["after", "sau"]) else "Truoc"

        return f"{clean_date}_{dept_slug}_{item_tag}_{kind_tag}.jpg"


# =============================================================================
# Route Handlers
# =============================================================================

@hse_router.get("/health")
def get_hse_health():
    return {"status": "ok", "module": "hse_report_studio"}


@hse_router.get("/checklist_schema")
@hse_router.get("/checklist")
def get_checklist_schema():
    from core.hse_report_engine import CHECKLIST_SECTIONS
    return {
        "sections": CHECKLIST_SECTIONS,
        "total_items": 26,
        "today": date.today().isoformat()
    }


@hse_router.post("/generate_docx")
@hse_router.post("/export")
def generate_docx_endpoint(payload: GenerateReportRequest):
    from core.hse_report_engine import build_docx, safe_write_bytes

    raw_date = payload.metadata.date
    if raw_date:
        try:
            clean_date_str = raw_date.split("T")[0].replace("Z", "")
            date.fromisoformat(clean_date_str)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Ngày kiểm tra không hợp lệ: {raw_date}")

    # Auto-fill missing bilingual issues for failed checklist items instead of failing
    for item in payload.checklist:
        if item.status == "fail":
            if not item.issueVi or not item.issueVi.strip():
                item.issueVi = "Chưa đạt tiêu chuẩn an toàn EHS (Cần khắc phục)"
            if not item.issueZh or not item.issueZh.strip():
                item.issueZh = "未达到EHS安全标准 (需整改)"

    payload_dict = payload.model_dump()

    try:
        docx_bytes = build_docx(payload_dict)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo tài liệu Word: {exc}")

    insp_date = payload.metadata.date or date.today().isoformat()
    clean_date = insp_date.split("T")[0]
    suffix = "_Improvement" if payload.get_effective_mode() == "improvement" else ""
    filename = f"HSE_Report_{clean_date}{suffix}.docx"
    bilingual_filename = f"越南展辰_HSE_办巡厂报告_{clean_date}{suffix}.docx"
    quoted_bilingual = urllib.parse.quote(bilingual_filename)
    target_path = REPORTS_DIR / filename

    actual_path, was_locked = safe_write_bytes(target_path, docx_bytes)

    # Save to monthly HSE_ZhanChen_Storage/{year_month}/Bao_Cao_Xuat_File/
    year_month = clean_date[:7] if len(clean_date) >= 7 else date.today().strftime("%Y-%m")
    _, rpt_dir_word = HSEStorageManager.get_or_create_monthly_folder(year_month)
    std_docx_name = f"Bao_Cao_HSE_{clean_date}{suffix}.docx"
    safe_write_bytes(rpt_dir_word / std_docx_name, docx_bytes)

    # Google Drive auto-backup check
    drive_backup = False
    drive_path = detect_google_drive()
    drive_locked = was_locked
    drive_filename = actual_path.name
    if drive_path:
        try:
            month_dir = drive_path / clean_date[:7]
            month_dir.mkdir(parents=True, exist_ok=True)
            drive_file, drive_locked = safe_write_bytes(month_dir / filename, docx_bytes)
            drive_filename = drive_file.name
            drive_backup = True
        except Exception:
            pass

    headers = {
        "Content-Disposition": f'attachment; filename="{actual_path.name}"; filename*=UTF-8\'\'{quoted_bilingual}',
        "X-Drive-Locked": "true" if was_locked else "false",
        "X-Drive-File": urllib.parse.quote(drive_filename),
        "X-Drive-Backup": "true" if drive_backup else "false",
        "Access-Control-Expose-Headers": "Content-Disposition, X-Drive-Locked, X-Drive-File, X-Drive-Backup"
    }
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers
    )


@hse_router.post("/export_excel")
@hse_router.get("/export_excel")
async def export_excel_endpoint(request: Request):
    from core.hse_excel_exporter import HSEExcelExporter
    from core.hse_report_engine import safe_write_bytes

    payload_dict = None
    if request.method == "POST":
        try:
            body = await request.body()
            if body:
                payload_dict = json.loads(body)
        except Exception:
            payload_dict = None

    try:
        exporter = HSEExcelExporter()
        excel_bytes = exporter.export_bytes(payload_dict)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo tài liệu Excel: {exc}")

    meta = (payload_dict or {}).get("metadata", {})
    raw_date = meta.get("date") or "2026-09-30"
    clean_date = raw_date.split("T")[0]
    parts = clean_date.split("-")
    if len(parts) >= 2:
        month_year_str = f"{parts[1]}_{parts[0]}"
    else:
        month_year_str = "09_2026"
    filename = f"HSE_Report_{month_year_str}.xlsx"
    target_path = REPORTS_DIR / filename

    actual_path, was_locked = safe_write_bytes(target_path, excel_bytes)
    quoted_filename = urllib.parse.quote(filename)

    # Save to monthly HSE_ZhanChen_Storage/{year_month}/Bao_Cao_Xuat_File/
    year_month = clean_date[:7] if len(clean_date) >= 7 else date.today().strftime("%Y-%m")
    _, rpt_dir_excel = HSEStorageManager.get_or_create_monthly_folder(year_month)
    std_excel_name = f"Tong_Hop_Loi_HSE_{month_year_str}.xlsx"
    safe_write_bytes(rpt_dir_excel / std_excel_name, excel_bytes)

    # Google Drive auto-backup check
    drive_backup = False
    drive_path = detect_google_drive()
    drive_locked = was_locked
    drive_filename = actual_path.name
    if drive_path:
        try:
            month_dir = drive_path / clean_date[:7]
            month_dir.mkdir(parents=True, exist_ok=True)
            drive_file, drive_locked = safe_write_bytes(month_dir / filename, excel_bytes)
            drive_filename = drive_file.name
            drive_backup = True
        except Exception:
            pass

    headers = {
        "Content-Disposition": f'attachment; filename="{actual_path.name}"; filename*=UTF-8\'\'{quoted_filename}',
        "X-Drive-Locked": "true" if was_locked else "false",
        "X-Drive-File": urllib.parse.quote(drive_filename),
        "X-Drive-Backup": "true" if drive_backup else "false",
        "Access-Control-Expose-Headers": "Content-Disposition, X-Drive-Locked, X-Drive-File, X-Drive-Backup"
    }
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )


@hse_router.post("/preview_docx")
def preview_docx_endpoint(payload: GenerateReportRequest):
    from core.hse_report_engine import build_docx, safe_write_bytes
    payload_dict = payload.model_dump()
    try:
        docx_bytes = build_docx(payload_dict)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    temp_name = f"preview_{payload.id or 'current'}.docx"
    temp_path = REPORTS_DIR / temp_name
    safe_write_bytes(temp_path, docx_bytes)
    return {
        "success": True,
        "filename": temp_name,
        "findings_count": len(payload.findings),
        "pages_estimate": max(1, (len(payload.findings) + 1) // 2) + 4
    }


@hse_router.post("/import_docx")
async def import_docx_endpoint(request: Request):
    from core.hse_report_engine import parse_docx_to_report
    content_type = request.headers.get("content-type", "").lower()
    file_bytes = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        upload_file: Optional[UploadFile] = form.get("file")
        if not upload_file:
            raise HTTPException(status_code=400, detail="Thiếu tệp tải lên (file parameter).")
        file_bytes = await upload_file.read()
    else:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Dữ liệu JSON không hợp lệ.")
        file_data = body.get("fileData")
        file_path = body.get("path")
        if file_data:
            if "," in file_data:
                file_data = file_data.split(",", 1)[1]
            try:
                file_bytes = base64.b64decode(file_data)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Dữ liệu Base64 không hợp lệ: {exc}")
        elif file_path and Path(file_path).exists():
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        else:
            raise HTTPException(status_code=400, detail="Cần cung cấp fileData (Base64) hoặc path.")

    try:
        parsed_report = parse_docx_to_report(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Không thể giải mã tệp docx: {exc}")

    return {"success": True, "report": parsed_report}


@hse_router.post("/ai_analyze")
def ai_analyze_endpoint(req: AIAnalyzeRequest):
    from core.hse_report_engine import analyze_image_ai
    try:
        result = analyze_image_ai(req.get_image_data(), req.get_hint(), req.context, req.model)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi AI Vision: {str(exc)}")


@hse_router.post("/ai_batch_analyze")
@hse_router.post("/batch_ai_analyze")
def ai_batch_analyze_endpoint(req: AIBatchAnalyzeRequest):
    from core.hse_report_engine import analyze_image_ai
    results = []
    for item in req.items:
        try:
            res = analyze_image_ai(item.get_image_data(), item.get_hint())
            results.append({"id": item.id, **res})
        except Exception as exc:
            results.append({"id": item.id, "error": str(exc)})
    return {"results": results}


@hse_router.post("/polish")
def polish_endpoint(req: PolishRequest):
    from core.hse_report_engine import professionalize_hse
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Nội dung không được để trống.")
    try:
        context = getattr(req, "context", "") or ""
        options = professionalize_hse(req.text, context)
        return {"options": options}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi AI viết chuyên nghiệp: {str(exc)}")


@hse_router.post("/translate")
def translate_endpoint(req: TranslateRequest):
    from core.hse_report_engine import translate_vi_to_zh
    if not req.text or not req.text.strip():
        return {"translation": "", "translated": ""}
    try:
        translated = translate_vi_to_zh(req.text, req.kind or "text")
        return {"translation": translated, "translated": translated}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi dịch thuật: {str(exc)}")


@hse_router.get("/config")
@hse_router.get("/ai_config")
def get_ai_config(request: Request):
    from core.ai_text_engine import AITextEngine
    role = get_current_role(request)
    creds = AITextEngine.get_ai_credentials()
    api_key = creds.get("api_key", "")
    provider = creds.get("provider", "gemini")
    model = creds.get("model", "gemini-2.5-flash")
    base_url = creds.get("base_url", "")

    if role == "guest":
        return {
            "has_key": bool(api_key),
            "api_key": "",
            "deepseek_api_key_masked": "••••••••••••••••" if api_key else "",
            "provider": provider,
            "base_url": base_url,
            "model": model,
            "endpoint": base_url,
            "read_only": True
        }
    masked = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else ("***" if api_key else "")
    return {
        "has_key": bool(api_key),
        "api_key": api_key,
        "deepseek_api_key_masked": masked,
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "endpoint": base_url,
        "read_only": False
    }


@hse_router.post("/config")
@hse_router.post("/ai_config")
def save_ai_config(cfg: AIConfigModel, _: str = Depends(require_owner)):
    data = {}
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    if cfg.api_key:
        data["deepseek_api_key"] = cfg.api_key
    if cfg.base_url:
        data["deepseek_base_url"] = cfg.base_url
    if cfg.model:
        data["deepseek_model"] = cfg.model
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"success": True, "message": "Đã lưu cấu hình AI thành công."}


@hse_router.post("/save_report")
@hse_router.post("/reports/save")
def save_report_endpoint(req: SaveReportRequest):
    from core.hse_report_engine import build_docx, safe_write_bytes

    payload_dict = req.model_dump()
    report_id = req.id or f"hse_{int(datetime.now().timestamp()*1000)}"
    payload_dict["id"] = report_id
    payload_dict["reportType"] = req.get_effective_mode()
    insp_date = req.metadata.date or date.today().isoformat()
    clean_date = insp_date.split("T")[0]

    json_filename = f"HSE_Report_{clean_date}_{report_id}.json"
    json_path = REPORTS_DIR / json_filename
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload_dict, f, ensure_ascii=False, indent=2)

    docx_saved_path = None
    docx_bytes = None
    suffix = "_Improvement" if req.get_effective_mode() == "improvement" else ""
    docx_filename = f"HSE_Report_{clean_date}_{report_id}{suffix}.docx"
    try:
        docx_bytes = build_docx(payload_dict)
        docx_target = REPORTS_DIR / docx_filename
        actual_path, _ = safe_write_bytes(docx_target, docx_bytes)
        docx_saved_path = str(actual_path)
    except Exception as e:
        print(f"[HSE_SAVE_DOCX_ERROR] {e}", flush=True)

    # Save to monthly HSE_ZhanChen_Storage/{year_month}/
    year_month = clean_date[:7] if len(clean_date) >= 7 else date.today().strftime("%Y-%m")
    img_dir, rpt_dir = HSEStorageManager.get_or_create_monthly_folder(year_month)

    # 1. Save standard Word report and JSON into Bao_Cao_Xuat_File
    std_docx_name = f"Bao_Cao_HSE_{clean_date}{suffix}.docx"
    if docx_bytes:
        safe_write_bytes(rpt_dir / std_docx_name, docx_bytes)
    shutil.copy2(json_path, rpt_dir / json_filename)

    # 2. Extract and organize field images into Hinh_Anh_Hien_Truong
    for f_idx, finding in enumerate(req.findings, 1):
        for kind, d_field in [("before", "imageData"), ("after", "imageAfterData")]:
            img_val = getattr(finding, d_field, "") or ""
            if img_val and ("," in img_val or len(img_val) > 100):
                try:
                    b64_part = img_val.split(",", 1)[1] if "," in img_val else img_val
                    b64_bytes = base64.b64decode(re.sub(r'\s+', '', b64_part))
                    f_name = HSEStorageManager.build_standard_image_filename(
                        date_str=clean_date,
                        dept_vi=finding.departmentVi or "Sản xuất",
                        dept_key=finding.departmentKey or "san-xuat",
                        item_type="finding",
                        finding_index=f_idx,
                        photo_kind=kind
                    )
                    with open(img_dir / f_name, "wb") as img_f:
                        img_f.write(b64_bytes)
                except Exception:
                    pass

    # Google Drive Direct Storage Sync
    drive_dir = detect_google_drive()
    drive_saved = False
    drive_report_path = None
    if drive_dir and drive_dir.exists():
        try:
            target_drive_folder = drive_dir if drive_dir.name in ("HSE_ZhanChen_Storage", "HSE_BaoCao") else (drive_dir / "HSE_ZhanChen_Storage")
            target_drive_folder.mkdir(parents=True, exist_ok=True)
            # Copy JSON to Drive
            drive_json = target_drive_folder / json_filename
            shutil.copy2(json_path, drive_json)
            # Copy or write DOCX to Drive
            if docx_bytes:
                drive_docx = target_drive_folder / docx_filename
                safe_write_bytes(drive_docx, docx_bytes)
                drive_report_path = str(drive_docx)
            else:
                drive_report_path = str(drive_json)
            drive_saved = True
        except Exception as e:
            print(f"[HSE_DRIVE_SYNC_WARNING] Error syncing to drive: {e}", flush=True)

    return {
        "success": True,
        "id": report_id,
        "title": req.metadata.title or f"Báo cáo HSE {clean_date}",
        "filename": json_filename,
        "json_file": json_filename,
        "docx_file": docx_filename if docx_saved_path else None,
        "drive_saved": drive_saved,
        "drive_path": drive_report_path,
        "web_drive_url": "https://drive.google.com/drive/u/0/my-drive"
    }


@hse_router.get("/reports/download-docx/{filename}")
def download_report_docx_endpoint(filename: str):
    p = REPORTS_DIR / filename
    if not p.exists():
        drive_dir = detect_google_drive()
        if drive_dir:
            target_folder = drive_dir if drive_dir.name == "HSE_BaoCao" else (drive_dir / "HSE_BaoCao")
            p_drive = target_folder / filename
            if p_drive.exists():
                p = p_drive
    if not p.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp Word.")
    return FileResponse(
        str(p),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@hse_router.get("/reports")
@hse_router.get("/reports/list")
def list_reports_endpoint():
    reports = []
    for file in sorted(REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            clean_d = (data.get("metadata", {}).get("date") or "").split("T")[0]
            rep_id = data.get("id", file.stem)
            rep_type = data.get("reportType") or data.get("mode", "inspection")
            suffix = "_Improvement" if rep_type == "improvement" else ""
            
            # Check DOCX file
            docx_cand1 = f"HSE_Report_{clean_d}_{rep_id}{suffix}.docx"
            docx_cand2 = f"HSE_Report_{clean_d}{suffix}.docx"
            docx_found = None
            if (REPORTS_DIR / docx_cand1).exists():
                docx_found = docx_cand1
            elif (REPORTS_DIR / docx_cand2).exists():
                docx_found = docx_cand2

            reports.append({
                "id": rep_id,
                "title": data.get("metadata", {}).get("title") or f"Báo cáo HSE {clean_d or file.stem}",
                "date": clean_d,
                "reportType": rep_type,
                "findingsCount": len(data.get("findings", [])),
                "filename": file.name,
                "docx_file": docx_found,
                "size_kb": round(file.stat().st_size / 1024, 1),
                "mtime": file.stat().st_mtime
            })
        except Exception:
            pass
    return {"success": True, "reports": reports, "total": len(reports)}


@hse_router.get("/load_report/{filename}")
@hse_router.get("/reports/load")
def load_report_endpoint(filename: Optional[str] = None, id: Optional[str] = None):
    target = None
    target_identifier = filename or id
    if target_identifier:
        direct = REPORTS_DIR / target_identifier
        if direct.exists() and direct.is_file():
            target = direct
        else:
            for f in REPORTS_DIR.glob("*.json"):
                if target_identifier in f.name:
                    target = f
                    break

    if not target or not target.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy bản lưu báo cáo.")

    with open(target, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "reportType" not in data:
        data["reportType"] = data.get("mode", "inspection")
    return data


@hse_router.delete("/reports/{filename}")
@hse_router.delete("/reports/delete")
def delete_report_endpoint(filename: Optional[str] = None, id: Optional[str] = None):
    target_identifier = filename or id
    deleted = False
    if target_identifier:
        direct = REPORTS_DIR / target_identifier
        if direct.exists() and direct.is_file():
            direct.unlink()
            deleted = True
            docx_cand = direct.with_suffix(".docx")
            if docx_cand.exists():
                try:
                    docx_cand.unlink()
                except Exception:
                    pass
        else:
            for f in REPORTS_DIR.glob("*.json"):
                if target_identifier in f.name:
                    f.unlink()
                    deleted = True
                    docx_cand = f.with_suffix(".docx")
                    if docx_cand.exists():
                        try:
                            docx_cand.unlink()
                        except Exception:
                            pass
                    break
    if not deleted:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi để xóa.")
    return {"success": True, "message": "Đã xóa bản lưu thành công."}


@hse_router.post("/drive/upload_image")
@hse_router.post("/upload_image")
def upload_image_endpoint(req: UploadImageRequest):
    data_url = (req.imageData or "").strip()
    if not data_url:
        raise HTTPException(status_code=400, detail="Thiếu dữ liệu ảnh.")

    try:
        if "," in data_url:
            _, b64 = data_url.split(",", 1)
        else:
            b64 = data_url
        b64_clean = re.sub(r'\s+', '', b64)
        img_bytes = base64.b64decode(b64_clean)
        if len(img_bytes) == 0:
            raise ValueError("Dữ liệu ảnh rỗng.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể giải mã ảnh: {e}")

    # Determine date & month
    raw_date = (req.date or date.today().isoformat()).split("T")[0]
    year_month = raw_date[:7] if len(raw_date) >= 7 else date.today().strftime("%Y-%m")

    # Generate standardized filename: [YYYYMMDD]_[BoPhan]_[DongChecklist/Loi]_[Truoc/SauCaiThien].jpg
    filename = req.customFilename or HSEStorageManager.build_standard_image_filename(
        date_str=raw_date,
        dept_vi=req.departmentVi or "Sản xuất",
        dept_key=req.departmentKey or "san-xuat",
        item_type=req.itemType or "finding",
        row=req.row,
        finding_index=req.findingIndex or 1,
        photo_kind=req.photoKind or "before"
    )

    # 1. Save to local monthly storage hierarchy: HSE_ZhanChen_Storage/{year_month}/Hinh_Anh_Hien_Truong/
    img_dir, _ = HSEStorageManager.get_or_create_monthly_folder(year_month)
    local_file_path = img_dir / filename
    with open(local_file_path, "wb") as f:
        f.write(img_bytes)

    # Also save to local app cache folder if root was on G:
    cache_dir = Path(DATA_DIR) / "data" / "HSE_ZhanChen_Storage" / year_month / "Hinh_Anh_Hien_Truong"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / filename
    if cache_file != local_file_path:
        with open(cache_file, "wb") as f:
            f.write(img_bytes)

    # 2. Upload to Google Drive Cloud via GAS (if configured)
    drive_file_id = f"local_{year_month}_{filename}"
    drive_direct_url = f"/api/hse/image/{year_month}/{filename}"
    drive_view_url = f"https://drive.google.com/drive/u/0/my-drive"
    drive_folder_id = f"hse_{year_month}"
    drive_folder_url = f"https://drive.google.com/drive/u/0/my-drive"
    cloud_synced = False

    try:
        from core.msds_gas_sync import MSDSGASSyncService
        if MSDSGASSyncService.is_configured():
            gas_subfolder = f"HSE_Report_Images/{year_month}"
            res = MSDSGASSyncService.upload_file_to_drive(
                file_bytes=img_bytes,
                filename=filename,
                mime_type="image/jpeg",
                subfolder=gas_subfolder
            )
            if res and (res.get("fileId") or res.get("file_id") or res.get("success")):
                drive_file_id = res.get("fileId") or res.get("file_id") or drive_file_id
                drive_view_url = res.get("viewUrl") or res.get("view_url") or f"https://drive.google.com/file/d/{drive_file_id}/view"
                drive_direct_url = f"https://drive.google.com/uc?export=view&id={drive_file_id}"
                drive_folder_url = res.get("folderUrl") or res.get("folder_url") or drive_folder_url
                drive_folder_id = res.get("folderId") or res.get("folder_id") or drive_folder_id
                _monthly_drive_urls[year_month] = drive_folder_url
                cloud_synced = True
    except Exception as gas_err:
        print(f"[HSE_IMAGE_GAS_SYNC_WARN] {gas_err}", flush=True)

    return {
        "success": True,
        "filename": filename,
        "yearMonth": year_month,
        "driveFileId": drive_file_id,
        "driveDirectUrl": drive_direct_url,
        "driveViewUrl": drive_view_url,
        "driveFolderId": drive_folder_id,
        "driveFolderUrl": drive_folder_url,
        "localPath": str(local_file_path),
        "cloudSynced": cloud_synced
    }


@hse_router.get("/image/{year_month}/{filename}")
def get_hse_image_endpoint(year_month: str, filename: str):
    root = HSEStorageManager.get_storage_root()
    p = root / year_month / "Hinh_Anh_Hien_Truong" / filename
    if not p.exists():
        p = Path(DATA_DIR) / "data" / "HSE_ZhanChen_Storage" / year_month / "Hinh_Anh_Hien_Truong" / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail="Ảnh không tồn tại.")
    return FileResponse(p, media_type="image/jpeg")


@hse_router.post("/open_folder")
@hse_router.post("/drive/open")
def open_folder_endpoint(req: Optional[OpenFolderRequest] = None):
    month_str = (req.month if req and req.month else "").strip()
    if not month_str:
        month_str = date.today().strftime("%Y-%m")

    img_dir, rpt_dir = HSEStorageManager.get_or_create_monthly_folder(month_str)
    target_dir = rpt_dir.parent  # HSE_ZhanChen_Storage/{month_str}

    if hasattr(os, "startfile") and os.name == "nt":
        try:
            os.startfile(str(target_dir))
        except Exception:
            pass

    web_drive_url = _monthly_drive_urls.get(month_str) or "https://drive.google.com/drive/u/0/my-drive"
    return {
        "success": True,
        "month": month_str,
        "folder": str(target_dir),
        "webDriveUrl": web_drive_url
    }


@hse_router.post("/open_file")
@hse_router.post("/drive/open_file")
def open_file_endpoint(req: OpenFileRequest):
    p = Path(req.path).resolve()
    if not p.exists():
        raise HTTPException(status_code=404, detail="Tệp không tồn tại.")
    if hasattr(os, "startfile") and os.name == "nt":
        try:
            os.startfile(str(p))
        except Exception:
            pass
    return {"success": True, "file": str(p)}


@hse_router.get("/drive/status")
def drive_status_endpoint():
    drive = detect_google_drive()
    if drive and drive.exists():
        free_bytes = shutil.disk_usage(drive).free
        free_gb = round(free_bytes / (1024**3), 2)
        return {"available": True, "path": str(drive), "free_space_gb": free_gb}
    return {"available": False, "path": "", "free_space_gb": 0.0}


@hse_router.post("/drive/config")
def drive_config_endpoint(cfg: DriveConfigRequest):
    data = {}
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    if cfg.custom_path is not None:
        data["hse_drive_path"] = cfg.custom_path
    if cfg.auto_backup_on_export is not None:
        data["hse_auto_backup"] = cfg.auto_backup_on_export
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"success": True, "message": "Đã lưu cài đặt Google Drive."}


# =============================================================================
# DEFECT TRACKER APIS (/api/hse/defects/* & /api/hse/defect_image/*)
# =============================================================================

@hse_router.get("/defects")
def get_defects_endpoint(
    month: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None
):
    from core.hse_defect_tracker import DefectAggregatorService
    return DefectAggregatorService.aggregate_all_defects(
        month_filter=month,
        dept_filter=department,
        status_filter=status,
        search_query=search
    )


@hse_router.post("/defects/update")
def update_defect_endpoint(payload: Dict[str, Any]):
    from core.hse_defect_tracker import DefectAggregatorService, DefectUpdatePayload
    p = DefectUpdatePayload(**payload)
    return DefectAggregatorService.update_defect(p)


@hse_router.post("/defects/sync_gas")
@hse_router.get("/defects/sync_gas")
def sync_defects_gas_endpoint():
    from core.hse_defect_tracker import DefectAggregatorService
    return DefectAggregatorService.sync_with_gas()


@hse_router.get("/defects/export_master_excel")
@hse_router.post("/defects/export_master_excel")
async def export_master_excel_endpoint(
    request: Request,
    all: bool = True,
    month: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None
):
    from core.hse_defect_tracker import DefectAggregatorService, MasterHSEExcelExporter

    # If filtered export requested
    if not all and (month or department or status or search):
        data = DefectAggregatorService.aggregate_all_defects(
            month_filter=month,
            dept_filter=department,
            status_filter=status,
            search_query=search
        )
        defects = data["defects"]
        suffix = f"_{month}" if month and month != "all" else "_Filtered"
    else:
        data = DefectAggregatorService.aggregate_all_defects()
        defects = data["defects"]
        suffix = "_All_Months"

    exporter = MasterHSEExcelExporter()
    excel_bytes = exporter.export_master_bytes(defects)

    filename = f"Master_Theo_Doi_Loi_HSE_Toan_Cong_Ty{suffix}.xlsx"
    quoted_filename = urllib.parse.quote(filename)

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quoted_filename}',
        "Access-Control-Expose-Headers": "Content-Disposition"
    }
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )


@hse_router.get("/defect_image/{year_month}/{filename}")
def get_defect_image_endpoint(year_month: str, filename: str):
    # 1. Check extracted images baseline
    p1 = Path(BASE_DIR) / "core" / "data" / "hse" / "extracted_images" / filename
    if p1.exists():
        return FileResponse(p1, media_type="image/jpeg")

    # 2. Check storage hierarchy
    root = HSEStorageManager.get_storage_root()
    p2 = root / year_month / "Hinh_Anh_Hien_Truong" / filename
    if p2.exists():
        return FileResponse(p2, media_type="image/jpeg")

    p3 = Path(DATA_DIR) / "data" / "HSE_ZhanChen_Storage" / year_month / "Hinh_Anh_Hien_Truong" / filename
    if p3.exists():
        return FileResponse(p3, media_type="image/jpeg")

    raise HTTPException(status_code=404, detail="Ảnh sự cố không tồn tại.")

