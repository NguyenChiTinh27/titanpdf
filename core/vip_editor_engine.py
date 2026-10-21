import os
import json
import base64
import fitz

class VIPEditorEngine:
    """
    VIP Editor Engine - Động cơ chỉnh sửa và biên tập tài liệu PDF VIP Pro.
    Tái tạo toàn bộ các lớp vector (Shapes, Chữ viết Unicode, Vẽ tự do, Dạ quang, Hình ảnh)
    trực tiếp vào trang PDF gốc với chất lượng Vector 100% siêu nét, không nén vỡ hạt.
    """

    BUNDLED_FONT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "fonts", "DejaVuSans.ttf"))
    WINDOWS_FONT_PATH = "C:/Windows/Fonts/arial.ttf"

    @classmethod
    def get_font_path(cls):
        candidates = [
            cls.BUNDLED_FONT_PATH,
            cls.WINDOWS_FONT_PATH,
            "C:/Windows/Fonts/times.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    @staticmethod
    def hex_to_rgb(hex_str):
        if not hex_str or hex_str.lower() in ("none", "transparent"):
            return None
        hex_str = hex_str.lstrip("#")
        if len(hex_str) == 6:
            return tuple(int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4))
        elif len(hex_str) == 3:
            return tuple(int(hex_str[i]*2, 16) / 255.0 for i in range(3))
        return (0, 0, 0)

    @classmethod
    def apply_annotations(cls, input_pdf_path: str, output_pdf_path: str, annotations: list) -> dict:
        """
        Nhúng danh sách các annotation tương tác từ Editor Canvas vào tài liệu PDF gốc.
        """
        doc = fitz.open(input_pdf_path)
        if not doc.is_pdf:
            pdf_bytes = doc.convert_to_pdf()
            doc = fitz.open("pdf", pdf_bytes)
        font_path = cls.get_font_path()

        # Group annotations by page (1-indexed from client)
        page_annots = {}
        for ann in annotations:
            p_num = int(ann.get("page", 1))
            if p_num not in page_annots:
                page_annots[p_num] = []
            page_annots[p_num].append(ann)

        applied_count = 0

        for p_num, items in page_annots.items():
            if p_num < 1 or p_num > len(doc):
                continue
            page = doc[p_num - 1]
            page_rect = page.rect
            
            # Client canvas dimensions (if supplied for scale mapping)
            for item in items:
                ann_type = item.get("type", "").lower()
                c_w = float(item.get("canvasWidth", page_rect.width) or page_rect.width)
                c_h = float(item.get("canvasHeight", page_rect.height) or page_rect.height)
                scale_x = page_rect.width / c_w if c_w > 0 else 1.0
                scale_y = page_rect.height / c_h if c_h > 0 else 1.0

                shape = page.new_shape()

                if ann_type in ("pen", "draw"):
                    pts_raw = item.get("points", [])
                    if len(pts_raw) > 1:
                        pts = [fitz.Point(p["x"] * scale_x, p["y"] * scale_y) for p in pts_raw]
                        stroke_rgb = cls.hex_to_rgb(item.get("color", "#ef4444")) or (0.9, 0.2, 0.2)
                        stroke_w = float(item.get("width", 2.5)) * scale_x
                        opacity = float(item.get("opacity", 1.0))
                        shape.draw_polyline(pts)
                        shape.finish(color=stroke_rgb, width=stroke_w, stroke_opacity=opacity)
                        shape.commit()
                        applied_count += 1

                elif ann_type == "highlighter":
                    pts_raw = item.get("points", [])
                    if len(pts_raw) > 1:
                        pts = [fitz.Point(p["x"] * scale_x, p["y"] * scale_y) for p in pts_raw]
                        hl_rgb = cls.hex_to_rgb(item.get("color", "#f472b6")) or (0.95, 0.45, 0.7)
                        stroke_w = float(item.get("width", 16.0)) * scale_x
                        opacity = float(item.get("opacity", 0.45))
                        shape.draw_polyline(pts)
                        shape.finish(color=hl_rgb, width=stroke_w, stroke_opacity=opacity)
                        shape.commit()
                        applied_count += 1

                elif ann_type == "rect":
                    x = float(item.get("x", 0)) * scale_x
                    y = float(item.get("y", 0)) * scale_y
                    w = float(item.get("width", 50)) * scale_x
                    h = float(item.get("height", 30)) * scale_y
                    stroke_rgb = cls.hex_to_rgb(item.get("strokeColor", "#2563eb"))
                    fill_rgb = cls.hex_to_rgb(item.get("fillColor", "none"))
                    stroke_w = float(item.get("strokeWidth", 2)) * scale_x
                    opacity = float(item.get("opacity", 1.0))

                    rect = fitz.Rect(x, y, x + w, y + h)
                    shape.draw_rect(rect)
                    shape.finish(
                        color=stroke_rgb if stroke_rgb else None,
                        fill=fill_rgb if fill_rgb else None,
                        width=stroke_w,
                        stroke_opacity=opacity,
                        fill_opacity=opacity if fill_rgb else 0.0
                    )
                    shape.commit()
                    applied_count += 1

                elif ann_type in ("circle", "ellipse"):
                    x = float(item.get("x", 0)) * scale_x
                    y = float(item.get("y", 0)) * scale_y
                    w = float(item.get("width", 50)) * scale_x
                    h = float(item.get("height", 50)) * scale_y
                    stroke_rgb = cls.hex_to_rgb(item.get("strokeColor", "#2563eb"))
                    fill_rgb = cls.hex_to_rgb(item.get("fillColor", "none"))
                    stroke_w = float(item.get("strokeWidth", 2)) * scale_x
                    opacity = float(item.get("opacity", 1.0))

                    rect = fitz.Rect(x, y, x + w, y + h)
                    shape.draw_oval(rect)
                    shape.finish(
                        color=stroke_rgb if stroke_rgb else None,
                        fill=fill_rgb if fill_rgb else None,
                        width=stroke_w,
                        stroke_opacity=opacity,
                        fill_opacity=opacity if fill_rgb else 0.0
                    )
                    shape.commit()
                    applied_count += 1

                elif ann_type in ("line", "arrow"):
                    x1 = float(item.get("x1", 0)) * scale_x
                    y1 = float(item.get("y1", 0)) * scale_y
                    x2 = float(item.get("x2", 50)) * scale_x
                    y2 = float(item.get("y2", 50)) * scale_y
                    stroke_rgb = cls.hex_to_rgb(item.get("strokeColor", "#ef4444")) or (0.9, 0.2, 0.2)
                    stroke_w = float(item.get("strokeWidth", 2)) * scale_x
                    opacity = float(item.get("opacity", 1.0))

                    shape.draw_line(fitz.Point(x1, y1), fitz.Point(x2, y2))
                    shape.finish(color=stroke_rgb, width=stroke_w, stroke_opacity=opacity)
                    shape.commit()
                    applied_count += 1

                elif ann_type == "text":
                    text_str = str(item.get("text", "")).strip()
                    if text_str:
                        x = float(item.get("x", 0)) * scale_x
                        y = float(item.get("y", 0)) * scale_y
                        w = max(float(item.get("width", 200)) * scale_x, 50)
                        h = max(float(item.get("height", 50)) * scale_y, 25)
                        font_size = float(item.get("fontSize", 16)) * scale_x
                        text_rgb = cls.hex_to_rgb(item.get("color", "#0f172a")) or (0.1, 0.1, 0.1)

                        rect = fitz.Rect(x, y, x + w, y + h)
                        if font_path:
                            page.insert_textbox(rect, text_str, fontsize=font_size, color=text_rgb, fontfile=font_path)
                        else:
                            page.insert_textbox(rect, text_str, fontsize=font_size, color=text_rgb, fontname="helv")
                        applied_count += 1

                elif ann_type == "image":
                    img_b64 = item.get("imageBase64", "")
                    if img_b64:
                        if "," in img_b64:
                            img_b64 = img_b64.split(",")[1]
                        try:
                            img_bytes = base64.b64decode(img_b64)
                            x = float(item.get("x", 0)) * scale_x
                            y = float(item.get("y", 0)) * scale_y
                            w = float(item.get("width", 100)) * scale_x
                            h = float(item.get("height", 80)) * scale_y
                            rect = fitz.Rect(x, y, x + w, y + h)
                            page.insert_image(rect, stream=img_bytes)
                            applied_count += 1
                        except Exception as img_err:
                            print(f"[VIPEditorEngine] Image decode warning: {img_err}")

        # Save result with high optimization
        doc.save(output_pdf_path, garbage=4, deflate=True)
        doc.close()

        return {
            "success": True,
            "applied_count": applied_count,
            "total_pages": len(page_annots)
        }
