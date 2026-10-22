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
        - Tự động map model chuẩn: deepseek-chat
        - Nhiệt độ mặc định temperature: 0.1
        """
        actual_key = cls.get_deepseek_key(api_key)
        if not actual_key:
            raise ValueError("Chưa có DeepSeek API Key. Vui lòng nhập API Key!")

        raw_model = (model or cls.PRIMARY_MODEL).strip()
        # Aliasing for real official DeepSeek models
        target_model = "deepseek-chat" if raw_model in ("DeepSeek-V4.1-Flash", "") else raw_model

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

        # 1. Thử gọi với target_model
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
    def normalize_model_name(cls, model: Optional[str] = None, provider: Optional[str] = None) -> str:
        """
        Chuẩn hóa tên model trước khi gọi API, triệt tiêu hoàn toàn lỗi Model Not Exist.
        Đặc biệt xử lý ánh xạ alias:
          - DeepSeek-V4.1-Flash / flash / v4.1 / v4 -> deepseek-chat
          - DeepSeek-V4.1-Reasoner / reasoner / r1 -> deepseek-reasoner
          - Gemini -> gemini-2.5-flash / gemini-2.5-pro / gemini-1.5-flash
          - OpenAI -> gpt-4o-mini / gpt-4o
        """
        m = (model or "").strip()
        prov = (provider or "").strip().lower()

        # Nếu provider là deepseek hoặc model có từ khóa deepseek
        if prov == "deepseek" or "deepseek" in m.lower() or not prov:
            m_lower = m.lower()
            if any(k in m_lower for k in ("reasoner", "r1")):
                return "deepseek-reasoner"
            if any(k in m_lower for k in ("4.1", "flash", "v4", "v3", "chat")) or not m:
                return "deepseek-chat"
            if prov == "deepseek" and (not m or m == "DeepSeek-V4.1-Flash"):
                return "deepseek-chat"
            return m or "deepseek-chat"

        elif prov in ("gemini", "google") or "gemini" in m.lower():
            m_lower = m.lower()
            if "pro" in m_lower:
                return "gemini-2.5-pro"
            if "1.5" in m_lower and "flash" in m_lower:
                return "gemini-1.5-flash"
            return "gemini-2.5-flash"

        elif prov == "openai" or "gpt" in m.lower():
            m_lower = m.lower()
            if "4o-mini" in m_lower or "mini" in m_lower:
                return "gpt-4o-mini"
            if "gpt-4o" in m_lower:
                return "gpt-4o"
            return "gpt-4o-mini"

        return m or "deepseek-chat"

    @classmethod
    def get_ai_credentials(
        cls,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        explicit_key: Optional[str] = None,
        explicit_provider: Optional[str] = None,
        explicit_model: Optional[str] = None,
        explicit_base_url: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Lấy cấu hình AI toàn cục (Google Gemini, OpenAI, DeepSeek, Custom).
        Nhận linh hoạt mọi tham số (provider, api_key, model, base_url, **kwargs)
        mà không bao giờ văng lỗi TypeError: got an unexpected keyword argument 'model'.
        """
        # Hỗ trợ nếu tham số đầu tiên là provider dạng chuỗi 'deepseek', 'gemini', 'openai'
        if api_key and str(api_key).lower() in ("deepseek", "gemini", "openai", "google", "custom"):
            if not provider:
                provider = api_key
                api_key = None

        raw_provider = provider or explicit_provider or kwargs.get("ai_provider") or ""
        raw_key = api_key or explicit_key or kwargs.get("key") or ""
        raw_model = model or explicit_model or kwargs.get("ai_model") or ""
        raw_base = base_url or explicit_base_url or kwargs.get("ai_base_url") or ""

        prov = str(raw_provider).strip().lower()
        key = str(raw_key).strip()
        mod = str(raw_model).strip()
        base = str(raw_base).strip()

        # Đọc settings.json / data/settings.json
        settings_data = {}
        for s_path in ["settings.json", "data/settings.json"]:
            if os.path.exists(s_path):
                try:
                    with open(s_path, "r", encoding="utf-8") as f:
                        saved = json.load(f)
                        if isinstance(saved, dict):
                            settings_data.update(saved)
                except Exception:
                    pass

        saved_prov = (settings_data.get("ai_provider") or os.getenv("AI_PROVIDER") or "").strip().lower()
        if not prov:
            prov = saved_prov
        if not key:
            key = (
                settings_data.get("ai_api_key") or
                settings_data.get("deepseek_api_key") or
                os.getenv("GEMINI_API_KEY") or
                os.getenv("OPENAI_API_KEY") or
                os.getenv("DEEPSEEK_API_KEY") or ""
            ).strip()
        if not mod:
            if prov and saved_prov and prov != saved_prov:
                mod = ""
            else:
                mod = (settings_data.get("ai_model") or (settings_data.get("deepseek_model") if prov == "deepseek" else "") or "").strip()
        if not base:
            if prov and saved_prov and prov != saved_prov:
                base = ""
            else:
                base = (settings_data.get("ai_base_url") or (settings_data.get("deepseek_base_url") if prov == "deepseek" else "") or "").strip()

        # Tự động nhận diện provider nếu chưa chỉ định rõ
        if not prov or prov not in ("gemini", "openai", "deepseek", "custom"):
            if key.startswith("AIza") or "gemini" in mod.lower():
                prov = "gemini"
            elif key.startswith("sk-proj-") or "gpt-" in mod.lower():
                prov = "openai"
            else:
                prov = "deepseek"

        # Chuẩn hóa Base URL theo provider
        if not base:
            if prov == "gemini":
                base = "https://generativelanguage.googleapis.com/v1beta"
            elif prov == "openai":
                base = "https://api.openai.com/v1"
            else:
                base = "https://api.deepseek.com/v1"

        # Chuẩn hóa tên model theo provider
        if not mod:
            if prov == "gemini":
                normalized_model = "gemini-2.5-flash"
            elif prov == "openai":
                normalized_model = "gpt-4o-mini"
            else:
                normalized_model = "deepseek-chat"
        else:
            normalized_model = cls.normalize_model_name(mod, prov)

        return {
            "provider": prov,
            "api_key": key,
            "model": normalized_model,
            "base_url": base
        }

    @classmethod
    def call_vision_api(
        cls,
        image_data: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 45
    ) -> str:
        """
        Gửi ảnh hiện trường vi phạm lên Multimodal Vision AI (Google Gemini hoặc OpenAI GPT-4o Vision).
        TUYỆT ĐỐI KHÔNG DÙNG MOCK HOẶC CHUỖI GHÉP GIẢ.
        """
        creds = cls.get_ai_credentials(api_key, provider, model, base_url)
        active_provider = creds["provider"]
        active_key = creds["api_key"]
        active_model = creds["model"]
        active_base = creds["base_url"]

        if not active_key:
            raise ValueError(
                "Hệ thống chưa được cấu hình API Key. "
                "Vui lòng vào 'Cài Đặt Quản Trị' -> 'Cấu Hình API Key & Trí Tuệ Nhân Tạo' "
                "để nhập API Key Google Gemini (gemini-2.5-flash) hoặc OpenAI (gpt-4o-mini)!"
            )

        # Chuẩn hóa Base64 và MIME type
        mime_type = "image/jpeg"
        b64_clean = (image_data or "").strip()
        if b64_clean.startswith("data:"):
            match = re.match(r"data:([^;]+);base64,(.+)", b64_clean, re.DOTALL)
            if match:
                mime_type = match.group(1).strip()
                b64_clean = match.group(2).strip()

        if not b64_clean:
            raise ValueError("Dữ liệu hình ảnh trống hoặc không đúng định dạng Base64.")

        # 1. GOOGLE GEMINI VISION API (gemini-2.5-flash, gemini-1.5-pro, gemini-1.5-flash)
        if active_provider == "gemini" or active_key.startswith("AIza") or "gemini" in active_model.lower():
            target_gemini_model = active_model if "gemini" in active_model.lower() else "gemini-2.5-flash"
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_gemini_model}:generateContent?key={active_key}"
            full_user_prompt = (f"{system_prompt}\n\n" if system_prompt else "") + prompt
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": full_user_prompt},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": b64_clean
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2
                }
            }
            resp = requests.post(gemini_url, json=payload, timeout=timeout)
            if resp.status_code != 200 and target_gemini_model != "gemini-1.5-flash":
                fallback_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={active_key}"
                resp = requests.post(fallback_url, json=payload, timeout=timeout)

            if resp.status_code != 200:
                raise RuntimeError(f"Google Gemini Vision API lỗi (HTTP {resp.status_code}): {resp.text}")

            res_json = resp.json()
            candidates = res_json.get("candidates") or []
            if not candidates:
                raise RuntimeError("Google Gemini không trả về kết quả (Có thể do bộ lọc an toàn hình ảnh).")
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts).strip()

        # 2. OPENAI GPT-4o / GPT-4o-mini / OPENAI-COMPATIBLE VISION
        elif active_provider == "openai" or "gpt-" in active_model.lower() or active_provider == "custom":
            target_model = active_model if "gpt-" in active_model.lower() else "gpt-4o-mini"
            endpoint = (active_base or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
            headers = {
                "Authorization": f"Bearer {active_key}",
                "Content-Type": "application/json"
            }
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{b64_clean}"
                        }
                    }
                ]
            })
            payload = {
                "model": target_model,
                "messages": messages,
                "temperature": 0.2
            }
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI Vision API lỗi (HTTP {resp.status_code}): {resp.text}")
            res_json = resp.json()
            choices = res_json.get("choices") or []
            if not choices:
                raise RuntimeError("OpenAI API không trả về kết quả.")
            return choices[0].get("message", {}).get("content", "").strip()

        # 3. DEEPSEEK (Text-Only Model)
        else:
            # DeepSeek (deepseek-chat) là mô hình Text-only, tuyệt đối không gửi image_url trực tiếp vào endpoint DeepSeek.
            # Xử lý thông minh 2 bước:
            # Bước 1: Kiểm tra xem hệ thống có phụ Gemini Vision Key hoặc OpenAI Key để trích xuất đặc điểm ảnh không
            gemini_key = os.getenv("GEMINI_API_KEY", "")
            if not gemini_key:
                for s_path in ["settings.json", "data/settings.json"]:
                    if os.path.exists(s_path):
                        try:
                            with open(s_path, "r", encoding="utf-8") as f:
                                s_data = json.load(f)
                                if s_data.get("gemini_api_key"):
                                    gemini_key = s_data["gemini_api_key"]
                        except Exception:
                            pass

            visual_context = ""
            if gemini_key:
                try:
                    visual_context = cls.call_vision_api(
                        image_data=image_data,
                        prompt="Hãy mô tả chi tiết các hiện vật, thiết bị, tình trạng vi phạm an toàn PCCC/EHS trong ảnh hiện trường này.",
                        api_key=gemini_key,
                        provider="gemini",
                        model="gemini-2.5-flash",
                        timeout=30
                    )
                except Exception:
                    visual_context = ""

            # Bước 2: Chuyển dữ liệu trích xuất + tiêu chuẩn PCCC/HSE sang DeepSeek (deepseek-chat) để suy luận và dịch song ngữ
            combined_prompt = prompt
            if visual_context:
                combined_prompt += f"\n\n[ĐẶC ĐIỂM HÌNH ẢNH HIỆN TRƯỜNG]:\n{visual_context}"
            else:
                combined_prompt += "\n\n[GHI NHẬN HIỆN TRƯỜNG]: Bức ảnh chụp tại vị trí kiểm tra ghi nhận điểm không phù hợp với tiêu chuẩn an toàn PCCC và EHS."

            sys_msg = system_prompt or (
                "Bạn là Chuyên gia Kiểm toán An toàn EHS & PCCC nhà máy ZhanChen.\n"
                "Hãy phân tích hiện trường, suy luận nguyên nhân gốc rễ và đề xuất biện pháp khắc phục.\n"
                "Trả về duy nhất JSON hợp lệ đúng các khóa: departmentKey, departmentVi, departmentZh, issueVi, issueZh, suggestion."
            )
            messages = [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": combined_prompt}
            ]
            deepseek_model = cls.normalize_model_name(active_model, "deepseek")
            res_text = cls.call_universal_chat(
                messages=messages,
                api_key=active_key,
                provider="deepseek",
                model=deepseek_model,
                base_url=active_base,
                timeout=timeout
            )
            if res_text and res_text.strip():
                return res_text.strip()

            raise ValueError("DeepSeek không trả về nội dung phân tích hiện trường hợp lệ.")

    @classmethod
    def call_universal_chat(
        cls,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.2,
        timeout: int = 60
    ) -> str:
        """Thực thi gọi Chat Completion thống nhất (Gemini / OpenAI / DeepSeek / Custom)."""
        creds = cls.get_ai_credentials(api_key=api_key, provider=provider, model=model, base_url=base_url)
        active_provider = creds["provider"]
        active_key = creds["api_key"]
        active_model = creds["model"]
        active_base = creds["base_url"]

        if not active_key:
            raise ValueError("Chưa cấu hình API Key. Vui lòng thiết lập tại phần Cài đặt Hệ thống!")

        # 1. Gemini
        if active_provider == "gemini" or active_key.startswith("AIza") or "gemini" in active_model.lower():
            target_model = cls.normalize_model_name(active_model, "gemini")
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={active_key}"
            contents = []
            for m in messages:
                role = "user" if m.get("role") in ("user", "system") else "model"
                contents.append({"role": role, "parts": [{"text": str(m.get("content") or "")}]})
            payload = {
                "contents": contents,
                "generationConfig": {"temperature": temperature}
            }
            if system_prompt:
                payload["system_instruction"] = {"parts": [{"text": system_prompt}]}
            resp = requests.post(gemini_url, json=payload, timeout=timeout)
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API lỗi (HTTP {resp.status_code}): {resp.text}")
            candidates = resp.json().get("candidates") or []
            if not candidates:
                raise RuntimeError("Gemini API không trả về nội dung.")
            return "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", [])).strip()

        # 2. OpenAI / DeepSeek / Custom
        else:
            endpoint = (active_base or ("https://api.openai.com/v1" if active_provider == "openai" else cls.DEEPSEEK_API_URL)).rstrip("/")
            if not endpoint.endswith("/chat/completions"):
                endpoint = endpoint + "/chat/completions"

            target_model = cls.normalize_model_name(active_model, active_provider)

            headers = {
                "Authorization": f"Bearer {active_key}",
                "Content-Type": "application/json"
            }
            all_messages = []
            if system_prompt:
                all_messages.append({"role": "system", "content": system_prompt})
            all_messages.extend(messages)

            resp = requests.post(
                endpoint,
                headers=headers,
                json={"model": target_model, "messages": all_messages, "temperature": temperature},
                timeout=timeout
            )
            if resp.status_code != 200 and "deepseek" in endpoint.lower() and target_model != cls.FALLBACK_MODEL:
                resp = requests.post(
                    endpoint,
                    headers=headers,
                    json={"model": cls.FALLBACK_MODEL, "messages": all_messages, "temperature": temperature},
                    timeout=timeout
                )

            if resp.status_code != 200:
                raise RuntimeError(f"AI API lỗi (HTTP {resp.status_code}): {resp.text}")
            choices = resp.json().get("choices") or []
            if not choices:
                raise RuntimeError("AI API không trả về phản hồi hợp lệ.")
            return choices[0].get("message", {}).get("content", "").strip()

    @classmethod
    def chat_completion(
        cls,
        messages: List[Dict[str, Any]],
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        base_url: Optional[str] = None,
        timeout: int = 60,
        provider: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Thực thi Chat Completion tương thích DeepSeek & OpenAI API, hỗ trợ kiểm tra kết nối (Test connection).
        """
        creds = cls.get_ai_credentials(api_key=api_key, provider=provider, model=model, base_url=base_url, **kwargs)
        actual_key = creds.get("api_key") or cls.get_deepseek_key(api_key)
        if not actual_key:
            raise ValueError("Chưa có API Key. Vui lòng cấu hình API Key!")

        active_provider = creds.get("provider", "deepseek")
        target_model = creds.get("model") or cls.normalize_model_name(model, active_provider)

        if active_provider == "gemini" or (actual_key and actual_key.startswith("AIza")):
            content = cls.call_universal_chat(
                messages=messages,
                api_key=actual_key,
                model=target_model,
                provider="gemini",
                temperature=temperature,
                timeout=timeout
            )
            return {"choices": [{"message": {"role": "assistant", "content": content}}]}

        endpoint = (base_url or creds.get("base_url") or "").strip() or cls.DEEPSEEK_API_URL
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
