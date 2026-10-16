/**
 * ============================================================================
 * TitanPDF — Chemical Legal Lookup & Compliance Module
 * Script: static/legal_lookup.js
 * 
 * Capabilities:
 * - IIFE Module exporting window.initLegalCatalog & window.refreshLegalCatalog
 * - Live KPI Metrics (Total Records 2,191, Unique CAS 1,787, CIL Matches, Filtered)
 * - Cascading Filter Chain (Source -> Section -> Subgroup -> Item Type)
 * - Debounced Instant Search (280ms) with Clear Control
 * - Bi-directional Mode Switch (Toàn bộ danh mục vs Chỉ chất đang trùng trong CIL)
 * - 5-Tier High-Contrast Badge System (Cấm, Kiểm soát/Tiền chất, Điều kiện, Sự cố, QCVN)
 * - Server-Side Excel (.xlsx) Multi-Sheet Export Trigger
 * - Sticky Header 50-items/page Table Pagination
 * ============================================================================
 */

(() => {
  'use strict';

  // --------------------------------------------------------------------------
  // 1. MODULE STATE
  // --------------------------------------------------------------------------
  const state = {
    meta: null,
    mode: 'catalog', // 'catalog' | 'matches'
    page: 1,
    pageSize: 50,
    total: 0,
    cilMatchedTotal: 0,
    isLoading: false,
    initialized: false,
    searchDebounceTimer: null
  };

  // --------------------------------------------------------------------------
  // 2. UTILITY HELPERS
  // --------------------------------------------------------------------------
  const byId = (id) => document.getElementById(id);

  function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    const str = String(value);
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatNumber(num) {
    return Number(num || 0).toLocaleString('vi-VN');
  }

  /**
   * International CAS Checksum validation (Mod 10).
   * Verifies whether a normalized CAS number has a valid check digit.
   */
  function isValidCasChecksum(cas) {
    if (!cas) return false;
    const match = String(cas).trim().match(/^([1-9]\d{1,6})-(\d{2})-(\d)$/);
    if (!match) return false;
    const body = match[1] + match[2];
    const checkDigit = parseInt(match[3], 10);
    let sum = 0;
    const reversed = body.split('').reverse();
    for (let i = 0; i < reversed.length; i++) {
      sum += (i + 1) * parseInt(reversed[i], 10);
    }
    return (sum % 10) === checkDigit;
  }

  /**
   * Collect active toolbar filter values.
   */
  function getFilters() {
    return {
      source_id: byId('legalSourceFilter')?.value || '',
      section_id: byId('legalSectionFilter')?.value || '',
      subgroup: byId('legalSubgroupFilter')?.value || '',
      item_type: byId('legalItemTypeFilter')?.value || '',
      q: byId('legalSearchInput')?.value.trim() || ''
    };
  }

  /**
   * Construct URL query string for API requests.
   */
  function buildQueryString(includePagination = true) {
    const params = new URLSearchParams();
    const f = getFilters();

    if (f.source_id) params.set('source_id', f.source_id);
    if (f.section_id) params.set('section_id', f.section_id);
    if (f.subgroup) params.set('subgroup', f.subgroup);
    if (f.item_type) params.set('item_type', f.item_type);
    if (f.q) params.set('q', f.q);

    if (includePagination) {
      params.set('page', state.page);
      params.set('page_size', state.pageSize);
    }

    return params.toString();
  }

  // --------------------------------------------------------------------------
  // 3. 5-TIER BADGE & METADATA BUILDERS
  // --------------------------------------------------------------------------

  /**
   * Generates 5-tier badge HTML based on item's regulatory classification:
   * Tier 1: 🔴 Cấm tuyệt đối: badge-danger
   * Tier 2: 🟠 Kiểm soát đặc biệt / Tiền chất: badge-warning
   * Tier 3: 🟡 Hạn chế / Có điều kiện: badge-conditional
   * Tier 4: 🔵 Kế hoạch sự cố / Trọng điểm CN: badge-incident
   * Tier 5: 🟢 QCVN tiếp xúc: badge-qcvn
   */
  function renderTierBadge(item) {
    if (!item) return '';

    const b = item.badge || {};
    const sec = item.section_id || '';
    const src = item.source_id || '';
    const cat = b.category || '';
    const tier = b.tier;

    let tierClass = 'badge-incident';
    let icon = '🔵';
    let label = b.label || item.section_title || 'Quy chuẩn';

    if (tier === 1 || cat === 'prohibited' || ['ND28-I-A', 'ND28-I-B', 'ND28-IV-A'].includes(sec)) {
      tierClass = 'badge-danger';
      icon = '🔴';
    } else if (tier === 2 || ['special_control', 'precursor_essential', 'precursor_industrial', 'restricted'].includes(cat) ||
               ['ND24-PL-III', 'ND28-IV-B', 'ND28-IV-C', 'ND28-II-A', 'ND28-II-B'].includes(sec)) {
      tierClass = 'badge-warning';
      icon = '🟠';
    } else if (tier === 3 || ['conditional', 'medical_veterinary'].includes(cat) ||
               ['ND24-PL-II', 'ND28-III'].includes(sec)) {
      tierClass = 'badge-conditional';
      icon = '🟡';
    } else if (tier === 4 && (src === 'QCVN01' || sec === 'QCVN01-70' || cat === 'occupational_limit')) {
      tierClass = 'badge-qcvn';
      icon = '🟢';
    } else if (tier === 4 || ['incident_plan', 'key_industrial'].includes(cat) ||
               ['ND24-PL-IV-A', 'ND24-PL-IV-B', 'ND24-PL-I'].includes(sec)) {
      tierClass = 'badge-incident';
      icon = '🔵';
    } else if (src === 'QCVN01') {
      tierClass = 'badge-qcvn';
      icon = '🟢';
    }

    return `<span class="legal-badge ${tierClass}" title="${escapeHtml(label)}">${icon} ${escapeHtml(label)}</span>`;
  }

  function renderSourceBadge(sourceId, sourceTitle) {
    const sId = escapeHtml(sourceId || 'ND24');
    const sTitle = escapeHtml(sourceTitle || sourceId || 'Nghị định');
    return `<span class="legal-source-badge legal-source-${sId}">${sTitle}</span>`;
  }

  function renderItemTypeBadge(itemType) {
    if (!itemType) return '';
    const isRaw = itemType === 'raw_material';
    const label = isRaw ? 'Nguyên liệu' : 'Thành phẩm';
    const cls = isRaw ? 'item-type-raw' : 'item-type-finished';
    const icon = isRaw ? '🧪' : '📦';
    return `<span class="legal-item-type-badge ${cls}" title="Phân loại: ${label}">${icon} ${label}</span>`;
  }

  function renderCasCell(cas, casRaw) {
    if (!cas && !casRaw) {
      return '<span style="color:var(--legal-text-muted);">—</span>';
    }
    const displayCas = cas || casRaw;
    const isValid = isValidCasChecksum(displayCas);
    const checkIcon = isValid
      ? '<span class="legal-checksum-valid" title="Checksum Mod 10 Hợp lệ">✓</span>'
      : '<span class="legal-checksum-invalid" title="Checksum Chưa chuẩn hoặc Không có">✗</span>';

    let html = `<code class="legal-cas-code">${escapeHtml(displayCas)} ${checkIcon}</code>`;
    if (casRaw && cas && casRaw !== cas) {
      html += `<small title="Số CAS trong văn bản gốc">Gốc: ${escapeHtml(casRaw)}</small>`;
    }
    return html;
  }

  // --------------------------------------------------------------------------
  // 4. CASCADING FILTER CONTROLS
  // --------------------------------------------------------------------------

  function updateSectionOptions() {
    if (!state.meta || !byId('legalSectionFilter')) return;
    const selectedSource = byId('legalSourceFilter')?.value || '';
    const currentSection = byId('legalSectionFilter')?.value || '';

    const sections = (state.meta.sections || []).filter(
      (sec) => !selectedSource || sec.source_id === selectedSource
    );

    let options = '<option value="">Tất cả mục / phụ lục</option>';
    sections.forEach((sec) => {
      options += `<option value="${escapeHtml(sec.section_id)}">${escapeHtml(sec.section_title)} (${formatNumber(sec.count)})</option>`;
    });

    byId('legalSectionFilter').innerHTML = options;
    if (sections.some((s) => s.section_id === currentSection)) {
      byId('legalSectionFilter').value = currentSection;
    } else {
      byId('legalSectionFilter').value = '';
    }

    updateSubgroupOptions();
  }

  function updateSubgroupOptions() {
    if (!state.meta || !byId('legalSubgroupFilter')) return;
    const selectedSectionId = byId('legalSectionFilter')?.value || '';
    const currentSubgroup = byId('legalSubgroupFilter')?.value || '';

    const section = (state.meta.sections || []).find((s) => s.section_id === selectedSectionId);
    const subgroups = section?.subgroups || [];

    const subgroupField = byId('legalSubgroupField');
    const subgroupSelect = byId('legalSubgroupFilter');

    if (!subgroups.length || state.mode === 'matches') {
      subgroupSelect.innerHTML = '<option value="">Tất cả phân nhóm</option>';
      subgroupSelect.disabled = true;
      if (subgroupField) subgroupField.classList.add('legal-disabled');
      return;
    }

    subgroupSelect.disabled = false;
    if (subgroupField) subgroupField.classList.remove('legal-disabled');

    let options = '<option value="">Tất cả phân nhóm</option>';
    subgroups.forEach((grp) => {
      options += `<option value="${escapeHtml(grp)}">${escapeHtml(grp)}</option>`;
    });

    subgroupSelect.innerHTML = options;
    if (subgroups.includes(currentSubgroup)) {
      subgroupSelect.value = currentSubgroup;
    } else {
      subgroupSelect.value = '';
    }
  }

  // --------------------------------------------------------------------------
  // 5. TABLE RENDERING: CATALOG VS MATCHES
  // --------------------------------------------------------------------------

  function renderCatalogTable(items) {
    if (!items || !items.length) {
      return `
        <div class="legal-state-box">
          <div class="legal-state-icon">🔍</div>
          <strong>Không tìm thấy hóa chất phù hợp</strong>
          <p>Thử điều chỉnh từ khóa tìm kiếm, kiểm tra số CAS hoặc mở rộng bộ lọc văn bản pháp luật.</p>
        </div>
      `;
    }

    return `
      <table class="legal-table" id="legalDataTable">
        <thead>
          <tr>
            <th style="width: 140px;">Văn bản</th>
            <th style="width: 170px;">Mục / Phụ lục</th>
            <th style="width: 120px;">Phân nhóm</th>
            <th style="width: 50px; text-align: center;">STT</th>
            <th style="width: 220px;">Tên hóa chất (VN)</th>
            <th style="width: 200px;">Tên khoa học / Quốc tế</th>
            <th style="width: 140px;">Số CAS</th>
            <th style="width: 100px;">Công thức</th>
            <th style="width: 130px;">Ngưỡng / Tiếp xúc</th>
            <th style="min-width: 220px;">Huy hiệu & Nghĩa vụ tuân thủ</th>
          </tr>
        </thead>
        <tbody>
          ${items.map((item) => `
            <tr>
              <td>
                ${renderSourceBadge(item.source_id, item.source_title)}
                <small>${escapeHtml(item.law_basis || '')}</small>
              </td>
              <td>
                <strong>${escapeHtml(item.section_title || '')}</strong>
              </td>
              <td>${escapeHtml(item.subgroup || '—')}</td>
              <td style="text-align: center; font-weight: 700;">${escapeHtml(item.serial || '—')}</td>
              <td>
                <strong>${escapeHtml(item.name_vi || '—')}</strong>
              </td>
              <td>
                <span style="color: var(--legal-text-secondary);">${escapeHtml(item.name_scientific || '—')}</span>
              </td>
              <td>
                ${renderCasCell(item.cas, item.cas_raw)}
              </td>
              <td>
                <span style="font-family: var(--legal-font-mono);">${escapeHtml(item.formula || '—')}</span>
              </td>
              <td>
                ${item.threshold ? `<strong>${escapeHtml(item.threshold)}</strong> kg/năm` : ''}
                ${item.twa ? `<div><small>TWA: ${escapeHtml(item.twa)}</small></div>` : ''}
                ${item.stel ? `<div><small>STEL: ${escapeHtml(item.stel)}</small></div>` : ''}
                ${!item.threshold && !item.twa && !item.stel ? '<span style="color:var(--legal-text-muted);">—</span>' : ''}
              </td>
              <td>
                <div>${renderTierBadge(item)}</div>
                ${item.obligation ? `
                  <div class="legal-obligation-text" title="${escapeHtml(item.obligation)}">
                    ${escapeHtml(item.obligation)}
                  </div>
                ` : ''}
                ${item.authority ? `<small>Cơ quan: ${escapeHtml(item.authority)}</small>` : ''}
                ${item.hs_code ? `<small>Mã HS: ${escapeHtml(item.hs_code)}</small>` : ''}
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }

  function renderMatchesTable(items) {
    if (!items || !items.length) {
      return `
        <div class="legal-state-box">
          <div class="legal-state-icon">🎯</div>
          <strong>Chưa phát hiện chất trùng trong danh mục CIL</strong>
          <p>Không có hóa chất nào trong kho CIL SQLite trùng với các bộ lọc quy chuẩn đang chọn.</p>
        </div>
      `;
    }

    return `
      <table class="legal-table" id="legalDataTable">
        <thead>
          <tr>
            <th style="width: 160px;">Mã / Loại hàng hóa</th>
            <th style="width: 220px;">Tên hóa chất CIL</th>
            <th style="width: 200px;">Thành phần SDS trùng</th>
            <th style="width: 140px;">CAS đối chiếu</th>
            <th style="width: 100px;">Hàm lượng (%)</th>
            <th style="width: 150px;">Văn bản áp dụng</th>
            <th style="width: 180px;">Tên chất theo luật</th>
            <th style="min-width: 220px;">Huy hiệu 5 bậc & Nghĩa vụ</th>
            <th style="width: 160px;">Tệp hồ sơ MSDS</th>
          </tr>
        </thead>
        <tbody>
          ${items.map((item) => {
            const legal = item.legal_item || {};
            const productDisplay = item.product_name_vi || item.product_name_original || 'Hóa chất';
            const componentDisplay = item.ingredient_name_vi || item.ingredient_name_original || item.component_name_original || '—';
            const codeDisplay = item.product_code || item.chemical_id || '—';

            return `
              <tr>
                <td>
                  <strong>${escapeHtml(codeDisplay)}</strong>
                  <div style="margin-top: 4px;">${renderItemTypeBadge(item.item_type)}</div>
                </td>
                <td>
                  <strong>${escapeHtml(productDisplay)}</strong>
                  ${item.manufacturer ? `<small>NSX: ${escapeHtml(item.manufacturer)}</small>` : ''}
                </td>
                <td>
                  <strong>${escapeHtml(componentDisplay)}</strong>
                </td>
                <td>
                  ${renderCasCell(item.matched_cas || item.cas_number || item.cas, null)}
                </td>
                <td>
                  <span style="font-weight: 700;">${escapeHtml(item.concentration_text || '—')}</span>
                </td>
                <td>
                  ${renderSourceBadge(legal.source_id, legal.source_title)}
                  <small>${escapeHtml(legal.section_title || '')}</small>
                </td>
                <td>
                  <strong>${escapeHtml(legal.name_vi || legal.name_scientific || '—')}</strong>
                </td>
                <td>
                  <div>${renderTierBadge(legal)}</div>
                  ${legal.obligation ? `
                    <div class="legal-obligation-text" title="${escapeHtml(legal.obligation)}">
                      ${escapeHtml(legal.obligation)}
                    </div>
                  ` : ''}
                </td>
                <td>
                  <span style="font-size: 11.5px; word-break: break-all; color: var(--legal-text-secondary);">
                    📄 ${escapeHtml(item.source_file || item.file_name || '—')}
                  </span>
                </td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    `;
  }

  // --------------------------------------------------------------------------
  // 6. DATA LOADING & PAGINATION
  // --------------------------------------------------------------------------

  async function loadRows() {
    const tableWrap = byId('legalCatalogTable');
    const msgEl = byId('legalCatalogMessage');
    const resultCountEl = byId('legalResultCount');
    const matchCountEl = byId('legalMatchCount');
    const pageInfoEl = byId('legalPageInfo');
    const prevBtn = byId('legalPrevBtn');
    const nextBtn = byId('legalNextBtn');

    if (!tableWrap) return;

    state.isLoading = true;
    tableWrap.innerHTML = `
      <div class="legal-state-box">
        <div class="legal-spinner"></div>
        <strong>Đang tra cứu dữ liệu pháp lý…</strong>
        <p>Hệ thống đang truy xuất chỉ mục in-memory siêu tốc.</p>
      </div>
    `;
    if (msgEl) msgEl.textContent = '';

    try {
      const endpoint = state.mode === 'matches' ? '/api/legal/matches' : '/api/legal/search';
      const qs = buildQueryString(true);
      const res = await fetch(`${endpoint}?${qs}`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        cache: 'no-store'
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Máy chủ phản hồi mã lỗi ${res.status}`);
      }

      const data = await res.json();
      state.total = Number(data.total || 0);

      // Render table rows
      if (state.mode === 'matches') {
        tableWrap.innerHTML = renderMatchesTable(data.items || []);
        if (matchCountEl) matchCountEl.textContent = formatNumber(state.total);
      } else {
        tableWrap.innerHTML = renderCatalogTable(data.items || []);
      }

      // Update KPI counter
      if (resultCountEl) {
        resultCountEl.textContent = formatNumber(state.total);
      }

      // Update Pagination Controls
      const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
      if (pageInfoEl) {
        pageInfoEl.innerHTML = `Trang <strong>${formatNumber(state.page)}</strong> / ${formatNumber(totalPages)} · Tổng <strong>${formatNumber(state.total)}</strong> bản ghi`;
      }

      if (prevBtn) prevBtn.disabled = state.page <= 1;
      if (nextBtn) nextBtn.disabled = state.page >= totalPages;

    } catch (err) {
      console.error('[LegalLookup] Lỗi tải dữ liệu:', err);
      tableWrap.innerHTML = `
        <div class="legal-state-box" style="color: #dc2626;">
          <div class="legal-state-icon">⚠️</div>
          <strong>Không thể nạp dữ liệu pháp lý</strong>
          <p>${escapeHtml(err.message)}</p>
        </div>
      `;
      if (msgEl) msgEl.textContent = `❌ ${err.message}`;
    } finally {
      state.isLoading = false;
    }
  }

  /**
   * Load metadata & initial stats from /api/legal/catalog.
   */
  async function loadMeta() {
    try {
      const res = await fetch('/api/legal/catalog', {
        headers: { 'Accept': 'application/json' },
        cache: 'no-store'
      });

      if (!res.ok) {
        throw new Error(`Lỗi tải siêu dữ liệu: HTTP ${res.status}`);
      }

      const data = await res.json();
      state.meta = data;

      // Update Top Scope Note
      const scopeNoteEl = byId('legalScopeNote');
      if (scopeNoteEl && data.scope_note) {
        scopeNoteEl.innerHTML = `
          <span class="legal-scope-note-icon">ℹ️</span>
          <span>${escapeHtml(data.scope_note)}</span>
        `;
      }

      // Update KPI Stat Cards
      const totalRecEl = byId('legalTotalRecords');
      const uniqueCasEl = byId('legalUniqueCas');
      if (totalRecEl) totalRecEl.textContent = formatNumber(data.total_records || 2191);
      if (uniqueCasEl) uniqueCasEl.textContent = formatNumber(data.unique_cas || 1787);

      // Populate Source Dropdown
      const sourceSelect = byId('legalSourceFilter');
      if (sourceSelect && Array.isArray(data.sources)) {
        let opts = '<option value="">Tất cả văn bản (NĐ 24, NĐ 28, QCVN 01)</option>';
        data.sources.forEach((src) => {
          opts += `<option value="${escapeHtml(src.source_id)}">${escapeHtml(src.source_title)} (${formatNumber(src.count)})</option>`;
        });
        sourceSelect.innerHTML = opts;
      }

      updateSectionOptions();

      // Pre-fetch CIL match total count for badge pill
      fetchCilMatchesCount();

    } catch (err) {
      console.warn('[LegalLookup] loadMeta fallback error:', err);
      const msgEl = byId('legalCatalogMessage');
      if (msgEl) msgEl.textContent = `Cảnh báo kết nối máy chủ: ${err.message}`;
    }
  }

  /**
   * Fetches the total number of CIL inventory matches.
   */
  async function fetchCilMatchesCount() {
    try {
      const res = await fetch('/api/legal/matches?page=1&page_size=1', { cache: 'no-store' });
      if (res.ok) {
        const data = await res.json();
        state.cilMatchedTotal = Number(data.total || 0);
        const matchCountEl = byId('legalMatchCount');
        if (matchCountEl) matchCountEl.textContent = formatNumber(state.cilMatchedTotal);

        const badgePill = byId('legalMatchesPillCount');
        if (badgePill) badgePill.textContent = formatNumber(state.cilMatchedTotal);
      }
    } catch (e) {
      console.debug('[LegalLookup] Cannot prefetch CIL matches count', e);
    }
  }

  // --------------------------------------------------------------------------
  // 7. USER INTERACTIONS & EVENT BINDINGS
  // --------------------------------------------------------------------------

  function setMode(newMode) {
    if (state.mode === newMode) return;
    state.mode = newMode;
    state.page = 1;

    const catalogBtn = byId('legalCatalogModeBtn');
    const matchesBtn = byId('legalMatchesModeBtn');
    const itemTypeField = byId('legalItemTypeField');

    if (catalogBtn) catalogBtn.classList.toggle('active', newMode === 'catalog');
    if (matchesBtn) matchesBtn.classList.toggle('active', newMode === 'matches');

    // Show/hide or emphasize item_type filter
    if (itemTypeField) {
      if (newMode === 'matches') {
        itemTypeField.classList.remove('legal-disabled');
      }
    }

    updateSubgroupOptions();
    loadRows();
  }

  function handleSearchInput() {
    const input = byId('legalSearchInput');
    const clearBtn = byId('legalSearchClearBtn');

    if (clearBtn) {
      clearBtn.classList.toggle('hidden', !input?.value);
    }

    clearTimeout(state.searchDebounceTimer);
    state.searchDebounceTimer = setTimeout(() => {
      state.page = 1;
      loadRows();
    }, 280); // Exact 280ms debounce specification
  }

  function clearSearchInput() {
    const input = byId('legalSearchInput');
    const clearBtn = byId('legalSearchClearBtn');
    if (input) {
      input.value = '';
      input.focus();
    }
    if (clearBtn) {
      clearBtn.classList.add('hidden');
    }
    state.page = 1;
    loadRows();
  }

  function triggerExport() {
    const qs = buildQueryString(false);
    const modeParam = state.mode;
    const url = `/api/legal/export?mode=${encodeURIComponent(modeParam)}&${qs}`;
    window.location.href = url;
  }

  function attachEventListeners() {
    // Cascading Filter Listeners
    byId('legalSourceFilter')?.addEventListener('change', () => {
      state.page = 1;
      updateSectionOptions();
      loadRows();
    });

    byId('legalSectionFilter')?.addEventListener('change', () => {
      state.page = 1;
      updateSubgroupOptions();
      loadRows();
    });

    byId('legalSubgroupFilter')?.addEventListener('change', () => {
      state.page = 1;
      loadRows();
    });

    byId('legalItemTypeFilter')?.addEventListener('change', () => {
      state.page = 1;
      loadRows();
    });

    // Search Input with 280ms Debounce & Clear Control
    byId('legalSearchInput')?.addEventListener('input', handleSearchInput);
    byId('legalSearchClearBtn')?.addEventListener('click', clearSearchInput);

    // Refresh & Export Action Buttons
    byId('legalRefreshBtn')?.addEventListener('click', () => {
      loadMeta();
      loadRows();
    });

    byId('legalExportBtn')?.addEventListener('click', triggerExport);

    // Mode Switch Buttons
    byId('legalCatalogModeBtn')?.addEventListener('click', () => setMode('catalog'));
    byId('legalMatchesModeBtn')?.addEventListener('click', () => setMode('matches'));

    // Pagination Buttons
    byId('legalPrevBtn')?.addEventListener('click', () => {
      if (state.page > 1 && !state.isLoading) {
        state.page--;
        loadRows();
      }
    });

    byId('legalNextBtn')?.addEventListener('click', () => {
      const maxPages = Math.max(1, Math.ceil(state.total / state.pageSize));
      if (state.page < maxPages && !state.isLoading) {
        state.page++;
        loadRows();
      }
    });
  }

  // --------------------------------------------------------------------------
  // 8. PUBLIC EXPORT HOOKS
  // --------------------------------------------------------------------------

  async function initLegalCatalog() {
    const viewContainer = byId('legal-lookup-view');
    if (!viewContainer) {
      console.warn('[LegalLookup] Container #legal-lookup-view không tồn tại trên trang.');
      return;
    }

    if (!state.initialized) {
      state.initialized = true;
      attachEventListeners();
      await loadMeta();
    }

    await loadRows();
  }

  function refreshLegalCatalog() {
    return loadRows();
  }

  // Export to window global scope
  window.initLegalCatalog = initLegalCatalog;
  window.refreshLegalCatalog = refreshLegalCatalog;

  // Auto-bind to DOM navigation tab if loaded
  document.addEventListener('DOMContentLoaded', () => {
    const legalNavTab = byId('nav-tab-legal');
    if (legalNavTab) {
      legalNavTab.addEventListener('click', () => {
        initLegalCatalog();
      });
    }
  });

})();
