/**
 * LUV-PDF PRIVATE SUITE — ENTERPRISE GLOBAL AI SERVICE
 * ============================================================================
 * Module quản lý API Key và điều phối gọi AI tập trung (Single Source of Truth).
 * 
 * - Quản lý cấu hình toàn cục: Provider (DeepSeek, OpenAI, Custom), Key, Model, Base URL.
 * - Bảo vệ API Key tuyệt đối: Masking cho Khách, phân quyền Admin (Chính chủ).
 * - Kiểm soát hạn mức cho Khách (Guest Rate Limit: Max 15 lượt gọi / phiên).
 * - Đồng bộ hóa trạng thái tức thì đến tất cả các tab (MSDS, HSE, OCR, Dịch, Tóm tắt).
 * - Trải nghiệm Fallback mượt mà: Điều hướng 1-click tới Cài đặt cho Admin.
 * ============================================================================
 */

(function (window) {
    "use strict";

    const STORAGE_KEY_CONFIG = "luv_ai_config";
    const STORAGE_KEY_LEGACY = "deepseek_api_key";
    const STORAGE_KEY_LEGACY_MODEL = "deepseek_model";
    const STORAGE_KEY_LEGACY_BASE = "deepseek_base_url";
    const SESSION_KEY_GUEST_CALLS = "luv_guest_ai_calls";
    const GUEST_MAX_CALLS_PER_SESSION = 15;

    class LuvAIServiceManager {
        constructor() {
            this.config = {
                provider: "deepseek", // 'deepseek' | 'openai' | 'custom'
                apiKey: "",
                model: "DeepSeek-V4.1-Flash",
                baseUrl: "https://api.deepseek.com/v1"
            };
            this._registeredBadgeContainers = new Set();
            this._isInitialized = false;

            // Load stored settings on instantiation
            this._loadLocalConfig();
        }

        /**
         * Khởi tạo service khi tải trang
         */
        async init() {
            if (this._isInitialized) return;
            this._loadLocalConfig();

            // Đồng bộ cấu hình từ máy chủ (nếu người dùng là Admin hoặc Khách)
            await this.syncFromServer();

            // Đăng ký listener sự kiện thay đổi vai trò hoặc cấu hình
            window.addEventListener("storage", (e) => {
                if (e.key === STORAGE_KEY_CONFIG || e.key === STORAGE_KEY_LEGACY) {
                    this._loadLocalConfig();
                    this.refreshAllBadges();
                }
            });

            this._isInitialized = true;
            this.refreshAllBadges();
        }

        /**
         * Kiểm tra vai trò hiện tại của người dùng
         */
        isGuest() {
            try {
                return document.body?.getAttribute("data-role") === "guest" ||
                    sessionStorage.getItem("luv_user_role") === "guest" ||
                    window.__CURRENT_ROLE === "guest";
            } catch (e) {
                return false;
            }
        }

        /**
         * Nạp cấu hình từ localStorage & fallback sang legacy keys
         */
        _loadLocalConfig() {
            try {
                const raw = localStorage.getItem(STORAGE_KEY_CONFIG);
                if (raw) {
                    const parsed = JSON.parse(raw);
                    this.config = Object.assign({}, this.config, parsed);
                } else {
                    // Fallback to individual keys
                    const legacyKey = localStorage.getItem(STORAGE_KEY_LEGACY);
                    const legacyModel = localStorage.getItem(STORAGE_KEY_LEGACY_MODEL);
                    const legacyBase = localStorage.getItem(STORAGE_KEY_LEGACY_BASE);
                    if (legacyKey) this.config.apiKey = legacyKey.trim();
                    if (legacyModel) this.config.model = legacyModel.trim();
                    if (legacyBase) this.config.baseUrl = legacyBase.trim();
                }
            } catch (e) {
                console.warn("[LuvAIService] Lỗi đọc cấu hình từ localStorage:", e);
            }
        }

        /**
         * Lưu cấu hình vào localStorage và đồng bộ legacy keys
         */
        _saveLocalConfig(newCfg) {
            this.config = Object.assign({}, this.config, newCfg);
            try {
                localStorage.setItem(STORAGE_KEY_CONFIG, JSON.stringify(this.config));
                if (this.config.apiKey) {
                    localStorage.setItem(STORAGE_KEY_LEGACY, this.config.apiKey);
                } else {
                    localStorage.removeItem(STORAGE_KEY_LEGACY);
                }
                if (this.config.model) localStorage.setItem(STORAGE_KEY_LEGACY_MODEL, this.config.model);
                if (this.config.baseUrl) localStorage.setItem(STORAGE_KEY_LEGACY_BASE, this.config.baseUrl);
            } catch (e) {
                console.warn("[LuvAIService] Không thể ghi vào localStorage:", e);
            }

            // Phát sự kiện toàn cục
            window.dispatchEvent(new CustomEvent("luv:ai:config:changed", { detail: this.getConfig() }));
            this.refreshAllBadges();
        }

        /**
         * Đồng bộ cấu hình AI từ máy chủ (GET /api/settings/deepseek)
         */
        async syncFromServer() {
            try {
                const res = await fetch("/api/settings/deepseek");
                if (!res.ok) return;
                const data = await res.json();
                if (data) {
                    const isG = this.isGuest();
                    if (!isG && data.key) {
                        this.config.apiKey = data.key;
                    }
                    if (data.model || data.default_model) {
                        this.config.model = data.model || data.default_model;
                    }
                    if (data.provider) {
                        this.config.provider = data.provider;
                    }
                    if (data.base_url) {
                        this.config.baseUrl = data.base_url;
                    }
                    // Đánh dấu hệ thống có key (kể cả khi guest bị mask)
                    this._serverHasKey = !!data.has_key;

                    if (!isG && this.config.apiKey) {
                        this._saveLocalConfig(this.config);
                    } else {
                        this.refreshAllBadges();
                    }
                }
            } catch (e) {
                console.warn("[LuvAIService] Chưa thể kết nối máy chủ để lấy cấu hình AI:", e);
            }
        }

        /**
         * Lấy toàn bộ thông tin cấu hình AI an toàn
         */
        getConfig() {
            return {
                provider: this.config.provider || "deepseek",
                apiKey: this.getApiKey(),
                model: this.getModel(),
                baseUrl: this.getBaseUrl(),
                hasKey: this.hasKey(),
                isGuest: this.isGuest(),
                guestQuota: this.getGuestUsage()
            };
        }

        /**
         * Kiểm tra hệ thống đã có API Key chưa
         */
        hasKey() {
            if (this.isGuest()) {
                // Đối với Khách, kiểm tra cờ serverHasKey hoặc legacy masked
                return this._serverHasKey !== false;
            }
            return Boolean(this.config.apiKey && this.config.apiKey.trim().length > 5);
        }

        /**
         * Lấy API Key (Khách luôn nhận chuỗi đã che giấu)
         */
        getApiKey() {
            if (this.isGuest()) {
                return "••••••••••••••••";
            }
            return this.config.apiKey || "";
        }

        /**
         * Lấy Raw API Key phục vụ gửi HTTP request
         */
        getRawApiKey() {
            return (this.config.apiKey || "").trim();
        }

        /**
         * Lấy tên Model hiện tại
         */
        getModel() {
            return this.config.model || "DeepSeek-V4.1-Flash";
        }

        /**
         * Lấy Provider (deepseek, openai, custom)
         */
        getProvider() {
            return this.config.provider || "deepseek";
        }

        /**
         * Lấy Base URL của API
         */
        getBaseUrl() {
            return this.config.baseUrl || "https://api.deepseek.com/v1";
        }

        /**
         * Cập nhật cấu hình toàn cục (Chỉ dành cho Admin)
         */
        async saveConfig({ apiKey, model, provider, baseUrl }) {
            if (this.isGuest()) {
                throw new Error("Chế độ Khách (Guest) không có quyền thay đổi cấu hình API Key!");
            }

            const cleanKey = (apiKey || "").trim();
            const cleanModel = (model || "").trim() || "DeepSeek-V4.1-Flash";
            const cleanProvider = (provider || "").trim() || "deepseek";
            const cleanBaseUrl = (baseUrl || "").trim() || "https://api.deepseek.com/v1";

            if (!cleanKey) {
                throw new Error("Vui lòng nhập API Key hợp lệ!");
            }

            // Gửi lưu lên backend
            const fd = new FormData();
            fd.append("api_key", cleanKey);
            fd.append("model", cleanModel);
            fd.append("provider", cleanProvider);
            fd.append("base_url", cleanBaseUrl);

            const res = await fetch("/api/settings/deepseek", {
                method: "POST",
                body: fd
            });
            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error(data.detail || data.error || "Lỗi lưu cấu hình lên máy chủ.");
            }

            // Lưu cục bộ và đồng bộ UI
            this._saveLocalConfig({
                apiKey: cleanKey,
                model: cleanModel,
                provider: cleanProvider,
                baseUrl: cleanBaseUrl
            });
            this._serverHasKey = true;

            // Đồng bộ các trường input legacy (nếu còn tồn tại trong DOM)
            this._syncLegacyInputFields(cleanKey);

            return data;
        }

        /**
         * Kiểm tra kết nối API thực tế trước khi lưu
         */
        async testConnection({ apiKey, model, provider, baseUrl } = {}) {
            const keyToTest = (apiKey || this.getRawApiKey() || "").trim();
            const modelToTest = (model || this.getModel() || "").trim();
            const providerToTest = (provider || this.getProvider() || "deepseek").trim();
            const baseToTest = (baseUrl || this.getBaseUrl() || "").trim();

            if (!keyToTest) {
                throw new Error("Vui lòng nhập API Key trước khi kiểm tra kết nối!");
            }

            const fd = new FormData();
            fd.append("api_key", keyToTest);
            fd.append("model", modelToTest);
            fd.append("provider", providerToTest);
            fd.append("base_url", baseToTest);

            const res = await fetch("/api/settings/deepseek/test", {
                method: "POST",
                body: fd
            });
            const data = await res.json();
            if (!res.ok || !data.success) {
                let msg = data.message || data.detail || "Vui lòng kiểm tra lại Key hoặc Base URL!";
                msg = msg.replace(/^(?:❌\s*)?(?:Kết nối thất bại\s*[:：]\s*)+/gi, "").trim();
                throw new Error(msg);
            }
            return data;
        }

        /**
         * Kiểm tra và kiểm soát hạn mức gọi AI của Khách (Guest Rate Limiting)
         */
        getGuestUsage() {
            try {
                const used = parseInt(sessionStorage.getItem(SESSION_KEY_GUEST_CALLS) || "0", 10);
                return {
                    used: isNaN(used) ? 0 : used,
                    max: GUEST_MAX_CALLS_PER_SESSION,
                    remaining: Math.max(0, GUEST_MAX_CALLS_PER_SESSION - (isNaN(used) ? 0 : used))
                };
            } catch (e) {
                return { used: 0, max: GUEST_MAX_CALLS_PER_SESSION, remaining: GUEST_MAX_CALLS_PER_SESSION };
            }
        }

        recordGuestCall() {
            if (!this.isGuest()) return;
            try {
                const usage = this.getGuestUsage();
                const nextUsed = usage.used + 1;
                sessionStorage.setItem(SESSION_KEY_GUEST_CALLS, nextUsed.toString());
                this.refreshAllBadges();
            } catch (e) {
                console.warn("[LuvAIService] Không thể ghi nhận lượt gọi khách:", e);
            }
        }

        /**
         * Kiểm tra trước khi thực thi AI:
         * - Nếu chưa có key: Hiển thị hướng dẫn hoặc nút mở Cài đặt (cho Admin)
         * - Nếu Khách hết lượt: Báo lỗi hạn mức
         * @returns {boolean} true nếu hợp lệ, false nếu dừng
         */
        requireReady({ contextName = "tác vụ AI" } = {}) {
            // 1. Kiểm tra hạn mức Khách
            if (this.isGuest()) {
                const quota = this.getGuestUsage();
                if (quota.remaining <= 0) {
                    this.showGuestLimitExceededModal();
                    return false;
                }
            }

            // 2. Kiểm tra API Key
            if (!this.hasKey()) {
                this.showMissingKeyPrompt(contextName);
                return false;
            }

            return true;
        }

        /**
         * Modal / Hộp thoại cảnh báo khi chưa có API Key
         */
        showMissingKeyPrompt(contextName = "tác vụ AI") {
            const isG = this.isGuest();
            if (isG) {
                alert(
                    `⚠️ HỆ THỐNG CHƯA ĐƯỢC THIẾT LẬP API KEY\n\n` +
                    `Để thực hiện "${contextName}", hệ thống cần kết nối với dịch vụ AI.\n` +
                    `Vui lòng liên hệ Quản trị viên (Chính chủ) để cấu hình API Key tại phần Cài Đặt Hệ Thống.`
                );
            } else {
                const proceed = confirm(
                    `⚠️ CHƯA CẤU HÌNH API KEY CHO HỆ THỐNG\n\n` +
                    `Bạn đang yêu cầu thực hiện "${contextName}" nhưng chưa cấu hình API Key.\n\n` +
                    `Nhấn "OK" để MỞ NGAY PHẦN CÀI ĐẶT và thiết lập API Key (chỉ cần nhập 1 lần, tự động áp dụng cho tất cả các công cụ).\n` +
                    `Nhấn "Cancel" để quay lại.`
                );
                if (proceed) {
                    this.openSettings();
                }
            }
        }

        /**
         * Cảnh báo khi Khách hết hạn mức phiên làm việc
         */
        showGuestLimitExceededModal() {
            alert(
                `⚠️ ĐÃ HẾT HẠN MỨC AI TRONG PHIÊN LÀM VIỆC CỦA KHÁCH\n\n` +
                `Bạn đã sử dụng hết ${GUEST_MAX_CALLS_PER_SESSION}/${GUEST_MAX_CALLS_PER_SESSION} lượt gọi AI miễn phí trong phiên làm việc này.\n\n` +
                `Vui lòng liên hệ Quản trị viên (Chính chủ) hoặc mở tab mới/quay lại sau để tiếp tục sử dụng!`
            );
        }

        /**
         * Mở Modal Quản trị và chuyển thẳng tới Tab Cấu Hình AI
         */
        openSettings() {
            if (this.isGuest()) {
                alert("Mục Cài Đặt API Key chỉ dành riêng cho Quản trị viên (Chính chủ).");
                return;
            }
            if (typeof window.openSecurityModal === "function") {
                window.openSecurityModal();
            } else {
                const modal = document.getElementById("security-settings-modal");
                if (modal) modal.classList.remove("hidden");
            }
            if (typeof window.switchSecTab === "function") {
                window.switchSecTab("ai");
            }
        }

        /**
         * Đăng ký và hiển thị Badge trạng thái AI tại bất kỳ Tab/Công cụ nào
         * @param {string|HTMLElement} container
         * @param {Object} options
         */
        renderBadge(container, { compact = false, showButton = true } = {}) {
            const el = typeof container === "string" ? document.getElementById(container) : container;
            if (!el) return;

            this._registeredBadgeContainers.add({
                el,
                options: { compact, showButton }
            });

            this._renderSingleBadge(el, { compact, showButton });
        }

        /**
         * Vẽ giao diện Badge trạng thái
         */
        _renderSingleBadge(el, { compact = false, showButton = true } = {}) {
            const isG = this.isGuest();
            const hasK = this.hasKey();
            const model = this.getModel();
            const provider = this.getProvider();
            const providerLabel = provider === "deepseek" ? "DeepSeek" : (provider === "openai" ? "OpenAI" : "AI");
            const quota = this.getGuestUsage();

            if (hasK) {
                // Trạng thái: Đã sẵn sàng
                let guestBadgeHtml = "";
                if (isG) {
                    guestBadgeHtml = `<span style="font-size:11px; padding:2px 7px; border-radius:10px; background:#eff6ff; color:#1e40af; border:1px solid #bfdbfe; font-weight:600;">Lượt gọi: ${quota.remaining}/${quota.max}</span>`;
                }

                let adminBtnHtml = "";
                if (!isG && showButton) {
                    adminBtnHtml = `
                        <button type="button" onclick="LuvAIService.openSettings()" title="Thay đổi Model hoặc Key trong Cài đặt Quản trị" style="background:#fff; border:1px solid #cbd5e1; border-radius:6px; padding:3px 9px; font-size:11.5px; font-weight:600; color:#334155; cursor:pointer; display:inline-flex; align-items:center; gap:4px; box-shadow:0 1px 2px rgba(0,0,0,0.05); transition:all 0.15s ease;">
                            <span>⚙️</span> Cài đặt
                        </button>
                    `;
                }

                el.innerHTML = `
                    <div style="display:inline-flex; align-items:center; gap:8px; padding:4px 10px; background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; font-size:12px; color:#166534;">
                        <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#22c55e; box-shadow:0 0 0 2px rgba(34,197,94,0.2);"></span>
                        <span style="font-weight:700;">AI Sẵn Sàng</span>
                        <span style="color:#64748b; font-weight:400;">(${providerLabel} · ${model})</span>
                        ${guestBadgeHtml}
                        ${adminBtnHtml}
                    </div>
                `;
            } else {
                // Trạng thái: Chưa cấu hình key
                let actionBtnHtml = "";
                if (!isG) {
                    actionBtnHtml = `
                        <button type="button" onclick="LuvAIService.openSettings()" style="background:#2563eb; color:#fff; border:none; border-radius:6px; padding:3px 10px; font-size:11.5px; font-weight:700; cursor:pointer; display:inline-flex; align-items:center; gap:4px; box-shadow:0 1px 2px rgba(0,0,0,0.1);">
                            <span>⚙️</span> Cấu hình ngay
                        </button>
                    `;
                } else {
                    actionBtnHtml = `<span style="font-size:11px; color:#92400e;">(Liên hệ Quản trị viên)</span>`;
                }

                el.innerHTML = `
                    <div style="display:inline-flex; align-items:center; gap:8px; padding:4px 10px; background:#fffbeb; border:1px solid #fde68a; border-radius:8px; font-size:12px; color:#92400e;">
                        <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#f59e0b; box-shadow:0 0 0 2px rgba(245,158,11,0.2);"></span>
                        <span style="font-weight:700;">Chưa cấu hình AI API Key</span>
                        ${actionBtnHtml}
                    </div>
                `;
            }
        }

        /**
         * Cập nhật lại toàn bộ các Badge trạng thái đã đăng ký
         */
        refreshAllBadges() {
            this._registeredBadgeContainers.forEach(({ el, options }) => {
                if (document.body.contains(el)) {
                    this._renderSingleBadge(el, options);
                }
            });

            // Cập nhật badge trong modal quản trị (#global-deepseek-badge) nếu có
            const globalBadge = document.getElementById("global-deepseek-badge");
            if (globalBadge) {
                if (this.hasKey()) {
                    globalBadge.style.background = "#ecfdf5";
                    globalBadge.style.color = "#065f46";
                    globalBadge.style.borderColor = "#a7f3d0";
                    globalBadge.innerHTML = `🟢 Đã kết nối (${this.getModel()})`;
                } else {
                    globalBadge.style.background = "#fef2f2";
                    globalBadge.style.color = "#991b1b";
                    globalBadge.style.borderColor = "#fecaca";
                    globalBadge.innerHTML = "🔴 Chưa cấu hình";
                }
            }

            // Đồng bộ trạng thái trên Tab MSDS (#msds-ai-key-text)
            const msdsText = document.getElementById("msds-ai-key-text");
            if (msdsText) {
                if (this.hasKey()) {
                    msdsText.innerHTML = `<span style="color:#059669; font-weight:600;">✓ DeepSeek AI Sẵn Sàng (${this.getModel()})</span>`;
                } else {
                    msdsText.innerHTML = `<span style="color:#d97706; font-weight:600;">⚠️ Chưa có DeepSeek Key (Dùng Cục Bộ)</span>`;
                }
            }
        }

        /**
         * Đồng bộ các ô input DOM legacy (giữ tương thích 100% với các test suite hiện hữu)
         */
        _syncLegacyInputFields(cleanKey) {
            const isG = this.isGuest();
            const effectiveVal = isG ? "••••••••••••••••" : cleanKey;

            const legacyIds = ["opt-deepseek-key", "opt-trans-key", "ai-deepseek-key", "ai-sum-key", "global-deepseek-key-input"];
            legacyIds.forEach(id => {
                const input = document.getElementById(id);
                if (input) {
                    input.value = effectiveVal;
                    if (isG) {
                        input.setAttribute("readonly", "true");
                        input.setAttribute("disabled", "true");
                        input.setAttribute("type", "password");
                    }
                }
            });
        }
    }

    // Đăng ký instance toàn cục duy nhất
    window.LuvAIService = new LuvAIServiceManager();

    // Tự động khởi tạo sau khi DOM sẵn sàng
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => {
            window.LuvAIService.init();
        });
    } else {
        window.LuvAIService.init();
    }

})(window);
