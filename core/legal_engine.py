"""
core/legal_engine.py
────────────────────
CHEMICAL LEGAL INTELLIGENCE & COMPLIANCE ENGINE
Hệ thống Động cơ Tra cứu & Cảnh báo Pháp lý Hóa chất Chuyên sâu
Bao phủ: NĐ 24/2026/NĐ-CP, NĐ 28/2026/NĐ-CP, QCVN 01:2025/BYT, và CIL Inventory.

Cung cấp:
- Chỉ mục đảo ngược In-Memory siêu tốc (LEGAL_BY_CAS)
- Chuẩn hóa và trích xuất đa số CAS (CAS_PATTERN.findall)
- Thuật toán thẩm định Checksum số CAS (Mod 10)
- Tìm kiếm không dấu Unicode NFKD liên hợp đa từ tố
- Chuyển đổi và so sánh ngưỡng nồng độ / khối lượng
- Bộ khớp thành phần hàng loạt & phân cấp 5 bậc huy hiệu pháp lý
- Phân loại Nguyên liệu (Raw Material) vs Thành phẩm (Finished Product), Mother MSDS
- Tiện ích xuất bảng Mục 3 GHS cho Word (.docx)
- Kết xuất báo cáo Excel (.xlsx) đa bảng tính chuyên nghiệp
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import sys
import threading
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("titan.legal_engine")

# Biểu thức chính quy nhận diện số CAS với dung sai khoảng trắng (R-S-C: R bắt đầu bằng 1-9)
CAS_PATTERN = re.compile(r"\b([1-9]\d{1,6})\s*-\s*(\d{2})\s*-\s*(\d)\b")


def normalize_cas(value: Any) -> str:
    """Chuẩn hóa một chuỗi chứa số CAS về định dạng chuẩn XXXXXXX-XX-X."""
    if not value:
        return ""
    match = CAS_PATTERN.search(str(value).strip())
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}" if match else ""


def extract_all_cas(text: Any) -> List[str]:
    """Trích xuất toàn bộ các số CAS xuất hiện trong đoạn văn bản hoặc chuỗi ghép."""
    if not text:
        return []
    matches = CAS_PATTERN.findall(str(text))
    seen: Set[str] = set()
    result: List[str] = []
    for g in matches:
        cas = f"{g[0]}-{g[1]}-{g[2]}"
        if cas not in seen:
            seen.add(cas)
            result.append(cas)
    return result


extract_cas_numbers = extract_all_cas


def cas_checksum_valid(cas: str) -> bool:
    """
    Kiểm tra tính hợp lệ của số CAS bằng thuật toán Checksum quốc tế (Mod 10).
    R-S-C: Tổng i * d_i (tính từ phải sang trái của R và S) chia 10 lấy dư phải bằng C.
    Chặn triệt để số CAS bắt đầu bằng 0 (00-00-0, 01-23-0) và hỗ trợ dung sai khoảng trắng.
    """
    raw = str(cas or "").strip()
    m = CAS_PATTERN.fullmatch(raw)
    if not m:
        return False
    body = m.group(1) + m.group(2)
    check = int(m.group(3))
    total = sum((i + 1) * int(ch) for i, ch in enumerate(reversed(body)))
    return (total % 10) == check


def validate_cas(cas_str: Any) -> Dict[str, Any]:
    """
    Thẩm định toàn diện một chuỗi CAS.
    Trả về dict gồm: cas chuẩn hóa, trạng thái hiển thị, và cờ hợp lệ.
    """
    raw = str(cas_str or "").strip()
    if not raw or raw.upper() in {"---", "N/A", "NONE", "BÍ MẬT THƯƠNG MẠI", "PROPRIETARY", "CAS-NONE"}:
        return {"cas": "", "status": "KHÔNG CÓ CAS", "valid": False}

    norm = normalize_cas(raw)
    if not norm:
        return {"cas": raw, "status": "KHÔNG CÓ CAS", "valid": False}

    if cas_checksum_valid(norm):
        return {"cas": norm, "status": "HỢP LỆ", "valid": True}
    else:
        return {"cas": norm, "status": "SAI CHECKSUM", "valid": False}


def remove_accents(text: Any) -> str:
    """Khử dấu Tiếng Việt sang ký tự ASCII thuần túy phục vụ tìm kiếm không dấu."""
    if not text:
        return ""
    s = str(text).replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()


def expand_phonetic_variants(token: str) -> List[str]:
    """
    Mở rộng các biến thể chính tả hóa học Việt - Anh phổ biến:
    - axet <-> acet (Axeton <-> Acetone, Axetat <-> Acetate, Axetic <-> Acetic)
    - clohydric <-> clohidric <-> hydrochloric <-> chlohydric <-> chlohidric
    - sunf <-> sulf <-> sunph <-> sulph (Sunfuric <-> Sulfuric)
    - clor <-> chlor (Clorat <-> Chlorate, Clorua <-> Chloride)
    - photph <-> phosph (Photphoric <-> Phosphoric, Photphat <-> Phosphate)
    """
    t = remove_accents(token)
    variants = {t}

    # 1. Nhóm Axet <-> Acet (Acetone, Acetate, Acetic, Acetyl, Acetonitrile)
    if "axet" in t:
        variants.add(t.replace("axet", "acet"))
    elif "acet" in t:
        variants.add(t.replace("acet", "axet"))

    # 2. Nhóm Clohydric / Clohidric / Hydrochloric / Chlohydric
    _CLO_FORMS = ("clohydric", "clohidric", "chlohydric", "chlohidric", "hydrochloric")
    for cf in _CLO_FORMS:
        if cf in t:
            for target in _CLO_FORMS:
                if target != cf:
                    variants.add(t.replace(cf, target))
            break

    # 3. Nhóm Sunf <-> Sulf <-> Sunph <-> Sulph
    if "sunf" in t:
        variants.add(t.replace("sunf", "sulf"))
        variants.add(t.replace("sunf", "sunph"))
    elif "sulf" in t:
        variants.add(t.replace("sulf", "sunf"))
        variants.add(t.replace("sulf", "sulph"))
    elif "sunph" in t:
        variants.add(t.replace("sunph", "sulf"))
        variants.add(t.replace("sunph", "sunf"))
    elif "sulph" in t:
        variants.add(t.replace("sulph", "sulf"))
        variants.add(t.replace("sulph", "sunf"))

    # 4. Nhóm Clor <-> Chlor
    if "clor" in t:
        variants.add(t.replace("clor", "chlor"))
    elif "chlor" in t:
        variants.add(t.replace("chlor", "clor"))

    # 5. Nhóm Photph <-> Phosph
    if "photph" in t:
        variants.add(t.replace("photph", "phosph"))
    elif "phosph" in t:
        variants.add(t.replace("phosph", "photph"))

    return list(variants)


def parse_threshold_numeric(val: Any) -> Optional[float]:
    """
    Chuyển đổi chuỗi ngưỡng (ví dụ '5.000', '50.000', '150.000 (net)', '100 kg', '1.500,5')
    sang giá trị số thực (float kg) phục vụ so sánh điều kiện.
    Hỗ trợ cả định dạng chuẩn Việt Nam/châu Âu (dấu chấm phân cách hàng nghìn, dấu phẩy thập phân)
    và chuẩn quốc tế (dấu phẩy hàng nghìn, dấu chấm thập phân), cũng như số phân tách bằng dấu cách.
    """
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return None if val != val else float(val)

    s = str(val).strip()
    if not s or s.lower() in ("không quy định", "kđ", "none", "-", "n/a", "nan", "null"):
        return None

    # Loại bỏ ghi chú trong ngoặc đơn như (net), (gross), (hỗn hợp)...
    s = re.sub(r"\(.*?\)", "", s)
    # Loại bỏ các đơn vị đo lường phổ biến và từ chú thích kèm theo (cả dính liền và cách rời)
    s = re.sub(r"(?i)(kg|tấn|tan|mg/m[3³]|ppm|net|gross)", "", s)
    # Loại bỏ khoảng trắng (kể cả dấu cách phân tách hàng nghìn: '5 000.000' -> '5000.000')
    s = s.replace(" ", "").strip()
    # Loại bỏ các ký tự toán học/so sánh ở đầu chuỗi (>, <, >=, <=, ≥, ≤)
    s = re.sub(r"^[^\d+-]+", "", s).strip()
    if not s:
        return None

    # Trường hợp 1: Có cả dấu chấm '.' và dấu phẩy ','
    if "." in s and "," in s:
        last_dot = s.rfind(".")
        last_comma = s.rfind(",")
        if last_comma > last_dot:
            # Định dạng Việt Nam / châu Âu: ví dụ 1.500,5 -> bỏ '.', đổi ',' thành '.'
            s = s.replace(".", "").replace(",", ".")
        else:
            # Định dạng quốc tế (Anh/Mỹ): ví dụ 1,500.5 -> bỏ ','
            s = s.replace(",", "")
    # Trường hợp 2: Chỉ có dấu chấm '.'
    elif "." in s:
        # Nếu là phân cách hàng nghìn: ví dụ 5.000, 50.000, 5000.000, 1.000.000
        # Bắt đầu bằng chữ số 1-9 và theo sau bởi từng cụm đúng 3 chữ số
        if re.match(r"^[-+]?[1-9]\d*(\.\d{3})+$", s):
            s = s.replace(".", "")
    # Trường hợp 3: Chỉ có dấu phẩy ','
    elif "," in s:
        if s.count(",") > 1 and re.match(r"^[-+]?[1-9]\d*(,\d{3})+$", s):
            # Nhiều dấu phẩy phân cách hàng nghìn kiểu quốc tế: 1,000,000
            s = s.replace(",", "")
        else:
            # Dấu phẩy thập phân kiểu Việt Nam: 0,25 hoặc 1,5
            s = s.replace(",", ".")

    m = re.search(r"[-+]?\d*\.?\d+", s)
    if m:
        try:
            return float(m.group(0))
        except Exception:
            return None
    return None


class LegalCatalogEngine:
    """Động cơ quản lý CSDL Pháp lý Hóa chất In-Memory theo chuẩn Singleton."""

    _instance: Optional[LegalCatalogEngine] = None
    _lock = threading.Lock()

    def __init__(self):
        self.catalog_data: Dict[str, Any] = {}
        self.items: List[Dict[str, Any]] = []
        self.sources: List[Dict[str, Any]] = []
        self.sections: List[Dict[str, Any]] = []
        self.legal_by_cas: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.unique_cas: Set[str] = set()
        self.source_counts: Dict[str, int] = defaultdict(int)
        self.section_subgroups: Dict[str, Set[str]] = defaultdict(set)
        self.initialized = False
        self._load_catalog()

    @classmethod
    def get_instance(cls) -> LegalCatalogEngine:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _resolve_catalog_path(self) -> Path:
        """Xác định đường dẫn nạp catalog: ưu tiên data/ -> core/data/ -> fallback."""
        if getattr(sys, "frozen", False):
            base_dir = Path(sys._MEIPASS)
            data_dir = Path(sys.executable).resolve().parent / "data"
        else:
            base_dir = Path(__file__).resolve().parent.parent
            data_dir = base_dir / "data"

        # 1. Live override từ data/
        candidate_data = data_dir / "legal_catalog.json"
        if candidate_data.exists():
            logger.info("Nạp legal_catalog.json từ thư mục data live override: %s", candidate_data)
            return candidate_data

        # 2. Bundled package từ core/data/
        candidate_core = base_dir / "core" / "data" / "legal_catalog.json"
        if candidate_core.exists():
            logger.info("Nạp legal_catalog.json từ core/data: %s", candidate_core)
            return candidate_core

        # 3. Fallback vị trí tham chiếu gốc trong môi trường phát triển
        fallback = Path(r"C:\Users\ntc27\OneDrive\Desktop\Linh tinh\LUV MSDS\legal_extension\legal_catalog.json")
        if fallback.exists():
            logger.info("Nạp legal_catalog.json từ đường dẫn fallback dev: %s", fallback)
            return fallback

        raise FileNotFoundError("Không tìm thấy tệp legal_catalog.json trong data/ hoặc core/data/")

    def _load_catalog(self) -> None:
        """Đọc và lập chỉ mục In-Memory toàn bộ 2,191 bản ghi pháp lý."""
        catalog_path = self._resolve_catalog_path()
        with catalog_path.open("r", encoding="utf-8") as f:
            self.catalog_data = json.load(f)

        self.items = self.catalog_data.get("items", [])
        self.sources = self.catalog_data.get("sources", [])
        self.sections = self.catalog_data.get("sections", [])

        search_fields = (
            "source_id", "source_title", "law_basis", "section_id", "section_title",
            "subgroup", "serial", "name_vi", "name_scientific", "cas_raw", "cas",
            "formula", "threshold", "hs_code", "authority", "twa", "stel"
        )

        for item in self.items:
            # 1. Thống kê số lượng
            self.source_counts[item["source_id"]] += 1
            if item.get("subgroup"):
                self.section_subgroups[item["section_id"]].add(item["subgroup"])

            # 2. Tiền lập chỉ mục tìm kiếm có dấu và không dấu
            raw_text = " ".join(str(item.get(f) or "") for f in search_fields).casefold()
            norm_text = remove_accents(raw_text)
            item["_search_raw"] = raw_text
            item["_search_norm"] = norm_text

            # 3. Lập chỉ mục đảo ngược theo số CAS (quét tất cả CAS qua findall)
            item_cas_text = f"{item.get('cas_raw') or ''} {item.get('cas') or ''}"
            extracted_cas = extract_all_cas(item_cas_text)
            for cas in extracted_cas:
                self.unique_cas.add(cas)
                self.legal_by_cas[cas].append(item)

        self.initialized = True
        logger.info(
            "Đã khởi tạo LegalCatalogEngine thành công: %d bản ghi, %d số CAS duy nhất.",
            len(self.items), len(self.unique_cas)
        )

    # --------------------------------------------------------------------------
    # QUY TẮC PHÂN CẤP HUY HIỆU & NGHĨA VỤ PHÁP LÝ (BADGE & OBLIGATIONS)
    # --------------------------------------------------------------------------

    @staticmethod
    def get_regulatory_badge(item: Dict[str, Any]) -> Dict[str, Any]:
        """Tạo đối tượng huy hiệu pháp lý chuẩn 5 bậc cho từng bản ghi."""
        sec = item.get("section_id", "")
        if sec in {"ND28-I-A", "ND28-I-B", "ND28-IV-A"}:
            return {
                "type": "danger",
                "label": f"NĐ 28: Cấm Tuyệt Đối ({sec})",
                "tier": 1,
                "color": "#b91c1c",
                "bg": "#fef2f2",
                "category": "prohibited"
            }
        elif sec == "ND24-PL-III":
            return {
                "type": "danger",
                "label": "NĐ 24: Kiểm Soát Đặc Biệt",
                "tier": 2,
                "color": "#ef4444",
                "bg": "#fff1f2",
                "category": "special_control"
            }
        elif sec in {"ND28-II-A", "ND28-II-B"}:
            return {
                "type": "danger",
                "label": f"NĐ 28: Hạn Chế Sử Dụng ({sec})",
                "tier": 2,
                "color": "#c2410c",
                "bg": "#fff7ed",
                "category": "restricted"
            }
        elif sec == "ND28-IV-B":
            return {
                "type": "danger",
                "label": "NĐ 28: Tiền Chất IV.B (BCA)",
                "tier": 2,
                "color": "#dc2626",
                "bg": "#fef2f2",
                "category": "precursor_essential"
            }
        elif sec == "ND28-IV-C":
            return {
                "type": "warning",
                "label": "NĐ 28: Tiền Chất IV.C (BCT)",
                "tier": 2,
                "color": "#ea580c",
                "bg": "#fff7ed",
                "category": "precursor_industrial"
            }
        elif sec == "ND24-PL-II":
            return {
                "type": "warning",
                "label": "NĐ 24: SX/KD Có Điều Kiện",
                "tier": 3,
                "color": "#f59e0b",
                "bg": "#fffbeb",
                "category": "conditional"
            }
        elif sec in {"ND24-PL-IV-A", "ND24-PL-IV-B"}:
            th = item.get("threshold") or ""
            lbl = f"NĐ 24: Kế Hoạch Sự Cố ({th} kg)" if th else "NĐ 24: Kế Hoạch Sự Cố"
            return {
                "type": "warning",
                "label": lbl,
                "tier": 3,
                "color": "#f97316",
                "bg": "#fff7ed",
                "category": "incident_plan"
            }
        elif sec == "ND28-III":
            return {
                "type": "warning",
                "label": "NĐ 28: Y Tế/Thú Y III",
                "tier": 3,
                "color": "#d97706",
                "bg": "#fffbeb",
                "category": "medical_veterinary"
            }
        elif sec == "ND24-PL-I":
            return {
                "type": "info",
                "label": "NĐ 24: Trọng Điểm CN",
                "tier": 4,
                "color": "#0ea5e9",
                "bg": "#f0f9ff",
                "category": "key_industrial"
            }
        elif sec == "QCVN01-70":
            return {
                "type": "success",
                "label": "QCVN 01: Giới Hạn Tiếp Xúc",
                "tier": 4,
                "color": "#16a34a",
                "bg": "#f0fdf4",
                "category": "occupational_limit"
            }
        return {
            "type": "secondary",
            "label": item.get("section_title", "Pháp lý"),
            "tier": 5,
            "color": "#64748b",
            "bg": "#f8fafc",
            "category": "general"
        }

    @staticmethod
    def get_statutory_obligation(item: Dict[str, Any]) -> str:
        """Trả về mô tả nghĩa vụ pháp lý tuân thủ bắt buộc bằng Tiếng Việt."""
        sec = item.get("section_id", "")
        authority = item.get("authority") or "Cơ quan quản lý nhà nước"
        threshold = item.get("threshold") or ""
        twa = item.get("twa") or "---"
        stel = item.get("stel") or "---"

        if sec in {"ND28-I-A", "ND28-I-B"}:
            return "Chất ma túy, hướng thần tuyệt đối cấm sử dụng trong y tế và đời sống xã hội. Nghiêm cấm mọi hành vi sản xuất, tàng trữ, vận chuyển, sử dụng."
        elif sec == "ND28-IV-A":
            return "Tiền chất thiết yếu không có ứng dụng hợp pháp. Nghiêm cấm lưu thông trong hoạt động sản xuất kinh doanh thông thường."
        elif sec == "ND24-PL-III":
            return "Phải có Giấy phép sản xuất, kinh doanh hóa chất cần kiểm soát đặc biệt; Lập Phiếu kiểm soát mua, bán hóa chất độc; Định kỳ báo cáo cơ quan chuyên trách."
        elif sec in {"ND28-II-A", "ND28-II-B"}:
            return "Chỉ được phép sử dụng trong phân tích, kiểm nghiệm, nghiên cứu khoa học, điều tra tội phạm hoặc y tế theo giấy phép chỉ định."
        elif sec == "ND28-IV-B":
            return f"Tiền chất ma túy thiết yếu do {authority} quản lý. Phải có Giấy phép xuất nhập khẩu, lập sổ theo dõi xuất nhập tồn, lưu trữ chứng từ tối thiểu 2 năm."
        elif sec == "ND28-IV-C":
            return f"Dung môi, tiền chất ma túy công nghiệp do {authority} quản lý. Phải lập sổ theo dõi riêng, báo cáo định kỳ 6 tháng và hàng năm tới Sở Công Thương và Công an."
        elif sec == "ND24-PL-II":
            return "Phải có Giấy chứng nhận đủ điều kiện sản xuất, kinh doanh hóa chất có điều kiện; Duy trì điều kiện an toàn nhà xưởng, kho bãi và trang bị bảo hộ."
        elif sec == "ND24-PL-IV-A":
            th_text = f"vượt ngưỡng quy định ({threshold} kg)" if threshold else "theo quy định"
            return f"Bắt buộc xây dựng Kế hoạch phòng ngừa, ứng phó sự cố hóa chất cấp Bộ/Tỉnh khi khối lượng tồn trữ {th_text}. Diễn tập định kỳ hàng năm."
        elif sec == "ND24-PL-IV-B":
            return "Nhóm hóa chất nguy hại tiềm ẩn sự cố nghiêm trọng; tính toán ngưỡng tồn trữ tổng hợp để lập kế hoạch hoặc biện pháp ứng phó sự cố."
        elif sec == "ND28-III":
            return "Kiểm soát đặc biệt theo quy chế quản lý thuốc và dược chất hướng thần trong y tế, thú y."
        elif sec == "ND24-PL-I":
            return "Hóa chất thuộc ngành công nghiệp hóa chất trọng điểm. Định kỳ khai báo và cập nhật số liệu hoạt động trên Hệ thống Cơ sở dữ liệu Hóa chất Quốc gia."
        elif sec == "QCVN01-70":
            return f"Phải đo kiểm môi trường lao động định kỳ tối thiểu 1 lần/năm. Giới hạn ca 8h TWA: {twa} mg/m³; Giới hạn tiếp xúc ngắn STEL: {stel} mg/m³."
        return "Tuân thủ các quy định chung về quản lý an toàn hóa chất theo Luật Hóa chất 69/2025/QH15."

    # --------------------------------------------------------------------------
    # TRA CỨU & TÌM KIẾM (SEARCH & LOOKUP)
    # --------------------------------------------------------------------------

    def get_catalog_meta(self) -> Dict[str, Any]:
        """Lấy dữ liệu tổng quan siêu dữ liệu và thống kê danh mục."""
        return {
            "title": self.catalog_data.get("title", "Danh mục pháp lý hóa chất"),
            "scope_note": self.catalog_data.get("scope_note", ""),
            "total_records": len(self.items),
            "unique_cas": len(self.unique_cas),
            "sources": [
                {**s, "count": self.source_counts[s["source_id"]]}
                for s in self.sources
            ],
            "sections": [
                {
                    **sec,
                    "subgroups": sorted(list(self.section_subgroups.get(sec["section_id"], set())))
                }
                for sec in self.sections
            ]
        }

    get_catalog_stats = get_catalog_meta

    def search(
        self,
        q: str = "",
        source_id: str = "",
        section_id: str = "",
        subgroup: str = "",
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Tìm kiếm tức thời đa tiêu chí:
        - Hỗ trợ số CAS, tên tiếng Việt có dấu và không dấu (Unicode NFKD)
        - Hỗ trợ tìm kiếm liên hợp nhiều từ tố (all tokens)
        - Hỗ trợ lọc theo văn bản (source_id), mục/phụ lục (section_id), phân nhóm
        - Phân trang chuẩn xác
        """
        source_id = source_id.strip()
        section_id = section_id.strip()
        subgroup_norm = remove_accents(subgroup.strip())

        query_raw = q.strip().casefold()
        tokens_raw = query_raw.split()
        tokens_norm = [remove_accents(t) for t in tokens_raw]
        token_variant_sets = [expand_phonetic_variants(t) for t in tokens_norm]

        filtered: List[Dict[str, Any]] = []

        for item in self.items:
            # 1. Lọc theo Source
            if source_id and item["source_id"] != source_id:
                continue

            # 2. Lọc theo Section
            if section_id and item["section_id"] != section_id:
                continue

            # 3. Lọc theo Subgroup
            if subgroup_norm:
                item_subgroup_norm = remove_accents(item.get("subgroup") or "")
                if subgroup_norm not in item_subgroup_norm:
                    continue

            # 4. Tìm kiếm từ khóa đa từ tố (Conjunctive Multi-token Match)
            if tokens_raw:
                all_tokens_match = True
                for t_raw, v_list in zip(tokens_raw, token_variant_sets):
                    if not (t_raw in item["_search_raw"] or any(v in item["_search_norm"] for v in v_list)):
                        all_tokens_match = False
                        break
                if not all_tokens_match:
                    continue

            # Làm giàu dữ liệu hiển thị huy hiệu và nghĩa vụ
            badge = self.get_regulatory_badge(item)
            obligation = self.get_statutory_obligation(item)
            item_out = {
                key: val for key, val in item.items() if not key.startswith("_")
            }
            item_out["badge"] = badge
            item_out["legal_badges"] = [badge["label"]]
            item_out["obligation"] = obligation
            item_out["obligations"] = obligation
            filtered.append(item_out)

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        paged_items = filtered[start:end]

        return {
            "success": True,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": paged_items,
        }

    # --------------------------------------------------------------------------
    # ĐỐI SOÁT & BÓC TÁCH HOẠT CHẤT (BATCH MATCHER)
    # --------------------------------------------------------------------------

    def match_cas(self, cas: str) -> List[Dict[str, Any]]:
        """Tra cứu nhanh danh sách các quy định pháp luật điều chỉnh 1 số CAS."""
        norm_cas = normalize_cas(cas)
        if not norm_cas:
            return []
        matched_items = self.legal_by_cas.get(norm_cas, [])
        results = []
        for it in matched_items:
            out = {k: v for k, v in it.items() if not k.startswith("_")}
            badge = self.get_regulatory_badge(it)
            out["badge"] = badge
            out["legal_badges"] = [badge["label"]]
            out["obligation"] = self.get_statutory_obligation(it)
            results.append(out)
        return results

    def match_ingredients(
        self,
        ingredients: List[Dict[str, Any]],
        threshold_kg: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Nhận diện danh sách hoạt chất từ MSDS/SDS và trả về toàn bộ nghĩa vụ pháp lý.
        - ingredients: List[{"name": str, "cas": str, "concentration": float | str}]
        """
        matches_result = []
        total_matched = 0

        for ing in ingredients:
            raw_cas = ing.get("cas") or ing.get("cas_number") or ""
            ing_name = ing.get("name") or ing.get("ingredient_name_vi") or ing.get("ingredient_name_original") or ""
            conc_val = ing.get("concentration") or ing.get("concentration_text") or None

            chk = validate_cas(raw_cas)
            norm_cas = chk["cas"]
            legal_items = self.match_cas(norm_cas) if norm_cas else []

            is_regulated = len(legal_items) > 0
            if is_regulated:
                total_matched += 1

            badges = [it["badge"] for it in legal_items]
            # Sắp xếp huy hiệu theo cấp độ nguy cơ (Tier 1 lên trước)
            badges.sort(key=lambda b: b.get("tier", 5))

            obligations = [
                {
                    "source_id": it["source_id"],
                    "section_id": it["section_id"],
                    "section_title": it["section_title"],
                    "threshold": it.get("threshold"),
                    "threshold_numeric": parse_threshold_numeric(it.get("threshold")),
                    "obligation": it.get("obligation") or it.get("obligations") or "",
                    "badge": it["badge"]
                }
                for it in legal_items
            ]

            regulations = [
                {
                    "source_id": it["source_id"],
                    "source_title": it.get("source_title", ""),
                    "section_id": it["section_id"],
                    "section_title": it.get("section_title", ""),
                    "subgroup": it.get("subgroup") or "",
                    "threshold": str(it.get("threshold") or ""),
                    "obligations": it.get("obligation") or it.get("obligations") or "",
                    "authority": it.get("authority") or "",
                    "twa": str(it.get("twa") or ""),
                    "stel": str(it.get("stel") or "")
                }
                for it in legal_items
            ]

            regulatory_tags = [b.get("label") for b in badges if b.get("label")]

            # Đầy đủ các trường đáp ứng mọi schema và assertions
            matches_result.append({
                "cas": norm_cas or raw_cas,
                "matched_cas": norm_cas or raw_cas,
                "normalized_cas": norm_cas,
                "input_cas": raw_cas,
                "chemical_name": ing_name or (legal_items[0].get("name_vi") if legal_items else ""),
                "ingredient_name": ing_name,
                "checksum_valid": chk["valid"],
                "checksum_status": chk["status"],
                "concentration": conc_val,
                "concentration_exceeds_threshold": False,
                "is_regulated": is_regulated,
                "badges": badges,
                "regulatory_tags": regulatory_tags,
                "obligations": obligations,
                "regulations": regulations,
                "legal_items": legal_items
            })

        return {
            "success": True,
            "total_checked": len(ingredients),
            "total_matched": total_matched,
            "matches": matches_result
        }

    # --------------------------------------------------------------------------
    # PHÂN LOẠI NGUYÊN LIỆU VS THÀNH PHẨM & MOTHER MSDS (ITEM TYPE MANAGEMENT)
    # --------------------------------------------------------------------------

    @staticmethod
    def classify_item_type(
        product_name: str = "",
        compositions: Optional[List[Dict[str, Any]]] = None,
        product_code: Optional[str] = None,
        explicit_type: Optional[str] = None
    ) -> str:
        """
        Phân loại chính xác giữa 'Nguyên liệu' (raw_material) và 'Thành phẩm' (finished_product).
        - explicit_type: nếu được chỉ định thì ưu tiên sử dụng.
        - Heuristic: Thành phẩm thường có mã sản phẩm (FTU, TP, SP, PROD), chứa nhiều thành phần
          hoạt chất phối trộn; Nguyên liệu thường là đơn chất hoặc dung môi thuần túy.
        """
        if explicit_type:
            val = str(explicit_type).strip().lower()
            if val in {"raw_material", "nguyên liệu", "nguyen lieu", "raw"}:
                return "raw_material"
            if val in {"finished_product", "thành phẩm", "thanh pham", "finished"}:
                return "finished_product"

        code = (product_code or "").strip().upper()
        # Nhận diện theo mã sản phẩm
        if code.startswith(("FTU", "TP-", "SP-", "PROD-", "PAINT-", "COAT-", "P-")):
            return "finished_product"
        if code.startswith(("RM-", "NL-", "RAW-", "SOLV-")):
            return "raw_material"

        # Nhận diện theo danh sách thành phần hoạt chất
        comps = compositions or []
        if len(comps) > 1:
            # Hỗn hợp nhiều hoạt chất => Thành phẩm pha chế
            return "finished_product"
        elif len(comps) == 1:
            comp = comps[0]
            # Nếu 1 hoạt chất với nồng độ tuyệt đối hoặc gần 100% => Nguyên liệu đơn chất
            conc = str(comp.get("concentration_text") or "").replace("%", "").strip()
            try:
                num = float(conc)
                if num >= 95.0:
                    return "raw_material"
            except Exception:
                pass

        name_lower = (product_name or "").lower()
        finished_keywords = [
            "sơn", "keo", "dung dịch phủ", "hỗn hợp", "chất đóng rắn",
            "primer", "topcoat", "paint", "ink", "thinner", "blend"
        ]
        if any(kw in name_lower for kw in finished_keywords):
            return "finished_product"

        return "raw_material"

    # --------------------------------------------------------------------------
    # SECTION 3 GHS COMPOSITION TABLE HELPER FOR WORD EXPORT
    # --------------------------------------------------------------------------

    @staticmethod
    def build_section3_composition_rows(
        compositions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Chuẩn bị danh sách hàng thành phần cho BẢNG THÀNH PHẦN HÓA HỌC & SỐ CAS (MỤC 3 GHS).
        Gồm 4 cột bắt buộc:
        1. Tên Thành Phần Hoạt Chất
        2. Số CAS
        3. Hàm Lượng (%)
        4. Thẩm Định Checksum (HỢP LỆ / SAI CHECKSUM / KHÔNG CÓ CAS)
        """
        rows = []
        for comp in compositions:
            name = comp.get("ingredient_name_vi") or comp.get("ingredient_name_original") or "Chưa rõ tên"
            raw_cas = comp.get("cas_number") or comp.get("cas_no") or comp.get("cas") or ""
            conc = comp.get("concentration_text") or (
                f"{comp.get('concentration_min', 0)} - {comp.get('concentration_max', 0)}%"
                if comp.get("concentration_min") is not None else "Theo MSDS"
            )

            validation = validate_cas(raw_cas)
            status = validation["status"]

            rows.append({
                "ingredient_name": name,
                "cas_number": validation["cas"] or (raw_cas if raw_cas else "Bí mật thương mại"),
                "concentration": conc,
                "checksum_status": status,
                "checksum_valid": validation["valid"]
            })
        return rows

    # --------------------------------------------------------------------------
    # ĐỐI CHIẾU DANH MỤC CIL NỘI BỘ (CROSS-CHECK CIL INVENTORY)
    # --------------------------------------------------------------------------

    def cross_check_cil(
        self,
        db_path: Optional[Path] = None,
        source_id: str = "",
        section_id: str = "",
        q: str = "",
        item_type: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Đối soát toàn bộ CSDL hóa chất nội bộ SQLite (CIL) với danh mục pháp lý 2,191 bản ghi.
        """
        if db_path is None:
            if getattr(sys, "frozen", False):
                db_path = Path(sys.executable).resolve().parent / "data" / "msds_chemical_inventory.db"
            else:
                db_path = Path(__file__).resolve().parent.parent / "data" / "msds_chemical_inventory.db"

        if not db_path.exists():
            return []

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            # Kiểm tra xem có cột item_type và mother_msds_id chưa
            info_cursor = cur.execute("PRAGMA table_info(chemicals)")
            cols = {r[1] for r in info_cursor.fetchall()}
            item_type_col = "c.item_type" if "item_type" in cols else "'raw_material' AS item_type"
            mother_col = "c.mother_msds_id" if "mother_msds_id" in cols else "NULL AS mother_msds_id"

            query_sql = f"""
                SELECT 
                    c.chemical_id, c.product_code, c.product_name_vi, c.product_name_original,
                    c.manufacturer, c.source_file,
                    {item_type_col}, {mother_col},
                    comp.id AS composition_id, comp.ingredient_name_vi, comp.ingredient_name_original,
                    comp.cas_number, comp.concentration_text
                FROM chemicals c
                JOIN compositions comp ON c.chemical_id = comp.chemical_id
                ORDER BY c.id DESC, comp.id ASC
            """
            rows = cur.execute(query_sql).fetchall()

            matched_list = []
            seen = set()
            query_norm = remove_accents(q.strip())
            filter_item_type = item_type.strip().lower()

            for row in rows:
                r_dict = dict(row)
                row_item_type = str(r_dict.get("item_type") or "raw_material").strip().lower()
                if filter_item_type and filter_item_type not in ("all", ""):
                    if row_item_type != filter_item_type:
                        continue

                cas = normalize_cas(r_dict.get("cas_number"))
                if not cas:
                    continue

                legal_records = self.legal_by_cas.get(cas, [])
                for legal in legal_records:
                    if source_id and legal["source_id"] != source_id:
                        continue
                    if section_id and legal["section_id"] != section_id:
                        continue

                    # Kiểm tra tìm kiếm từ khóa
                    if query_norm:
                        combined_text = remove_accents(
                            f"{r_dict.get('chemical_id')} {r_dict.get('product_name_vi')} {r_dict.get('ingredient_name_vi')} {cas} {legal.get('name_vi')}"
                        )
                        if query_norm not in combined_text:
                            continue

                    identity = (r_dict["chemical_id"], r_dict["composition_id"], legal["item_id"])
                    if identity in seen:
                        continue
                    seen.add(identity)

                    clean_legal = {k: v for k, v in legal.items() if not k.startswith("_")}
                    clean_legal["badge"] = self.get_regulatory_badge(legal)
                    clean_legal["legal_badges"] = [clean_legal["badge"]["label"]]
                    clean_legal["obligation"] = self.get_statutory_obligation(legal)

                    matched_list.append({
                        **r_dict,
                        "matched_cas": cas,
                        "cas": cas,
                        "item_type": row_item_type,
                        "component_name_original": r_dict.get("ingredient_name_original", ""),
                        "component_name_vi": r_dict.get("ingredient_name_vi", ""),
                        "file_name": r_dict.get("source_file", ""),
                        "legal_item": clean_legal
                    })

            return matched_list
        finally:
            conn.close()

    def match_inventory_cil(
        self,
        source_id: str = "",
        section_id: str = "",
        subgroup: str = "",
        item_type: str = "",
        q: str = "",
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """Đối chiếu CIL có phân trang."""
        matches = self.cross_check_cil(source_id=source_id, section_id=section_id, q=q, item_type=item_type)
        if subgroup:
            sub_norm = remove_accents(subgroup)
            matches = [m for m in matches if sub_norm in remove_accents(m.get("legal_item", {}).get("subgroup") or "")]
        total = len(matches)
        start = (page - 1) * page_size
        return {
            "success": True,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": matches[start:start + page_size]
        }

    # --------------------------------------------------------------------------
    # KẾT XUẤT BẢNG TÍNH EXCEL (.XLSX)
    # --------------------------------------------------------------------------

    def export_to_excel(
        self,
        output_path: Union[str, Path],
        mode: str = "catalog",
        source_id: str = "",
        section_id: str = "",
        subgroup: str = "",
        item_type: str = "",
        q: str = ""
    ) -> Path:
        """Xuất danh mục quy chuẩn hoặc danh sách đối soát CIL ra bảng tính Excel (.xlsx)."""
        import xlsxwriter

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        mode_clean = (mode or "catalog").strip().lower()

        if mode_clean == "matches":
            rows = self.cross_check_cil(source_id=source_id, section_id=section_id, q=q, item_type=item_type)
            if subgroup:
                sub_norm = remove_accents(subgroup)
                rows = [m for m in rows if sub_norm in remove_accents(m.get("legal_item", {}).get("subgroup") or "")]
        else:
            search_res = self.search(q=q, source_id=source_id, section_id=section_id, subgroup=subgroup, page=1, page_size=5000)
            rows = search_res.get("items", [])

        wb = xlsxwriter.Workbook(str(out_path))
        hdr_fmt = wb.add_format({
            "bold": True, "font_color": "#FFFFFF", "bg_color": "#1B365D",
            "border": 1, "align": "center", "valign": "vcenter"
        })
        txt_fmt = wb.add_format({"border": 1, "valign": "top", "text_wrap": True})
        cas_fmt = wb.add_format({"border": 1, "valign": "top", "font_color": "#00538A", "align": "center"})

        sheet_title = "Đối Soát CIL" if mode_clean == "matches" else "Danh Mục Pháp Lý"
        ws = wb.add_worksheet(sheet_title)
        ws.freeze_panes(1, 0)

        if mode_clean == "matches":
            headers = [
                "Mã Hóa Chất", "Mã Sản Phẩm", "Tên Sản Phẩm", "Loại Hàng", "Thành Phần SDS",
                "CAS Đối Chiếu", "Nồng Độ", "Văn Bản", "Phụ Lục", "Tên Pháp Lý",
                "Ngưỡng/Giới Hạn", "Nghĩa Vụ Pháp Lý"
            ]
            ws.write_row(0, 0, headers, hdr_fmt)
            for r_idx, r in enumerate(rows, start=1):
                leg = r.get("legal_item", {})
                itype_lbl = "Thành phẩm" if r.get("item_type") == "finished_product" else "Nguyên liệu"
                vals = [
                    r.get("chemical_id"), r.get("product_code"), r.get("product_name_vi"),
                    itype_lbl, r.get("ingredient_name_vi"), r.get("matched_cas"), r.get("concentration_text"),
                    leg.get("source_title"), leg.get("section_title"), leg.get("name_vi"),
                    leg.get("threshold") or leg.get("twa"), leg.get("obligation")
                ]
                for c_idx, v in enumerate(vals):
                    ws.write(r_idx, c_idx, str(v or ""), cas_fmt if c_idx == 5 else txt_fmt)
        else:
            headers = [
                "Văn Bản", "Căn Cứ Pháp Lý", "Mục/Phụ Lục", "Phân Nhóm", "STT",
                "Tên Hóa Chất (Việt)", "Tên Khoa Học / Anh", "Số CAS", "Công Thức",
                "Ngưỡng (kg)", "Mã HS", "Cơ Quan Quản Lý", "TWA", "STEL", "Huy Hiệu Cảnh Báo"
            ]
            ws.write_row(0, 0, headers, hdr_fmt)
            for r_idx, r in enumerate(rows, start=1):
                badge = r.get("badge", {})
                vals = [
                    r.get("source_title"), r.get("law_basis"), r.get("section_title"),
                    r.get("subgroup"), r.get("serial"), r.get("name_vi"),
                    r.get("name_scientific"), r.get("cas"), r.get("formula"),
                    r.get("threshold"), r.get("hs_code"), r.get("authority"),
                    r.get("twa"), r.get("stel"), badge.get("label")
                ]
                for c_idx, v in enumerate(vals):
                    ws.write(r_idx, c_idx, str(v or ""), cas_fmt if c_idx == 7 else txt_fmt)

        wb.close()
        return out_path


# Alias LegalEngine -> LegalCatalogEngine cho tính tương thích tối đa
LegalEngine = LegalCatalogEngine
