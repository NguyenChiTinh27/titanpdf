/**
 * static/hse_layout_canvas.js — HSE Safety Layout Planner PRO CAD Canvas Engine
 * Milestone M2: Viewport Pan/Zoom Transform Engine, Dual-Layer Renderer,
 * Smart Snap Engine, Scale Ruler Engine & Minimap Navigator
 *
 * Architecture:
 * 1. HseViewportEngine   - Normalized coordinates [0.0, 1.0], focal zoom, pan, screen/svg mapping
 * 2. HseDualLayerRenderer - Background Canvas (Layer 1) & Vector SVG (Layer 2) with HiDPI support
 * 3. HseSnapEngine        - 1% / metric grid snapping, 45°/90° angular snapping & visual crosshair
 * 4. HseScaleRulerEngine  - Dynamic LOD engineering metric rulers with mouse cursor tracking
 * 5. MinimapNavigator     - High-performance 2D canvas minimap with camera box & click/drag-to-pan
 * 6. HseLayoutCanvas      - Unified coordinator facade
 */

(function (window, document) {
    "use strict";

    // =========================================================================
    // SECTION 1: VIEWPORT TRANSFORM & COORDINATE ENGINE
    // =========================================================================

    class HseViewportEngine {
        /**
         * @param {Object} config
         * @param {HTMLElement} config.viewportEl   - #layout-viewport-area
         * @param {HTMLElement} config.stageEl      - #layout-stage-wrapper
         * @param {HTMLElement} config.transformEl  - #layout-canvas-transform (1000x1000)
         * @param {SVGSVGElement} config.svgEl      - #layout-svg-stage
         * @param {HTMLElement} [config.zoomBadge]  - #layout-zoom-val
         * @param {Function} [config.onTransformChange] - Transform callback
         */
        constructor(config = {}) {
            this.viewportEl = config.viewportEl || document.getElementById("layout-viewport-area");
            this.stageEl = config.stageEl || document.getElementById("layout-stage-wrapper");
            this.transformEl = config.transformEl || document.getElementById("layout-canvas-transform");
            this.svgEl = config.svgEl || document.getElementById("layout-svg-stage");
            this.zoomBadge = config.zoomBadge || document.getElementById("layout-zoom-val");
            this.onTransformChange = config.onTransformChange || null;

            // Viewport Transform State
            this.transform = {
                scale: 1.0,
                x: 0,
                y: 0
            };

            // Zoom Constraints
            this.minScale = 0.15; // 15%
            this.maxScale = 5.0;  // 500%
            this.baseWidth = 1000;
            this.baseHeight = 1000;

            // Interaction State
            this.isPanning = false;
            this.panStart = { x: 0, y: 0 };
            this.activePointerId = null;
            this.spacePressed = false;
            this.currentMode = "select"; // "select" | "pan" | "route" | "zone"

            // Performance batching
            this._rafId = null;
            this._boundHandlers = {};
        }

        /**
         * Map screen coordinates (clientX, clientY) to normalized space (x, y) in [0.0, 1.0]
         * @param {number} clientX
         * @param {number} clientY
         * @param {Object} [options]
         * @param {boolean} [options.clamp=true]
         * @param {boolean} [options.snap=false]
         * @param {number}  [options.step=0.01]
         * @returns {{x: number, y: number}}
         */
        screenToNorm(clientX, clientY, options = {}) {
            if (!this.transformEl) return { x: 0, y: 0 };
            const rect = this.transformEl.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0) return { x: 0, y: 0 };

            let normX = (clientX - rect.left) / rect.width;
            let normY = (clientY - rect.top) / rect.height;

            if (options.clamp !== false) {
                normX = Math.max(0.0, Math.min(1.0, normX));
                normY = Math.max(0.0, Math.min(1.0, normY));
            }

            if (options.snap) {
                const step = options.step || 0.01;
                normX = Math.round(normX / step) * step;
                normY = Math.round(normY / step) * step;
                if (options.clamp !== false) {
                    normX = Math.max(0.0, Math.min(1.0, normX));
                    normY = Math.max(0.0, Math.min(1.0, normY));
                }
            }

            return {
                x: Number(normX.toFixed(6)),
                y: Number(normY.toFixed(6))
            };
        }

        /**
         * Map normalized coordinates [0.0, 1.0] to screen pixels (clientX, clientY)
         * @param {number} normX
         * @param {number} normY
         * @returns {{clientX: number, clientY: number}}
         */
        normToScreen(normX, normY) {
            if (!this.transformEl) return { clientX: 0, clientY: 0 };
            const rect = this.transformEl.getBoundingClientRect();
            return {
                clientX: rect.left + normX * rect.width,
                clientY: rect.top + normY * rect.height
            };
        }

        /**
         * Map normalized coordinates [0.0, 1.0] to SVG viewBox coordinates (default 0 0 1000 1000)
         * @param {number} normX
         * @param {number} normY
         * @param {Object} [viewBox]
         * @returns {{svgX: number, svgY: number}}
         */
        normToSvg(normX, normY, viewBox) {
            const vb = viewBox || (this.svgEl && this.svgEl.viewBox ? this.svgEl.viewBox.baseVal : null) || {
                x: 0, y: 0, width: this.baseWidth, height: this.baseHeight
            };
            return {
                svgX: vb.x + normX * vb.width,
                svgY: vb.y + normY * vb.height
            };
        }

        /**
         * Map SVG viewBox coordinates to normalized space [0.0, 1.0]
         * @param {number} svgX
         * @param {number} svgY
         * @param {Object} [viewBox]
         * @returns {{normX: number, normY: number}}
         */
        svgToNorm(svgX, svgY, viewBox) {
            const vb = viewBox || (this.svgEl && this.svgEl.viewBox ? this.svgEl.viewBox.baseVal : null) || {
                x: 0, y: 0, width: this.baseWidth, height: this.baseHeight
            };
            const w = vb.width || this.baseWidth;
            const h = vb.height || this.baseHeight;
            return {
                normX: (svgX - vb.x) / w,
                normY: (svgY - vb.y) / h
            };
        }

        /**
         * Zoom viewport centered at a specific screen point (focal invariance)
         * @param {number} factor
         * @param {number} clientX
         * @param {number} clientY
         */
        syncState() {
            if (this.zoomBadge) {
                this.zoomBadge.textContent = `${Math.round(this.transform.scale * 100)}%`;
            }
            if (typeof this.onTransformChange === "function") {
                this.onTransformChange(this.getTransform());
            }
        }

        zoomAtPoint(factor, clientX, clientY) {
            if (!this.stageEl || !this.transformEl) return;
            const stageRect = this.stageEl.getBoundingClientRect();
            const mouseX = clientX - stageRect.left;
            const mouseY = clientY - stageRect.top;

            const oldScale = this.transform.scale;
            const newScale = Math.min(this.maxScale, Math.max(this.minScale, oldScale * factor));
            if (Math.abs(newScale - oldScale) < 0.0001) return;

            // Focal translation adjustment
            this.transform.x = mouseX - (mouseX - this.transform.x) * (newScale / oldScale);
            this.transform.y = mouseY - (mouseY - this.transform.y) * (newScale / oldScale);
            this.transform.scale = newScale;

            this.syncState();
            this.applyTransform();
        }

        zoomIn(factor = 1.2) {
            const rect = this.stageEl ? this.stageEl.getBoundingClientRect() : { left: 0, top: 0, width: 800, height: 600 };
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;
            this.zoomAtPoint(factor, cx, cy);
        }

        zoomOut(factor = 1.2) {
            const rect = this.stageEl ? this.stageEl.getBoundingClientRect() : { left: 0, top: 0, width: 800, height: 600 };
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;
            this.zoomAtPoint(1.0 / factor, cx, cy);
        }

        panCanvas(deltaX, deltaY) {
            this.transform.x += deltaX;
            this.transform.y += deltaY;
            this.syncState();
            this.applyTransform();
        }

        fitToScreen(padding = 32) {
            if (!this.stageEl || !this.transformEl) return;
            const vw = this.stageEl.clientWidth - padding * 2;
            const vh = this.stageEl.clientHeight - padding * 2;
            if (vw <= 0 || vh <= 0) return;

            const scale = Math.min(vw / this.baseWidth, vh / this.baseHeight);
            this.transform.scale = Math.max(this.minScale, Math.min(3.0, scale));

            this.transform.x = Math.round((this.stageEl.clientWidth - this.baseWidth * this.transform.scale) / 2);
            this.transform.y = Math.round((this.stageEl.clientHeight - this.baseHeight * this.transform.scale) / 2);

            this.syncState();
            this.applyTransform();
        }

        resetZoom() {
            if (!this.stageEl || !this.transformEl) return;
            this.transform.scale = 1.0;
            this.transform.x = Math.round((this.stageEl.clientWidth - this.baseWidth) / 2);
            this.transform.y = Math.round((this.stageEl.clientHeight - this.baseHeight) / 2);
            this.syncState();
            this.applyTransform();
        }

        applyTransform() {
            if (this._rafId) cancelAnimationFrame(this._rafId);
            this._rafId = requestAnimationFrame(() => {
                if (this.transformEl) {
                    this.transformEl.style.transform = `translate(${this.transform.x}px, ${this.transform.y}px) scale(${this.transform.scale})`;
                }
            });
        }

        getTransform() {
            return {
                scale: this.transform.scale,
                x: this.transform.x,
                y: this.transform.y
            };
        }

        setTransform(t) {
            if (!t) return;
            if (typeof t.scale === "number") this.transform.scale = Math.max(this.minScale, Math.min(this.maxScale, t.scale));
            if (typeof t.x === "number") this.transform.x = t.x;
            if (typeof t.y === "number") this.transform.y = t.y;
            this.syncState();
            this.applyTransform();
        }

        setMode(mode) {
            this.currentMode = mode;
            this.updateCursor();
        }

        updateCursor() {
            if (!this.stageEl) return;
            if (this.isPanning) {
                this.stageEl.style.cursor = "grabbing";
            } else if (this.spacePressed || this.currentMode === "pan") {
                this.stageEl.style.cursor = "grab";
            } else {
                this.stageEl.style.cursor = "default";
            }
        }

        bindEvents() {
            if (!this.stageEl) return;

            // A. Wheel Event (Zoom cursor-centered)
            this._boundHandlers.wheel = (e) => {
                e.preventDefault();
                const delta = e.deltaY;
                const factor = Math.exp(-delta * 0.0018);
                const clampedFactor = Math.max(0.75, Math.min(1.35, factor));
                this.zoomAtPoint(clampedFactor, e.clientX, e.clientY);
            };
            this.stageEl.addEventListener("wheel", this._boundHandlers.wheel, { passive: false });

            // B. Pointer Events for Pan & Drag
            this._boundHandlers.pointerDown = (e) => {
                const isMiddle = e.button === 1;
                const isSpaceDrag = this.spacePressed && e.button === 0;
                const isPanMode = this.currentMode === "pan" && e.button === 0;
                const isBgClick = e.button === 0 && (
                    e.target === this.stageEl ||
                    e.target === this.transformEl ||
                    e.target.id === "layout-floorplan-canvas" ||
                    e.target.id === "layout-svg-stage"
                );

                if (isMiddle || isSpaceDrag || isPanMode || (isBgClick && this.currentMode === "select")) {
                    e.preventDefault();
                    this.isPanning = true;
                    this.activePointerId = e.pointerId;
                    this.panStart = { x: e.clientX, y: e.clientY };
                    if (typeof this.stageEl.setPointerCapture === "function") {
                        try { this.stageEl.setPointerCapture(e.pointerId); } catch (_) {}
                    }
                    this.updateCursor();
                }
            };

            this._boundHandlers.pointerMove = (e) => {
                if (!this.isPanning || e.pointerId !== this.activePointerId) return;
                e.preventDefault();
                const dx = e.clientX - this.panStart.x;
                const dy = e.clientY - this.panStart.y;
                this.panStart = { x: e.clientX, y: e.clientY };
                this.panCanvas(dx, dy);
            };

            this._boundHandlers.pointerUp = (e) => {
                if (this.isPanning && e.pointerId === this.activePointerId) {
                    this.isPanning = false;
                    this.activePointerId = null;
                    if (typeof this.stageEl.releasePointerCapture === "function") {
                        try { this.stageEl.releasePointerCapture(e.pointerId); } catch (_) {}
                    }
                    this.updateCursor();
                }
            };

            this.stageEl.addEventListener("pointerdown", this._boundHandlers.pointerDown);
            window.addEventListener("pointermove", this._boundHandlers.pointerMove);
            window.addEventListener("pointerup", this._boundHandlers.pointerUp);
            window.addEventListener("pointercancel", this._boundHandlers.pointerUp);

            // C. Keyboard Listeners: Spacebar Panning & Arrow Keys Pan
            this._boundHandlers.keyDown = (e) => {
                const targetTag = e.target?.tagName;
                if (targetTag && ["INPUT", "TEXTAREA", "SELECT"].includes(targetTag)) return;

                if (e.code === "Space" && !this.spacePressed) {
                    this.spacePressed = true;
                    this.updateCursor();
                }

                // Keyboard arrow pan
                const panStep = e.shiftKey ? 80 : 30;
                if (e.key === "ArrowLeft") {
                    e.preventDefault();
                    this.panCanvas(panStep, 0);
                } else if (e.key === "ArrowRight") {
                    e.preventDefault();
                    this.panCanvas(-panStep, 0);
                } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    this.panCanvas(0, panStep);
                } else if (e.key === "ArrowDown") {
                    e.preventDefault();
                    this.panCanvas(0, -panStep);
                }
            };

            this._boundHandlers.keyUp = (e) => {
                if (e.code === "Space") {
                    this.spacePressed = false;
                    this.updateCursor();
                }
            };

            window.addEventListener("keydown", this._boundHandlers.keyDown);
            window.addEventListener("keyup", this._boundHandlers.keyUp);
        }

        unbindEvents() {
            if (this.stageEl && this._boundHandlers.wheel) {
                this.stageEl.removeEventListener("wheel", this._boundHandlers.wheel);
            }
            if (this.stageEl && this._boundHandlers.pointerDown) {
                this.stageEl.removeEventListener("pointerdown", this._boundHandlers.pointerDown);
            }
            if (this._boundHandlers.pointerMove) {
                window.removeEventListener("pointermove", this._boundHandlers.pointerMove);
            }
            if (this._boundHandlers.pointerUp) {
                window.removeEventListener("pointerup", this._boundHandlers.pointerUp);
                window.removeEventListener("pointercancel", this._boundHandlers.pointerUp);
            }
            if (this._boundHandlers.keyDown) {
                window.removeEventListener("keydown", this._boundHandlers.keyDown);
            }
            if (this._boundHandlers.keyUp) {
                window.removeEventListener("keyup", this._boundHandlers.keyUp);
            }
            if (this._rafId) {
                cancelAnimationFrame(this._rafId);
                this._rafId = null;
            }
        }

        destroy() {
            this.unbindEvents();
            this.isPanning = false;
            this.activePointerId = null;
        }
    }

    // =========================================================================
    // SECTION 2: DUAL-LAYER RENDERER (CANVAS GRID/BLUEPRINT + SVG VECTOR STAGE)
    // =========================================================================

    const HseDualLayerRenderer = {
        bgCanvas: null,
        bgCtx: null,
        svgRoot: null,
        transformContainer: null,
        currentDpr: 1.0,
        cachedBlueprintImg: null,
        isDirty: true,

        init: function () {
            this.bgCanvas = document.getElementById("layout-floorplan-canvas") || document.getElementById("layout-bg-canvas");
            if (this.bgCanvas) {
                this.bgCtx = this.bgCanvas.getContext("2d", { alpha: true });
            }
            this.svgRoot = document.getElementById("layout-svg-stage") || document.getElementById("layout-svg-root");
            this.transformContainer = document.getElementById("layout-canvas-transform");

            this.updateDpr();
            this.renderBackground();
            console.log("[HseDualLayerRenderer] Initialized with HiDPI support.");
        },

        updateDpr: function () {
            const dpr = window.devicePixelRatio || 1.0;
            this.currentDpr = Math.max(1.0, Math.min(3.0, dpr));

            if (this.bgCanvas) {
                const logicalWidth = 1000;
                const logicalHeight = 1000;

                this.bgCanvas.width = Math.round(logicalWidth * this.currentDpr);
                this.bgCanvas.height = Math.round(logicalHeight * this.currentDpr);
                this.bgCanvas.style.width = logicalWidth + "px";
                this.bgCanvas.style.height = logicalHeight + "px";

                if (this.bgCtx) {
                    this.bgCtx.setTransform(this.currentDpr, 0, 0, this.currentDpr, 0, 0);
                }
            }
        },

        renderBackground: function (forceRedraw = false) {
            if (!this.bgCtx || !this.bgCanvas) return;
            const ctx = this.bgCtx;
            const width = 1000;
            const height = 1000;

            const state = (window.HseLayout && window.HseLayout.state) ? window.HseLayout.state : null;
            const currentPlanId = state ? state.currentPlan : "A";
            const planData = (state && state.plans && state.plans[currentPlanId]) ? state.plans[currentPlanId] : null;
            const settings = (state && state.settings) ? state.settings : { snap: true, gridSize: 1.0, opacity: 1.0 };
            const building = (planData && planData.building) ? planData.building : { width: 60.0, height: 72.1, grid: 1.0 };

            // A. Clear canvas
            ctx.clearRect(0, 0, width, height);

            // B. Draw architectural paper background
            const computedStyle = getComputedStyle(document.documentElement);
            const paperColor = computedStyle.getPropertyValue("--layout-canvas-paper").trim() || "#ffffff";
            ctx.fillStyle = paperColor;
            ctx.fillRect(0, 0, width, height);

            // C. Draw background blueprint image if provided
            if (planData && planData.backgroundImage) {
                this.drawBackgroundImage(ctx, planData.backgroundImage, width, height, settings.opacity);
            } else if (this.cachedBlueprintImg) {
                this.drawLoadedImage(ctx, this.cachedBlueprintImg, width, height, settings.opacity);
            }

            // D. Draw engineering grid lines
            this.drawEngineeringGrid(ctx, width, height, building, computedStyle);

            // E. Draw structural border and north arrow
            this.drawStructuralBoundary(ctx, width, height, building, computedStyle);

            this.isDirty = false;
        },

        drawEngineeringGrid: function (ctx, width, height, building, style) {
            const gridInterval = building.grid || 1.0;
            const bw = building.width || 60.0;
            const bh = building.height || 60.0;

            const stepX = (gridInterval / bw) * width;
            const stepY = (gridInterval / bh) * height;

            const minorColor = style.getPropertyValue("--layout-grid-minor").trim() || "rgba(148, 163, 184, 0.25)";
            const majorColor = style.getPropertyValue("--layout-grid-major").trim() || "rgba(100, 116, 139, 0.45)";

            ctx.save();
            ctx.lineWidth = 1.0;

            // Minor Grid Lines
            ctx.strokeStyle = minorColor;
            ctx.beginPath();
            for (let x = 0; x <= width + 0.1; x += stepX) {
                ctx.moveTo(Math.round(x) + 0.5, 0);
                ctx.lineTo(Math.round(x) + 0.5, height);
            }
            for (let y = 0; y <= height + 0.1; y += stepY) {
                ctx.moveTo(0, Math.round(y) + 0.5);
                ctx.lineTo(width, Math.round(y) + 0.5);
            }
            ctx.stroke();

            // Major Grid Lines (every 5m or 10m)
            const majorInterval = (gridInterval <= 0.5) ? 5.0 : 10.0;
            const majorStepX = (majorInterval / bw) * width;
            const majorStepY = (majorInterval / bh) * height;

            ctx.strokeStyle = majorColor;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            for (let x = 0; x <= width + 0.1; x += majorStepX) {
                ctx.moveTo(Math.round(x) + 0.5, 0);
                ctx.lineTo(Math.round(x) + 0.5, height);
            }
            for (let y = 0; y <= height + 0.1; y += majorStepY) {
                ctx.moveTo(0, Math.round(y) + 0.5);
                ctx.lineTo(width, Math.round(y) + 0.5);
            }
            ctx.stroke();

            ctx.restore();
        },

        drawStructuralBoundary: function (ctx, width, height, building, style) {
            ctx.save();
            const brandDark = style.getPropertyValue("--layout-border-focus").trim() || "#0f172a";
            ctx.strokeStyle = brandDark;
            ctx.lineWidth = 2.0;
            ctx.strokeRect(1, 1, width - 2, height - 2);

            // North Arrow indicator at top right
            const naX = width - 40;
            const naY = 40;
            ctx.fillStyle = "rgba(15, 23, 42, 0.75)";
            ctx.beginPath();
            ctx.moveTo(naX, naY - 20);
            ctx.lineTo(naX - 8, naY + 10);
            ctx.lineTo(naX, naY + 4);
            ctx.closePath();
            ctx.fill();

            ctx.fillStyle = "rgba(239, 68, 68, 0.9)";
            ctx.beginPath();
            ctx.moveTo(naX, naY - 20);
            ctx.lineTo(naX + 8, naY + 10);
            ctx.lineTo(naX, naY + 4);
            ctx.closePath();
            ctx.fill();

            ctx.font = "bold 11px system-ui, sans-serif";
            ctx.fillStyle = brandDark;
            ctx.textAlign = "center";
            ctx.fillText("N", naX, naY - 24);

            ctx.restore();
        },

        drawBackgroundImage: function (ctx, imageSrc, width, height, opacity = 1.0) {
            if (!imageSrc) return;
            if (this.cachedBlueprintImg && this.cachedBlueprintImg.src === imageSrc && this.cachedBlueprintImg.complete) {
                this.drawLoadedImage(ctx, this.cachedBlueprintImg, width, height, opacity);
            } else {
                const img = new Image();
                img.onload = () => {
                    this.cachedBlueprintImg = img;
                    this.renderBackground();
                };
                img.src = imageSrc;
            }
        },

        drawLoadedImage: function (ctx, img, width, height, opacity) {
            ctx.save();
            ctx.globalAlpha = Math.max(0.1, Math.min(1.0, opacity));
            ctx.drawImage(img, 0, 0, width, height);
            ctx.restore();
        }
    };

    // =========================================================================
    // SECTION 3: SMART SNAP ENGINE (GRID & ANGULAR SNAPPING)
    // =========================================================================

    const HseSnapEngine = {
        /**
         * 1D Scalar Snap
         * @param {number} v
         * @param {number} [step=0.01]
         * @returns {number}
         */
        snap: function (v, step = 0.01) {
            if (!step || step <= 0) return v;
            const inv = 1.0 / step;
            return Math.round(v * inv) / inv;
        },

        /**
         * 2D Metric Point Snap based on real factory meters
         * @param {Object} normPt - { x, y } in [0.0, 1.0]
         * @param {Object} building - { width, height, grid }
         * @param {number} [overrideInterval]
         * @returns {{x: number, y: number}}
         */
        snapPoint: function (normPt, building, overrideInterval = null) {
            const state = (window.HseLayout && window.HseLayout.state) ? window.HseLayout.state : null;
            const isSnapActive = state && state.settings ? state.settings.snap : true;
            if (!isSnapActive) {
                return { x: normPt.x, y: normPt.y };
            }

            const bw = (building && building.width) ? building.width : 60.0;
            const bh = (building && building.height) ? building.height : 60.0;
            const interval = overrideInterval || (building && building.grid) || 1.0;

            const stepX = interval / bw;
            const stepY = interval / bh;

            const sx = Math.max(0.0, Math.min(1.0, this.snap(normPt.x, stepX)));
            const sy = Math.max(0.0, Math.min(1.0, this.snap(normPt.y, stepY)));

            return {
                x: Math.round(sx * 1e6) / 1e6,
                y: Math.round(sy * 1e6) / 1e6
            };
        },

        /**
         * Angular snapping (45° or 90°) for routes and segments
         * @param {Object} p0 - Starting normalized point { x, y }
         * @param {Object} p1 - Current normalized cursor point { x, y }
         * @param {Object} building - Factory dimensions
         * @param {number} [snapAngleDeg=45]
         * @returns {{x: number, y: number, angleDeg: number, distanceMeters: number}}
         */
        snapSegment: function (p0, p1, building, snapAngleDeg = 45) {
            const bw = (building && building.width) ? building.width : 60.0;
            const bh = (building && building.height) ? building.height : 60.0;

            const dxMetric = (p1.x - p0.x) * bw;
            const dyMetric = (p1.y - p0.y) * bh;
            const distanceMeters = Math.sqrt(dxMetric * dxMetric + dyMetric * dyMetric);

            if (distanceMeters < 0.001) {
                return { x: p1.x, y: p1.y, angleDeg: 0, distanceMeters: 0 };
            }

            const rawRad = Math.atan2(dyMetric, dxMetric);
            let rawDeg = (rawRad * 180.0 / Math.PI + 360.0) % 360.0;

            const snappedDeg = (Math.round(rawDeg / snapAngleDeg) * snapAngleDeg) % 360.0;
            const snappedRad = snappedDeg * Math.PI / 180.0;

            const snappedDxMetric = distanceMeters * Math.cos(snappedRad);
            const snappedDyMetric = distanceMeters * Math.sin(snappedRad);

            const targetX = Math.max(0.0, Math.min(1.0, p0.x + snappedDxMetric / bw));
            const targetY = Math.max(0.0, Math.min(1.0, p0.y + snappedDyMetric / bh));

            return {
                x: Math.round(targetX * 1e6) / 1e6,
                y: Math.round(targetY * 1e6) / 1e6,
                angleDeg: snappedDeg,
                distanceMeters: Math.round(distanceMeters * 10) / 10
            };
        },

        /**
         * Equipment rotation angle snapping
         * @param {number} angleDeg
         * @param {boolean} [isShiftHeld=false]
         * @returns {number}
         */
        snapRotation: function (angleDeg, isShiftHeld = false) {
            const cleanAngle = ((angleDeg % 360) + 360) % 360;
            if (isShiftHeld) {
                return (Math.round(cleanAngle / 45) * 45) % 360;
            }
            return (Math.round(cleanAngle / 15) * 15) % 360;
        },

        /**
         * Render visual crosshair and measurement badge on active draw SVG group
         */
        renderSnapGuide: function (normPt, extraInfo = null) {
            const activeGroup = document.getElementById("layout-active-draw-group");
            if (!activeGroup) return;

            let guideEl = document.getElementById("layout-snap-crosshair");
            if (!guideEl) {
                guideEl = document.createElementNS("http://www.w3.org/2000/svg", "g");
                guideEl.id = "layout-snap-crosshair";
                activeGroup.appendChild(guideEl);
            }

            const svgX = normPt.x * 1000;
            const svgY = normPt.y * 1000;

            let badgeHtml = "";
            if (extraInfo && extraInfo.angleDeg !== undefined) {
                badgeHtml = `
                    <rect x="${svgX + 12}" y="${svgY - 22}" width="80" height="20" rx="4" fill="rgba(15, 23, 42, 0.85)" stroke="#10b981" stroke-width="1"/>
                    <text x="${svgX + 52}" y="${svgY - 8}" fill="#ffffff" font-size="11" font-weight="bold" font-family="monospace" text-anchor="middle">
                        ${extraInfo.angleDeg}° | ${extraInfo.distanceMeters || 0}m
                    </text>
                `;
            }

            guideEl.innerHTML = `
                <circle cx="${svgX}" cy="${svgY}" r="6" fill="none" stroke="#10b981" stroke-width="2"/>
                <circle cx="${svgX}" cy="${svgY}" r="2" fill="#10b981"/>
                <line x1="${svgX - 14}" y1="${svgY}" x2="${svgX - 6}" y2="${svgY}" stroke="#10b981" stroke-width="1.5"/>
                <line x1="${svgX + 6}" y1="${svgY}" x2="${svgX + 14}" y2="${svgY}" stroke="#10b981" stroke-width="1.5"/>
                <line x1="${svgX}" y1="${svgY - 14}" x2="${svgX}" y2="${svgY - 6}" stroke="#10b981" stroke-width="1.5"/>
                <line x1="${svgX}" y1="${svgY + 6}" x2="${svgX}" y2="${svgY + 14}" stroke="#10b981" stroke-width="1.5"/>
                ${badgeHtml}
            `;
        },

        clearSnapGuide: function () {
            const guideEl = document.getElementById("layout-snap-crosshair");
            if (guideEl) guideEl.remove();
        }
    };

    // =========================================================================
    // SECTION 4: SCALE RULER ENGINE (DYNAMIC METRIC RULERS & CURSOR TRACKING)
    // =========================================================================

    const HseScaleRulerEngine = {
        rulerH: null,
        rulerV: null,
        ctxH: null,
        ctxV: null,
        viewportArea: null,
        stageTransform: null,
        cursorPos: null,
        rafId: null,

        init: function () {
            this.rulerH = document.getElementById("layout-ruler-h") || document.getElementById("layout-ruler-x");
            this.rulerV = document.getElementById("layout-ruler-v") || document.getElementById("layout-ruler-y");
            this.viewportArea = document.getElementById("layout-viewport-area");
            this.stageTransform = document.getElementById("layout-canvas-transform");

            if (this.rulerH) this.ctxH = this.rulerH.getContext("2d");
            if (this.rulerV) this.ctxV = this.rulerV.getContext("2d");

            this.bindCursorTracking();
            this.render();
            console.log("[HseScaleRulerEngine] Metric rulers initialized.");
        },

        bindCursorTracking: function () {
            if (!this.viewportArea) return;

            this._onMouseMove = (e) => {
                this.cursorPos = { clientX: e.clientX, clientY: e.clientY };
                this.requestRender();
            };

            this._onMouseLeave = () => {
                this.cursorPos = null;
                this.requestRender();
            };

            this.viewportArea.addEventListener("mousemove", this._onMouseMove, { passive: true });
            this.viewportArea.addEventListener("mouseleave", this._onMouseLeave, { passive: true });
        },

        requestRender: function () {
            if (this.rafId) return;
            this.rafId = requestAnimationFrame(() => {
                this.render();
                this.rafId = null;
            });
        },

        calculateLOD: function (pixelsPerMeter) {
            if (pixelsPerMeter < 3.5) {
                return { major: 20.0, minor: 5.0, sub: 2.5 };
            } else if (pixelsPerMeter < 8.0) {
                return { major: 10.0, minor: 2.0, sub: 1.0 };
            } else if (pixelsPerMeter < 18.0) {
                return { major: 5.0, minor: 1.0, sub: 0.5 };
            } else if (pixelsPerMeter < 45.0) {
                return { major: 2.0, minor: 0.5, sub: 0.25 };
            } else if (pixelsPerMeter < 90.0) {
                return { major: 1.0, minor: 0.2, sub: 0.1 };
            } else {
                return { major: 0.5, minor: 0.1, sub: 0.05 };
            }
        },

        render: function () {
            if (!this.rulerH || !this.rulerV || !this.ctxH || !this.ctxV) return;

            const state = (window.HseLayout && window.HseLayout.state) ? window.HseLayout.state : null;
            if (state && state.settings && state.settings.showRuler === false) {
                this.rulerH.style.display = "none";
                this.rulerV.style.display = "none";
                return;
            } else {
                this.rulerH.style.display = "block";
                this.rulerV.style.display = "block";
            }

            const currentPlanId = state ? state.currentPlan : "A";
            const planData = (state && state.plans && state.plans[currentPlanId]) ? state.plans[currentPlanId] : null;
            const building = (planData && planData.building) ? planData.building : { width: 60.0, height: 72.1 };

            const dpr = window.devicePixelRatio || 1.0;
            const computedStyle = getComputedStyle(document.documentElement);

            // A. Horizontal Ruler
            const rwH = this.rulerH.clientWidth || (this.viewportArea ? this.viewportArea.clientWidth - 20 : 800);
            const rhH = 20;
            if (this.rulerH.width !== Math.round(rwH * dpr) || this.rulerH.height !== Math.round(rhH * dpr)) {
                this.rulerH.width = Math.round(rwH * dpr);
                this.rulerH.height = Math.round(rhH * dpr);
            }
            this.ctxH.setTransform(dpr, 0, 0, dpr, 0, 0);

            // B. Vertical Ruler
            const rwV = 20;
            const rhV = this.rulerV.clientHeight || (this.viewportArea ? this.viewportArea.clientHeight - 20 : 600);
            if (this.rulerV.width !== Math.round(rwV * dpr) || this.rulerV.height !== Math.round(rhV * dpr)) {
                this.rulerV.width = Math.round(rwV * dpr);
                this.rulerV.height = Math.round(rhV * dpr);
            }
            this.ctxV.setTransform(dpr, 0, 0, dpr, 0, 0);

            // C. Canvas coordinate mapping
            const rectCanvas = this.stageTransform ? this.stageTransform.getBoundingClientRect() : { left: 20, top: 20, width: 1000, height: 1000 };
            const rectRulerH = this.rulerH.getBoundingClientRect();
            const rectRulerV = this.rulerV.getBoundingClientRect();

            const originX = rectCanvas.left - rectRulerH.left;
            const originY = rectCanvas.top - rectRulerV.top;
            const canvasPixelWidth = rectCanvas.width;
            const canvasPixelHeight = rectCanvas.height;

            // D. Render rulers
            this.renderHorizontalRuler(this.ctxH, rwH, rhH, originX, canvasPixelWidth, building.width, computedStyle);
            this.renderVerticalRuler(this.ctxV, rwV, rhV, originY, canvasPixelHeight, building.height, computedStyle);

            // E. Render hairlines
            if (this.cursorPos) {
                this.renderCursorIndicators(rectRulerH, rectRulerV, originX, originY, canvasPixelWidth, canvasPixelHeight, building);
            }
        },

        renderHorizontalRuler: function (ctx, width, height, originX, canvasPixelW, buildingW, style) {
            ctx.clearRect(0, 0, width, height);

            const rulerBg = style.getPropertyValue("--layout-ruler-bg").trim() || "#ffffff";
            const tickColor = style.getPropertyValue("--layout-ruler-tick").trim() || "#94a3b8";
            const textColor = style.getPropertyValue("--layout-ruler-text").trim() || "#64748b";
            const borderColor = style.getPropertyValue("--layout-border").trim() || "#e2e8f0";

            ctx.fillStyle = rulerBg;
            ctx.fillRect(0, 0, width, height);

            const ppm = canvasPixelW / buildingW;
            const lod = this.calculateLOD(ppm);

            ctx.font = "9px system-ui, -apple-system, sans-serif";
            ctx.fillStyle = textColor;
            ctx.strokeStyle = tickColor;
            ctx.lineWidth = 1.0;

            const minMeter = Math.floor((-originX) / (ppm * lod.sub)) * lod.sub;
            const maxMeter = Math.ceil((width - originX) / (ppm * lod.sub)) * lod.sub;

            ctx.beginPath();
            for (let m = minMeter; m <= maxMeter; m += lod.sub) {
                const px = originX + m * ppm;
                if (px < -10 || px > width + 10) continue;

                const isMajor = Math.abs(m % lod.major) < 1e-4 || Math.abs((m % lod.major) - lod.major) < 1e-4;
                const isMinor = Math.abs(m % lod.minor) < 1e-4 || Math.abs((m % lod.minor) - lod.minor) < 1e-4;
                const roundedPx = Math.round(px) + 0.5;

                if (isMajor) {
                    ctx.moveTo(roundedPx, height - 12);
                    ctx.lineTo(roundedPx, height);
                    const label = (Math.abs(m) < 1e-4 ? "0" : Math.round(m)) + "m";
                    ctx.fillText(label, roundedPx + 3, height - 8);
                } else if (isMinor) {
                    ctx.moveTo(roundedPx, height - 7);
                    ctx.lineTo(roundedPx, height);
                } else {
                    ctx.moveTo(roundedPx, height - 4);
                    ctx.lineTo(roundedPx, height);
                }
            }
            ctx.stroke();

            ctx.strokeStyle = borderColor;
            ctx.beginPath();
            ctx.moveTo(0, height - 0.5);
            ctx.lineTo(width, height - 0.5);
            ctx.stroke();
        },

        renderVerticalRuler: function (ctx, width, height, originY, canvasPixelH, buildingH, style) {
            ctx.clearRect(0, 0, width, height);

            const rulerBg = style.getPropertyValue("--layout-ruler-bg").trim() || "#ffffff";
            const tickColor = style.getPropertyValue("--layout-ruler-tick").trim() || "#94a3b8";
            const textColor = style.getPropertyValue("--layout-ruler-text").trim() || "#64748b";
            const borderColor = style.getPropertyValue("--layout-border").trim() || "#e2e8f0";

            ctx.fillStyle = rulerBg;
            ctx.fillRect(0, 0, width, height);

            const ppm = canvasPixelH / buildingH;
            const lod = this.calculateLOD(ppm);

            ctx.font = "8.5px system-ui, -apple-system, sans-serif";
            ctx.fillStyle = textColor;
            ctx.strokeStyle = tickColor;
            ctx.lineWidth = 1.0;

            const minMeter = Math.floor((-originY) / (ppm * lod.sub)) * lod.sub;
            const maxMeter = Math.ceil((height - originY) / (ppm * lod.sub)) * lod.sub;

            ctx.beginPath();
            for (let m = minMeter; m <= maxMeter; m += lod.sub) {
                const py = originY + m * ppm;
                if (py < -10 || py > height + 10) continue;

                const isMajor = Math.abs(m % lod.major) < 1e-4 || Math.abs((m % lod.major) - lod.major) < 1e-4;
                const isMinor = Math.abs(m % lod.minor) < 1e-4 || Math.abs((m % lod.minor) - lod.minor) < 1e-4;
                const roundedPy = Math.round(py) + 0.5;

                if (isMajor) {
                    ctx.moveTo(width - 12, roundedPy);
                    ctx.lineTo(width, roundedPy);

                    ctx.save();
                    ctx.translate(2, roundedPy + 9);
                    const label = (Math.abs(m) < 1e-4 ? "0" : Math.round(m)) + "m";
                    ctx.fillText(label, 0, 0);
                    ctx.restore();
                } else if (isMinor) {
                    ctx.moveTo(width - 7, roundedPy);
                    ctx.lineTo(width, roundedPy);
                } else {
                    ctx.moveTo(width - 4, roundedPy);
                    ctx.lineTo(width, roundedPy);
                }
            }
            ctx.stroke();

            ctx.strokeStyle = borderColor;
            ctx.beginPath();
            ctx.moveTo(width - 0.5, 0);
            ctx.lineTo(width - 0.5, height);
            ctx.stroke();
        },

        renderCursorIndicators: function (rectRulerH, rectRulerV, originX, originY, canvasW, canvasH, building) {
            const cursorRulerX = this.cursorPos.clientX - rectRulerH.left;
            const cursorRulerY = this.cursorPos.clientY - rectRulerV.top;

            const meterX = ((cursorRulerX - originX) / canvasW) * building.width;
            const meterY = ((cursorRulerY - originY) / canvasH) * building.height;

            // Horizontal indicator
            if (cursorRulerX >= 0 && cursorRulerX <= this.rulerH.clientWidth) {
                this.ctxH.save();
                this.ctxH.strokeStyle = "#ef4444";
                this.ctxH.lineWidth = 1.5;
                this.ctxH.beginPath();
                this.ctxH.moveTo(Math.round(cursorRulerX) + 0.5, 0);
                this.ctxH.lineTo(Math.round(cursorRulerX) + 0.5, 20);
                this.ctxH.stroke();

                this.ctxH.fillStyle = "rgba(239, 68, 68, 0.9)";
                this.ctxH.fillRect(cursorRulerX + 2, 2, 40, 12);
                this.ctxH.fillStyle = "#ffffff";
                this.ctxH.font = "bold 8.5px monospace";
                this.ctxH.fillText(meterX.toFixed(1) + "m", cursorRulerX + 4, 11);
                this.ctxH.restore();
            }

            // Vertical indicator
            if (cursorRulerY >= 0 && cursorRulerY <= this.rulerV.clientHeight) {
                this.ctxV.save();
                this.ctxV.strokeStyle = "#ef4444";
                this.ctxV.lineWidth = 1.5;
                this.ctxV.beginPath();
                this.ctxV.moveTo(0, Math.round(cursorRulerY) + 0.5);
                this.ctxV.lineTo(20, Math.round(cursorRulerY) + 0.5);
                this.ctxV.stroke();

                this.ctxV.fillStyle = "rgba(239, 68, 68, 0.9)";
                this.ctxV.fillRect(1, cursorRulerY + 2, 18, 11);
                this.ctxV.fillStyle = "#ffffff";
                this.ctxV.font = "bold 8px monospace";
                this.ctxV.fillText(Math.round(meterY) + "m", 2, cursorRulerY + 10);
                this.ctxV.restore();
            }
        },

        destroy: function () {
            if (this.viewportArea && this._onMouseMove) {
                this.viewportArea.removeEventListener("mousemove", this._onMouseMove);
                this.viewportArea.removeEventListener("mouseleave", this._onMouseLeave);
            }
            if (this.rafId) {
                cancelAnimationFrame(this.rafId);
                this.rafId = null;
            }
        }
    };

    // =========================================================================
    // SECTION 5: MINIMAP NAVIGATOR (2D CANVAS VIEWPORT SYNC & NAVIGATION)
    // =========================================================================

    const MinimapNavigator = {
        container: null,
        canvas: null,
        ctx: null,
        controller: null,
        badgeEl: null,
        toggleBtn: null,

        isDragging: false,
        dragOffset: { x: 0, y: 0 },
        isCollapsed: false,
        rafId: null,

        CSS_WIDTH: 160,
        CSS_HEIGHT: 110,
        PADDING: 6,

        metrics: {
            sm: 0.098,
            Ox: 31,
            Oy: 6,
            stageW: 1000,
            stageH: 1000,
            vx: 0,
            vy: 0,
            vw: 0,
            vh: 0
        },

        init: function (controller) {
            this.controller = controller || window.HseLayout;

            this.container = document.getElementById("layout-minimap-container") ||
                             document.getElementById("layout-minimap-card");
            this.canvas = document.getElementById("layout-minimap-canvas");

            if (!this.container || !this.canvas) {
                console.warn("[MinimapNavigator] Minimap elements not found.");
                return;
            }

            this.ctx = this.canvas.getContext("2d");
            this.badgeEl = document.getElementById("layout-minimap-scale-badge");
            this.toggleBtn = this.container.querySelector(".layout-minimap-toggle");

            this.calibrateRetina();
            this.bindEvents();
            this.requestRender();
            console.log("[MinimapNavigator] Initialized successfully.");
        },

        calibrateRetina: function () {
            if (!this.canvas) return;
            const dpr = window.devicePixelRatio || 1;
            this.canvas.width = Math.round(this.CSS_WIDTH * dpr);
            this.canvas.height = Math.round(this.CSS_HEIGHT * dpr);
            this.canvas.style.width = this.CSS_WIDTH + "px";
            this.canvas.style.height = this.CSS_HEIGHT + "px";

            if (this.ctx && typeof this.ctx.resetTransform === "function") {
                this.ctx.resetTransform();
            }
            if (this.ctx) {
                this.ctx.scale(dpr, dpr);
            }
        },

        bindEvents: function () {
            if (!this.canvas) return;

            this._onMouseDown = (e) => this.handleMouseDown(e);
            this._onMouseMove = (e) => this.handleMouseMove(e);
            this._onMouseUp = () => this.handleMouseUp();

            this.canvas.addEventListener("mousedown", this._onMouseDown);
            this.canvas.addEventListener("mousemove", this._onMouseMove);
            window.addEventListener("mouseup", this._onMouseUp);

            if (this.toggleBtn) {
                this.toggleBtn.onclick = (e) => {
                    e.stopPropagation();
                    this.toggleCollapse();
                };
            }

            this._onResize = () => {
                this.calibrateRetina();
                this.requestRender();
            };
            window.addEventListener("resize", this._onResize);
        },

        toggleCollapse: function () {
            this.isCollapsed = !this.isCollapsed;
            if (this.container) {
                this.container.classList.toggle("collapsed", this.isCollapsed);
            }
            if (this.toggleBtn) {
                this.toggleBtn.textContent = this.isCollapsed ? "+" : "_";
                this.toggleBtn.title = this.isCollapsed ? "Mở rộng Minimap" : "Thu gọn Minimap";
            }
            if (!this.isCollapsed) {
                this.requestRender();
            }
        },

        requestRender: function () {
            if (this.isCollapsed) return;
            if (this.rafId) return;

            this.rafId = requestAnimationFrame(() => {
                this.rafId = null;
                this.render();
            });
        },

        updateMetrics: function () {
            const viewport = document.getElementById("layout-stage-wrapper") ||
                             document.getElementById("layout-viewport-area");

            const Vw = (viewport && viewport.clientWidth) || 1000;
            const Vh = (viewport && viewport.clientHeight) || 800;

            const scale = (this.controller && this.controller.currentZoom) || 1.0;
            const Tx = (this.controller && this.controller.panOffset && this.controller.panOffset.x) || 0;
            const Ty = (this.controller && this.controller.panOffset && this.controller.panOffset.y) || 0;

            const Wu = this.CSS_WIDTH - 2 * this.PADDING;
            const Hu = this.CSS_HEIGHT - 2 * this.PADDING;
            const stageW = 1000;
            const stageH = 1000;

            const sm = Math.min(Wu / stageW, Hu / stageH);
            const Ox = this.PADDING + (Wu - stageW * sm) / 2;
            const Oy = this.PADDING + (Hu - stageH * sm) / 2;

            const vx = Ox - (Tx * sm) / scale;
            const vy = Oy - (Ty * sm) / scale;
            const vw = (Vw * sm) / scale;
            const vh = (Vh * sm) / scale;

            this.metrics = { sm, Ox, Oy, stageW, stageH, vx, vy, vw, vh, Vw, Vh, scale, Tx, Ty };
        },

        render: function () {
            if (!this.ctx || this.isCollapsed) return;

            this.updateMetrics();
            const { sm, Ox, Oy, vx, vy, vw, vh, scale } = this.metrics;
            const ctx = this.ctx;

            // Clear
            ctx.clearRect(0, 0, this.CSS_WIDTH, this.CSS_HEIGHT);

            // Bounds
            this.drawLayoutBounds(ctx, Ox, Oy, sm);

            // Plan elements
            const plan = this.getCurrentPlan();

            if (plan && plan.zones && plan.zones.length > 0) {
                this.drawZones(ctx, Ox, Oy, sm, plan.zones);
            }
            if (plan && plan.routes && plan.routes.length > 0) {
                this.drawRoutes(ctx, Ox, Oy, sm, plan.routes);
            }
            if (plan && plan.markers && plan.markers.length > 0) {
                this.drawMarkers(ctx, Ox, Oy, sm, plan.markers);
            }

            // Viewport box
            this.drawViewportIndicator(ctx, vx, vy, vw, vh);

            // Scale badge
            if (this.badgeEl) {
                this.badgeEl.textContent = `${Math.round(scale * 100)}%`;
            }
        },

        drawLayoutBounds: function (ctx, Ox, Oy, sm) {
            const w = 1000 * sm;
            const h = 1000 * sm;

            const isDark = document.documentElement.getAttribute("data-theme") !== "clean" &&
                           document.documentElement.getAttribute("data-theme") !== "light";

            ctx.fillStyle = isDark ? "#1b1e26" : "#ffffff";
            ctx.fillRect(Ox, Oy, w, h);

            // 5x5 Grid
            ctx.strokeStyle = isDark ? "rgba(255, 255, 255, 0.05)" : "rgba(0, 0, 0, 0.05)";
            ctx.lineWidth = 0.5;
            for (let i = 1; i < 5; i++) {
                const gx = Ox + (w * i) / 5;
                const gy = Oy + (h * i) / 5;
                ctx.beginPath();
                ctx.moveTo(gx, Oy); ctx.lineTo(gx, Oy + h);
                ctx.moveTo(Ox, gy); ctx.lineTo(Ox + w, gy);
                ctx.stroke();
            }

            ctx.strokeStyle = isDark ? "rgba(148, 163, 184, 0.35)" : "rgba(100, 116, 139, 0.35)";
            ctx.lineWidth = 1;
            ctx.strokeRect(Ox, Oy, w, h);
        },

        drawZones: function (ctx, Ox, Oy, sm, zones) {
            const PRESET_COLORS = {
                chemical: { fill: "rgba(234, 88, 12, 0.40)", stroke: "#ea580c" },
                hazard_high: { fill: "rgba(239, 68, 68, 0.40)", stroke: "#dc2626" },
                electrical: { fill: "rgba(99, 102, 241, 0.40)", stroke: "#4f46e5" },
                keep_clear: { fill: "rgba(234, 179, 8, 0.40)", stroke: "#ca8a04" },
                safe_zone: { fill: "rgba(22, 163, 74, 0.40)", stroke: "#16a34a" }
            };

            for (let i = 0; i < zones.length; i++) {
                const z = zones[i];
                const style = PRESET_COLORS[z.category || z.preset] || {
                    fill: z.color || "rgba(148, 163, 184, 0.3)",
                    stroke: z.color || "#94a3b8"
                };

                ctx.fillStyle = style.fill;
                ctx.strokeStyle = style.stroke;
                ctx.lineWidth = 0.8;

                if (z.type === "polygon" && Array.isArray(z.points) && z.points.length > 2) {
                    ctx.beginPath();
                    for (let pIdx = 0; pIdx < z.points.length; pIdx++) {
                        const px = Ox + z.points[pIdx].x * 1000 * sm;
                        const py = Oy + z.points[pIdx].y * 1000 * sm;
                        if (pIdx === 0) ctx.moveTo(px, py);
                        else ctx.lineTo(px, py);
                    }
                    ctx.closePath();
                    ctx.fill();
                    ctx.stroke();
                } else if (z.w && z.h) {
                    const zx = Ox + (z.x || 0) * 1000 * sm;
                    const zy = Oy + (z.y || 0) * 1000 * sm;
                    const zw = z.w * 1000 * sm;
                    const zh = z.h * 1000 * sm;
                    ctx.fillRect(zx, zy, zw, zh);
                    ctx.strokeRect(zx, zy, zw, zh);
                }
            }
        },

        drawRoutes: function (ctx, Ox, Oy, sm, routes) {
            ctx.lineCap = "round";
            ctx.lineJoin = "round";

            for (let i = 0; i < routes.length; i++) {
                const r = routes[i];
                if (!Array.isArray(r.points) || r.points.length < 2) continue;

                ctx.strokeStyle = (r.type === "secondary") ? "#0284c7" : "#16a34a";
                ctx.lineWidth = 1.6;

                ctx.beginPath();
                for (let pIdx = 0; pIdx < r.points.length; pIdx++) {
                    const rx = Ox + r.points[pIdx].x * 1000 * sm;
                    const ry = Oy + r.points[pIdx].y * 1000 * sm;
                    if (pIdx === 0) ctx.moveTo(rx, ry);
                    else ctx.lineTo(rx, ry);
                }
                ctx.stroke();
            }
        },

        drawMarkers: function (ctx, Ox, Oy, sm, markers) {
            const selectedId = this.controller && this.controller.selectedObjectId;

            for (let i = 0; i < markers.length; i++) {
                const m = markers[i];
                const mx = Ox + m.x * 1000 * sm;
                const my = Oy + m.y * 1000 * sm;
                const type = m.type || "";

                if (type.startsWith("ext_") || type.includes("abc") || type.includes("co2")) {
                    ctx.fillStyle = "#ef4444";
                    ctx.beginPath();
                    ctx.arc(mx, my, 2.0, 0, Math.PI * 2);
                    ctx.fill();
                } else if (type.includes("cabinet") || type.includes("hydrant") || type.includes("hose")) {
                    ctx.fillStyle = "#991b1b";
                    ctx.fillRect(mx - 1.8, my - 1.8, 3.6, 3.6);
                } else if (type.includes("bell") || type.includes("smoke") || type.includes("heat") || type.includes("alarm")) {
                    ctx.fillStyle = "#f59e0b";
                    ctx.beginPath();
                    ctx.arc(mx, my, 1.8, 0, Math.PI * 2);
                    ctx.fill();
                } else {
                    ctx.fillStyle = "#10b981";
                    ctx.beginPath();
                    ctx.arc(mx, my, 2.0, 0, Math.PI * 2);
                    ctx.fill();
                }

                if (m.id === selectedId) {
                    ctx.strokeStyle = "#38bdf8";
                    ctx.lineWidth = 1.2;
                    ctx.beginPath();
                    ctx.arc(mx, my, 4.2, 0, Math.PI * 2);
                    ctx.stroke();
                }
            }
        },

        drawViewportIndicator: function (ctx, vx, vy, vw, vh) {
            const rw = Math.max(6, vw);
            const rh = Math.max(6, vh);

            // Semi-transparent red fill
            ctx.fillStyle = "rgba(239, 68, 68, 0.18)";
            ctx.fillRect(vx, vy, rw, rh);

            // Red border
            ctx.strokeStyle = "rgba(220, 38, 38, 0.92)";
            ctx.lineWidth = 1.5;
            ctx.strokeRect(vx, vy, rw, rh);

            // Center crosshair
            const cx = vx + rw / 2;
            const cy = vy + rh / 2;
            ctx.strokeStyle = "rgba(220, 38, 38, 0.75)";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(cx - 3, cy); ctx.lineTo(cx + 3, cy);
            ctx.moveTo(cx, cy - 3); ctx.lineTo(cx, cy + 3);
            ctx.stroke();

            // Corner white brackets
            const bLen = Math.min(4, rw / 3, rh / 3);
            ctx.strokeStyle = "#ffffff";
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.moveTo(vx, vy + bLen); ctx.lineTo(vx, vy); ctx.lineTo(vx + bLen, vy);
            ctx.moveTo(vx + rw - bLen, vy); ctx.lineTo(vx + rw, vy); ctx.lineTo(vx + rw, vy + bLen);
            ctx.moveTo(vx + rw, vy + rh - bLen); ctx.lineTo(vx + rw, vy + rh); ctx.lineTo(vx + rw - bLen, vy + rh);
            ctx.moveTo(vx + bLen, vy + rh); ctx.lineTo(vx, vy + rh); ctx.lineTo(vx, vy + rh - bLen);
            ctx.stroke();
        },

        handleMouseDown: function (e) {
            if (!this.canvas) return;
            const rect = this.canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;

            this.isDragging = true;
            this.dragOffset = { x: 0, y: 0 };
            this.centerOnMinimapPoint(mx, my);
        },

        handleMouseMove: function (e) {
            if (!this.canvas) return;
            const rect = this.canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;

            const { Ox, Oy, sm } = this.metrics;

            if (!this.isDragging) {
                const isOverLayout = (mx >= Ox && mx <= Ox + 1000 * sm &&
                                      my >= Oy && my <= Oy + 1000 * sm);
                this.canvas.style.cursor = isOverLayout ? "pointer" : "default";
                return;
            }

            this.canvas.style.cursor = "move";
            this.centerOnMinimapPoint(mx, my);
        },

        handleMouseUp: function () {
            if (this.isDragging) {
                this.isDragging = false;
                if (this.canvas) this.canvas.style.cursor = "default";
            }
        },

        centerOnMinimapPoint: function (mx, my) {
            const { Ox, Oy, sm, Vw, Vh, scale } = this.metrics;
            if (!this.controller) return;

            const u = (mx - Ox) / (1000 * sm);
            const v = (my - Oy) / (1000 * sm);

            const clampedU = Math.max(-0.2, Math.min(1.2, u));
            const clampedV = Math.max(-0.2, Math.min(1.2, v));

            const Tx_new = Math.round(Vw / 2 - (clampedU * 1000) * scale);
            const Ty_new = Math.round(Vh / 2 - (clampedV * 1000) * scale);

            if (this.controller.viewportEngine) {
                this.controller.viewportEngine.setTransform({ scale, x: Tx_new, y: Ty_new });
            } else {
                this.controller.panOffset = { x: Tx_new, y: Ty_new };
                if (typeof this.controller.applyTransform === "function") {
                    this.controller.applyTransform();
                }
            }
            this.render();
        },

        getCurrentPlan: function () {
            if (!this.controller || !this.controller.state) return null;
            const state = this.controller.state;
            const planKey = state.currentPlan || "A";
            return (state.plans && state.plans[planKey]) || null;
        },

        destroy: function () {
            if (this.canvas && this._onMouseDown) {
                this.canvas.removeEventListener("mousedown", this._onMouseDown);
                this.canvas.removeEventListener("mousemove", this._onMouseMove);
            }
            if (this._onMouseUp) {
                window.removeEventListener("mouseup", this._onMouseUp);
            }
            if (this._onResize) {
                window.removeEventListener("resize", this._onResize);
            }
            if (this.rafId) {
                cancelAnimationFrame(this.rafId);
                this.rafId = null;
            }
            this.isDragging = false;
        }
    };

    // =========================================================================
    // SECTION 6: UNIFIED HSE LAYOUT CANVAS FACADE COORDINATOR
    // =========================================================================

    class HseLayoutCanvas {
        constructor(layoutController) {
            this.controller = layoutController || window.HseLayout;

            this.viewport = new HseViewportEngine({
                viewportEl: document.getElementById("layout-viewport-area"),
                stageEl: document.getElementById("layout-stage-wrapper"),
                transformEl: document.getElementById("layout-canvas-transform"),
                svgEl: document.getElementById("layout-svg-stage"),
                zoomBadge: document.getElementById("layout-zoom-val"),
                onTransformChange: (t) => {
                    // Update controller's currentZoom and panOffset
                    if (this.controller) {
                        this.controller.currentZoom = t.scale;
                        this.controller.panOffset = { x: t.x, y: t.y };
                    }
                    // Update Rulers
                    HseScaleRulerEngine.requestRender();
                    // Update Minimap
                    MinimapNavigator.requestRender();
                }
            });

            this.renderer = HseDualLayerRenderer;
            this.snap = HseSnapEngine;
            this.rulers = HseScaleRulerEngine;
            this.minimap = MinimapNavigator;
        }

        init() {
            this.viewport.bindEvents();
            this.renderer.init();
            this.rulers.init();
            this.minimap.init(this.controller);
            this.viewport.fitToScreen();
            console.log("[HseLayoutCanvas] All M2 modules initialized successfully.");
        }

        fitToScreen(padding) {
            this.viewport.fitToScreen(padding);
        }

        resetZoom() {
            this.viewport.resetZoom();
        }

        zoomIn(factor) {
            this.viewport.zoomIn(factor);
        }

        zoomOut(factor) {
            this.viewport.zoomOut(factor);
        }

        pan(dx, dy) {
            this.viewport.panCanvas(dx, dy);
        }

        setMode(mode) {
            this.viewport.setMode(mode);
        }

        renderBackground(force = true) {
            this.renderer.renderBackground(force);
            this.minimap.requestRender();
        }

        switchPlan(planId) {
            this.renderBackground(true);
            this.rulers.requestRender();
            this.minimap.requestRender();
        }

        destroy() {
            this.viewport.destroy();
            this.rulers.destroy();
            this.minimap.destroy();
            console.log("[HseLayoutCanvas] Cleaned up.");
        }
    }

    // Export globally to window
    window.HseViewportEngine = HseViewportEngine;
    window.HseDualLayerRenderer = HseDualLayerRenderer;
    window.HseSnapEngine = HseSnapEngine;
    window.HseScaleRulerEngine = HseScaleRulerEngine;
    window.MinimapNavigator = MinimapNavigator;
    window.HseLayoutCanvas = HseLayoutCanvas;

})(window, document);
