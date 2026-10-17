/**
 * ============================================================================
 * TitanPDF — Monthly Chemical Inventory & Usage Tracking (NXT) Module
 * Script: static/monthly_inventory.js
 * 
 * Complies 100% with Vietnamese Chemical Regulations:
 * - Law on Chemicals No. 69/2025/QH15
 * - Decree 24/2026/NĐ-CP (Annex I, II, III, IV storage thresholds, V)
 * - Decree 26/2026/NĐ-CP (Industrial Precursors, Category IV.C)
 * - Circular 01/2026/TT-BCT & Circular 02/2026/TT-BCT
 * ============================================================================
 */

(() => {
  'use strict';

  // --------------------------------------------------------------------------
  // 1. MODULE STATE
  // --------------------------------------------------------------------------
  const state = {
    periods: [],
    currentPeriodKey: null,
    currentPeriod: null,
    records: [],
    transactions: [],
    kpi: null,
    cilChemicals: [],
    viewMode: 'summary', // 'summary' | 'transactions'
    searchQuery: '',
    filterStatus: 'all', // 'all' | 'warning' | 'negative' | 'decree24'
    isLoading: false,
    initialized: false,
    saveDebounceTimers: {}
  };

  const API_BASE = '/api/monthly-inventory';

  // --------------------------------------------------------------------------
  // 2. UTILITY HELPERS
  // --------------------------------------------------------------------------
  const byId = (id) => document.getElementById(id);

  function isGuestUser() {
    return document.body?.getAttribute('data-role') === 'guest' || sessionStorage.getItem('luv_user_role') === 'guest';
  }

  function escapeHtml(val) {
    if (val === null || val === undefined) return '';
    return String(val)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatNum(num, decimals = 2) {
    if (num === null || num === undefined || isNaN(num)) return '0';
    const n = Number(num);
    return n.toLocaleString('vi-VN', {
      minimumFractionDigits: 0,
      maximumFractionDigits: decimals
    });
  }

  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `nxt-toast nxt-toast-${type}`;
    toast.style.cssText = `
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 10000;
      padding: 12px 20px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 600;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      animation: nxtToastFade 250ms ease-out;
      background: ${type === 'success' ? '#059669' : type === 'error' ? '#dc2626' : '#2563eb'};
      color: #ffffff;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 300ms ease';
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  }

  // --------------------------------------------------------------------------
  // 3. INITIALIZATION & DATA FETCHING
  // --------------------------------------------------------------------------
  async function initMonthlyInventory() {
    console.log('[NXT] initMonthlyInventory called');
    if (!state.initialized) {
      bindEvents();
      state.initialized = true;
    }

    try {
      state.isLoading = true;
      renderLoading();
      await loadCilChemicals();
      await loadPeriods();
    } catch (err) {
      console.error('[NXT] Initialization failed:', err);
      showToast('Lỗi nạp dữ liệu phân hệ Báo Cáo Tháng: ' + err.message, 'error');
    } finally {
      state.isLoading = false;
    }
  }

  async function loadCilChemicals() {
    try {
      const res = await fetch('/api/msds/chemicals');
      if (res.ok) {
        const data = await res.json();
        state.cilChemicals = Array.isArray(data) ? data : (data.items || []);
      }
    } catch (err) {
      console.warn('[NXT] Failed to prefetch CIL chemicals:', err);
    }
  }

  async function loadPeriods() {
    const res = await fetch(`${API_BASE}/periods`);
    if (!res.ok) throw new Error('Không thể lấy danh sách kỳ báo cáo');
    const data = await res.json();
    state.periods = Array.isArray(data) ? data : (data.items || data.periods || []);

    // Populate period selector
    const select = byId('nxt-period-select');
    if (!select) return;

    select.innerHTML = '';
    if (state.periods.length === 0) {
      // Create current month default
      const now = new Date();
      await createPeriod(now.getMonth() + 1, now.getFullYear(), true);
      return;
    }

    state.periods.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.period_key;
      opt.textContent = `Tháng ${p.month}/${p.year} — ${p.title || 'Kỳ chuẩn'} (${p.status === 'LOCKED' ? '🔒 Đã Khóa' : '🔓 Đang Mở'})`;
      select.appendChild(opt);
    });

    // Default to current month (e.g. 2026-10) if present, or previously selected, or first period
    const now = new Date();
    const currentMonthKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;

    if (!state.currentPeriodKey || !state.periods.some(p => p.period_key === state.currentPeriodKey)) {
      const matchCurrent = state.periods.find(p => p.period_key === currentMonthKey);
      state.currentPeriodKey = matchCurrent ? matchCurrent.period_key : state.periods[0].period_key;
    }
    select.value = state.currentPeriodKey;

    await loadPeriodData(state.currentPeriodKey);
  }

  async function loadPeriodData(periodKey) {
    state.currentPeriodKey = periodKey;
    state.currentPeriod = state.periods.find((p) => p.period_key === periodKey);

    renderHeader();

    // Fetch records, transactions, KPIs in parallel
    const [recRes, transRes, kpiRes] = await Promise.all([
      fetch(`${API_BASE}/records?period_key=${encodeURIComponent(periodKey)}`),
      fetch(`${API_BASE}/transactions?period_key=${encodeURIComponent(periodKey)}`),
      fetch(`${API_BASE}/kpi?period_key=${encodeURIComponent(periodKey)}`)
    ]);

    if (recRes.ok) {
      const recData = await recRes.json();
      state.records = Array.isArray(recData) ? recData : (recData.records || recData.items || []);
      if (recData.kpi) {
        state.kpi = recData.kpi;
      }
    } else {
      state.records = [];
    }

    if (transRes.ok) {
      const transData = await transRes.json();
      state.transactions = Array.isArray(transData) ? transData : (transData.transactions || transData.items || []);
    } else {
      state.transactions = [];
    }

    if (kpiRes.ok) {
      state.kpi = await kpiRes.json();
    } else {
      state.kpi = null;
    }

    renderKpis();
    renderContent();
  }

  // --------------------------------------------------------------------------
  // 4. RENDERING FUNCTIONS
  // --------------------------------------------------------------------------
  function renderHeader() {
    const p = state.currentPeriod;
    const badge = byId('nxt-period-status-badge');
    const lockBtn = byId('nxt-btn-lock-toggle');

    if (p && badge) {
      const isLocked = p.status === 'LOCKED' || p.status === 'CLOSED';
      badge.className = `nxt-period-badge ${isLocked ? 'locked' : ''}`;
      badge.textContent = isLocked ? '🔒 Đã Khóa Sổ' : '🔓 Đang Mở Ghi Nhận';
      if (lockBtn) {
        lockBtn.textContent = isLocked ? '🔓 Mở Lại Kỳ' : '🔒 Khóa Sổ Kỳ';
        lockBtn.title = isLocked ? 'Mở lại kỳ để cho phép sửa đổi' : 'Khóa sổ kỳ để ngăn sửa đổi số liệu';
      }
    }

    // Prev / Next button states
    const select = byId('nxt-period-select');
    const prevBtn = byId('nxt-btn-period-prev');
    const nextBtn = byId('nxt-btn-period-next');
    if (select && prevBtn && nextBtn) {
      const idx = select.selectedIndex;
      prevBtn.disabled = idx >= select.options.length - 1;
      nextBtn.disabled = idx <= 0;
    }

    // Nav pill count badge
    const navBadge = byId('nav-monthly-count-badge');
    if (navBadge) {
      navBadge.textContent = state.records.length > 0 ? `${state.records.length} chất` : 'NXT';
    }
  }

  function renderKpis() {
    const kpi = state.kpi;
    const recs = state.records;

    const countElem = byId('nxt-kpi-total-chem');
    const importElem = byId('nxt-kpi-total-import');
    const exportElem = byId('nxt-kpi-total-export');
    const balanceElem = byId('nxt-kpi-ending-balance');
    const alertElem = byId('nxt-kpi-alert-status');

    if (countElem) {
      countElem.textContent = kpi ? kpi.total_chemicals : recs.length;
    }

    if (importElem) {
      const totalImp = kpi ? kpi.total_import : recs.reduce((acc, r) => acc + (Number(r.import_qty) || 0), 0);
      importElem.textContent = formatNum(totalImp) + ' kg/L';
    }

    if (exportElem) {
      const totalExp = kpi ? kpi.total_export : recs.reduce((acc, r) => acc + (Number(r.export_qty) || 0), 0);
      exportElem.textContent = formatNum(totalExp) + ' kg/L';
    }

    if (balanceElem) {
      const totalBal = kpi ? kpi.total_closing : recs.reduce((acc, r) => acc + (Number(r.closing_stock) || 0), 0);
      balanceElem.textContent = formatNum(totalBal) + ' kg/L';
    }

    if (alertElem) {
      const warnCount = kpi ? (kpi.warning_count || 0) : recs.filter(r => r.has_warning || r.closing_stock < 0).length;
      if (warnCount > 0) {
        alertElem.innerHTML = `<span class="nxt-status-pill nxt-status-danger">⚠️ ${warnCount} cảnh báo tồn kho</span>`;
      } else {
        alertElem.innerHTML = `<span class="nxt-status-pill nxt-status-safe">🟢 Tất cả đạt định mức an toàn</span>`;
      }
    }
  }

  function renderContent() {
    if (state.viewMode === 'summary') {
      renderSummaryGrid();
    } else {
      renderTransactionsTable();
    }
  }

  function renderLoading() {
    const container = byId('nxt-table-container');
    if (!container) return;
    container.innerHTML = `
      <div class="nxt-state-box">
        <div class="nxt-spinner" style="font-size:2rem; animation: spin 1s linear infinite;">⏳</div>
        <strong>Đang nạp dữ liệu Báo Cáo Hóa Chất Tháng...</strong>
        <p>Vui lòng chờ trong giây lát.</p>
      </div>
    `;
  }

  // --------------------------------------------------------------------------
  // 5. SUMMARY DATA GRID (INLINE EDITING & AUTO BALANCE)
  // --------------------------------------------------------------------------
  function renderSummaryGrid() {
    const container = byId('nxt-table-container');
    if (!container) return;

    let filtered = [...state.records];

    // Filter by search query
    if (state.searchQuery.trim()) {
      const q = state.searchQuery.trim().toLowerCase();
      filtered = filtered.filter(
        (r) =>
          (r.chemical_name && r.chemical_name.toLowerCase().includes(q)) ||
          (r.product_name && r.product_name.toLowerCase().includes(q)) ||
          (r.chemical_name_vi && r.chemical_name_vi.toLowerCase().includes(q)) ||
          (r.chemical_id && r.chemical_id.toLowerCase().includes(q)) ||
          (r.cas_number && r.cas_number.toLowerCase().includes(q)) ||
          (r.storage_location && r.storage_location.toLowerCase().includes(q))
      );
    }

    // Filter by status dropdown
    if (state.filterStatus === 'warning') {
      filtered = filtered.filter((r) => r.has_warning || (r.safety_threshold > 0 && r.closing_stock > r.safety_threshold));
    } else if (state.filterStatus === 'negative') {
      filtered = filtered.filter((r) => r.closing_stock < 0);
    } else if (state.filterStatus === 'decree24') {
      filtered = filtered.filter((r) => r.is_conditional || r.is_special_control || r.is_precursor);
    }

    if (filtered.length === 0) {
      container.innerHTML = `
        <div class="nxt-state-box">
          <div class="nxt-state-icon">📋</div>
          <strong>Chưa có hóa chất nào trong kỳ báo cáo này</strong>
          ${isGuestUser() ? '<p>Tài khoản Khách ở chế độ chỉ đọc.</p>' : `
          <p>Bấm nút <b>"➕ Thêm Hóa Chất Từ CIL"</b> để chọn các hóa chất cần theo dõi trong tháng.</p>
          <button class="nxt-btn nxt-btn-primary" onclick="window.openMonthlyAddCilModal()">
            ➕ Thêm Hóa Chất Từ Sổ CIL
          </button>
          `}
        </div>
      `;
      return;
    }

    const isGuest = isGuestUser();
    const isLocked = (state.currentPeriod && (state.currentPeriod.status === 'LOCKED' || state.currentPeriod.status === 'CLOSED')) || isGuest;

    let html = `
      <div class="nxt-table-wrapper">
        <table class="nxt-table">
          <thead>
            <tr>
              <th style="width: 45px; text-align: center;">STT</th>
              <th style="width: 110px;">Mã SP</th>
              <th style="min-width: 220px;">Tên Hóa Chất & CAS</th>
              <th style="width: 140px;">Phân Loại Pháp Lý</th>
              <th style="width: 60px; text-align: center;">ĐVT</th>
              <th style="width: 115px; text-align: right;">Tồn Đầu Kỳ</th>
              <th style="width: 115px; text-align: right;">Nhập Trong Kỳ</th>
              <th style="width: 115px; text-align: right;">Xuất Sử Dụng</th>
              <th style="width: 125px; text-align: right;">Tồn Cuối Kỳ</th>
              <th style="width: 140px; text-align: center;">Ngưỡng NĐ 24</th>
              <th style="min-width: 130px;">Vị Trí Kho</th>
              <th style="width: 110px; text-align: center;">Thao Tác</th>
            </tr>
          </thead>
          <tbody>
    `;

    filtered.forEach((r, idx) => {
      const closing = (Number(r.opening_stock) || 0) + (Number(r.import_qty) || 0) - (Number(r.export_qty) || 0);
      const isNegative = closing < 0;
      const isOverThreshold = r.safety_threshold > 0 && closing > r.safety_threshold;
      const isNearThreshold = r.safety_threshold > 0 && closing > r.safety_threshold * 0.8 && !isOverThreshold;

      let balanceClass = 'safe';
      let statusHtml = '<span class="nxt-status-pill nxt-status-safe">🟢 An toàn</span>';

      if (isNegative) {
        balanceClass = 'danger';
        statusHtml = '<span class="nxt-status-pill nxt-status-danger" title="Tồn kho âm - Cần kiểm tra phiếu nhập">⚠️ TỒN ÂM</span>';
      } else if (isOverThreshold) {
        balanceClass = 'danger';
        statusHtml = `<span class="nxt-status-pill nxt-status-danger" title="Vượt ngưỡng tồn trữ quy định tại Phụ lục IV NĐ 24 (${r.safety_threshold} kg)">🔴 VƯỢT NGƯỠNG</span>`;
      } else if (isNearThreshold) {
        balanceClass = 'warning';
        statusHtml = `<span class="nxt-status-pill nxt-status-warn" title="Tiệm cận ngưỡng an toàn (${r.safety_threshold} kg)">🟡 CẬN NGƯỠNG</span>`;
      }

      // Legal tags
      let legalTags = [];
      if (r.is_precursor) legalTags.push('<span class="nxt-status-pill nxt-status-warn" style="font-size:0.65rem;">Tiền chất NĐ 26</span>');
      if (r.is_conditional) legalTags.push('<span class="nxt-status-pill nxt-status-safe" style="font-size:0.65rem;">Có ĐK NĐ 24</span>');
      if (r.is_special_control) legalTags.push('<span class="nxt-status-pill nxt-status-danger" style="font-size:0.65rem;">Kiểm soát ĐB</span>');
      if (legalTags.length === 0) legalTags.push('<span style="color:var(--nxt-text-muted); font-size:0.75rem;">Thông thường</span>');

      html += `
        <tr id="nxt-row-${r.id}" data-record-id="${r.id}">
          <td style="text-align: center;" class="nxt-col-num">${idx + 1}</td>
          <td>
            <strong style="font-family:var(--nxt-font-mono); font-size:0.8rem; color:var(--nxt-text-primary);">${escapeHtml(r.chemical_id)}</strong>
          </td>
          <td>
            <div class="nxt-chem-name-cell">
              <span class="nxt-chem-name">${escapeHtml(r.chemical_name || r.product_name || r.chemical_name_vi || r.chemical_id)}</span>
              <div class="nxt-chem-code-row">
                ${r.cas_number ? `<span class="nxt-cas-badge">CAS: ${escapeHtml(r.cas_number)}</span>` : ''}
                ${r.supplier ? `<span>${escapeHtml(r.supplier)}</span>` : ''}
              </div>
            </div>
          </td>
          <td>
            <div style="display:flex; flex-direction:column; gap:0.2rem;">
              ${legalTags.join('')}
            </div>
          </td>
          <td style="text-align: center; font-weight:600; color:var(--nxt-text-secondary);">
            ${escapeHtml(r.unit || 'kg')}
          </td>
          <td style="text-align: right;">
            <input 
              type="number" 
              step="any" 
              class="nxt-num-input" 
              id="nxt-open-${r.id}" 
              value="${r.opening_stock ?? 0}" 
              ${isLocked ? 'disabled' : ''}
              oninput="window.handleNxtInlineChange(${r.id})"
            />
          </td>
          <td style="text-align: right;">
            <input 
              type="number" 
              step="any" 
              class="nxt-num-input" 
              id="nxt-imp-${r.id}" 
              value="${r.import_qty ?? 0}" 
              ${isLocked ? 'disabled' : ''}
              oninput="window.handleNxtInlineChange(${r.id})"
            />
          </td>
          <td style="text-align: right;">
            <input 
              type="number" 
              step="any" 
              class="nxt-num-input" 
              id="nxt-exp-${r.id}" 
              value="${r.export_qty ?? 0}" 
              ${isLocked ? 'disabled' : ''}
              oninput="window.handleNxtInlineChange(${r.id})"
            />
          </td>
          <td style="text-align: right;">
            <div class="nxt-balance-cell ${balanceClass}" id="nxt-bal-${r.id}">
              ${formatNum(closing)}
            </div>
          </td>
          <td style="text-align: center;" id="nxt-status-${r.id}">
            ${statusHtml}
            ${r.safety_threshold > 0 ? `<div style="font-size:0.7rem; color:var(--nxt-text-muted); margin-top:2px;">Định mức: ${formatNum(r.safety_threshold)} ${r.unit || 'kg'}</div>` : ''}
          </td>
          <td>
            <input 
              type="text" 
              class="nxt-num-input" 
              style="width:100%; text-align:left;" 
              id="nxt-loc-${r.id}" 
              value="${escapeHtml(r.storage_location || '')}" 
              placeholder="Vị trí kho..." 
              ${isLocked ? 'disabled' : ''}
              onchange="window.saveNxtRecord(${r.id})"
            />
          </td>
          <td style="text-align: center;">
            ${isGuest ? '<span style="color:var(--nxt-text-muted); font-size:0.75rem;">Chỉ xem</span>' : `
            <div class="nxt-action-cell" style="justify-content: center;">
              <button 
                class="nxt-btn-mini nxt-btn-mini-save" 
                id="nxt-save-btn-${r.id}" 
                title="Lưu dòng này" 
                onclick="window.saveNxtRecord(${r.id})"
                ${isLocked ? 'disabled' : ''}
              >
                💾
              </button>
              <button 
                class="nxt-btn-mini" 
                title="Tạo phiếu nhập/xuất cho chất này" 
                onclick="window.openTransactionModalForChemical('${escapeHtml(r.chemical_id)}')"
                ${isLocked ? 'disabled' : ''}
              >
                📝
              </button>
              <button 
                class="nxt-btn-mini nxt-btn-mini-danger" 
                title="Xóa chất này khỏi kỳ" 
                onclick="window.deleteNxtRecord(${r.id})"
                ${isLocked ? 'disabled' : ''}
              >
                🗑️
              </button>
            </div>
            `}
          </td>
        </tr>
      `;
    });

    html += `
          </tbody>
        </table>
      </div>
    `;

    container.innerHTML = html;
  }

  // --------------------------------------------------------------------------
  // 6. DETAILED TRANSACTIONS TABLE (NHẬT KÝ PHIẾU GIAO DỊCH)
  // --------------------------------------------------------------------------
  function renderTransactionsTable() {
    const container = byId('nxt-table-container');
    if (!container) return;

    let filtered = [...state.transactions];

    if (state.searchQuery.trim()) {
      const q = state.searchQuery.trim().toLowerCase();
      filtered = filtered.filter(
        (t) =>
          (t.chemical_name_vi && t.chemical_name_vi.toLowerCase().includes(q)) ||
          (t.chemical_id && t.chemical_id.toLowerCase().includes(q)) ||
          (t.reference_doc && t.reference_doc.toLowerCase().includes(q)) ||
          (t.department && t.department.toLowerCase().includes(q)) ||
          (t.purpose && t.purpose.toLowerCase().includes(q))
      );
    }

    if (filtered.length === 0) {
      container.innerHTML = `
        <div class="nxt-state-box">
          <div class="nxt-state-icon">📝</div>
          <strong>Chưa có phiếu giao dịch nào trong kỳ này</strong>
          ${isGuestUser() ? '<p>Tài khoản Khách ở chế độ chỉ đọc.</p>' : `
          <p>Bấm nút <b>"📝 Ghi Phiếu Nhập / Xuất"</b> để thêm giao dịch xuất kho hoặc nhập kho chi tiết.</p>
          <button class="nxt-btn nxt-btn-info" onclick="window.openMonthlyTransactionModal()">
            📝 Thêm Phiếu Giao Dịch Mới
          </button>
          `}
        </div>
      `;
      return;
    }

    const isGuest = isGuestUser();
    const isLocked = (state.currentPeriod && (state.currentPeriod.status === 'LOCKED' || state.currentPeriod.status === 'CLOSED')) || isGuest;

    let html = `
      <div class="nxt-table-wrapper">
        <table class="nxt-table">
          <thead>
            <tr>
              <th style="width: 45px; text-align: center;">STT</th>
              <th style="width: 100px;">Ngày</th>
              <th style="width: 105px; text-align: center;">Loại Phiếu</th>
              <th style="width: 100px;">Mã Hóa Chất</th>
              <th style="min-width: 200px;">Tên Hóa Chất</th>
              <th style="width: 110px; text-align: right;">Số Lượng</th>
              <th style="width: 55px; text-align: center;">ĐVT</th>
              <th style="width: 130px;">Số Chứng Từ / PO</th>
              <th style="min-width: 150px;">Bộ Phận / Phân Xưởng</th>
              <th style="min-width: 160px;">Mục Đích Sử Dụng</th>
              <th style="width: 70px; text-align: center;">Xóa</th>
            </tr>
          </thead>
          <tbody>
    `;

    filtered.forEach((t, idx) => {
      const isImport = t.transaction_type === 'IMPORT';
      const badgeClass = isImport ? 'nxt-status-info' : 'nxt-status-warn';
      const typeText = isImport ? '📥 Nhập Kho' : '📤 Xuất Dùng';

      html += `
        <tr>
          <td style="text-align: center;" class="nxt-col-num">${idx + 1}</td>
          <td style="font-family:var(--nxt-font-mono);">${escapeHtml(t.transaction_date || '')}</td>
          <td style="text-align: center;">
            <span class="nxt-status-pill ${badgeClass}">${typeText}</span>
          </td>
          <td><strong style="font-family:var(--nxt-font-mono); font-size:0.8rem;">${escapeHtml(t.chemical_id)}</strong></td>
          <td>
            <div class="nxt-chem-name-cell">
              <span class="nxt-chem-name">${escapeHtml(t.chemical_name_vi || t.chemical_id)}</span>
            </div>
          </td>
          <td style="text-align: right; font-family:var(--nxt-font-mono); font-weight:700;">
            ${formatNum(t.quantity)}
          </td>
          <td style="text-align: center; color:var(--nxt-text-secondary);">${escapeHtml(t.unit || 'kg')}</td>
          <td><span style="font-family:var(--nxt-font-mono); font-size:0.75rem;">${escapeHtml(t.reference_doc || '—')}</span></td>
          <td>${escapeHtml(t.department || '—')}</td>
          <td>${escapeHtml(t.purpose || '—')}</td>
          <td style="text-align: center;">
            ${isGuest ? '<span style="color:var(--nxt-text-muted); font-size:0.75rem;">—</span>' : `
            <button 
              class="nxt-btn-mini nxt-btn-mini-danger" 
              title="Xóa phiếu giao dịch này" 
              onclick="window.deleteNxtTransaction(${t.id})"
              ${isLocked ? 'disabled' : ''}
            >
              🗑️
            </button>
            `}
          </td>
        </tr>
      `;
    });

    html += `
          </tbody>
        </table>
      </div>
    `;

    container.innerHTML = html;
  }

  // --------------------------------------------------------------------------
  // 7. INLINE RECORD UPDATES & REAL-TIME CALCULATION
  // --------------------------------------------------------------------------
  function handleNxtInlineChange(recordId) {
    const openInp = byId(`nxt-open-${recordId}`);
    const impInp = byId(`nxt-imp-${recordId}`);
    const expInp = byId(`nxt-exp-${recordId}`);
    const balElem = byId(`nxt-bal-${recordId}`);
    const statusElem = byId(`nxt-status-${recordId}`);

    if (!openInp || !impInp || !expInp || !balElem) return;

    const opening = parseFloat(openInp.value) || 0;
    const imp = parseFloat(impInp.value) || 0;
    const exp = parseFloat(expInp.value) || 0;

    // Real-time Ending Balance: Ending = Opening + Import - Export
    const ending = opening + imp - exp;
    balElem.textContent = formatNum(ending);

    const rec = state.records.find((r) => r.id === recordId);
    const threshold = rec ? rec.safety_threshold : 0;

    balElem.classList.remove('safe', 'warning', 'danger');
    if (ending < 0) {
      balElem.classList.add('danger');
      if (statusElem) statusElem.innerHTML = '<span class="nxt-status-pill nxt-status-danger">⚠️ TỒN ÂM</span>';
    } else if (threshold > 0 && ending > threshold) {
      balElem.classList.add('danger');
      if (statusElem) statusElem.innerHTML = '<span class="nxt-status-pill nxt-status-danger">🔴 VƯỢT NGƯỠNG</span>';
    } else if (threshold > 0 && ending > threshold * 0.8) {
      balElem.classList.add('warning');
      if (statusElem) statusElem.innerHTML = '<span class="nxt-status-pill nxt-status-warn">🟡 CẬN NGƯỠNG</span>';
    } else {
      balElem.classList.add('safe');
      if (statusElem) statusElem.innerHTML = '<span class="nxt-status-pill nxt-status-safe">🟢 An toàn</span>';
    }

    // Mark input as changed
    openInp.classList.add('changed');
    impInp.classList.add('changed');
    expInp.classList.add('changed');

    // Debounced autosave after 800ms
    if (state.saveDebounceTimers[recordId]) {
      clearTimeout(state.saveDebounceTimers[recordId]);
    }
    state.saveDebounceTimers[recordId] = setTimeout(() => {
      saveNxtRecord(recordId, false);
    }, 800);
  }

  async function saveNxtRecord(recordId, showSuccessToast = true) {
    if (isGuestUser()) {
      showToast("Khách (Guest) chỉ có quyền Xem & Xuất báo cáo, không thể lưu số liệu.", "warn");
      return;
    }
    const openInp = byId(`nxt-open-${recordId}`);
    const impInp = byId(`nxt-imp-${recordId}`);
    const expInp = byId(`nxt-exp-${recordId}`);
    const locInp = byId(`nxt-loc-${recordId}`);

    if (!openInp || !impInp || !expInp) return;

    const payload = {
      opening_stock: parseFloat(openInp.value) || 0,
      import_qty: parseFloat(impInp.value) || 0,
      export_qty: parseFloat(expInp.value) || 0,
      storage_location: locInp ? locInp.value.trim() : ''
    };

    try {
      const res = await fetch(`${API_BASE}/records/${recordId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Lưu thất bại');
      }

      const updated = await res.json();

      // Update in state
      const idx = state.records.findIndex((r) => r.id === recordId);
      if (idx !== -1) {
        state.records[idx] = { ...state.records[idx], ...updated.record };
      }

      openInp.classList.remove('changed');
      impInp.classList.remove('changed');
      expInp.classList.remove('changed');

      if (showSuccessToast) {
        showToast('Đã lưu số liệu hóa chất thành công!', 'success');
      }

      // Re-fetch KPIs
      const kpiRes = await fetch(`${API_BASE}/kpi?period_key=${encodeURIComponent(state.currentPeriodKey)}`);
      if (kpiRes.ok) {
        state.kpi = await kpiRes.json();
        renderKpis();
      }
    } catch (err) {
      console.error('[NXT] Save record error:', err);
      showToast('Lỗi khi lưu số liệu: ' + err.message, 'error');
    }
  }

  async function deleteNxtRecord(recordId) {
    if (isGuestUser()) {
      showToast("Khách (Guest) không có quyền xóa hóa chất khỏi kỳ báo cáo.", "warn");
      return;
    }
    if (!confirm('Bạn có chắc chắn muốn bỏ hóa chất này khỏi kỳ báo cáo hiện tại?')) return;

    try {
      const token = sessionStorage.getItem("luv_auth_token") || localStorage.getItem("luv_auth_token") || "verified";
      const role = sessionStorage.getItem("luv_user_role") || "owner";
      const res = await fetch(`${API_BASE}/records/${recordId}`, {
        method: 'DELETE',
        headers: {
          'X-Titan-Session': token,
          'X-Titan-Role': role,
          'Authorization': 'Bearer ' + token
        }
      });
      if (!res.ok) throw new Error('Không thể xóa hóa chất khỏi kỳ');
      showToast('Đã xóa hóa chất khỏi kỳ báo cáo', 'success');
      await loadPeriodData(state.currentPeriodKey);
    } catch (err) {
      showToast('Lỗi: ' + err.message, 'error');
    }
  }

  async function deleteNxtTransaction(transactionId) {
    if (isGuestUser()) {
      showToast("Khách (Guest) không có quyền xóa giao dịch.", "warn");
      return;
    }
    if (!confirm('Bạn có chắc muốn xóa phiếu giao dịch này? Số dư kỳ sẽ được tự động tính toán lại.')) return;

    try {
      const token = sessionStorage.getItem("luv_auth_token") || localStorage.getItem("luv_auth_token") || "verified";
      const role = sessionStorage.getItem("luv_user_role") || "owner";
      const res = await fetch(`${API_BASE}/transactions/${transactionId}`, {
        method: 'DELETE',
        headers: {
          'X-Titan-Session': token,
          'X-Titan-Role': role,
          'Authorization': 'Bearer ' + token
        }
      });
      if (!res.ok) throw new Error('Không thể xóa giao dịch');
      showToast('Đã xóa phiếu giao dịch thành công!', 'success');
      await loadPeriodData(state.currentPeriodKey);
    } catch (err) {
      showToast('Lỗi: ' + err.message, 'error');
    }
  }

  // --------------------------------------------------------------------------
  // 8. PERIOD CREATION & MANAGEMENT
  // --------------------------------------------------------------------------
  async function createPeriod(month, year, autoLoad = true) {
    if (isGuestUser()) {
      showToast("Khách (Guest) không có quyền tạo kỳ báo cáo mới.", "warn");
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/periods`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          month: parseInt(month, 10),
          year: parseInt(year, 10),
          title: `Kỳ Tháng ${month}/${year}`,
          copy_from_previous: true,
          auto_roll_forward: true
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Không thể tạo kỳ mới');
      }

      showToast(`Đã tạo kỳ Tháng ${month}/${year} thành công!`, 'success');
      await loadPeriods();

      if (autoLoad) {
        const newKey = `${year}-${String(month).padStart(2, '0')}`;
        const select = byId('nxt-period-select');
        if (select) select.value = newKey;
        await loadPeriodData(newKey);
      }
    } catch (err) {
      showToast('Lỗi tạo kỳ mới: ' + err.message, 'error');
    }
  }

  async function togglePeriodLock() {
    if (isGuestUser()) {
      showToast("Khách (Guest) không có quyền khóa hoặc mở sổ kỳ báo cáo.", "warn");
      return;
    }
    if (!state.currentPeriod) return;
    const isLocked = state.currentPeriod.status === 'LOCKED' || state.currentPeriod.status === 'CLOSED';
    const newStatus = isLocked ? 'OPEN' : 'LOCKED';
    const confirmMsg = isLocked
      ? 'Bạn có muốn mở lại kỳ báo cáo này để tiếp tục ghi nhận giao dịch?'
      : 'Khóa sổ kỳ báo cáo sẽ chốt số liệu và ngăn việc sửa đổi. Tiếp tục?';

    if (!confirm(confirmMsg)) return;

    try {
      const res = await fetch(`${API_BASE}/periods/${state.currentPeriodKey}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      });

      if (!res.ok) throw new Error('Không thể thay đổi trạng thái kỳ');
      showToast(`Đã ${newStatus === 'LOCKED' ? 'khóa sổ' : 'mở lại'} kỳ báo cáo thành công!`, 'success');
      await loadPeriods();
    } catch (err) {
      showToast('Lỗi: ' + err.message, 'error');
    }
  }

  async function rollForwardCurrentPeriod() {
    if (isGuestUser()) {
      showToast("Khách (Guest) không có quyền kết chuyển số dư kỳ.", "warn");
      return;
    }
    if (!state.currentPeriod) return;
    if (!confirm(`Bạn có muốn kế thừa toàn bộ Tồn cuối kỳ ${state.currentPeriodKey} sang làm Tồn đầu kỳ của tháng tiếp theo?`)) return;

    try {
      const res = await fetch(`${API_BASE}/roll-forward`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          from_period: state.currentPeriodKey,
          overwrite_initial: true
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Chuyển số dư thất bại');
      }

      const data = await res.json();
      showToast(`Chuyển số dư thành công! Đã cập nhật ${data.records_transferred || data.transferred || 0} hóa chất sang kỳ sau.`, 'success');
      await loadPeriods();
    } catch (err) {
      showToast('Lỗi chuyển kỳ sau: ' + err.message, 'error');
    }
  }

  // --------------------------------------------------------------------------
  // 9. EXCEL EXPORT & PRINT
  // --------------------------------------------------------------------------
  function exportMonthlyExcel() {
    if (!state.currentPeriodKey) return;
    showToast('Đang tạo tệp Báo Cáo Excel chuyên nghiệp...', 'info');
    const url = `${API_BASE}/export-excel?period_key=${encodeURIComponent(state.currentPeriodKey)}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = `Bao_Cao_Hoa_Chat_Thang_${state.currentPeriodKey}.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  function exportMonthlyPdf() {
    if (!state.currentPeriodKey) return;
    showToast('Đang kết xuất tệp Báo Cáo PDF chính thức (A4 Ngang)...', 'info');
    const url = `${API_BASE}/export-pdf?period_key=${encodeURIComponent(state.currentPeriodKey)}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = `Bao_Cao_Hoa_Chat_Thang_${state.currentPeriodKey}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  function openImportExcelModal() {
    if (isGuestUser()) {
      showToast("Khách (Guest) không có quyền nhập file Excel vào sổ.", "warn");
      return;
    }
    const modal = byId('nxt-modal-import-excel');
    if (!modal) return;
    const fileInp = byId('nxt-import-excel-file');
    const msg = byId('nxt-import-result-msg');
    if (fileInp) fileInp.value = '';
    if (msg) {
      msg.style.display = 'none';
      msg.textContent = '';
    }
    modal.classList.remove('hidden');
  }

  function closeImportExcelModal() {
    const modal = byId('nxt-modal-import-excel');
    if (modal) modal.classList.add('hidden');
  }

  async function submitImportExcel() {
    if (isGuestUser()) {
      showToast("Khách (Guest) không có quyền nhập file Excel vào sổ.", "warn");
      return;
    }
    const fileInp = byId('nxt-import-excel-file');
    const msg = byId('nxt-import-result-msg');
    const btn = byId('nxt-btn-submit-import-excel');

    if (!fileInp || !fileInp.files || fileInp.files.length === 0) {
      showToast('Vui lòng chọn một tệp Excel (.xlsx) để nạp', 'error');
      return;
    }

    const file = fileInp.files[0];
    const formData = new FormData();
    formData.append('file', file);
    formData.append('period_key', state.currentPeriodKey);

    try {
      if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳ Đang phân tích & nạp...';
      }
      showToast('Đang đọc và phân tích file Excel kho...', 'info');

      const res = await fetch(`${API_BASE}/import-excel`, {
        method: 'POST',
        body: formData
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Nạp file thất bại');
      }

      showToast(data.message || 'Nạp dữ liệu từ Excel thành công!', 'success');
      closeImportExcelModal();
      await loadPeriodData(state.currentPeriodKey);
    } catch (err) {
      if (msg) {
        msg.style.display = 'block';
        msg.style.background = '#fef2f2';
        msg.style.color = '#dc2626';
        msg.style.border = '1px solid #fecaca';
        msg.textContent = '❌ Lỗi: ' + err.message;
      }
      showToast('Lỗi nạp Excel: ' + err.message, 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = '⚡ Bắt Đầu Nạp Dữ Liệu';
      }
    }
  }

  function printMonthlyReport() {
    if (!state.currentPeriodKey) return;
    const url = `${API_BASE}/print-html?period_key=${encodeURIComponent(state.currentPeriodKey)}`;
    const w = window.open(url, '_blank', 'width=1100,height=800,menubar=no,toolbar=no');
    if (w) {
      w.focus();
    } else {
      window.print();
    }
  }

  // --------------------------------------------------------------------------
  // 10. MODALS: ADD CHEMICALS FROM CIL & NEW TRANSACTION
  // --------------------------------------------------------------------------
  function openAddCilModal() {
    if (isGuestUser()) {
      showToast("Khách (Guest) không có quyền thêm hóa chất vào kỳ.", "warn");
      return;
    }
    const modal = byId('nxt-modal-add-cil');
    if (!modal) return;

    modal.classList.remove('hidden');
    renderCilModalList();
  }

  function closeAddCilModal() {
    const modal = byId('nxt-modal-add-cil');
    if (modal) modal.classList.add('hidden');
  }

  function renderCilModalList() {
    const container = byId('nxt-cil-modal-list');
    const searchInp = byId('nxt-cil-search-input');
    if (!container) return;

    const query = searchInp ? searchInp.value.trim().toLowerCase() : '';
    const currentChemIds = new Set(state.records.map((r) => r.chemical_id));

    let list = state.cilChemicals;
    if (query) {
      list = list.filter(
        (c) =>
          (c.name_vi && c.name_vi.toLowerCase().includes(query)) ||
          (c.name_en && c.name_en.toLowerCase().includes(query)) ||
          (c.chemical_id && c.chemical_id.toLowerCase().includes(query)) ||
          (c.cas_number && c.cas_number.toLowerCase().includes(query))
      );
    }

    if (list.length === 0) {
      container.innerHTML = `<div style="padding:20px; text-align:center; color:var(--nxt-text-muted);">Không tìm thấy hóa chất nào khớp với từ khóa</div>`;
      return;
    }

    let html = '';
    list.forEach((c) => {
      const alreadyIn = currentChemIds.has(c.chemical_id);
      html += `
        <label class="nxt-cil-item" style="cursor:${alreadyIn ? 'default' : 'pointer'}; opacity:${alreadyIn ? 0.6 : 1};">
          <input 
            type="checkbox" 
            name="nxt-cil-select" 
            value="${escapeHtml(c.chemical_id)}" 
            ${alreadyIn ? 'checked disabled' : ''} 
          />
          <div class="nxt-cil-info">
            <div style="display:flex; align-items:center; gap:8px;">
              <strong style="font-family:var(--nxt-font-mono); font-size:0.8rem;">${escapeHtml(c.chemical_id)}</strong>
              <span style="font-weight:600; font-size:0.85rem;">${escapeHtml(c.name_vi || c.name_en || c.chemical_id)}</span>
              ${alreadyIn ? '<span class="nxt-status-pill nxt-status-info" style="font-size:0.65rem;">Đã có trong kỳ</span>' : ''}
            </div>
            <div style="font-size:0.75rem; color:var(--nxt-text-muted); display:flex; gap:12px;">
              ${c.cas_number ? `<span>CAS: ${escapeHtml(c.cas_number)}</span>` : ''}
              ${c.unit ? `<span>ĐVT: ${escapeHtml(c.unit)}</span>` : ''}
            </div>
          </div>
        </label>
      `;
    });

    container.innerHTML = html;
  }

  async function submitAddCilChemicals() {
    if (isGuestUser()) {
      showToast("Khách (Guest) không có quyền thêm hóa chất vào kỳ.", "warn");
      return;
    }
    const checkboxes = document.querySelectorAll('input[name="nxt-cil-select"]:checked:not(:disabled)');
    const ids = Array.from(checkboxes).map((cb) => cb.value);

    if (ids.length === 0) {
      showToast('Vui lòng chọn ít nhất một hóa chất từ danh sách', 'info');
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/chemicals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          period_key: state.currentPeriodKey,
          chemical_ids: ids
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Không thể thêm hóa chất');
      }

      showToast(`Đã thêm thành công ${ids.length} hóa chất vào kỳ báo cáo!`, 'success');
      closeAddCilModal();
      await loadPeriodData(state.currentPeriodKey);
    } catch (err) {
      showToast('Lỗi: ' + err.message, 'error');
    }
  }

  function openTransactionModal(chemId = '', transType = 'EXPORT') {
    if (isGuestUser()) {
      showToast("Khách (Guest) không có quyền lập phiếu giao dịch.", "warn");
      return;
    }
    const modal = byId('nxt-modal-transaction');
    if (!modal) return;

    // Populate chemical select
    const chemSelect = byId('nxt-trans-chemical-select');
    if (chemSelect) {
      chemSelect.innerHTML = '<option value="">-- Chọn Hóa Chất --</option>';
      state.records.forEach((r) => {
        const opt = document.createElement('option');
        opt.value = r.chemical_id;
        opt.textContent = `${r.chemical_id} — ${r.chemical_name_vi || r.chemical_name_en} (${r.unit || 'kg'})`;
        if (chemId && r.chemical_id === chemId) {
          opt.selected = true;
        }
        chemSelect.appendChild(opt);
      });
    }

    // Set today date
    const dateInp = byId('nxt-trans-date');
    if (dateInp) {
      const today = new Date().toISOString().split('T')[0];
      dateInp.value = today;
    }

    // Set transaction type radio
    const radioImp = byId('nxt-trans-type-import');
    const radioExp = byId('nxt-trans-type-export');
    if (transType === 'IMPORT' && radioImp) radioImp.checked = true;
    if (transType === 'EXPORT' && radioExp) radioExp.checked = true;

    // Clear other inputs
    const qtyInp = byId('nxt-trans-qty');
    const docInp = byId('nxt-trans-doc');
    const deptInp = byId('nxt-trans-dept');
    const purpInp = byId('nxt-trans-purpose');
    const noteInp = byId('nxt-trans-notes');
    if (qtyInp) qtyInp.value = '';
    if (docInp) docInp.value = '';
    if (deptInp) deptInp.value = '';
    if (purpInp) purpInp.value = '';
    if (noteInp) noteInp.value = '';

    modal.classList.remove('hidden');
  }

  function closeTransactionModal() {
    const modal = byId('nxt-modal-transaction');
    if (modal) modal.classList.add('hidden');
  }

  async function submitTransaction() {
    if (isGuestUser()) {
      showToast("Khách (Guest) không có quyền lập phiếu giao dịch.", "warn");
      return;
    }
    const chemSelect = byId('nxt-trans-chemical-select');
    const radioImp = byId('nxt-trans-type-import');
    const qtyInp = byId('nxt-trans-qty');
    const dateInp = byId('nxt-trans-date');
    const docInp = byId('nxt-trans-doc');
    const deptInp = byId('nxt-trans-dept');
    const purpInp = byId('nxt-trans-purpose');
    const noteInp = byId('nxt-trans-notes');

    if (!chemSelect || !chemSelect.value) {
      showToast('Vui lòng chọn hóa chất', 'error');
      return;
    }

    const qty = parseFloat(qtyInp ? qtyInp.value : 0);
    if (!qty || qty <= 0) {
      showToast('Vui lòng nhập số lượng hợp lệ (> 0)', 'error');
      return;
    }

    const payload = {
      period_key: state.currentPeriodKey,
      chemical_id: chemSelect.value,
      transaction_type: radioImp && radioImp.checked ? 'IMPORT' : 'EXPORT',
      quantity: qty,
      transaction_date: dateInp ? dateInp.value : '',
      reference_doc: docInp ? docInp.value.trim() : '',
      department: deptInp ? deptInp.value.trim() : '',
      purpose: purpInp ? purpInp.value.trim() : '',
      notes: noteInp ? noteInp.value.trim() : ''
    };

    try {
      const res = await fetch(`${API_BASE}/transactions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Lưu phiếu giao dịch thất bại');
      }

      showToast('Đã lưu phiếu giao dịch thành công!', 'success');
      closeTransactionModal();
      await loadPeriodData(state.currentPeriodKey);
    } catch (err) {
      showToast('Lỗi: ' + err.message, 'error');
    }
  }

  // --------------------------------------------------------------------------
  // 11. EVENT BINDING
  // --------------------------------------------------------------------------
  function bindEvents() {
    // Period select
    const pSelect = byId('nxt-period-select');
    if (pSelect) {
      pSelect.addEventListener('change', (e) => {
        loadPeriodData(e.target.value);
      });
    }

    // Prev / Next period buttons
    const prevBtn = byId('nxt-btn-period-prev');
    const nextBtn = byId('nxt-btn-period-next');
    if (prevBtn && pSelect) {
      prevBtn.addEventListener('click', () => {
        if (pSelect.selectedIndex < pSelect.options.length - 1) {
          pSelect.selectedIndex++;
          loadPeriodData(pSelect.value);
        }
      });
    }
    if (nextBtn && pSelect) {
      nextBtn.addEventListener('click', () => {
        if (pSelect.selectedIndex > 0) {
          pSelect.selectedIndex--;
          loadPeriodData(pSelect.value);
        }
      });
    }

    // Create period button
    const createBtn = byId('nxt-btn-create-period');
    if (createBtn) {
      createBtn.addEventListener('click', () => {
        const modal = byId('nxt-modal-new-period');
        if (modal) {
          // Pre-populate with current + 1 month
          const now = new Date();
          const mInp = byId('nxt-new-period-month');
          const yInp = byId('nxt-new-period-year');
          if (mInp) mInp.value = now.getMonth() === 11 ? 1 : now.getMonth() + 2;
          if (yInp) yInp.value = now.getMonth() === 11 ? now.getFullYear() + 1 : now.getFullYear();
          modal.classList.remove('hidden');
        }
      });
    }

    // Mode Switcher buttons (Summary vs Transactions)
    const modeSummaryBtn = byId('nxt-mode-summary-btn');
    const modeTransBtn = byId('nxt-mode-trans-btn');
    if (modeSummaryBtn && modeTransBtn) {
      modeSummaryBtn.addEventListener('click', () => {
        state.viewMode = 'summary';
        modeSummaryBtn.classList.add('active');
        modeTransBtn.classList.remove('active');
        renderContent();
      });
      modeTransBtn.addEventListener('click', () => {
        state.viewMode = 'transactions';
        modeTransBtn.classList.add('active');
        modeSummaryBtn.classList.remove('active');
        renderContent();
      });
    }

    // Search Box & Clear
    const searchInp = byId('nxt-search-input');
    const searchClear = byId('nxt-search-clear');
    if (searchInp) {
      searchInp.addEventListener('input', (e) => {
        state.searchQuery = e.target.value;
        if (searchClear) searchClear.style.display = state.searchQuery ? 'block' : 'none';
        renderContent();
      });
    }
    if (searchClear && searchInp) {
      searchClear.addEventListener('click', () => {
        searchInp.value = '';
        state.searchQuery = '';
        searchClear.style.display = 'none';
        renderContent();
      });
    }

    // Filter dropdown
    const filterSelect = byId('nxt-filter-select');
    if (filterSelect) {
      filterSelect.addEventListener('change', (e) => {
        state.filterStatus = e.target.value;
        renderContent();
      });
    }

    // Action bar buttons
    const addCilBtn = byId('nxt-btn-add-chemicals-cil');
    if (addCilBtn) addCilBtn.addEventListener('click', openAddCilModal);

    const importExcelBtn = byId('nxt-btn-import-excel');
    if (importExcelBtn) importExcelBtn.addEventListener('click', openImportExcelModal);

    const recordTransBtn = byId('nxt-btn-record-transaction');
    if (recordTransBtn) recordTransBtn.addEventListener('click', () => openTransactionModal());

    const exportBtn = byId('nxt-btn-export-excel');
    if (exportBtn) exportBtn.addEventListener('click', exportMonthlyExcel);

    const exportPdfBtn = byId('nxt-btn-export-pdf');
    if (exportPdfBtn) exportPdfBtn.addEventListener('click', exportMonthlyPdf);

    const printBtn = byId('nxt-btn-print-report');
    if (printBtn) printBtn.addEventListener('click', printMonthlyReport);

    const rollForwardBtn = byId('nxt-btn-roll-forward');
    if (rollForwardBtn) rollForwardBtn.addEventListener('click', rollForwardCurrentPeriod);

    const lockBtn = byId('nxt-btn-lock-toggle');
    if (lockBtn) lockBtn.addEventListener('click', togglePeriodLock);

    // CIL Modal Search
    const cilSearchInp = byId('nxt-cil-search-input');
    if (cilSearchInp) {
      cilSearchInp.addEventListener('input', renderCilModalList);
    }
  }

  // --------------------------------------------------------------------------
  // 12. EXPORT GLOBALS TO WINDOW
  // --------------------------------------------------------------------------
  window.initMonthlyInventory = initMonthlyInventory;
  window.handleNxtInlineChange = handleNxtInlineChange;
  window.saveNxtRecord = saveNxtRecord;
  window.deleteNxtRecord = deleteNxtRecord;
  window.deleteNxtTransaction = deleteNxtTransaction;
  window.openMonthlyAddCilModal = openAddCilModal;
  window.closeMonthlyAddCilModal = closeAddCilModal;
  window.submitMonthlyAddCil = submitAddCilChemicals;
  window.openMonthlyTransactionModal = openTransactionModal;
  window.openTransactionModalForChemical = (chemId) => openTransactionModal(chemId, 'EXPORT');
  window.closeMonthlyTransactionModal = closeTransactionModal;
  window.submitMonthlyTransaction = submitTransaction;
  window.exportMonthlyPdf = exportMonthlyPdf;
  window.openMonthlyImportExcelModal = openImportExcelModal;
  window.closeMonthlyImportExcelModal = closeImportExcelModal;
  window.submitMonthlyImportExcel = submitImportExcel;
  window.createMonthlyPeriodFromModal = async () => {
    const m = byId('nxt-new-period-month').value;
    const y = byId('nxt-new-period-year').value;
    await createPeriod(m, y, true);
    byId('nxt-modal-new-period').classList.add('hidden');
  };
  window.closeNewPeriodModal = () => {
    const modal = byId('nxt-modal-new-period');
    if (modal) modal.classList.add('hidden');
  };
})();
