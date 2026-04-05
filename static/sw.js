const CACHE_NAME = 'rt-studio-v1';
const ASSETS = [
  '/',
  '/static/uploads/rt_logo_192.png',
  '/static/uploads/rt_logo_512.png'
];

// 1. تثبيت العامل وتخزين الملفات الأساسية
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS);
    })
  );
});

// 2. خدمة الملفات من الكاش إذا لم يوجد إنترنت
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
}); // ✅ تم تصحيح الإغلاق هنا