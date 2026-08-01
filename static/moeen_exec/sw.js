const CACHE="moeen-executive-v39";
const ASSETS=["/moeen-executive/","/static/moeen_exec/styles.css?v=39","/static/moeen_exec/premium.css?v=39","/static/moeen_exec/i18n.js?v=39","/static/moeen_exec/app.js?v=39","/moeen-executive/manifest.webmanifest","/static/moeen_exec/icon-64.png","/static/moeen_exec/icon-192.png","/static/moeen_exec/icon-512.png","/static/moeen_exec/apple-touch-icon.png","/static/moeen_exec/fonts/noto-kufi-400.woff2","/static/moeen_exec/fonts/noto-kufi-500.woff2","/static/moeen_exec/fonts/noto-kufi-700.woff2"];
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
self.addEventListener("push",event=>{
  let data={title:"مُعين",body:"لديك تذكير جديد.",url:"/moeen-executive/"};
  try{data={...data,...event.data.json()}}catch{}
  const silent=data.silent===true;
  const options={
    body:data.body,tag:data.tag,icon:data.icon||"/static/moeen_exec/icon-192.png",
    badge:data.badge||"/static/moeen_exec/icon-64.png",
    data:{url:data.url,title:data.title,body:data.body,kind:data.kind||""},
    renotify:!silent,silent,timestamp:Date.now()
  };
  if(!silent)options.vibrate=[180,90,180];
  event.waitUntil(self.registration.showNotification(data.title,options));
});
self.addEventListener("notificationclick",event=>{
  event.notification.close();
  const notificationData=event.notification.data||{};
  let url=notificationData.url||"/moeen-executive/";
  const isBroadcast=notificationData.kind==="broadcast"||String(event.notification.tag||"").startsWith("moeen-message-");
  const messageData=isBroadcast?{
      title:String(notificationData.title||"مُعين").slice(0,100),
      body:String(notificationData.body||"").slice(0,500)
    }:null;
  if(messageData){
    url=`/moeen-executive/#message=${encodeURIComponent(JSON.stringify(messageData))}`;
  }
  event.waitUntil((async()=>{
    const absoluteUrl=new URL(url,self.location.origin).href;
    const list=await clients.matchAll({type:"window",includeUncontrolled:true});
    for(const client of list){
      if(!("focus" in client))continue;
      let target=client;
      try{if("navigate" in client)target=await client.navigate(absoluteUrl)||client}catch{}
      if(messageData&&"postMessage" in target)target.postMessage({type:"MOEEN_OPEN_MESSAGE",message:messageData});
      return target.focus();
    }
    return clients.openWindow(absoluteUrl);
  })());
});
