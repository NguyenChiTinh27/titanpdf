/**
 * static/hse_layout.js — Controller & Lifecycle Manager for Tool 33 (HSE Safety Layout Planner PRO)
 * Sắp xếp mặt bằng an toàn PCCC, tuyến thoát hiểm và phân vùng nguy hại.
 * Tích hợp độc quyền làm Công Cụ Thứ 33 trong bộ TitanPDF.
 */

(function (window, document) {
    "use strict";

    // Internal Module State
    let isInitialized = false;
    let resizeObserver = null;
    let resizeRafId = null;
    let autoSaveTimer = null;

    const LayoutController = {
        state: null,
        history: [],
        future: [],
        activeModal: null,
        currentMode: "select", // "select" | "pan" | "route" | "zone"
        activeTool: null,      // e.g. "ext_abc_8", "eyewash" when placing equipment
        selectedObjectId: null,
        selectedType: null,    // "marker" | "route" | "zone"
        currentZoom: 1.0,
        panOffset: { x: 0, y: 0 },
        canvasEngine: null,

        // Drawing Draft States
        routeDraft: [],
        routeModeType: "primary", // "primary" | "secondary" | "fireaccess"
        zoneDraft: [],
        draggingMarker: null,
        draggingVertex: null,

        get viewportEngine() {
            return this.canvasEngine ? this.canvasEngine.viewport : null;
        },

        currentPlanData: function () {
            if (!this.state || !this.state.plans) return null;
            const key = this.state.currentPlan || "A";
            return this.state.plans[key] || null;
        },

        markerArray: function () {
            const p = this.currentPlanData();
            return p ? (p.markers = p.markers || []) : [];
        },

        routeArray: function () {
            const p = this.currentPlanData();
            return p ? (p.routes = p.routes || []) : [];
        },

        zoneArray: function () {
            const p = this.currentPlanData();
            return p ? (p.zones = p.zones || []) : [];
        },

        // =========================================================================
        // 1. INITIALIZATION & RESUME LIFECYCLE
        // =========================================================================
        init: function () {
            if (isInitialized) {
                this.resume();
                return;
            }

            try {
                // A. State Hydration from LocalStorage
                const saved = localStorage.getItem("luv_hse_layout_project");
                if (saved) {
                    try {
                        this.state = JSON.parse(saved);
                        this.ensureStateShape();
                    } catch (e) {
                        console.warn("[HSE Layout] Corrupted project in localStorage, initializing default template.");
                        this.state = this.createDefaultState();
                    }
                } else {
                    this.state = this.createDefaultState();
                }

                // B. Populate Canvas Engine
                if (window.HseLayoutCanvas) {
                    this.canvasEngine = new window.HseLayoutCanvas(this);
                    this.canvasEngine.init();
                }

                // C. Render Palette, UI & Bind Events
                this.renderPalette("all");
                this.bindUIEvents();
                this.bindStageEvents();
                this.bindGlobalShortcuts();
                this.setupResizeMonitoring();

                // D. Theme Synchronization
                const currentTheme = document.documentElement.getAttribute("data-theme") || localStorage.getItem("luv_theme") || "clean";
                this.syncTheme(currentTheme);

                // E. Render Content
                this.renderAll();
                this.fitToScreen();

                isInitialized = true;
                console.log("[HSE Layout] Initialized successfully as Tool 33.");
            } catch (err) {
                console.error("[HSE Layout] Initialization error:", err);
            }
        },

        resume: function () {
            this.setupResizeMonitoring();
            this.bindGlobalShortcuts();
            const currentTheme = document.documentElement.getAttribute("data-theme") || localStorage.getItem("luv_theme") || "clean";
            this.syncTheme(currentTheme);
            if (this.canvasEngine) {
                this.canvasEngine.switchPlan(this.state.currentPlan);
                this.canvasEngine.fitToScreen();
            } else {
                this.fitToScreen();
            }
            this.renderAll();
            console.log("[HSE Layout] Resumed.");
        },

        destroy: function () {
            this.saveToStorage();
            if (autoSaveTimer) {
                clearTimeout(autoSaveTimer);
                autoSaveTimer = null;
            }
            if (resizeRafId) {
                cancelAnimationFrame(resizeRafId);
                resizeRafId = null;
            }
            if (resizeObserver) {
                resizeObserver.disconnect();
                resizeObserver = null;
            }
            window.removeEventListener("keydown", handleLayoutKeyDown);
            window.removeEventListener("resize", handleLayoutResize);

            this.closeAllModals();
            this.deselectObject();
            this.currentMode = "select";
            this.activeTool = null;

            if (this.canvasEngine) {
                this.canvasEngine.destroy();
                this.canvasEngine = null;
            }
            isInitialized = false;
            console.log("[HSE Layout] Teardown completed cleanly.");
        },

        // =========================================================================
        // 2. STATE PERSISTENCE & HISTORY ENGINE (UNDO / REDO)
        // =========================================================================
        createDefaultState: function () {
            const bp = window.HSE_FACTORY_BLUEPRINTS || {};
            const sp = window.HSE_SAMPLE_PLANS || {};

            return {
                version: "8.5",
                projectName: "Sơ đồ Mặt bằng An toàn PCCC & Thoát hiểm",
                currentPlan: "A",
                settings: {
                    snap: true,
                    gridSize: 1.0,
                    showRuler: true,
                    showRadius: true,
                    showArrows: true,
                    flowAnimation: true,
                    opacity: 1.0
                },
                titleBlock: {
                    companyName: "ZHAN CHEN (VIETNAM) CO., LTD.",
                    plantName: "Nhà Máy Bình Dương - Xưởng Sản Xuất A",
                    drawingNo: "HSE-DWG-2026-001",
                    designer: "Nguyễn Chí Tình",
                    checker: "Trưởng Phòng HSE",
                    date: new Date().toLocaleDateString("vi-VN"),
                    scale: "1:200"
                },
                plans: {
                    A: {
                        id: "A",
                        name: "Xưởng Sản Xuất A (60m × 72.1m)",
                        building: { width: 60, height: 72.1, grid: 1 },
                        backgroundImage: bp.A || null,
                        markers: sp.A ? JSON.parse(JSON.stringify(sp.A.markers)) : [],
                        routes: sp.A ? JSON.parse(JSON.stringify(sp.A.routes)) : [],
                        zones: sp.A ? JSON.parse(JSON.stringify(sp.A.zones)) : []
                    },
                    C: {
                        id: "C",
                        name: "Xưởng Sản Xuất C (60m × 54m)",
                        building: { width: 60, height: 54, grid: 1 },
                        backgroundImage: bp.C || null,
                        markers: sp.C ? JSON.parse(JSON.stringify(sp.C.markers)) : [],
                        routes: sp.C ? JSON.parse(JSON.stringify(sp.C.routes)) : [],
                        zones: sp.C ? JSON.parse(JSON.stringify(sp.C.zones)) : []
                    },
                    custom: {
                        id: "custom",
                        name: "Bản Vẽ Mặt Bằng Tùy Chỉnh",
                        building: { width: 50, height: 50, grid: 1 },
                        backgroundImage: null,
                        markers: [],
                        routes: [],
                        zones: []
                    }
                }
            };
        },

        ensureStateShape: function () {
            if (!this.state) this.state = this.createDefaultState();
            this.state.settings = Object.assign({
                snap: true,
                gridSize: 1.0,
                showRuler: true,
                showRadius: true,
                showArrows: true,
                flowAnimation: true,
                opacity: 1.0
            }, this.state.settings || {});

            const bp = window.HSE_FACTORY_BLUEPRINTS || {};
            if (this.state.plans) {
                if (this.state.plans.A && !this.state.plans.A.backgroundImage && bp.A) {
                    this.state.plans.A.backgroundImage = bp.A;
                }
                if (this.state.plans.C && !this.state.plans.C.backgroundImage && bp.C) {
                    this.state.plans.C.backgroundImage = bp.C;
                }
            }
        },

        saveToStorage: function () {
            if (!this.state) return;
            try {
                // To avoid QuotaExceededError in localStorage, strip heavy base64 backgrounds
                const copy = JSON.parse(JSON.stringify(this.state));
                if (copy.plans) {
                    if (copy.plans.A) copy.plans.A.backgroundImage = null;
                    if (copy.plans.C) copy.plans.C.backgroundImage = null;
                }
                localStorage.setItem("luv_hse_layout_project", JSON.stringify(copy));
            } catch (err) {
                console.warn("[HSE Layout] LocalStorage save warning:", err);
            }
        },

        pushHistory: function () {
            if (!this.state) return;
            try {
                // Copy without heavy backgrounds to keep stack fast
                const copy = JSON.parse(JSON.stringify(this.state));
                if (copy.plans) {
                    if (copy.plans.A) copy.plans.A.backgroundImage = null;
                    if (copy.plans.C) copy.plans.C.backgroundImage = null;
                }
                this.history.push(JSON.stringify(copy));
                if (this.history.length > 50) this.history.shift();
                this.future = [];
            } catch (e) {
                console.warn("[HSE Layout] Push history failed:", e);
            }
        },

        undo: function () {
            if (!this.history.length) return;
            const currentStr = JSON.stringify(this.state);
            this.future.push(currentStr);
            const prev = JSON.parse(this.history.pop());
            const bp = window.HSE_FACTORY_BLUEPRINTS || {};
            if (prev.plans) {
                if (prev.plans.A && !prev.plans.A.backgroundImage) prev.plans.A.backgroundImage = bp.A;
                if (prev.plans.C && !prev.plans.C.backgroundImage) prev.plans.C.backgroundImage = bp.C;
            }
            this.state = prev;
            this.deselectObject();
            this.renderAll();
            this.showToast("Đã hoàn tác (Undo)");
        },

        redo: function () {
            if (!this.future.length) return;
            const currentStr = JSON.stringify(this.state);
            this.history.push(currentStr);
            const next = JSON.parse(this.future.pop());
            const bp = window.HSE_FACTORY_BLUEPRINTS || {};
            if (next.plans) {
                if (next.plans.A && !next.plans.A.backgroundImage) next.plans.A.backgroundImage = bp.A;
                if (next.plans.C && !next.plans.C.backgroundImage) next.plans.C.backgroundImage = bp.C;
            }
            this.state = next;
            this.deselectObject();
            this.renderAll();
            this.showToast("Đã làm lại (Redo)");
        },

        // =========================================================================
        // 3. PALETTE CATALOG & SEARCH ENGINE (41 CANONICAL SVG SYMBOLS)
        // =========================================================================
        renderPalette: function (activeCategory = "all", filterText = "") {
            const grid = document.getElementById("layout-symbols-grid");
            if (!grid) return;

            const types = window.HSE_TYPES || {};
            const icons = window.HSE_SVG_ICONS || {};
            const q = (filterText || "").trim().toLowerCase();

            grid.innerHTML = "";
            let count = 0;

            for (const [key, t] of Object.entries(types)) {
                // Category Filter
                if (activeCategory === "pccc") {
                    if (t.group !== "extinguisher" && t.group !== "fireequipment") continue;
                } else if (activeCategory === "safety") {
                    if (t.group !== "safety") continue;
                } else if (activeCategory === "alarm") {
                    if (!["callpoint", "firebell", "smoke", "heat", "fapanel", "exitlight", "emlight", "exitdoor"].includes(key)) continue;
                }

                // Text Search Filter
                if (q) {
                    const matchName = (t.name || "").toLowerCase().includes(q);
                    const matchEn = (t.nameEn || "").toLowerCase().includes(q);
                    const matchZh = (t.nameZh || "").toLowerCase().includes(q);
                    const matchPrefix = (t.prefix || "").toLowerCase().includes(q);
                    const matchHint = (t.hint || "").toLowerCase().includes(q);
                    if (!matchName && !matchEn && !matchZh && !matchPrefix && !matchHint) continue;
                }

                count++;
                const itemEl = document.createElement("div");
                itemEl.className = "layout-symbol-item" + (this.activeTool === key ? " active-tool" : "");
                itemEl.setAttribute("data-type", key);
                itemEl.setAttribute("title", `${t.name} (${t.prefix || ''})\n${t.hint || ''}`);
                itemEl.setAttribute("draggable", "true");

                const iconSvg = icons[key] || window.getHseIconSvg(key);

                itemEl.innerHTML = `
                    <div class="layout-symbol-svg-wrapper">${iconSvg}</div>
                    <span class="layout-symbol-label">${t.name}</span>
                `;

                // Click to activate tool for placement
                itemEl.onclick = (e) => {
                    e.stopPropagation();
                    if (this.activeTool === key) {
                        this.deactivateTool();
                    } else {
                        this.activateTool(key);
                    }
                };

                // Drag & Drop onto canvas stage
                itemEl.ondragstart = (e) => {
                    e.dataTransfer.setData("text/plain", key);
                    e.dataTransfer.effectAllowed = "copy";
                };

                grid.appendChild(itemEl);
            }

            if (count === 0) {
                grid.innerHTML = `
                    <div style="grid-column: span 2; padding: 24px 8px; text-align: center; color: var(--layout-text-muted); font-size: 12px;">
                        Không tìm thấy ký hiệu phù hợp với từ khóa "${q}".
                    </div>
                `;
            }
        },

        activateTool: function (type) {
            this.activeTool = type;
            this.currentMode = "select";
            this.deselectObject();
            document.querySelectorAll(".layout-symbol-item").forEach(el => {
                el.classList.toggle("active-tool", el.getAttribute("data-type") === type);
            });
            const t = (window.HSE_TYPES && window.HSE_TYPES[type]) || {};
            this.showToast(`Đã chọn: ${t.name || type} — Nhấp vào mặt bằng để bố trí`);
        },

        deactivateTool: function () {
            this.activeTool = null;
            document.querySelectorAll(".layout-symbol-item").forEach(el => el.classList.remove("active-tool"));
        },

        // =========================================================================
        // 4. DRAWING & RENDERING ENGINE (MARKERS, ROUTES, ZONES & RADIUS)
        // =========================================================================
        renderAll: function () {
            this.renderMarkers();
            this.renderSVGLayers();
            this.renderActiveDraw();
            this.renderInspector();
            if (this.canvasEngine) {
                this.canvasEngine.renderBackground(true);
                this.canvasEngine.minimap.requestRender();
                this.canvasEngine.rulers.requestRender();
            }
        },

        renderMarkers: function () {
            const group = document.getElementById("layout-markers-group");
            const radiusGroup = document.getElementById("layout-radius-group");
            if (!group) return;

            group.innerHTML = "";
            if (radiusGroup) radiusGroup.innerHTML = "";

            const markers = this.markerArray();
            const types = window.HSE_TYPES || {};
            const icons = window.HSE_SVG_ICONS || {};
            const showRadius = this.state && this.state.settings && this.state.settings.showRadius;

            markers.forEach((m, idx) => {
                const t = types[m.type] || types.ext_abc_8 || {};
                const cx = m.x * 1000;
                const cy = m.y * 1000;
                const size = 32;
                const isSelected = this.selectedType === "marker" && this.selectedObjectId === m.id;

                // A. Render Protection Radius Circle (TCVN 15m / 25m / 75m)
                if (showRadius && radiusGroup && (m.radius || t.defaultRadius)) {
                    const radiusMeters = m.radius || t.defaultRadius || 15;
                    // Scale from building dimensions (e.g. 60m width -> 1000 svg units => ~16.66 units/meter)
                    const p = this.currentPlanData();
                    const bWidth = (p && p.building && p.building.width) || 60;
                    const rSvg = (radiusMeters / bWidth) * 1000;

                    const circleEl = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                    circleEl.setAttribute("class", "marker-radius-circle");
                    circleEl.setAttribute("cx", cx);
                    circleEl.setAttribute("cy", cy);
                    circleEl.setAttribute("r", rSvg);
                    circleEl.setAttribute("data-marker-id", m.id);
                    radiusGroup.appendChild(circleEl);
                }

                // B. Render Marker Group
                const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
                g.setAttribute("class", "layout-marker-g" + (isSelected ? " selected" : ""));
                g.setAttribute("data-marker-id", m.id);
                g.setAttribute("transform", `translate(${cx}, ${cy})`);
                g.setAttribute("filter", "url(#marker-drop-shadow)");

                // Background pin badge
                const bgRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
                bgRect.setAttribute("x", -size / 2);
                bgRect.setAttribute("y", -size / 2);
                bgRect.setAttribute("width", size);
                bgRect.setAttribute("height", size);
                bgRect.setAttribute("rx", "7");
                bgRect.setAttribute("fill", isSelected ? "#2563eb" : (t.color || "#ef4444"));
                bgRect.setAttribute("stroke", "#ffffff");
                bgRect.setAttribute("stroke-width", "2");
                bgRect.setAttribute("class", isSelected ? "marker-selection-ring" : "");
                g.appendChild(bgRect);

                // Nested SVG Icon
                const svgContent = icons[m.type] || window.getHseIconSvg(m.type);
                const iconContainer = document.createElementNS("http://www.w3.org/2000/svg", "g");
                iconContainer.setAttribute("transform", `translate(${-size / 2 + 3}, ${-size / 2 + 3}) scale(${ (size - 6) / 100 })`);
                iconContainer.innerHTML = svgContent;
                g.appendChild(iconContainer);

                // Text Badge below icon
                const labelText = document.createElementNS("http://www.w3.org/2000/svg", "text");
                labelText.setAttribute("class", "marker-label-text");
                labelText.setAttribute("x", "0");
                labelText.setAttribute("y", size / 2 + 12);
                labelText.textContent = m.label || `EQ-${idx + 1}`;
                g.appendChild(labelText);

                // Pointer Events for Dragging & Selection
                g.onpointerdown = (e) => this.handleMarkerPointerDown(e, m.id);

                group.appendChild(g);
            });
        },

        renderSVGLayers: function () {
            const zonesGroup = document.getElementById("layout-zones-group");
            const routesGroup = document.getElementById("layout-routes-group");
            if (!zonesGroup || !routesGroup) return;

            zonesGroup.innerHTML = "";
            routesGroup.innerHTML = "";

            const zones = this.zoneArray();
            const routes = this.routeArray();
            const zonePresets = window.HSE_ZONE_PRESETS || {};
            const routeTypes = window.HSE_ROUTE_TYPES || {};
            const isAnimated = this.state && this.state.settings && this.state.settings.flowAnimation;

            // 1. Render Hazard & Safety Zones
            zones.forEach(z => {
                if (!z.points || z.points.length < 3) return;
                const ptsStr = z.points.map(p => `${p.x * 1000},${p.y * 1000}`).join(" ");
                const preset = zonePresets[z.preset] || zonePresets.hazard_high || {};
                const isSelected = this.selectedType === "zone" && this.selectedObjectId === z.id;

                const poly = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
                poly.setAttribute("class", "zone-polygon" + (isSelected ? " selected" : ""));
                poly.setAttribute("points", ptsStr);
                poly.setAttribute("fill", preset.fill || "rgba(239, 68, 68, 0.22)");
                poly.setAttribute("stroke", preset.border || "#dc2626");
                poly.setAttribute("stroke-width", isSelected ? "3.5" : "2");
                poly.setAttribute("data-zone-id", z.id);

                poly.onclick = (e) => {
                    e.stopPropagation();
                    this.selectObject("zone", z.id);
                };

                zonesGroup.appendChild(poly);
            });

            // 2. Render Evacuation Polyline Routes
            routes.forEach(r => {
                if (!r.points || r.points.length < 2) return;
                const ptsStr = r.points.map(p => `${p.x * 1000},${p.y * 1000}`).join(" ");
                const rt = routeTypes[r.type] || routeTypes.primary || {};
                const isSelected = this.selectedType === "route" && this.selectedObjectId === r.id;

                const arrowId = r.type === "secondary" ? "arrowSecondary" : (r.type === "fireaccess" ? "arrowFireAccess" : "arrowPrimary");

                // White outline underneath for contrast
                const outline = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
                outline.setAttribute("class", "route-poly-outline");
                outline.setAttribute("points", ptsStr);
                outline.setAttribute("stroke", rt.outline || "#ffffff");
                outline.setAttribute("stroke-width", String((rt.width || 6) + 4));
                routesGroup.appendChild(outline);

                // Main directional line
                const mainLine = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
                mainLine.setAttribute("class", "route-poly-main" + (isAnimated ? " route-poly-animated" : ""));
                mainLine.setAttribute("points", ptsStr);
                mainLine.setAttribute("stroke", rt.color || "#16a34a");
                mainLine.setAttribute("stroke-width", String(rt.width || 6));
                mainLine.setAttribute("marker-end", `url(#${arrowId})`);
                routesGroup.appendChild(mainLine);

                // Invisible wide hit target for easy clicking
                const hitTarget = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
                hitTarget.setAttribute("class", "route-hit-target" + (isSelected ? " selected" : ""));
                hitTarget.setAttribute("points", ptsStr);
                hitTarget.onclick = (e) => {
                    e.stopPropagation();
                    this.selectObject("route", r.id);
                };
                routesGroup.appendChild(hitTarget);

                // If selected, render draggable vertex handles
                if (isSelected) {
                    r.points.forEach((pt, vIdx) => {
                        const handle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                        handle.setAttribute("class", "route-vertex-handle");
                        handle.setAttribute("cx", pt.x * 1000);
                        handle.setAttribute("cy", pt.y * 1000);
                        handle.setAttribute("r", "7");
                        handle.setAttribute("data-route-id", r.id);
                        handle.setAttribute("data-vertex-index", vIdx);

                        handle.onpointerdown = (e) => this.handleVertexPointerDown(e, r.id, vIdx);
                        routesGroup.appendChild(handle);
                    });
                }
            });
        },

        renderActiveDraw: function () {
            const activeGroup = document.getElementById("layout-active-draw-group");
            if (!activeGroup) return;
            activeGroup.innerHTML = "";

            // Active Route Draft
            if (this.currentMode === "route" && this.routeDraft.length > 0) {
                const ptsStr = this.routeDraft.map(p => `${p.x * 1000},${p.y * 1000}`).join(" ");
                const poly = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
                poly.setAttribute("class", "route-poly-main route-poly-animated");
                poly.setAttribute("points", ptsStr);
                poly.setAttribute("stroke", "#16a34a");
                poly.setAttribute("stroke-width", "4");
                poly.setAttribute("stroke-dasharray", "6 4");
                activeGroup.appendChild(poly);

                this.routeDraft.forEach(pt => {
                    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                    dot.setAttribute("cx", pt.x * 1000);
                    dot.setAttribute("cy", pt.y * 1000);
                    dot.setAttribute("r", "5");
                    dot.setAttribute("fill", "#16a34a");
                    dot.setAttribute("stroke", "#ffffff");
                    dot.setAttribute("stroke-width", "2");
                    activeGroup.appendChild(dot);
                });
            }

            // Active Zone Draft
            if (this.currentMode === "zone" && this.zoneDraft.length > 0) {
                const ptsStr = this.zoneDraft.map(p => `${p.x * 1000},${p.y * 1000}`).join(" ");
                const poly = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
                poly.setAttribute("points", ptsStr);
                poly.setAttribute("fill", "rgba(239, 68, 68, 0.25)");
                poly.setAttribute("stroke", "#dc2626");
                poly.setAttribute("stroke-width", "2");
                poly.setAttribute("stroke-dasharray", "6 4");
                activeGroup.appendChild(poly);

                this.zoneDraft.forEach(pt => {
                    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                    dot.setAttribute("cx", pt.x * 1000);
                    dot.setAttribute("cy", pt.y * 1000);
                    dot.setAttribute("r", "5");
                    dot.setAttribute("fill", "#dc2626");
                    dot.setAttribute("stroke", "#ffffff");
                    dot.setAttribute("stroke-width", "2");
                    activeGroup.appendChild(dot);
                });
            }
        },

        // =========================================================================
        // 5. STAGE EVENT DISPATCHING (POINTER, CLICK, DRAG, SNAP)
        // =========================================================================
        bindStageEvents: function () {
            const svgStage = document.getElementById("layout-svg-stage");
            const stageWrapper = document.getElementById("layout-stage-wrapper");
            if (!svgStage || !stageWrapper) return;

            // Handle stage clicks (Placing markers, Route vertices, Zone corners)
            svgStage.addEventListener("click", (e) => {
                if (this.draggingMarker || this.draggingVertex) return;

                // Normalize click position
                const norm = this.getNormalizedCoords(e.clientX, e.clientY);

                // A. Placing new marker from active tool
                if (this.activeTool) {
                    this.placeMarkerAt(norm.x, norm.y, this.activeTool);
                    if (!e.shiftKey) this.deactivateTool();
                    return;
                }

                // B. Drawing Evacuation Route
                if (this.currentMode === "route") {
                    this.routeDraft.push({ x: norm.x, y: norm.y });
                    this.renderActiveDraw();
                    return;
                }

                // C. Drawing Hazard Zone
                if (this.currentMode === "zone") {
                    this.zoneDraft.push({ x: norm.x, y: norm.y });
                    this.renderActiveDraw();
                    return;
                }

                // D. Clicked on empty space -> Deselect
                if (e.target === svgStage || e.target.id === "layout-canvas-transform") {
                    this.deselectObject();
                }
            });

            // Double Click to finish route or zone drawing
            svgStage.addEventListener("dblclick", (e) => {
                e.preventDefault();
                if (this.currentMode === "route") {
                    this.finishRoute();
                } else if (this.currentMode === "zone") {
                    this.finishZone();
                }
            });

            // HTML5 Drag & Drop onto Stage
            stageWrapper.addEventListener("dragover", (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = "copy";
            });

            stageWrapper.addEventListener("drop", (e) => {
                e.preventDefault();
                const type = e.dataTransfer.getData("text/plain");
                if (type && window.HSE_TYPES && window.HSE_TYPES[type]) {
                    const norm = this.getNormalizedCoords(e.clientX, e.clientY);
                    this.placeMarkerAt(norm.x, norm.y, type);
                }
            });
        },

        getNormalizedCoords: function (clientX, clientY) {
            if (this.viewportEngine) {
                const snapEnabled = this.state && this.state.settings && this.state.settings.snap;
                return this.viewportEngine.screenToNorm(clientX, clientY, { snap: snapEnabled, step: 0.01 });
            }
            const transform = document.getElementById("layout-canvas-transform");
            if (!transform) return { x: 0.5, y: 0.5 };
            const rect = transform.getBoundingClientRect();
            let nx = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
            let ny = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height));
            if (this.state && this.state.settings && this.state.settings.snap) {
                nx = Math.round(nx * 100) / 100;
                ny = Math.round(ny * 100) / 100;
            }
            return { x: Number(nx.toFixed(4)), y: Number(ny.toFixed(4)) };
        },

        placeMarkerAt: function (x, y, type) {
            this.pushHistory();
            const types = window.HSE_TYPES || {};
            const t = types[type] || {};
            const markers = this.markerArray();

            const newId = "m_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 6);
            const label = this.nextLabel(type);

            const marker = {
                id: newId,
                type: type,
                label: label,
                x: x,
                y: y,
                radius: t.defaultRadius || 15,
                dept: "Khu vực sản xuất",
                note: "Đạt tiêu chuẩn an toàn PCCC",
                status: "good",
                nextCheck: "2026-12-31"
            };

            markers.push(marker);
            this.selectObject("marker", newId);
            this.renderAll();
            this.saveToStorage();
            this.showToast(`Đã thêm thiết bị: ${label} (${t.name || type})`);
        },

        nextLabel: function (type) {
            const types = window.HSE_TYPES || {};
            const t = types[type] || {};
            const prefix = t.prefix || "EQ";
            const markers = this.markerArray();
            let maxNum = 0;
            const re = new RegExp(`^${prefix}[-_]?(\\d+)$`, "i");

            markers.forEach(m => {
                const match = String(m.label || "").match(re);
                if (match) {
                    const num = parseInt(match[1], 10);
                    if (num > maxNum) maxNum = num;
                }
            });

            const nextNum = maxNum + 1;
            return `${prefix}-${nextNum < 10 ? '0' : ''}${nextNum}`;
        },

        // Marker Drag Handling
        handleMarkerPointerDown: function (e, markerId) {
            e.stopPropagation();
            if (this.currentMode !== "select") return;

            this.selectObject("marker", markerId);
            this.pushHistory();

            this.draggingMarker = {
                id: markerId,
                pointerId: e.pointerId
            };

            if (e.currentTarget.setPointerCapture) {
                e.currentTarget.setPointerCapture(e.pointerId);
            }

            const onMove = (moveEvt) => {
                if (!this.draggingMarker || this.draggingMarker.id !== markerId) return;
                const norm = this.getNormalizedCoords(moveEvt.clientX, moveEvt.clientY);
                const m = this.markerArray().find(x => x.id === markerId);
                if (m) {
                    m.x = norm.x;
                    m.y = norm.y;
                    this.renderMarkers();
                    this.updateInspectorCoords(m.x, m.y);
                }
            };

            const onUp = (upEvt) => {
                document.removeEventListener("pointermove", onMove);
                document.removeEventListener("pointerup", onUp);
                this.draggingMarker = null;
                this.saveToStorage();
                this.renderAll();
            };

            document.addEventListener("pointermove", onMove);
            document.addEventListener("pointerup", onUp);
        },

        // Route Vertex Drag Handling
        handleVertexPointerDown: function (e, routeId, vertexIndex) {
            e.stopPropagation();
            this.pushHistory();
            this.draggingVertex = { routeId, vertexIndex };

            const onMove = (moveEvt) => {
                if (!this.draggingVertex) return;
                const norm = this.getNormalizedCoords(moveEvt.clientX, moveEvt.clientY);
                const r = this.routeArray().find(x => x.id === routeId);
                if (r && r.points[vertexIndex]) {
                    r.points[vertexIndex].x = norm.x;
                    r.points[vertexIndex].y = norm.y;
                    this.renderSVGLayers();
                }
            };

            const onUp = () => {
                document.removeEventListener("pointermove", onMove);
                document.removeEventListener("pointerup", onUp);
                this.draggingVertex = null;
                this.saveToStorage();
                this.renderSVGLayers();
            };

            document.addEventListener("pointermove", onMove);
            document.addEventListener("pointerup", onUp);
        },

        // =========================================================================
        // 6. DRAWING ROUTE & ZONE COMPLETION / CANCELLATION
        // =========================================================================
        finishRoute: function () {
            if (this.routeDraft.length < 2) {
                this.showToast("Cần ít nhất 2 điểm để tạo tuyến thoát hiểm.");
                return;
            }
            this.pushHistory();
            const newRoute = {
                id: "r_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 6),
                type: this.routeModeType || "primary",
                label: `Lối thoát hiểm ${this.routeArray().length + 1}`,
                points: [...this.routeDraft],
                note: "Hành lang thông thoáng, không vật cản"
            };

            this.routeArray().push(newRoute);
            this.routeDraft = [];
            this.setMode("select");
            this.selectObject("route", newRoute.id);
            this.renderAll();
            this.saveToStorage();
            this.showToast("Đã tạo đường thoát hiểm.");
        },

        cancelRoute: function () {
            this.routeDraft = [];
            this.renderActiveDraw();
            this.setMode("select");
            this.showToast("Đã hủy vẽ tuyến thoát hiểm.");
        },

        finishZone: function () {
            if (this.zoneDraft.length < 3) {
                this.showToast("Cần ít nhất 3 điểm để khoanh vùng nguy hại.");
                return;
            }
            this.pushHistory();
            const newZone = {
                id: "z_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 6),
                name: `Phân vùng an toàn ${this.zoneArray().length + 1}`,
                preset: "hazard_high",
                points: [...this.zoneDraft],
                note: "Khu vực nguy cơ rủi ro cao"
            };

            this.zoneArray().push(newZone);
            this.zoneDraft = [];
            this.setMode("select");
            this.selectObject("zone", newZone.id);
            this.renderAll();
            this.saveToStorage();
            this.showToast("Đã tạo phân vùng an toàn.");
        },

        cancelZone: function () {
            this.zoneDraft = [];
            this.renderActiveDraw();
            this.setMode("select");
            this.showToast("Đã hủy vẽ phân vùng.");
        },

        cancelDrawing: function () {
            if (this.currentMode === "route") this.cancelRoute();
            else if (this.currentMode === "zone") this.cancelZone();
            else if (this.activeTool) this.deactivateTool();
        },

        // =========================================================================
        // 7. SELECTION & PROPERTY INSPECTOR ENGINE
        // =========================================================================
        selectObject: function (type, id) {
            this.selectedType = type;
            this.selectedObjectId = id;
            this.renderMarkers();
            this.renderSVGLayers();
            this.renderInspector();
        },

        deselectObject: function () {
            this.selectedType = null;
            this.selectedObjectId = null;
            this.renderMarkers();
            this.renderSVGLayers();
            this.renderInspector();
        },

        renderInspector: function () {
            const form = document.getElementById("layout-inspector-form");
            const empty = document.querySelector(".layout-inspector-empty");
            if (!form) return;

            if (!this.selectedObjectId || !this.selectedType) {
                form.classList.add("hidden");
                if (empty) empty.classList.remove("hidden");
                return;
            }

            if (empty) empty.classList.add("hidden");
            form.classList.remove("hidden");

            if (this.selectedType === "marker") {
                const m = this.markerArray().find(x => x.id === this.selectedObjectId);
                if (!m) { this.deselectObject(); return; }
                const types = window.HSE_TYPES || {};

                let typeOpts = "";
                for (const [k, t] of Object.entries(types)) {
                    typeOpts += `<option value="${k}" ${k === m.type ? 'selected' : ''}>${t.name} (${t.prefix || ''})</option>`;
                }

                form.innerHTML = `
                    <div class="layout-form-group">
                        <label>Mã Thiết Bị (ID / Vị Trí)</label>
                        <input type="text" id="inspector-field-label" value="${m.label || ''}" />
                    </div>
                    <div class="layout-form-group">
                        <label>Loại Thiết Bị PCCC / An Toàn</label>
                        <select id="inspector-field-type">${typeOpts}</select>
                    </div>
                    <div class="layout-form-group">
                        <label>Vị Trí Cụ Thể (Phân xưởng/Cột)</label>
                        <input type="text" id="inspector-field-location" value="${m.dept || ''}" placeholder="VD: Cửa số 1, Trục D4..." />
                    </div>
                    <div class="layout-form-group">
                        <label>Bán Kính Bảo Vệ (m)</label>
                        <input type="number" id="inspector-field-radius" value="${m.radius || 15}" min="2" max="100" />
                    </div>
                    <div class="layout-form-group">
                        <label>Tình Trạng Thiết Bị</label>
                        <select id="inspector-field-status">
                            <option value="good" ${m.status === 'good' ? 'selected' : ''}>Hoạt Động Tốt</option>
                            <option value="warning" ${m.status === 'warning' ? 'selected' : ''}>Cần Bảo Dưỡng / Nạp</option>
                            <option value="expired" ${m.status === 'expired' ? 'selected' : ''}>Hết Hạn Kiểm Định</option>
                        </select>
                    </div>
                    <div class="layout-form-group">
                        <label>Ghi Chú Kiểm Định</label>
                        <textarea id="inspector-field-note" rows="2">${m.note || ''}</textarea>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 14px;">
                        <button type="button" class="layout-btn layout-btn-outline" id="inspector-btn-duplicate">📄 Nhân Bản</button>
                        <button type="button" class="layout-btn layout-btn-danger" id="inspector-btn-delete">🗑️ Xóa</button>
                    </div>
                `;

                // Bind Live Change Handlers
                const fLabel = document.getElementById("inspector-field-label");
                const fType = document.getElementById("inspector-field-type");
                const fLoc = document.getElementById("inspector-field-location");
                const fRad = document.getElementById("inspector-field-radius");
                const fStat = document.getElementById("inspector-field-status");
                const fNote = document.getElementById("inspector-field-note");
                const bDup = document.getElementById("inspector-btn-duplicate");
                const bDel = document.getElementById("inspector-btn-delete");

                if (fLabel) fLabel.onchange = (e) => { this.pushHistory(); m.label = e.target.value.trim(); this.renderAll(); this.saveToStorage(); };
                if (fType) fType.onchange = (e) => {
                    this.pushHistory();
                    m.type = e.target.value;
                    m.radius = types[m.type]?.defaultRadius || 15;
                    this.renderAll();
                    this.saveToStorage();
                };
                if (fLoc) fLoc.onchange = (e) => { this.pushHistory(); m.dept = e.target.value.trim(); this.saveToStorage(); };
                if (fRad) fRad.onchange = (e) => { this.pushHistory(); m.radius = parseFloat(e.target.value) || 15; this.renderAll(); this.saveToStorage(); };
                if (fStat) fStat.onchange = (e) => { this.pushHistory(); m.status = e.target.value; this.renderAll(); this.saveToStorage(); };
                if (fNote) fNote.onchange = (e) => { this.pushHistory(); m.note = e.target.value; this.saveToStorage(); };

                if (bDup) bDup.onclick = () => this.duplicateSelected();
                if (bDel) bDel.onclick = () => this.deleteSelected();
            } else if (this.selectedType === "route") {
                const r = this.routeArray().find(x => x.id === this.selectedObjectId);
                if (!r) { this.deselectObject(); return; }

                form.innerHTML = `
                    <div class="layout-form-group">
                        <label>Tên Tuyến Thoát Hiểm</label>
                        <input type="text" id="inspector-route-label" value="${r.label || ''}" />
                    </div>
                    <div class="layout-form-group">
                        <label>Phân Loại Tuyến</label>
                        <select id="inspector-route-type">
                            <option value="primary" ${r.type === 'primary' ? 'selected' : ''}>Tuyến Thoát Hiểm Chính (Màu Xanh)</option>
                            <option value="secondary" ${r.type === 'secondary' ? 'selected' : ''}>Tuyến Thoát Hiểm Phụ (Màu Vàng)</option>
                            <option value="fireaccess" ${r.type === 'fireaccess' ? 'selected' : ''}>Lối Cứu Hỏa & CNCH (Màu Đỏ)</option>
                        </select>
                    </div>
                    <div class="layout-form-group">
                        <label>Ghi Chú Hướng Dẫn</label>
                        <textarea id="inspector-route-note" rows="2">${r.note || ''}</textarea>
                    </div>
                    <div style="margin-top: 14px;">
                        <button type="button" class="layout-btn layout-btn-danger" style="width: 100%;" id="inspector-btn-delete">🗑️ Xóa Tuyến Thoát Hiểm</button>
                    </div>
                `;

                const rLabel = document.getElementById("inspector-route-label");
                const rType = document.getElementById("inspector-route-type");
                const rNote = document.getElementById("inspector-route-note");
                const bDel = document.getElementById("inspector-btn-delete");

                if (rLabel) rLabel.onchange = (e) => { this.pushHistory(); r.label = e.target.value; this.saveToStorage(); };
                if (rType) rType.onchange = (e) => { this.pushHistory(); r.type = e.target.value; this.renderSVGLayers(); this.saveToStorage(); };
                if (rNote) rNote.onchange = (e) => { this.pushHistory(); r.note = e.target.value; this.saveToStorage(); };
                if (bDel) bDel.onclick = () => this.deleteSelected();
            } else if (this.selectedType === "zone") {
                const z = this.zoneArray().find(x => x.id === this.selectedObjectId);
                if (!z) { this.deselectObject(); return; }

                form.innerHTML = `
                    <div class="layout-form-group">
                        <label>Tên Phân Vùng Nguy Hại</label>
                        <input type="text" id="inspector-zone-name" value="${z.name || ''}" />
                    </div>
                    <div class="layout-form-group">
                        <label>Cấp Độ / Nhóm Rủi Ro</label>
                        <select id="inspector-zone-preset">
                            <option value="hazard_high" ${z.preset === 'hazard_high' ? 'selected' : ''}>Khu Vực Nguy Hiểm Cao / Cháy Nổ (Đỏ)</option>
                            <option value="chemical" ${z.preset === 'chemical' ? 'selected' : ''}>Kho Lưu Trữ Hóa Chất (Cam)</option>
                            <option value="keep_clear" ${z.preset === 'keep_clear' ? 'selected' : ''}>Vùng Cấm Vật Cản / Cửa Thoát Nạn (Vàng)</option>
                            <option value="electrical" ${z.preset === 'electrical' ? 'selected' : ''}>Trạm Biến Áp / Phòng Máy Điện (Xanh Lam)</option>
                        </select>
                    </div>
                    <div class="layout-form-group">
                        <label>Quy Chuẩn An Toàn Áp Dụng</label>
                        <textarea id="inspector-zone-note" rows="2">${z.note || ''}</textarea>
                    </div>
                    <div style="margin-top: 14px;">
                        <button type="button" class="layout-btn layout-btn-danger" style="width: 100%;" id="inspector-btn-delete">🗑️ Xóa Phân Vùng</button>
                    </div>
                `;

                const zName = document.getElementById("inspector-zone-name");
                const zPreset = document.getElementById("inspector-zone-preset");
                const zNote = document.getElementById("inspector-zone-note");
                const bDel = document.getElementById("inspector-btn-delete");

                if (zName) zName.onchange = (e) => { this.pushHistory(); z.name = e.target.value; this.saveToStorage(); };
                if (zPreset) zPreset.onchange = (e) => { this.pushHistory(); z.preset = e.target.value; this.renderSVGLayers(); this.saveToStorage(); };
                if (zNote) zNote.onchange = (e) => { this.pushHistory(); z.note = e.target.value; this.saveToStorage(); };
                if (bDel) bDel.onclick = () => this.deleteSelected();
            }
        },

        updateInspectorCoords: function (x, y) {
            // Can display real-time live coordinate badge if needed
        },

        duplicateSelected: function () {
            if (this.selectedType !== "marker" || !this.selectedObjectId) return;
            const markers = this.markerArray();
            const m = markers.find(x => x.id === this.selectedObjectId);
            if (!m) return;

            this.pushHistory();
            const copy = {
                ...m,
                id: "m_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 6),
                label: this.nextLabel(m.type),
                x: Math.min(0.96, m.x + 0.03),
                y: Math.min(0.96, m.y + 0.03)
            };
            markers.push(copy);
            this.selectObject("marker", copy.id);
            this.renderAll();
            this.saveToStorage();
            this.showToast(`Đã nhân bản: ${copy.label}`);
        },

        deleteSelected: function () {
            if (!this.selectedObjectId || !this.selectedType) return;
            this.pushHistory();

            if (this.selectedType === "marker") {
                const markers = this.markerArray();
                const idx = markers.findIndex(x => x.id === this.selectedObjectId);
                if (idx !== -1) markers.splice(idx, 1);
            } else if (this.selectedType === "route") {
                const routes = this.routeArray();
                const idx = routes.findIndex(x => x.id === this.selectedObjectId);
                if (idx !== -1) routes.splice(idx, 1);
            } else if (this.selectedType === "zone") {
                const zones = this.zoneArray();
                const idx = zones.findIndex(x => x.id === this.selectedObjectId);
                if (idx !== -1) zones.splice(idx, 1);
            }

            this.deselectObject();
            this.renderAll();
            this.saveToStorage();
            this.showToast("Đã xóa đối tượng được chọn.");
        },

        // =========================================================================
        // 8. BOM INVENTORY TABLE & EXCEL EXPORTER
        // =========================================================================
        openBomModal: function () {
            const modal = document.getElementById("layout-bom-modal");
            if (!modal) return;
            this.renderBomTable();
            modal.classList.remove("hidden");
        },

        renderBomTable: function () {
            const body = document.getElementById("layout-bom-modal-body");
            if (!body) return;

            const markers = this.markerArray();
            const types = window.HSE_TYPES || {};
            const calc = window.calculateHseExtinguishers(markers);

            if (markers.length === 0) {
                body.innerHTML = `
                    <div style="text-align: center; padding: 48px 16px; color: var(--layout-text-muted);">
                        <p style="font-size: 14px; margin-bottom: 8px;">Chưa có thiết bị an toàn nào được bố trí trên mặt bằng này.</p>
                        <p style="font-size: 12px;">Kéo thả ký hiệu từ bảng công cụ bên trái vào sơ đồ để tự động thống kê BOM.</p>
                    </div>
                `;
                return;
            }

            let rows = "";
            markers.forEach((m, idx) => {
                const t = types[m.type] || {};
                const statLabel = m.status === "good" ? "<span style='color: #10b981; font-weight: 700;'>Hoạt Động Tốt</span>" : (m.status === "warning" ? "<span style='color: #f59e0b; font-weight: 700;'>Cần Bảo Dưỡng</span>" : "<span style='color: #ef4444; font-weight: 700;'>Hết Hạn</span>");

                rows += `
                    <tr>
                        <td>${idx + 1}</td>
                        <td><strong>${m.label || `EQ-${idx+1}`}</strong></td>
                        <td>${t.name || m.type}</td>
                        <td>${t.group === 'extinguisher' ? 'Bình Chữa Cháy' : (t.group === 'fireequipment' ? 'Phương Tiện PCCC' : 'An Toàn / Y Tế')}</td>
                        <td>${m.dept || 'Xưởng sản xuất'}</td>
                        <td>${m.radius || 15}m</td>
                        <td>${statLabel}</td>
                        <td>${m.nextCheck || '2026-12-31'}</td>
                    </tr>
                `;
            });

            body.innerHTML = `
                <div style="background: var(--layout-panel-hover); padding: 12px 16px; border-radius: var(--layout-radius-sm); margin-bottom: 16px; font-size: 12px; line-height: 1.6;">
                    <strong>Tổng Hợp Quy Đổi PCCC (TCVN 3890):</strong> ${calc.points} điểm bố trí · <strong>${calc.totalCylinders} bình</strong><br/>
                    • CO₂ 5kg: <strong>${calc.co2}</strong> bình &nbsp;|&nbsp; • Bột ABC 8kg: <strong>${calc.abc8}</strong> bình &nbsp;|&nbsp; • Xe đẩy ABC 35kg: <strong>${calc.abc35}</strong> xe &nbsp;|&nbsp; • Bọt Foam 9L: <strong>${calc.foam9}</strong> bình
                </div>
                <table class="layout-bom-table">
                    <thead>
                        <tr>
                            <th>STT</th>
                            <th>Mã Vị Trí</th>
                            <th>Loại Thiết Bị</th>
                            <th>Phân Nhóm</th>
                            <th>Vị Trí Lắp Đặt</th>
                            <th>Bán Kính</th>
                            <th>Tình Trạng</th>
                            <th>Hạn Kiểm Định</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
                <div style="margin-top: 16px; display: flex; justify-content: flex-end; gap: 8px;">
                    <button type="button" class="layout-btn layout-btn-primary" onclick="window.HseLayout.exportBomExcel()">📥 Tải Excel (.csv / .xlsx)</button>
                </div>
            `;
        },

        exportBomExcel: function () {
            const markers = this.markerArray();
            const types = window.HSE_TYPES || {};
            if (markers.length === 0) {
                this.showToast("Không có thiết bị nào để xuất BOM.");
                return;
            }

            let csv = "\uFEFFSTT,Mã Vị Trí,Loại Thiết Bị,Phân Nhóm,Vị Trí Lắp Đặt,Bán Kính (m),Tình Trạng,Hạn Kiểm Định,Ghi Chú\n";
            markers.forEach((m, idx) => {
                const t = types[m.type] || {};
                const group = t.group === 'extinguisher' ? 'Bình Chữa Cháy' : (t.group === 'fireequipment' ? 'Phương Tiện PCCC' : 'An Toàn & Cấp Cứu');
                const row = [
                    idx + 1,
                    `"${m.label || ''}"`,
                    `"${t.name || m.type}"`,
                    `"${group}"`,
                    `"${m.dept || ''}"`,
                    m.radius || 15,
                    `"${m.status === 'good' ? 'Hoạt Động Tốt' : (m.status === 'warning' ? 'Cần Bảo Dưỡng' : 'Hết Hạn')}"`,
                    `"${m.nextCheck || '2026-12-31'}"`,
                    `"${(m.note || '').replace(/"/g, '""')}"`
                ];
                csv += row.join(",") + "\n";
            });

            const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `HSE_BOM_Inventory_${this.state.currentPlan}_${Date.now()}.csv`;
            a.click();
            URL.revokeObjectURL(url);
            this.showToast("Đã tải tệp Excel BOM thành công.");
        },

        // =========================================================================
        // 9. EXPORT ENGINE: CAD PDF A3/A4, VECTOR SVG, 4K PNG & JSON PROJECT
        // =========================================================================
        openExportModal: function () {
            const modal = document.getElementById("layout-export-modal");
            if (modal) modal.classList.remove("hidden");
        },

        closeAllModals: function () {
            document.querySelectorAll(".layout-modal-backdrop").forEach(m => m.classList.add("hidden"));
        },

        exportPdf: function (paperSize = "A3") {
            this.closeAllModals();
            this.showToast(`Đang chuẩn bị Bản vẽ Kỹ thuật CAD ${paperSize}...`);

            const p = this.currentPlanData();
            if (!p) return;
            const tb = this.state.titleBlock || {};
            const markers = this.markerArray();
            const types = window.HSE_TYPES || {};
            const icons = window.HSE_SVG_ICONS || {};
            const calc = window.calculateHseExtinguishers(markers);

            // Generate Legend Items
            const usedTypes = [...new Set(markers.map(m => m.type))];
            let legendHtml = "";
            usedTypes.forEach(k => {
                const t = types[k] || {};
                const count = markers.filter(m => m.type === k).length;
                const iconSvg = icons[k] || window.getHseIconSvg(k);
                legendHtml += `
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <span style="display:inline-block; width:18px; height:18px;">${iconSvg}</span>
                        <span><b>${t.name || k}</b> (${count})</span>
                    </div>
                `;
            });

            // Clone SVG stage
            const svgStage = document.getElementById("layout-svg-stage");
            const svgContent = svgStage ? svgStage.innerHTML : "";

            const printHtml = `
                <div class="print-cad-sheet">
                    <div class="print-cad-border">
                        <!-- Top Banner -->
                        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0f172a; padding-bottom: 6px; margin-bottom: 6px;">
                            <div>
                                <h2 style="margin: 0; font-size: 16px; font-weight: 800; text-transform: uppercase;">${tb.companyName || 'ZHAN CHEN (VIETNAM) CO., LTD.'}</h2>
                                <p style="margin: 2px 0 0; font-size: 12px; color: #475569;">${p.name} · BẢN VẼ MẶT BẰNG AN TOÀN PCCC & THOÁT HIỂM</p>
                            </div>
                            <div style="text-align: right; font-size: 11px; color: #475569;">
                                Quy chuẩn TCVN 3890:2023 · QCVN 06:2022/BXD
                            </div>
                        </div>

                        <!-- CAD Drawing Floorplan Viewport -->
                        <div class="print-cad-canvas-wrapper">
                            ${p.backgroundImage ? `<img src="${p.backgroundImage}" style="position: absolute; width: 100%; height: 100%; object-fit: contain; opacity: 0.95;" />` : ''}
                            <svg viewBox="0 0 1000 1000" style="position: absolute; width: 100%; height: 100%; pointer-events: none;">
                                ${svgContent}
                            </svg>
                        </div>

                        <!-- Bottom Information: Legend & Title Block -->
                        <div class="print-cad-bottom">
                            <div class="print-cad-legend">
                                <div style="grid-column: span 4; font-weight: 700; border-bottom: 1px solid #cbd5e1; padding-bottom: 2px; margin-bottom: 2px;">
                                    BẢNG CHÚ GIẢI KÝ HIỆU PCCC & THOÁT HIỂM (${markers.length} THIẾT BỊ · ${calc.totalCylinders} BÌNH CHỮA CHÁY)
                                </div>
                                ${legendHtml}
                            </div>
                            <div class="print-cad-titleblock">
                                <div class="print-tb-cell full">
                                    <div class="print-tb-title">DỰ ÁN / CÔNG TRÌNH:</div>
                                    <div>${tb.plantName || p.name}</div>
                                </div>
                                <div class="print-tb-cell">
                                    <div class="print-tb-title">BẢN VẼ SỐ:</div>
                                    <div>${tb.drawingNo || 'HSE-DWG-2026-001'}</div>
                                </div>
                                <div class="print-tb-cell">
                                    <div class="print-tb-title">TỶ LỆ / KHỔ:</div>
                                    <div>${tb.scale || '1:200'} · ${paperSize}</div>
                                </div>
                                <div class="print-tb-cell">
                                    <div class="print-tb-title">THIẾT KẾ:</div>
                                    <div>${tb.designer || 'Nguyễn Chí Tình'}</div>
                                </div>
                                <div class="print-tb-cell">
                                    <div class="print-tb-title">NGÀY DUYỆT:</div>
                                    <div>${tb.date || new Date().toLocaleDateString('vi-VN')}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            const printRoot = document.getElementById("printRoot");
            if (printRoot) {
                printRoot.innerHTML = printHtml;
                printRoot.classList.remove("hidden");
                setTimeout(() => {
                    window.print();
                    printRoot.classList.add("hidden");
                }, 350);
            }
        },

        exportSvg: function () {
            this.closeAllModals();
            const svgStage = document.getElementById("layout-svg-stage");
            if (!svgStage) return;

            const content = new XMLSerializer().serializeToString(svgStage);
            const blob = new Blob([content], { type: "image/svg+xml;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `HSE_Safety_Vector_${this.state.currentPlan}_${Date.now()}.svg`;
            a.click();
            URL.revokeObjectURL(url);
            this.showToast("Đã xuất bản vẽ vector SVG.");
        },

        exportPng: function () {
            this.closeAllModals();
            this.showToast("Đang kết xuất ảnh PNG 4K độ nét cao...");

            const p = this.currentPlanData();
            if (!p) return;

            const width = 3840;
            const height = 2400;
            const canvas = document.createElement("canvas");
            canvas.width = width;
            canvas.height = height;
            const ctx = canvas.getContext("2d");

            ctx.fillStyle = "#ffffff";
            ctx.fillRect(0, 0, width, height);

            const renderAndSave = () => {
                // Draw Routes
                const routes = this.routeArray();
                const routeTypes = window.HSE_ROUTE_TYPES || {};
                routes.forEach(r => {
                    if (!r.points || r.points.length < 2) return;
                    const rt = routeTypes[r.type] || routeTypes.primary || {};
                    ctx.save();
                    ctx.strokeStyle = rt.color || "#16a34a";
                    ctx.lineWidth = 14;
                    ctx.lineCap = "round";
                    ctx.lineJoin = "round";
                    ctx.beginPath();
                    r.points.forEach((pt, idx) => {
                        const px = pt.x * width;
                        const py = pt.y * height;
                        if (idx === 0) ctx.moveTo(px, py);
                        else ctx.lineTo(px, py);
                    });
                    ctx.stroke();
                    ctx.restore();
                });

                // Draw Markers
                const markers = this.markerArray();
                const types = window.HSE_TYPES || {};
                markers.forEach(m => {
                    const t = types[m.type] || {};
                    const mx = m.x * width;
                    const my = m.y * height;
                    const size = 96;

                    ctx.save();
                    ctx.fillStyle = t.color || "#ef4444";
                    ctx.strokeStyle = "#ffffff";
                    ctx.lineWidth = 6;
                    ctx.beginPath();
                    ctx.roundRect(mx - size / 2, my - size / 2, size, size, 20);
                    ctx.fill();
                    ctx.stroke();

                    ctx.fillStyle = "#0f172a";
                    ctx.font = "bold 28px Arial, sans-serif";
                    ctx.textAlign = "center";
                    ctx.fillText(m.label || "", mx, my + size / 2 + 36);
                    ctx.restore();
                });

                canvas.toBlob(blob => {
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `HSE_Safety_4K_${p.name}_${Date.now()}.png`;
                    a.click();
                    URL.revokeObjectURL(url);
                    this.showToast("Đã tải hình ảnh PNG 4K.");
                }, "image/png");
            };

            if (p.backgroundImage) {
                const img = new Image();
                img.onload = () => {
                    ctx.drawImage(img, 0, 0, width, height);
                    renderAndSave();
                };
                img.onerror = () => renderAndSave();
                img.src = p.backgroundImage;
            } else {
                renderAndSave();
            }
        },

        exportProjectJson: function () {
            this.closeAllModals();
            if (!this.state) return;
            const str = JSON.stringify(this.state, null, 2);
            const blob = new Blob([str], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `HSE_Safety_Project_${Date.now()}.json`;
            a.click();
            URL.revokeObjectURL(url);
            this.showToast("Đã tải tệp sao lưu dự án (.json).");
        },

        // =========================================================================
        // 10. TOOL & MODE SWITCHING & VIEWPORT CONTROLS
        // =========================================================================
        setMode: function (mode) {
            this.currentMode = mode;
            if (mode !== "select") this.deactivateTool();

            document.querySelectorAll(".layout-tool-btn").forEach(btn => {
                btn.classList.toggle("active", btn.getAttribute("data-mode") === mode);
            });

            if (this.canvasEngine) {
                this.canvasEngine.setMode(mode);
            }

            if (mode === "route") {
                this.routeDraft = [];
                this.showToast("Chế độ Tuyến thoát hiểm: Nhấp các điểm trên lối đi, nhấp đúp để hoàn tất.");
            } else if (mode === "zone") {
                this.zoneDraft = [];
                this.showToast("Chế độ Phân vùng: Nhấp các góc để tạo đa giác, nhấp đúp để hoàn tất.");
            }
        },

        fitToScreen: function (padding = 32) {
            if (this.canvasEngine) {
                this.canvasEngine.fitToScreen(padding);
            }
        },

        resetZoom: function () {
            if (this.canvasEngine) this.canvasEngine.resetZoom();
        },

        zoomIn: function (factor = 1.2) {
            if (this.canvasEngine) this.canvasEngine.zoomIn(factor);
        },

        zoomOut: function (factor = 1.2) {
            if (this.canvasEngine) this.canvasEngine.zoomOut(factor);
        },

        syncTheme: function (themeName) {
            const ws = document.getElementById("hse-layout-workspace");
            if (ws) ws.setAttribute("data-theme", themeName || "clean");
            if (this.canvasEngine) {
                this.canvasEngine.renderBackground(true);
                this.canvasEngine.rulers.requestRender();
                this.canvasEngine.minimap.requestRender();
            }
        },

        showToast: function (msg) {
            const toast = document.getElementById("toast") || document.querySelector(".toast");
            if (toast) {
                toast.textContent = msg;
                toast.classList.add("show");
                setTimeout(() => toast.classList.remove("show"), 2800);
            } else {
                console.log("[HSE Layout Toast]", msg);
            }
        },

        // =========================================================================
        // 11. EVENT BINDINGS (BUTTONS, TABS, INPUTS & SHORTCUTS)
        // =========================================================================
        bindUIEvents: function () {
            // Mode buttons
            const selectBtn = document.getElementById("layout-tool-select");
            const panBtn = document.getElementById("layout-tool-pan");
            const routeBtn = document.getElementById("layout-tool-route");
            const zoneBtn = document.getElementById("layout-tool-zone");

            if (selectBtn) selectBtn.onclick = () => this.setMode("select");
            if (panBtn) panBtn.onclick = () => this.setMode("pan");
            if (routeBtn) routeBtn.onclick = () => this.setMode("route");
            if (zoneBtn) zoneBtn.onclick = () => this.setMode("zone");

            // Toggles
            const snapToggle = document.getElementById("layout-toggle-snap");
            const radiusToggle = document.getElementById("layout-toggle-radius");
            const rulerToggle = document.getElementById("layout-toggle-ruler");
            const flowToggle = document.getElementById("layout-toggle-flow");

            if (snapToggle) snapToggle.onclick = () => {
                snapToggle.classList.toggle("active");
                if (this.state && this.state.settings) this.state.settings.snap = snapToggle.classList.contains("active");
            };
            if (radiusToggle) radiusToggle.onclick = () => {
                radiusToggle.classList.toggle("active");
                if (this.state && this.state.settings) this.state.settings.showRadius = radiusToggle.classList.contains("active");
                this.renderMarkers();
            };
            if (rulerToggle) rulerToggle.onclick = () => {
                rulerToggle.classList.toggle("active");
                const isOff = !rulerToggle.classList.contains("active");
                if (this.state && this.state.settings) this.state.settings.showRuler = !isOff;
                const rh = document.getElementById("layout-ruler-h");
                const rv = document.getElementById("layout-ruler-v");
                if (rh) rh.style.display = isOff ? "none" : "";
                if (rv) rv.style.display = isOff ? "none" : "";
                if (this.canvasEngine && this.canvasEngine.rulers) this.canvasEngine.rulers.requestRender();
            };
            if (flowToggle) flowToggle.onclick = () => {
                flowToggle.classList.toggle("active");
                if (this.state && this.state.settings) this.state.settings.flowAnimation = flowToggle.classList.contains("active");
                this.renderSVGLayers();
            };

            // Zoom buttons
            const zoomInBtn = document.getElementById("layout-btn-zoom-in");
            const zoomOutBtn = document.getElementById("layout-btn-zoom-out");
            const fitBtn = document.getElementById("layout-btn-fit");

            if (zoomInBtn) zoomInBtn.onclick = () => this.zoomIn();
            if (zoomOutBtn) zoomOutBtn.onclick = () => this.zoomOut();
            if (fitBtn) fitBtn.onclick = () => this.fitToScreen();

            // Plant Selector Tabs
            const tabA = document.getElementById("layout-tab-plant-a");
            const tabC = document.getElementById("layout-tab-plant-c");
            const tabCustom = document.getElementById("layout-tab-plant-custom");

            const setPlant = (planId, el) => {
                if (this.state) this.state.currentPlan = planId;
                document.querySelectorAll(".layout-plant-tab").forEach(t => t.classList.remove("active"));
                if (el) el.classList.add("active");
                this.deselectObject();
                if (this.canvasEngine) {
                    this.canvasEngine.switchPlan(planId);
                    this.canvasEngine.fitToScreen();
                } else {
                    this.fitToScreen();
                }
                this.renderAll();
            };

            if (tabA) tabA.onclick = () => setPlant("A", tabA);
            if (tabC) tabC.onclick = () => setPlant("C", tabC);
            if (tabCustom) tabCustom.onclick = () => setPlant("custom", tabCustom);

            // Palette Tabs & Search Filter
            document.querySelectorAll(".layout-cat-pill").forEach(pill => {
                pill.onclick = () => {
                    document.querySelectorAll(".layout-cat-pill").forEach(p => p.classList.remove("active"));
                    pill.classList.add("active");
                    const cat = pill.getAttribute("data-cat") || "all";
                    const query = document.getElementById("layout-catalog-filter")?.value || "";
                    this.renderPalette(cat, query);
                };
            });

            const filterInput = document.getElementById("layout-catalog-filter");
            if (filterInput) {
                filterInput.oninput = (e) => {
                    const activePill = document.querySelector(".layout-cat-pill.active");
                    const cat = activePill ? (activePill.getAttribute("data-cat") || "all") : "all";
                    this.renderPalette(cat, e.target.value);
                };
            }

            // BOM and Export Modals
            const bomBtn = document.getElementById("layout-btn-open-bom");
            const exportBtn = document.getElementById("layout-btn-open-export");
            if (bomBtn) bomBtn.onclick = () => this.openBomModal();
            if (exportBtn) exportBtn.onclick = () => this.openExportModal();

            // Custom Background Upload
            const bgInput = document.getElementById("layout-bg-file-input");
            if (bgInput) {
                bgInput.onchange = (e) => {
                    const file = e.target.files && e.target.files[0];
                    if (file) {
                        const reader = new FileReader();
                        reader.onload = (re) => {
                            const dataUrl = re.target.result;
                            const p = this.currentPlanData();
                            if (p) p.backgroundImage = dataUrl;
                            if (this.canvasEngine) this.canvasEngine.renderBackground(true);
                            this.showToast("Đã nạp bản vẽ mặt bằng mới.");
                        };
                        reader.readAsDataURL(file);
                    }
                };
            }
        },

        bindGlobalShortcuts: function () {
            window.removeEventListener("keydown", handleLayoutKeyDown);
            window.addEventListener("keydown", handleLayoutKeyDown);
        },

        setupResizeMonitoring: function () {
            window.removeEventListener("resize", handleLayoutResize);
            window.addEventListener("resize", handleLayoutResize);

            const viewport = document.getElementById("layout-viewport-area");
            if (viewport && window.ResizeObserver) {
                if (resizeObserver) resizeObserver.disconnect();
                resizeObserver = new ResizeObserver(() => handleLayoutResize());
                resizeObserver.observe(viewport);
            }
        }
    };

    // 5-Tier Escape Key Cascade & Global Shortcuts
    function handleLayoutKeyDown(e) {
        const ws = document.getElementById("hse-layout-workspace");
        if (!ws || ws.classList.contains("hidden")) return;

        // Escape Key Handling
        if (e.key === "Escape") {
            // Tier 0: Inside active text input -> blur only
            const targetTag = e.target?.tagName;
            const activeTag = document.activeElement?.tagName;
            if (["INPUT", "TEXTAREA", "SELECT"].includes(targetTag) || ["INPUT", "TEXTAREA", "SELECT"].includes(activeTag)) {
                if (document.activeElement && typeof document.activeElement.blur === "function") document.activeElement.blur();
                if (e.target && typeof e.target.blur === "function") e.target.blur();
                e.stopPropagation();
                return;
            }

            // Tier 1: Modal is open -> close modal
            const openModal = document.querySelector(".layout-modal-backdrop:not(.hidden)");
            if (openModal) {
                openModal.classList.add("hidden");
                return;
            }

            // Tier 2: Currently drawing a route or zone -> cancel drawing
            if (LayoutController.currentMode !== "select" || LayoutController.activeTool) {
                LayoutController.cancelDrawing();
                return;
            }

            // Tier 3: An object is currently selected -> deselect object
            if (LayoutController.selectedObjectId) {
                LayoutController.deselectObject();
                return;
            }

            // Tier 4: Fully idle -> Return to Home Dashboard
            closeHseLayoutWorkspace();
            return;
        }

        // Delete / Backspace: Delete selected object
        if ((e.key === "Delete" || e.key === "Backspace") && LayoutController.selectedObjectId) {
            const targetTag = e.target?.tagName;
            if (!["INPUT", "TEXTAREA"].includes(targetTag)) {
                e.preventDefault();
                LayoutController.deleteSelected();
            }
        }

        // Undo: Ctrl+Z
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) {
            e.preventDefault();
            LayoutController.undo();
        }

        // Redo: Ctrl+Y or Ctrl+Shift+Z
        if (((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") || ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "z")) {
            e.preventDefault();
            LayoutController.redo();
        }

        // Zoom & Fit Shortcuts
        if ((e.ctrlKey || e.metaKey) && e.key === "0") {
            e.preventDefault();
            LayoutController.fitToScreen();
        } else if ((e.ctrlKey || e.metaKey) && (e.key === "=" || e.key === "+")) {
            e.preventDefault();
            LayoutController.zoomIn();
        } else if ((e.ctrlKey || e.metaKey) && (e.key === "-" || e.key === "_")) {
            e.preventDefault();
            LayoutController.zoomOut();
        }

        // Single Key Mode Shortcuts (When not typing in inputs)
        const activeTag = document.activeElement?.tagName;
        if (!["INPUT", "TEXTAREA"].includes(activeTag)) {
            if (e.key.toLowerCase() === "v") LayoutController.setMode("select");
            else if (e.key.toLowerCase() === "h") LayoutController.setMode("pan");
            else if (e.key.toLowerCase() === "e") LayoutController.setMode("route");
            else if (e.key.toLowerCase() === "z") LayoutController.setMode("zone");
        }
    }

    // Debounced Resize Handler
    function handleLayoutResize() {
        if (resizeRafId) cancelAnimationFrame(resizeRafId);
        resizeRafId = requestAnimationFrame(() => {
            const ws = document.getElementById("hse-layout-workspace");
            if (ws && !ws.classList.contains("hidden")) {
                LayoutController.fitToScreen();
            }
        });
    }

    // Global Workspace Dispatchers
    window.openHseLayoutWorkspace = function () {
        const homeView = document.getElementById("home-view");
        const wsView = document.getElementById("workspace-view");
        const editorView = document.getElementById("vip-editor-view");
        const aiView = document.getElementById("ai-studio-view");
        const msdsView = document.getElementById("msds-studio-view");
        const hseView = document.getElementById("hse-studio-view");
        const legalView = document.getElementById("legal-lookup-view");
        const layoutWs = document.getElementById("hse-layout-workspace");
        const footer = document.querySelector(".footer");

        if (homeView) homeView.classList.add("hidden");
        if (wsView) wsView.classList.add("hidden");
        if (editorView) editorView.classList.add("hidden");
        if (aiView) aiView.classList.add("hidden");
        if (msdsView) msdsView.classList.add("hidden");
        if (hseView) hseView.classList.add("hidden");
        if (legalView) legalView.classList.add("hidden");
        if (footer) footer.classList.add("hidden");

        // Clear top navbar tab active states since Tool 33 has zero navbar tabs
        document.querySelectorAll(".main-nav-tab").forEach(tab => tab.classList.remove("active"));

        if (layoutWs) {
            layoutWs.classList.remove("hidden");
            document.body.classList.add("hse-layout-active");
            LayoutController.init();
        }

        window.scrollTo({ top: 0, behavior: "instant" });
    };

    window.closeHseLayoutWorkspace = function () {
        const homeView = document.getElementById("home-view");
        const layoutWs = document.getElementById("hse-layout-workspace");
        const footer = document.querySelector(".footer");

        LayoutController.destroy();

        if (layoutWs) layoutWs.classList.add("hidden");
        if (homeView) homeView.classList.remove("hidden");
        if (footer) footer.classList.remove("hidden");
        document.body.classList.remove("hse-layout-active");

        // Restore active state to tools tab
        const navTools = document.getElementById("nav-tab-tools");
        if (navTools) navTools.classList.add("active");
    };

    window.initHseLayout = () => LayoutController.init();
    window.destroyHseLayout = () => LayoutController.destroy();
    window.syncLayoutTheme = (t) => LayoutController.syncTheme(t);
    window.HseLayout = LayoutController;

})(window, document);
