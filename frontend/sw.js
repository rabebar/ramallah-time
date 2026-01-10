const CACHE_NAME = "ramallah-time-v4"; // تم تغيير النسخة لفرض التحديث

// الملفات التي يتم تخزينها ليعمل الموقع بسرعة (الملفات الثابتة فقط)
const PRECACHE_URLS = [
  "/",
  "/static/style.css",
  "/static/ramallah.js"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.map(key => {
          if (key !== CACHE_NAME) return caches.delete(key);
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // --- الإصلاح الجوهري: أي طلب للـ API لا يتم تخزينه أبداً لضمان ظهور البيانات الجديدة فوراً ---
  if (url.pathname.startsWith("/api/")) {
    return; // اترك الطلب يذهب للسيرفر مباشرة دون تدخل من السيرفس وركر
  }

  // استراتيجية الملفات الثابتة: الكاش أولاً للسرعة
  if (PRECACHE_URLS.includes(url.pathname) || url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        return cached || fetch(event.request);
      })
    );
    return;
  }

  // استراتيجية الصفحات: الشبكة أولاً، وإذا لا يوجد إنترنت خذ من الكاش
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});