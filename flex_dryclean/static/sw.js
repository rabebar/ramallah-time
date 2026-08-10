const CACHE='flex-shell-v1';
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(['./static/app.css','./static/business.css','./static/app.js']))));
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('fetch',event=>{if(event.request.method==='GET'&&new URL(event.request.url).origin===location.origin){event.respondWith(fetch(event.request).catch(()=>caches.match(event.request)))}});
