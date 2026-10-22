"""
core/hse_excel_exporter.py — Professional Multi-Sheet Excel Exporter for HSE Reports.

Generates enterprise-grade .xlsx workbooks with:
1. Sheet 1: 📊 DASHBOARD with KPI summary cards, linked summary tables, and embedded Bar/Doughnut charts.
2. Sheet 2: 📋 Tổng Hợp Lỗi (11 standardized columns with direct thumbnail image embedding, zero #REF!).
3. Sheets 3+: Departmental breakdowns (🏭 Sản xuất, 📦 Bán hàng, 🔬 Kỹ thuật) with dedicated tab colors.
Strictly omits any "Mức độ rủi ro / 风险等级" columns.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import openpyxl
from openpyxl.chart import BarChart, DoughnutChart, Reference
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

logger = logging.getLogger("hse_excel_exporter")

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
HSE_DATA_DIR = Path(__file__).resolve().parent / "data" / "hse"
DEFAULT_DEFECTS_JSON = HSE_DATA_DIR / "extracted_defects.json"
DEFAULT_IMAGES_DIR = HSE_DATA_DIR / "extracted_images"

# Standard departmental theme styles (Tab color, Banner BG, Sub BG, Sub Text, Icon)
DEPT_STYLES = [
    ("F97316", "C2410C", "FFEDD5", "9A3412", "🏭"),  # Orange (Production)
    ("10B981", "047857", "D1FAE5", "065F46", "📦"),  # Emerald (Sales/Warehouse)
    ("8B5CF6", "6D28D9", "EDE9FE", "5B21B6", "🔬"),  # Purple (Tech/Lab)
    ("0284C7", "0369A1", "E0F2FE", "075985", "🔧"),  # Blue (Maintenance)
    ("EC4899", "BE185D", "FCE7F3", "9D174D", "🏢"),  # Pink (Admin/HR)
    ("F59E0B", "B45309", "FEF3C7", "78350F", "⚡"),  # Amber (Electrical/EHS)
    ("DC2626", "991B1B", "FEE2E2", "7F1D1D", "🧯"),  # Red (Fire/Emergency)
]


def sanitize_sheet_title(name: str, max_length: int = 31) -> str:
    """
    Sanitize worksheet title for Excel:
    - Replaces '/' with ' - ' or formats 'A / B' as 'B (A)'.
    - Strips forbidden characters: \\ / ? * : [ ]
    - Slices to max_length (<= 31 characters).
    - Cleans single quotes and leading/trailing whitespace.
    """
    if not name or not isinstance(name, str):
        return "Sheet"

    s = name.strip()
    if "/" in s:
        parts = [p.strip() for p in s.split("/") if p.strip()]
        if len(parts) == 2:
            s = f"{parts[1]} ({parts[0]})"
        else:
            s = " - ".join(parts)

    s = re.sub(r'[\\/*?:\[\]]', '-', s)
    s = s.strip(" '\"")
    s = re.sub(r'\s*-\s*', '-', s)
    s = re.sub(r'\s+', ' ', s).strip()

    if not s:
        s = "Bộ phận"

    return s[:max_length].strip()


def get_unique_sheet_title(base_title: str, existing_titles: Set[str], max_length: int = 31) -> str:
    """Ensure worksheet title is unique among existing sheets and strictly <= 31 chars."""
    cleaned = sanitize_sheet_title(base_title, max_length)
    if cleaned not in existing_titles:
        existing_titles.add(cleaned)
        return cleaned

    for i in range(2, 100):
        suffix = f"_{i}"
        truncated = cleaned[: max_length - len(suffix)] + suffix
        if truncated not in existing_titles:
            existing_titles.add(truncated)
            return truncated
    return cleaned[:max_length]


def clean_zh(s: str) -> str:
    """Sanitize Chinese text by removing internal line breaks and awkward spaces."""
    if not s:
        return ""
    s = re.sub(r'[\r\n]+', ' ', str(s)).strip()
    s = re.sub(r'(?<=[\u4e00-\u9fff，。；！？、（）《》])\s+(?=[\u4e00-\u9fff，。；！？、（）《》])', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def clean_vn(s: str) -> str:
    """Sanitize Vietnamese text by removing internal line breaks and normalizing spaces."""
    if not s:
        return ""
    s = re.sub(r'[\r\n]+', ' ', str(s)).strip()
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def categorize_hse(txt: str) -> str:
    """Categorize HSE issue into 4 standard industrial domains."""
    t = (txt or "").lower()
    if any(k in t for k in ["pccc", "chữa cháy", "báo cháy", "thoát hiểm", "cầu thang", "hành lang di chuyển", "灭火", "报警", "疏散", "逃生"]):
        return "PCCC & Thoát hiểm / 消防安全"
    if any(k in t for k in ["hóa chất", "dung môi", "sơn", "thùng phuy", "nắp ren", "đọng nước", "bột", "máy khuấy", "máy sấy", "化学", "溶剂", "油漆", "铁桶", "螺纹盖", "积水", "干燥机"]):
        return "An toàn Hóa chất & Thiết bị / 化学品与设备"
    if any(k in t for k in ["lối đi", "pallet", "tấm ván", "nghiêng", "bỏ lại", "gầm máy", "ruột gà", "đường đi", "通道", "垫板", "木托盘", "电缆"]):
        return "An toàn Hiện trường / 现场安全"
    return "5S & Vệ sinh Công nghiệp / 5S与环境卫生"


def normalize_department(d_zh: str = "", d_vn: str = "", dept_key: str = "") -> str:
    """Normalize department string to standard bilingual label."""
    combined = f"{d_zh} {d_vn} {dept_key}".lower()
    if any(k in combined for k in ["sản xuất", "san-xuat", "生产"]):
        return "生产部 / Sản xuất"
    if any(k in combined for k in ["bán hàng", "ban-hang", "营业", "kho", "vận chuyển"]):
        return "营业部 / Bán hàng"
    if any(k in combined for k in ["kỹ thuật", "ky-thuat", "技术", "lab", "rd", "r&d"]):
        return "技术部 / Kỹ thuật"
    
    # Fallback formatting
    zh_part = clean_zh(d_zh) or "生产部"
    vn_part = clean_vn(d_vn) or "Sản xuất"
    return f"{zh_part} / {vn_part}"


class HSEExcelExporter:
    """High-fidelity multi-sheet HSE Excel report builder."""

    def __init__(self, font_family: str = "Segoe UI"):
        self.font_family = font_family
        self.thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )
        self.header_border = Border(
            left=Side(style='thin', color='1E3A8A'),
            right=Side(style='thin', color='1E3A8A'),
            top=Side(style='thin', color='1E3A8A'),
            bottom=Side(style='medium', color='1E3A8A')
        )
        self.double_bottom_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='double', color='0F172A')
        )

    def _prepare_defects_data(self, payload: Optional[Dict[str, Any]] = None, temp_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """Extract and normalize defects data from payload or fallback dataset."""
        processed_defects: List[Dict[str, Any]] = []

        findings = payload.get("findings", []) if payload else []
        meta = payload.get("metadata", {}) if payload else {}
        from core.hse_report_engine import parse_flexible_date
        d_obj = parse_flexible_date(meta.get("date") or "2026-09-30")
        clean_date_str = d_obj.strftime("%Y-%m-%d")
        report_month = d_obj.strftime("%Y-%m")

        # Check if dynamic findings are provided and valid
        valid_findings = [f for f in findings if (f.get("issueVi") or f.get("issueZh") or f.get("aiHint"))]

        for idx, f in enumerate(valid_findings, 1):
            code = f"HSE-{report_month.replace('-', '')[2:]}-{idx:02d}"
            dept = normalize_department(
                f.get("departmentZh", ""),
                f.get("departmentVi", ""),
                f.get("departmentKey", "")
            )
            zh_issue = clean_zh(f.get("issueZh") or f.get("aiHint") or "")
            vn_issue = clean_vn(f.get("issueVi") or f.get("suggestion") or "")
            category = categorize_hse(zh_issue + " " + vn_issue)
            improved = bool(f.get("improved", False))
            status = "Cải thiện / 已改善" if improved else "Chưa cải thiện / 未改善"
            improve_date = f.get("recheckDate", "") if improved else ""
            note = clean_vn(f.get("note") or f.get("suggestion") or "")

            # Handle image null-safely
            img_path = ""
            img_data = f.get("imageData") or ""
            if img_data and isinstance(img_data, str) and temp_dir:
                try:
                    clean_data = img_data.strip()
                    if "," in clean_data:
                        header, b64 = clean_data.split(",", 1)
                    else:
                        header, b64 = "", clean_data
                    clean_b64 = re.sub(r"\s+", "", b64)
                    if clean_b64:
                        img_bytes = base64.b64decode(clean_b64)
                        if len(img_bytes) > 0 and len(img_bytes) <= 30 * 1024 * 1024:
                            ext = ".png" if "png" in header.lower() else ".jpg"
                            tmp_img = os.path.join(temp_dir, f"finding_{idx}{ext}")
                            with open(tmp_img, "wb") as ifile:
                                ifile.write(img_bytes)
                            if os.path.exists(tmp_img) and os.path.getsize(tmp_img) > 0:
                                img_path = tmp_img
                except Exception as e:
                    logger.warning(f"Failed to decode defect image safely: {e}")
                    img_path = ""
            elif f.get("imagePath") and os.path.exists(str(f["imagePath"])):
                img_path = str(f["imagePath"])

            processed_defects.append({
                "idx": idx,
                "code": code,
                "date": f.get("date") or clean_date_str,
                "month": report_month,
                "department": dept,
                "category": category,
                "zh_issue": zh_issue,
                "vn_issue": vn_issue,
                "img_path": img_path,
                "drive_view_url": f.get("driveViewUrl") or f.get("driveDirectUrl") or "",
                "status": status,
                "improve_date": improve_date,
                "note": note
            })

        # Also collect failed checklist items from the 26 inspection items
        checklist = payload.get("checklist", []) if payload else []
        failed_items = [c for c in checklist if c.get("status") == "fail"]
        seen_issues = {d.get("vn_issue", "").strip().lower() for d in processed_defects if d.get("vn_issue")}

        for c in failed_items:
            vn_issue = clean_vn(c.get("issueVi") or "Chưa đạt tiêu chuẩn an toàn EHS (Cần khắc phục)")
            zh_issue = clean_zh(c.get("issueZh") or "未达到EHS安全标准 (需整改)")
            if vn_issue.strip().lower() in seen_issues:
                continue
            seen_issues.add(vn_issue.strip().lower())

            r_num = c.get("row") or (len(processed_defects) + 1)
            code = f"HSE-{report_month.replace('-', '')[2:]}-CK{r_num}"
            dept = normalize_department("", "Sản xuất", "san-xuat")
            category = categorize_hse(zh_issue + " " + vn_issue)
            improved = bool(c.get("improved", False))
            status = "Cải thiện / 已改善" if improved else "Chưa cải thiện / 未改善"

            processed_defects.append({
                "idx": len(processed_defects) + 1,
                "code": code,
                "date": clean_date_str,
                "month": report_month,
                "department": dept,
                "category": category,
                "zh_issue": zh_issue,
                "vn_issue": vn_issue,
                "img_path": "",
                "drive_view_url": "",
                "status": status,
                "improve_date": clean_date_str if improved else "",
                "note": "Hạng mục kiểm tra 26 tiêu chuẩn xưởng ZhanChen"
            })

        # Fallback to standard 17 defects dataset ONLY if no findings and no failed checklist items
        if not processed_defects:
            raw_defects = []
            if DEFAULT_DEFECTS_JSON.exists():
                try:
                    with open(DEFAULT_DEFECTS_JSON, "r", encoding="utf-8") as jf:
                        raw_defects = json.load(jf)
                except Exception:
                    raw_defects = []

            img_map = [
                "p5_img2_IM48.jpg", "p5_img3_IM49.jpg", "p6_img2_IM52.jpg", "p6_img3_IM53.jpg",
                "p7_img2_IM56.jpg", "p7_img3_IM57.jpg", "p8_img2_IM60.jpg", "p8_img3_IM61.jpg",
                "p9_img2_IM64.jpg", "p9_img3_IM65.jpg", "p10_img2_IM68.jpg", "p10_img3_IM69.jpg",
                "p11_img2_IM72.jpg", "p11_img3_IM73.jpg", "p12_img2_IM76.jpg", "p12_img3_IM77.jpg",
                "p13_img2_IM80.jpg"
            ]

            for idx, d in enumerate(raw_defects, 1):
                code = f"HSE-2609-{idx:02d}"
                dept = normalize_department(d.get("zh_dept", ""), d.get("vn_dept", ""))
                zh_issue = clean_zh(d.get("zh_issue", ""))
                vn_issue = clean_vn(d.get("vn_issue", ""))
                category = categorize_hse(zh_issue + " " + vn_issue)
                status = "Cải thiện / 已改善" if idx == 1 else "Chưa cải thiện / 未改善"
                improve_date = "2026-10-21" if idx == 1 else ""
                note = "Đã dọn dẹp và sắp xếp gọn gàng mẫu thí nghiệm" if idx == 1 else ""

                img_name = img_map[idx - 1] if idx - 1 < len(img_map) else ""
                img_path = str(DEFAULT_IMAGES_DIR / img_name) if img_name and (DEFAULT_IMAGES_DIR / img_name).exists() else ""

                processed_defects.append({
                    "idx": idx,
                    "code": code,
                    "date": d.get("date", "2026-09-30"),
                    "month": "2026-09",
                    "department": dept,
                    "category": category,
                    "zh_issue": zh_issue,
                    "vn_issue": vn_issue,
                    "img_path": img_path,
                    "status": status,
                    "improve_date": improve_date,
                    "note": note
                })

        return processed_defects

    def generate_workbook(self, payload: Optional[Dict[str, Any]] = None) -> openpyxl.Workbook:
        """Construct the complete multi-sheet openpyxl Workbook."""
        with tempfile.TemporaryDirectory() as temp_dir:
            processed_defects = self._prepare_defects_data(payload, temp_dir)
            total_items = len(processed_defects)
            last_row = 4 + total_items

            wb = openpyxl.Workbook()

            # Data headers definition (11 columns strictly without Risk Level)
            data_headers = [
                ("A", "Mã lỗi\n编号", 15),
                ("B", "Ngày ghi nhận\n记录日期", 14),
                ("C", "Tháng\n月份", 12),
                ("D", "Bộ phận\n部门", 22),
                ("E", "Nhóm lỗi HSE\n隐患类别", 26),
                ("F", "Mô tả chi tiết (Tiếng Trung)\n详细描述 (中文)", 46),
                ("G", "Mô tả chi tiết (Tiếng Việt)\n详细描述 (越南语)", 46),
                ("H", "Hình ảnh hiện trường\n现场图片", 24),
                ("I", "Trạng thái\n状态", 20),
                ("J", "Ngày cải thiện\n改善日期", 15),
                ("K", "Ghi chú & Đối sách\n备注与改善对策", 26)
            ]

            # Status styling
            fill_done = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
            font_done = Font(name=self.font_family, size=9.5, bold=True, color="065F46")
            fill_pending = PatternFill(start_color="FFEDD5", end_color="FFEDD5", fill_type="solid")
            font_pending = Font(name=self.font_family, size=9.5, bold=True, color="9A3412")
            fill_processing = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
            font_processing = Font(name=self.font_family, size=9.5, bold=True, color="92400E")

            # =================================================================
            # SHEET 1: 📊 DASHBOARD
            # =================================================================
            ws_dash = wb.active
            ws_dash.title = "📊 DASHBOARD"
            ws_dash.sheet_properties.tabColor = "1E40AF"
            ws_dash.views.sheetView[0].showGridLines = False

            # Top Banners
            ws_dash.merge_cells("B2:M2")
            b2 = ws_dash["B2"]
            b2.value = "BÁO CÁO QUẢN TRỊ & PHÂN TÍCH LỖI AN TOÀN HSE (EHS EXECUTIVE DASHBOARD)"
            b2.fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
            b2.font = Font(name=self.font_family, size=15, bold=True, color="FFFFFF")
            b2.alignment = Alignment(horizontal="center", vertical="center")
            ws_dash.row_dimensions[2].height = 42

            meta_date = payload.get("metadata", {}).get("date") if payload else "2026-09-30"
            period_text = f"Kỳ báo cáo: Tháng {meta_date[:7]} (HSE安全隐患汇总看板)" if meta_date else "Kỳ báo cáo: Tháng 09/2026 (HSE安全隐患汇总看板)"

            ws_dash.merge_cells("B3:M3")
            b3 = ws_dash["B3"]
            b3.value = f"CÔNG TY TNHH VISION NEW MATERIALS VIỆT NAM  |  {period_text}"
            b3.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
            b3.font = Font(name=self.font_family, size=11, bold=True, color="E0E7FF")
            b3.alignment = Alignment(horizontal="center", vertical="center")
            ws_dash.row_dimensions[3].height = 28
            ws_dash.row_dimensions[4].height = 14

            # KPI Cards (Rows 5-7)
            kpis = [
                ("B", "C", "TỔNG SỐ LỖI GHI NHẬN / 总隐患数量", f"=COUNTA('📋 Tổng Hợp Lỗi'!A5:A{last_row})", "1E40AF", "DBEAFE", "1E40AF", "0"),
                ("E", "F", "CẢI THIỆN / 已改善
已改善完成", f'=COUNTIF(\'📋 Tổng Hợp Lỗi\'!I5:I{last_row}, "*Cải thiện*")', "065F46", "D1FAE5", "065F46", "0"),
                ("H", "I", "CHƯA CẢI THIỆN / 未改善
待处理/未改善", f'=COUNTIF(\'📋 Tổng Hợp Lỗi\'!I5:I{last_row}, "*Chưa cải thiện*")', "92400E", "FEF3C7", "92400E", "0"),
                ("K", "L", "TỶ LỆ HOÀN THÀNH / 整改完成率", "=IF(B6>0, E6/B6, 0)", "5B21B6", "EDE9FE", "5B21B6", "0.0%")
            ]
            ws_dash.row_dimensions[5].height = 26
            ws_dash.row_dimensions[6].height = 38
            ws_dash.row_dimensions[7].height = 6

            for c1, c2, title, formula, top_color, bg_color, text_color, num_fmt in kpis:
                ws_dash.merge_cells(f"{c1}5:{c2}5")
                t_cell = ws_dash[f"{c1}5"]
                t_cell.value = title
                t_cell.fill = PatternFill(start_color=top_color, end_color=top_color, fill_type="solid")
                t_cell.font = Font(name=self.font_family, size=9.5, bold=True, color="FFFFFF")
                t_cell.alignment = Alignment(horizontal="center", vertical="center")

                ws_dash.merge_cells(f"{c1}6:{c2}6")
                v_cell = ws_dash[f"{c1}6"]
                v_cell.value = formula
                v_cell.fill = PatternFill(start_color=bg_color, end_color=bg_color, fill_type="solid")
                v_cell.font = Font(name=self.font_family, size=20, bold=True, color=text_color)
                v_cell.alignment = Alignment(horizontal="center", vertical="center")
                v_cell.number_format = num_fmt

                for col_l in [c1, c2]:
                    for r_idx in [5, 6]:
                        ws_dash[f"{col_l}{r_idx}"].border = self.thin_border

            ws_dash.row_dimensions[8].height = 16

            # Summary Table 1: Department Statistics
            ws_dash.merge_cells("B9:F9")
            t1_head = ws_dash["B9"]
            t1_head.value = "1. THỐNG KÊ LỖI & TIẾN ĐỘ KHẮC PHỤC THEO BỘ PHẬN (按部门统计)"
            t1_head.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
            t1_head.font = Font(name=self.font_family, size=10.5, bold=True, color="FFFFFF")
            t1_head.alignment = Alignment(horizontal="left", vertical="center", indent=1)
            ws_dash.row_dimensions[9].height = 26

            t1_cols = [
                ("B", "Bộ phận / 部门"),
                ("C", "Tổng lỗi / 总数"),
                ("D", "Cải thiện / 已改善"),
                ("E", "Chưa cải thiện / 未改善"),
                ("F", "Tỷ lệ hoàn thành / 完成率")
            ]
            ws_dash.row_dimensions[10].height = 28
            for col_l, col_name in t1_cols:
                c = ws_dash[f"{col_l}10"]
                c.value = col_name
                c.fill = PatternFill(start_color="3B82F6", end_color="3B82F6", fill_type="solid")
                c.font = Font(name=self.font_family, size=9.5, bold=True, color="FFFFFF")
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                c.border = self.header_border

            dept_rows = [
                ("生产部 / Sản xuất", 11),
                ("营业部 / Bán hàng", 12),
                ("技术部 / Kỹ thuật", 13)
            ]
            for d_name, r_idx in dept_rows:
                ws_dash.row_dimensions[r_idx].height = 24
                ws_dash[f"B{r_idx}"] = d_name
                ws_dash[f"B{r_idx}"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
                ws_dash[f"C{r_idx}"] = f"=COUNTIF('📋 Tổng Hợp Lỗi'!$D$5:$D${last_row}, B{r_idx})"
                ws_dash[f"D{r_idx}"] = f'=COUNTIFS(\'📋 Tổng Hợp Lỗi\'!$D$5:$D${last_row}, B{r_idx}, \'📋 Tổng Hợp Lỗi\'!$I$5:$I${last_row}, "*Cải thiện*")'
                ws_dash[f"E{r_idx}"] = f'=COUNTIFS(\'📋 Tổng Hợp Lỗi\'!$D$5:$D${last_row}, B{r_idx}, \'📋 Tổng Hợp Lỗi\'!$I$5:$I${last_row}, "*Chưa cải thiện*")'
                ws_dash[f"F{r_idx}"] = f"=IF(C{r_idx}>0, D{r_idx}/C{r_idx}, 0)"
                ws_dash[f"F{r_idx}"].number_format = "0.0%"

                for col_l, _ in t1_cols:
                    cell = ws_dash[f"{col_l}{r_idx}"]
                    cell.font = Font(name=self.font_family, size=9.5)
                    cell.border = self.thin_border
                    if col_l != "B":
                        cell.alignment = Alignment(horizontal="center", vertical="center")

            # Table 1 Total Row
            ws_dash.row_dimensions[14].height = 26
            ws_dash["B14"] = "TỔNG CỘNG / 合计"
            ws_dash["B14"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
            ws_dash["C14"] = "=SUM(C11:C13)"
            ws_dash["D14"] = "=SUM(D11:D13)"
            ws_dash["E14"] = "=SUM(E11:E13)"
            ws_dash["F14"] = "=IF(C14>0, D14/C14, 0)"
            ws_dash["F14"].number_format = "0.0%"
            for col_l, _ in t1_cols:
                c = ws_dash[f"{col_l}14"]
                c.fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
                c.font = Font(name=self.font_family, size=9.5, bold=True, color="0F172A")
                c.border = self.double_bottom_border
                if col_l != "B":
                    c.alignment = Alignment(horizontal="center", vertical="center")

            # Summary Table 2: Category Statistics
            ws_dash.merge_cells("H9:L9")
            t2_head = ws_dash["H9"]
            t2_head.value = "2. PHÂN LOẠI THEO NHÓM LỖI HSE (按隐患类别分类)"
            t2_head.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
            t2_head.font = Font(name=self.font_family, size=10.5, bold=True, color="FFFFFF")
            t2_head.alignment = Alignment(horizontal="left", vertical="center", indent=1)

            ws_dash["H10"] = "Nhóm lỗi HSE / 隐患类别"
            ws_dash.merge_cells("I10:J10")
            ws_dash["I10"] = "Số lượng / 数量"
            ws_dash.merge_cells("K10:L10")
            ws_dash["K10"] = "Tỷ trọng / 占比"

            for c_letter in ["H", "I", "J", "K", "L"]:
                cell = ws_dash[f"{c_letter}10"]
                cell.fill = PatternFill(start_color="3B82F6", end_color="3B82F6", fill_type="solid")
                cell.font = Font(name=self.font_family, size=9.5, bold=True, color="FFFFFF")
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = self.header_border

            cat_rows = [
                ("PCCC & Thoát hiểm / 消防安全", 11),
                ("An toàn Hóa chất & Thiết bị / 化学品与设备", 12),
                ("An toàn Hiện trường / 现场安全", 13),
                ("5S & Vệ sinh Công nghiệp / 5S与环境卫生", 14)
            ]
            for c_name, r_idx in cat_rows:
                ws_dash.row_dimensions[r_idx].height = 24
                ws_dash[f"H{r_idx}"] = c_name
                ws_dash[f"H{r_idx}"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
                ws_dash.merge_cells(f"I{r_idx}:J{r_idx}")
                ws_dash[f"I{r_idx}"] = f"=COUNTIF('📋 Tổng Hợp Lỗi'!$E$5:$E${last_row}, H{r_idx})"
                ws_dash[f"I{r_idx}"].alignment = Alignment(horizontal="center", vertical="center")
                ws_dash.merge_cells(f"K{r_idx}:L{r_idx}")
                ws_dash[f"K{r_idx}"] = f"=IF($I$15>0, I{r_idx}/$I$15, 0)"
                ws_dash[f"K{r_idx}"].alignment = Alignment(horizontal="center", vertical="center")
                ws_dash[f"K{r_idx}"].number_format = "0.0%"

                for c_let in ["H", "I", "J", "K", "L"]:
                    ws_dash[f"{c_let}{r_idx}"].font = Font(name=self.font_family, size=9.5)
                    ws_dash[f"{c_let}{r_idx}"].border = self.thin_border

            # Table 2 Total Row
            ws_dash.row_dimensions[15].height = 26
            ws_dash["H15"] = "TỔNG CỘNG / 合计"
            ws_dash["H15"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
            ws_dash.merge_cells("I15:J15")
            ws_dash["I15"] = "=SUM(I11:I14)"
            ws_dash["I15"].alignment = Alignment(horizontal="center", vertical="center")
            ws_dash.merge_cells("K15:L15")
            ws_dash["K15"] = "=SUM(K11:K14)"
            ws_dash["K15"].alignment = Alignment(horizontal="center", vertical="center")
            ws_dash["K15"].number_format = "0.0%"
            for c_let in ["H", "I", "J", "K", "L"]:
                c = ws_dash[f"{c_let}15"]
                c.fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
                c.font = Font(name=self.font_family, size=9.5, bold=True, color="0F172A")
                c.border = self.double_bottom_border

            # Dashboard Charts
            # Chart 1: Stacked Bar Chart
            chart1 = BarChart()
            chart1.type = "col"
            chart1.grouping = "stacked"
            chart1.overlap = 100
            chart1.title = "TIẾN ĐỘ KHẮC PHỤC THEO BỘ PHẬN (按部门整改进度对比)"
            chart1.style = 10
            c1_data = Reference(ws_dash, min_col=4, min_row=10, max_col=5, max_row=13)
            c1_cats = Reference(ws_dash, min_col=2, min_row=11, max_row=13)
            chart1.add_data(c1_data, titles_from_data=True)
            chart1.set_categories(c1_cats)
            chart1.height = 14
            chart1.width = 17
            chart1.x_axis.title = "Bộ phận / 部门"
            chart1.y_axis.title = "Số lượng lỗi / 隐患数"
            ws_dash.add_chart(chart1, "B17")

            # Chart 2: Doughnut Chart
            chart2 = DoughnutChart()
            chart2.title = "CƠ CẤU NHÓM LỖI HSE (隐患类别分布占比)"
            chart2.style = 2
            c2_data = Reference(ws_dash, min_col=9, min_row=10, max_row=14)
            c2_cats = Reference(ws_dash, min_col=8, min_row=11, max_row=14)
            chart2.add_data(c2_data, titles_from_data=True)
            chart2.set_categories(c2_cats)
            chart2.height = 14
            chart2.width = 16
            ws_dash.add_chart(chart2, "H17")

            # Dashboard Column Widths
            dash_widths = {
                "A": 4, "B": 24, "C": 15, "D": 17, "E": 15, "F": 18,
                "G": 4, "H": 30, "I": 10, "J": 10, "K": 10, "L": 10, "M": 4
            }
            for col_l, w in dash_widths.items():
                ws_dash.column_dimensions[col_l].width = w

            # =================================================================
            # SHEET 2: 📋 Tổng Hợp Lỗi
            # =================================================================
            ws_all = wb.create_sheet(title="📋 Tổng Hợp Lỗi")
            ws_all.sheet_properties.tabColor = "10B981"

            # Data Validation for Status Column
            dv_status = DataValidation(
                type="list",
                formula1='"Cải thiện / 已改善,Chưa cải thiện / 未改善"',
                allow_blank=True
            )
            dv_status.error = "Vui lòng chọn trạng thái hợp lệ từ danh sách!"
            dv_status.errorTitle = "Trạng thái không hợp lệ"
            ws_all.add_data_validation(dv_status)
            dv_status.add(f"I5:I{last_row}")

            # Sheet 2 Banners
            ws_all.merge_cells("A1:K1")
            h1 = ws_all["A1"]
            h1.value = f"BẢNG TỔNG HỢP CHI TIẾT LỖI HSE TOÀN CÔNG TY - THÁNG {meta_date[:7]}"
            h1.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
            h1.font = Font(name=self.font_family, size=14, bold=True, color="FFFFFF")
            h1.alignment = Alignment(horizontal="center", vertical="center")
            ws_all.row_dimensions[1].height = 36

            ws_all.merge_cells("A2:K2")
            h2 = ws_all["A2"]
            h2.value = "CÔNG TY TNHH VISION NEW MATERIALS VIỆT NAM | Đã nhúng trực tiếp ảnh hiện trường & Chuẩn hóa dữ liệu song ngữ"
            h2.fill = PatternFill(start_color="3B82F6", end_color="3B82F6", fill_type="solid")
            h2.font = Font(name=self.font_family, size=10.5, bold=True, color="FFFFFF")
            h2.alignment = Alignment(horizontal="center", vertical="center")
            ws_all.row_dimensions[2].height = 24
            ws_all.row_dimensions[3].height = 10

            # Headers Row 4
            ws_all.row_dimensions[4].height = 36
            for col_l, col_name, width in data_headers:
                c = ws_all[f"{col_l}4"]
                c.value = col_name
                if col_l == "H":
                    c.fill = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
                    c.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
                else:
                    c.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
                    c.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                c.border = self.header_border
                ws_all.column_dimensions[col_l].width = width

            # Data Rows
            ws_all.auto_filter.ref = f"A4:K{last_row}"
            for idx, item in enumerate(processed_defects, 1):
                r_num = 4 + idx
                ws_all.row_dimensions[r_num].height = 85

                ws_all[f"A{r_num}"] = item["code"]
                ws_all[f"B{r_num}"] = item["date"]
                ws_all[f"C{r_num}"] = item["month"]
                ws_all[f"D{r_num}"] = item["department"]
                ws_all[f"E{r_num}"] = item["category"]
                ws_all[f"F{r_num}"] = item["zh_issue"]
                ws_all[f"G{r_num}"] = item["vn_issue"]
                ws_all[f"H{r_num}"] = ""
                ws_all[f"I{r_num}"] = item["status"]
                ws_all[f"J{r_num}"] = item["improve_date"]
                ws_all[f"K{r_num}"] = item["note"]

                # Embed Image directly (Zero #REF! formula error)
                if item["img_path"] and os.path.exists(item["img_path"]):
                    try:
                        img_obj = OpenpyxlImage(item["img_path"])
                        img_obj.width = 118
                        img_obj.height = 80
                        ws_all.add_image(img_obj, f"H{r_num}")
                        ws_all[f"H{r_num}"] = ""
                    except Exception as img_err:
                        logger.warning(f"Failed to embed defect image: {img_err}")
                        ws_all[f"H{r_num}"] = f"🔗 Xem ảnh Drive ({item['month']})" if item.get("drive_view_url") else "Không có ảnh\n无图片"
                else:
                    ws_all[f"H{r_num}"] = f"🔗 Xem ảnh Drive ({item['month']})" if item.get("drive_view_url") else "Không có ảnh\n无图片"

                if item.get("drive_view_url"):
                    ws_all[f"H{r_num}"].hyperlink = item["drive_view_url"]

                for col_l, _, _ in data_headers:
                    cell = ws_all[f"{col_l}{r_num}"]
                    cell.font = Font(name=self.font_family, size=9.5)
                    cell.border = self.thin_border
                    if col_l == "H":
                        if item.get("drive_view_url") and not (item["img_path"] and os.path.exists(item["img_path"])):
                            cell.font = Font(name=self.font_family, size=9, bold=True, color="2563EB", underline="single")
                        elif ws_all[f"H{r_num}"].value == "Không có ảnh\n无图片":
                            cell.font = Font(name=self.font_family, size=8.5, italic=True, color="94A3B8")
                    if col_l in ["A", "B", "C", "H", "J"]:
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    elif col_l in ["D", "E"]:
                        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    elif col_l in ["F", "G", "K"]:
                        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                    elif col_l == "I":
                        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                        if "Cải thiện" in item["status"] and "Chưa" not in item["status"]:
                            cell.fill = fill_done
                            cell.font = font_done
                        elif "Chưa cải thiện" in item["status"] or "Chờ xử lý" in item["status"]:
                            cell.fill = fill_pending
                            cell.font = font_pending
                        else:
                            cell.fill = fill_processing
                            cell.font = font_processing

            ws_all.freeze_panes = "A5"
            ws_all.auto_filter.ref = f"A4:K{last_row}"

            # =================================================================
            # SHEETS 3+: MULTI-SHEET PER DEPARTMENT (DYNAMIC & SANITIZED)
            # =================================================================
            existing_titles = {ws_dash.title, ws_all.title}

            # Discover unique departments from processed defects
            unique_depts: List[str] = []
            for item in processed_defects:
                d = item.get("department") or "生产部 / Sản xuất"
                if d not in unique_depts:
                    unique_depts.append(d)

            if not unique_depts:
                unique_depts = ["生产部 / Sản xuất"]

            for d_idx, dept_key in enumerate(unique_depts):
                dept_items = [d for d in processed_defects if d.get("department") == dept_key]
                if not dept_items:
                    continue

                style_idx = d_idx % len(DEPT_STYLES)
                tab_col, banner_bg, sub_bg, sub_text, default_icon = DEPT_STYLES[style_idx]

                # Match specialized theme based on department keywords
                dept_lower = dept_key.lower()
                icon = default_icon
                if any(k in dept_lower for k in ["sản xuất", "生产"]):
                    tab_col, banner_bg, sub_bg, sub_text, icon = DEPT_STYLES[0]
                elif any(k in dept_lower for k in ["bán hàng", "kho", "vận chuyển", "仓储", "营业"]):
                    tab_col, banner_bg, sub_bg, sub_text, icon = DEPT_STYLES[1]
                elif any(k in dept_lower for k in ["kỹ thuật", "thí nghiệm", "lab", "rd", "技术"]):
                    tab_col, banner_bg, sub_bg, sub_text, icon = DEPT_STYLES[2]
                elif any(k in dept_lower for k in ["bảo trì", "cơ điện", "sửa chữa", "维修"]):
                    tab_col, banner_bg, sub_bg, sub_text, icon = DEPT_STYLES[3]
                elif any(k in dept_lower for k in ["hành chính", "nhân sự", "văn phòng", "行政"]):
                    tab_col, banner_bg, sub_bg, sub_text, icon = DEPT_STYLES[4]

                # Sanitize sheet title strictly <= 31 chars without forbidden characters (/ \ ? * : [ ])
                clean_dept = sanitize_sheet_title(dept_key, max_length=26)
                raw_sheet_title = f"{icon} {clean_dept}".strip()
                sheet_title = get_unique_sheet_title(raw_sheet_title, existing_titles, max_length=31)

                ws_dept = wb.create_sheet(title=sheet_title)
                ws_dept.sheet_properties.tabColor = tab_col

                dv_dept = DataValidation(
                    type="list",
                    formula1='"Cải thiện / 已改善,Chưa cải thiện / 未改善"',
                    allow_blank=True
                )
                ws_dept.add_data_validation(dv_dept)
                dv_dept.add(f"I5:I{4 + len(dept_items)}")

                # Banner
                ws_dept.merge_cells("A1:K1")
                d_h1 = ws_dept["A1"]
                d_h1.value = f"DANH SÁCH THEO DÕI LỖI HSE - BỘ PHẬN: {dept_key.upper()}"
                d_h1.fill = PatternFill(start_color=banner_bg, end_color=banner_bg, fill_type="solid")
                d_h1.font = Font(name=self.font_family, size=13.5, bold=True, color="FFFFFF")
                d_h1.alignment = Alignment(horizontal="center", vertical="center")
                ws_dept.row_dimensions[1].height = 36

                ws_dept.merge_cells("A2:K2")
                d_h2 = ws_dept["A2"]
                d_h2.value = f"Trích xuất riêng cho bộ phận {dept_key} ({len(dept_items)} hạng mục) — Phục vụ đôn đốc & kiểm tra khắc phục hiện trường"
                d_h2.fill = PatternFill(start_color=sub_bg, end_color=sub_bg, fill_type="solid")
                d_h2.font = Font(name=self.font_family, size=10.5, bold=True, color=sub_text)
                d_h2.alignment = Alignment(horizontal="center", vertical="center")
                ws_dept.row_dimensions[2].height = 24
                ws_dept.row_dimensions[3].height = 10

                # Headers Row 4
                ws_dept.row_dimensions[4].height = 36
                for col_l, col_name, width in data_headers:
                    c = ws_dept[f"{col_l}4"]
                    c.value = col_name
                    c.fill = PatternFill(start_color=banner_bg, end_color=banner_bg, fill_type="solid")
                    c.font = Font(name=self.font_family, size=9.5, bold=True, color="FFFFFF")
                    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    c.border = self.header_border
                    ws_dept.column_dimensions[col_l].width = width

                # Data Rows
                for d_i, item in enumerate(dept_items, 1):
                    r_num = 4 + d_i
                    ws_dept.row_dimensions[r_num].height = 70

                    ws_dept[f"A{r_num}"] = item["code"]
                    ws_dept[f"B{r_num}"] = item["date"]
                    ws_dept[f"C{r_num}"] = item["month"]
                    ws_dept[f"D{r_num}"] = item["department"]
                    ws_dept[f"E{r_num}"] = item["category"]
                    ws_dept[f"F{r_num}"] = item["zh_issue"]
                    ws_dept[f"G{r_num}"] = item["vn_issue"]
                    ws_dept[f"H{r_num}"] = ""
                    ws_dept[f"I{r_num}"] = item["status"]
                    ws_dept[f"J{r_num}"] = item["improve_date"]
                    ws_dept[f"K{r_num}"] = item["note"]

                    if item["img_path"] and os.path.exists(item["img_path"]):
                        try:
                            img_dept = OpenpyxlImage(item["img_path"])
                            img_dept.width = 118
                            img_dept.height = 80
                            ws_dept.add_image(img_dept, f"H{r_num}")
                            ws_dept[f"H{r_num}"] = ""
                        except Exception as img_err:
                            logger.warning(f"Failed to embed dept image: {img_err}")
                            ws_dept[f"H{r_num}"] = f"🔗 Xem ảnh Drive ({item['month']})" if item.get("drive_view_url") else "Không có ảnh\n无图片"
                    else:
                        ws_dept[f"H{r_num}"] = f"🔗 Xem ảnh Drive ({item['month']})" if item.get("drive_view_url") else "Không có ảnh\n无图片"

                    if item.get("drive_view_url"):
                        ws_dept[f"H{r_num}"].hyperlink = item["drive_view_url"]

                    for col_l, _, _ in data_headers:
                        cell = ws_dept[f"{col_l}{r_num}"]
                        cell.font = Font(name=self.font_family, size=9.5)
                        cell.border = self.thin_border
                        if col_l == "H":
                            if item.get("drive_view_url") and not (item["img_path"] and os.path.exists(item["img_path"])):
                                cell.font = Font(name=self.font_family, size=9, bold=True, color="2563EB", underline="single")
                            elif ws_dept[f"H{r_num}"].value == "Không có ảnh\n无图片":
                                cell.font = Font(name=self.font_family, size=8.5, italic=True, color="94A3B8")
                        if col_l in ["A", "B", "C", "H", "J"]:
                            cell.alignment = Alignment(horizontal="center", vertical="center")
                        elif col_l in ["D", "E"]:
                            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                        elif col_l in ["F", "G", "K"]:
                            cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                        elif col_l == "I":
                            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                            if "Cải thiện" in item["status"] and "Chưa" not in item["status"]:
                                cell.fill = fill_done
                                cell.font = font_done
                            elif "Chưa cải thiện" in item["status"] or "Chờ xử lý" in item["status"]:
                                cell.fill = fill_pending
                                cell.font = font_pending
                            else:
                                cell.fill = fill_processing
                                cell.font = font_processing

                ws_dept.freeze_panes = "A5"
                ws_dept.auto_filter.ref = f"A4:K{4 + len(dept_items)}"

            return wb

    def export_bytes(self, payload: Optional[Dict[str, Any]] = None) -> bytes:
        """Export workbook to bytes buffer."""
        wb = self.generate_workbook(payload)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.getvalue()

    def export_to_file(self, target_path: Union[str, Path], payload: Optional[Dict[str, Any]] = None) -> Path:
        """Export workbook and save directly to file path."""
        target_path = Path(target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        wb = self.generate_workbook(payload)
        wb.save(str(target_path))
        return target_path
