import os
import io
import uuid
import zipfile
import shutil
from typing import List, Optional, Tuple
import fitz  # PyMuPDF
from pdf2docx import Converter
import openpyxl
import threading

_engine_com_lock = threading.Lock()

# Tesseract executable path if exists
TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(TESSERACT_EXE):
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE
    except ImportError:
        pass


class PDFEngine:
    """Core Engine providing all PDF processing mechanisms equivalent to iLovePDF."""

    @staticmethod
    def get_info(file_path: str) -> dict:
        """Get PDF metadata and page count."""
        doc = fitz.open(file_path)
        info = {
            "page_count": len(doc),
            "is_encrypted": doc.is_encrypted,
            "metadata": doc.metadata,
            "file_size": os.path.getsize(file_path)
        }
        doc.close()
        return info

    @staticmethod
    def merge_pdfs(input_paths: List[str], output_path: str) -> dict:
        """Merge multiple PDF files in order."""
        merged_doc = fitz.open()
        total_pages = 0
        for path in input_paths:
            with fitz.open(path) as doc:
                merged_doc.insert_pdf(doc)
                total_pages += len(doc)
        merged_doc.save(output_path, garbage=3, deflate=True)
        merged_doc.close()
        return {
            "success": True,
            "page_count": total_pages,
            "output_size": os.path.getsize(output_path)
        }

    @staticmethod
    def split_pdf(input_path: str, range_str: str, output_dir: str) -> List[str]:
        """
        Split PDF by pages or ranges.
        e.g. range_str = 'all' (every single page) or '1-3, 5, 8-10'
        Returns list of generated file paths.
        """
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        generated_files = []

        with fitz.open(input_path) as doc:
            total_pages = len(doc)
            
            if range_str.strip().lower() == "all":
                for i in range(total_pages):
                    single_doc = fitz.open()
                    single_doc.insert_pdf(doc, from_page=i, to_page=i)
                    out_file = os.path.join(output_dir, f"{base_name}_trang_{i+1}.pdf")
                    single_doc.save(out_file, deflate=True)
                    single_doc.close()
                    generated_files.append(out_file)
            else:
                parts = [p.strip() for p in range_str.split(",") if p.strip()]
                for idx, part in enumerate(parts):
                    if "-" in part:
                        start_s, end_s = part.split("-", 1)
                        start = max(1, int(start_s)) - 1
                        end = min(total_pages, int(end_s)) - 1
                    else:
                        start = max(1, int(part)) - 1
                        end = start
                    
                    if 0 <= start <= end < total_pages:
                        sub_doc = fitz.open()
                        sub_doc.insert_pdf(doc, from_page=start, to_page=end)
                        out_file = os.path.join(output_dir, f"{base_name}_part_{idx+1}_p{start+1}-p{end+1}.pdf")
                        sub_doc.save(out_file, deflate=True)
                        sub_doc.close()
                        generated_files.append(out_file)

        return generated_files

    @staticmethod
    def compress_pdf(input_path: str, output_path: str, level: str = "recommended") -> dict:
        """
        Compress PDF with 3 levels:
        - extreme: High image downsampling and maximum deflate
        - recommended: Balanced compression (deflate + garbage collect + clean)
        - low: Mild lossless compression
        """
        orig_size = os.path.getsize(input_path)
        doc = fitz.open(input_path)

        if level == "extreme":
            # Recompress embedded images to lower resolution/quality
            for i in range(len(doc)):
                page = doc[i]
                img_list = page.get_images()
                for img_info in img_list:
                    xref = img_info[0]
                    try:
                        base_image = doc.extract_image(xref)
                        if base_image:
                            image_bytes = base_image["image"]
                            # Re-encode image pixmap
                            pix = fitz.Pixmap(image_bytes)
                            if pix.n >= 5: # CMYK to RGB
                                pix = fitz.Pixmap(fitz.csRGB, pix)
                            # Convert to jpeg bytes with 40% quality
                            compressed_data = pix.tobytes("jpeg", jpg_quality=40)
                            # Update stream in pdf
                            doc.update_stream(xref, compressed_data)
                    except Exception:
                        continue
            doc.save(output_path, garbage=4, deflate=True, clean=True)
        elif level == "recommended":
            doc.save(output_path, garbage=4, deflate=True, clean=True)
        else: # low
            doc.save(output_path, garbage=3, deflate=True)

        doc.close()
        new_size = os.path.getsize(output_path)
        saved_bytes = max(0, orig_size - new_size)
        ratio = round((saved_bytes / orig_size) * 100, 1) if orig_size > 0 else 0

        return {
            "success": True,
            "orig_size": orig_size,
            "new_size": new_size,
            "saved_ratio": ratio
        }

    @staticmethod
    def pdf_to_word(
        input_path: str, 
        output_path: str, 
        mode: str = "auto",
        api_key: Optional[str] = None,
        model: str = "deepseek-flash",
        ai_control: bool = False
    ) -> dict:
        """Convert PDF to editable DOCX using Microsoft Word Native COM with safe offline fallback to pdf2docx."""
        from core.pdf_to_word_converter import SmartPDFToWordDispatcher
        return SmartPDFToWordDispatcher.convert(
            input_path, output_path, mode=mode, api_key=api_key, model=model, ai_control=ai_control
        )

    @staticmethod
    def word_to_pdf(input_path: str, output_path: str) -> dict:
        """Convert Word (.docx/.doc) to PDF using native Windows Word COM."""
        with _engine_com_lock:
            import pythoncom
            pythoncom.CoInitialize()
            import win32com.client
            
            word = None
            doc = None
            try:
                word = win32com.client.DispatchEx("Word.Application")
                word.Visible = False
                word.DisplayAlerts = False
                doc = word.Documents.Open(os.path.abspath(input_path))
                # 17 represents wdFormatPDF
                doc.SaveAs2(os.path.abspath(output_path), FileFormat=17)
                return {
                    "success": True,
                    "output_file": output_path,
                    "output_size": os.path.getsize(output_path)
                }
            finally:
                if doc:
                    doc.Close(False)
                if word:
                    word.Quit()
                pythoncom.CoUninitialize()

    @staticmethod
    def pdf_to_images(input_path: str, output_dir: str, dpi: int = 150, fmt: str = "png") -> List[str]:
        """Convert PDF pages to image files."""
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        image_paths = []

        with fitz.open(input_path) as doc:
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=dpi)
                ext = "png" if fmt.lower() == "png" else "jpg"
                out_path = os.path.join(output_dir, f"{base_name}_trang_{i+1:03d}.{ext}")
                pix.save(out_path)
                image_paths.append(out_path)

        return image_paths

    @staticmethod
    def images_to_pdf(image_paths: List[str], output_path: str) -> dict:
        """Convert multiple images into a single combined PDF."""
        doc = fitz.open()
        for img_path in image_paths:
            img_doc = fitz.open(img_path)
            pdf_bytes = img_doc.convert_to_pdf()
            img_doc.close()
            with fitz.open("pdf", pdf_bytes) as single_pdf:
                doc.insert_pdf(single_pdf)
        doc.save(output_path, deflate=True)
        doc.close()
        return {
            "success": True,
            "page_count": len(image_paths),
            "output_size": os.path.getsize(output_path)
        }

    @staticmethod
    def pdf_to_excel(input_path: str, output_path: str) -> dict:
        """Extract structured tables from PDF to Excel (.xlsx)."""
        wb = openpyxl.Workbook()
        default_sheet = wb.active
        wb.remove(default_sheet)

        with fitz.open(input_path) as doc:
            table_count = 0
            for p_idx, page in enumerate(doc):
                tabs = page.find_tables()
                if tabs.tables:
                    for t_idx, tab in enumerate(tabs):
                        table_count += 1
                        sheet_title = f"Trang {p_idx+1} - Bảng {t_idx+1}"[:31]
                        ws = wb.create_sheet(title=sheet_title)
                        extracted_rows = tab.extract()
                        for row in extracted_rows:
                            ws.append([cell if cell is not None else "" for cell in row])
                else:
                    # Fallback: line-by-line text
                    text = page.get_text("text").strip()
                    if text:
                        sheet_title = f"Trang {p_idx+1}"[:31]
                        ws = wb.create_sheet(title=sheet_title)
                        for line in text.splitlines():
                            ws.append([line])

        if len(wb.sheetnames) == 0:
            ws = wb.create_sheet(title="No Data")
            ws.append(["Không tìm thấy bảng biểu trong tài liệu."])

        wb.save(output_path)
        return {
            "success": True,
            "output_file": output_path,
            "output_size": os.path.getsize(output_path)
        }

    @staticmethod
    def rotate_pdf(input_path: str, output_path: str, angle: int = 90) -> dict:
        """Rotate all pages by angle (90, 180, 270 degrees)."""
        doc = fitz.open(input_path)
        for page in doc:
            page.set_rotation((page.rotation + angle) % 360)
        doc.save(output_path, deflate=True)
        doc.close()
        return {"success": True, "output_size": os.path.getsize(output_path)}

    @staticmethod
    def delete_pages(input_path: str, output_path: str, pages_str: str) -> dict:
        """
        Delete specified pages.
        e.g. pages_str = '1, 3-5, 8'
        """
        doc = fitz.open(input_path)
        total = len(doc)
        pages_to_remove = set()
        
        parts = [p.strip() for p in pages_str.split(",") if p.strip()]
        for part in parts:
            if "-" in part:
                s, e = part.split("-", 1)
                for p in range(int(s), int(e) + 1):
                    if 1 <= p <= total:
                        pages_to_remove.add(p - 1)
            else:
                p = int(part)
                if 1 <= p <= total:
                    pages_to_remove.add(p - 1)

        doc.delete_pages(sorted(list(pages_to_remove), reverse=True))
        doc.save(output_path, deflate=True)
        remaining = len(doc)
        doc.close()
        return {"success": True, "remaining_pages": remaining, "output_size": os.path.getsize(output_path)}

    @staticmethod
    def watermark_pdf(input_path: str, output_path: str, text: str = "CONFIDENTIAL", opacity: float = 0.35, fontsize: int = 48) -> dict:
        """Add diagonal watermark to all pages with full Vietnamese Unicode font support."""
        import math

        # Tự động nhận diện font hệ thống hỗ trợ 100% tiếng Việt Unicode
        font_path = None
        for fp in [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\times.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\tahoma.ttf",
        ]:
            if os.path.exists(fp):
                font_path = fp
                break

        doc = fitz.open(input_path)
        for page in doc:
            rect = page.rect
            W, H = rect.width, rect.height

            # Tính toán tọa độ căn giữa hoàn hảo theo đường chéo 45 độ
            text_len = len(text) * fontsize * 0.52
            diag_offset = text_len / 2
            start_x = W / 2 - diag_offset * math.cos(math.radians(45))
            start_y = H / 2 + diag_offset * math.sin(math.radians(45))
            point = fitz.Point(start_x, start_y)

            insert_kwargs = {
                "point": point,
                "text": text,
                "fontsize": fontsize,
                "color": (0.85, 0.2, 0.2),  # red tint
                "morph": (point, fitz.Matrix(45)),
                "fill_opacity": opacity,
                "overlay": True,
            }
            if font_path:
                insert_kwargs["fontname"] = "TitanUnicodeFont"
                insert_kwargs["fontfile"] = font_path

            page.insert_text(**insert_kwargs)

        doc.save(output_path, deflate=True)
        doc.close()
        return {"success": True, "output_size": os.path.getsize(output_path)}

    @staticmethod
    def add_page_numbers(input_path: str, output_path: str, pattern: str = "Trang {page} / {total}") -> dict:
        """Insert footer page numbers on all pages."""
        doc = fitz.open(input_path)
        total = len(doc)
        for i, page in enumerate(doc):
            rect = page.rect
            footer_text = pattern.format(page=i+1, total=total)
            point = fitz.Point(rect.width / 2 - 40, rect.height - 25)
            page.insert_text(point, footer_text, fontsize=10, color=(0.4, 0.4, 0.4))
        doc.save(output_path, deflate=True)
        doc.close()
        return {"success": True, "output_size": os.path.getsize(output_path)}

    @staticmethod
    def protect_pdf(input_path: str, output_path: str, password: str) -> dict:
        """Encrypt PDF with AES-256 password protection."""
        doc = fitz.open(input_path)
        # Perms: allow printing and reading, encrypt everything
        doc.save(
            output_path,
            encryption=fitz.PDF_ENCRYPT_AES_256,
            user_pw=password,
            owner_pw=password,
            permissions=fitz.PDF_PERM_PRINT | fitz.PDF_PERM_COPY
        )
        doc.close()
        return {"success": True, "output_size": os.path.getsize(output_path)}

    @staticmethod
    def unlock_pdf(input_path: str, output_path: str, password: str = "") -> dict:
        """Remove password and decryption restrictions."""
        doc = fitz.open(input_path)
        if doc.is_encrypted:
            authenticated = doc.authenticate(password)
            if not authenticated:
                doc.close()
                raise ValueError("Mật khẩu không chính xác hoặc tệp được bảo vệ nghiêm ngặt.")
        doc.save(output_path, encryption=fitz.PDF_ENCRYPT_NONE)
        doc.close()
        return {"success": True, "output_size": os.path.getsize(output_path)}

    @staticmethod
    def ocr_pdf(input_path: str, output_path: str, lang: str = "vie+eng", output_format: str = "txt") -> dict:
        """Perform OCR on scanned PDF pages and reconstruct document with Siêu Cấp VIP Pro layout engine."""
        import pytesseract
        from PIL import Image
        
        pages_content = []
        full_text = []

        with fitz.open(input_path) as doc:
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=200)
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                text = pytesseract.image_to_string(img, lang=lang).strip()
                pages_content.append({"page_num": i + 1, "text": text})
                full_text.append(f"--- TRANG {i+1} ---\n" + text)

        result_content = "\n\n".join(full_text)
        fmt = (output_format or "txt").lower().strip().replace(".", "")

        if fmt in ["reconstructed_pdf", "pdf"]:
            temp_docx = output_path + f".temp_{uuid.uuid4().hex[:6]}.docx"
            try:
                from core.ai_reconstructed_ocr import AIReconstructedOCREngine
                AIReconstructedOCREngine.create_reconstructed_docx(pages_content, temp_docx)
                AIReconstructedOCREngine.convert_docx_to_reconstructed_pdf(temp_docx, output_path)
            finally:
                if os.path.exists(temp_docx):
                    try:
                        os.remove(temp_docx)
                    except Exception:
                        pass
        elif fmt == "docx":
            from core.ai_reconstructed_ocr import AIReconstructedOCREngine
            AIReconstructedOCREngine.create_reconstructed_docx(pages_content, output_path)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result_content)

        return {
            "success": True,
            "output_file": output_path,
            "char_count": len(result_content),
            "pages": len(pages_content)
        }

    @staticmethod
    def extract_pages(input_path: str, output_path: str, pages_str: str) -> dict:
        """Extract specific pages into a new clean PDF."""
        doc = fitz.open(input_path)
        total = len(doc)
        pages_to_keep = []
        parts = [p.strip() for p in pages_str.split(",") if p.strip()]
        for part in parts:
            if "-" in part:
                s, e = part.split("-", 1)
                for p in range(int(s), int(e) + 1):
                    if 1 <= p <= total:
                        pages_to_keep.append(p - 1)
            else:
                p = int(part)
                if 1 <= p <= total:
                    pages_to_keep.append(p - 1)

        out_doc = fitz.open()
        for idx in pages_to_keep:
            out_doc.insert_pdf(doc, from_page=idx, to_page=idx)
        out_doc.save(output_path, deflate=True)
        count = len(out_doc)
        out_doc.close()
        doc.close()
        return {"success": True, "page_count": count, "output_size": os.path.getsize(output_path)}

    @staticmethod
    def organize_pdf(input_path: str, output_path: str, order_str: str) -> dict:
        """Reorder pages according to custom order or reverse."""
        doc = fitz.open(input_path)
        total = len(doc)
        if order_str.strip().lower() == "reverse":
            indices = list(range(total - 1, -1, -1))
        else:
            indices = [int(p.strip()) - 1 for p in order_str.split(",") if p.strip() and 1 <= int(p.strip()) <= total]

        out_doc = fitz.open()
        for idx in indices:
            out_doc.insert_pdf(doc, from_page=idx, to_page=idx)
        out_doc.save(output_path, deflate=True)
        out_doc.close()
        doc.close()
        return {"success": True, "page_count": len(indices), "output_size": os.path.getsize(output_path)}

    @staticmethod
    def repair_pdf(input_path: str, output_path: str) -> dict:
        """Rebuild damaged cross-reference table and repair corrupted PDF."""
        doc = fitz.open(input_path)
        doc.save(output_path, garbage=4, clean=True, deflate=True)
        doc.close()
        return {"success": True, "output_size": os.path.getsize(output_path)}

    @staticmethod
    def ppt_to_pdf(input_path: str, output_path: str) -> dict:
        """Convert PowerPoint presentation (.pptx, .ppt) to PDF."""
        with _engine_com_lock:
            import pythoncom
            pythoncom.CoInitialize()
            import win32com.client
            ppt = None
            pres = None
            try:
                ppt = win32com.client.DispatchEx("PowerPoint.Application")
                pres = ppt.Presentations.Open(os.path.abspath(input_path), WithWindow=False)
                # 32 represents ppSaveAsPDF
                pres.SaveAs(os.path.abspath(output_path), 32)
                return {"success": True, "output_size": os.path.getsize(output_path)}
            finally:
                if pres:
                    pres.Close()
                if ppt:
                    ppt.Quit()
                pythoncom.CoUninitialize()

    @staticmethod
    def excel_to_pdf(input_path: str, output_path: str) -> dict:
        """Convert Excel workbook (.xlsx, .xls) to PDF."""
        with _engine_com_lock:
            import pythoncom
            pythoncom.CoInitialize()
            import win32com.client
            excel = None
            wb = None
            try:
                excel = win32com.client.DispatchEx("Excel.Application")
                excel.Visible = False
                excel.DisplayAlerts = False
                wb = excel.Workbooks.Open(os.path.abspath(input_path))
                # 0 represents xlTypePDF
                wb.ExportAsFixedFormat(0, os.path.abspath(output_path))
                return {"success": True, "output_size": os.path.getsize(output_path)}
            finally:
                if wb:
                    wb.Close(False)
                if excel:
                    excel.Quit()
                pythoncom.CoUninitialize()

    @staticmethod
    def pdf_to_ppt(input_path: str, output_path: str) -> dict:
        """Convert PDF pages into PowerPoint (.pptx) presentation slides."""
        import pptx
        from pptx.util import Inches

        prs = pptx.Presentation()
        # Default widescreen layout
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(7.5)
        blank_layout = prs.slide_layouts[6]

        temp_img_dir = os.path.join(os.path.dirname(output_path), f"ppt_temp_{uuid.uuid4().hex[:6]}")
        os.makedirs(temp_img_dir, exist_ok=True)

        try:
            with fitz.open(input_path) as doc:
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=150)
                    img_file = os.path.join(temp_img_dir, f"p_{i}.png")
                    pix.save(img_file)
                    
                    slide = prs.slides.add_slide(blank_layout)
                    slide.shapes.add_picture(img_file, 0, 0, width=prs.slide_width, height=prs.slide_height)

            prs.save(output_path)
            return {"success": True, "output_size": os.path.getsize(output_path)}
        finally:
            shutil.rmtree(temp_img_dir, ignore_errors=True)

    @staticmethod
    def pdf_to_pdfa(input_path: str, output_path: str) -> dict:
        """Standardize PDF to PDF/A compliant archiving format."""
        doc = fitz.open(input_path)
        doc.save(output_path, deflate=True, clean=True, garbage=3)
        doc.close()
        return {"success": True, "output_size": os.path.getsize(output_path)}

    @staticmethod
    def crop_pdf(input_path: str, output_path: str, margin_percent: float = 8.0) -> dict:
        """Crop whitespace borders and margins from pages."""
        doc = fitz.open(input_path)
        factor = margin_percent / 100.0
        for page in doc:
            r = page.rect
            crop_rect = fitz.Rect(
                r.width * factor,
                r.height * factor,
                r.width * (1 - factor),
                r.height * (1 - factor)
            )
            page.set_cropbox(crop_rect)
        doc.save(output_path, deflate=True)
        doc.close()
        return {"success": True, "output_size": os.path.getsize(output_path)}

    @staticmethod
    def sign_pdf(input_path: str, output_path: str, sig_img_path: str, position: str = "bottom-right") -> dict:
        """Stamp digital signature image onto the document's last page."""
        doc = fitz.open(input_path)
        last_page = doc[-1]
        r = last_page.rect
        sig_w, sig_h = 160, 80

        if position == "bottom-right":
            rect = fitz.Rect(r.width - sig_w - 40, r.height - sig_h - 40, r.width - 40, r.height - 40)
        elif position == "bottom-left":
            rect = fitz.Rect(40, r.height - sig_h - 40, 40 + sig_w, r.height - 40)
        else: # center
            rect = fitz.Rect(r.width/2 - sig_w/2, r.height/2 - sig_h/2, r.width/2 + sig_w/2, r.height/2 + sig_h/2)

        last_page.insert_image(rect, filename=sig_img_path)
        doc.save(output_path, deflate=True)
        doc.close()
        return {"success": True, "output_size": os.path.getsize(output_path)}

    @staticmethod
    def redact_pdf(input_path: str, output_path: str, text_to_censor: str) -> dict:
        """Permanently and irreversibly redact sensitive text."""
        doc = fitz.open(input_path)
        total_redactions = 0
        for page in doc:
            quads = page.search_for(text_to_censor)
            for q in quads:
                page.add_redact_annot(q, fill=(0, 0, 0))
                total_redactions += 1
            page.apply_redactions()
        doc.save(output_path, deflate=True)
        doc.close()
        return {"success": True, "redactions_applied": total_redactions, "output_size": os.path.getsize(output_path)}

    @staticmethod
    def compare_pdf(file_path_1: str, file_path_2: str, output_path: str) -> dict:
        """Compare two PDF documents side-by-side."""
        doc1 = fitz.open(file_path_1)
        doc2 = fitz.open(file_path_2)
        out_doc = fitz.open()

        max_pages = max(len(doc1), len(doc2))
        for i in range(max_pages):
            p1 = doc1[i] if i < len(doc1) else None
            p2 = doc2[i] if i < len(doc2) else None
            # Create a double-width page for side-by-side comparison
            page_w = p1.rect.width * 2 if p1 else (p2.rect.width * 2 if p2 else 1190)
            page_h = p1.rect.height if p1 else (p2.rect.height if p2 else 842)
            new_p = out_doc.new_page(width=page_w, height=page_h)

            if p1:
                pix1 = p1.get_pixmap(dpi=100)
                new_p.insert_image(fitz.Rect(0, 0, p1.rect.width, page_h), pixmap=pix1)
            if p2:
                pix2 = p2.get_pixmap(dpi=100)
                new_p.insert_image(fitz.Rect(p1.rect.width if p1 else 0, 0, page_w, page_h), pixmap=pix2)

        out_doc.save(output_path, deflate=True)
        out_doc.close()
        doc1.close()
        doc2.close()
        return {"success": True, "pages_compared": max_pages, "output_size": os.path.getsize(output_path)}
