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

function initAiStudio() {
    // Load saved DeepSeek API key from localStorage
    const savedKey = localStorage.getItem("deepseek_api_key") || "";
    const keyInput1 = document.getElementById("ai-deepseek-key");
    const keyInput2 = document.getElementById("ai-sum-key");
    if (keyInput1 && savedKey) keyInput1.value = savedKey;
    if (keyInput2 && savedKey) keyInput2.value = savedKey;

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
    const keyBox = document.getElementById("ai-deepseek-key-box");
    if (keyBox) {
        if (engine === "deepseek") {
            keyBox.classList.remove("hidden");
        } else {
            keyBox.classList.add("hidden");
        }
    }
}

function saveAiDeepSeekKey() {
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

    const textToTranslate = input.value.trim();
    const srcLang = document.getElementById("ai-trans-src-lang")?.value || "auto";
    const tgtLang = document.getElementById("ai-trans-tgt-lang")?.value || "vi";
    const engine = document.getElementById("ai-trans-engine-select")?.value || "google";
    const apiKey = document.getElementById("ai-deepseek-key")?.value.trim() || localStorage.getItem("deepseek_api_key") || "";

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
    const keyGrp = document.getElementById("ai-sum-key-group");
    if (keyGrp) {
        if (engine === "deepseek") {
            keyGrp.classList.remove("hidden");
        } else {
            keyGrp.classList.add("hidden");
        }
    }
}

function saveAiSumKey() {
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

    const mode = document.getElementById("ai-sum-mode")?.value || "executive";
    const length = document.getElementById("ai-sum-length")?.value || "medium";
    const engine = document.getElementById("ai-sum-engine")?.value || "deepseek";
    const apiKey = document.getElementById("ai-sum-key")?.value.trim() || localStorage.getItem("deepseek_api_key") || "";

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
        } else if (upper.includes("TIỀN CHẤT") || upper.includes("ND28-IV")) {
            badgeClass = "badge-precursor";
            icon = "⚡";
            titleDesc = "Tiền chất ma túy / công nghiệp theo NĐ 28/2026/NĐ-CP (Cần lập sổ theo dõi & báo cáo)";
        } else if (upper.includes("HẠN CHẾ") || upper.includes("CẤM") || upper.includes("ND28-I") || upper.includes("ND28-II")) {
            badgeClass = "badge-restricted";
            icon = "🚫";
            titleDesc = "Hóa chất cấm hoặc hạn chế sản xuất, kinh doanh";
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
    if (CURRENT_MSDS_FILES.length === 0) {
        alert("Vui lòng chọn hoặc kéo thả tệp MSDS / SDS (.pdf, .docx, .doc, .txt) vào khung nạp trước!");
        document.getElementById("msds-file-input")?.click();
        return;
    }

    const engine = document.getElementById("msds-ai-engine")?.value || "deepseek";
    const apiKey = localStorage.getItem("deepseek_api_key") || "";

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

async function loadMsdsChemicalsList(query = "") {
    const tbody = document.getElementById("msds-table-body");
    if (!tbody) return;

    try {
        // Nạp song song CSDL hóa chất và CSDL đối soát pháp lý
        const [respMsds] = await Promise.all([
            fetch("/api/msds/list"),
            preloadCilLegalMatches()
        ]);
        const res = await respMsds.json();

        if (!respMsds.ok || !res.success) {
            throw new Error(res.error || "Không thể tải danh sách hóa chất.");
        }

        ALL_MSDS_CHEMICALS_CACHE = res.data || [];
        updateMsdsKpiStats(ALL_MSDS_CHEMICALS_CACHE);

        const activeSearch = query || (document.getElementById("msds-search-input")?.value || "").trim();
        renderMsdsFilteredTable(ALL_MSDS_CHEMICALS_CACHE, activeSearch);
    } catch (err) {
        console.error("loadMsdsChemicalsList error:", err);
    }
}

function renderMsdsFilteredTable(sourceItems, searchQuery = "") {
    const tbody = document.getElementById("msds-table-body");
    const emptyNotice = document.getElementById("msds-table-empty");
    const showingCountEl = document.getElementById("msds-showing-count");
    if (!tbody) return;

    const q = (searchQuery || "").toLowerCase();

    // Lọc theo GHS pill + Item Type (Nguyên liệu vs Thành phẩm) + Search text
    const filtered = (sourceItems || []).filter(item => {
        const rawGhs = String(item.ghs_symbols || "").trim().toUpperCase();
        const isNonDg = !rawGhs || rawGhs.includes("NON DG") || rawGhs.includes("NONDG") || rawGhs === "NONE";

        if (CURRENT_MSDS_GHS_FILTER === "NON DG" && !isNonDg) return false;
        if (CURRENT_MSDS_GHS_FILTER === "HAZARD" && isNonDg) return false;
        if (CURRENT_MSDS_GHS_FILTER.startsWith("GHS") && !rawGhs.includes(CURRENT_MSDS_GHS_FILTER)) return false;

        // Lọc theo item_type
        if (CURRENT_MSDS_ITEM_TYPE_FILTER !== "all") {
            const rawType = String(item.item_type || "raw_material").trim().toLowerCase();
            if (rawType !== CURRENT_MSDS_ITEM_TYPE_FILTER.toLowerCase()) {
                return false;
            }
        }

        if (!q) return true;
        const haystack = [
            item.product_code,
            item.chem_id,
            item.product_name,
            item.cas_numbers,
            item.manufacturer_supplier,
            item.manufacturer,
            item.intended_use,
            item.ghs_symbols,
            item.source_file,
            item.item_type,
            item.mother_msds_id
        ].map(v => String(v || "").toLowerCase()).join(" ");
        return haystack.includes(q);
    });

    CURRENT_FILTERED_MSDS = filtered;
    if (showingCountEl) {
        showingCountEl.textContent = `Hiển thị ${filtered.length} / ${(sourceItems || []).length} hóa chất`;
    }

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
    filtered.forEach((item, index) => {
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

        const subInfoParts = [];
        if (item.product_code && item.product_code !== item.chem_id) {
            subInfoParts.push(`Mã SP: <b>${escapeHtml(item.product_code)}</b>`);
        }
        if (item.intended_use) subInfoParts.push(escapeHtml(item.intended_use));
        if (item.revision_date) subInfoParts.push("Cập nhật: " + escapeHtml(item.revision_date));
        const subInfoHtml = subInfoParts.length > 0 ? subInfoParts.join(" · ") : "Hóa chất công nghiệp";

        const srcFileName = item.source_file || `MSDS-${displayCode}.docx`;
        const downloadOriginalUrl = `/api/msds/download-original/${encodeURIComponent(item.chem_id || displayCode)}`;
        const exportWordDocxUrl = `/api/msds/export-safety-card/${encodeURIComponent(item.chem_id || displayCode)}`;
        const isSelected = SELECTED_MSDS_IDS.has(safeChemId);

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
                    <div class="msds-chem-title" onclick="openMsdsSafetyModal('${safeChemId}')">${escapeHtml(item.product_name || "N/A")}</div>
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
                    <a href="${downloadOriginalUrl}" download class="msds-dl-file-btn" title="Tải tệp MSDS gốc: ${escapeHtml(srcFileName)}">
                        <span>📥 Tải MSDS Gốc</span>
                    </a>
                    <div class="msds-file-caption" title="${escapeHtml(srcFileName)}">${escapeHtml(srcFileName)}</div>
                </td>
                <td class="msds-col-actions">
                    <div class="msds-action-group">
                        <button type="button" class="msds-btn-view-card" onclick="openMsdsSafetyModal('${safeChemId}')" title="Xem Thẻ An Toàn Hóa Chất Khẩn Cấp">
                            <span>👁️ Thẻ An Toàn</span>
                        </button>
                        <a href="${exportWordDocxUrl}" download="SafetyCard_${escapeHtml(displayCode)}.docx" class="msds-btn-export-docx" title="Xuất Thẻ An Toàn Word (.docx) chuẩn Mục 3 GHS có Checksum">
                            <span>📄 Xuất Word</span>
                        </a>
                        <button type="button" class="msds-btn-del-row" onclick="deleteMsdsChemical('${safeChemId}')" title="Xóa hóa chất này khỏi sổ CIL">
                            🗑️
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });
    tbody.innerHTML = html;
    updateMsdsBatchActionBar();
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
        if (btnDownloadOriginal) {
            btnDownloadOriginal.href = `/api/msds/download-original/${encodeURIComponent(chem.chem_id || codeDisplay)}`;
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
                const sourceBadge = ob.source_id === "ND28"
                    ? `<span style="font-size:10.5px; font-weight:800; background:#fff7ed; color:#ea580c; border:1px solid #fed7aa; padding:2px 6px; border-radius:4px;">NĐ 28/2026/NĐ-CP</span>`
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
                            <span>⚖️ BẢNG NGHĨA VỤ PHÁP LÝ & TUÂN THỦ (LUẬT HÓA CHẤT 2026)</span>
                            <span style="font-size:11px; font-weight:800; background:#fef2f2; color:#b91c1c; border:1px solid #fecdd3; padding:2px 7px; border-radius:4px;">
                                ${legal.total_regulated_components || legal.obligations.length} HOẠT CHẤT ĐƯỢC ĐIỀU CHỈNH
                            </span>
                        </div>
                        <div style="font-size:11px; color:#64748b;">Căn cứ NĐ 24/2026/NĐ-CP · NĐ 28/2026/NĐ-CP · QCVN 01:2025/BYT</div>
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
                            Sản phẩm không chứa hoạt chất thuộc diện Cấm, Hạn chế, Tiền chất ma túy (NĐ 28/2026/NĐ-CP) hay Kiểm soát đặc biệt (NĐ 24/2026/NĐ-CP). Doanh nghiệp áp dụng quy trình an toàn lao động và lập sổ lưu trữ hóa chất thông thường.
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
    if (!confirm(`Bạn có chắc chắn muốn xóa mã hóa chất "${chemId}" khỏi Danh mục Hóa chất CIL?`)) {
        return;
    }

    try {
        const resp = await fetch(`/api/msds/delete/${encodeURIComponent(chemId)}`, {
            method: "DELETE"
        });
        const res = await resp.json();
        if (!resp.ok || !res.success) {
            throw new Error(res.error || "Không thể xóa hóa chất.");
        }
        SELECTED_MSDS_IDS.delete(chemId);
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
    const ids = Array.from(SELECTED_MSDS_IDS);
    if (ids.length === 0) {
        alert("Vui lòng chọn ít nhất một hóa chất để xóa.");
        return;
    }

    if (!confirm(`Bạn có chắc chắn muốn xóa ${ids.length} hóa chất đã chọn khỏi Sổ CIL không?\n\n⚠️ Lưu ý: Thao tác này sẽ xóa vĩnh viễn dữ liệu và không thể hoàn tác!`)) {
        return;
    }

    try {
        const resp = await fetch("/api/msds/delete-batch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
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

function openMsdsDeleteAllModal() {
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

    if (pwd !== "270120") {
        if (errDiv) errDiv.classList.remove("hidden");
        if (errTxt) errTxt.textContent = "Mật khẩu xác nhận không chính xác! Thao tác bị từ chối.";
        if (pwdInp) {
            pwdInp.select();
            pwdInp.focus();
        }
        return;
    }

    const btnConfirm = document.getElementById("btn-confirm-delete-all");
    try {
        if (btnConfirm) {
            btnConfirm.disabled = true;
            btnConfirm.textContent = "⏳ Đang xóa sạch CSDL...";
        }

        const resp = await fetch("/api/msds/delete-all", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ password: pwd })
        });
        const res = await resp.json();
        if (!resp.ok || !res.success) {
            throw new Error(res.detail || res.message || "Không thể xóa toàn bộ CSDL.");
        }

        closeMsdsDeleteAllModal();
        clearMsdsSelection();
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

async function openMsdsStorageFolder() {
    try {
        const resp = await fetch("/api/msds/open-storage-folder", { method: "POST" });
        const res = await resp.json();
        if (!resp.ok || !res.success) {
            throw new Error(res.detail || res.error || "Không thể mở thư mục lưu trữ MSDS.");
        }
    } catch (err) {
        alert("Lỗi mở thư mục lưu trữ MSDS: " + err.message);
    }
}

async function syncMsdsToGoogleDrive() {
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
