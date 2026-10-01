// Minimal service worker for PWA installability + offline static shell.
// Strategy:
//   - same-origin static assets: cache-first (versioned cache, old caches purged on activate)
//   - /api/ requests: network-first, NEVER cached (tenant data must not persist in Cache Storage)
//   - everything else (cross-origin, etc.): network passthrough
const CACHE_NAME = "admin-dashboard-v1";
const STATIC_ASSETS = ["/", "/index.html", "/manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // API traffic: network-first, never cached.
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(request).catch(() =>
        new Response(JSON.stringify({ error: "offline" }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        })
      )
    );
    return;
  }

  // Only handle same-origin requests; let cross-origin go to network.
  if (url.origin !== self.location.origin) return;

  // Static assets: cache-first, then network (and populate cache on success).
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        if (response.ok && (request.destination === "document" || request.destination === "script" ||
            request.destination === "style" || request.destination === "image" || request.destination === "font")) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      });
    })
  );
});
