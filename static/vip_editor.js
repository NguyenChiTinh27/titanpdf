/**
 * ==========================================================================
 * TRÌNH CHỈNH SỬA VIP PRO - VIP PDF EDITOR STUDIO
 * 100% Offline • Zero CDN • Động cơ tương tác Vector cao cấp
 * Vẽ tự do (Pen), Dạ quang (Highlighter), Chèn chữ (Text),
 * Hình khối co giãn đa hướng (Resize Handles), Chèn ảnh, Xuất PDF Vector.
 * ==========================================================================
 */

const VIP_STATE = {
    loadedFile: null,
    pdfDoc: null,
    isImageDoc: false,
    imageDocObj: null,
    imageDocDataUrl: null,
    imageDocWidth: 800,
    imageDocHeight: 1100,
    replacingImageId: null,
    croppingAnnotId: null,
    pageCount: 0,
    currentPage: 1,
    zoom: 1.5,
    activeTool: 'select',   // 'select' | 'hand' | 'pen' | 'highlighter' | 'text' | 'rect' | 'circle' | 'line'
    activeColor: '#ef4444',
    fillColor: 'none',
    strokeWidth: 2.5,
    opacity: 1.0,
    annotations: [],        // [{ id, page, type, x, y, width, height, ... }]
    undoStack: [],
    redoStack: [],
    selectedAnnotId: null,
    isDrawing: false,
    activePageNum: 1,
    isSidebarCollapsed: false
};

// -------------------------------------------------------------
// 1. MAIN TAB SWITCHER (Tools Dashboard <-> VIP Editor <-> AI Studio <-> MSDS CIL)
// -------------------------------------------------------------
function switchMainTab(tab, subTab = null) {
    if (typeof window.isSecurityAuthorized === "function" && !window.isSecurityAuthorized()) {
        if (typeof window.lockApp === "function") window.lockApp();
        return false;
    }
    if ((tab === 'ai' || tab === 'ai-studio') && subTab === 'msds') {
        tab = 'msds';
    }
    if (tab === 'msds-studio') tab = 'msds';
    if (tab === 'hse-studio') tab = 'hse';
    if (tab === 'hse-tracker' || tab === 'defect-tracker' || tab === 'tracker') tab = 'hse-tracker';
    if (tab === 'legal-lookup') tab = 'legal';
    if (tab === 'ai-studio') tab = 'ai';
    if (tab === 'vip-editor') tab = 'editor';
    if (tab === 'inventory' || tab === 'nxt') tab = 'monthly-inventory';
    if (tab === 'gatepass' || tab === 'gatepass-studio') tab = 'gatepass';
    if (tab === 'license' || tab === 'license-manager') tab = 'license';

    // RBAC: Check guest permissions before switching tabs
    if (document.body.getAttribute('data-role') === 'guest' && window.GUEST_PERMISSIONS_CACHE) {
        if (tab === 'license') {
            alert('Khu vực Quản lý Bản quyền chỉ dành riêng cho Quản trị viên / Chủ sở hữu (Owner).');
            return;
        }
        if (typeof isToolAllowedForGuest === "function") {
            if (tab === 'editor' && !isToolAllowedForGuest('vip-editor')) {
                alert('Công cụ [VIP Editor] đã bị khóa đối với Chế độ Khách bởi Quản trị viên.');
                return;
            }
            if (tab === 'ai' && !isToolAllowedForGuest('ai-studio') && !isToolAllowedForGuest('ai-translator') && !isToolAllowedForGuest('ai-summarizer') && !isToolAllowedForGuest('ocr') && !isToolAllowedForGuest('interlinear-translate')) {
                alert('Công cụ [AI Studio] đã bị khóa đối với Chế độ Khách bởi Quản trị viên.');
                return;
            }
            if (tab === 'hse' && !isToolAllowedForGuest('hse-studio')) {
                alert('Công cụ [HSE Report Studio] đã bị khóa đối với Chế độ Khách bởi Quản trị viên.');
                return;
            }
            if (tab === 'legal' && !isToolAllowedForGuest('legal-lookup')) {
                alert('Công cụ [Tra Cứu Pháp Lý] đã bị khóa đối với Chế độ Khách bởi Quản trị viên.');
                return;
            }
            if (tab === 'msds' && !isToolAllowedForGuest('msds-studio')) {
                alert('Công cụ [Sổ Hóa Chất MSDS & CIL] đã bị khóa đối với Chế độ Khách bởi Quản trị viên.');
                return;
            }
            if (tab === 'monthly-inventory' && !isToolAllowedForGuest('monthly-inventory')) {
                alert('Công cụ [Báo Cáo Tháng (NXT)] đã bị khóa đối với Chế độ Khách bởi Quản trị viên.');
                return;
            }
            if (tab === 'gatepass' && !isToolAllowedForGuest('gatepass-studio')) {
                alert('Công cụ [Phiếu Xuất & Vật Tư] đã bị khóa đối với Chế độ Khách bởi Quản trị viên.');
                return;
            }
        } else {
            const groups = window.GUEST_PERMISSIONS_CACHE.tool_groups || {};
            if (tab === 'editor' && groups.pro_tools === false) {
                alert('Công cụ [VIP Editor] đã bị khóa đối với Chế độ Khách bởi Quản trị viên.');
                return;
            }
            if (tab === 'ai' && groups.studios === false && groups.pro_tools === false) {
                alert('Công cụ [AI Studio] đã bị khóa đối với Chế độ Khách bởi Quản trị viên.');
                return;
            }
            if (tab === 'hse' && groups.studios === false) {
                alert('Công cụ [HSE Report Studio] đã bị khóa đối với Chế độ Khách bởi Quản trị viên.');
                return;
            }
            if (tab === 'legal' && groups.legal === false) {
                alert('Công cụ [Tra Cứu Pháp Lý] đã bị khóa đối với Chế độ Khách bởi Quản trị viên.');
                return;
            }
            if (tab === 'msds' && groups.msds === false) {
                alert('Công cụ [Sổ Hóa Chất MSDS & CIL] đã bị khóa đối với Chế độ Khách bởi Quản trị viên.');
                return;
            }
            if (tab === 'monthly-inventory' && groups.monthly_inventory === false) {
                alert('Công cụ [Báo Cáo Tháng (NXT)] đã bị khóa đối với Chế độ Khách bởi Quản trị viên.');
                return;
            }
            if (tab === 'gatepass' && groups.gatepass === false) {
                alert('Công cụ [Phiếu Xuất & Vật Tư] đã bị khóa đối với Chế độ Khách bởi Quản trị viên.');
                return;
            }
        }
    }

    const homeView = document.getElementById("home-view");
    const wsView = document.getElementById("workspace-view");
    const editorView = document.getElementById("vip-editor-view");
    const aiView = document.getElementById("ai-studio-view");
    const msdsView = document.getElementById("msds-studio-view");
    const hseView = document.getElementById("hse-studio-view");
    const hseTrackerView = document.getElementById("hse-tracker-view");
    const legalView = document.getElementById("legal-lookup-view");
    const monthlyView = document.getElementById("monthly-inventory-view");
    const gatepassView = document.getElementById("gatepass-studio-view");
    const licenseView = document.getElementById("license-manager-view");
    const navTools = document.getElementById("nav-tab-tools");
    const navEditor = document.getElementById("nav-tab-editor");
    const navAi = document.getElementById("nav-tab-ai");
    const navMsds = document.getElementById("nav-tab-msds");
    const navHse = document.getElementById("nav-tab-hse");
    const navHseTracker = document.getElementById("nav-tab-hse-tracker");
    const navLegal = document.getElementById("nav-tab-legal");
    const navMonthly = document.getElementById("nav-tab-inventory") || document.getElementById("nav-tab-monthly-inventory");
    const navGatepass = document.getElementById("nav-tab-gatepass");
    const navLicense = document.getElementById("nav-tab-license");
    const footer = document.querySelector(".footer");

    // Reset active nav states & aria-selected attributes
    [navTools, navEditor, navAi, navMsds, navHse, navHseTracker, navLegal, navMonthly, navGatepass, navLicense].forEach(n => {
        if (n) {
            n.classList.remove("active");
            n.setAttribute("aria-selected", "false");
        }
    });

    // 1. Luôn cuộn trang lên đỉnh (0, 0) ngay lập tức để thanh Header/Navbar không bị trôi/lỗi đè
    try {
        window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    } catch (_e) {
        window.scrollTo(0, 0);
    }
    if (document.documentElement) document.documentElement.scrollTop = 0;
    if (document.body) document.body.scrollTop = 0;

    // 2. Danh sách toàn bộ 10 view chính trong hệ thống
    const allViews = [
        homeView, wsView, editorView, aiView, msdsView,
        hseView, hseTrackerView, legalView, monthlyView, gatepassView, licenseView
    ];

    // 3. Ẩn toàn bộ tất cả các view trước khi bật view được chọn
    allViews.forEach(v => {
        if (v) {
            v.classList.add("hidden");
            if (v === licenseView) {
                v.style.setProperty("display", "none", "important");
            }
        }
    });

    if (tab === 'editor') {
        if (editorView) editorView.classList.remove("hidden");
        if (footer) footer.classList.add("hidden");
        document.body.classList.add("vip-editor-active");
        document.body.classList.remove("msds-studio-active");

        if (navEditor) { navEditor.classList.add("active"); navEditor.setAttribute("aria-selected", "true"); }

        // If no file loaded yet, check if workspace has a file to import
        if (!VIP_STATE.loadedFile && typeof selectedFiles !== 'undefined' && selectedFiles.length > 0) {
            loadVipPdfDocument(selectedFiles[0]);
        }
    } else if (tab === 'msds') {
        if (msdsView) msdsView.classList.remove("hidden");
        if (footer) footer.classList.add("hidden");
        document.body.classList.remove("vip-editor-active");
        document.body.classList.add("msds-studio-active");

        if (navMsds) { navMsds.classList.add("active"); navMsds.setAttribute("aria-selected", "true"); }

        if (typeof loadMsdsChemicalsList === 'function') {
            loadMsdsChemicalsList();
        }
    } else if (tab === 'monthly-inventory') {
        if (monthlyView) monthlyView.classList.remove("hidden");
        if (footer) footer.classList.remove("hidden");
        document.body.classList.remove("vip-editor-active");
        document.body.classList.remove("msds-studio-active");

        if (navMonthly) { navMonthly.classList.add("active"); navMonthly.setAttribute("aria-selected", "true"); }

        if (typeof window.initMonthlyInventory === 'function') {
            window.initMonthlyInventory();
        }
    } else if (tab === 'ai') {
        if (aiView) aiView.classList.remove("hidden");
        if (footer) footer.classList.remove("hidden");
        document.body.classList.remove("vip-editor-active");
        document.body.classList.remove("msds-studio-active");

        if (navAi) { navAi.classList.add("active"); navAi.setAttribute("aria-selected", "true"); }

        if (subTab && typeof switchAiSubTab === 'function') {
            switchAiSubTab(subTab);
        }
    } else if (tab === 'hse') {
        if (hseView) hseView.classList.remove("hidden");
        if (footer) footer.classList.remove("hidden");
        document.body.classList.remove("vip-editor-active");
        document.body.classList.remove("msds-studio-active");

        if (navHse) { navHse.classList.add("active"); navHse.setAttribute("aria-selected", "true"); }

        if (typeof window.initHseStudio === 'function') {
            window.initHseStudio();
        }
    } else if (tab === 'hse-tracker') {
        if (hseTrackerView) hseTrackerView.classList.remove("hidden");
        if (footer) footer.classList.remove("hidden");
        document.body.classList.remove("vip-editor-active");
        document.body.classList.remove("msds-studio-active");

        if (navHseTracker) { navHseTracker.classList.add("active"); navHseTracker.setAttribute("aria-selected", "true"); }

        if (typeof window.initHseDefectTracker === 'function') {
            window.initHseDefectTracker();
        }
    } else if (tab === 'legal') {
        if (legalView) legalView.classList.remove("hidden");
        if (footer) footer.classList.remove("hidden");
        document.body.classList.remove("vip-editor-active");
        document.body.classList.remove("msds-studio-active");

        if (navLegal) { navLegal.classList.add("active"); navLegal.setAttribute("aria-selected", "true"); }

        if (typeof window.initLegalCatalog === 'function') {
            window.initLegalCatalog();
        }
    } else if (tab === 'gatepass') {
        if (gatepassView) gatepassView.classList.remove("hidden");
        if (footer) footer.classList.remove("hidden");
        document.body.classList.remove("vip-editor-active");
        document.body.classList.remove("msds-studio-active");

        if (navGatepass) { navGatepass.classList.add("active"); navGatepass.setAttribute("aria-selected", "true"); }

        if (window.location.hash !== '#gatepass-studio' && window.location.hash !== '#gatepass') {
            history.replaceState(null, '', '#gatepass-studio');
        }

        if (window.GatePassStudio && typeof window.GatePassStudio.init === 'function') {
            window.GatePassStudio.init();
        } else if (typeof window.initGatePassStudio === 'function') {
            window.initGatePassStudio();
        }
    } else if (tab === 'license') {
        if (licenseView) {
            licenseView.style.removeProperty("display");
            licenseView.classList.remove("hidden");
        }
        if (footer) footer.classList.remove("hidden");
        document.body.classList.remove("vip-editor-active");
        document.body.classList.remove("msds-studio-active");

        if (navLicense) { navLicense.classList.add("active"); navLicense.setAttribute("aria-selected", "true"); }

        if (window.location.hash !== '#license-manager' && window.location.hash !== '#license') {
            history.replaceState(null, '', '#license-manager');
        }

        if (window.LicenseManager && typeof window.LicenseManager.init === 'function') {
            window.LicenseManager.init();
        } else if (typeof window.initLicenseManager === 'function') {
            window.initLicenseManager();
        }
    } else {
        if (homeView) homeView.classList.remove("hidden");
        if (footer) footer.classList.remove("hidden");
        document.body.classList.remove("vip-editor-active");
        document.body.classList.remove("msds-studio-active");

        if (navTools) { navTools.classList.add("active"); navTools.setAttribute("aria-selected", "true"); }
        if (window.location.hash === '#gatepass-studio' || window.location.hash === '#gatepass') {
            history.replaceState(null, '', window.location.pathname + window.location.search);
        }
    }

    if (typeof window.applyNavTabsGuestStyling === "function") {
        window.applyNavTabsGuestStyling();
    }
}

// URL Hash Router Bridge
window.addEventListener("DOMContentLoaded", () => {
    const handleHash = () => {
        const hash = window.location.hash.toLowerCase();
        if (hash === "#gatepass-studio" || hash === "#gatepass") {
            switchMainTab("gatepass");
        } else if (hash === "#monthly-inventory" || hash === "#inventory" || hash === "#nxt") {
            switchMainTab("monthly-inventory");
        } else if (hash === "#vip-editor" || hash === "#editor") {
            switchMainTab("editor");
        } else if (hash === "#msds" || hash === "#msds-studio") {
            switchMainTab("msds");
        } else if (hash === "#hse" || hash === "#hse-studio") {
            switchMainTab("hse");
        } else if (hash === "#legal" || hash === "#legal-lookup") {
            switchMainTab("legal");
        } else if (hash === "#license" || hash === "#license-manager") {
            switchMainTab("license");
        }
    };
    window.addEventListener("hashchange", handleHash);
    handleHash();
});

// -------------------------------------------------------------
// 2. FILE LOADING & INITIALIZATION (Supports PDF & Image Files)
// -------------------------------------------------------------
function handleVipFileInput(e) {
    if (e.target && e.target.files && e.target.files.length > 0) {
        loadVipPdfDocument(e.target.files[0]);
    }
}

async function loadVipPdfDocument(file) {
    if (!file) return;
    VIP_STATE.loadedFile = file;

    const filenameEl = document.getElementById("vip-active-filename");
    if (filenameEl) filenameEl.textContent = file.name;

    const isImage = file.type.startsWith("image/") || /\.(png|jpe?g|webp|bmp|gif)$/i.test(file.name);

    if (isImage) {
        VIP_STATE.isImageDoc = true;
        VIP_STATE.pdfDoc = null;
        try {
            const dataUrl = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = ev => resolve(ev.target.result);
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
            const img = await new Promise((resolve, reject) => {
                const image = new Image();
                image.onload = () => resolve(image);
                image.onerror = reject;
                image.src = dataUrl;
            });
            VIP_STATE.imageDocObj = img;
            VIP_STATE.imageDocDataUrl = dataUrl;
            VIP_STATE.imageDocWidth = img.naturalWidth || 800;
            VIP_STATE.imageDocHeight = img.naturalHeight || 1100;
            VIP_STATE.pageCount = 1;
            VIP_STATE.currentPage = 1;
            VIP_STATE.annotations = [];
            VIP_STATE.undoStack = [];
            VIP_STATE.redoStack = [];

            document.getElementById("vip-empty-dropzone")?.classList.add("hidden");
            const pagesContainer = document.getElementById("vip-pages-container");
            if (pagesContainer) {
                pagesContainer.classList.remove("hidden");
                pagesContainer.innerHTML = "";
            }
            document.getElementById("vip-bottom-nav")?.classList.remove("hidden");

            updateVipPageIndicator();
            await renderVipAllPages();
            await renderVipThumbnails();
            return;
        } catch (err) {
            alert("Lỗi nạp tệp hình ảnh vào Trình Chỉnh Sửa VIP Pro: " + err.message);
            return;
        }
    }

    VIP_STATE.isImageDoc = false;
    VIP_STATE.imageDocObj = null;

    try {
        const arrayBuffer = await file.arrayBuffer();
        const pdfDoc = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        VIP_STATE.pdfDoc = pdfDoc;
        VIP_STATE.pageCount = pdfDoc.numPages;
        VIP_STATE.currentPage = 1;
        VIP_STATE.annotations = [];
        VIP_STATE.undoStack = [];
        VIP_STATE.redoStack = [];

        // Show editor viewport & bottom nav
        document.getElementById("vip-empty-dropzone")?.classList.add("hidden");
        const pagesContainer = document.getElementById("vip-pages-container");
        if (pagesContainer) {
            pagesContainer.classList.remove("hidden");
            pagesContainer.innerHTML = "";
        }
        document.getElementById("vip-bottom-nav")?.classList.remove("hidden");

        updateVipPageIndicator();
        await renderVipAllPages();
        await renderVipThumbnails();
    } catch (err) {
        alert("Lỗi nạp tệp PDF vào Trình Chỉnh Sửa VIP Pro: " + err.message);
    }
}

// -------------------------------------------------------------
// 3. PAGE RENDERING (MAIN CANVAS & OVERLAYS)
// -------------------------------------------------------------
async function renderVipAllPages() {
    const container = document.getElementById("vip-pages-container");
    if (!container) return;
    container.innerHTML = "";

    // BRANCH A: Image Document Mode
    if (VIP_STATE.isImageDoc && VIP_STATE.imageDocObj) {
        const baseWidth = Math.min(850, window.innerWidth - 300);
        const ratio = VIP_STATE.imageDocHeight / VIP_STATE.imageDocWidth;
        const targetWidth = Math.round(baseWidth * (VIP_STATE.zoom / 1.5));
        const targetHeight = Math.round(targetWidth * ratio);

        const pageWrap = document.createElement("div");
        pageWrap.className = "vip-page-container";
        pageWrap.id = "vip-page-wrap-1";
        pageWrap.setAttribute("data-page", 1);
        pageWrap.style.width = `${targetWidth}px`;
        pageWrap.style.height = `${targetHeight}px`;

        const bgCanvas = document.createElement("canvas");
        bgCanvas.className = "vip-bg-canvas";
        bgCanvas.id = "vip-bg-canvas-1";
        bgCanvas.width = targetWidth;
        bgCanvas.height = targetHeight;
        bgCanvas.style.width = `${targetWidth}px`;
        bgCanvas.style.height = `${targetHeight}px`;
        const ctx = bgCanvas.getContext("2d");
        ctx.drawImage(VIP_STATE.imageDocObj, 0, 0, targetWidth, targetHeight);

        const drawCanvas = document.createElement("canvas");
        drawCanvas.className = "vip-draw-canvas";
        drawCanvas.id = "vip-draw-canvas-1";
        drawCanvas.setAttribute("data-page", 1);
        drawCanvas.width = targetWidth;
        drawCanvas.height = targetHeight;
        drawCanvas.style.width = `${targetWidth}px`;
        drawCanvas.style.height = `${targetHeight}px`;

        const annotLayer = document.createElement("div");
        annotLayer.className = "vip-annot-layer";
        annotLayer.id = "vip-annot-layer-1";
        annotLayer.setAttribute("data-page", 1);
        annotLayer.style.width = `${targetWidth}px`;
        annotLayer.style.height = `${targetHeight}px`;

        pageWrap.appendChild(bgCanvas);
        pageWrap.appendChild(drawCanvas);
        pageWrap.appendChild(annotLayer);
        container.appendChild(pageWrap);

        setupDrawEvents(drawCanvas, 1, targetWidth, targetHeight);
        redrawAllAnnotations();
        return;
    }

    // BRANCH B: PDF Document Mode
    if (!VIP_STATE.pdfDoc) return;

    for (let p = 1; p <= VIP_STATE.pageCount; p++) {
        const page = await VIP_STATE.pdfDoc.getPage(p);
        const viewport = page.getViewport({ scale: VIP_STATE.zoom });

        const pageWrap = document.createElement("div");
        pageWrap.className = "vip-page-container";
        pageWrap.id = `vip-page-wrap-${p}`;
        pageWrap.setAttribute("data-page", p);
        pageWrap.style.width = `${viewport.width}px`;
        pageWrap.style.height = `${viewport.height}px`;

        // 1. PDF Background Canvas
        const bgCanvas = document.createElement("canvas");
        bgCanvas.className = "vip-bg-canvas";
        bgCanvas.id = `vip-bg-canvas-${p}`;
        bgCanvas.width = viewport.width;
        bgCanvas.height = viewport.height;
        bgCanvas.style.width = `${viewport.width}px`;
        bgCanvas.style.height = `${viewport.height}px`;
        const ctx = bgCanvas.getContext("2d");
        await page.render({ canvasContext: ctx, viewport: viewport }).promise;

        // 2. Drawing Overlay Canvas (for pen / highlighter)
        const drawCanvas = document.createElement("canvas");
        drawCanvas.className = "vip-draw-canvas";
        drawCanvas.id = `vip-draw-canvas-${p}`;
        drawCanvas.setAttribute("data-page", p);
        drawCanvas.width = viewport.width;
        drawCanvas.height = viewport.height;
        drawCanvas.style.width = `${viewport.width}px`;
        drawCanvas.style.height = `${viewport.height}px`;

        // 3. Interactive Annotations DOM Layer
        const annotLayer = document.createElement("div");
        annotLayer.className = "vip-annot-layer";
        annotLayer.id = `vip-annot-layer-${p}`;
        annotLayer.setAttribute("data-page", p);
        annotLayer.style.width = `${viewport.width}px`;
        annotLayer.style.height = `${viewport.height}px`;

        pageWrap.appendChild(bgCanvas);
        pageWrap.appendChild(drawCanvas);
        pageWrap.appendChild(annotLayer);
        container.appendChild(pageWrap);

        setupDrawEvents(drawCanvas, p, viewport.width, viewport.height);
    }

    redrawAllAnnotations();
}

// Render Thumbnails in Left Sidebar
async function renderVipThumbnails() {
    const sidebar = document.getElementById("vip-sidebar");
    if (!sidebar) return;
    sidebar.innerHTML = "";

    // Image Document Thumbnail
    if (VIP_STATE.isImageDoc && VIP_STATE.imageDocObj) {
        const card = document.createElement("div");
        card.className = "vip-thumb-card active";
        card.id = "vip-thumb-1";
        card.onclick = () => scrollToVipPage(1);

        const pageNum = document.createElement("div");
        pageNum.className = "vip-thumb-page-num";
        pageNum.textContent = "Hình ảnh";

        const imgWrapper = document.createElement("div");
        imgWrapper.className = "vip-thumb-img-wrapper";

        const canvas = document.createElement("canvas");
        canvas.width = 160;
        canvas.height = Math.round(160 * (VIP_STATE.imageDocHeight / VIP_STATE.imageDocWidth));
        const ctx = canvas.getContext("2d");
        ctx.drawImage(VIP_STATE.imageDocObj, 0, 0, canvas.width, canvas.height);

        imgWrapper.appendChild(canvas);
        card.appendChild(pageNum);
        card.appendChild(imgWrapper);
        sidebar.appendChild(card);
        return;
    }

    if (!VIP_STATE.pdfDoc) return;

    for (let p = 1; p <= VIP_STATE.pageCount; p++) {
        const page = await VIP_STATE.pdfDoc.getPage(p);
        const viewport = page.getViewport({ scale: 0.25 });

        const card = document.createElement("div");
        card.className = `vip-thumb-card ${p === VIP_STATE.currentPage ? 'active' : ''}`;
        card.id = `vip-thumb-${p}`;
        card.onclick = () => scrollToVipPage(p);

        const pageNum = document.createElement("div");
        pageNum.className = "vip-thumb-page-num";
        pageNum.textContent = `Trang ${p}`;

        const imgWrapper = document.createElement("div");
        imgWrapper.className = "vip-thumb-img-wrapper";

        const canvas = document.createElement("canvas");
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const ctx = canvas.getContext("2d");
        await page.render({ canvasContext: ctx, viewport: viewport }).promise;

        imgWrapper.appendChild(canvas);
        card.appendChild(pageNum);
        card.appendChild(imgWrapper);
        sidebar.appendChild(card);
    }
}

function scrollToVipPage(p) {
    VIP_STATE.currentPage = p;
    updateVipPageIndicator();
    const target = document.getElementById(`vip-page-wrap-${p}`);
    if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    // Update active thumb
    document.querySelectorAll(".vip-thumb-card").forEach(c => c.classList.remove("active"));
    document.getElementById(`vip-thumb-${p}`)?.classList.add("active");
}

// -------------------------------------------------------------
// 4. DRAWING & CREATION ENGINE (PEN, HIGHLIGHTER, SHAPES, TEXT)
// -------------------------------------------------------------
function setupDrawEvents(canvas, pageNum, cWidth, cHeight) {
    const ctx = canvas.getContext("2d");
    let isDown = false;
    let startX = 0;
    let startY = 0;
    let currentPoints = [];

    canvas.addEventListener("mousedown", (e) => {
        if (VIP_STATE.activeTool === 'select' || VIP_STATE.activeTool === 'hand') return;

        isDown = true;
        VIP_STATE.activePageNum = pageNum;
        const rect = canvas.getBoundingClientRect();
        startX = e.clientX - rect.left;
        startY = e.clientY - rect.top;

        if (VIP_STATE.activeTool === 'pen' || VIP_STATE.activeTool === 'highlighter') {
            currentPoints = [{ x: startX, y: startY }];
            ctx.beginPath();
            ctx.moveTo(startX, startY);
        } else if (VIP_STATE.activeTool === 'text') {
            isDown = false;
            createVipTextAnnotation(pageNum, startX, startY, cWidth, cHeight);
        }
    });

    canvas.addEventListener("mousemove", (e) => {
        if (!isDown) return;
        const rect = canvas.getBoundingClientRect();
        const curX = e.clientX - rect.left;
        const curY = e.clientY - rect.top;

        if (VIP_STATE.activeTool === 'pen') {
            currentPoints.push({ x: curX, y: curY });
            ctx.strokeStyle = VIP_STATE.activeColor;
            ctx.lineWidth = VIP_STATE.strokeWidth * (VIP_STATE.zoom / 1.5);
            ctx.lineCap = "round";
            ctx.lineJoin = "round";
            ctx.lineTo(curX, curY);
            ctx.stroke();
        } else if (VIP_STATE.activeTool === 'highlighter') {
            currentPoints.push({ x: curX, y: curY });
            ctx.strokeStyle = VIP_STATE.activeColor;
            ctx.lineWidth = 18 * (VIP_STATE.zoom / 1.5);
            ctx.globalAlpha = 0.45;
            ctx.lineCap = "square";
            ctx.lineJoin = "round";
            ctx.lineTo(curX, curY);
            ctx.stroke();
            ctx.globalAlpha = 1.0;
        } else if (['rect', 'circle', 'line'].includes(VIP_STATE.activeTool)) {
            // Live preview shape
            ctx.clearRect(0, 0, cWidth, cHeight);
            ctx.strokeStyle = VIP_STATE.activeColor;
            ctx.lineWidth = VIP_STATE.strokeWidth * (VIP_STATE.zoom / 1.5);
            if (VIP_STATE.fillColor !== 'none') {
                ctx.fillStyle = VIP_STATE.fillColor;
            }

            if (VIP_STATE.activeTool === 'rect') {
                const w = curX - startX;
                const h = curY - startY;
                if (VIP_STATE.fillColor !== 'none') ctx.fillRect(startX, startY, w, h);
                ctx.strokeRect(startX, startY, w, h);
            } else if (VIP_STATE.activeTool === 'circle') {
                const rx = Math.abs(curX - startX) / 2;
                const ry = Math.abs(curY - startY) / 2;
                const cx = Math.min(startX, curX) + rx;
                const cy = Math.min(startY, curY) + ry;
                ctx.beginPath();
                ctx.ellipse(cx, cy, rx, ry, 0, 0, 2 * Math.PI);
                if (VIP_STATE.fillColor !== 'none') ctx.fill();
                ctx.stroke();
            } else if (VIP_STATE.activeTool === 'line') {
                ctx.beginPath();
                ctx.moveTo(startX, startY);
                ctx.lineTo(curX, curY);
                ctx.stroke();
            }
        }
    });

    canvas.addEventListener("mouseup", (e) => {
        if (!isDown) return;
        isDown = false;
        const rect = canvas.getBoundingClientRect();
        const endX = e.clientX - rect.left;
        const endY = e.clientY - rect.top;

        if (VIP_STATE.activeTool === 'pen' || VIP_STATE.activeTool === 'highlighter') {
            ctx.closePath();
            if (currentPoints.length > 1) {
                const annot = {
                    id: `annot_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
                    page: pageNum,
                    type: VIP_STATE.activeTool,
                    points: currentPoints,
                    color: VIP_STATE.activeColor,
                    width: VIP_STATE.activeTool === 'pen' ? VIP_STATE.strokeWidth : 16,
                    opacity: VIP_STATE.activeTool === 'pen' ? 1.0 : 0.45,
                    canvasWidth: cWidth,
                    canvasHeight: cHeight
                };
                addVipAnnotation(annot);
            }
        } else if (['rect', 'circle', 'line'].includes(VIP_STATE.activeTool)) {
            ctx.clearRect(0, 0, cWidth, cHeight);
            const w = Math.abs(endX - startX);
            const h = Math.abs(endY - startY);
            if (w > 5 || h > 5) {
                const annot = {
                    id: `annot_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
                    page: pageNum,
                    type: VIP_STATE.activeTool,
                    x: Math.min(startX, endX),
                    y: Math.min(startY, endY),
                    width: w,
                    height: h,
                    strokeColor: VIP_STATE.activeColor,
                    fillColor: VIP_STATE.fillColor,
                    strokeWidth: VIP_STATE.strokeWidth,
                    opacity: 1.0,
                    canvasWidth: cWidth,
                    canvasHeight: cHeight
                };
                addVipAnnotation(annot);
                renderInteractiveDomAnnot(annot);
                setVipTool('select');
                selectVipAnnotation(annot.id);
            }
        }
    });
}

function createVipTextAnnotation(pageNum, x, y, cWidth, cHeight) {
    const annot = {
        id: `annot_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
        page: pageNum,
        type: 'text',
        x: x,
        y: y,
        width: 140,
        height: 36,
        text: 'Nhập chữ...',
        color: VIP_STATE.activeColor,
        fontSize: 16,
        canvasWidth: cWidth,
        canvasHeight: cHeight
    };
    addVipAnnotation(annot);
    renderInteractiveDomAnnot(annot);
    setVipTool('select');
    selectVipAnnotation(annot.id);
}

// -------------------------------------------------------------
// 5. INTERACTIVE OBJECTS (SELECTION, RESIZE HANDLES, DRAG)
// -------------------------------------------------------------
function renderInteractiveDomAnnot(annot) {
    const layer = document.getElementById(`vip-annot-layer-${annot.page}`);
    if (!layer) return;

    // Check if element exists
    let el = document.getElementById(annot.id);
    if (!el) {
        el = document.createElement("div");
        el.id = annot.id;
        el.className = "vip-annot-item";
        layer.appendChild(el);
    }

    el.style.left = `${annot.x}px`;
    el.style.top = `${annot.y}px`;
    el.style.width = `${annot.width}px`;
    el.style.height = `${annot.height}px`;

    if (annot.type === 'rect') {
        el.style.border = `${annot.strokeWidth}px solid ${annot.strokeColor}`;
        el.style.backgroundColor = annot.fillColor !== 'none' ? annot.fillColor : 'transparent';
        el.style.borderRadius = '2px';
    } else if (annot.type === 'circle') {
        el.style.border = `${annot.strokeWidth}px solid ${annot.strokeColor}`;
        el.style.backgroundColor = annot.fillColor !== 'none' ? annot.fillColor : 'transparent';
        el.style.borderRadius = '50%';
    } else if (annot.type === 'text') {
        el.innerHTML = `<div class="vip-text-box" contenteditable="true" style="color:${annot.color}; font-size:${annot.fontSize}px;">${annot.text}</div>`;
        const txtBox = el.querySelector(".vip-text-box");
        txtBox.oninput = () => {
            annot.text = txtBox.innerText;
        };
    } else if (annot.type === 'image') {
        el.innerHTML = `<img src="${annot.imageBase64}" style="width:100%; height:100%; object-fit:contain; pointer-events:none;" />`;
    }

    setupInteractiveControls(el, annot);
}

function setupInteractiveControls(el, annot) {
    el.onclick = (e) => {
        if (VIP_STATE.activeTool === 'select') {
            e.stopPropagation();
            selectVipAnnotation(annot.id);
        }
    };

    // Drag to Move
    let isMoving = false;
    let startX = 0, startY = 0;
    let origX = 0, origY = 0;

    el.addEventListener("mousedown", (e) => {
        if (VIP_STATE.activeTool !== 'select' || e.target.classList.contains("vip-handle")) return;
        isMoving = true;
        startX = e.clientX;
        startY = e.clientY;
        origX = annot.x;
        origY = annot.y;
        selectVipAnnotation(annot.id);
        e.stopPropagation();

        const onMouseMove = (ev) => {
            if (!isMoving) return;
            const dx = ev.clientX - startX;
            const dy = ev.clientY - startY;
            annot.x = Math.max(0, origX + dx);
            annot.y = Math.max(0, origY + dy);
            el.style.left = `${annot.x}px`;
            el.style.top = `${annot.y}px`;
        };

        const onMouseUp = () => {
            isMoving = false;
            window.removeEventListener("mousemove", onMouseMove);
            window.removeEventListener("mouseup", onMouseUp);
        };

        window.addEventListener("mousemove", onMouseMove);
        window.addEventListener("mouseup", onMouseUp);
    });
}

// Select annotation & attach 8 resize handles (matching user screenshot)
function selectVipAnnotation(id) {
    VIP_STATE.selectedAnnotId = id;
    document.querySelectorAll(".vip-annot-item").forEach(el => {
        el.classList.remove("selected");
        el.querySelectorAll(".vip-handle").forEach(h => h.remove());
        el.querySelectorAll(".vip-image-toolbar").forEach(tb => tb.remove());
    });
    document.getElementById("vip-filter-popup-menu")?.remove();

    const targetEl = document.getElementById(id);
    const annot = VIP_STATE.annotations.find(a => a.id === id);
    if (!targetEl || !annot) return;

    targetEl.classList.add("selected");

    // Add 8 resize handles
    const handles = ['tl', 'tc', 'tr', 'ml', 'mr', 'bl', 'bc', 'br'];
    handles.forEach(pos => {
        const h = document.createElement("div");
        h.className = `vip-handle vip-handle-${pos}`;
        h.setAttribute("data-handle", pos);
        targetEl.appendChild(h);
        setupHandleResize(h, annot, targetEl, pos);
    });

    // If annotation is IMAGE -> Add floating Image Editing Toolbar
    if (annot.type === 'image') {
        const imgBar = document.createElement("div");
        imgBar.className = "vip-image-toolbar";
        imgBar.innerHTML = `
            <button type="button" title="Xoay ảnh 90°" onclick="rotateVipImage('${annot.id}')">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/></svg>
                <span>Xoay 90°</span>
            </button>
            <button type="button" title="Lật ngang (Flip H)" onclick="flipVipImage('${annot.id}', 'h')">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m8 3 4 8 5-5 5 15H2L8 3z"/><path d="M12 2v20"/></svg>
                <span>Lật ngang</span>
            </button>
            <button type="button" title="Lật dọc (Flip V)" onclick="flipVipImage('${annot.id}', 'v')">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12h20"/><path d="m5 8 7-6 7 6"/><path d="m5 16 7 6 7-6"/></svg>
                <span>Lật dọc</span>
            </button>
            <button type="button" title="Cắt xén ảnh (Crop)" onclick="openVipCropModal('${annot.id}')">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 2v14a2 2 0 0 0 2 2h14"/><path d="M18 22V8a2 2 0 0 0-2-2H2"/></svg>
                <span>Cắt ảnh</span>
            </button>
            <button type="button" title="Bộ lọc & Hiệu ứng màu" onclick="toggleVipImageFilterMenu('${annot.id}', event)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 1 0 20Z" fill="currentColor"/></svg>
                <span>Bộ lọc</span>
            </button>
            <button type="button" title="Đổi sang ảnh khác" onclick="replaceVipImage('${annot.id}')">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                <span>Đổi ảnh</span>
            </button>
            <button type="button" class="btn-del" title="Xóa ảnh" onclick="deleteVipSelectedAnnot()">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
            </button>
        `;
        targetEl.appendChild(imgBar);
    }
}

function setupHandleResize(handleEl, annot, itemEl, pos) {
    handleEl.addEventListener("mousedown", (e) => {
        e.stopPropagation();
        const startX = e.clientX;
        const startY = e.clientY;
        const origX = annot.x;
        const origY = annot.y;
        const origW = annot.width;
        const origH = annot.height;

        const onMove = (ev) => {
            const dx = ev.clientX - startX;
            const dy = ev.clientY - startY;

            if (pos.includes('r')) annot.width = Math.max(20, origW + dx);
            if (pos.includes('b')) annot.height = Math.max(20, origH + dy);
            if (pos.includes('l')) {
                const nw = Math.max(20, origW - dx);
                annot.x = origX + (origW - nw);
                annot.width = nw;
            }
            if (pos.includes('t')) {
                const nh = Math.max(20, origH - dy);
                annot.y = origY + (origH - nh);
                annot.height = nh;
            }

            itemEl.style.left = `${annot.x}px`;
            itemEl.style.top = `${annot.y}px`;
            itemEl.style.width = `${annot.width}px`;
            itemEl.style.height = `${annot.height}px`;
        };

        const onUp = () => {
            window.removeEventListener("mousemove", onMove);
            window.removeEventListener("mouseup", onUp);
        };

        window.addEventListener("mousemove", onMove);
        window.addEventListener("mouseup", onUp);
    });
}

function deleteVipSelectedAnnot() {
    if (!VIP_STATE.selectedAnnotId) return;
    const idx = VIP_STATE.annotations.findIndex(a => a.id === VIP_STATE.selectedAnnotId);
    if (idx !== -1) {
        document.getElementById(VIP_STATE.selectedAnnotId)?.remove();
        VIP_STATE.annotations.splice(idx, 1);
        VIP_STATE.selectedAnnotId = null;
        redrawAllAnnotations();
    }
}

// -------------------------------------------------------------
// 6. REDRAWING & RENDERING PIPELINE
// -------------------------------------------------------------
function addVipAnnotation(annot) {
    VIP_STATE.annotations.push(annot);
    VIP_STATE.undoStack.push({ action: 'add', annot: annot });
    VIP_STATE.redoStack = [];
}

function redrawAllAnnotations() {
    // Clear all draw canvases
    for (let p = 1; p <= VIP_STATE.pageCount; p++) {
        const drawC = document.getElementById(`vip-draw-canvas-${p}`);
        if (drawC) {
            const ctx = drawC.getContext("2d");
            ctx.clearRect(0, 0, drawC.width, drawC.height);
        }
    }

    // Redraw pen & highlighter on overlay canvas; render DOM shapes
    VIP_STATE.annotations.forEach(annot => {
        if (annot.type === 'pen' || annot.type === 'highlighter') {
            const drawC = document.getElementById(`vip-draw-canvas-${annot.page}`);
            if (drawC) {
                const ctx = drawC.getContext("2d");
                ctx.beginPath();
                ctx.strokeStyle = annot.color;
                ctx.lineWidth = annot.width * (VIP_STATE.zoom / 1.5);
                ctx.lineCap = annot.type === 'pen' ? "round" : "square";
                ctx.lineJoin = "round";
                if (annot.type === 'highlighter') ctx.globalAlpha = annot.opacity || 0.45;

                annot.points.forEach((pt, i) => {
                    if (i === 0) ctx.moveTo(pt.x, pt.y);
                    else ctx.lineTo(pt.x, pt.y);
                });
                ctx.stroke();
                ctx.globalAlpha = 1.0;
            }
        } else {
            renderInteractiveDomAnnot(annot);
        }
    });
}

// -------------------------------------------------------------
// 7. TOOLBAR ACTIONS & SHORTCUTS
// -------------------------------------------------------------
function setVipTool(toolName) {
    VIP_STATE.activeTool = toolName;
    document.querySelectorAll(".vip-tool-btn").forEach(btn => {
        btn.classList.remove("active");
    });
    const activeBtn = document.getElementById(`vip-tool-${toolName}`);
    if (activeBtn) activeBtn.classList.add("active");

    // Change cursor based on tool
    const canvases = document.querySelectorAll(".vip-draw-canvas");
    canvases.forEach(c => {
        if (toolName === 'select') c.style.cursor = 'default';
        else if (toolName === 'hand') c.style.cursor = 'grab';
        else if (toolName === 'text') c.style.cursor = 'text';
        else c.style.cursor = 'crosshair';
    });
}

function setVipColor(colorHex) {
    VIP_STATE.activeColor = colorHex;
    document.querySelectorAll(".vip-color-dot").forEach(d => {
        d.classList.remove("active");
        if (d.getAttribute("style")?.includes(colorHex)) {
            d.classList.add("active");
        }
    });

    // If an annotation is currently selected, update its color immediately!
    if (VIP_STATE.selectedAnnotId) {
        const annot = VIP_STATE.annotations.find(a => a.id === VIP_STATE.selectedAnnotId);
        if (annot) {
            if (annot.type === 'rect' || annot.type === 'circle') {
                annot.fillColor = colorHex;
            } else if (annot.type === 'text') {
                annot.color = colorHex;
            }
            renderInteractiveDomAnnot(annot);
        }
    }
}

function handleVipImageInsert(e) {
    if (!e.target || !e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    const reader = new FileReader();
    reader.onload = function(evt) {
        const b64 = evt.target.result;
        const annot = {
            id: `annot_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
            page: VIP_STATE.currentPage || 1,
            type: 'image',
            x: 100,
            y: 100,
            width: 150,
            height: 120,
            imageBase64: b64,
            canvasWidth: 600,
            canvasHeight: 800
        };
        addVipAnnotation(annot);
        renderInteractiveDomAnnot(annot);
        setVipTool('select');
        selectVipAnnotation(annot.id);
    };
    reader.readAsDataURL(file);
}

function toggleVipSidebar() {
    const sb = document.getElementById("vip-sidebar");
    if (!sb) return;
    VIP_STATE.isSidebarCollapsed = !VIP_STATE.isSidebarCollapsed;
    sb.classList.toggle("collapsed", VIP_STATE.isSidebarCollapsed);
}

function changeVipZoom(newZoom) {
    VIP_STATE.zoom = parseFloat(newZoom);
    renderVipAllPages();
}

function fitVipWidth() {
    const vp = document.getElementById("vip-viewport");
    if (!vp) return;
    const availableW = vp.clientWidth - 80;
    VIP_STATE.zoom = Math.max(0.8, Math.min(2.5, availableW / 595));
    const sel = document.getElementById("vip-nav-zoom");
    if (sel) sel.value = "1.5";
    renderVipAllPages();
}

function goToVipPrevPage() {
    if (VIP_STATE.currentPage > 1) {
        scrollToVipPage(VIP_STATE.currentPage - 1);
    }
}

function goToVipNextPage() {
    if (VIP_STATE.currentPage < VIP_STATE.pageCount) {
        scrollToVipPage(VIP_STATE.currentPage + 1);
    }
}

function updateVipPageIndicator() {
    const ind = document.getElementById("vip-nav-page-indicator");
    if (ind) ind.textContent = `${VIP_STATE.currentPage} trên ${VIP_STATE.pageCount}`;
}

function vipUndo() {
    if (VIP_STATE.undoStack.length === 0) return;
    const last = VIP_STATE.undoStack.pop();
    VIP_STATE.redoStack.push(last);

    const idx = VIP_STATE.annotations.findIndex(a => a.id === last.annot.id);
    if (idx !== -1) {
        document.getElementById(last.annot.id)?.remove();
        VIP_STATE.annotations.splice(idx, 1);
        redrawAllAnnotations();
    }
}

function vipRedo() {
    if (VIP_STATE.redoStack.length === 0) return;
    const item = VIP_STATE.redoStack.pop();
    VIP_STATE.undoStack.push(item);
    VIP_STATE.annotations.push(item.annot);
    redrawAllAnnotations();
}

// Keyboard shortcuts for Editor (Delete, Undo, Redo)
window.addEventListener("keydown", (e) => {
    if (document.getElementById("vip-editor-view")?.classList.contains("hidden")) return;
    if (e.key === "Delete" || e.key === "Backspace") {
        if (!e.target.isContentEditable) {
            deleteVipSelectedAnnot();
        }
    } else if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        e.preventDefault();
        vipUndo();
    } else if ((e.ctrlKey || e.metaKey) && e.key === 'y') {
        e.preventDefault();
        vipRedo();
    }
});

// -------------------------------------------------------------
// 7.1 IMAGE MANIPULATION ENGINE (ROTATE, FLIP, CROP, FILTER, REPLACE)
// -------------------------------------------------------------
function rotateVipImage(id) {
    const annot = VIP_STATE.annotations.find(a => a.id === id);
    if (!annot || annot.type !== 'image') return;
    const img = new Image();
    img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = img.height;
        canvas.height = img.width;
        const ctx = canvas.getContext("2d");
        ctx.translate(canvas.width / 2, canvas.height / 2);
        ctx.rotate(90 * Math.PI / 180);
        ctx.drawImage(img, -img.width / 2, -img.height / 2);

        annot.imageBase64 = canvas.toDataURL("image/png");
        const tempW = annot.width;
        annot.width = annot.height;
        annot.height = tempW;

        renderInteractiveDomAnnot(annot);
        selectVipAnnotation(annot.id);
    };
    img.src = annot.imageBase64;
}

function flipVipImage(id, axis) {
    const annot = VIP_STATE.annotations.find(a => a.id === id);
    if (!annot || annot.type !== 'image') return;
    const img = new Image();
    img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = img.width;
        canvas.height = img.height;
        const ctx = canvas.getContext("2d");
        if (axis === 'h') {
            ctx.translate(canvas.width, 0);
            ctx.scale(-1, 1);
        } else {
            ctx.translate(0, canvas.height);
            ctx.scale(1, -1);
        }
        ctx.drawImage(img, 0, 0);

        annot.imageBase64 = canvas.toDataURL("image/png");
        renderInteractiveDomAnnot(annot);
        selectVipAnnotation(annot.id);
    };
    img.src = annot.imageBase64;
}

function replaceVipImage(id) {
    VIP_STATE.replacingImageId = id;
    document.getElementById("vip-replace-image-input")?.click();
}

function handleVipReplaceImage(e) {
    if (!e.target || !e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    const annot = VIP_STATE.annotations.find(a => a.id === VIP_STATE.replacingImageId);
    if (!annot) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
        const newB64 = evt.target.result;
        const img = new Image();
        img.onload = () => {
            annot.imageBase64 = newB64;
            annot.originalImageBase64 = newB64;
            const ratio = img.height / img.width;
            annot.height = Math.round(annot.width * ratio);
            renderInteractiveDomAnnot(annot);
            selectVipAnnotation(annot.id);
        };
        img.src = newB64;
    };
    reader.readAsDataURL(file);
    e.target.value = "";
}

function toggleVipImageFilterMenu(id, e) {
    e?.stopPropagation();
    const existing = document.getElementById("vip-filter-popup-menu");
    if (existing) {
        existing.remove();
        return;
    }
    const targetEl = document.getElementById(id);
    if (!targetEl) return;

    const menu = document.createElement("div");
    menu.id = "vip-filter-popup-menu";
    menu.className = "vip-filter-menu";
    menu.innerHTML = `
        <button type="button" class="vip-filter-item" onclick="applyVipImageFilter('${id}', 'normal')"><span>Ảnh gốc (Normal)</span></button>
        <button type="button" class="vip-filter-item" onclick="applyVipImageFilter('${id}', 'grayscale')"><span>Đen trắng (B&W)</span></button>
        <button type="button" class="vip-filter-item" onclick="applyVipImageFilter('${id}', 'high-contrast')"><span>Tăng nét (High Contrast)</span></button>
        <button type="button" class="vip-filter-item" onclick="applyVipImageFilter('${id}', 'clean-doc')"><span>Lọc nền văn bản (Clean Scan)</span></button>
        <button type="button" class="vip-filter-item" onclick="applyVipImageFilter('${id}', 'brighten')"><span>Tăng sáng (+25%)</span></button>
        <button type="button" class="vip-filter-item" onclick="applyVipImageFilter('${id}', 'darken')"><span>Tối màu (-25%)</span></button>
        <button type="button" class="vip-filter-item" onclick="applyVipImageFilter('${id}', 'invert')"><span>Đảo màu âm bản</span></button>
        <button type="button" class="vip-filter-item" onclick="applyVipImageFilter('${id}', 'sepia')"><span>Tông màu ấm (Sepia)</span></button>
    `;
    targetEl.appendChild(menu);
}

function applyVipImageFilter(id, filterType) {
    document.getElementById("vip-filter-popup-menu")?.remove();
    const annot = VIP_STATE.annotations.find(a => a.id === id);
    if (!annot || annot.type !== 'image') return;

    if (!annot.originalImageBase64) {
        annot.originalImageBase64 = annot.imageBase64;
    }

    const baseSrc = filterType === 'normal' ? annot.originalImageBase64 : annot.imageBase64;
    const img = new Image();
    img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = img.width;
        canvas.height = img.height;
        const ctx = canvas.getContext("2d");

        if (filterType === 'normal') {
            annot.imageBase64 = annot.originalImageBase64;
            renderInteractiveDomAnnot(annot);
            selectVipAnnotation(annot.id);
            return;
        } else if (filterType === 'grayscale') {
            ctx.filter = 'grayscale(100%)';
        } else if (filterType === 'high-contrast') {
            ctx.filter = 'contrast(170%) brightness(105%)';
        } else if (filterType === 'brighten') {
            ctx.filter = 'brightness(125%)';
        } else if (filterType === 'darken') {
            ctx.filter = 'brightness(75%)';
        } else if (filterType === 'invert') {
            ctx.filter = 'invert(100%)';
        } else if (filterType === 'sepia') {
            ctx.filter = 'sepia(100%)';
        }

        ctx.drawImage(img, 0, 0);

        if (filterType === 'clean-doc') {
            const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            const d = imgData.data;
            for (let i = 0; i < d.length; i += 4) {
                const gray = 0.299 * d[i] + 0.587 * d[i+1] + 0.114 * d[i+2];
                if (gray > 185) {
                    d[i] = 255; d[i+1] = 255; d[i+2] = 255;
                } else {
                    const enhanced = Math.max(0, gray * 0.75);
                    d[i] = enhanced; d[i+1] = enhanced; d[i+2] = enhanced;
                }
            }
            ctx.putImageData(imgData, 0, 0);
        }

        annot.imageBase64 = canvas.toDataURL("image/png");
        renderInteractiveDomAnnot(annot);
        selectVipAnnotation(annot.id);
    };
    img.src = baseSrc;
}

// CROP MODAL LOGIC
let vipCropState = {
    annotId: null,
    aspect: 'free'
};

function openVipCropModal(id) {
    const annot = VIP_STATE.annotations.find(a => a.id === id);
    if (!annot || annot.type !== 'image') return;

    vipCropState.annotId = id;
    const modal = document.getElementById("vip-crop-modal");
    const previewImg = document.getElementById("vip-crop-preview-img");
    const cropBox = document.getElementById("vip-crop-box");

    if (!modal || !previewImg || !cropBox) return;

    previewImg.onload = () => {
        const dispW = previewImg.clientWidth;
        const dispH = previewImg.clientHeight;

        cropBox.style.left = `${Math.round(dispW * 0.1)}px`;
        cropBox.style.top = `${Math.round(dispH * 0.1)}px`;
        cropBox.style.width = `${Math.round(dispW * 0.8)}px`;
        cropBox.style.height = `${Math.round(dispH * 0.8)}px`;

        initCropDragAndResize(cropBox, previewImg);
    };

    previewImg.src = annot.imageBase64;
    modal.classList.remove("hidden");
}

function closeVipCropModal() {
    document.getElementById("vip-crop-modal")?.classList.add("hidden");
    vipCropState.annotId = null;
}

function setVipCropAspect(aspect) {
    vipCropState.aspect = aspect;
    document.querySelectorAll(".crop-aspect-btn").forEach(btn => btn.classList.remove("active"));
    event?.target?.classList.add("active");

    const cropBox = document.getElementById("vip-crop-box");
    const previewImg = document.getElementById("vip-crop-preview-img");
    if (!cropBox || !previewImg) return;

    const w = parseFloat(cropBox.style.width);
    const dispH = previewImg.clientHeight;

    if (aspect === '1:1') {
        const size = Math.min(w, dispH);
        cropBox.style.width = `${size}px`;
        cropBox.style.height = `${size}px`;
    } else if (aspect === '4:3') {
        cropBox.style.height = `${Math.min(dispH, w * 0.75)}px`;
    } else if (aspect === '16:9') {
        cropBox.style.height = `${Math.min(dispH, w * (9/16))}px`;
    }
}

function initCropDragAndResize(box, img) {
    let isDragging = false;
    let isResizing = false;
    let activeHandle = null;
    let startX = 0, startY = 0;
    let origLeft = 0, origTop = 0, origW = 0, origH = 0;

    box.onmousedown = (e) => {
        if (e.target.classList.contains("vip-handle")) {
            isResizing = true;
            activeHandle = e.target.className.split("vip-handle-")[1] || "br";
        } else {
            isDragging = true;
        }
        startX = e.clientX;
        startY = e.clientY;
        origLeft = parseFloat(box.style.left) || 0;
        origTop = parseFloat(box.style.top) || 0;
        origW = parseFloat(box.style.width) || 100;
        origH = parseFloat(box.style.height) || 100;
        e.preventDefault();
        e.stopPropagation();

        const onMouseMove = (ev) => {
            const dx = ev.clientX - startX;
            const dy = ev.clientY - startY;
            const maxW = img.clientWidth;
            const maxH = img.clientHeight;

            if (isDragging) {
                const newL = Math.max(0, Math.min(maxW - origW, origLeft + dx));
                const newT = Math.max(0, Math.min(maxH - origH, origTop + dy));
                box.style.left = `${newL}px`;
                box.style.top = `${newT}px`;
            } else if (isResizing) {
                if (activeHandle.includes('r')) box.style.width = `${Math.max(30, Math.min(maxW - origLeft, origW + dx))}px`;
                if (activeHandle.includes('b')) box.style.height = `${Math.max(30, Math.min(maxH - origTop, origH + dy))}px`;
                if (activeHandle.includes('l')) {
                    const nw = Math.max(30, origW - dx);
                    box.style.left = `${origLeft + (origW - nw)}px`;
                    box.style.width = `${nw}px`;
                }
                if (activeHandle.includes('t')) {
                    const nh = Math.max(30, origH - dy);
                    box.style.top = `${origTop + (origH - nh)}px`;
                    box.style.height = `${nh}px`;
                }
            }
        };

        const onMouseUp = () => {
            isDragging = false;
            isResizing = false;
            window.removeEventListener("mousemove", onMouseMove);
            window.removeEventListener("mouseup", onMouseUp);
        };

        window.addEventListener("mousemove", onMouseMove);
        window.addEventListener("mouseup", onMouseUp);
    };
}

function applyVipCrop() {
    if (!vipCropState.annotId) return;
    const annot = VIP_STATE.annotations.find(a => a.id === vipCropState.annotId);
    const previewImg = document.getElementById("vip-crop-preview-img");
    const cropBox = document.getElementById("vip-crop-box");
    if (!annot || !previewImg || !cropBox) return;

    const scaleX = previewImg.naturalWidth / previewImg.clientWidth;
    const scaleY = previewImg.naturalHeight / previewImg.clientHeight;

    const cropX = Math.round((parseFloat(cropBox.style.left) || 0) * scaleX);
    const cropY = Math.round((parseFloat(cropBox.style.top) || 0) * scaleY);
    const cropW = Math.round((parseFloat(cropBox.style.width) || 50) * scaleX);
    const cropH = Math.round((parseFloat(cropBox.style.height) || 50) * scaleY);

    const img = new Image();
    img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, cropW);
        canvas.height = Math.max(1, cropH);
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, cropX, cropY, cropW, cropH, 0, 0, cropW, cropH);

        annot.imageBase64 = canvas.toDataURL("image/png");
        annot.height = Math.round(annot.width * (cropH / cropW));

        renderInteractiveDomAnnot(annot);
        selectVipAnnotation(annot.id);
        closeVipCropModal();
    };
    img.src = annot.imageBase64;
}

// Deselect on clicking empty canvas
document.addEventListener("click", (e) => {
    if (e.target.closest("#vip-crop-modal") || e.target.closest("#vip-filter-popup-menu")) return;
    if (VIP_STATE.activeTool === 'select' && !e.target.closest(".vip-annot-item") && !e.target.closest(".vip-toolbar")) {
        VIP_STATE.selectedAnnotId = null;
        document.querySelectorAll(".vip-annot-item").forEach(el => {
            el.classList.remove("selected");
            el.querySelectorAll(".vip-handle").forEach(h => h.remove());
            el.querySelectorAll(".vip-image-toolbar").forEach(tb => tb.remove());
        });
        document.getElementById("vip-filter-popup-menu")?.remove();
    }
});

// -------------------------------------------------------------
// 8. SAVE & EXPORT PDF (NATIVE PYMUPDF VECTOR EMBEDDING)
// -------------------------------------------------------------
async function saveVipEditedPdf() {
    if (!VIP_STATE.loadedFile) {
        alert("Chưa có tệp PDF hoặc Hình ảnh nào được nạp!");
        return;
    }

    const saveBtn = document.getElementById("vip-btn-save-export");
    const origText = saveBtn ? saveBtn.innerHTML : "";
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = `<span>Đang lưu Vector...</span>`;
    }

    try {
        const formData = new FormData();
        formData.append("file", VIP_STATE.loadedFile);
        formData.append("annotations", JSON.stringify(VIP_STATE.annotations));

        const res = await fetch("/api/process/vip-editor-save", {
            method: "POST",
            body: formData
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `HTTP ${res.status}`);
        }

        const data = await res.json();
        if (data.success && data.download_url) {
            // Trigger download
            const a = document.createElement("a");
            a.href = data.download_url;
            a.download = data.filename || "LUV_PDF_VIP_Edited.pdf";
            document.body.appendChild(a);
            a.click();
            a.remove();

            alert(`✅ ${data.details || "Đã lưu bản vẽ và xuất bản PDF chỉnh sửa VIP Pro thành công!"}`);
        } else {
            throw new Error("Không thể lưu file chỉnh sửa.");
        }
    } catch (err) {
        alert("Lỗi xuất bản PDF: " + err.message);
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = origText;
        }
    }
}
