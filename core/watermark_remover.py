import os
import re
import fitz
from typing import Optional, List, Dict, Any

class WatermarkRemover:
    """
    TitanPDF Watermark & Background Artifacts Cleaner
    - Tự động phát hiện và loại bỏ chữ mờ watermark (Text Watermarks)
    - Xóa ảnh nền chìm, logo mờ (Background & XObject Images)
    - Xóa các tem mộc chú thích (Stamp & Watermark Annotations)
    - Tẩy sạch vệt quảng cáo mép trang (Header & Footer Ads)
    100% Cục bộ & Không giảm chất lượng các thành phần văn bản khác.
    """

    COMMON_KEYWORDS = [
        "draft", "confidential", "sample", "copy", "do not copy",
        "watermark", "evaluation", "camscanner", "scanned by",
        "bản nháp", "nháp", "tài liệu nội bộ", "mẫu", "tạm thời",
        "không sao chép", "bản sao", "bảo lưu", "internal use only",
        "preview", "demo", "specimen", "personal copy", "duplicate",
        "scanned with", "created with", "unregistered"
    ]

    @classmethod
    def clean_pdf(
        cls,
        input_path: str,
        output_path: str,
        custom_text: Optional[str] = None,
        use_common_keywords: bool = True,
        remove_bg_images: bool = True,
        remove_annotations: bool = True,
        clean_headers_footers: bool = False,
        header_footer_margin: float = 35.0
    ) -> Dict[str, Any]:
        """
        Quét và loại bỏ sạch sẽ các lớp Watermark và nền rác khỏi PDF.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Tệp tin không tồn tại: {input_path}")

        doc = fitz.open(input_path)
        total_pages = len(doc)
        total_text_removed = 0
        total_images_removed = 0
        total_annots_removed = 0

        # Build list of search keywords
        keywords_to_remove = []
        if custom_text and custom_text.strip():
            # Support comma-separated or newline-separated custom texts
            for piece in re.split(r"[,;\n]+", custom_text):
                p = piece.strip()
                if p:
                    keywords_to_remove.append(p)

        if use_common_keywords:
            for kw in cls.COMMON_KEYWORDS:
                if kw not in keywords_to_remove:
                    keywords_to_remove.append(kw)

        for page_idx in range(total_pages):
            page = doc[page_idx]
            page_rect = page.rect
            page_area = page_rect.width * page_rect.height

            # 1. REMOVE ANNOTATIONS (STAMP, WATERMARK, TEXT)
            if remove_annotations:
                annots = list(page.annots() or [])
                for annot in annots:
                    subtype = annot.type[0]
                    # PDF_ANNOT_STAMP = 13, PDF_ANNOT_WATERMARK = 25
                    if subtype in (fitz.PDF_ANNOT_STAMP, fitz.PDF_ANNOT_WATERMARK):
                        page.delete_annot(annot)
                        total_annots_removed += 1
                    else:
                        # Check annot contents/title for watermark keywords
                        info = annot.info
                        content = (info.get("content", "") + " " + info.get("title", "")).lower()
                        if any(kw.lower() in content for kw in keywords_to_remove):
                            page.delete_annot(annot)
                            total_annots_removed += 1

            # 2. REMOVE TEXT WATERMARKS VIA REDACTION (fill=None purges glyphs without white boxes)
            redact_applied_on_page = False
            for kw in keywords_to_remove:
                if not kw:
                    continue
                # Case-insensitive text search
                instances = page.search_for(kw)
                if instances:
                    for rect in instances:
                        page.add_redact_annot(rect, fill=None)
                        total_text_removed += 1
                        redact_applied_on_page = True

            # 3. CLEAN HEADERS & FOOTERS (OPTIONAL)
            if clean_headers_footers and header_footer_margin > 0:
                # Top header bar
                header_rect = fitz.Rect(0, 0, page_rect.width, header_footer_margin)
                # Bottom footer bar
                footer_rect = fitz.Rect(0, page_rect.height - header_footer_margin, page_rect.width, page_rect.height)
                
                # Check if there is text matching ads/watermarks in header/footer
                for rect_zone in [header_rect, footer_rect]:
                    zone_text = page.get_text("text", clip=rect_zone).strip().lower()
                    if zone_text and any(kw in zone_text for kw in ["camscanner", "scanned", "watermark", "page", "trang", "created"]):
                        page.add_redact_annot(rect_zone, fill=None)
                        redact_applied_on_page = True

            # Apply redactions if any text was marked
            if redact_applied_on_page:
                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

            # 4. REMOVE BACKGROUND & TRANSPARENT WATERMARK IMAGES
            if remove_bg_images:
                img_list = list(page.get_images() or [])
                for img_info in img_list:
                    xref = img_info[0]
                    smask = img_info[1] # smask indicates transparency mask
                    rects = page.get_image_rects(xref)
                    
                    for r in rects:
                        r_area = r.width * r.height
                        ratio = r_area / max(1, page_area)
                        
                        # Background condition:
                        # a) Covers a large portion of the page (ratio > 0.45)
                        # b) Or has transparency mask (smask != 0) and is centered or covers > 25% of page
                        is_bg = False
                        if ratio >= 0.50:
                            is_bg = True
                        elif smask != 0 and ratio >= 0.20:
                            is_bg = True

                        if is_bg:
                            try:
                                # Native clean purge
                                page.delete_image(xref)
                                total_images_removed += 1
                            except Exception:
                                pass
                            break

        # Save cleaned document with optimization & garbage collection
        doc.save(
            output_path,
            garbage=4,
            deflate=True,
            clean=True
        )
        doc.close()

        total_cleaned = total_text_removed + total_images_removed + total_annots_removed
        summary_msg = f"Đã quét {total_pages} trang: Xóa {total_text_removed} mục chữ mờ, {total_images_removed} ảnh nền rác, {total_annots_removed} tem mộc."

        return {
            "success": True,
            "filename": os.path.basename(output_path),
            "total_pages": total_pages,
            "text_removed": total_text_removed,
            "images_removed": total_images_removed,
            "annots_removed": total_annots_removed,
            "total_cleaned": total_cleaned,
            "details": summary_msg
        }
