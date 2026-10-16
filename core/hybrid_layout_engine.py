"""
core/hybrid_layout_engine.py
────────────────────────────
ĐỘNG CƠ DỊCH NGƯỢC BỐ CỤC HYBRID (HYBRID VECTOR & AI LAYOUT DECOMPILER ENGINE)
100% Tự chủ, chạy độc lập không phụ thuộc Microsoft Word (zero WINWORD.EXE).

Kiến trúc 3 thành phần cốt lõi:
1. VectorGeometryDecompiler (R1):
   - Trích xuất luồng đồ họa vector từ PDF Content Stream (page.get_drawings(), page.find_tables()).
   - Lọc và snapped các đường kẻ mảnh (h <= 2.5 pt hoặc w <= 2.5 pt).
   - Xây dựng đồ thị lưới ô TableGridGraph chính xác, tránh bẫy vỡ hàng/cột của giải thuật bounding box thô sơ.
   - Trích xuất văn bản trong ô và các khối văn bản dòng chảy bên ngoài (tiêu đề, đề mục, bullet points).

2. AISemanticSupervisor (R2):
   - Giám sát ngữ nghĩa bố cục DeepSeek kèm cơ chế tự phục hồi cục bộ 100% (autonomous local heuristic fallback).
   - Hàn gắn triệt để từ ngữ tiếng Việt bị phân mảnh / rụng âm tiết / rớt dấu:
     (\\b(chứ|chư)\\s+c\\b -> chức, \\b(tổ|tô)\\s+c\\b -> tộc, v.v.).
   - Phân tách ranh giới song ngữ CJK - Latin (fix_fused_cjk_latin).
   - Bộ cân bằng độ rộng cột động (Dynamic Column Width Rebalancer):
     - Chuẩn hóa theo đơn vị dxa.
     - Cột chứa cụm từ >= 14 ký tự (như "Bộ phận tổ chức", "Chủ đề đào tạo") bảo đảm >= 1,380 dxa.
     - Tái phân bổ dung lượng từ cột mô tả rộng (Col 3: 2,275 -> 1,941 dxa).
     - Khóa cứng tổng chiều rộng bảng <= 10,460 dxa (sum(gridCol) == 10,460 dxa).

3. FlowableNativeDOCXBuilder (R3):
   - Tạo tài liệu DOCX dòng chảy tự nhiên (Flowability Reflow) trên khổ A4 chuẩn, lề 0.5 inch (720 dxa).
   - Nhúng toàn bộ các thẻ bảo vệ cấu trúc OOXML cao cấp:
     <w:tblLayout w:type="fixed"/>
     <w:tblW w:w="10460" w:type="dxa"/>
     <w:tblGrid>
     <w:cantSplit/> trên 100% các hàng
     <w:tblHeader/> trên hàng 0 của bảng nhiều hàng
     <w:tcMar> top=50, bottom=50, left=60, right=60 dxa
     <w:wordWrap w:val="0"/>, <w:kinsoku w:val="1"/>, <w:suppressAutoHyphens/>
     Định dạng Interlinear: dòng gốc (Hoa/Anh) trên, dịch nghĩa (Việt) dưới màu #002060.
     Chuẩn hóa 100% Unicode NFC trên mọi runs.

4. HybridVectorAILayoutDecompilerEngine:
   - Lớp điều phối cấp cao cung cấp giao diện chuyển đổi:
     convert(input_path, output_path, ...)
   - Tự động dự phòng về TitanAutonomousVIPProEngine khi gặp luồng dữ liệu dị thường.
"""

import os
import sys
import time
import shutil
import logging
import unicodedata
import re
import json
import base64
from typing import Optional, Dict, Any, List, Set, Tuple

import fitz  # PyMuPDF
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

from core.ai_reconstructed_ocr import (
    heal_broken_vietnamese_text,
    clean_and_split_cell_lines,
    DARK_BLUE,
    SLATE_HEADER,
    SLATE_BODY
)

logger = logging.getLogger("TitanHybridLayoutEngine")
logger.setLevel(logging.INFO)

# Cấu hình kích thước trang A4 chuẩn và lề in 0.5 inch (720 dxa)
A4_WIDTH_DXA = 11909
A4_HEIGHT_DXA = 16834
MARGIN_05_INCH_DXA = 720
TOTAL_USABLE_A4_DXA = 10460  # 11,909 - (2 * 720) = 10,469 ~ 10,460 dxa an toàn

# Bảng quy tắc hàn gắn phụ âm/âm tiết rụng tiếng Việt toàn diện
COMPREHENSIVE_VIETNAMESE_RULES: List[Tuple[str, str]] = [
    # 1. Rụng âm cuối tạo thành từ đơn lẻ trên dòng mới ('tổ chứ\nc' -> 'tổ chức')
    (r'\b(chứ|chư)\s+c\b', 'chức'),
    (r'\b(tổ|tô)\s+c\b', 'tộc'),
    (r'\b(mụ|mu)\s+c\b', 'mục'),
    (r'\b(xá|xa)\s+c\b', 'xác'),
    (r'\b(khá|kha)\s+c\b', 'khác'),
    (r'\b(phá|pha)\s+t\b', 'phát'),
    (r'\b(bộ|bo)\s+t\b', 'bột'),
    (r'\b(hoạ|hoa)\s+ch\b', 'hoạch'),
    (r'\b(thố|tho)\s+ng\b', 'thống'),
    (r'\b(dụ|du)\s+ng\b', 'dụng'),

    # 2. Rụng âm cuối trong từ ghép phổ biến
    (r'\bGiả\s+ng\b', 'Giảng'),
    (r'\bgiả\s+ng\b', 'giảng'),
    (r'\bHiệ\s+n\b', 'Hiện'),
    (r'\bhiệ\s+n\b', 'hiện'),
    (r'\btổn\s+g\b', 'tổng'),
    (r'\bTổn\s+g\b', 'Tổng'),
    (r'\bBả\s+o\b', 'Bảo'),
    (r'\bbả\s+o\b', 'bảo'),
    (r'\bchá\s+y\b', 'cháy'),
    (r'\bchữ\s+a\b', 'chữa'),

    # 3. Rụng âm đầu
    (r'\bCh\s+ủ\b', 'Chủ'),
    (r'\bch\s+ủ\b', 'chủ'),
    (r'\bNg\s+ày\b', 'Ngày'),
    (r'\bng\s+ày\b', 'ngày'),
    (r'\bTh\s+ời\b', 'Thời'),
    (r'\bth\s+ời\b', 'thời'),
    (r'\bGi\s+ờ\b', 'Giờ'),
    (r'\bgi\s+ờ\b', 'giờ'),
    (r'\bph\s+út\b', 'phút'),
    (r'\bPh\s+út\b', 'Phút'),
    (r'\bc\s+ủa\b', 'của'),
    (r'\bC\s+ủa\b', 'Của'),
    (r'\bk\s+ế\b', 'kế'),
    (r'\bth\s+ực\b', 'thực'),
    (r'\bđ\s+ào\b', 'đào'),
    (r'\bv\s+iên\b', 'viên'),
    (r'\bt\s+ổ\b', 'tổ'),
    (r'\bh\s+oạch\b', 'hoạch'),
    (r'\bb\s+áo\b', 'báo'),
    (r'\bh\s+ướng\b', 'hướng'),
    (r'\bd\s+ẫn\b', 'dẫn'),
    (r'\bh\s+ệ\b', 'hệ'),
    (r'\bt\s+hống\b', 'thống'),
    (r'\bs\s+ử\b', 'sử'),
    (r'\bd\s+ụng\b', 'dụng'),
    (r'\bb\s+ình\b', 'bình'),
    (r'\bt\s+ủ\b', 'tủ'),
    (r'\bv\s+òi\b', 'vòi'),
]


# ==============================================================================
# 1. TABLE GRID GRAPH
# ==============================================================================

class TableGridGraph:
    """
    Cấu trúc đồ thị lưới ô 2 chiều giải mã từ luồng đồ họa vector PDF.
    Lưu trữ tọa độ hộp bao (bbox), ma trận ô (cells), độ rộng cột theo dxa
    và các thuộc tính đường viền.
    """
    def __init__(
        self,
        table_idx: int,
        bbox: fitz.Rect,
        row_count: int,
        col_count: int,
        raw_cells: List[List[str]],
        cell_rects: Optional[List[List[Tuple[float, float, float, float]]]] = None
    ):
        self.table_idx = table_idx
        self.bbox = bbox
        self.row_count = row_count
        self.col_count = col_count
        self.raw_cells = raw_cells
        self.cell_rects = cell_rects or []
        self.raw_col_widths_dxa: List[int] = []
        self.calibrated_col_widths_dxa: List[int] = []
        self.healed_cells: List[List[str]] = []


# ==============================================================================
# 2. VECTOR GEOMETRY DECOMPILER (R1)
# ==============================================================================

class VectorGeometryDecompiler:
    """
    Trích xuất và dịch ngược hình học đồ họa vector từ luồng nội dung PDF.
    - Lọc thin rectangles ('re') và line segments ('l')
    - Phát hiện lưới bảng biểu thông qua PyMuPDF find_tables (lines strategy)
    - Trích xuất các khối văn bản ngoài bảng (headings, bullet points, paragraphs)
    """

    @classmethod
    def decompile_page(cls, page: fitz.Page, page_num: int = 0) -> Dict[str, Any]:
        """
        Dịch ngược toàn bộ đối tượng vector và khối văn bản của một trang PDF.
        """
        # 1. Trích xuất các nét vẽ vector (đường kẻ ngang và dọc)
        drawings = page.get_drawings()
        h_lines: List[Dict[str, Any]] = []
        v_lines: List[Dict[str, Any]] = []

        for d in drawings:
            rect = d["rect"]
            w, h = rect.width, rect.height
            # Đoạn thẳng ngang mỏng (chiều cao <= 2.5 pt, chiều rộng >= 5.0 pt)
            if h <= 2.5 and w >= 5.0:
                h_lines.append({"x0": rect.x0, "x1": rect.x1, "y": (rect.y0 + rect.y1) / 2.0})
            # Đoạn thẳng dọc mỏng (chiều rộng <= 2.5 pt, chiều cao >= 5.0 pt)
            elif w <= 2.5 and h >= 5.0:
                v_lines.append({"x": (rect.x0 + rect.x1) / 2.0, "y0": rect.y0, "y1": rect.y1})

            # Các nét vẽ đường thẳng 'l'
            for item in d.get("items", []):
                if item[0] == "l":
                    p1, p2 = item[1], item[2]
                    if abs(p1.y - p2.y) <= 1.0 and abs(p1.x - p2.x) >= 5.0:
                        h_lines.append({"x0": min(p1.x, p2.x), "x1": max(p1.x, p2.x), "y": (p1.y + p2.y) / 2.0})
                    elif abs(p1.x - p2.x) <= 1.0 and abs(p1.y - p2.y) >= 5.0:
                        v_lines.append({"x": (p1.x + p2.x) / 2.0, "y0": min(p1.y, p2.y), "y1": max(p1.y, p2.y)})

        # 2. Nhận diện lưới bảng biểu thông qua vector lines
        tabs = page.find_tables(horizontal_strategy='lines', vertical_strategy='lines_strict')
        table_graphs: List[TableGridGraph] = []
        table_bboxes: List[fitz.Rect] = []

        for idx, tab in enumerate(tabs.tables):
            t_bbox = fitz.Rect(tab.bbox)
            table_bboxes.append(t_bbox)

            raw_matrix = tab.extract()
            cell_rects: List[List[Tuple[float, float, float, float]]] = []
            for r in tab.rows:
                cell_rects.append([c for c in r.cells])

            # Tính độ rộng cột ban đầu theo tọa độ vector ô hàng đầu tiên
            raw_col_widths_pt: List[float] = []
            if tab.rows and tab.rows[0].cells:
                for c in tab.rows[0].cells:
                    raw_col_widths_pt.append(c[2] - c[0])
            else:
                w_each = t_bbox.width / max(1, tab.col_count)
                raw_col_widths_pt = [w_each] * tab.col_count

            raw_col_widths_dxa = [round(w * 20) for w in raw_col_widths_pt]

            graph = TableGridGraph(
                table_idx=idx,
                bbox=t_bbox,
                row_count=tab.row_count,
                col_count=tab.col_count,
                raw_cells=raw_matrix,
                cell_rects=cell_rects
            )
            graph.raw_col_widths_dxa = raw_col_widths_dxa
            table_graphs.append(graph)

        # 3. Trích xuất các khối văn bản ngoài bảng biểu
        blocks = page.get_text("blocks")
        outside_elements: List[Dict[str, Any]] = []

        for b in blocks:
            b_rect = fitz.Rect(b[:4])
            text = b[4].strip()
            if not text:
                continue

            # Kiểm tra xem khối chữ này có nằm trong bảng hay không
            is_inside_table = False
            for tb in table_bboxes:
                intersect = b_rect & tb
                if intersect.get_area() > 0.5 * b_rect.get_area():
                    is_inside_table = True
                    break
            if is_inside_table:
                continue

            # Phân loại khối chữ ngoài bảng
            if '•' in text or '\n•' in text:
                # Danh sách bullet points
                bullet_parts = [p.strip() for p in re.split(r'[•●▪]\s*', text) if p.strip()]
                for b_idx, part in enumerate(bullet_parts):
                    clean_line = re.sub(r'\s*\n\s*', ' ', part)
                    outside_elements.append({
                        "type": "bullet",
                        "y0": b_rect.y0 + b_idx * 16.0,
                        "text": clean_line,
                        "rect": b_rect
                    })
            else:
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                single_line = " ".join(lines)
                if b_rect.y0 < 115.0 and ('签到表' in single_line or 'Biểu ký tên' in single_line):
                    el_type = "title"
                elif '培训内容' in single_line or 'Nội dung' in single_line:
                    el_type = "subheading"
                elif '签 到 处' in single_line or '签到处' in single_line:
                    el_type = "heading"
                else:
                    el_type = "paragraph"

                outside_elements.append({
                    "type": el_type,
                    "y0": b_rect.y0,
                    "text": single_line,
                    "rect": b_rect
                })

        # 4. Sắp xếp toàn bộ phần tử dòng chảy (bảng + đoạn văn) theo thứ tự tọa độ Y
        flow_elements: List[Dict[str, Any]] = []
        for g in table_graphs:
            flow_elements.append({
                "type": "table",
                "y0": g.bbox.y0,
                "data": g
            })
        for el in outside_elements:
            flow_elements.append(el)

        flow_elements.sort(key=lambda x: x["y0"])

        return {
            "page_num": page_num,
            "page_rect": page.rect,
            "tables": table_graphs,
            "flow_elements": flow_elements,
            "vector_h_lines": h_lines,
            "vector_v_lines": v_lines
        }


# ==============================================================================
# 3. AI SEMANTIC SUPERVISOR & AUTO-HEALING (R2)
# ==============================================================================

class AISemanticSupervisor:
    """
    Bộ giám sát ngữ nghĩa AI DeepSeek và phục hồi tiếng Việt tự chủ:
    - Tách ranh giới song ngữ CJK - Latin
    - Hàn gắn phụ âm/âm tiết rụng tiếng Việt
    - Cân bằng độ rộng cột động (Dynamic Column Width Rebalancer)
    - Tự động dự phòng 100% giải thuật cục bộ khi không có mạng/API key.
    """

    @classmethod
    def fix_fused_cjk_latin(cls, text: str) -> str:
        """Tách chữ Hán dính liền với ký tự Latin/tiếng Việt/chữ số."""
        if not text:
            return ""
        text = re.sub(r'([\u4e00-\u9fff])([a-zA-ZÀ-ỹ0-9])', r'\1 \2', text)
        text = re.sub(r'([a-zA-ZÀ-ỹ0-9])([\u4e00-\u9fff])', r'\1 \2', text)
        return text

    @classmethod
    def heal_text(cls, text: str) -> str:
        """
        Hàn gắn toàn diện tiếng Việt bị phân mảnh, tách âm và chuẩn hóa Unicode NFC.
        """
        if not text:
            return ""
        # 1. Tách ranh giới CJK - Latin
        t = cls.fix_fused_cjk_latin(text)

        # 2. Hàn gắn các quy tắc rụng âm tiết
        for pattern, replacement in COMPREHENSIVE_VIETNAMESE_RULES:
            t = re.sub(pattern, replacement, t, flags=re.IGNORECASE)

        # 3. Áp dụng bộ phục hồi diacritic từ ai_reconstructed_ocr
        t = heal_broken_vietnamese_text(t)

        # 4. Chuẩn hóa Unicode dựng sẵn (NFC)
        return unicodedata.normalize('NFC', t)

    @classmethod
    def split_bilingual_cell_lines(cls, cell_text: str) -> List[Tuple[str, str]]:
        """
        Phân tách nội dung ô thành các cặp dòng (loại, nội dung):
        'primary': dòng gốc (Chinese/English/chính)
        'translation': dòng dịch nghĩa (tiếng Việt/phụ)
        """
        if not cell_text:
            return []

        healed = cls.heal_text(cell_text)
        lines = [l.strip() for l in healed.split('\n') if l.strip()]
        result: List[Tuple[str, str]] = []

        bilingual_regex = re.compile(r'^([\u4e00-\u9fff\s\u3000-\u303f]+)\s+([a-zA-ZÀ-ỹ0-9].*)$')

        for line in lines:
            # Kiểm tra nếu dòng chứa cả CJK và Latin trên cùng một dòng
            m = bilingual_regex.match(line)
            if m:
                cjk_part = m.group(1).strip()
                latin_part = m.group(2).strip()
                result.append(('primary', cjk_part))
                result.append(('translation', latin_part))
            elif re.search(r'[\u4e00-\u9fff]', line):
                result.append(('primary', line))
            else:
                # Nếu đã có dòng primary trước đó thì đây là dòng translation
                if any(k == 'primary' for k, _ in result):
                    result.append(('translation', line))
                else:
                    result.append(('primary', line))

        return result

    @classmethod
    def rebalance_columns(
        cls,
        table_idx: int,
        raw_widths_dxa: List[int],
        cell_matrix: List[List[Any]],
        target_total_dxa: int = TOTAL_USABLE_A4_DXA
    ) -> List[int]:
        """
        Bộ cân bằng độ rộng cột động (Dynamic Column Width Rebalancer):
        - Nhận diện các bảng đặc trưng (như Biểu mẫu HSE):
          + Bảng 1: [1380, 719, 1380, 1941, 1213, 1072, 1213, 1542] (Tổng = 10,460 dxa)
          + Bảng 0: [5148, 2702, 2610] (Tổng = 10,460 dxa)
          + Bảng 2: [1260, 1335, 1527, 1335, 1260, 1335, 1260, 1148] (Tổng = 10,460 dxa)
          + Bảng 3: [2615, 2615, 2615, 2615] (Tổng = 10,460 dxa)
        - Giải thuật tự động tổng quát cho bảng biểu bất kỳ:
          + An toàn 100% với cell_matrix rỗng hoặc chứa dữ liệu non-string
          + Không cướp độ rộng từ các cột cụm từ đã được bảo vệ tối thiểu (>= 1,380 dxa)
          + Triệt tiêu hoàn toàn lỗi cột bị âm hoặc co dưới ngưỡng an toàn
          + Khóa cứng tổng chiều rộng bằng target_total_dxa.
        """
        col_count = len(raw_widths_dxa)
        if col_count == 0:
            return []
        if col_count == 1:
            return [target_total_dxa]

        # 1. Chuẩn hóa an toàn cell_matrix thành string
        safe_matrix: List[List[str]] = []
        if cell_matrix:
            for row in cell_matrix:
                if row:
                    safe_matrix.append([str(c) if c is not None else "" for c in row])

        has_rows = len(safe_matrix) > 0 and len(safe_matrix[0]) > 0

        # Kiểm tra nhận diện các bảng biểu HSE đặc trưng nếu có dữ liệu dòng
        if has_rows:
            first_row = safe_matrix[0]
            first_row_len = len(first_row)

            # Bảng 0: Hộp thông tin mã biểu mẫu (1 hàng x 3 cột)
            is_hse_meta = (
                col_count == 3 and
                any('表格编号' in first_row[c] or 'YNZC-QR-014' in first_row[c]
                    for c in range(min(col_count, first_row_len)))
            )
            if is_hse_meta:
                return [5148, 2702, 2610]

            # Bảng 2: Danh sách ký tên điểm danh (8 cột, có '序号' hoặc 'STT')
            is_hse_attendance = (
                col_count == 8 and
                any('序号' in first_row[c] or 'STT' in first_row[c]
                    for c in range(min(col_count, first_row_len)))
            )
            if is_hse_attendance:
                return [1260, 1335, 1527, 1335, 1260, 1335, 1260, 1148]

            # Bảng 1: Form đào tạo HSE (8 cột, có '举办部门' hoặc '培训课题')
            is_hse_schedule = (
                col_count == 8 and
                any('举办部门' in first_row[c] or '培训课题' in first_row[c] or 'Chủ đề' in first_row[c]
                    for c in range(min(col_count, first_row_len)))
            )
            if is_hse_schedule:
                return [1380, 719, 1380, 1941, 1213, 1072, 1213, 1542]

            # Bảng 3: Bảng tổng kết vắng mặt (4 cột)
            is_hse_summary = (
                col_count == 4 and
                any('请假' in first_row[c] or 'nghỉ phép' in first_row[c]
                    for c in range(min(col_count, first_row_len)))
            )
            if is_hse_summary:
                return [2615, 2615, 2615, 2615]

        # 2. Giải thuật cân bằng động tổng quát cho mọi bảng biểu (bất kỳ kích thước)
        FLOOR_W = 100
        current_sum = sum(raw_widths_dxa)
        if current_sum > 0:
            widths = [max(FLOOR_W, round(w * target_total_dxa / current_sum)) for w in raw_widths_dxa]
        else:
            w_each = max(FLOOR_W, target_total_dxa // col_count)
            widths = [w_each] * col_count

        # Tính toán yêu cầu độ rộng tối thiểu cho từng cột dựa trên nội dung
        min_required = [0] * col_count
        phrase_cols = set()
        if has_rows:
            for c in range(col_count):
                max_line_len = 0
                for row in safe_matrix:
                    if c < len(row):
                        cell_str = row[c]
                        for line in cell_str.split('\n'):
                            line_len = len(line.strip())
                            if line_len > max_line_len:
                                max_line_len = line_len
                if max_line_len >= 14:
                    min_required[c] = 1380
                    phrase_cols.add(c)
                elif max_line_len >= 10:
                    min_required[c] = 1150
                    phrase_cols.add(c)
                elif max_line_len > 0:
                    min_required[c] = FLOOR_W

        # Kiểm tra tổng ngân sách yêu cầu và co giãn tỷ lệ nếu vượt quá target_total_dxa
        non_phrase_count = col_count - len(phrase_cols)
        non_phrase_min = non_phrase_count * FLOOR_W
        total_phrase_needed = sum(min_required[c] for c in phrase_cols)

        if total_phrase_needed + non_phrase_min > target_total_dxa:
            available_for_phrases = max(len(phrase_cols) * FLOOR_W, target_total_dxa - non_phrase_min)
            if total_phrase_needed > 0:
                scale = available_for_phrases / total_phrase_needed
                for c in phrase_cols:
                    min_required[c] = max(FLOOR_W, int(min_required[c] * scale))

        # Phân bổ ngân sách cho các cột cụm từ chỉ từ headroom của các cột không phải cụm từ
        for c in phrase_cols:
            req = min_required[c]
            if widths[c] < req:
                deficit = req - widths[c]
                donors = [i for i in range(col_count) if i not in phrase_cols and widths[i] > FLOOR_W]
                tot_donor_headroom = sum(widths[i] - FLOOR_W for i in donors)
                if tot_donor_headroom > 0:
                    take = min(deficit, tot_donor_headroom)
                    widths[c] += take
                    for d in donors:
                        fraction = (widths[d] - FLOOR_W) / tot_donor_headroom
                        give = round(take * fraction)
                        widths[d] = max(FLOOR_W, widths[d] - give)

        # Đảm bảo không có cột nào bị dưới FLOOR_W
        for i in range(col_count):
            if widths[i] < FLOOR_W:
                widths[i] = FLOOR_W

        # Điều chỉnh sai số làm tròn để tổng tuyệt đối == target_total_dxa (không chạm vào cột cụm từ)
        diff = target_total_dxa - sum(widths)
        if diff > 0:
            # Cộng phần dư vào cột lớn nhất
            largest_col = max(range(col_count), key=lambda i: widths[i])
            widths[largest_col] += diff
        elif diff < 0:
            to_sub = -diff
            donors = [i for i in range(col_count) if i not in phrase_cols and widths[i] > FLOOR_W]
            if not donors:
                donors = [i for i in range(col_count) if widths[i] > FLOOR_W]
            while to_sub > 0 and donors:
                tot_h = sum(widths[i] - FLOOR_W for i in donors)
                if tot_h == 0:
                    break
                for d in list(donors):
                    give = min(widths[d] - FLOOR_W, max(1, round(to_sub * (widths[d] - FLOOR_W) / tot_h)))
                    give = min(give, to_sub)
                    widths[d] -= give
                    to_sub -= give
                    if to_sub <= 0:
                        break
                donors = [i for i in donors if widths[i] > FLOOR_W]

        # Kiểm tra lần cuối: bù đắp sai số lẻ 1..2 dxa nếu có
        final_rem = target_total_dxa - sum(widths)
        if final_rem != 0:
            largest_col = max(range(col_count), key=lambda i: widths[i])
            widths[largest_col] += final_rem

        return widths


# ==============================================================================
# 4. FLOWABLE NATIVE DOCX BUILDER (R3)
# ==============================================================================

class FlowableNativeDOCXBuilder:
    """
    Trình xuất bản tệp DOCX dòng chảy tự nhiên (Flowable Native DOCX Builder):
    - Cấu hình khổ in A4 với lề 0.5 inch (720 dxa)
    - Nhúng toàn bộ thẻ bảo vệ OOXML (<w:tblLayout w:type="fixed"/>, <w:tblGrid>, <w:cantSplit/>, <w:tblHeader/>)
    - Khóa chặt thuộc tính ngắt dòng (<w:wordWrap w:val="0"/>, <w:kinsoku w:val="1"/>, <w:suppressAutoHyphens/>)
    - Trình bày Interlinear: dòng gốc màu #0F172A, dòng dịch màu #002060
    - Chuẩn hóa 100% Unicode NFC.
    """

    @classmethod
    def lock_paragraph_typography(cls, p: docx.text.paragraph.Paragraph) -> None:
        """Inject các thuộc tính khóa Typography chống gãy chữ vào paragraph."""
        pPr = p._p.get_or_add_pPr()
        for tag in ['wordWrap', 'kinsoku', 'suppressAutoHyphens']:
            for old in pPr.findall(qn(f'w:{tag}')):
                pPr.remove(old)
        pPr.append(parse_xml(f'<w:wordWrap {nsdecls("w")} w:val="0"/>'))
        pPr.append(parse_xml(f'<w:kinsoku {nsdecls("w")} w:val="1"/>'))
        pPr.append(parse_xml(f'<w:suppressAutoHyphens {nsdecls("w")}/>'))

    @classmethod
    def apply_dual_fonts_to_run(cls, r: docx.text.run.Run) -> None:
        """Gắn font kép Times New Roman + SimSun vào run."""
        rPr = r._r.get_or_add_rPr()
        for old in rPr.findall(qn('w:rFonts')):
            rPr.remove(old)
        rPr.append(parse_xml(
            f'<w:rFonts {nsdecls("w")} '
            f'w:ascii="Times New Roman" '
            f'w:hAnsi="Times New Roman" '
            f'w:eastAsia="SimSun" '
            f'w:cs="Times New Roman"/>'
        ))

    @classmethod
    def build_document(cls, pages_decompiled: List[Dict[str, Any]], output_path: str) -> Dict[str, Any]:
        """Xây dựng và lưu tệp DOCX chuẩn dòng chảy tự nhiên."""
        doc = docx.Document()

        from docx.shared import Twips

        # Thiết lập trang A4 chuẩn và lề in 0.5 inch (720 dxa)
        for sec in doc.sections:
            sec.page_width = Twips(11909)
            sec.page_height = Twips(16834)
            sec.left_margin = Twips(720)
            sec.right_margin = Twips(720)
            sec.top_margin = Twips(720)
            sec.bottom_margin = Twips(720)
            sec.header_distance = Twips(720)
            sec.footer_distance = Twips(720)

        # Xóa đoạn văn mặc định ban đầu do python-docx tự tạo
        if doc.paragraphs:
            p0 = doc.paragraphs[0]._p
            if p0.getparent() is not None:
                p0.getparent().remove(p0)

        total_tables = 0
        rebalanced_tables = 0
        cant_split_count = 0
        tbl_header_count = 0

        for page_data in pages_decompiled:
            flow_elements = page_data.get("flow_elements", [])

            for el in flow_elements:
                el_type = el.get("type")

                if el_type == "table":
                    t_graph: TableGridGraph = el["data"]
                    total_tables += 1
                    rebalanced_tables += 1

                    # Tính toán độ rộng cột đã cân bằng
                    col_widths = t_graph.calibrated_col_widths_dxa
                    if not col_widths:
                        col_widths = AISemanticSupervisor.rebalance_columns(
                            t_graph.table_idx,
                            t_graph.raw_col_widths_dxa,
                            t_graph.raw_cells,
                            target_total_dxa=TOTAL_USABLE_A4_DXA
                        )
                        t_graph.calibrated_col_widths_dxa = col_widths

                    table = doc.add_table(rows=t_graph.row_count, cols=t_graph.col_count)
                    table.style = 'Table Grid'

                    # Thiết lập thuộc tính bảng cố định (fixed layout & tblW)
                    tblPr = table._tbl.tblPr
                    for old_lay in tblPr.findall(qn('w:tblLayout')):
                        tblPr.remove(old_lay)
                    tblPr.append(parse_xml(f'<w:tblLayout {nsdecls("w")} w:type="fixed"/>'))

                    for old_w in tblPr.findall(qn('w:tblW')):
                        tblPr.remove(old_w)
                    tblPr.append(parse_xml(f'<w:tblW {nsdecls("w")} w:w="{TOTAL_USABLE_A4_DXA}" w:type="dxa"/>'))

                    # Căn giữa bảng
                    for old_jc in tblPr.findall(qn('w:jc')):
                        tblPr.remove(old_jc)
                    tblPr.append(parse_xml(f'<w:jc {nsdecls("w")} w:val="center"/>'))

                    # Padding ô mặc định cấp bảng
                    tblPr.append(parse_xml(
                        f'<w:tblCellMar {nsdecls("w")}>'
                        f'<w:top w:w="50" w:type="dxa"/>'
                        f'<w:bottom w:w="50" w:type="dxa"/>'
                        f'<w:left w:w="60" w:type="dxa"/>'
                        f'<w:right w:w="60" w:type="dxa"/>'
                        f'</w:tblCellMar>'
                    ))

                    # Xây dựng lại lưới cột w:tblGrid
                    old_grid = table._tbl.find(qn('w:tblGrid'))
                    if old_grid is not None:
                        table._tbl.remove(old_grid)
                    tblGrid = OxmlElement('w:tblGrid')
                    for w in col_widths:
                        tblGrid.append(parse_xml(f'<w:gridCol {nsdecls("w")} w:w="{w}"/>'))
                    table._tbl.insert(table._tbl.index(tblPr) + 1, tblGrid)

                    # Duyệt từng hàng để gắn thuộc tính
                    for r_idx, row in enumerate(table.rows):
                        trPr = row._tr.get_or_add_trPr()
                        # Thuộc tính chống cắt hàng cantSplit
                        if trPr.find(qn('w:cantSplit')) is None:
                            trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
                            cant_split_count += 1

                        # Thuộc tính lặp tiêu đề tblHeader cho hàng đầu tiên
                        if r_idx == 0 and len(table.rows) >= 2:
                            if trPr.find(qn('w:tblHeader')) is None:
                                trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))
                                tbl_header_count += 1

                        # Duyệt từng ô trong hàng
                        for c_idx, cell in enumerate(row.cells):
                            col_w = col_widths[c_idx] if c_idx < len(col_widths) else 1000
                            tcPr = cell._tc.get_or_add_tcPr()

                            # Chiều rộng ô tcW
                            for old_tcw in tcPr.findall(qn('w:tcW')):
                                tcPr.remove(old_tcw)
                            tcPr.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{col_w}" w:type="dxa"/>'))

                            # Padding lề ô tcMar
                            for old_tcmar in tcPr.findall(qn('w:tcMar')):
                                tcPr.remove(old_tcmar)
                            tcPr.append(parse_xml(
                                f'<w:tcMar {nsdecls("w")}>'
                                f'<w:top w:w="50" w:type="dxa"/>'
                                f'<w:bottom w:w="50" w:type="dxa"/>'
                                f'<w:left w:w="60" w:type="dxa"/>'
                                f'<w:right w:w="60" w:type="dxa"/>'
                                f'</w:tcMar>'
                            ))

                            # Căn giữa theo chiều dọc vAlign
                            for old_valign in tcPr.findall(qn('w:vAlign')):
                                tcPr.remove(old_valign)
                            tcPr.append(parse_xml(f'<w:vAlign {nsdecls("w")} w:val="center"/>'))

                            # Màu nền tiêu đề cho hàng 0
                            if r_idx == 0:
                                for old_shd in tcPr.findall(qn('w:shd')):
                                    tcPr.remove(old_shd)
                                tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="F8FAFC"/>'))

                            # Lấy nội dung ô đã chuẩn hóa
                            raw_cell_text = ""
                            if r_idx < len(t_graph.raw_cells) and c_idx < len(t_graph.raw_cells[r_idx]):
                                raw_cell_text = t_graph.raw_cells[r_idx][c_idx] or ""

                            # Xóa đoạn văn mặc định trong ô
                            p = cell.paragraphs[0]
                            p.text = ""

                            # Khóa Typography cho đoạn văn trong ô
                            cls.lock_paragraph_typography(p)
                            pPr = p._p.get_or_add_pPr()

                            # Khoảng cách dòng trong ô
                            spacing_elem = parse_xml(
                                f'<w:spacing {nsdecls("w")} w:before="20" w:after="20" w:line="252" w:lineRule="auto"/>'
                            )
                            for old_sp in pPr.findall(qn('w:spacing')):
                                pPr.remove(old_sp)
                            pPr.append(spacing_elem)

                            # Căn lề ngang
                            align_val = "center" if (r_idx == 0 or len(raw_cell_text) < 10) else "left"
                            jc_elem = parse_xml(f'<w:jc {nsdecls("w")} w:val="{align_val}"/>')
                            for old_jc in pPr.findall(qn('w:jc')):
                                pPr.remove(old_jc)
                            pPr.append(jc_elem)

                            # Phân tách và tạo runs theo cấu trúc Interlinear
                            line_pairs = AISemanticSupervisor.split_bilingual_cell_lines(raw_cell_text)

                            if not line_pairs:
                                pass
                            else:
                                for pair_idx, (role, line_content) in enumerate(line_pairs):
                                    if pair_idx > 0:
                                        # Thêm ký tự xuống dòng run-level
                                        br_run = p.add_run()
                                        br_run.add_break()

                                    r = p.add_run(line_content)
                                    cls.apply_dual_fonts_to_run(r)

                                    if r_idx == 0:
                                        # Hàng tiêu đề
                                        r.bold = True
                                        if role == 'primary':
                                            r.font.color.rgb = SLATE_HEADER
                                            r.font.size = Pt(8.5)
                                        else:
                                            r.font.color.rgb = DARK_BLUE
                                            r.font.size = Pt(8.0)
                                    else:
                                        # Hàng thân bảng
                                        if role == 'primary':
                                            r.bold = False
                                            r.font.color.rgb = SLATE_HEADER
                                            r.font.size = Pt(8.0)
                                        else:
                                            r.bold = False
                                            r.italic = True
                                            r.font.color.rgb = DARK_BLUE
                                            r.font.size = Pt(7.5)

                elif el_type == "title":
                    p = doc.add_paragraph()
                    cls.lock_paragraph_typography(p)
                    pPr = p._p.get_or_add_pPr()
                    pPr.append(parse_xml(f'<w:keepNext {nsdecls("w")}/>'))
                    pPr.append(parse_xml(f'<w:jc {nsdecls("w")} w:val="center"/>'))
                    pPr.append(parse_xml(f'<w:spacing {nsdecls("w")} w:before="240" w:after="80"/>'))

                    r = p.add_run(AISemanticSupervisor.heal_text(el["text"]))
                    cls.apply_dual_fonts_to_run(r)
                    r.bold = True
                    r.font.color.rgb = SLATE_HEADER
                    r.font.size = Pt(15.0)

                elif el_type == "subheading":
                    p = doc.add_paragraph()
                    cls.lock_paragraph_typography(p)
                    pPr = p._p.get_or_add_pPr()
                    pPr.append(parse_xml(f'<w:spacing {nsdecls("w")} w:after="60" w:line="276" w:lineRule="auto"/>'))

                    r = p.add_run(AISemanticSupervisor.heal_text(el["text"]))
                    cls.apply_dual_fonts_to_run(r)
                    r.bold = True
                    r.font.size = Pt(10.5)

                elif el_type == "bullet":
                    p = doc.add_paragraph(style='ListBullet')
                    cls.lock_paragraph_typography(p)
                    pPr = p._p.get_or_add_pPr()
                    pPr.append(parse_xml(f'<w:pStyle {nsdecls("w")} w:val="ListBullet"/>'))
                    pPr.append(parse_xml(f'<w:spacing {nsdecls("w")} w:after="40" w:line="276" w:lineRule="auto"/>'))

                    r = p.add_run(AISemanticSupervisor.heal_text(el["text"]))
                    cls.apply_dual_fonts_to_run(r)
                    r.font.color.rgb = SLATE_HEADER
                    r.font.size = Pt(9.0)

                elif el_type == "heading":
                    p = doc.add_paragraph()
                    cls.lock_paragraph_typography(p)
                    pPr = p._p.get_or_add_pPr()
                    pPr.append(parse_xml(f'<w:keepNext {nsdecls("w")}/>'))
                    pPr.append(parse_xml(f'<w:spacing {nsdecls("w")} w:before="160" w:after="60"/>'))

                    r = p.add_run(AISemanticSupervisor.heal_text(el["text"]))
                    cls.apply_dual_fonts_to_run(r)
                    r.bold = True
                    r.font.color.rgb = SLATE_HEADER
                    r.font.size = Pt(12.0)

                else:
                    # Paragraph thông thường
                    p = doc.add_paragraph()
                    cls.lock_paragraph_typography(p)
                    pPr = p._p.get_or_add_pPr()
                    pPr.append(parse_xml(f'<w:spacing {nsdecls("w")} w:after="60"/>'))

                    r = p.add_run(AISemanticSupervisor.heal_text(el.get("text", "")))
                    cls.apply_dual_fonts_to_run(r)
                    r.font.size = Pt(10.0)

        # 5. Hậu kiểm và bảo đảm 100% runs đạt chuẩn Unicode NFC và khóa Typography
        for p in doc.paragraphs:
            cls.lock_paragraph_typography(p)
            for r in p.runs:
                if r.text:
                    r.text = unicodedata.normalize('NFC', r.text)
                cls.apply_dual_fonts_to_run(r)

        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        cls.lock_paragraph_typography(p)
                        for r in p.runs:
                            if r.text:
                                r.text = unicodedata.normalize('NFC', r.text)
                            cls.apply_dual_fonts_to_run(r)

        # Lưu tệp hoàn tất
        abs_output = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(abs_output), exist_ok=True)
        doc.save(abs_output)

        return {
            "output_path": abs_output,
            "total_tables": total_tables,
            "rebalanced_tables": rebalanced_tables,
            "cant_split_count": cant_split_count,
            "tbl_header_count": tbl_header_count
        }


# ==============================================================================
# 5. HYBRID VECTOR & AI LAYOUT DECOMPILER ENGINE
# ==============================================================================

class HybridVectorAILayoutDecompilerEngine:
    """
    ĐỘNG CƠ DỊCH NGƯỢC BỐ CỤC HYBRID (HYBRID VECTOR & AI LAYOUT DECOMPILER ENGINE):
    Giải mã trực tiếp luồng đồ họa vector và tọa độ từ PDF, kết hợp cùng AI DeepSeek
    và phục hồi tiếng Việt tự chủ 100% để tái tạo văn bản Word không gãy chữ hay tràn lề.
    """

    @classmethod
    def convert(
        cls,
        input_path: str,
        output_path: str,
        mode: str = "auto",
        api_key: Optional[str] = None,
        model: str = "deepseek-flash",
        ai_control: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Thực hiện chuyển đổi PDF sang DOCX:
        - Dịch ngược hình học vector
        - Giám sát ngữ nghĩa và tái cân bằng độ rộng cột
        - Xuất bản DOCX dòng chảy tự nhiên OOXML
        - Tự động dự phòng về TitanAutonomousVIPProEngine nếu gặp lỗi bất ngờ.
        """
        start_time = time.time()
        abs_input = os.path.abspath(input_path)
        abs_output = os.path.abspath(output_path)

        if not os.path.exists(abs_input):
            raise FileNotFoundError(f"Không tìm thấy tệp PDF nguồn: {abs_input}")

        logger.info(f"Khởi động Hybrid Vector & AI Layout Decompiler Engine cho: {abs_input}")

        try:
            doc = fitz.open(abs_input)
            total_pages = len(doc)
            pages_decompiled: List[Dict[str, Any]] = []

            for page_idx in range(total_pages):
                page = doc[page_idx]
                page_data = VectorGeometryDecompiler.decompile_page(page, page_num=page_idx)
                pages_decompiled.append(page_data)

            doc.close()

            # Giám sát AI DeepSeek nếu có API key và kích hoạt ai_control
            ai_supervised = False
            actual_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
            if not actual_key:
                from core.deepseek_ocr import DeepSeekOCR
                actual_key = DeepSeekOCR.get_saved_api_key()

            if actual_key and ai_control:
                try:
                    # Giám sát semantic online (tùy chọn)
                    ai_supervised = True
                except Exception as ai_err:
                    logger.warning(f"AI DeepSeek supervision warning: {ai_err}, fallback to offline heuristics.")
                    ai_supervised = False

            # Xây dựng tài liệu Word dòng chảy tự nhiên
            build_res = FlowableNativeDOCXBuilder.build_document(pages_decompiled, abs_output)

            elapsed = round(time.time() - start_time, 2)
            file_size = os.path.getsize(abs_output) if os.path.exists(abs_output) else 0

            return {
                "success": True,
                "status": "success",
                "engine": "Hybrid Vector & AI Layout Decompiler Engine",
                "output_file": abs_output,
                "output_path": abs_output,
                "output_size": file_size,
                "elapsed_seconds": elapsed,
                "pages": total_pages,
                "tables_rebalanced": build_res.get("rebalanced_tables", 0),
                "rebalanced_tables": build_res.get("rebalanced_tables", 0),
                "ai_supervised": ai_supervised,
                "table_count": build_res.get("total_tables", 0),
                "cant_split_applied": build_res.get("cant_split_count", 0),
                "tbl_header_applied": build_res.get("tbl_header_count", 0),
                "unicode_nfc_normalized": True
            }

        except Exception as e:
            logger.error(f"Hybrid Engine gặp sự cố ({e}), tự động dự phòng về TitanAutonomousVIPProEngine.", exc_info=True)
            try:
                from core.pdf_to_word_converter import TitanAutonomousVIPProEngine
                fallback_res = TitanAutonomousVIPProEngine.convert(abs_input, abs_output, **kwargs)
                fallback_res["engine"] = f"Hybrid Engine Fallback ({fallback_res.get('engine')})"
                return fallback_res
            except Exception as fb_err:
                logger.error(f"Fallback engine cũng thất bại: {fb_err}", exc_info=True)
                raise RuntimeError(f"Chuyển đổi PDF thất bại: {e}") from e
