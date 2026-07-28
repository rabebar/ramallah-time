const CACHE="moeen-executive-v2";
const ASSETS=["/moeen-executive/","/static/moeen_exec/styles.css","/static/moeen_exec/premium.css","/static/moeen_exec/app.js","/moeen-executive/manifest.webmanifest","/static/moeen_exec/icon.svg","/static/moeen_exec/fonts/noto-kufi-400.woff2","/static/moeen_exec/fonts/noto-kufi-500.woff2","/static/moeen_exec/fonts/noto-kufi-700.woff2"];
self.addEventListener("install",event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)));
  self.skipWaiting();
});
self.addEventListener("activate",event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))));
  self.clients.claim();
});
self.addEventListener("fetch",event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=="GET"||url.pathname.startsWith("/moeen-executive/api/"))return;
  event.respondWith(fetch(event.request).then(response=>{
    const copy=response.clone();
    caches.open(CACHE).then(cache=>cache.put(event.request,copy));
    return response;
  }).catch(()=>caches.match(event.request).then(hit=>hit||caches.match("/moeen-executive/"))));
});
