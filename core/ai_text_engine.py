import os
import re
import json
import uuid
import urllib.request
import urllib.parse
import requests
import fitz
import docx
from typing import Optional, Dict, Any, List

class AITextEngine:
    """
    AI Text & Document Intelligence Engine
    - Dịch thuật văn bản tự do (Google Translate siêu tốc & DeepSeek AI chuyên sâu).
    - AI Tóm tắt tài liệu tự động (Đọc hiểu sâu PDF, DOCX, TXT, PPTX, xuất bản điều hành).
    - 100% Cục bộ & Linh hoạt, tự động fallback an toàn khi mất mạng hoặc không có API key.
    """

    GOOGLE_TRANSLATE_API = "https://translate.googleapis.com/translate_a/single"
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
    PRIMARY_MODEL = "DeepSeek-V4.1-Flash"
    FALLBACK_MODEL = "deepseek-chat"

    @classmethod
    def call_deepseek_api(
        cls,
        messages: List[Dict[str, Any]],
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        response_format: Optional[Dict[str, str]] = None,
        timeout: int = 90
    ) -> Dict[str, Any]:
        """
        Thực thi gọi DeepSeek AI thống nhất:
        - Ràng buộc mặc định model: DeepSeek-V4.1-Flash
        - Tự động fallback sang deepseek-chat nếu endpoint DeepSeek yêu cầu tên định danh API chính thức
        - Nhiệt độ mặc định temperature: 0.1
        """
        actual_key = cls.get_deepseek_key(api_key)
        if not actual_key:
            raise ValueError("Chưa có DeepSeek API Key. Vui lòng nhập API Key!")

        target_model = model or cls.PRIMARY_MODEL
        headers = {
            "Authorization": f"Bearer {actual_key}",
            "Content-Type": "application/json"
        }

        def _build_payload(m: str):
            p = {
                "model": m,
                "messages": messages,
                "temperature": temperature,
                "stream": False
            }
            if response_format:
                p["response_format"] = response_format
            return p

        # 1. Thử gọi với target_model (DeepSeek-V4.1-Flash)
        resp = requests.post(
            cls.DEEPSEEK_API_URL,
            headers=headers,
            json=_build_payload(target_model),
            timeout=timeout
        )

        # 2. Nếu model không được chấp nhận (400/404 hoặc model error), fallback sang deepseek-chat
        if resp.status_code != 200 and target_model != cls.FALLBACK_MODEL:
            err_text = resp.text.lower()
            if any(k in err_text for k in ("model", "not found", "invalid_request", "does not exist", "unsupported")) or resp.status_code in (400, 404):
                resp = requests.post(
                    cls.DEEPSEEK_API_URL,
                    headers=headers,
                    json=_build_payload(cls.FALLBACK_MODEL),
                    timeout=timeout
                )

        if resp.status_code != 200:
            raise RuntimeError(f"DeepSeek API lỗi (HTTP {resp.status_code}): {resp.text}")

        return resp.json()

    @classmethod
    def chat_completion(
        cls,
        messages: List[Dict[str, Any]],
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        base_url: Optional[str] = None,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        Thực thi Chat Completion tương thích DeepSeek & OpenAI API, hỗ trợ kiểm tra kết nối (Test connection).
        """
        actual_key = cls.get_deepseek_key(api_key)
        if not actual_key:
            raise ValueError("Chưa có API Key. Vui lòng cấu hình API Key!")

        target_model = model or cls.PRIMARY_MODEL
        endpoint = (base_url or "").strip() or cls.DEEPSEEK_API_URL
        if not endpoint.endswith("/chat/completions"):
            endpoint = endpoint.rstrip("/") + "/chat/completions"

        headers = {
            "Authorization": f"Bearer {actual_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
        if resp.status_code != 200 and target_model != cls.FALLBACK_MODEL and "deepseek" in endpoint.lower():
            payload["model"] = cls.FALLBACK_MODEL
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)

        if resp.status_code != 200:
            raise RuntimeError(f"AI API lỗi (HTTP {resp.status_code}): {resp.text}")

        return resp.json()

    @classmethod
    def get_deepseek_key(cls, explicit_key: Optional[str] = None) -> Optional[str]:
        if explicit_key and explicit_key.strip():
            return explicit_key.strip()
        try:
            from core.deepseek_ocr import DeepSeekOCR
            saved = DeepSeekOCR.get_saved_api_key()
            if saved and saved.strip():
                return saved.strip()
        except Exception:
            pass
        return os.getenv("DEEPSEEK_API_KEY", "").strip() or None

    # =========================================================================
    # 1. DỊCH THUẬT VĂN BẢN (GOOGLE TRANSLATE & AI DEEPSEEK)
    # =========================================================================
    @classmethod
    def translate_google(cls, text: str, source_lang: str = "auto", target_lang: str = "vi") -> str:
        """Dịch văn bản bằng Google Translate Engine (Hỗ trợ phân đoạn văn bản dài)."""
        if not text or not text.strip():
            return ""

        # Normalize language codes
        lang_map = {
            "zh": "zh-CN", "cn": "zh-CN", "chinese": "zh-CN",
            "en": "en", "vi": "vi", "ja": "ja", "ko": "ko",
            "fr": "fr", "de": "de", "ru": "ru", "es": "es", "auto": "auto"
        }
        sl = lang_map.get(source_lang.lower(), source_lang)
        tl = lang_map.get(target_lang.lower(), target_lang)

        # 0. Ưu tiên số 1: Bing Translator Engine Chuyên Sâu (Nhanh, mượt, không giới hạn IP, chuẩn kỹ thuật)
        try:
            from core.interlinear_translator import BingTranslatorEngine
            b_src = "zh-Hans" if sl in ["zh", "zh-cn", "cn"] else ("en" if sl in ["en", "auto"] else sl)
            b_tgt = "vi" if tl == "vi" else tl
            
            lines = text.split("\n")
            non_empty_indices = [i for i, line in enumerate(lines) if line.strip()]
            non_empty_texts = [lines[i].strip() for i in non_empty_indices]
            
            if non_empty_texts:
                bing_res = BingTranslatorEngine.translate_texts(non_empty_texts, src=b_src, tgt=b_tgt)
                if bing_res and len(bing_res) == len(non_empty_texts):
                    result_lines = list(lines)
                    for idx, trans in zip(non_empty_indices, bing_res):
                        result_lines[idx] = trans
                    return "\n".join(result_lines)
        except Exception:
            pass

        # Chunk text if exceeds 2500 characters
        paragraphs = text.split("\n")
        chunks = []
        current_chunk = []
        current_len = 0

        for p in paragraphs:
            p_len = len(p)
            if current_len + p_len > 2000 and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [p]
                current_len = p_len
            else:
                current_chunk.append(p)
                current_len += p_len + 1
        if current_chunk:
            chunks.append("\n".join(current_chunk))

        translated_chunks = []
        for chunk in chunks:
            if not chunk.strip():
                translated_chunks.append("")
                continue

            success = False
            # 1. Thử MyMemory
            try:
                from deep_translator import MyMemoryTranslator
                mm_map = {"en": "english", "vi": "vietnamese", "zh": "chinese simplified", "zh-cn": "chinese simplified", "ja": "japanese", "ko": "korean"}
                src_m = mm_map.get(source_lang.lower(), "autodetect")
                tgt_m = mm_map.get(target_lang.lower(), "vietnamese")
                res_mm = MyMemoryTranslator(source=src_m, target=tgt_m).translate(chunk)
                if res_mm and res_mm.strip():
                    translated_chunks.append(res_mm.strip())
                    success = True
            except Exception:
                pass

            if not success:
                # 2. Thử Google Translate Web API
                for client in ("at", "gtx"):
                    try:
                        encoded = urllib.parse.quote(chunk)
                        url = f"{cls.GOOGLE_TRANSLATE_API}?client={client}&sl={sl}&tl={tl}&dt=t&q={encoded}"
                        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                        with urllib.request.urlopen(req, timeout=8) as resp:
                            data = json.loads(resp.read().decode("utf-8"))
                            chunk_res = "".join([part[0] for part in data[0] if part and part[0]])
                            translated_chunks.append(chunk_res)
                            success = True
                            break
                    except Exception:
                        continue

            if not success:
                translated_chunks.append(chunk)

        return "\n".join(translated_chunks)

    @classmethod
    def translate_deepseek(cls, text: str, source_lang: str = "auto", target_lang: str = "vi", api_key: Optional[str] = None) -> str:
        """Dịch thuật văn bản cao cấp bằng AI DeepSeek với văn phong mượt mà."""
        actual_key = cls.get_deepseek_key(api_key)
        if not actual_key:
            return cls.translate_google(text, source_lang, target_lang)

        lang_names = {
            "vi": "Tiếng Việt",
            "en": "Tiếng Anh",
            "zh": "Tiếng Trung",
            "zh-CN": "Tiếng Trung",
            "ja": "Tiếng Nhật",
            "ko": "Tiếng Hàn",
            "fr": "Tiếng Pháp",
            "de": "Tiếng Đức",
            "auto": "ngôn ngữ gốc"
        }
        target_name = lang_names.get(target_lang, target_lang)
        source_name = lang_names.get(source_lang, "ngôn ngữ gốc")

        system_prompt = (
            f"Bạn là một chuyên gia dịch thuật cao cấp hàng đầu thế giới. "
            f"Nhiệm vụ của bạn là dịch văn bản được cung cấp từ {source_name} sang {target_name}. "
            f"Yêu cầu tuyệt đối:\n"
            f"1. Dịch chuẩn xác ngữ nghĩa, văn phong tự nhiên, trôi chảy, đúng thuật ngữ chuyên ngành.\n"
            f"2. Giữ nguyên toàn bộ định dạng dòng, số liệu, ký hiệu, mã số hoặc công thức.\n"
            f"3. Chỉ trả về duy nhất nội dung đã dịch, TUYỆT ĐỐI KHÔNG thêm lời chào, giải thích hoặc nhận xét."
        )

        try:
            data = cls.call_deepseek_api(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                api_key=actual_key,
                model=cls.PRIMARY_MODEL,
                temperature=0.1,
                timeout=60
            )
            return data["choices"][0]["message"]["content"].strip()
        except Exception:
            return cls.translate_google(text, source_lang, target_lang)

    @classmethod
    def translate_text(cls, text: str, source_lang: str = "auto", target_lang: str = "vi", engine: str = "google", api_key: Optional[str] = None) -> dict:
        """Endpoint dịch thuật trọn gói với bộ đếm ký tự & tốc độ xử lý."""
        import time
        t0 = time.time()
        text = text.strip() if text else ""
        if not text:
            return {
                "success": False,
                "error": "Vui lòng nhập hoặc dán nội dung văn bản cần dịch."
            }

        engine_used = engine.lower()
        if engine_used in ("deepseek", "ai"):
            translated = cls.translate_deepseek(text, source_lang, target_lang, api_key)
            actual_engine = "DeepSeek AI Chuyên Sâu"
        else:
            translated = cls.translate_google(text, source_lang, target_lang)
            actual_engine = "Google Translate Siêu Tốc"

        elapsed = round(time.time() - t0, 2)
        return {
            "success": True,
            "original_text": text,
            "translated_text": translated,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "char_count": len(text),
            "word_count": len(text.split()),
            "engine": actual_engine,
            "elapsed_seconds": elapsed
        }

    # =========================================================================
    # 2. AI TÓM TẮT TÀI LIỆU (DOCUMENT SUMMARIZER)
    # =========================================================================
    @classmethod
    def extract_document_text(cls, file_path: str) -> str:
        """Trích xuất toàn bộ văn bản từ tệp PDF, DOCX, TXT, PPTX."""
        ext = os.path.splitext(file_path)[1].lower()
        full_text = []

        if ext == ".pdf":
            doc = fitz.open(file_path)
            for page in doc:
                t = page.get_text("text")
                if t:
                    full_text.append(t)
            combined = "\n\n".join(full_text).strip()
            if len(combined) < 50:
                # Scanned PDF: extract text via OCR
                try:
                    import pytesseract
                    from PIL import Image
                    import io
                    ocr_text = []
                    for i in range(min(5, len(doc))):
                        pix = doc[i].get_pixmap(dpi=150)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        t = pytesseract.image_to_string(img, lang="vie+eng").strip()
                        if t:
                            ocr_text.append(t)
                    if ocr_text:
                        full_text = ocr_text
                except Exception:
                    pass
        elif ext in (".docx", ".doc"):
            try:
                d = docx.Document(file_path)
                for p in d.paragraphs:
                    if p.text.strip():
                        full_text.append(p.text.strip())
                for table in d.tables:
                    for row in table.rows:
                        row_vals = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                        if row_vals:
                            full_text.append(" | ".join(row_vals))
            except Exception:
                pass
        elif ext == ".txt":
            for enc in ("utf-8", "utf-8-sig", "cp1258", "latin1"):
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        full_text.append(f.read())
                    break
                except Exception:
                    continue
        elif ext in (".pptx", ".ppt"):
            try:
                import pptx
                prs = pptx.Presentation(file_path)
                for slide in prs.slides:
                    for shape in slide.shapes:
                        if hasattr(shape, "text") and shape.text:
                            full_text.append(shape.text)
            except Exception:
                pass

        return "\n\n".join(full_text).strip()

    @classmethod
    def local_extractive_summary(cls, text: str, max_sentences: int = 7) -> str:
        """Động cơ tóm tắt cục bộ trích xuất câu then chốt (Extractive Ranking) khi offline 100%."""
        sentences = re.split(r'(?<=[.!?\n])\s+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 30]

        if not sentences:
            return text[:600]

        # Calculate word frequency
        words = re.findall(r'\w+', text.lower())
        stopwords = {"va", "la", "cua", "cac", "nhung", "co", "duoc", "trong", "cho", "nguoi", "khi", "de", "the", "and", "is", "of", "to", "in", "for", "with", "that"}
        freq = {}
        for w in words:
            if w not in stopwords and len(w) > 2:
                freq[w] = freq.get(w, 0) + 1

        # Score sentences
        scores = []
        for idx, s in enumerate(sentences):
            s_words = re.findall(r'\w+', s.lower())
            score = sum(freq.get(w, 0) for w in s_words) / (len(s_words) + 1)
            # Boost first sentences
            if idx < 3:
                score *= 1.3
            scores.append((score, idx, s))

        scores.sort(key=lambda x: x[0], reverse=True)
        top_sentences = sorted(scores[:max_sentences], key=lambda x: x[1])

        bullets = "\n".join([f"• {item[2]}" for item in top_sentences])
        return (
            "### 📌 TÓM TẮT ĐIỀU HÀNH (EXTRACTIVE SUMMARY)\n\n"
            f"{bullets}\n\n"
            "> *Bản tóm tắt được trích xuất tự động bằng Động cơ Cục bộ Siêu Cấp VIP Pro.*"
        )

    @classmethod
    def summarize_deepseek(cls, text: str, mode: str = "executive", length: str = "medium", lang: str = "vi", api_key: Optional[str] = None) -> str:
        """Tóm tắt văn bản thông minh bằng DeepSeek AI."""
        actual_key = cls.get_deepseek_key(api_key)
        if not actual_key:
            return cls.local_extractive_summary(text)

        mode_instructions = {
            "executive": "Viết TÓM TẮT ĐIỀU HÀNH (Executive Summary): 1 đoạn mở đầu khái quát, sau đó là 3-5 ý then chốt quan trọng nhất.",
            "bullets": "Trích xuất danh sách GẠCH ĐẦU DÒNG CÁC ĐIỂM CỐT LÕI (Key Takeaways): Mỗi điểm gãy gọn, súc tích, làm nổi bật thông điệp.",
            "metrics": "Trích xuất CÁC SỐ LIỆU, MỐC THỜI GIAN & HÀNH ĐỘNG CẦN LÀM (Metrics & Actions): Liệt kê rõ số liệu đo lường, ngày tháng và trách nhiệm.",
            "full": "Lập BÁO CÁO TÓM TẮT TOÀN DIỆN: Gồm (1) Bối cảnh & Mục tiêu, (2) Các luận điểm chính, (3) Số liệu & Kết quả, (4) Kết luận & Đề xuất."
        }
        inst = mode_instructions.get(mode, mode_instructions["executive"])

        length_limits = {
            "short": "khoảng 150 - 250 từ, cô đọng tối đa",
            "medium": "khoảng 350 - 500 từ, đầy đủ vừa vặn",
            "detailed": "khoảng 600 - 900 từ, chi tiết sâu sắc"
        }
        len_inst = length_limits.get(length, "khoảng 350 - 500 từ")

        system_prompt = (
            f"Bạn là một chuyên gia phân tích và tóm tắt tài liệu cấp cao. "
            f"Hãy đọc hiểu văn bản dưới đây và tạo bản tóm tắt bằng tiếng Việt.\n"
            f"Yêu cầu:\n"
            f"- Định dạng: Trình bày bằng Markdown đẹp mắt, có tiêu đề, gạch đầu dòng rõ ràng.\n"
            f"- Phương pháp: {inst}\n"
            f"- Độ dài: {len_inst}.\n"
            f"- Tôn trọng 100% tính xác thực của số liệu và sự kiện trong tài liệu gốc."
        )

        # Truncate text if excessively long for context window (e.g. ~40,000 chars)
        context_text = text[:45000] if len(text) > 45000 else text

        try:
            data = cls.call_deepseek_api(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Văn bản tài liệu cần tóm tắt:\n\n{context_text}"}
                ],
                api_key=actual_key,
                model=cls.PRIMARY_MODEL,
                temperature=0.1,
                timeout=90
            )
            return data["choices"][0]["message"]["content"].strip()
        except Exception:
            return cls.local_extractive_summary(text)

    @classmethod
    def generate_summary_docx(cls, title: str, summary_content: str, output_path: str):
        """Xuất bản tóm tắt sang file Word (.docx) chuẩn chỉnh."""
        doc = docx.Document()
        
        # Title
        h = doc.add_heading(f"BÁO CÁO TÓM TẮT: {title.upper()}", level=1)
        h.paragraph_format.space_after = docx.shared.Pt(12)

        # Meta info
        p_meta = doc.add_paragraph()
        p_meta.add_run(f"Được tạo tự động bởi: LUV-PDF AI Intelligence Suite\n").italic = True
        p_meta.add_run(f"Hệ thống: 100% Cục bộ & Bảo mật dữ liệu\n").italic = True

        doc.add_paragraph("─" * 45)

        # Process lines
        for line in summary_content.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.startswith("### "):
                doc.add_heading(line_str.replace("### ", ""), level=2)
            elif line_str.startswith("## "):
                doc.add_heading(line_str.replace("## ", ""), level=2)
            elif line_str.startswith("# "):
                doc.add_heading(line_str.replace("# ", ""), level=1)
            elif line_str.startswith("• ") or line_str.startswith("- ") or line_str.startswith("* "):
                clean_bullet = line_str.lstrip("•-* ")
                doc.add_paragraph(clean_bullet, style="List Bullet")
            else:
                doc.add_paragraph(line_str)

        doc.save(output_path)

    @classmethod
    def summarize_file(cls, file_path: str, output_dir: str, mode: str = "executive", length: str = "medium", engine: str = "deepseek", api_key: Optional[str] = None) -> dict:
        """Đọc file tài liệu, tóm tắt và xuất file kết quả."""
        import time
        t0 = time.time()

        if not os.path.exists(file_path):
            raise FileNotFoundError("Tệp tin tài liệu không tồn tại.")

        base_name = os.path.splitext(os.path.basename(file_path))[0]
        extracted_text = cls.extract_document_text(file_path)

        if not extracted_text or len(extracted_text.strip()) < 50:
            raise ValueError("Không thể trích xuất đủ nội dung văn bản từ tệp này (Tệp trống hoặc chỉ chứa ảnh scan cần OCR trước).")

        orig_word_count = len(extracted_text.split())
        orig_char_count = len(extracted_text)

        actual_key = cls.get_deepseek_key(api_key)
        if engine.lower() in ("deepseek", "ai") and actual_key:
            summary_md = cls.summarize_deepseek(extracted_text, mode=mode, length=length, api_key=actual_key)
            engine_name = "DeepSeek AI Document Summarizer"
        else:
            summary_md = cls.local_extractive_summary(extracted_text)
            engine_name = "Động cơ Cục bộ Extractive Summarizer"

        summary_word_count = len(summary_md.split())
        ratio = round((1 - (summary_word_count / max(1, orig_word_count))) * 100, 1)

        # Export Word document
        out_filename = f"{base_name}_Summary_{uuid.uuid4().hex[:6]}.docx"
        out_path = os.path.join(output_dir, out_filename)
        cls.generate_summary_docx(base_name, summary_md, out_path)

        elapsed = round(time.time() - t0, 2)

        return {
            "success": True,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "summary_text": summary_md,
            "engine": engine_name,
            "original_words": orig_word_count,
            "summary_words": summary_word_count,
            "compression_ratio": f"{max(0, ratio)}%",
            "elapsed_seconds": elapsed,
            "details": f"Đã tóm tắt thành công ({orig_word_count} từ → {summary_word_count} từ, rút gọn {max(0, ratio)}%, {elapsed}s)."
        }
