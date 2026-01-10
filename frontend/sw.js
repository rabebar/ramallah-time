const CACHE_NAME = "ramallah-time-v3"; // تغيير النسخة لتحديث المتصفح
const PRECACHE_URLS = [
  "/",
  "/places",
  "/add-place",
  "/static/style.css",
  "/static/ramallah.js",
  "/manifest.json"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.map(k => (k !== CACHE_NAME ? caches.delete(k) : Promise.resolve())))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // --- الإصلاح: تجاهل روابط الـ API والروابط الخارجية ---
  if (url.pathname.startsWith("/api/") || !url.origin.includes(location.hostname)) {
    return; // لا تتدخل في هذه الطلبات واتركها للإنترنت العادي
  }

  // Cache-first للملفات الثابتة (CSS, JS)
  if (url.pathname.startsWith("/static/") || url.pathname === "/manifest.json") {
    event.respondWith(
      caches.match(req).then(cached => cached || fetch(req).then(res => {
        if (!res || res.status !== 200) return res;
        const copy = res.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(req, copy));
        return res;
      }))
    );
    return;
  }

  // Network-first للصفحات لضمان تحديث البيانات
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).then(res => {
        const copy = res.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(req, copy));
        return res;
      }).catch(() => caches.match(req).then(cached => cached || caches.match("/")))
    );
    return;
  }

  event.respondWith(fetch(req).catch(() => caches.match(req)));
});