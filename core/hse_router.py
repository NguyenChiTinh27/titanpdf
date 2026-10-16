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
import shutil
import subprocess
import sys
import urllib.parse
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

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


class OpenFolderRequest(BaseModel):
    path: Optional[str] = Field(default="")


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

    payload_dict = payload.model_dump()
    raw_date = payload.metadata.date
    if raw_date:
        try:
            clean_date_str = raw_date.split("T")[0].replace("Z", "")
            date.fromisoformat(clean_date_str)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Ngày kiểm tra không hợp lệ: {raw_date}")

    for item in payload.checklist:
        if item.status == "fail" and not item.issueVi and not item.issueZh:
            raise HTTPException(status_code=400, detail=f"Mục checklist dòng {item.row} chưa đủ vấn đề Việt–Trung.")

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
    target_path = REPORTS_DIR / filename

    actual_path, was_locked = safe_write_bytes(target_path, docx_bytes)

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
        "Content-Disposition": f'attachment; filename="{actual_path.name}"',
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
    result = analyze_image_ai(req.get_image_data(), req.get_hint(), req.context, req.model)
    return result


@hse_router.post("/ai_batch_analyze")
@hse_router.post("/batch_ai_analyze")
def ai_batch_analyze_endpoint(req: AIBatchAnalyzeRequest):
    from core.hse_report_engine import analyze_image_ai
    results = []
    for item in req.items:
        res = analyze_image_ai(item.get_image_data(), item.get_hint())
        results.append({"id": item.id, **res})
    return {"results": results}


@hse_router.post("/polish")
def polish_endpoint(req: PolishRequest):
    from core.hse_report_engine import professionalize_hse
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Nội dung không được để trống.")
    try:
        options = professionalize_hse(req.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"options": options}


@hse_router.post("/translate")
def translate_endpoint(req: TranslateRequest):
    from core.hse_report_engine import translate_vi_to_zh
    translated = translate_vi_to_zh(req.text, req.kind or "text")
    return {"translation": translated, "translated": translated}


@hse_router.get("/config")
@hse_router.get("/ai_config")
def get_ai_config():
    data = {}
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    api_key = data.get("deepseek_api_key", "")
    masked = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else ("***" if api_key else "")
    return {
        "api_key": api_key,
        "deepseek_api_key_masked": masked,
        "base_url": data.get("deepseek_base_url", "https://api.deepseek.com/v1"),
        "model": data.get("deepseek_model", "DeepSeek-V4.1-Flash"),
        "endpoint": data.get("deepseek_base_url", "https://api.deepseek.com/v1")
    }


@hse_router.post("/config")
@hse_router.post("/ai_config")
def save_ai_config(cfg: AIConfigModel):
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

    # Google Drive Direct Storage Sync
    drive_dir = detect_google_drive()
    drive_saved = False
    drive_report_path = None
    if drive_dir and drive_dir.exists():
        try:
            target_drive_folder = drive_dir if drive_dir.name == "HSE_BaoCao" else (drive_dir / "HSE_BaoCao")
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


@hse_router.post("/open_folder")
@hse_router.post("/drive/open")
def open_folder_endpoint(req: Optional[OpenFolderRequest] = None):
    folder_path = (req.path if req and req.path else str(REPORTS_DIR))
    p = Path(folder_path).resolve()
    p.mkdir(parents=True, exist_ok=True)
    if hasattr(os, "startfile") and os.name == "nt":
        try:
            os.startfile(str(p))
        except Exception:
            pass
    return {"success": True, "folder": str(folder_path)}


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
