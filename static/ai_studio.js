// ==============================================================================
// MSDS ADVANCED ACCENT-INSENSITIVE SEARCH & DUAL VIEW MODE HELPERS
// ==============================================================================
function removeVietnameseTones(str) {
    if (!str) return "";
    return String(str)
        .normalize("NFD")
        .replace(/[̀-ͯ]/g, "")
        .replace(/đ/g, "d")
        .replace(/Đ/g, "D")
        .toLowerCase()
        .trim();
}

let CURRENT_MSDS_VIEW_MODE = localStorage.getItem("luv_msds_view_mode") || "table";
let CURRENT_DRAWER_CHEM_ID = null;

function setMsdsViewMode(mode) {
    CURRENT_MSDS_VIEW_MODE = mode === "grid" ? "grid" : "table";
    try {
        localStorage.setItem("luv_msds_view_mode", CURRENT_MSDS_VIEW_MODE);
    } catch (_) {}

    const btnTable = document.getElementById("msds-view-btn-table");
    const btnGrid = document.getElementById("msds-view-btn-grid");
    const tableEl = document.querySelector(".msds-modern-table");
    const gridContainer = document.getElementById("msds-grid-container");

    if (btnTable) btnTable.classList.toggle("active", CURRENT_MSDS_VIEW_MODE === "table");
    if (btnGrid) btnGrid.classList.toggle("active", CURRENT_MSDS_VIEW_MODE === "grid");

    if (tableEl) tableEl.style.display = CURRENT_MSDS_VIEW_MODE === "table" ? "table" : "none";
    if (gridContainer) gridContainer.classList.toggle("hidden", CURRENT_MSDS_VIEW_MODE !== "grid");

    const searchVal = document.getElementById("msds-search-input")?.value || "";
    renderMsdsFilteredTable(ALL_MSDS_CHEMICALS_CACHE, searchVal);
}

function applyMsdsRbacVisibility() {
    const isGuest = isGuestUser();
    document.querySelectorAll(".admin-only-ctrl").forEach(el => {
        el.style.display = isGuest ? "none" : "";
    });
    const delAllBtn = document.getElementById("btn-msds-delete-all") || document.querySelector(".msds-btn-delete-all");
    if (delAllBtn) {
        delAllBtn.style.display = isGuest ? "none" : "";
    }

    const guestCard = document.getElementById("msds-guest-badge-card");
    if (guestCard) {
        guestCard.classList.toggle("hidden", !isGuest);
    }

    const intakeDrawer = document.getElementById("msds-intake-drawer");
    if (intakeDrawer && isGuest) {
        intakeDrawer.style.display = "none";
    }

    const batchBar = document.getElementById("msds-batch-action-bar");
    if (batchBar && isGuest) {
        batchBar.classList.add("hidden");
    }

    const selectAllTh = document.getElementById("msds-select-all");
    if (selectAllTh) {
        const thCell = selectAllTh.closest("th");
        if (thCell) thCell.style.display = isGuest ? "none" : "";
    }
}

// ============================================================
// TitanPDF Private Suite - AI Studio Intelligence Module
// 1. Dịch Thuật Tự Do (Google Translate Siêu Tốc & AI DeepSeek)
// 2. AI Tóm Tắt Tài Liệu Thông Minh (PDF, DOCX, TXT, PPTX)
// 100% Cục bộ & Bảo Mật Tuyệt Đối (127.0.0.1:8888)
// ============================================================

let SELECTED_AI_SUM_FILE = null;
let CURRENT_AI_SUMMARY_TEXT = "";
let CURRENT_AI_TRANSLATED_TEXT = "";

document.addEventListener("DOMContentLoaded", () => {
    initAiStudio();
});

function isGuestUser() {
    return document.body?.getAttribute("data-role") === "guest" || sessionStorage.getItem("luv_user_role") === "guest";
}

function initAiStudio() {
    const isGuest = isGuestUser();
    // Load saved DeepSeek API key from localStorage or mask if guest
    const savedKey = isGuest ? "••••••••••••••••" : (localStorage.getItem("deepseek_api_key") || "");
    const keyInput1 = document.getElementById("ai-deepseek-key");
    const keyInput2 = document.getElementById("ai-sum-key");
    if (keyInput1) {
        keyInput1.value = savedKey;
        if (isGuest) {
            keyInput1.setAttribute("readonly", "true");
            keyInput1.setAttribute("disabled", "true");
            keyInput1.setAttribute("type", "password");
        }
    }
    if (keyInput2) {
        keyInput2.value = savedKey;
        if (isGuest) {
            keyInput2.setAttribute("readonly", "true");
            keyInput2.setAttribute("disabled", "true");
            keyInput2.setAttribute("type", "password");
        }
    }

    // Tự động gắn kết Badge trạng thái AI toàn cục vào Tab Dịch & Tab Tóm tắt
    if (window.LuvAIService) {
        window.LuvAIService.renderBadge("ai-trans-global-badge-container");
        window.LuvAIService.renderBadge("ai-sum-global-badge-container");
    }

    // Attach Ctrl+Enter keyboard shortcut to translation input
    const inputArea = document.getElementById("ai-input-text");
    if (inputArea) {
        inputArea.addEventListener("keydown", (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                e.preventDefault();
                runAiTranslation();
            }
        });
    }

    // Drag and drop for summarizer dropzone
    const sumDrop = document.getElementById("ai-sum-dropzone");
    if (sumDrop) {
        sumDrop.addEventListener("dragover", (e) => {
            e.preventDefault();
            sumDrop.classList.add("drag-hover");
        });
        sumDrop.addEventListener("dragleave", (e) => {
            e.preventDefault();
            sumDrop.classList.remove("drag-hover");
        });
        sumDrop.addEventListener("drop", (e) => {
            e.preventDefault();
            sumDrop.classList.remove("drag-hover");
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                setAiSumFile(e.dataTransfer.files[0]);
            }
        });
    }

    // Drag and drop for translation text area (reads file text)
    if (inputArea) {
        inputArea.addEventListener("dragover", (e) => {
            e.preventDefault();
            inputArea.classList.add("drag-hover");
        });
        inputArea.addEventListener("dragleave", (e) => {
            e.preventDefault();
            inputArea.classList.remove("drag-hover");
        });
        inputArea.addEventListener("drop", (e) => {
            e.preventDefault();
            inputArea.classList.remove("drag-hover");
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                loadTextFromFile(e.dataTransfer.files[0]);
            }
        });
    }

    // Drag and drop for MSDS dropzone (supports multiple files)
    const msdsDrop = document.getElementById("msds-upload-dropzone");
    if (msdsDrop) {
        msdsDrop.addEventListener("dragover", (e) => {
            e.preventDefault();
            msdsDrop.classList.add("drag-hover");
        });
        msdsDrop.addEventListener("dragleave", (e) => {
            e.preventDefault();
            msdsDrop.classList.remove("drag-hover");
        });
        msdsDrop.addEventListener("drop", (e) => {
            e.preventDefault();
            msdsDrop.classList.remove("drag-hover");
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                const droppedFiles = Array.from(e.dataTransfer.files);
                droppedFiles.forEach(f => {
                    const isDup = CURRENT_MSDS_FILES.some(x => x.name === f.name && x.size === f.size);
                    if (!isDup) CURRENT_MSDS_FILES.push(f);
                });
                renderMsdsFileList();
            }
        });
    }

    // Preload MSDS list & navbar badge count
    loadMsdsChemicalsList();
}

// -------------------------------------------------------------
// 1. SUB-TAB SWITCHING (Dịch Thuật vs Tóm Tắt)
// -------------------------------------------------------------
function switchAiSubTab(tab) {
    if (tab === "msds") {
        if (typeof switchMainTab === "function") {
            switchMainTab("msds");
        }
        return;
    }

    const btnTrans = document.getElementById("ai-subtab-translate");
    const btnSum = document.getElementById("ai-subtab-summarize");
    const panelTrans = document.getElementById("ai-panel-translate");
    const panelSum = document.getElementById("ai-panel-summarize");

    if (btnTrans) btnTrans.classList.remove("active");
    if (btnSum) btnSum.classList.remove("active");

    if (panelTrans) panelTrans.classList.add("hidden");
    if (panelSum) panelSum.classList.add("hidden");

    if (tab === "summarize") {
        if (btnSum) btnSum.classList.add("active");
        if (panelSum) panelSum.classList.remove("hidden");
    } else {
        if (btnTrans) btnTrans.classList.add("active");
        if (panelTrans) panelTrans.classList.remove("hidden");
    }
}

// -------------------------------------------------------------
// 2. DỊCH THUẬT VĂN BẢN TỰ DO (AI TRANSLATOR)
// -------------------------------------------------------------
function swapAiLanguages() {
    const srcSelect = document.getElementById("ai-trans-src-lang");
    const tgtSelect = document.getElementById("ai-trans-tgt-lang");
    if (!srcSelect || !tgtSelect) return;

    let srcVal = srcSelect.value;
    let tgtVal = tgtSelect.value;

    if (srcVal === "auto") {
        srcVal = "en"; // Default swap if auto
    }

    srcSelect.value = tgtVal;
    tgtSelect.value = srcVal;

    // Also swap text if both have content
    const inputArea = document.getElementById("ai-input-text");
    const outputArea = document.getElementById("ai-output-text");
    if (inputArea && outputArea && outputArea.value.trim()) {
        const temp = inputArea.value;
        inputArea.value = outputArea.value;
        outputArea.value = temp;
        updateAiInputStats();
    }
}

function toggleAiKeyInput() {
    const engine = document.getElementById("ai-trans-engine-select")?.value;
    const badgeContainer = document.getElementById("ai-trans-global-badge-container");
    if (badgeContainer) {
        if (engine === "deepseek") {
            badgeContainer.classList.remove("hidden");
            if (window.LuvAIService) {
                window.LuvAIService.renderBadge("ai-trans-global-badge-container");
            }
        } else {
            badgeContainer.classList.add("hidden");
        }
    }
}

function saveAiDeepSeekKey() {
    if (isGuestUser()) {
        alert("Khách (Guest) không có quyền thay đổi API key.");
        return;
    }
    const input = document.getElementById("ai-deepseek-key");
    if (!input) return;
    const key = input.value.trim();
    if (!key) {
        alert("Vui lòng nhập API key của DeepSeek!");
        return;
    }
    localStorage.setItem("deepseek_api_key", key);
    const sumKey = document.getElementById("ai-sum-key");
    if (sumKey) sumKey.value = key;
    alert("✓ Đã lưu DeepSeek API Key an toàn trong trình duyệt.");
}

function updateAiInputStats() {
    const input = document.getElementById("ai-input-text");
    const stats = document.getElementById("ai-input-stats");
    if (!input || !stats) return;

    const text = input.value;
    const chars = text.length;
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;
    stats.innerText = `${chars.toLocaleString()} ký tự · ${words.toLocaleString()} từ`;
}

function clearAiInput() {
    const input = document.getElementById("ai-input-text");
    const output = document.getElementById("ai-output-text");
    const outStats = document.getElementById("ai-output-stats");
    if (input) input.value = "";
    if (output) output.value = "";
    CURRENT_AI_TRANSLATED_TEXT = "";
    if (outStats) outStats.innerText = "Sẵn sàng dịch";
    updateAiInputStats();
}

async function pasteToAiInput() {
    try {
        const text = await navigator.clipboard.readText();
        const input = document.getElementById("ai-input-text");
        if (input && text) {
            input.value = text;
            updateAiInputStats();
            input.focus();
        }
    } catch (err) {
        alert("Không thể đọc bộ nhớ tạm: Vui lòng dán trực tiếp (Ctrl+V) vào ô.");
    }
}

function handleAiFileToInput(event) {
    if (event.target && event.target.files && event.target.files.length > 0) {
        loadTextFromFile(event.target.files[0]);
    }
}

async function loadTextFromFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    const input = document.getElementById("ai-input-text");

    if (ext === "txt") {
        const reader = new FileReader();
        reader.onload = (e) => {
            if (input) {
                input.value = e.target.result;
                updateAiInputStats();
            }
        };
        reader.readAsText(file);
    } else {
        // Send file to extract text via server endpoint
        try {
            const formData = new FormData();
            formData.append("file", file);
            formData.append("mode", "executive");
            formData.append("length", "short");

            const statusText = document.getElementById("ai-input-stats");
            if (statusText) statusText.innerText = "Đang đọc văn bản từ file...";

            // Use FileReader or extract text
            const reader = new FileReader();
            reader.onload = (e) => {
                // If it's readable as text
                const sample = e.target.result;
                if (typeof sample === "string" && sample.length > 20) {
                    if (input) {
                        input.value = sample;
                        updateAiInputStats();
                    }
                }
            };
            reader.readAsText(file);
        } catch (err) {
            alert("Lỗi nạp tệp: " + err.message);
        }
    }
}

async function runAiTranslation() {
    const input = document.getElementById("ai-input-text");
    const output = document.getElementById("ai-output-text");
    const btn = document.getElementById("btn-ai-translate");
    const btnText = document.getElementById("txt-btn-ai-translate");
    const outStats = document.getElementById("ai-output-stats");
    const engineBadge = document.getElementById("ai-engine-badge");

    if (!input || !input.value.trim()) {
        alert("Vui lòng nhập hoặc dán nội dung văn bản cần dịch!");
        input?.focus();
        return;
    }

    if (typeof checkGuestAiQuota === "function" && !checkGuestAiQuota()) {
        return;
    }
    if (typeof logGuestActivity === "function") {
        logGuestActivity("AI Studio: Dịch văn bản");
    }

    const textToTranslate = input.value.trim();
    const srcLang = document.getElementById("ai-trans-src-lang")?.value || "auto";
    const tgtLang = document.getElementById("ai-trans-tgt-lang")?.value || "vi";
    const engine = document.getElementById("ai-trans-engine-select")?.value || "google";

    if (engine === "deepseek" && window.LuvAIService) {
        if (!window.LuvAIService.requireReady({ contextName: "Dịch thuật AI DeepSeek" })) {
            return;
        }
    }

    const apiKey = (window.LuvAIService ? window.LuvAIService.getRawApiKey() : "") || document.getElementById("ai-deepseek-key")?.value.trim() || localStorage.getItem("deepseek_api_key") || "";

    // Set loading state
    if (btn) {
        btn.disabled = true;
        btn.classList.add("btn-loading");
    }
    if (btnText) btnText.innerText = "ĐANG DỊCH...";
    if (outStats) outStats.innerText = "Đang gửi dữ liệu đến máy chủ...";
    if (typeof showProcessingAnimation === "function") {
        showProcessingAnimation("AI đang dịch văn bản...");
    }

    const formData = new FormData();
    formData.append("text", textToTranslate);
    formData.append("source_lang", srcLang);
    formData.append("target_lang", tgtLang);
    formData.append("engine", engine);
    if (apiKey) formData.append("api_key", apiKey);

    try {
        const res = await fetch("/api/process/ai-translate", {
            method: "POST",
            body: formData
        });

        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.detail || data.error || "Không thể dịch văn bản");
        }

        CURRENT_AI_TRANSLATED_TEXT = data.translated_text || "";
        if (output) output.value = CURRENT_AI_TRANSLATED_TEXT;

        if (outStats) {
            outStats.innerText = `Hoàn tất trong ${data.elapsed_seconds}s (${data.word_count} từ)`;
        }
        if (engineBadge) {
            engineBadge.innerText = data.engine || "Google Translate";
        }
        if (engine === "deepseek" && window.LuvAIService) {
            window.LuvAIService.recordGuestCall();
        }

    } catch (err) {
        console.error("Lỗi dịch thuật:", err);
        alert("Lỗi dịch văn bản: " + err.message);
        if (outStats) outStats.innerText = "Lỗi xử lý, vui lòng thử lại";
    } finally {
        if (typeof hideProcessingAnimation === "function") {
            hideProcessingAnimation();
        }
        if (btn) {
            btn.disabled = false;
            btn.classList.remove("btn-loading");
        }
        if (btnText) btnText.innerText = "DỊCH NGAY";
    }
}

async function copyAiTranslatedText() {
    const output = document.getElementById("ai-output-text");
    const textToCopy = output?.value || CURRENT_AI_TRANSLATED_TEXT;

    if (!textToCopy || !textToCopy.trim()) {
        alert("Chưa có nội dung bản dịch để sao chép!");
        return;
    }

    try {
        await navigator.clipboard.writeText(textToCopy);
        
        // Immediate visual feedback on the button
        const btn = document.getElementById("btn-copy-trans");
        const btnTxt = document.getElementById("txt-copy-trans");
        if (btn && btnTxt) {
            const origHtml = btnTxt.innerHTML;
            btn.classList.add("btn-copy-success");
            btnTxt.innerText = "✓ Đã sao chép!";
            
            setTimeout(() => {
                btn.classList.remove("btn-copy-success");
                btnTxt.innerHTML = origHtml;
            }, 2200);
        }
    } catch (err) {
        // Fallback copy
        if (output) {
            output.select();
            document.execCommand("copy");
            alert("✓ Đã sao chép bản dịch vào bộ nhớ tạm!");
        }
    }
}

function downloadAiTranslatedText() {
    const text = CURRENT_AI_TRANSLATED_TEXT || document.getElementById("ai-output-text")?.value;
    if (!text || !text.trim()) {
        alert("Chưa có bản dịch để lưu!");
        return;
    }

    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Ban_Dich_${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// -------------------------------------------------------------
// 3. AI TÓM TẮT TÀI LIỆU (AI SUMMARIZER)
// -------------------------------------------------------------
function handleAiSumFileSelect(event) {
    if (event.target && event.target.files && event.target.files.length > 0) {
        setAiSumFile(event.target.files[0]);
    }
}

function setAiSumFile(file) {
    SELECTED_AI_SUM_FILE = file;
    const promptBox = document.getElementById("ai-sum-drop-prompt");
    const infoBox = document.getElementById("ai-sum-selected-info");
    const nameSpan = document.getElementById("ai-sum-filename");
    const sizeSpan = document.getElementById("ai-sum-filesize");

    if (promptBox) promptBox.classList.add("hidden");
    if (infoBox) infoBox.classList.remove("hidden");
    if (nameSpan) nameSpan.innerText = file.name;
    if (sizeSpan) sizeSpan.innerText = formatFileSize(file.size);
}

function clearAiSumFile() {
    SELECTED_AI_SUM_FILE = null;
    const fileInput = document.getElementById("ai-sum-file-input");
    if (fileInput) fileInput.value = "";

    const promptBox = document.getElementById("ai-sum-drop-prompt");
    const infoBox = document.getElementById("ai-sum-selected-info");
    if (promptBox) promptBox.classList.remove("hidden");
    if (infoBox) infoBox.classList.add("hidden");
}

function toggleAiSumKeyInput() {
    const engine = document.getElementById("ai-sum-engine")?.value;
    const badgeContainer = document.getElementById("ai-sum-global-badge-container");
    if (badgeContainer) {
        if (engine === "deepseek") {
            badgeContainer.classList.remove("hidden");
            if (window.LuvAIService) {
                window.LuvAIService.renderBadge("ai-sum-global-badge-container");
            }
        } else {
            badgeContainer.classList.add("hidden");
        }
    }
}

function saveAiSumKey() {
    if (isGuestUser()) {
        alert("Khách (Guest) không có quyền thay đổi API key.");
        return;
    }
    const input = document.getElementById("ai-sum-key");
    if (!input) return;
    const key = input.value.trim();
    if (!key) {
        alert("Vui lòng nhập API key của DeepSeek!");
        return;
    }
    localStorage.setItem("deepseek_api_key", key);
    const transKey = document.getElementById("ai-deepseek-key");
    if (transKey) transKey.value = key;
    alert("✓ Đã lưu DeepSeek API Key an toàn trong trình duyệt.");
}

async function runAiDocumentSummarize() {
    if (!SELECTED_AI_SUM_FILE) {
        alert("Vui lòng chọn hoặc kéo thả tệp tài liệu cần tóm tắt (.pdf, .docx, .doc, .txt, .pptx)!");
        document.getElementById("ai-sum-file-input")?.click();
        return;
    }

    if (typeof checkGuestAiQuota === "function" && !checkGuestAiQuota()) {
        return;
    }
    if (typeof logGuestActivity === "function") {
        logGuestActivity("AI Studio: Tóm tắt tài liệu");
    }

    const mode = document.getElementById("ai-sum-mode")?.value || "executive";
    const length = document.getElementById("ai-sum-length")?.value || "medium";
    const engine = document.getElementById("ai-sum-engine")?.value || "deepseek";

    if (engine === "deepseek" && window.LuvAIService) {
        if (!window.LuvAIService.requireReady({ contextName: "Tóm tắt tài liệu AI DeepSeek" })) {
            return;
        }
    }

    const apiKey = (window.LuvAIService ? window.LuvAIService.getRawApiKey() : "") || document.getElementById("ai-sum-key")?.value.trim() || localStorage.getItem("deepseek_api_key") || "";

    const btn = document.getElementById("btn-run-ai-summarize");
    const btnText = document.getElementById("txt-run-ai-sum");
    const emptyState = document.getElementById("ai-sum-empty-state");
    const loadingState = document.getElementById("ai-sum-loading");
    const resultBox = document.getElementById("ai-sum-result-box");

    // UI state: loading
    if (emptyState) emptyState.classList.add("hidden");
    if (resultBox) resultBox.classList.add("hidden");
    if (loadingState) loadingState.classList.remove("hidden");

    if (btn) {
        btn.disabled = true;
        btn.classList.add("btn-loading");
    }
    if (btnText) btnText.innerText = "ĐANG ĐỌC & TÓM TẮT...";
    if (typeof showProcessingAnimation === "function") {
        showProcessingAnimation("AI đang đọc & tóm tắt tài liệu...");
    }

    const formData = new FormData();
    formData.append("file", SELECTED_AI_SUM_FILE);
    formData.append("mode", mode);
    formData.append("length", length);
    formData.append("engine", engine);
    if (apiKey) formData.append("api_key", apiKey);

    try {
        const res = await fetch("/api/process/ai-summarize", {
            method: "POST",
            body: formData
        });

        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.detail || data.error || "Không thể tạo bản tóm tắt");
        }

        CURRENT_AI_SUMMARY_TEXT = data.summary_text || "";

        // Update metrics
        const ratioEl = document.getElementById("metric-ratio");
        const wordsEl = document.getElementById("metric-words");
        const origWordsEl = document.getElementById("metric-orig-words");
        const timeEl = document.getElementById("metric-time");

        if (ratioEl) ratioEl.innerText = `-${data.compression_ratio}`;
        if (wordsEl) wordsEl.innerText = `${data.summary_words.toLocaleString()} từ`;
        if (origWordsEl) origWordsEl.innerText = `${data.original_words.toLocaleString()} từ`;
        if (timeEl) timeEl.innerText = `${data.elapsed_seconds}s`;

        // Update download Word button
        const dlBtn = document.getElementById("btn-download-summary-docx");
        if (dlBtn && data.download_url) {
            dlBtn.href = data.download_url;
            dlBtn.download = data.filename;
        }

        // Render Markdown content to HTML
        const article = document.getElementById("ai-summary-content");
        if (article) {
            article.innerHTML = renderMarkdownToHtml(CURRENT_AI_SUMMARY_TEXT);
        }

        // Show result box
        if (loadingState) loadingState.classList.add("hidden");
        if (resultBox) resultBox.classList.remove("hidden");
        if (engine === "deepseek" && window.LuvAIService) {
            window.LuvAIService.recordGuestCall();
        }

    } catch (err) {
        console.error("Lỗi tóm tắt tài liệu:", err);
        alert("Lỗi tóm tắt tài liệu: " + err.message);
        if (loadingState) loadingState.classList.add("hidden");
        if (emptyState) emptyState.classList.remove("hidden");
    } finally {
        if (typeof hideProcessingAnimation === "function") {
            hideProcessingAnimation();
        }
        if (btn) {
            btn.disabled = false;
            btn.classList.remove("btn-loading");
        }
        if (btnText) btnText.innerText = "TÓM TẮT TÀI LIỆU BẰNG AI";
    }
}

async function copyAiSummaryText() {
    if (!CURRENT_AI_SUMMARY_TEXT || !CURRENT_AI_SUMMARY_TEXT.trim()) {
        alert("Chưa có nội dung bản tóm tắt để sao chép!");
        return;
    }

    try {
        await navigator.clipboard.writeText(CURRENT_AI_SUMMARY_TEXT);
        
        // Immediate feedback
        const btn = document.getElementById("btn-copy-summary");
        const btnTxt = document.getElementById("txt-copy-summary");
        if (btn && btnTxt) {
            const origHtml = btnTxt.innerHTML;
            btn.classList.add("btn-copy-success");
            btnTxt.innerText = "✓ Đã sao chép bản tóm tắt!";

            setTimeout(() => {
                btn.classList.remove("btn-copy-success");
                btnTxt.innerHTML = origHtml;
            }, 2500);
        }
    } catch (err) {
        alert("Không thể sao chép tự động: Vui lòng bôi đen văn bản và nhấn Ctrl+C.");
    }
}

// -------------------------------------------------------------
// 4. HELPER UTILITIES
// -------------------------------------------------------------
function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return "0 KB";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function renderMarkdownToHtml(md) {
    if (!md) return "";
    let html = md;

    // Headings
    html = html.replace(/^### (.*$)/gim, '<h3 class="summary-h3">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 class="summary-h2">$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1 class="summary-h1">$1</h1>');

    // Bold & Italic
    html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
    html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');

    // Bullet points
    html = html.replace(/^\s*[-•*]\s+(.*$)/gim, '<li class="summary-li">$1</li>');

    // Numbered lists
    html = html.replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li class="summary-li-num"><b>$1.</b> $2</li>');

    // Wrap consecutive list items in <ul>
    html = html.replace(/(<li class="summary-li">[\s\S]*?<\/li>)/gm, '<ul class="summary-ul">$1</ul>');
    html = html.replace(/<\/ul>\s*<ul class="summary-ul">/g, '');

    // Paragraphs
    const lines = html.split("\n");
    const result = [];
    for (let line of lines) {
        let trimmed = line.trim();
        if (trimmed && !trimmed.startsWith("<h") && !trimmed.startsWith("<ul") && !trimmed.startsWith("<li") && !trimmed.startsWith("</ul")) {
            result.push(`<p class="summary-p">${trimmed}</p>`);
        } else if (trimmed) {
            result.push(trimmed);
        }
    }

    return result.join("\n");
}

// -------------------------------------------------------------
// 5. MSDS INTELLIGENCE & SỔ HÓA CHẤT (CIL) CONTROLLER
// -------------------------------------------------------------
let CURRENT_MSDS_FILES = [];   // Array of File objects
let CURRENT_MSDS_FILE = null;  // Keep for backward compatibility (last file)
let msdsSearchTimer = null;
let CURRENT_MSDS_GHS_FILTER = "all";
let CURRENT_MSDS_ITEM_TYPE_FILTER = "all"; // "all" | "raw_material" | "finished_product"
let ALL_MSDS_CHEMICALS_CACHE = [];
let CURRENT_FILTERED_MSDS = [];
let SELECTED_MSDS_IDS = new Set();
let CIL_LEGAL_MATCHES_CACHE = new Map();   // Map<chem_id, Array<badgeObj>>
let CIL_LEGAL_CAS_MAP = new Map();         // Map<normalized_cas, badgeObj>

function normalizeCasSimple(cas) {
    if (!cas) return "";
    const m = String(cas).trim().match(/\b([1-9]\d{1,6})\s*-\s*(\d{2})\s*-\s*(\d)\b/);
    return m ? `${m[1]}-${m[2]}-${m[3]}` : "";
}

/**
 * Tải danh mục đối soát pháp lý CIL một lần để cache O(1) tra cứu huy hiệu
 */
async function preloadCilLegalMatches() {
    try {
        const resp = await fetch("/api/legal/matches?page_size=500");
        if (!resp.ok) return;
        const data = await resp.json();
        const items = data.items || [];
        
        CIL_LEGAL_MATCHES_CACHE.clear();
        CIL_LEGAL_CAS_MAP.clear();

        items.forEach(it => {
            const chemId = it.chemical_id;
            const cas = it.cas || it.matched_cas;
            const badge = it.legal_item?.badge || {
                label: it.legal_item?.section_title || "Pháp lý",
                tier: 3,
                color: "#f59e0b",
                bg: "#fffbeb"
            };

            if (chemId) {
                if (!CIL_LEGAL_MATCHES_CACHE.has(chemId)) {
                    CIL_LEGAL_MATCHES_CACHE.set(chemId, []);
                }
                const existing = CIL_LEGAL_MATCHES_CACHE.get(chemId);
                if (!existing.some(b => b.label === badge.label)) {
                    existing.push(badge);
                }
            }

            if (cas) {
                const norm = normalizeCasSimple(cas);
                if (norm && !CIL_LEGAL_CAS_MAP.has(norm)) {
                    CIL_LEGAL_CAS_MAP.set(norm, badge);
                }
            }
        });
    } catch (e) {
        console.warn("preloadCilLegalMatches non-blocking error:", e);
    }
}

/**
 * Lấy danh sách huy hiệu pháp lý cho 1 hóa chất (xét cả CAS chính và thành phần Mục 3)
 */
function getChemicalLegalBadges(item) {
    const badges = [];
    const seenLabels = new Set();

    // 1. Kiểm tra cache theo chemical_id
    const chemId = item.chem_id || item.chemical_id;
    if (chemId && CIL_LEGAL_MATCHES_CACHE.has(chemId)) {
        CIL_LEGAL_MATCHES_CACHE.get(chemId).forEach(b => {
            if (!seenLabels.has(b.label)) {
                seenLabels.add(b.label);
                badges.push(b);
            }
        });
    }

    // 2. Kiểm tra theo CAS chính
    const primaryCas = normalizeCasSimple(item.cas_numbers || item.cas_primary);
    if (primaryCas && CIL_LEGAL_CAS_MAP.has(primaryCas)) {
        const b = CIL_LEGAL_CAS_MAP.get(primaryCas);
        if (!seenLabels.has(b.label)) {
            seenLabels.add(b.label);
            badges.push(b);
        }
    }

    // 3. Kiểm tra từng thành phần trong composition nếu có
    if (Array.isArray(item.composition)) {
        item.composition.forEach(comp => {
            const cCas = normalizeCasSimple(comp.cas_number || comp.cas_no);
            if (cCas && CIL_LEGAL_CAS_MAP.has(cCas)) {
                const b = CIL_LEGAL_CAS_MAP.get(cCas);
                if (!seenLabels.has(b.label)) {
                    seenLabels.add(b.label);
                    badges.push(b);
                }
            }
        });
    }

    // 4. Nếu backend đã gửi sẵn legal_badges hoặc summary_badges
    const rawBadges = item.legal_badges || item.summary_badges || [];
    rawBadges.forEach(rb => {
        const lbl = typeof rb === "string" ? rb : rb.label;
        if (lbl && !seenLabels.has(lbl)) {
            seenLabels.add(lbl);
            badges.push(typeof rb === "object" ? rb : { label: lbl, tier: 3 });
        }
    });

    return badges;
}

/**
 * Render HTML cho nhóm huy hiệu pháp lý chuẩn 5 phân loại
 */
function renderLegalBadgesHtml(badges) {
    if (!badges || badges.length === 0) return "";
    
    return badges.map(b => {
        const label = b.label || String(b);
        let badgeClass = "badge-declare";
        let icon = "📋";
        let titleDesc = "Hóa chất cần khai báo / có điều kiện theo NĐ 24/2026/NĐ-CP";

        const upper = label.toUpperCase();
        if (upper.includes("KIỂM SOÁT ĐẶC BIỆT") || upper.includes("PL-III")) {
            badgeClass = "badge-special";
            icon = "⚠️";
            titleDesc = "Hóa chất cần kiểm soát đặc biệt nghiêm ngặt theo NĐ 24/2026/NĐ-CP (Phụ lục III)";
        } else if (upper.includes("TIỀN CHẤT") || upper.includes("ND26-IV") || upper.includes("ND28-IV")) {
            badgeClass = "badge-precursor";
            icon = "⚡";
            titleDesc = "Tiền chất ma túy / công nghiệp theo NĐ 26/2026/NĐ-CP (Cần lập sổ theo dõi & báo cáo)";
        } else if (upper.includes("HẠN CHẾ") || upper.includes("CẤM") || upper.includes("ND26-I") || upper.includes("ND26-II") || upper.includes("ND28-I") || upper.includes("ND28-II")) {
            badgeClass = "badge-restricted";
            icon = "🚫";
            titleDesc = "Hóa chất cấm hoặc hạn chế sản xuất, kinh doanh theo NĐ 24 & NĐ 26";
        } else if (upper.includes("QCVN") || upper.includes("TIẾP XÚC")) {
            badgeClass = "badge-qcvn";
            icon = "🛡️";
            titleDesc = "QCVN 01:2025/BYT - Quy chuẩn giới hạn tiếp xúc nghề nghiệp (Bắt buộc quan trắc môi trường)";
        }

        return `<span class="msds-legal-badge ${badgeClass}" title="${escapeHtml(titleDesc)}">${icon} ${escapeHtml(label)}</span>`;
    }).join("");
}

/**
 * Điều khiển chọn bộ lọc loại hàng: Tất cả / Nguyên liệu / Thành phẩm
 */
function setMsdsItemTypeFilter(type) {
    CURRENT_MSDS_ITEM_TYPE_FILTER = type || "all";

    document.querySelectorAll(".msds-type-pill").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.type === CURRENT_MSDS_ITEM_TYPE_FILTER);
    });

    const selectEl = document.getElementById("msds-item-type-select");
    if (selectEl) selectEl.value = CURRENT_MSDS_ITEM_TYPE_FILTER;

    const activeSearch = (document.getElementById("msds-search-input")?.value || "").trim();
    renderMsdsFilteredTable(ALL_MSDS_CHEMICALS_CACHE, activeSearch);
}

function toggleMsdsSidebar() {
    const sidebar = document.getElementById("msds-left-panel");
    const reopenBtn = document.getElementById("btn-reopen-msds-sidebar");
    if (!sidebar) return;
    const isCollapsed = sidebar.classList.toggle("collapsed");
    if (reopenBtn) {
        reopenBtn.classList.toggle("hidden", !isCollapsed);
    }
}
window.toggleMsdsSidebar = toggleMsdsSidebar;

function toggleMsdsIntakePanel() {
    if (isGuestUser()) {
        alert("Khách (Guest) không có quyền nạp hồ sơ MSDS.");
        return;
    }
    const drawer = document.getElementById("msds-intake-drawer");
    const btn = document.getElementById("btn-toggle-msds-intake");
    const txt = document.getElementById("txt-toggle-msds-intake");
    if (!drawer) return;

    const isHidden = drawer.classList.toggle("collapsed");
    if (btn) btn.classList.toggle("active", !isHidden);
    if (txt) {
        txt.textContent = isHidden ? "➕ Mở khung nạp MSDS" : "Thu gọn khung nạp";
    }
}

function handleMsdsFileSelect(e) {
    if (e.target && e.target.files && e.target.files.length > 0) {
        const newFiles = Array.from(e.target.files);
        // Merge with existing list (avoid duplicates by name+size)
        newFiles.forEach(f => {
            const isDup = CURRENT_MSDS_FILES.some(x => x.name === f.name && x.size === f.size);
            if (!isDup) CURRENT_MSDS_FILES.push(f);
        });
        renderMsdsFileList();
    }
}

function renderMsdsFileList() {
    const dropPrompt = document.getElementById("msds-drop-prompt");
    const selectedInfo = document.getElementById("msds-selected-info");
    const fileCountEl = document.getElementById("msds-file-count");
    const fileListEl = document.getElementById("msds-file-list");

    // Ensure intake drawer is expanded when files are selected
    const drawer = document.getElementById("msds-intake-drawer");
    if (drawer && CURRENT_MSDS_FILES.length > 0 && drawer.classList.contains("collapsed")) {
        toggleMsdsIntakePanel();
    }

    if (CURRENT_MSDS_FILES.length === 0) {
        if (dropPrompt) dropPrompt.classList.remove("hidden");
        if (selectedInfo) selectedInfo.classList.add("hidden");
        return;
    }

    if (dropPrompt) dropPrompt.classList.add("hidden");
    if (selectedInfo) selectedInfo.classList.remove("hidden");

    const count = CURRENT_MSDS_FILES.length;
    if (fileCountEl) fileCountEl.textContent = `📦 ${count} tệp đã chọn`;

    if (fileListEl) {
        fileListEl.innerHTML = CURRENT_MSDS_FILES.map((f, idx) => `
            <div class="msds-file-chip" title="${escapeHtml(f.name)} (${formatFileSize(f.size)})">
                <span class="msds-chip-name">${escapeHtml(f.name)}</span>
                <span class="msds-chip-size">${formatFileSize(f.size)}</span>
                <button type="button" class="msds-chip-rm" onclick="removeMsdsFile(${idx})" title="Gỡ tệp này">✕</button>
            </div>
        `).join("");
    }

    // Update legacy single-file compat
    CURRENT_MSDS_FILE = CURRENT_MSDS_FILES[CURRENT_MSDS_FILES.length - 1] || null;
}

function removeMsdsFile(idx) {
    CURRENT_MSDS_FILES.splice(idx, 1);
    const inp = document.getElementById("msds-file-input");
    if (inp) inp.value = "";
    renderMsdsFileList();
}

function setMsdsFile(file) {
    CURRENT_MSDS_FILES = [file];
    CURRENT_MSDS_FILE = file;
    renderMsdsFileList();
}

function clearMsdsFile() {
    CURRENT_MSDS_FILES = [];
    CURRENT_MSDS_FILE = null;
    const fileInput = document.getElementById("msds-file-input");
    if (fileInput) fileInput.value = "";
    renderMsdsFileList();
}

let PENDING_MSDS_DUPLICATE_PAYLOAD = null;

async function runMsdsAnalysis() {
    if (isGuestUser()) {
        alert("Khách (Guest) chỉ có quyền Xem & Xuất dữ liệu MSDS, không thể nạp hoặc phân tích tệp mới.");
        return;
    }
    if (CURRENT_MSDS_FILES.length === 0) {
        alert("Vui lòng chọn hoặc kéo thả tệp MSDS / SDS (.pdf, .docx, .doc, .txt) vào khung nạp trước!");
        document.getElementById("msds-file-input")?.click();
        return;
    }

    const engine = document.getElementById("msds-ai-engine")?.value || "deepseek";

    if (engine === "deepseek" && window.LuvAIService) {
        if (!window.LuvAIService.requireReady({ contextName: "Bóc tách & Phân tích MSDS bằng AI DeepSeek" })) {
            return;
        }
    }

    let apiKey = (window.LuvAIService ? window.LuvAIService.getRawApiKey() : "") || (localStorage.getItem("deepseek_api_key") || "").trim();

    const btn = document.getElementById("btn-run-msds-analyze");
    const txtBtn = document.getElementById("txt-run-msds-analyze");
    const loading = document.getElementById("msds-loading");
    const inventory = document.getElementById("msds-inventory-container");

    if (btn) btn.disabled = true;
    if (loading) loading.classList.remove("hidden");
    if (inventory) inventory.classList.add("hidden");

    const totalFiles = CURRENT_MSDS_FILES.length;
    const results = { success: [], duplicate: [], failed: [] };

    for (let i = 0; i < totalFiles; i++) {
        const file = CURRENT_MSDS_FILES[i];
        if (txtBtn) txtBtn.textContent = `Đang phân tích ${i + 1}/${totalFiles}: ${file.name.length > 24 ? file.name.substring(0, 22) + "..." : file.name}`;
        if (typeof showProcessingAnimation === "function") {
            showProcessingAnimation(`Phân tích ${i + 1}/${totalFiles} — AI đang bóc tách 16 mục GHS: ${file.name}`);
        }

        const formData = new FormData();
        formData.append("file", file);
        formData.append("engine", engine);
        if (apiKey) formData.append("api_key", apiKey);

        try {
            const resp = await fetch("/api/msds/upload-and-summarize", {
                method: "POST",
                body: formData
            });
            const data = await resp.json();

            if (!resp.ok || !data.success) {
                results.failed.push({ name: file.name, error: data.detail || data.error || "Lỗi không xác định" });
                continue;
            }

            if (data.duplicate) {
                results.duplicate.push({ name: file.name, data });
                continue;
            }

            const savedCode = data.chemical_id || (data.data && data.data.chem_id) || "";
            const savedName = (data.data && data.data.product_name) || "Thành công";
            const chemObj = data.data || { chemical_id: savedCode, product_name: savedName };

            // Tự động đẩy file gốc lên Google Drive & đồng bộ 2 chiều vào Google Sheets qua GAS Web App
            if (window.MsdsGasSync && window.MsdsGasSync.getUrl()) {
                try {
                    const fileBase64 = await readFileAsBase64(file);
                    const gasResult = await window.MsdsGasSync.upsertChemical(chemObj, fileBase64, file.name, file.type);
                    if (gasResult && gasResult.item) {
                        if (gasResult.item.drive_view_url) chemObj.drive_view_url = gasResult.item.drive_view_url;
                        if (gasResult.item.drive_download_url) chemObj.drive_download_url = gasResult.item.drive_download_url;
                        if (gasResult.item.drive_file_id) chemObj.drive_file_id = gasResult.item.drive_file_id;

                        // Đồng bộ liên kết Google Drive vào SQLite trên máy chủ
                        await fetch("/api/msds/update-drive-links", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                chemical_id: savedCode,
                                drive_file_id: gasResult.item.drive_file_id || "",
                                drive_view_url: gasResult.item.drive_view_url || "",
                                drive_download_url: gasResult.item.drive_download_url || ""
                            })
                        }).catch(() => {});
                    }
                    if (window.MsdsGasSync && typeof window.MsdsGasSync.updateBadge === "function") {
                        window.MsdsGasSync.updateBadge("synced", "Đã đồng bộ Drive");
                    }
                } catch (gasErr) {
                    console.warn("GAS auto-sync in runMsdsAnalysis warning:", gasErr);
                }
            }

            results.success.push({ name: file.name, code: savedCode, productName: savedName });
        } catch (err) {
            results.failed.push({ name: file.name, error: err.message });
        }
    }

    // Restore button text
    if (txtBtn) txtBtn.textContent = "PHÂN TÍCH & LƯU VÀO SỔ CIL";
    if (btn) btn.disabled = false;
    if (loading) loading.classList.add("hidden");
    if (inventory) inventory.classList.remove("hidden");
    if (typeof hideProcessingAnimation === "function") hideProcessingAnimation();

    // If only 1 file was uploaded and it's a duplicate, open the interactive Duplicate Comparison Modal
    if (totalFiles === 1 && results.duplicate.length === 1) {
        PENDING_MSDS_DUPLICATE_PAYLOAD = results.duplicate[0].data;
        openMsdsDuplicateModal(PENDING_MSDS_DUPLICATE_PAYLOAD);
        return;
    }

    // Build summary message
    let msg = `📊 KẾT QUẢ PHÂN TÍCH MSDS (${totalFiles} tệp)\n`;
    msg += `${"─".repeat(42)}\n`;
    if (results.success.length > 0) {
        msg += `✅ Thành công (${results.success.length}):\n`;
        results.success.forEach(r => { msg += `  • ${r.code} — ${r.productName}\n    (${r.name})\n`; });
    }
    if (results.duplicate.length > 0) {
        msg += `\n⚠️ Trùng lặp - Đã bỏ qua (${results.duplicate.length}):\n`;
        results.duplicate.forEach(r => { msg += `  • ${r.name}\n    → Mã đã tồn tại: ${r.data.chemical_id || "N/A"}\n`; });
    }
    if (results.failed.length > 0) {
        msg += `\n❌ Thất bại (${results.failed.length}):\n`;
        results.failed.forEach(r => { msg += `  • ${r.name}\n    → ${r.error}\n`; });
    }

    alert(msg);
    clearMsdsFile();
    await loadMsdsChemicalsList();

    // Auto-open safety card for the last successfully saved chemical
    if (results.success.length > 0) {
        const lastCode = results.success[results.success.length - 1].code;
        if (lastCode) openMsdsSafetyModal(lastCode);
    }
}

function openMsdsDuplicateModal(dupPayload) {
    const modal = document.getElementById("msds-duplicate-modal");
    if (!modal) return;

    const code = dupPayload.chemical_id || dupPayload.chem_id || "N/A";
    const existing = dupPayload.existing_chemical || {};
    const newData = dupPayload.data || {};
    const suggested = dupPayload.suggested_new_code || `${code}-V2`;

    const codeHighlight = document.getElementById("dup-code-highlight");
    const overwriteLbl = document.getElementById("dup-overwrite-code-lbl");
    const existingBox = document.getElementById("dup-existing-details");
    const newBox = document.getElementById("dup-new-details");
    const newCodeInput = document.getElementById("dup-new-code-input");

    if (codeHighlight) codeHighlight.innerText = code;
    if (overwriteLbl) overwriteLbl.innerText = code;
    if (newCodeInput) newCodeInput.value = suggested;

    if (existingBox) {
        existingBox.innerHTML = `
            <div><b>Mã SP / MSDS:</b> <span style="font-family:monospace; color:#0F5C78; font-weight:700;">${escapeHtml(existing.chemical_id || code)}</span></div>
            <div><b>Tên sản phẩm:</b> ${escapeHtml(existing.product_name_vi || existing.product_name_original || "N/A")}</div>
            <div><b>Công dụng:</b> ${escapeHtml(existing.intended_use || "N/A")}</div>
            <div><b>Ngày sửa đổi:</b> ${escapeHtml(existing.revision_date || "N/A")}</div>
            <div><b>Số CAS chính:</b> <span style="font-family:monospace;">${escapeHtml(existing.cas_primary || "N/A")}</span></div>
            <div><b>Nhà sản xuất:</b> ${escapeHtml(existing.manufacturer || "N/A")}</div>
            <div><b>Tệp gốc:</b> <span style="color:#64748b;">${escapeHtml(existing.source_file || "N/A")}</span></div>
        `;
    }

    if (newBox) {
        newBox.innerHTML = `
            <div><b>Mã SP / MSDS:</b> <span style="font-family:monospace; color:#166534; font-weight:700;">${escapeHtml(newData.product_code || code)}</span></div>
            <div><b>Tên sản phẩm:</b> ${escapeHtml(newData.product_name_vi || newData.product_name_original || "N/A")}</div>
            <div><b>Công dụng:</b> ${escapeHtml(newData.intended_use || "N/A")}</div>
            <div><b>Ngày sửa đổi:</b> ${escapeHtml(newData.revision_date || "N/A")}</div>
            <div><b>Số CAS chính:</b> <span style="font-family:monospace;">${escapeHtml(newData.cas_primary || "N/A")}</span></div>
            <div><b>Nhà sản xuất:</b> ${escapeHtml(newData.manufacturer || "N/A")}</div>
            <div><b>Tệp mới nạp:</b> <span style="color:#166534;">${escapeHtml(newData.source_file || "N/A")}</span></div>
        `;
    }

    modal.classList.remove("hidden");
}

function closeMsdsDuplicateModal() {
    const modal = document.getElementById("msds-duplicate-modal");
    if (modal) modal.classList.add("hidden");
    PENDING_MSDS_DUPLICATE_PAYLOAD = null;
}

async function confirmMsdsDuplicateAction(action) {
    if (!PENDING_MSDS_DUPLICATE_PAYLOAD || !PENDING_MSDS_DUPLICATE_PAYLOAD.data) {
        closeMsdsDuplicateModal();
        return;
    }

    const baseCode = PENDING_MSDS_DUPLICATE_PAYLOAD.chemical_id || PENDING_MSDS_DUPLICATE_PAYLOAD.data.product_code || "";
    let targetCode = baseCode;

    if (action === "new_code") {
        const inp = document.getElementById("dup-new-code-input");
        targetCode = (inp ? inp.value : "").trim().toUpperCase();
        if (!targetCode) {
            alert("Vui lòng nhập Mã Sản Phẩm / MSDS mới!");
            inp?.focus();
            return;
        }
        if (targetCode.toUpperCase() === baseCode.toUpperCase()) {
            alert(`Mã mới đang trùng với mã cũ "${baseCode}". Vui lòng nhập mã khác (ví dụ: ${baseCode}-V2) hoặc bấm "Ghi đè mã cũ"!`);
            inp?.focus();
            return;
        }
    }

    const btnOverwrite = document.getElementById("btn-dup-overwrite");
    const btnSaveNew = document.getElementById("btn-dup-save-new");
    if (btnOverwrite) btnOverwrite.disabled = true;
    if (btnSaveNew) btnSaveNew.disabled = true;

    try {
        const resp = await fetch("/api/msds/confirm-save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                data: PENDING_MSDS_DUPLICATE_PAYLOAD.data,
                action: action,
                target_code: targetCode
            })
        });

        const res = await resp.json();
        if (!resp.ok || !res.success) {
            alert("⚠️ " + (res.error || res.detail || "Không thể lưu dữ liệu MSDS."));
            return;
        }

        const finalCode = res.chemical_id || targetCode;
        closeMsdsDuplicateModal();
        clearMsdsFile();
        await loadMsdsChemicalsList();
        openMsdsSafetyModal(finalCode);
    } catch (err) {
        alert("Lỗi xác nhận lưu MSDS: " + err.message);
    } finally {
        if (btnOverwrite) btnOverwrite.disabled = false;
        if (btnSaveNew) btnSaveNew.disabled = false;
    }
}

// =========================================================================
// HỆ THỐNG BIỂU TRƯNG NGUY HẠI GHS QUỐC TẾ (HÌNH THOI VIỀN ĐỎ SVG CHUẨN)
// =========================================================================
const GHS_PICTOGRAM_INFO = {
    "GHS01": {
        short_vi: "Chất nổ",
        full_vi: "GHS01: Chất nổ / Vật liệu dễ nổ",
        svg_inner: `<circle cx="17" cy="21" r="4.5" fill="#0f172a"/><path d="M21 17l5-5M22 20l7-1M20 15l2-6M15 15l-3-4M21 23l6 4" stroke="#0f172a" stroke-width="1.8" stroke-linecap="round"/><circle cx="26" cy="14" r="1.2" fill="#0f172a"/><circle cx="28" cy="21" r="1.1" fill="#0f172a"/>`
    },
    "GHS02": {
        short_vi: "Dễ cháy",
        full_vi: "GHS02: Chất dễ cháy (Khí, Lỏng, Rắn)",
        svg_inner: `<path d="M20 9c1.5 3.5-1.5 5.5 0 8.5 1-2 3-3 3.5-5 2 3 2.5 6.8.5 9.8-1.2 1.8-3 2.7-4 2.7s-2.8-.9-4-2.7c-1.8-2.6-1.2-6 .8-8.2-.2 1.5.5 2.5 1.5 3-.8-2.8-.3-5.8 1.7-8.1z" fill="#0f172a"/><line x1="13.5" y1="27" x2="26.5" y2="27" stroke="#0f172a" stroke-width="2" stroke-linecap="round"/>`
    },
    "GHS03": {
        short_vi: "Oxy hóa",
        full_vi: "GHS03: Chất oxy hóa mạnh",
        svg_inner: `<path d="M20 8c1.2 2.8-1 4.2 0 6.5.8-1.5 2.2-2.2 2.5-3.8 1.5 2.2 1.8 4.8.4 7-1.8 1.2-4.2 1.2-5.8 0-1.2-1.8-.8-4.2.6-5.8 0 1 .4 1.8 1.1 2.2-.5-2-.2-4.2 1.2-6.1z" fill="#0f172a"/><circle cx="20" cy="22.5" r="4" fill="none" stroke="#0f172a" stroke-width="2"/><line x1="13.5" y1="27.5" x2="26.5" y2="27.5" stroke="#0f172a" stroke-width="2" stroke-linecap="round"/>`
    },
    "GHS04": {
        short_vi: "Khí nén",
        full_vi: "GHS04: Khí dưới áp suất / Khí nén",
        svg_inner: `<path d="M14 23l9-9c1.5-1.5 3.8-1.5 5.2 0 .5.5.5 1.2 0 1.8l-1.2 1.2c.3 1.2-.2 2.6-1.2 3.6l-8.2 8.2c-1 1-2.5 1-3.5 0l-.1-.1c-1-1-1-2.5 0-3.5z" fill="#0f172a"/>`
    },
    "GHS05": {
        short_vi: "Ăn mòn",
        full_vi: "GHS05: Chất ăn mòn kim loại / Bỏng da & mắt",
        svg_inner: `<path d="M13 13l4 3-1.2 1.8-4-3zM27 13l-4 3 1.2 1.8 4-3z" fill="#0f172a"/><circle cx="17" cy="20" r="1.1" fill="#0f172a"/><circle cx="23" cy="20" r="1.1" fill="#0f172a"/><rect x="11.5" y="24" width="7.5" height="2.8" fill="#0f172a"/><path d="M21.5 23.5h6.5c.8 0 1.2.6 1.2 1.2v1.8h-7.7z" fill="#0f172a"/>`
    },
    "GHS06": {
        short_vi: "Độc cấp tính",
        full_vi: "GHS06: Độc tính cấp (Nguy hiểm chết người khi nuốt/hít/tiếp xúc)",
        svg_inner: `<circle cx="20" cy="16.5" r="5" fill="#0f172a"/><circle cx="18.2" cy="16" r="1.1" fill="#fff"/><circle cx="21.8" cy="16" r="1.1" fill="#fff"/><path d="M19.3 18.2h1.4l-.7 1.3z" fill="#fff"/><rect x="18" y="20.5" width="4" height="2.2" rx="0.5" fill="#0f172a"/><path d="M13 24.5l14-5M13 19.5l14 5" stroke="#0f172a" stroke-width="2" stroke-linecap="round"/>`
    },
    "GHS07": {
        short_vi: "Kích ứng",
        full_vi: "GHS07: Nguy hại / Kích ứng da, mắt, hô hấp",
        svg_inner: `<path d="M20 11.5v10" stroke="#0f172a" stroke-width="3.4" stroke-linecap="round"/><circle cx="20" cy="26.2" r="2" fill="#0f172a"/>`
    },
    "GHS08": {
        short_vi: "Sức khỏe",
        full_vi: "GHS08: Nguy hại sức khỏe nghiêm trọng lâu dài / Hô hấp",
        svg_inner: `<circle cx="20" cy="13" r="3.2" fill="#0f172a"/><path d="M14.5 26.5c0-4.2 2.5-6.8 5.5-6.8s5.5 2.6 5.5 6.8z" fill="#0f172a"/><path d="M20 18.2l.8 2.2 2.3-.5-1.5 1.8 1.5 1.8-2.3-.5-.8 2.2-.8-2.2-2.3.5 1.5-1.8-1.5-1.8 2.3.5z" fill="#fff"/>`
    },
    "GHS09": {
        short_vi: "Môi trường",
        full_vi: "GHS09: Nguy hại đối với môi trường thủy sinh",
        svg_inner: `<path d="M16.5 24v-8M16.5 18l-2.5-2M16.5 19.5l2.5-2M16.5 16l1.5-2.2" stroke="#0f172a" stroke-width="1.6" stroke-linecap="round"/><path d="M12 24.5h16" stroke="#0f172a" stroke-width="1.6" stroke-linecap="round"/><path d="M21 22c2-1.5 4.5-1.2 6 .3-1.5 1.5-4 1.8-6-.3z" fill="#0f172a"/><path d="M26.5 22.2l1.8-1.2v2.4z" fill="#0f172a"/>`
    }
};

function renderGhsDiamondSvg(code, size = 28) {
    const cleanCode = String(code || "").trim().toUpperCase();
    const info = GHS_PICTOGRAM_INFO[cleanCode] || GHS_PICTOGRAM_INFO["GHS07"];
    return `
        <svg width="${size}" height="${size}" viewBox="0 0 40 40" style="flex-shrink:0; display:inline-block; vertical-align:middle; filter:drop-shadow(0 1px 2px rgba(220,38,38,0.18));" aria-label="${cleanCode}">
            <polygon points="20,2.2 37.8,20 20,37.8 2.2,20" fill="#ffffff" stroke="#dc2626" stroke-width="3.2" stroke-linejoin="round"/>
            ${info.svg_inner}
        </svg>
    `;
}

function renderGhsTableBadge(code) {
    const cleanCode = String(code || "").trim().toUpperCase();
    if (!cleanCode || cleanCode === "NON DG" || cleanCode === "NONDG" || cleanCode === "NONE" || cleanCode === "-") {
        return `
            <div title="NON DG: Không phải là chất hay hỗn hợp nguy hại theo Phần 2 GHS" style="display:inline-flex; align-items:center; gap:6px; background:#f0fdf4; border:1px solid #86efac; border-radius:6px; padding:3px 9px 3px 6px; margin:2px 4px 2px 0; box-shadow:0 1px 2px rgba(22,163,74,0.06);">
                <span style="display:inline-flex; align-items:center; justify-content:center; width:19px; height:19px; border-radius:50%; background:#16a34a; color:#ffffff; font-size:11px; font-weight:800; flex-shrink:0;">✓</span>
                <div style="line-height:1.15;">
                    <div style="font-family:monospace; font-weight:800; font-size:11px; color:#15803d;">NON DG</div>
                    <div style="font-size:9.5px; font-weight:600; color:#166534; white-space:nowrap;">Không nguy hại</div>
                </div>
            </div>
        `;
    }
    const info = GHS_PICTOGRAM_INFO[cleanCode];
    if (!info) {
        return `<span style="background:#f1f5f9; color:#0f172a; border:1px solid #cbd5e1; padding:2px 6px; border-radius:4px; font-family:monospace; font-size:11px;">${escapeHtml(cleanCode)}</span>`;
    }
    return `
        <div title="${escapeHtml(info.full_vi)}" style="display:inline-flex; align-items:center; gap:5px; background:#fff; border:1px solid #fecaca; border-radius:6px; padding:2px 7px 2px 3px; margin:2px 4px 2px 0; box-shadow:0 1px 2px rgba(0,0,0,0.04);">
            ${renderGhsDiamondSvg(cleanCode, 24)}
            <div style="line-height:1.15;">
                <div style="font-family:monospace; font-weight:800; font-size:10.5px; color:#b91c1c;">${cleanCode}</div>
                <div style="font-size:10px; font-weight:600; color:#334155; white-space:nowrap;">${info.short_vi}</div>
            </div>
        </div>
    `;
}

function renderGhsSafetyCardGallery(codesStr) {
    const rawStr = String(codesStr || "").trim().toUpperCase();
    const codes = rawStr.split(/[,;]+/).map(s => s.trim()).filter(c => /^GHS0[1-9]$/.test(c));
    if (codes.length === 0 || rawStr.includes("NON DG") || rawStr.includes("NONDG")) {
        return `
            <div style="display:flex; align-items:center; gap:10px; background:#f0fdf4; border:1.5px solid #86efac; border-radius:8px; padding:8px 14px; margin-top:10px;">
                <span style="display:inline-flex; align-items:center; justify-content:center; width:34px; height:34px; border-radius:50%; background:#16a34a; color:#ffffff; font-size:17px; font-weight:800; flex-shrink:0;">✓</span>
                <div>
                    <div style="font-family:monospace; font-weight:800; font-size:12.5px; color:#15803d;">NON DG — KHÔNG PHÂN LOẠI NGUY HẠI THEO GHS</div>
                    <div style="font-size:11.5px; color:#166534; font-weight:500; margin-top:1px;">Phần 2 của MSDS xác nhận sản phẩm không thuộc diện phân loại nguy hại GHS (Không có hình đồ cảnh báo).</div>
                </div>
            </div>
        `;
    }
    return `
        <div style="display:flex; flex-wrap:wrap; gap:10px; margin-top:10px;">
            ${codes.map(code => {
                const info = GHS_PICTOGRAM_INFO[code] || GHS_PICTOGRAM_INFO["GHS07"];
                return `
                    <div style="display:flex; align-items:center; gap:10px; background:#ffffff; border:1.5px solid #fca5a5; border-radius:8px; padding:6px 12px 6px 8px; box-shadow:0 2px 5px rgba(220,38,38,0.08);">
                        ${renderGhsDiamondSvg(code, 42)}
                        <div>
                            <div style="font-family:monospace; font-weight:800; font-size:12px; color:#dc2626;">${code} — ${info.short_vi.toUpperCase()}</div>
                            <div style="font-size:11.5px; color:#334155; font-weight:500; margin-top:1px;">${info.full_vi.replace(/^GHS0\d:\s*/, "")}</div>
                        </div>
                    </div>
                `;
            }).join("")}
        </div>
    `;
}

function setMsdsGhsFilter(ghsCode) {
    CURRENT_MSDS_GHS_FILTER = ghsCode || "all";
    const pillsContainer = document.getElementById("msds-ghs-filter-pills");
    if (pillsContainer) {
        const buttons = pillsContainer.querySelectorAll(".msds-filter-pill");
        buttons.forEach(btn => {
            const code = btn.getAttribute("data-ghs");
            btn.classList.toggle("active", code === CURRENT_MSDS_GHS_FILTER);
        });
    }
    const searchVal = document.getElementById("msds-search-input")?.value || "";
    renderMsdsFilteredTable(ALL_MSDS_CHEMICALS_CACHE, searchVal.trim());
}

function clearMsdsSearchInput() {
    const inp = document.getElementById("msds-search-input");
    const clearBtn = document.getElementById("msds-search-clear");
    if (inp) {
        inp.value = "";
        inp.focus();
    }
    if (clearBtn) clearBtn.classList.add("hidden");
    renderMsdsFilteredTable(ALL_MSDS_CHEMICALS_CACHE, "");
}

function updateMsdsKpiStats(allItems) {
    const total = allItems.length;
    let nonDgCount = 0;
    let hazardCount = 0;
    const suppliersSet = new Set();

    allItems.forEach(item => {
        const rawGhs = String(item.ghs_symbols || "").trim().toUpperCase();
        const isNonDg = !rawGhs || rawGhs.includes("NON DG") || rawGhs.includes("NONDG") || rawGhs === "NONE";
        if (isNonDg) {
            nonDgCount++;
        } else {
            hazardCount++;
        }
        const sup = String(item.manufacturer_supplier || item.manufacturer || "").trim();
        if (sup && sup.toLowerCase() !== "chưa cập nhật" && sup.toLowerCase() !== "n/a") {
            suppliersSet.add(sup.toUpperCase());
        }
    });

    const elTotal = document.getElementById("msds-stat-total");
    const elHaz = document.getElementById("msds-stat-hazardous");
    const elNonDg = document.getElementById("msds-stat-nondg");
    const elSup = document.getElementById("msds-stat-suppliers");
    const navBadge = document.getElementById("nav-msds-count-badge");

    if (elTotal) elTotal.textContent = total;
    if (elHaz) elHaz.textContent = hazardCount;
    if (elNonDg) elNonDg.textContent = nonDgCount;
    if (elSup) elSup.textContent = suppliersSet.size;
    if (navBadge) navBadge.textContent = total > 0 ? `${total} CIL` : "CIL";
}


function readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = err => reject(err);
        reader.readAsDataURL(file);
    });
}

// ==============================================================================
// MSDS & CIL CONTINUOUS 2-WAY GOOGLE SHEETS & DRIVE SYNC ENGINE
// ==============================================================================
const MsdsGasSync = {
    DEFAULT_TOKEN: "LUV_PDF_SYNC_KEY_2026",
    DEFAULT_FOLDER_URL: "https://drive.google.com/drive/u/0/my-drive",

    getUrl() {
        return (localStorage.getItem("msds_gas_url") || "").trim();
    },
    setUrl(url) {
        localStorage.setItem("msds_gas_url", (url || "").trim());
    },
    getToken() {
        return (localStorage.getItem("msds_gas_token") || this.DEFAULT_TOKEN).trim();
    },
    setToken(token) {
        localStorage.setItem("msds_gas_token", (token || this.DEFAULT_TOKEN).trim());
    },
    getFolderUrl() {
        return localStorage.getItem("msds_gas_folder_url") || this.DEFAULT_FOLDER_URL;
    },
    setFolderUrl(url) {
        if (url) localStorage.setItem("msds_gas_folder_url", url);
    },
    getLocalVersion() {
        return parseInt(localStorage.getItem("luv_msds_version") || "0", 10);
    },
    setLocalVersion(v) {
        localStorage.setItem("luv_msds_version", String(v || 0));
    },
    getOutbox() {
        try {
            return JSON.parse(localStorage.getItem("cil_sync_outbox") || "[]");
        } catch (_) {
            return [];
        }
    },
    setOutbox(list) {
        localStorage.setItem("cil_sync_outbox", JSON.stringify(list || []));
        this.updateBadgeFromOutbox();
    },
    queueOutbox(actionPayload) {
        const queue = this.getOutbox();
        queue.push({
            id: "outbox_" + Date.now() + "_" + Math.random().toString(36).substring(2, 7),
            payload: actionPayload,
            queuedAt: new Date().toISOString()
        });
        this.setOutbox(queue);
    },
    updateBadge(status, text) {
        const badge = document.getElementById("msds-cloud-sync-status");
        if (!badge) return;
        if (status === "syncing") {
            badge.style.background = "#eff6ff";
            badge.style.color = "#1d4ed8";
            badge.style.borderColor = "#93c5fd";
            badge.innerHTML = `<span style="display:inline-block; animation:spin 1s linear infinite; margin-right:4px;">⏳</span> ${text || "Đang đồng bộ Drive..."}`;
        } else if (status === "synced") {
            badge.style.background = "#ecfdf5";
            badge.style.color = "#065f46";
            badge.style.borderColor = "#a7f3d0";
            badge.innerHTML = `☁️ ${text || "Đã đồng bộ Drive"}`;
        } else if (status === "pending" || status === "error") {
            badge.style.background = "#fff7ed";
            badge.style.color = "#c2410c";
            badge.style.borderColor = "#fdba74";
            const outboxCount = this.getOutbox().length;
            const countText = outboxCount > 0 ? ` (${outboxCount})` : "";
            badge.innerHTML = `⚠️ ${text || ("Chờ đồng bộ Drive" + countText)}`;
        }
    },
    updateBadgeFromOutbox() {
        const count = this.getOutbox().length;
        if (count > 0) {
            this.updateBadge("pending", `Chờ đồng bộ Drive (${count})`);
        } else {
            this.updateBadge("synced", "Đã đồng bộ Drive");
        }
    },

    // Convert any chemical object to 16-field standard format
    normalizeItem(item) {
        if (!item || typeof item !== "object") return null;
        const id = item.id || item.chemical_id || item.chem_id || item.product_code || ("CHEM_" + Date.now());
        const product_code = item.product_code || item.chem_id || item.chemical_id || id;
        const chemical_name = item.chemical_name || item.product_name_vi || item.product_name || item.product_name_original || product_code;
        const rawType = String(item.category || item.item_type || "").toLowerCase();
        const category = (rawType.includes("finish") || rawType.includes("thành phẩm")) ? "Thành phẩm" : "Nguyên liệu";
        const usage = item.usage || item.intended_use || item.storage_condition || "Sử dụng trong sản xuất công nghiệp";
        const updated_date = item.updated_date || item.revision_date || item.updated_at || item.created_at || new Date().toISOString().slice(0, 10);
        const cas_number = item.cas_number || item.cas_primary || item.cas_numbers || "";
        const supplier = item.supplier || item.manufacturer_supplier || item.manufacturer || "";

        let ghs_classifications = [];
        if (Array.isArray(item.ghs_classifications)) {
            ghs_classifications = item.ghs_classifications;
        } else if (Array.isArray(item.ghs_codes)) {
            ghs_classifications = item.ghs_codes;
        } else if (typeof item.ghs_symbols === "string") {
            ghs_classifications = item.ghs_symbols.split(/[,;]+/).map(s => s.trim()).filter(Boolean);
        }
        if (ghs_classifications.length === 0) ghs_classifications = ["NON DG"];

        const drive_file_id = item.drive_file_id || "";
        const drive_view_url = item.drive_view_url || (drive_file_id ? `https://drive.google.com/file/d/${drive_file_id}/preview` : "");
        const drive_download_url = item.drive_download_url || (drive_file_id ? `https://drive.google.com/uc?export=download&id=${drive_file_id}` : "");

        const normalized = {
            id,
            product_code,
            category,
            chemical_name,
            usage,
            updated_date,
            cas_number,
            legal_flags: Array.isArray(item.legal_flags) ? item.legal_flags : [],
            supplier,
            ghs_classifications,
            ghs_16_sections: item.ghs_16_sections || item.composition || {},
            file_name: item.file_name || item.source_file || item.source_file_name || (product_code ? `MSDS-${product_code}.pdf` : ""),
            drive_file_id,
            drive_view_url,
            drive_download_url,
            last_synced_at: item.last_synced_at || new Date().toISOString(),

            // Backward compatibility aliases
            chem_id: id,
            chemical_id: id,
            product_name: chemical_name,
            product_name_vi: chemical_name,
            product_name_original: supplier || chemical_name,
            item_type: category === "Thành phẩm" ? "finished_product" : "raw_material",
            intended_use: usage,
            revision_date: updated_date,
            cas_primary: cas_number,
            cas_numbers: cas_number,
            manufacturer_supplier: supplier,
            manufacturer: supplier,
            ghs_codes: ghs_classifications,
            ghs_symbols: ghs_classifications.join(", "),
            source_file: item.file_name || item.source_file || (product_code ? `MSDS-${product_code}.pdf` : "")
        };
        return normalized;
    },

    async ping() {
        const url = this.getUrl();
        if (!url) return null;
        try {
            const resp = await fetch(`${url}?action=ping&t=${Date.now()}`);
            if (!resp.ok) return null;
            return await resp.json();
        } catch (e) {
            console.warn("GAS Ping failed:", e);
            return null;
        }
    },

    async fetchList() {
        const url = this.getUrl();
        if (!url) return null;
        try {
            const resp = await fetch(`${url}?action=list&t=${Date.now()}`);
            if (!resp.ok) return null;
            const data = await resp.json();
            if (data && data.folderUrl) {
                this.setFolderUrl(data.folderUrl);
            }
            return data;
        } catch (e) {
            console.warn("GAS FetchList failed:", e);
            return null;
        }
    },

    async postAction(payload) {
        const url = this.getUrl();
        if (!url) throw new Error("Chưa cấu hình Webhook URL của Google Apps Script.");
        payload.token = payload.token || this.getToken();

        const resp = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "text/plain;charset=utf-8" },
            body: JSON.stringify(payload)
        });
        if (!resp.ok) {
            throw new Error(`GAS HTTP error ${resp.status}`);
        }
        return await resp.json();
    },

    async upsertChemical(item, fileBase64, fileName, mimeType) {
        const normItem = this.normalizeItem(item);
        const payload = {
            token: this.getToken(),
            action: "upsert",
            item: normItem
        };
        if (fileBase64) {
            payload.fileBase64 = fileBase64;
            payload.fileName = fileName || normItem.file_name;
            payload.mimeType = mimeType || "application/pdf";
        }

        this.updateBadge("syncing", "Đang lưu lên Drive & Sheets...");
        try {
            const res = await this.postAction(payload);
            if (res && (res.status === "ok" || res.success)) {
                if (res.drive_view_url) normItem.drive_view_url = res.drive_view_url;
                if (res.drive_download_url) normItem.drive_download_url = res.drive_download_url;
                if (res.drive_file_id) normItem.drive_file_id = res.drive_file_id;
                if (res.version) this.setLocalVersion(res.version);
                this.updateBadge("synced", "Đã đồng bộ Drive");
                return { success: true, res, item: normItem };
            } else {
                throw new Error((res && res.error) || "Lỗi lưu dữ liệu GAS");
            }
        } catch (err) {
            console.warn("Lưu lên GAS thất bại, lưu vào hàng đợi outbox:", err);
            this.queueOutbox(payload);
            this.updateBadge("pending", "Chờ đồng bộ Drive");
            return { success: false, queued: true, item: normItem, error: err.message };
        }
    },

    async bulkSync(items) {
        if (!items || !items.length) return { success: true, count: 0 };
        const normList = items.map(it => this.normalizeItem(it));
        const payload = {
            token: this.getToken(),
            action: "bulk_sync",
            items: normList
        };

        this.updateBadge("syncing", "Đang đồng bộ hàng loạt lên Drive...");
        try {
            const res = await this.postAction(payload);
            if (res && (res.status === "ok" || res.success)) {
                if (res.version) this.setLocalVersion(res.version);
                this.updateBadge("synced", "Đã đồng bộ Drive");
                return { success: true, count: normList.length, res };
            } else {
                throw new Error((res && res.error) || "Lỗi bulk_sync");
            }
        } catch (err) {
            console.warn("Bulk sync thất bại, lưu hàng đợi outbox:", err);
            this.queueOutbox(payload);
            this.updateBadge("pending", "Chờ đồng bộ Drive");
            return { success: false, queued: true, count: normList.length, error: err.message };
        }
    },

    async deleteChemical(id, productCode, deleteDriveFile = true) {
        const payload = {
            token: this.getToken(),
            action: "delete",
            id: id || productCode,
            product_code: productCode || id,
            deleteDriveFile: deleteDriveFile !== false
        };

        this.updateBadge("syncing", "Đang xóa trên Drive...");
        try {
            const res = await this.postAction(payload);
            if (res && (res.status === "ok" || res.success)) {
                if (res.version) this.setLocalVersion(res.version);
                this.updateBadge("synced", "Đã đồng bộ Drive");
                return { success: true, res };
            } else {
                throw new Error((res && res.error) || "Lỗi xóa GAS");
            }
        } catch (err) {
            console.warn("Xóa trên GAS thất bại, lưu hàng đợi outbox:", err);
            this.queueOutbox(payload);
            this.updateBadge("pending", "Chờ đồng bộ Drive");
            return { success: false, queued: true, error: err.message };
        }
    },

    async flushOutbox() {
        const queue = this.getOutbox();
        if (!queue || queue.length === 0) {
            this.updateBadge("synced", "Đã đồng bộ Drive");
            return;
        }

        this.updateBadge("syncing", `Đang đẩy ${queue.length} tác vụ tồn đọng...`);
        const remaining = [];
        let successCount = 0;

        for (let i = 0; i < queue.length; i++) {
            const item = queue[i];
            try {
                const res = await this.postAction(item.payload);
                if (res && (res.status === "ok" || res.success)) {
                    if (res.version) this.setLocalVersion(res.version);
                    successCount++;
                } else {
                    remaining.push(item);
                }
            } catch (err) {
                remaining.push(item);
                for (let k = i + 1; k < queue.length; k++) {
                    remaining.push(queue[k]);
                }
                break;
            }
        }

        this.setOutbox(remaining);
        if (remaining.length === 0) {
            this.updateBadge("synced", "Đã đồng bộ Drive");
        } else {
            this.updateBadge("pending", `Chờ đồng bộ Drive (${remaining.length})`);
        }
        return { successCount, remainingCount: remaining.length };
    },

    async pullFromCloud(force = false) {
        const url = this.getUrl();
        if (!url) return false;

        this.updateBadge("syncing", "Đang kiểm tra Google Sheets...");
        try {
            await this.flushOutbox();

            const cloudRes = await this.fetchList();
            if (cloudRes && (cloudRes.status === "ok" || cloudRes.success)) {
                const rawData = Array.isArray(cloudRes.data) ? cloudRes.data : (Array.isArray(cloudRes.chemicals) ? cloudRes.chemicals : []);
                const cloudVersion = cloudRes.version || 1;
                const cloudCount = cloudRes.count || rawData.length;

                // AUTO-MIGRATION: If cloud has 0 rows but local cache has chemicals, migrate up!
                if (cloudCount === 0 && ALL_MSDS_CHEMICALS_CACHE && ALL_MSDS_CHEMICALS_CACHE.length > 0) {
                    console.log("Google Sheets đang trống, kích hoạt Auto-Migration tự động đẩy danh mục cục bộ lên đám mây...");
                    this.updateBadge("syncing", "Tự động di trú dữ liệu lên Google Sheets...");
                    await this.bulkSync(ALL_MSDS_CHEMICALS_CACHE);
                    this.updateBadge("synced", "Đã đồng bộ Drive");
                    return true;
                }

                if (cloudCount > 0 || force) {
                    const normalizedList = rawData.map(it => this.normalizeItem(it));
                    ALL_MSDS_CHEMICALS_CACHE = normalizedList;
                    try {
                        localStorage.setItem("luv_msds_cache", JSON.stringify(ALL_MSDS_CHEMICALS_CACHE));
                    } catch (_) {}
                    this.setLocalVersion(cloudVersion);
                    updateMsdsKpiStats(ALL_MSDS_CHEMICALS_CACHE);
                    const activeSearch = (document.getElementById("msds-search-input")?.value || "").trim();
                    renderMsdsFilteredTable(ALL_MSDS_CHEMICALS_CACHE, activeSearch);
                    this.updateBadge("synced", "Đã đồng bộ Drive");
                    return true;
                }
            }
            this.updateBadgeFromOutbox();
            return false;
        } catch (err) {
            console.warn("Lỗi khi kéo dữ liệu từ Google Sheets:", err);
            this.updateBadgeFromOutbox();
            return false;
        }
    },

    async checkHeartbeat() {
        const url = this.getUrl();
        if (!url) return;
        try {
            const pingRes = await this.ping();
            if (pingRes && pingRes.version) {
                const cloudVer = parseInt(pingRes.version, 10);
                const localVer = this.getLocalVersion();
                if (cloudVer > localVer) {
                    console.log(`Phát hiện phiên bản Cloud mới (${cloudVer} > ${localVer}), tự động đồng bộ về...`);
                    await this.pullFromCloud(true);
                }
            }
        } catch (_) {}
    }
};
window.MsdsGasSync = MsdsGasSync;

if (!window._msdsGasSyncIntervalStarted) {
    window._msdsGasSyncIntervalStarted = true;
    setInterval(() => {
        if (window.MsdsGasSync) window.MsdsGasSync.checkHeartbeat();
    }, 15000);

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden && window.MsdsGasSync) {
            window.MsdsGasSync.checkHeartbeat();
        }
    });

    window.addEventListener("online", () => {
        if (window.MsdsGasSync) window.MsdsGasSync.flushOutbox();
    });
}

async function refreshMsdsCatalogWithCloud() {
    if (window.MsdsGasSync) {
        await window.MsdsGasSync.flushOutbox();
        await window.MsdsGasSync.pullFromCloud(true);
    } else {
        await loadMsdsChemicalsList();
    }
}
window.refreshMsdsCatalogWithCloud = refreshMsdsCatalogWithCloud;

async function loadMsdsChemicalsList(query = "") {
    const tbody = document.getElementById("msds-table-body");
    if (!tbody) return;

    applyMsdsRbacVisibility();

    // 1. Instant Cache Retrieval (< 100ms)
    try {
        const cachedRaw = localStorage.getItem("luv_msds_cache");
        if (cachedRaw) {
            const cachedList = JSON.parse(cachedRaw);
            if (Array.isArray(cachedList) && cachedList.length > 0) {
                ALL_MSDS_CHEMICALS_CACHE = cachedList;
                updateMsdsKpiStats(ALL_MSDS_CHEMICALS_CACHE);
                const activeSearch = query || (document.getElementById("msds-search-input")?.value || "").trim();
                renderMsdsFilteredTable(ALL_MSDS_CHEMICALS_CACHE, activeSearch);
            }
        }
    } catch (_cacheErr) {
        console.warn("Lỗi đọc cache MSDS từ localStorage:", _cacheErr);
    }

    // 2. Fetch fresh live data: ưu tiên kéo dữ liệu đồng bộ hai chiều từ Google Sheets / Google Drive
    try {
        let syncedWithGas = false;
        if (window.MsdsGasSync && window.MsdsGasSync.getUrl()) {
            syncedWithGas = await window.MsdsGasSync.pullFromCloud(false);
        }

        if (!syncedWithGas) {
            const [respMsds] = await Promise.all([
                fetch("/api/msds/list"),
                preloadCilLegalMatches()
            ]);
            const res = await respMsds.json();

            if (respMsds.ok && res.success && Array.isArray(res.data) && res.data.length > 0) {
                ALL_MSDS_CHEMICALS_CACHE = res.data;
                try {
                    localStorage.setItem("luv_msds_cache", JSON.stringify(ALL_MSDS_CHEMICALS_CACHE));
                } catch (_saveErr) {}
                updateMsdsKpiStats(ALL_MSDS_CHEMICALS_CACHE);
                const activeSearch = query || (document.getElementById("msds-search-input")?.value || "").trim();
                renderMsdsFilteredTable(ALL_MSDS_CHEMICALS_CACHE, activeSearch);

                // Auto-Migration: nếu Google Sheets đang rỗng và GAS URL đã cấu hình, đẩy toàn bộ dữ liệu lên Sheets
                if (window.MsdsGasSync && window.MsdsGasSync.getUrl()) {
                    await window.MsdsGasSync.pullFromCloud(false);
                }
            } else if ((!res.data || res.data.length === 0) && ALL_MSDS_CHEMICALS_CACHE.length === 0) {
                // Fallback to static catalog if SQLite is temporarily empty
                const fallbackResp = await fetch("/api/msds/fallback-catalog");
                if (fallbackResp.ok) {
                    const fbJson = await fallbackResp.json();
                    const fbList = Array.isArray(fbJson) ? fbJson : (fbJson.data || []);
                    if (fbList.length > 0) {
                        ALL_MSDS_CHEMICALS_CACHE = fbList;
                        updateMsdsKpiStats(ALL_MSDS_CHEMICALS_CACHE);
                        renderMsdsFilteredTable(ALL_MSDS_CHEMICALS_CACHE, query);
                        if (window.MsdsGasSync && window.MsdsGasSync.getUrl()) {
                            await window.MsdsGasSync.bulkSync(ALL_MSDS_CHEMICALS_CACHE);
                        }
                    }
                }
            }
        }
    } catch (err) {
        console.warn("loadMsdsChemicalsList network warning (using cache):", err);
        if (ALL_MSDS_CHEMICALS_CACHE && ALL_MSDS_CHEMICALS_CACHE.length > 0) {
            const countBadge = document.getElementById("msds-showing-count");
            if (countBadge) {
                countBadge.title = "Đang hiển thị bản lưu ngoại tuyến (Offline cache)";
            }
        }
    }
}

function renderMsdsFilteredTable(sourceItems, searchQuery = "") {
    const tbody = document.getElementById("msds-table-body");
    const emptyNotice = document.getElementById("msds-table-empty");
    const showingCountEl = document.getElementById("msds-showing-count");
    if (!tbody) return;

    applyMsdsRbacVisibility();

    const cleanQ = (searchQuery || "").trim().toLowerCase();
    const unaccentQ = removeVietnameseTones(cleanQ);

    // Lọc theo GHS pill + Hết hạn > 3 năm + Item Type + Search text
    const filtered = (sourceItems || []).filter(item => {
        const rawGhs = String(item.ghs_symbols || "").trim().toUpperCase();
        const isNonDg = !rawGhs || rawGhs.includes("NON DG") || rawGhs.includes("NONDG") || rawGhs === "NONE";

        if (CURRENT_MSDS_GHS_FILTER === "NON DG" && !isNonDg) return false;
        if (CURRENT_MSDS_GHS_FILTER === "HAZARD" && isNonDg) return false;
        if (CURRENT_MSDS_GHS_FILTER === "EXPIRED_3Y") {
            const rev = String(item.revision_date || "");
            const m = rev.match(/\b(19\d\d|20\d\d)\b/);
            const curYear = new Date().getFullYear();
            if (m && (curYear - parseInt(m[1]) < 3)) {
                return false;
            }
        } else if (CURRENT_MSDS_GHS_FILTER.startsWith("GHS") && !rawGhs.includes(CURRENT_MSDS_GHS_FILTER)) {
            return false;
        }

        // Lọc theo item_type
        if (CURRENT_MSDS_ITEM_TYPE_FILTER !== "all") {
            const rawType = String(item.item_type || "raw_material").trim().toLowerCase();
            if (rawType !== CURRENT_MSDS_ITEM_TYPE_FILTER.toLowerCase()) {
                return false;
            }
        }

        if (!cleanQ) return true;

        const rawHaystack = [
            item.product_code,
            item.chem_id,
            item.product_name,
            item.product_name_vi,
            item.product_name_original,
            item.cas_numbers,
            item.cas_primary,
            item.un_no,
            item.manufacturer_supplier,
            item.manufacturer,
            item.intended_use,
            item.ghs_symbols,
            item.hazard_statements,
            item.source_file,
            item.item_type,
            item.mother_msds_id
        ].map(v => String(v || "").toLowerCase()).join(" ");

        if (rawHaystack.includes(cleanQ)) return true;
        const unaccentHaystack = removeVietnameseTones(rawHaystack);
        return unaccentHaystack.includes(unaccentQ);
    });

    CURRENT_FILTERED_MSDS = filtered;
    if (showingCountEl) {
        showingCountEl.textContent = `Hiển thị ${filtered.length} / ${(sourceItems || []).length} hóa chất`;
    }

    // Pagination logic
    if (typeof window.CURRENT_MSDS_PAGE === "undefined") {
        window.CURRENT_MSDS_PAGE = 1;
        window.CURRENT_MSDS_PAGE_SIZE = "20";
    }

    const totalRecords = filtered.length;
    const isAll = String(window.CURRENT_MSDS_PAGE_SIZE).toLowerCase() === "all";
    const pageSize = isAll ? Math.max(1, totalRecords) : (parseInt(window.CURRENT_MSDS_PAGE_SIZE) || 20);
    const totalPages = Math.max(1, Math.ceil(totalRecords / pageSize));

    if (window.CURRENT_MSDS_PAGE > totalPages) window.CURRENT_MSDS_PAGE = totalPages;
    if (window.CURRENT_MSDS_PAGE < 1) window.CURRENT_MSDS_PAGE = 1;

    const startIdx = isAll ? 0 : (window.CURRENT_MSDS_PAGE - 1) * pageSize;
    const endIdx = isAll ? totalRecords : Math.min(startIdx + pageSize, totalRecords);
    const pagedItems = filtered.slice(startIdx, endIdx);

    // Update Pagination HUD elements if present
    const pageInfoEl = document.getElementById("msds-pagination-info");
    const pageDisplayEl = document.getElementById("msds-page-current-display");
    const prevBtn = document.getElementById("msds-page-prev-btn");
    const nextBtn = document.getElementById("msds-page-next-btn");

    if (pageInfoEl) {
        if (totalRecords === 0) {
            pageInfoEl.textContent = "Không có hóa chất nào";
        } else {
            pageInfoEl.textContent = `Hiển thị ${startIdx + 1} - ${endIdx} trên tổng số ${totalRecords} hóa chất`;
        }
    }
    if (pageDisplayEl) {
        pageDisplayEl.textContent = `Trang ${window.CURRENT_MSDS_PAGE} / ${totalPages}`;
    }
    if (prevBtn) prevBtn.disabled = window.CURRENT_MSDS_PAGE <= 1;
    if (nextBtn) nextBtn.disabled = window.CURRENT_MSDS_PAGE >= totalPages;

    if (filtered.length === 0) {
        tbody.innerHTML = "";
        if (emptyNotice) {
            emptyNotice.classList.remove("hidden");
        }
        updateMsdsBatchActionBar();
        return;
    }

    if (emptyNotice) emptyNotice.classList.add("hidden");

    let html = "";
    pagedItems.forEach((item, localIdx) => {
        const index = startIdx + localIdx;
        const rawGhs = String(item.ghs_symbols || "").trim();
        let ghsCodes = rawGhs.split(/[,;]+/).map(s => s.trim()).filter(Boolean);
        if (ghsCodes.length === 0 || rawGhs.toUpperCase().includes("NON DG")) {
            ghsCodes = ["NON DG"];
        }
        const ghsBadges = ghsCodes.map(c => renderGhsTableBadge(c)).join("");

        // Render CAS badge và Legal Badges tương ứng
        let casBadge = "";
        if (item.cas_numbers) {
            casBadge = `<span class="msds-cas-pill">${escapeHtml(item.cas_numbers)}</span>`;
        } else {
            casBadge = `<span class="msds-cas-mix">Hỗn hợp</span>`;
        }

        // Lấy danh sách huy hiệu pháp lý
        const legalBadgesList = getChemicalLegalBadges(item);
        const legalBadgesHtml = renderLegalBadgesHtml(legalBadgesList);

        const displayCode = item.product_code || item.chem_id || "";
        const safeChemId = escapeHtml(item.chem_id || displayCode);
        const supplierName = item.manufacturer_supplier || item.manufacturer || "Chưa cập nhật";
        
        // Item type badge & Mother MSDS indicator
        const isFinished = (item.item_type || "").toLowerCase() === "finished_product";
        const itemTypeBadge = isFinished
            ? `<span class="msds-type-badge type-finished" title="Thành phẩm pha chế / hỗn hợp đa thành phần">🏷️ Thành phẩm</span>`
            : `<span class="msds-type-badge type-raw" title="Nguyên liệu đơn chất thuần túy">🧪 Nguyên liệu</span>`;

        const motherBadge = item.mother_msds_id
            ? `<span class="msds-mother-badge" title="Sản phẩm liên kết Mother MSDS: ${escapeHtml(item.mother_msds_id)}">🔗 Mother: <b>${escapeHtml(item.mother_msds_id)}</b></span>`
            : "";

        let isExpired = false;
        if (item.revision_date) {
            const yMatch = String(item.revision_date).match(/\b(19\d\d|20\d\d)\b/);
            if (yMatch) {
                const docY = parseInt(yMatch[1], 10);
                if (new Date().getFullYear() - docY >= 3) {
                    isExpired = true;
                }
            }
        }
        const expiredBadge = isExpired
            ? `<span class="msds-badge-expired" style="background:#fff7ed; color:#c2410c; border:1px solid #fdba74; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:700; margin-left:6px; display:inline-block;" title="MSDS đã ban hành quá 3 năm, cần cập nhật!">⏳ Quá hạn (> 3 năm)</span>`
            : "";

        const subInfoParts = [];
        if (item.product_code && item.product_code !== item.chem_id) {
            subInfoParts.push(`Mã SP: <b>${escapeHtml(item.product_code)}</b>`);
        }
        if (item.intended_use) subInfoParts.push(escapeHtml(item.intended_use));
        if (item.revision_date) subInfoParts.push("Cập nhật: " + escapeHtml(item.revision_date));
        const subInfoHtml = subInfoParts.length > 0 ? subInfoParts.join(" · ") : "Hóa chất công nghiệp";

        const srcFileName = item.file_name || item.source_file || `MSDS-${displayCode}.docx`;
        const driveDownloadUrl = item.drive_download_url || (item.drive_file_id ? `https://drive.google.com/uc?export=download&id=${item.drive_file_id}` : "");
        const driveViewUrl = item.drive_view_url || (item.drive_file_id ? `https://drive.google.com/file/d/${item.drive_file_id}/preview` : "");
        const downloadOriginalUrl = driveDownloadUrl || `/api/msds/download-original/${encodeURIComponent(item.chem_id || displayCode)}`;
        const exportWordDocxUrl = `/api/msds/export-safety-card/${encodeURIComponent(item.chem_id || displayCode)}`;
        const isSelected = SELECTED_MSDS_IDS.has(safeChemId);
        const driveFileId = item.drive_file_id || "";
        const viewAction = driveViewUrl 
            ? `window.open('${escapeHtml(driveViewUrl)}', '_blank')`
            : `openMsdsDriveViewer('${safeChemId}', '${escapeHtml(driveFileId)}', '${escapeHtml(srcFileName)}')`;

        html += `
            <tr class="msds-table-row ${isSelected ? 'row-selected' : ''}" ondblclick="openMsdsSafetyModal('${safeChemId}')">
                <td class="msds-col-check">
                    <input type="checkbox" class="msds-row-checkbox" value="${safeChemId}" ${isSelected ? 'checked' : ''} onchange="onMsdsRowCheckboxChange(event, '${safeChemId}')" />
                </td>
                <td class="msds-col-stt">${index + 1}</td>
                <td class="msds-col-code">
                    <div class="msds-code-cell">
                        <span class="msds-code-badge" onclick="openMsdsSafetyModal('${safeChemId}')" title="Bấm để xem Thẻ An Toàn Khẩn Cấp">${escapeHtml(displayCode)}</span>
                        <div class="msds-code-sub-badges">
                            ${itemTypeBadge}
                            ${motherBadge}
                        </div>
                    </div>
                </td>
                <td class="msds-col-name">
                    <div class="msds-chem-title" onclick="openMsdsSafetyModal('${safeChemId}')">${escapeHtml(item.product_name || "N/A")}${expiredBadge}</div>
                    <div class="msds-chem-meta">${subInfoHtml}</div>
                </td>
                <td class="msds-col-cas">
                    <div class="msds-cas-cell-wrap">
                        <div class="msds-cas-main-row">${casBadge}</div>
                        ${legalBadgesHtml ? `<div class="msds-legal-badges-wrap">${legalBadgesHtml}</div>` : ""}
                    </div>
                </td>
                <td class="msds-col-supplier">${escapeHtml(supplierName)}</td>
                <td class="msds-col-ghs">
                    <div class="msds-ghs-wrap">${ghsBadges}</div>
                </td>
                <td class="msds-col-file">
                    <div style="display:flex; gap:4px; align-items:center; flex-wrap:wrap;">
                        <a href="${downloadOriginalUrl}" target="_blank" download class="msds-dl-file-btn" title="Tải tệp MSDS gốc: ${escapeHtml(srcFileName)}">
                            <span>📥 Tải MSDS Gốc</span>
                        </a>
                        <button type="button" class="msds-btn-preview-file" onclick="${viewAction}" title="Xem nhanh tệp MSDS gốc trực tiếp (Google Drive Preview)" style="display:inline-flex; align-items:center; gap:4px; padding:3px 7px; font-size:11px; font-weight:600; color:#1e40af; background:#eff6ff; border:1px solid #bfdbfe; border-radius:4px; cursor:pointer;">
                            <span>👁️ Xem File Gốc</span>
                        </button>
                    </div>
                    <div class="msds-file-caption" title="${escapeHtml(srcFileName)}">${escapeHtml(srcFileName)}</div>
                </td>
                <td class="msds-col-actions">
                    <div class="msds-action-group">
                        <button type="button" class="msds-btn-view-card" onclick="openMsdsSafetyModal('${safeChemId}')" title="Xem Thẻ An Toàn Hóa Chất Khẩn Cấp">
                            <span>👁️ Thẻ An Toàn</span>
                        </button>
                        <button type="button" class="msds-btn-qr-row" onclick="openMsdsQrModal('${safeChemId}')" title="Mã QR tra cứu khẩn cấp & in tem">
                            <span>📱 QR</span>
                        </button>
                        <button type="button" class="msds-btn-label-row" onclick="openMsdsLabelModal('${safeChemId}')" title="Tạo & In Nhãn Phụ GHS Chiết Rót (Thông Tư 01/2026/TT-BCT)">
                            <span>🏷️ In Nhãn GHS</span>
                        </button>
                        <a href="${exportWordDocxUrl}" download="SafetyCard_${escapeHtml(displayCode)}.docx" class="msds-btn-export-docx" title="Xuất Thẻ An Toàn Word (.docx) chuẩn Mục 3 GHS có Checksum">
                            <span>📄 Xuất Word</span>
                        </a>
                        <button type="button" class="msds-btn-matrix-row" onclick="openStorageMatrixModal('${safeChemId}')" title="Kiểm tra tương thích lưu kho hóa chất này (TCVN 5507:2002)">
                            <span>🧭 Kho</span>
                        </button>
                        ${isGuestUser() ? '' : `
                        <button type="button" class="msds-btn-del-row" onclick="deleteMsdsChemical('${safeChemId}')" title="Xóa hóa chất này khỏi sổ CIL">
                            🗑️
                        </button>
                        `}
                    </div>
                </td>
            </tr>
        `;
    });
    tbody.innerHTML = html;
    updateMsdsBatchActionBar();

    // Đồng thời kết xuất Chế độ Thẻ Lưới (Grid Card View)
    renderMsdsCardGrid(pagedItems, filtered.length, startIdx);
}

function handleMsdsSearch(val) {
    const clearBtn = document.getElementById("msds-search-clear");
    if (clearBtn) {
        clearBtn.classList.toggle("hidden", !val || !val.trim());
    }
    if (msdsSearchTimer) clearTimeout(msdsSearchTimer);
    msdsSearchTimer = setTimeout(() => {
        renderMsdsFilteredTable(ALL_MSDS_CHEMICALS_CACHE, val ? val.trim() : "");
    }, 120);
}

async function openMsdsSafetyModal(chemId) {
    const modal = document.getElementById("msds-safety-modal");
    const cardTitle = document.getElementById("modal-card-title");
    const cardSub = document.getElementById("modal-card-subtitle");
    const cardBody = document.getElementById("modal-card-body");
    const btnDownloadWord = document.getElementById("modal-btn-download-word");
    const btnDownloadOriginal = document.getElementById("modal-btn-download-original");

    if (!modal) return;
    modal.classList.remove("hidden");

    if (cardBody) {
        cardBody.innerHTML = `
            <div style="text-align:center; padding:40px;">
                <div class="spinner"></div>
                <div style="margin-top:12px; font-size:14px; color:#475569;">Đang trích xuất dữ liệu Thẻ An Toàn & Đối soát Pháp luật Hóa chất...</div>
            </div>
        `;
    }

    try {
        const resp = await fetch(`/api/msds/detail/${encodeURIComponent(chemId)}`);
        const res = await resp.json();
        if (!resp.ok || !res.success) {
            throw new Error(res.error || "Không thể lấy thông tin chi tiết hóa chất.");
        }

        const data = res.data;
        const chem = data.chemical || {};
        const comps = data.compositions || [];
        const sec = data.sections || {};
        const legal = data.legal_compliance || {};

        const codeDisplay = chem.product_code || chem.chem_id || chemId;
        const supplierDisplay = chem.manufacturer_supplier || chem.manufacturer || "Theo hồ sơ MSDS";
        const itemTypeLabel = chem.item_type === "finished_product" ? "Thành phẩm" : "Nguyên liệu";
        const motherInfo = chem.mother_msds_id ? ` | Mother MSDS: ${chem.mother_msds_id}` : "";

        if (cardTitle) cardTitle.innerText = `THẺ AN TOÀN KHẨN CẤP: ${codeDisplay} — ${(chem.product_name || "HÓA CHẤT").toUpperCase()}`;
        if (cardSub) cardSub.innerText = `Mã SP: ${codeDisplay} | Phân loại: [${itemTypeLabel}]${motherInfo} | Nhà cung cấp: ${supplierDisplay} | Ngày sửa đổi: ${chem.revision_date || "N/A"}`;
        
        // Cấu hình nút xuất Thẻ An Toàn Word (.docx) chuẩn Mục 3 GHS có Checksum
        if (btnDownloadWord) {
            btnDownloadWord.href = `/api/msds/export-safety-card/${encodeURIComponent(chem.chem_id || codeDisplay)}`;
            btnDownloadWord.download = `SafetyCard_${codeDisplay}.docx`;
            btnDownloadWord.title = "Tải Thẻ An Toàn Word (.docx) chuẩn 4 cột Mục 3 GHS và Thẩm Định Checksum";
        }
        window.CURRENT_SAFETY_MODAL_CHEM = chem;
        window.CURRENT_SAFETY_MODAL_CHEM_ID = chem.chem_id || codeDisplay;
        const driveDownloadUrl = chem.drive_download_url || (chem.drive_file_id ? `https://drive.google.com/uc?export=download&id=${chem.drive_file_id}` : "");
        if (btnDownloadOriginal) {
            btnDownloadOriginal.href = driveDownloadUrl || `/api/msds/download-original/${encodeURIComponent(chem.chem_id || codeDisplay)}`;
            btnDownloadOriginal.download = chem.source_file || `MSDS-${codeDisplay}`;
        }

        // 1. Render Compositions table (Mục 3 GHS 4 cột chuẩn Checksum)
        let compRows = "";
        if (comps.length > 0) {
            for (const c of comps) {
                const isValid = c.checksum_valid !== false && (c.validation_status === "VALID" || c.checksum_status === "HỢP LỆ");
                const statusColor = isValid ? "#16a34a" : (c.cas_number ? "#ea580c" : "#64748b");
                const statusLabelVi = c.checksum_status || (isValid ? "✓ HỢP LỆ" : (c.cas_number ? "⚠ SAI CHECKSUM" : "KHÔNG CÓ CAS"));
                
                // Badges pháp lý thành phần nếu có
                let compLegalTagsHtml = "";
                if (c.legal_badges && c.legal_badges.length > 0) {
                    compLegalTagsHtml = `<div style="display:flex; gap:3px; flex-wrap:wrap; margin-top:3px;">` +
                        c.legal_badges.map(b => `<span style="font-size:9.5px; padding:1px 5px; border-radius:3px; font-weight:700; background:#fff1f2; color:#e11d48; border:1px solid #fecdd3;">${escapeHtml(b)}</span>`).join("") +
                        `</div>`;
                }

                compRows += `
                    <tr style="border-bottom:1px solid #e2e8f0;">
                        <td style="padding:8px 10px; font-weight:500;">
                            <div>${escapeHtml(c.component_name || "")}</div>
                            ${compLegalTagsHtml}
                        </td>
                        <td style="padding:8px 10px; font-family:monospace; font-weight:700; color:#0F5C78;">${escapeHtml(c.cas_number || "Bí mật thương mại")}</td>
                        <td style="padding:8px 10px; text-align:center; font-weight:600;">${escapeHtml(c.percentage || "Xem MSDS")}</td>
                        <td style="padding:8px 10px; text-align:center;">
                            <span style="font-size:10.5px; font-weight:700; color:${statusColor}; background:#f8fafc; border:1px solid #cbd5e1; padding:2px 7px; border-radius:4px;">
                                ${escapeHtml(statusLabelVi)}
                            </span>
                        </td>
                    </tr>
                `;
            }
        } else {
            compRows = `<tr><td colspan="4" style="padding:12px; text-align:center; color:#94a3b8;">Không có thông tin thành phần chi tiết.</td></tr>`;
        }

        // 2. Render Khối Bảng Nghĩa Vụ Pháp Lý & Tuân Thủ (Luật Hóa Chất 2026)
        let legalComplianceHtml = "";
        const isRegulated = legal.is_regulated || (legal.obligations && legal.obligations.length > 0);

        if (isRegulated && legal.obligations && legal.obligations.length > 0) {
            let obligationRows = "";
            legal.obligations.forEach((ob, idx) => {
                const sourceBadge = (ob.source_id === "ND26" || ob.source_id === "ND28")
                    ? `<span style="font-size:10.5px; font-weight:800; background:#fff7ed; color:#ea580c; border:1px solid #fed7aa; padding:2px 6px; border-radius:4px;">NĐ 26/2026/NĐ-CP</span>`
                    : (ob.source_id === "QCVN01"
                        ? `<span style="font-size:10.5px; font-weight:800; background:#f0fdf4; color:#16a34a; border:1px solid #bbf7d0; padding:2px 6px; border-radius:4px;">QCVN 01:2025/BYT</span>`
                        : `<span style="font-size:10.5px; font-weight:800; background:#f0f9ff; color:#0284c7; border:1px solid #bae6fd; padding:2px 6px; border-radius:4px;">NĐ 24/2026/NĐ-CP</span>`);

                const tierBadge = ob.badge?.label
                    ? `<div style="margin-top:3px;"><span style="font-size:10px; font-weight:700; color:${ob.badge.color || '#b91c1c'}; background:${ob.badge.bg || '#fef2f2'}; padding:1px 5px; border-radius:3px; border:1px solid rgba(0,0,0,0.1);">${escapeHtml(ob.badge.label)}</span></div>`
                    : "";

                const thresholdTxt = ob.threshold ? `${escapeHtml(ob.threshold)}` : "Theo quy định hiện hành";

                obligationRows += `
                    <tr style="border-bottom:1px solid #e2e8f0; font-size:12px; vertical-align:top;">
                        <td style="padding:9px 10px; font-weight:700; color:#1e293b;">
                            ${idx + 1}. ${sourceBadge}
                            ${tierBadge}
                        </td>
                        <td style="padding:9px 10px; color:#334155;">
                            <b>${escapeHtml(ob.section_title || ob.section_id || "")}</b>
                        </td>
                        <td style="padding:9px 10px; text-align:center; color:#0f172a; font-weight:600; font-family:monospace;">
                            ${thresholdTxt}
                        </td>
                        <td style="padding:9px 10px; color:#1e293b; line-height:1.45;">
                            ${escapeHtml(ob.obligation || "Tuân thủ quy chế an toàn hóa chất hiện hành.")}
                        </td>
                    </tr>
                `;
            });

            legalComplianceHtml = `
                <div style="margin-top:16px; margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; flex-wrap:wrap; gap:6px;">
                        <div style="font-weight:800; color:#0f172a; font-size:13.5px; display:flex; align-items:center; gap:6px;">
                            <span>⚖️ BẢNG NGHĨA VỤ PHÁP LÝ & TUÂN THỦ (LUẬT HÓA CHẤT SỐ 69/2025/QH15)</span>
                            <span style="font-size:11px; font-weight:800; background:#fef2f2; color:#b91c1c; border:1px solid #fecdd3; padding:2px 7px; border-radius:4px;">
                                ${legal.total_regulated_components || legal.obligations.length} HOẠT CHẤT ĐƯỢC ĐIỀU CHỈNH
                            </span>
                        </div>
                        <div style="font-size:11px; color:#64748b;">Căn cứ Luật 69 · NĐ 24/2026/NĐ-CP · NĐ 25/2026/NĐ-CP · NĐ 26/2026/NĐ-CP · TT 01/2026 · TT 02/2026 · QCVN 01</div>
                    </div>
                    <div style="border:1px solid #cbd5e1; border-radius:6px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                        <table style="width:100%; border-collapse:collapse; font-size:12px; text-align:left;">
                            <thead style="background:#1e293b; color:#f8fafc;">
                                <tr>
                                    <th style="padding:8px 10px; width:22%;">Quy Chuẩn / Văn Bản Luật</th>
                                    <th style="padding:8px 10px; width:25%;">Điều Khoản Quy Định</th>
                                    <th style="padding:8px 10px; width:15%; text-align:center;">Ngưỡng Áp Dụng</th>
                                    <th style="padding:8px 10px; width:38%;">Nghĩa Vụ Bắt Buộc (Giấy phép, Sổ, Báo cáo, Sự cố)</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${obligationRows}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        } else {
            legalComplianceHtml = `
                <div style="margin-top:16px; margin-bottom:8px; background:#f0fdf4; border:1px solid #bbf7d0; border-radius:6px; padding:12px 16px; display:flex; align-items:center; gap:12px;">
                    <div style="font-size:24px;">🛡️</div>
                    <div>
                        <div style="font-weight:700; color:#166534; font-size:13px;">HÓA CHẤT AN TOÀN / KHÔNG THUỘC DANH MỤC KIỂM SOÁT ĐẶC BIỆT</div>
                        <div style="font-size:12px; color:#15803d; margin-top:2px; line-height:1.4;">
                            Sản phẩm không chứa hoạt chất thuộc diện Cấm, Hạn chế, Tiền chất ma túy (NĐ 26/2026/NĐ-CP) hay Kiểm soát đặc biệt (NĐ 24/2026/NĐ-CP). Doanh nghiệp áp dụng quy trình an toàn lao động và lập sổ lưu trữ hóa chất theo Luật Hóa chất 69/2025/QH15.
                        </div>
                    </div>
                </div>
            `;
        }

        const isNonDg = String(chem.ghs_symbols || "").toUpperCase().includes("NON DG") || String(chem.signal_word || "").toUpperCase().includes("NON DG");
        const signalVi = isNonDg
            ? "NON DG (KHÔNG NGUY HẠI)"
            : ((chem.signal_word || "").toLowerCase().includes("danger") || (chem.signal_word || "").toLowerCase().includes("nguy hiểm")
                ? "NGUY HIỂM (DANGER)"
                : "CẢNH BÁO (WARNING)");
        const sec2BoxBg = isNonDg ? "#f0fdf4" : "#fff1f2";
        const sec2BorderColor = isNonDg ? "#16a34a" : "#e11d48";
        const sec2TitleColor = isNonDg ? "#15803d" : "#9f1239";
        const sec2InnerBorder = isNonDg ? "#bbf7d0" : "#fecdd3";

        // Render modal body with high-fidelity Vietnamese safety card + Visual GHS Diamonds + Legal Compliance Table
        cardBody.innerHTML = `
            <div style="font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                <!-- Section: General & Identifiers -->
                <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px 16px; margin-bottom:16px;">
                    <div>
                        <div style="font-size:11px; color:#64748b; font-weight:600; text-transform:uppercase;">Mã Sản Phẩm / MSDS</div>
                        <div style="font-size:14px; font-weight:800; color:#0F5C78; font-family:monospace; margin-top:2px;">${escapeHtml(codeDisplay)}</div>
                    </div>
                    <div>
                        <div style="font-size:11px; color:#64748b; font-weight:600; text-transform:uppercase;">Phân Loại & Mother MSDS</div>
                        <div style="font-size:13px; font-weight:700; color:#0f172a; margin-top:2px;">
                            ${itemTypeLabel} ${chem.mother_msds_id ? `<span style="font-size:11px; color:#0284c7;">(Mother: ${escapeHtml(chem.mother_msds_id)})</span>` : ''}
                        </div>
                    </div>
                    <div>
                        <div style="font-size:11px; color:#64748b; font-weight:600; text-transform:uppercase;">Số CAS Chính</div>
                        <div style="font-size:14px; font-weight:700; color:#0F5C78; font-family:monospace; margin-top:2px;">${escapeHtml(chem.cas_numbers || "Hỗn hợp")}</div>
                    </div>
                    <div>
                        <div style="font-size:11px; color:#64748b; font-weight:600; text-transform:uppercase;">Ngoại Quan & Điểm Chớp Cháy</div>
                        <div style="font-size:13px; font-weight:600; color:#334155; margin-top:2px;">${escapeHtml(chem.physical_state || chem.appearance || "Chất lỏng")} · <span style="color:#b91c1c; font-weight:700;">${escapeHtml(chem.flash_point || "K/XĐ")}</span></div>
                    </div>
                </div>

                <!-- Section: Hazard & Warning with GHS Diamonds -->
                <div style="background:${sec2BoxBg}; border-left:4px solid ${sec2BorderColor}; border-radius:0 8px 8px 0; padding:14px 16px; margin-bottom:16px;">
                    <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px;">
                        <div style="font-weight:800; color:${sec2TitleColor}; font-size:13.5px; text-transform:uppercase;">
                            ${isNonDg ? "✅" : "⚠️"} NHẬN DẠNG MỐI NGUY HIỂM GHS (PHẦN 2) — PHÂN LOẠI: ${escapeHtml(signalVi)}
                        </div>
                    </div>
                    ${renderGhsSafetyCardGallery(chem.ghs_symbols)}
                    <div style="font-size:13px; color:#1e293b; margin-top:10px; line-height:1.55; background:rgba(255,255,255,0.65); padding:8px 12px; border-radius:6px; border:1px solid ${sec2InnerBorder};">
                        <b>Cảnh báo nguy cơ (Phần 2):</b> ${escapeHtml(sec.sec_02_hazards || "Tuân thủ quy trình an toàn hóa chất khi tiếp xúc.")}
                    </div>
                </div>

                <!-- Section: First Aid Measures (4 STEPS) -->
                <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:14px 16px; margin-bottom:16px;">
                    <div style="font-weight:700; color:#166534; font-size:14px; display:flex; align-items:center; gap:6px; margin-bottom:10px;">
                        <span>🚑 4 BƯỚC SƠ CỨU KHẨN CẤP (MỤC 4 GHS — TIẾNG VIỆT)</span>
                    </div>
                    <div style="font-size:13px; color:#1e293b; line-height:1.65; white-space:pre-line;">${escapeHtml(sec.sec_04_first_aid)}</div>
                </div>

                <!-- Section: PPE (MỤC 8 GHS) -->
                <div style="background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px; padding:14px 16px; margin-bottom:16px;">
                    <div style="font-weight:700; color:#1e40af; font-size:14px; margin-bottom:8px;">
                        🛡️ TRANG BỊ BẢO HỘ CÁ NHÂN BẮT BUỘC (PPE - MỤC 8 GHS)
                    </div>
                    <div style="font-size:13px; color:#1e293b; line-height:1.65; white-space:pre-line;">${escapeHtml(sec.sec_08_ppe)}</div>
                </div>

                <!-- Section: Storage & Handling (MỤC 5 & 7 GHS) -->
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:14px 16px; margin-bottom:16px;">
                    <div style="font-weight:700; color:#334155; font-size:14px; margin-bottom:8px;">
                        📦 ĐIỀU KIỆN LƯU TRỮ, BẢO QUẢN & PCCC (MỤC 5 & MỤC 7 GHS)
                    </div>
                    <div style="font-size:13px; color:#334155; line-height:1.6;">
                        <div><b>• Bảo quản & Lưu kho:</b> ${escapeHtml(sec.sec_07_handling)}</div>
                        <div style="margin-top:4px;"><b>• Biện pháp chữa cháy:</b> ${escapeHtml(chem.fire_measures || "Sử dụng bình bột khô, bọt chữa cháy hoặc khí CO2. Không phun tia nước trực tiếp.")}</div>
                    </div>
                </div>

                <!-- Section: Chemical Composition Table (MỤC 3 GHS 4 CỘT) -->
                <div style="margin-bottom:8px;">
                    <div style="font-weight:700; color:#0f172a; font-size:13px; margin-bottom:6px;">
                        🧪 BẢNG THÀNH PHẦN HÓA HỌC & SỐ CAS (MỤC 3 GHS)
                    </div>
                    <div style="border:1px solid #e2e8f0; border-radius:6px; overflow:hidden;">
                        <table style="width:100%; border-collapse:collapse; font-size:12px; text-align:left;">
                            <thead style="background:#f1f5f9; color:#475569;">
                                <tr>
                                    <th style="padding:7px 10px;">Tên Thành Phần Hoạt Chất</th>
                                    <th style="padding:7px 10px;">Số CAS</th>
                                    <th style="padding:7px 10px; text-align:center;">Hàm Lượng (%)</th>
                                    <th style="padding:7px 10px; text-align:center;">Thẩm Định Checksum</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${compRows}
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- INJECT: BẢNG NGHĨA VỤ PHÁP LÝ & TUÂN THỦ (LUẬT HÓA CHẤT 2026) -->
                ${legalComplianceHtml}
            </div>
        `;
    } catch (err) {
        if (cardBody) {
            cardBody.innerHTML = `
                <div style="padding:30px; text-align:center; color:#ef4444;">
                    <div style="font-size:16px; font-weight:700;">Không thể tải dữ liệu Thẻ An Toàn</div>
                    <div style="margin-top:6px; font-size:13px;">${escapeHtml(err.message)}</div>
                </div>
            `;
        }
    }
}

function closeMsdsSafetyModal() {
    const modal = document.getElementById("msds-safety-modal");
    if (modal) modal.classList.add("hidden");
}

async function deleteMsdsChemical(chemId) {
    if (isGuestUser()) {
        alert("Khách (Guest) không có quyền xóa hóa chất.");
        return;
    }
    if (!confirm(`Bạn có chắc chắn muốn xóa mã hóa chất "${chemId}" khỏi Danh mục Hóa chất CIL?\n\n⚠️ Lưu ý: Thao tác này sẽ xóa vĩnh viễn trên cả máy chủ và Google Sheet (chống phục hồi lại khi server khởi động lại).`)) {
        return;
    }

    try {
        const token = sessionStorage.getItem("luv_auth_token") || localStorage.getItem("luv_auth_token") || "verified";
        const role = sessionStorage.getItem("luv_user_role") || "owner";
        const resp = await fetch(`/api/msds/delete/${encodeURIComponent(chemId)}`, {
            method: "DELETE",
            headers: {
                "X-Titan-Session": token,
                "X-Titan-Role": role,
                "Authorization": "Bearer " + token
            }
        });
        const res = await resp.json();
        if (!resp.ok || !res.success) {
            throw new Error(res.error || "Không thể xóa hóa chất.");
        }
        SELECTED_MSDS_IDS.delete(chemId);

        // Xóa trên Google Apps Script / Google Drive
        if (window.MsdsGasSync && window.MsdsGasSync.getUrl()) {
            try {
                await window.MsdsGasSync.deleteChemical(chemId, chemId, true);
            } catch (gDelErr) {
                console.warn("GAS deleteChemical warning:", gDelErr);
            }
        }

        // Cập nhật bộ nhớ đệm cục bộ
        ALL_MSDS_CHEMICALS_CACHE = (ALL_MSDS_CHEMICALS_CACHE || []).filter(c => (c.id !== chemId && c.product_code !== chemId && c.chem_id !== chemId));
        try {
            localStorage.setItem("luv_msds_cache", JSON.stringify(ALL_MSDS_CHEMICALS_CACHE));
        } catch (_) {}
        updateMsdsKpiStats(ALL_MSDS_CHEMICALS_CACHE);
        renderMsdsFilteredTable(ALL_MSDS_CHEMICALS_CACHE);
        await loadMsdsChemicalsList();
    } catch (err) {
        alert("Lỗi xóa hóa chất: " + err.message);
    }
}

// -------------------------------------------------------------
// CHỨC NĂNG CHỌN NHIỀU ĐỂ XÓA (BATCH DELETE) & XÓA TẤT CẢ (DELETE ALL)
// -------------------------------------------------------------

function toggleSelectAllMsds(checked) {
    if (!CURRENT_FILTERED_MSDS || CURRENT_FILTERED_MSDS.length === 0) return;
    CURRENT_FILTERED_MSDS.forEach(item => {
        const id = String(item.chem_id || item.product_code || "");
        if (!id) return;
        if (checked) {
            SELECTED_MSDS_IDS.add(id);
        } else {
            SELECTED_MSDS_IDS.delete(id);
        }
    });

    const rowBoxes = document.querySelectorAll(".msds-row-checkbox");
    rowBoxes.forEach(box => {
        box.checked = checked;
        const row = box.closest("tr");
        if (row) row.classList.toggle("row-selected", checked);
    });

    updateMsdsBatchActionBar();
}
window.toggleSelectAllMsds = toggleSelectAllMsds;

function toggleSelectAllFiltered(select) {
    toggleSelectAllMsds(select);
}
window.toggleSelectAllFiltered = toggleSelectAllFiltered;

function onMsdsRowCheckboxChange(event, chemId) {
    if (!chemId) return;
    const isChecked = event ? event.target.checked : false;
    if (isChecked) {
        SELECTED_MSDS_IDS.add(chemId);
    } else {
        SELECTED_MSDS_IDS.delete(chemId);
    }

    const row = event && event.target ? event.target.closest("tr") : null;
    if (row) row.classList.toggle("row-selected", isChecked);

    updateMsdsBatchActionBar();
}
window.onMsdsRowCheckboxChange = onMsdsRowCheckboxChange;

function updateMsdsBatchActionBar() {
    const bar = document.getElementById("msds-batch-action-bar");
    const countEl = document.getElementById("msds-selected-count");
    const delNumEl = document.getElementById("msds-batch-del-num");
    const headerBox = document.getElementById("msds-select-all");

    const selCount = SELECTED_MSDS_IDS.size;

    if (countEl) countEl.textContent = selCount;
    if (delNumEl) delNumEl.textContent = selCount;

    if (bar) {
        bar.classList.toggle("hidden", selCount === 0);
    }

    if (headerBox) {
        if (CURRENT_FILTERED_MSDS.length > 0 && selCount > 0) {
            const allSelected = CURRENT_FILTERED_MSDS.every(item => {
                const id = String(item.chem_id || item.product_code || "");
                return SELECTED_MSDS_IDS.has(id);
            });
            headerBox.checked = allSelected;
            headerBox.indeterminate = !allSelected && selCount > 0;
        } else {
            headerBox.checked = false;
            headerBox.indeterminate = false;
        }
    }
}
window.updateMsdsBatchActionBar = updateMsdsBatchActionBar;

function clearMsdsSelection() {
    SELECTED_MSDS_IDS.clear();
    const rowBoxes = document.querySelectorAll(".msds-row-checkbox");
    rowBoxes.forEach(box => {
        box.checked = false;
        const row = box.closest("tr");
        if (row) row.classList.remove("row-selected");
    });
    const headerBox = document.getElementById("msds-select-all");
    if (headerBox) {
        headerBox.checked = false;
        headerBox.indeterminate = false;
    }
    updateMsdsBatchActionBar();
}
window.clearMsdsSelection = clearMsdsSelection;

async function deleteSelectedMsdsBatch() {
    if (isGuestUser()) {
        alert("Khách (Guest) không có quyền xóa hóa chất.");
        return;
    }
    const ids = Array.from(SELECTED_MSDS_IDS);
    if (ids.length === 0) {
        alert("Vui lòng chọn ít nhất một hóa chất để xóa.");
        return;
    }

    if (!confirm(`Bạn có chắc chắn muốn xóa ${ids.length} hóa chất đã chọn khỏi Sổ CIL không?\n\n⚠️ Lưu ý: Thao tác này sẽ xóa vĩnh viễn dữ liệu trên cả máy chủ và Google Sheet (chống phục hồi lại khi server khởi động lại)!`)) {
        return;
    }

    try {
        const token = sessionStorage.getItem("luv_auth_token") || localStorage.getItem("luv_auth_token") || "verified";
        const role = sessionStorage.getItem("luv_user_role") || "owner";
        const resp = await fetch("/api/msds/delete-batch", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Titan-Session": token,
                "X-Titan-Role": role,
                "Authorization": "Bearer " + token
            },
            body: JSON.stringify({ ids: ids })
        });
        const res = await resp.json();
        if (!resp.ok || !res.success) {
            throw new Error(res.detail || res.message || "Lỗi khi xóa hàng loạt.");
        }
        clearMsdsSelection();
        await loadMsdsChemicalsList();
        alert(`✅ Đã xóa thành công ${res.deleted_count || ids.length} hóa chất khỏi danh mục CIL!`);
    } catch (err) {
        alert("Lỗi xóa hàng loạt: " + err.message);
    }
}
window.deleteSelectedMsdsBatch = deleteSelectedMsdsBatch;

// =============================================================
// TẢI HÀNG LOẠT FILE GỐC & THẺ AN TOÀN WORD (.ZIP) (MILESTONE M1)
// =============================================================

async function downloadSelectedMsdsOriginalZip() {
    const ids = Array.from(SELECTED_MSDS_IDS);
    if (!ids.length) {
        alert("Vui lòng chọn ít nhất một hóa chất để tải tệp MSDS gốc.");
        return;
    }
    const btn = document.getElementById("btn-batch-download-original");
    const origHtml = btn ? btn.innerHTML : "";
    try {
        if (btn) { btn.disabled = true; btn.innerHTML = "<span>⏳ Đang nén ZIP...</span>"; }
        const resp = await fetch("/api/msds/download-batch-original", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ids: ids })
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || "Lỗi đóng gói tệp ZIP MSDS gốc.");
        }
        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const now = new Date().toISOString().slice(0, 10).replace(/-/g, "");
        a.download = `MSDS_Goc_TongHop_${now}.zip`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    } catch (e) {
        alert("Lỗi tải ZIP MSDS gốc: " + e.message);
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
    }
}
window.downloadSelectedMsdsOriginalZip = downloadSelectedMsdsOriginalZip;

async function exportSelectedMsdsSafetyCardsZip() {
    const ids = Array.from(SELECTED_MSDS_IDS);
    if (!ids.length) {
        alert("Vui lòng chọn ít nhất một hóa chất để xuất Thẻ An Toàn Word.");
        return;
    }
    const btn = document.getElementById("btn-batch-download-cards");
    const origHtml = btn ? btn.innerHTML : "";
    try {
        if (btn) { btn.disabled = true; btn.innerHTML = "<span>⏳ Đang sinh Thẻ Word...</span>"; }
        const resp = await fetch("/api/msds/export-batch-safety-cards", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ids: ids })
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || "Lỗi đóng gói Thẻ An Toàn Word.");
        }
        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const now = new Date().toISOString().slice(0, 10).replace(/-/g, "");
        a.download = `The_An_Toan_TongHop_${now}.zip`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    } catch (e) {
        alert("Lỗi xuất ZIP Thẻ An Toàn: " + e.message);
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
    }
}
window.exportSelectedMsdsSafetyCardsZip = exportSelectedMsdsSafetyCardsZip;

function downloadAllMsdsOriginalZip() {
    window.location.href = "/api/msds/download-batch-original?scope=all";
}
window.downloadAllMsdsOriginalZip = downloadAllMsdsOriginalZip;

function exportAllMsdsSafetyCardsZip() {
    window.location.href = "/api/msds/export-batch-safety-cards?scope=all";
}
window.exportAllMsdsSafetyCardsZip = exportAllMsdsSafetyCardsZip;

function openMsdsDeleteAllModal() {
    if (isGuestUser()) {
        alert("Khách (Guest) không có quyền xóa danh mục hóa chất.");
        return;
    }
    const modal = document.getElementById("msds-delete-all-modal");
    const pwdInp = document.getElementById("msds-delete-all-pwd");
    const errDiv = document.getElementById("msds-delete-all-err");
    if (modal) {
        modal.classList.remove("hidden");
    }
    if (errDiv) errDiv.classList.add("hidden");
    if (pwdInp) {
        pwdInp.value = "";
        setTimeout(() => pwdInp.focus(), 100);
    }
}
window.openMsdsDeleteAllModal = openMsdsDeleteAllModal;

function closeMsdsDeleteAllModal() {
    const modal = document.getElementById("msds-delete-all-modal");
    const pwdInp = document.getElementById("msds-delete-all-pwd");
    const errDiv = document.getElementById("msds-delete-all-err");
    if (modal) modal.classList.add("hidden");
    if (pwdInp) pwdInp.value = "";
    if (errDiv) errDiv.classList.add("hidden");
}
window.closeMsdsDeleteAllModal = closeMsdsDeleteAllModal;

async function executeDeleteAllMsds() {
    if (isGuestUser()) {
        alert("Khách (Guest) không có quyền xóa danh mục hóa chất.");
        return;
    }
    const pwdInp = document.getElementById("msds-delete-all-pwd");
    const errDiv = document.getElementById("msds-delete-all-err");
    const errTxt = document.getElementById("msds-delete-all-err-txt");
    const pwd = (pwdInp ? pwdInp.value : "").trim();

    if (!pwd) {
        if (errDiv) errDiv.classList.remove("hidden");
        if (errTxt) errTxt.textContent = "Vui lòng nhập mật khẩu quản trị!";
        if (pwdInp) pwdInp.focus();
        return;
    }

    if (pwd !== "270120" && pwd.toUpperCase() !== "XOA") {
        if (errDiv) errDiv.classList.remove("hidden");
        if (errTxt) errTxt.textContent = "Vui lòng nhập đúng chữ 'XOA' hoặc mật khẩu 270120 để xác nhận!";
        if (pwdInp) {
            pwdInp.select();
            pwdInp.focus();
        }
        return;
    }

    // Tự động tải xuống 1 bản Sao lưu JSON dự phòng trước khi xóa vĩnh viễn CSDL
    try {
        const backupLink = document.createElement("a");
        backupLink.href = "/api/msds/export-json";
        backupLink.download = `Backup_CIL_Before_Delete_${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(backupLink);
        backupLink.click();
        document.body.removeChild(backupLink);
        await new Promise(r => setTimeout(r, 600));
    } catch (_bErr) {
        console.warn("Lỗi sao lưu JSON dự phòng trước khi xóa:", _bErr);
    }

    const btnConfirm = document.getElementById("btn-confirm-delete-all");
    try {
        if (btnConfirm) {
            btnConfirm.disabled = true;
            btnConfirm.textContent = "⏳ Đang xóa sạch CSDL...";
        }

        const token = sessionStorage.getItem("luv_auth_token") || localStorage.getItem("luv_auth_token") || "verified";
        const role = sessionStorage.getItem("luv_user_role") || "owner";
        const resp = await fetch("/api/msds/delete-all", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Titan-Session": token,
                "X-Titan-Role": role,
                "Authorization": "Bearer " + token
            },
            body: JSON.stringify({ password: pwd })
        });
        const res = await resp.json();
        if (!resp.ok || !res.success) {
            throw new Error(res.detail || res.message || "Không thể xóa toàn bộ CSDL.");
        }

        closeMsdsDeleteAllModal();
        clearMsdsSelection();

        ALL_MSDS_CHEMICALS_CACHE = [];
        try {
            localStorage.removeItem("luv_msds_cache");
            localStorage.setItem("cil_sync_outbox", "[]");
        } catch (_) {}

        if (window.MsdsGasSync && window.MsdsGasSync.getUrl()) {
            try {
                await window.MsdsGasSync.postAction({
                    token: window.MsdsGasSync.getToken(),
                    action: "deleteAllChemicals"
                });
            } catch (_) {}
        }

        await loadMsdsChemicalsList();
        alert("✅ Đã xóa sạch toàn bộ cơ sở dữ liệu hóa chất CIL thành công!");
    } catch (err) {
        if (errDiv) errDiv.classList.remove("hidden");
        if (errTxt) errTxt.textContent = err.message;
    } finally {
        if (btnConfirm) {
            btnConfirm.disabled = false;
            btnConfirm.textContent = "🗑️ Xác Nhận Xóa Sạch CSDL";
        }
    }
}
window.executeDeleteAllMsds = executeDeleteAllMsds;


function exportCilExcel() {
    window.location.href = "/api/msds/export-cil";
}

function openMsdsStorageFolder() {
    const folderUrl = (window.MsdsGasSync && window.MsdsGasSync.getFolderUrl()) || "https://drive.google.com/drive/u/0/my-drive";
    window.open(folderUrl, "_blank", "noopener,noreferrer");
}
window.openMsdsStorageFolder = openMsdsStorageFolder;

async function syncMsdsToGoogleDrive() {
    if (isGuestUser()) {
        alert("Khách (Guest) không có quyền đồng bộ Google Drive.");
        return;
    }
    const btn = document.getElementById("btn-msds-gdrive-sync");
    const txt = document.getElementById("txt-msds-gdrive-sync");
    const origText = txt ? txt.textContent : "☁️ Lưu Google Drive";

    try {
        if (txt) txt.textContent = "⏳ Đang đồng bộ...";
        if (btn) btn.disabled = true;

        const resp = await fetch("/api/msds/gdrive/sync", { method: "POST" });
        const res = await resp.json();

        if (!resp.ok || !res.success) {
            throw new Error(res.detail || res.error || "Không thể đồng bộ lên Google Drive.");
        }

        alert(`✅ ${res.message}\n\nThư mục Google Drive:\n${res.target_dir}`);
    } catch (err) {
        alert("Lỗi lưu vào Google Drive: " + err.message);
    } finally {
        if (txt) txt.textContent = origText;
        if (btn) btn.disabled = false;
    }
}

async function openMsdsGoogleDriveFolder() {
    // 1. Luôn mở Google Drive trực tuyến trên tab mới của trình duyệt ngay lập tức
    const webDriveUrl = "https://drive.google.com/drive/u/0/my-drive";
    window.open(webDriveUrl, "_blank", "noopener,noreferrer");

    // 2. Đồng thời gọi backend để mở Explorer cục bộ nếu ứng dụng đang chạy trên máy tính Windows
    try {
        const resp = await fetch("/api/msds/gdrive/open-folder", { method: "POST" });
        const res = await resp.json();
        if (resp.ok && res.success) {
            console.log("Google Drive open folder response:", res);
        }
    } catch (err) {
        console.warn("Local folder open warning (non-blocking):", err);
    }
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


/* ============================================================================== */
/* GHS DECANTING LABEL MAKER & PRINT ENGINE (MILESTONE M2)                        */
/* Circular 01/2026/TT-BCT Compliance                                             */
/* ============================================================================== */

let CURRENT_LABEL_SIZE = "A4_4UP";
let CURRENT_LABEL_CHEM_ID = null;
let CURRENT_LABEL_DATA = null;

const ALL_GHS_CODES = [
    { code: "GHS01", name: "Chất nổ" },
    { code: "GHS02", name: "Dễ cháy" },
    { code: "GHS03", name: "Oxy hóa" },
    { code: "GHS04", name: "Khí nén" },
    { code: "GHS05", name: "Ăn mòn" },
    { code: "GHS06", name: "Độc cấp tính" },
    { code: "GHS07", name: "Kích ứng" },
    { code: "GHS08", name: "Nguy hại sức khỏe" },
    { code: "GHS09", name: "Môi trường" }
];

function initGhsSelectorGrid(selectedCodes = []) {
    const grid = document.getElementById("label-ghs-grid");
    if (!grid) return;
    const normSelected = (selectedCodes || []).map(c => String(c).trim().toUpperCase());
    
    let html = "";
    ALL_GHS_CODES.forEach(item => {
        const isChecked = normSelected.includes(item.code);
        const tileClass = isChecked ? "ghs-checkbox-tile checked" : "ghs-checkbox-tile";
        html += `
            <label class="${tileClass}" id="tile-${item.code}">
                <input type="checkbox" value="${item.code}" ${isChecked ? "checked" : ""} onchange="onGhsCheckboxChange(this)" style="display:none;" />
                ${renderGhsDiamondSvg(item.code, 18)}
                <span>${item.code}</span>
            </label>
        `;
    });
    grid.innerHTML = html;
}

function onGhsCheckboxChange(checkbox) {
    const tile = document.getElementById(`tile-${checkbox.value}`);
    if (tile) {
        if (checkbox.checked) {
            tile.classList.add("checked");
        } else {
            tile.classList.remove("checked");
        }
    }
    updateLabelPreview();
}

function getSelectedGhsCodes() {
    const grid = document.getElementById("label-ghs-grid");
    if (!grid) return [];
    const checked = grid.querySelectorAll("input[type='checkbox']:checked");
    return Array.from(checked).map(cb => cb.value);
}

async function openMsdsLabelModal(chemId) {
    CURRENT_LABEL_CHEM_ID = chemId;
    CURRENT_LABEL_SIZE = "A4_4UP";
    setLabelPrintSize("A4_4UP");

    const modal = document.getElementById("msds-label-creator-modal");
    if (modal) modal.classList.remove("hidden");

    try {
        const resp = await fetch(`/api/msds/label-data/${encodeURIComponent(chemId)}`);
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}: Lỗi tải thông tin nhãn.`);
        }
        const data = await resp.json();
        CURRENT_LABEL_DATA = data;

        // Populate Form Controls
        const elName = document.getElementById("label-form-name");
        if (elName) elName.value = data.product_name || "";

        const elCode = document.getElementById("label-form-code");
        if (elCode) elCode.value = data.product_code || "";

        const elCas = document.getElementById("label-form-cas");
        if (elCas) elCas.value = data.cas_primary || "";

        const elFacility = document.getElementById("label-form-facility");
        if (elFacility) elFacility.value = data.facility || "Công ty TNHH Sơn ZhanChen (Việt Nam) - Phân Xưởng Pha Chế";

        const elDate = document.getElementById("label-form-date");
        if (elDate) elDate.value = data.decanting_date || new Date().toLocaleDateString("vi-VN");

        const elExpiry = document.getElementById("label-form-expiry");
        if (elExpiry) elExpiry.value = data.expiry_date || "Theo hạn sử dụng lô gốc (12 tháng)";

        const elLot = document.getElementById("label-form-lot");
        if (elLot) elLot.value = data.lot_number || `LOT-${new Date().toISOString().slice(0,10).replace(/-/g,'')}-01`;

        const elSignal = document.getElementById("label-form-signal");
        if (elSignal) {
            const sig = (data.signal_word || "").toUpperCase();
            if (sig.includes("NGUY HIỂM") || sig.includes("DANGER")) {
                elSignal.value = "NGUY HIỂM / DANGER";
            } else if (sig.includes("CẢNH BÁO") || sig.includes("WARNING")) {
                elSignal.value = "CẢNH BÁO / WARNING";
            } else {
                elSignal.value = "NON DG (AN TOÀN)";
            }
        }

        // Initialize GHS grid with pre-checked codes
        initGhsSelectorGrid(data.ghs_codes || []);

        const elH = document.getElementById("label-form-h");
        if (elH) elH.value = data.hazard_statements || "";

        const elP = document.getElementById("label-form-p");
        if (elP) elP.value = data.precautionary_statements || "";

        const elHotline = document.getElementById("label-form-hotline");
        if (elHotline) elHotline.value = data.hotline || "PCCC: 114 | Cấp Cứu: 115 | ZhanChen EHS: 0274.376.8888";

        updateLabelPreview();
    } catch (err) {
        console.error("Error loading label data:", err);
        alert("Không thể tải thông tin nhãn chiết rót: " + err.message);
    }
}

function closeMsdsLabelModal() {
    const modal = document.getElementById("msds-label-creator-modal");
    if (modal) modal.classList.add("hidden");
    CURRENT_LABEL_CHEM_ID = null;
    CURRENT_LABEL_DATA = null;
}

function setLabelPrintSize(size) {
    CURRENT_LABEL_SIZE = size;
    const container = document.getElementById("label-size-buttons");
    if (container) {
        const btns = container.querySelectorAll(".msds-btn-size");
        btns.forEach(btn => {
            if (btn.getAttribute("data-size") === size) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        });
    }

    const wrapper = document.getElementById("label-preview-wrapper");
    if (wrapper) {
        wrapper.className = `msds-label-preview-canvas-wrap size-${size.toLowerCase()}`;
    }
    updateLabelPreview();
}

function updateLabelPreview() {
    const previewBox = document.getElementById("label-preview-box");
    if (!previewBox) return;

    const pName = document.getElementById("label-form-name")?.value || "TÊN HÓA CHẤT CHIẾT RÓT";
    const pCode = document.getElementById("label-form-code")?.value || "CODE-01";
    const pCas = document.getElementById("label-form-cas")?.value || "N/A";
    const facility = document.getElementById("label-form-facility")?.value || "Công ty TNHH Sơn ZhanChen (Việt Nam)";
    const decantDate = document.getElementById("label-form-date")?.value || "";
    const expiryDate = document.getElementById("label-form-expiry")?.value || "";
    const lotNo = document.getElementById("label-form-lot")?.value || "";
    const signalWord = document.getElementById("label-form-signal")?.value || "NGUY HIỂM / DANGER";
    const hText = document.getElementById("label-form-h")?.value || "";
    const pText = document.getElementById("label-form-p")?.value || "";
    const hotline = document.getElementById("label-form-hotline")?.value || "114 / 115 / 0274.376.8888";

    const ghsCodes = getSelectedGhsCodes();

    // Signal word styling
    const isDanger = signalWord.includes("NGUY HIỂM") || signalWord.includes("DANGER");
    const isNonDg = signalWord.includes("NON DG");
    const sigBg = isDanger ? "#dc2626" : (isNonDg ? "#16a34a" : "#f59e0b");

    // Build SVG diamonds
    let ghsHtml = "";
    if (ghsCodes.length > 0) {
        ghsCodes.forEach(code => {
            ghsHtml += `<div class="ghs-icon-wrap" style="width:34px; height:34px; display:inline-block;">${renderGhsDiamondSvg(code, 34)}</div>`;
        });
    } else {
        ghsHtml = `<span style="font-size:11px; font-weight:bold; color:#16a34a; border:1px solid #16a34a; border-radius:4px; padding:2px 6px;">NON DG</span>`;
    }

    const cardMarkup = `
        <div class="ghs-label-card" style="border: 2px solid #cc0000; border-radius:4px; padding:10px; background:#fff;">
            <div style="text-align:center; border-bottom:1.5px solid #cc0000; padding-bottom:4px; margin-bottom:6px;">
                <div style="font-size:9px; font-weight:800; color:#0f172a; text-transform:uppercase;">${escapeHtml(facility)}</div>
                <div style="font-size:8px; font-weight:700; color:#dc2626; margin-top:1px;">NHÃN PHỤ HÓA CHẤT CHIẾT RÓT (THÔNG TƯ 01/2026/TT-BCT)</div>
            </div>

            <div style="margin-bottom:6px;">
                <div style="font-size:14px; font-weight:900; color:#0f172a; text-transform:uppercase; line-height:1.2;">${escapeHtml(pName)}</div>
                <div style="font-size:9.5px; color:#334155; margin-top:2px;">
                    <b>Mã SP:</b> ${escapeHtml(pCode)} &nbsp;|&nbsp; 
                    <b>CAS:</b> ${escapeHtml(pCas)} &nbsp;|&nbsp; 
                    <b>Lô:</b> ${escapeHtml(lotNo)}
                </div>
                <div style="font-size:9px; color:#475569; margin-top:1px;">
                    <b>Ngày chiết rót:</b> ${escapeHtml(decantDate)} &nbsp;|&nbsp; 
                    <b>Hạn dùng:</b> ${escapeHtml(expiryDate)}
                </div>
            </div>

            <div style="display:flex; align-items:center; justify-content:space-between; gap:10px; padding:5px 0; border-top:1px dashed #cbd5e1; border-bottom:1px dashed #cbd5e1; margin:6px 0;">
                <div style="background:${sigBg}; color:#fff; font-size:11px; font-weight:900; padding:4px 8px; border-radius:3px; letter-spacing:0.5px;">
                    ${escapeHtml(signalWord)}
                </div>
                <div style="display:flex; gap:4px; align-items:center; flex-wrap:wrap;">
                    ${ghsHtml}
                </div>
            </div>

            <div style="font-size:9px; color:#1e293b; line-height:1.3; margin:4px 0;">
                <div style="margin-bottom:3px;">
                    <b style="color:#991b1b;">⚠️ CẢNH BÁO NGUY CƠ (H):</b>
                    <span>${escapeHtml(hText)}</span>
                </div>
                <div>
                    <b style="color:#0369a1;">🛡️ BIỆN PHÁP PHÒNG NGỪA &amp; SƠ CỨU (P):</b>
                    <span>${escapeHtml(pText)}</span>
                </div>
            </div>

            <div style="border-top:1px solid #cbd5e1; padding-top:4px; margin-top:6px; text-align:center; font-size:8.5px; font-weight:700; color:#b91c1c;">
                📞 ỨNG PHÓ SỰ CỐ KHẨN CẤP: ${escapeHtml(hotline)}
            </div>
        </div>
    `;

    previewBox.innerHTML = cardMarkup;
}

function printGhsLabelSheet() {
    if (!CURRENT_LABEL_CHEM_ID) {
        alert("Vui lòng chọn một hóa chất để in nhãn.");
        return;
    }
    const url = `/api/msds/label-print-html/${encodeURIComponent(CURRENT_LABEL_CHEM_ID)}?size=${encodeURIComponent(CURRENT_LABEL_SIZE)}`;
    const printWin = window.open(url, "_blank");
    if (printWin) {
        printWin.focus();
    } else {
        alert("Trình duyệt đã chặn popup. Vui lòng cho phép popup để mở trang in nhãn.");
    }
}

async function downloadGhsLabelPdf() {
    if (!CURRENT_LABEL_CHEM_ID) {
        alert("Vui lòng chọn một hóa chất để tải PDF nhãn.");
        return;
    }

    try {
        const payload = {
            ids: [CURRENT_LABEL_CHEM_ID],
            size: CURRENT_LABEL_SIZE
        };
        const resp = await fetch("/api/msds/export-ghs-labels-pdf", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}: Lỗi xuất tệp PDF nhãn.`);
        }
        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const now = new Date().toISOString().slice(0, 10).replace(/-/g, "");
        a.download = `Nhan_GHS_${CURRENT_LABEL_CHEM_ID}_${CURRENT_LABEL_SIZE}_${now}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    } catch (err) {
        console.error("PDF download error:", err);
        alert("Lỗi tải PDF nhãn GHS: " + err.message);
    }
}

function openBatchLabelModal() {
    const ids = Array.from(SELECTED_MSDS_IDS || []);
    if (!ids.length) {
        alert("Vui lòng chọn ít nhất một hóa chất trong bảng để in nhãn GHS.");
        return;
    }
    // Open modal with the first selected chemical
    openMsdsLabelModal(ids[0]);
}

// ==============================================================================
// MILESTONE M3: STORAGE COMPATIBILITY MATRIX & WAREHOUSE CHECKER (TCVN 5507:2002)
// ==============================================================================

let STORAGE_MATRIX_DATA = null;
let STORAGE_CHEMICALS_CACHE = [];

async function loadStorageMatrixData() {
    if (STORAGE_MATRIX_DATA) return STORAGE_MATRIX_DATA;
    try {
        const resp = await fetch("/api/msds/storage-compatibility-matrix");
        if (resp.ok) {
            STORAGE_MATRIX_DATA = await resp.json();
            return STORAGE_MATRIX_DATA;
        }
    } catch (e) {
        console.error("Error loading storage matrix:", e);
    }
    return null;
}

async function openStorageMatrixModal(preselectChemIdA = null, preselectChemIdB = null) {
    const modal = document.getElementById("msds-storage-matrix-modal");
    if (!modal) return;
    modal.classList.remove("hidden");

    // Populate chemical selects from MSDS_CHEMICALS_DATA
    const selectA = document.getElementById("storage-select-chem-a");
    const selectB = document.getElementById("storage-select-chem-b");

    if (selectA && selectB) {
        let list = (typeof ALL_MSDS_CHEMICALS_CACHE !== "undefined" && Array.isArray(ALL_MSDS_CHEMICALS_CACHE) && ALL_MSDS_CHEMICALS_CACHE.length > 0)
            ? ALL_MSDS_CHEMICALS_CACHE
            : [];

        if (!list.length) {
            try {
                const resp = await fetch("/api/msds/list");
                if (resp.ok) {
                    const data = await resp.json();
                    list = data.data || [];
                    if (typeof ALL_MSDS_CHEMICALS_CACHE !== "undefined") {
                        ALL_MSDS_CHEMICALS_CACHE = list;
                    }
                }
            } catch (err) {
                console.error("Error fetching chemical list for matrix modal:", err);
            }
        }

        STORAGE_CHEMICALS_CACHE = list;

        let optionsHtml = "";
        list.forEach((c) => {
            const cid = c.chem_id || c.chemical_id || c.product_code || "";
            const name = c.product_name_vi || c.product_name || c.product_name_original || cid;
            const cas = c.cas_primary || c.cas_numbers || "";
            const casLabel = cas ? ` (CAS: ${cas})` : "";
            optionsHtml += `<option value="${escapeHtml(cid)}">${escapeHtml(cid)} — ${escapeHtml(name)}${escapeHtml(casLabel)}</option>`;
        });

        if (!list.length) {
            optionsHtml = '<option value="">(Không có hóa chất trong CSDL CIL)</option>';
        }

        selectA.innerHTML = optionsHtml;
        selectB.innerHTML = optionsHtml;

        if (preselectChemIdA && selectA.querySelector(`option[value="${preselectChemIdA}"]`)) {
            selectA.value = preselectChemIdA;
        } else if (list.length > 0) {
            selectA.selectedIndex = 0;
        }

        if (preselectChemIdB && selectB.querySelector(`option[value="${preselectChemIdB}"]`)) {
            selectB.value = preselectChemIdB;
        } else if (list.length > 1) {
            selectB.selectedIndex = 1;
        } else if (list.length > 0) {
            selectB.selectedIndex = 0;
        }
    }

    // Load and render matrix grid
    await renderStorageMatrixGrid();

    // Trigger initial pairwise evaluation
    evaluatePairwiseStorage();
}

function closeStorageMatrixModal() {
    const modal = document.getElementById("msds-storage-matrix-modal");
    if (modal) {
        modal.classList.add("hidden");
    }
}

function swapStoragePairwiseChems() {
    const selectA = document.getElementById("storage-select-chem-a");
    const selectB = document.getElementById("storage-select-chem-b");
    if (!selectA || !selectB) return;
    const valA = selectA.value;
    selectA.value = selectB.value;
    selectB.value = valA;
    evaluatePairwiseStorage();
}

async function evaluatePairwiseStorage() {
    const selectA = document.getElementById("storage-select-chem-a");
    const selectB = document.getElementById("storage-select-chem-b");
    if (!selectA || !selectB) return;

    const idA = selectA.value;
    const idB = selectB.value;
    if (!idA || !idB) return;

    const card = document.getElementById("storage-pairwise-card");
    const badge = document.getElementById("storage-pairwise-badge");
    const code = document.getElementById("storage-pairwise-code");
    const mech = document.getElementById("storage-pairwise-mech");
    const measures = document.getElementById("storage-pairwise-measures");
    const tcvn = document.getElementById("storage-pairwise-tcvn");
    const wrapA = document.getElementById("storage-pairwise-classes-a");
    const wrapB = document.getElementById("storage-pairwise-classes-b");

    try {
        const payload = {
            chem_a: idA,
            chem_b: idB
        };
        const resp = await fetch("/api/msds/storage-compatibility-check", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }

        const data = await resp.json();
        const pair = data.pairwise || (data.pairs && data.pairs[0]) || data;

        const pCode = pair.code || "C";
        const pBadge = pair.badge || (pCode === "X" ? "CẤM LƯU TRỮ CHUNG" : (pCode === "S" ? "YÊU CẦU CÁCH LY" : "CHO PHÉP LƯU TRỮ"));
        const pColor = pair.color || (pCode === "X" ? "#dc2626" : (pCode === "S" ? "#eab308" : "#16a34a"));
        const pBg = pCode === "X" ? "#fef2f2" : (pCode === "S" ? "#fefce8" : "#f0fdf4");
        const pBorder = pCode === "X" ? "#f87171" : (pCode === "S" ? "#facc15" : "#86efac");

        if (card) {
            card.style.background = pBg;
            card.style.borderColor = pBorder;
        }

        if (badge) {
            badge.innerText = pBadge;
            badge.style.background = pColor;
        }

        if (code) {
            code.innerText = `Mã: ${pCode}`;
            code.style.color = pColor;
        }

        if (mech) {
            mech.innerText = pair.danger_mechanism || "Không có xung đột nguy hại.";
        }

        if (measures) {
            measures.innerText = pair.safety_measures || pair.recommended_measures || "Lưu kho thông thường.";
        }

        if (tcvn) {
            tcvn.innerText = `Căn cứ: ${pair.tcvn_reference || 'TCVN 5507:2002'}`;
        }

        if (wrapA && pair.chem_a) {
            const classesInfoA = (Array.isArray(pair.chem_a.classes_info) && pair.chem_a.classes_info.length > 0)
                ? pair.chem_a.classes_info
                : (pair.chem_a.storage_classes || ["NON_DG"]).map(c => ({ code: c, label_vi: c, icon: "🏷️" }));
            wrapA.innerHTML = classesInfoA.map(info => {
                const icon = info.icon || "🏷️";
                const label = info.label_vi || info.code || "NON_DG";
                const code = info.code || "";
                return `<span style="font-size:11px; font-weight:700; background:#f0fdf4; color:#166534; padding:3px 8px; border-radius:5px; border:1px solid #bbf7d0;" title="${escapeHtml(info.description || '')}">${icon} ${escapeHtml(code ? code + ' - ' + label : label)}</span>`;
            }).join(" ");
        }

        if (wrapB && pair.chem_b) {
            const classesInfoB = (Array.isArray(pair.chem_b.classes_info) && pair.chem_b.classes_info.length > 0)
                ? pair.chem_b.classes_info
                : (pair.chem_b.storage_classes || ["NON_DG"]).map(c => ({ code: c, label_vi: c, icon: "🏷️" }));
            wrapB.innerHTML = classesInfoB.map(info => {
                const icon = info.icon || "🏷️";
                const label = info.label_vi || info.code || "NON_DG";
                const code = info.code || "";
                return `<span style="font-size:11px; font-weight:700; background:#f0fdf4; color:#166534; padding:3px 8px; border-radius:5px; border:1px solid #bbf7d0;" title="${escapeHtml(info.description || '')}">${icon} ${escapeHtml(code ? code + ' - ' + label : label)}</span>`;
            }).join(" ");
        }

    } catch (err) {
        console.error("Pairwise evaluate error:", err);
    }
}

async function renderStorageMatrixGrid() {
    const table = document.getElementById("storage-matrix-table");
    if (!table) return;

    const matrixData = await loadStorageMatrixData();
    if (!matrixData || !matrixData.classes || !matrixData.matrix) {
        table.innerHTML = "<tr><td style='padding:20px; color:#ef4444;'>Không thể nạp dữ liệu ma trận lưu kho.</td></tr>";
        return;
    }

    const classes = matrixData.classes;
    const matrix = matrixData.matrix;

    let html = "<thead><tr><th style='padding:8px; background:#1e293b; color:#fff; border:1px solid #475569;'>Nhóm / GHS</th>";
    classes.forEach(c => {
        html += `<th style='padding:6px; background:#334155; color:#f8fafc; border:1px solid #475569; font-size:11px; cursor:help;' title='${escapeHtml(c.label_vi)}: ${escapeHtml(c.description)}'>${escapeHtml(c.code)}</th>`;
    });
    html += "</tr></thead><tbody>";

    classes.forEach(rowClass => {
        html += `<tr><td style='padding:6px 10px; font-weight:700; text-align:left; background:#f1f5f9; border:1px solid #cbd5e1; white-space:nowrap;'>`;
        html += `<span style='margin-right:4px;'>${rowClass.icon || '⚗️'}</span> <b>${escapeHtml(rowClass.code)}</b> <span style='font-size:10.5px; color:#64748b;'>(${escapeHtml(rowClass.label_vi)})</span>`;
        html += `</td>`;

        classes.forEach(colClass => {
            const cell = (matrix[rowClass.id] && matrix[rowClass.id][colClass.id]) || { code: "C" };
            const code = cell.code || "C";
            let bg = "#dcfce7";
            let fg = "#15803d";
            let title = "Cho phép xếp chung";

            if (code === "X") {
                bg = "#fee2e2";
                fg = "#b91c1c";
                title = "NGHIÊM CẤM để chung (Nguy cơ cháy nổ/phản ứng)";
            } else if (code === "S") {
                bg = "#fef9c3";
                fg = "#a16207";
                title = "YÊU CẦU CÁCH LY (>= 3-5m hoặc có vách ngăn)";
            }

            html += `<td style='padding:6px; font-weight:800; font-size:12px; cursor:pointer; background:${bg}; color:${fg}; border:1px solid #cbd5e1; transition:all 0.15s;' 
                        onclick="showStorageCellDetail('${escapeHtml(rowClass.id)}', '${escapeHtml(colClass.id)}')"
                        title='${escapeHtml(rowClass.code)} + ${escapeHtml(colClass.code)}: ${title}'>
                        ${code}
                    </td>`;
        });

        html += "</tr>";
    });

    html += "</tbody>";
    table.innerHTML = html;
}

function showStorageCellDetail(classAId, classBId) {
    if (!STORAGE_MATRIX_DATA || !STORAGE_MATRIX_DATA.matrix) return;
    const rule = (STORAGE_MATRIX_DATA.matrix[classAId] && STORAGE_MATRIX_DATA.matrix[classAId][classBId]) || {};
    const classA = (STORAGE_MATRIX_DATA.classes || []).find(c => c.id === classAId) || { code: classAId, label_vi: classAId };
    const classB = (STORAGE_MATRIX_DATA.classes || []).find(c => c.id === classBId) || { code: classBId, label_vi: classBId };

    const popover = document.getElementById("storage-cell-detail-card");
    const title = document.getElementById("storage-cell-detail-title");
    const text = document.getElementById("storage-cell-detail-text");
    if (!popover || !title || !text) return;

    const code = rule.code || "C";
    const badge = rule.badge || (code === "X" ? "CẤM LƯU TRỮ CHUNG" : (code === "S" ? "YÊU CẦU CÁCH LY" : "CHO PHÉP"));
    const color = rule.color || (code === "X" ? "#dc2626" : (code === "S" ? "#eab308" : "#16a34a"));

    title.innerHTML = `
        <span style="display:inline-flex; align-items:center; gap:6px;">
            <span>${classA.icon || '⚗️'} <b>${escapeHtml(classA.code)}</b> (${escapeHtml(classA.label_vi)})</span>
            <span>+</span>
            <span>${classB.icon || '⚗️'} <b>${escapeHtml(classB.code)}</b> (${escapeHtml(classB.label_vi)})</span>
            <span style="background:${color}; color:#fff; padding:2px 8px; border-radius:4px; font-size:11px; margin-left:8px;">${badge} [${code}]</span>
        </span>
    `;

    text.innerHTML = `
        <div style="margin-bottom:6px;"><b>Cơ chế phản ứng &amp; Nguy hại:</b> ${escapeHtml(rule.mechanism || 'Cho phép lưu trữ chung.')}</div>
        <div style="color:#64748b; font-size:11.5px;"><b>Căn cứ quy chuẩn:</b> ${escapeHtml(rule.tcvn_clause || 'TCVN 5507:2002')}</div>
    `;

    popover.style.display = "block";
    popover.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function auditFullWarehouseStorage() {
    try {
        const btn = document.querySelector("#msds-storage-matrix-modal button[onclick='auditFullWarehouseStorage()']");
        if (btn) { btn.disabled = true; btn.innerHTML = "⏳ Đang quét toàn kho..."; }

        const resp = await fetch("/api/msds/storage-compatibility-check", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({})
        });

        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }

        const data = await resp.json();
        const conflicts = data.conflicts || [];
        const warnings = data.warnings || [];
        const total = data.total_chemicals || 0;

        let alertMsg = `KẾT QUẢ KIỂM TOÁN TỒN TRỮ KHO HÓA CHẤT (TCVN 5507:2002):\n`;
        alertMsg += `--------------------------------------------------\n`;
        alertMsg += `Tổng số hóa chất kiểm tra: ${total} chất (${data.total_pairs || 0} cặp tương tác)\n`;
        alertMsg += `🔴 Số cặp NGHIÊM CẤM lưu trữ chung (Mã X): ${conflicts.length}\n`;
        alertMsg += `🟡 Số cặp YÊU CẦU CÁCH LY ≥ 3-5m (Mã S): ${warnings.length}\n`;
        alertMsg += `🟢 Số cặp CHO PHÉP (Mã C): ${data.compatible_count || 0}\n\n`;

        if (conflicts.length > 0) {
            alertMsg += `DANH SÁCH XUNG ĐỘT CẤM CẦN XỬ LÝ NGAY:\n`;
            conflicts.forEach((c, i) => {
                const nameA = (c.chem_a && c.chem_a.name) || "Chất A";
                const nameB = (c.chem_b && c.chem_b.name) || "Chất B";
                alertMsg += `  ${i + 1}. [${nameA}] + [${nameB}]: ${c.danger_mechanism}\n`;
            });
        } else if (warnings.length > 0) {
            alertMsg += `Lưu ý: Không có xung đột cấm (X), nhưng cần duy trì khoảng cách cách ly cho ${warnings.length} cặp hóa chất.\n`;
        } else {
            alertMsg += `Tuyệt vời! Toàn bộ kho hóa chất hiện tại đều tương thích lưu trữ an toàn!\n`;
        }

        alert(alertMsg);

    } catch (err) {
        console.error("Audit error:", err);
        alert("Lỗi kiểm toán kho hóa chất: " + err.message);
    } finally {
        const btn = document.querySelector("#msds-storage-matrix-modal button[onclick='auditFullWarehouseStorage()']");
        if (btn) { btn.disabled = false; btn.innerHTML = "🔍 <span>Quét Xung Đột Toàn Kho</span>"; }
    }
}

// ==============================================================================
// MILESTONE M4: ANNUAL CHEMICAL REPORT EXPORT (THÔNG TƯ 02/2026/TT-BCT)
// ==============================================================================

async function exportAnnualChemicalReport() {
    const btn = document.getElementById("btn-export-annual-report");
    const originalText = btn ? btn.innerHTML : "";
    try {
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = `<span>⏳ Đang kết xuất Báo cáo...</span>`;
        }

        const resp = await fetch("/api/msds/export-annual-chemical-report");
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}: Lỗi khi xuất báo cáo hóa chất hàng năm.`);
        }

        const blob = await resp.blob();
        const disposition = resp.headers.get("content-disposition") || "";
        let filename = "Bao_Cao_Tong_Hop_Hoa_Chat_Hang_Nam_2026.xlsx";
        const filenameMatch = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
            filename = filenameMatch[1].replace(/['"]/g, "");
        }

        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (err) {
        console.error("Lỗi xuất Báo Cáo Hóa Chất Hàng Năm:", err);
        alert("Không thể xuất Báo Cáo Hàng Năm: " + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
}

// ==============================================================================
// MILESTONE M5: FIELD MOBILE QR CODE & STICKER PRINT MODAL
// ==============================================================================

let CURRENT_QR_CHEM_ID = null;
let CURRENT_QR_STICKER_SIZE = 50; // mm

async function openMsdsQrModal(chemId) {
    CURRENT_QR_CHEM_ID = chemId;
    const modal = document.getElementById("msds-qr-modal");
    const codeEl = document.getElementById("msds-qr-chem-code");
    const nameEl = document.getElementById("msds-qr-chem-name");
    const casEl = document.getElementById("msds-qr-chem-cas");
    const previewEl = document.getElementById("msds-qr-preview");
    const mobileLink = document.getElementById("msds-qr-mobile-link");

    if (!modal) return;
    modal.classList.remove("hidden");

    if (codeEl) codeEl.textContent = chemId;
    if (nameEl) nameEl.textContent = "Đang tải...";
    if (casEl) casEl.textContent = "CAS: ...";
    if (previewEl) previewEl.innerHTML = `<div class="spinner"></div>`;
    if (mobileLink) {
        mobileLink.href = `/mobile-msds/${encodeURIComponent(chemId)}`;
    }

    try {
        // Fetch chemical details
        const detailResp = await fetch(`/api/msds/detail/${encodeURIComponent(chemId)}`);
        if (detailResp.ok) {
            const json = await detailResp.json();
            const chem = (json.data && json.data.chemical) || {};
            if (codeEl) codeEl.textContent = chem.product_code || chem.chem_id || chemId;
            if (nameEl) nameEl.textContent = chem.product_name || "Hóa chất";
            if (casEl) casEl.textContent = `CAS: ${chem.cas_numbers || "Hỗn hợp"}`;
        }

        // Fetch SVG QR code
        const qrResp = await fetch(`/api/msds/qr-code/${encodeURIComponent(chemId)}`);
        if (!qrResp.ok) {
            throw new Error(`HTTP ${qrResp.status}: Không thể tải mã QR.`);
        }
        const svgText = await qrResp.text();
        if (previewEl) {
            previewEl.innerHTML = svgText;
        }
    } catch (err) {
        console.error("Lỗi nạp mã QR:", err);
        if (previewEl) {
            previewEl.innerHTML = `<div style="color:#ef4444; font-size:12px; padding:10px;">Lỗi tải mã QR: ${err.message}</div>`;
        }
    }
}

function closeMsdsQrModal() {
    const modal = document.getElementById("msds-qr-modal");
    if (modal) {
        modal.classList.add("hidden");
    }
    CURRENT_QR_CHEM_ID = null;
}

function selectQrStickerPreset(sizeMm, btn) {
    CURRENT_QR_STICKER_SIZE = sizeMm;
    const buttons = document.querySelectorAll(".msds-btn-qr-size");
    buttons.forEach(b => b.classList.remove("active"));
    if (btn) btn.classList.add("active");

    const card = document.getElementById("msds-qr-sticker-card");
    if (card) {
        card.setAttribute("data-size", sizeMm);
    }
}

function downloadQrImage(format = "png", card = 1) {
    if (!CURRENT_QR_CHEM_ID) {
        alert("Chưa chọn hóa chất để tải mã QR.");
        return;
    }
    const ext = format === "png" ? "png" : "svg";
    const a = document.createElement("a");
    a.href = `/api/msds/qr-code/${encodeURIComponent(CURRENT_QR_CHEM_ID)}?format=${ext}&card=${card ? 1 : 0}`;
    a.download = `QR_Emergency_${CURRENT_QR_CHEM_ID}.${ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

function printQrSticker() {
    if (!CURRENT_QR_CHEM_ID) {
        alert("Chưa chọn hóa chất để in tem QR.");
        return;
    }

    const previewSvg = document.getElementById("msds-qr-preview")?.innerHTML || "";
    const codeText = document.getElementById("msds-qr-chem-code")?.textContent || CURRENT_QR_CHEM_ID;
    const nameText = document.getElementById("msds-qr-chem-name")?.textContent || "";
    const casText = document.getElementById("msds-qr-chem-cas")?.textContent || "";
    const sizeMm = CURRENT_QR_STICKER_SIZE || 50;

    const printWin = window.open("", "_blank", "width=600,height=600");
    if (!printWin) {
        alert("Trình duyệt đã chặn cửa sổ in tem. Vui lòng cho phép popup.");
        return;
    }

    const htmlContent = `<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Tem QR Cứu Hộ - ${escapeHtml(codeText)}</title>
    <style>
        @page {
            size: ${sizeMm}mm ${sizeMm}mm;
            margin: 0;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            width: ${sizeMm}mm;
            height: ${sizeMm}mm;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            background: #fff;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 2mm;
            text-align: center;
            overflow: hidden;
        }
        .tag {
            font-size: ${sizeMm <= 50 ? '6pt' : '8pt'};
            font-weight: 800;
            color: #c2410c;
            background: #fff7ed;
            border: 0.5pt solid #fdba74;
            padding: 1pt 3pt;
            border-radius: 2pt;
            margin-bottom: 1.5mm;
            text-transform: uppercase;
        }
        .qr-box {
            width: ${sizeMm <= 50 ? '24mm' : (sizeMm <= 70 ? '36mm' : '52mm')};
            height: ${sizeMm <= 50 ? '24mm' : (sizeMm <= 70 ? '36mm' : '52mm')};
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .qr-box svg {
            width: 100% !important;
            height: 100% !important;
        }
        .code {
            font-size: ${sizeMm <= 50 ? '7pt' : '9pt'};
            font-weight: 900;
            color: #0f172a;
            margin-top: 1mm;
        }
        .name {
            font-size: ${sizeMm <= 50 ? '5.5pt' : '7.5pt'};
            color: #334155;
            font-weight: 600;
            max-width: 95%;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .cas {
            font-size: ${sizeMm <= 50 ? '5pt' : '6.5pt'};
            color: #64748b;
            font-family: monospace;
        }
        .call {
            font-size: ${sizeMm <= 50 ? '5pt' : '6pt'};
            color: #dc2626;
            font-weight: 700;
            margin-top: 0.5mm;
        }
    </style>
</head>
<body>
    <div class="tag">⚡ CỨU HỘ KHẨN CẤP</div>
    <div class="qr-box">${previewSvg}</div>
    <div class="code">${escapeHtml(codeText)}</div>
    <div class="name">${escapeHtml(nameText)}</div>
    <div class="cas">${escapeHtml(casText)}</div>
    <div class="call">Cứu hỏa 114 · Y tế 115</div>
    <script>
        window.onload = function() {
            window.print();
            setTimeout(function() { window.close(); }, 600);
        };
    </` + `script>
</body>
</html>`;

    printWin.document.open();
    printWin.document.write(htmlContent);
    printWin.document.close();
}

// ==============================================================================
// GOOGLE APPS SCRIPT (GAS) & DRIVE CLOUD PERSISTENCE (MILESTONE 2)
// ==============================================================================

async function openMsdsGasSettingsModal() {
    if (isGuestUser()) {
        alert("Khách (Guest) không có quyền truy cập cấu hình Cloud.");
        return;
    }
    const modal = document.getElementById("msds-gas-settings-modal");
    if (!modal) return;
    modal.classList.remove("hidden");
    await loadMsdsGasConfig();
}
window.openMsdsGasSettingsModal = openMsdsGasSettingsModal;

function closeMsdsGasSettingsModal() {
    const modal = document.getElementById("msds-gas-settings-modal");
    if (modal) modal.classList.add("hidden");
}
window.closeMsdsGasSettingsModal = closeMsdsGasSettingsModal;

async function loadMsdsGasConfig() {
    const urlInput = document.getElementById("msds-gas-url-input");
    const tokenInput = document.getElementById("msds-gas-token-input");
    const autoSyncInput = document.getElementById("msds-gas-autosync-input");
    const badge = document.getElementById("msds-gas-live-badge");
    const statusMsg = document.getElementById("msds-gas-status-msg");

    // Ưu tiên đọc cấu hình từ localStorage
    const localUrl = (localStorage.getItem("msds_gas_url") || "").trim();
    const localToken = (localStorage.getItem("msds_gas_token") || "LUV_PDF_SYNC_KEY_2026").trim();
    if (urlInput && localUrl) urlInput.value = localUrl;
    if (tokenInput && localToken) tokenInput.value = localToken;

    try {
        const token = sessionStorage.getItem("luv_auth_token") || localStorage.getItem("luv_auth_token") || "verified";
        const role = sessionStorage.getItem("luv_user_role") || "owner";
        const resp = await fetch("/api/msds/gas/config", {
            headers: {
                "X-Titan-Session": token,
                "X-Titan-Role": role,
                "Authorization": "Bearer " + token
            }
        });
        const data = await resp.json();
        if (data && data.success) {
            if (urlInput && !urlInput.value && data.webhook_url) {
                urlInput.value = data.webhook_url;
                localStorage.setItem("msds_gas_url", data.webhook_url);
            }
            if (tokenInput && (!tokenInput.value || tokenInput.value === "LUV_PDF_SYNC_KEY_2026") && data.secret_token && !data.secret_token.includes("••••")) {
                tokenInput.value = data.secret_token;
                localStorage.setItem("msds_gas_token", data.secret_token);
            }
            if (autoSyncInput) autoSyncInput.checked = (data.auto_sync !== false);
        }
    } catch (err) {
        console.warn("Backend GAS config fallback:", err);
    }

    const currentUrl = urlInput ? urlInput.value.trim() : "";
    if (currentUrl) {
        if (badge) {
            badge.textContent = "Đã cấu hình";
            badge.style.background = "#dbeafe";
            badge.style.color = "#1d4ed8";
        }
        if (statusMsg) {
            statusMsg.textContent = "Webhook URL đã sẵn sàng. Bấm 'Kiểm Tra Kết Nối' để xác thực live.";
        }
    } else {
        if (badge) {
            badge.textContent = "Chưa kết nối";
            badge.style.background = "#e2e8f0";
            badge.style.color = "#475569";
        }
        if (statusMsg) {
            statusMsg.textContent = "Nhập Webhook URL Google Apps Script và bấm Lưu Cài Đặt.";
        }
    }
}
window.loadMsdsGasConfig = loadMsdsGasConfig;

async function saveMsdsGasConfig() {
    if (isGuestUser()) {
        alert("Khách (Guest) không có quyền lưu cấu hình.");
        return;
    }
    const urlInput = document.getElementById("msds-gas-url-input");
    const tokenInput = document.getElementById("msds-gas-token-input");
    const autoSyncInput = document.getElementById("msds-gas-autosync-input");
    const btnSave = document.getElementById("btn-save-gas-config");

    const webhookUrl = (urlInput ? urlInput.value : "").trim();
    let secretToken = (tokenInput ? tokenInput.value : "").trim() || "LUV_PDF_SYNC_KEY_2026";
    if (secretToken === "******" || secretToken.indexOf("•") !== -1) {
        secretToken = localStorage.getItem("msds_gas_token") || "LUV_PDF_SYNC_KEY_2026";
    }
    const autoSync = autoSyncInput ? autoSyncInput.checked : true;

    // Lưu vào localStorage ngay lập tức
    localStorage.setItem("msds_gas_url", webhookUrl);
    localStorage.setItem("msds_gas_token", secretToken);

    try {
        if (btnSave) {
            btnSave.disabled = true;
            btnSave.textContent = "⏳ Đang lưu...";
        }

        const token = sessionStorage.getItem("luv_auth_token") || localStorage.getItem("luv_auth_token") || "verified";
        const role = sessionStorage.getItem("luv_user_role") || "owner";
        try {
            await fetch("/api/msds/gas/config", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Titan-Session": token,
                    "X-Titan-Role": role,
                    "Authorization": "Bearer " + token
                },
                body: JSON.stringify({
                    webhook_url: webhookUrl,
                    secret_token: secretToken,
                    auto_sync: autoSync
                })
            });
        } catch (_) {}

        alert("✅ Đã lưu cấu hình Google Apps Script thành công!");
        await loadMsdsGasConfig();
        // Kích hoạt đồng bộ đám mây ngay lập tức
        if (webhookUrl && window.MsdsGasSync) {
            await window.MsdsGasSync.pullFromCloud(true);
        }
    } catch (err) {
        alert("Lỗi khi lưu cấu hình GAS: " + err.message);
    } finally {
        if (btnSave) {
            btnSave.disabled = false;
            btnSave.textContent = "💾 Lưu Cài Đặt";
        }
    }
}
window.saveMsdsGasConfig = saveMsdsGasConfig;

async function testMsdsGasConnection() {
    const urlInput = document.getElementById("msds-gas-url-input");
    const tokenInput = document.getElementById("msds-gas-token-input");
    const badge = document.getElementById("msds-gas-live-badge");
    const statusMsg = document.getElementById("msds-gas-status-msg");
    const btnTest = document.getElementById("btn-gas-test-conn");

    const webhookUrl = (urlInput ? urlInput.value : "").trim();
    let secretToken = (tokenInput ? tokenInput.value : "").trim() || "LUV_PDF_SYNC_KEY_2026";

    if (!webhookUrl) {
        alert("Vui lòng nhập Google Apps Script Webhook URL trước khi kiểm tra!");
        if (urlInput) urlInput.focus();
        return;
    }

    try {
        if (btnTest) {
            btnTest.disabled = true;
            btnTest.textContent = "⏳ Đang kiểm tra...";
        }
        if (badge) {
            badge.textContent = "Đang kết nối...";
            badge.style.background = "#fef3c7";
            badge.style.color = "#b45309";
        }
        if (statusMsg) {
            statusMsg.textContent = "Đang gửi tín hiệu ping tới Google Apps Script...";
        }

        // Kiểm tra ping trực tiếp qua GET (không lo CORS preflight)
        let pingData = null;
        try {
            const directResp = await fetch(`${webhookUrl}?action=ping&t=${Date.now()}`);
            if (directResp.ok) {
                pingData = await directResp.json();
            }
        } catch (_corsErr) {
            console.warn("Direct ping warning, falling back to backend proxy:", _corsErr);
        }

        // Nếu direct ping không qua được thì gọi qua proxy Backend
        if (!pingData) {
            const token = sessionStorage.getItem("luv_auth_token") || localStorage.getItem("luv_auth_token") || "verified";
            const role = sessionStorage.getItem("luv_user_role") || "owner";
            const resp = await fetch("/api/msds/gas/test-connection", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Titan-Session": token,
                    "X-Titan-Role": role,
                    "Authorization": "Bearer " + token
                },
                body: JSON.stringify({
                    webhook_url: webhookUrl,
                    secret_token: secretToken
                })
            });
            const res = await resp.json();
            if (res.success && res.data) {
                pingData = res.data;
            } else {
                throw new Error(res.error || res.detail || "Không thể kết nối.");
            }
        }

        if (pingData && (pingData.status === "ok" || pingData.success)) {
            if (badge) {
                badge.textContent = "🟢 Kết Nối Hoạt Động";
                badge.style.background = "#dcfce7";
                badge.style.color = "#15803d";
            }
            if (statusMsg) {
                const sheetRows = pingData.count ?? pingData.total_rows ?? pingData.total_chemicals_in_sheet ?? 0;
                const cloudVer = pingData.version ? `v${pingData.version}` : "v1";
                statusMsg.innerHTML = `<b>Kết nối Google Apps Script thành công!</b><br>` +
                    `• Bảng tính: <b>${pingData.spreadsheetName || pingData.spreadsheet_name || "CIL_Chemical_Inventory"}</b><br>` +
                    `• Số lượng hóa chất trong Sheet: <b>${sheetRows}</b><br>` +
                    `• Phiên bản Cloud: <b>${cloudVer}</b><br>` +
                    `• Thư mục Google Drive: <b>${pingData.driveSubFolder || pingData.drive_folder || "MSDS_Originals"}</b>`;
            }
            if (pingData.driveSubFolderUrl) {
                localStorage.setItem("msds_gas_folder_url", pingData.driveSubFolderUrl);
            }
        } else {
            throw new Error((pingData && pingData.error) || "Phản hồi không xác thực");
        }
    } catch (err) {
        if (badge) {
            badge.textContent = "🔴 Lỗi Kết Nối";
            badge.style.background = "#fee2e2";
            badge.style.color = "#b91c1c";
        }
        if (statusMsg) {
            statusMsg.textContent = "Lỗi kết nối: " + err.message;
        }
    } finally {
        if (btnTest) {
            btnTest.disabled = false;
            btnTest.textContent = "▶ Kiểm Tra Kết Nối";
        }
    }
}
window.testMsdsGasConnection = testMsdsGasConnection;

async function executeGasSyncToSheet() {
    if (isGuestUser()) {
        alert("Khách (Guest) không có quyền đồng bộ dữ liệu.");
        return;
    }
    if (!confirm("Bạn có muốn đẩy toàn bộ hóa chất hiện có từ máy chủ lên Google Sheet (Backup) không?")) {
        return;
    }
    const btnSync = document.getElementById("btn-gas-sync-to-sheet");
    try {
        if (btnSync) {
            btnSync.disabled = true;
            btnSync.textContent = "⏳ Đang đẩy lên Sheet...";
        }
        const token = sessionStorage.getItem("luv_auth_token") || localStorage.getItem("luv_auth_token") || "verified";
        const role = sessionStorage.getItem("luv_user_role") || "owner";
        const resp = await fetch("/api/msds/gas/sync-to-sheet", {
            method: "POST",
            headers: {
                "X-Titan-Session": token,
                "X-Titan-Role": role,
                "Authorization": "Bearer " + token
            }
        });
        const res = await resp.json();
        if (!resp.ok || !res.success) {
            throw new Error(res.detail || res.message || "Không thể đồng bộ lên Google Sheet.");
        }
        alert(`✅ ${res.message || "Đồng bộ thành công!"}`);
    } catch (err) {
        alert("Lỗi đồng bộ lên Sheet: " + err.message);
    } finally {
        if (btnSync) {
            btnSync.disabled = false;
            btnSync.textContent = "⬆️ Đẩy Lên Sheet (Backup)";
        }
    }
}
window.executeGasSyncToSheet = executeGasSyncToSheet;

async function executeGasSyncFromSheet() {
    if (isGuestUser()) {
        alert("Khách (Guest) không có quyền đồng bộ dữ liệu.");
        return;
    }
    if (!confirm("Bạn có chắc muốn kéo dữ liệu từ Google Sheet về máy chủ (Restore/Hòa giải)?\n\nDữ liệu cục bộ sẽ được đồng bộ theo Google Sheet (Nguồn dữ liệu gốc).")) {
        return;
    }
    const btnPull = document.getElementById("btn-gas-sync-from-sheet");
    try {
        if (btnPull) {
            btnPull.disabled = true;
            btnPull.textContent = "⏳ Đang tải về...";
        }
        const token = sessionStorage.getItem("luv_auth_token") || localStorage.getItem("luv_auth_token") || "verified";
        const role = sessionStorage.getItem("luv_user_role") || "owner";
        const resp = await fetch("/api/msds/gas/sync-from-sheet", {
            method: "POST",
            headers: {
                "X-Titan-Session": token,
                "X-Titan-Role": role,
                "Authorization": "Bearer " + token
            }
        });
        const res = await resp.json();
        if (!resp.ok || !res.success) {
            throw new Error(res.detail || res.message || "Không thể tải từ Google Sheet.");
        }
        await loadMsdsChemicalsList();
        alert(`✅ ${res.message || "Đã hòa giải dữ liệu từ Google Sheet thành công!"}`);
    } catch (err) {
        alert("Lỗi tải từ Google Sheet: " + err.message);
    } finally {
        if (btnPull) {
            btnPull.disabled = false;
            btnPull.textContent = "⬇️ Tải Về Từ Sheet (Restore)";
        }
    }
}
window.executeGasSyncFromSheet = executeGasSyncFromSheet;




// MSDS SMART PAGINATION HANDLERS (M3 Anti-Crash & Fast Rendering)
window.onMsdsPageChange = function(delta) {
    if (typeof window.CURRENT_MSDS_PAGE === "undefined") window.CURRENT_MSDS_PAGE = 1;
    window.CURRENT_MSDS_PAGE += delta;
    if (window.CURRENT_MSDS_PAGE < 1) window.CURRENT_MSDS_PAGE = 1;
    const activeSearch = (document.getElementById("msds-search-input")?.value || "").trim();
    renderMsdsFilteredTable(ALL_MSDS_CHEMICALS_CACHE, activeSearch);
};

window.onMsdsPageSizeChange = function(newSize) {
    window.CURRENT_MSDS_PAGE_SIZE = newSize;
    window.CURRENT_MSDS_PAGE = 1;
    const activeSearch = (document.getElementById("msds-search-input")?.value || "").trim();
    renderMsdsFilteredTable(ALL_MSDS_CHEMICALS_CACHE, activeSearch);
};


// ==============================================================================
// CHẾ ĐỘ THẺ LƯỚI (GRID CARD VIEW) CHO MSDS & EHS
// ==============================================================================
function renderMsdsCardGrid(items, totalCount, startIdx = 0) {
    const gridBody = document.getElementById("msds-grid-body");
    const gridEmpty = document.getElementById("msds-grid-empty");
    if (!gridBody) return;

    if (!items || items.length === 0) {
        gridBody.innerHTML = "";
        if (gridEmpty) gridEmpty.classList.remove("hidden");
        return;
    }
    if (gridEmpty) gridEmpty.classList.add("hidden");

    const isGuest = isGuestUser();
    let cardsHtml = "";

    items.forEach((item, localIdx) => {
        const index = startIdx + localIdx;
        const displayCode = item.product_code || item.chem_id || "CHM";
        const safeChemId = escapeHtml(item.chem_id || displayCode);
        const nameVi = item.product_name_vi || item.product_name || "Hóa chất công nghiệp";
        const nameOrig = item.product_name_original || "";
        const casNo = item.cas_numbers || item.cas_primary || "Hỗn hợp";
        const supplier = item.manufacturer_supplier || item.manufacturer || "Chưa cập nhật";
        const driveFileId = item.drive_file_id || "";
        const srcFileName = item.source_file || `MSDS-${displayCode}.pdf`;

        const isFinished = (item.item_type || "").toLowerCase() === "finished_product";
        const typeBadge = isFinished
            ? `<span class="msds-type-badge type-finished">🏷️ Thành phẩm</span>`
            : `<span class="msds-type-badge type-raw">🧪 Nguyên liệu</span>`;

        // Check if revision date expired > 3 years
        const revDate = item.revision_date || "";
        let expiredBadge = "";
        const m = revDate.match(/\b(19\d\d|20\d\d)\b/);
        const curYear = new Date().getFullYear();
        if (!m || (curYear - parseInt(m[1]) >= 3)) {
            expiredBadge = `<span class="msds-expired-pill" title="Tài liệu MSDS cần cập nhật định kỳ (> 3 năm)">⏳ Cần cập nhật</span>`;
        }

        // GHS Badges
        const rawGhs = String(item.ghs_symbols || "").trim();
        let ghsCodes = rawGhs.split(/[,;]+/).map(s => s.trim()).filter(Boolean);
        if (ghsCodes.length === 0 || rawGhs.toUpperCase().includes("NON DG")) {
            ghsCodes = ["NON DG"];
        }
        const ghsBadges = ghsCodes.map(c => renderGhsTableBadge(c)).join("");

        // Language tag
        const isEn = srcFileName.toLowerCase().includes("-en") || (nameOrig && !nameVi);
        const langBadge = isEn ? `<span class="msds-lang-badge lang-en">EN</span>` : `<span class="msds-lang-badge lang-vn">VN</span>`;

        cardsHtml += `
            <div class="msds-chem-card" data-chem-id="${safeChemId}">
                <!-- Card Header -->
                <div class="msds-card-head">
                    <div class="msds-card-badges-row">
                        <span class="msds-code-badge" onclick="openMsdsDriveViewer('${safeChemId}', '${escapeHtml(driveFileId)}', '${escapeHtml(srcFileName)}')">${escapeHtml(displayCode)}</span>
                        ${typeBadge}
                        ${langBadge}
                        ${expiredBadge}
                    </div>
                    <span class="msds-card-stt">#${index + 1}</span>
                </div>

                <!-- Card Body -->
                <div class="msds-card-content" onclick="openMsdsDriveViewer('${safeChemId}', '${escapeHtml(driveFileId)}', '${escapeHtml(srcFileName)}')">
                    <h4 class="msds-card-title">${escapeHtml(nameVi)}</h4>
                    ${nameOrig && nameOrig !== nameVi ? `<div class="msds-card-orig-name">${escapeHtml(nameOrig)}</div>` : ''}
                    <div class="msds-card-meta-row">
                        <div class="msds-card-meta-item">
                            <span class="msds-meta-k">CAS:</span>
                            <span class="msds-cas-pill">${escapeHtml(casNo)}</span>
                        </div>
                        <div class="msds-card-meta-item msds-meta-supplier" title="${escapeHtml(supplier)}">
                            <span class="msds-meta-k">NSX:</span>
                            <span class="msds-meta-v">${escapeHtml(supplier)}</span>
                        </div>
                    </div>
                    <!-- GHS Badges -->
                    <div class="msds-card-ghs-strip">
                        ${ghsBadges}
                    </div>
                    <!-- Quick PPE Icons -->
                    <div class="msds-card-ppe-quick" title="Trang bị bảo hộ: Kính mắt, Găng tay, Mặt nạ, Ủng bảo hộ">
                        <span class="msds-card-ppe-ico">🥽</span>
                        <span class="msds-card-ppe-ico">🧤</span>
                        <span class="msds-card-ppe-ico">😷</span>
                        <span class="msds-card-ppe-ico">🥾</span>
                        <span class="msds-card-ppe-txt">Bảo hộ bắt buộc</span>
                    </div>
                </div>

                <!-- Card Footer Actions -->
                <div class="msds-card-foot">
                    <div class="msds-card-btns-grid">
                        <button type="button" class="msds-card-btn btn-view" onclick="openMsdsDriveViewer('${safeChemId}', '${escapeHtml(driveFileId)}', '${escapeHtml(srcFileName)}')">
                            <span>👁️ Xem Trực Tiếp</span>
                        </button>
                        <button type="button" class="msds-card-btn btn-qr" onclick="openMsdsQrModal('${safeChemId}')" title="Mã QR dán thùng / nhãn kho">
                            <span>📱 QR</span>
                        </button>
                        <button type="button" class="msds-card-btn btn-card" onclick="openMsdsSafetyModal('${safeChemId}')" title="Thẻ an toàn khẩn cấp chuẩn 16 mục">
                            <span>📄 Thẻ An Toàn</span>
                        </button>
                        <a href="/api/msds/download-original/${encodeURIComponent(safeChemId)}" download="${escapeHtml(srcFileName)}" class="msds-card-btn btn-dl" title="Tải tệp MSDS gốc">
                            <span>📥 Tải File</span>
                        </a>
                    </div>
                    <!-- Action Row: Workflow Chaining -->
                    <div class="msds-card-chain-links">
                        <button type="button" class="msds-btn-chain-chip" onclick="msdsSendToAi('${safeChemId}')" title="Dịch hoặc tóm tắt bằng AI">
                            🤖 Dịch AI
                        </button>
                        <button type="button" class="msds-btn-chain-chip" onclick="msdsSendToGatepass('${safeChemId}')" title="Tạo phiếu xuất kho">
                            📦 Xuất kho
                        </button>
                        <button type="button" class="msds-btn-chain-chip" onclick="msdsSendToPdfTool('${safeChemId}', 'watermark')" title="Đóng dấu kiểm soát">
                            🏷️ Đóng dấu
                        </button>
                    </div>
                </div>
            </div>
        `;
    });

    gridBody.innerHTML = cardsHtml;
}

// ==============================================================================
// SLIDE-OVER IN-APP GOOGLE DRIVE & EMERGENCY SAFETY VIEWER
// ==============================================================================
async function openMsdsDriveViewer(chemId, driveFileId = "", filename = "") {
    CURRENT_DRAWER_CHEM_ID = chemId;
    const backdrop = document.getElementById("msds-slideover-backdrop");
    const drawer = document.getElementById("msds-slideover-drawer");
    const codeEl = document.getElementById("drawer-chem-code");
    const casEl = document.getElementById("drawer-chem-cas");
    const nameEl = document.getElementById("drawer-chem-name");
    const langEl = document.getElementById("drawer-chem-lang");
    const typeEl = document.getElementById("drawer-chem-type");
    const newtabBtn = document.getElementById("drawer-btn-newtab");
    const dlBtn = document.getElementById("drawer-btn-download");
    const iframe = document.getElementById("msds-drawer-iframe");
    const spinner = document.getElementById("msds-drawer-spinner");
    const noticeEl = document.getElementById("msds-drawer-notice");

    if (!backdrop || !drawer) return;
    backdrop.classList.remove("hidden");

    if (codeEl) codeEl.textContent = chemId;
    if (nameEl) nameEl.textContent = "Đang tải dữ liệu...";
    if (casEl) casEl.textContent = "CAS: ...";
    if (spinner) spinner.classList.remove("hidden");
    if (noticeEl) noticeEl.classList.add("hidden");

    // Fetch chemical details
    let chemObj = ALL_MSDS_CHEMICALS_CACHE.find(c => (c.chemical_id === chemId || c.chem_id === chemId || c.product_code === chemId));

    try {
        const detailResp = await fetch(`/api/msds/detail/${encodeURIComponent(chemId)}`);
        if (detailResp.ok) {
            const res = await detailResp.json();
            if (res.data && res.data.chemical) {
                chemObj = res.data.chemical;
            }
        }
    } catch (_) {}

    if (chemObj) {
        const displayCode = chemObj.product_code || chemObj.chem_id || chemId;
        const chemName = chemObj.product_name_vi || chemObj.product_name || "Hóa chất";
        const casNo = chemObj.cas_numbers || chemObj.cas_primary || "Hỗn hợp";
        const actualFileId = driveFileId || chemObj.drive_file_id || "";
        const actualSrc = filename || chemObj.source_file || `MSDS-${displayCode}.pdf`;

        if (codeEl) codeEl.textContent = displayCode;
        if (nameEl) nameEl.textContent = chemName;
        if (casEl) casEl.textContent = `CAS: ${casNo}`;

        if (typeEl) {
            const isFin = (chemObj.item_type || "").toLowerCase() === "finished_product";
            typeEl.className = isFin ? "msds-type-badge type-finished" : "msds-type-badge type-raw";
            typeEl.textContent = isFin ? "🏷️ Thành phẩm" : "🧪 Nguyên liệu";
        }

        if (langEl) {
            const isEn = actualSrc.toLowerCase().includes("-en") || (!chemObj.product_name_vi && chemObj.product_name_original);
            langEl.className = isEn ? "msds-lang-badge lang-en" : "msds-lang-badge lang-vn";
            langEl.textContent = isEn ? "EN" : "VN";
        }

        // Fill PPE strip
        const eyeEl = document.getElementById("drawer-ppe-eye");
        const handEl = document.getElementById("drawer-ppe-hand");
        const respEl = document.getElementById("drawer-ppe-resp");
        const skinEl = document.getElementById("drawer-ppe-skin");
        const emergSpillEl = document.getElementById("drawer-emerg-spill");
        const emergFaEl = document.getElementById("drawer-emerg-firstaid");

        if (eyeEl) eyeEl.textContent = chemObj.eye_protection || "Kính bảo hộ chống văng hóa chất";
        if (handEl) handEl.textContent = chemObj.hand_protection || "Găng tay chịu hóa chất (Nitrile/Butyl)";
        if (respEl) respEl.textContent = chemObj.respiratory_protection || "Mặt nạ phòng độc phin lọc hữu cơ/vô cơ";
        if (skinEl) skinEl.textContent = chemObj.skin_protection || "Ủng cao su, yếm chống hóa chất";
        if (emergSpillEl) emergSpillEl.textContent = chemObj.spill_measures || chemObj.fire_measures || "Thu gom bằng cát khô / chất thấm trơ, cách ly nguồn nhiệt.";
        if (emergFaEl) emergFaEl.textContent = chemObj.first_aid_eyes || chemObj.first_aid_inhalation || "Rửa mắt/da 15 phút dưới vòi nước chảy, đưa nạn nhân ra nơi thoáng khí.";

        // Viewer URLs
        let viewerUrl = "";
        let directDlUrl = "";
        let newTabUrl = "";

        if (actualFileId) {
            viewerUrl = `https://drive.google.com/file/d/${encodeURIComponent(actualFileId)}/preview`;
            directDlUrl = `https://drive.google.com/uc?export=download&id=${encodeURIComponent(actualFileId)}`;
            newTabUrl = `https://drive.google.com/file/d/${encodeURIComponent(actualFileId)}/view`;
            if (noticeEl) noticeEl.classList.remove("hidden");
        } else {
            viewerUrl = `/api/msds/download-original/${encodeURIComponent(chemId)}`;
            directDlUrl = `/api/msds/download-original/${encodeURIComponent(chemId)}`;
            newTabUrl = `/api/msds/download-original/${encodeURIComponent(chemId)}`;
        }

        if (newtabBtn) newtabBtn.href = newTabUrl;
        if (dlBtn) {
            dlBtn.href = directDlUrl;
            dlBtn.setAttribute("download", actualSrc);
        }

        if (iframe) {
            iframe.src = viewerUrl;
        }
    }
}

function closeMsdsDriveViewer() {
    const backdrop = document.getElementById("msds-slideover-backdrop");
    const iframe = document.getElementById("msds-drawer-iframe");
    if (backdrop) backdrop.classList.add("hidden");
    if (iframe) iframe.src = "about:blank";
    CURRENT_DRAWER_CHEM_ID = null;
}

function onMsdsIframeLoaded() {
    const spinner = document.getElementById("msds-drawer-spinner");
    if (spinner) spinner.classList.add("hidden");
}

// ==============================================================================
// LIÊN THÔNG CÔNG CỤ (WORKFLOW CHAINING) TỪ MSDS
// ==============================================================================
async function msdsSendToAi(chemId) {
    if (!chemId) return;
    closeMsdsDriveViewer();
    const chem = ALL_MSDS_CHEMICALS_CACHE.find(c => c.chemical_id === chemId || c.chem_id === chemId) || { chemical_id: chemId };
    const name = chem.product_name_vi || chem.product_name || chem.product_code || chemId;
    const cas = chem.cas_numbers || chem.cas_primary || "Hỗn hợp";
    const code = chem.product_code || chemId;

    if (typeof switchMainTab === "function") {
        switchMainTab("ai", "translate");
        setTimeout(() => {
            const input = document.getElementById("ai-input-text");
            if (input) {
                input.value = `Vui lòng tóm tắt đầy đủ 16 mục GHS và dịch thuật các biện pháp an toàn bắt buộc cho hóa chất:
Tên hóa chất: ${name}
Mã SP: ${code}
Số CAS: ${cas}
Yêu cầu: Định dạng song ngữ đối chiếu Tiếng Việt - Tiếng Anh rõ ràng.`;
                input.focus();
            }
            if (typeof showSafetyToast === "function") {
                showSafetyToast(`✓ Đã nạp thông tin [${name}] vào AI Studio!`, 3500);
            }
        }, 150);
    }
}

async function msdsSendToGatepass(chemId) {
    if (!chemId) return;
    closeMsdsDriveViewer();
    const chem = ALL_MSDS_CHEMICALS_CACHE.find(c => c.chemical_id === chemId || c.chem_id === chemId) || { chemical_id: chemId };
    const name = chem.product_name_vi || chem.product_name || chem.product_code || chemId;
    const code = chem.product_code || chemId;
    const cas = chem.cas_numbers || chem.cas_primary || "";

    if (typeof switchMainTab === "function") {
        switchMainTab("gatepass");
        setTimeout(() => {
            if (window.GatePassStudio && typeof window.GatePassStudio.addCustomItem === "function") {
                window.GatePassStudio.addCustomItem({
                    loai_hang_hoa: `${name} (${code})`,
                    quy_cach: "25kg/can hoặc 200kg/phuy",
                    sl_kien: "1",
                    sl_thung: "1",
                    khoi_luong_kg: "25.0",
                    ghi_chu: `Hóa chất CAS: ${cas || 'Theo hồ sơ'}`
                });
            } else if (typeof addGatePassItemRow === "function") {
                addGatePassItemRow({
                    loai_hang_hoa: `${name} (${code})`,
                    quy_cach: "25kg/can",
                    sl_kien: "1",
                    sl_thung: "1",
                    khoi_luong_kg: "25.0",
                    ghi_chu: `CAS: ${cas || 'MSDS'}`
                });
            }
            if (typeof showSafetyToast === "function") {
                showSafetyToast(`✓ Đã thêm hóa chất [${name}] vào Phiếu Xuất Kho!`, 3500);
            }
        }, 180);
    }
}

async function msdsSendToPdfTool(chemId, toolId) {
    if (!chemId) return;
    closeMsdsDriveViewer();
    if (typeof showSafetyToast === "function") {
        showSafetyToast("⏳ Đang chuẩn bị tệp MSDS gốc...", 2500);
    }

    try {
        const resp = await fetch(`/api/msds/download-original/${encodeURIComponent(chemId)}`);
        if (!resp.ok) throw new Error("Không thể tải tệp MSDS gốc.");
        const blob = await resp.blob();

        const chem = ALL_MSDS_CHEMICALS_CACHE.find(c => c.chemical_id === chemId || c.chem_id === chemId) || {};
        const filename = chem.source_file || `MSDS-${chemId}.pdf`;
        const file = new File([blob], filename, { type: blob.type || "application/pdf" });

        if (typeof openTool === "function") {
            await openTool(toolId);
            setTimeout(() => {
                if (typeof handleFileSelection === "function") {
                    handleFileSelection([file]);
                }
                if (typeof showSafetyToast === "function") {
                    showSafetyToast(`✓ Đã nạp tệp MSDS vào công cụ [${toolId.toUpperCase()}]!`, 3500);
                }
            }, 200);
        }
    } catch (err) {
        console.error("Lỗi chuyển tiếp PDF:", err);
        alert("Không thể chuyển tiếp tệp PDF: " + err.message);
    }
}

// ==============================================================================
// SAO LƯU & KHÔI PHỤC CSDL MSDS (.JSON)
// ==============================================================================
function exportMsdsCatalogJson() {
    window.location.href = "/api/msds/export-json";
    if (typeof showSafetyToast === "function") {
        showSafetyToast("💾 Đang tải tệp sao lưu JSON danh mục MSDS...", 3000);
    }
}

async function importMsdsCatalogJson(event) {
    const file = event?.target?.files?.[0];
    if (!file) return;

    if (isGuestUser()) {
        alert("Khách (Guest) không có quyền nhập CSDL.");
        return;
    }

    if (!confirm(`Bạn có chắc chắn muốn nhập danh mục hóa chất từ tệp "${file.name}" vào CSDL?`)) {
        event.target.value = "";
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
        if (typeof showSafetyToast === "function") {
            showSafetyToast("⏳ Đang nhập danh mục MSDS vào hệ thống...", 4000);
        }
        const resp = await fetch("/api/msds/import-json", {
            method: "POST",
            body: formData
        });
        const res = await resp.json();
        if (!resp.ok || !res.success) {
            throw new Error(res.detail || res.error || "Không thể nhập dữ liệu JSON.");
        }
        alert(`✅ ${res.message}`);
        await loadMsdsChemicalsList();
    } catch (err) {
        alert("Lỗi nhập tệp JSON: " + err.message);
    } finally {
        event.target.value = "";
    }
}

// ==============================================================================
// DEEP-LINKING SUPPORT (URL PARAMETERS & HASH)
// ==============================================================================
window.addEventListener("DOMContentLoaded", () => {
    try {
        const params = new URLSearchParams(window.location.search);
        const hash = window.location.hash || "";
        const targetTab = params.get("tab") || (hash.includes("msds") ? "msds" : null);
        const targetId = params.get("id") || (hash.match(/#msds-detail-([^&]+)/)?.[1]);

        if (targetTab === "msds" && typeof switchMainTab === "function") {
            switchMainTab("msds");
            if (targetId) {
                setTimeout(() => {
                    openMsdsDriveViewer(targetId);
                }, 400);
            }
        }
    } catch (_) {}
});


async function sanitizeMsdsCatalogWithAi() {
    if (isGuestUser()) {
        alert("Chức năng chỉ dành cho Quản trị viên (Admin).");
        return;
    }
    if (!confirm("Hệ thống AI sẽ quét toàn bộ Sổ CIL để sửa các tên hóa chất chung chung ('Hóa chất FTU0005', 'A1935'...) và làm sạch trường Nhà cung cấp (loại bỏ '- Product Name', 'Address:...').\n\nBạn có muốn tiếp tục?")) {
        return;
    }
    try {
        showMsdsLoading("Đang quét & chuẩn hóa Sổ CIL bằng AI...");
        const token = sessionStorage.getItem("luv_auth_token") || localStorage.getItem("luv_auth_token") || "verified";
        const role = sessionStorage.getItem("luv_user_role") || "owner";
        const resp = await fetch("/api/msds/sanitize-catalog", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Titan-Session": token,
                "X-Titan-Role": role,
                "Authorization": "Bearer " + token
            }
        });
        const res = await resp.json();
        if (!resp.ok || !res.success) throw new Error(res.detail || res.message || "Lỗi chuẩn hóa CIL.");
        await loadMsdsChemicalsList();

        // Tự động gọi POST (action: 'bulk_sync') để lưu toàn bộ thông tin đã chuẩn hóa lên Google Sheets
        if (window.MsdsGasSync && window.MsdsGasSync.getUrl() && ALL_MSDS_CHEMICALS_CACHE.length > 0) {
            await window.MsdsGasSync.bulkSync(ALL_MSDS_CHEMICALS_CACHE);
        }

        alert("✅ " + (res.message || "Đã chuẩn hóa Sổ CIL thành công!"));
    } catch (err) {
        alert("❌ " + err.message);
    } finally {
        hideMsdsLoading();
    }
}
window.sanitizeMsdsCatalogWithAi = sanitizeMsdsCatalogWithAi;

function openCurrentModalDriveViewer() {
    if (!window.CURRENT_SAFETY_MODAL_CHEM_ID) return;
    const chem = window.CURRENT_SAFETY_MODAL_CHEM || {};
    const chemId = window.CURRENT_SAFETY_MODAL_CHEM_ID;
    const driveFileId = chem.drive_file_id || "";
    const filename = chem.source_file || `MSDS-${chemId}.pdf`;
    openMsdsDriveViewer(chemId, driveFileId, filename);
}
window.openCurrentModalDriveViewer = openCurrentModalDriveViewer;
