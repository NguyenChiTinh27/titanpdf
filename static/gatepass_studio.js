/**
 * TitanPDF — Gate Pass & Material Dispatch Studio Controller
 * File: static/gatepass_studio.js
 *
 * Comprehensive client-side state machine & API controller for Gate Pass Studio.
 * Exposes window.GatePassStudio and window.initGatePassStudio.
 */

(function () {
  'use strict';

  // =========================================================================
  // 1. STATE & GLOBAL INSTANCES
  // =========================================================================

  const GatePassState = {
    initialized: false,
    currentArea: 'dashboard',
    currentPeriod: 'month',
    chartMetric: 'kg', // 'kg' | 'slips' | 'units'
    dashboardData: null,

    canvas: {
      zoom: 1.0,
      rotation: 0,
      contrast: false,
      isDragging: false,
      startX: 0,
      startY: 0,
      scrollLeft: 0,
      scrollTop: 0
    },

    queue: [],
    activeIndex: -1,

    proofs: {
      vehicle: null,
      plate: null,
      cargo: null
    },

    history: {
      page: 1,
      pageSize: 15,
      total: 0,
      totalPages: 1,
      searchDebounceTimer: null
    },

    activeDetailSlip: null
  };

  let gpTimelineChartInstance = null;
  let gpCustomerChartInstance = null;

  function destroyCharts() {
    if (gpTimelineChartInstance && typeof gpTimelineChartInstance.destroy === 'function') {
      try { gpTimelineChartInstance.destroy(); } catch (e) { console.warn(e); }
      gpTimelineChartInstance = null;
    }
    if (gpCustomerChartInstance && typeof gpCustomerChartInstance.destroy === 'function') {
      try { gpCustomerChartInstance.destroy(); } catch (e) { console.warn(e); }
      gpCustomerChartInstance = null;
    }
  }

  // =========================================================================
  // 2. HELPER UTILITIES
  // =========================================================================

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function isGuestMode() {
    return document.body.getAttribute('data-role') === 'guest';
  }

  function showToast(message, type = 'info') {
    console.log(`[GatePass ${type.toUpperCase()}]: ${message}`);
    if (typeof window.showToast === 'function') {
      window.showToast(message, type);
    } else {
      const existing = document.getElementById('gp-inline-toast');
      if (existing) existing.remove();
      const toast = document.createElement('div');
      toast.id = 'gp-inline-toast';
      toast.style.cssText = `
        position: fixed; bottom: 24px; right: 24px; z-index: 10000;
        background: ${type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#2563eb'};
        color: #fff; padding: 10px 16px; border-radius: 8px; font-weight: 600;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15); font-size: 0.85rem;
      `;
      toast.innerText = message;
      document.body.appendChild(toast);
      setTimeout(() => toast.remove(), 3500);
    }
  }

  function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function getAuthHeaders(extraHeaders = {}) {
    const token = sessionStorage.getItem("luv_auth_token") || localStorage.getItem("luv_auth_token") || "verified";
    const role = sessionStorage.getItem("luv_user_role") || document.body.getAttribute('data-role') || "owner";
    return {
      'X-Titan-Session': token,
      'X-Titan-Role': role,
      'Authorization': 'Bearer ' + token,
      ...extraHeaders
    };
  }

  // =========================================================================
  // 3. CANVAS ROTATOR & INTERACTION (CanvasRotator)
  // =========================================================================

  function applyCanvasTransform() {
    const stage = document.getElementById('gp-canvas-stage') || document.getElementById('gp-canvas-container');
    const img = document.getElementById('gp-canvas-image') || document.getElementById('gp-slip-canvas');
    if (!stage) return;

    if (img) {
      img.style.transform = `scale(${GatePassState.canvas.zoom}) rotate(${GatePassState.canvas.rotation}deg)`;
      img.style.transformOrigin = 'center center';
      img.style.transition = 'transform 60ms linear';
      if (GatePassState.canvas.contrast) {
        img.style.filter = 'contrast(1.4) brightness(0.95)';
      } else {
        img.style.filter = 'none';
      }
    }

    const zoomText = Math.round(GatePassState.canvas.zoom * 100) + '%';
    const hudVal = document.getElementById('gp-hud-zoom-val');
    if (hudVal) hudVal.innerText = zoomText;
    const resetBtn = document.getElementById('gp-btn-zoom-reset') || document.getElementById('btn-gp-zoom-reset');
    if (resetBtn) resetBtn.innerText = '100%';
  }

  function canvasZoom(factor) {
    if (factor > 1) {
      GatePassState.canvas.zoom = Math.min(3.5, GatePassState.canvas.zoom + 0.2);
    } else {
      GatePassState.canvas.zoom = Math.max(0.2, GatePassState.canvas.zoom - 0.2);
    }
    applyCanvasTransform();
  }

  function canvasResetZoom() {
    GatePassState.canvas.zoom = 1.0;
    GatePassState.canvas.rotation = 0;
    applyCanvasTransform();
  }

  function canvasRotate(delta = 90) {
    GatePassState.canvas.rotation = ((GatePassState.canvas.rotation + delta) % 360 + 360) % 360;
    applyCanvasTransform();
  }

  function canvasToggleContrast() {
    GatePassState.canvas.contrast = !GatePassState.canvas.contrast;
    const btn = document.getElementById('btn-gp-contrast') || document.getElementById('gp-btn-filter-contrast');
    if (btn) btn.classList.toggle('active', GatePassState.canvas.contrast);
    applyCanvasTransform();
  }

  function transformImageRotation(sourceBase64, angle, quality = 0.90) {
    return new Promise((resolve) => {
      if (!sourceBase64 || angle === 0) return resolve(sourceBase64);
      const img = new Image();
      img.onload = () => {
        const offCanvas = document.createElement('canvas');
        const ctx = offCanvas.getContext('2d');
        if (angle === 90 || angle === 270) {
          offCanvas.width = img.height;
          offCanvas.height = img.width;
        } else {
          offCanvas.width = img.width;
          offCanvas.height = img.height;
        }
        ctx.translate(offCanvas.width / 2, offCanvas.height / 2);
        ctx.rotate((angle * Math.PI) / 180);
        ctx.drawImage(img, -img.width / 2, -img.height / 2);
        resolve(offCanvas.toDataURL('image/jpeg', quality));
      };
      img.onerror = () => resolve(sourceBase64);
      img.src = sourceBase64;
    });
  }

  function setupCanvasPan() {
    const container = document.getElementById('gp-canvas-container') || document.getElementById('gp-canvas-viewport');
    if (!container) return;

    container.addEventListener('mousedown', (e) => {
      if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT') return;
      GatePassState.canvas.isDragging = true;
      container.classList.add('grabbing');
      GatePassState.canvas.startX = e.pageX - container.offsetLeft;
      GatePassState.canvas.startY = e.pageY - container.offsetTop;
      GatePassState.canvas.scrollLeft = container.scrollLeft;
      GatePassState.canvas.scrollTop = container.scrollTop;
    });

    container.addEventListener('mouseleave', () => {
      GatePassState.canvas.isDragging = false;
      container.classList.remove('grabbing');
    });

    container.addEventListener('mouseup', () => {
      GatePassState.canvas.isDragging = false;
      container.classList.remove('grabbing');
    });

    container.addEventListener('mousemove', (e) => {
      if (!GatePassState.canvas.isDragging) return;
      e.preventDefault();
      const x = e.pageX - container.offsetLeft;
      const y = e.pageY - container.offsetTop;
      const walkX = x - GatePassState.canvas.startX;
      const walkY = y - GatePassState.canvas.startY;
      container.scrollLeft = GatePassState.canvas.scrollLeft - walkX;
      container.scrollTop = GatePassState.canvas.scrollTop - walkY;
    });

    container.addEventListener('wheel', (e) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        canvasZoom(e.deltaY < 0 ? 1.1 : 0.9);
      }
    }, { passive: false });
  }

  // Clipboard paste listener
  window.addEventListener('paste', async (e) => {
    const gpView = document.getElementById('gatepass-studio-view');
    if (!gpView || gpView.classList.contains('hidden')) return;

    if (isGuestMode()) {
      showToast('Chế độ Khách không thể thêm ảnh phiếu mới.', 'error');
      return;
    }

    const items = (e.clipboardData || window.clipboardData)?.items;
    if (!items) return;

    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf('image') !== -1) {
        const file = items[i].getAsFile();
        if (file) {
          e.preventDefault();
          showToast('Đang nhận ảnh từ Clipboard...', 'info');
          const dataUrl = await readFileAsDataUrl(file);
          addQueueItem(dataUrl, `paste_${Date.now()}.png`);
          break;
        }
      }
    }
  });

  // =========================================================================
  // 4. QUEUE MANAGER (QueueManager)
  // =========================================================================

  async function addQueueItem(base64, fileName) {
    const item = {
      id: 'gp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6),
      fileName: fileName || 'phieu_xuat.jpg',
      originalBase64: base64,
      thumbnailBase64: base64,
      rotationAngle: 0,
      status: 'ready',
      loai_xuat: 'Xuất hàng thành phẩm',
      aiResult: null,
      userEditedData: null,
      proofImages: []
    };

    GatePassState.queue.push(item);
    renderQueueStrip();
    selectQueueItem(GatePassState.queue.length - 1);
  }

  function renderQueueStrip() {
    const strip = document.getElementById('gp-queue-strip');
    const counter = document.getElementById('gp-queue-counter') || document.getElementById('gp-queue-count');
    if (!strip) return;

    if (counter) {
      counter.innerText = `(${GatePassState.queue.length} ảnh)`;
    }

    strip.innerHTML = '';
    GatePassState.queue.forEach((item, idx) => {
      const card = document.createElement('div');
      card.className = `gp-queue-card ${idx === GatePassState.activeIndex ? 'active' : ''}`;
      card.style.cssText = 'flex: 0 0 110px; background: var(--gp-bg-subtle, #f1f5f9); border: 1px solid var(--gp-border, #e2e8f0); border-radius: 6px; padding: 6px; cursor: pointer; text-align: center;';
      card.onclick = () => selectQueueItem(idx);

      card.innerHTML = `
        <img src="${item.thumbnailBase64}" alt="${escapeHtml(item.fileName)}" style="width: 100%; height: 60px; object-fit: cover; border-radius: 4px; display: block; margin-bottom: 4px;" />
        <div style="font-size: 0.7rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(item.fileName)}</div>
      `;
      strip.appendChild(card);
    });
  }

  function selectQueueItem(idx) {
    if (idx < 0 || idx >= GatePassState.queue.length) return;
    GatePassState.activeIndex = idx;
    const item = GatePassState.queue[idx];

    const canvas = document.getElementById('gp-slip-canvas') || document.getElementById('gp-canvas-image');
    const emptyState = document.getElementById('gp-canvas-empty') || document.getElementById('gp-canvas-placeholder');

    if (canvas) {
      if (canvas.tagName === 'CANVAS') {
        const img = new Image();
        img.onload = () => {
          canvas.width = img.width;
          canvas.height = img.height;
          const ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0);
          canvas.style.display = 'block';
          if (emptyState) emptyState.style.display = 'none';
        };
        img.src = item.originalBase64;
      } else {
        canvas.src = item.originalBase64;
        canvas.style.display = 'block';
        canvas.classList.remove('hidden');
        if (emptyState) emptyState.style.display = 'none';
      }
    }

    canvasResetZoom();
    renderQueueStrip();
  }

  function setupDropzone() {
    const dropzone = document.getElementById('gp-canvas-container') || document.getElementById('gp-dropzone');
    if (!dropzone) return;

    ['dragenter', 'dragover'].forEach(name => {
      dropzone.addEventListener(name, (e) => {
        e.preventDefault();
        e.stopPropagation();
      });
    });

    dropzone.addEventListener('drop', async (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (isGuestMode()) {
        showToast('Chế độ Khách không thể tải tệp.', 'error');
        return;
      }
      const files = e.dataTransfer.files;
      if (!files || files.length === 0) return;
      for (let i = 0; i < files.length; i++) {
        if (files[i].type.startsWith('image/')) {
          const durl = await readFileAsDataUrl(files[i]);
          await addQueueItem(durl, files[i].name);
        }
      }
    });

    const fileInput = document.getElementById('gp-queue-file-input') || document.getElementById('gp-file-input');
    if (fileInput) {
      fileInput.addEventListener('change', async (e) => {
        const files = e.target.files;
        if (!files) return;
        for (let i = 0; i < files.length; i++) {
          if (files[i].type.startsWith('image/')) {
            const durl = await readFileAsDataUrl(files[i]);
            await addQueueItem(durl, files[i].name);
          }
        }
        e.target.value = '';
      });
    }
  }

  // =========================================================================
  // 5. DYNAMIC BILINGUAL ITEMS TABLE & AUTO-SUMMATION
  // =========================================================================

  function addGatePassItemRow(data = {}) {
    const tbody = document.getElementById('gp-items-tbody');
    if (!tbody) return;

    const count = tbody.children.length + 1;
    const isTP = (document.querySelector('input[name="gp_loai_xuat"]:checked')?.value || document.querySelector('input[name="gp-dispatch-type"]:checked')?.value || '') !== 'Xuất vật tư ra công';

    const tr = document.createElement('tr');
    tr.className = 'gatepass-item-row gp-item-row';
    tr.innerHTML = `
      <td class="gp-cell-stt font-mono font-bold" style="text-align: center; color: var(--gp-text-muted, #94a3b8);">${count}</td>
      <td><input type="text" class="gp-input-ten-hang it-loai" value="${escapeHtml(data.loai_hang_hoa || '')}" placeholder="Tên hàng (Trung - Việt)..." /></td>
      <td><input type="text" class="gp-input-quy-cach it-quycach" value="${escapeHtml(data.quy_cach || '')}" placeholder="${isTP ? '20kg/thùng hoặc 25kg/bao' : 'Quy cách...'}" /></td>
      <td><input type="text" class="gp-input-sl-kien it-kien font-mono" style="text-align: right; font-weight: 700; color: #7c3aed;" value="${escapeHtml(data.sl_kien != null ? data.sl_kien : '')}" placeholder="0" /></td>
      <td><input type="text" class="gp-input-sl-thung it-thung font-mono" style="text-align: right; font-weight: 700; color: #0284c7;" value="${escapeHtml(data.sl_thung != null ? data.sl_thung : '')}" placeholder="0" /></td>
      <td><input type="text" class="gp-input-kg it-kg font-mono font-bold" style="text-align: right; color: #059669;" value="${escapeHtml(data.khoi_luong_kg || data.trong_luong_kg || '')}" placeholder="0.0" /></td>
      <td><input type="text" class="gp-input-ghi-chu it-ghichu" value="${escapeHtml(data.ghi_chu || '')}" placeholder="Ghi chú..." /></td>
      <td style="text-align: center;">
        <button type="button" class="btn-table-delete gatepass-btn-del-row" onclick="this.closest('tr').remove(); GatePassStudio.recalcTotals();" title="Xóa dòng" style="background:transparent; border:none; cursor:pointer;">🗑️</button>
      </td>
    `;

    tr.querySelectorAll('.gp-input-sl-kien, .gp-input-sl-thung, .gp-input-kg, .gp-input-quy-cach').forEach(inp => {
      inp.addEventListener('input', () => recalcTotals());
      inp.addEventListener('change', () => recalcTotals());
    });

    tbody.appendChild(tr);
    recalcTotals();
  }

  function autoNumberItemRows() {
    document.querySelectorAll('#gp-items-tbody tr').forEach((row, i) => {
      const cell = row.querySelector('.gp-cell-stt');
      if (cell) cell.innerText = i + 1;
    });
  }

  function recalcTotals() {
    let totalKien = 0;
    let totalThung = 0;
    let totalKg = 0.0;

    document.querySelectorAll('#gp-items-tbody tr').forEach(tr => {
      const kienRaw = tr.querySelector('.gp-input-sl-kien')?.value || tr.querySelector('.it-kien')?.value || '';
      const thungRaw = tr.querySelector('.gp-input-sl-thung')?.value || tr.querySelector('.it-thung')?.value || '';
      const kgRaw = tr.querySelector('.gp-input-kg')?.value || tr.querySelector('.it-kg')?.value || '';
      const qcRaw = tr.querySelector('.gp-input-quy-cach')?.value || tr.querySelector('.it-quycach')?.value || '';

      const kien = parseFloat(kienRaw.replace(/[^\d.]/g, '')) || 0;
      const thung = parseFloat(thungRaw.replace(/[^\d.]/g, '')) || 0;
      let kg = parseFloat(kgRaw.replace(/[^\d.]/g, '')) || 0.0;

      // Multiplier heuristic
      if (kg === 0.0 && qcRaw) {
        const matchKg = qcRaw.match(/(\d+(?:\.\d+)?)\s*(?:kg|kilo)/i);
        if (matchKg && (kien > 0 || thung > 0)) {
          const unitWeight = parseFloat(matchKg[1]);
          const count = kien > 0 ? kien : thung;
          kg = unitWeight * count;
          const kgInput = tr.querySelector('.gp-input-kg') || tr.querySelector('.it-kg');
          if (kgInput && !kgInput.value) kgInput.value = kg.toFixed(1);
        }
      }

      totalKien += Math.round(kien);
      totalThung += Math.round(thung);
      totalKg += kg;
    });

    autoNumberItemRows();

    // Update all matching elements
    const kienEls = [document.getElementById('gp-total-kien'), document.getElementById('gp-sum-kien')].filter(Boolean);
    const thungEls = [document.getElementById('gp-total-thung'), document.getElementById('gp-sum-thung')].filter(Boolean);
    const kgEls = [document.getElementById('gp-total-kg'), document.getElementById('gp-sum-kg')].filter(Boolean);

    kienEls.forEach(el => el.innerText = totalKien);
    thungEls.forEach(el => el.innerText = totalThung);
    kgEls.forEach(el => {
      el.innerText = `${totalKg.toLocaleString('vi-VN', { minimumFractionDigits: 1, maximumFractionDigits: 2 })} kg`;
    });
  }

  // =========================================================================
  // 6. FORM SERIALIZATION & HYDRATION
  // =========================================================================

  function serializeFormSlipData() {
    const items = [];
    document.querySelectorAll('#gp-items-tbody tr').forEach((tr, i) => {
      items.push({
        stt: i + 1,
        loai_hang_hoa: tr.querySelector('.gp-input-ten-hang')?.value || tr.querySelector('.it-loai')?.value || '',
        quy_cach: tr.querySelector('.gp-input-quy-cach')?.value || tr.querySelector('.it-quycach')?.value || '',
        sl_kien: tr.querySelector('.gp-input-sl-kien')?.value || tr.querySelector('.it-kien')?.value || '',
        sl_thung: tr.querySelector('.gp-input-sl-thung')?.value || tr.querySelector('.it-thung')?.value || '',
        khoi_luong_kg: tr.querySelector('.gp-input-kg')?.value || tr.querySelector('.it-kg')?.value || '',
        ghi_chu: tr.querySelector('.gp-input-ghi-chu')?.value || tr.querySelector('.it-ghichu')?.value || ''
      });
    });

    const loaiXuat = document.querySelector('input[name="gp_loai_xuat"]:checked')?.value || 
                     document.querySelector('input[name="gp-dispatch-type"]:checked')?.value || 
                     'Xuất hàng thành phẩm';

    const getVal = (id1, id2) => (document.getElementById(id1)?.value || document.getElementById(id2)?.value || '').trim();

    return {
      so_phieu: getVal('gp-field-so-phieu', 'gp-input-so-phieu'),
      ngay_thang: getVal('gp-field-ngay-thang', 'gp-input-ngay-thang'),
      loai_xuat: loaiXuat,
      don_vi_van_chuyen: getVal('gp-field-don-vi-vc', 'gp-input-don-vi-vc'),
      so_xe: getVal('gp-field-so-xe', 'gp-input-so-xe'),
      don_vi_dat_hang: getVal('gp-field-khach-hang', 'gp-input-khach-hang'),
      khach_hang: getVal('gp-field-khach-hang', 'gp-input-khach-hang'),
      so_don_hang: getVal('gp-field-so-po', 'gp-input-so-po'),
      bo_phan: getVal('gp-field-bo-phan', 'gp-input-bo-phan'),
      phe_duyet: getVal('gp-field-phe-duyet', 'gp-input-phe-duyet'),
      ghi_chu_chung: getVal('gp-field-ghi-chu', 'gp-input-ghi-chu'),
      tong_cong_kg: parseFloat((document.getElementById('gp-total-kg')?.innerText || document.getElementById('gp-sum-kg')?.innerText || '0').replace(/[^\d.]/g, '')) || 0,
      items: items
    };
  }

  function hydrateFormSlipData(data) {
    if (!data) return;
    const setVal = (id1, id2, val) => {
      const el1 = document.getElementById(id1);
      const el2 = document.getElementById(id2);
      if (el1) el1.value = val || '';
      if (el2) el2.value = val || '';
    };

    setVal('gp-field-so-phieu', 'gp-input-so-phieu', data.so_phieu);
    setVal('gp-field-ngay-thang', 'gp-input-ngay-thang', data.ngay_thang);
    setVal('gp-field-don-vi-vc', 'gp-input-don-vi-vc', data.don_vi_van_chuyen);
    setVal('gp-field-so-xe', 'gp-input-so-xe', data.so_xe);
    setVal('gp-field-khach-hang', 'gp-input-khach-hang', data.don_vi_dat_hang || data.khach_hang);
    setVal('gp-field-so-po', 'gp-input-so-po', data.so_don_hang || data.so_po);
    setVal('gp-field-bo-phan', 'gp-input-bo-phan', data.bo_phan);
    setVal('gp-field-phe-duyet', 'gp-input-phe-duyet', data.phe_duyet);
    setVal('gp-field-ghi-chu', 'gp-input-ghi-chu', data.ghi_chu_chung);

    if (data.loai_xuat) {
      document.querySelectorAll('input[name="gp_loai_xuat"], input[name="gp-dispatch-type"]').forEach(r => {
        if (r.value === data.loai_xuat) r.checked = true;
      });
    }

    const tbody = document.getElementById('gp-items-tbody');
    if (tbody) {
      tbody.innerHTML = '';
      const items = data.items || data.danh_sach_hang_hoa || [];
      if (Array.isArray(items) && items.length > 0) {
        items.forEach(it => addGatePassItemRow(it));
      } else {
        addGatePassItemRow();
      }
    }
  }

  function clearFormFields() {
    ['gp-field-so-phieu', 'gp-field-ngay-thang', 'gp-field-so-xe', 'gp-field-don-vi-vc',
     'gp-field-khach-hang', 'gp-field-so-po', 'gp-field-bo-phan', 'gp-field-phe-duyet', 'gp-field-ghi-chu',
     'gp-input-so-phieu', 'gp-input-ngay-thang', 'gp-input-don-vi-vc', 'gp-input-so-xe',
     'gp-input-khach-hang', 'gp-input-so-po', 'gp-input-bo-phan', 'gp-input-phe-duyet', 'gp-input-ghi-chu'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });

    const tbody = document.getElementById('gp-items-tbody');
    if (tbody) tbody.innerHTML = '';
    recalcTotals();
  }

  // =========================================================================
  // 7. CHART.JS BINDER & DASHBOARD API (GET /api/gatepass/dashboard)
  // =========================================================================

  async function loadDashboardData() {
    try {
      const res = await fetch(`/api/gatepass/dashboard?period=${encodeURIComponent(GatePassState.currentPeriod)}`, {
        headers: getAuthHeaders()
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const payload = await res.json();
      GatePassState.dashboardData = payload;

      const kpi = payload.kpi || {};
      const elSlips = document.getElementById('gp-kpi-total-slips');
      const elKg = document.getElementById('gp-kpi-total-kg');
      const elUnits = document.getElementById('gp-kpi-total-units') || document.getElementById('gp-kpi-total-packages');
      const elClients = document.getElementById('gp-kpi-total-clients') || document.getElementById('gp-kpi-active-clients');

      if (elSlips) elSlips.innerText = kpi.total_passes != null ? kpi.total_passes : 0;
      if (elKg) elKg.innerText = (kpi.total_weight_kg || 0).toLocaleString('vi-VN', { maximumFractionDigits: 1 }) + ' kg';
      if (elUnits) elUnits.innerText = `${kpi.total_packages || 0} kiện / ${kpi.total_cartons || 0} thùng`;
      if (elClients) elClients.innerText = `${kpi.active_customers || 0} KH (${kpi.active_vehicles || 0} xe)`;

      renderTimelineChart(payload.charts?.timeline);
      renderCustomerChart(payload.charts?.customers);
    } catch (err) {
      console.warn('[GatePass] Dashboard load error:', err);
    }
  }

  function renderTimelineChart(timelineData) {
    const canvas = document.getElementById('gp-chart-timeline');
    if (!canvas) return;

    if (typeof window.Chart === 'undefined') {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#64748b';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Biểu đồ đang hiển thị ở chế độ ngoại tuyến.', canvas.width / 2, canvas.height / 2);
      return;
    }

    if (gpTimelineChartInstance) {
      gpTimelineChartInstance.destroy();
      gpTimelineChartInstance = null;
    }

    const labels = timelineData?.labels || ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];
    let datasetLabel = 'Khối Lượng (KG)';
    let dataPoints = timelineData?.data_kg || [0, 0, 0, 0, 0, 0, 0];
    let borderColor = '#2563eb';
    let bgColor = 'rgba(37, 99, 235, 0.15)';

    if (GatePassState.chartMetric === 'slips') {
      datasetLabel = 'Số Phiếu';
      dataPoints = timelineData?.data_passes || [0, 0, 0, 0, 0, 0, 0];
      borderColor = '#059669';
      bgColor = 'rgba(5, 150, 105, 0.15)';
    } else if (GatePassState.chartMetric === 'units' || GatePassState.chartMetric === 'packages') {
      datasetLabel = 'Kiện / Thùng';
      dataPoints = timelineData?.data_units || [0, 0, 0, 0, 0, 0, 0];
      borderColor = '#d97706';
      bgColor = 'rgba(217, 119, 6, 0.15)';
    }

    try {
      gpTimelineChartInstance = new window.Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
          labels: labels,
          datasets: [{
            label: datasetLabel,
            data: dataPoints,
            borderColor: borderColor,
            backgroundColor: bgColor,
            fill: true,
            tension: 0.35,
            borderWidth: 2.2,
            pointRadius: 4
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false }
          },
          scales: {
            x: { grid: { display: false } },
            y: { beginAtZero: true, grid: { color: 'rgba(150, 150, 150, 0.12)' } }
          }
        }
      });
    } catch (e) {
      console.warn('[GatePass] Timeline chart error:', e);
    }
  }

  function renderCustomerChart(customerData) {
    const canvas = document.getElementById('gp-chart-customers');
    if (!canvas) return;

    if (typeof window.Chart === 'undefined') {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#64748b';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Biểu đồ cơ cấu khách hàng.', canvas.width / 2, canvas.height / 2);
      return;
    }

    if (gpCustomerChartInstance) {
      gpCustomerChartInstance.destroy();
      gpCustomerChartInstance = null;
    }

    const labels = customerData?.labels || ['Chưa có dữ liệu'];
    const dataPoints = customerData?.data_kg || customerData?.data || [1];
    const colors = ['#2563eb', '#38bdf8', '#059669', '#d97706', '#ec4899', '#8b5cf6'];

    try {
      gpCustomerChartInstance = new window.Chart(canvas.getContext('2d'), {
        type: 'doughnut',
        data: {
          labels: labels,
          datasets: [{
            data: dataPoints,
            backgroundColor: colors.slice(0, labels.length),
            borderWidth: 2
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'bottom',
              labels: { boxWidth: 12, font: { size: 10 } }
            }
          },
          cutout: '65%'
        }
      });
    } catch (e) {
      console.warn('[GatePass] Customer chart error:', e);
    }
  }

  // =========================================================================
  // 8. OCR SCAN API (POST /api/gatepass/ocr-scan)
  // =========================================================================

  async function scanOcr() {
    if (isGuestMode()) {
      showToast('Chế độ Khách không có quyền quét AI.', 'error');
      return;
    }

    let b64 = null;
    let fileName = 'slip.jpg';

    if (GatePassState.activeIndex >= 0 && GatePassState.queue[GatePassState.activeIndex]) {
      b64 = GatePassState.queue[GatePassState.activeIndex].originalBase64;
      fileName = GatePassState.queue[GatePassState.activeIndex].fileName;
    }

    if (!b64) {
      showToast('Vui lòng chọn hoặc dán ảnh phiếu xuất trước khi quét.', 'error');
      return;
    }

    const scanBtn = document.getElementById('btn-gatepass-scan-ocr') || document.getElementById('gp-btn-ai-scan');
    const origHtml = scanBtn ? scanBtn.innerHTML : '';
    if (scanBtn) {
      scanBtn.disabled = true;
      scanBtn.innerText = '⏳ Đang Quét Vision AI...';
    }

    try {
      if (GatePassState.canvas.rotation !== 0) {
        b64 = await transformImageRotation(b64, GatePassState.canvas.rotation);
      }

      const res = await fetch('/api/gatepass/ocr-scan', {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ image_b64: b64, filename: fileName })
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const payload = await res.json();
      const extracted = payload.data || payload;

      hydrateFormSlipData(extracted);
      showToast('✨ Trích xuất Vision AI thành công!', 'success');
    } catch (err) {
      console.warn('[GatePass] Scan error:', err);
      showToast('Lỗi khi quét phiếu Vision AI.', 'error');
    } finally {
      if (scanBtn) {
        scanBtn.disabled = false;
        scanBtn.innerHTML = origHtml;
      }
    }
  }

  // =========================================================================
  // 9. AUDIT & PROOF MATCHING (POST /api/gatepass/audit-match)
  // =========================================================================

  async function auditProof() {
    if (isGuestMode()) {
      showToast('Chế độ Khách không có quyền đối soát AI.', 'error');
      return;
    }

    const auditBtn = document.getElementById('btn-gatepass-audit-proof') || document.getElementById('gp-btn-run-audit');
    if (auditBtn) auditBtn.disabled = true;

    try {
      const slipData = serializeFormSlipData();
      const proofs = [GatePassState.proofs.vehicle, GatePassState.proofs.plate, GatePassState.proofs.cargo].filter(Boolean);

      const res = await fetch('/api/gatepass/audit-match', {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ slip_data: slipData, proof_images: proofs })
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const payload = await res.json();
      const audit = payload.data || payload;

      const resultBox = document.getElementById('gp-audit-result-box');
      if (resultBox) {
        resultBox.style.display = 'block';
        resultBox.innerHTML = `
          <div style="font-weight: 700; margin-bottom: 4px;">Kết quả đối soát: Điểm ${audit.score || 0}/100</div>
          <div>Biển số: ${audit.plate_matched ? '🟢 Khớp' : '🟡 Cần kiểm tra'} — ${escapeHtml(audit.match_summary || '')}</div>
          <div>Chữ ký: ${audit.signature_detected ? '🟢 Hợp lệ' : '⚪ Chưa phát hiện'}</div>
        `;
      }
      showToast('Đã đối soát bằng chứng hiện trường.', 'success');
    } catch (err) {
      console.warn('[GatePass] Audit error:', err);
      showToast('Lỗi khi thực hiện đối soát AI.', 'error');
    } finally {
      if (auditBtn) auditBtn.disabled = false;
    }
  }

  // =========================================================================
  // 10. SAVE SLIP & HISTORY API (POST /api/gatepass/save, GET /api/gatepass/history)
  // =========================================================================

  async function saveSlip(syncCloud = true) {
    if (isGuestMode()) {
      showToast('Chế độ Khách không có quyền lưu phiếu xuất.', 'error');
      return;
    }

    const slipData = serializeFormSlipData();
    if (!slipData.so_phieu) {
      showToast('Vui lòng nhập Mã Số Phiếu Xuất.', 'error');
      return;
    }

    const saveBtn = document.getElementById('btn-gatepass-save-slip') || document.getElementById('gp-btn-save-slip');
    if (saveBtn) saveBtn.disabled = true;

    try {
      let mainImgB64 = null;
      if (GatePassState.activeIndex >= 0 && GatePassState.queue[GatePassState.activeIndex]) {
        mainImgB64 = GatePassState.queue[GatePassState.activeIndex].originalBase64;
      }

      const payload = {
        ...slipData,
        slip: slipData,
        main_image_b64: mainImgB64,
        proof_images: [GatePassState.proofs.vehicle, GatePassState.proofs.plate, GatePassState.proofs.cargo].filter(Boolean),
        sync_cloud: syncCloud
      };

      const res = await fetch('/api/gatepass/save', {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}`);
      }

      showToast('💾 Đã lưu phiếu xuất và đồng bộ cloud thành công!', 'success');
      loadDashboardData();
      loadHistoryData();
    } catch (err) {
      console.error('[GatePass] Save error:', err);
      showToast(`Lỗi khi lưu phiếu: ${err.message}`, 'error');
    } finally {
      if (saveBtn) saveBtn.disabled = false;
    }
  }

  async function loadHistoryData() {
    const tbody = document.getElementById('gp-history-tbody');
    if (!tbody) return;

    const search = document.getElementById('gp-history-search')?.value.trim() || '';
    const period = document.getElementById('gp-history-filter-period')?.value || 'all';

    let url = `/api/gatepass/history?page=${GatePassState.history.page}&page_size=${GatePassState.history.pageSize}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (period !== 'all') url += `&period=${encodeURIComponent(period)}`;

    try {
      const res = await fetch(url, {
        headers: getAuthHeaders()
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const payload = await res.json();

      GatePassState.history.total = payload.total || 0;
      GatePassState.history.totalPages = payload.total_pages || 1;

      renderHistoryTable(payload.items || []);
    } catch (err) {
      console.warn('[GatePass] History error:', err);
    }
  }

  function renderHistoryTable(items) {
    const tbody = document.getElementById('gp-history-tbody');
    if (!tbody) return;

    if (!items || items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--gp-text-muted); padding: 24px;">Chưa có phiếu xuất nào.</td></tr>`;
      return;
    }

    tbody.innerHTML = '';
    const isGuest = isGuestMode();

    items.forEach(slip => {
      const tr = document.createElement('tr');
      const syncStatus = slip.sync_status === 'synced' ? '🟢 Đồng bộ' : '🟡 Chờ sync';
      const driveUrl = slip.main_file_url ? `<a href="${slip.main_file_url}" target="_blank" style="color:#2563eb; text-decoration:none;">☁️ Mở</a>` : '-';

      tr.innerHTML = `
        <td class="font-mono font-bold" style="color: var(--gp-primary-bg, #2563eb);">${escapeHtml(slip.so_phieu)}</td>
        <td>${escapeHtml(slip.ngay_thang || '')}</td>
        <td><small>${escapeHtml(slip.loai_xuat || '')}</small></td>
        <td class="font-mono font-bold">${escapeHtml(slip.so_xe || '---')}</td>
        <td>${escapeHtml(slip.don_vi_dat_hang || slip.khach_hang || '---')}</td>
        <td style="text-align: right; font-weight: 700; color: #059669;">${(slip.tong_cong_kg || 0).toLocaleString('vi-VN', { maximumFractionDigits: 1 })} kg</td>
        <td style="text-align: center;"><small>${syncStatus}</small></td>
        <td style="text-align: center;">${driveUrl}</td>
        <td style="text-align: center;">
          <div style="display: inline-flex; gap: 4px;">
            <button type="button" class="gatepass-btn-xs" title="Xem chi tiết" onclick="window.GatePassStudio.openDetailModal('${escapeHtml(slip.so_phieu)}')">🔍</button>
            <button type="button" class="gatepass-btn-xs" title="In phiếu" onclick="window.GatePassStudio.printSlip('${escapeHtml(slip.so_phieu)}')">🖨️</button>
            ${!isGuest ? `<button type="button" class="gatepass-btn-xs gatepass-btn-delete-slip" title="Xóa phiếu" style="color: #dc2626;" onclick="window.GatePassStudio.deleteSlip('${escapeHtml(slip.so_phieu)}')">🗑️</button>` : ''}
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });

    const pag = document.getElementById('gp-history-pagination');
    if (pag) {
      pag.innerHTML = `
        <span style="font-size: 0.8rem; color: var(--gp-text-secondary, #64748b);">Tổng cộng: <b>${GatePassState.history.total}</b> phiếu</span>
        <div style="display: flex; gap: 4px;">
          <button type="button" class="gatepass-hud-btn" ${GatePassState.history.page <= 1 ? 'disabled' : ''} onclick="window.GatePassStudio.changePage(-1)">◀ Trước</button>
          <span style="font-size: 0.82rem; font-weight: 700; padding: 4px 8px;">${GatePassState.history.page} / ${GatePassState.history.totalPages}</span>
          <button type="button" class="gatepass-hud-btn" ${GatePassState.history.page >= GatePassState.history.totalPages ? 'disabled' : ''} onclick="window.GatePassStudio.changePage(1)">Sau ▶</button>
        </div>
      `;
    }
  }

  // =========================================================================
  // 11. DETAIL MODAL & PRINTING
  // =========================================================================

  async function openDetailModal(soPhieu) {
    const modal = document.getElementById('gp-detail-modal') || document.getElementById('gp-modal-detail');
    if (!modal) return;

    try {
      const res = await fetch(`/api/gatepass/detail/${encodeURIComponent(soPhieu)}`, {
        headers: getAuthHeaders()
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const payload = await res.json();
      const slip = payload.data || payload;
      GatePassState.activeDetailSlip = slip;

      const titleEl = document.getElementById('gp-modal-slip-title');
      if (titleEl) titleEl.innerText = `Chi Tiết Phiếu Xuất: ${slip.so_phieu}`;

      const metaEl = document.getElementById('gp-modal-slip-meta');
      if (metaEl) {
        metaEl.innerHTML = `
          <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; font-size: 0.82rem;">
            <div><b>Ngày xuất:</b> ${escapeHtml(slip.ngay_thang || '---')}</div>
            <div><b>Biển số xe:</b> <span class="font-mono font-bold">${escapeHtml(slip.so_xe || '---')}</span></div>
            <div><b>Loại xuất:</b> ${escapeHtml(slip.loai_xuat || '---')}</div>
            <div><b>Số PO:</b> ${escapeHtml(slip.so_don_hang || slip.so_po || '---')}</div>
            <div style="grid-column: span 2;"><b>Khách hàng:</b> ${escapeHtml(slip.don_vi_dat_hang || slip.khach_hang || '---')}</div>
            <div style="grid-column: span 2;"><b>Đơn vị VC:</b> ${escapeHtml(slip.don_vi_van_chuyen || '---')}</div>
          </div>
        `;
      }

      const imgEl = document.getElementById('gp-modal-slip-img');
      if (imgEl) {
        if (slip.image_data_uri || slip.main_image_url) {
          imgEl.src = slip.image_data_uri || slip.main_image_url;
          imgEl.style.display = 'block';
        } else {
          imgEl.style.display = 'none';
        }
      }

      const tbody = document.getElementById('gp-modal-items-tbody');
      if (tbody) {
        tbody.innerHTML = '';
        (slip.items || []).forEach(it => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td style="text-align: center;">${it.stt}</td>
            <td><strong>${escapeHtml(it.loai_hang_hoa || '')}</strong></td>
            <td>${escapeHtml(it.quy_cach || '')}</td>
            <td style="text-align: right;">${it.sl_kien || '-'}</td>
            <td style="text-align: right;">${it.sl_thung || '-'}</td>
            <td style="text-align: right; font-weight: 700;">${it.khoi_luong_kg ? it.khoi_luong_kg + ' kg' : '-'}</td>
            <td><small>${escapeHtml(it.ghi_chu || '')}</small></td>
          `;
          tbody.appendChild(tr);
        });
      }

      modal.classList.remove('hidden');
      modal.style.display = 'flex';
    } catch (err) {
      console.warn('[GatePass] Open detail modal failed:', err);
      showToast('Lỗi khi tải chi tiết phiếu xuất.', 'error');
    }
  }

  function closeDetailModal() {
    const modal = document.getElementById('gp-detail-modal') || document.getElementById('gp-modal-detail');
    if (modal) {
      modal.classList.add('hidden');
      modal.style.display = 'none';
    }
  }

  function printSlip(soPhieu, paperSize = 'A4') {
    const code = soPhieu || GatePassState.activeDetailSlip?.so_phieu || document.getElementById('gp-field-so-phieu')?.value || document.getElementById('gp-input-so-phieu')?.value;
    if (!code) {
      showToast('Vui lòng chọn phiếu xuất để in.', 'error');
      return;
    }
    window.open(`/api/gatepass/print/${encodeURIComponent(code)}?paper_size=${paperSize}`, '_blank');
  }

  async function deleteSlip(soPhieu) {
    if (isGuestMode()) {
      showToast('Chế độ Khách không có quyền xóa phiếu.', 'error');
      return;
    }

    if (!confirm(`Bạn có chắc chắn muốn xóa vĩnh viễn phiếu [${soPhieu}]?`)) return;

    try {
      const res = await fetch(`/api/gatepass/${encodeURIComponent(soPhieu)}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showToast(`Đã xóa thành công phiếu [${soPhieu}].`, 'success');
      loadHistoryData();
      loadDashboardData();
    } catch (err) {
      console.warn('[GatePass] Delete error:', err);
      showToast('Lỗi khi xóa phiếu xuất.', 'error');
    }
  }

  // =========================================================================
  // 12. INITIALIZATION & PUBLIC API BINDINGS
  // =========================================================================

  function bindDomEvents() {
    // Zoom & Canvas Controls
    document.getElementById('btn-gp-zoom-in')?.addEventListener('click', () => canvasZoom(1.2));
    document.getElementById('btn-gp-zoom-out')?.addEventListener('click', () => canvasZoom(0.8));
    document.getElementById('btn-gp-zoom-reset')?.addEventListener('click', () => canvasResetZoom());
    document.getElementById('btn-gp-rotate')?.addEventListener('click', () => canvasRotate(90));
    document.getElementById('btn-gp-contrast')?.addEventListener('click', () => canvasToggleContrast());

    // Metric toggles
    document.querySelectorAll('.gatepass-chart-toggle-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.gatepass-chart-toggle-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        GatePassState.chartMetric = btn.getAttribute('data-metric') || 'kg';
        if (GatePassState.dashboardData) {
          renderTimelineChart(GatePassState.dashboardData.charts?.timeline);
        }
      });
    });

    // Add item button
    const btnAddItem = document.getElementById('btn-gatepass-add-item');
    if (btnAddItem) {
      btnAddItem.addEventListener('click', () => addGatePassItemRow());
    }

    // Save button
    const btnSave = document.getElementById('btn-gatepass-save-slip');
    if (btnSave) {
      btnSave.addEventListener('click', () => saveSlip(true));
    }

    // Scan OCR button
    const btnScan = document.getElementById('btn-gatepass-scan-ocr');
    if (btnScan) {
      btnScan.addEventListener('click', () => scanOcr());
    }

    // Audit Proof button
    const btnAudit = document.getElementById('btn-gatepass-audit-proof');
    if (btnAudit) {
      btnAudit.addEventListener('click', () => auditProof());
    }

    // New slip button
    const btnNew = document.getElementById('btn-gatepass-new-slip');
    if (btnNew) {
      btnNew.addEventListener('click', () => clearFormFields());
    }

    // Print button
    const btnPrint = document.getElementById('btn-gatepass-print');
    if (btnPrint) {
      btnPrint.addEventListener('click', () => printSlip());
    }

    const btnModalPrint = document.getElementById('gp-btn-modal-print');
    if (btnModalPrint) {
      btnModalPrint.addEventListener('click', () => printSlip());
    }

    // History search
    const searchInput = document.getElementById('gp-history-search');
    if (searchInput) {
      searchInput.addEventListener('input', () => {
        clearTimeout(GatePassState.history.searchDebounceTimer);
        GatePassState.history.searchDebounceTimer = setTimeout(() => {
          GatePassState.history.page = 1;
          loadHistoryData();
        }, 250);
      });
    }

    // History filter period
    const filterPeriod = document.getElementById('gp-history-filter-period');
    if (filterPeriod) {
      filterPeriod.addEventListener('change', () => {
        GatePassState.history.page = 1;
        loadHistoryData();
      });
    }

    // Proof file slots
    const proofInputs = [
      { id: 'gp-proof-input-vehicle', type: 'vehicle', slot: 'gp-proof-slot-vehicle' },
      { id: 'gp-proof-input-plate', type: 'plate', slot: 'gp-proof-slot-plate' },
      { id: 'gp-proof-input-cargo', type: 'cargo', slot: 'gp-proof-slot-cargo' }
    ];

    proofInputs.forEach(item => {
      const el = document.getElementById(item.id);
      if (el) {
        el.addEventListener('change', async (e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          const durl = await readFileAsDataUrl(file);
          GatePassState.proofs[item.type] = durl;
          const slot = document.getElementById(item.slot);
          if (slot) {
            slot.style.background = '#dcfce7';
            slot.innerHTML = `<span style="color:#166534; font-weight:700;">✓ Đã chọn ảnh</span>`;
          }
        });
      }
    });

    // Setup canvas pan and dropzone
    setupCanvasPan();
    setupDropzone();
  }

  function applyGuestRestrictions() {
    const isGuest = isGuestMode();
    const formInputSelectors = [
      '#gp-field-so-phieu', '#gp-field-so-xe', '#gp-field-don-vi-vc',
      '#gp-field-khach-hang', '#gp-field-so-po', '#gp-field-bo-phan',
      '#gp-field-phe-duyet', '#gp-field-ghi-chu', '#gp-field-ngay-thang',
      '#gp-input-so-phieu', '#gp-input-so-xe', '#gp-input-don-vi-vc',
      '#gp-input-khach-hang', '#gp-input-so-po', '#gp-input-bo-phan',
      '#gp-input-phe-duyet', '#gp-input-ghi-chu', '#gp-input-ngay-thang'
    ];

    formInputSelectors.forEach(sel => {
      document.querySelectorAll(sel).forEach(el => {
        if (isGuest) {
          el.setAttribute('readonly', 'readonly');
        } else {
          el.removeAttribute('readonly');
        }
      });
    });

    const mutationSelectors = [
      '#btn-gatepass-scan-ocr', '#btn-gatepass-save-slip', '#btn-gatepass-audit-proof',
      '#btn-gatepass-add-item', '.gatepass-btn-add-item', '.gatepass-mutation-action'
    ];
    mutationSelectors.forEach(sel => {
      document.querySelectorAll(sel).forEach(el => {
        el.style.display = isGuest ? 'none' : '';
      });
    });

    document.querySelectorAll('.gatepass-guest-badge').forEach(el => {
      el.style.display = isGuest ? 'inline-flex' : 'none';
    });
  }

  // Observe role attribute changes on document.body for instant reactive locking
  try {
    const roleObserver = new MutationObserver((mutations) => {
      for (const m of mutations) {
        if (m.type === 'attributes' && m.attributeName === 'data-role') {
          applyGuestRestrictions();
          loadHistoryData();
          break;
        }
      }
    });
    if (document.body) {
      roleObserver.observe(document.body, { attributes: true, attributeFilter: ['data-role'] });
    } else {
      document.addEventListener('DOMContentLoaded', () => {
        if (document.body) roleObserver.observe(document.body, { attributes: true, attributeFilter: ['data-role'] });
      });
    }
  } catch (e) {
    console.warn('[GatePass] Role observer setup error:', e);
  }

  function init() {
    if (!GatePassState.initialized) {
      bindDomEvents();
      GatePassState.initialized = true;
    }

    applyGuestRestrictions();
    loadDashboardData();
    loadHistoryData();
  }

  // Define public API on window.GatePassStudio
  window.GatePassStudio = {
    init: init,
    closeDetailModal: closeDetailModal,
    openDetailModal: openDetailModal,
    saveSlip: saveSlip,
    scanOcr: scanOcr,
    auditProof: auditProof,
    newSlip: clearFormFields,
    printSlip: printSlip,
    deleteSlip: deleteSlip,
    addCustomItem: addGatePassItemRow,
    recalcTotals: recalcTotals,
    zoomIn: () => canvasZoom(1.2),
    zoomOut: () => canvasZoom(0.8),
    resetZoom: canvasResetZoom,
    rotate: () => canvasRotate(90),
    toggleContrast: canvasToggleContrast,
    changePage: (delta) => {
      const target = GatePassState.history.page + delta;
      if (target >= 1 && target <= GatePassState.history.totalPages) {
        GatePassState.history.page = target;
        loadHistoryData();
      }
    }
  };

  // Backward compatibility alias
  window.initGatePassStudio = init;

  // Auto-init if loaded with gatepass hash
  document.addEventListener('DOMContentLoaded', () => {
    if (!GatePassState.initialized) {
      bindDomEvents();
      GatePassState.initialized = true;
    }
    if (window.location.hash === '#gatepass-studio' || window.location.hash === '#gatepass') {
      if (typeof window.switchMainTab === 'function') {
        window.switchMainTab('gatepass');
      }
    }
  });

})();
