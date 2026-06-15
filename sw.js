/**
 * RT Studio service worker.
 * Cache only the local app icons and leave all other requests to the browser.
 */

const CACHE_NAME = 'rt-studio-v1.5';
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

self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (error) {
    payload = { title: 'طلب جديد', body: event.data ? event.data.text() : '' };
  }

  const title = payload.title || 'طلب جديد';
  const options = {
    body: payload.body || 'وصل طلب جديد إلى متجرك.',
    icon: payload.icon || '/static/rt_logo_192.png',
    badge: payload.badge || '/static/rt_logo_192.png',
    tag: payload.tag || 'rt-studio-new-order',
    renotify: true,
    silent: false,
    vibrate: [180, 80, 180],
    data: {
      url: payload.url || '/admin?active_tab=orders',
      order_id: payload.order_id || null
    }
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = new URL(
    event.notification.data?.url || '/admin?active_tab=orders',
    self.location.origin
  ).href;

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url.startsWith(self.location.origin) && 'focus' in client) {
          if ('navigate' in client) {
            return client.navigate(targetUrl).then(() => client.focus());
          }
          return client.focus();
        }
      }
      return clients.openWindow ? clients.openWindow(targetUrl) : undefined;
    })
  );
});
