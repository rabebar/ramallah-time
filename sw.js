/**
 * RT Studio service worker.
 * Cache only the local app icons and leave all other requests to the browser.
 */

const CACHE_NAME = 'rt-studio-v1.4';
const ASSETS = [
  '/static/rt_logo_192.png',
  '/static/rt_logo_512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => Promise.all(
      cacheNames
        .filter((cacheName) => cacheName !== CACHE_NAME)
        .map((cacheName) => caches.delete(cacheName))
    ))
  );
  return self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET' || event.request.mode === 'navigate') {
    return;
  }

  const requestUrl = new URL(event.request.url);
  if (requestUrl.origin !== self.location.origin || !ASSETS.includes(requestUrl.pathname)) {
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then((response) => response || fetch(event.request))
      .catch(() => Response.error())
  );
});
