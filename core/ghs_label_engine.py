"""
core/ghs_label_engine.py — GHS Decanting Label Maker & Multi-Format Print Engine
conforming to Circular 01/2026/TT-BCT (Ministry of Industry and Trade).

Capabilities:
1. Label Data Preparation:
   - Product name, product code, primary CAS, composition.
   - Facility identity: "Công ty TNHH Sơn ZhanChen (Việt Nam) - Phân Xưởng Pha Chế".
   - Decanting date (today), expiry date (+12 months), and batch lot number.
   - Signal word ("NGUY HIỂM / DANGER" or "CẢNH BÁO / WARNING" or "NON DG").
   - GHS hazard pictograms (GHS01 - GHS09) from vector SVGs or raster PNGs.
   - Hazard statements (H-codes) and Precautionary statements (P-codes).
   - Emergency hotlines (114 PCCC, 115 Y tế, ZhanChen EHS Hotline: 0274.376.8888).

2. Multi-Format HTML Generator:
   - Standalone printable HTML with isolated @media print rules.
   - 4 standard presets:
     * A4_4UP: 4 labels on A4 (2x2 grid, ~105mm x 148mm) for 5L-20L containers.
     * A5: 1 label on A5 (148mm x 210mm) for 200L drums and 1000L IBC totes.
     * DECAL_150: Industrial thermal decal 100mm x 150mm.
     * DECAL_75: Compact chemical decal 100mm x 75mm.
   - Graceful fallback for unknown presets to A4_4UP.

3. Vector PDF Generator:
   - Generates valid %PDF- vector documents using PyMuPDF (fitz) with Arial Unicode fonts.
   - High-DPI GHS diamond pictograms, custom red borders, and multi-label tiling.
"""

import os
import sys
import re
import html
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import fitz  # PyMuPDF

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GHS_TEMPLATES_DIR = PROJECT_ROOT / "core" / "ghs_templates"

DEFAULT_FACILITY = "Công ty TNHH Sơn ZhanChen (Việt Nam) - Phân Xưởng Pha Chế"
DEFAULT_HOTLINE = "PCCC: 114 | Cấp Cứu: 115 | ZhanChen EHS: 0274.376.8888"

STANDARD_PRESETS = {"A4_4UP", "A5", "DECAL_150", "DECAL_75"}

PRESET_CONFIG = {
    "A4_4UP": {
        "title": "A4 (4 nhãn / trang)",
        "desc": "Dán can & xô 5L – 20L",
        "w_mm": 210,
        "h_mm": 297,
        "labels_per_page": 4,
        "cols": 2,
        "rows": 2,
    },
    "A5": {
        "title": "A5 (1 nhãn / trang)",
        "desc": "Dán phuy 200L & bồn IBC 1000L",
        "w_mm": 148,
        "h_mm": 210,
        "labels_per_page": 1,
        "cols": 1,
        "rows": 1,
    },
    "DECAL_150": {
        "title": "Decal 100×150mm",
        "desc": "Tem mã vạch công nghiệp 4×6 inch",
        "w_mm": 100,
        "h_mm": 150,
        "labels_per_page": 1,
        "cols": 1,
        "rows": 1,
    },
    "DECAL_75": {
        "title": "Decal 100×75mm",
        "desc": "Tem nhỏ gọn chai lọ 500ml – 2L",
        "w_mm": 100,
        "h_mm": 75,
        "labels_per_page": 1,
        "cols": 1,
        "rows": 1,
    },
}

# Standard fallback H-statements if database field is blank
DEFAULT_H_STATEMENTS = {
    "GHS01": "H201: Chất nổ; nguy cơ nổ khối lớn.",
    "GHS02": "H225: Chất lỏng và hơi rất dễ cháy.",
    "GHS03": "H272: Có thể làm đám cháy dữ dội hơn; chất oxy hóa.",
    "GHS04": "H280: Chứa khí dưới áp suất; có thể nổ nếu bị đốt nóng.",
    "GHS05": "H314: Gây bỏng da nặng và tổn thương mắt.",
    "GHS06": "H301: Độc nếu nuốt phải. H331: Độc nếu hít phải.",
    "GHS07": "H315: Gây kích ứng da. H319: Gây kích ứng mắt nghiêm trọng.",
    "GHS08": "H304: Có thể tử vong nếu nuốt phải và đi vào đường thở.",
    "GHS09": "H411: Độc đối với đời sống thủy sinh có tác động lâu dài.",
    "NON DG": "Không phát hiện mối nguy hại đặc biệt theo phân loại GHS.",
}

# Standard fallback P-statements if database field is blank
DEFAULT_P_STATEMENTS = {
    "GHS01": "P210: Tránh xa nhiệt/tia lửa/ngọn lửa trần. P280: Trang bị bảo hộ chống nổ chuyên dụng.",
    "GHS02": "P210: Tránh xa nguồn nhiệt/tia lửa/ngọn lửa trần. P233: Đóng chặt thùng chứa. P280: Mang găng tay/quần áo bảo hộ/kính bảo hộ. P303+P361+P353: NẾU DÍNH VÀO DA: Cởi bỏ ngay quần áo nhiễm bẩn, rửa sạch bằng nước. P403+P235: Bảo quản nơi thoáng mát.",
    "GHS03": "P220: Để cách xa quần áo và các chất dễ cháy khác. P280: Mang trang bị bảo hộ thích hợp.",
    "GHS04": "P410+P403: Bảo quản nơi thông thoáng, tránh ánh sáng mặt trời.",
    "GHS05": "P260: Không hít bụi/khói/hơi. P280: Mang găng tay/kính bảo hộ chống hóa chất. P305+P351+P338: NẾU VÀO MẮT: Rửa cẩn thận bằng nước trong 15 phút. P310: Gọi ngay cấp cứu.",
    "GHS06": "P264: Rửa sạch tay sau khi tiếp xúc. P270: Không ăn uống hoặc hút thuốc khi sử dụng. P301+P310: NẾU NUỐT PHẢI: Gọi ngay Trung tâm cấp cứu.",
    "GHS07": "P261: Tránh hít phải hơi/bụi. P280: Mang trang bị bảo hộ cá nhân. P305+P351+P338: NẾU VÀO MẮT: Rửa cẩn thận bằng nước trong vài phút.",
    "GHS08": "P201: Nhận hướng dẫn đặc biệt trước khi sử dụng. P301+P310: NẾU NUỐT PHẢI: Gọi ngay cho bác sĩ. KHÔNG gây nôn.",
    "GHS09": "P273: Tránh thải ra môi trường. P391: Thu gom chất tràn đổ. P501: Xử lý theo quy định môi trường.",
    "NON DG": "P102: Để xa tầm tay trẻ em. P262: Tránh để hóa chất dính vào mắt. P501: Thải bỏ bao bì đúng nơi quy định.",
}

# Cache for GHS SVG and PNG assets
_GHS_SVG_CACHE: Dict[str, str] = {}
_GHS_PNG_CACHE: Dict[str, bytes] = {}


def _load_ghs_assets():
    """Preload all 9 standard GHS pictogram SVGs and PNGs."""
    global _GHS_SVG_CACHE, _GHS_PNG_CACHE
    if _GHS_SVG_CACHE and _GHS_PNG_CACHE:
        return

    for i in range(1, 10):
        code = f"GHS0{i}"
        svg_file = GHS_TEMPLATES_DIR / f"{code}.svg"
        png_file = GHS_TEMPLATES_DIR / f"{code}.png"

        if svg_file.exists():
            try:
                _GHS_SVG_CACHE[code] = svg_file.read_text(encoding="utf-8")
            except Exception:
                pass

        if png_file.exists():
            try:
                _GHS_PNG_CACHE[code] = png_file.read_bytes()
            except Exception:
                pass


def get_ghs_svg(code: str) -> str:
    """Get raw SVG text for a GHS code."""
    _load_ghs_assets()
    code_clean = code.strip().upper()
    if code_clean in _GHS_SVG_CACHE:
        return _GHS_SVG_CACHE[code_clean]
    # Fallback placeholder diamond SVG if not found
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        f'<polygon points="50,5 95,50 50,95 5,50" fill="#ffffff" stroke="#cc0000" stroke-width="6"/>'
        f'<text x="50" y="55" font-family="Arial" font-size="14" font-weight="bold" fill="#000" text-anchor="middle">{code_clean}</text>'
        f'</svg>'
    )


def get_ghs_png_bytes(code: str) -> Optional[bytes]:
    """Get PNG bytes for a GHS code."""
    _load_ghs_assets()
    code_clean = code.strip().upper()
    return _GHS_PNG_CACHE.get(code_clean)


def normalize_preset_size(size: Optional[str]) -> str:
    """Normalize and validate print size preset, falling back to A4_4UP if invalid."""
    if not size:
        return "A4_4UP"
    s = str(size).strip().upper()
    # Normalize common aliases
    if s in ("A4", "A4_4", "A4-4UP", "A4_4_UP"):
        return "A4_4UP"
    if s in ("A5_1", "A5_1UP", "A5-1UP"):
        return "A5"
    if s in ("DECAL_100X150", "DECAL150", "DECAL_150MM", "100X150"):
        return "DECAL_150"
    if s in ("DECAL_100X75", "DECAL75", "DECAL_75MM", "100X75"):
        return "DECAL_75"
    if s in STANDARD_PRESETS:
        return s
    return "A4_4UP"


def prepare_label_data(
    chem_or_id: Union[str, Dict[str, Any]],
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Extract and assemble all mandatory Decanting Label fields per Circular 01/2026/TT-BCT.
    Accepts chemical ID string or raw chemical dictionary from database.
    """
    _load_ghs_assets()

    chem: Dict[str, Any] = {}
    if isinstance(chem_or_id, str):
        from core.msds_intelligence import MSDSDatabase, MSDSExtractorEngine
        chem = MSDSDatabase.get_chemical(chem_or_id) or {}
        chem = MSDSExtractorEngine.ensure_vietnamese_msds_fields(chem)
        if not chem:
            # Fallback for unknown ID in testing/preview
            chem = {
                "chemical_id": chem_or_id,
                "product_code": chem_or_id,
                "product_name_vi": f"Hóa chất {chem_or_id}",
                "cas_primary": "N/A",
                "signal_word": "CẢNH BÁO / WARNING",
                "ghs_codes": ["GHS07"],
            }
    elif isinstance(chem_or_id, dict):
        chem = dict(chem_or_id)

    # Apply caller overrides if provided
    if overrides and isinstance(overrides, dict):
        chem.update(overrides)

    chem_id = chem.get("chemical_id") or chem.get("id") or chem.get("chem_id") or "CHEM-01"
    product_code = chem.get("product_code") or chem_id

    # 1. Product name / commercial name
    product_name = (
        chem.get("product_name")
        or chem.get("product_name_vi")
        or chem.get("commercial_name")
        or chem.get("product_name_original")
        or f"Hóa chất {product_code}"
    )

    # 2. CAS number / Ingredients
    cas_primary = chem.get("cas_primary") or chem.get("cas") or chem.get("cas_number") or ""
    if not cas_primary:
        # Try extracting first valid CAS from composition list
        comps = chem.get("composition") or []
        for c in comps:
            c_num = c.get("cas_number") or ""
            if re.match(r"^\d{2,7}-\d{2}-\d$", c_num):
                cas_primary = c_num
                break
    if not cas_primary:
        cas_primary = "Hỗn hợp phức hợp (Mixture)"

    # 3. Decanting Facility / Plant
    facility = chem.get("facility") or chem.get("plant") or chem.get("facility_name") or DEFAULT_FACILITY

    # 4. Dates & Lot
    today_dt = datetime.date.today()
    decanting_date = chem.get("decanting_date") or today_dt.strftime("%d/%m/%Y")
    expiry_date = chem.get("expiry_date") or (today_dt + datetime.timedelta(days=365)).strftime("%d/%m/%Y")
    lot_number = chem.get("lot_number") or f"LOT-{today_dt.strftime('%Y%m%d')}-01"

    # 5. GHS Codes & Pictograms
    raw_ghs = chem.get("ghs_codes") or chem.get("ghs_pictograms") or chem.get("ghs_codes_list")
    ghs_codes: List[str] = []
    if isinstance(raw_ghs, list):
        for item in raw_ghs:
            if isinstance(item, str):
                for m in re.findall(r"GHS0\d|NON\s*DG", item, re.IGNORECASE):
                    norm = m.upper().replace(" ", " ")
                    if norm not in ghs_codes:
                        ghs_codes.append(norm)
    elif isinstance(raw_ghs, str):
        for m in re.findall(r"GHS0\d|NON\s*DG", raw_ghs, re.IGNORECASE):
            norm = m.upper().replace(" ", " ")
            if norm not in ghs_codes:
                ghs_codes.append(norm)

    if not ghs_codes:
        ghs_codes = ["GHS02"] if chem.get("flammable") else ["NON DG"]

    # 6. Signal Word
    raw_signal = (chem.get("signal_word") or "").strip()
    signal_lower = raw_signal.lower()
    if "nguy hiểm" in signal_lower or "danger" in signal_lower:
        signal_word = "NGUY HIỂM / DANGER"
    elif "cảnh báo" in signal_lower or "warning" in signal_lower:
        signal_word = "CẢNH BÁO / WARNING"
    elif "non dg" in signal_lower or "an toàn" in signal_lower:
        signal_word = "NON DG (AN TOÀN)"
    else:
        # Determine based on GHS pictograms
        danger_set = {"GHS01", "GHS02", "GHS05", "GHS06", "GHS08"}
        if any(c in danger_set for c in ghs_codes):
            signal_word = "NGUY HIỂM / DANGER"
        elif any(c.startswith("GHS") for c in ghs_codes):
            signal_word = "CẢNH BÁO / WARNING"
        else:
            signal_word = "NON DG (AN TOÀN)"

    # 7. Hazard Statements (H-codes)
    raw_h = chem.get("h_codes") or chem.get("hazard_statements") or ""
    if isinstance(raw_h, list):
        h_statements = " ".join(raw_h).strip()
    else:
        h_statements = str(raw_h).strip()

    if not h_statements:
        h_list = [DEFAULT_H_STATEMENTS[c] for c in ghs_codes if c in DEFAULT_H_STATEMENTS]
        h_statements = " ".join(h_list) if h_list else DEFAULT_H_STATEMENTS["NON DG"]

    # 8. Precautionary Statements (P-codes)
    raw_p = chem.get("p_codes") or chem.get("precautionary_statements") or ""
    if isinstance(raw_p, list):
        p_statements = " ".join(raw_p).strip()
    else:
        p_statements = str(raw_p).strip()

    if not p_statements:
        p_list = [DEFAULT_P_STATEMENTS[c] for c in ghs_codes if c in DEFAULT_P_STATEMENTS]
        p_statements = " ".join(p_list) if p_list else DEFAULT_P_STATEMENTS["NON DG"]

    # 9. Emergency Hotline
    hotline = chem.get("hotline") or chem.get("emergency_hotline") or DEFAULT_HOTLINE

    # 10. Ingredient Breakdown
    ingredients = []
    raw_comp = chem.get("composition") or []
    for comp in raw_comp:
        c_name = comp.get("ingredient_name_vi") or comp.get("ingredient_name_original") or comp.get("name") or ""
        c_cas = comp.get("cas_number") or comp.get("cas") or ""
        c_pct = comp.get("concentration_text") or comp.get("concentration") or comp.get("percent") or ""
        if c_name:
            ingredients.append({"name": c_name, "cas": c_cas, "percent": str(c_pct)})

    # 11. Inline SVG dictionary for fast UI rendering
    ghs_svgs = {code: get_ghs_svg(code) for code in ghs_codes if code.startswith("GHS")}

    return {
        "chemical_id": str(chem_id),
        "product_code": str(product_code),
        "product_name": str(product_name),
        "commercial_name": str(product_name),
        "name_vi": str(product_name),
        "product_name_vi": str(product_name),
        "cas_primary": str(cas_primary),
        "cas": str(cas_primary),
        "cas_number": str(cas_primary),
        "facility": str(facility),
        "plant": str(facility),
        "facility_name": str(facility),
        "decanting_date": str(decanting_date),
        "expiry_date": str(expiry_date),
        "lot_number": str(lot_number),
        "signal_word": str(signal_word),
        "ghs_codes": ghs_codes,
        "ghs_pictograms": ghs_codes,
        "hazard_statements": str(h_statements),
        "h_codes": str(h_statements),
        "precautionary_statements": str(p_statements),
        "p_codes": str(p_statements),
        "hotline": str(hotline),
        "emergency_hotline": str(hotline),
        "ingredients": ingredients,
        "ghs_svg_icons": ghs_svgs,
    }


def _render_single_label_card_html(label: Dict[str, Any], card_class: str = "ghs-label-card") -> str:
    """Render HTML for a single GHS Decanting Label card."""
    signal_word = label.get("signal_word", "")
    is_danger = "nguy hiểm" in signal_word.lower() or "danger" in signal_word.lower()
    is_non_dg = "non dg" in signal_word.lower()

    signal_bg = "#dc2626" if is_danger else ("#16a34a" if is_non_dg else "#f59e0b")
    signal_text_color = "#ffffff"

    # Build SVG icons HTML
    svg_html_parts = []
    ghs_svgs = label.get("ghs_svg_icons") or {}
    for code, svg in ghs_svgs.items():
        svg_html_parts.append(
            f'<div class="ghs-icon-wrap" title="{code}">{svg}</div>'
        )
    if not svg_html_parts:
        svg_html_parts.append(
            '<div class="ghs-icon-wrap ghs-non-dg-badge" title="NON DG">'
            '<span style="font-weight:bold; font-size:11px; color:#16a34a; border:2px solid #16a34a; border-radius:4px; padding:2px 6px;">NON DG</span>'
            '</div>'
        )
    icons_html = "".join(svg_html_parts)

    # Format ingredient line
    ingredients = label.get("ingredients") or []
    if ingredients:
        comp_summary = ", ".join(
            f"{html.escape(str(i['name']))} ({html.escape(str(i['cas']))})" if i.get("cas") else html.escape(str(i['name']))
            for i in ingredients[:4]
        )
    else:
        comp_summary = f"{html.escape(str(label.get('product_name') or ''))} (CAS: {html.escape(str(label.get('cas_primary') or ''))})"

    facility_str = html.escape(str(label.get('facility') or ''))
    pname_str = html.escape(str(label.get('product_name') or ''))
    pcode_str = html.escape(str(label.get('product_code') or ''))
    cas_str = html.escape(str(label.get('cas_primary') or ''))
    lot_str = html.escape(str(label.get('lot_number') or ''))
    decant_date_str = html.escape(str(label.get('decanting_date') or ''))
    expiry_date_str = html.escape(str(label.get('expiry_date') or ''))
    signal_word_str = html.escape(str(signal_word or ''))
    hazard_stmts_str = html.escape(str(label.get('hazard_statements') or ''))
    prec_stmts_str = html.escape(str(label.get('precautionary_statements') or ''))
    hotline_str = html.escape(str(label.get('hotline') or ''))

    return f"""
    <div class="{card_class}">
        <!-- Header -->
        <div class="label-header">
            <div class="facility-name">{facility_str}</div>
            <div class="label-title">NHÃN PHỤ HÓA CHẤT CHIẾT RÓT (THÔNG TƯ 01/2026/TT-BCT)</div>
        </div>

        <!-- Product Identity -->
        <div class="product-id-row">
            <div class="product-name">{pname_str}</div>
            <div class="product-meta">
                <span><b>Mã SP:</b> {pcode_str}</span> &nbsp;|&nbsp; 
                <span><b>CAS:</b> {cas_str}</span> &nbsp;|&nbsp; 
                <span><b>Số Lô:</b> {lot_str}</span>
            </div>
            <div class="product-dates">
                <span><b>Ngày chiết:</b> {decant_date_str}</span> &nbsp;|&nbsp; 
                <span><b>Hạn dùng:</b> {expiry_date_str}</span>
            </div>
        </div>

        <!-- Signal Word & GHS Icons -->
        <div class="signal-ghs-row">
            <div class="signal-banner" style="background-color: {signal_bg}; color: {signal_text_color};">
                {signal_word_str}
            </div>
            <div class="ghs-icons-strip">
                {icons_html}
            </div>
        </div>

        <!-- Statements Body -->
        <div class="statements-box">
            <div class="statement-group">
                <span class="stmt-label">⚠️ CẢNH BÁO NGUY CƠ (H):</span>
                <span class="stmt-text">{hazard_stmts_str}</span>
            </div>
            <div class="statement-group">
                <span class="stmt-label">🛡️ BIỆN PHÁP PHÒNG NGỪA & SƠ CỨU (P):</span>
                <span class="stmt-text">{prec_stmts_str}</span>
            </div>
            <div class="statement-group">
                <span class="stmt-label">🧪 THÀNH PHẦN:</span>
                <span class="stmt-text">{comp_summary}</span>
            </div>
        </div>

        <!-- Footer Hotline -->
        <div class="label-footer">
            <div class="hotline-text">
                📞 <b>ỨNG PHÓ KHẨN CẤP:</b> {hotline_str}
            </div>
        </div>
    </div>
    """


def generate_label_html(
    chem_data: Union[Dict[str, Any], List[Dict[str, Any]], str],
    size: str = "A4_4UP",
) -> str:
    """
    Generate standalone, self-contained HTML for printing GHS Decanting Labels.
    Supports presets: A4_4UP, A5, DECAL_150, DECAL_75.
    Embeds isolated @media print rules for 100% clean browser printing.
    """
    preset = normalize_preset_size(size)

    # Prepare list of label items
    if isinstance(chem_data, list):
        labels = [prepare_label_data(c) for c in chem_data]
    else:
        labels = [prepare_label_data(chem_data)]

    if not labels:
        labels = [prepare_label_data("CHEM-01")]

    primary_label = labels[0]
    sheet_class_map = {
        "A4_4UP": "print-sheet-a4-4",
        "A5": "print-sheet-a5-1",
        "DECAL_150": "print-sheet-decal-150",
        "DECAL_75": "print-sheet-decal-75",
    }
    sheet_class = sheet_class_map.get(preset, "print-sheet-a4-4")

    # For A4_4UP, if only 1 chemical provided, repeat it 4 times on the sheet
    if preset == "A4_4UP":
        if len(labels) == 1:
            render_labels = [labels[0]] * 4
        elif len(labels) < 4:
            render_labels = (labels * 4)[:4]
        else:
            render_labels = labels[:4]
    else:
        render_labels = [labels[0]]

    # Render card markup
    cards_html = "\n".join(_render_single_label_card_html(lb) for lb in render_labels)

    title_pname = html.escape(str(primary_label.get('product_name') or ''))
    title_pcode = html.escape(str(primary_label.get('product_code') or ''))

    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nhãn Phụ Hóa Chất GHS Chiết Rót — {title_pname} ({title_pcode})</title>
    <style>
        /* Base Screen Styles */
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: #f1f5f9;
            color: #0f172a;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .no-print-toolbar {{
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 12px 20px;
            margin-bottom: 20px;
            display: flex;
            gap: 15px;
            align-items: center;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            width: 100%;
            max-width: 900px;
        }}
        .no-print-toolbar button {{
            padding: 8px 16px;
            font-size: 14px;
            font-weight: 600;
            border-radius: 6px;
            cursor: pointer;
            border: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .btn-print {{
            background: #2563eb;
            color: #ffffff;
        }}
        .btn-print:hover {{
            background: #1d4ed8;
        }}
        .btn-close {{
            background: #e2e8f0;
            color: #334155;
        }}
        .btn-close:hover {{
            background: #cbd5e1;
        }}

        /* Print Container Outer Wrapper */
        #ghs-print-container {{
            background: #ffffff;
            box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
        }}

        /* Preset Sheet Dimensions on Screen & Print */
        .print-sheet-a4-4 {{
            width: 210mm;
            min-height: 297mm;
            padding: 8mm;
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: 1fr 1fr;
            gap: 6mm;
            box-sizing: border-box;
        }}

        .print-sheet-a5-1 {{
            width: 148mm;
            min-height: 210mm;
            padding: 8mm;
            display: flex;
            flex-direction: column;
            box-sizing: border-box;
        }}

        .print-sheet-decal-150 {{
            width: 100mm;
            min-height: 150mm;
            padding: 4mm;
            display: flex;
            flex-direction: column;
            box-sizing: border-box;
        }}

        .print-sheet-decal-75 {{
            width: 100mm;
            min-height: 75mm;
            padding: 3mm;
            display: flex;
            flex-direction: column;
            box-sizing: border-box;
        }}

        /* Label Card Elements */
        .ghs-label-card {{
            border: 2.5px solid #cc0000;
            border-radius: 4px;
            background: #ffffff;
            padding: 8px 10px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            overflow: hidden;
            box-sizing: border-box;
            height: 100%;
        }}

        .label-header {{
            text-align: center;
            border-bottom: 1.5px solid #cc0000;
            padding-bottom: 4px;
            margin-bottom: 4px;
        }}
        .facility-name {{
            font-size: 10px;
            font-weight: 700;
            color: #0f172a;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}
        .label-title {{
            font-size: 8px;
            font-weight: 600;
            color: #64748b;
        }}

        .product-id-row {{
            margin-bottom: 4px;
        }}
        .product-name {{
            font-size: 15px;
            font-weight: 800;
            color: #0f172a;
            line-height: 1.2;
            text-transform: uppercase;
        }}
        .product-meta, .product-dates {{
            font-size: 9px;
            color: #334155;
            margin-top: 1px;
        }}

        .signal-ghs-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            margin: 4px 0;
            padding: 3px 0;
            border-top: 1px dashed #cbd5e1;
            border-bottom: 1px dashed #cbd5e1;
        }}
        .signal-banner {{
            font-size: 11px;
            font-weight: 900;
            padding: 4px 8px;
            border-radius: 3px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            white-space: nowrap;
        }}
        .ghs-icons-strip {{
            display: flex;
            gap: 4px;
            align-items: center;
            flex-wrap: wrap;
        }}
        .ghs-icon-wrap {{
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .ghs-icon-wrap svg {{
            width: 100%;
            height: 100%;
            display: block;
        }}

        .statements-box {{
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 3px;
            font-size: 8.5px;
            line-height: 1.25;
            color: #1e293b;
            margin: 3px 0;
            overflow: hidden;
        }}
        .statement-group {{
            display: flex;
            flex-direction: column;
        }}
        .stmt-label {{
            font-weight: 800;
            color: #991b1b;
            font-size: 8px;
        }}
        .stmt-text {{
            color: #334155;
        }}

        .label-footer {{
            border-top: 1px solid #cbd5e1;
            padding-top: 3px;
            margin-top: 3px;
            text-align: center;
        }}
        .hotline-text {{
            font-size: 8px;
            font-weight: 700;
            color: #b91c1c;
        }}

        /* Compact Decal Scalings */
        .print-sheet-decal-75 .ghs-label-card {{
            padding: 5px 6px;
        }}
        .print-sheet-decal-75 .product-name {{
            font-size: 11px;
        }}
        .print-sheet-decal-75 .ghs-icon-wrap {{
            width: 24px;
            height: 24px;
        }}
        .print-sheet-decal-75 .statements-box {{
            font-size: 7px;
            line-height: 1.15;
        }}

        /* ============================================================ */
        /* ISOLATED PRINT STYLESHEET (WINDOW.PRINT / CTR+P)             */
        /* ============================================================ */
        @media print {{
            body {{
                background: #ffffff !important;
                padding: 0 !important;
                margin: 0 !important;
            }}
            .no-print-toolbar {{
                display: none !important;
            }}
            #ghs-print-container {{
                box-shadow: none !important;
                margin: 0 !important;
                padding: 0 !important;
                width: 100% !important;
            }}
            @page {{
                margin: 0;
                size: auto;
            }}
            .print-sheet-a4-4,
            .print-sheet-a5-1,
            .print-sheet-decal-150,
            .print-sheet-decal-75 {{
                page-break-after: always;
            }}
        }}
    </style>
</head>
<body>
    <div class="no-print-toolbar">
        <div style="flex:1;">
            <b style="font-size: 15px;">🏷️ Nhãn Phụ GHS Chiết Rót — Khổ: {PRESET_CONFIG[preset]['title']}</b>
            <div style="font-size: 12px; color: #64748b;">Quy chuẩn Thông tư 01/2026/TT-BCT & TCVN GHS | Đơn vị: {primary_label.get('facility')}</div>
        </div>
        <button type="button" class="btn-print" onclick="window.print()">
            🖨️ In Nhãn Ngay
        </button>
        <button type="button" class="btn-close" onclick="window.close()">
            ✕ Đóng
        </button>
    </div>

    <div id="ghs-print-container">
        <div class="{sheet_class}">
            {cards_html}
        </div>
    </div>
</body>
</html>"""
    return html_content


def _find_windows_font(bold: bool = False) -> Optional[str]:
    """Find a system TrueType font supporting Vietnamese Unicode."""
    candidates = (
        ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/timesbd.ttf"]
        if bold
        else ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/times.ttf"]
    )
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def generate_labels_pdf(
    chem_list_or_data: Union[Dict[str, Any], List[Dict[str, Any]], str],
    size: str = "A4_4UP",
) -> bytes:
    """
    Generate valid vector PDF (%PDF-) containing high-DPI GHS Decanting Labels.
    Supports A4_4UP, A5, DECAL_150, DECAL_75 presets.
    """
    preset = normalize_preset_size(size)
    cfg = PRESET_CONFIG[preset]

    # Normalize data to list of label dicts
    if isinstance(chem_list_or_data, list):
        labels = [prepare_label_data(c) for c in chem_list_or_data]
    else:
        labels = [prepare_label_data(chem_list_or_data)]

    if not labels:
        labels = [prepare_label_data("CHEM-01")]

    # Dimensions in PDF points (1mm = 72 / 25.4 pt ≈ 2.83465 pt)
    PT_PER_MM = 72.0 / 25.4
    page_w_pt = cfg["w_mm"] * PT_PER_MM
    page_h_pt = cfg["h_mm"] * PT_PER_MM

    doc = fitz.open()

    font_regular = _find_windows_font(bold=False)
    font_bold = _find_windows_font(bold=True)

    font_reg_name = "arial_reg" if font_regular else "helv"
    font_bold_name = "arial_bold" if font_bold else "hebo"

    def _draw_label_card(page, rect: fitz.Rect, lb: Dict[str, Any]):
        """Draw a single GHS label onto the given page inside rect."""
        # Draw red border
        page.draw_rect(rect, color=(0.8, 0.0, 0.0), width=2.0, fill=(1, 1, 1))

        margin = 6.0
        inner_w = rect.width - 2 * margin
        cur_y = rect.y0 + margin

        # 1. Header (Facility + Circular 01)
        facility_str = str(lb.get("facility") or DEFAULT_FACILITY).upper()
        page.insert_textbox(
            fitz.Rect(rect.x0 + margin, cur_y, rect.x1 - margin, cur_y + 16),
            facility_str,
            fontname=font_bold_name,
            fontfile=font_bold,
            fontsize=7.5 if rect.width > 200 else 6.0,
            align=fitz.TEXT_ALIGN_CENTER,
            color=(0.1, 0.1, 0.1),
        )
        cur_y += 14

        page.insert_textbox(
            fitz.Rect(rect.x0 + margin, cur_y, rect.x1 - margin, cur_y + 12),
            "NHÃN PHỤ HÓA CHẤT CHIẾT RÓT (THÔNG TƯ 01/2026/TT-BCT)",
            fontname=font_bold_name,
            fontfile=font_bold,
            fontsize=6.5 if rect.width > 200 else 5.0,
            align=fitz.TEXT_ALIGN_CENTER,
            color=(0.4, 0.4, 0.4),
        )
        cur_y += 12

        # Header divider line
        page.draw_line(
            fitz.Point(rect.x0 + margin, cur_y),
            fitz.Point(rect.x1 - margin, cur_y),
            color=(0.8, 0.0, 0.0),
            width=1.0,
        )
        cur_y += 4

        # 2. Product Name & Codes
        p_name = str(lb.get("product_name") or "HÓA CHẤT").upper()
        p_name_h = 24 if rect.width > 200 else 18
        page.insert_textbox(
            fitz.Rect(rect.x0 + margin, cur_y, rect.x1 - margin, cur_y + p_name_h),
            p_name,
            fontname=font_bold_name,
            fontfile=font_bold,
            fontsize=11.0 if rect.width > 200 else 8.5,
            align=fitz.TEXT_ALIGN_LEFT,
            color=(0.0, 0.0, 0.0),
        )
        cur_y += p_name_h

        meta_line = f"Mã SP: {lb.get('product_code')}   |   CAS: {lb.get('cas_primary')}   |   Lô: {lb.get('lot_number')}"
        page.insert_textbox(
            fitz.Rect(rect.x0 + margin, cur_y, rect.x1 - margin, cur_y + 12),
            meta_line,
            fontname=font_bold_name,
            fontfile=font_bold,
            fontsize=7.0 if rect.width > 200 else 5.5,
            align=fitz.TEXT_ALIGN_LEFT,
            color=(0.2, 0.2, 0.2),
        )
        cur_y += 12

        dates_line = f"Ngày chiết rót: {lb.get('decanting_date')}   |   Hạn dùng: {lb.get('expiry_date')}"
        page.insert_textbox(
            fitz.Rect(rect.x0 + margin, cur_y, rect.x1 - margin, cur_y + 12),
            dates_line,
            fontname=font_reg_name,
            fontfile=font_regular,
            fontsize=6.5 if rect.width > 200 else 5.5,
            align=fitz.TEXT_ALIGN_LEFT,
            color=(0.2, 0.2, 0.2),
        )
        cur_y += 12

        # 3. Signal Word Band & GHS Icons Row
        cur_y += 2
        sig_rect_h = 24.0 if rect.width > 200 else 18.0
        signal_word = str(lb.get("signal_word") or "NGUY HIỂM / DANGER").upper()

        is_danger = "NGUY HIỂM" in signal_word or "DANGER" in signal_word
        is_nondg = "NON DG" in signal_word
        sig_bg = (0.85, 0.1, 0.1) if is_danger else ((0.1, 0.6, 0.2) if is_nondg else (0.9, 0.6, 0.1))

        # Signal word box on the left
        sig_w = 120.0 if rect.width > 200 else 85.0
        sig_box = fitz.Rect(rect.x0 + margin, cur_y, rect.x0 + margin + sig_w, cur_y + sig_rect_h)
        page.draw_rect(sig_box, color=None, fill=sig_bg)
        page.insert_textbox(
            sig_box,
            signal_word,
            fontname=font_bold_name,
            fontfile=font_bold,
            fontsize=8.5 if rect.width > 200 else 6.5,
            align=fitz.TEXT_ALIGN_CENTER,
            color=(1, 1, 1),
        )

        # GHS Pictograms on the right of signal word
        icon_size = sig_rect_h + 4
        ghs_codes = [c for c in lb.get("ghs_codes", []) if c.startswith("GHS")]
        icon_x = sig_box.x1 + 6.0
        for code in ghs_codes[:4]:
            png_bytes = get_ghs_png_bytes(code)
            if png_bytes and (icon_x + icon_size <= rect.x1 - margin):
                icon_rect = fitz.Rect(icon_x, cur_y - 2, icon_x + icon_size, cur_y - 2 + icon_size)
                page.insert_image(icon_rect, stream=png_bytes)
                icon_x += icon_size + 4.0

        cur_y += sig_rect_h + 8

        # 4. Statements Section (H-codes & P-codes)
        rem_h = (rect.y1 - margin - 20) - cur_y
        h_part = f"CẢNH BÁO NGUY CƠ (H):\n{lb.get('hazard_statements', '')}\n\nBIỆN PHÁP PHÒNG NGỪA & SƠ CỨU (P):\n{lb.get('precautionary_statements', '')}"

        stmts_rect = fitz.Rect(rect.x0 + margin, cur_y, rect.x1 - margin, rect.y1 - margin - 18)
        page.insert_textbox(
            stmts_rect,
            h_part,
            fontname=font_reg_name,
            fontfile=font_regular,
            fontsize=7.0 if rect.width > 200 else 5.5,
            align=fitz.TEXT_ALIGN_LEFT,
            color=(0.1, 0.1, 0.1),
        )

        # 5. Bottom Emergency Hotline Band
        footer_line_y = rect.y1 - margin - 14
        page.draw_line(
            fitz.Point(rect.x0 + margin, footer_line_y),
            fitz.Point(rect.x1 - margin, footer_line_y),
            color=(0.8, 0.0, 0.0),
            width=0.8,
        )
        hotline_str = f"ỨNG PHÓ SỰ CỐ KHẨN CẤP: {lb.get('hotline') or DEFAULT_HOTLINE}"
        page.insert_textbox(
            fitz.Rect(rect.x0 + margin, footer_line_y + 2, rect.x1 - margin, rect.y1 - margin),
            hotline_str,
            fontname=font_bold_name,
            fontfile=font_bold,
            fontsize=6.5 if rect.width > 200 else 5.0,
            align=fitz.TEXT_ALIGN_CENTER,
            color=(0.7, 0.0, 0.0),
        )

    # Multi-label layout logic
    if preset == "A4_4UP":
        # 4 labels on A4 page (2 columns x 2 rows)
        page = doc.new_page(width=page_w_pt, height=page_h_pt)
        page_margin = 18.0
        gap = 12.0
        cell_w = (page_w_pt - 2 * page_margin - gap) / 2.0
        cell_h = (page_h_pt - 2 * page_margin - gap) / 2.0

        if len(labels) == 1:
            page_labels = [labels[0]] * 4
        elif len(labels) < 4:
            page_labels = (labels * 4)[:4]
        else:
            page_labels = labels[:4]

        positions = [
            (page_margin, page_margin),
            (page_margin + cell_w + gap, page_margin),
            (page_margin, page_margin + cell_h + gap),
            (page_margin + cell_w + gap, page_margin + cell_h + gap),
        ]

        for i, (x, y) in enumerate(positions):
            card_rect = fitz.Rect(x, y, x + cell_w, y + cell_h)
            _draw_label_card(page, card_rect, page_labels[i])

    else:
        # 1 label per page
        for lb in labels:
            page = doc.new_page(width=page_w_pt, height=page_h_pt)
            page_margin = 10.0 if preset == "A5" else 6.0
            card_rect = fitz.Rect(
                page_margin,
                page_margin,
                page_w_pt - page_margin,
                page_h_pt - page_margin,
            )
            _draw_label_card(page, card_rect, lb)

    try:
        doc.subset_fonts()
    except Exception:
        pass

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
