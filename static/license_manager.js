/**
 * license_manager.js
 * ──────────────────
 * Trình Quản Lý Bản Quyền LUV Trực Tuyến (Online License Manager Suite)
 * Cho phép Quản trị viên/Owner:
 * 1. Tạo Khóa Bản Quyền Mới (Key Generator) chuẩn mật mã SHA-256.
 * 2. Tự động sinh Mẫu Tin Nhắn Bàn Giao Khách Hàng chuyên nghiệp (1-Click Copy).
 * 3. Xem danh sách, tìm kiếm, lọc theo trạng thái/gói bản quyền.
 * 4. Thu hồi (Revoke) và Xóa vĩnh viễn khóa bản quyền từ xa.
 */

window.LicenseManager = {
    keysCache: [],

    init: async function() {
        // RBAC check: only owner/admin can access
        const isGuest = document.body.getAttribute('data-role') === 'guest';
        if (isGuest) {
            const container = document.getElementById('license-manager-view');
            if (container) {
                container.innerHTML = `
                    <div style="padding:60px 20px; text-align:center; color:#f87171;">
                        <h2>🔒 TRUY CẬP BỊ TỪ CHỐI</h2>
                        <p style="color:#94a3b8; margin-top:8px;">Khu vực Quản lý Bản quyền chỉ dành riêng cho Quản trị viên / Chủ sở hữu hệ thống (Owner).</p>
                    </div>
                `;
            }
            return;
        }

        await this.loadLicenses();
        this.bindEvents();
    },

    bindEvents: function() {
        const btnGen = document.getElementById('btn-license-gen');
        if (btnGen && !btnGen._bound) {
            btnGen._bound = true;
            btnGen.addEventListener('click', () => this.handleGenerate());
        }

        const inputSearch = document.getElementById('license-search-query');
        if (inputSearch && !inputSearch._bound) {
            inputSearch._bound = true;
            inputSearch.addEventListener('input', (e) => this.filterList(e.target.value));
        }

        const selectStatus = document.getElementById('license-filter-status');
        if (selectStatus && !selectStatus._bound) {
            selectStatus._bound = true;
            selectStatus.addEventListener('change', () => this.loadLicenses());
        }
    },

    loadLicenses: async function() {
        const tbody = document.getElementById('license-table-body');
        if (!tbody) return;

        const statusFilter = document.getElementById('license-filter-status')?.value || '';
        const searchQuery = document.getElementById('license-search-query')?.value || '';

        try {
            tbody.innerHTML = `<tr><td colspan="7" class="license-empty-state">Đang tải danh sách bản quyền...</td></tr>`;
            const resp = await fetch(`/api/admin/licenses?q=${encodeURIComponent(searchQuery)}&status=${encodeURIComponent(statusFilter)}`);
            const res = await resp.json();

            if (res.success && Array.isArray(res.data)) {
                this.keysCache = res.data;
                this.renderTable(res.data);
                const countBadge = document.getElementById('license-total-count');
                if (countBadge) countBadge.textContent = res.data.length;
            } else {
                tbody.innerHTML = `<tr><td colspan="7" class="license-empty-state">Không có dữ liệu hoặc có lỗi xảy ra.</td></tr>`;
            }
        } catch (err) {
            console.error('Lỗi tải danh sách bản quyền:', err);
            tbody.innerHTML = `<tr><td colspan="7" class="license-empty-state" style="color:#ef4444;">Lỗi kết nối máy chủ: ${err.message}</td></tr>`;
        }
    },

    renderTable: function(keys) {
        const tbody = document.getElementById('license-table-body');
        if (!tbody) return;

        if (!keys || keys.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="license-empty-state">Chưa có khóa bản quyền nào phù hợp.</td></tr>`;
            return;
        }

        tbody.innerHTML = keys.map((item, idx) => {
            const isActive = item.status === 'active';
            const badgeClass = isActive ? 'license-badge-active' : 'license-badge-revoked';
            const badgeText = isActive ? '✓ Hoạt Động' : '✕ Đã Thu Hồi';
            const activeDev = item.active_devices !== undefined ? item.active_devices : 0;
            const maxDev = item.max_devices !== undefined ? item.max_devices : 1;
            const isFull = maxDev > 0 && activeDev >= maxDev;
            const devTagClass = isFull ? 'license-device-tag tag-full' : 'license-device-tag';
            const devTagStyle = isFull ? 'color:#ef4444; font-weight:700; background:rgba(239,68,68,0.12); padding:2px 6px; border-radius:4px; display:inline-block; margin-top:4px;' : 'color:#38bdf8; font-size:11px; margin-top:4px;';
            const deviceText = `${activeDev}/${maxDev} máy${isFull ? ' (ĐÃ ĐẦY - TỪ CHỐI THÊM)' : ''}`;
            const itemId = item.id || '';
            const itemKey = item.license_key || '';
            const fullKey = item.full_key || '';

            return `
                <tr>
                    <td style="text-align:center; color:#64748b;">${idx + 1}</td>
                    <td>
                        <span class="license-table-key">${this.escapeHtml(itemKey)}</span>
                        <div class="${devTagClass}" style="${devTagStyle}">📱 ${this.escapeHtml(deviceText)}</div>
                    </td>
                    <td><strong>${this.escapeHtml(item.registered_to || 'Khách hàng')}</strong></td>
                    <td><span style="color:#e2e8f0;">${this.escapeHtml(item.tier || 'Enterprise')}</span></td>
                    <td><span style="color:#94a3b8;">${this.escapeHtml(item.expires_at || 'Vĩnh viễn')}</span></td>
                    <td><span class="license-badge-status ${badgeClass}">${badgeText}</span></td>
                    <td style="white-space:nowrap;">
                        <button class="license-btn-xs license-btn-xs-copy" onclick="window.LicenseManager.copyKey('${this.escapeHtml(fullKey || itemKey)}')" title="Sao chép Key">Sao chép</button>
                        <button class="license-btn-xs" style="background:#16a34a;color:#fff;" onclick="window.LicenseManager.copyHandover('${this.escapeHtml(itemKey)}')" title="Copy mẫu bàn giao">Bàn giao</button>
                        ${isActive ? `
                            <button class="license-btn-xs license-btn-xs-reset" onclick="window.LicenseManager.resetDevices('${this.escapeHtml(itemId)}', '${this.escapeHtml(itemKey)}')" title="Xóa liên kết máy, cho phép kích hoạt trên thiết bị mới">Reset Máy</button>
                            <button class="license-btn-xs license-btn-xs-revoke" onclick="window.LicenseManager.revokeKey('${this.escapeHtml(itemId)}', '${this.escapeHtml(itemKey)}')" title="Thu hồi khóa này">Thu hồi</button>
                        ` : ''}
                        <button class="license-btn-xs license-btn-xs-delete" onclick="window.LicenseManager.deleteKey('${this.escapeHtml(itemId)}', '${this.escapeHtml(itemKey)}')" title="Xóa vĩnh viễn">✕</button>
                    </td>
                </tr>
            `;
        }).join('');
    },

    handleGenerate: async function() {
        const regInput = document.getElementById('license-ent-reg');
        const tierSelect = document.getElementById('license-ent-tier');
        const expSelect = document.getElementById('license-ent-exp');
        const maxDevInput = document.getElementById('license-ent-max-devices');
        const notesInput = document.getElementById('license-ent-notes');

        const reg = regInput?.value.trim();
        if (!reg) {
            alert('Vui lòng nhập tên Khách hàng hoặc Doanh nghiệp!');
            regInput?.focus();
            return;
        }

        const tier = tierSelect?.value || 'Enterprise Lifetime (Vĩnh viễn)';
        const exp = expSelect?.value || 'Vĩnh viễn (Lifetime)';
        const maxDev = parseInt(maxDevInput?.value) || 1;
        const notes = notesInput?.value.trim() || '';

        const formData = new FormData();
        formData.append('registered_to', reg);
        formData.append('tier', tier);
        formData.append('expires', exp);
        formData.append('max_devices', maxDev);
        formData.append('notes', notes);

        try {
            const btn = document.getElementById('btn-license-gen');
            if (btn) btn.disabled = true;

            const resp = await fetch('/api/admin/licenses/create', {
                method: 'POST',
                body: formData
            });
            const res = await resp.json();

            if (res.success && res.data) {
                const resultBox = document.getElementById('license-result-box');
                const keyDisplay = document.getElementById('license-key-disp');
                if (resultBox) resultBox.style.display = 'block';
                if (keyDisplay) keyDisplay.textContent = res.data.license_key;

                this._lastGenerated = res.data;
                await this.loadLicenses();
            } else {
                alert('Không thể tạo bản quyền: ' + (res.detail || res.message || 'Lỗi không xác định'));
            }
        } catch (err) {
            alert('Lỗi máy chủ khi tạo bản quyền: ' + err.message);
        } finally {
            const btn = document.getElementById('btn-license-gen');
            if (btn) btn.disabled = false;
        }
    },

    copyKey: function(key) {
        if (!key) return;
        navigator.clipboard.writeText(key).then(() => {
            this.showToast('✓ Đã sao chép Khóa: ' + key);
        }).catch(() => {
            prompt('Sao chép mã bản quyền:', key);
        });
    },

    copyLastKey: function() {
        if (this._lastGenerated?.license_key) {
            this.copyKey(this._lastGenerated.license_key);
        }
    },

    copyHandover: function(key) {
        const item = this.keysCache.find(k => k.license_key === key || k.full_key === key || k.id === key) || this._lastGenerated;
        if (!item) return;

        const text = item.handover_message || `Mã bản quyền: ${item.full_key || item.license_key}\nKhách hàng: ${item.registered_to}\nGói: ${item.tier}\nThời hạn: ${item.expires_at}`;
        navigator.clipboard.writeText(text).then(() => {
            this.showToast('📋 Đã copy Mẫu Tin Nhắn Bàn Giao Khách Hàng!');
        }).catch(() => {
            alert('Mẫu bàn giao:\n\n' + text);
        });
    },

    copyLastHandover: function() {
        if (this._lastGenerated?.handover_message) {
            navigator.clipboard.writeText(this._lastGenerated.handover_message).then(() => {
                this.showToast('📋 Đã copy Mẫu Tin Nhắn Bàn Giao Khách Hàng!');
            });
        }
    },

    resetDevices: async function(id, key) {
        const displayLabel = key || id;
        if (!confirm(`Bạn có chắc chắn muốn RESET LIÊN KẾT MÁY cho giấy phép [${displayLabel}] không?\nToàn bộ máy đang liên kết sẽ được giải phóng để khách hàng có thể kích hoạt trên thiết bị mới.`)) {
            return;
        }

        const formData = new FormData();
        const targetId = id || key;
        formData.append('license_id', targetId);
        formData.append('id', targetId);
        if (key) formData.append('key', key);

        try {
            const resp = await fetch('/api/admin/licenses/reset-devices', {
                method: 'POST',
                body: formData
            });
            const res = await resp.json();
            if (res.success) {
                this.showToast('✓ Đã reset liên kết máy thành công!');
                await this.loadLicenses();
            } else {
                alert('Không thể reset máy: ' + (res.detail || res.message || 'Lỗi không xác định'));
            }
        } catch (err) {
            alert('Lỗi kết nối máy chủ: ' + err.message);
        }
    },

    revokeKey: async function(id, key) {
        const displayLabel = key || id;
        if (!confirm(`Bạn có chắc chắn muốn THU HỒI giấy phép [${displayLabel}] không?\nSau khi thu hồi, client sử dụng mã này sẽ bị khóa bản quyền.`)) {
            return;
        }

        const formData = new FormData();
        const targetId = id || key;
        formData.append('license_id', targetId);
        formData.append('id', targetId);
        if (key) formData.append('key', key);

        try {
            const resp = await fetch('/api/admin/licenses/revoke', {
                method: 'POST',
                body: formData
            });
            const res = await resp.json();
            if (res.success) {
                this.showToast('✓ Đã thu hồi bản quyền: ' + displayLabel);
                await this.loadLicenses();
            } else {
                alert('Không thể thu hồi: ' + (res.detail || res.message || 'Lỗi không xác định'));
            }
        } catch (err) {
            alert('Lỗi kết nối: ' + err.message);
        }
    },

    deleteKey: async function(id, key) {
        const displayLabel = key || id;
        if (!confirm(`Xóa vĩnh viễn hồ sơ bản quyền [${displayLabel}] khỏi cơ sở dữ liệu?`)) {
            return;
        }

        const formData = new FormData();
        const targetId = id || key;
        formData.append('license_id', targetId);
        formData.append('id', targetId);
        if (key) formData.append('key', key);

        try {
            const resp = await fetch('/api/admin/licenses/delete', {
                method: 'POST',
                body: formData
            });
            const res = await resp.json();
            if (res.success) {
                this.showToast('✓ Đã xóa bản quyền khỏi hệ thống');
                await this.loadLicenses();
            } else {
                alert('Không thể xóa: ' + (res.detail || res.message || 'Lỗi không xác định'));
            }
        } catch (err) {
            alert('Lỗi kết nối: ' + err.message);
        }
    },

    filterList: function(query) {
        query = (query || '').toLowerCase().trim();
        if (!query) {
            this.renderTable(this.keysCache);
            return;
        }
        const filtered = this.keysCache.filter(item => 
            (item.license_key || '').toLowerCase().includes(query) ||
            (item.registered_to || '').toLowerCase().includes(query) ||
            (item.tier || '').toLowerCase().includes(query)
        );
        this.renderTable(filtered);
    },

    showToast: function(msg) {
        let toast = document.getElementById('license-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'license-toast';
            toast.style.cssText = `
                position: fixed;
                bottom: 24px;
                right: 24px;
                background: #0284c7;
                color: #ffffff;
                padding: 12px 20px;
                border-radius: 10px;
                font-weight: 600;
                font-size: 0.9rem;
                box-shadow: 0 10px 25px rgba(0,0,0,0.4);
                z-index: 99999;
                transition: opacity 0.3s ease;
                display: flex;
                align-items: center;
                gap: 8px;
            `;
            document.body.appendChild(toast);
        }
        toast.textContent = msg;
        toast.style.opacity = '1';
        clearTimeout(toast._timer);
        toast._timer = setTimeout(() => {
            toast.style.opacity = '0';
        }, 3000);
    },

    escapeHtml: function(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
};

window.initLicenseManager = function() {
    window.LicenseManager.init();
};
