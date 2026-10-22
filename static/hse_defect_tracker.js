// ==========================================================================
// HSE MASTER DEFECT TRACKER · CONTROLLER & STATE MACHINE
// LUV-PDF Private Suite · ZhanChen Enterprise Standard
// ==========================================================================

(function() {
  "use strict";

  const state = {
    allDefects: [],
    filteredDefects: [],
    selectedMonth: "all",
    selectedDept: "all",
    selectedStatus: "all",
    searchQuery: "",
    viewMode: "table", // "table" (default 7-col Excel standard) | "cards"
    kpis: { total: 0, improved: 0, pending: 0, rate: 0.0 },
    availableMonths: [],
    availableDepts: [],
    currentDetailDefect: null,
    pendingAfterImage: "",
    initialized: false
  };

  let currentLightboxZoom = 1;
  let currentLightboxRotate = 0;
  let currentLightboxSrc = "";
  let formCurrentImage = "";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  function escapeHtml(val = "") {
    return String(val).replace(/[&<>'"]/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
    }[c]));
  }

  function showToast(message, isError = false) {
    let toast = $("#hse-tracker-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "hse-tracker-toast";
      toast.className = "toast";
      toast.style.cssText = `
        position: fixed; bottom: 24px; right: 24px; z-index: 10000;
        background: #1e293b; color: #fff; padding: 12px 20px;
        border-radius: 8px; font-size: 13.5px; font-weight: 600;
        box-shadow: 0 4px 16px rgba(0,0,0,0.2); transition: opacity 0.2s;
      `;
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.style.background = isError ? "#ef4444" : "#10b981";
    toast.style.display = "block";
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => {
      toast.style.display = "none";
    }, 3500);
  }

  function setLoading(active, text = "Đang đồng bộ dữ liệu...") {
    let overlay = $("#hse-tracker-loading");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "hse-tracker-loading";
      overlay.style.cssText = `
        position: fixed; inset: 0; background: rgba(15,23,42,0.6);
        backdrop-filter: blur(4px); z-index: 10001; display: none;
        align-items: center; justify-content: center; flex-direction: column;
        color: #fff; font-size: 15px; font-weight: 700;
      `;
      overlay.innerHTML = `
        <div style="width:40px; height:40px; border:4px solid #fff; border-top-color:#3b82f6; border-radius:50%; animation:spin 0.8s linear infinite; margin-bottom:12px;"></div>
        <div id="hse-tracker-loading-text">${escapeHtml(text)}</div>
      `;
      document.body.appendChild(overlay);
    }
    const t = $("#hse-tracker-loading-text");
    if (t) t.textContent = text;
    overlay.style.display = active ? "flex" : "none";
  }

  // ==========================================================================
  // DATA FETCHING & FILTERING
  // ==========================================================================

  async function loadDefects(syncGas = false, forceReconcile = false) {
    try {
      if (syncGas) setLoading(true, "Đang kết nối & đồng bộ Google Apps Script...");

      const url = forceReconcile ? "/api/hse/defects?force_reconcile=true" : "/api/hse/defects";
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`Lỗi tải dữ liệu (Mã ${resp.status})`);
      const data = await resp.json();

      let fetchedDefects = data.defects || [];

      // Lọc qua Tombstones và mốc thời gian xóa trong localStorage để chống phục hồi dữ liệu đã xóa
      const isCleared = localStorage.getItem("IS_DB_CLEARED_HSE") === "true" || localStorage.getItem("HSE_TRACKER_CLEARED") === "true";
      const clearedAt = localStorage.getItem("hse_cleared_at_timestamp") || "";

      try {
        const deletedIds = JSON.parse(localStorage.getItem("deleted_hse_defect_ids") || "[]");
        const delSet = new Set(deletedIds.map(x => String(x).trim().toUpperCase()));

        fetchedDefects = fetchedDefects.filter(d => {
          const codeUpper = String(d.id || d.code || "").trim().toUpperCase();
          if (delSet.has(codeUpper)) return false;

          // Nếu hệ thống đã bị xóa sạch: loại bỏ bất kỳ bản ghi cũ nào (tháng 2026-09 hoặc các lỗi cũ)
          if (isCleared) {
            if (d.month === "2026-09" || codeUpper.startsWith("DEF-202609-")) return false;
            if (clearedAt && d.created_at && d.created_at <= clearedAt) return false;
          }
          return true;
        });
      } catch (_) {}

      if (isCleared && fetchedDefects.length === 0) {
        state.allDefects = [];
      } else {
        state.allDefects = fetchedDefects;
      }

      state.availableMonths = data.available_months || [];
      state.availableDepts = data.available_departments || [];

      // Update badge on main header
      const badge = $("#nav-hse-tracker-count-badge");
      if (badge) {
        const total = data.total ?? state.allDefects.length;
        badge.textContent = `${total} LỖI`;
        const pendingCount = state.allDefects.filter(d => !d.improved).length;
        badge.title = `🎯 Theo Dõi Lỗi HSE: ${total} lỗi tổng (${pendingCount} còn tồn đọng, ${total - pendingCount} đã cải thiện)`;
      }

      populateDropdowns();
      applyFilters();
    } catch (err) {
      console.warn("Tracker load error:", err);
      showToast(err.message, true);
    } finally {
      if (syncGas) setLoading(false);
    }
  }

  function populateDropdowns() {
    // 1. Month dropdown - Động 100%, tự động tổng hợp tháng thực tế
    const mSelect = $("#hse-tracker-month-select");
    if (mSelect) {
      const curVal = state.selectedMonth;
      let mHtml = `<option value="all">🌟 Tất cả các tháng / 全部月份 (${state.allDefects.length} lỗi)</option>`;
      for (const m of state.availableMonths) {
        const count = state.allDefects.filter(d => d.month === m).length;
        mHtml += `<option value="${escapeHtml(m)}" ${curVal === m ? "selected" : ""}>📅 Tháng ${escapeHtml(m)} (${count} lỗi)</option>`;
      }
      mSelect.innerHTML = mHtml;
      mSelect.value = (curVal && (curVal === "all" || state.availableMonths.includes(curVal))) ? curVal : "all";
      state.selectedMonth = mSelect.value;
    }

    // 2. Department dropdown
    const dSelect = $("#hse-tracker-dept-select");
    if (dSelect) {
      const curVal = state.selectedDept;
      let dHtml = `<option value="all">🏢 Tất cả bộ phận / 全部部门</option>`;
      for (const d of state.availableDepts) {
        const count = state.allDefects.filter(x => x.department === d).length;
        dHtml += `<option value="${escapeHtml(d)}" ${curVal === d ? "selected" : ""}>${escapeHtml(d)} (${count})</option>`;
      }
      dSelect.innerHTML = dHtml;
      dSelect.value = curVal;
    }
  }

  function applyFilters() {
    let list = state.allDefects;

    if (state.selectedMonth && state.selectedMonth !== "all") {
      list = list.filter(d => d.month === state.selectedMonth);
    }

    if (state.selectedDept && state.selectedDept !== "all") {
      list = list.filter(d => d.department === state.selectedDept || d.dept_key === state.selectedDept);
    }

    if (state.selectedStatus && state.selectedStatus !== "all") {
      if (state.selectedStatus === "improved") {
        list = list.filter(d => d.improved);
      } else if (state.selectedStatus === "pending") {
        list = list.filter(d => !d.improved);
      }
    }

    if (state.searchQuery && state.searchQuery.trim()) {
      const q = state.searchQuery.trim().toLowerCase();
      list = list.filter(d =>
        (d.code || "").toLowerCase().includes(q) ||
        (d.zh_issue || "").toLowerCase().includes(q) ||
        (d.vn_issue || "").toLowerCase().includes(q) ||
        (d.department || "").toLowerCase().includes(q) ||
        (d.category || "").toLowerCase().includes(q) ||
        (d.note || "").toLowerCase().includes(q)
      );
    }

    state.filteredDefects = list;

    // Recalculate KPIs based on current filtered view
    const tot = list.length;
    const imp = list.filter(d => d.improved).length;
    const pnd = tot - imp;
    const rate = tot > 0 ? (imp / tot) * 100 : 0.0;
    state.kpis = { total: tot, improved: imp, pending: pnd, rate: rate };

    renderKPIs();
    renderDefectsView();
  }

  // ==========================================================================
  // VIEW RENDERING (KPIs, Cards, Table)
  // ==========================================================================

  function renderKPIs() {
    const k = state.kpis;
    const elTot = $("#hse-kpi-val-total");
    const elImp = $("#hse-kpi-val-improved");
    const elPnd = $("#hse-kpi-val-pending");
    const elRate = $("#hse-kpi-val-rate");

    if (elTot) elTot.textContent = k.total;
    if (elImp) elImp.textContent = k.improved;
    if (elPnd) elPnd.textContent = k.pending;
    if (elRate) elRate.textContent = `${k.rate.toFixed(1)}%`;

    const counter = $("#hse-defects-counter-label");
    if (counter) {
      counter.textContent = `Hiển thị ${k.total} sự cố / 共有 ${k.total} 条缺陷记录`;
    }
  }

  function renderDefectsView() {
    const cardsRoot = $("#hse-tracker-cards-root");
    const tableRoot = $("#hse-tracker-table-root");
    const emptyEl = $("#hse-tracker-empty");

    if (!cardsRoot || !tableRoot) return;

    if (state.filteredDefects.length === 0) {
      cardsRoot.style.display = "none";
      tableRoot.style.display = "none";
      if (emptyEl) emptyEl.style.display = "block";
      return;
    }

    if (emptyEl) emptyEl.style.display = "none";

    if (state.viewMode === "cards") {
      cardsRoot.style.display = "grid";
      tableRoot.style.display = "none";
      renderCards(cardsRoot, state.filteredDefects);
    } else {
      cardsRoot.style.display = "none";
      tableRoot.style.display = "block";
      renderTable(tableRoot, state.filteredDefects);
    }
  }

  // ==========================================================================
  // LIGHTBOX CONTROLS
  // ==========================================================================
  function applyLightboxTransform() {
    const img = $("#hse-lightbox-img");
    if (img) {
      img.style.transform = `scale(${currentLightboxZoom}) rotate(${currentLightboxRotate}deg)`;
    }
  }

  function openLightbox(src, caption = "") {
    if (!src) return;
    currentLightboxSrc = src;
    currentLightboxZoom = 1;
    currentLightboxRotate = 0;
    const modal = $("#hse-image-lightbox-modal");
    const img = $("#hse-lightbox-img");
    const cap = $("#hse-lightbox-caption");
    if (!modal || !img) return;
    img.src = src;
    applyLightboxTransform();
    if (cap) cap.textContent = caption || "";
    modal.style.display = "flex";
  }

  function closeLightbox() {
    const modal = $("#hse-image-lightbox-modal");
    if (modal) modal.style.display = "none";
    const img = $("#hse-lightbox-img");
    if (img) img.src = "";
    currentLightboxSrc = "";
  }

  function zoomLightbox(delta) {
    currentLightboxZoom = Math.max(0.4, Math.min(3.5, +(currentLightboxZoom + delta).toFixed(2)));
    applyLightboxTransform();
  }

  function rotateLightbox() {
    currentLightboxRotate = (currentLightboxRotate + 90) % 360;
    applyLightboxTransform();
  }

  function downloadLightboxImage() {
    if (!currentLightboxSrc) return;
    const a = document.createElement("a");
    a.href = currentLightboxSrc;
    a.download = `HSE_Loi_Hien_Truong_${Date.now()}.jpg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  // ==========================================================================
  // INLINE TABLE ACTIONS (AUTO-SAVE)
  // ==========================================================================
  async function handleInlineStatusChange(defectId, newStatusVal, rowEl) {
    const isImproved = newStatusVal === "Cải thiện";
    const nowIsoDate = new Date().toISOString().substring(0, 10);
    const improveDateVal = isImproved ? nowIsoDate : "";

    const statusSelect = rowEl ? rowEl.querySelector(".hse-table-status-select") : null;
    if (statusSelect) {
      statusSelect.style.background = isImproved ? "#dcfce7" : "#ffedd5";
      statusSelect.style.color = isImproved ? "#166534" : "#9a3412";
      statusSelect.style.borderColor = isImproved ? "#86efac" : "#fdba74";
    }

    const dateInput = rowEl ? rowEl.querySelector(".hse-table-improve-date") : null;
    if (dateInput) {
      dateInput.value = improveDateVal;
      dateInput.disabled = !isImproved;
      dateInput.style.background = isImproved ? "#ffffff" : "#f8fafc";
      dateInput.style.color = isImproved ? "#0f172a" : "#94a3b8";
      dateInput.style.cursor = isImproved ? "pointer" : "not-allowed";
    }

    // Cập nhật state in-memory
    const target = state.allDefects.find(d => d.id === defectId || d.code === defectId);
    if (target) {
      target.improved = isImproved;
      target.status = isImproved ? "Cải thiện" : "Chưa cải thiện";
      target.improve_date = improveDateVal;
    }

    // Cập nhật lại thanh KPI
    const tot = state.filteredDefects.length;
    const imp = state.filteredDefects.filter(d => d.improved).length;
    const pnd = tot - imp;
    const rate = tot > 0 ? (imp / tot) * 100 : 0.0;
    state.kpis = { total: tot, improved: imp, pending: pnd, rate: rate };
    renderKPIs();

    // Auto-save lên server
    try {
      const payload = {
        defectId: defectId,
        status: isImproved ? "Cải thiện" : "Chưa cải thiện",
        improved: isImproved,
        improveDate: improveDateVal,
        improve_date: improveDateVal
      };
      const resp = await fetch("/api/hse/defects/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!resp.ok) throw new Error("Không thể cập nhật trạng thái");
      showToast(isImproved ? `✓ Đã lưu trạng thái: CẢI THIỆN (${defectId})` : `⚠️ Đã lưu trạng thái: CHƯA CẢI THIỆN (${defectId})`);
    } catch (err) {
      showToast("Lỗi lưu trạng thái: " + err.message, true);
    }
  }

  async function handleInlineImproveDateChange(defectId, newDate) {
    const target = state.allDefects.find(d => d.id === defectId || d.code === defectId);
    if (target) {
      target.improve_date = newDate;
    }
    try {
      await fetch("/api/hse/defects/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          defectId: defectId,
          improveDate: newDate,
          improve_date: newDate
        })
      });
      showToast(`✓ Đã lưu ngày cải thiện: ${newDate}`);
    } catch (err) {
      showToast("Lỗi lưu ngày: " + err.message, true);
    }
  }

  // ==========================================================================
  // DEFECT FORM MODAL (CRUD - 7 FIELDS)
  // ==========================================================================
  function updateFormImageDisplay(src) {
    formCurrentImage = src || "";
    const thumb = $("#hse-form-img-thumb");
    const emptyLabel = $("#hse-form-img-empty-label");
    const removeBtn = $("#hse-form-remove-img-btn");
    if (src) {
      if (thumb) {
        thumb.src = src;
        thumb.style.display = "block";
      }
      if (emptyLabel) emptyLabel.style.display = "none";
      if (removeBtn) removeBtn.style.display = "inline-flex";
    } else {
      if (thumb) {
        thumb.src = "";
        thumb.style.display = "none";
      }
      if (emptyLabel) emptyLabel.style.display = "block";
      if (removeBtn) removeBtn.style.display = "none";
    }
  }

  function updateFormStatusStyling(statusVal) {
    const isImp = statusVal === "Cải thiện";
    const select = $("#hse-form-status-select");
    if (select) {
      select.value = statusVal;
      select.style.background = isImp ? "#dcfce7" : "#ffedd5";
      select.style.color = isImp ? "#166534" : "#9a3412";
      select.style.borderColor = isImp ? "#86efac" : "#fdba74";
    }
  }

  function openDefectFormModal(defectId = null) {
    const modal = $("#hse-defect-form-modal");
    if (!modal) return;

    const titleEl = $("#hse-form-modal-title");
    const idInp = $("#hse-form-defect-id");
    const dateInp = $("#hse-form-date");
    const deptSelect = $("#hse-form-dept-select");
    const deptCustom = $("#hse-form-dept-custom");
    const issueVnInp = $("#hse-form-issue-vn");
    const issueZhInp = $("#hse-form-issue-zh");
    const improveDateInp = $("#hse-form-improve-date");

    if (defectId) {
      // Chỉnh sửa lỗi hiện có
      const d = state.allDefects.find(x => x.id === defectId || x.code === defectId);
      if (!d) return;
      if (titleEl) titleEl.textContent = `✏️ Chỉnh Sửa Sự Cố HSE / 编辑HSE隐患 (${d.code || d.id})`;
      if (idInp) idInp.value = d.code || d.id;
      if (dateInp) dateInp.value = d.date || d.created_at || (d.month ? `${d.month}-01` : new Date().toISOString().substring(0, 10));

      const dept = d.department || "";
      let foundDept = false;
      if (deptSelect) {
        for (const opt of deptSelect.options) {
          if (opt.value !== "__custom__" && (opt.value === dept || dept.includes(opt.value.split(" / ")[0]) || (opt.value.split(" / ")[1] && dept.includes(opt.value.split(" / ")[1])))) {
            deptSelect.value = opt.value;
            foundDept = true;
            break;
          }
        }
        if (!foundDept) {
          deptSelect.value = "__custom__";
          if (deptCustom) {
            deptCustom.value = dept;
            deptCustom.style.display = "block";
          }
        } else {
          if (deptCustom) {
            deptCustom.value = "";
            deptCustom.style.display = "none";
          }
        }
      }

      if (issueVnInp) issueVnInp.value = d.vn_issue || "";
      if (issueZhInp) issueZhInp.value = d.zh_issue || "";
      updateFormImageDisplay(d.img_before || d.img_after || "");

      const isImp = Boolean(d.improved);
      updateFormStatusStyling(isImp ? "Cải thiện" : "Chưa cải thiện");
      if (improveDateInp) improveDateInp.value = d.improve_date || "";
    } else {
      // Thêm mới lỗi
      if (titleEl) titleEl.textContent = "➕ Thêm Mới Sự Cố HSE / 新增HSE隐患";
      if (idInp) idInp.value = "";
      if (dateInp) dateInp.value = new Date().toISOString().substring(0, 10);
      if (deptSelect) deptSelect.value = "技术部 / Kỹ thuật";
      if (deptCustom) {
        deptCustom.value = "";
        deptCustom.style.display = "none";
      }
      if (issueVnInp) issueVnInp.value = "";
      if (issueZhInp) issueZhInp.value = "";
      updateFormImageDisplay("");
      updateFormStatusStyling("Chưa cải thiện");
      if (improveDateInp) improveDateInp.value = "";
    }

    modal.style.display = "flex";
  }

  function closeDefectFormModal() {
    const modal = $("#hse-defect-form-modal");
    if (modal) modal.style.display = "none";
    updateFormImageDisplay("");
  }

  async function translateVnToZh() {
    const vnInp = $("#hse-form-issue-vn");
    const zhInp = $("#hse-form-issue-zh");
    const btn = $("#hse-btn-ai-translate-zh");
    const text = (vnInp?.value || "").trim();
    if (!text) {
      showToast("Vui lòng nhập mô tả Tiếng Việt trước khi dịch!", true);
      return;
    }
    try {
      if (btn) {
        btn.disabled = true;
        btn.textContent = "⏳ Đang dịch...";
      }
      const resp = await fetch("/api/hse/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text, kind: "vi_to_zh" })
      });
      if (!resp.ok) throw new Error("Lỗi kết nối dịch thuật AI");
      const res = await resp.json();
      const translated = res.translated || res.text || "";
      if (zhInp && translated) {
        zhInp.value = translated;
      }
      showToast("🌐 Đã dịch sang Tiếng Trung thành công!");
    } catch (err) {
      showToast("Lỗi dịch AI: " + err.message, true);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = "🌐 Dịch sang Tiếng Trung";
      }
    }
  }

  async function translateZhToVn() {
    const zhInp = $("#hse-form-issue-zh");
    const vnInp = $("#hse-form-issue-vn");
    const btn = $("#hse-btn-ai-translate-vn");
    const text = (zhInp?.value || "").trim();
    if (!text) {
      showToast("Vui lòng nhập mô tả Tiếng Trung trước khi dịch!", true);
      return;
    }
    try {
      if (btn) {
        btn.disabled = true;
        btn.textContent = "⏳ Đang dịch...";
      }
      const resp = await fetch("/api/hse/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text, kind: "zh_to_vi" })
      });
      if (!resp.ok) throw new Error("Lỗi kết nối dịch thuật AI");
      const res = await resp.json();
      const translated = res.translated || res.text || "";
      if (vnInp && translated) {
        vnInp.value = translated;
      }
      showToast("🌐 Đã dịch sang Tiếng Việt thành công!");
    } catch (err) {
      showToast("Lỗi dịch AI: " + err.message, true);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = "🌐 Dịch sang Tiếng Việt";
      }
    }
  }

  async function analyzePhotoWithAIVision() {
    if (!formCurrentImage) {
      showToast("Vui lòng tải hoặc dán ảnh hiện trường trước khi phân tích AI!", true);
      return;
    }
    const btn = $("#hse-btn-ai-vision-analyze");
    try {
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = "⏳ AI đang nhìn & phân tích...";
      }
      setLoading(true, "AI Vision đang đọc hiện trường và soạn thảo đối sách...");
      const resp = await fetch("/api/hse/ai_analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          imageData: formCurrentImage,
          hint: "HSE site inspection defect hazard analysis"
        })
      });
      if (!resp.ok) throw new Error("Lỗi phân tích AI Vision");
      const res = await resp.json();
      const data = res.data || res;

      const zhInp = $("#hse-form-issue-zh");
      const vnInp = $("#hse-form-issue-vn");
      const deptSelect = $("#hse-form-dept-select");

      if (data.zh_issue && zhInp) zhInp.value = data.zh_issue;
      if (data.vn_issue && vnInp) vnInp.value = data.vn_issue;
      if (data.department && deptSelect) {
        for (const opt of deptSelect.options) {
          if (opt.value.includes(data.department) || data.department.includes(opt.value.split(" / ")[0])) {
            deptSelect.value = opt.value;
            break;
          }
        }
      }
      showToast("✨ AI đã phân tích ảnh hiện trường và tự động soạn thảo mô tả song ngữ!");
    } catch (err) {
      showToast("Lỗi AI Vision: " + err.message, true);
    } finally {
      setLoading(false);
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = "✨ AI Phân tích lỗi từ ảnh";
      }
    }
  }

  async function handleDefectFormSubmit(e) {
    if (e) e.preventDefault();
    const idInp = $("#hse-form-defect-id");
    const dateInp = $("#hse-form-date");
    const deptSelect = $("#hse-form-dept-select");
    const deptCustom = $("#hse-form-dept-custom");
    const issueVnInp = $("#hse-form-issue-vn");
    const issueZhInp = $("#hse-form-issue-zh");
    const statusSelect = $("#hse-form-status-select");
    const improveDateInp = $("#hse-form-improve-date");

    const defectId = (idInp?.value || "").trim();
    const rawDate = (dateInp?.value || "").trim() || new Date().toISOString().substring(0, 10);
    let department = deptSelect?.value || "";
    if (department === "__custom__") {
      department = (deptCustom?.value || "").trim() || "HSE / An toàn Môi trường";
    }
    const vnIssue = (issueVnInp?.value || "").trim();
    const zhIssue = (issueZhInp?.value || "").trim();
    const statusVal = statusSelect?.value || "Chưa cải thiện";
    const isImproved = statusVal === "Cải thiện";
    const improveDate = isImproved ? (improveDateInp?.value || new Date().toISOString().substring(0, 10)) : "";

    if (!vnIssue && !zhIssue) {
      showToast("Vui lòng nhập mô tả sự cố (tiếng Việt hoặc tiếng Trung)!", true);
      return;
    }

    const payload = {
      defectId: defectId,
      date: rawDate,
      department: department,
      vn_issue: vnIssue,
      zh_issue: zhIssue,
      img_before: formCurrentImage,
      status: statusVal,
      improved: isImproved,
      improveDate: improveDate,
      improve_date: improveDate
    };

    try {
      setLoading(true, defectId ? `Đang cập nhật sự cố ${defectId}...` : "Đang tạo mới sự cố HSE...");
      const url = defectId ? "/api/hse/defects/update" : "/api/hse/defects/create";
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!resp.ok) throw new Error("Lỗi khi lưu dữ liệu lên server");
      const res = await resp.json();

      closeDefectFormModal();
      showToast(res.message || "✓ Đã lưu sự cố thành công!");
      await loadDefects(false);
    } catch (err) {
      showToast("Lỗi lưu sự cố: " + err.message, true);
    } finally {
      setLoading(false);
    }
  }

  // ==========================================================================
  // CARDS & TABLE VIEW RENDERING
  // ==========================================================================
  function renderCards(root, defects) {
    root.innerHTML = defects.map(d => {
      const isDone = Boolean(d.improved);
      const hasAfterImg = Boolean(d.img_after);
      const hasBeforeImg = Boolean(d.img_before);
      const initialImg = (isDone && hasAfterImg) ? d.img_after : (d.img_before || d.img_after || "");
      const captionText = `${d.code || d.id} - ${d.zh_issue || d.vn_issue || ''}`;

      return `
        <article class="hse-defect-card ${isDone ? "card-improved" : ""}" data-id="${escapeHtml(d.id)}">
          <!-- Card Photo Box -->
          <div class="hse-defect-photo-box" ${initialImg ? `data-action="open-lightbox" data-src="${initialImg}" data-caption="${escapeHtml(captionText)}" style="cursor:pointer;" title="Bấm xem ảnh phóng to"` : ''}>
            ${initialImg ? `
              <img src="${initialImg}" alt="Ảnh sự cố" id="photo-${escapeHtml(d.id)}" loading="lazy">
            ` : `
              <div class="hse-defect-no-photo">
                <span style="font-size:26px;">📸</span>
                <span>(Không có ảnh / 无图片)</span>
              </div>
            `}

            <!-- Month Tag -->
            <div class="hse-photo-month-tag">📅 ${escapeHtml(d.date || d.month || 'HSE')}</div>

            <!-- Status Badge -->
            <div class="hse-photo-status-badge ${isDone ? 'done' : 'pending'}">
              ${isDone ? '✓ CẢI THIỆN / 已改善' : '⚠️ CHƯA CẢI THIỆN / 未改善'}
            </div>

            <!-- Before/After Toggle Switch if both photos exist -->
            ${(hasBeforeImg && hasAfterImg) ? `
              <div class="hse-photo-toggle-bar" onclick="event.stopPropagation();">
                <button type="button" class="hse-toggle-photo-btn ${!isDone ? 'active' : ''}" data-action="toggle-photo" data-target="photo-${escapeHtml(d.id)}" data-src="${escapeHtml(d.img_before)}">Trước (整改前)</button>
                <button type="button" class="hse-toggle-photo-btn ${isDone ? 'active' : ''}" data-action="toggle-photo" data-target="photo-${escapeHtml(d.id)}" data-src="${escapeHtml(d.img_after)}">Sau (整改后)</button>
              </div>
            ` : ""}
          </div>

          <!-- Card Body -->
          <div class="hse-defect-body">
            <div class="hse-defect-topline">
              <span class="hse-defect-code">${escapeHtml(d.code || d.id)}</span>
              <span class="hse-defect-dept-badge">${escapeHtml(d.dept_icon || '🏢')} ${escapeHtml(d.department || 'Bộ phận')}</span>
            </div>

            <div class="hse-defect-category-pill">
              <span>🏷️</span>
              <span>${escapeHtml(d.category || 'An toàn xưởng')}</span>
            </div>

            <p class="hse-defect-zh">${escapeHtml(d.zh_issue || '暂无详细描述')}</p>
            <p class="hse-defect-vn">${escapeHtml(d.vn_issue || '(Chưa có mô tả tiếng Việt)')}</p>
          </div>

          <!-- Card Footer -->
          <div class="hse-defect-footer" style="display:flex; justify-content:space-between; align-items:center;">
            <label class="hse-checkbox-label ${isDone ? 'done' : 'pending'}">
              <input type="checkbox" data-action="quick-toggle" data-id="${escapeHtml(d.id)}" ${isDone ? 'checked' : ''}>
              <span>${isDone ? `✓ Cải thiện (${escapeHtml(d.improve_date || 'Xong')})` : '⚠️ Chưa cải thiện'}</span>
            </label>

            <div style="display:inline-flex; gap:6px; align-items:center;">
              <button type="button" class="hse-btn-detail" data-action="edit-defect" data-id="${escapeHtml(d.id)}">
                ✏️ Sửa / 编辑
              </button>
              <button type="button" class="hse-btn-delete-defect" data-action="delete-defect" data-id="${escapeHtml(d.id)}" title="Xóa vĩnh viễn sự cố này" style="background:#fee2e2; color:#ef4444; border:1px solid #fca5a5; padding:5px 9px; border-radius:6px; font-size:12px; font-weight:700; cursor:pointer; transition:all 0.15s;">
                🗑️
              </button>
            </div>
          </div>
        </article>
      `;
    }).join("");
  }

  function renderTable(root, defects) {
    const rows = defects.map(d => {
      const isDone = Boolean(d.improved);
      const img = d.img_before || d.img_after || "";
      const rawDate = d.date || d.created_at || (d.month ? `${d.month}-01` : "---");
      const captionText = `${d.code || d.id} - ${d.zh_issue || d.vn_issue || ''}`;

      return `
        <tr data-defect-id="${escapeHtml(d.id || d.code)}" style="border-bottom:1px solid #e2e8f0; transition:background 0.15s;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background='transparent'">
          <!-- Cột A: Ngày ghi nhận (记录日期) -->
          <td style="padding:10px 12px; vertical-align:middle; white-space:nowrap;">
            <div style="font-weight:700; color:#0f172a; font-size:13px;">${escapeHtml(rawDate)}</div>
            <div style="font-family:monospace; font-size:11px; font-weight:800; color:#1e3a8a; margin-top:3px; background:#eff6ff; padding:2px 6px; border-radius:4px; display:inline-block; border:1px solid #dbeafe;">
              ${escapeHtml(d.code || d.id)}
            </div>
          </td>

          <!-- Cột B: Bộ phận (部门) -->
          <td style="padding:10px 12px; vertical-align:middle; white-space:nowrap;">
            <span class="hse-defect-dept-badge" style="font-size:12px; padding:4px 8px; border-radius:6px; background:#f1f5f9; color:#334155; font-weight:700; display:inline-flex; align-items:center; gap:4px; border:1px solid #cbd5e1;">
              ${escapeHtml(d.dept_icon || '🏢')} ${escapeHtml(d.department)}
            </span>
          </td>

          <!-- Cột C: Mô tả chi tiết (Tiếng Trung) -->
          <td style="padding:10px 12px; vertical-align:top; min-width:260px; max-width:380px;">
            <div style="font-size:13px; line-height:1.5; color:#0f172a; word-break:break-word; white-space:pre-wrap; font-weight:500;">
              ${escapeHtml(d.zh_issue || '---')}
            </div>
          </td>

          <!-- Cột D: Mô tả chi tiết (Tiếng Việt) -->
          <td style="padding:10px 12px; vertical-align:top; min-width:260px; max-width:380px;">
            <div style="font-size:13px; line-height:1.5; color:#334155; word-break:break-word; white-space:pre-wrap;">
              ${escapeHtml(d.vn_issue || '---')}
            </div>
          </td>

          <!-- Cột E: Xem ảnh (图片预览) -->
          <td style="padding:10px 12px; vertical-align:middle; text-align:center; white-space:nowrap;">
            ${img ? `
              <div style="display:inline-block; position:relative; cursor:pointer;" data-action="open-lightbox" data-src="${img}" data-caption="${escapeHtml(captionText)}" title="Click để phóng to ảnh chất lượng cao">
                <img src="${img}" alt="Ảnh hiện trường" style="width:72px; height:54px; object-fit:cover; border-radius:6px; border:1.5px solid #cbd5e1; box-shadow:0 1px 3px rgba(0,0,0,0.1); display:block; transition:transform 0.15s;" onmouseover="this.style.transform='scale(1.08)'" onmouseout="this.style.transform='scale(1)'">
                <span style="position:absolute; bottom:2px; right:2px; background:rgba(0,0,0,0.65); color:#fff; font-size:10px; border-radius:3px; padding:1px 4px; pointer-events:none;">🔍</span>
              </div>
            ` : `
              <span style="font-size:11px; color:#94a3b8; font-style:italic;">(Không có ảnh<br>无图片)</span>
            `}
          </td>

          <!-- Cột F: Trạng thái (状态) - Dropdown inline chuẩn 2 giá trị -->
          <td style="padding:10px 12px; vertical-align:middle; text-align:center; white-space:nowrap;">
            <select class="hse-table-status-select" data-id="${escapeHtml(d.id || d.code)}" style="padding:6px 10px; border-radius:6px; font-size:12.5px; font-weight:800; cursor:pointer; outline:none; border:1.5px solid ${isDone ? '#86efac' : '#fdba74'}; background:${isDone ? '#dcfce7' : '#ffedd5'}; color:${isDone ? '#166534' : '#9a3412'}; transition:all 0.15s;">
              <option value="Chưa cải thiện" ${!isDone ? 'selected' : ''} style="background:#ffedd5; color:#9a3412; font-weight:700;">Chưa cải thiện</option>
              <option value="Cải thiện" ${isDone ? 'selected' : ''} style="background:#dcfce7; color:#166534; font-weight:700;">Cải thiện</option>
            </select>
          </td>

          <!-- Cột G: Ngày cải thiện (改善日期) -->
          <td style="padding:10px 12px; vertical-align:middle; text-align:center; white-space:nowrap;">
            <input type="date" class="hse-table-improve-date" data-id="${escapeHtml(d.id || d.code)}" value="${escapeHtml(d.improve_date || '')}" ${!isDone ? 'disabled' : ''} style="width:125px; height:32px; padding:3px 6px; font-size:12px; border-radius:6px; border:1.5px solid ${isDone ? '#cbd5e1' : '#e2e8f0'}; background:${isDone ? '#ffffff' : '#f8fafc'}; color:${isDone ? '#0f172a' : '#94a3b8'}; cursor:${isDone ? 'pointer' : 'not-allowed'}; box-sizing:border-box;">
          </td>

          <!-- Cột Thao tác -->
          <td style="padding:10px 12px; vertical-align:middle; text-align:center; white-space:nowrap;">
            <div style="display:inline-flex; gap:6px; align-items:center;">
              <button type="button" class="hse-btn-edit-row" data-action="edit-defect" data-id="${escapeHtml(d.id || d.code)}" title="Chỉnh sửa chi tiết sự cố này" style="background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe; padding:5px 9px; border-radius:6px; font-size:12px; font-weight:700; cursor:pointer; display:inline-flex; align-items:center; gap:3px;">
                ✏️ Sửa
              </button>
              <button type="button" class="hse-btn-delete-row" data-action="delete-defect" data-id="${escapeHtml(d.id || d.code)}" title="Xóa vĩnh viễn sự cố này" style="background:#fee2e2; color:#ef4444; border:1px solid #fca5a5; padding:5px 9px; border-radius:6px; font-size:12px; font-weight:700; cursor:pointer; display:inline-flex; align-items:center; gap:3px;">
                🗑️
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join("");

    root.innerHTML = `
      <div class="hse-defects-table-wrapper" style="overflow-x:auto; background:#ffffff; border-radius:10px; border:1px solid #cbd5e1; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
        <table class="hse-defects-table" style="width:100%; border-collapse:collapse; min-width:1150px;">
          <thead style="background:#1e3a8a; color:#ffffff; position:sticky; top:0; z-index:10;">
            <tr style="height:44px;">
              <th style="padding:10px 12px; text-align:left; font-size:13px; font-weight:700; border-right:1px solid rgba(255,255,255,0.15); width:130px; white-space:nowrap;">
                Ngày ghi nhận<br><span style="font-size:11px; font-weight:400; opacity:0.85;">记录日期</span>
              </th>
              <th style="padding:10px 12px; text-align:left; font-size:13px; font-weight:700; border-right:1px solid rgba(255,255,255,0.15); width:180px; white-space:nowrap;">
                Bộ phận<br><span style="font-size:11px; font-weight:400; opacity:0.85;">部门</span>
              </th>
              <th style="padding:10px 12px; text-align:left; font-size:13px; font-weight:700; border-right:1px solid rgba(255,255,255,0.15); min-width:260px;">
                Mô tả chi tiết (Tiếng Trung)<br><span style="font-size:11px; font-weight:400; opacity:0.85;">详细描述 (中文)</span>
              </th>
              <th style="padding:10px 12px; text-align:left; font-size:13px; font-weight:700; border-right:1px solid rgba(255,255,255,0.15); min-width:260px;">
                Mô tả chi tiết (Tiếng Việt)<br><span style="font-size:11px; font-weight:400; opacity:0.85;">详细描述 (越南语)</span>
              </th>
              <th style="padding:10px 12px; text-align:center; font-size:13px; font-weight:700; border-right:1px solid rgba(255,255,255,0.15); width:110px; white-space:nowrap;">
                Xem ảnh<br><span style="font-size:11px; font-weight:400; opacity:0.85;">图片预览</span>
              </th>
              <th style="padding:10px 12px; text-align:center; font-size:13px; font-weight:700; border-right:1px solid rgba(255,255,255,0.15); width:160px; white-space:nowrap;">
                Trạng thái<br><span style="font-size:11px; font-weight:400; opacity:0.85;">状态</span>
              </th>
              <th style="padding:10px 12px; text-align:center; font-size:13px; font-weight:700; border-right:1px solid rgba(255,255,255,0.15); width:140px; white-space:nowrap;">
                Ngày cải thiện<br><span style="font-size:11px; font-weight:400; opacity:0.85;">改善日期</span>
              </th>
              <th style="padding:10px 12px; text-align:center; font-size:13px; font-weight:700; width:120px; white-space:nowrap;">
                Thao tác<br><span style="font-size:11px; font-weight:400; opacity:0.85;">操作</span>
              </th>
            </tr>
          </thead>
          <tbody>
            ${rows}
          </tbody>
        </table>
      </div>
    `;
  }

  // ==========================================================================
  // QUICK ACTIONS & DETAIL MODAL
  // ==========================================================================

  async function quickToggleStatus(defectId, isImproved) {
    try {
      const nowStr = new Date().toISOString().substring(0, 16).replace("T", " ");
      const payload = {
        defectId,
        improved: isImproved,
        improveDate: isImproved ? nowStr : "",
        note: ""
      };

      const resp = await fetch("/api/hse/defects/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!resp.ok) throw new Error("Không thể cập nhật trạng thái.");

      // Update in memory
      const target = state.allDefects.find(d => d.id === defectId || d.code === defectId);
      if (target) {
        target.improved = isImproved;
        target.status = isImproved ? "Cải thiện / 已改善" : "Chưa cải thiện / 未改善";
        target.improve_date = isImproved ? nowStr : "";
      }

      applyFilters();
      showToast(isImproved ? `✓ Đã cập nhật: CẢI THIỆN / 已改善 (${defectId})!` : `⚠️ Đã chuyển sang: CHƯA CẢI THIỆN / 未改善 (${defectId})`);
    } catch (e) {
      showToast(e.message, true);
    }
  }

  function openDetailModal(defectId) {
    const d = state.allDefects.find(x => x.id === defectId || x.code === defectId);
    if (!d) return;

    state.currentDetailDefect = d;
    state.pendingAfterImage = d.img_after || "";

    const modal = $("#hse-tracker-detail-modal");
    if (!modal) return;

    $("#modal-defect-title").textContent = `Chi Tiết Sự Cố: ${d.code || d.id}`;
    $("#modal-defect-code-badge").textContent = d.code || d.id;
    $("#modal-defect-dept-badge").textContent = `${d.dept_icon || '🏢'} ${d.department}`;
    $("#modal-defect-category").textContent = d.category || "An toàn xưởng";

    // Descriptions with elegant empty placeholders
    const zhEl = $("#modal-defect-zh");
    const vnEl = $("#modal-defect-vn");
    if (zhEl) {
      if (d.zh_issue && d.zh_issue.trim() && d.zh_issue.trim() !== "(Không có)") {
        zhEl.textContent = d.zh_issue;
        zhEl.style.fontStyle = "normal";
        zhEl.style.color = "#0f172a";
      } else {
        zhEl.innerHTML = '<span style="color:#94a3b8; font-style:italic; font-weight:normal;">(Chưa có mô tả)</span>';
      }
    }
    if (vnEl) {
      if (d.vn_issue && d.vn_issue.trim() && d.vn_issue.trim() !== "(Không có)") {
        vnEl.textContent = d.vn_issue;
        vnEl.style.fontStyle = "normal";
        vnEl.style.color = "#334155";
      } else {
        vnEl.innerHTML = '<span style="color:#94a3b8; font-style:italic; font-weight:normal;">(Chưa có mô tả)</span>';
      }
    }

    // Before Photo
    const bImg = $("#modal-photo-before");
    const bNo = $("#modal-no-photo-before");
    if (d.img_before) {
      bImg.src = d.img_before;
      bImg.style.display = "block";
      if (bNo) bNo.style.display = "none";
    } else {
      bImg.style.display = "none";
      if (bNo) bNo.style.display = "flex";
    }

    // After Photo
    updateModalAfterPhotoDisplay(state.pendingAfterImage);

    // Form inputs
    const isImproved = Boolean(d.improved);
    const sel = $("#modal-status-select");
    if (sel) sel.value = isImproved ? "improved" : "pending";
    const chk = $("#modal-status-chk");
    if (chk) chk.checked = isImproved;

    const dateInp = $("#modal-improve-date");
    if (dateInp) {
      dateInp.value = d.improve_date || (isImproved ? new Date().toISOString().substring(0, 10) : "");
    }

    const noteInp = $("#modal-note-inp");
    if (noteInp) {
      noteInp.value = d.note || "";
    }

    modal.classList.add("active", "is-open");
    modal.style.setProperty("display", "flex", "important");
  }

  function closeDetailModal() {
    const modal = $("#hse-tracker-detail-modal");
    if (modal) {
      modal.classList.remove("active", "is-open");
      modal.style.setProperty("display", "none", "important");
    }
    state.currentDetailDefect = null;
    state.pendingAfterImage = "";
  }

  function updateModalAfterPhotoDisplay(imgUrl) {
    const aImg = $("#modal-photo-after");
    const aNo = $("#modal-no-photo-after");
    if (imgUrl) {
      if (aImg) {
        aImg.src = imgUrl;
        aImg.style.display = "block";
      }
      if (aNo) aNo.style.display = "none";
    } else {
      if (aImg) aImg.style.display = "none";
      if (aNo) aNo.style.display = "flex";
    }
  }

  async function saveDetailModal() {
    if (!state.currentDetailDefect) return;

    try {
      setLoading(true, "Đang lưu thay đổi & đồng bộ...");
      const d = state.currentDetailDefect;
      const sel = $("#modal-status-select");
      const isImp = sel ? sel.value === "improved" : Boolean($("#modal-status-chk")?.checked);
      const dateInp = $("#modal-improve-date");
      const noteInp = $("#modal-note-inp");

      const payload = {
        defectId: d.code || d.id,
        improved: isImp,
        improveDate: isImp ? (dateInp?.value || new Date().toISOString().substring(0, 10)) : "",
        note: noteInp?.value || "",
        afterImageData: state.pendingAfterImage || ""
      };

      const resp = await fetch("/api/hse/defects/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!resp.ok) throw new Error("Lỗi khi lưu bản ghi.");

      // Update in local state
      d.improved = isImp;
      d.status = isImp ? "Cải thiện / 已改善" : "Chưa cải thiện / 未改善";
      d.improve_date = payload.improveDate;
      d.note = payload.note;
      if (payload.afterImageData) d.img_after = payload.afterImageData;

      applyFilters();
      closeDetailModal();
      showToast(`💾 Đã lưu & cập nhật sự cố ${d.code} thành công!`);
    } catch (e) {
      showToast(e.message, true);
    } finally {
      setLoading(false);
    }
  }

  // ==========================================================================
  // EXPORT EXCEL & GAS SYNC
  // ==========================================================================

  function exportMasterExcel(allMonths = true) {
    let url = "/api/hse/defects/export_master_excel?all=" + (allMonths ? "true" : "false");
    if (!allMonths) {
      url += `&month=${encodeURIComponent(state.selectedMonth)}&department=${encodeURIComponent(state.selectedDept)}&status=${encodeURIComponent(state.selectedStatus)}&search=${encodeURIComponent(state.searchQuery)}`;
    }
    showToast(`📊 Đang tạo file Excel Tổng Thể (kèm ảnh vào cell): ${allMonths ? 'Tất cả các tháng' : 'Theo bộ lọc'}...`);
    window.location.href = url;
  }

  function handleImportMasterExcel(file) {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    setLoading(true, "Đang đồng bộ dữ liệu từ Master Excel...");
    fetch("/api/hse/defects/import_master_excel", {
      method: "POST",
      body: formData
    })
    .then(r => r.json())
    .then(res => {
      if (res.success) {
        showToast("✅ " + (res.message || "Đã đồng bộ thành công!"));
        loadDefects(false);
      } else {
        showToast("❌ " + (res.detail || res.message || "Lỗi đồng bộ"), true);
      }
    })
    .catch(err => {
      showToast("❌ Lỗi: " + err.message, true);
    })
    .finally(() => {
      setLoading(false);
      const inp = $("#hse-tracker-import-file-input");
      if (inp) inp.value = "";
    });
  }

  async function syncGasNow() {
    try {
      setLoading(true, "Đang kết nối hai chiều với Google Apps Script Web App...");
      const savedGasUrl = localStorage.getItem("hse_gas_web_app_url") || localStorage.getItem("gas_web_app_url") || "";
      const resp = await fetch("/api/hse/defects/sync_gas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gas_url: savedGasUrl })
      });
      if (!resp.ok) throw new Error("Lỗi kết nối Google Apps Script.");
      const res = await resp.json();
      await loadDefects(false);
      if (res.is_html || (res.message && (res.message.includes("HTML") || res.message.includes("quyền truy cập")))) {
        showToast(`⚠️ ${res.message}`, true);
        openGasConfigModal(res.message);
      } else {
        showToast(`☁️ ${res.message || 'Đồng bộ GAS thành công!'}`);
      }
    } catch (e) {
      showToast(e.message, true);
    } finally {
      setLoading(false);
    }
  }

  function openGasConfigModal(notice = "") {
    let modal = $("#hse-gas-config-modal");
    if (!modal) return;
    const currentUrl = localStorage.getItem("hse_gas_web_app_url") || localStorage.getItem("gas_web_app_url") || "https://script.google.com/macros/s/AKfycbzc2q-vTj-8xCykJqEiH8a7rkfaLLpkpl6bOUuvJOBv86a5QpeqzT46twZuuyQkePg/exec";
    const inp = $("#hse-gas-url-input");
    if (inp) inp.value = currentUrl;
    const noticeEl = $("#hse-gas-modal-notice");
    if (noticeEl) {
      if (notice) {
        noticeEl.style.display = "block";
        noticeEl.textContent = notice;
      } else {
        noticeEl.style.display = "none";
      }
    }
    const testResultEl = $("#hse-gas-test-result");
    if (testResultEl) {
      testResultEl.style.display = "none";
      testResultEl.textContent = "";
    }
    modal.style.display = "flex";
  }

  function closeGasConfigModal() {
    const modal = $("#hse-gas-config-modal");
    if (modal) modal.style.display = "none";
  }

  async function testGasConnection() {
    const inp = $("#hse-gas-url-input");
    const testResultEl = $("#hse-gas-test-result");
    const btn = $("#hse-gas-test-btn");
    const url = (inp?.value || "").trim();
    if (!url || !url.includes("script.google.com")) {
      alert("Vui lòng nhập URL Web App hợp lệ bắt đầu bằng https://script.google.com/macros/s/.../exec");
      return;
    }
    if (btn) {
      btn.disabled = true;
      btn.textContent = "⏳ Đang kiểm tra...";
    }
    if (testResultEl) {
      testResultEl.style.display = "block";
      testResultEl.style.background = "#eff6ff";
      testResultEl.style.color = "#1d4ed8";
      testResultEl.textContent = "Đang gửi kiểm tra tới Google Apps Script...";
    }
    try {
      const resp = await fetch("/api/hse/defects/sync_gas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gas_url: url })
      });
      const data = await resp.json();
      if (data.is_html) {
        testResultEl.style.background = "#fef2f2";
        testResultEl.style.color = "#b91c1c";
        testResultEl.innerHTML = `❌ <b>Lỗi quyền truy cập (HTML):</b> Google yêu cầu đăng nhập.<br>👉 Bạn cần vào Google Apps Script > <b>Triển khai mới</b> > Đặt <b>Who has access</b> là <b>Anyone (Bất kỳ ai)</b>!`;
      } else if (data.success) {
        testResultEl.style.background = "#f0fdf4";
        testResultEl.style.color = "#15803d";
        testResultEl.innerHTML = `✅ <b>Kết nối thành công!</b> Đã tìm thấy ${data.remote_defects_count || 0} lỗi trên Google Sheet.`;
        localStorage.setItem("hse_gas_web_app_url", url);
        await loadDefects(false);
      } else {
        testResultEl.style.background = "#fffbeb";
        testResultEl.style.color = "#b45309";
        testResultEl.textContent = `⚠️ Phản hồi: ${data.message || 'Không có phản hồi'}`;
      }
    } catch (err) {
      testResultEl.style.background = "#fef2f2";
      testResultEl.style.color = "#b91c1c";
      testResultEl.textContent = `❌ Lỗi kết nối: ${err.message}`;
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "🔄 Kiểm Tra Kết Nối";
      }
    }
  }

  function saveGasConfig() {
    const inp = $("#hse-gas-url-input");
    const url = (inp?.value || "").trim();
    if (!url || !url.includes("script.google.com")) {
      alert("Vui lòng nhập URL Google Apps Script hợp lệ!");
      return;
    }
    localStorage.setItem("hse_gas_web_app_url", url);
    localStorage.setItem("gas_web_app_url", url);
    showToast("✓ Đã lưu cấu hình Google Apps Script!");
    closeGasConfigModal();
    syncGasNow();
  }

    async function deleteSingleDefect(defectId) {
    if (!defectId) return;
    if (!confirm(`⚠️ Bạn có chắc chắn muốn XÓA VĨNH VIỄN sự cố [${defectId}]?\n\nHành động này sẽ xóa sự cố khỏi hệ thống và đồng bộ xóa trên Google Sheet.`)) {
      return;
    }

    try {
      setLoading(true, `Đang xóa sự cố ${defectId}...`);

      // 1. Lưu Tombstone vào localStorage để UI không bao giờ nạp lại
      try {
        const deletedIds = JSON.parse(localStorage.getItem("deleted_hse_defect_ids") || "[]");
        if (!deletedIds.includes(defectId)) {
          deletedIds.push(defectId);
          localStorage.setItem("deleted_hse_defect_ids", JSON.stringify(deletedIds));
        }
      } catch (_) {}

      // 2. Gửi request DELETE tới Backend Server
      try {
        await fetch(`/api/hse/defects/${encodeURIComponent(defectId)}`, {
          method: "DELETE"
        });
      } catch (beErr) {
        console.warn("Backend defect delete error:", beErr);
      }

      // 3. Gửi trực tiếp lên GAS Web App nếu có URL
      const savedGasUrl = localStorage.getItem("hse_gas_web_app_url") || localStorage.getItem("gas_web_app_url") || "";
      if (savedGasUrl) {
        try {
          fetch(savedGasUrl, {
            method: "POST",
            mode: "no-cors",
            headers: { "Content-Type": "text/plain;charset=utf-8" },
            body: JSON.stringify({
              action: "deleteDefect",
              defectId: defectId,
              code: defectId,
              timestamp: new Date().toISOString()
            })
          }).catch(() => {});
        } catch (_) {}
      }

      // 4. Cập nhật state in-memory
      state.allDefects = state.allDefects.filter(d => d.id !== defectId && d.code !== defectId);
      applyFilters();

      // Cập nhật badge
      const badge = $("#nav-hse-tracker-count-badge");
      if (badge) {
        const total = state.allDefects.length;
        badge.textContent = `${total} LỖI`;
      }

      closeDetailModal();
      showToast(`🗑️ Đã xóa vĩnh viễn sự cố [${defectId}]!`);
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setLoading(false);
    }
  }

  async function clearAllDefects() {
    if (!confirm("⚠️ BẠN CÓ CHẮC CHẮN MUỐN XÓA TẤT CẢ SỰ CỐ LỖI HSE?\n\nHành động này sẽ xóa sạch toàn bộ sự cố lỗi HSE trên hệ thống và làm trống Google Sheet.\n\nBấm OK để tiếp tục, hoặc Hủy để dừng.")) {
      return;
    }
    const pwd = prompt("Nhập mật khẩu quản trị (270120) hoặc gõ 'XOA' để xác nhận:");
    if (!pwd || (pwd !== "270120" && pwd.toUpperCase() !== "XOA")) {
      alert("Mật khẩu không chính xác hoặc đã hủy thao tác.");
      return;
    }
    try {
      setLoading(true, "Đang xóa sạch toàn bộ sự cố HSE...");
      const resp = await fetch("/api/hse/defects/clear_all", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: pwd })
      });
      const res = await resp.json();
      if (!resp.ok || !res.success) throw new Error(res.detail || res.message || "Lỗi khi xóa dữ liệu HSE.");

      try {
        const nowIso = new Date().toISOString();
        localStorage.setItem("IS_DB_CLEARED_HSE", "true");
        localStorage.setItem("IS_DB_CLEARED", "true");
        localStorage.setItem("HSE_TRACKER_CLEARED", "true");
        localStorage.setItem("hse_cleared_at_timestamp", nowIso);
        localStorage.setItem("deleted_hse_defect_ids", "[]");
      } catch (_) {}

      // Gửi trực tiếp lên GAS Web App action clearAllDefects
      const savedGasUrl = localStorage.getItem("hse_gas_web_app_url") || localStorage.getItem("gas_web_app_url") || "";
      if (savedGasUrl) {
        try {
          fetch(savedGasUrl, {
            method: "POST",
            mode: "no-cors",
            headers: { "Content-Type": "text/plain;charset=utf-8" },
            body: JSON.stringify({
              action: "clearAllDefects",
              timestamp: new Date().toISOString()
            })
          }).catch(() => {});
        } catch (_) {}
      }

      state.allDefects = [];
      state.filteredDefects = [];
      state.kpis = { total: 0, improved: 0, pending: 0, rate: 0.0 };
      renderKPIs();
      renderDefectsView();

      const badge = $("#nav-hse-tracker-count-badge");
      if (badge) badge.textContent = "0 LỖI";

      showToast("🗑️ Đã xóa sạch toàn bộ sự cố HSE thành công!");
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setLoading(false);
    }
  }

  // Client Image Compression for after-photo upload in modal
  function compressImageClient(file, maxWidth = 1600, quality = 0.85) {
    return new Promise((resolve, reject) => {
      if (!file || !file.type || !file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
        return;
      }
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
          let width = img.width;
          let height = img.height;
          if (width > maxWidth) {
            height = Math.round((height * maxWidth) / width);
            width = maxWidth;
          }
          const canvas = document.createElement("canvas");
          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext("2d");
          ctx.drawImage(img, 0, 0, width, height);
          resolve(canvas.toDataURL("image/jpeg", quality));
        };
        img.onerror = () => resolve(e.target.result);
        img.src = e.target.result;
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  // ==========================================================================
  // EVENT BINDINGS & LIFECYCLE
  // ==========================================================================

  function bindEvents() {
    if (state.initialized) return;
    state.initialized = true;

    // Filter changes
    $("#hse-tracker-month-select")?.addEventListener("change", (e) => {
      state.selectedMonth = e.target.value;
      applyFilters();
    });

    $("#hse-tracker-dept-select")?.addEventListener("change", (e) => {
      state.selectedDept = e.target.value;
      applyFilters();
    });

    $("#hse-tracker-status-select")?.addEventListener("change", (e) => {
      state.selectedStatus = e.target.value;
      applyFilters();
    });

    $("#hse-tracker-search-inp")?.addEventListener("input", (e) => {
      state.searchQuery = e.target.value;
      applyFilters();
    });

    // View toggle
    $("#hse-view-cards-btn")?.addEventListener("click", () => {
      state.viewMode = "cards";
      $("#hse-view-cards-btn")?.classList.add("active");
      $("#hse-view-table-btn")?.classList.remove("active");
      renderDefectsView();
    });

    $("#hse-view-table-btn")?.addEventListener("click", () => {
      state.viewMode = "table";
      $("#hse-view-table-btn")?.classList.add("active");
      $("#hse-view-cards-btn")?.classList.remove("active");
      renderDefectsView();
    });

    // Toolbar buttons
    $("#hse-btn-sync-gas")?.addEventListener("click", syncGasNow);
    $("#hse-btn-config-gas")?.addEventListener("click", () => openGasConfigModal());
    $("#hse-gas-modal-close-btn")?.addEventListener("click", closeGasConfigModal);
    $("#hse-gas-save-btn")?.addEventListener("click", saveGasConfig);
    $("#hse-gas-test-btn")?.addEventListener("click", testGasConnection);
    $("#hse-btn-clear-all-defects")?.addEventListener("click", clearAllDefects);
    $("#hse-btn-excel-all")?.addEventListener("click", () => exportMasterExcel(true));
    $("#hse-btn-excel-filter")?.addEventListener("click", () => exportMasterExcel(false));
    $("#hse-btn-import-excel")?.addEventListener("click", () => $("#hse-tracker-import-file-input")?.click());
    $("#hse-tracker-import-file-input")?.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        handleImportMasterExcel(e.target.files[0]);
      }
    });

    // Nút Thêm Lỗi Mới (Mở Form 7 Trường Chuẩn Excel)
    $("#hse-btn-add-defect")?.addEventListener("click", () => openDefectFormModal(null));

    // Form CRUD Modal Events
    $("#hse-defect-crud-form")?.addEventListener("submit", handleDefectFormSubmit);
    $("#hse-form-modal-close-btn")?.addEventListener("click", closeDefectFormModal);
    $("#hse-form-cancel-btn")?.addEventListener("click", closeDefectFormModal);

    $("#hse-form-dept-select")?.addEventListener("change", (e) => {
      const isCustom = e.target.value === "__custom__";
      const customInp = $("#hse-form-dept-custom");
      if (customInp) {
        customInp.style.display = isCustom ? "block" : "none";
        if (isCustom) customInp.focus();
      }
    });

    $("#hse-form-status-select")?.addEventListener("change", (e) => {
      const val = e.target.value;
      updateFormStatusStyling(val);
      const dateInp = $("#hse-form-improve-date");
      if (val === "Cải thiện") {
        if (dateInp && !dateInp.value) {
          dateInp.value = new Date().toISOString().substring(0, 10);
        }
      } else {
        if (dateInp) dateInp.value = "";
      }
    });

    // AI Translation Buttons in Form
    $("#hse-btn-ai-translate-zh")?.addEventListener("click", translateVnToZh);
    $("#hse-btn-ai-translate-vn")?.addEventListener("click", translateZhToVn);

    // AI Vision Button in Form
    $("#hse-btn-ai-vision-analyze")?.addEventListener("click", analyzePhotoWithAIVision);

    // Form Image Upload & Remove
    $("#hse-form-img-preview-box")?.addEventListener("click", () => {
      $("#hse-form-file-input")?.click();
    });
    $("#hse-form-file-input")?.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        showToast("📸 Đang nén ảnh...");
        const compressed = await compressImageClient(file);
        updateFormImageDisplay(compressed);
        showToast("✓ Đã tải ảnh lên thành công!");
      } catch (err) {
        showToast("Lỗi nạp ảnh: " + err.message, true);
      } finally {
        e.target.value = "";
      }
    });
    $("#hse-form-remove-img-btn")?.addEventListener("click", () => {
      updateFormImageDisplay("");
      showToast("🗑️ Đã xóa ảnh!");
    });

    // Lightbox Controls
    $("#hse-lightbox-zoom-in")?.addEventListener("click", () => zoomLightbox(0.25));
    $("#hse-lightbox-zoom-out")?.addEventListener("click", () => zoomLightbox(-0.25));
    $("#hse-lightbox-rotate")?.addEventListener("click", rotateLightbox);
    $("#hse-lightbox-download")?.addEventListener("click", downloadLightboxImage);
    $("#hse-lightbox-close")?.addEventListener("click", closeLightbox);

    // Clipboard Paste Listener (Ctrl + V để dán ảnh vào Form)
    window.addEventListener("paste", async (e) => {
      const modal = $("#hse-defect-form-modal");
      if (!modal || modal.style.display === "none") return;

      const items = (e.clipboardData || e.originalEvent?.clipboardData)?.items;
      if (!items) return;

      for (const item of items) {
        if (item.type.indexOf("image") !== -1) {
          const blob = item.getAsFile();
          if (blob) {
            showToast("📸 Đang nạp ảnh từ Clipboard...");
            const compressed = await compressImageClient(blob);
            updateFormImageDisplay(compressed);
            showToast("✓ Đã dán ảnh từ Clipboard thành công!");
            break;
          }
        }
      }
    });

    // Global delegation for dynamic card/table clicks
    document.addEventListener("click", (e) => {
      // Lightbox open from image thumbnail
      const lbBtn = e.target.closest("[data-action='open-lightbox']");
      if (lbBtn) {
        openLightbox(lbBtn.dataset.src, lbBtn.dataset.caption);
        return;
      }

      // Edit defect in full form modal
      const editBtn = e.target.closest("[data-action='edit-defect']");
      if (editBtn) {
        openDefectFormModal(editBtn.dataset.id);
        return;
      }

      // Toggle before/after photo preview in card
      const togBtn = e.target.closest("[data-action='toggle-photo']");
      if (togBtn) {
        const targetId = togBtn.dataset.target;
        const src = togBtn.dataset.src;
        const imgEl = document.getElementById(targetId);
        if (imgEl && src) {
          imgEl.src = src;
          togBtn.parentElement.querySelectorAll(".hse-toggle-photo-btn").forEach(b => b.classList.remove("active"));
          togBtn.classList.add("active");
        }
        return;
      }

      // Quick toggle checkbox in card
      const chk = e.target.closest("input[data-action='quick-toggle']");
      if (chk) {
        quickToggleStatus(chk.dataset.id, chk.checked);
        return;
      }

      // Quick toggle button in table/card
      const qBtn = e.target.closest("[data-action='quick-toggle-btn']");
      if (qBtn) {
        const currentImproved = qBtn.dataset.improved === "true";
        quickToggleStatus(qBtn.dataset.id, !currentImproved);
        return;
      }

      // Delete single defect button
      const delBtn = e.target.closest("[data-action='delete-defect']");
      if (delBtn) {
        deleteSingleDefect(delBtn.dataset.id);
        return;
      }

      // Open detail modal
      const dBtn = e.target.closest("[data-action='open-detail']");
      if (dBtn) {
        openDetailModal(dBtn.dataset.id);
        return;
      }
    });

    // Inline Table Delegations (Status Select & Improve Date Input)
    document.addEventListener("change", (e) => {
      const statusSel = e.target.closest(".hse-table-status-select");
      if (statusSel) {
        const row = statusSel.closest("tr");
        handleInlineStatusChange(statusSel.dataset.id, statusSel.value, row);
        return;
      }
      const dtInp = e.target.closest(".hse-table-improve-date");
      if (dtInp) {
        handleInlineImproveDateChange(dtInp.dataset.id, dtInp.value);
        return;
      }
    });

    // Detail Modal actions
    $("#modal-close-btn")?.addEventListener("click", closeDetailModal);
    $("#modal-cancel-btn")?.addEventListener("click", closeDetailModal);
    $("#modal-save-btn")?.addEventListener("click", saveDetailModal);
    $("#modal-delete-defect-btn")?.addEventListener("click", () => {
      if (state.currentDetailDefect) {
        deleteSingleDefect(state.currentDetailDefect.code || state.currentDetailDefect.id);
      }
    });

    // Close on backdrop click
    const detailModal = $("#hse-tracker-detail-modal");
    detailModal?.addEventListener("click", (e) => {
      if (e.target === detailModal) {
        closeDetailModal();
      }
    });

    const gasModal = $("#hse-gas-config-modal");
    gasModal?.addEventListener("click", (e) => {
      if (e.target === gasModal) {
        closeGasConfigModal();
      }
    });

    const formModal = $("#hse-defect-form-modal");
    formModal?.addEventListener("click", (e) => {
      if (e.target === formModal) {
        closeDefectFormModal();
      }
    });

    const lbModal = $("#hse-image-lightbox-modal");
    lbModal?.addEventListener("click", (e) => {
      if (e.target === lbModal) {
        closeLightbox();
      }
    });

    // Close on Escape key
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        closeLightbox();
        closeDefectFormModal();
        closeDetailModal();
        closeGasConfigModal();
      }
    });

    // Copy mã nguồn Code.gs
    const setupCopyBtn = (btnId) => {
      const btn = $(btnId);
      btn?.addEventListener("click", async () => {
        try {
          btn.textContent = "⏳ Đang lấy mã...";
          let codeText = "";
          const preview = $("#hse-gas-code-preview");
          if (preview && preview.value.trim()) {
            codeText = preview.value;
          } else {
            const resp = await fetch("/api/hse/gas_code");
            if (resp.ok) {
              codeText = await resp.text();
              if (preview) preview.value = codeText;
            }
          }
          if (!codeText) throw new Error("Không thể tải mã Code.gs từ server.");

          await navigator.clipboard.writeText(codeText);
          btn.textContent = "✅ Đã Copy Mã GAS!";
          btn.style.background = "#059669";
          setTimeout(() => {
            btn.textContent = "📋 Copy Mã GAS";
            btn.style.background = "#16a34a";
          }, 3000);
          showToast("✓ Đã sao chép toàn bộ mã nguồn Code.gs! Bạn hãy dán đè vào Apps Script Editor.");
        } catch (err) {
          showToast("Lỗi sao chép: " + err.message, true);
          btn.textContent = "📋 Copy Mã GAS";
        }
      });
    };
    setupCopyBtn("#hse-gas-copy-code-btn");
    setupCopyBtn("#msds-gas-copy-code-btn");

    $("#hse-gas-toggle-code-btn")?.addEventListener("click", async () => {
      const preview = $("#hse-gas-code-preview");
      const btn = $("#hse-gas-toggle-code-btn");
      if (!preview) return;
      if (preview.style.display === "none") {
        if (!preview.value.trim()) {
          try {
            const resp = await fetch("/api/hse/gas_code");
            if (resp.ok) preview.value = await resp.text();
          } catch (_) {}
        }
        preview.style.display = "block";
        if (btn) btn.textContent = "🙈 Ẩn mã nguồn";
      } else {
        preview.style.display = "none";
        if (btn) btn.textContent = "👁️ Xem trước mã nguồn";
      }
    });

    // Status selection via dropdown or checkbox
    $("#modal-status-select")?.addEventListener("change", (e) => {
      const isImp = e.target.value === "improved";
      const chk = $("#modal-status-chk");
      if (chk) chk.checked = isImp;
      const dateInp = $("#modal-improve-date");
      if (isImp && dateInp && !dateInp.value.trim()) {
        const now = new Date();
        const yyyy = now.getFullYear();
        const mm = String(now.getMonth() + 1).padStart(2, "0");
        const dd = String(now.getDate()).padStart(2, "0");
        const hh = String(now.getHours()).padStart(2, "0");
        const min = String(now.getMinutes()).padStart(2, "0");
        dateInp.value = `${yyyy}-${mm}-${dd} ${hh}:${min}`;
      } else if (!isImp && dateInp) {
        dateInp.value = "";
      }
    });

    // Auto-fill completion date when checkbox is checked
    $("#modal-status-chk")?.addEventListener("change", (e) => {
      const chk = e.target;
      const sel = $("#modal-status-select");
      if (sel) sel.value = chk.checked ? "improved" : "pending";
      const dateInp = $("#modal-improve-date");
      if (chk && chk.checked && dateInp && !dateInp.value.trim()) {
        const now = new Date();
        const yyyy = now.getFullYear();
        const mm = String(now.getMonth() + 1).padStart(2, "0");
        const dd = String(now.getDate()).padStart(2, "0");
        const hh = String(now.getHours()).padStart(2, "0");
        const min = String(now.getMinutes()).padStart(2, "0");
        dateInp.value = `${yyyy}-${mm}-${dd} ${hh}:${min}`;
      } else if (chk && !chk.checked && dateInp) {
        dateInp.value = "";
      }
    });

    // Modal after photo upload
    $("#modal-upload-after-inp")?.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        showToast("📸 Đang nén ảnh...");
        const compressed = await compressImageClient(file);
        state.pendingAfterImage = compressed;
        updateModalAfterPhotoDisplay(compressed);
        const chk = $("#modal-status-chk");
        if (chk) {
          chk.checked = true; // Auto-check when after-photo uploaded
          const dateInp = $("#modal-improve-date");
          if (dateInp && !dateInp.value.trim()) {
            const now = new Date();
            const yyyy = now.getFullYear();
            const mm = String(now.getMonth() + 1).padStart(2, "0");
            const dd = String(now.getDate()).padStart(2, "0");
            const hh = String(now.getHours()).padStart(2, "0");
            const min = String(now.getMinutes()).padStart(2, "0");
            dateInp.value = `${yyyy}-${mm}-${dd} ${hh}:${min}`;
          }
        }
        showToast("✓ Đã nạp ảnh sau cải thiện!");
      } catch (err) {
        showToast("Lỗi nạp ảnh: " + err.message, true);
      }
    });
  }

  // Public entrypoint
  window.initHseDefectTracker = function() {
    bindEvents();
    loadDefects();
  };

  window.HseDefectTracker = {
    loadDefects,
    deleteSingleDefect,
    clearAllDefects,
    applyFilters,
    exportMasterExcel,
    syncGasNow,
    openGasConfigModal,
    closeGasConfigModal,
    openDetailModal,
    closeDetailModal,
    openDefectFormModal,
    closeDefectFormModal,
    openLightbox,
    closeLightbox,
    testGasConnection,
    saveGasConfig
  };
  window.HSEDefectTracker = window.HseDefectTracker;

  // Lắng nghe các sự kiện vòng đời báo cáo để cập nhật UI tức thì không cần F5
  window.addEventListener("hse-report-saved", () => {
    loadDefects(false);
  });
  window.addEventListener("hse-report-deleted", () => {
    loadDefects(false);
  });

  // Tự động khởi chạy ngầm khi tải trang để nạp số đếm badge Navbar
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      bindEvents();
      loadDefects(false);
    });
  } else {
    setTimeout(() => {
      bindEvents();
      loadDefects(false);
    }, 100);
  }
})();
