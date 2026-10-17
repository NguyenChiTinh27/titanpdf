"""
storage_compatibility_engine.py — Chemical Storage Compatibility Matrix & Warehouse Checker
Conforming to Vietnamese Standard TCVN 5507:2002 (Hazardous Chemicals - Code of Safety
in Production, Commerce, Use, Storage and Transportation) and UN GHS.

Hazard Classes (11 Classes):
  1. GHS01: Explosives (Chất nổ, hợp chất tự phản ứng)
  2. GHS02: Flammables (Chất lỏng, khí và chất rắn dễ cháy)
  3. GHS03: Oxidizers (Chất oxy hóa mạnh, Peroxit hữu cơ)
  4. GHS04: Compressed Gases (Khí nén, khí hóa lỏng áp suất cao)
  5. GHS05_ACID: Corrosive Acids (Chất ăn mòn mang tính Axit, pH < 7)
  6. GHS05_BASE: Corrosive Bases (Chất ăn mòn mang tính Bazơ/Kiềm, pH > 7)
  7. GHS06: Acute Toxics (Chất độc cấp tính, muối xyanua, sunfua)
  8. GHS07: Harmful / Irritants (Kích ứng da/mắt, độc tính mức trung bình)
  9. GHS08: Health Hazards / CMR (Nguy hại sức khỏe lâu dài, ung thư, đột biến)
  10. GHS09: Environmental Hazards (Nguy hại môi trường thủy sinh)
  11. NON_DG: Non-dangerous Goods (Hóa chất an toàn, không nguy hại)

Compatibility Tiers:
  - C (COMPATIBLE / CHO PHÉP / Green #16A34A): Co-storage permitted in same compartment.
  - S (RESTRICTED / YÊU CẦU CÁCH LY / Yellow #EAB308): Segregation required (>= 3-5m or fire barrier).
  - X (FORBIDDEN / NGHIÊM CẤM / Red #DC2626): Strictly prohibited from co-storage.
"""

import json
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple


def _remove_accents(text: str) -> str:
    """Chuyển chuỗi tiếng Việt có dấu thành không dấu chữ thường."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    clean = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return clean.replace("đ", "d").replace("Đ", "d").lower().strip()


# =============================================================================
# 1. 11 HAZARD CLASS DEFINITIONS
# =============================================================================

STORAGE_CLASSES: Dict[str, Dict[str, Any]] = {
    "GHS01": {
        "id": "GHS01",
        "code": "GHS01",
        "label_vi": "Chất nổ & Tự phản ứng",
        "label_en": "Explosives & Self-Reactives",
        "icon": "💥",
        "color": "#B91C1C",
        "description": "Các chất và vật phẩm nổ, chất tự phản ứng loại A/B, chất phóng hỏa nổ.",
        "tcvn_clause": "TCVN 5507:2002 Mục 5.1 & 5.2"
    },
    "GHS02": {
        "id": "GHS02",
        "code": "GHS02",
        "label_vi": "Khí, Lỏng & Rắn dễ cháy",
        "label_en": "Flammables",
        "icon": "🔥",
        "color": "#DC2626",
        "description": "Chất lỏng có điểm chớp cháy ≤ 60°C, khí dễ cháy, chất rắn tự bắt cháy.",
        "tcvn_clause": "TCVN 5507:2002 Mục 5.3"
    },
    "GHS03": {
        "id": "GHS03",
        "code": "GHS03",
        "label_vi": "Chất oxy hóa mạnh",
        "label_en": "Oxidizers & Organic Peroxides",
        "icon": "⭕",
        "color": "#EA580C",
        "description": "Chất giải phóng oxy kích hoạt cháy nổ, peroxit hữu cơ loại B-F.",
        "tcvn_clause": "TCVN 5507:2002 Mục 5.3 & 5.4"
    },
    "GHS04": {
        "id": "GHS04",
        "code": "GHS04",
        "label_vi": "Khí nén & Hóa lỏng",
        "label_en": "Gases Under Pressure",
        "icon": "🗜️",
        "color": "#0284C7",
        "description": "Bình khí nén, khí hóa lỏng hoặc khí hòa tan dưới áp suất.",
        "tcvn_clause": "TCVN 5507:2002 Mục 5.5"
    },
    "GHS05_ACID": {
        "id": "GHS05_ACID",
        "code": "GHS05_ACID",
        "label_vi": "Ăn mòn mang tính Axit",
        "label_en": "Corrosive Acids (pH < 7)",
        "icon": "🧪",
        "color": "#7C3AED",
        "description": "Chất ăn mòn vô cơ và hữu cơ có tính axit (pH < 7, HCl, H2SO4, HNO3...).",
        "tcvn_clause": "TCVN 5507:2002 Mục 5.6"
    },
    "GHS05_BASE": {
        "id": "GHS05_BASE",
        "code": "GHS05_BASE",
        "label_vi": "Ăn mòn mang tính Bazơ / Kiềm",
        "label_en": "Corrosive Bases (pH > 7)",
        "icon": "⚗️",
        "color": "#4338CA",
        "description": "Chất ăn mòn mang tính kiềm (pH > 7, NaOH, KOH, NH4OH, dung dịch amin...).",
        "tcvn_clause": "TCVN 5507:2002 Mục 5.6"
    },
    "GHS06": {
        "id": "GHS06",
        "code": "GHS06",
        "label_vi": "Độc cấp tính nguy hiểm",
        "label_en": "Acute Toxicity (Cat 1-3)",
        "icon": "☠️",
        "color": "#991B1B",
        "description": "Chất độc chết người qua đường hít thở, tiêu hóa hoặc hấp thụ qua da (H300, H310, H330).",
        "tcvn_clause": "TCVN 5507:2002 Mục 5.7"
    },
    "GHS07": {
        "id": "GHS07",
        "code": "GHS07",
        "label_vi": "Kích ứng & Độc hại trung bình",
        "label_en": "Harmful / Irritants (Cat 4)",
        "icon": "⚠️",
        "color": "#D97706",
        "description": "Kích ứng đường hô hấp, kích ứng mắt/da, độc cấp tính loại 4 (H302, H312, H332).",
        "tcvn_clause": "TCVN 5507:2002 Mục 5.8"
    },
    "GHS08": {
        "id": "GHS08",
        "code": "GHS08",
        "label_vi": "Nguy hại sức khỏe lâu dài (CMR)",
        "label_en": "Health Hazards / CMR",
        "icon": "🫁",
        "color": "#C026D3",
        "description": "Chất gây ung thư, đột biến gen, độc tính sinh sản hoặc tổn thương nội tạng mãn tính.",
        "tcvn_clause": "TCVN 5507:2002 Mục 5.8"
    },
    "GHS09": {
        "id": "GHS09",
        "code": "GHS09",
        "label_vi": "Nguy hại môi trường thủy sinh",
        "label_en": "Environmental Hazards",
        "icon": "🐟",
        "color": "#0D9488",
        "description": "Độc hại cho sinh vật thủy sinh ngắn hạn và dài hạn (H400, H410, H411).",
        "tcvn_clause": "TCVN 5507:2002 Mục 5.9"
    },
    "NON_DG": {
        "id": "NON_DG",
        "code": "NON_DG",
        "label_vi": "Hóa chất an toàn (Không nguy hại)",
        "label_en": "Non-Dangerous Goods",
        "icon": "✅",
        "color": "#16A34A",
        "description": "Hóa chất không thuộc phân loại nguy hại theo hệ thống GHS và TCVN 5507.",
        "tcvn_clause": "TCVN 5507:2002 Mục 5.10"
    }
}


# =============================================================================
# 2. RAW PAIRWISE RULES TABLE UNDER TCVN 5507:2002
# =============================================================================

# Define specific interactions (order-independent). Default is "C" (Compatible).
_RULE_DEFINITIONS: List[Tuple[str, str, str, str, str, str]] = [
    # (ClassA, ClassB, Code, Status, DangerMechanism, TcvnClause)
    
    # --- GHS01 (Explosives) Interactions ---
    ("GHS01", "GHS01", "C", "COMPATIBLE", "Chất nổ lưu trữ trong kho thuốc nổ chuyên dụng theo nhóm tương thích.", "TCVN 5507 Mục 5.1"),
    ("GHS01", "GHS02", "X", "FORBIDDEN", "Chất nổ tuyệt đối cấm lưu trữ chung với chất dễ cháy; nguy cơ kích nổ tức thì.", "TCVN 5507 Điều 5.1 & 5.3"),
    ("GHS01", "GHS03", "X", "FORBIDDEN", "Chất nổ tuyệt đối cấm lưu trữ chung với chất oxy hóa; tăng độ nhạy nổ dữ dội.", "TCVN 5507 Điều 5.1 & 5.3"),
    ("GHS01", "GHS04", "X", "FORBIDDEN", "Chất nổ tuyệt đối cấm lưu trữ chung với bình khí nén áp suất cao.", "TCVN 5507 Điều 5.1 & 5.5"),
    ("GHS01", "GHS05_ACID", "X", "FORBIDDEN", "Chất nổ tuyệt đối cấm lưu trữ chung với axit ăn mòn; ăn mòn vỏ kíp và kích nổ.", "TCVN 5507 Điều 5.1 & 5.6"),
    ("GHS01", "GHS05_BASE", "X", "FORBIDDEN", "Chất nổ tuyệt đối cấm lưu trữ chung với chất ăn mòn kiềm.", "TCVN 5507 Điều 5.1 & 5.6"),
    ("GHS01", "GHS06", "X", "FORBIDDEN", "Chất nổ tuyệt đối cấm lưu trữ chung với chất độc hại cấp tính.", "TCVN 5507 Điều 5.1 & 5.7"),
    ("GHS01", "GHS07", "X", "FORBIDDEN", "Chất nổ cấm lưu trữ chung với hóa chất kích ứng thông thường.", "TCVN 5507 Điều 5.1"),
    ("GHS01", "GHS08", "X", "FORBIDDEN", "Chất nổ cấm lưu trữ chung với hóa chất nguy hại sức khỏe.", "TCVN 5507 Điều 5.1"),
    ("GHS01", "GHS09", "X", "FORBIDDEN", "Chất nổ cấm lưu trữ chung với hóa chất nguy hại môi trường.", "TCVN 5507 Điều 5.1"),
    ("GHS01", "NON_DG", "C", "COMPATIBLE", "Lưu trữ chung với vật tư an toàn nếu tuân thủ tiêu chuẩn kho vũ khí/thuốc nổ.", "TCVN 5507 Điều 5.1"),

    # --- GHS02 (Flammables) Interactions ---
    ("GHS02", "GHS02", "C", "COMPATIBLE", "Các chất dễ cháy được phép lưu trữ chung trong kho có hệ thống chống cháy nổ (PCCC).", "TCVN 5507 Mục 5.3"),
    ("GHS02", "GHS03", "X", "FORBIDDEN", "Nguy cơ cháy nổ cực lớn do chất oxy hóa kích hoạt và thúc đẩy đám cháy chất lỏng dễ cháy.", "TCVN 5507 Điều 5.3"),
    ("GHS02", "GHS04", "S", "RESTRICTED", "Phải cách ly tối thiểu 3-5m hoặc có tường ngăn chống cháy giữa bình khí nén và chất lỏng dễ cháy.", "TCVN 5507 Điều 5.3 & 5.5"),
    ("GHS02", "GHS05_ACID", "S", "RESTRICTED", "Phải có khay chống tràn riêng biệt ngăn axit ăn mòn làm thủng thùng chứa dung môi dễ cháy.", "TCVN 5507 Điều 5.3 & 5.6"),
    ("GHS02", "GHS05_BASE", "S", "RESTRICTED", "Phải cách ly khu vực hoặc dùng đê bao riêng biệt chống rò rỉ kiềm ăn mòn.", "TCVN 5507 Điều 5.3 & 5.6"),
    ("GHS02", "GHS06", "S", "RESTRICTED", "Phải cách ly tối thiểu 3-5m; khi có cháy dung môi sẽ phát tán khói độc nguy hiểm đến tính mạng.", "TCVN 5507 Điều 5.3 & 5.7"),
    ("GHS02", "GHS07", "C", "COMPATIBLE", "Cho phép lưu trữ chung trong kho thông thoáng và có thông gió cơ khí cục bộ.", "TCVN 5507 Mục 5.3"),
    ("GHS02", "GHS08", "C", "COMPATIBLE", "Cho phép lưu trữ chung nhưng cần kiểm soát nồng độ hơi hữu cơ trong không khí.", "TCVN 5507 Mục 5.3"),
    ("GHS02", "GHS09", "C", "COMPATIBLE", "Cho phép lưu trữ chung; yêu cầu có rãnh thu gom nước thải tràn đổ.", "TCVN 5507 Mục 5.3"),
    ("GHS02", "NON_DG", "C", "COMPATIBLE", "Cho phép lưu trữ chung trong kho hàng.", "TCVN 5507 Mục 5.3"),

    # --- GHS03 (Oxidizers) Interactions ---
    ("GHS03", "GHS03", "C", "COMPATIBLE", "Lưu trữ chung tại kho riêng biệt thoáng mát, tránh ánh nắng trực tiếp và nhiệt độ cao.", "TCVN 5507 Mục 5.4"),
    ("GHS03", "GHS04", "S", "RESTRICTED", "Phải cách ly bình khí nén khỏi chất oxy hóa tối thiểu 5m hoặc ngăn bằng tường chống cháy.", "TCVN 5507 Điều 5.4 & 5.5"),
    ("GHS03", "GHS05_ACID", "X", "FORBIDDEN", "Chất oxy hóa phản ứng với axit sinh nhiệt dữ dội và giải phóng khí độc/khí clo ăn mòn.", "TCVN 5507 Điều 5.4 & 5.6"),
    ("GHS03", "GHS05_BASE", "S", "RESTRICTED", "Phải lưu trữ ở khu vực cách ly và trang bị hệ thống thu gom tràn đổ riêng.", "TCVN 5507 Điều 5.4 & 5.6"),
    ("GHS03", "GHS06", "X", "FORBIDDEN", "Chất oxy hóa phản ứng với chất độc có thể giải phóng khí độc hại cấp tính và gây nổ.", "TCVN 5507 Điều 5.4 & 5.7"),
    ("GHS03", "GHS07", "S", "RESTRICTED", "Cách ly tránh phản ứng oxy hóa không kiểm soát với các hợp chất hữu cơ.", "TCVN 5507 Điều 5.4"),
    ("GHS03", "GHS08", "S", "RESTRICTED", "Yêu cầu cách ly tối thiểu 3m ngăn ngừa phản ứng xúc tác oxy hóa.", "TCVN 5507 Điều 5.4"),
    ("GHS03", "GHS09", "C", "COMPATIBLE", "Cho phép lưu trữ chung trong kho khô ráo.", "TCVN 5507 Mục 5.4"),
    ("GHS03", "NON_DG", "C", "COMPATIBLE", "Cho phép lưu trữ chung với vật tư trơ không cháy.", "TCVN 5507 Mục 5.4"),

    # --- GHS04 (Compressed Gases) Interactions ---
    ("GHS04", "GHS04", "C", "COMPATIBLE", "Bình khí nén được lưu trữ đứng, xích giữ an toàn, có nắp chụp bảo vệ van.", "TCVN 5507 Mục 5.5"),
    ("GHS04", "GHS05_ACID", "S", "RESTRICTED", "Cách ly bình khí nén khỏi khu vực axit để ngăn hơi axit ăn mòn van và vỏ bình.", "TCVN 5507 Điều 5.5 & 5.6"),
    ("GHS04", "GHS05_BASE", "S", "RESTRICTED", "Cách ly bình khí nén khỏi khu vực kiềm ăn mòn.", "TCVN 5507 Điều 5.5 & 5.6"),
    ("GHS04", "GHS06", "S", "RESTRICTED", "Bình khí độc và khí nén thường phải có khu vực lưu trữ chuyên dụng có cảm biến rò rỉ.", "TCVN 5507 Điều 5.5 & 5.7"),
    ("GHS04", "GHS07", "C", "COMPATIBLE", "Cho phép lưu trữ chung trong kho có thông gió tự nhiên.", "TCVN 5507 Mục 5.5"),
    ("GHS04", "GHS08", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.5"),
    ("GHS04", "GHS09", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.5"),
    ("GHS04", "NON_DG", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.5"),

    # --- GHS05_ACID (Corrosive Acids) Interactions ---
    ("GHS05_ACID", "GHS05_ACID", "C", "COMPATIBLE", "Axit lưu trữ chung trong tủ hoặc khoang chống ăn mòn có khay hứng sự cố.", "TCVN 5507 Mục 5.6"),
    ("GHS05_ACID", "GHS05_BASE", "X", "FORBIDDEN", "Phản ứng trung hòa tỏa nhiệt mãnh liệt có thể gây nổ bồn chứa hoặc bắn tóe hóa chất ăn mòn nguy hiểm.", "TCVN 5507 Điều 5.6"),
    ("GHS05_ACID", "GHS06", "X", "FORBIDDEN", "Axit phản ứng với muối xyanua/sunfua giải phóng khí cực độc HCN hoặc H2S gây chết người tức thì.", "TCVN 5507 Điều 5.6 & 5.7"),
    ("GHS05_ACID", "GHS07", "C", "COMPATIBLE", "Cho phép lưu trữ chung nhưng cần có khay hứng chống ăn mòn sàn kho.", "TCVN 5507 Mục 5.6"),
    ("GHS05_ACID", "GHS08", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.6"),
    ("GHS05_ACID", "GHS09", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.6"),
    ("GHS05_ACID", "NON_DG", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.6"),

    # --- GHS05_BASE (Corrosive Bases) Interactions ---
    ("GHS05_BASE", "GHS05_BASE", "C", "COMPATIBLE", "Kiềm lưu trữ chung trong khu vực chống kiềm có bồn gom sự cố tràn đổ.", "TCVN 5507 Mục 5.6"),
    ("GHS05_BASE", "GHS06", "S", "RESTRICTED", "Cách ly tối thiểu 3m để kiểm soát rò rỉ và nguy cơ phản ứng sinh khí độc.", "TCVN 5507 Điều 5.6 & 5.7"),
    ("GHS05_BASE", "GHS07", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.6"),
    ("GHS05_BASE", "GHS08", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.6"),
    ("GHS05_BASE", "GHS09", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.6"),
    ("GHS05_BASE", "NON_DG", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.6"),

    # --- GHS06 (Acute Toxics) Interactions ---
    ("GHS06", "GHS06", "C", "COMPATIBLE", "Hóa chất độc cấp tính lưu trữ trong tủ có khóa bảo vệ và biển cảnh báo nguy hiểm.", "TCVN 5507 Mục 5.7"),
    ("GHS06", "GHS07", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.7"),
    ("GHS06", "GHS08", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.7"),
    ("GHS06", "GHS09", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.7"),
    ("GHS06", "NON_DG", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.7"),

    # --- GHS07 (Harmful / Irritants) Interactions ---
    ("GHS07", "GHS07", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.8"),
    ("GHS07", "GHS08", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.8"),
    ("GHS07", "GHS09", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.8"),
    ("GHS07", "NON_DG", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.8"),

    # --- GHS08 (Health Hazards / CMR) Interactions ---
    ("GHS08", "GHS08", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.8"),
    ("GHS08", "GHS09", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.8"),
    ("GHS08", "NON_DG", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.8"),

    # --- GHS09 (Environmental Hazards) Interactions ---
    ("GHS09", "GHS09", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.9"),
    ("GHS09", "NON_DG", "C", "COMPATIBLE", "Cho phép lưu trữ chung.", "TCVN 5507 Mục 5.9"),

    # --- NON_DG (Non-Dangerous Goods) Interactions ---
    ("NON_DG", "NON_DG", "C", "COMPATIBLE", "Cho phép lưu trữ chung tự do theo quy trình kho thông thường.", "TCVN 5507 Mục 5.10"),
]

# Build symmetric lookup table
COMPATIBILITY_MATRIX_MAP: Dict[Tuple[str, str], Dict[str, Any]] = {}

for _ca, _cb, _code, _status, _mech, _ref in _RULE_DEFINITIONS:
    _badge = "CẤM LƯU TRỮ CHUNG" if _code == "X" else ("YÊU CẦU CÁCH LY" if _code == "S" else "CHO PHÉP LƯU TRỮ")
    _color = "#DC2626" if _code == "X" else ("#EAB308" if _code == "S" else "#16A34A")
    _entry = {
        "class_a": _ca,
        "class_b": _cb,
        "code": _code,
        "status": _status,
        "badge": _badge,
        "color": _color,
        "mechanism": _mech,
        "tcvn_clause": _ref
    }
    COMPATIBILITY_MATRIX_MAP[(_ca, _cb)] = _entry
    COMPATIBILITY_MATRIX_MAP[(_cb, _ca)] = dict(_entry, class_a=_cb, class_b=_ca)


# =============================================================================
# 3. HELPER FUNCTIONS: CLASSIFICATION & MATRIX ENGINE
# =============================================================================

# Keywords for Acid vs Base heuristic detection
ACID_KEYWORDS = [
    "axit", "acid", "hcl", "h2so4", "hno3", "h3po4", "ch3cooh", "hf", "hbr",
    "clohydric", "sunfuric", "sulfuric", "photphoric", "phosphoric", "nitric",
    "axetic", "acetic", "formic", "oxalic", "citric", "ptsa", "sulfonic"
]

BASE_KEYWORDS = [
    "hydroxit", "hydroxide", "naoh", "koh", "ca(oh)2", "ba(oh)2", "nh3", "nh4oh",
    "amoniac", "ammonia", "kiềm", "kiem", "bazo", "bazơ", "base", "amin", "amine",
    "trietanolamin", "tea", "dmea", "dimetylamin", "dietylamin"
]


def classify_storage_classes(chem_data: Any) -> List[str]:
    """
    Phân loại hóa chất vào 11 nhóm nguy hại lưu trữ kho theo TCVN 5507:2002.
    Đặc biệt bóc tách GHS05 thành GHS05_ACID vs GHS05_BASE dựa vào pH, chemical_type và tên gọi.
    """
    if not chem_data:
        return ["NON_DG"]

    # If chem_data is a string ID, try looking up in DB
    if isinstance(chem_data, (str, int)):
        try:
            from core.msds_intelligence import MSDSDatabase
            loaded = MSDSDatabase.get_chemical(str(chem_data))
            if loaded:
                chem_data = loaded
            else:
                chem_data = {"id": str(chem_data), "name": str(chem_data)}
        except Exception:
            chem_data = {"id": str(chem_data), "name": str(chem_data)}

    # Extract GHS codes
    ghs_list: List[str] = []
    raw_ghs = chem_data.get("ghs_codes") or chem_data.get("ghs") or chem_data.get("ghs_pictograms") or []
    if isinstance(raw_ghs, str):
        # Could be comma or space separated
        for part in re.split(r"[,;\s]+", raw_ghs):
            part = part.strip().upper()
            if part:
                ghs_list.append(part)
    elif isinstance(raw_ghs, (list, tuple, set)):
        for item in raw_ghs:
            if isinstance(item, str):
                item_s = item.strip().upper()
                if item_s:
                    ghs_list.append(item_s)

    # Check for NON DG
    if not ghs_list or any("NON" in g and "DG" in g for g in ghs_list):
        return ["NON_DG"]

    detected_classes: Set[str] = set()

    for g in ghs_list:
        # Standard GHS classes
        if "GHS01" in g:
            detected_classes.add("GHS01")
        elif "GHS02" in g:
            detected_classes.add("GHS02")
        elif "GHS03" in g:
            detected_classes.add("GHS03")
        elif "GHS04" in g:
            detected_classes.add("GHS04")
        elif "GHS05" in g or "GHS05_ACID" in g or "GHS05_BASE" in g:
            # Handle Corrosive Subclassification (Acid vs Base)
            c_type = str(chem_data.get("chemical_type") or "").strip().lower()
            ph_val = None
            try:
                raw_ph = chem_data.get("ph") or chem_data.get("ph_value")
                if raw_ph is not None:
                    # extract numbers from pH string like "pH: 1.5 - 2.0"
                    m = re.search(r"[-+]?\d*\.\d+|\d+", str(raw_ph))
                    if m:
                        ph_val = float(m.group(0))
            except Exception:
                ph_val = None

            search_text = " ".join([
                str(chem_data.get("product_name_vi") or ""),
                str(chem_data.get("product_name_original") or ""),
                str(chem_data.get("product_name") or ""),
                str(chem_data.get("name") or ""),
                str(chem_data.get("code") or ""),
                str(chem_data.get("product_code") or ""),
                str(chem_data.get("intended_use") or ""),
                str(chem_data.get("formula") or ""),
            ])
            norm_text = _remove_accents(search_text)

            is_acid = False
            is_base = False

            if "acid" in c_type or "axit" in c_type:
                is_acid = True
            elif "base" in c_type or "bazo" in c_type or "alkali" in c_type or "kiem" in c_type:
                is_base = True
            elif ph_val is not None:
                if ph_val < 6.5:
                    is_acid = True
                elif ph_val > 7.5:
                    is_base = True

            if not is_acid and not is_base:
                # Check keywords
                for kw in ACID_KEYWORDS:
                    if kw in norm_text:
                        is_acid = True
                        break
                for kw in BASE_KEYWORDS:
                    if kw in norm_text:
                        is_base = True
                        break

            if is_base and not is_acid:
                detected_classes.add("GHS05_BASE")
            elif is_acid and not is_base:
                detected_classes.add("GHS05_ACID")
            else:
                # Default for GHS05 when undetermined: classify as Acid (most common corrosive)
                # or if specifically flagged in input
                if "BASE" in g:
                    detected_classes.add("GHS05_BASE")
                else:
                    detected_classes.add("GHS05_ACID")
        elif "GHS06" in g:
            detected_classes.add("GHS06")
        elif "GHS07" in g:
            detected_classes.add("GHS07")
        elif "GHS08" in g:
            detected_classes.add("GHS08")
        elif "GHS09" in g:
            detected_classes.add("GHS09")

    if not detected_classes:
        return ["NON_DG"]

    return sorted(list(detected_classes))


def get_matrix_definition() -> Dict[str, Any]:
    """
    Trả về định nghĩa toàn diện của ma trận tương thích lưu kho 11x11 theo TCVN 5507:2002.
    Bao gồm danh mục nhóm nguy hại, bảng tra 11x11, chú dẫn mã C/S/X và căn cứ pháp lý.
    """
    classes_list = list(STORAGE_CLASSES.values())
    class_ids = [c["id"] for c in classes_list]

    grid_matrix: Dict[str, Dict[str, Any]] = {}
    for ca in class_ids:
        grid_matrix[ca] = {}
        for cb in class_ids:
            rule = COMPATIBILITY_MATRIX_MAP.get((ca, cb))
            if rule:
                grid_matrix[ca][cb] = rule
            else:
                # Fallback default: C
                grid_matrix[ca][cb] = {
                    "class_a": ca,
                    "class_b": cb,
                    "code": "C",
                    "status": "COMPATIBLE",
                    "badge": "CHO PHÉP",
                    "color": "#16A34A",
                    "mechanism": "Cho phép lưu trữ chung trong cùng khoang chứa theo điều kiện kho tiêu chuẩn.",
                    "tcvn_clause": "TCVN 5507:2002 Mục 5"
                }

    legend = {
        "C": {
            "code": "C",
            "status": "COMPATIBLE",
            "label": "Cho phép lưu trữ chung (Compatible)",
            "badge": "CHO PHÉP",
            "color": "#16A34A",
            "description": "Được phép xếp chung trong cùng một khoang chứa hoặc kệ hàng tiêu chuẩn có thông gió phù hợp."
        },
        "S": {
            "code": "S",
            "status": "RESTRICTED",
            "label": "Yêu cầu cách ly (Segregation required)",
            "badge": "CÁCH LY",
            "color": "#EAB308",
            "description": "Phải cách ly khoảng cách tối thiểu 3m - 5m, sử dụng khay chống tràn sự cố riêng biệt hoặc vách ngăn chống cháy."
        },
        "X": {
            "code": "X",
            "status": "FORBIDDEN",
            "label": "Nghiêm cấm lưu trữ chung (Forbidden)",
            "badge": "CẤM",
            "color": "#DC2626",
            "description": "Tuyệt đối không lưu trữ trong cùng một kho/ngăn chứa. Nguy cơ cháy nổ cực lớn, tỏa nhiệt mãnh liệt hoặc thoát khí độc chết người."
        }
    }

    return {
        "standard": "TCVN 5507:2002",
        "title": "MA TRẬN TƯƠNG THÍCH LƯU KHO HÓA CHẤT NGUY HIỂM (TCVN 5507:2002 & GHS)",
        "authority": "Bộ Khoa học và Công nghệ / Bộ Công Thương",
        "classes": classes_list,
        "hazard_classes": classes_list,
        "categories": classes_list,
        "matrix": grid_matrix,
        "rules": grid_matrix,
        "legend": legend,
        "total_classes": len(classes_list)
    }


def evaluate_pairwise(chem_a: Any, chem_b: Any) -> Dict[str, Any]:
    """
    Đánh giá tương thích lưu kho giữa 2 hóa chất cụ thể theo TCVN 5507:2002.
    Nếu một hóa chất có nhiều nhóm nguy hại, trả về mức tương thích nghiêm ngặt nhất (X > S > C).
    """
    # Normalize Chem A
    if isinstance(chem_a, (str, int)):
        try:
            from core.msds_intelligence import MSDSDatabase
            loaded = MSDSDatabase.get_chemical(str(chem_a))
            chem_a = loaded or {"id": str(chem_a), "name": str(chem_a)}
        except Exception:
            chem_a = {"id": str(chem_a), "name": str(chem_a)}

    # Normalize Chem B
    if isinstance(chem_b, (str, int)):
        try:
            from core.msds_intelligence import MSDSDatabase
            loaded = MSDSDatabase.get_chemical(str(chem_b))
            chem_b = loaded or {"id": str(chem_b), "name": str(chem_b)}
        except Exception:
            chem_b = {"id": str(chem_b), "name": str(chem_b)}

    id_a = str(chem_a.get("id") or chem_a.get("chemical_id") or chem_a.get("product_code") or "CHEM_A")
    name_a = str(chem_a.get("product_name_vi") or chem_a.get("product_name") or chem_a.get("name") or id_a)

    id_b = str(chem_b.get("id") or chem_b.get("chemical_id") or chem_b.get("product_code") or "CHEM_B")
    name_b = str(chem_b.get("product_name_vi") or chem_b.get("product_name") or chem_b.get("name") or id_b)

    classes_a = classify_storage_classes(chem_a)
    classes_b = classify_storage_classes(chem_b)

    # Worst-case compatibility evaluation across all hazard class pairs
    # Hierarchy: X (severity 3) > S (severity 2) > C (severity 1)
    worst_code = "C"
    worst_severity = 1
    worst_status = "COMPATIBLE"
    worst_color = "#16A34A"
    worst_badge = "CHO PHÉP"
    all_mechanisms: List[str] = []
    all_clauses: List[str] = []
    conflict_pairs: List[Dict[str, Any]] = []

    for ca in classes_a:
        for cb in classes_b:
            rule = COMPATIBILITY_MATRIX_MAP.get((ca, cb))
            if not rule:
                continue

            code = rule.get("code", "C")
            sev = 3 if code == "X" else (2 if code == "S" else 1)

            if sev > 1:
                conflict_pairs.append({
                    "class_a": ca,
                    "class_a_label": STORAGE_CLASSES.get(ca, {}).get("label_vi", ca),
                    "class_b": cb,
                    "class_b_label": STORAGE_CLASSES.get(cb, {}).get("label_vi", cb),
                    "code": code,
                    "mechanism": rule.get("mechanism", ""),
                    "tcvn_clause": rule.get("tcvn_clause", "")
                })

            if sev > worst_severity:
                worst_severity = sev
                worst_code = code
                worst_status = rule.get("status", "COMPATIBLE")
                worst_color = rule.get("color", "#16A34A")
                worst_badge = rule.get("badge", "CHO PHÉP")

            mech = rule.get("mechanism")
            if mech and mech not in all_mechanisms and sev > 1:
                all_mechanisms.append(mech)
            clause = rule.get("tcvn_clause")
            if clause and clause not in all_clauses:
                all_clauses.append(clause)

    if not all_mechanisms:
        danger_mechanism = "Hai hóa chất này không có phản ứng tương khắc nguy hiểm; cho phép lưu trữ chung trong kho tiêu chuẩn."
        safety_measures = "Đảm bảo khoảng cách bảo quản hàng hóa thông thường, lối đi thông thoáng và thông gió tự nhiên."
    else:
        danger_mechanism = " | ".join(all_mechanisms)
        if worst_code == "X":
            safety_measures = "TUYỆT ĐỐI CẤM ĐỂ CHUNG. Bắt buộc lưu trữ ở 2 kho riêng biệt hoặc ngăn cách bằng tường chống cháy giới hạn chịu lửa REI ≥ 150 phút. Trang bị hệ thống chữa cháy chuyên dụng."
        else:
            safety_measures = "BẮT BUỘC CÁCH LY. Duy trì khoảng cách tối thiểu từ 3m đến 5m giữa hai lô hàng hoặc ngăn cách bằng vách chống cháy. Trang bị khay chống tràn riêng biệt để ngăn ngừa rò rỉ tiếp xúc."

    return {
        "chem_a": {
            "id": id_a,
            "name": name_a,
            "storage_classes": classes_a,
            "classes_info": [STORAGE_CLASSES.get(c) for c in classes_a if c in STORAGE_CLASSES]
        },
        "chem_b": {
            "id": id_b,
            "name": name_b,
            "storage_classes": classes_b,
            "classes_info": [STORAGE_CLASSES.get(c) for c in classes_b if c in STORAGE_CLASSES]
        },
        "code": worst_code,
        "status": worst_status,
        "badge": worst_badge,
        "color": worst_color,
        "severity": worst_severity,
        "danger_mechanism": danger_mechanism,
        "safety_measures": safety_measures,
        "recommended_measures": safety_measures,
        "tcvn_reference": " | ".join(all_clauses) if all_clauses else "TCVN 5507:2002 Mục 5",
        "conflict_pairs": conflict_pairs
    }


def check_inventory_compatibility(chem_list: Optional[List[Any]]) -> Dict[str, Any]:
    """
    Kiểm tra tương thích toàn diện cho một danh sách hóa chất trong kho (hoặc toàn bộ CSDL).
    Trả về danh sách các cặp tương khắc cấm (X), cặp cần cách ly (S), và cặp an toàn (C).
    Xử lý an toàn các trường hợp danh sách rỗng hoặc chỉ có 1 hóa chất mà không gây lỗi.
    """
    # If None or empty list
    if not chem_list:
        return {
            "total_chemicals": 0,
            "total_pairs": 0,
            "conflicts": [],
            "warnings": [],
            "compatible": [],
            "conflict_count": 0,
            "warning_count": 0,
            "compatible_count": 0,
            "status": "COMPATIBLE",
            "summary": "Không có hóa chất nào được chỉ định để kiểm tra.",
            "pairs": []
        }

    # Normalize chemicals list
    normalized_chems: List[Dict[str, Any]] = []
    for item in chem_list:
        if isinstance(item, (str, int)):
            try:
                from core.msds_intelligence import MSDSDatabase
                loaded = MSDSDatabase.get_chemical(str(item))
                if loaded:
                    normalized_chems.append(loaded)
                else:
                    normalized_chems.append({"id": str(item), "name": str(item)})
            except Exception:
                normalized_chems.append({"id": str(item), "name": str(item)})
        elif isinstance(item, dict):
            normalized_chems.append(item)

    n = len(normalized_chems)
    if n <= 1:
        single_name = normalized_chems[0].get("product_name_vi") or normalized_chems[0].get("name") or "Hóa chất" if n == 1 else ""
        return {
            "total_chemicals": n,
            "total_pairs": 0,
            "conflicts": [],
            "warnings": [],
            "compatible": [],
            "conflict_count": 0,
            "warning_count": 0,
            "compatible_count": 0,
            "status": "COMPATIBLE",
            "summary": f"Chỉ có {n} hóa chất ({single_name}), không có xung đột lưu trữ kho.",
            "pairs": []
        }

    conflicts: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    compatible: List[Dict[str, Any]] = []
    all_pairs: List[Dict[str, Any]] = []

    for i in range(n):
        for j in range(i + 1, n):
            eval_res = evaluate_pairwise(normalized_chems[i], normalized_chems[j])
            all_pairs.append(eval_res)
            code = eval_res.get("code")
            if code == "X":
                conflicts.append(eval_res)
            elif code == "S":
                warnings.append(eval_res)
            else:
                compatible.append(eval_res)

    total_pairs = len(all_pairs)
    overall_status = "FORBIDDEN" if conflicts else ("RESTRICTED" if warnings else "COMPATIBLE")

    if conflicts:
        summary = f"NGUY HIỂM: Phát hiện {len(conflicts)} cặp hóa chất CẤM LƯU TRỮ CHUNG (Mã X) theo TCVN 5507:2002! Cần di dời ngay vào các kho riêng biệt."
    elif warnings:
        summary = f"CẢNH BÁO: Phát hiện {len(warnings)} cặp hóa chất CẦN CÁCH LY (Mã S, ≥ 3-5m hoặc có vách ngăn). Không phát hiện xung đột cấm."
    else:
        summary = f"AN TOÀN: Tất cả {total_pairs} cặp hóa chất đều TƯƠNG THÍCH LƯU TRỮ (Mã C) theo TCVN 5507:2002."

    return {
        "total_chemicals": n,
        "total_pairs": total_pairs,
        "conflicts": conflicts,
        "warnings": warnings,
        "compatible": compatible,
        "conflict_count": len(conflicts),
        "warning_count": len(warnings),
        "compatible_count": len(compatible),
        "status": overall_status,
        "summary": summary,
        "pairs": all_pairs
    }
