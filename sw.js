/**
 * RT Studio - Service Worker (sw.js)
 * مسؤول عن تحويل الموقع إلى تطبيق ويب (PWA) يعمل بكفاءة.
 */

const CACHE_NAME = 'rt-studio-v1.3';
const ASSETS = [
  '/static/rt_logo_192.png',
  '/static/rt_logo_512.png'
];

// 1. تثبيت العامل: تخزين الأصول الثابتة فقط (بدون /)
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('RT Studio: يتم الآن تخزين الملفات الأساسية...');
      return cache.addAll(ASSETS);
    })
  );
  self.skipWaiting();
});

// 2. التنشيط: حذف الكاش القديم
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            console.log('RT Studio: يتم حذف الكاش القديم:', cache);
            return caches.delete(cache);
          }
        })
      );
    })
  );
  return self.clients.claim();
});

// 3. جلب البيانات: تجاهل navigation requests تماماً
// هذا يضمن أن start_url في الـ manifest هو الذي يتحكم بصفحة الفتح
self.addEventListener('fetch', (event) => {
  // navigation requests (فتح صفحة) — لا تتدخل، دع المتصفح يتولى
  if (event.request.mode === 'navigate') {
    return;
  }

  // الأصول الثابتة فقط — كاش أولاً
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});