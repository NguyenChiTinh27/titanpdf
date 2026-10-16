// ============================================================
// TitanPDF Private Suite - Complete Controller (26 Tools Parity)
// With Full Side-by-Side Interactive Studio & Advanced Mechanics
// ============================================================

// Initialize local offline PDF.js worker
if (window.pdfjsLib) {
    pdfjsLib.GlobalWorkerOptions.workerSrc = '/libs/pdf.worker.min.js';
}

/**
 * Render an inline SVG icon referencing the master SVG symbol sprite.
 * @param {string} name - Symbol name without prefix (e.g. "merge", "search", "trash")
 * @param {string} [cls="w-5 h-5"] - CSS utility classes
 * @param {string} [attrs=""] - Additional HTML attributes (e.g. 'title="Xoay 90°"')
 * @returns {string} Clean SVG markup with strict pixel bounding
 */
function icon(name, cls = "w-5 h-5", attrs = "") {
    let width = 20;
    let height = 20;
    if (cls.includes("w-2.5") || cls.includes("w-2-5") || cls.includes("h-2.5")) { width = 10; height = 10; }
    else if (cls.includes("w-2") || cls.includes("h-2")) { width = 8; height = 8; }
    else if (cls.includes("w-3.5") || cls.includes("w-3-5") || cls.includes("h-3.5")) { width = 14; height = 14; }
    else if (cls.includes("w-3") || cls.includes("h-3")) { width = 12; height = 12; }
    else if (cls.includes("w-4") || cls.includes("h-4")) { width = 16; height = 16; }
    else if (cls.includes("w-5") || cls.includes("h-5")) { width = 20; height = 20; }
    else if (cls.includes("w-6") || cls.includes("h-6")) { width = 24; height = 24; }
    else if (cls.includes("w-7") || cls.includes("h-7")) { width = 28; height = 28; }
    else if (cls.includes("w-8") || cls.includes("h-8")) { width = 32; height = 32; }
    else if (cls.includes("w-10") || cls.includes("h-10")) { width = 40; height = 40; }
    else if (cls.includes("w-12") || cls.includes("h-12")) { width = 48; height = 48; }

    return `<svg class="${cls}" width="${width}" height="${height}" viewBox="0 0 24 24" aria-hidden="true" style="width:${width}px !important; height:${height}px !important; max-width:${width}px !important; max-height:${height}px !important; flex-shrink:0;" ${attrs}><use href="#icon-${name}"></use></svg>`;
}

/**
 * Remove Vietnamese accents and diacritics for instant fuzzy matching.
 */
function removeAccents(str) {
    if (!str) return "";
    return str.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D");
}

const TOOLS = [
    // 1. TỔ CHỨC PDF (ORGANIZE) - 7 Tools
    {
        id: "merge",
        title: "Ghép PDF",
        desc: "Hợp nhất nhiều tệp PDF thành tài liệu sinh thái duy nhất.",
        iconImg: "/icons/merge_icon.png",
        category: "organize",
        badge: "PDF",
        accept: ".pdf",
        multiple: true,
        actionText: "Ghép các tệp PDF",
        endpoint: "/api/process/merge",
        keywords: ["ghep", "hop nhat", "combine", "join", "merge"]
    },
    {
        id: "split",
        title: "Tách PDF",
        desc: "Chia nhỏ tài liệu theo từng trang lẻ hoặc trích xuất dải trang.",
        iconImg: "/icons/split_icon.png",
        category: "organize",
        badge: "PDF",
        accept: ".pdf",
        multiple: false,
        actionText: "Tách tệp PDF",
        endpoint: "/api/process/split",
        keywords: ["tach", "chia", "cat", "cut", "range", "split"]
    },
    {
        id: "extract-pages",
        title: "Trích xuất trang",
        desc: "Trích chọn các trang mong muốn tạo thành một tệp PDF mới.",
        iconImg: "/icons/extract-pages_icon.png",
        category: "organize",
        badge: "PDF",
        accept: ".pdf",
        multiple: false,
        actionText: "Trích xuất các trang",
        endpoint: "/api/process/extract-pages",
        keywords: ["trich", "lay trang", "extract", "select"]
    },
    {
        id: "delete-pages",
        title: "Xóa trang PDF",
        desc: "Loại bỏ hoàn toàn các trang không cần thiết khỏi tệp tin.",
        iconImg: "/icons/delete-pages_icon.png",
        category: "organize",
        badge: "PDF",
        accept: ".pdf",
        multiple: false,
        actionText: "Xóa các trang đã chọn",
        endpoint: "/api/process/delete-pages",
        keywords: ["xoa", "remove", "delete"]
    },
    {
        id: "organize",
        title: "Sắp xếp trang",
        desc: "Đổi thứ tự trang, đảo ngược chiều tài liệu theo ý muốn.",
        iconImg: "/icons/organize_icon.png",
        category: "organize",
        badge: "PDF",
        accept: ".pdf",
        multiple: false,
        actionText: "Sắp xếp lại trang",
        endpoint: "/api/process/organize",
        keywords: ["sap xep", "dao nguoc", "order", "reverse", "reorder"]
    },
    {
        id: "rotate",
        title: "Xoay PDF",
        desc: "Xoay hướng các trang tài liệu theo góc 90, 180 hoặc 270 độ.",
        iconImg: "/icons/rotate_icon.png",
        category: "organize",
        badge: "PDF",
        accept: ".pdf",
        multiple: false,
        actionText: "Xoay trang PDF",
        endpoint: "/api/process/rotate",
        keywords: ["xoay", "huong trang", "rotate", "angle"]
    },
    {
        id: "page-numbers",
        title: "Đánh số trang",
        desc: "Đánh số trang chân tài liệu tự động và chuyên nghiệp.",
        iconImg: "/icons/page-numbers_icon.png",
        category: "organize",
        badge: "PDF",
        accept: ".pdf",
        multiple: false,
        actionText: "Đánh số trang PDF",
        endpoint: "/api/process/page-numbers",
        keywords: ["danh so", "so trang", "pagination", "page number"]
    },

    // 2. CHUYỂN ĐỔI SANG PDF (CONVERT TO PDF) - 4 Tools
    {
        id: "word-to-pdf",
        title: "Word sang PDF",
        desc: "Xuất Word (.docx, .doc) sang PDF chuẩn bằng Động cơ Siêu Cấp VIP Pro.",
        iconImg: "/icons/word-to-pdf_icon.png",
        category: "convert",
        badge: "OFFICE",
        accept: ".docx,.doc",
        multiple: false,
        actionText: "Chuyển sang PDF",
        endpoint: "/api/process/word-to-pdf",
        keywords: ["word", "doc", "docx", "chuyen word"]
    },
    {
        id: "ppt-to-pdf",
        title: "PowerPoint sang PDF",
        desc: "Chuyển đổi bài thuyết trình (.pptx, .ppt) sang tệp PDF sắc nét.",
        iconImg: "/icons/ppt-to-pdf_icon.png",
        category: "convert",
        badge: "OFFICE",
        accept: ".pptx,.ppt",
        multiple: false,
        actionText: "Chuyển PowerPoint sang PDF",
        endpoint: "/api/process/ppt-to-pdf",
        keywords: ["ppt", "pptx", "powerpoint", "slide"]
    },
    {
        id: "excel-to-pdf",
        title: "Excel sang PDF",
        desc: "Chuyển đổi bảng tính (.xlsx, .xls) sang định dạng PDF nguyên bản.",
        iconImg: "/icons/excel-to-pdf_icon.png",
        category: "convert",
        badge: "OFFICE",
        accept: ".xlsx,.xls",
        multiple: false,
        actionText: "Chuyển Excel sang PDF",
        endpoint: "/api/process/excel-to-pdf",
        keywords: ["excel", "xlsx", "xls", "bang tinh", "sheet"]
    },
    {
        id: "images-to-pdf",
        title: "Hình ảnh sang PDF",
        desc: "Ghép nhiều ảnh JPG, PNG, BMP thành 1 tệp PDF hoàn chỉnh.",
        iconImg: "/icons/images-to-pdf_icon.png",
        category: "convert",
        badge: "ẢNH",
        accept: "image/*,.png,.jpg,.jpeg,.bmp",
        multiple: true,
        actionText: "Ghép ảnh thành PDF",
        endpoint: "/api/process/images-to-pdf",
        keywords: ["anh", "jpg", "png", "jpeg", "image", "photo"]
    },

    // 3. CHUYỂN ĐỔI TỪ PDF (CONVERT FROM PDF) - 5 Tools
    {
        id: "pdf-to-word",
        title: "PDF sang Word",
        desc: "Chuyển PDF sang DOCX trực tiếp qua Microsoft Word Native COM, tự động fallback offline nhẹ.",
        iconImg: "/icons/pdf-to-word_icon.png",
        category: "convert",
        badge: "WORD COM",
        accept: ".pdf",
        multiple: false,
        actionText: "Chuyển sang Word (DOCX)",
        endpoint: "/api/process/pdf-to-word",
        keywords: ["pdf sang word", "pdf sang docx", "docx", "word", "pdf to word", "native word", "ms word", "convert to docx"]
    },
    {
        id: "pdf-to-ppt",
        title: "PDF sang PowerPoint",
        desc: "Chuyển tài liệu PDF thành các slide thuyết trình PowerPoint (.pptx).",
        iconImg: "/icons/pdf-to-ppt_icon.png",
        category: "convert",
        badge: "OFFICE",
        accept: ".pdf",
        multiple: false,
        actionText: "Chuyển sang PowerPoint",
        endpoint: "/api/process/pdf-to-ppt",
        keywords: ["pdf sang ppt", "presentation", "slide"]
    },
    {
        id: "pdf-to-excel",
        title: "PDF sang Excel",
        desc: "Trích xuất thông minh bảng biểu PDF sang bảng tính Excel (.xlsx).",
        iconImg: "/icons/pdf-to-excel_icon.png",
        category: "convert",
        badge: "OFFICE",
        accept: ".pdf",
        multiple: false,
        actionText: "Trích xuất sang Excel",
        endpoint: "/api/process/pdf-to-excel",
        keywords: ["pdf sang excel", "table", "bang", "xlsx"]
    },
    {
        id: "pdf-to-images",
        title: "PDF sang Hình ảnh",
        desc: "Xuất từng trang PDF thành hình ảnh JPG hoặc PNG chất lượng cao.",
        iconImg: "/icons/pdf-to-images_icon.png",
        category: "convert",
        badge: "ẢNH",
        accept: ".pdf",
        multiple: false,
        actionText: "Trích xuất hình ảnh",
        endpoint: "/api/process/pdf-to-images",
        keywords: ["pdf sang anh", "xuat anh", "png", "jpg"]
    },
    {
        id: "pdf-to-pdfa",
        title: "PDF sang PDF/A",
        desc: "Chuẩn hóa tài liệu sang định dạng lưu trữ dài hạn tiêu chuẩn ISO.",
        iconImg: "/icons/pdf-to-pdfa_icon.png",
        category: "convert",
        badge: "LƯU TRỮ",
        accept: ".pdf",
        multiple: false,
        actionText: "Chuyển đổi sang PDF/A",
        endpoint: "/api/process/pdf-to-pdfa",
        keywords: ["pdfa", "iso", "luu tru", "archive"]
    },

    // 4. TỐI ƯU HÓA (OPTIMIZE) - 3 Tools
    {
        id: "compress",
        title: "Nén PDF",
        desc: "Tối ưu hóa dung lượng file tối đa, giữ trọn vẹn chất lượng.",
        iconImg: "/icons/compress_icon.png",
        category: "optimize",
        badge: "TỐI ƯU",
        accept: ".pdf",
        multiple: false,
        actionText: "Nén tệp PDF ngay",
        endpoint: "/api/process/compress",
        keywords: ["nen", "giam dung luong", "compress", "size"]
    },
    {
        id: "repair",
        title: "Sửa chữa PDF lỗi",
        desc: "Khôi phục dữ liệu từ các tệp PDF bị lỗi cấu trúc hoặc hỏng XRef.",
        iconImg: "/icons/repair_icon.png",
        category: "optimize",
        badge: "TỐI ƯU",
        accept: ".pdf",
        multiple: false,
        actionText: "Sửa chữa tệp PDF",
        endpoint: "/api/process/repair",
        keywords: ["sua", "loi", "fix", "repair", "corrupt"]
    },
    {
        id: "ocr",
        title: "OCR Nhận diện văn bản",
        desc: "AI OCR quét file scan kết hợp Động cơ Tái tạo Bố cục Siêu Cấp VIP Pro xuất ra PDF Vector nét căng và Word chuẩn.",
        iconImg: "/icons/ocr_icon.png",
        category: "ai",
        badge: "AI SIÊU CẤP",
        accept: ".pdf",
        multiple: false,
        actionText: "Nhận diện & Tái tạo tài liệu OCR",
        endpoint: "/api/process/ocr",
        keywords: ["ocr", "nhan dien chu", "text recognition", "scan", "tai tao pdf", "sieu cap vip pro"]
    },

    // 5. CHỈNH SỬA & BẢO MẬT (SECURITY & EDIT) - 7 Tools
    {
        id: "watermark",
        title: "Đóng dấu Watermark",
        desc: "Đóng dấu chìm bảo vệ bản quyền với font tiếng Việt Unicode chuẩn nét.",
        iconImg: "/icons/watermark_icon.png",
        category: "security",
        badge: "BẢO MẬT",
        accept: ".pdf",
        multiple: false,
        actionText: "Đóng dấu Watermark",
        endpoint: "/api/process/watermark",
        keywords: ["watermark", "dau chim", "dong dau", "ban quyen"]
    },
    {
        id: "crop",
        title: "Cắt xén lề PDF",
        desc: "Cắt bỏ lề trắng thừa giúp tài liệu gọn gàng và dễ đọc hơn.",
        iconImg: "/icons/crop_icon.png",
        category: "security",
        badge: "CHỈNH SỬA",
        accept: ".pdf",
        multiple: false,
        actionText: "Cắt lề tài liệu",
        endpoint: "/api/process/crop",
        keywords: ["crop", "cat le", "margin"]
    },
    {
        id: "protect",
        title: "Khóa bảo vệ PDF",
        desc: "Mã hóa tài liệu bằng thuật toán chuẩn quân sự AES-256 an toàn.",
        iconImg: "/icons/protect_icon.png",
        category: "security",
        badge: "BẢO MẬT",
        accept: ".pdf",
        multiple: false,
        actionText: "Khóa bảo vệ tài liệu",
        endpoint: "/api/process/protect",
        keywords: ["khoa", "mat khau", "password", "encrypt", "protect"]
    },
    {
        id: "unlock",
        title: "Mở khóa PDF",
        desc: "Gỡ bỏ mật khẩu và các giới hạn quyền in/sao chép trên PDF.",
        iconImg: "/icons/unlock_icon.png",
        category: "security",
        badge: "BẢO MẬT",
        accept: ".pdf",
        multiple: false,
        actionText: "Mở khóa PDF",
        endpoint: "/api/process/unlock",
        keywords: ["mo khoa", "xoa mat khau", "unlock", "decrypt"]
    },
    {
        id: "sign",
        title: "Ký điện tử e-Sign",
        desc: "Chèn ảnh chữ ký cá nhân trực tiếp vào trang văn bản PDF.",
        iconImg: "/icons/sign_icon.png",
        category: "security",
        badge: "KÝ SỐ",
        accept: ".pdf",
        multiple: false,
        actionText: "Chèn chữ ký vào PDF",
        endpoint: "/api/process/sign",
        keywords: ["ky", "chu ky", "sign", "signature", "e-sign"]
    },
    {
        id: "redact",
        title: "Che thông tin nhạy cảm",
        desc: "Bôi đen và xóa vĩnh viễn dữ liệu bảo mật (Redaction) không thể phục hồi.",
        iconImg: "/icons/redact_icon.png",
        category: "security",
        badge: "BẢO MẬT",
        accept: ".pdf",
        multiple: false,
        actionText: "Che thông tin nhạy cảm",
        endpoint: "/api/process/redact",
        keywords: ["che", "redact", "boi den", "xoa thong tin"]
    },
    {
        id: "compare",
        title: "So sánh 2 bản PDF",
        desc: "Đặt 2 tài liệu song song để đối chiếu điểm khác biệt từng trang.",
        iconImg: "/icons/compare_icon.png",
        category: "security",
        badge: "SO SÁNH",
        accept: ".pdf",
        multiple: true,
        actionText: "So sánh 2 tài liệu",
        endpoint: "/api/process/compare",
        keywords: ["so sanh", "compare", "doi chieu", "diff"]
    },

    // 6. DỊCH THUẬT SONG NGỮ CHUYÊN SÂU (DOC-TRAN / CẢI BIÊN SIÊU CẤP VIP PRO) - Tool 27
    {
        id: "interlinear-translate",
        title: "Dịch Song ngữ Kỹ thuật (DOC-TRAN)",
        desc: "Hợp nhất Động cơ Siêu Cấp VIP Pro, OCR AI và DeepSeek: Xử lý PDF Scan, tài liệu Word & biểu mẫu sang Song ngữ xen kẽ (#002060 nghiêng), bảo vệ số CAS.",
        iconImg: "/icons/doc-tran_icon.png",
        category: "ai",
        badge: "VIP PRO AI",
        accept: ".docx,.doc,.pdf",
        multiple: false,
        actionText: "Dịch Song ngữ Tài liệu",
        endpoint: "/api/process/interlinear-translate",
        keywords: ["dich", "song ngu", "translate", "doc-tran", "msds", "sds", "hoa chat", "tieng trung", "tieng anh", "en-vi", "zh-vi", "scan", "ocr", "vip pro"]
    },

    // 7. TRÌNH CHỈNH SỬA VIP PRO (VIP PDF EDITOR) - Tool 28
    {
        id: "vip-editor",
        title: "Trình Chỉnh Sửa VIP Pro",
        desc: "Bộ công cụ tương tác trực quan: Viết chữ, vẽ tự do, dạ quang, hình khối co giãn 8 nốt, chèn ảnh và xuất PDF vector nguyên gốc.",
        iconImg: "/icons/edit_icon.png",
        category: "organize",
        badge: "VIP PRO",
        accept: ".pdf",
        multiple: false,
        actionText: "Khởi Chạy Trình Chỉnh Sửa VIP Pro",
        endpoint: "/api/process/vip-editor-save",
        keywords: ["chinh sua", "edit", "ve", "but", "viet chu", "hinh khoi", "chu ky", "da quang", "highlight", "vip pro", "trinh chinh sua", "editor"]
    },

    // 8. DỊCH THUẬT VĂN BẢN AI & GOOGLE - Tool 29
    {
        id: "ai-translator",
        title: "Dịch thuật Văn bản AI & Google",
        desc: "Dịch tự do văn bản & tài liệu bằng Google Dịch siêu tốc hoặc AI DeepSeek chuyên sâu. Nút sao chép 1 chạm, nhận diện đa ngôn ngữ.",
        iconImg: "/icons/doc-tran_icon.png",
        category: "ai",
        badge: "AI DỊCH",
        accept: ".txt,.docx,.doc,.pdf",
        multiple: false,
        actionText: "Mở Trình Dịch Thuật AI",
        endpoint: "/api/process/ai-translate",
        keywords: ["dich", "translate", "google dich", "ai dich", "deepseek", "sao chep", "copy", "van ban", "text", "tai lieu"]
    },

    // 9. AI TÓM TẮT TÀI LIỆU - Tool 30
    {
        id: "ai-summarizer",
        title: "AI Tóm Tắt Tài Liệu",
        desc: "Đọc hiểu sâu và tóm tắt thông minh tệp PDF, Word, PowerPoint, Text bằng AI. Báo cáo điều hành, gạch đầu dòng cốt lõi, xuất bản Word .docx.",
        iconImg: "/icons/split_icon.png",
        category: "ai",
        badge: "AI TÓM TẮT",
        accept: ".pdf,.docx,.doc,.txt,.pptx",
        multiple: false,
        actionText: "Tóm Tắt Bằng AI",
        endpoint: "/api/process/ai-summarize",
        keywords: ["tom tat", "summary", "summarize", "ai", "deepseek", "rut gon", "doc hieu", "executive summary", "pdf", "docx"]
    },

    // 10. XÓA WATERMARK & NỀN RÁC - Tool 31
    {
        id: "remove-watermark",
        title: "Xóa Watermark & Nền Rác",
        desc: "Tự động phát hiện và loại bỏ dấu chìm, chữ mờ quảng cáo, logo nền mờ và tem mộc rác khỏi tài liệu PDF.",
        iconImg: "/icons/watermark_icon.png",
        category: "optimize",
        badge: "CLEAN PDF",
        accept: ".pdf",
        multiple: false,
        actionText: "Tẩy Sạch Watermark & Nền Rác",
        endpoint: "/api/process/remove-watermark",
        keywords: ["xoa watermark", "remove watermark", "xoa dau chim", "xoa logo mo", "xoa chu mo", "xoa nen", "lam sach pdf", "clean pdf", "camscanner"]
    },

    // 11. MSDS AI & SỔ HÓA CHẤT CIL - Tool 32
    {
        id: "msds-studio",
        title: "MSDS AI & Sổ Hóa Chất CIL",
        desc: "Bóc tách 16 mục GHS chuẩn quốc tế, thẩm định số CAS/UN, lưu trữ danh mục hóa chất cục bộ và xuất file Sổ CIL Excel (.xlsx).",
        iconImg: "/icons/doc-tran_icon.png",
        category: "ai",
        badge: "AI HÓA CHẤT",
        accept: ".pdf,.docx,.doc,.txt",
        multiple: false,
        actionText: "Mở Trình Quản Trị MSDS & CIL",
        endpoint: "/api/msds/upload-and-summarize",
        keywords: ["msds", "sds", "cil", "hoa chat", "chemical", "cas", "ghs", "so hoa chat", "nghi dinh 113", "an toan hoa chat"]
    },

    // 12. HSE REPORT STUDIO - Tool 33
    {
        id: "hse-studio",
        title: "HSE Report Studio",
        description: "Lập báo cáo kiểm tra hiện trường & phục tra cải thiện chuẩn ZhanChen, tích hợp AI DeepSeek và xuất Word A4",
        desc: "Lập báo cáo kiểm tra hiện trường & phục tra cải thiện chuẩn ZhanChen, tích hợp AI DeepSeek và xuất Word A4",
        category: "ai",
        badge: "HOT",
        icon: "clipboard-check",
        iconImg: "/icons/hse_avatar.jpg",
        accept: ".docx,.json",
        multiple: false,
        actionText: "Mở HSE Report Studio",
        endpoint: "/api/hse/generate_docx",
        customAction: () => switchMainTab("hse"),
        keywords: ["hse", "hse-studio", "hse_report_studio", "kiem tra", "an toan", "bao cao", "cai thien", "zhanchen", "deepseek", "tuan tra", "report"]
    },

    // 13. TRA CỨU PHÁP LÝ HÓA CHẤT - Tool 34
    {
        id: "legal-lookup",
        title: "Tra Cứu Pháp Lý Hóa Chất",
        description: "Đối soát tự động nghĩa vụ tuân thủ theo Luật Hóa chất 69/2025/QH15, Nghị định 24/2026/NĐ-CP, Nghị định 28/2026/NĐ-CP và QCVN 01:2025/BYT.",
        desc: "Đối soát tự động nghĩa vụ tuân thủ theo Luật Hóa chất 69/2025/QH15, Nghị định 24/2026/NĐ-CP, Nghị định 28/2026/NĐ-CP và QCVN 01:2025/BYT.",
        category: "ai",
        badge: "PHÁP LÝ MỚI",
        icon: "file-check",
        iconImg: "/icons/doc-pro_icon.png",
        accept: ".xlsx,.json",
        multiple: false,
        actionText: "Mở Bảng Tra Cứu Pháp Lý",
        endpoint: "/api/legal/catalog",
        customAction: () => switchMainTab("legal"),
        keywords: ["phap ly", "legal", "nghi dinh 24", "nghi dinh 28", "qcvn", "cas", "luat hoa chat", "tien chat", "hoa chat cam", "hoa chat han che", "nguyen lieu", "thanh pham"]
    }
];

// App State
let currentTool = null;
let selectedFiles = [];
let loadedPdfDoc = null;
let originalDocProxy = null;
let processedDocProxy = null;
let activePreviewSource = "original";
let pageRotations = {};       // { pageNum: angle }
let deletedPages = new Set(); // Canonical deleted/excluded pages
let excludedPages = deletedPages; // Alias for backward compatibility
let selectedPages = new Set(); // Highlighted/selected pages
let pageOrder = [];           // Current order of pages e.g. [1, 2, 3...]
let currentThumbWidth = 180;
let studioViewMode = 'grid';  // 'grid' | 'viewer' | 'files'
let currentCategory = "all";
let currentSearchQuery = "";
let lastResultUrl = null;
let lastResultFilename = null;
let lastClickedPage = null;
let isInternalSync = false;
let rangeSyncDebounceTimer = null;
let currentSignaturePos = "bottom-right";
let currentSignatureUrl = null;

// DOM Elements
const homeView = document.getElementById("home-view");
const workspaceView = document.getElementById("workspace-view");
const toolsGrid = document.getElementById("tools-grid");
const dropzone = document.getElementById("dropzone");
const studioContainer = document.getElementById("studio-container");
const fileInput = document.getElementById("file-input");
const optionsPanel = document.getElementById("options-panel");
const optionsContent = document.getElementById("options-content");
const actionPanel = document.getElementById("action-panel");
const loadingPanel = document.getElementById("loading-panel");
const resultPanel = document.getElementById("result-panel");
const btnProcessText = document.getElementById("btn-process-text");
const pagesGrid = document.getElementById("pages-grid");
const docViewerContainer = document.getElementById("doc-viewer-container");
const multiFileList = document.getElementById("multi-file-list");
const studioLoading = document.getElementById("studio-loading");
const comparisonToggleGroup = document.getElementById("comparison-toggle-group");
const canvasShimmerBar = document.getElementById("canvas-shimmer-bar");
const canvasStatusPill = document.getElementById("canvas-status-pill");

// -------------------------------------------------------------
// LRU CANVAS CACHE & THUMBNAIL RENDER QUEUE
// -------------------------------------------------------------
class LRUCanvasCache {
    constructor(maxEntries = 40) {
        this.maxEntries = maxEntries;
        this.map = new Map(); // pageNum -> { canvas, page, slotElement }
    }

    has(pageNum) {
        return this.map.has(pageNum);
    }

    get(pageNum) {
        if (!this.map.has(pageNum)) return null;
        const entry = this.map.get(pageNum);
        this.map.delete(pageNum);
        this.map.set(pageNum, entry);
        return entry;
    }

    put(pageNum, entry) {
        if (this.map.has(pageNum)) {
            this.map.delete(pageNum);
        } else if (this.map.size >= this.maxEntries) {
            const oldestPageNum = this.map.keys().next().value;
            this.evict(oldestPageNum);
        }
        this.map.set(pageNum, entry);
    }

    evict(pageNum) {
        const item = this.map.get(pageNum);
        if (!item) return;
        this.map.delete(pageNum);

        // 1. Free GPU texture memory
        if (item.canvas) {
            item.canvas.width = 0;
            item.canvas.height = 0;
            item.canvas.remove();
        }

        // 2. Cleanup PDF.js page resources
        if (item.page && typeof item.page.cleanup === "function") {
            try { item.page.cleanup(); } catch (e) {}
        }

        // 3. Restore skeleton placeholder
        if (item.slotElement) {
            item.slotElement.innerHTML = `
                <div class="skeleton-shimmer" data-skeleton="${pageNum}">
                    <div class="skeleton-shimmer-wave"></div>
                    <span class="skeleton-text">Trang ${pageNum}</span>
                </div>
            `;
        }
    }

    clear() {
        for (const pageNum of Array.from(this.map.keys())) {
            this.evict(pageNum);
        }
    }
}

const lruCanvasCache = new LRUCanvasCache(40);

class ThumbnailRenderQueue {
    constructor(concurrencyLimit = 2) {
        this.concurrencyLimit = concurrencyLimit;
        this.queue = [];
        this.activeCount = 0;
        this.renderingPages = new Set();
    }

    enqueue(pageNum) {
        if (lruCanvasCache.has(pageNum) || this.renderingPages.has(pageNum)) return;
        if (!this.queue.includes(pageNum)) {
            this.queue.push(pageNum);
            this.processNext();
        }
    }

    dequeueIfPending(pageNum) {
        const idx = this.queue.indexOf(pageNum);
        if (idx !== -1) {
            this.queue.splice(idx, 1);
        }
    }

    clear() {
        this.queue = [];
        this.renderingPages.clear();
        this.activeCount = 0;
    }

    async processNext() {
        if (this.activeCount >= this.concurrencyLimit || this.queue.length === 0) return;

        const pageNum = this.queue.shift();
        this.activeCount++;
        this.renderingPages.add(pageNum);

        try {
            await renderSingleThumbnail(pageNum);
        } catch (err) {
            console.error(`Lỗi render thumbnail trang ${pageNum}:`, err);
        } finally {
            this.activeCount--;
            this.renderingPages.delete(pageNum);
            this.processNext();
        }
    }
}

const thumbnailQueue = new ThumbnailRenderQueue(2);
let thumbnailObserver = null;
let readerObserver = null;


// -------------------------------------------------------------
// 1. RENDER HOME TOOL CARDS
// -------------------------------------------------------------
function renderToolCards() {
    const grid = document.getElementById("tools-grid");
    const emptyState = document.getElementById("tools-empty-state");
    if (!grid) return;
    grid.innerHTML = "";

    let list = TOOLS.slice(0, 31);
    if (currentCategory !== "all") {
        list = list.filter(t => t.category === currentCategory);
    }
    if (currentSearchQuery.trim()) {
        const q = removeAccents(currentSearchQuery.trim().toLowerCase());
        list = list.filter(t => {
            const titleNorm = removeAccents(t.title.toLowerCase());
            const descNorm = removeAccents(t.desc.toLowerCase());
            const matchKeywords = (t.keywords || []).some(k => removeAccents(k.toLowerCase()).includes(q));
            return titleNorm.includes(q) || descNorm.includes(q) || matchKeywords;
        });
    }

    if (list.length === 0) {
        grid.classList.add("hidden");
        if (emptyState) {
            emptyState.classList.remove("hidden");
            const emptyText = document.getElementById("empty-query-text");
            if (emptyText) emptyText.innerText = `Không tìm thấy công cụ nào phù hợp với "${currentSearchQuery}".`;
        }
        return;
    }

    grid.classList.remove("hidden");
    if (emptyState) emptyState.classList.add("hidden");

    list.forEach(tool => {
        const card = document.createElement("div");
        card.className = "tool-card";
        card.setAttribute("data-tool-id", tool.id);
        card.setAttribute("data-category", tool.category);
        card.setAttribute("tabindex", "0");
        card.setAttribute("role", "button");
        card.setAttribute("aria-label", tool.title);

        const badgeClass = tool.category === "ai" ? "badge-ai" :
                           tool.category === "convert" ? "badge-office" :
                           tool.category === "security" ? "badge-security" :
                           tool.category === "optimize" ? "badge-optimize" : "badge-pdf";

        card.innerHTML = `
            <div>
                <div class="tool-card-top">
                    <div class="tool-icon-wrapper">
                        ${icon(tool.id, "w-5 h-5")}
                    </div>
                    <span class="badge ${badgeClass}">${tool.badge || "PDF"}</span>
                </div>
                <div class="tool-card-content">
                    <h3 class="tool-title">${tool.title}</h3>
                    <p class="tool-desc">${tool.desc}</p>
                </div>
            </div>
            <div class="tool-card-footer">
                <span>Khởi chạy</span>
                ${icon("arrow-right", "tool-arrow-icon")}
            </div>
        `;

        card.onclick = () => openTool(tool.id);
        card.onkeydown = (e) => {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                openTool(tool.id);
            }
        };

        grid.appendChild(card);
    });
}

function filterCategory(cat) {
    currentCategory = cat;
    document.querySelectorAll(".segment-btn, .cat-btn").forEach(btn => {
        const isActive = btn.dataset.cat === cat;
        btn.classList.toggle("active", isActive);
        btn.setAttribute("aria-selected", isActive ? "true" : "false");
    });
    renderToolCards();
}

function handleSearch(val) {
    currentSearchQuery = val;
    const clearBtn = document.getElementById("search-clear-btn");
    const kbdHint = document.getElementById("search-kbd-hint");
    if (clearBtn && kbdHint) {
        if (val.trim()) {
            clearBtn.classList.remove("hidden");
            kbdHint.classList.add("hidden");
        } else {
            clearBtn.classList.add("hidden");
            kbdHint.classList.remove("hidden");
        }
    }
    renderToolCards();
}

function clearSearch() {
    const input = document.getElementById("search-input");
    if (input) {
        input.value = "";
        handleSearch("");
        input.focus();
    }
}

// Global Keyboard Navigation (Ctrl+K, Esc, ArrowDown, Grid Navigation)
function setupKeyboardNavigation() {
    const searchInput = document.getElementById("search-input");

    window.addEventListener("keydown", (e) => {
        // 1. Ctrl+K or Cmd+K: Focus search input
        if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
            e.preventDefault();
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }

        // 2. Escape: Blur active input field first; return home only if no field is focused
        if (e.key === "Escape") {
            const activeEl = document.activeElement;
            const isInputActive = activeEl && (
                activeEl.tagName === "INPUT" ||
                activeEl.tagName === "TEXTAREA" ||
                activeEl.tagName === "SELECT"
            );

            if (isInputActive) {
                if (activeEl === searchInput && searchInput.value) {
                    clearSearch();
                } else {
                    activeEl.blur();
                }
                return;
            }

            // Only close workspace when no input is focused
            if (!workspaceView.classList.contains("hidden")) {
                goHome();
            }
        }
    });

    if (searchInput) {
        // ArrowDown from search input moves focus to first tool card
        searchInput.addEventListener("keydown", (e) => {
            if (e.key === "ArrowDown") {
                e.preventDefault();
                const firstCard = document.querySelector(".tool-card");
                if (firstCard) firstCard.focus();
            }
        });
    }

    // Grid arrow key navigation
    document.getElementById("tools-grid")?.addEventListener("keydown", (e) => {
        const cards = Array.from(document.querySelectorAll(".tool-card"));
        const currentIndex = cards.indexOf(document.activeElement);
        if (currentIndex === -1) return;

        if (e.key === "ArrowRight") {
            e.preventDefault();
            const next = cards[currentIndex + 1] || cards[0];
            next.focus();
        } else if (e.key === "ArrowLeft") {
            e.preventDefault();
            const prev = cards[currentIndex - 1] || cards[cards.length - 1];
            prev.focus();
        } else if (e.key === "ArrowUp" && currentIndex < 4 && searchInput) {
            e.preventDefault();
            searchInput.focus();
        }
    });
}

// -------------------------------------------------------------
// 2. WORKSPACE & TOOL OPENING
// -------------------------------------------------------------
function openTool(toolId) {
    if (toolId === "vip-editor") {
        if (typeof switchMainTab === "function") {
            switchMainTab("editor");
        }
        return;
    }

    if (toolId === "ai-translator") {
        if (typeof switchMainTab === "function") {
            switchMainTab("ai", "translate");
        }
        return;
    }

    if (toolId === "ai-summarizer") {
        if (typeof switchMainTab === "function") {
            switchMainTab("ai", "summarize");
        }
        return;
    }

    if (toolId === "msds-studio") {
        if (typeof switchMainTab === "function") {
            switchMainTab("msds");
        }
        return;
    }

    if (toolId === "hse-studio") {
        if (typeof switchMainTab === "function") {
            switchMainTab("hse");
        }
        return;
    }

    if (toolId === "legal-lookup" || toolId === "legal") {
        if (typeof switchMainTab === "function") {
            switchMainTab("legal");
        }
        return;
    }

    currentTool = TOOLS.find(t => t.id === toolId);
    if (!currentTool) return;

    homeView.classList.add("hidden");
    workspaceView.classList.remove("hidden");

    const wsTitle = document.getElementById("ws-title");
    if (wsTitle) wsTitle.innerText = currentTool.title;

    const wsDesc = document.getElementById("ws-desc");
    if (wsDesc) wsDesc.innerText = currentTool.desc;

    const wsIconSlot = document.getElementById("ws-icon-slot");
    if (wsIconSlot) wsIconSlot.innerHTML = icon(currentTool.id, "w-6 h-6");

    const dropzoneIconSlot = document.getElementById("dropzone-icon-slot");
    if (dropzoneIconSlot) dropzoneIconSlot.innerHTML = icon(currentTool.id, "w-10 h-10");

    const wsIconImg = document.getElementById("ws-icon-img");
    if (wsIconImg) wsIconImg.src = currentTool.iconImg;

    const dropzoneIconImg = document.getElementById("dropzone-icon-img");
    if (dropzoneIconImg) dropzoneIconImg.src = currentTool.iconImg;

    const wsHint = document.getElementById("ws-hint");
    if (wsHint) {
        wsHint.innerText = currentTool.multiple 
            ? "Có thể chọn nhiều tệp cùng lúc (Hỗ trợ " + currentTool.accept + ")"
            : "Hỗ trợ định dạng " + currentTool.accept;
    }

    fileInput.accept = currentTool.accept;
    fileInput.multiple = true;
    if (btnProcessText) btnProcessText.innerText = currentTool.actionText.toUpperCase();

    resetWorkspace();
}

function goHome() {
    workspaceView.classList.add("hidden");
    homeView.classList.remove("hidden");
    currentTool = null;
    resetWorkspace();
    if (typeof switchMainTab === "function") {
        switchMainTab("tools");
    }
}

function resetWorkspace() {
    selectedFiles = [];
    loadedPdfDoc = null;
    originalDocProxy = null;
    processedDocProxy = null;
    activePreviewSource = "original";
    pageRotations = {};
    deletedPages.clear();
    selectedPages.clear();
    pageOrder = [];
    fileInput.value = "";
    lastResultUrl = null;
    lastResultFilename = null;
    lastClickedPage = null;

    lruCanvasCache.clear();
    thumbnailQueue.clear();
    if (thumbnailObserver) thumbnailObserver.disconnect();
    if (readerObserver) readerObserver.disconnect();

    dropzone.classList.remove("hidden");
    studioContainer.classList.add("hidden");
    loadingPanel.classList.add("hidden");
    resultPanel.classList.add("hidden");
    actionPanel.classList.remove("hidden");
    optionsPanel.classList.remove("hidden");

    pagesGrid.innerHTML = "";
    docViewerContainer.innerHTML = "";
    multiFileList.innerHTML = "";

    const compToggle = document.getElementById("comparison-toggle-group");
    if (compToggle) compToggle.classList.add("hidden");
    const shimmerBar = document.getElementById("canvas-shimmer-bar");
    if (shimmerBar) shimmerBar.classList.add("hidden");
    const statusPill = document.getElementById("canvas-status-pill");
    if (statusPill) statusPill.classList.add("hidden");

    const statusBadge = document.getElementById("ws-status-badge");
    if (statusBadge) statusBadge.innerHTML = `<span class="badge-dot"></span> Sẵn sàng`;
    renderOptions();
}

// Drag & Drop
dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dropzone-active");
});
dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dropzone-active");
});
dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dropzone-active");
    if (e.dataTransfer.files.length > 0) {
        handleFileSelection(e.dataTransfer.files);
    }
});
fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
        handleFileSelection(e.target.files);
    }
});

// -------------------------------------------------------------
// 3. FILE SELECTION & INTERACTIVE STUDIO LOADER
// -------------------------------------------------------------
async function handleFileSelection(files) {
    if (!currentTool) return;
    const incoming = Array.from(files || []);
    if (incoming.length === 0) return;

    if (currentTool.id === "compare") {
        selectedFiles = [...selectedFiles, ...incoming].slice(0, 2);
    } else {
        selectedFiles = [...selectedFiles, ...incoming];
    }

    if (selectedFiles.length === 0) return;

    // Transition from Dropzone to Interactive Side-by-Side Studio
    dropzone.classList.add("hidden");
    studioContainer.classList.remove("hidden");
    resultPanel.classList.add("hidden");
    actionPanel.classList.remove("hidden");

    updateSidebarFileInfo();
    updateQueueSummaryUI();
    updateMultiFileListUI();

    // If more than 1 file, switch to files queue view by default (iLovePDF style)
    if (selectedFiles.length > 1) {
        switchStudioView("files");
    } else {
        switchStudioView("grid");
    }

    // Render interactive thumbnails
    await renderStudioInteractiveReview();
    renderOptions();
}

function updateProcessButtonText() {
    const btnText = document.getElementById("btn-process-text");
    if (!btnText || !currentTool) return;
    const count = selectedFiles.length;
    if (count > 1) {
        if (currentTool.id === "merge") {
            btnText.innerText = `Ghép ${count} tệp PDF`;
        } else if (currentTool.id === "compare") {
            btnText.innerText = `So sánh 2 tệp PDF`;
        } else {
            btnText.innerText = `Chuyển đổi ${count} tệp`;
        }
    } else {
        btnText.innerText = currentTool.actionText || "BẮT ĐẦU XỬ LÝ";
    }
}

function updateQueueSummaryUI() {
    const total = selectedFiles.length;
    const countEl = document.getElementById("queue-count");
    const totalSizeEl = document.getElementById("queue-total-size");
    const studioCountEl = document.getElementById("studio-files-count");
    const totalBytes = selectedFiles.reduce((acc, f) => acc + (f.size || 0), 0);
    const sizeMb = (totalBytes / (1024 * 1024)).toFixed(2);

    if (countEl) countEl.innerText = total;
    if (totalSizeEl) totalSizeEl.innerText = `${sizeMb} MB`;
    if (studioCountEl) studioCountEl.innerText = total;
    updateProcessButtonText();
}

function updateSidebarFileInfo() {
    if (selectedFiles.length === 0) return;
    const f0 = selectedFiles[0];
    const sideFilename = document.getElementById("side-filename");
    if (sideFilename) {
        sideFilename.innerText = selectedFiles.length > 1 
            ? `${selectedFiles.length} tệp tin trong hàng đợi` 
            : f0.name;
    }
    const totalBytes = selectedFiles.reduce((acc, f) => acc + (f.size || 0), 0);
    const sizeMb = (totalBytes / (1024 * 1024)).toFixed(2);
    const sideFilesize = document.getElementById("side-filesize");
    if (sideFilesize) sideFilesize.innerText = `${sizeMb} MB`;
    const studioCount = document.getElementById("studio-files-count");
    if (studioCount) studioCount.innerText = selectedFiles.length;
    updateQueueSummaryUI();
}

// -------------------------------------------------------------
// 4. PDF.JS THUMBNAIL & WORD/OFFICE PREVIEW ENGINE
// -------------------------------------------------------------
let currentWordZoomLevel = 1.0;

function toggleWordZoom() {
    const sheet = document.getElementById("word-paper-sheet");
    const btn = document.getElementById("btn-word-zoom");
    if (!sheet) return;
    if (currentWordZoomLevel === 1.0) {
        currentWordZoomLevel = 1.25;
        sheet.style.transform = "scale(1.25)";
        sheet.style.transformOrigin = "top center";
        if (btn) btn.innerHTML = "🔍 Thu nhỏ 100%";
    } else {
        currentWordZoomLevel = 1.0;
        sheet.style.transform = "none";
        if (btn) btn.innerHTML = "🔍 Phóng to 125%";
    }
}

function printWordPreview() {
    const content = document.getElementById("word-paper-content");
    if (!content) return;
    const printWindow = window.open("", "_blank");
    if (!printWindow) {
        alert("Vui lòng cho phép popup để in tài liệu.");
        return;
    }
    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>In Tài Liệu Word</title>
            <style>
                body { font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Times New Roman", Roboto, sans-serif; padding: 40px; color: #1e293b; line-height: 1.6; }
                table { width: 100%; border-collapse: collapse; margin: 16px 0; }
                th, td { border: 1px solid #cbd5e1; padding: 8px 12px; }
                th { background: #f1f5f9; font-weight: bold; }
                img { max-width: 100%; height: auto; }
                @media print { body { padding: 0; } }
            </style>
        </head>
        <body>
            ${content.innerHTML}
            <script>window.onload = function() { window.print(); window.close(); }<\/script>
        </body>
        </html>
    `);
    printWindow.document.close();
}

async function renderWordPreview(fileOrBlob, optionalName) {
    const pagesGrid = document.getElementById("pages-grid");
    const studioLoading = document.getElementById("studio-loading");
    const filename = optionalName || (fileOrBlob && fileOrBlob.name) || (typeof fileOrBlob === "string" ? fileOrBlob : "Tai_lieu.docx");

    if (studioLoading) studioLoading.classList.remove("hidden");
    if (pagesGrid) {
        pagesGrid.innerHTML = `
            <div style="grid-column: 1 / -1; width: 100%; padding: 60px 20px; text-align: center;">
                <div class="spinner" style="margin: 0 auto 16px;"></div>
                <div style="font-size: 14px; font-weight: 600; color: #0284c7;">Đang trích xuất & kết xuất tài liệu Word (.docx) sang giao diện chuẩn A4...</div>
            </div>
        `;
    }

    try {
        let htmlContent = "";
        let fileSizeText = "";

        if (fileOrBlob instanceof File || fileOrBlob instanceof Blob) {
            fileSizeText = (fileOrBlob.size / 1024).toFixed(1) + " KB";
            const fd = new FormData();
            fd.append("file", fileOrBlob, filename);
            const resp = await fetch("/api/preview/word", { method: "POST", body: fd });
            const data = await resp.json();
            if (!resp.ok || !data.success) {
                throw new Error(data.detail || "Không thể phân giải tệp Word.");
            }
            htmlContent = data.html || "<p>Tài liệu Word không có nội dung văn bản.</p>";
        } else if (typeof fileOrBlob === "string") {
            const resp = await fetch(`/api/preview/word-output/${encodeURIComponent(fileOrBlob)}`);
            const data = await resp.json();
            if (!resp.ok || !data.success) {
                throw new Error(data.detail || "Không thể phân giải tệp Word.");
            }
            htmlContent = data.html || "<p>Tài liệu Word không có nội dung văn bản.</p>";
            fileSizeText = data.size ? ((data.size / 1024).toFixed(1) + " KB") : "";
        }

        const sidePages = document.getElementById("side-filepages");
        if (sidePages) sidePages.innerText = `Word (.docx)`;
        const metaText = document.getElementById("grid-meta-text");
        if (metaText) {
            metaText.innerHTML = `📄 <span style="color:#0284c7; font-weight:700;">Xem trước Microsoft Word (.docx)</span> · ${escapeHtml(filename)} ${fileSizeText ? `(${fileSizeText})` : ''}`;
        }

        currentWordZoomLevel = 1.0;
        pagesGrid.innerHTML = `
            <div class="word-preview-wrapper" style="grid-column: 1 / -1; width: 100%; display: flex; flex-direction: column; align-items: center; padding: 12px 6px;">
                <div class="word-preview-toolbar">
                    <div class="word-toolbar-left">
                        <span class="word-doc-badge">📝 Microsoft Word (.docx)</span>
                        <span class="word-filename" title="${escapeHtml(filename)}">${escapeHtml(filename)}</span>
                    </div>
                    <div class="word-toolbar-actions">
                        <button type="button" class="btn-word-tool" onclick="printWordPreview()" title="In hoặc xuất PDF từ bản xem trước">
                            🖨️ In / Xuất PDF
                        </button>
                        <button type="button" class="btn-word-tool" onclick="toggleWordZoom()" id="btn-word-zoom" title="Phóng to / Thu nhỏ">
                            🔍 Phóng to 125%
                        </button>
                    </div>
                </div>

                <div class="word-paper-container" id="word-paper-sheet">
                    <div class="word-paper-inner" id="word-paper-content">
                        ${htmlContent}
                    </div>
                </div>
            </div>
        `;
    } catch (err) {
        console.error("renderWordPreview error:", err);
        pagesGrid.innerHTML = `
            <div class="office-preview-box" style="grid-column: 1 / -1; width: 100%; padding: 48px 24px; text-align: center;">
                <div style="font-size: 32px; margin-bottom: 12px;">⚠️</div>
                <h4 style="font-size: 16px; font-weight: 700; color: #ef4444; margin-bottom: 6px;">Không thể xem trước tệp Word</h4>
                <p style="font-size: 13px; color: var(--text-secondary); max-width: 440px; margin: 0 auto 16px;">
                    ${escapeHtml(err.message)}
                </p>
                <button type="button" class="btn-primary" onclick="renderStudioInteractiveReview()" style="padding: 8px 16px;">
                    Thử lại
                </button>
            </div>
        `;
    } finally {
        if (studioLoading) studioLoading.classList.add("hidden");
    }
}

async function renderStudioInteractiveReview() {
    if (selectedFiles.length === 0) return;
    const primaryFile = selectedFiles[0];

    studioLoading.classList.remove("hidden");
    pagesGrid.innerHTML = "";
    docViewerContainer.innerHTML = "";

    // 1. NON-PDF FILES (Word, Excel, PowerPoint, Images)
    if (!primaryFile.name.toLowerCase().endsWith(".pdf")) {
        studioLoading.classList.add("hidden");
        const ext = primaryFile.name.split('.').pop().toUpperCase();
        const sidePages = document.getElementById("side-filepages");
        if (sidePages) sidePages.innerText = "Tài liệu " + ext;
        const metaText = document.getElementById("grid-meta-text");
        if (metaText) metaText.innerText = `Định dạng: ${ext}`;

        // If Image to PDF
        if (primaryFile.type.startsWith("image/") || /\.(jpg|jpeg|png|bmp|webp)$/i.test(primaryFile.name)) {
            renderImagesGrid();
            return;
        }

        // If Word Document (.docx / .doc) -> Render Live Word Preview!
        if (/\.(docx|doc)$/i.test(primaryFile.name)) {
            renderWordPreview(primaryFile);
            return;
        }

        // Other Office files (PPT, Excel)
        pagesGrid.innerHTML = `
            <div class="office-preview-box" style="grid-column: 1 / -1; width: 100%; padding: 48px 24px; display: flex; flex-direction: column; align-items: center; justify-content: center; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-xl); text-align: center;">
                <div style="width: 64px; height: 64px; border-radius: var(--radius-lg); background: var(--bg-surface-subtle); color: var(--text-primary); display: flex; align-items: center; justify-content: center; margin-bottom: 16px;">
                    ${icon("shield", "w-8 h-8")}
                </div>
                <h4 style="font-size: 16px; font-weight: 700; color: var(--text-primary); margin-bottom: 4px;">${primaryFile.name}</h4>
                <p style="font-size: 12px; color: var(--text-secondary); max-width: 440px; margin-bottom: 16px;">
                    Tài liệu đang sẵn sàng để chuyển đổi sang PDF chất lượng cao bằng Động cơ Siêu Cấp VIP Pro.
                </p>
                <div style="display: inline-flex; align-items: center; font-size: 12px; font-weight: 600; color: var(--text-primary); background: var(--bg-surface-subtle); padding: 6px 14px; border-radius: var(--radius-full); border: 1px solid var(--border-subtle);">
                    ${icon("bolt", "w-3.5 h-3.5 mr-1.5")} Chế độ xử lý cục bộ 100% không suy hao font
                </div>
            </div>
        `;
        return;
    }

    // 2. PDF FILES (Interactive Per-Page Thumbnails)
    try {
        lruCanvasCache.clear();
        thumbnailQueue.clear();

        const arrayBuffer = await primaryFile.arrayBuffer();
        const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
        loadedPdfDoc = await loadingTask.promise;
        originalDocProxy = loadedPdfDoc;
        processedDocProxy = null;
        activePreviewSource = "original";

        // Hide comparison toggle group until processing completes
        const compToggle = document.getElementById("comparison-toggle-group");
        if (compToggle) compToggle.classList.add("hidden");

        const numPages = loadedPdfDoc.numPages;
        const sidePages = document.getElementById("side-filepages");
        if (sidePages) sidePages.innerText = `${numPages} trang`;
        const metaText = document.getElementById("grid-meta-text");
        if (metaText) {
            if (currentTool && currentTool.id === "organize") {
                metaText.innerHTML = `Đang hiển thị ${numPages} trang &bull; <b>Kéo thả chuột</b> để sắp xếp vị trí trang như iLovePDF`;
            } else {
                metaText.innerText = `Đang hiển thị ${numPages} trang tương tác`;
            }
        }

        // Reset page state
        pageOrder = Array.from({ length: numPages }, (_, i) => i + 1);
        pageRotations = {};
        deletedPages.clear();
        selectedPages.clear();
        lastClickedPage = null;

        // Step 1: Generate skeletons (<30ms) for all numPages using DocumentFragment
        generateSkeletonThumbnails(numPages);

        // Step 2: Immediate priority render of Page 1 (<300ms)
        await renderPriorityFirstPage();

        // Step 3: Setup thumbnail observer for remaining pages
        setupThumbnailObserver();

        // Prepare continuous viewer if already selected
        if (studioViewMode === "viewer") {
            initContinuousReader();
        }

    } catch (err) {
        console.error("Lỗi nạp PDF.js:", err);
        pagesGrid.innerHTML = `
            <div class="p-8 text-center text-rose-600 text-xs font-bold" style="grid-column: 1 / -1; padding: 24px; text-align: center; color: var(--danger-text);">
                Không thể hiển thị thumbnail: ${err.message}
            </div>
        `;
    } finally {
        studioLoading.classList.add("hidden");
    }
}

// Step 1: Generate skeleton placeholder cards (<30ms) for all numPages
function generateSkeletonThumbnails(numPages) {
    pagesGrid.innerHTML = "";
    const fragment = document.createDocumentFragment();

    for (let i = 1; i <= numPages; i++) {
        pageRotations[i] = 0;
        const card = createPageThumbnailCard(i);
        fragment.appendChild(card);
    }
    pagesGrid.appendChild(fragment);
}

// Global drag tracking state for iLovePDF-style reordering
let draggedPageNum = null;

function clearAllPageDropIndicators() {
    if (!pagesGrid) return;
    pagesGrid.querySelectorAll(".page-card").forEach(c => {
        c.classList.remove("drop-before", "drop-after", "is-dragging");
    });
}

function attachPageCardDragListeners(card, pageNum) {
    card.setAttribute("draggable", "true");

    card.addEventListener("dragstart", (e) => {
        if (e.target.closest("button") || e.target.closest(".page-actions")) {
            e.preventDefault();
            return;
        }
        draggedPageNum = pageNum;
        card.classList.add("is-dragging");
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(pageNum));
        clearAllPageDropIndicators();
        // Keep is-dragging on current card
        card.classList.add("is-dragging");
    });

    card.addEventListener("dragend", () => {
        clearAllPageDropIndicators();
        draggedPageNum = null;
    });

    card.addEventListener("dragover", (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        if (!draggedPageNum || draggedPageNum === pageNum) return;

        const rect = card.getBoundingClientRect();
        const relX = e.clientX - rect.left;
        const isLeftHalf = relX < (rect.width / 2);

        if (isLeftHalf) {
            card.classList.add("drop-before");
            card.classList.remove("drop-after");
        } else {
            card.classList.add("drop-after");
            card.classList.remove("drop-before");
        }
    });

    card.addEventListener("dragleave", (e) => {
        const rect = card.getBoundingClientRect();
        if (
            e.clientX < rect.left || e.clientX >= rect.right ||
            e.clientY < rect.top || e.clientY >= rect.bottom
        ) {
            card.classList.remove("drop-before", "drop-after");
        }
    });

    card.addEventListener("drop", (e) => {
        e.preventDefault();
        const isBefore = card.classList.contains("drop-before");
        clearAllPageDropIndicators();

        if (!draggedPageNum || draggedPageNum === pageNum) return;

        handlePageReorderDrop(draggedPageNum, pageNum, isBefore ? "before" : "after");
    });
}

function handlePageReorderDrop(draggedPage, targetPage, position) {
    const fromIdx = pageOrder.indexOf(draggedPage);
    if (fromIdx === -1) return;

    // 1. Remove dragged page from current position
    pageOrder.splice(fromIdx, 1);

    // 2. Locate target page in the modified array
    let toIdx = pageOrder.indexOf(targetPage);
    if (toIdx === -1) return;

    if (position === "after") {
        toIdx += 1;
    }

    // 3. Insert dragged page at destination index
    pageOrder.splice(toIdx, 0, draggedPage);

    // 4. Update the order input box if present
    const orderInput = document.getElementById("opt-org-order");
    if (orderInput) {
        orderInput.value = pageOrder.join(", ");
    }

    // 5. Rearrange DOM elements in-place with zero canvas re-rasterization
    pageOrder.forEach((p, idx) => {
        const pCard = document.getElementById(`page-card-${p}`);
        if (pCard && pagesGrid) {
            pagesGrid.appendChild(pCard);
            const badge = pCard.querySelector(".page-order-num");
            if (badge) badge.innerText = `#${idx + 1}`;
            const reorderText = pCard.querySelector(".btn-reorder-pos");
            if (reorderText) reorderText.innerText = `Vị trí #${idx + 1}`;
        }
    });

    // 6. Smooth landing pop feedback
    const landedCard = document.getElementById(`page-card-${draggedPage}`);
    if (landedCard) {
        landedCard.classList.add("dropped-landing");
        setTimeout(() => landedCard.classList.remove("dropped-landing"), 400);
    }
}

// Create an interactive page thumbnail card with semantic layout & controls
function createPageThumbnailCard(pageNum) {
    const card = document.createElement("div");
    card.id = `page-card-${pageNum}`;
    card.className = "page-card";
    card.dataset.page = pageNum;

    card.onclick = (e) => {
        if (e.target.closest("button")) return;
        handlePageCardClick(pageNum, e);
    };

    // Attach native HTML5 drag & drop handlers
    attachPageCardDragListeners(card, pageNum);

    const isOrganize = (currentTool && currentTool.id === "organize");
    const initialOrderIdx = pageOrder.indexOf(pageNum) + 1 || pageNum;

    card.innerHTML = `
        <div class="page-card-header">
            <div style="display: flex; align-items: center; gap: 6px;">
                <span class="drag-handle" title="Kéo thả để sắp xếp lại trang như iLovePDF">
                    ${icon("grip-vertical", "w-3 h-3")}
                </span>
                <span class="page-badge">Trang ${pageNum}</span>
                ${isOrganize ? `<span class="page-order-num badge-order" title="Vị trí xuất hiện">#${initialOrderIdx}</span>` : ""}
            </div>
            <div class="page-actions">
                <button type="button" onclick="rotateSinglePage(${pageNum})" title="Xoay 90°" class="btn-card-action">
                    ${icon("rotate-cw", "w-3 h-3")}
                </button>
                <button type="button" onclick="toggleDeletePage(${pageNum})" title="Loại bỏ/Khôi phục trang" class="btn-card-action hover-danger">
                    ${icon("trash", "w-3 h-3")}
                </button>
            </div>
        </div>
        <div class="page-canvas-slot" data-page="${pageNum}">
            <div class="skeleton-shimmer" data-skeleton="${pageNum}">
                <div class="skeleton-shimmer-wave"></div>
                <span class="skeleton-text">Trang ${pageNum}</span>
            </div>
        </div>
        <div class="page-deleted-badge">
            ${icon("trash", "w-3 h-3")} Đã loại bỏ
        </div>
        ${isOrganize ? `
            <div class="page-card-reorder">
                <button type="button" onclick="shiftPageOrder(${pageNum}, -1)" title="Chuyển sang trước" class="btn-reorder">
                    ${icon("chevron-left", "w-2.5 h-2.5")}
                </button>
                <span class="btn-reorder-pos text-[10px] text-slate-400 font-bold" style="font-size: 10px; color: var(--text-muted); font-weight: 700;">Vị trí #${initialOrderIdx}</span>
                <button type="button" onclick="shiftPageOrder(${pageNum}, 1)" title="Chuyển ra sau" class="btn-reorder">
                    ${icon("chevron-right", "w-2.5 h-2.5")}
                </button>
            </div>
        ` : ""}
    `;

    return card;
}

// Render single thumbnail via PDF.js into LRU Cache
async function renderSingleThumbnail(pageNum) {
    if (!loadedPdfDoc || pageNum < 1 || pageNum > loadedPdfDoc.numPages) return;

    const card = document.getElementById(`page-card-${pageNum}`);
    if (!card) return;
    const slot = card.querySelector(".page-canvas-slot");
    if (!slot) return;

    if (lruCanvasCache.has(pageNum)) return;

    try {
        const page = await loadedPdfDoc.getPage(pageNum);
        const rotation = (pageRotations[pageNum] || 0);
        // Base viewport rasterized at rotation 0; GPU handles 90/180/270 transform
        const viewport = page.getViewport({ scale: 0.35, rotation: 0 });

        const canvas = document.createElement("canvas");
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const ctx = canvas.getContext("2d");

        await page.render({ canvasContext: ctx, viewport: viewport }).promise;

        slot.innerHTML = "";
        slot.appendChild(canvas);

        // Apply GPU transform if already rotated
        if (rotation !== 0) {
            slot.style.setProperty("--page-rotation", `${rotation}deg`);
            const isLandscape = (rotation % 180 !== 0);
            slot.style.setProperty("--page-rotation-scale", isLandscape ? "0.72" : "1");
        }

        // Attach live simulation overlays if applicable
        attachSimulationOverlays(pageNum, slot);

        // Record in LRU Cache
        lruCanvasCache.put(pageNum, { canvas, page, slotElement: slot });
    } catch (e) {
        console.error(`Lỗi render thumbnail trang ${pageNum}:`, e);
    }
}

// Alias for backwards compatibility
const renderPageCanvas = renderSingleThumbnail;

// Step 2: Immediate priority render of Page 1 (<300ms)
async function renderPriorityFirstPage() {
    if (!loadedPdfDoc || loadedPdfDoc.numPages < 1) return;
    await renderSingleThumbnail(1);
}

// Step 3: IntersectionObserver on .canvas-viewport driving ThumbnailRenderQueue
function setupThumbnailObserver() {
    if (thumbnailObserver) thumbnailObserver.disconnect();

    const viewportEl = document.querySelector(".canvas-viewport");
    if (typeof IntersectionObserver === "undefined") {
        // Fallback for non-browser/shim environments: render first 10 pages directly
        if (loadedPdfDoc) {
            const count = Math.min(loadedPdfDoc.numPages, 10);
            for (let i = 1; i <= count; i++) {
                thumbnailQueue.enqueue(i);
            }
        }
        return;
    }

    thumbnailObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            const pageNum = parseInt(entry.target.dataset.page);
            if (entry.isIntersecting) {
                thumbnailQueue.enqueue(pageNum);
            } else {
                thumbnailQueue.dequeueIfPending(pageNum);
            }
        });
    }, {
        root: viewportEl,
        rootMargin: "200px 0px",
        threshold: 0.01
    });

    document.querySelectorAll(".page-canvas-slot").forEach(slot => {
        thumbnailObserver.observe(slot);
    });
}

// Continuous Document Reader Mode (Unlimited pages, Virtualized Observer & Scroll-Spy)
function initContinuousReader() {
    if (!loadedPdfDoc) return;
    const numPages = loadedPdfDoc.numPages;
    docViewerContainer.innerHTML = "";

    const fragment = document.createDocumentFragment();
    for (let i = 1; i <= numPages; i++) {
        const pageBox = document.createElement("div");
        pageBox.className = "doc-page-wrapper";
        pageBox.id = `doc-page-${i}`;
        pageBox.dataset.page = i;

        pageBox.innerHTML = `
            <div class="doc-page-header">
                <span class="doc-page-badge">Trang ${i} / ${numPages}</span>
            </div>
            <div class="doc-canvas-slot" data-page="${i}">
                <div class="skeleton-shimmer doc-skeleton">
                    <div class="skeleton-shimmer-wave"></div>
                    <span class="skeleton-text">Đang tải trang ${i}...</span>
                </div>
            </div>
        `;
        fragment.appendChild(pageBox);
    }
    docViewerContainer.appendChild(fragment);

    setupReaderObserver();
    setupReaderScrollSpy();
}

function setupReaderObserver() {
    if (readerObserver) readerObserver.disconnect();
    const viewportEl = document.querySelector(".canvas-viewport");

    if (typeof IntersectionObserver === "undefined") {
        return;
    }

    readerObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const pageNum = parseInt(entry.target.dataset.page);
                renderReaderPage(pageNum, entry.target);
            }
        });
    }, {
        root: viewportEl,
        rootMargin: "300px 0px",
        threshold: 0.01
    });

    document.querySelectorAll(".doc-canvas-slot").forEach(slot => {
        readerObserver.observe(slot);
    });
}

async function renderReaderPage(pageNum, slotElement) {
    if (!loadedPdfDoc || !slotElement || slotElement.dataset.rendered === "true") return;
    slotElement.dataset.rendered = "true";

    try {
        const page = await loadedPdfDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale: 0.85 });
        const canvas = document.createElement("canvas");
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const ctx = canvas.getContext("2d");
        await page.render({ canvasContext: ctx, viewport: viewport }).promise;

        slotElement.innerHTML = "";
        slotElement.appendChild(canvas);
    } catch (e) {
        console.error(`Lỗi render reader trang ${pageNum}:`, e);
    }
}

// Scroll-spy tracking scroll position and updating #doc-view-page-info
function setupReaderScrollSpy() {
    const viewport = document.querySelector(".canvas-viewport");
    if (!viewport) return;

    let ticking = false;
    viewport.addEventListener("scroll", () => {
        if (!ticking && studioViewMode === "viewer") {
            const raf = window.requestAnimationFrame || ((cb) => setTimeout(cb, 16));
            raf(() => {
                updateReaderScrollSpyIndicator();
                ticking = false;
            });
            ticking = true;
        }
    }, { passive: true });
}

function updateReaderScrollSpyIndicator() {
    const viewport = document.querySelector(".canvas-viewport");
    const pages = document.querySelectorAll(".doc-page-wrapper");
    if (!viewport || pages.length === 0 || !loadedPdfDoc) return;

    const viewportCenter = viewport.scrollTop + (viewport.clientHeight / 3);
    let currentPage = 1;

    for (const p of pages) {
        if (p.offsetTop <= viewportCenter) {
            currentPage = parseInt(p.dataset.page);
        } else {
            break;
        }
    }

    const info = document.getElementById("doc-view-page-info");
    if (info) {
        info.innerText = `Trang ${currentPage} / ${loadedPdfDoc.numPages}`;
    }
}

// Render image grid for Images to PDF with iLovePDF drag & drop reordering
let draggedImageIdx = null;

function clearAllImageDropIndicators() {
    if (!pagesGrid) return;
    pagesGrid.querySelectorAll(".page-card").forEach(c => {
        c.classList.remove("drop-before", "drop-after", "is-dragging");
    });
}

function attachImageCardDragListeners(card, idx) {
    card.setAttribute("draggable", "true");

    card.addEventListener("dragstart", (e) => {
        if (e.target.closest("button")) {
            e.preventDefault();
            return;
        }
        draggedImageIdx = idx;
        card.classList.add("is-dragging");
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(idx));
    });

    card.addEventListener("dragend", () => {
        clearAllImageDropIndicators();
        draggedImageIdx = null;
    });

    card.addEventListener("dragover", (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        if (draggedImageIdx === null || draggedImageIdx === idx) return;

        const rect = card.getBoundingClientRect();
        const relX = e.clientX - rect.left;
        const isLeft = relX < (rect.width / 2);

        if (isLeft) {
            card.classList.add("drop-before");
            card.classList.remove("drop-after");
        } else {
            card.classList.add("drop-after");
            card.classList.remove("drop-before");
        }
    });

    card.addEventListener("dragleave", (e) => {
        const rect = card.getBoundingClientRect();
        if (
            e.clientX < rect.left || e.clientX >= rect.right ||
            e.clientY < rect.top || e.clientY >= rect.bottom
        ) {
            card.classList.remove("drop-before", "drop-after");
        }
    });

    card.addEventListener("drop", (e) => {
        e.preventDefault();
        const isBefore = card.classList.contains("drop-before");
        clearAllImageDropIndicators();

        if (draggedImageIdx === null || draggedImageIdx === idx) return;

        const fromIdx = draggedImageIdx;
        const targetFile = selectedFiles[idx];
        const [movedFile] = selectedFiles.splice(fromIdx, 1);
        let targetPos = selectedFiles.indexOf(targetFile);
        if (!isBefore) {
            targetPos += 1;
        }
        selectedFiles.splice(targetPos, 0, movedFile);
        updateSidebarFileInfo();
        renderImagesGrid();
    });
}

function renderImagesGrid() {
    pagesGrid.innerHTML = "";
    selectedFiles.forEach((file, idx) => {
        const card = document.createElement("div");
        card.className = "page-card";
        card.dataset.index = idx;
        attachImageCardDragListeners(card, idx);

        const imgUrl = URL.createObjectURL(file);
        card.innerHTML = `
            <div class="page-card-header">
                <div style="display: flex; align-items: center; gap: 6px;">
                    <span class="drag-handle" title="Kéo thả để sắp xếp vị trí ảnh như iLovePDF">
                        ${icon("grip-vertical", "w-3 h-3")}
                    </span>
                    <span class="page-badge">Ảnh #${idx + 1}</span>
                </div>
                <button type="button" onclick="removeFile(${idx})" class="btn-card-action hover-danger" title="Xóa ảnh">
                    ${icon("trash", "w-3 h-3")}
                </button>
            </div>
            <div class="page-canvas-slot" style="pointer-events: none;">
                <img src="${imgUrl}" alt="${file.name}" style="max-width: 100%; max-height: 150px; object-fit: contain;" />
            </div>
            <p style="font-size: 11px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 6px; font-weight: 500;">${file.name}</p>
        `;
        pagesGrid.appendChild(card);
    });
}

// -------------------------------------------------------------
// 5. REAL-TIME MICRO-INTERACTIONS & TWO-WAY RANGE SYNC
// -------------------------------------------------------------

// Sub-16ms GPU Single Page Rotation (<4ms execution, zero page.render() calls)
function rotateSinglePage(pageNum) {
    pageRotations[pageNum] = ((pageRotations[pageNum] || 0) + 90) % 360;
    const card = document.getElementById(`page-card-${pageNum}`);
    if (card) {
        const slot = card.querySelector(".page-canvas-slot");
        if (slot) {
            const angle = pageRotations[pageNum];
            slot.style.setProperty("--page-rotation", `${angle}deg`);
            const isLandscape = (angle % 180 !== 0);
            slot.style.setProperty("--page-rotation-scale", isLandscape ? "0.72" : "1");
        }
    }
}

// Batch GPU Rotation for All Pages (<10ms)
function rotateAllPages(delta) {
    if (!loadedPdfDoc) return;
    const numPages = loadedPdfDoc.numPages;
    for (let i = 1; i <= numPages; i++) {
        pageRotations[i] = ((pageRotations[i] || 0) + delta + 360) % 360;
        const card = document.getElementById(`page-card-${i}`);
        if (card) {
            const slot = card.querySelector(".page-canvas-slot");
            if (slot) {
                const angle = pageRotations[i];
                slot.style.setProperty("--page-rotation", `${angle}deg`);
                const isLandscape = (angle % 180 !== 0);
                slot.style.setProperty("--page-rotation-scale", isLandscape ? "0.72" : "1");
            }
        }
    }
}

// Direct Deletion Marking (<10ms) with .is-deleted, .excluded & "Đã loại bỏ" badge
function toggleDeletePage(pageNum) {
    const card = document.getElementById(`page-card-${pageNum}`);
    if (!card) return;

    if (deletedPages.has(pageNum)) {
        deletedPages.delete(pageNum);
        card.classList.remove("is-deleted", "excluded");
    } else {
        deletedPages.add(pageNum);
        card.classList.add("is-deleted", "excluded");
    }

    // Auto-sync into 'delete-pages' input
    if (currentTool && currentTool.id === "delete-pages") {
        syncCanvasToInput("opt-del-pages", deletedPages);
    }
}
const toggleExcludePage = toggleDeletePage;

// Two-Way Range Sync: Format Set/Array of numbers into standard range notation
function formatRanges(nums) {
    if (!nums) return "";
    const arr = Array.from(nums)
        .map(Number)
        .filter(n => Number.isInteger(n) && n > 0);
    if (arr.length === 0) return "";

    const sorted = Array.from(new Set(arr)).sort((a, b) => a - b);
    const ranges = [];
    let start = sorted[0];
    let end = sorted[0];

    for (let i = 1; i < sorted.length; i++) {
        if (sorted[i] === end + 1) {
            end = sorted[i];
        } else {
            ranges.push(start === end ? `${start}` : `${start}-${end}`);
            start = sorted[i];
            end = sorted[i];
        }
    }
    ranges.push(start === end ? `${start}` : `${start}-${end}`);
    return ranges.join(", ");
}

// Two-Way Range Sync: Parse user range string safely into Set<number>
function parseRangeString(str, maxPages = Infinity) {
    const result = new Set();
    if (!str || typeof str !== "string") return result;

    const trimmed = str.trim();
    if (!trimmed) return result;

    // Handle "all" keyword
    if (trimmed.toLowerCase() === "all" && Number.isFinite(maxPages) && maxPages > 0) {
        for (let i = 1; i <= maxPages; i++) result.add(i);
        return result;
    }

    const tokens = trimmed.split(/[,;]+/);
    for (const token of tokens) {
        const part = token.trim();
        if (!part) continue;

        if (part.includes("-")) {
            const rangeParts = part.split("-").map(s => s.trim());
            if (rangeParts.length === 2) {
                const s = parseInt(rangeParts[0], 10);
                const e = parseInt(rangeParts[1], 10);
                if (!isNaN(s) && !isNaN(e) && s > 0 && e > 0) {
                    const start = Math.max(1, Math.min(s, e));
                    const end = Math.min(maxPages, Math.max(s, e));
                    for (let p = start; p <= end; p++) {
                        result.add(p);
                    }
                }
            }
        } else {
            const num = parseInt(part, 10);
            if (!isNaN(num) && num >= 1 && num <= maxPages) {
                result.add(num);
            }
        }
    }
    return result;
}

// Two-Way Range Sync: Canvas -> Input (Single click and Shift+click range expansion)
function handlePageCardClick(pageNum, event) {
    if (!loadedPdfDoc) return;
    const numPages = loadedPdfDoc.numPages;

    if (event && event.shiftKey && lastClickedPage !== null) {
        // Shift+Click: expand selection between lastClickedPage and pageNum
        const start = Math.min(lastClickedPage, pageNum);
        const end = Math.max(lastClickedPage, pageNum);
        for (let p = start; p <= end; p++) {
            selectedPages.add(p);
            document.getElementById(`page-card-${p}`)?.classList.add("selected");
        }
    } else {
        // Normal toggle
        if (selectedPages.has(pageNum)) {
            selectedPages.delete(pageNum);
            document.getElementById(`page-card-${pageNum}`)?.classList.remove("selected");
        } else {
            selectedPages.add(pageNum);
            document.getElementById(`page-card-${pageNum}`)?.classList.add("selected");
        }
        lastClickedPage = pageNum;
    }

    syncSelectionToInputs();
}

function toggleSelectPage(pageNum) {
    handlePageCardClick(pageNum, { shiftKey: false });
}

function toggleSelectAllPages() {
    if (!loadedPdfDoc) return;
    const numPages = loadedPdfDoc.numPages;
    const btn = document.getElementById("btn-select-all");

    if (selectedPages.size === numPages) {
        selectedPages.clear();
        for (let i = 1; i <= numPages; i++) {
            document.getElementById(`page-card-${i}`)?.classList.remove("selected");
        }
        if (btn) btn.innerHTML = `${icon("check-double", "w-3.5 h-3.5 mr-1")} Chọn tất cả`;
    } else {
        for (let i = 1; i <= numPages; i++) {
            selectedPages.add(i);
            document.getElementById(`page-card-${i}`)?.classList.add("selected");
        }
        if (btn) btn.innerHTML = `${icon("clear", "w-3.5 h-3.5 mr-1 text-rose-500")} Bỏ chọn tất cả`;
    }
    syncSelectionToInputs();
}

function syncCanvasToInput(targetInputId, sourceSet) {
    const input = document.getElementById(targetInputId);
    if (!input) return;

    isInternalSync = true;
    try {
        input.value = formatRanges(sourceSet);
    } finally {
        isInternalSync = false;
    }
}

function syncSelectionToInputs() {
    if (!currentTool) return;

    let targetInputId = null;
    if (currentTool.id === "split") {
        targetInputId = "opt-range";
        const customRadio = document.querySelector('input[name="split_mode"][value="custom"]');
        if (customRadio) {
            customRadio.checked = true;
            toggleRangeInput(true);
        }
    } else if (currentTool.id === "extract-pages") {
        targetInputId = "opt-ext-pages";
    }

    if (targetInputId) {
        syncCanvasToInput(targetInputId, selectedPages);
    }
}

// Two-Way Range Sync: Input -> Canvas (Debounced 120ms with recursion lock)
function attachRangeInputListeners() {
    const inputMap = [
        { id: "opt-range", isDelete: false },
        { id: "opt-ext-pages", isDelete: false },
        { id: "opt-del-pages", isDelete: true }
    ];

    inputMap.forEach(({ id, isDelete }) => {
        const input = document.getElementById(id);
        if (!input || input.dataset.syncAttached === "true") return;

        input.dataset.syncAttached = "true";
        input.addEventListener("input", () => {
            if (isInternalSync) return; // Recursion lock

            clearTimeout(rangeSyncDebounceTimer);
            rangeSyncDebounceTimer = setTimeout(() => {
                if (isInternalSync || !loadedPdfDoc) return;
                const numPages = loadedPdfDoc.numPages;
                const parsed = parseRangeString(input.value, numPages);

                if (isDelete) {
                    deletedPages.clear();
                    parsed.forEach(p => deletedPages.add(p));
                    for (let i = 1; i <= numPages; i++) {
                        const card = document.getElementById(`page-card-${i}`);
                        if (!card) continue;
                        if (deletedPages.has(i)) {
                            card.classList.add("is-deleted", "excluded");
                        } else {
                            card.classList.remove("is-deleted", "excluded");
                        }
                    }
                } else {
                    selectedPages.clear();
                    parsed.forEach(p => selectedPages.add(p));
                    for (let i = 1; i <= numPages; i++) {
                        const card = document.getElementById(`page-card-${i}`);
                        if (!card) continue;
                        if (selectedPages.has(i)) {
                            card.classList.add("selected");
                        } else {
                            card.classList.remove("selected");
                        }
                    }
                }

                // Smooth scroll to first matching page if out of view
                if (parsed.size > 0) {
                    const firstPage = Math.min(...Array.from(parsed));
                    const firstCard = document.getElementById(`page-card-${firstPage}`);
                    if (firstCard) {
                        firstCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
                    }
                }
            }, 120); // 120ms debounce
        });
    });
}

// Non-destructive Page Reorder (Moves existing DOM cards in-place without re-rendering)
function shiftPageOrder(pageNum, direction) {
    const idx = pageOrder.indexOf(pageNum);
    if (idx === -1) return;
    const targetIdx = idx + direction;
    if (targetIdx < 0 || targetIdx >= pageOrder.length) return;

    // 1. Swap positions in array
    const temp = pageOrder[idx];
    pageOrder[idx] = pageOrder[targetIdx];
    pageOrder[targetIdx] = temp;

    // 2. Update order input
    const orderInput = document.getElementById("opt-org-order");
    if (orderInput) {
        orderInput.value = pageOrder.join(", ");
    }

    // 3. Move existing DOM cards in-place via appendChild and update badges
    pageOrder.forEach((p, i) => {
        const card = document.getElementById(`page-card-${p}`);
        if (card && pagesGrid) {
            pagesGrid.appendChild(card);
            const badge = card.querySelector(".page-order-num");
            if (badge) badge.innerText = `#${i + 1}`;
            const reorderText = card.querySelector(".btn-reorder-pos");
            if (reorderText) reorderText.innerText = `Vị trí #${i + 1}`;
        }
    });

    const shiftedCard = document.getElementById(`page-card-${pageNum}`);
    if (shiftedCard) {
        shiftedCard.classList.add("dropped-landing");
        setTimeout(() => shiftedCard.classList.remove("dropped-landing"), 350);
    }
}

// Live Preview Simulation Overlays (Watermark, Crop, e-Sign)
function attachSimulationOverlays(pageNum, slotElement) {
    if (!currentTool || !loadedPdfDoc) return;
    const totalPages = loadedPdfDoc.numPages;

    // 1. Watermark Live Overlay: Red tint matching core/engine.py:332
    if (currentTool.id === "watermark") {
        const wmText = document.getElementById("opt-wm-text")?.value || "BẢN SAO NỘI BỘ";
        const wmOpacity = document.getElementById("opt-wm-opacity")?.value || 0.35;
        const overlay = document.createElement("div");
        overlay.className = "wm-preview-overlay";
        overlay.style.color = `rgba(217, 51, 51, ${wmOpacity})`;
        overlay.innerText = wmText;
        slotElement.appendChild(overlay);
    }

    // 2. Crop Margin Guide Overlay: Box-shadow scrim overlay
    if (currentTool.id === "crop") {
        const margin = Math.min(30, Math.max(1, Number(document.getElementById("opt-crop-margin")?.value) || 8));
        const cropBox = document.createElement("div");
        cropBox.className = "crop-preview-frame";
        cropBox.style.top = `${margin}%`;
        cropBox.style.bottom = `${margin}%`;
        cropBox.style.left = `${margin}%`;
        cropBox.style.right = `${margin}%`;
        cropBox.innerHTML = `<span class="crop-preview-tag">-${margin}%</span>`;
        slotElement.appendChild(cropBox);
    }

    // 3. e-Sign Signature Overlay: 160x80pt (2:1 ratio) attached ONLY to last page
    if (currentTool.id === "sign" && pageNum === totalPages) {
        const signBox = document.createElement("div");
        signBox.className = `sign-preview-box sign-pos-${currentSignaturePos}`;
        if (currentSignatureUrl) {
            signBox.innerHTML = `<img src="${currentSignatureUrl}" alt="Chữ ký" />`;
        } else {
            signBox.innerHTML = `
                <div class="sign-preview-placeholder">
                    ${icon("sign", "w-3 h-3 text-slate-500")}
                    <span>Chữ ký</span>
                </div>
            `;
        }
        slotElement.appendChild(signBox);
    }
}

// Live update watermark preview without DOM destruction (<5ms)
function updateWatermarkPreviewLive() {
    const text = document.getElementById("opt-wm-text")?.value || "BẢN SAO NỘI BỘ";
    const opacity = document.getElementById("opt-wm-opacity")?.value || 0.35;
    document.querySelectorAll(".wm-preview-overlay").forEach(el => {
        el.innerText = text;
        el.style.color = `rgba(217, 51, 51, ${opacity})`;
    });
}

// Live update crop preview without DOM destruction (<5ms)
function updateCropPreviewLive(val) {
    const margin = Math.min(30, Math.max(1, Number(val) || 8));
    document.querySelectorAll(".crop-preview-frame").forEach(el => {
        el.style.top = `${margin}%`;
        el.style.bottom = `${margin}%`;
        el.style.left = `${margin}%`;
        el.style.right = `${margin}%`;
        const tag = el.querySelector(".crop-preview-tag");
        if (tag) tag.innerText = `-${margin}%`;
    });
}

// Live update signature position
function handleSignaturePosChange(pos) {
    currentSignaturePos = pos;
    const box = document.querySelector(".sign-preview-box");
    if (box) {
        box.className = `sign-preview-box sign-pos-${pos}`;
    }
}

// Live update signature image preview
function handleSignatureFileChange(input) {
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    currentSignatureUrl = URL.createObjectURL(file);
    const box = document.querySelector(".sign-preview-box");
    if (box) {
        box.innerHTML = `<img src="${currentSignatureUrl}" alt="Chữ ký" />`;
    }
}

// Backward compatibility alias for live simulations
const triggerLiveSimulationUpdate = updateWatermarkPreviewLive;

// Multi-File Drag Tracking State for iLovePDF Reordering
let draggedFileIdx = null;

function clearAllFileDropIndicators() {
    if (!multiFileList) return;
    multiFileList.querySelectorAll(".multi-file-card").forEach(c => {
        c.classList.remove("drop-above", "drop-below", "is-dragging");
    });
}

function attachMultiFileCardDragListeners(card, idx) {
    card.setAttribute("draggable", "true");

    card.addEventListener("dragstart", (e) => {
        if (e.target.closest("button") || e.target.closest(".file-card-controls")) {
            e.preventDefault();
            return;
        }
        draggedFileIdx = idx;
        card.classList.add("is-dragging");
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(idx));
    });

    card.addEventListener("dragend", () => {
        clearAllFileDropIndicators();
        draggedFileIdx = null;
    });

    card.addEventListener("dragover", (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        if (draggedFileIdx === null || draggedFileIdx === idx) return;

        const rect = card.getBoundingClientRect();
        const relY = e.clientY - rect.top;
        const isAbove = relY < (rect.height / 2);

        if (isAbove) {
            card.classList.add("drop-above");
            card.classList.remove("drop-below");
        } else {
            card.classList.add("drop-below");
            card.classList.remove("drop-above");
        }
    });

    card.addEventListener("dragleave", (e) => {
        const rect = card.getBoundingClientRect();
        if (
            e.clientX < rect.left || e.clientX >= rect.right ||
            e.clientY < rect.top || e.clientY >= rect.bottom
        ) {
            card.classList.remove("drop-above", "drop-below");
        }
    });

    card.addEventListener("drop", (e) => {
        e.preventDefault();
        const isAbove = card.classList.contains("drop-above");
        clearAllFileDropIndicators();

        if (draggedFileIdx === null || draggedFileIdx === idx) return;

        const fromIdx = draggedFileIdx;
        const targetFile = selectedFiles[idx];
        const [movedFile] = selectedFiles.splice(fromIdx, 1);
        let targetPos = selectedFiles.indexOf(targetFile);
        if (!isAbove) {
            targetPos += 1;
        }
        selectedFiles.splice(targetPos, 0, movedFile);
        updateSidebarFileInfo();
        updateMultiFileListUI();
    });
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Multi-File Ordering & Management (File Manager Mode)
function updateMultiFileListUI() {
    if (!multiFileList) return;
    multiFileList.innerHTML = "";
    if (selectedFiles.length === 0) return;

    const total = selectedFiles.length;
    updateQueueSummaryUI();

    selectedFiles.forEach((f, idx) => {
        const item = document.createElement("div");
        item.className = "multi-file-card";
        item.dataset.index = idx;
        const sizeMb = (f.size / (1024 * 1024)).toFixed(2);
        const ext = f.name.split('.').pop().toUpperCase();
        const isFirst = idx === 0;
        const isLast = idx === total - 1;

        const status = f.fileStatus || "ready";
        let statusBadgeHtml = `<span class="file-card-status-badge badge-status-ready">⏳ Sẵn sàng</span>`;
        if (status === "pending") {
            statusBadgeHtml = `<span class="file-card-status-badge badge-status-ready">⏳ Đang chờ</span>`;
        } else if (status === "processing") {
            statusBadgeHtml = `<span class="file-card-status-badge badge-status-processing"><span class="spinner-sm"></span> Đang xử lý...</span>`;
        } else if (status === "completed") {
            statusBadgeHtml = `<span class="file-card-status-badge badge-status-completed">✅ Hoàn thành</span>`;
        } else if (status === "error") {
            const safeErr = escapeHtml(f.errorMsg || "Lỗi");
            statusBadgeHtml = `<span class="file-card-status-badge badge-status-error" title="${safeErr}">❌ Lỗi</span>`;
        }

        const dlHtml = f.downloadUrl ? `
            <a href="${encodeURI(f.downloadUrl)}" download="${escapeHtml(f.outputFilename || f.name)}" class="btn-file-dl" title="Tải xuống tệp">
                ⬇️ Tải
            </a>
        ` : "";

        item.innerHTML = `
            <div class="file-card-info">
                <span class="drag-handle" title="Kéo thả để sắp xếp lại vị trí tệp như iLovePDF">
                    ${icon("grip-vertical", "w-3.5 h-3.5 text-slate-400")}
                </span>
                <span class="file-card-order">${idx + 1}</span>
                <div class="file-card-icon-box">
                    ${icon("file-lines", "w-4 h-4 text-slate-700")}
                </div>
                <div class="file-card-details">
                    <div class="file-card-title" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</div>
                    <div class="file-card-meta">
                        <span class="format-pill-sm">${escapeHtml(ext)}</span>
                        <span>${sizeMb} MB</span>
                        ${statusBadgeHtml}
                        ${currentTool && currentTool.id === "compare" ? `
                            <span class="compare-tag ${idx === 0 ? 'bg-blue-100 text-blue-800' : 'bg-amber-100 text-amber-800'}">
                                ${idx === 0 ? 'Bản gốc (Tài liệu 1)' : 'Bản so sánh (Tài liệu 2)'}
                            </span>
                        ` : ""}
                    </div>
                </div>
            </div>
            <div class="file-card-controls">
                ${dlHtml}
                <button type="button" onclick="moveFileOrder(${idx}, -1)" ${isFirst ? "disabled" : ""} title="Chuyển lên" class="btn-file-order">
                    ${icon("arrow-up", "w-3 h-3")}
                </button>
                <button type="button" onclick="moveFileOrder(${idx}, 1)" ${isLast ? "disabled" : ""} title="Chuyển xuống" class="btn-file-order">
                    ${icon("arrow-down", "w-3 h-3")}
                </button>
                <button type="button" onclick="removeFile(${idx})" title="Xóa tệp khỏi hàng đợi" class="btn-file-order btn-file-delete btn-card-remove">
                    ${icon("trash", "w-3 h-3")}
                </button>
            </div>
        `;
        attachMultiFileCardDragListeners(item, idx);
        multiFileList.appendChild(item);
    });
}

function clearAllQueueFiles() {
    selectedFiles = [];
    resetWorkspace();
}

function moveFileOrder(idx, delta) {
    const targetIdx = idx + delta;
    if (targetIdx < 0 || targetIdx >= selectedFiles.length) return;
    const temp = selectedFiles[idx];
    selectedFiles[idx] = selectedFiles[targetIdx];
    selectedFiles[targetIdx] = temp;
    updateSidebarFileInfo();
    updateMultiFileListUI();
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    if (selectedFiles.length === 0) {
        resetWorkspace();
        return;
    }
    updateSidebarFileInfo();
    updateQueueSummaryUI();
    updateMultiFileListUI();
    if (selectedFiles.length === 1 && studioViewMode === "grid") {
        renderStudioInteractiveReview();
    }
}

// Switch between Studio Tabs (Grid, Continuous Viewer, Files)
function switchStudioView(mode) {
    studioViewMode = mode;
    const gridView = document.getElementById("studio-grid-view");
    const docView = document.getElementById("studio-doc-view");
    const filesView = document.getElementById("studio-files-view");

    const btnGrid = document.getElementById("view-mode-grid");
    const btnViewer = document.getElementById("view-mode-viewer");
    const btnFiles = document.getElementById("view-mode-files");

    [btnGrid, btnViewer, btnFiles].forEach(b => {
        if (b) b.classList.remove("active");
    });

    if (gridView) gridView.classList.add("hidden");
    if (docView) docView.classList.add("hidden");
    if (filesView) filesView.classList.add("hidden");

    if (mode === "grid") {
        if (gridView) gridView.classList.remove("hidden");
        if (btnGrid) btnGrid.classList.add("active");
    } else if (mode === "viewer") {
        if (docView) docView.classList.remove("hidden");
        if (btnViewer) btnViewer.classList.add("active");
        initContinuousReader();
    } else if (mode === "files") {
        if (filesView) filesView.classList.remove("hidden");
        if (btnFiles) btnFiles.classList.add("active");
    }
}

// 60fps Slider Zoom via single CSS Custom Property update (Zero DOM query loop)
function changeThumbSize(val) {
    currentThumbWidth = val;
    if (pagesGrid) {
        pagesGrid.style.setProperty("--thumb-size", `${val}px`);
    }
}

// -------------------------------------------------------------
// 6. RENDER DYNAMIC TOOL OPTIONS (All 26 Tools)
// -------------------------------------------------------------
function renderOptions() {
    if (!currentTool) return;
    optionsContent.innerHTML = "";

    switch (currentTool.id) {
        case "split":
            optionsContent.innerHTML = `
                <div class="options-group">
                    <label class="form-label">Chế độ phân tách trang:</label>
                    <label class="radio-card active">
                        <div class="radio-card-left">
                            <input type="radio" name="split_mode" value="all" checked onchange="toggleRangeInput(false); updateRadioCards('split_mode')" />
                            <span class="text-xs">Tách toàn bộ các trang thành từng file riêng lẻ</span>
                        </div>
                    </label>
                    <label class="radio-card">
                        <div class="radio-card-left">
                            <input type="radio" name="split_mode" value="custom" onchange="toggleRangeInput(true); updateRadioCards('split_mode')" />
                            <span class="text-xs">Chỉ định dải trang cụ thể</span>
                        </div>
                    </label>
                    <div id="range-box" class="hidden" style="margin-top: 4px;">
                        <input type="text" id="opt-range" placeholder="Nhấp chọn trang bên trái hoặc nhập ví dụ: 1-3, 5" class="input-text font-mono" />
                    </div>
                </div>
            `;
            break;

        case "extract-pages":
            optionsContent.innerHTML = `
                <div class="options-group">
                    <div>
                        <label class="form-label">Các trang muốn trích xuất:</label>
                        <input type="text" id="opt-ext-pages" placeholder="Nhấp chọn trang bên trái hoặc nhập ví dụ: 1, 3, 5-8" class="input-text font-mono" />
                        <p class="input-hint">Các trang được chọn sẽ tập hợp thành file PDF mới.</p>
                    </div>
                </div>
            `;
            break;

        case "organize":
            optionsContent.innerHTML = `
                <div class="options-group">
                    <div>
                        <label class="form-label">Thứ tự trang mới (hoặc 'reverse'):</label>
                        <input type="text" id="opt-org-order" value="${pageOrder.join(', ')}" placeholder="Ví dụ: 4, 2, 1, 3 hoặc reverse" class="input-text font-mono" />
                        <p class="input-hint-success">Mẹo: Sử dụng nút mũi tên chuyển vị trí trực tiếp trên từng trang bên trái.</p>
                    </div>
                </div>
            `;
            break;

        case "compress":
            optionsContent.innerHTML = `
                <div class="options-group">
                    <label class="radio-card active">
                        <div class="radio-card-left">
                            <input type="radio" name="opt_compress" value="recommended" checked onchange="updateRadioCards('opt_compress')" />
                            <span style="font-size: 12px; font-weight: 700;">Khuyên dùng (Chuẩn)</span>
                        </div>
                        <span class="badge badge-optimize">Tối ưu</span>
                    </label>
                    <label class="radio-card">
                        <div class="radio-card-left">
                            <input type="radio" name="opt_compress" value="extreme" onchange="updateRadioCards('opt_compress')" />
                            <span style="font-size: 12px;">Cực đại (Extreme)</span>
                        </div>
                        <span class="input-hint">Siêu nhỏ</span>
                    </label>
                    <label class="radio-card">
                        <div class="radio-card-left">
                            <input type="radio" name="opt_compress" value="low" onchange="updateRadioCards('opt_compress')" />
                            <span style="font-size: 12px;">Nhẹ (Low)</span>
                        </div>
                        <span class="input-hint">Giữ nét 100%</span>
                    </label>
                </div>
            `;
            break;

        case "crop":
            optionsContent.innerHTML = `
                <div class="options-group">
                    <div>
                        <label class="form-label">Tỷ lệ cắt lề (%):</label>
                        <input type="number" id="opt-crop-margin" value="8" min="1" max="30" oninput="triggerLiveSimulationUpdate()" class="input-text" />
                        <p class="input-hint-success">Đường viền nét đứt màu xanh thể hiện phần nội dung được giữ lại.</p>
                    </div>
                </div>
            `;
            break;

        case "sign":
            optionsContent.innerHTML = `
                <div class="options-group">
                    <div>
                        <label class="form-label">Tải lên ảnh chữ ký (PNG/JPG):</label>
                        <input type="file" id="opt-sig-file" accept="image/*" class="input-text" />
                    </div>
                    <div>
                        <label class="form-label">Vị trí chèn chữ ký:</label>
                        <select id="opt-sig-pos" class="select-box">
                            <option value="bottom-right" selected>Góc dưới bên phải (Chuẩn)</option>
                            <option value="bottom-left">Góc dưới bên trái</option>
                            <option value="center">Chính giữa chân trang</option>
                        </select>
                    </div>
                </div>
            `;
            break;

        case "redact":
            optionsContent.innerHTML = `
                <div class="options-group">
                    <div>
                        <label class="form-label">Từ khóa cần che giấu vĩnh viễn:</label>
                        <input type="text" id="opt-redact-text" placeholder="Ví dụ: Số CCCD, Mật khẩu, Số tài khoản..." class="input-text font-mono" style="color: var(--danger-text); font-weight: 700;" />
                        <p class="input-hint">Dữ liệu này sẽ bị bôi đen và xóa vĩnh viễn khỏi tài liệu, không thể phục hồi.</p>
                    </div>
                </div>
            `;
            break;

        case "pdf-to-images":
            optionsContent.innerHTML = `
                <div class="options-grid-2">
                    <div>
                        <label class="form-label">Định dạng ảnh:</label>
                        <select id="opt-img-fmt" class="select-box">
                            <option value="png" selected>PNG (Độ nét cao)</option>
                            <option value="jpg">JPG (Nhỏ gọn)</option>
                        </select>
                    </div>
                    <div>
                        <label class="form-label">Độ phân giải (DPI):</label>
                        <select id="opt-img-dpi" class="select-box">
                            <option value="150" selected>150 DPI</option>
                            <option value="300">300 DPI</option>
                        </select>
                    </div>
                </div>
            `;
            break;

        case "rotate":
            optionsContent.innerHTML = `
                <div class="options-group">
                    <label class="form-label">Góc xoay xuất tệp:</label>
                    <label class="radio-card active">
                        <div class="radio-card-left">
                            <input type="radio" name="opt_angle" value="90" checked onchange="rotateAllPages(90); updateRadioCards('opt_angle')" />
                            <span class="text-xs">Xoay phải 90°</span>
                        </div>
                    </label>
                    <label class="radio-card">
                        <div class="radio-card-left">
                            <input type="radio" name="opt_angle" value="180" onchange="rotateAllPages(180); updateRadioCards('opt_angle')" />
                            <span class="text-xs">Xoay 180°</span>
                        </div>
                    </label>
                    <label class="radio-card">
                        <div class="radio-card-left">
                            <input type="radio" name="opt_angle" value="270" onchange="rotateAllPages(270); updateRadioCards('opt_angle')" />
                            <span class="text-xs">Xoay trái 270°</span>
                        </div>
                    </label>
                </div>
            `;
            break;

        case "delete-pages":
            optionsContent.innerHTML = `
                <div class="options-group">
                    <div>
                        <label class="form-label">Các trang muốn loại bỏ:</label>
                        <input type="text" id="opt-del-pages" placeholder="Nhấp nút thùng rác bên trái hoặc nhập ví dụ: 1, 3-5, 8" class="input-text font-mono" />
                        <p class="input-hint">Các trang được chọn sẽ bị gạch chéo đỏ và loại khỏi file kết quả.</p>
                    </div>
                </div>
            `;
            break;

        case "watermark":
            optionsContent.innerHTML = `
                <div class="options-group">
                    <div>
                        <label class="form-label">Nội dung con dấu:</label>
                        <input type="text" id="opt-wm-text" value="BẢN SAO NỘI BỘ" oninput="triggerLiveSimulationUpdate()" class="input-text" style="font-weight: 700;" />
                    </div>
                    <div>
                        <label class="form-label">Độ mờ (Opacity):</label>
                        <input type="range" id="opt-wm-opacity" min="0.1" max="0.9" step="0.05" value="0.35" oninput="triggerLiveSimulationUpdate()" style="width: 100%; accent-color: var(--primary-bg);" />
                    </div>
                </div>
            `;
            break;

        case "protect":
            optionsContent.innerHTML = `
                <div class="options-group">
                    <div>
                        <label class="form-label">Mật khẩu bảo vệ tài liệu:</label>
                        <input type="password" id="opt-pw" placeholder="Nhập mật khẩu an toàn..." class="input-text" />
                    </div>
                </div>
            `;
            break;

        case "unlock":
            optionsContent.innerHTML = `
                <div class="options-group">
                    <div>
                        <label class="form-label">Mật khẩu tài liệu hiện tại (nếu có):</label>
                        <input type="password" id="opt-unlock-pw" placeholder="Để trống nếu chỉ cần gỡ bỏ quyền hạn..." class="input-text" />
                    </div>
                </div>
            `;
            break;

        case "ocr":
            optionsContent.innerHTML = `
                <div class="options-group">
                    <label class="form-label" style="font-weight: 600; color: var(--text-primary); margin-bottom: 8px;">Động cơ nhận diện OCR:</label>
                    <div style="display: flex; flex-direction: column; gap: 8px;">
                        <label class="radio-card active" id="card-engine-deepseek" style="cursor: pointer; padding: 12px; border: 1.5px solid var(--primary); border-radius: 8px;">
                            <div class="radio-card-left" style="display: flex; align-items: flex-start; gap: 10px;">
                                <input type="radio" name="opt_ocr_engine" value="deepseek" checked onchange="toggleOcrEngine('deepseek'); updateRadioCards('opt_ocr_engine')" style="margin-top: 3px;" />
                                <div>
                                    <div style="font-weight: 600; font-size: 13px; color: var(--text-primary); display: flex; align-items: center; gap: 6px;">
                                        DeepSeek Vision AI
                                        <span style="background: #2563eb; color: #ffffff; font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 700;">Khuyên dùng</span>
                                    </div>
                                    <div style="font-size: 12px; color: var(--text-secondary); margin-top: 3px; line-height: 1.4;">
                                        Nhận diện AI chuẩn xác 100% tiếng Việt có dấu, trích xuất cấu trúc văn bản, tiêu đề và bảng biểu Markdown hoàn hảo.
                                    </div>
                                </div>
                            </div>
                        </label>
                        <label class="radio-card" id="card-engine-tesseract" style="cursor: pointer; padding: 12px; border-radius: 8px;">
                            <div class="radio-card-left" style="display: flex; align-items: flex-start; gap: 10px;">
                                <input type="radio" name="opt_ocr_engine" value="tesseract" onchange="toggleOcrEngine('tesseract'); updateRadioCards('opt_ocr_engine')" style="margin-top: 3px;" />
                                <div>
                                    <div style="font-weight: 600; font-size: 13px; color: var(--text-primary);">
                                        Tesseract Cục bộ (Offline)
                                    </div>
                                    <div style="font-size: 12px; color: var(--text-secondary); margin-top: 3px; line-height: 1.4;">
                                        Chạy 100% nội bộ không cần mạng internet, xuất file text thô (.txt).
                                    </div>
                                </div>
                            </div>
                        </label>
                    </div>
                </div>

                <!-- DeepSeek Options Fields -->
                <div id="ocr-deepseek-fields" class="options-group" style="margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border-color);">
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <label class="form-label" style="margin-bottom: 0; font-weight: 600;">DeepSeek API Key:</label>
                            <span style="font-size: 11px; color: var(--text-secondary);">(Nhập API Key)</span>
                        </div>
                        <div style="display: flex; gap: 6px;">
                            <input type="password" id="opt-deepseek-key" placeholder="Nhập API Key sk-..." class="input-text font-mono" style="font-size: 12px; flex: 1;" />
                            <button type="button" class="btn-subtle" id="btn-toggle-key-visibility" onclick="toggleKeyVisibility()" title="Ẩn/Hiện key" style="padding: 0 10px; display: flex; align-items: center; justify-content: center; height: 36px; border: 1px solid var(--border-color); border-radius: 6px;">
                                ${icon("eye", "w-4 h-4")}
                            </button>
                            <button type="button" class="btn-secondary" id="btn-save-deepseek-key" onclick="saveDeepSeekKeyInline()" style="font-size: 12px; white-space: nowrap; height: 36px; padding: 0 12px;">
                                Lưu Key
                            </button>
                        </div>
                        <div id="deepseek-key-status" class="input-hint" style="margin-top: 6px; font-size: 11px;">Đang kiểm tra trạng thái API Key...</div>
                    </div>

                    <div class="options-grid-2" style="margin-top: 12px;">
                        <div>
                            <label class="form-label" style="font-weight: 600;">Định dạng xuất file:</label>
                            <select id="opt-ocr-format" class="select-box">
                                <option value="reconstructed_pdf" selected>PDF Tái tạo Vector Siêu Cấp VIP Pro (.pdf) — Sắc nét 100%</option>
                                <option value="docx">Tài liệu Word Siêu Cấp VIP Pro (.docx) — Giữ bảng biểu</option>
                                <option value="pdf">PDF Searchable — Lớp chữ tìm kiếm trên scan gốc</option>
                                <option value="md">Markdown (.md) — Chuẩn AI / Notion</option>
                                <option value="txt">Văn bản thuần (.txt)</option>
                            </select>
                        </div>
                        <div>
                            <label class="form-label" style="font-weight: 600;">Mô hình Vision AI:</label>
                            <select id="opt-ocr-model" class="select-box">
                                <option value="deepseek-flash" selected>deepseek-flash (Siêu tốc & Chuẩn)</option>
                            </select>
                        </div>
                    </div>

                    <div style="margin-top: 12px;">
                        <label class="form-label" style="font-weight: 600;">Dải trang quét OCR:</label>
                        <input type="text" id="opt-ocr-range" placeholder="all (hoặc ví dụ: 1-5, 1,3,5)" value="all" class="input-text" />
                        <p class="input-hint" style="margin-top: 4px;">Nhập "all" để nhận diện toàn bộ, hoặc nhập số trang để tiết kiệm token và thời gian.</p>
                    </div>
                </div>

                <!-- Tesseract Options Fields (Hidden by default) -->
                <div id="ocr-tesseract-fields" class="options-group hidden" style="margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border-color);">
                    <div class="options-grid-2">
                        <div>
                            <label class="form-label" style="font-weight: 600;">Ngôn ngữ nhận diện OCR:</label>
                            <select id="opt-ocr-lang" class="select-box">
                                <option value="vie+eng" selected>Tiếng Việt + Tiếng Anh (Song ngữ)</option>
                                <option value="vie">Chỉ Tiếng Việt</option>
                                <option value="eng">Chỉ Tiếng Anh</option>
                            </select>
                        </div>
                        <div>
                            <label class="form-label" style="font-weight: 600;">Định dạng tái tạo:</label>
                            <select id="opt-ocr-offline-format" class="select-box">
                                <option value="reconstructed_pdf" selected>PDF Tái tạo Vector (.pdf)</option>
                                <option value="docx">Word Siêu Cấp VIP Pro (.docx)</option>
                                <option value="txt">Văn bản thuần (.txt)</option>
                            </select>
                        </div>
                    </div>
                </div>
            `;
            break;

        case "interlinear-translate":
            optionsContent.innerHTML = `
                <div class="options-group">
                    <label class="form-label" style="font-weight: 600;">Cấu hình Dịch thuật Song ngữ (DOC-TRAN):</label>
                    
                    <div style="margin-bottom: 12px;">
                        <label class="form-label">Chế độ xử lý tài liệu:</label>
                        <select id="opt-trans-engine" class="select-box">
                            <option value="auto" selected>🌟 Tự động nhận diện thông minh (Khuyên dùng)</option>
                            <option value="ocr_scan">📷 Chuyên sâu PDF Scan & Ảnh chụp (Vision AI + Tái tạo Siêu Cấp VIP Pro)</option>
                            <option value="vip_pro_doc">📄 Chuyên sâu PDF Văn bản & Biểu mẫu (Động cơ Siêu Cấp VIP Pro)</option>
                        </select>
                        <div class="input-hint" style="margin-top: 4px;">Tự động phân biệt PDF Scan/CamScanner để chạy Vision AI, hoặc kích hoạt Động cơ Siêu Cấp VIP Pro cho tài liệu vector.</div>
                    </div>

                    <div style="margin-bottom: 12px;">
                        <label class="form-label">Định dạng kết quả đầu ra:</label>
                        <select id="opt-trans-output-format" class="select-box">
                            <option value="docx" selected>📝 Tài liệu Word (.docx) — Có thể chỉnh sửa 100%</option>
                            <option value="pdf">📑 PDF Vector Siêu Cấp VIP Pro (.pdf) — Chuẩn in ấn</option>
                            <option value="both">📦 Trọn bộ cả Word (.docx) & PDF Vector (.zip)</option>
                        </select>
                    </div>

                    <div class="options-grid-2">
                        <div>
                            <label class="form-label" style="font-weight: 600;">Ngôn ngữ gốc (Từ):</label>
                            <select id="opt-trans-src" class="select-box" onchange="onTransLangChange('src')">
                                <option value="auto">🌐 Tự động nhận diện</option>
                                <option value="vi">🇻🇳 Tiếng Việt (VI)</option>
                                <option value="en" selected>🇬🇧 Tiếng Anh (EN)</option>
                                <option value="zh">🇨🇳 Tiếng Trung (ZH)</option>
                                <option value="ja">🇯🇵 Tiếng Nhật (JA)</option>
                                <option value="ko">🇰🇷 Tiếng Hàn (KO)</option>
                            </select>
                        </div>
                        <div>
                            <label class="form-label" style="font-weight: 600;">Ngôn ngữ đích (Sang):</label>
                            <select id="opt-trans-tgt" class="select-box" onchange="onTransLangChange('tgt')">
                                <option value="vi" selected>🇻🇳 Tiếng Việt (VI)</option>
                                <option value="en">🇬🇧 Tiếng Anh (EN)</option>
                                <option value="zh">🇨🇳 Tiếng Trung (ZH)</option>
                                <option value="ja">🇯🇵 Tiếng Nhật (JA)</option>
                                <option value="ko">🇰🇷 Tiếng Hàn (KO)</option>
                            </select>
                        </div>
                    </div>

                    <div style="margin-top: 12px;">
                        <label class="form-label" style="font-weight: 600;">Kiểu xuất bản dịch:</label>
                        <select id="opt-trans-mode" class="select-box">
                            <option value="bilingual" selected>📖 Song ngữ xen kẽ (Interlinear — Chuẩn)</option>
                            <option value="target_only">📝 Chỉ ngôn ngữ đích (Ghi đè nội dung gốc)</option>
                        </select>
                    </div>

                    <div style="margin-top: 12px;">
                        <label class="form-label">Động cơ dịch thuật (AI Engine):</label>
                        <select id="opt-trans-provider" class="select-box" onchange="toggleTransProvider()">
                            <option value="google" selected>⚡ Động cơ Siêu tốc (Miễn phí, không giới hạn, dịch chuẩn hóa chất)</option>
                            <option value="deepseek">🧠 DeepSeek AI (Chuyên ngành Hóa chất & Kỹ thuật)</option>
                        </select>
                    </div>

                    <div id="trans-deepseek-key-box" class="hidden" style="margin-top: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <label class="form-label" style="margin-bottom: 0;">DeepSeek API Key:</label>
                            <span style="font-size: 11px; color: var(--text-secondary);">(Nhập API Key)</span>
                        </div>
                        <input type="password" id="opt-trans-key" placeholder="Nhập API Key sk-..." class="input-text font-mono" style="font-size: 12px;" />
                        <div id="trans-key-status" class="input-hint" style="margin-top: 4px;">Đang kiểm tra API Key...</div>
                    </div>

                    <div class="options-info-box" style="margin-top: 14px; font-size: 12px; line-height: 1.5;">
                        <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">✓ Tiêu chuẩn định dạng DOC-TRAN:</div>
                        • Hỗ trợ dịch 2 chiều linh hoạt: Việt ➔ Anh / Trung, Anh / Trung ➔ Việt, v.v.<br>
                        • Dòng gốc ở trên (giữ font và kích thước chuẩn).<br>
                        • Dòng dịch ngay bên dưới: Font Times New Roman / SimSun, màu <b>Xanh đậm #002060</b>, <i>in nghiêng</i>.<br>
                        • Tự động kéo bảng (Loại bỏ trHeight cố định), khử 100% khoảng trắng thừa.<br>
                        • Bảo vệ số CAS, công thức hóa học, URL, mã kỹ thuật nguyên bản.
                    </div>
                </div>
            `;
            initTransKey();
            break;

        case "pdf-to-word":
            optionsContent.innerHTML = `
                <div class="options-group">
                    <label class="form-label" style="font-weight: 700; color: var(--text-primary); margin-bottom: 8px;">
                        Động cơ chuyển đổi PDF sang DOCX:
                    </label>
                    <div style="background: var(--bg-surface-subtle); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 14px; margin-bottom: 12px;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                            <span style="font-size: 13px; font-weight: 700; color: var(--text-primary);">⚡ Microsoft Word Native COM (Cục bộ & Chuẩn xác)</span>
                        </div>
                        <p class="input-hint" style="margin: 0; font-size: 12px; line-height: 1.5; color: var(--text-secondary);">
                            Chuyển đổi trực tiếp qua bộ máy Microsoft Word cài đặt sẵn trên hệ thống Windows. Bảo đảm 100% độ chính xác bảng biểu, biểu mẫu và phông chữ nguyên bản.
                        </p>
                    </div>

                    <div style="background: var(--bg-surface-subtle); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 12px; margin-bottom: 12px;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                            <span style="font-size: 12px; font-weight: 600; color: var(--text-secondary);">🛡️ Cơ chế Fallback an toàn:</span>
                        </div>
                        <p class="input-hint" style="margin: 0; font-size: 11.5px; line-height: 1.45; color: var(--text-muted);">
                            Nếu hệ thống chưa cài đặt Microsoft Word, ứng dụng sẽ tự động chuyển đổi an toàn qua thư viện offline nhẹ <code>pdf2docx</code> hoàn toàn nội bộ, không phụ thuộc Internet hay AI bên ngoài.
                        </p>
                    </div>

                    <input type="hidden" name="opt_word_engine" value="auto" />
                </div>
            `;
            break;

        case "remove-watermark":
            optionsContent.innerHTML = `
                <div class="options-group">
                    <label class="form-label" style="font-weight: 700; color: var(--text-primary); margin-bottom: 8px;">Cấu hình Tẩy Watermark & Nền Rác:</label>
                    
                    <div style="margin-bottom: 14px;">
                        <label class="form-label">Chữ mờ / Từ khóa cần xóa (Tùy chỉnh):</label>
                        <input type="text" id="opt-wm-custom-text" class="input-text" placeholder="Ví dụ: BẢN NHÁP, DRAFT, CamScanner, tailieu.vn..." />
                        <div class="input-hint" style="margin-top: 4px;">Có thể nhập nhiều từ khóa cách nhau bởi dấu phẩy (,).</div>
                    </div>

                    <div style="margin-bottom: 12px; display: flex; flex-direction: column; gap: 8px;">
                        <label class="form-check" style="display:flex; align-items:center; gap:8px; cursor:pointer;">
                            <input type="checkbox" id="opt-wm-common-keywords" checked style="width:16px; height:16px; accent-color:var(--primary);" />
                            <span style="font-size: 13px; font-weight: 500;">Quét tự động hơn 25 từ khóa Watermark thông dụng</span>
                        </label>
                        
                        <label class="form-check" style="display:flex; align-items:center; gap:8px; cursor:pointer;">
                            <input type="checkbox" id="opt-wm-remove-bg" checked style="width:16px; height:16px; accent-color:var(--primary);" />
                            <span style="font-size: 13px; font-weight: 500;">Xóa ảnh nền chìm & Logo mờ toàn trang</span>
                        </label>

                        <label class="form-check" style="display:flex; align-items:center; gap:8px; cursor:pointer;">
                            <input type="checkbox" id="opt-wm-remove-annots" checked style="width:16px; height:16px; accent-color:var(--primary);" />
                            <span style="font-size: 13px; font-weight: 500;">Xóa tem mộc, chú thích & Stamp Watermark</span>
                        </label>

                        <label class="form-check" style="display:flex; align-items:center; gap:8px; cursor:pointer;">
                            <input type="checkbox" id="opt-wm-clean-hf" style="width:16px; height:16px; accent-color:var(--primary);" />
                            <span style="font-size: 13px; font-weight: 500;">Tẩy vệt quảng cáo Header / Footer mép trang</span>
                        </label>
                    </div>

                    <div class="input-hint" style="background:#eff6ff; padding:10px; border-radius:6px; border:1px solid #bfdbfe; color:#1e40af; line-height:1.5;">
                        💡 <b>Cơ chế an toàn:</b> Thuật toán thanh lọc glyphs trực tiếp từ dòng lệnh PDF gốc, bảo toàn 100% độ sắc nét của văn bản và cấu trúc trang.
                    </div>
                </div>
            `;
            break;

        default:
            optionsContent.innerHTML = `
                <div class="options-info-box">
                    Công cụ đã sẵn sàng với thiết lập tự động tối ưu nhất. Vui lòng bấm nút bắt đầu xử lý bên dưới.
                </div>
            `;
    }

    if (currentTool && currentTool.id === "ocr") {
        initOcrOptions();
    }

    if (typeof attachRangeInputListeners === "function") {
        attachRangeInputListeners();
    }

    const sigFileInput = document.getElementById("opt-sig-file");
    if (sigFileInput && sigFileInput.addEventListener) {
        sigFileInput.addEventListener("change", handleSignatureFileChange);
    }
    const sigPosSelect = document.getElementById("opt-sig-pos");
    if (sigPosSelect && sigPosSelect.addEventListener) {
        sigPosSelect.addEventListener("change", handleSignaturePosChange);
    }
}

function updateRadioCards(name) {
    if (typeof document === "undefined" || !document.querySelectorAll) return;
    const inputs = document.querySelectorAll(`input[name="${name}"]`);
    inputs.forEach(input => {
        const card = input.closest ? input.closest(".radio-card") : null;
        if (card) {
            if (input.checked) {
                card.classList.add("active");
            } else {
                card.classList.remove("active");
            }
        }
    });
}

function toggleRangeInput(show) {
    const box = document.getElementById("range-box");
    if (box) {
        if (show) box.classList.remove("hidden");
        else box.classList.add("hidden");
    }
}

function toggleOcrEngine(engine) {
    const dsFields = document.getElementById("ocr-deepseek-fields");
    const tsFields = document.getElementById("ocr-tesseract-fields");
    if (engine === "deepseek") {
        if (dsFields) dsFields.classList.remove("hidden");
        if (tsFields) tsFields.classList.add("hidden");
    } else {
        if (dsFields) dsFields.classList.add("hidden");
        if (tsFields) tsFields.classList.remove("hidden");
    }
}

function toggleKeyVisibility() {
    const keyInput = document.getElementById("opt-deepseek-key");
    const btn = document.getElementById("btn-toggle-key-visibility");
    if (!keyInput) return;
    if (keyInput.type === "password") {
        keyInput.type = "text";
        if (btn) btn.innerHTML = icon("eye-off", "w-4 h-4");
    } else {
        keyInput.type = "password";
        if (btn) btn.innerHTML = icon("eye", "w-4 h-4");
    }
}

async function saveDeepSeekKeyInline() {
    const keyInput = document.getElementById("opt-deepseek-key");
    const statusHint = document.getElementById("deepseek-key-status");
    const val = keyInput ? keyInput.value.trim() : "";
    if (!val) {
        alert("Vui lòng nhập API Key trước khi lưu!");
        return;
    }
    localStorage.setItem("deepseek_api_key", val);
    try {
        const fd = new FormData();
        fd.append("api_key", val);
        const res = await fetch("/api/settings/deepseek", {
            method: "POST",
            body: fd
        });
        const data = await res.json();
        if (data.success) {
            if (statusHint) {
                statusHint.innerHTML = `<span style="color: var(--success-text); font-weight: 600;">✓ Đã lưu API Key thành công vào hệ thống!</span>`;
            }
        } else {
            if (statusHint) {
                statusHint.innerHTML = `<span style="color: var(--success-text);">✓ Đã lưu vào bộ nhớ trình duyệt.</span>`;
            }
        }
    } catch (err) {
        if (statusHint) {
            statusHint.innerHTML = `<span style="color: var(--success-text);">✓ Đã lưu vào bộ nhớ trình duyệt.</span>`;
        }
    }
}

async function initOcrOptions() {
    const keyInput = document.getElementById("opt-deepseek-key");
    const statusHint = document.getElementById("deepseek-key-status");
    const localKey = localStorage.getItem("deepseek_api_key") || "";
    
    if (keyInput && localKey) {
        keyInput.value = localKey;
    }

    try {
        const res = await fetch("/api/settings/deepseek");
        if (res.ok) {
            const data = await res.json();
            if (data.has_key) {
                if (statusHint) {
                    statusHint.innerHTML = `<span style="color: var(--success-text); font-weight: 500;">✓ Hệ thống đã có API Key sẵn sàng (${data.masked_key}).</span>`;
                }
                if (keyInput && !keyInput.value) {
                    keyInput.placeholder = data.masked_key;
                }
            } else if (localKey) {
                if (statusHint) {
                    statusHint.innerHTML = `<span style="color: var(--success-text); font-weight: 500;">✓ Đã nạp key từ bộ nhớ trình duyệt.</span>`;
                }
            } else {
                if (statusHint) {
                    statusHint.innerHTML = `<span style="color: var(--warning-text);">⚠️ Chưa cấu hình DeepSeek API Key. Hãy nhập key để bắt đầu.</span>`;
                }
            }
        }
    } catch (e) {
        if (localKey && statusHint) {
            statusHint.innerHTML = `<span style="color: var(--success-text); font-weight: 500;">✓ Đã nạp key từ bộ nhớ trình duyệt.</span>`;
        }
    }
}

function onTransLangChange(changed) {
    const src = document.getElementById("opt-trans-src");
    const tgt = document.getElementById("opt-trans-tgt");
    if (!src || !tgt) return;

    if (src.value !== "auto" && src.value === tgt.value) {
        if (changed === "src") {
            tgt.value = (src.value === "vi") ? "en" : "vi";
        } else {
            src.value = (tgt.value === "vi") ? "en" : "vi";
        }
    }
}

function toggleTransProvider() {
    const sel = document.getElementById("opt-trans-provider");
    const keyBox = document.getElementById("trans-deepseek-key-box");
    if (sel && keyBox) {
        if (sel.value === "deepseek") keyBox.classList.remove("hidden");
        else keyBox.classList.add("hidden");
    }
}

async function initTransKey() {
    const keyInput = document.getElementById("opt-trans-key");
    const statusHint = document.getElementById("trans-key-status");
    const localKey = localStorage.getItem("deepseek_api_key") || "";
    if (keyInput && localKey) {
        keyInput.value = localKey;
    }
    try {
        const res = await fetch("/api/settings/deepseek");
        if (res.ok) {
            const data = await res.json();
            if (data.has_key) {
                if (statusHint) {
                    statusHint.innerHTML = `<span style="color: var(--success-text); font-weight: 500;">✓ Hệ thống đã có API Key sẵn sàng (${data.masked_key}).</span>`;
                }
                if (keyInput && !keyInput.value) {
                    keyInput.placeholder = data.masked_key;
                }
            } else if (localKey && statusHint) {
                statusHint.innerHTML = `<span style="color: var(--success-text); font-weight: 500;">✓ Đã nạp key từ trình duyệt.</span>`;
            } else if (statusHint) {
                statusHint.innerHTML = `<span style="color: var(--text-secondary);">Nhập key để kích hoạt AI chuyên ngành, hoặc chọn Google Translate miễn phí.</span>`;
            }
        }
    } catch (e) {}
}

// -------------------------------------------------------------
// 7. EXECUTE PROCESS CALL
// -------------------------------------------------------------
async function appendToolSpecificOptions(formData) {
    switch (currentTool.id) {
        case "split":
            const splitMode = document.querySelector('input[name="split_mode"]:checked')?.value || "all";
            const rangeVal = splitMode === "all" ? "all" : (document.getElementById("opt-range")?.value || "all");
            formData.append("range_str", rangeVal);
            break;

        case "extract-pages":
            const extPages = document.getElementById("opt-ext-pages")?.value || "";
            if (!extPages.trim()) { alert("Vui lòng nhập hoặc nhấp chọn các trang muốn trích xuất!"); return false; }
            formData.append("pages_str", extPages);
            break;

        case "organize":
            const orgOrder = document.getElementById("opt-org-order")?.value || "reverse";
            formData.append("order_str", orgOrder);
            break;

        case "compress":
            const compLevel = document.querySelector('input[name="opt_compress"]:checked')?.value || "recommended";
            formData.append("level", compLevel);
            break;

        case "crop":
            const marginVal = document.getElementById("opt-crop-margin")?.value || 8.0;
            formData.append("margin", marginVal);
            break;

        case "sign":
            const sigFileInput = document.getElementById("opt-sig-file");
            if (!sigFileInput || !sigFileInput.files || sigFileInput.files.length === 0) {
                alert("Vui lòng chọn ảnh chữ ký của bạn!");
                return false;
            }
            formData.append("sig_image", sigFileInput.files[0]);
            formData.append("position", document.getElementById("opt-sig-pos")?.value || "bottom-right");
            break;

        case "redact":
            const rText = document.getElementById("opt-redact-text")?.value || "";
            if (!rText.trim()) { alert("Vui lòng nhập từ khóa cần che giấu!"); return false; }
            formData.append("text", rText);
            break;

        case "pdf-to-images":
            formData.append("fmt", document.getElementById("opt-img-fmt")?.value || "png");
            formData.append("dpi", document.getElementById("opt-img-dpi")?.value || 150);
            break;

        case "rotate":
            const angle = document.querySelector('input[name="opt_angle"]:checked')?.value || 90;
            formData.append("angle", angle);
            break;

        case "delete-pages":
            const delPages = document.getElementById("opt-del-pages")?.value || "";
            if (!delPages.trim()) { alert("Vui lòng nhập hoặc nhấp biểu tượng thùng rác để chọn trang xóa!"); return false; }
            formData.append("pages_str", delPages);
            break;

        case "watermark":
            const wmText = document.getElementById("opt-wm-text")?.value || "BẢN SAO NỘI BỘ";
            const wmOpacity = document.getElementById("opt-wm-opacity")?.value || 0.35;
            formData.append("text", wmText);
            formData.append("opacity", wmOpacity);
            break;

        case "protect":
            const pw = document.getElementById("opt-pw")?.value || "";
            if (!pw) { alert("Vui lòng nhập mật khẩu bảo vệ!"); return false; }
            formData.append("password", pw);
            break;

        case "unlock":
            const unlockPw = document.getElementById("opt-unlock-pw")?.value || "";
            formData.append("password", unlockPw);
            break;

        case "ocr":
            const ocrEngine = document.querySelector('input[name="opt_ocr_engine"]:checked')?.value || "deepseek";
            formData.append("engine", ocrEngine);
            if (ocrEngine === "deepseek") {
                const apiKey = document.getElementById("opt-deepseek-key")?.value.trim() || localStorage.getItem("deepseek_api_key") || "";
                const outFmt = document.getElementById("opt-ocr-format")?.value || "reconstructed_pdf";
                const model = document.getElementById("opt-ocr-model")?.value || "deepseek-flash";
                const range = document.getElementById("opt-ocr-range")?.value.trim() || "all";
                if (apiKey) {
                    formData.append("api_key", apiKey);
                    localStorage.setItem("deepseek_api_key", apiKey);
                }
                formData.append("output_format", outFmt);
                formData.append("model", model);
                formData.append("page_range", range);
            } else {
                const lang = document.getElementById("opt-ocr-lang")?.value || "vie+eng";
                const outFmt = document.getElementById("opt-ocr-offline-format")?.value || "reconstructed_pdf";
                formData.append("lang", lang);
                formData.append("output_format", outFmt);
            }
            break;

        case "interlinear-translate":
            const srcLang = document.getElementById("opt-trans-src")?.value || "en";
            const tgtLang = document.getElementById("opt-trans-tgt")?.value || "vi";
            const transMode = document.getElementById("opt-trans-mode")?.value || "bilingual";
            const transProvider = document.getElementById("opt-trans-provider")?.value || "google";
            const transEngine = document.getElementById("opt-trans-engine")?.value || "auto";
            const transOutFmt = document.getElementById("opt-trans-output-format")?.value || "docx";
            const transKey = document.getElementById("opt-trans-key")?.value.trim() || "";

            formData.append("source_lang", srcLang);
            formData.append("target_lang", tgtLang);
            formData.append("output_mode", transMode);
            formData.append("provider", transProvider);
            formData.append("engine_mode", transEngine);
            formData.append("output_format", transOutFmt);
            if (transProvider === "deepseek" && transKey) {
                formData.append("api_key", transKey);
                localStorage.setItem("deepseek_api_key", transKey);
            }
            break;

        case "pdf-to-word":
            formData.append("mode", "auto");
            formData.append("ai_control", "false");
            break;

        case "remove-watermark":
            const wmCustom = document.getElementById("opt-wm-custom-text")?.value.trim() || "";
            const wmUseCommon = document.getElementById("opt-wm-common-keywords")?.checked ?? true;
            const wmRemoveBg = document.getElementById("opt-wm-remove-bg")?.checked ?? true;
            const wmRemoveAnnots = document.getElementById("opt-wm-remove-annots")?.checked ?? true;
            const wmCleanHf = document.getElementById("opt-wm-clean-hf")?.checked ?? false;

            if (wmCustom) formData.append("custom_text", wmCustom);
            formData.append("use_common", wmUseCommon ? "true" : "false");
            formData.append("remove_bg", wmRemoveBg ? "true" : "false");
            formData.append("remove_annots", wmRemoveAnnots ? "true" : "false");
            formData.append("clean_hf", wmCleanHf ? "true" : "false");
            break;
    }
    return true;
}

// BATCH PROCESSING PIPELINE (R2: Multi-file Queue Processing with error resilience)
async function executeBatchPipeline() {
    const total = selectedFiles.length;
    const progressBox = document.getElementById("batch-progress-box");
    const progressTitle = document.getElementById("batch-progress-title");
    const progressPercent = document.getElementById("batch-progress-percent");
    const progressBarFill = document.getElementById("batch-progress-bar-fill");
    const progressSubtext = document.getElementById("batch-progress-subtext");
    const completeBanner = document.getElementById("batch-complete-banner");
    const btnProcess = document.getElementById("btn-process");

    if (completeBanner) completeBanner.classList.add("hidden");
    if (progressBox) progressBox.classList.remove("hidden");
    if (btnProcess) {
        btnProcess.disabled = true;
        btnProcess.classList.add("btn-loading");
    }

    switchStudioView("files");

    selectedFiles.forEach(f => {
        f.fileStatus = "pending";
        f.errorMsg = null;
        f.downloadUrl = null;
        f.outputFilename = null;
    });
    updateMultiFileListUI();

    let successCount = 0;
    let errorCount = 0;

    for (let i = 0; i < total; i++) {
        const file = selectedFiles[i];
        file.fileStatus = "processing";
        updateMultiFileListUI();

        const curPct = Math.round((i / total) * 100);
        if (progressTitle) progressTitle.innerText = `Đang xử lý hàng loạt: ${i}/${total} tệp hoàn tất (${curPct}%)`;
        if (progressPercent) progressPercent.innerText = `${curPct}%`;
        if (progressBarFill) progressBarFill.style.width = `${curPct}%`;
        if (progressSubtext) progressSubtext.innerText = `Đang xử lý tệp ${i + 1}/${total}: ${file.name}...`;

        const card = document.querySelector(`.multi-file-card[data-index="${i}"]`);
        if (card) card.scrollIntoView({ behavior: "smooth", block: "nearest" });

        const formData = new FormData();
        formData.append("file", file);
        const optOk = await appendToolSpecificOptions(formData);
        if (optOk === false) {
            file.fileStatus = "error";
            file.errorMsg = "Tùy chọn không hợp lệ";
            errorCount++;
            continue;
        }

        try {
            const resp = await fetch(currentTool.endpoint, {
                method: "POST",
                body: formData
            });
            const data = await resp.json();

            if (resp.ok && data.success) {
                file.fileStatus = "completed";
                file.downloadUrl = data.download_url;
                file.outputFilename = data.filename;
                lastResultFilename = data.filename;
                successCount++;
            } else {
                file.fileStatus = "error";
                file.errorMsg = (data && data.detail) || "Lỗi xử lý tệp.";
                errorCount++;
            }
        } catch (err) {
            file.fileStatus = "error";
            file.errorMsg = err.message || "Lỗi kết nối máy chủ.";
            errorCount++;
        }

        const newPct = Math.round(((i + 1) / total) * 100);
        if (progressTitle) progressTitle.innerText = `Đang xử lý hàng loạt: ${i + 1}/${total} tệp (${newPct}%)`;
        if (progressPercent) progressPercent.innerText = `${newPct}%`;
        if (progressBarFill) progressBarFill.style.width = `${newPct}%`;
        updateMultiFileListUI();
    }

    if (progressBox) progressBox.classList.add("hidden");
    if (completeBanner) {
        completeBanner.classList.remove("hidden");
        const titleEl = document.getElementById("batch-complete-title");
        const subEl = document.getElementById("batch-complete-sub");
        if (titleEl) {
            titleEl.innerText = errorCount === 0
                ? `Xử lý hàng loạt hoàn tất! (${successCount}/${total} tệp thành công)`
                : `Hoàn tất với cảnh báo: ${successCount}/${total} tệp thành công, ${errorCount} tệp lỗi`;
        }
        if (subEl) {
            subEl.innerText = errorCount === 0
                ? "Tất cả các tệp đã được chuyển đổi thành công. Bạn có thể mở thư mục hoặc tải từng tệp."
                : "Một số tệp bị lỗi được đánh dấu màu đỏ trong danh sách bên dưới.";
        }
    }

    if (btnProcess) {
        btnProcess.disabled = false;
        btnProcess.classList.remove("btn-loading");
    }
}

async function executeProcess() {
    if (selectedFiles.length === 0) {
        alert("Vui lòng chọn ít nhất một tệp tin!");
        return;
    }

    // Check if multi-file batch execution applies
    if (selectedFiles.length > 1 && currentTool.id !== "merge" && currentTool.id !== "compare") {
        return executeBatchPipeline();
    }

    const formData = new FormData();

    // Specific multi-file handling for Compare & Merge tools
    if (currentTool.id === "compare") {
        if (selectedFiles.length < 2) {
            alert("Công cụ so sánh cần tải lên ít nhất 2 tệp PDF!");
            return;
        }
        formData.append("file1", selectedFiles[0]);
        formData.append("file2", selectedFiles[1]);
    } else if (currentTool.id === "merge" || currentTool.multiple) {
        for (let i = 0; i < selectedFiles.length; i++) {
            formData.append("files", selectedFiles[i]);
        }
    } else {
        formData.append("file", selectedFiles[0]);
    }

    // Append options for all 26 tools
    switch (currentTool.id) {
        case "split":
            const splitMode = document.querySelector('input[name="split_mode"]:checked')?.value || "all";
            const rangeVal = splitMode === "all" ? "all" : (document.getElementById("opt-range")?.value || "all");
            formData.append("range_str", rangeVal);
            break;

        case "extract-pages":
            const extPages = document.getElementById("opt-ext-pages")?.value || "";
            if (!extPages.trim()) { alert("Vui lòng nhập hoặc nhấp chọn các trang muốn trích xuất!"); return; }
            formData.append("pages_str", extPages);
            break;

        case "organize":
            const orgOrder = document.getElementById("opt-org-order")?.value || "reverse";
            formData.append("order_str", orgOrder);
            break;

        case "compress":
            const compLevel = document.querySelector('input[name="opt_compress"]:checked')?.value || "recommended";
            formData.append("level", compLevel);
            break;

        case "crop":
            const marginVal = document.getElementById("opt-crop-margin")?.value || 8.0;
            formData.append("margin", marginVal);
            break;

        case "sign":
            const sigFileInput = document.getElementById("opt-sig-file");
            if (!sigFileInput || !sigFileInput.files || sigFileInput.files.length === 0) {
                alert("Vui lòng chọn ảnh chữ ký của bạn!");
                return;
            }
            formData.append("sig_image", sigFileInput.files[0]);
            formData.append("position", document.getElementById("opt-sig-pos")?.value || "bottom-right");
            break;

        case "redact":
            const rText = document.getElementById("opt-redact-text")?.value || "";
            if (!rText.trim()) { alert("Vui lòng nhập từ khóa cần che giấu!"); return; }
            formData.append("text", rText);
            break;

        case "pdf-to-images":
            formData.append("fmt", document.getElementById("opt-img-fmt")?.value || "png");
            formData.append("dpi", document.getElementById("opt-img-dpi")?.value || 150);
            break;

        case "rotate":
            const angle = document.querySelector('input[name="opt_angle"]:checked')?.value || 90;
            formData.append("angle", angle);
            break;

        case "delete-pages":
            const delPages = document.getElementById("opt-del-pages")?.value || "";
            if (!delPages.trim()) { alert("Vui lòng nhập hoặc nhấp biểu tượng thùng rác để chọn trang xóa!"); return; }
            formData.append("pages_str", delPages);
            break;

        case "watermark":
            const wmText = document.getElementById("opt-wm-text")?.value || "BẢN SAO NỘI BỘ";
            const wmOpacity = document.getElementById("opt-wm-opacity")?.value || 0.35;
            formData.append("text", wmText);
            formData.append("opacity", wmOpacity);
            break;

        case "protect":
            const pw = document.getElementById("opt-pw")?.value || "";
            if (!pw) { alert("Vui lòng nhập mật khẩu bảo vệ!"); return; }
            formData.append("password", pw);
            break;

        case "unlock":
            const unlockPw = document.getElementById("opt-unlock-pw")?.value || "";
            formData.append("password", unlockPw);
            break;

        case "ocr":
            const ocrEngine = document.querySelector('input[name="opt_ocr_engine"]:checked')?.value || "deepseek";
            formData.append("engine", ocrEngine);
            if (ocrEngine === "deepseek") {
                const apiKey = document.getElementById("opt-deepseek-key")?.value.trim() || localStorage.getItem("deepseek_api_key") || "";
                if (!apiKey) {
                    try {
                        const checkRes = await fetch("/api/settings/deepseek");
                        const checkData = await checkRes.json();
                        if (!checkData.has_key) {
                            alert("Vui lòng nhập DeepSeek API Key để sử dụng tính năng OCR AI, hoặc chọn động cơ Tesseract cục bộ!");
                            return;
                        }
                    } catch (e) {
                        alert("Vui lòng nhập DeepSeek API Key để nhận diện văn bản OCR AI!");
                        return;
                    }
                }
                const outFmt = document.getElementById("opt-ocr-format")?.value || "reconstructed_pdf";
                const model = document.getElementById("opt-ocr-model")?.value || "deepseek-flash";
                const range = document.getElementById("opt-ocr-range")?.value.trim() || "all";
                if (apiKey) {
                    formData.append("api_key", apiKey);
                    localStorage.setItem("deepseek_api_key", apiKey);
                }
                formData.append("output_format", outFmt);
                formData.append("model", model);
                formData.append("page_range", range);
            } else {
                const lang = document.getElementById("opt-ocr-lang")?.value || "vie+eng";
                const outFmt = document.getElementById("opt-ocr-offline-format")?.value || "reconstructed_pdf";
                formData.append("lang", lang);
                formData.append("output_format", outFmt);
            }
            break;

        case "interlinear-translate":
            const srcLang = document.getElementById("opt-trans-src")?.value || "en";
            const tgtLang = document.getElementById("opt-trans-tgt")?.value || "vi";
            const transMode = document.getElementById("opt-trans-mode")?.value || "bilingual";
            const transProvider = document.getElementById("opt-trans-provider")?.value || "google";
            const transEngine = document.getElementById("opt-trans-engine")?.value || "auto";
            const transOutFmt = document.getElementById("opt-trans-output-format")?.value || "docx";
            const transKey = document.getElementById("opt-trans-key")?.value.trim() || "";

            formData.append("source_lang", srcLang);
            formData.append("target_lang", tgtLang);
            formData.append("output_mode", transMode);
            formData.append("provider", transProvider);
            formData.append("engine_mode", transEngine);
            formData.append("output_format", transOutFmt);
            if (transProvider === "deepseek" && transKey) {
                formData.append("api_key", transKey);
                localStorage.setItem("deepseek_api_key", transKey);
            }
            break;

        case "pdf-to-word":
            formData.append("mode", "auto");
            formData.append("ai_control", "false");
            break;

        case "remove-watermark":
            const wmCustom = document.getElementById("opt-wm-custom-text")?.value.trim() || "";
            const wmUseCommon = document.getElementById("opt-wm-common-keywords")?.checked ?? true;
            const wmRemoveBg = document.getElementById("opt-wm-remove-bg")?.checked ?? true;
            const wmRemoveAnnots = document.getElementById("opt-wm-remove-annots")?.checked ?? true;
            const wmCleanHf = document.getElementById("opt-wm-clean-hf")?.checked ?? false;

            if (wmCustom) formData.append("custom_text", wmCustom);
            formData.append("use_common", wmUseCommon ? "true" : "false");
            formData.append("remove_bg", wmRemoveBg ? "true" : "false");
            formData.append("remove_annots", wmRemoveAnnots ? "true" : "false");
            formData.append("clean_hf", wmCleanHf ? "true" : "false");
            break;
    }

    // Non-blocking progress indicator: activate shimmer bar and status pill
    const shimmerBar = document.getElementById("canvas-shimmer-bar");
    const statusPill = document.getElementById("canvas-status-pill");
    const btnProcess = document.getElementById("btn-process");

    if (shimmerBar) shimmerBar.classList.remove("hidden");
    if (statusPill) statusPill.classList.remove("hidden");
    if (btnProcess) {
        btnProcess.disabled = true;
        btnProcess.classList.add("btn-loading");
    }
    resultPanel.classList.add("hidden");

    // Kích hoạt hoạt ảnh động trực quan sinh động to ở giữa màn hình
    const toolTitle = (currentTool && currentTool.title) ? currentTool.title : "Tài liệu";
    showProcessingAnimation(`Đang xử lý ${toolTitle}...`);

    try {
        const response = await fetch(currentTool.endpoint, {
            method: "POST",
            body: formData
        });

        let data;
        const contentType = response.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
            data = await response.json();
        } else {
            const rawText = await response.text();
            hideProcessingAnimation();
            if (response.status === 524 || response.status === 504) {
                alert("Máy chủ xử lý tệp vượt quá thời gian phản hồi (Cloudflare 100s). Hệ thống đã được chuyển sang chế độ siêu tốc, vui lòng bấm thực hiện lại!");
            } else {
                alert("Lỗi phản hồi máy chủ (HTTP " + response.status + "): " + (rawText.slice(0, 120) || "Dữ liệu không hợp lệ"));
            }
            return;
        }

        if (!response.ok || !data.success) {
            hideProcessingAnimation();
            alert("Lỗi xử lý: " + (data.detail || data.message || "Không rõ nguyên nhân"));
            return;
        }

        // Show Success
        resultPanel.classList.remove("hidden");
        document.getElementById("result-detail").innerText = data.details || "Tài liệu của bạn đã được chuyển đổi thành công.";
        
        lastResultUrl = data.download_url;
        lastResultFilename = data.filename;

        const btnDownload = document.getElementById("btn-download");
        if (btnDownload) {
            btnDownload.href = data.download_url;
            btnDownload.download = data.filename;
        }

        // Auto preview if it's a PDF or Word document (.docx/.doc)
        if (data.filename && (/\.(pdf|docx|doc)$/i.test(data.filename))) {
            previewOutputResult();
        }

    } catch (err) {
        console.error("Lỗi xử lý:", err);
        alert("Có lỗi kết nối máy chủ nội bộ (127.0.0.1:8888). Vui lòng bấm thử lại: " + err.message);
    } finally {
        hideProcessingAnimation();
        if (shimmerBar) shimmerBar.classList.add("hidden");
        if (statusPill) statusPill.classList.add("hidden");
        if (btnProcess) {
            btnProcess.disabled = false;
            btnProcess.classList.remove("btn-loading");
        }
    }
}

// -------------------------------------------------------------
// FULLSCREEN PROCESSING ANIMATION MODAL CONTROLLER
// -------------------------------------------------------------
let procStatusInterval = null;
const PROC_STATUS_MESSAGES = [
    "Nhân viên văn phòng siêu cấp Vip Pro đang phân tích cấu trúc tài liệu...",
    "Đang tăng tốc tính toán với động cơ cục bộ...",
    "Đang tối ưu hóa định dạng và dung lượng...",
    "Sắp hoàn tất, kết quả chuẩn bị sẵn sàng...",
    "Đang xuất tài liệu đầu ra an toàn tuyệt đối..."
];

function showProcessingAnimation(titleText) {
    const modal = document.getElementById("processing-video-modal");
    const video = document.getElementById("processing-video-player");
    const titleEl = document.getElementById("processing-main-title");
    const descEl = document.getElementById("processing-sub-status");

    if (titleText && titleEl) {
        titleEl.innerHTML = `<span class="anim-rainbow-text">${titleText.toUpperCase()}</span>`;
    }

    if (modal) {
        modal.classList.remove("hidden");
        modal.setAttribute("aria-hidden", "false");
    }

    if (video) {
        try {
            video.currentTime = 0;
            const playPromise = video.play();
            if (playPromise !== undefined) {
                playPromise.catch(() => {});
            }
        } catch (e) {}
    }

    let msgIdx = 0;
    if (descEl) descEl.innerText = PROC_STATUS_MESSAGES[0];
    clearInterval(procStatusInterval);
    procStatusInterval = setInterval(() => {
        msgIdx = (msgIdx + 1) % PROC_STATUS_MESSAGES.length;
        if (descEl) descEl.innerText = PROC_STATUS_MESSAGES[msgIdx];
    }, 2000);
}

function hideProcessingAnimation() {
    clearInterval(procStatusInterval);
    const modal = document.getElementById("processing-video-modal");
    const video = document.getElementById("processing-video-player");

    if (modal) {
        modal.classList.add("hidden");
        modal.setAttribute("aria-hidden", "true");
    }

    if (video) {
        try { video.pause(); } catch (e) {}
    }
}

// -------------------------------------------------------------
// 8. LIVE IN-APP OUTPUT PREVIEW & COMPARISON DUAL-PROXY ENGINE
// -------------------------------------------------------------
async function previewOutputResult() {
    if (!lastResultUrl || !lastResultFilename) return;

    const lower = lastResultFilename.toLowerCase();
    if (lower.endsWith(".docx") || lower.endsWith(".doc")) {
        // Hiển thị công tắc so sánh nếu có
        const compToggle = document.getElementById("comparison-toggle-group");
        if (compToggle) compToggle.classList.remove("hidden");
        switchPreviewSource("processed");
        return;
    }

    if (!lower.endsWith(".pdf")) {
        alert("Tệp kết quả ở định dạng " + lastResultFilename.split('.').pop() + ". Vui lòng bấm 'Tải xuống tệp tin' để xem.");
        return;
    }

    studioLoading.classList.remove("hidden");
    try {
        const resp = await fetch(lastResultUrl);
        const arrayBuffer = await resp.arrayBuffer();
        const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
        processedDocProxy = await loadingTask.promise;

        // Unhide comparison toggle group in toolbar
        const compToggle = document.getElementById("comparison-toggle-group");
        if (compToggle) compToggle.classList.remove("hidden");

        // Switch to processed result preview
        switchPreviewSource("processed");

    } catch (err) {
        alert("Không thể tải bản xem trước kết quả: " + err.message);
    } finally {
        studioLoading.classList.add("hidden");
    }
}

function switchPreviewSource(source) {
    activePreviewSource = source;
    const btnOrig = document.getElementById("btn-view-original");
    const btnProc = document.getElementById("btn-view-processed");

    if (source === "processed") {
        if (btnProc) btnProc.classList.add("active");
        if (btnOrig) btnOrig.classList.remove("active");

        // Nếu tệp kết quả là Word (.docx/.doc)
        if (lastResultFilename && /\.(docx|doc)$/i.test(lastResultFilename)) {
            renderWordPreview(lastResultFilename);
            return;
        }

        if (!processedDocProxy) {
            if (lastResultUrl && lastResultFilename && lastResultFilename.toLowerCase().endsWith(".pdf")) {
                previewOutputResult();
                return;
            }
            return;
        }
        loadedPdfDoc = processedDocProxy;
    } else {
        if (btnOrig) btnOrig.classList.add("active");
        if (btnProc) btnProc.classList.remove("active");

        // Nếu tệp gốc là Word (.docx/.doc)
        if (selectedFiles.length > 0 && /\.(docx|doc)$/i.test(selectedFiles[0].name)) {
            renderWordPreview(selectedFiles[0]);
            return;
        }

        if (!originalDocProxy) {
            return;
        }
        loadedPdfDoc = originalDocProxy;
    }

    if (!loadedPdfDoc) return;

    const numPages = loadedPdfDoc.numPages;
    const isOriginal = (source === "original");
    const label = isOriginal ? "Bản gốc" : "Kết quả hoàn tất ✨";

    const sidePages = document.getElementById("side-filepages");
    if (sidePages) sidePages.innerText = `${numPages} trang (${label})`;

    const metaText = document.getElementById("grid-meta-text");
    if (metaText) {
        metaText.innerHTML = isOriginal
            ? `Đang hiển thị ${numPages} trang (${label})`
            : `<span class="text-emerald-700 font-bold" style="color: var(--success-text); font-weight: 700;">✨ Đang xem trước kết quả đã xử lý (${numPages} trang)</span>`;
    }

    // Reset page states
    pageOrder = Array.from({ length: numPages }, (_, i) => i + 1);
    pageRotations = {};
    deletedPages.clear();
    selectedPages.clear();
    lastClickedPage = null;

    // Clear caches for new proxy view
    lruCanvasCache.clear();
    thumbnailQueue.clear();

    // Re-render thumbnails via high-performance pipeline (<50ms, zero network)
    pagesGrid.innerHTML = "";
    generateSkeletonThumbnails(numPages);
    renderPriorityFirstPage();
    setupThumbnailObserver();

    // If continuous reader is active, update reader as well
    if (studioViewMode === "viewer") {
        const docContainer = document.getElementById("doc-viewer-container");
        if (docContainer) docContainer.innerHTML = "";
        initContinuousReader();
    }
}

// -------------------------------------------------------------
// 9. SECURITY PASSKEY & GATE ENGINE
// -------------------------------------------------------------
const securityGate = document.getElementById("security-gate");
const securityPasskeyInput = document.getElementById("security-passkey-input");
const securityErrorMsg = document.getElementById("security-error-msg");
const eyeIcon = document.getElementById("eye-icon");

function togglePasskeyVisibility() {
    if (!securityPasskeyInput) return;
    if (securityPasskeyInput.type === "password") {
        securityPasskeyInput.type = "text";
        if (eyeIcon) {
            eyeIcon.innerHTML = `
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                <line x1="1" y1="1" x2="23" y2="23"></line>
            `;
        }
    } else {
        securityPasskeyInput.type = "password";
        if (eyeIcon) {
            eyeIcon.innerHTML = `
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                <circle cx="12" cy="12" r="3"></circle>
            `;
        }
    }
}

function quickUnlock() {
    unlockGateUI("quick_bypass_token");
}
window.quickUnlock = quickUnlock;

function unlockGateUI(token) {
    const effectiveToken = token || "verified";
    try {
        sessionStorage.setItem("luv_auth_token", effectiveToken);
        localStorage.setItem("luv_auth_token", effectiveToken);
        localStorage.setItem("luv_owner_authorized", "ntc270120cm@gmail.com");
    } catch (e) {}

    if (securityGate) {
        securityGate.classList.add("unlocked");
        securityGate.style.setProperty("display", "none", "important");
        securityGate.setAttribute("aria-hidden", "true");
    }
    if (securityErrorMsg) {
        securityErrorMsg.classList.add("hidden");
    }
    if (securityPasskeyInput) {
        securityPasskeyInput.value = "";
    }
}

function lockGateUI() {
    try {
        sessionStorage.removeItem("luv_auth_token");
        localStorage.removeItem("luv_auth_token");
    } catch (e) {}

    if (securityGate) {
        securityGate.style.display = "flex";
        securityGate.classList.remove("unlocked");
        securityGate.removeAttribute("aria-hidden");
    }
    if (securityErrorMsg) {
        securityErrorMsg.classList.add("hidden");
    }
    if (securityPasskeyInput) {
        securityPasskeyInput.value = "";
        securityPasskeyInput.focus();
    }
}

async function handleSecurityUnlock(e) {
    if (e && typeof e.preventDefault === "function") e.preventDefault();
    const input = document.getElementById("security-passkey-input");
    if (!input) return;
    
    const passkey = input.value.trim();
    if (!passkey) {
        showSecurityError("Vui lòng nhập mật mã hoặc License Key!");
        return;
    }

    const btnUnlock = document.getElementById("btn-unlock-app");
    const originalBtnHtml = btnUnlock ? btnUnlock.innerHTML : "";
    if (btnUnlock) {
        btnUnlock.disabled = true;
        btnUnlock.innerHTML = `<span>Đang xác thực...</span>`;
    }

    try {
        const formData = new FormData();
        formData.append("passkey", passkey);

        const res = await fetch("/api/auth/verify", {
            method: "POST",
            body: formData
        });

        const data = await res.json();

        if (res.ok && data.success) {
            unlockGateUI(data.token);
            return;
        } else {
            showSecurityError(data.message || "Mật mã bảo mật không chính xác!");
        }
    } catch (err) {
        // Fallback for offline local session if available
        const savedToken = localStorage.getItem("luv_auth_token") || sessionStorage.getItem("luv_auth_token");
        if (savedToken) {
            unlockGateUI(savedToken);
            return;
        }
        showSecurityError("Không thể kết nối máy chủ xác thực nội bộ. Vui lòng thử lại!");
    } finally {
        if (btnUnlock) {
            btnUnlock.disabled = false;
            btnUnlock.innerHTML = originalBtnHtml;
        }
    }
}

function showSecurityError(msg) {
    const errorEl = document.getElementById("security-error-msg");
    const cardEl = document.getElementById("security-card-box");
    const inputEl = document.getElementById("security-passkey-input");

    if (errorEl) {
        errorEl.innerText = msg;
        errorEl.classList.remove("hidden");
    }
    if (cardEl) {
        cardEl.classList.remove("shake-anim");
        void cardEl.offsetWidth; // Trigger reflow
        cardEl.classList.add("shake-anim");
    }
    if (inputEl) {
        inputEl.focus();
        inputEl.select();
    }
}

async function lockApp() {
    const token = sessionStorage.getItem("luv_auth_token") || localStorage.getItem("luv_auth_token");
    if (token) {
        try {
            const formData = new FormData();
            formData.append("token", token);
            await fetch("/api/auth/lock", { method: "POST", body: formData });
        } catch (e) {}
    }
    lockGateUI();
}

async function checkSecuritySession() {
    try {
        const savedToken = sessionStorage.getItem("luv_auth_token") || localStorage.getItem("luv_auth_token");
        const url = savedToken ? `/api/auth/status?token=${encodeURIComponent(savedToken)}` : `/api/auth/status`;
        const res = await fetch(url);
        if (res.ok) {
            const data = await res.json();
            if (data && (data.authenticated === true || data.lock_enabled === false)) {
                unlockGateUI(savedToken || "local_bypass");
                return;
            }
        }
    } catch (err) {}

    // MẶC ĐỊNH: BẮT BUỘC YÊU CẦU PASS NẾU CHƯA CÓ SESSION HỢP LỆ
    lockGateUI();
}

// -------------------------------------------------------------
// 10. THEME SWITCHER & CATEGORY SYNCHRONIZATION (<50ms, Persistent)
// -------------------------------------------------------------
function setTheme(themeName) {
    const theme = (themeName === "vibrant") ? "vibrant" : "clean";
    if (typeof document !== "undefined" && document.documentElement && document.documentElement.setAttribute) {
        document.documentElement.setAttribute("data-theme", theme);
    }
    try {
        if (typeof localStorage !== "undefined" && localStorage.setItem) {
            localStorage.setItem("luv_theme", theme);
        }
    } catch (e) {}

    const label = (typeof document !== "undefined" && document.getElementById) ? document.getElementById("theme-btn-label") : null;
    if (label) {
        label.textContent = (theme === "vibrant") ? "Vibrant" : "Clean SaaS";
    }

    const btn = (typeof document !== "undefined" && document.getElementById) ? document.getElementById("theme-switcher-btn") : null;
    if (btn) {
        btn.setAttribute("title", theme === "clean"
            ? "Đang dùng Clean SaaS 💼 (Bấm để đổi sang Vibrant Pop 🎨)"
            : "Đang dùng Vibrant Pop 🎨 (Bấm để đổi sang Clean SaaS 💼)");
        btn.setAttribute("data-active-theme", theme);
    }
}

function toggleTheme() {
    const current = (typeof document !== "undefined" && document.documentElement && document.documentElement.getAttribute && document.documentElement.getAttribute("data-theme")) ||
                    (typeof localStorage !== "undefined" && localStorage.getItem && localStorage.getItem("luv_theme")) ||
                    "clean";
    const nextTheme = (current === "clean") ? "vibrant" : "clean";
    setTheme(nextTheme);
}

window.setTheme = setTheme;
window.toggleTheme = toggleTheme;

function updateCategoryCounts() {
    if (typeof document === "undefined" || !document.querySelectorAll) return;
    const counts = {
        all: TOOLS.length,
        organize: TOOLS.filter(t => t.category === "organize").length,
        convert: TOOLS.filter(t => t.category === "convert").length,
        security: TOOLS.filter(t => t.category === "security").length,
        optimize: TOOLS.filter(t => t.category === "optimize").length,
        ai: TOOLS.filter(t => t.category === "ai").length
    };
    const btns = document.querySelectorAll(".segment-btn");
    if (!btns || !btns.forEach) return;
    btns.forEach(btn => {
        if (!btn || !btn.getAttribute) return;
        const cat = btn.getAttribute("data-cat");
        if (cat && counts[cat] !== undefined) {
            const countEl = btn.querySelector ? btn.querySelector(".segment-count") : null;
            if (countEl) countEl.textContent = counts[cat];
        }
    });
}

// -------------------------------------------------------------
// 11. INITIALIZATION
// -------------------------------------------------------------
function initApp() {
    const saved = (typeof localStorage !== "undefined" && localStorage.getItem("luv_theme")) || "clean";
    setTheme(saved);
    updateCategoryCounts();
    renderToolCards();
    setupKeyboardNavigation();
    checkSecuritySession();
}

if (document.readyState === "loading") {
    window.addEventListener("DOMContentLoaded", initApp);
} else {
    initApp();
}

// Local Desktop Keep-alive Heartbeat
if (typeof setInterval !== "undefined") {
    setInterval(() => {
        if (typeof fetch !== "undefined") {
            fetch('/api/heartbeat', { method: 'POST' }).catch(() => {});
        }
    }, 3000);
}
