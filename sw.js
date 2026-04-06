/**
 * RT Studio - Service Worker (sw.js)
 * مسؤول عن تحويل الموقع إلى تطبيق ويب (PWA) يعمل بكفاءة.
 */

const CACHE_NAME = 'rt-studio-v1.1'; // تم تحديث الإصدار لضمان التحديث
const ASSETS = [
  '/',
  '/static/uploads/rt_logo_192.png',
  '/static/uploads/rt_logo_512.png'
];

// 1. تثبيت العامل (Install): تخزين الملفات الأساسية في ذاكرة الهاتف
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('RT Studio: يتم الآن تخزين الملفات الأساسية...');
      return cache.addAll(ASSETS);
    })
  );
  // إجبار العامل الجديد على العمل فوراً
  self.skipWaiting();
});

// 2. التنشيط (Activate): حذف الكاش القديم عند صدور نسخة جديدة
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            console.log('RT Studio: يتم الآن حذف الكاش القديم:', cache);
            return caches.delete(cache);
          }
        })
      );
    })
  );
  // تفعيل السيطرة على العميل (المتصفح) فوراً
  return self.clients.claim();
});

// 3. جلب البيانات (Fetch): استراتيجية "الكاش أولاً" لسرعة التصفح
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      // إرجاع الملف من الكاش إذا وجد، وإلا جلبه من الإنترنت
      return response || fetch(event.request);
    })
  );
});