"""
Module: core/ghs_image_detector.py
Chuyên gia nhận diện hình đồ cảnh báo nguy hiểm GHS (GHS01 - GHS09) trực tiếp từ hình ảnh
vật lý có trong tài liệu MSDS/SDS (.docx, .doc, .pdf).

Nguyên tắc cốt lõi:
- Nhận diện dựa trên HÌNH ĐỒ THỰC TẾ mà tệp MSDS đang có (ở Mục 2 / Yếu tố nhãn),
  TUYỆT ĐỐI KHÔNG tự suy diễn hoặc phóng đại thêm các mã GHS khác từ câu chữ mô tả nguy cơ.
- Hỗ trợ cả 9 hình đồ chuẩn UN GHS quốc tế:
  GHS01: Bom nổ (Exploding Bomb)
  GHS02: Ngọn lửa (Flame)
  GHS03: Ngọn lửa trên vòng tròn (Flame over circle)
  GHS04: Bình khí nén (Gas Cylinder)
  GHS05: Ăn mòn (Corrosion)
  GHS06: Đầu lâu xương chéo (Skull and Crossbones)
  GHS07: Dấu chấm than (Exclamation Mark)
  GHS08: Nguy hại sức khỏe lâu dài (Health Hazard)
  GHS09: Môi trường (Environment)
"""

import os
import re
import io
import cv2
import numpy as np
from PIL import Image
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
import fitz  # PyMuPDF
import docx

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ghs_templates")

class GHSImageDetector:
    """Bộ nhận diện hình đồ GHS trực tiếp từ ảnh trong tài liệu Word và PDF."""

    _templates: Optional[Dict[str, Tuple[np.ndarray, float]]] = None

    @classmethod
    def _init_templates(cls):
        """Khởi tạo và nạp trước bộ mặt nạ chuẩn 9 biểu trưng UN GHS."""
        if cls._templates is not None:
            return

        cls._templates = {}
        for i in range(1, 10):
            code = f"GHS0{i}"
            png_path = os.path.join(TEMPLATES_DIR, f"{code}.png")
            if os.path.exists(png_path):
                crop, dens = cls._extract_symbol_crop(png_path)
                cls._templates[code] = (crop, dens)

    @classmethod
    def _extract_symbol_crop(cls, img_input: Any, target_size: Tuple[int, int] = (128, 128)) -> Tuple[np.ndarray, float]:
        """Bóc tách biểu trưng đen bên trong hình thoi viền đỏ GHS và chuẩn hóa kích thước."""
        if isinstance(img_input, (str, Path)):
            im = Image.open(str(img_input)).convert("RGB")
            arr = np.array(im)
        elif isinstance(img_input, bytes):
            im = Image.open(io.BytesIO(img_input)).convert("RGB")
            arr = np.array(im)
        elif isinstance(img_input, np.ndarray):
            arr = img_input
        else:
            return np.zeros(target_size, dtype=np.uint8), 0.0

        h, w, _ = arr.shape
        if h < 15 or w < 15:
            return np.zeros(target_size, dtype=np.uint8), 0.0

        r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
        # Phát hiện viền đỏ của hình thoi GHS
        is_red = (r > 125) & (g < 125) & (b < 125) & ((r - g) > 20) & ((r - b) > 20)

        # Lấy các điểm ảnh màu tối/đen (biểu trưng bên trong)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        is_dark = (gray < 130) & (~is_red)

        # Giới hạn trong vùng trung tâm 76% (loại bỏ viền ngoài)
        my, mx = int(h * 0.12), int(w * 0.12)
        inner = np.zeros_like(is_dark, dtype=np.uint8)
        inner[my:h - my, mx:w - mx] = is_dark[my:h - my, mx:w - mx].astype(np.uint8) * 255

        pts = cv2.findNonZero(inner)
        if pts is not None:
            bx, by, bw, bh = cv2.boundingRect(pts)
            if bw >= 4 and bh >= 4:
                crop = inner[by:by + bh, bx:bx + bw]
                resized = cv2.resize(crop, target_size, interpolation=cv2.INTER_AREA)
                _, binary = cv2.threshold(resized, 50, 255, cv2.THRESH_BINARY)
                density = float(pts.shape[0]) / float(h * w)
                return binary, density

        return np.zeros(target_size, dtype=np.uint8), 0.0

    @classmethod
    def _has_oxidizing_circle(cls, binary_crop: np.ndarray) -> bool:
        """Kiểm tra xem biểu trưng có vòng tròn rỗng đặc trưng của GHS03 (Chất oxy hóa) không."""
        contours, hierarchy = cv2.findContours(binary_crop, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is not None:
            for i, h in enumerate(hierarchy[0]):
                if h[3] != -1:  # Có contour cha -> đây là lỗ hổng bên trong
                    area = cv2.contourArea(contours[i])
                    peri = cv2.arcLength(contours[i], True)
                    if peri > 0:
                        circularity = 4 * np.pi * area / (peri * peri)
                        if circularity > 0.55 and area > 45:
                            return True
        return False

    @classmethod
    def is_ghs_diamond_image(cls, img_bytes_or_path: Any) -> bool:
        """Kiểm tra xem một ảnh có phải là hình thoi cảnh báo GHS hay không (dựa trên tỷ lệ đỏ và hình học)."""
        try:
            if isinstance(img_bytes_or_path, (str, Path)):
                im = Image.open(str(img_bytes_or_path)).convert("RGB")
            else:
                im = Image.open(io.BytesIO(img_bytes_or_path)).convert("RGB")
            
            w, h = im.size
            if w < 20 or h < 20:
                return False
            
            # Tỷ lệ khung hình thoi GHS chuẩn gần như vuông (0.65 đến 1.5)
            aspect = float(w) / float(h)
            if aspect < 0.65 or aspect > 1.55:
                return False

            arr = np.array(im)
            r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
            is_red = (r > 125) & (g < 125) & (b < 125) & ((r - g) > 20) & ((r - b) > 20)
            red_ratio = float(np.mean(is_red))

            # Viền đỏ hình thoi chiếm từ 6% đến 35% diện tích ảnh
            if red_ratio >= 0.05:
                return True

            # Kiểm tra ảnh đen trắng (nếu tài liệu photo/scan)
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            is_dark = gray < 100
            dark_ratio = float(np.mean(is_dark))
            if 0.04 <= dark_ratio <= 0.35:
                # Nếu có biểu trưng bên trong vùng trung tâm
                _, dens = cls._extract_symbol_crop(arr)
                if dens >= 0.02:
                    return True

            return False
        except Exception:
            return False

    @classmethod
    def classify_pictogram_image(cls, img_bytes_or_path: Any) -> Tuple[Optional[str], float]:
        """
        Phân loại chính xác một ảnh hình đồ thành mã GHS01..GHS09.
        Trả về (mã_ghs, độ_tin_cậy).
        """
        cls._init_templates()
        if not cls._templates:
            return None, 0.0

        q_crop, q_dens = cls._extract_symbol_crop(img_bytes_or_path)
        if np.sum(q_crop) < 15 or q_dens < 0.01:
            return None, 0.0

        scores: Dict[str, float] = {}
        for code, (t_crop, t_dens) in cls._templates.items():
            # Tương quan chéo (Cross-correlation)
            corr = cv2.matchTemplate(q_crop, t_crop, cv2.TM_CCOEFF_NORMED)[0][0]
            # Độ tương đồng IoU
            q_b = q_crop > 0
            t_b = t_crop > 0
            intersection = np.sum(q_b & t_b)
            union = np.sum(q_b | t_b)
            iou = float(intersection) / float(union) if union > 0 else 0.0
            # Độ tương đồng mật độ nét đen
            dens_ratio = min(q_dens, t_dens) / max(q_dens, t_dens) if max(q_dens, t_dens) > 0 else 0.0

            score = 0.5 * max(0.0, float(corr)) + 0.35 * iou + 0.15 * dens_ratio
            scores[code] = score

        # Xử lý phân biệt đặc biệt giữa GHS02 (Ngọn lửa dễ cháy) và GHS03 (Chất oxy hóa)
        # GHS03 bắt buộc phải có vòng tròn rỗng bên dưới ngọn lửa
        if "GHS03" in scores and "GHS02" in scores:
            has_circle = cls._has_oxidizing_circle(q_crop)
            if not has_circle and scores["GHS03"] > scores["GHS02"]:
                scores["GHS02"] = max(scores["GHS02"], scores["GHS03"] + 0.05)
                scores["GHS03"] *= 0.5

        best_code = max(scores, key=scores.get)
        best_score = scores[best_code]

        if best_score >= 0.25:
            return best_code, best_score
        return None, best_score

    @classmethod
    def extract_label_ghs_images_from_docx(cls, doc_path: str) -> List[bytes]:
        """
        Trích xuất hình ảnh biểu trưng GHS nằm chính xác tại hàng 'Hình đồ cảnh báo' / 'Hazard pictogram'
        ở Mục 2 của tệp Word (.docx).
        """
        d = docx.Document(doc_path)
        extracted_images: List[bytes] = []

        label_keywords = [
            "hình đồ cảnh báo", "hình đồ", "hazard pictogram", "pictogram",
            "biểu trưng", "ghs pictogram", "biểu tượng nguy hiểm", "nhãn ghs",
            "危险象形图", "象形图"
        ]

        found_in_target_cell = False

        # 1. Quét theo bảng biểu (Tables)
        for table in d.tables:
            for row in table.rows:
                cells_text = [c.text.strip().lower() for c in row.cells]
                # Kiểm tra xem hàng này có phải là hàng Hình đồ cảnh báo không
                is_pictogram_row = any(any(k in ct for k in label_keywords) for ct in cells_text)
                if is_pictogram_row:
                    for cell in row.cells:
                        xml = cell._tc.xml
                        # Tìm các rId nhúng ảnh
                        rids = re.findall(r'r:embed="([^"]+)"', xml) + re.findall(r'r:id="([^"]+)"', xml)
                        for rid in rids:
                            if rid in d.part.rels:
                                rel = d.part.rels[rid]
                                if "image" in rel.target_ref:
                                    img_data = rel.target_part.blob
                                    if cls.is_ghs_diamond_image(img_data):
                                        extracted_images.append(img_data)
                                        found_in_target_cell = True

        if extracted_images:
            return extracted_images

        # 2. Nếu không tìm thấy trong ô cụ thể, quét toàn bộ ảnh của Phần 2
        sec2_images: List[bytes] = []
        for rel in d.part.rels.values():
            if "image" in rel.target_ref:
                img_data = rel.target_part.blob
                if cls.is_ghs_diamond_image(img_data):
                    sec2_images.append(img_data)

        return sec2_images

    @classmethod
    def extract_label_ghs_images_from_pdf(cls, pdf_path: str) -> List[bytes]:
        """
        Trích xuất các ảnh biểu trưng GHS tại Mục 2 / Yếu tố nhãn trong tệp PDF.
        """
        doc = fitz.open(pdf_path)
        extracted: List[bytes] = []

        # Mục 2 luôn nằm ở Trang 1 hoặc Trang 2
        for page_idx in range(min(3, len(doc))):
            page = doc[page_idx]
            page_text = page.get_text("text").lower()
            
            # Kiểm tra xem trang có Phần 2 / Nhận dạng nguy hiểm không
            if not any(k in page_text for k in ["nhận dạng", "hazard", "mục 2", "section 2", "phần 2", "pictogram", "hình đồ"]):
                continue

            images = page.get_images(full=True)
            for img_info in images:
                xref = img_info[0]
                base_img = doc.extract_image(xref)
                img_bytes = base_img["image"]
                
                # Kiểm tra kích thước và tính chất hình thoi GHS
                if cls.is_ghs_diamond_image(img_bytes):
                    # Kiểm tra vị trí hình ảnh trên trang:
                    rects = page.get_image_rects(xref)
                    if rects:
                        r = rects[0]
                        # Không lấy logo công ty ở sát mép trên cùng (y < 120 mà có chữ header)
                        if r.y0 < 110 and r.width > 200:
                            continue
                    extracted.append(img_bytes)

            if extracted:
                break

        doc.close()
        return extracted

    @classmethod
    def detect_ghs_pictograms_from_file(cls, file_path: str) -> List[str]:
        """
        Đọc và phân tích trực tiếp các hình đồ GHS có mặt trong tệp (.docx, .doc, .pdf).
        Trả về danh sách mã GHS duy nhất (ví dụ: ['GHS02'] hoặc ['GHS02', 'GHS07']).
        Nếu tệp không có bất kỳ hình đồ nào -> trả về [].
        """
        p = Path(file_path)
        ext = p.suffix.lower()
        extracted_images: List[bytes] = []

        if ext == ".docx":
            extracted_images = cls.extract_label_ghs_images_from_docx(file_path)
        elif ext == ".doc":
            # Tệp Word .doc: Chuyển sang .docx tạm thời
            temp_docx = str(p.parent / f"temp_ghs_{p.stem}.docx")
            try:
                from core.interlinear_translator import convert_doc_to_docx
                conv_path = convert_doc_to_docx(file_path, temp_docx)
                extracted_images = cls.extract_label_ghs_images_from_docx(conv_path)
                try:
                    os.remove(conv_path)
                except Exception:
                    pass
            except Exception as e:
                print(f"[GHSImageDetector] Lỗi chuyển đổi .doc sang .docx: {e}")
        elif ext == ".pdf":
            extracted_images = cls.extract_label_ghs_images_from_pdf(file_path)

        if not extracted_images:
            return []

        detected_codes = []
        for img_bytes in extracted_images:
            code, conf = cls.classify_pictogram_image(img_bytes)
            if code and code not in detected_codes:
                detected_codes.append(code)

        return sorted(detected_codes)
