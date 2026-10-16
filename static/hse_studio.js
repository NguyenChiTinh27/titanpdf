// ==========================================================================
// HSE REPORT STUDIO · CLIENT ARCHITECTURE & STATE MACHINE
// TitanPDF Integrated Module · Offline & DeepSeek AI Assisted
// ==========================================================================

(function() {
  "use strict";

  // Factory Department Taxonomy (ZhanChen Standard)
  const DEPARTMENTS = {
    "san-xuat": { vi: "Sản xuất", zh: "生产部", icon: "🏭" },
    "ban-hang": { vi: "Bán hàng", zh: "营业部", icon: "🛒" },
    "ky-thuat": { vi: "Kỹ thuật", zh: "技术部", icon: "🧪" },
    "kho": { vi: "Kho hàng", zh: "仓储部", icon: "📦" },
    "bao-tri": { vi: "Bảo trì", zh: "维修部", icon: "🔧" },
    "hanh-chinh": { vi: "Hành chính", zh: "行政部", icon: "🏢" }
  };

  // Standard 26 Checklist Items Schema (ZhanChen Factory 5-Category Baseline)
  const DEFAULT_SECTIONS = [
    {
      category: "PCCC & Thoát hiểm",
      title: "I. PHÒNG CHÁY CHỮA CHÁY & THOÁT HIỂM (消防与安全疏散)",
      items: [
        { row: 3, category: "PCCC", content: "Bình chữa cháy còn hạn kiểm định, đồng hồ áp suất kim chỉ vạch xanh, niêm phong chì nguyên vẹn.", method: "Kiểm tra trực quan" },
        { row: 4, category: "PCCC", content: "Lối tiếp cận bình chữa cháy và họng nước vách tường thông thoáng, không bị che chắn tối thiểu 0.8m.", method: "Đo đạc hiện trường" },
        { row: 5, category: "PCCC", content: "Hệ thống báo cháy tự động hoạt động, đầu báo khói/nhiệt không bị che lấp hoặc hư hỏng.", method: "Kiểm tra đèn tín hiệu" },
        { row: 6, category: "PCCC", content: "Đèn chiếu sáng sự cố khẩn cấp và đèn Exit thoát hiểm sáng tốt khi cúp điện.", method: "Nhấn nút test" },
        { row: 7, category: "PCCC", content: "Cửa thoát hiểm mở một chiều theo hướng thoát nạn, không bị khóa then cài hay chốt chặn.", method: "Đẩy thử cửa" },
        { row: 8, category: "PCCC", content: "Lối thoát nạn, hành lang, cầu thang thoát hiểm thông thoáng, không chứa hàng hóa, pallet.", method: "Quan sát hiện trường" },
        { row: 9, category: "PCCC", content: "Sơ đồ chỉ dẫn thoát hiểm được niêm yết tại các vị trí dễ thấy của từng khu vực xưởng.", method: "Kiểm tra trực quan" },
        { row: 10, category: "PCCC", content: "Khu vực sạc xe nâng có bình bọt, biển cảnh báo nguy hiểm cháy nổ và trang bị đủ thông gió.", method: "Kiểm tra hiện trường" },
        { row: 11, category: "PCCC", content: "Không phát hiện hành vi hút thuốc lá hoặc mang lửa vào khu vực cấm lửa nhà xưởng.", method: "Tuần tra quan sát" },
        { row: 12, category: "PCCC", content: "Các họng nước cứu hỏa ngoài trời và van tiếp nước trụ tiếp cận thông suốt.", method: "Mở van kiểm tra" },
        { row: 13, category: "PCCC", content: "Khu vực kho chứa phế liệu cách xa khu vực sản xuất tối thiểu khoảng cách an toàn PCCC.", method: "Đo đạc kiểm tra" }
      ]
    },
    {
      category: "An toàn hóa chất",
      title: "II. AN TOÀN HÓA CHẤT & CHẤT THẢI NGUY HẠI (化学品及危废安全)",
      items: [
        { row: 15, category: "Hóa chất", content: "Thùng chứa dung môi, hóa chất đậy kín nắp, có khay chống tràn dung tích tối thiểu 110%.", method: "Kiểm tra khay tràn" },
        { row: 16, category: "Hóa chất", content: "Nhãn mác hóa chất đầy đủ biểu trưng GHS, cảnh báo nguy hại và mã nhận diện rõ ràng.", method: "Kiểm tra nhãn mác" },
        { row: 17, category: "Hóa chất", content: "Phiếu an toàn hóa chất (MSDS/SDS) niêm yết sẵn sàng tại nơi lưu trữ và sử dụng.", method: "Kiểm tra tài liệu" },
        { row: 18, category: "Hóa chất", content: "Trang bị bồn rửa mắt và vòi tắm khẩn cấp trong bán kính 10 giây tiếp cận, nước chảy sạch.", method: "Thử xả nước" },
        { row: 19, category: "Hóa chất", content: "Hóa chất không tương thích (axit/bazơ, chất oxy hóa/chất dễ cháy) lưu trữ cách ly an toàn.", method: "Đối chiếu bảng tương thích" },
        { row: 20, category: "Hóa chất", content: "Dụng cụ thấm hút ứng phó tràn đổ (cát, bông thấm, xẻng đồng) bố trí đầy đủ tại chỗ.", method: "Kiểm tra bộ kit tràn đổ" },
        { row: 21, category: "Hóa chất", content: "Khu vực kho phế thải nguy hại có mái che, rãnh thu gom và dán mã chất thải theo quy định.", method: "Kiểm tra kho危废" },
        { row: 22, category: "Hóa chất", content: "Công nhân thao tác tiếp xúc hóa chất mang đủ PPE chuyên dụng (găng nitrile, kính, mặt nạ).", method: "Quan sát thao tác" },
        { row: 23, category: "Hóa chất", content: "Khu vực pha chế dung môi được nối đất tiếp địa khử tĩnh điện hoàn chỉnh.", method: "Đo điện trở tiếp địa" }
      ]
    },
    {
      category: "An toàn điện",
      title: "III. AN TOÀN ĐIỆN & CƠ KHÍ THIẾT BỊ (电气及机械安全)",
      items: [
        { row: 25, category: "Điện", content: "Tủ điện đóng kín cửa, có khóa, có biển cảnh báo nguy hiểm điện và sơ đồ đấu nối một sợi.", method: "Kiểm tra tủ điện" },
        { row: 26, category: "Điện", content: "Dây dẫn điện không bị hở vỏ cách điện, không câu móc tạm bợ, có ống luồn bảo vệ cơ học.", method: "Kiểm tra đường dây" }
      ]
    },
    {
      category: "Thiết bị cơ khí",
      title: "IV. CHE CHẮN AN TOÀN TRUYỀN ĐỘNG & BẢO HỘ (机械防护与劳保)",
      items: [
        { row: 28, category: "Cơ khí", content: "Bộ phận truyền động máy khuấy, xích, đai dây curoa có nắp che chắn an toàn đầy đủ.", method: "Kiểm tra nắp che" },
        { row: 29, category: "Cơ khí", content: "Nút dừng khẩn cấp (Emergency Stop) trên máy móc thiết bị hoạt động nhạy bén.", method: "Nhấn thử dừng khẩn" }
      ]
    },
    {
      category: "Vệ sinh 5S",
      title: "V. VỆ SINH MÔI TRƯỜNG & 5S CÔNG NGHIỆP (现场卫生与5S)",
      items: [
        { row: 31, category: "5S", content: "Sàn thao tác sạch sẽ, không trơn trượt do dầu mỡ, không đọng nước hay dung môi rò rỉ.", method: "Kiểm tra mặt sàn" },
        { row: 32, category: "5S", content: "Dụng cụ, công cụ lao động sắp xếp ngăn nắp, đúng vạch kẻ định vị theo tiêu chuẩn 5S.", method: "Kiểm tra ô phân định" }
      ]
    }
  ];

  // Core Application State
  const state = {
    reportMode: "inspection", // "inspection" | "improvement"
    globalAiHint: "",
    metadata: {
      date: new Date().toISOString().substring(0, 10),
      prevDate: "",
      inspectors: "Ban HSE - ZhanChen Safety Team"
    },
    sections: DEFAULT_SECTIONS,
    checklist: new Map(),
    findings: [],
    previewMode: "findings", // "findings" | "checklist"
    writingTarget: null,
    writingOptions: [],
    currentReportId: "",
    autoSaveTimer: null
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  function escapeHtml(val = "") {
    return String(val).replace(/[&<>'"]/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
    }[c]));
  }

  function showToast(message, isError = false) {
    let toast = $("#hse-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "hse-toast";
      toast.className = "toast";
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.className = `toast show ${isError ? "error" : ""}`;
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => {
      if (toast) toast.className = "toast";
    }, 3500);
  }

  function setLoading(active, text = "Đang xử lý...") {
    let overlay = $("#loadingOverlay");
    if (overlay) {
      overlay.hidden = !active;
      const t = $("#loadingText");
      if (t) t.textContent = text;
    }
  }

  // ==========================================================================
  // INDEXEDDB PERSISTENCE (HseStudioDB · store: current_session · key: latest)
  // ==========================================================================
  const DB_NAME = "HseStudioDB";
  const STORE_NAME = "current_session";

  function initDb() {
    return new Promise((resolve) => {
      try {
        const req = indexedDB.open(DB_NAME, 1);
        req.onupgradeneeded = (e) => {
          const db = e.target.result;
          if (!db.objectStoreNames.contains(STORE_NAME)) {
            db.createObjectStore(STORE_NAME);
          }
        };
        req.onsuccess = (e) => resolve(e.target.result);
        req.onerror = () => resolve(null);
      } catch (e) {
        resolve(null);
      }
    });
  }

  async function saveSessionToDb(payload) {
    try {
      const db = await initDb();
      if (!db) return;
      const tx = db.transaction(STORE_NAME, "readwrite");
      tx.objectStore(STORE_NAME).put(payload, "latest");
      updateSaveIndicator("Đã tự lưu (Bao gồm ảnh)");
    } catch (err) {
      console.warn("IndexedDB auto-save warning:", err);
    }
  }

  async function loadSessionFromDb() {
    try {
      const db = await initDb();
      if (!db) return null;
      return new Promise((resolve) => {
        const tx = db.transaction(STORE_NAME, "readonly");
        const req = tx.objectStore(STORE_NAME).get("latest");
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => resolve(null);
      });
    } catch (e) {
      return null;
    }
  }

  function updateSaveIndicator(text) {
    const ind = $("#hse-save-status");
    if (ind) {
      ind.innerHTML = `<span class="hse-status-dot"></span>${escapeHtml(text)}`;
    }
  }

  // Auto-Save Debouncer (1000ms delay)
  function triggerAutoSave() {
    clearTimeout(state.autoSaveTimer);
    state.autoSaveTimer = setTimeout(async () => {
      const payload = makePayload();
      // 1. LocalStorage light sync: strip heavy base64 image data to prevent 5MB quota overflow
      try {
        const lightCopy = {
          ...payload,
          findings: payload.findings.map(f => ({
            ...f,
            imageData: "",
            imageAfterData: ""
          }))
        };
        localStorage.setItem("hse_studio_light_cache", JSON.stringify(lightCopy));
        localStorage.setItem("hse-report-studio-light", JSON.stringify(lightCopy));
      } catch (err) {
        console.warn("LocalStorage light sync exceeded:", err);
      }
      // 2. Full session with binary photos into IndexedDB
      await saveSessionToDb(payload);
    }, 1000);
  }

  // ==========================================================================
  // DATA PAYLOAD BUILDER & NORMALIZATION
  // ==========================================================================
  function makePayload() {
    const dateInput = $("#hse-inspection-date");
    const inspectorsInput = $("#hse-inspectors");
    const dateVal = dateInput ? dateInput.value : state.metadata.date;
    const inspectorsVal = inspectorsInput ? inspectorsInput.value : state.metadata.inspectors;

    return {
      id: state.currentReportId || `hse_${Date.now()}`,
      reportType: state.reportMode,
      globalAiHint: state.globalAiHint || "",
      metadata: {
        date: dateVal || new Date().toISOString().substring(0, 10),
        prevDate: state.metadata.prevDate || "",
        inspectors: inspectorsVal || "Ban HSE - ZhanChen"
      },
      checklist: [...state.checklist.values()].map(item => ({
        row: Number(item.row),
        status: item.status || "pass",
        issueVi: item.issueVi || "",
        issueZh: item.issueZh || "",
        improved: Boolean(item.improved)
      })),
      findings: state.findings.map(f => ({
        id: f.id,
        departmentKey: f.departmentKey || "san-xuat",
        departmentVi: f.departmentVi || "Sản xuất",
        departmentZh: f.departmentZh || "生产部",
        aiHint: f.aiHint || "",
        issueVi: f.issueVi || "",
        issueZh: f.issueZh || "",
        suggestion: f.suggestion || "",
        imageData: f.imageData || "",
        imageName: f.imageName || "",
        improved: Boolean(f.improved),
        imageAfterData: f.imageAfterData || "",
        imageAfterName: f.imageAfterName || ""
      }))
    };
  }

  function applyReportData(report) {
    if (!report) return;
    state.currentReportId = report.id || "";
    state.reportMode = report.reportType || "inspection";
    state.globalAiHint = report.globalAiHint || "";

    const globalHintInput = $("#hse-global-ai-hint");
    if (globalHintInput) globalHintInput.value = state.globalAiHint;

    state.metadata.date = report.metadata?.date || new Date().toISOString().substring(0, 10);
    state.metadata.prevDate = report.metadata?.prevDate || "";
    state.metadata.inspectors = report.metadata?.inspectors || "Ban HSE";

    const dateInput = $("#hse-inspection-date");
    if (dateInput) dateInput.value = state.metadata.date;
    const inspectorsInput = $("#hse-inspectors");
    if (inspectorsInput) inspectorsInput.value = state.metadata.inspectors;

    // Restore checklist map
    const savedChecklist = new Map((report.checklist || []).map(i => [Number(i.row), i]));
    for (const sec of state.sections) {
      for (const item of sec.items) {
        const row = Number(item.row);
        const existing = savedChecklist.get(row);
        state.checklist.set(row, {
          ...item,
          status: existing ? (existing.status || "pass") : "pass",
          issueVi: existing ? (existing.issueVi || "") : "",
          issueZh: existing ? (existing.issueZh || "") : "",
          improved: existing ? Boolean(existing.improved) : false
        });
      }
    }

    // Restore findings
    state.findings = (report.findings || []).map(f => ({
      id: f.id || `finding_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
      departmentKey: f.departmentKey || "san-xuat",
      departmentVi: f.departmentVi || DEPARTMENTS[f.departmentKey || "san-xuat"]?.vi || "Sản xuất",
      departmentZh: f.departmentZh || DEPARTMENTS[f.departmentKey || "san-xuat"]?.zh || "生产部",
      aiHint: f.aiHint || "",
      issueVi: f.issueVi || "",
      issueZh: f.issueZh || "",
      suggestion: f.suggestion || "",
      imageData: f.imageData || "",
      imageName: f.imageName || "",
      improved: Boolean(f.improved),
      imageAfterData: f.imageAfterData || "",
      imageAfterName: f.imageAfterName || ""
    }));

    updateModeUI();
    renderChecklist();
    renderFindings();
    renderPreview();
    triggerAutoSave();
  }

  // ==========================================================================
  // AI INTEGRATION CLIENT (/api/hse/*)
  // ==========================================================================
  async function analyzeImageWithAi(imageData, hint = "") {
    const resp = await fetch("/api/hse/ai_analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ imageData, hint })
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || err.error || "Không thể phân tích ảnh bằng AI.");
    }
    return await resp.json();
  }

  async function translateText(text, kind = "text") {
    const resp = await fetch("/api/hse/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, kind })
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || err.error || "Không thể dịch.");
    }
    const data = await resp.json();
    return data.translation || "";
  }

  async function polishText(text) {
    const resp = await fetch("/api/hse/polish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || err.error || "Không thể tinh chỉnh câu từ.");
    }
    const data = await resp.json();
    return data.options || [];
  }

  // ==========================================================================
  // FINDINGS CONTROLLER
  // ==========================================================================
  function addFinding() {
    const newId = `finding_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
    state.findings.push({
      id: newId,
      departmentKey: "san-xuat",
      departmentVi: "Sản xuất",
      departmentZh: "生产部",
      aiHint: "",
      issueVi: "",
      issueZh: "",
      suggestion: "",
      imageData: "",
      imageName: "",
      improved: false,
      imageAfterData: "",
      imageAfterName: ""
    });
    renderFindings();
    renderPreview();
    triggerAutoSave();

    setTimeout(() => {
      const last = $(".hse-finding-card:last-child", $("#hse-findings-root"));
      if (last) last.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 60);
  }

  function selectDepartment(findingId, deptKey) {
    const f = state.findings.find(item => item.id === findingId);
    if (!f || !DEPARTMENTS[deptKey]) return;
    f.departmentKey = deptKey;
    f.departmentVi = DEPARTMENTS[deptKey].vi;
    f.departmentZh = DEPARTMENTS[deptKey].zh;
    renderFindings();
    renderPreview();
    triggerAutoSave();
    showToast(`Đã chọn: ${DEPARTMENTS[deptKey].vi} (${DEPARTMENTS[deptKey].zh})`);
  }

  function renderFindings() {
    const root = $("#hse-findings-root");
    const emptyEl = $("#hse-findings-empty");
    if (!root) return;

    if (emptyEl) {
      emptyEl.hidden = state.findings.length > 0;
    }

    const isImproveMode = (state.reportMode === "improvement");

    root.innerHTML = state.findings.map((finding, idx) => {
      const isImproved = Boolean(finding.improved);
      const activeKey = finding.departmentKey || "san-xuat";

      return `
      <article class="hse-finding-card ${isImproveMode && isImproved ? "card-improved" : ""}" data-id="${finding.id}">
        <div class="hse-finding-head">
          <div>
            <strong>Vấn đề ${idx + 1}</strong>
            <span class="hse-finding-badge">Trang ảnh ${Math.floor(idx / 2) + 1} · Vị trí ${(idx % 2) + 1}/2</span>
            ${isImproveMode ? `
              <span class="hse-status-tag ${isImproved ? "pass" : "fail"}">
                ${isImproved ? "✓ Đã cải thiện (符合)" : "✕ Chưa cải thiện (不符合)"}
              </span>
            ` : ""}
          </div>
          <button class="hse-btn hse-btn-danger" data-action="remove">Xóa</button>
        </div>

        <div class="hse-finding-body">
          <!-- Left Column: Department & Bilingual Details -->
          <div class="hse-finding-fields">
            <div class="hse-global-hint" style="margin-bottom: 0;">
              <div class="hse-global-hint-head">
                <span>💡 Gợi ý cho AI viết đúng hướng:</span>
                <span>Nhập vài từ then chốt</span>
              </div>
              <input type="text" 
                     class="hse-input" 
                     data-field="aiHint" 
                     value="${escapeHtml(finding.aiHint || '')}" 
                     placeholder="Ví dụ: bình chữa cháy bị che, dây điện hở, không mang bảo hộ..." />
              <div class="hse-quick-hints">
                <span style="font-size: 11px; color: #64748b; align-self: center;">Gợi ý nhanh:</span>
                <button type="button" class="hse-quick-hint-tag" data-action="quick-hint" data-hint="bình chữa cháy bị che khuất">🔥 Bình PCCC che</button>
                <button type="button" class="hse-quick-hint-tag" data-action="quick-hint" data-hint="lối thoát hiểm bị cản trở">🚪 Lối thoát hiểm</button>
                <button type="button" class="hse-quick-hint-tag" data-action="quick-hint" data-hint="thùng hóa chất mở nắp không khay tràn">🧪 Thùng hóa chất</button>
                <button type="button" class="hse-quick-hint-tag" data-action="quick-hint" data-hint="dây điện hở vỏ bọc">⚡ Dây điện hở</button>
                <button type="button" class="hse-quick-hint-tag" data-action="quick-hint" data-hint="vi phạm 5S sàn thao tác bừa bộn">🧹 Vi phạm 5S</button>
              </div>
            </div>

            <!-- Fast Department Selector Chips -->
            <div>
              <span style="font-size: 12px; font-weight: 700; color: #334155;">Tích chọn nhanh bộ phận:</span>
              <div class="hse-dept-chips">
                ${Object.entries(DEPARTMENTS).map(([k, d]) => `
                  <button type="button" class="hse-dept-chip ${activeKey === k ? "active" : ""}" data-action="select-dept" data-dept="${k}">
                    ${d.icon} ${d.vi} (${d.zh})
                  </button>
                `).join("")}
              </div>
            </div>

            <div class="hse-form-grid" style="grid-template-columns: 1fr 1fr; margin-bottom: 0;">
              <label class="hse-label">
                <span>负责部门（中文）</span>
                <input class="hse-input" data-field="departmentZh" value="${escapeHtml(finding.departmentZh)}" placeholder="生产部" />
              </label>
              <label class="hse-label">
                <span>Bộ phận (Tiếng Việt)</span>
                <input class="hse-input" data-field="departmentVi" value="${escapeHtml(finding.departmentVi)}" placeholder="Sản xuất" />
              </label>
            </div>

            <label class="hse-label">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span><strong>问题（中文）</strong></span>
                <button type="button" class="hse-btn hse-btn-outline" style="padding: 4px 8px; font-size: 11px;" data-action="translate-issue">
                  Dịch từ tiếng Việt
                </button>
              </div>
              <textarea class="hse-textarea" data-field="issueZh" placeholder="Bản dịch tiếng Trung tự động (问题: ...)...">${escapeHtml(finding.issueZh)}</textarea>
            </label>

            <label class="hse-label">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span><strong>Vấn đề (Tiếng Việt)</strong></span>
                <button type="button" class="hse-btn hse-btn-secondary" style="padding: 4px 8px; font-size: 11px;" data-action="polish-issue">
                  ✦ Viết chuyên nghiệp AI
                </button>
              </div>
              <textarea class="hse-textarea" data-field="issueVi" placeholder="Mô tả hiện trường vi phạm và yêu cầu an toàn...">${escapeHtml(finding.issueVi)}</textarea>
            </label>
          </div>

          <!-- Right Column: Before/After Photos & AI Trigger -->
          <div class="hse-dropzone-col">
            <label class="hse-dropzone ${finding.imageData ? "has-image" : ""}">
              ${finding.imageData ? `
                <img src="${finding.imageData}" alt="Ảnh vấn đề ${idx + 1}">
              ` : `
                <span style="font-size: 24px; margin-bottom: 6px;">📸</span>
                <strong>Tải ảnh vi phạm lên</strong>
                <span style="font-size: 11px; color: #64748b;">Kéo thả hoặc click (JPG/PNG)</span>
              `}
              <input type="file" accept="image/jpeg,image/png,image/webp" data-action="image-before">
            </label>

            <button type="button" class="hse-btn hse-btn-primary" style="width: 100%; justify-content: center;" data-action="ai-read" ${!finding.imageData ? "disabled" : ""}>
              🐳 ✦ DeepSeek đọc ảnh & tự soạn
            </button>

            <!-- Improvement Mode Controls & After Photo -->
            ${isImproveMode ? `
              <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px;">
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-weight: 700; font-size: 12.5px;">
                  <input type="checkbox" data-action="toggle-improved" ${isImproved ? "checked" : ""}>
                  <span style="color: ${isImproved ? "#15803d" : "#b91c1c"};">
                    ${isImproved ? "✓ ĐÃ CẢI THIỆN (Đã khắc phục)" : "✕ Chưa cải thiện (Khối đỏ)"}
                  </span>
                </label>

                ${isImproved ? `
                  <div style="margin-top: 8px;">
                    <label class="hse-sub-dropzone ${finding.imageAfterData ? "has-image" : ""}">
                      ${finding.imageAfterData ? `
                        <img src="${finding.imageAfterData}" alt="Ảnh sau cải thiện">
                      ` : `
                        <span style="font-size: 18px;">📸</span>
                        <strong style="font-size: 11.5px; color: #166534;">Tải ảnh sau cải thiện (整改后)</strong>
                      `}
                      <input type="file" accept="image/jpeg,image/png,image/webp" data-action="image-after">
                    </label>
                  </div>
                ` : ""}
              </div>
            ` : ""}
          </div>
        </div>
      </article>
      `;
    }).join("");

    bindFindingEvents(root);
    updateSummaries();
  }

  function bindFindingEvents(root) {
    $$(".hse-finding-card", root).forEach(card => {
      const findingId = card.dataset.id;
      const finding = state.findings.find(f => f.id === findingId);
      if (!finding) return;

      // Click handlers
      card.addEventListener("click", async (e) => {
        // Quick hint
        const qBtn = e.target.closest("[data-action='quick-hint']");
        if (qBtn) {
          finding.aiHint = qBtn.dataset.hint || "";
          renderFindings();
          renderPreview();
          triggerAutoSave();
          showToast(`Đã thêm gợi ý: "${finding.aiHint}"`);
          return;
        }

        // Dept select
        const deptBtn = e.target.closest("[data-action='select-dept']");
        if (deptBtn) {
          selectDepartment(findingId, deptBtn.dataset.dept);
          return;
        }

        // Remove
        const removeBtn = e.target.closest("[data-action='remove']");
        if (removeBtn) {
          if (confirm("Bạn có chắc chắn muốn xóa vấn đề này không?")) {
            state.findings = state.findings.filter(f => f.id !== findingId);
            renderFindings();
            renderPreview();
            triggerAutoSave();
          }
          return;
        }

        // AI Read
        const aiBtn = e.target.closest("[data-action='ai-read']");
        if (aiBtn) {
          if (!finding.imageData) return showToast("Vui lòng tải ảnh lên trước.", true);
          aiBtn.disabled = true;
          aiBtn.innerHTML = `<span>⏳</span> Đang đọc ảnh...`;
          try {
            const hint = (finding.aiHint || "").trim() || (state.globalAiHint || "").trim() || (finding.issueVi || "").trim();
            const res = await analyzeImageWithAi(finding.imageData, hint);
            if (res.departmentKey && DEPARTMENTS[res.departmentKey]) {
              finding.departmentKey = res.departmentKey;
              finding.departmentVi = res.departmentVi || DEPARTMENTS[res.departmentKey].vi;
              finding.departmentZh = res.departmentZh || DEPARTMENTS[res.departmentKey].zh;
            }
            if (res.issueVi) finding.issueVi = res.issueVi;
            if (res.issueZh) finding.issueZh = res.issueZh;
            renderFindings();
            renderPreview();
            triggerAutoSave();
            showToast("✦ DeepSeek AI đã phân tích ảnh và hoàn thành soạn thảo!");
          } catch (err) {
            showToast(`Lỗi AI: ${err.message}`, true);
          } finally {
            aiBtn.disabled = false;
            aiBtn.innerHTML = `🐳 ✦ DeepSeek đọc ảnh & tự soạn`;
          }
          return;
        }

        // Polish
        const polishBtn = e.target.closest("[data-action='polish-issue']");
        if (polishBtn) {
          const txt = (finding.issueVi || "").trim() || (finding.aiHint || "").trim();
          if (!txt) return showToast("Vui lòng nhập nội dung hoặc gợi ý tiếng Việt trước.", true);
          openWritingAssistant(txt, { type: "finding", id: findingId });
          return;
        }

        // Translate
        const transBtn = e.target.closest("[data-action='translate-issue']");
        if (transBtn) {
          if (!finding.issueVi.trim()) return showToast("Vui lòng nhập nội dung tiếng Việt trước.", true);
          transBtn.disabled = true;
          transBtn.textContent = "Đang dịch...";
          try {
            const tr = await translateText(finding.issueVi, "text");
            finding.issueZh = tr.startsWith("问题:") ? tr : `问题: ${tr}`;
            renderFindings();
            renderPreview();
            triggerAutoSave();
            showToast("Đã dịch xong sang tiếng Trung!");
          } catch (err) {
            showToast(err.message, true);
          } finally {
            transBtn.disabled = false;
            transBtn.textContent = "Dịch từ tiếng Việt";
          }
          return;
        }
      });

      // Toggle improved checkbox
      const impChk = card.querySelector("[data-action='toggle-improved']");
      if (impChk) {
        impChk.addEventListener("change", (e) => {
          finding.improved = e.target.checked;
          renderFindings();
          renderPreview();
          triggerAutoSave();
          showToast(finding.improved ? "Đã đánh dấu: ĐÃ CẢI THIỆN" : "Đã chuyển sang: CHƯA CẢI THIỆN");
        });
      }

      // Input changes
      $$("[data-field]", card).forEach(input => {
        input.addEventListener("input", () => {
          finding[input.dataset.field] = input.value;
          renderPreview();
          triggerAutoSave();
        });
      });

      // Before image upload
      const beforeInput = card.querySelector("[data-action='image-before']");
      if (beforeInput) {
        beforeInput.addEventListener("change", async (e) => {
          const file = e.target.files[0];
          if (!file) return;
          if (file.size > 20 * 1024 * 1024) return showToast("Ảnh không vượt quá 20MB.", true);
          finding.imageData = await fileToDataUrl(file);
          finding.imageName = file.name;
          renderFindings();
          renderPreview();
          triggerAutoSave();
          showToast("Đã tải ảnh! Bấm 'DeepSeek đọc ảnh' để AI tự động soạn.");
        });
      }

      // After image upload
      const afterInput = card.querySelector("[data-action='image-after']");
      if (afterInput) {
        afterInput.addEventListener("change", async (e) => {
          const file = e.target.files[0];
          if (!file) return;
          finding.imageAfterData = await fileToDataUrl(file);
          finding.imageAfterName = file.name;
          renderFindings();
          renderPreview();
          triggerAutoSave();
          showToast("Đã tải ảnh sau cải thiện!");
        });
      }
    });
  }

  function fileToDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  // ==========================================================================
  // CHECKLIST CONTROLLER (26 Items across 5 Categories)
  // ==========================================================================
  async function loadChecklistSchema() {
    try {
      const resp = await fetch("/api/hse/checklist_schema").catch(() => null);
      if (resp && resp.ok) {
        const data = await resp.json();
        if (data.sections && Array.isArray(data.sections) && data.sections.length === 5) {
          state.sections = data.sections;
        }
      }
    } catch (e) {
      console.warn("Using offline checklist schema:", e);
    }

    // Populate checklist map
    for (const sec of state.sections) {
      for (const item of sec.items) {
        const row = Number(item.row);
        if (!state.checklist.has(row)) {
          state.checklist.set(row, {
            ...item,
            status: "pass",
            issueVi: "",
            issueZh: "",
            improved: false
          });
        }
      }
    }
  }

  function markAllChecklistPass() {
    for (const item of state.checklist.values()) {
      item.status = "pass";
      item.issueVi = "";
      item.issueZh = "";
    }
    renderChecklist();
    renderPreview();
    triggerAutoSave();
    showToast("✓ Đã đánh dấu tất cả 26 hạng mục đạt chuẩn!");
  }

  function renderChecklist() {
    const root = $("#hse-checklist-root");
    if (!root) return;

    const isImproveMode = (state.reportMode === "improvement");

    root.innerHTML = state.sections.map(sec => `
      <div class="hse-check-category">
        <div class="hse-check-category-head">
          <span>${escapeHtml(sec.title)}</span>
          <span style="font-size: 11.5px; color: #64748b;">${sec.items.length} hạng mục</span>
        </div>
        ${sec.items.map(item => {
          const row = Number(item.row);
          const data = state.checklist.get(row) || { status: "pass", issueVi: "", issueZh: "", improved: false };
          const isPass = (data.status === "pass");

          return `
          <div class="hse-check-item ${!isPass ? "fail" : ""}" data-row="${row}">
            <div class="hse-check-item-info">
              <h4>${escapeHtml(item.category)} (Dòng ${row})</h4>
              <p>${escapeHtml(item.content)}</p>
              <p class="hse-check-method">Phương pháp: ${escapeHtml(item.method)}</p>
            </div>

            <div class="hse-check-switch">
              <button class="pass ${isPass ? "active" : ""}" data-status="pass">✓ Đạt</button>
              <button class="fail ${!isPass ? "active" : ""}" data-status="fail">✕ Không đạt</button>
            </div>

            ${!isPass ? `
              <div class="hse-check-issue-box">
                ${isImproveMode ? `
                  <div style="grid-column: 1 / -1; margin-bottom: 4px;">
                    <label style="display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; color: #166534;">
                      <input type="checkbox" data-action="toggle-check-improved" ${data.improved ? "checked" : ""}>
                      <span>${data.improved ? "✓ Đã phục tra cải thiện (Khối xanh)" : "✕ Chưa cải thiện (Khối đỏ)"}</span>
                    </label>
                  </div>
                ` : ""}

                <label class="hse-label">
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span>Vấn đề (Tiếng Việt) *</span>
                    <span style="display: flex; gap: 4px;">
                      <button type="button" class="hse-btn hse-btn-secondary" style="padding: 2px 6px; font-size: 10.5px;" data-action="polish-check">✦ Viết AI</button>
                      <button type="button" class="hse-btn hse-btn-outline" style="padding: 2px 6px; font-size: 10.5px;" data-action="translate-check">Dịch Trung</button>
                    </span>
                  </div>
                  <textarea class="hse-textarea" data-field="issueVi" placeholder="Mô tả vi phạm phát hiện tại mục này...">${escapeHtml(data.issueVi)}</textarea>
                </label>

                <label class="hse-label">
                  <span>问题（中文）*</span>
                  <textarea class="hse-textarea" data-field="issueZh" placeholder="问题: ...">${escapeHtml(data.issueZh)}</textarea>
                </label>
              </div>
            ` : ""}
          </div>
          `;
        }).join("")}
      </div>
    `).join("");

    bindChecklistEvents(root);
    updateSummaries();
  }

  function bindChecklistEvents(root) {
    $$(".hse-check-item", root).forEach(itemCard => {
      const row = Number(itemCard.dataset.row);
      const itemData = state.checklist.get(row);
      if (!itemData) return;

      itemCard.addEventListener("click", async (e) => {
        // Status toggle
        const sBtn = e.target.closest("[data-status]");
        if (sBtn) {
          itemData.status = sBtn.dataset.status;
          renderChecklist();
          renderPreview();
          triggerAutoSave();
          return;
        }

        // Polish
        const pBtn = e.target.closest("[data-action='polish-check']");
        if (pBtn) {
          if (!itemData.issueVi.trim()) return showToast("Vui lòng nhập nội dung tiếng Việt trước.", true);
          openWritingAssistant(itemData.issueVi, { type: "checklist", row });
          return;
        }

        // Translate
        const tBtn = e.target.closest("[data-action='translate-check']");
        if (tBtn) {
          if (!itemData.issueVi.trim()) return showToast("Vui lòng nhập nội dung tiếng Việt trước.", true);
          tBtn.disabled = true;
          tBtn.textContent = "Đang dịch...";
          try {
            itemData.issueZh = await translateText(itemData.issueVi);
            renderChecklist();
            renderPreview();
            triggerAutoSave();
            showToast("Đã dịch xong!");
          } catch (err) {
            showToast(err.message, true);
          } finally {
            tBtn.disabled = false;
            tBtn.textContent = "Dịch Trung";
          }
          return;
        }
      });

      // Toggle improved
      const chkImp = itemCard.querySelector("[data-action='toggle-check-improved']");
      if (chkImp) {
        chkImp.addEventListener("change", (e) => {
          itemData.improved = e.target.checked;
          renderPreview();
          triggerAutoSave();
        });
      }

      // Input
      $$("textarea", itemCard).forEach(inp => {
        inp.addEventListener("input", () => {
          itemData[inp.dataset.field] = inp.value;
          renderPreview();
          triggerAutoSave();
        });
      });
    });
  }

  function updateSummaries() {
    const failed = [...state.checklist.values()].filter(i => i.status === "fail").length;
    const summaryEl = $("#hse-checklist-summary");
    if (summaryEl) {
      summaryEl.textContent = `${failed} không đạt · ${state.checklist.size - failed} đạt`;
    }
    const pageCount = 4 + Math.max(1, Math.ceil(state.findings.length / 2));
    const pageSumEl = $("#hse-page-summary");
    if (pageSumEl) {
      pageSumEl.textContent = `Tổng ${pageCount} trang A4 chuẩn ZhanChen`;
    }
  }

  // ==========================================================================
  // REAL-TIME A4 PREVIEW CANVAS (Findings view: 2 items/page; Checklist view)
  // ==========================================================================
  function renderPreview() {
    const root = $("#hse-preview-root");
    if (!root) return;

    const isImprove = (state.reportMode === "improvement");
    const dateInput = $("#hse-inspection-date");
    const dateVal = (dateInput && dateInput.value) ? dateInput.value : state.metadata.date;

    // View Mode: Checklist Table
    if (state.previewMode === "checklist") {
      const items = [...state.checklist.values()];
      const pages = [];
      for (let i = 0; i < items.length; i += 7) {
        pages.push(items.slice(i, i + 7));
      }
      root.innerHTML = pages.map((page, pIdx) => `
        <article class="hse-a4-paper">
          <h3 style="margin: 0 0 10px; text-align: center; font-size: 11.5px; font-family: 'Microsoft YaHei', sans-serif;">
            NHẬT KÝ KIỂM TRA AN TOÀN - MÔI TRƯỜNG - PCCC ${isImprove ? "(PHỤC TRA)" : ""}
          </h3>
          <table style="width: 100%; border-collapse: collapse; font-size: 7.5px; line-height: 1.25; flex: 1;">
            <thead>
              <tr style="background: #f1f5f9;">
                <th style="border: 1px solid #333; padding: 4px; width: 15%;">Hạng mục</th>
                <th style="border: 1px solid #333; padding: 4px; width: 45%;">Nội dung kiểm tra</th>
                <th style="border: 1px solid #333; padding: 4px; width: 15%;">Kết quả</th>
                <th style="border: 1px solid #333; padding: 4px; width: 25%;">Ghi chú vi phạm</th>
              </tr>
            </thead>
            <tbody>
              ${page.map(item => `
                <tr>
                  <td style="border: 1px solid #333; padding: 3px;">${escapeHtml(item.category)}</td>
                  <td style="border: 1px solid #333; padding: 3px;">${escapeHtml(item.content)}</td>
                  <td style="border: 1px solid #333; padding: 3px; text-align: center; font-weight: bold; color: ${item.status === "pass" ? "#15803d" : "#b91c1c"};">
                    ${item.status === "pass" ? "✓ Đạt" : (isImprove ? (item.improved ? "✓ Đã sửa" : "✕ Chưa sửa") : "✕ K.Đạt")}
                  </td>
                  <td style="border: 1px solid #333; padding: 3px;">
                    ${item.status === "fail" ? `${escapeHtml(item.issueVi)}` : ""}
                  </td>
                </tr>
              `).join("")}
            </tbody>
          </table>
          <span class="hse-a4-page-number">Trang ${pIdx + 1} / ${pages.length}</span>
        </article>
      `).join("");
      return;
    }

    // View Mode: Findings (2 items per page)
    const findingPages = [];
    for (let i = 0; i < state.findings.length; i += 2) {
      findingPages.push(state.findings.slice(i, i + 2));
    }
    if (!findingPages.length) findingPages.push([]);

    root.innerHTML = findingPages.map((page, pIdx) => `
      <article class="hse-a4-paper">
        <!-- 3-Column Header Table -->
        <table class="hse-a4-header-table">
          <tr>
            <td class="col-logo">
              <img src="icons/hse_avatar.jpg" alt="Logo">
            </td>
            <td class="col-title">
              <strong>越南展辰 HSE 办巡厂报告 ${isImprove ? "(整改复查)" : ""}</strong>
            </td>
            <td class="col-date">
              <time>${escapeHtml(dateVal)}</time>
            </td>
          </tr>
        </table>
        <div class="hse-a4-blue-line"></div>

        ${page.length ? `
          <table class="hse-a4-findings-table">
            ${page.map((finding, fIdx) => {
              const cleanZh = (finding.issueZh || "").replace(/^问题[:：]\s*/, "");
              const cleanVi = (finding.issueVi || "").replace(/^Vấn đề[:：]\s*/i, "");
              const displayImg = (isImprove && finding.improved && finding.imageAfterData) ? finding.imageAfterData : finding.imageData;

              const rowHtml = `
              <tr class="hse-a4-row-finding">
                <td class="hse-a4-copy-cell">
                  <div class="hse-a4-copy-line">
                    <strong class="label-zh">负责部门:</strong>
                    <span style="font-family: 'Microsoft YaHei', sans-serif;">${escapeHtml(finding.departmentZh || "...")}</span>
                  </div>
                  <div class="hse-a4-copy-line">
                    <strong class="label-zh">问题:</strong>
                    <span style="font-family: 'Microsoft YaHei', sans-serif;">${escapeHtml(cleanZh || "...")}</span>
                  </div>
                  <div class="hse-a4-copy-line">
                    <strong class="label-vi">Bộ phận:</strong>
                    <span>${escapeHtml(finding.departmentVi || "...")}</span>
                  </div>
                  <div class="hse-a4-copy-line">
                    <strong class="label-vi">Vấn đề:</strong>
                    <span>${escapeHtml(cleanVi || "...")}</span>
                  </div>
                  ${isImprove ? `
                    <div style="font-size: 8.5px; font-weight: bold; margin-top: 4px; color: ${finding.improved ? "#15803d" : "#b91c1c"};">
                      复查：${escapeHtml(dateVal)}-${finding.improved ? "已整改" : "未整改"}<br>
                      Kiểm tra：${escapeHtml(dateVal)}-${finding.improved ? "Đã cải thiện" : "Chưa cải thiện"}
                    </div>
                  ` : ""}
                </td>
                <td class="hse-a4-img-cell">
                  ${displayImg ? `
                    <img src="${displayImg}" alt="Ảnh hiện trường">
                  ` : `
                    <div style="display: grid; place-items: center; height: 100%; min-height: 140px; color: #94a3b8; font-size: 11px; background: #f8fafc;">
                      📸 Chưa có ảnh
                    </div>
                  `}
                </td>
              </tr>
              `;

              if (fIdx > 0) {
                return `
                <tr class="hse-a4-separator-row">
                  <td class="hse-a4-separator-cell"></td>
                  <td class="hse-a4-separator-cell"></td>
                </tr>
                ` + rowHtml;
              }
              return rowHtml;
            }).join("")}
          </table>
        ` : `
          <div style="display: grid; place-items: center; height: 70%; color: #94a3b8; border: 1.5px dashed #cbd5e1; border-radius: 8px; font-size: 12px; text-align: center; padding: 20px;">
            Chưa có vấn đề hiện trường.<br>Bấm "+ Thêm vấn đề" để bắt đầu soạn thảo.
          </div>
        `}
        <span class="hse-a4-page-number">Trang ${pIdx + 5}</span>
      </article>
    `).join("");
  }

  // ==========================================================================
  // WORD EXPORT & DECOMPILER IMPORT
  // ==========================================================================
  async function exportWordDocument() {
    try {
      const dateVal = ($("#hse-inspection-date")?.value || "").trim();
      if (!dateVal) throw new Error("Vui lòng chọn ngày kiểm tra.");

      // Check checklist fail items validation
      for (const item of state.checklist.values()) {
        if (item.status === "fail" && (!item.issueVi.trim() || !item.issueZh.trim())) {
          throw new Error(`Mục "${item.category}" đánh dấu Không đạt nhưng thiếu văn bản mô tả song ngữ.`);
        }
      }

      setLoading(true, "Đang khởi tạo tài liệu Word (.docx) chuẩn A4 ZhanChen...");
      const payload = makePayload();

      const resp = await fetch("/api/hse/generate_docx", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || err.error || `Lỗi xuất file Word (Mã ${resp.status}).`);
      }

      const blob = await resp.blob();
      const disposition = resp.headers.get("Content-Disposition") || "";
      const suffix = (state.reportMode === "improvement") ? "_Improvement" : "";
      const filename = disposition.match(/filename="([^"]+)"/)?.[1] || `HSE_Report_${payload.metadata.date}${suffix}.docx`;

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 2500);

      const isDriveLocked = resp.headers.get("X-Drive-Locked") === "true";
      if (isDriveLocked) {
        showToast("⚠️ Tệp gốc đang được mở trong Word, hệ thống đã tự lưu bản sao có mốc thời gian an toàn!");
      } else {
        showToast("✓ Đã xuất file Word (.docx) thành công!");
      }
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setLoading(false);
    }
  }

  async function importWordOld(file) {
    if (!file) return;
    try {
      setLoading(true, "Đang giải mã file Word tháng trước sang Báo Cáo Phục Tra Cải Thiện...");
      const reader = new FileReader();
      reader.onload = async () => {
        try {
          const resp = await fetch("/api/hse/import_docx", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ fileData: reader.result })
          });
          if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || err.error || "Không thể phân tích file Word.");
          }
          const res = await resp.json();
          if (res.report) {
            applyReportData(res.report);
            state.reportMode = "improvement";
            updateModeUI();
            showToast(`✓ Đã nạp ${res.report.findings?.length || 0} vấn đề từ Word cũ vào Báo Cáo Cải Thiện!`);
          }
        } catch (e) {
          showToast(`Lỗi giải mã Word: ${e.message}`, true);
        } finally {
          setLoading(false);
        }
      };
      reader.readAsDataURL(file);
    } catch (err) {
      showToast(err.message, true);
      setLoading(false);
    }
  }

  function exportBackupJson() {
    const payload = makePayload();
    const str = JSON.stringify(payload, null, 2);
    const blob = new Blob([str], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `HSE_Report_${payload.metadata.date || "data"}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    showToast("Đã tải tệp JSON sao lưu.");
  }

  function importBackupJson(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result);
        applyReportData(data);
        showToast("✓ Đã nạp thành công báo cáo từ JSON!");
      } catch (err) {
        showToast(`Lỗi JSON: ${err.message}`, true);
      }
    };
    reader.readAsText(file);
  }

  async function openExplorerFolder() {
    try {
      const resp = await fetch("/api/hse/open_folder", { method: "POST" });
      if (resp.ok) {
        showToast("Đã mở thư mục lưu trữ trong Windows Explorer.");
      }
    } catch (e) {
      console.warn("Open folder error:", e);
    }
  }

  // ==========================================================================
  // REPORT SAVING, LISTING, CLONING TO IMPROVEMENT & GOOGLE DRIVE SYNC
  // ==========================================================================
  let savedReportsList = [];

  async function saveHseReportNow() {
    try {
      const dateVal = ($("#hse-inspection-date")?.value || state.metadata.date || "").trim();
      if (!dateVal) {
        showToast("⚠️ Vui lòng chọn ngày kiểm tra trước khi lưu báo cáo.", true);
        const inp = $("#hse-inspection-date");
        if (inp) {
          inp.focus();
          inp.scrollIntoView({ behavior: "smooth", block: "center" });
        }
        return;
      }

      setLoading(true, "Đang lưu báo cáo và đồng bộ Google Drive...");
      const payload = makePayload();
      
      const resp = await fetch("/api/hse/reports/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, save_docx: true })
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || err.error || `Lỗi lưu báo cáo (Mã ${resp.status}).`);
      }

      const res = await resp.json();
      if (res.id) {
        state.currentReportId = res.id;
      }
      triggerAutoSave();
      await updateHseSavedCountBadge();

      if (res.drive_saved) {
        showToast(`💾 Đã lưu báo cáo & đồng bộ Google Drive thành công!\n📁 Vị trí: ${res.drive_path || 'G:\\Drive của tôi\\HSE_BaoCao'}`);
      } else {
        showToast("💾 Đã lưu báo cáo thành công vào hệ thống!");
      }

      const modal = $("#hse-reports-modal");
      if (modal && !modal.classList.contains("hidden")) {
        loadHseReportsList();
      }
    } catch (err) {
      showToast(`Lỗi khi lưu: ${err.message}`, true);
    } finally {
      setLoading(false);
    }
  }

  async function updateHseSavedCountBadge() {
    try {
      const resp = await fetch("/api/hse/reports/list");
      if (!resp.ok) return;
      const data = await resp.json();
      const count = (data.reports || []).length;
      
      const badge = $("#hse-reports-count-badge");
      if (badge) badge.textContent = count;

      const modalCount = $("#hse-reports-modal-count");
      if (modalCount) modalCount.textContent = `${count} báo cáo`;
    } catch (e) {
      console.warn("Could not update saved count badge:", e);
    }
  }

  function openHseReportsModal() {
    const modal = $("#hse-reports-modal");
    if (!modal) return;
    modal.classList.remove("hidden");
    loadHseReportsList();
  }

  function closeHseReportsModal() {
    const modal = $("#hse-reports-modal");
    if (modal) modal.classList.add("hidden");
  }

  async function loadHseReportsList() {
    const body = $("#hse-reports-modal-body");
    if (!body) return;

    body.innerHTML = `
      <div style="text-align:center; padding:48px 20px; color:#64748b;">
        <div style="margin:0 auto 12px; width:32px; height:32px; border:3px solid #e2e8f0; border-top-color:#2563eb; border-radius:50%; animation:spin 0.8s linear infinite;"></div>
        <div style="font-weight:600; font-size:13.5px;">Đang tải danh sách báo cáo đã lưu...</div>
      </div>
    `;

    try {
      const resp = await fetch("/api/hse/reports/list");
      if (!resp.ok) throw new Error("Không thể tải danh sách báo cáo từ máy chủ.");
      const data = await resp.json();
      savedReportsList = data.reports || [];
      
      const countEl = $("#hse-reports-modal-count");
      if (countEl) countEl.textContent = `${savedReportsList.length} báo cáo`;
      const badge = $("#hse-reports-count-badge");
      if (badge) badge.textContent = savedReportsList.length;

      filterHseReportsList();
    } catch (err) {
      body.innerHTML = `
        <div style="text-align:center; padding:36px 20px; color:#ef4444; background:#fef2f2; border-radius:10px; border:1px solid #fee2e2;">
          <div style="font-size:32px; margin-bottom:8px;">⚠️</div>
          <div style="font-weight:700; font-size:14px; margin-bottom:4px;">Lỗi tải danh sách báo cáo</div>
          <div style="font-size:12.5px; color:#b91c1c;">${escapeHtml(err.message)}</div>
          <button type="button" onclick="loadHseReportsList()" style="margin-top:12px; padding:6px 16px; background:#ef4444; color:#fff; border:none; border-radius:6px; font-weight:700; font-size:12px; cursor:pointer;">Thử lại</button>
        </div>
      `;
    }
  }

  function filterHseReportsList(query = null) {
    const searchInput = $("#hse-search-reports-input");
    const q = (query !== null ? query : (searchInput?.value || "")).trim().toLowerCase();
    const typeFilter = ($("#hse-filter-report-type")?.value || "all").toLowerCase();

    let filtered = savedReportsList;

    if (typeFilter && typeFilter !== "all") {
      filtered = filtered.filter(r => (r.reportType || "inspection").toLowerCase() === typeFilter);
    }

    if (q) {
      filtered = filtered.filter(r => {
        const title = (r.title || "").toLowerCase();
        const date = (r.date || "").toLowerCase();
        const id = (r.id || "").toLowerCase();
        const filename = (r.filename || "").toLowerCase();
        return title.includes(q) || date.includes(q) || id.includes(q) || filename.includes(q);
      });
    }

    renderReportsListTable(filtered);
  }

  function renderReportsListTable(reports) {
    const body = $("#hse-reports-modal-body");
    if (!body) return;

    if (!reports || !reports.length) {
      body.innerHTML = `
        <div style="text-align:center; padding:52px 20px; color:#64748b; background:#f8fafc; border-radius:12px; border:1px dashed #cbd5e1;">
          <div style="font-size:44px; margin-bottom:10px;">📋</div>
          <div style="font-weight:700; font-size:15px; color:#1e293b; margin-bottom:4px;">Chưa có báo cáo nào phù hợp</div>
          <div style="font-size:12.5px; color:#64748b; max-width:420px; margin:0 auto;">
            Bạn có thể nhấn nút <strong>"💾 Lưu Báo Cáo"</strong> trên thanh công cụ để lưu dữ liệu hiện tại vào hệ thống và tự động đồng bộ Google Drive.
          </div>
        </div>
      `;
      return;
    }

    const rowsHtml = reports.map((r, idx) => {
      const isImprovement = (r.reportType === "improvement");
      const typeBadge = isImprovement
        ? `<span style="display:inline-flex; align-items:center; gap:4px; padding:3px 9px; border-radius:6px; font-size:11.5px; font-weight:700; background:#fff7ed; color:#c2410c; border:1px solid #fed7aa;" title="Báo cáo phục tra cải thiện">🛠️ Cải Thiện</span>`
        : `<span style="display:inline-flex; align-items:center; gap:4px; padding:3px 9px; border-radius:6px; font-size:11.5px; font-weight:700; background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe;" title="Báo cáo kiểm tra hiện trường">📋 Kiểm Tra</span>`;

      const findingsBadge = `<span style="display:inline-flex; align-items:center; gap:4px; padding:2px 8px; border-radius:6px; font-size:12px; font-weight:700; background:#f1f5f9; color:#334155;">⚠️ ${r.findingsCount || 0} vi phạm</span>`;
      
      const docxName = r.docx_file || (r.filename ? r.filename.replace(/\\.json$/, ".docx") : "");

      return `
        <tr style="border-bottom:1px solid #f1f5f9; transition:background 0.15s ease;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background='transparent'">
          <td style="padding:12px 14px; font-weight:700; color:#0f172a; white-space:nowrap; font-size:13px;">
            ${escapeHtml(r.date || "---")}
          </td>
          <td style="padding:12px 14px;">
            <div style="font-weight:700; font-size:13.5px; color:#1e293b; line-height:1.4;">
              ${escapeHtml(r.title || "Báo cáo HSE")}
            </div>
            <div style="font-size:11px; color:#94a3b8; margin-top:2px; font-family:monospace;">
              ${escapeHtml(r.id || r.filename)}
            </div>
          </td>
          <td style="padding:12px 14px; text-align:center; white-space:nowrap;">
            ${typeBadge}
          </td>
          <td style="padding:12px 14px; text-align:center; white-space:nowrap;">
            ${findingsBadge}
          </td>
          <td style="padding:12px 14px; text-align:right; font-size:12px; color:#64748b; white-space:nowrap;">
            ${r.size_kb ? `${r.size_kb} KB` : "---"}
          </td>
          <td style="padding:12px 14px; text-align:right; white-space:nowrap;">
            <div style="display:inline-flex; align-items:center; gap:6px;">
              <button type="button" onclick="loadHseReportById('${escapeHtml(r.id || r.filename)}')" title="Mở tải lại báo cáo vào HSE Studio" style="display:inline-flex; align-items:center; gap:4px; padding:6px 10px; font-size:12px; font-weight:700; background:#f1f5f9; color:#0f172a; border:1px solid #cbd5e1; border-radius:6px; cursor:pointer;">
                📂 Mở tải
              </button>
              <button type="button" onclick="cloneReportToImprovement('${escapeHtml(r.id || r.filename)}')" title="Sao chép báo cáo này thành Báo Cáo Phục Tra Cải Thiện (kế thừa toàn bộ ảnh và vi phạm)" style="display:inline-flex; align-items:center; gap:4px; padding:6px 12px; font-size:12px; font-weight:700; background:linear-gradient(135deg, #f59e0b, #d97706); color:#fff; border:none; border-radius:6px; cursor:pointer; box-shadow:0 1px 3px rgba(217,119,6,0.3);">
                🔄 Copy làm Cải Thiện
              </button>
              <button type="button" onclick="downloadReportDocx('${escapeHtml(docxName)}')" title="Tải xuống tệp Word (.docx)" style="display:inline-flex; align-items:center; gap:4px; padding:6px 10px; font-size:12px; font-weight:700; background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe; border-radius:6px; cursor:pointer;">
                📄 Tải Word
              </button>
              <button type="button" onclick="deleteHseReport('${escapeHtml(r.filename)}')" title="Xóa bản lưu này" style="display:inline-flex; align-items:center; padding:6px 9px; font-size:12px; font-weight:700; background:#fef2f2; color:#ef4444; border:1px solid #fee2e2; border-radius:6px; cursor:pointer;">
                🗑️
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join("");

    body.innerHTML = `
      <div style="overflow-x:auto;">
        <table style="width:100%; border-collapse:collapse; text-align:left;">
          <thead>
            <tr style="background:#f8fafc; border-bottom:2px solid #e2e8f0; font-size:12px; font-weight:800; color:#475569; text-transform:uppercase; letter-spacing:0.5px;">
              <th style="padding:10px 14px;">Ngày</th>
              <th style="padding:10px 14px;">Tiêu Đề / Hồ Sơ</th>
              <th style="padding:10px 14px; text-align:center;">Loại Báo Cáo</th>
              <th style="padding:10px 14px; text-align:center;">Phát Hiện</th>
              <th style="padding:10px 14px; text-align:right;">Dung Lượng</th>
              <th style="padding:10px 14px; text-align:right;">Hành Động</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>
      </div>
    `;
  }

  async function loadHseReportById(reportIdentifier) {
    try {
      setLoading(true, "Đang tải dữ liệu báo cáo đã lưu...");
      const resp = await fetch(`/api/hse/reports/load?id=${encodeURIComponent(reportIdentifier)}`);
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || err.error || "Không thể tải báo cáo.");
      }
      const data = await resp.json();
      applyReportData(data);
      closeHseReportsModal();
      showToast(`✓ Đã nạp thành công báo cáo: "${data.metadata?.title || data.id || reportIdentifier}"!`);
    } catch (err) {
      showToast(`Lỗi nạp báo cáo: ${err.message}`, true);
    } finally {
      setLoading(false);
    }
  }

  async function cloneReportToImprovement(reportIdentifier) {
    try {
      setLoading(true, "Đang sao chép báo cáo sang Báo Cáo Phục Tra Cải Thiện...");
      const resp = await fetch(`/api/hse/reports/load?id=${encodeURIComponent(reportIdentifier)}`);
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || err.error || "Không thể tải dữ liệu báo cáo gốc.");
      }
      const original = await resp.json();

      // Switch to improvement mode
      state.reportMode = "improvement";

      const originalDate = original.metadata?.date || new Date().toISOString().split("T")[0];
      const todayDate = new Date().toISOString().split("T")[0];

      // Update metadata
      state.metadata = {
        ...state.metadata,
        ...(original.metadata || {}),
        prevDate: originalDate,
        date: todayDate,
        title: (original.metadata?.title || "").replace(/kiểm tra/gi, "phục tra cải thiện") || `Báo cáo Phục tra Cải thiện ${todayDate}`
      };

      const dateInp = $("#hse-inspection-date");
      if (dateInp) dateInp.value = state.metadata.date;

      const titleInp = $("#hse-report-title");
      if (titleInp) titleInp.value = state.metadata.title;

      // Assign fresh ID for the improvement cycle
      state.currentReportId = `hse_imp_${Date.now()}`;

      // Inherit all findings, preserving violation info & initial photos, but reset improvement fields
      const originalFindings = original.findings || [];
      state.findings = originalFindings.map((f, idx) => ({
        id: `finding_${Date.now()}_${idx + 1}`,
        departmentKey: f.departmentKey || "san-xuat",
        departmentVi: f.departmentVi || "Sản xuất",
        departmentZh: f.departmentZh || "生产部",
        aiHint: f.aiHint || "",
        issueVi: f.issueVi || "",
        issueZh: f.issueZh || "",
        suggestion: f.suggestion || "",
        imageData: f.imageData || f.photoBefore || "",
        imageName: f.imageName || "",
        // Reset improvement verification slots
        improved: false,
        imageAfterData: "",
        imageAfterName: "",
        date: todayDate,
        recheckDate: todayDate,
        note: ""
      }));

      // Inherit checklist items
      if (original.checklist && Array.isArray(original.checklist)) {
        for (const item of original.checklist) {
          const row = Number(item.row);
          const existing = state.checklist.get(row);
          if (existing) {
            existing.status = item.status || "pass";
            existing.issueVi = item.issueVi || "";
            existing.issueZh = item.issueZh || "";
            existing.improved = false;
          }
        }
      }

      // Re-render entire UI in improvement mode
      updateModeUI();
      renderChecklist();
      renderFindings();
      renderPreview();
      triggerAutoSave();
      closeHseReportsModal();

      showToast(`🎉 Đã sao chép thành BÁO CÁO PHỤC TRA CẢI THIỆN (整改复查)!\n✓ Kế thừa ${state.findings.length} vi phạm ban đầu.\n📸 Hãy nạp ảnh minh chứng sau cải thiện để đối chiếu.`);
    } catch (err) {
      showToast(`Lỗi sao chép: ${err.message}`, true);
    } finally {
      setLoading(false);
    }
  }

  function downloadReportDocx(docxFilename) {
    if (!docxFilename) {
      return showToast("Không tìm thấy tên tệp Word tương ứng.", true);
    }
    const cleanName = docxFilename.endsWith(".docx") ? docxFilename : `${docxFilename}.docx`;
    const url = `/api/hse/reports/download-docx/${encodeURIComponent(cleanName)}`;
    
    const a = document.createElement("a");
    a.href = url;
    a.download = cleanName;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => a.remove(), 1000);
    showToast(`📄 Đang tải tệp Word: ${cleanName}`);
  }

  async function deleteHseReport(filename) {
    if (!filename) return;
    if (!confirm(`Bạn có chắc chắn muốn xóa vĩnh viễn bản lưu báo cáo "${filename}"?`)) {
      return;
    }

    try {
      setLoading(true, "Đang xóa bản lưu báo cáo...");
      const resp = await fetch(`/api/hse/reports/${encodeURIComponent(filename)}`, {
        method: "DELETE"
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || err.error || "Không thể xóa bản ghi.");
      }
      showToast(`✓ Đã xóa báo cáo "${filename}" thành công.`);
      await loadHseReportsList();
      await updateHseSavedCountBadge();
    } catch (err) {
      showToast(`Lỗi xóa: ${err.message}`, true);
    } finally {
      setLoading(false);
    }
  }

  async function openHseGoogleDriveFolder() {
    try {
      fetch("/api/hse/drive/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: "G:\\Drive của tôi\\HSE_BaoCao" })
      }).catch(() => {});

      window.open("https://drive.google.com/drive/u/0/my-drive", "_blank");
      showToast("☁️ Đã mở Google Drive (G:\\Drive của tôi\\HSE_BaoCao)!");
    } catch (err) {
      showToast(`Lỗi mở Drive: ${err.message}`, true);
    }
  }

  // ==========================================================================
  // WRITING ASSISTANT (3 Phrasing Options)
  // ==========================================================================
  function openWritingAssistant(initialText = "", target = null) {
    state.writingTarget = target;
    state.writingOptions = [];
    const panel = $("#hse-writing-assistant");
    if (panel) panel.classList.remove("hidden");
    const input = $("#hse-assistant-input");
    if (input) {
      input.value = initialText;
      setTimeout(() => input.focus(), 50);
    }
    renderWritingOptions();
  }

  function closeWritingAssistant() {
    const panel = $("#hse-writing-assistant");
    if (panel) panel.classList.add("hidden");
    state.writingTarget = null;
    state.writingOptions = [];
  }

  async function generateWritingOptions() {
    const input = $("#hse-assistant-input");
    const btn = $("#hse-assistant-generate-btn");
    const text = (input?.value || "").trim();
    if (!text) return showToast("Vui lòng nhập ý ghi nhận.", true);

    if (btn) {
      btn.disabled = true;
      btn.textContent = "Đang soạn...";
    }
    try {
      state.writingOptions = await polishText(text);
      renderWritingOptions();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Tạo 3 lựa chọn";
      }
    }
  }

  function renderWritingOptions() {
    const root = $("#hse-assistant-options");
    if (!root) return;

    if (!state.writingOptions.length) {
      root.innerHTML = `<div style="text-align: center; color: #64748b; font-size: 12px; padding: 16px;">Nhập ý ghi nhận và nhấn "Tạo 3 lựa chọn" để AI DeepSeek gợi ý các phương án văn phong chuẩn mực.</div>`;
      return;
    }

    const labels = ["Ngắn gọn & Trực tiếp", "Tập trung Rủi ro & Hiểm họa", "Hành động & Khắc phục"];

    root.innerHTML = state.writingOptions.map((opt, i) => `
      <div class="hse-assistant-option-card">
        <span class="hse-opt-badge">${labels[i] || `Phương án ${i + 1}`}</span>
        <p>${escapeHtml(opt)}</p>
        <button type="button" class="hse-btn hse-btn-secondary" style="padding: 5px 10px; font-size: 11.5px; align-self: flex-end;" data-use-opt="${i}">
          ${state.writingTarget ? "Dùng câu này" : "Sao chép"}
        </button>
      </div>
    `).join("");

    $$("[data-use-opt]", root).forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = Number(btn.dataset.useOpt);
        applyChosenOption(state.writingOptions[idx]);
      });
    });
  }

  async function applyChosenOption(text) {
    if (!text) return;
    if (!state.writingTarget) {
      try {
        await navigator.clipboard.writeText(text);
        showToast("Đã sao chép vào bộ nhớ tạm.");
      } catch {
        const inp = $("#hse-assistant-input");
        if (inp) inp.value = text;
      }
      closeWritingAssistant();
      return;
    }

    if (state.writingTarget.type === "finding") {
      const f = state.findings.find(item => item.id === state.writingTarget.id);
      if (f) {
        f.issueVi = text;
        renderFindings();
        renderPreview();
        triggerAutoSave();
        showToast("Đã áp dụng câu văn vào vấn đề hiện trường!");
      }
    } else if (state.writingTarget.type === "checklist") {
      const it = state.checklist.get(state.writingTarget.row);
      if (it) {
        it.issueVi = text;
        renderChecklist();
        renderPreview();
        triggerAutoSave();
        showToast("Đã áp dụng câu văn vào checklist!");
      }
    }
    closeWritingAssistant();
  }

  // ==========================================================================
  // MODE UI SWITCHER
  // ==========================================================================
  function updateModeUI() {
    $$(".hse-mode-pill").forEach(p => {
      p.classList.toggle("active", p.dataset.mode === state.reportMode);
    });
    const impBanner = $("#hse-improvement-banner");
    if (impBanner) {
      impBanner.classList.toggle("hidden", state.reportMode !== "improvement");
    }
  }

  // ==========================================================================
  // INITIALIZATION & EVENT BINDING
  // ==========================================================================
  async function init() {
    // 1. Load schema
    await loadChecklistSchema();

    // 2. Restore previous session from IndexedDB if present
    const savedSession = await loadSessionFromDb();
    if (savedSession) {
      applyReportData(savedSession);
    } else {
      // Try light cache from localStorage
      try {
        const light = localStorage.getItem("hse_studio_light_cache");
        if (light) applyReportData(JSON.parse(light));
      } catch (e) {}
    }

    // 3. Bind UI buttons & handlers
    // Mode switcher
    $$(".hse-mode-pill").forEach(pill => {
      pill.addEventListener("click", () => {
        state.reportMode = pill.dataset.mode || "inspection";
        updateModeUI();
        renderChecklist();
        renderFindings();
        renderPreview();
        triggerAutoSave();
        showToast(`Đã chuyển sang: ${state.reportMode === "improvement" ? "BÁO CÁO PHỤC TRA CẢI THIỆN (整改复查)" : "KIỂM TRA HIỆN TRƯỜNG THƯỜNG KỲ"}`);
      });
    });

    // Step navigation
    $$(".hse-step-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        $$(".hse-step-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const target = $(`#${btn.dataset.target}`);
        if (target) target.scrollIntoView({ behavior: "smooth" });
      });
    });

    // Preview segmented tab switch
    $$(".hse-segmented-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        $$(".hse-segmented-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.previewMode = btn.dataset.preview || "findings";
        renderPreview();
      });
    });

    // Add finding buttons
    $("#hse-add-finding-btn")?.addEventListener("click", addFinding);
    $("#hse-empty-add-btn")?.addEventListener("click", addFinding);

    // Batch AI analyze
    $("#hse-batch-ai-btn")?.addEventListener("click", async () => {
      const candidates = state.findings.filter(f => f.imageData && (!f.issueVi || !f.issueZh));
      if (!candidates.length) return showToast("Tất cả các ảnh đã có nội dung hoặc chưa có ảnh.", true);

      setLoading(true, `DeepSeek AI đang phân tích đồng loạt ${candidates.length} ảnh...`);
      try {
        for (const f of candidates) {
          const hint = (f.aiHint || "").trim() || (state.globalAiHint || "").trim();
          const res = await analyzeImageWithAi(f.imageData, hint);
          if (res.departmentKey && DEPARTMENTS[res.departmentKey]) {
            f.departmentKey = res.departmentKey;
            f.departmentVi = res.departmentVi || DEPARTMENTS[res.departmentKey].vi;
            f.departmentZh = res.departmentZh || DEPARTMENTS[res.departmentKey].zh;
          }
          if (res.issueVi) f.issueVi = res.issueVi;
          if (res.issueZh) f.issueZh = res.issueZh;
        }
        renderFindings();
        renderPreview();
        triggerAutoSave();
        showToast("✦ Đã phân tích toàn bộ ảnh thành công!");
      } catch (err) {
        showToast(err.message, true);
      } finally {
        setLoading(false);
      }
    });

    // Mark all pass
    $("#hse-mark-all-pass-btn")?.addEventListener("click", markAllChecklistPass);

    // Export Word
    $("#hse-export-word-btn")?.addEventListener("click", exportWordDocument);
    $("#hse-preview-export-btn")?.addEventListener("click", exportWordDocument);

    // Metadata inputs
    $("#hse-inspection-date")?.addEventListener("input", (e) => {
      state.metadata.date = e.target.value;
      renderPreview();
      triggerAutoSave();
    });

    $("#hse-inspectors")?.addEventListener("input", (e) => {
      state.metadata.inspectors = e.target.value;
      triggerAutoSave();
    });

    $("#hse-global-ai-hint")?.addEventListener("input", (e) => {
      state.globalAiHint = e.target.value;
      triggerAutoSave();
    });

    // JSON backup / restore
    $("#hse-export-json-btn")?.addEventListener("click", exportBackupJson);

    $("#hse-import-json-input")?.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) importBackupJson(file);
      e.target.value = "";
    });

    // Word import (Improvement cycle)
    $("#hse-import-docx-input")?.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) importWordOld(file);
      e.target.value = "";
    });

    // Open folder
    $("#hse-open-folder-btn")?.addEventListener("click", openExplorerFolder);

    // Save report button
    $("#hse-save-report-btn")?.addEventListener("click", saveHseReportNow);

    // List reports button
    $("#hse-list-reports-btn")?.addEventListener("click", openHseReportsModal);

    // Google Drive button
    $("#hse-gdrive-open-btn")?.addEventListener("click", openHseGoogleDriveFolder);

    // Modal click backdrop / ESC to close
    $("#hse-reports-modal")?.addEventListener("click", (e) => {
      if (e.target.id === "hse-reports-modal") {
        closeHseReportsModal();
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        closeHseReportsModal();
      }
    });

    // Assistant controls
    $("#hse-assistant-launcher")?.addEventListener("click", () => openWritingAssistant());
    $("#hse-assistant-close-btn")?.addEventListener("click", closeWritingAssistant);
    $("#hse-assistant-generate-btn")?.addEventListener("click", generateWritingOptions);

    $("#hse-assistant-input")?.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        generateWritingOptions();
      }
    });

    // Initial render
    renderChecklist();
    renderFindings();
    renderPreview();

    // Update saved reports count badge on startup
    updateHseSavedCountBadge();
  }

  // Expose global initializer and helpers
  window.initHseStudio = init;
  window.saveHseReportNow = saveHseReportNow;
  window.openHseReportsModal = openHseReportsModal;
  window.closeHseReportsModal = closeHseReportsModal;
  window.loadHseReportsList = loadHseReportsList;
  window.filterHseReportsList = filterHseReportsList;
  window.loadHseReportById = loadHseReportById;
  window.cloneReportToImprovement = cloneReportToImprovement;
  window.downloadReportDocx = downloadReportDocx;
  window.deleteHseReport = deleteHseReport;
  window.openHseGoogleDriveFolder = openHseGoogleDriveFolder;
  window.updateHseSavedCountBadge = updateHseSavedCountBadge;

  window.hseStudio = {
    state,
    makePayload,
    applyReportData,
    renderFindings,
    renderChecklist,
    renderPreview,
    triggerAutoSave,
    saveHseReportNow,
    openHseReportsModal,
    closeHseReportsModal,
    loadHseReportsList,
    filterHseReportsList,
    loadHseReportById,
    cloneReportToImprovement,
    downloadReportDocx,
    deleteHseReport,
    openHseGoogleDriveFolder,
    updateHseSavedCountBadge
  };

  // Auto boot when DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
