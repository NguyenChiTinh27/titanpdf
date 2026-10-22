"""
core/hse_report_engine.py — Core HSE Report Studio Engine for TitanPDF.

Provides:
- 26-item ZhanChen checklist schema and Table 0 bidirectional mapping.
- Template asset bundling resolution (sys._MEIPASS & multi-tier fallbacks).
- OOXML generator with strict A4 page geometry, 2 items/page clustering,
  row heights (6150 dxa / 700 dxa separator with <w:cantSplit/>).
- Lanczos image fitting pipeline (max 3.38 in x 4.25 in).
- Collision-safe Windows file lock resolver (safe_write_bytes).
- Full DOCX decompiler (parse_docx_to_report) with DrawingML/VML image extraction.
- Offline heuristics, translation, and text professionalizer.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("hse_report_engine")

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from PIL import Image, ImageOps


# =============================================================================
# Path & Asset Resolution (4-tier fallback including PyInstaller _MEIPASS)
# =============================================================================

def get_template_path() -> Path:
    candidates = []
    if getattr(sys, "frozen", False):
        base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates.extend([
            base_dir / "core" / "templates" / "HSE-template.docx",
            base_dir / "templates" / "HSE-template.docx",
        ])
    module_dir = Path(__file__).resolve().parent
    candidates.extend([
        module_dir / "templates" / "HSE-template.docx",
        module_dir.parent / "core" / "templates" / "HSE-template.docx",
        module_dir.parent / "template" / "HSE-template.docx",
        Path("/app/core/templates/HSE-template.docx"),
        Path("/app/templates/HSE-template.docx"),
        Path("/opt/render/project/src/core/templates/HSE-template.docx"),
        Path(r"E:\Tool\hse-report-app\template\HSE-template.docx"),
    ])
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    raise RuntimeError(f"Không tìm thấy file mẫu HSE-template.docx. Đã kiểm tra: {candidates}")


def get_logo_path() -> Path:
    candidates = []
    if getattr(sys, "frozen", False):
        base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates.extend([
            base_dir / "core" / "templates" / "logo.jpeg",
            base_dir / "templates" / "logo.jpeg",
        ])
    module_dir = Path(__file__).resolve().parent
    candidates.extend([
        module_dir / "templates" / "logo.jpeg",
        module_dir.parent / "core" / "templates" / "logo.jpeg",
        module_dir.parent / "static" / "assets" / "logo.jpeg",
        Path(r"E:\Tool\hse-report-app\assets\logo.jpeg"),
    ])
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return candidates[0]


# =============================================================================
# 26-Item Checklist Schema (5 Thematic Categories matching Table 0)
# =============================================================================

CHECKLIST_SECTIONS = [
    {
        "title": "一、消防安全检查 / Kiểm tra an toàn phòng cháy",
        "items": [
            {"row": 3, "category": "消防设施 / Thiết bị PCCC", "content": "火灾自动报警系统是否存在关闭、停用现象（两个门卫室都要查看）；\nHệ thống báo cháy tự động có bị tắt hoặc ngừng sử dụng không (kiểm tra cả hai phòng bảo vệ).", "method": "查现场 / Kiểm tra hiện trường"},
            {"row": 4, "category": "消防设施 / Thiết bị PCCC", "content": "火灾自动报警系统是否存在故障、误报现象。\nHệ thống báo cháy tự động có bị lỗi hoặc báo động giả không.", "method": "查报警信息 / Kiểm tra thông tin báo động"},
            {"row": 5, "category": "消防设施 / Thiết bị PCCC", "content": "检查门卫室处警记录表，所有报警是否进行现场处置并填写处警记录。\nKiểm tra sổ ghi chép xử lý báo động tại phòng bảo vệ, xem tất cả cảnh báo có được xử lý tại hiện trường và ghi chép lại không.", "method": "查门卫室记录 / Kiểm tra sổ phòng bảo vệ"},
            {"row": 6, "category": "消防设施 / Thiết bị PCCC", "content": "抽查2处雨淋阀处消防警铃是否可以正常报警。（新厂有该设施）\nKiểm tra ngẫu nhiên chuông báo cháy tại 2 vị trí van xả tràn xem có hoạt động bình thường không (nhà máy mới có thiết bị này).", "method": "测试设备设施 / Thử nghiệm thiết bị"},
            {"row": 7, "category": "消防器材 / Dụng cụ chữa cháy", "content": "抽查4处灭火器是否按时间点检，是否设置在明显和便于取用的地方，设置是否稳固、铭牌朝外。\nKiểm tra ngẫu nhiên 4 vị trí bình chữa cháy: đúng hạn, dễ thấy, dễ lấy, đặt chắc chắn và nhãn hướng ra ngoài.", "method": "查现场 / Kiểm tra hiện trường"},
            {"row": 8, "category": "消防器材 / Dụng cụ chữa cháy", "content": "抽查4处消火栓水带、水枪及接口是否完好、匹配，是否缺少垫片。\nKiểm tra ngẫu nhiên 4 tủ chữa cháy: vòi, lăng phun, đầu nối và ron đệm có đầy đủ, phù hợp và nguyên vẹn không.", "method": "查现场 / Kiểm tra hiện trường"},
            {"row": 9, "category": "安全通道 / Lối thoát hiểm", "content": "检查车间安全出口、疏散通道是否畅通，安全门是否有上锁、遮挡、占用情况。\nKiểm tra cửa và lối thoát hiểm của xưởng có thông thoáng; cửa an toàn có bị khóa, che khuất hoặc chiếm dụng không.", "method": "查现场 / Kiểm tra hiện trường"},
            {"row": 10, "category": "安全通道 / Lối thoát hiểm", "content": "抽查仓库4处安全出口、疏散通道是否畅通，安全门是否有上锁、遮挡、占用情况。\nKiểm tra ngẫu nhiên 4 cửa và lối thoát hiểm của kho có thông thoáng; cửa có bị khóa, che khuất hoặc chiếm dụng không.", "method": "查现场 / Kiểm tra hiện trường"},
            {"row": 11, "category": "安全通道 / Lối thoát hiểm", "content": "抽查3处安全疏散指示标志、应急照明是否完好。\nKiểm tra ngẫu nhiên 3 biển chỉ dẫn thoát hiểm và đèn chiếu sáng sự cố có hoạt động tốt không.", "method": "查设施 / Kiểm tra thiết bị"},
            {"row": 12, "category": "特殊作业及机动叉车操作 / Công việc đặc thù & vận hành xe nâng", "content": "查看车间、仓库是否有动火、高处作业，是否严格执行制度要求。\nKiểm tra hiện trường xưởng, kho có công việc sinh nhiệt/tia lửa, làm việc trên cao và có tuân thủ quy định không.", "method": "查现场 / Kiểm tra hiện trường"},
            {"row": 13, "category": "特殊作业及机动叉车操作 / Công việc đặc thù & vận hành xe nâng", "content": "查叉车司机是否违规，并检查1台叉车刹车、灯火系统是否正常。\nKiểm tra tài xế xe nâng có vi phạm không; kiểm tra phanh và hệ thống đèn của 1 xe nâng.", "method": "查现场、查设备 / Kiểm tra hiện trường, thiết bị"},
        ],
    },
    {
        "title": "二、仓储安全检查 / Kiểm tra an toàn kho hàng",
        "items": [
            {"row": 15, "category": "安全设施 / Thiết bị an toàn", "content": "检查区域排风扇是否完好，可正常使用。\nKiểm tra quạt thông gió trong khu vực có nguyên vẹn và hoạt động bình thường không.", "method": "查设施 / Kiểm tra thiết bị"},
            {"row": 16, "category": "安全设施 / Thiết bị an toàn", "content": "化学品仓库是否配置温湿度表，是否在温湿度范围内。\nKho hóa chất có trang bị nhiệt ẩm kế; nhiệt độ và độ ẩm có trong giới hạn quy định không.", "method": "查现场 / Kiểm tra hiện trường"},
            {"row": 17, "category": "消防安全 / An toàn PCCC", "content": "检查仓库门口安全标识是否完好。\nKiểm tra biển cảnh báo an toàn ở cửa kho có nguyên vẹn không.", "method": "查现场 / Kiểm tra hiện trường"},
            {"row": 18, "category": "消防安全 / An toàn PCCC", "content": "检查照明线路、应急灯具、手动报警按钮是否完好。\nKiểm tra đường dây chiếu sáng, đèn sự cố và nút báo cháy bằng tay có hoạt động tốt không.", "method": "查现场 / Kiểm tra hiện trường"},
            {"row": 19, "category": "作业安全 / An toàn làm việc", "content": "装卸、搬运危险品是否轻装轻卸；严禁摔、碰、撞击、拖拉、倾倒、滚动。\nBốc dỡ, vận chuyển hàng nguy hiểm có thao tác nhẹ nhàng; không ném, va đập, kéo lê, làm đổ hoặc lăn.", "method": "查现场 / Kiểm tra hiện trường"},
            {"row": 20, "category": "作业安全 / An toàn làm việc", "content": "托板是否规范放置，地面是否清扫，废弃物是否当日送至废弃物仓库。\nPallet có xếp đúng quy định, nền có sạch và rác thải có được chuyển đến kho rác trong ngày không.", "method": "查现场 / Kiểm tra hiện trường"},
            {"row": 21, "category": "作业安全 / An toàn làm việc", "content": "操作工人是否有违反劳动纪律现象。\nCông nhân thao tác có vi phạm kỷ luật lao động không.", "method": "查现场 / Kiểm tra hiện trường"},
            {"row": 22, "category": "仓储管理 / Quản lý kho", "content": "危险化学品是否根据化学性质、火灾危险性分类储存。\nHóa chất nguy hiểm có được lưu trữ, phân loại theo tính chất hóa học và nguy cơ cháy nổ không.", "method": "查现场 / Kiểm tra hiện trường"},
            {"row": 23, "category": "仓储管理 / Quản lý kho", "content": "仓库现场是否悬挂安全技术说明书。\nHiện trường kho có treo Bảng dữ liệu an toàn hóa chất (MSDS/SDS) không.", "method": "查现场 / Kiểm tra hiện trường"},
        ],
    },
    {
        "title": "三、电气安全检查 / Kiểm tra an toàn điện",
        "items": [
            {"row": 25, "category": "电器、线路 / Thiết bị điện, dây dẫn", "content": "露天用电设备、配电装置应采取防雨、防雪、防雾和防尘措施。\nThiết bị điện, tủ phân phối ngoài trời phải có biện pháp che mưa, tuyết, sương mù và chống bụi.", "method": "查现场 / Kiểm tra hiện trường"},
            {"row": 26, "category": "电器、线路 / Thiết bị điện, dây dẫn", "content": "电气线路须有足够绝缘、机械强度和导电能力，禁止使用绝缘老化或失效线路。\nDây điện phải đủ cách điện, độ bền cơ học và khả năng dẫn điện; không dùng dây lão hóa hoặc mất cách điện.", "method": "查现场 / Kiểm tra hiện trường"},
        ],
    },
    {
        "title": "四、应急管理检查 / Kiểm tra quản lý ứng cấp",
        "items": [
            {"row": 28, "category": "应急预案 / Phương án ứng phó sự cố", "content": "是否针对各场所风险制定可行的专项应急预案或现场处置方案。\nCó lập phương án ứng phó sự cố chuyên đề hoặc xử lý tại chỗ khả thi cho rủi ro tại từng khu vực không.", "method": "查文件 / Kiểm tra hồ sơ"},
            {"row": 29, "category": "应急物资 / Vật tư sự cố", "content": "应急装备、设施、物资、器材及存放位置是否充足、明确并有效。\nTrang bị, thiết bị, vật tư, dụng cụ ứng phó và vị trí lưu trữ có đầy đủ, rõ ràng và đảm bảo hiệu quả không.", "method": "查现场 / Kiểm tra hiện trường"},
        ],
    },
    {
        "title": "五、安全保卫 / An toàn bảo vệ",
        "items": [
            {"row": 31, "category": "24小时值班 / Trực ban 24h", "content": "24小时应急值守人员是否明确，值班记录完善。\nNhân viên trực ban sự cố 24h có phân công rõ ràng và ghi chép đầy đủ không.", "method": "查记录 / Kiểm tra ghi chép"},
            {"row": 32, "category": "假期值班 / Trực ban lễ tết", "content": "是否落实节假日领导干部值班工作。\nCó thực hiện công tác trực ban của cán bộ lãnh đạo trong các ngày lễ tết không.", "method": "查值班表 / Kiểm tra lịch trực"},
        ],
    },
]

EXPECTED_CHECKLIST_ROWS = (
    list(range(3, 14)) +
    list(range(15, 24)) +
    list(range(25, 27)) +
    list(range(28, 30)) +
    list(range(31, 33))
)

DEPARTMENT_TRANSLATIONS = {
    "sản xuất": "生产部",
    "ban san xuat": "生产部",
    "bán hàng": "销售部",
    "ban hang": "销售部",
    "kỹ thuật phục vụ": "技术服务部",
    "ky thuat phuc vu": "技术服务部",
    "kỹ thuật": "技术部",
    "ky thuat": "技术部",
    "kho": "仓储部",
    "kho hàng": "仓储部",
    "an toàn": "安全部",
    "hse": "HSE部门",
    "bảo trì": "维修部",
    "bao tri": "维修部",
    "hành chính": "行政部",
    "hanh chinh": "行政部",
}

OFFLINE_HSE_PATTERNS = [
    (("cửa thoát hiểm", "che"), "安全出口被货物遮挡。"),
    (("lối thoát hiểm", "che"), "疏散通道被货物遮挡。"),
    (("cửa thoát hiểm", "khóa"), "安全出口被上锁。"),
    (("lối thoát hiểm", "khóa"), "安全疏散通道被上锁。"),
    (("bình chữa cháy", "che"), "灭火器被遮挡，事故发生时会延误取用。"),
    (("bình chữa cháy", "hết hạn"), "灭火器超出点检有效期限。"),
    (("thùng", "hóa chất", "đậy"), "化学品容器未密封，存在溶剂蒸气扩散和火灾爆炸风险。"),
    (("thùng", "hóa chất", "mở"), "化学品容器未加盖密封，存在挥发泄漏隐患。"),
    (("dây điện", "hở"), "电线绝缘保护层破损裸露，存在短路、火灾和触电风险。"),
    (("dây điện", "hỏng"), "电线绝缘保护层破损，存在短路、火灾和触电风险。"),
    (("móp méo",), "化学品桶凹陷变形，存在倾倒和泄漏风险。"),
    (("bụi", "vệ sinh"), "该区域灰尘较多，需要清洁。"),
    (("sắp xếp", "gọn gàng"), "物品摆放杂乱，需要重新整理。"),
    (("rác", "dọn"), "该区域散落垃圾，需要清理。"),
]

HSE_WRITING_GUIDANCE = [
    (
        ("hóa chất", "dung môi", "thùng", "can", "chai", "nắp"),
        "Tình trạng này có thể làm phát tán hơi hóa chất, gây ô nhiễm môi trường và gia tăng nguy cơ cháy, nổ.",
        "đậy kín, kiểm tra tình trạng bao bì và quản lý hóa chất theo đúng quy định",
    ),
    (
        ("bình chữa cháy", "thiết bị pccc", "tủ pccc", "pccc"),
        "Tình trạng này có thể làm chậm khả năng tiếp cận và xử lý khi xảy ra sự cố cháy.",
        "di dời vật cản và duy trì lối tiếp cận thiết bị PCCC thông thoáng",
    ),
    (
        ("thoát hiểm", "thoát nạn", "lối đi", "cửa thoát"),
        "Tình trạng này có thể cản trở quá trình lưu thông, thoát nạn và sơ tán khẩn cấp.",
        "giải phóng và duy trì lối đi, lối thoát hiểm thông thoáng",
    ),
    (
        ("dây điện", "điện", "ổ cắm", "tủ điện"),
        "Tình trạng này làm gia tăng nguy cơ chạm chập, điện giật và cháy.",
        "sửa chữa hoặc thay thế phần hư hỏng và bổ sung biện pháp bảo vệ cách điện phù hợp",
    ),
    (
        ("bụi", "bẩn", "vệ sinh", "rác"),
        "Tình trạng này ảnh hưởng đến điều kiện vệ sinh công nghiệp và môi trường làm việc.",
        "vệ sinh khu vực và duy trì tần suất làm sạch phù hợp",
    ),
    (
        ("sắp xếp", "gọn gàng", "bừa bộn", "vật tư", "hàng hóa", "5s"),
        "Tình trạng này có thể cản trở thao tác, lưu thông và làm gia tăng nguy cơ mất an toàn.",
        "sắp xếp lại vật tư, hàng hóa theo đúng vị trí quy định",
    ),
    (
        ("móp", "méo", "biến dạng", "rò rỉ"),
        "Tình trạng này làm gia tăng nguy cơ mất ổn định, đổ ngã hoặc rò rỉ.",
        "phân loại, cách ly và xử lý các bao bì hoặc thiết bị hư hỏng",
    ),
]


# =============================================================================
# Helper Utilities & Typography Functions
# =============================================================================

def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_flexible_date(raw_date: Any) -> date:
    """
    Parses date from various formats flexibly:
    - date or datetime instance
    - ISO format: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS...
    - Vietnamese / European: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    - Chinese / Japanese: YYYY/MM/DD, YYYY.MM.DD, YYYY年MM月DD日
    - Compact: YYYYMMDD
    Falls back to date.today() if invalid or None.
    """
    if isinstance(raw_date, datetime):
        return raw_date.date()
    if isinstance(raw_date, date):
        return raw_date
    if not raw_date:
        return date.today()

    s = str(raw_date).strip()
    if not s:
        return date.today()

    # Strip ISO time if present
    s = s.split("T")[0].split(" ")[0].replace("Z", "").strip()

    # Check for Chinese date format: 2026年10月21日
    m_cn = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日?$", s)
    if m_cn:
        try:
            return date(int(m_cn.group(1)), int(m_cn.group(2)), int(m_cn.group(3)))
        except ValueError:
            pass

    # Normalize delimiters / . _ to -
    # Case: DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    m_dmy = re.match(r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})$", s)
    if m_dmy:
        day, month, year = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
        try:
            return date(year, month, day)
        except ValueError:
            pass

    # Case: YYYY/MM/DD or YYYY-MM-DD or YYYY.MM.DD
    m_ymd = re.match(r"^(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})$", s)
    if m_ymd:
        year, month, day = int(m_ymd.group(1)), int(m_ymd.group(2)), int(m_ymd.group(3))
        try:
            return date(year, month, day)
        except ValueError:
            pass

    # Case: YYYYMMDD (8 digits)
    if len(s) == 8 and s.isdigit():
        try:
            return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            pass

    # Standard isoformat try
    try:
        return date.fromisoformat(s)
    except Exception:
        pass

    return date.today()


def classify_department_from_text(hint: str) -> tuple[str, str, str]:
    hint_lower = (hint or "").casefold()
    if any(k in hint_lower for k in ("kho", "chứa hàng", "pallet", "thành phẩm")):
        return "kho", "Kho hàng", "仓储部"
    elif any(k in hint_lower for k in ("bảo trì", "cơ điện", "sửa chữa", "máy móc", "bảo dưỡng")):
        return "bao-tri", "Bảo trì", "维修部"
    elif any(k in hint_lower for k in ("kỹ thuật", "thí nghiệm", "lab", "nghiên cứu", "phòng mẫu", "pha màu", "pha mẫu")):
        return "ky-thuat", "Kỹ thuật", "技术部"
    elif any(k in hint_lower for k in ("bán hàng", "kinh doanh", "thị trường", "tiếp thị")):
        return "ban-hang", "Bán hàng", "销售部"
    elif any(k in hint_lower for k in ("hành chính", "văn phòng", "nhà ăn", "bảo vệ", "cổng")):
        return "hanh-chinh", "Hành chính", "行政部"
    else:
        return "san-xuat", "Sản xuất", "生产部"


def professionalize_hse(text: str, context: str = "") -> list[str]:
    """
    Soạn thảo biên bản HSE chuyên nghiệp bằng AI (3 phương án: Ngắn gọn, Tập trung Rủi ro, Hành động CAPA).
    Tuyệt đối không dùng template nối chuỗi thô thiển hay mock string.
    """
    raw = normalize_space(text)
    if not raw:
        raise ValueError("Hãy nhập nội dung ghi nhận trước khi tạo câu chuyên nghiệp.")

    from core.ai_text_engine import AITextEngine
    creds = AITextEngine.get_ai_credentials()
    if not creds.get("api_key"):
        raise ValueError(
            "Chưa cấu hình API Key. Vui lòng vào 'Cài Đặt Quản Trị' -> 'Cấu Hình API Key & Trí Tuệ Nhân Tạo' "
            "để nhập API Key (Google Gemini, OpenAI hoặc DeepSeek) cho tính năng Viết Chuyên Nghiệp EHS!"
        )

    system_prompt = (
        "Bạn là Chuyên gia Soạn thảo Biên bản An toàn EHS & PCCC nhà máy sản xuất chuyên nghiệp.\n"
        "Nhiệm vụ: Dựa vào (1) Ý ghi nhận hiện trường của người dùng + (2) Tiêu chuẩn/ngữ cảnh kiểm tra an toàn PCCC/EHS,\n"
        "hãy soạn thảo lại thành 3 phương án câu văn phong kỹ thuật EHS sắc bén, chuẩn mực theo đúng quy chuẩn an toàn:\n"
        "- Phương án 1 (Ngắn gọn & Trực tiếp): Mô tả chính xác hiện trạng lỗi và điểm không phù hợp tại hiện trường.\n"
        "- Phương án 2 (Phân tích Rủi ro & Vi phạm): Nêu rõ hiện trạng lỗi -> Phân tích nguy cơ mất an toàn, rủi ro cháy nổ hoặc vi phạm quy chuẩn PCCC/EHS.\n"
        "- Phương án 3 (Hành động Khắc phục CAPA): Nêu rõ yêu cầu biện pháp khắc phục (CAPA) cụ thể và chỉ đạo bộ phận liên quan chấn chỉnh dứt điểm.\n\n"
        "YÊU CẦU ĐỊNH DẠNG BẮT BUỘC:\n"
        "Chỉ trả về DUY NHẤT một mảng JSON 3 phần tử chuỗi tiếng Việt dạng [\"Phương án 1...\", \"Phương án 2...\", \"Phương án 3...\"], tuyệt đối không giải thích thêm."
    )
    user_prompt = (
        f"GHI NHẬN HIỆN TRƯỜNG: {raw}\n"
        f"TIÊU CHUẨN KIỂM TRA / HẠNG MỤC: {context or 'Kiểm tra hiện trường An toàn PCCC & EHS'}"
    )

    try:
        ai_res = AITextEngine.call_universal_chat(
            messages=[{"role": "user", "content": user_prompt}],
            system_prompt=system_prompt,
            temperature=0.2,
            timeout=25
        )
        m_json = re.search(r"\[[\s\S]*\]", ai_res)
        if m_json:
            opts = json.loads(m_json.group(0))
            if isinstance(opts, list) and len(opts) >= 3 and all(isinstance(x, str) for x in opts):
                return [normalize_space(opts[0]), normalize_space(opts[1]), normalize_space(opts[2])]
            elif isinstance(opts, list) and len(opts) > 0:
                cleaned_opts = [normalize_space(x) for x in opts if isinstance(x, str) and x.strip()]
                if cleaned_opts:
                    while len(cleaned_opts) < 3:
                        cleaned_opts.append(cleaned_opts[-1])
                    return cleaned_opts[:3]
    except Exception as exc:
        raise RuntimeError(f"Lỗi gọi AI viết chuyên nghiệp: {exc}")

    raise RuntimeError("AI không trả về định dạng 3 phương án hợp lệ. Vui lòng thử lại!")


def translate_vi_to_zh(text: str, kind: str = "text") -> str:
    """
    Dịch thuật 2 chiều chuẩn xác giữa Tiếng Việt và Tiếng Trung chuyên ngành EHS.
    Tuyệt đối không giữ lại tiền tố '问题: 现场问题:' hoặc trộn lẫn ngôn ngữ.
    """
    clean_text = normalize_space(text).strip()
    if not clean_text:
        return ""

    if kind == "department":
        key = clean_text.casefold()
        if key in DEPARTMENT_TRANSLATIONS:
            return DEPARTMENT_TRANSLATIONS[key]

    # Kiểm tra chiều dịch: Nếu văn bản phần lớn là chữ Hán -> Dịch sang Tiếng Việt
    is_chinese_input = bool(re.search(r"[\u4e00-\u9fff]", clean_text)) and len(re.findall(r"[\u4e00-\u9fff]", clean_text)) > len(clean_text) * 0.3

    # 1. Thử dùng AI LLM (Gemini, OpenAI, DeepSeek) để dịch thuật chuẩn chuyên ngành
    try:
        from core.ai_text_engine import AITextEngine
        creds = AITextEngine.get_ai_credentials()
        if creds.get("api_key"):
            if is_chinese_input:
                sys_prompt = "Bạn là dịch giả chuyên nghiệp. Hãy dịch đoạn văn bản sau sang TIẾNG VIỆT chuẩn kỹ thuật EHS/PCCC nhà máy. Chỉ trả về bản dịch tiếng Việt thuần túy, TUYỆT ĐỐI KHÔNG thêm bất kỳ tiền tố hay giải thích nào."
            else:
                sys_prompt = "Bạn là dịch giả chuyên nghiệp. Hãy dịch đoạn văn bản sau sang TIẾNG TRUNG GIẢN THỂ (简体中文) chuẩn thuật ngữ an toàn sản xuất EHS/PCCC. Chỉ trả về bản dịch tiếng Trung thuần túy, TUYỆT ĐỐI KHÔNG thêm tiền tố '问题:' hay '现场问题:' hay '隐患:'."

            res = AITextEngine.call_universal_chat(
                messages=[{"role": "user", "content": clean_text}],
                system_prompt=sys_prompt,
                temperature=0.1,
                timeout=20
            )
            if res and res.strip():
                cleaned = re.sub(r"^(?:问题|现场问题|隐患|整改要求|整改措施)\s*[:：]\s*", "", res.strip())
                # Loại bỏ hoàn toàn tiền tố lặp lại
                cleaned = re.sub(r"^(?:问题|现场问题|隐患)\s*[:：]\s*", "", cleaned)
                return cleaned
    except Exception as e:
        logger.warning(f"Lỗi gọi AI dịch ({e}), chuyển sang Google Translate...")

    # 2. Dịch qua Google Translate API trực tuyến
    try:
        sl = "zh-CN" if is_chinese_input else "vi"
        tl = "vi" if is_chinese_input else "zh-CN"
        query = urllib.parse.urlencode({
            "client": "gtx",
            "sl": sl,
            "tl": tl,
            "dt": "t",
            "q": clean_text,
        })
        request = urllib.request.Request(
            f"https://translate.googleapis.com/translate_a/single?{query}",
            headers={"User-Agent": "Mozilla/5.0 HSE-Report-App/2.0"},
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        translated = "".join(part[0] for part in data[0] if part and part[0])
        if translated and translated.strip():
            cleaned = re.sub(r"^(?:问题|现场问题|隐患|整改要求)\s*[:：]\s*", "", translated.strip())
            return cleaned
    except Exception as e:
        logger.warning(f"Lỗi Google Translate: {e}")

    # Báo lỗi rõ ràng chứ không ghép chuỗi giả!
    raise ValueError(f"Không thể kết nối dịch vụ dịch thuật để dịch: '{clean_text[:40]}...'. Vui lòng kiểm tra lại kết nối mạng hoặc cấu hình API Key trong Cài đặt Hệ thống!")


def analyze_image_ai(
    image_data: str,
    hint: str = "",
    context: str = "",
    model: str = "gemini-2.5-flash"
) -> dict[str, str]:
    """
    Phân tích ảnh hiện trường vi phạm bằng Multimodal Vision AI thực thụ (Google Gemini / OpenAI GPT-4o Vision).
    TUYỆT ĐỐI KHÔNG DÙNG MOCK KEYWORD HAY CHUỖI GHÉP GIẢ.
    """
    if not image_data or not image_data.strip():
        raise ValueError("Vui lòng tải ảnh hiện trường vi phạm lên trước khi bấm Đọc ảnh & Tự soạn!")

    from core.ai_text_engine import AITextEngine
    creds = AITextEngine.get_ai_credentials()
    if not creds.get("api_key"):
        raise ValueError(
            "Hệ thống chưa được cấu hình API Key. "
            "Vui lòng vào 'Cài Đặt Quản Trị' -> 'Cấu Hình API Key & Trí Tuệ Nhân Tạo' "
            "để nhập API Key (DeepSeek AI, Google Gemini hoặc OpenAI)!"
        )

    system_prompt = (
        "Bạn là Chuyên gia Kiểm toán An toàn EHS & PCCC nhà máy hàng đầu thế giới.\n"
        "Nhiệm vụ: Quan sát kỹ bức ảnh hiện trường vi phạm được cung cấp, kết hợp với ngữ cảnh hạng mục kiểm tra.\n"
        "Suy luận nguyên nhân gốc rễ, chỉ ra điểm không phù hợp (Non-conformity), mức độ rủi ro theo tiêu chuẩn an toàn PCCC/EHS và hành động khắc phục (CAPA).\n\n"
        "YÊU CẦU ĐỊNH DẠNG ĐẦU RA:\n"
        "Trả về DUY NHẤT một chuỗi JSON hợp lệ không có markdown bọc ngoài, đúng cấu trúc sau:\n"
        "{\n"
        '  "departmentKey": "san-xuat" hoặc "kho-hang" hoặc "bao-tri" hoặc "ky-thuat" hoặc "hanh-chinh",\n'
        '  "departmentVi": "Sản xuất | Kho hàng | Bảo trì | Kỹ thuật | Hành chính",\n'
        '  "departmentZh": "生产部 | 仓储部 | 维修部 | 技术部 | 行政部",\n'
        '  "issueVi": "Mô tả vi phạm hiện trường và kiến nghị khắc phục bằng tiếng Việt kỹ thuật chuyên nghiệp, sắc bén.",\n'
        '  "issueZh": "现场不符合项及整改要求（规范简体中文，严禁包含任何越南文字符，不要加问题:或现场问题:前缀）",\n'
        '  "suggestion": "Biện pháp khắc phục ngắn hạn và dài hạn"\n'
        "}"
    )

    user_prompt = (
        f"HẠNG MỤC KIỂM TRA:\n"
        f"- Ngữ cảnh / Tiêu chuẩn kiểm tra: {context or 'Kiểm tra hiện trường An toàn PCCC & EHS'}\n"
        f"- Ghi chú sơ bộ của kiểm tra viên: {hint or 'Không có ghi chú trước'}\n\n"
        f"Hãy quan sát bức ảnh hiện trường vi phạm trên và trích xuất JSON theo đúng quy định."
    )

    # Gọi Vision AI thực tế
    raw_ai_text = AITextEngine.call_vision_api(
        image_data=image_data,
        prompt=user_prompt,
        system_prompt=system_prompt,
        model=model or creds.get("model") or "gemini-2.5-flash"
    )

    # Bóc tách JSON từ phản hồi của AI
    cleaned_text = re.sub(r"^```(?:json)?\s*", "", raw_ai_text.strip(), flags=re.IGNORECASE)
    cleaned_text = re.sub(r"\s*```$", "", cleaned_text)
    m_json = re.search(r"\{[\s\S]*\}", cleaned_text)
    if not m_json:
        raise RuntimeError(f"AI không trả về định dạng JSON hợp lệ: {raw_ai_text[:200]}")

    try:
        parsed = json.loads(m_json.group(0))
    except Exception as exc:
        raise RuntimeError(f"Không thể giải mã JSON từ Vision AI: {exc}\nNội dung AI: {raw_ai_text[:200]}")

    # Chuẩn hóa dữ liệu trả về
    dept_key = parsed.get("departmentKey") or "san-xuat"
    if dept_key not in ("san-xuat", "kho-hang", "bao-tri", "ky-thuat", "hanh-chinh"):
        dept_key, dept_vi_auto, dept_zh_auto = classify_department_from_text(parsed.get("departmentVi") or hint)
    else:
        dept_vi_auto = DEPARTMENTS[dept_key]["vi"]
        dept_zh_auto = DEPARTMENTS[dept_key]["zh"]

    issue_vi = normalize_space(str(parsed.get("issueVi") or "")).strip()
    issue_zh = normalize_space(str(parsed.get("issueZh") or "")).strip()

    # Dọn dẹp tiền tố thừa trong tiếng Trung nếu AI có thêm vào
    issue_zh = re.sub(r"^(?:问题|现场问题|隐患|整改要求)\s*[:：]\s*", "", issue_zh)

    # Đảm bảo nếu issue_zh rỗng thì tự động dịch chuẩn xác từ issue_vi
    if not issue_zh and issue_vi:
        issue_zh = translate_vi_to_zh(issue_vi)

    suggestion = normalize_space(str(parsed.get("suggestion") or "")).strip()

    return {
        "departmentKey": dept_key,
        "departmentVi": parsed.get("departmentVi") or dept_vi_auto,
        "departmentZh": parsed.get("departmentZh") or dept_zh_auto,
        "issueVi": issue_vi,
        "issueZh": issue_zh,
        "suggestion": suggestion
    }


# =============================================================================
# OOXML Formatting Utilities
# =============================================================================

def add_run(
    paragraph,
    text: str,
    *,
    size: float = 10.5,
    bold: bool = False,
    font: str = "Times New Roman",
    color: RGBColor | None = None,
    east_asia: str | None = None,
):
    run = paragraph.add_run(text)
    run.bold = bold
    run.font.name = font
    run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:ascii"), font)
    rfonts.set(qn("w:hAnsi"), font)
    rfonts.set(qn("w:cs"), font)
    ea = east_asia
    if not ea:
        if any("\u4e00" <= char <= "\u9fff" for char in text):
            ea = "Microsoft YaHei"
        else:
            ea = font
    rfonts.set(qn("w:eastAsia"), ea)
    return run


def clear_paragraph(paragraph) -> None:
    p = paragraph._p
    for child in list(p):
        if child.tag.endswith(("r", "hyperlink", "fldSimple")):
            p.remove(child)


def set_paragraph_layout(
    p,
    *,
    space_before_pt: float = 0,
    space_after_pt: float = 0,
    line_spacing: float = 1.0,
) -> None:
    pPr = p._p.get_or_add_pPr()
    stg = pPr.find(qn("w:snapToGrid"))
    if stg is None:
        stg = OxmlElement("w:snapToGrid")
        pPr.append(stg)
    stg.set(qn("w:val"), "0")

    sp = pPr.find(qn("w:spacing"))
    if sp is None:
        sp = OxmlElement("w:spacing")
        pPr.append(sp)
    sp.set(qn("w:before"), str(int(space_before_pt * 20)))
    sp.set(qn("w:after"), str(int(space_after_pt * 20)))
    sp.set(qn("w:line"), str(int(line_spacing * 240)))
    sp.set(qn("w:lineRule"), "auto")


def set_cell_margins(cell, top: int = 80, start: int = 90, bottom: int = 80, end: int = 90) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for name, value in (("top", top), ("left", start), ("bottom", bottom), ("right", end)):
        node = OxmlElement(f"w:{name}")
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def set_table_geometry(
    table,
    widths: list[int],
    *,
    indent: int = 0,
    borders: bool = True,
    border_color: str = "D3D3D3",
    border_sz: str = "4",
) -> None:
    table.autofit = False
    table.alignment = WD_ALIGN_PARAGRAPH.LEFT
    tblPr = table._tbl.tblPr

    tblW = tblPr.find(qn("w:tblW"))
    if tblW is None:
        tblW = OxmlElement("w:tblW")
        tblPr.append(tblW)
    tblW.set(qn("w:type"), "dxa")
    tblW.set(qn("w:w"), str(sum(widths)))

    tblInd = tblPr.find(qn("w:tblInd"))
    if tblInd is None:
        tblInd = OxmlElement("w:tblInd")
        tblPr.append(tblInd)
    tblInd.set(qn("w:w"), str(indent))
    tblInd.set(qn("w:type"), "dxa")

    tblBorders = tblPr.find(qn("w:tblBorders"))
    if tblBorders is not None:
        tblPr.remove(tblBorders)
    node = OxmlElement("w:tblBorders")
    for border_name in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = OxmlElement(f"w:{border_name}")
        if borders:
            border.set(qn("w:val"), "single")
            border.set(qn("w:sz"), border_sz)
            border.set(qn("w:space"), "0")
            border.set(qn("w:color"), border_color)
        else:
            border.set(qn("w:val"), "none")
        node.append(border)
    tblPr.append(node)

    for row in table.rows:
        for index, width in enumerate(widths):
            if index < len(row.cells):
                cell = row.cells[index]
                cell.width = Inches(width / 1440.0)
                tcW = cell._tc.get_or_add_tcPr().find(qn("w:tcW"))
                if tcW is None:
                    tcW = OxmlElement("w:tcW")
                    cell._tc.get_or_add_tcPr().append(tcW)
                tcW.set(qn("w:type"), "dxa")
                tcW.set(qn("w:w"), str(width))
                set_cell_margins(cell)


def add_bottom_border(paragraph, color: str = "004B97", size: str = "24") -> None:
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = pPr.find(qn("w:pBdr"))
    if pBdr is None:
        pBdr = OxmlElement("w:pBdr")
        pPr.append(pBdr)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), color)
    pBdr.append(bottom)


def add_page_field(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    p = paragraph._p
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    r = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "19")  # 9.5 pt
    rPr.append(sz)
    r.append(rPr)
    t = OxmlElement("w:t")
    t.text = "1"
    r.append(t)
    fld.append(r)
    p.append(fld)


# =============================================================================
# Image Processing & Media Helpers
# =============================================================================

def fit_image(
    data_url: Optional[str],
    max_width: float = 3.38,
    max_height: float = 4.25,
    drive_url: Optional[str] = None
) -> tuple[Optional[io.BytesIO], float, float]:
    """
    Fits base64 or remote Google Drive image proportionally within max bounding box using Lanczos resampling.
    Auto-corrects EXIF orientation and outputs high-quality JPEG (90%).
    Null-safe: Never raises ValueError, returns (None, 0.0, 0.0) if missing or invalid.
    """
    raw = None

    if data_url and isinstance(data_url, str) and data_url.strip():
        try:
            if "," in data_url:
                _, encoded = data_url.split(",", 1)
            else:
                encoded = data_url.strip()

            clean_encoded = re.sub(r"\s+", "", encoded)
            if clean_encoded:
                raw = base64.b64decode(clean_encoded)
                if len(raw) == 0 or len(raw) > 30 * 1024 * 1024:
                    raw = None
        except Exception:
            raw = None

    # Fallback to fetching from Google Drive if base64 is missing
    if not raw and drive_url and isinstance(drive_url, str) and drive_url.startswith("http"):
        try:
            import requests
            req_url = drive_url
            if "/file/d/" in req_url:
                f_id = req_url.split("/file/d/")[1].split("/")[0]
                req_url = f"https://drive.google.com/uc?export=view&id={f_id}"
            resp = requests.get(req_url, timeout=2.0)
            if resp.ok and len(resp.content) > 100:
                raw = resp.content
        except Exception as drive_err:
            logger.warning(f"Failed to fetch image from drive_url {drive_url}: {drive_err}")
            raw = None

    if not raw:
        return None, 0.0, 0.0

    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=90, optimize=True)
        out.seek(0)
        width_px, height_px = img.size
        aspect = width_px / max(1, height_px)
        max_aspect = max_width / max_height
        if aspect >= max_aspect:
            w_in = max_width
            h_in = max_width / aspect
        else:
            h_in = max_height
            w_in = max_height * aspect
        return out, w_in, h_in
    except Exception as exc:
        logger.warning(f"fit_image failed safely: {exc}")
        return None, 0.0, 0.0


def extract_cell_image_base64(cell, doc: Document) -> str:
    """Extract embedded DrawingML or VML image from a table cell to Base64 Data URL."""
    r_id = None
    try:
        blips = cell._element.xpath(".//a:blip/@r:embed")
        if blips:
            r_id = str(blips[0])
    except Exception:
        pass

    if not r_id:
        for node in cell._element.iter():
            for key, val in node.attrib.items():
                if key.endswith("embed") or key.endswith("id"):
                    if val in doc.part.related_parts:
                        r_id = val
                        break
            if r_id:
                break

    if not r_id or r_id not in doc.part.related_parts:
        return ""

    try:
        img_part = doc.part.related_parts[r_id]
        blob = img_part.blob
        content_type = getattr(img_part, "content_type", "image/jpeg")
        b64_str = base64.b64encode(blob).decode("ascii")
        return f"data:{content_type};base64,{b64_str}"
    except Exception:
        return ""


# =============================================================================
# Document Transformation & Cleanup
# =============================================================================

def strip_original_findings(doc: Document) -> None:
    """
    Strips legacy findings paragraphs and tables while preserving Table 0,
    the signature lines, and the section properties (<w:sectPr>).
    """
    for tbl in list(doc.tables[1:]):
        parent = tbl._tbl.getparent()
        if parent is not None:
            parent.remove(tbl._tbl)

    body = doc._element.body
    children = list(body)
    start = None
    for index, child in enumerate(children):
        if child.tag != qn("w:p"):
            continue
        text = "".join(node.text or "" for node in child.iter(qn("w:t")))
        if "越南展" in text and "HSE" in text:
            start = index
            break

    if start is None and doc.tables:
        first_tbl = doc.tables[0]._tbl
        found_table = False
        p_count = 0
        for index, child in enumerate(children):
            if child == first_tbl:
                found_table = True
                continue
            if found_table:
                if child.tag == qn("w:p"):
                    p_count += 1
                    if p_count > 3:
                        start = index
                        break
                elif child.tag == qn("w:tbl"):
                    start = index
                    break

    if start is not None:
        for child in children[start:]:
            if child.tag != qn("w:sectPr"):
                body.remove(child)


def apply_metadata(doc: Document, metadata: dict[str, Any], report_type: str = "inspection") -> None:
    dt = parse_flexible_date(metadata.get("date"))

    year_str = str(dt.year)
    month_str = f"{dt.month:02d}"
    day_str = f"{dt.day:02d}"
    display_date = f"{day_str}/{month_str}/{year_str}"

    inspectors = normalize_space(metadata.get("inspectors")) or "Ban HSE"
    is_imp = (report_type == "improvement")

    for p in doc.paragraphs:
        txt = p.text
        if any(k in txt for k in ("检查日期", "Ngày kiểm tra", "检查时间", "Thời gian kiểm tra")):
            clear_paragraph(p)
            label = "复查日期/ Ngày phục tra" if is_imp else "检查日期/ Ngày kiểm tra"
            add_run(p, f"{label}：{year_str}年{month_str}月{day_str}日 / {display_date}", size=10.5, bold=True)
        elif any(k in txt for k in ("检查人员", "Người kiểm tra", "复查人员", "Người phục tra")):
            clear_paragraph(p)
            label = "复查人员/ Người phục tra" if is_imp else "检查人员/ Người kiểm tra"
            add_run(p, f"{label}：{inspectors}", size=10.5, bold=True)
        elif "月度安全、环保、消防检查记录" in txt:
            clear_paragraph(p)
            if is_imp:
                add_run(p, f"{year_str}年{month_str}月度安全、环保、消防整改复查记录", size=13, bold=True, font="Microsoft YaHei")
            else:
                add_run(p, f"{year_str}年{month_str}月度安全、环保、消防检查记录", size=13, bold=True, font="Microsoft YaHei")
        elif "NHẬT KÝ KIỂM TRA AN TOÀN-MÔI TRƯỜNG-PHÒNG CHÁY" in txt:
            clear_paragraph(p)
            if is_imp:
                add_run(p, "BÁO CÁO PHỤC TRA CẢI THIỆN AN TOÀN - MÔI TRƯỜNG - PCCC", size=12, bold=True, font="Times New Roman")
            else:
                add_run(p, "NHẬT KÝ KIỂM TRA AN TOÀN-MÔI TRƯỜNG-PHÒNG CHÁY", size=12, bold=True, font="Times New Roman")
        elif "THÁNG " in txt and "/" in txt:
            clear_paragraph(p)
            if is_imp:
                add_run(p, f"THÁNG {month_str}/{year_str} (PHỤC TRA CẢI THIỆN)", size=12, bold=True, font="Times New Roman")
            else:
                add_run(p, f"THÁNG {month_str}/{year_str}", size=12, bold=True, font="Times New Roman")


def apply_checklist(
    doc: Document,
    checklist: list[dict[str, Any]],
    report_type: str = "inspection",
    date_str: str = ""
) -> None:
    if not doc.tables:
        raise RuntimeError("File mẫu không có bảng checklist.")
    table = doc.tables[0]
    by_row = {int(item["row"]): item for item in checklist if str(item.get("row", "")).isdigit()}
    recheck_date = date_str or date.today().isoformat()

    for section in CHECKLIST_SECTIONS:
        for template_item in section["items"]:
            row_index = template_item["row"]
            result = by_row.get(row_index, {"status": "pass"})
            status = result.get("status", "pass")
            row = table.rows[row_index]
            c4 = row.cells[4]
            c5 = row.cells[5]

            for p in c4.paragraphs:
                clear_paragraph(p)
            for p in c5.paragraphs:
                clear_paragraph(p)

            if status == "pass":
                c4.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                p4 = c4.paragraphs[0]
                p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
                set_paragraph_layout(p4, space_before_pt=0, space_after_pt=0, line_spacing=1.0)
                add_run(p4, "√", size=11, bold=True, font="Times New Roman")
            elif status == "fail":
                issue_vi = normalize_space(result.get("issueVi", ""))
                issue_zh = normalize_space(result.get("issueZh", ""))
                if not issue_vi and not issue_zh:
                    issue_vi = "Chưa đạt tiêu chuẩn an toàn EHS (Cần khắc phục)"
                    issue_zh = "未达到EHS安全标准 (需整改)"
                elif not issue_zh:
                    try:
                        issue_zh = translate_vi_to_zh(issue_vi)
                    except Exception:
                        issue_zh = f"整改问题: {issue_vi}"
                elif not issue_vi:
                    try:
                        issue_vi = translate_vi_to_zh(issue_zh, kind="text")
                    except Exception:
                        issue_vi = f"Vấn đề an toàn: {issue_zh}"
                clean_issue_zh = re.sub(r"^问题[:：]\s*", "", issue_zh, flags=re.IGNORECASE).strip()
                clean_issue_vi = re.sub(r"^Vấn đề[:：]\s*", "", issue_vi, flags=re.IGNORECASE).strip()
                is_improved = bool(result.get("improved", False))

                if report_type == "improvement":
                    c4.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                    p4 = c4.paragraphs[0]
                    p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    set_paragraph_layout(p4, space_before_pt=0, space_after_pt=0, line_spacing=1.0)
                    if is_improved:
                        recheck_block = f"复查:\n{recheck_date}\n已改善\nKiểm tra:\n{recheck_date}\nCải thiện"
                        color = RGBColor(19, 138, 91)
                    else:
                        recheck_block = f"复查:\n{recheck_date}\n未改善\nKiểm tra:\n{recheck_date}\nChưa cải thiện"
                        color = RGBColor(200, 0, 0)
                    add_run(p4, recheck_block, size=9.0, bold=False, font="Times New Roman", color=color)

                c5.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                p5 = c5.paragraphs[0]
                p5.alignment = WD_ALIGN_PARAGRAPH.LEFT
                set_paragraph_layout(p5, space_before_pt=0, space_after_pt=2, line_spacing=1.1)
                if clean_issue_zh:
                    add_run(p5, clean_issue_zh + "\n", size=8.7, font="Microsoft YaHei")
                if clean_issue_vi:
                    add_run(p5, clean_issue_vi, size=8.7, font="Times New Roman")
            else:
                raise ValueError(f"Trạng thái checklist '{status}' tại dòng {row_index} không hợp lệ.")


def add_issue_header(
    doc: Document,
    inspection_date: str,
    report_type: str = "inspection",
    logo_path: Path | None = None
) -> None:
    table = doc.add_table(rows=1, cols=3)
    set_table_geometry(table, [900, 7600, 2250], borders=False)
    cells = table.rows[0].cells

    # Column 0: Logo
    if logo_path and logo_path.exists():
        p_logo = cells[0].paragraphs[0]
        p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_logo.add_run().add_picture(str(logo_path), width=Inches(0.65))

    # Column 1: Title
    title = cells[1].paragraphs[0]
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_paragraph_layout(title, space_before_pt=2, space_after_pt=0, line_spacing=1.0)
    header_title = "越南展辰 HSE 办整改复查报告" if report_type == "improvement" else "越南展辰 HSE 办巡厂报告"
    add_run(title, header_title, size=13, bold=True, font="Microsoft YaHei")

    # Column 2: Date
    date_p = cells[2].paragraphs[0]
    date_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_paragraph_layout(date_p, space_before_pt=3, space_after_pt=0, line_spacing=1.0)
    add_run(date_p, inspection_date, size=11, font="Times New Roman")

    # Signature Navy bottom line
    line = doc.add_paragraph()
    line.paragraph_format.space_before = Pt(0)
    line.paragraph_format.space_after = Pt(8.5)
    add_bottom_border(line, color="174EA6", size="18")


def populate_finding_row(
    row,
    finding: dict[str, Any],
    report_type: str = "inspection",
    date_str: str = ""
) -> None:
    department_vi = normalize_space(finding.get("departmentVi")) or "Sản xuất"
    department_zh = normalize_space(finding.get("departmentZh")) or "生产部"
    issue_vi = normalize_space(finding.get("issueVi")) or "Ghi nhận vi phạm tại hiện trường."
    issue_zh = normalize_space(finding.get("issueZh")) or "未记录问题"

    clean_issue_zh = re.sub(r"^问题[:：]\s*", "", issue_zh).strip()
    clean_issue_vi = re.sub(r"^Vấn đề[:：]\s*", "", issue_vi, flags=re.IGNORECASE).strip()
    is_improved = bool(finding.get("improved", False))

    trPr = row._tr.get_or_add_trPr()
    if trPr.find(qn("w:cantSplit")) is None:
        trPr.append(OxmlElement("w:cantSplit"))
    trHeight = trPr.find(qn("w:trHeight"))
    if trHeight is None:
        trHeight = OxmlElement("w:trHeight")
        trPr.append(trHeight)
    trHeight.set(qn("w:val"), "6150")
    trHeight.set(qn("w:hRule"), "exact")

    left, right = row.cells
    left.vertical_alignment = WD_ALIGN_VERTICAL.TOP
    right.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    set_cell_margins(left, top=90, start=100, bottom=90, end=100)
    set_cell_margins(right, top=15, start=15, bottom=15, end=15)

    # Left cell paragraphs
    p0 = left.paragraphs[0]
    set_paragraph_layout(p0, space_before_pt=0, space_after_pt=4, line_spacing=1.1)
    add_run(p0, "负责部门: ", size=10.5, bold=True, font="Microsoft YaHei")
    add_run(p0, department_zh, size=10.5, font="Microsoft YaHei")

    p1 = left.add_paragraph()
    set_paragraph_layout(p1, space_before_pt=0, space_after_pt=5, line_spacing=1.15)
    add_run(p1, "问题: ", size=10.5, bold=True, font="Microsoft YaHei")
    add_run(p1, clean_issue_zh, size=10.5, font="Microsoft YaHei")

    p2 = left.add_paragraph()
    set_paragraph_layout(p2, space_before_pt=0, space_after_pt=4, line_spacing=1.1)
    add_run(p2, "Bộ phận: ", size=10.5, bold=True, font="Times New Roman")
    add_run(p2, department_vi, size=10.5, font="Times New Roman")

    p3 = left.add_paragraph()
    set_paragraph_layout(p3, space_before_pt=0, space_after_pt=2, line_spacing=1.15)
    add_run(p3, "Vấn đề: ", size=10.5, bold=True, font="Times New Roman")
    add_run(p3, clean_issue_vi, size=10.5, font="Times New Roman")

    if report_type == "improvement":
        p_recheck_zh = left.add_paragraph()
        set_paragraph_layout(p_recheck_zh, space_before_pt=4, space_after_pt=2, line_spacing=1.1)
        status_zh = "已整改" if is_improved else "未整改"
        color_zh = RGBColor(19, 138, 91) if is_improved else RGBColor(199, 55, 55)
        add_run(p_recheck_zh, f"复查：{date_str}-{status_zh}", size=10.5, bold=True, font="Microsoft YaHei", color=color_zh)

        p_recheck_vi = left.add_paragraph()
        set_paragraph_layout(p_recheck_vi, space_before_pt=0, space_after_pt=0, line_spacing=1.1)
        status_vi = "Đã cải thiện" if is_improved else "Chưa cải thiện"
        color_vi = RGBColor(19, 138, 91) if is_improved else RGBColor(199, 55, 55)
        add_run(p_recheck_vi, f"Kiểm tra: {date_str}-{status_vi}", size=10.5, bold=True, font="Times New Roman", color=color_vi)

    # Right cell image
    image_data = str(finding.get("imageData") or "")
    image_after = str(finding.get("imageAfterData") or "")
    if report_type == "improvement" and is_improved and image_after:
        target_img = image_after
        target_drive_url = str(finding.get("afterDriveDirectUrl") or finding.get("afterDriveViewUrl") or "")
    else:
        target_img = image_data
        target_drive_url = str(finding.get("driveDirectUrl") or finding.get("driveViewUrl") or "")

    stream, w_in, h_in = fit_image(target_img, max_width=3.38, max_height=4.25, drive_url=target_drive_url)
    p_img = right.paragraphs[0]
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if stream:
        try:
            set_paragraph_layout(p_img, space_before_pt=0, space_after_pt=0, line_spacing=1.0)
            p_img.add_run().add_picture(stream, width=Inches(w_in), height=Inches(h_in))
        except Exception as pic_err:
            logger.warning(f"Failed to add picture to cell: {pic_err}")
            set_paragraph_layout(p_img, space_before_pt=30, space_after_pt=0, line_spacing=1.2)
            run = p_img.add_run("(Không có ảnh / 无图片)")
            run.font.italic = True
            run.font.color.rgb = RGBColor(140, 140, 140)
            run.font.name = "Times New Roman"
            run.font.size = Pt(10.5)
    else:
        set_paragraph_layout(p_img, space_before_pt=30, space_after_pt=0, line_spacing=1.2)
        run = p_img.add_run("(Không có ảnh / 无图片)")
        run.font.italic = True
        run.font.color.rgb = RGBColor(140, 140, 140)
        run.font.name = "Times New Roman"
        run.font.size = Pt(10.5)


def format_separator_row(row) -> None:
    trPr = row._tr.get_or_add_trPr()
    if trPr.find(qn("w:cantSplit")) is None:
        trPr.append(OxmlElement("w:cantSplit"))
    trHeight = trPr.find(qn("w:trHeight"))
    if trHeight is None:
        trHeight = OxmlElement("w:trHeight")
        trPr.append(trHeight)
    trHeight.set(qn("w:val"), "700")
    trHeight.set(qn("w:hRule"), "exact")

    for cell in row.cells:
        p = cell.paragraphs[0]
        clear_paragraph(p)
        set_paragraph_layout(p, space_before_pt=0, space_after_pt=0, line_spacing=1.0)
        pPr = p._p.get_or_add_pPr()
        rPr = OxmlElement("w:rPr")
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), "8")  # 4 pt font
        rPr.append(sz)
        pPr.append(rPr)
        set_cell_margins(cell, top=0, start=0, bottom=0, end=0)


# =============================================================================
# Document Builder & Exporter (2 items / page on A4)
# =============================================================================

def build_docx(
    payload: dict[str, Any],
    template_path: Optional[Path] = None,
    logo_path: Optional[Path] = None,
) -> bytes:
    tpl_path = template_path or get_template_path()
    if not tpl_path.exists():
        raise RuntimeError(f"Thiếu file mẫu Word: {tpl_path}")
    lg_path = logo_path or get_logo_path()

    metadata = payload.get("metadata") or {}
    checklist = payload.get("checklist") or []
    findings = payload.get("findings") or []
    report_type = payload.get("reportType") or payload.get("mode") or "inspection"
    d_obj = parse_flexible_date(metadata.get("date"))
    inspection_date = d_obj.strftime("%Y-%m-%d")

    doc = Document(str(tpl_path))
    apply_metadata(doc, metadata, report_type=report_type)
    apply_checklist(doc, checklist, report_type=report_type, date_str=inspection_date)
    strip_original_findings(doc)

    # Configure Section 0 (Letter Checklist Section)
    checklist_sec = doc.sections[-1]
    checklist_sec.page_width = Inches(8.5)
    checklist_sec.page_height = Inches(11.0)
    checklist_sec.left_margin = Inches(0.50)
    checklist_sec.right_margin = Inches(0.50)
    checklist_sec.top_margin = Inches(0.56)
    checklist_sec.bottom_margin = Inches(0.50)

    # Append Section 1 (Strict A4 Findings Section)
    issue_section = doc.add_section(WD_SECTION.NEW_PAGE)
    issue_section.page_width = Cm(21.0)
    issue_section.page_height = Cm(29.7)
    issue_section.left_margin = Cm(1.0)
    issue_section.right_margin = Cm(1.0)
    issue_section.top_margin = Cm(1.1)
    issue_section.bottom_margin = Cm(1.0)
    issue_section.header_distance = Cm(0.4)
    issue_section.footer_distance = Cm(0.4)
    issue_section.footer.is_linked_to_previous = False

    # Dynamic Page field in footer
    footer = issue_section.footer
    for p in footer.paragraphs:
        clear_paragraph(p)
    add_page_field(footer.paragraphs[0])

    if findings:
        for i in range(0, len(findings), 2):
            if i > 0:
                doc.add_page_break()
            add_issue_header(doc, inspection_date, report_type=report_type, logo_path=lg_path)
            has_second = (i + 1) < len(findings)
            table = doc.add_table(rows=3 if has_second else 1, cols=2)
            set_table_geometry(table, [5850, 4900], borders=True, border_color="D3D3D3", border_sz="4")
            populate_finding_row(table.rows[0], findings[i], report_type=report_type, date_str=inspection_date)
            if has_second:
                format_separator_row(table.rows[1])
                populate_finding_row(table.rows[2], findings[i + 1], report_type=report_type, date_str=inspection_date)
    else:
        add_issue_header(doc, inspection_date, report_type=report_type, logo_path=lg_path)
        note = doc.add_paragraph()
        note.alignment = WD_ALIGN_PARAGRAPH.CENTER
        note.paragraph_format.space_before = Pt(60)
        add_run(note, "本次检查未记录现场问题。", size=12, font="Microsoft YaHei", color=RGBColor(90, 98, 108))
        note.add_run().add_break()
        add_run(note, "Không ghi nhận vấn đề hiện trường trong đợt kiểm tra này.", size=11, color=RGBColor(90, 98, 108))

    # Auto-update field codes on open
    settings = doc.settings._element
    update_fields = settings.find(qn("w:updateFields"))
    if update_fields is None:
        update_fields = OxmlElement("w:updateFields")
        settings.append(update_fields)
    update_fields.set(qn("w:val"), "true")

    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()


# =============================================================================
# Collision-Safe File Lock Resolver
# =============================================================================

def safe_write_bytes(target_file: Path | str, data: bytes) -> tuple[Path, bool]:
    """
    Safely writes data to target_file. If locked by Microsoft Word (PermissionError/OSError),
    falls back to timestamped file '{stem}_{HHMMSS}{suffix}'.
    Returns: (actual_saved_path, was_locked_flag).
    """
    target_path = Path(target_file)
    clean_name = re.sub(r'[\\/*?:"<>|]', '_', target_path.name)
    target_path = target_path.parent / clean_name
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(target_path, "wb") as f:
            f.write(data)
        return target_path, False
    except (PermissionError, OSError):
        timestamp = datetime.now().strftime("%H%M%S")
        alt_path = target_path.parent / f"{target_path.stem}_{timestamp}{target_path.suffix}"
        with open(alt_path, "wb") as f:
            f.write(data)
        return alt_path, True


# =============================================================================
# Prior-Month Word Decompiler (parse_docx_to_report)
# =============================================================================

def parse_docx_to_report(doc_input: Union[bytes, str, Path, io.BytesIO]) -> dict[str, Any]:
    """
    Decompiles a prior month inspection DOCX report into an improvement workflow JSON object.
    Extracts inspection date, inspectors, checklist evaluations, and embedded findings with photos.
    """
    if isinstance(doc_input, (str, Path)):
        p = Path(doc_input)
        if not p.exists():
            raise ValueError(f"Không tìm thấy tệp docx: {p}")
        with open(p, "rb") as f:
            stream = io.BytesIO(f.read())
    elif isinstance(doc_input, bytes):
        stream = io.BytesIO(doc_input)
    elif isinstance(doc_input, io.BytesIO):
        stream = doc_input
    else:
        raise ValueError("Định dạng đầu vào không hợp lệ cho bộ dịch ngược DOCX.")

    try:
        doc = Document(stream)
    except Exception as exc:
        raise ValueError(f"Tệp DOCX hỏng hoặc không đúng định dạng OOXML: {exc}") from exc

    if not doc.tables or len(doc.tables[0].rows) < 34:
        raise ValueError("Tài liệu không phải mẫu báo cáo HSE hợp lệ hoặc thiếu bảng kiểm tra 26 hạng mục.")

    # Extract date & inspectors from header paragraphs
    date_str = ""
    inspectors_str = ""
    for p in doc.paragraphs:
        txt = p.text
        if not date_str and any(k in txt for k in ("检查日期", "Ngày kiểm tra", "复查日期", "Ngày phục tra")):
            m = re.search(r"(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})", txt)
            if m:
                date_str = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            else:
                m2 = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", txt)
                if m2:
                    date_str = f"{m2.group(3)}-{int(m2.group(2)):02d}-{int(m2.group(1)):02d}"
        if not inspectors_str and any(k in txt for k in ("检查人员", "Người kiểm tra", "复查人员", "Người phục tra")):
            m = re.search(r"(?:检查人员|Người kiểm tra|复查人员|Người phục tra)[:：\s]*(.*?)(?:\n|$)", txt)
            if m:
                inspectors_str = m.group(1).strip()

    if not date_str:
        date_str = date.today().isoformat()

    # Decompile Table 0 Checklist items
    table0 = doc.tables[0]
    decompiled_checklist: List[dict[str, Any]] = []
    for row_idx in EXPECTED_CHECKLIST_ROWS:
        if row_idx < len(table0.rows):
            row = table0.rows[row_idx]
            c4_text = row.cells[4].text.strip()
            c5_text = row.cells[5].text.strip()
            if "√" in c4_text or not c5_text:
                status = "pass"
                issue_vi = ""
                issue_zh = ""
            else:
                status = "fail"
                lines = [line.strip() for line in c5_text.splitlines() if line.strip()]
                issue_zh = lines[0] if lines else ""
                issue_vi = lines[1] if len(lines) > 1 else (lines[0] if lines else "")
            improved = ("已整改" in c4_text or "Đã cải thiện" in c4_text)
            decompiled_checklist.append({
                "row": row_idx,
                "status": status,
                "issueVi": issue_vi,
                "issueZh": issue_zh,
                "improved": improved
            })

    # Decompile Findings from doc.tables[1:]
    findings: List[dict[str, Any]] = []
    for tbl in doc.tables[1:]:
        for row in tbl.rows:
            if len(row.cells) == 2:
                left_text = row.cells[0].text.strip()
                if any(k in left_text for k in ("负责部门", "Bộ phận", "问题", "Vấn đề")):
                    m_zh_dept = re.search(r"负责部门[:：]\s*(.*?)(?:\n|$)", left_text)
                    m_vi_dept = re.search(r"Bộ phận[:：]\s*(.*?)(?:\n|$)", left_text)
                    m_zh_issue = re.search(r"问题[:：]\s*(.*?)(?:\nBộ phận|\n复查|\nKiểm tra|$)", left_text, re.DOTALL)
                    m_vi_issue = re.search(r"Vấn đề[:：]\s*(.*?)(?:\n复查|\nKiểm tra|$)", left_text, re.DOTALL)

                    dept_zh = m_zh_dept.group(1).strip() if m_zh_dept else ""
                    dept_vi = m_vi_dept.group(1).strip() if m_vi_dept else ""
                    issue_zh = m_zh_issue.group(1).strip() if m_zh_issue else ""
                    issue_vi = m_vi_issue.group(1).strip() if m_vi_issue else ""

                    issue_zh = re.sub(r"^问题[:：]\s*", "", issue_zh).strip()
                    issue_vi = re.sub(r"^Vấn đề[:：]\s*", "", issue_vi, flags=re.IGNORECASE).strip()

                    dept_key, _, _ = classify_department_from_text(f"{dept_zh} {dept_vi}")
                    img_data = extract_cell_image_base64(row.cells[1], doc)

                    findings.append({
                        "id": f"imported_{len(findings)+1}",
                        "departmentKey": dept_key,
                        "departmentVi": dept_vi or "Sản xuất",
                        "departmentZh": dept_zh or "生产部",
                        "aiHint": "",
                        "issueVi": issue_vi,
                        "issueZh": f"问题: {issue_zh}" if issue_zh and not issue_zh.startswith("问题") else issue_zh,
                        "suggestion": "",
                        "imageData": img_data,
                        "imageName": f"imported_{len(findings)+1}.jpg",
                        "improved": False,
                        "imageAfterData": "",
                        "imageAfterName": ""
                    })

    return {
        "id": f"hse_imp_{int(datetime.now().timestamp()*1000)}",
        "reportType": "improvement",
        "mode": "improvement",
        "globalAiHint": f"Phục tra các vi phạm kỳ kiểm tra {date_str}",
        "metadata": {
            "date": date_str,
            "prevDate": date_str,
            "inspectors": inspectors_str or "Ban HSE"
        },
        "checklist": decompiled_checklist,
        "findings": findings
    }
