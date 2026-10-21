// ==============================================================================
// LUV-PDF PRIVATE SUITE - SERVICE WORKER (PWA & TRUE OFFLINE ENGINE)
// High-Performance Stale-While-Revalidate Architecture with Zero Cold-Start Latency
// ==============================================================================

const CACHE_NAME = "luv-pdf-offline-v2.1";

// Critical static assets for 100% offline standalone capability
const STATIC_PRECACHE_URLS = [
    "./",
    "./index.html",
    "./style.css",
    "./hse_style.css",
    "./legal_style.css",
    "./monthly_inventory.css",
    "./gatepass_studio.css",
    "./license_manager.css",
    "./app.js",
    "./vip_editor.js",
    "./ai_studio.js",
    "./hse_studio.js",
    "./legal_lookup.js",
    "./monthly_inventory.js",
    "./gatepass_studio.js",
    "./license_manager.js",
    "./libs/pdf.min.js",
    "./libs/chart.umd.min.js",
    "./manifest.json",
    "./icons/icon-192.png",
    "./icons/icon-512.png",
    "./icons/hse_avatar.jpg"
];

// 1. INSTALL LIFECYCLE: Pre-cache core shell
self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(async (cache) => {
            console.log("[ServiceWorker] Pre-caching core application shell...");
            for (const url of STATIC_PRECACHE_URLS) {
                try {
                    await cache.add(url);
                } catch (err) {
                    console.warn("[ServiceWorker] Failed to precache asset:", url, err);
                }
            }
        }).then(() => self.skipWaiting())
    );
});

// 2. ACTIVATE LIFECYCLE: Purge obsolete cache stores
self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((name) => {
                    if (name !== CACHE_NAME) {
                        console.log("[ServiceWorker] Deleting obsolete cache store:", name);
                        return caches.delete(name);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// 3. FETCH INTERCEPTOR: Intelligent Stale-While-Revalidate Strategy
self.addEventListener("fetch", (event) => {
    const req = event.request;
    const url = new URL(req.url);

    // Bypass non-GET requests (e.g. POST file uploads, API updates)
    if (req.method !== "GET") {
        return;
    }

    // Dynamic API Requests: Network-First with safe JSON fallback if offline
    if (url.pathname.startsWith("/api/")) {
        event.respondWith(
            fetch(req).catch(() => {
                return new Response(
                    JSON.stringify({
                        offline: true,
                        success: false,
                        message: "Hệ thống đang hoạt động ở chế độ Offline. Vui lòng kết nối mạng để sử dụng dịch vụ này."
                    }),
                    {
                        headers: { "Content-Type": "application/json; charset=utf-8" },
                        status: 503
                    }
                );
            })
        );
        return;
    }

    // App Navigation (HTML Page Load): Network-First falling back to cached index.html
    if (req.mode === "navigate") {
        event.respondWith(
            fetch(req)
                .then((networkResp) => {
                    if (networkResp && networkResp.status === 200) {
                        const copy = networkResp.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
                    }
                    return networkResp;
                })
                .catch(async () => {
                    console.log("[ServiceWorker] Serving cached application shell for navigation");
                    const cached = await caches.match("./index.html");
                    return cached || caches.match("./");
                })
        );
        return;
    }

    // Static Assets (CSS, JS, Fonts, Images, Icons): Stale-While-Revalidate
    event.respondWith(
        caches.match(req).then((cachedResponse) => {
            const fetchPromise = fetch(req)
                .then((networkResponse) => {
                    if (networkResponse && networkResponse.status === 200) {
                        const respClone = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(req, respClone));
                    }
                    return networkResponse;
                })
                .catch(() => cachedResponse);

            // Return cached response instantly (0ms), while background fetch updates the cache
            return cachedResponse || fetchPromise;
        })
    );
});
