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
    viewMode: "cards", // "cards" | "table"
    kpis: { total: 0, improved: 0, pending: 0, rate: 0.0 },
    availableMonths: [],
    availableDepts: [],
    currentDetailDefect: null,
    pendingAfterImage: "",
    initialized: false
  };

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

  async function loadDefects(syncGas = false) {
    try {
      if (syncGas) setLoading(true, "Đang kết nối & đồng bộ Google Apps Script...");

      const resp = await fetch("/api/hse/defects");
      if (!resp.ok) throw new Error(`Lỗi tải dữ liệu (Mã ${resp.status})`);
      const data = await resp.json();

      state.allDefects = data.defects || [];
      state.availableMonths = data.available_months || [];
      state.availableDepts = data.available_departments || [];

      // Update badge on main header
      const badge = $("#nav-hse-tracker-count-badge");
      if (badge) {
        badge.textContent = `${data.total || state.allDefects.length} LỖI`;
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
    // 1. Month dropdown
    const mSelect = $("#hse-tracker-month-select");
    if (mSelect) {
      const curVal = state.selectedMonth;
      let mHtml = `<option value="all">🌟 Tất cả các tháng / 全部月份 (${state.allDefects.length} lỗi)</option>`;
      for (const m of state.availableMonths) {
        const count = state.allDefects.filter(d => d.month === m).length;
        mHtml += `<option value="${escapeHtml(m)}" ${curVal === m ? "selected" : ""}>📅 Tháng ${escapeHtml(m)} (${count} lỗi)</option>`;
      }
      mSelect.innerHTML = mHtml;
      mSelect.value = curVal;
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

  function renderCards(root, defects) {
    root.innerHTML = defects.map(d => {
      const isDone = Boolean(d.improved);
      const hasAfterImg = Boolean(d.img_after);
      const hasBeforeImg = Boolean(d.img_before);
      const initialImg = (isDone && hasAfterImg) ? d.img_after : (d.img_before || d.img_after || "");

      return `
        <article class="hse-defect-card ${isDone ? "card-improved" : ""}" data-id="${escapeHtml(d.id)}">
          <!-- Card Photo Box -->
          <div class="hse-defect-photo-box">
            ${initialImg ? `
              <img src="${initialImg}" alt="Ảnh sự cố" id="photo-${escapeHtml(d.id)}" loading="lazy">
            ` : `
              <div class="hse-defect-no-photo">
                <span style="font-size:26px;">📸</span>
                <span>(Không có ảnh / 无图片)</span>
              </div>
            `}

            <!-- Month Tag -->
            <div class="hse-photo-month-tag">📅 ${escapeHtml(d.month || 'HSE')}</div>

            <!-- Status Badge -->
            <div class="hse-photo-status-badge ${isDone ? 'done' : 'pending'}">
              ${isDone ? '✓ ĐÃ CẢI THIỆN / 已改善' : '• CHỜ XỬ LÝ / 待处理'}
            </div>

            <!-- Before/After Toggle Switch if both photos exist -->
            ${(hasBeforeImg && hasAfterImg) ? `
              <div class="hse-photo-toggle-bar">
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

            ${d.note ? `
              <div class="hse-defect-note-box">
                <strong>Đối sách / 改善对策:</strong> ${escapeHtml(d.note)}
              </div>
            ` : ""}
          </div>

          <!-- Card Footer -->
          <div class="hse-defect-footer">
            <label class="hse-checkbox-label ${isDone ? 'done' : 'pending'}">
              <input type="checkbox" data-action="quick-toggle" data-id="${escapeHtml(d.id)}" ${isDone ? 'checked' : ''}>
              <span>${isDone ? `✓ Đã cải thiện (${escapeHtml(d.improve_date || 'Xong')})` : '✕ Chờ xử lý'}</span>
            </label>

            <button type="button" class="hse-btn-detail" data-action="open-detail" data-id="${escapeHtml(d.id)}">
              Chi Tiết / 详情
            </button>
          </div>
        </article>
      `;
    }).join("");
  }

  function renderTable(root, defects) {
    const rows = defects.map(d => {
      const isDone = Boolean(d.improved);
      const img = d.img_before || d.img_after || "";

      return `
        <tr>
          <td style="font-family:monospace; font-weight:800; color:#0f172a; white-space:nowrap;">
            ${escapeHtml(d.code || d.id)}
          </td>
          <td style="white-space:nowrap; font-weight:600;">
            ${escapeHtml(d.month || '---')}
          </td>
          <td style="white-space:nowrap;">
            <span class="hse-defect-dept-badge">${escapeHtml(d.dept_icon || '🏢')} ${escapeHtml(d.department)}</span>
          </td>
          <td style="text-align:center;">
            ${img ? `
              <img src="${img}" alt="Ảnh" style="width:48px; height:36px; object-fit:cover; border-radius:4px; border:1px solid #cbd5e1; cursor:pointer;" onclick="window.open('${img}', '_blank')" title="Bấm mở ảnh lớn">
            ` : `<span style="font-size:11px; color:#94a3b8;">无图片</span>`}
          </td>
          <td style="max-width:380px;">
            <div style="font-weight:700; color:#0f172a; line-height:1.35; margin-bottom:3px;">${escapeHtml(d.zh_issue)}</div>
            <div style="font-size:12px; font-style:italic; color:#64748b;">${escapeHtml(d.vn_issue)}</div>
          </td>
          <td style="text-align:center; white-space:nowrap;">
            <span class="hse-photo-status-badge ${isDone ? 'done' : 'pending'}" style="position:static; box-shadow:none;">
              ${isDone ? '✓ ĐÃ CẢI THIỆN' : '• CHỜ XỬ LÝ'}
            </span>
          </td>
          <td style="font-size:12px; color:#64748b; white-space:nowrap;">
            ${escapeHtml(d.improve_date || '---')}
          </td>
          <td style="text-align:right; white-space:nowrap;">
            <div style="display:inline-flex; gap:6px;">
              <button type="button" class="hse-btn-detail" data-action="quick-toggle-btn" data-id="${escapeHtml(d.id)}" data-improved="${isDone}">
                ${isDone ? 'Hủy hoàn thành' : '✓ Hoàn thành'}
              </button>
              <button type="button" class="hse-btn-detail" data-action="open-detail" data-id="${escapeHtml(d.id)}">
                Chi Tiết
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join("");

    root.innerHTML = `
      <div class="hse-defects-table-wrapper">
        <table class="hse-defects-table">
          <thead>
            <tr>
              <th>Mã sự cố</th>
              <th>Tháng</th>
              <th>Bộ phận</th>
              <th style="text-align:center;">Ảnh</th>
              <th>Mô tả chi tiết song ngữ (中/越)</th>
              <th style="text-align:center;">Trạng thái</th>
              <th>Ngày cải thiện</th>
              <th style="text-align:right;">Thao tác</th>
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
        target.status = isImproved ? "Đã cải thiện / 已改善" : "Chờ xử lý / 待处理";
        target.improve_date = isImproved ? nowStr : "";
      }

      applyFilters();
      showToast(isImproved ? `✓ Đã cập nhật: ĐÃ CẢI THIỆN (${defectId})!` : `Đã chuyển sang CHỜ XỬ LÝ (${defectId})`);
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
    $("#modal-defect-zh").textContent = d.zh_issue || "(Không có)";
    $("#modal-defect-vn").textContent = d.vn_issue || "(Không có)";

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
    const chk = $("#modal-status-chk");
    if (chk) chk.checked = Boolean(d.improved);

    const dateInp = $("#modal-improve-date");
    if (dateInp) {
      dateInp.value = d.improve_date || new Date().toISOString().substring(0, 10);
    }

    const noteInp = $("#modal-note-inp");
    if (noteInp) {
      noteInp.value = d.note || "";
    }

    modal.style.display = "flex";
  }

  function closeDetailModal() {
    const modal = $("#hse-tracker-detail-modal");
    if (modal) modal.style.display = "none";
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
      const chk = $("#modal-status-chk");
      const isImp = chk ? chk.checked : d.improved;
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
      d.status = isImp ? "Đã cải thiện / 已改善" : "Chờ xử lý / 待处理";
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
    showToast(`📊 Đang tạo file Excel Tổng Thể: ${allMonths ? 'Tất cả các tháng' : 'Theo bộ lọc'}...`);
    window.location.href = url;
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
        localStorage.setItem("IS_DB_CLEARED_HSE", "true");
        localStorage.setItem("IS_DB_CLEARED", "true");
      } catch (_) {}

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

    // Global delegation for dynamic card/table clicks
    document.addEventListener("click", (e) => {
      // Toggle before/after photo preview
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

      // Quick toggle checkbox
      const chk = e.target.closest("input[data-action='quick-toggle']");
      if (chk) {
        quickToggleStatus(chk.dataset.id, chk.checked);
        return;
      }

      // Quick toggle button in table
      const qBtn = e.target.closest("[data-action='quick-toggle-btn']");
      if (qBtn) {
        const currentImproved = qBtn.dataset.improved === "true";
        quickToggleStatus(qBtn.dataset.id, !currentImproved);
        return;
      }

      // Open detail modal
      const dBtn = e.target.closest("[data-action='open-detail']");
      if (dBtn) {
        openDetailModal(dBtn.dataset.id);
        return;
      }
    });

    // Detail Modal actions
    $("#modal-close-btn")?.addEventListener("click", closeDetailModal);
    $("#modal-cancel-btn")?.addEventListener("click", closeDetailModal);
    $("#modal-save-btn")?.addEventListener("click", saveDetailModal);

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
        if (chk) chk.checked = true; // Auto-check when after-photo uploaded
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
    applyFilters,
    exportMasterExcel,
    syncGasNow,
    openGasConfigModal,
    closeGasConfigModal,
    testGasConnection,
    saveGasConfig
  };
})();
