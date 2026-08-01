const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const uiT=value=>window.MoeenI18n?.t(value)??value;
const uiLocale=()=>window.MoeenI18n?.locale||"ar-PS";
const speechLocale=()=>window.MoeenI18n?.speechLocale||"ar-PS";
let apiCsrf="";
const API_BASE="/moeen-executive";
const dataKinds=["memories","tasks","meetings","contacts"];
let secureState={memories:[],tasks:[],meetings:[],contacts:[],_deleted:{}};
let vaultKey=null,syncVersion=0,syncTimer=null,syncBusy=false;
function installPullToRefresh(){
  if(!("ontouchstart" in window))return;
  const indicator=document.createElement("div");
  indicator.className="pull-refresh";
  indicator.setAttribute("aria-hidden","true");
  indicator.textContent="اسحب للتحديث";
  document.body.appendChild(indicator);
  let startX=0,startY=0,pulling=false,ready=false;
  document.addEventListener("touchstart",event=>{
    if(window.scrollY>0||event.touches.length!==1||event.target.closest("dialog,input,textarea,select"))return;
    startX=event.touches[0].clientX;startY=event.touches[0].clientY;pulling=true;ready=false;
  },{passive:true});
  document.addEventListener("touchmove",event=>{
    if(!pulling||event.touches.length!==1)return;
    const dx=Math.abs(event.touches[0].clientX-startX),dy=event.touches[0].clientY-startY;
    if(dy<=0||dx>dy){pulling=false;indicator.classList.remove("visible","ready");return}
    const distance=Math.min(dy,120);
    ready=distance>=82;
    indicator.classList.toggle("visible",distance>18);
    indicator.classList.toggle("ready",ready);
    indicator.textContent=ready?"اترك للتحديث":"اسحب للتحديث";
    indicator.style.setProperty("--pull",`${distance}px`);
  },{passive:true});
  document.addEventListener("touchend",()=>{
    if(!pulling)return;
    pulling=false;
    if(ready){indicator.textContent="جارٍ التحديث…";indicator.classList.add("loading");location.reload();return}
    indicator.classList.remove("visible","ready");indicator.style.removeProperty("--pull");
  },{passive:true});
}
installPullToRefresh();
const trustedKeyStore={
  async open(){return new Promise((resolve,reject)=>{const r=indexedDB.open("moeen_exec_trusted_device",1);r.onupgradeneeded=()=>r.result.createObjectStore("session");r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)})},
  async save(scope,key){const db=await this.open();return new Promise((resolve,reject)=>{const q=db.transaction("session","readwrite").objectStore("session").put({scope,key},"vault");q.onsuccess=()=>resolve();q.onerror=()=>reject(q.error)})},
  async load(scope){const db=await this.open();return new Promise((resolve,reject)=>{const q=db.transaction("session").objectStore("session").get("vault");q.onsuccess=()=>resolve(q.result?.scope===scope?q.result.key:null);q.onerror=()=>reject(q.error)})},
  async clear(){const db=await this.open();return new Promise(resolve=>{const q=db.transaction("session","readwrite").objectStore("session").delete("vault");q.onsuccess=()=>resolve();q.onerror=()=>resolve()})}
};
let installPrompt=null;
function urlBase64ToUint8Array(value){
  const padding="=".repeat((4-value.length%4)%4),base64=(value+padding).replace(/-/g,"+").replace(/_/g,"/");
  return Uint8Array.from(atob(base64),c=>c.charCodeAt(0));
}
async function enableMoeenPush(){
  const status=$("#moeenPushStatus"),button=$("#enableMoeenPush");
  if(!("serviceWorker" in navigator)||!("PushManager" in window)||!("Notification" in window)){status.textContent="هذا المتصفح لا يدعم الإشعارات الخلفية.";return}
  try{
    const permission=await Notification.requestPermission();
    if(permission!=="granted"){status.textContent="لم يتم السماح بالإشعارات من إعدادات الجهاز.";return}
    const config=await api("/api/push/config");
    if(!config.configured)throw new Error("NOT_CONFIGURED");
    const registration=await navigator.serviceWorker.ready;
    let subscription=await registration.pushManager.getSubscription();
    if(!subscription)subscription=await registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:urlBase64ToUint8Array(config.public_key)});
    await api("/api/push/subscribe",{method:"POST",body:JSON.stringify({...subscription.toJSON(),locale:uiLocale().startsWith("en")?"en":"ar"})});
    await refreshMoeenPushStatus();
  }catch{status.textContent="تعذر تفعيل الإشعارات. تحقق من إعدادات المتصفح ثم حاول مجددًا."}
}
$("#enableMoeenPush").onclick=enableMoeenPush;
async function refreshMoeenPushStatus(){
  const status=$("#moeenPushStatus"),button=$("#enableMoeenPush"),testButton=$("#testMoeenPush");
  if(!status||!button||!testButton)return false;
  if(!("serviceWorker" in navigator)||!("PushManager" in window)||!("Notification" in window)){
    status.textContent="هذا المتصفح لا يدعم الإشعارات الخلفية.";button.disabled=true;testButton.hidden=true;return false;
  }
  if(Notification.permission==="denied"){
    status.textContent="الإشعارات محظورة من إعدادات الجهاز. اسمح بها من إعدادات الموقع.";button.textContent="الإشعارات محظورة";testButton.hidden=true;return false;
  }
  if(Notification.permission!=="granted"){
    status.textContent="الإشعارات غير مفعّلة على هذا الجهاز.";button.textContent="تفعيل الإشعارات على هذا الجهاز";testButton.hidden=true;return false;
  }
  const registration=await navigator.serviceWorker.ready;
  const subscription=await registration.pushManager.getSubscription();
  if(!subscription){
    status.textContent="يحتاج هذا الجهاز إلى إعادة ربط الإشعارات.";button.textContent="إعادة تفعيل الإشعارات";testButton.hidden=true;return false;
  }
  await api("/api/push/subscribe",{method:"POST",body:JSON.stringify({...subscription.toJSON(),locale:uiLocale().startsWith("en")?"en":"ar"})});
  const serverStatus=await api("/api/push/status");
  if(!serverStatus.configured)throw new Error("NOT_CONFIGURED");
  status.textContent="الإشعارات مفعّلة ومتصلة بهذا الحساب.";
  button.textContent="الإشعارات مفعّلة";
  testButton.hidden=false;
  return true;
}
$("#testMoeenPush").onclick=async()=>{
  const button=$("#testMoeenPush"),status=$("#moeenPushStatus");
  button.disabled=true;status.textContent="جارٍ إرسال إشعار تجريبي…";
  try{
    const registration=await navigator.serviceWorker.ready;
    const subscription=await registration.pushManager.getSubscription();
    if(!subscription)throw new Error("NO_ACTIVE_SUBSCRIPTIONS");
    await api("/api/push/test",{method:"POST",body:JSON.stringify({endpoint:subscription.endpoint})});
    status.textContent="تم إرسال الإشعار التجريبي. يفترض أن يظهر خلال لحظات.";
  }catch(error){
    status.textContent=error.message==="NO_ACTIVE_SUBSCRIPTIONS"
      ?"لم يعد اشتراك هذا الجهاز صالحًا. أعد تفعيل الإشعارات."
      :"تعذر إرسال الإشعار التجريبي الآن.";
  }finally{button.disabled=false}
};
async function syncReminder(itemId,itemType,eventAt,offsetMinutes){
  if(!eventAt||offsetMinutes==="none")return api(`/api/reminders/${encodeURIComponent(itemId)}`,{method:"DELETE",body:"{}"}).catch(()=>{});
  const remindAt=new Date(new Date(eventAt).getTime()-Number(offsetMinutes)*60000);
  if(Number.isNaN(remindAt.getTime()))return;
  return api(`/api/reminders/${encodeURIComponent(itemId)}`,{method:"PUT",body:JSON.stringify({item_type:itemType,remind_at:remindAt.toISOString()})}).catch(()=>{});
}
function reminderPayload(){
  const reminders=[];
  const add=(item,itemType,eventAt)=>{
    if(!item?.id||item.done||!eventAt||item.reminder==="none")return;
    const offset=Number(item.reminder??0),remindAt=new Date(new Date(eventAt).getTime()-offset*60000);
    if(Number.isNaN(remindAt.getTime()))return;
    reminders.push({item_id:item.id,item_type:itemType,remind_at:remindAt.toISOString()});
  };
  secureState.tasks.forEach(item=>add(item,item.itemType==="call"?"call":"task",item.due));
  secureState.meetings.forEach(item=>add(item,"meeting",item.date));
  return reminders;
}
async function reconcileReminders(){
  if(!vaultKey||!navigator.onLine)return;
  await api("/api/reminders/reconcile",{method:"POST",body:JSON.stringify({reminders:reminderPayload()})});
}
const installButtons=()=>[$("#authInstallBtn"),$("#headerInstallBtn")].filter(Boolean);
function isInstalled(){return window.matchMedia("(display-mode: standalone)").matches||window.navigator.standalone===true}
function refreshInstallButtons(){const installed=isInstalled();installButtons().forEach(button=>button.hidden=installed)}
window.addEventListener("beforeinstallprompt",event=>{event.preventDefault();installPrompt=event;refreshInstallButtons()});
window.addEventListener("appinstalled",()=>{installPrompt=null;refreshInstallButtons()});
async function installMoeen(){
  if(isInstalled()){alert("مُعين مثبت بالفعل على هذا الجهاز.");return}
  if(installPrompt){installPrompt.prompt();await installPrompt.userChoice;installPrompt=null;refreshInstallButtons();return}
  const ios=/iPhone|iPad|iPod/i.test(navigator.userAgent);
  alert(ios
    ?"على iPhone: اضغط زر المشاركة في Safari، ثم اختر «إضافة إلى الشاشة الرئيسية»، وبعدها اضغط «إضافة»."
    :"من قائمة المتصفح اختر «تثبيت التطبيق» أو «إضافة إلى الشاشة الرئيسية».");
}
installButtons().forEach(button=>button.onclick=installMoeen);
refreshInstallButtons();
const store={
  get:(k)=>secureState[k]||[],
  set:(k,v)=>{
    const previous=secureState[k]||[],stamp=new Date().toISOString(),oldById=new Map(previous.map(x=>[x.id,x]));
    const next=v.map(item=>{
      const old=oldById.get(item.id),cleanOld=old?JSON.stringify({...old,_updated:undefined}):"",cleanNew=JSON.stringify({...item,_updated:undefined});
      return {...item,_updated:old&&cleanOld===cleanNew?old._updated:(item._updated||stamp)};
    });
    const nextIds=new Set(next.map(x=>x.id));secureState._deleted=secureState._deleted||{};secureState._deleted[k]=secureState._deleted[k]||{};
    previous.filter(x=>!nextIds.has(x.id)).forEach(x=>secureState._deleted[k][x.id]=stamp);
    secureState[k]=next;scheduleSecureSave();
  }
};
let mediaRecorder, chunks=[], audioBlob=null, recognition=null;
let audioStream=null,audioMimeType="",audioStopRequested=false,audioRestartTimer=null;
let dictationActive=false,dictationStopRequested=false,dictationRestartTimer=null,dictationLastError="";
const CAPTURE_LIMIT_SECONDS=120;
let captureTimer=null,captureDeadline=0,captureMode=null,captureLimitReached=false,captureWarned=false;
let fieldRecognition=null, activeMic=null;
let renewalPollTimer=null,subscriptionGuardTimer=null,subscriptionDeadlineTimer=null;
let currentProfile=null,currentSubscription=null,subscriptionCheckBusy=false;
let activityLastSent=0,activitySendBusy=false;
const ACTIVITY_INTERVAL=5*60*1000;
const fmt=d=>new Intl.DateTimeFormat(uiLocale(),{dateStyle:"medium"}).format(new Date(d));
const fmtDateTime=d=>new Intl.DateTimeFormat(uiLocale(),{dateStyle:"medium",timeStyle:"short"}).format(new Date(d));
const esc=s=>(s||"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
function showNotificationMessage(message){
  try{
    $("#notificationDialogLabel").textContent=uiLocale().startsWith("en")?"Message from Moeen":"رسالة من مُعين";
    $("#notificationDialogTitle").textContent=String(message.title||"مُعين").slice(0,100);
    $("#notificationDialogBody").textContent=String(message.body||"").slice(0,500);
    $("#notificationDialogClose").textContent=uiLocale().startsWith("en")?"Read":"تمت القراءة";
    if(!$("#notificationDialog").open)$("#notificationDialog").showModal();
  }catch{}
}
function openNotificationFromHash(){
  if(!location.hash.startsWith("#message="))return;
  try{showNotificationMessage(JSON.parse(decodeURIComponent(location.hash.slice(9))))}catch{}
  history.replaceState(null,"",`${location.pathname}${location.search}`);
}
window.addEventListener("hashchange",openNotificationFromHash);
if("serviceWorker" in navigator){
  navigator.serviceWorker.addEventListener("message",event=>{
    if(event.data?.type==="MOEEN_OPEN_MESSAGE"&&event.data.message)showNotificationMessage(event.data.message);
  });
}
openNotificationFromHash();
function eventVisualState(value,done=false){
  if(done||!value)return{className:"",badge:""};
  const eventTime=new Date(value).getTime(),difference=eventTime-Date.now();
  if(Number.isNaN(eventTime))return{className:"",badge:""};
  if(difference<=0)return{className:"event-due",badge:uiT("حان الآن")};
  if(difference<=60*60*1000)return{className:"event-soon",badge:uiT("خلال ساعة")};
  if(difference<=24*60*60*1000)return{className:"event-today",badge:uiT("اليوم")};
  return{className:"",badge:""};
}
const eventBadge=state=>state.badge?`<span class="event-status">${state.badge}</span>`:"";
function setView(id){$$(".view,.nav").forEach(x=>x.classList.remove("active"));$("#"+id).classList.add("active");$(`.nav[data-view="${id}"]`).classList.add("active");render();installVoiceFields();}
$$(".nav").forEach(b=>b.onclick=()=>setView(b.dataset.view));$$("[data-view-jump]").forEach(b=>b.onclick=()=>setView(b.dataset.viewJump));
async function shareMoeenRegistration(){
  const english=uiLocale().startsWith("en");
  const url=new URL("/moeen-executive/register",window.location.origin).href;
  const title=english?"Moeen — Your Executive Assistant":"مُعين — مساعدك التنفيذي";
  const text=english
    ?"Moeen helps organize appointments, notes, meetings, contacts, and follow-ups. Start your free trial:"
    :"مُعين مساعد شخصي لتنظيم المواعيد والملاحظات والاجتماعات والاتصالات والمتابعات. ابدأ تجربتك المجانية:";
  const status=$("#shareMoeenStatus");
  if(status)status.textContent="";
  try{
    if(navigator.share){
      await navigator.share({title,text,url});
      if(status)status.textContent=english?"Registration link shared.":"تمت مشاركة رابط التسجيل.";
      return;
    }
    if(navigator.clipboard?.writeText)await navigator.clipboard.writeText(`${text}\n${url}`);
    else{
      const area=document.createElement("textarea");
      area.value=`${text}\n${url}`;area.style.position="fixed";area.style.opacity="0";
      document.body.appendChild(area);area.select();document.execCommand("copy");area.remove();
    }
    if(status)status.textContent=english?"Registration link copied.":"تم نسخ رابط التسجيل.";
  }catch(err){
    if(err?.name==="AbortError")return;
    if(status)status.textContent=english?"Could not share the link. Please try again.":"تعذرت مشاركة الرابط. حاول مجددًا.";
  }
}
$("#shareMoeenApp").onclick=shareMoeenRegistration;
const now=new Date();$("#date").textContent=new Intl.DateTimeFormat(uiLocale(),{weekday:"long",day:"numeric",month:"long",year:"numeric"}).format(now);
const hour=now.getHours();
const timeGreeting=hour>=5&&hour<12?"صباح الخير":hour>=12&&hour<17?"طاب يومك":hour>=17&&hour<23?"مساء الخير":"أهلًا بعودتك";
$("#greeting").textContent=uiT(timeGreeting);
function applyProfile(profile){
  if(!profile)return;
  currentProfile=profile;
  const label=[profile.title,profile.name].filter(Boolean).join(" ");
  $("#greeting").textContent=`${uiT(timeGreeting)}${window.MoeenI18n?.language==="en"?", ":"، "}${label}`;
}
function applySubscription(subscription){
  currentSubscription=subscription||null;
  const alert=$("#subscriptionAlert");
  if(!alert||!subscription||subscription.hours_left==null){if(alert)alert.hidden=true;return}
  const hours=Number(subscription.hours_left),isTrial=subscription.plan_type==="trial";
  if(hours>168||(isTrial&&hours>24)){alert.hidden=true;return}
  const timing=hours<=24?`${Math.max(1,Math.ceil(hours))} ساعة`:`${Math.max(1,Math.ceil(hours/24))} أيام`;
  alert.innerHTML=`<strong>${isTrial?"تنتهي تجربتك المجانية":"ينتهي اشتراكك"} خلال ${timing}</strong> · اضغط لعرض خيارات التجديد والدفع.`;
  alert.hidden=false;
}
$("#subscriptionAlert").onclick=()=>setView("subscription");
function stopSubscriptionGuard(){
  if(subscriptionGuardTimer)clearInterval(subscriptionGuardTimer);
  if(subscriptionDeadlineTimer)clearTimeout(subscriptionDeadlineTimer);
  subscriptionGuardTimer=null;subscriptionDeadlineTimer=null;subscriptionCheckBusy=false;
}
function armSubscriptionDeadline(){
  if(subscriptionDeadlineTimer)clearTimeout(subscriptionDeadlineTimer);
  const deadline=new Date(currentSubscription?.ends_at||"").getTime();
  if(!Number.isFinite(deadline))return;
  const remaining=deadline-Date.now();
  if(remaining<=0){enterRenewalMode(currentProfile,{...currentSubscription,hours_left:0});return}
  subscriptionDeadlineTimer=setTimeout(armSubscriptionDeadline,Math.min(remaining+500,24*60*60*1000));
}
async function verifySubscriptionAccess(){
  if(subscriptionCheckBusy||document.body.classList.contains("locked")||document.body.classList.contains("renewal-only"))return;
  subscriptionCheckBusy=true;
  try{
    const status=await api("/api/auth/status");
    if(!status.authenticated){
      stopSubscriptionGuard();vaultKey=null;secureState=emptyState();apiCsrf="";
      document.body.classList.add("locked");$("#loginPane").hidden=false;
      $("#authMessage").textContent="انتهت الجلسة أو تم إيقاف الحساب. سجّل الدخول مجددًا.";
      return;
    }
    apiCsrf=status.csrf||apiCsrf;applyProfile(status.profile);applySubscription(status.subscription);
    if(status.renewal_only){enterRenewalMode(status.profile,status.subscription);return}
    armSubscriptionDeadline();
  }catch{
    const deadline=new Date(currentSubscription?.ends_at||"").getTime();
    if(Number.isFinite(deadline)&&deadline<=Date.now())enterRenewalMode(currentProfile,{...currentSubscription,hours_left:0});
  }finally{subscriptionCheckBusy=false}
}
function startSubscriptionGuard(subscription){
  stopSubscriptionGuard();currentSubscription=subscription||currentSubscription;
  armSubscriptionDeadline();
  if(document.body.classList.contains("renewal-only"))return;
  subscriptionGuardTimer=setInterval(verifySubscriptionAccess,60000);
}
function enterRenewalMode(profile,subscription){
  if(document.body.classList.contains("renewal-only"))return;
  stopSubscriptionGuard();
  applyProfile(profile);applySubscription(subscription);
  vaultKey=null;secureState=emptyState();
  document.body.classList.remove("locked");document.body.classList.add("renewal-only");
  setView("subscription");
  const message=$("#paymentMessage");
  if(message&&!message.textContent)message.textContent="انتهى اشتراكك. بياناتك محفوظة ومقفلة حتى اعتماد التجديد.";
  clearInterval(renewalPollTimer);
  renewalPollTimer=setInterval(async()=>{
    try{
      const status=await api("/api/auth/status");
      if(status.authenticated&&!status.renewal_only)location.reload();
    }catch{}
  },30000);
}

function render(){
  const memories=store.get("memories"),tasks=store.get("tasks"),meetings=store.get("meetings");
  const open=tasks.filter(t=>!t.done), today=new Date().toISOString().slice(0,10);
  $("#openTasks").textContent=open.length;$("#dueTasks").textContent=open.filter(t=>t.due===today).length;$("#memoryCount").textContent=memories.length;
  $("#dailyLine").textContent=open.length?`لديك ${open.length} متابعة مفتوحة. ركّز على الأكثر إلحاحًا أولًا.`:"جدول المتابعة هادئ. سجّل ما يستحق التذكر.";
  renderHomeAlerts(tasks,meetings);
  $("#todayTasks").innerHTML=open.slice(0,4).map(taskRow).join("")||'<div class="empty">لا توجد متابعات بعد.</div>';
  $("#recentMemories").innerHTML=memories.slice(0,3).map(m=>`<div class="card-top"><div><b>${esc(m.title)}</b><div class="meta">${fmt(m.created)}</div></div><span class="tag">ملاحظة</span></div>`).join("")||'<div class="empty">ذاكرتك جاهزة لأول ملاحظة.</div>';
  renderMemories();$("#taskList").innerHTML=tasks.map(taskCard).join("")||'<div class="empty">أضف أول متابعة أو التزام.</div>';
  $("#meetingList").innerHTML=meetings.map(meetingCard).join("")||'<div class="empty">سجّل اجتماعك الأول.</div>';
  renderContacts();
  bindAudioPlayers();
  if($("#security").classList.contains("active"))loadSecurity();
}
setInterval(()=>{if(!document.body.classList.contains("locked"))render()},60000);
function renderHomeAlerts(tasks,meetings){
  const taskEvents=tasks.filter(item=>!item.done&&item.due).map(item=>({...item,eventAt:item.due,view:"tasks",kind:item.itemType==="call"?"اتصال":"متابعة"}));
  const meetingEvents=meetings.filter(item=>!item.done&&item.date).map(item=>({...item,eventAt:item.date,view:"meetings",kind:"اجتماع"}));
  const events=[...taskEvents,...meetingEvents]
    .filter(item=>eventVisualState(item.eventAt).badge)
    .sort((a,b)=>new Date(a.eventAt)-new Date(b.eventAt));
  const panel=$("#homeAlerts");
  if(!events.length){panel.hidden=true;return}
  const dueCount=events.filter(item=>new Date(item.eventAt)<=new Date()).length;
  $("#homeAlertsTitle").textContent=dueCount?`لديك ${dueCount} حدث حان موعده`:"مواعيد وتنبيهات اليوم";
  $("#homeAlertsCount").textContent=`${events.length} تنبيه`;
  $("#homeAlertsList").innerHTML=events.slice(0,4).map(item=>{
    const state=eventVisualState(item.eventAt);
    return `<button type="button" class="home-alert-item ${state.className}" data-action="set-view" data-view-target="${esc(item.view)}"><span class="home-alert-kind">${item.kind}</span><span class="home-alert-content"><strong>${esc(item.title)}</strong><small>${fmtDateTime(item.eventAt)}${item.person||item.people?` · ${esc(item.person||item.people)}`:""}</small></span>${eventBadge(state)}<b aria-hidden="true">←</b></button>`;
  }).join("");
  panel.hidden=false;
}
function taskRow(t){const state=eventVisualState(t.due,t.done);return `<div class="card-top event-row ${state.className} ${t.done?"done":""}"><div><b>${esc(t.title)}</b><div class="meta">${t.due?fmtDateTime(t.due):"بلا موعد"} · ${esc(t.person||"")}</div>${eventBadge(state)}</div><button class="icon-btn" data-action="toggle-task" data-id="${esc(t.id)}">${t.done?"↩":"✓"}</button></div>`}
function taskCard(t){const state=eventVisualState(t.due,t.done);return `<article class="card event-card ${state.className} ${t.done?"done":""}"><div class="card-top"><div><h3>${esc(t.title)}</h3><div class="meta"><span>${t.due?fmtDateTime(t.due):"بلا موعد"}</span><span>${esc(t.person||"")}</span></div>${eventBadge(state)}</div><div class="card-actions"><button class="icon-btn share-btn" data-action="share" data-kind="tasks" data-id="${esc(t.id)}">مشاركة</button><button class="icon-btn" data-action="toggle-task" data-id="${esc(t.id)}">${t.done?"إعادة":"تم"}</button><button class="icon-btn" data-action="remove" data-kind="tasks" data-id="${esc(t.id)}">حذف</button></div></div><p>${esc(t.notes||"")}</p>${t.audioId?`<audio controls data-audio="${esc(t.audioId)}"></audio>`:""}</article>`}
function meetingCard(m){const state=eventVisualState(m.date,m.done);return `<article class="card event-card ${state.className} ${m.done?"done":""}"><div class="card-top"><div><h3>${esc(m.title)}</h3><div class="meta">${fmtDateTime(m.date)} · ${esc(m.people||"")}</div>${eventBadge(state)}</div><div class="card-actions"><button class="icon-btn share-btn" data-action="share" data-kind="meetings" data-id="${esc(m.id)}">مشاركة</button><button class="icon-btn" data-action="toggle-meeting" data-id="${esc(m.id)}">${m.done?"إعادة":"تم الاجتماع"}</button><button class="icon-btn" data-action="remove" data-kind="meetings" data-id="${esc(m.id)}">حذف</button></div></div><p>${esc(m.notes||"")}</p>${m.audioId?`<audio controls data-audio="${esc(m.audioId)}"></audio>`:""}</article>`}
function renderContacts(){
  if(!$("#contactList"))return;
  const q=($("#contactSearch")?.value||"").toLowerCase();
  const list=store.get("contacts").filter(c=>(`${c.name} ${c.role} ${c.org} ${c.phone} ${c.email}`).toLowerCase().includes(q));
  $("#contactList").innerHTML=list.map(c=>`<article class="contact-card"><div class="contact-head"><div class="contact-avatar">${esc((c.name||"؟").trim()[0])}</div><div><h3>${esc(c.name)}</h3><p>${esc([c.role,c.org].filter(Boolean).join(" · "))}</p></div></div><div class="contact-details">${c.phone?`<a href="tel:${esc(c.phone)}">☎ ${esc(c.phone)}</a>`:""}${c.email?`<a href="mailto:${esc(c.email)}">✉ ${esc(c.email)}</a>`:""}${c.notes?`<p>${esc(c.notes)}</p>`:""}${c.audioId?`<audio controls data-audio="${esc(c.audioId)}"></audio>`:""}</div><div class="contact-actions">${c.phone?`<a class="call" href="tel:${esc(c.phone)}">اتصال الآن</a>`:""}${c.email?`<a href="mailto:${esc(c.email)}">إرسال بريد</a>`:""}<button data-action="add-call-task" data-id="${esc(c.id)}">تذكير بالاتصال</button><button data-action="remove" data-kind="contacts" data-id="${esc(c.id)}">حذف</button></div></article>`).join("")||'<div class="empty">أضف أول جهة اتصال إلى دليلك الشخصي.</div>';
}
function renderMemories(){
  const q=($("#search").value||"").toLowerCase(), list=store.get("memories").filter(m=>(m.title+" "+m.text).toLowerCase().includes(q));
  $("#memories").innerHTML=list.map(m=>`<article class="card"><div class="card-top"><div><h3>${esc(m.title)}</h3><div class="meta">${fmt(m.created)} · ${m.hasAudio?"صوت ونص":"نص"}</div></div><div class="card-actions"><button class="icon-btn share-btn" data-action="share" data-kind="memories" data-id="${esc(m.id)}">مشاركة</button><button class="icon-btn" data-action="remove-memory" data-id="${esc(m.id)}">حذف</button></div></div><p>${esc(m.text)}</p>${m.hasAudio?`<audio controls data-audio="${esc(m.id)}"></audio>`:""}</article>`).join("")||'<div class="empty">لا توجد نتائج.</div>';
  $$("audio[data-audio]").forEach(async a=>{const blob=await audioDb.get(a.dataset.audio);if(blob)a.src=URL.createObjectURL(blob)});
}
document.addEventListener("click",event=>{
  const control=event.target.closest("[data-action]");
  if(!control)return;
  const action=control.dataset.action,id=control.dataset.id,kind=control.dataset.kind;
  if(action==="set-view")setView(control.dataset.viewTarget);
  else if(action==="toggle-task")toggleTask(id);
  else if(action==="toggle-meeting")toggleMeeting(id);
  else if(action==="share")shareWhatsApp(kind,id);
  else if(action==="remove")removeItem(kind,id);
  else if(action==="remove-memory")removeMemory(id);
  else if(action==="add-call-task")addCallTask(id);
  else if(action==="revoke-device")revokeDevice(id);
});
function bindAudioPlayers(){$$("audio[data-audio]").forEach(async a=>{if(a.src)return;const blob=await audioDb.get(a.dataset.audio);if(blob)a.src=URL.createObjectURL(blob)})}
$("#search").oninput=renderMemories;
window.toggleTask=id=>{let a=store.get("tasks"),t=a.find(x=>x.id===id);if(t){t.done=!t.done;if(t.done)syncReminder(id,"task",null,"none")}store.set("tasks",a);render()};
window.toggleMeeting=id=>{let a=store.get("meetings"),meeting=a.find(x=>x.id===id);if(meeting){meeting.done=!meeting.done;if(meeting.done)syncReminder(id,"meeting",null,"none")}store.set("meetings",a);render()};
window.shareWhatsApp=async(kind,id)=>{
  const item=store.get(kind).find(entry=>entry.id===id);
  if(!item)return;
  const labels={memories:"ملاحظة",tasks:item.itemType==="call"?"تذكير اتصال":"متابعة",meetings:"اجتماع"};
  const lines=[`*${labels[kind]}: ${item.title||"دون عنوان"}*`];
  const eventAt=item.due||item.date||item.created;
  if(eventAt)lines.push(`التاريخ: ${fmtDateTime(eventAt)}`);
  const people=item.person||item.people;
  if(people)lines.push(`${kind==="meetings"?"الحاضرون":"المعني"}: ${people}`);
  const notes=item.notes||item.text;
  if(notes)lines.push("",notes);
  const text=lines.join("\n");
  if(navigator.share){
    try{
      await navigator.share({title:`مُعين التنفيذي — ${labels[kind]}`,text});
      return;
    }catch(error){
      if(error?.name==="AbortError")return;
    }
  }
  window.open(`https://wa.me/?text=${encodeURIComponent(text)}`,"_blank","noopener");
};
window.removeItem=(k,id)=>{if(confirm("حذف هذا العنصر؟")){store.set(k,store.get(k).filter(x=>x.id!==id));if(k==="tasks"||k==="meetings")syncReminder(id,k==="tasks"?"task":"meeting",null,"none");render()}};
window.removeMemory=async id=>{if(confirm("حذف الملاحظة وتسجيلها الصوتي؟")){store.set("memories",store.get("memories").filter(x=>x.id!==id));await audioDb.remove(id);render()}};

function openSimple(kind,prefill={}){
  const task=kind==="task", title=task?"متابعة جديدة":"اجتماع جديد";
  $("#simpleForm").innerHTML=`<button type="button" class="close" data-close-simple>×</button><p class="eyebrow">${title}</p><h2>${task?"ما الذي يجب متابعته؟":"ما الاجتماع الذي تريد حفظه؟"}</h2><input name="title" required placeholder="${task?"عنوان المتابعة":"عنوان الاجتماع"}"><input name="person" placeholder="${task?"الشخص أو الإدارة":"الحاضرون"}"><label>التاريخ والوقت</label><input name="date" type="datetime-local" required><label>موعد الإشعار</label><select name="reminder"><option value="0">عند الموعد</option><option value="15">قبل 15 دقيقة</option><option value="30" selected>قبل 30 دقيقة</option><option value="60">قبل ساعة</option><option value="1440">قبل يوم</option><option value="none">دون إشعار</option></select><textarea name="notes" rows="5" placeholder="ملاحظات مختصرة"></textarea><div class="modal-actions"><button type="button" data-close-simple>إلغاء</button><button type="submit" class="primary">حفظ</button></div>`;
  $("#simpleForm").querySelectorAll("[data-close-simple]").forEach(button=>button.onclick=()=>$("#simpleDialog").close());
  if(prefill.title)$("#simpleForm").elements.title.value=prefill.title;
  if(prefill.person)$("#simpleForm").elements.person.value=prefill.person;
  if(prefill.notes)$("#simpleForm").elements.notes.value=prefill.notes;
  $("#simpleForm").onsubmit=e=>{e.preventDefault();const f=new FormData(e.target),key=task?"tasks":"meetings",arr=store.get(key),id=crypto.randomUUID(),eventAt=new Date(f.get("date")).toISOString(),itemType=prefill.itemType||(task?"task":"meeting");arr.unshift({id,title:f.get("title"),[task?"person":"people"]:f.get("person"),[task?"due":"date"]:eventAt,notes:f.get("notes"),done:false,reminder:f.get("reminder"),itemType});store.set(key,arr);syncReminder(id,itemType,eventAt,f.get("reminder"));$("#simpleDialog").close();render()};
  installVoiceFields($("#simpleForm"));$("#simpleDialog").showModal();
}
$("#addTask").onclick=()=>openSimple("task");$("#addMeeting").onclick=()=>openSimple("meeting");
$("#contactSearch").oninput=renderContacts;
$("#addContact").onclick=()=>{
  $("#simpleForm").innerHTML=`<button type="button" class="close" data-close-simple>×</button><p class="eyebrow">دفتر الاتصالات</p><h2>جهة اتصال جديدة</h2><input name="name" required placeholder="الاسم الكامل"><input name="role" placeholder="المنصب"><input name="org" placeholder="الجهة أو الإدارة"><input name="phone" type="tel" inputmode="tel" placeholder="رقم الهاتف"><small class="voice-hint">يمكنك قول الرقم بالصوت، ثم مراجعته قبل الحفظ.</small><input name="email" type="email" inputmode="email" placeholder="البريد الإلكتروني"><small class="voice-hint">قل مثلًا: name آت example نقطة com</small><textarea name="notes" rows="4" placeholder="ملاحظات الاتصال"></textarea><div class="modal-actions"><button type="button" data-close-simple>إلغاء</button><button type="submit" class="primary">حفظ جهة الاتصال</button></div>`;
  $("#simpleForm").querySelectorAll("[data-close-simple]").forEach(button=>button.onclick=()=>$("#simpleDialog").close());
  $("#simpleForm").onsubmit=e=>{e.preventDefault();const f=new FormData(e.target),arr=store.get("contacts");arr.unshift({id:crypto.randomUUID(),name:f.get("name"),role:f.get("role"),org:f.get("org"),phone:normalizeVoiceValue(f.get("phone"),"tel"),email:normalizeVoiceValue(f.get("email"),"email"),notes:f.get("notes")});store.set("contacts",arr);$("#simpleDialog").close();render()};
  installVoiceFields($("#simpleForm"));$("#simpleDialog").showModal();
};
window.addCallTask=id=>{const c=store.get("contacts").find(x=>x.id===id);if(!c)return;openSimple("task",{title:`الاتصال بـ ${c.name}`,person:c.org||c.role||"",notes:c.phone||c.email||"",itemType:"call"})};
function updateCaptureCountdown(seconds=CAPTURE_LIMIT_SECONDS){
  const safe=Math.max(0,seconds),minutes=Math.floor(safe/60),remaining=safe%60;
  $("#recordCountdown").textContent=`${String(minutes).padStart(2,"0")}:${String(remaining).padStart(2,"0")}`;
}
function stopCaptureTimer(mode,{reset=false}={}){
  if(mode&&captureMode&&captureMode!==mode)return;
  if(captureTimer)clearInterval(captureTimer);
  captureTimer=null;captureDeadline=0;captureMode=null;captureWarned=false;
  $("#recordTimer").classList.remove("active","warning");
  if(reset)updateCaptureCountdown();
}
function startCaptureTimer(mode){
  stopCaptureTimer(null,{reset:true});
  captureMode=mode;captureLimitReached=false;captureWarned=false;
  captureDeadline=Date.now()+CAPTURE_LIMIT_SECONDS*1000;
  $("#recordTimer").classList.add("active");
  const tick=()=>{
    const remaining=Math.max(0,Math.ceil((captureDeadline-Date.now())/1000));
    updateCaptureCountdown(remaining);
    if(remaining<=10&&remaining>0){
      $("#recordTimer").classList.add("warning");
      if(!captureWarned){captureWarned=true;$("#recordStatus").textContent="تبقّت 10 ثوانٍ وسيتم الإيقاف تلقائيًا مع الاحتفاظ بما تم تسجيله."}
    }
    if(remaining>0)return;
    captureLimitReached=true;
    stopCaptureTimer(mode);
    if(mode==="audio"){
      audioStopRequested=true;
      if(mediaRecorder?.state==="recording")mediaRecorder.stop();
      else finishAudioCapture(true);
    }
    if(mode==="dictation"){
      dictationActive=false;dictationStopRequested=true;
      if(recognition)recognition.stop();
      else finishDictation(true);
    }
  };
  tick();captureTimer=setInterval(tick,250);
}
function openRecorder(){$("#noteText").value="";$("#noteTitle").value="";$("#noteCategory").value="memory";audioBlob=null;stopCaptureTimer(null,{reset:true});updateSmartRoute();$("#recordStatus").textContent="يمكنك التسجيل فقط، أو استخدام الإملاء لتحويل العربية إلى نص لمدة تصل إلى دقيقتين.";$("#recordDialog").showModal()}
$("#quickRecord").onclick=openRecorder;
$("#heroRecord").onclick=openRecorder;
$("#ahkihaStart").onclick=openRecorder;
$("#addMemory").onclick=openRecorder;
function finishAudioCapture(timedOut=false){
  if(audioRestartTimer)clearTimeout(audioRestartTimer);
  audioRestartTimer=null;
  captureLimitReached=false;
  stopCaptureTimer("audio");
  audioBlob=new Blob(chunks,{type:audioMimeType||mediaRecorder?.mimeType||"audio/webm"});
  if(audioStream){audioStream.getTracks().forEach(track=>track.stop());audioStream=null}
  $("#recordBtn").textContent="إعادة التسجيل";
  $("#pulse").classList.remove("live");
  $("#recordStatus").textContent=timedOut?`اكتملت مدة الدقيقتين وتم إيقاف التسجيل تلقائيًا وحفظه مؤقتًا (${Math.ceil(audioBlob.size/1024)} كيلوبايت).`:`تم حفظ التسجيل مؤقتًا (${Math.ceil(audioBlob.size/1024)} كيلوبايت).`;
}
function startAudioSegment(){
  if(!audioStream||!audioStream.getTracks().some(track=>track.readyState==="live"))throw new Error("audio-stream-ended");
  const recorder=new MediaRecorder(audioStream);
  mediaRecorder=recorder;
  audioMimeType=recorder.mimeType||audioMimeType;
  recorder.ondataavailable=event=>{if(event.data?.size)chunks.push(event.data)};
  recorder.onerror=()=>{$("#recordStatus").textContent="حدث انقطاع قصير في التسجيل، ويحاول مُعين المتابعة تلقائيًا…"};
  recorder.onstop=()=>{
    if(mediaRecorder!==recorder)return;
    const timedOut=captureLimitReached;
    const mayContinue=!timedOut&&!audioStopRequested&&captureMode==="audio"&&captureDeadline>Date.now();
    if(mayContinue){
      $("#recordStatus").textContent="تمت متابعة التسجيل تلقائيًا بعد انقطاع قصير…";
      audioRestartTimer=setTimeout(()=>{
        audioRestartTimer=null;
        try{startAudioSegment()}catch(error){audioStopRequested=true;finishAudioCapture(false)}
      },180);
      return;
    }
    finishAudioCapture(timedOut);
  };
  recorder.start(1000);
}
$("#recordBtn").onclick=async()=>{
  if(captureMode==="audio"){
    audioStopRequested=true;
    if(audioRestartTimer){clearTimeout(audioRestartTimer);audioRestartTimer=null}
    if(mediaRecorder?.state==="recording")mediaRecorder.stop();
    else finishAudioCapture(false);
    return;
  }
  if(dictationActive||recognition){$("#recordStatus").textContent="أوقف الإملاء المباشر أولًا قبل بدء التسجيل الصوتي.";return}
  try{audioStream=await navigator.mediaDevices.getUserMedia({audio:true});chunks=[];audioBlob=null;audioMimeType="";audioStopRequested=false;startCaptureTimer("audio");startAudioSegment();$("#recordBtn").textContent="إيقاف التسجيل";$("#pulse").classList.add("live");$("#recordStatus").textContent="التسجيل جارٍ… الحد الأقصى دقيقتان.";}catch(e){audioStopRequested=true;if(audioStream){audioStream.getTracks().forEach(track=>track.stop());audioStream=null}stopCaptureTimer("audio",{reset:true});$("#recordStatus").textContent="تعذر الوصول إلى الميكروفون. اسمح للتطبيق باستخدامه ثم حاول مجددًا."}
};
function finishDictation(timedOut=false,failed=false){
  if(dictationRestartTimer)clearTimeout(dictationRestartTimer);
  dictationRestartTimer=null;dictationActive=false;dictationStopRequested=false;dictationLastError="";
  captureLimitReached=false;stopCaptureTimer("dictation");recognition=null;
  $("#transcribeBtn").textContent="تحويل الكلام مباشرة";
  $("#pulse").classList.remove("live");
  $("#recordStatus").textContent=timedOut?"اكتملت مدة الدقيقتين وتوقف الإملاء تلقائيًا. راجع النص ثم احفظه أو شاركه.":failed?"تعذر استمرار الإملاء. تحقق من إذن الميكروفون والاتصال ثم حاول مجددًا.":"انتهى الإملاء. راجع النص قبل الحفظ.";
}
function startDictationSession(SR){
  const session=new SR(),baseText=$("#noteText").value.trim();
  recognition=session;dictationLastError="";
  session.lang=speechLocale();session.continuous=true;session.interimResults=true;
  session.onresult=event=>{$("#noteText").value=joinSpeechResult(baseText,event);updateSmartRoute()};
  session.onerror=event=>{
    dictationLastError=event.error||"";
    if(["not-allowed","service-not-allowed","audio-capture"].includes(dictationLastError)){
      dictationStopRequested=true;dictationActive=false;
    }
  };
  session.onend=()=>{
    if(recognition!==session)return;
    recognition=null;
    const timedOut=captureLimitReached;
    const mayContinue=!timedOut&&!dictationStopRequested&&dictationActive&&captureMode==="dictation"&&captureDeadline>Date.now();
    if(mayContinue){
      $("#recordStatus").textContent="الإملاء مستمر… تمت استعادة الاستماع تلقائيًا.";
      dictationRestartTimer=setTimeout(()=>{
        dictationRestartTimer=null;
        try{startDictationSession(SR)}catch(error){finishDictation(false,true)}
      },180);
      return;
    }
    finishDictation(timedOut,!!dictationLastError);
  };
  session.start();
}
$("#transcribeBtn").onclick=()=>{
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){$("#recordStatus").textContent="الإملاء الصوتي غير متاح في هذا المتصفح. لا يزال بإمكانك حفظ التسجيل.";return}
  if(dictationActive||recognition){
    dictationStopRequested=true;dictationActive=false;
    if(dictationRestartTimer){clearTimeout(dictationRestartTimer);dictationRestartTimer=null}
    if(recognition)recognition.stop();
    else finishDictation(false);
    return;
  }
  if(captureMode==="audio"||mediaRecorder?.state==="recording"){$("#recordStatus").textContent="أوقف التسجيل الصوتي أولًا قبل بدء الإملاء المباشر.";return}
  dictationActive=true;dictationStopRequested=false;dictationLastError="";
  startCaptureTimer("dictation");
  try{startDictationSession(SR)}catch(error){finishDictation(false,true);return}
  $("#transcribeBtn").textContent="إيقاف الإملاء";$("#pulse").classList.add("live");$("#recordStatus").textContent="أتحدث الآن… سيظهر النص أثناء كلامك، والحد الأقصى دقيقتان.";
};
$("#recordDialog").addEventListener("close",()=>{
  audioStopRequested=true;
  if(audioRestartTimer){clearTimeout(audioRestartTimer);audioRestartTimer=null}
  if(mediaRecorder?.state==="recording")mediaRecorder.stop();
  dictationStopRequested=true;dictationActive=false;
  if(dictationRestartTimer){clearTimeout(dictationRestartTimer);dictationRestartTimer=null}
  if(recognition)recognition.stop();
  stopCaptureTimer(null,{reset:true});
});
$("#shareNoteText").onclick=async()=>{
  const text=$("#noteText").value.trim(),title=$("#noteTitle").value.trim();
  if(!text){$("#recordStatus").textContent="تحدّث أو اكتب النص أولًا، ثم اضغط مشاركة.";return}
  const shareText=title?`${title}\n\n${text}`:text;
  try{
    if(navigator.share){
      await navigator.share({title:"اِحكيها من مُعين",text:shareText});
      $("#recordStatus").textContent="تمت مشاركة النص.";
      return;
    }
    if(navigator.clipboard?.writeText)await navigator.clipboard.writeText(shareText);
    else{
      const area=document.createElement("textarea");
      area.value=shareText;area.style.position="fixed";area.style.opacity="0";
      document.body.appendChild(area);area.select();document.execCommand("copy");area.remove();
    }
    $("#recordStatus").textContent="تم نسخ النص؛ أصبح جاهزًا للصقه في واتساب أو أي تطبيق.";
  }catch(error){
    if(error?.name==="AbortError")return;
    $("#recordStatus").textContent="تعذرت مشاركة النص. حاول مجددًا.";
  }
};
function extractArabicDateTime(value){
  let text=(value||"").toLowerCase().replace(/[٠-٩]/g,d=>"٠١٢٣٤٥٦٧٨٩".indexOf(d));
  const now=new Date(),result=new Date(now);
  let english=text.match(/\bin\s+(half an hour|an hour|one hour|two hours|(\d+)\s*(minutes?|hours?))\b/);
  if(english){
    if(english[1]==="half an hour")return new Date(now.getTime()+30*60000);
    if(english[1]==="an hour"||english[1]==="one hour")return new Date(now.getTime()+60*60000);
    if(english[1]==="two hours")return new Date(now.getTime()+120*60000);
    const amount=Number(english[2]),unit=english[3];
    return new Date(now.getTime()+amount*(unit.startsWith("hour")?3600000:60000));
  }
  let match=text.match(/(?:بعد|كمان)\s+(نصف)\s+ساعة/);
  if(match)return new Date(now.getTime()+30*60000);
  match=text.match(/(?:بعد|كمان)\s+(ساعة|ساعه)(?:\s+واحدة)?/);
  if(match)return new Date(now.getTime()+60*60000);
  match=text.match(/(?:بعد|كمان)\s+(ساعتين|ساعتان)/);
  if(match)return new Date(now.getTime()+120*60000);
  match=text.match(/(?:بعد|كمان)\s+(\d+)\s*(دقيقة|دقيقه|دقائق)/);
  if(match)return new Date(now.getTime()+Number(match[1])*60000);
  match=text.match(/(?:بعد|كمان)\s+(\d+)\s*(ساعة|ساعه|ساعات)/);
  if(match)return new Date(now.getTime()+Number(match[1])*3600000);
  const dayNames={الأحد:0,الاحد:0,الإثنين:1,الاثنين:1,الثلاثاء:2,الأربعاء:3,الاربعاء:3,الخميس:4,الجمعة:5,الجمعه:5,السبت:6,sunday:0,monday:1,tuesday:2,wednesday:3,thursday:4,friday:5,saturday:6};
  let hasDate=false;
  if(/غدا|غدًا|بكرة|بكره|\btomorrow\b/.test(text)){result.setDate(result.getDate()+1);hasDate=true}
  for(const [name,day] of Object.entries(dayNames)){
    if(text.includes(name)){let add=(day-result.getDay()+7)%7;if(add===0)add=7;result.setDate(result.getDate()+add);hasDate=true;break}
  }
  if(/اليوم|\btoday\b/.test(text))hasDate=true;
  match=text.match(/(?:الساعة|الساعه|\bat\b)\s*(\d{1,2})(?::(\d{1,2}))?\s*(am|pm)?/);
  if(match){
    let hour=Number(match[1]),minute=Number(match[2]||0);
    if(match[3]==="pm"&&hour<12)hour+=12;
    if(match[3]==="am"&&hour===12)hour=0;
    if(/مساء|المساء|ليلا|ليلًا/.test(text)&&hour<12)hour+=12;
    if(/صباح|الصباح/.test(text)&&hour===12)hour=0;
    result.setHours(hour,minute,0,0);hasDate=true;
    if(result<=now&&!/غدا|غدًا|بكرة|بكره|\btomorrow\b/.test(text)&&!Object.keys(dayNames).some(d=>text.includes(d)))result.setDate(result.getDate()+1);
  }else if(hasDate){
    result.setHours(/مساء/.test(text)?18:9,0,0,0);
  }
  return hasDate?result:null;
}
$("#saveNote").onclick=async()=>{
  const text=$("#noteText").value.trim();if(!text&&!audioBlob){alert("سجّل صوتًا أو اكتب ملاحظة أولًا.");return}
  const id=crypto.randomUUID(),title=$("#noteTitle").value.trim()||text.slice(0,45)||"ملاحظة صوتية",category=$("#noteCategory").value,spokenDate=extractArabicDateTime(text),eventAt=(spokenDate||new Date()).toISOString();
  if(category==="meeting"){const arr=store.get("meetings");arr.unshift({id,title,people:"",date:eventAt,notes:text,audioId:audioBlob?id:null,reminder:spokenDate?"0":"none"});store.set("meetings",arr);if(spokenDate)await syncReminder(id,"meeting",eventAt,"0")}
  else if(category==="task"){const arr=store.get("tasks");arr.unshift({id,title,person:"",due:eventAt,notes:text,done:false,audioId:audioBlob?id:null,reminder:spokenDate?"0":"none"});store.set("tasks",arr);if(spokenDate)await syncReminder(id,/اتصال|اتصل/.test(text)?"call":"task",eventAt,"0")}
  else if(category==="contact"){const arr=store.get("contacts"),phone=(text.match(/(?:\\+?\\d[\\d\\s-]{6,}\\d)/)||[""])[0].replace(/[\\s-]/g,""),email=(text.match(/[\\w.+-]+@[\\w.-]+\\.[a-z]{2,}/i)||[""])[0];arr.unshift({id,name:$("#noteTitle").value.trim()||"جهة اتصال صوتية",role:"",org:"",phone,email,notes:text,audioId:audioBlob?id:null});store.set("contacts",arr)}
  else{const mem=store.get("memories");mem.unshift({id,title,text,created:new Date().toISOString(),hasAudio:!!audioBlob});store.set("memories",mem)}
  if(audioBlob)await audioDb.put(id,audioBlob);$("#recordDialog").close();setView(category==="memory"?"memory":category==="meeting"?"meetings":category==="task"?"tasks":"contacts");if(spokenDate&&(category==="meeting"||category==="task"))alert(`تم ضبط الموعد والتنبيه تلقائيًا: ${spokenDate.toLocaleString(uiLocale())}`);
};
$("#noteText").oninput=updateSmartRoute;
$("#noteCategory").onchange=updateSaveLabel;
function classifyText(text){
  const t=(text||"").toLowerCase();
  if(/اجتماع|اجتمعت|اجتمعنا|الحاضرون|ناقشنا|محضر|جلسة|\bmeeting\b|\battendees?\b|\bminutes\b|\bsession\b/.test(t))return{type:"meeting",reason:uiT("تم التعرف على مضمون متعلق باجتماع.")};
  if(/ذكّرني|ذكرني|متابعة|تابع|يجب|موعد|إنجاز|انجاز|مطلوب|\bremind\b|\bfollow[\s-]?up\b|\btask\b|\bdue\b|\bappointment\b|\bmust\b/.test(t))return{type:"task",reason:uiT("تم التعرف على التزام أو متابعة.")};
  if(/هاتف|رقم|اتصال|ايميل|إيميل|بريد|@|\\+?\\d[\\d\\s-]{6,}|\bphone\b|\bnumber\b|\bcall\b|\bemail\b|\bcontact\b/.test(t))return{type:"contact",reason:uiT("تم التعرف على بيانات اتصال.")};
  return{type:"memory",reason:uiT("ستُحفظ كملاحظة في الذاكرة.")};
}
function updateSmartRoute(){const result=classifyText($("#noteText").value);$("#noteCategory").value=result.type;$("#routeReason").textContent=result.reason;updateSaveLabel()}
function updateSaveLabel(){const names={memory:uiT("الذاكرة"),meeting:uiT("الاجتماعات"),task:uiT("المتابعات"),contact:uiT("الاتصالات")};$("#saveNote").textContent=window.MoeenI18n?.language==="en"?`Save to ${names[$("#noteCategory").value]}`:`حفظ في ${names[$("#noteCategory").value]}`}
const audioDb={
  db:null,
  async init(){return new Promise((res,rej)=>{const r=indexedDB.open("moeen_exec_audio",1);r.onupgradeneeded=()=>r.result.createObjectStore("audio");r.onsuccess=()=>{this.db=r.result;res()};r.onerror=()=>rej(r.error)})},
  async rawGet(k){return new Promise(r=>{const q=this.db.transaction("audio").objectStore("audio").get(k);q.onsuccess=()=>r(q.result)})},
  async rawPut(k,v){return new Promise(r=>{const q=this.db.transaction("audio","readwrite").objectStore("audio").put(v,k);q.onsuccess=r})},
  async put(k,blob){
    if(!vaultKey)throw new Error("VAULT_LOCKED");
    const iv=crypto.getRandomValues(new Uint8Array(12)),plain=await blob.arrayBuffer(),cipher=await crypto.subtle.encrypt({name:"AES-GCM",iv},vaultKey,plain);
    const record={cipher,iv:toB64(iv),type:blob.type||"audio/webm"};await this.rawPut(k,record);
    try{await fetch(`${API_BASE}/api/sync/audio/${encodeURIComponent(k)}`,{method:"PUT",headers:{"Content-Type":"application/octet-stream","X-CSRF-Token":apiCsrf,"X-Audio-IV":record.iv,"X-Audio-Type":record.type},body:cipher})}catch{}
  },
  async get(k){
    if(!vaultKey)return null;
    let record=await this.rawGet(k);
    if(record instanceof Blob){await this.put(k,record);return record}
    if(!record){
      try{const r=await fetch(`${API_BASE}/api/sync/audio/${encodeURIComponent(k)}`,{headers:{"X-CSRF-Token":apiCsrf}});if(!r.ok)return null;record={cipher:await r.arrayBuffer(),iv:r.headers.get("X-Audio-IV"),type:r.headers.get("X-Audio-Type")||"audio/webm"};await this.rawPut(k,record)}catch{return null}
    }
    try{const plain=await crypto.subtle.decrypt({name:"AES-GCM",iv:fromB64(record.iv)},vaultKey,record.cipher);return new Blob([plain],{type:record.type})}catch{return null}
  },
  async remove(k){
    await new Promise(r=>{const q=this.db.transaction("audio","readwrite").objectStore("audio").delete(k);q.onsuccess=r});
    try{await api(`/api/sync/audio/${encodeURIComponent(k)}`,{method:"DELETE",body:"{}"})}catch{}
  }
};
function installVoiceFields(root=document){
  root.querySelectorAll('input:not([type="date"]):not([type="hidden"]):not([type="password"]), textarea').forEach(field=>{
    if(field.closest(".voice-field")||field.id==="noteText"||field.id==="search"||field.id==="contactSearch")return;
    const wrap=document.createElement("div");wrap.className="voice-field";field.parentNode.insertBefore(wrap,field);wrap.appendChild(field);
    const mic=document.createElement("button");mic.type="button";mic.className="voice-mic";mic.title="تحدث لتحويل الصوت إلى نص";mic.setAttribute("aria-label","إملاء صوتي");mic.textContent="🎙";wrap.appendChild(mic);
    mic.onclick=()=>dictateInto(field,mic);
  });
}
function dictateInto(field,mic){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){alert("تحويل الصوت إلى نص غير متاح في هذا المتصفح.");return}
  if(fieldRecognition){fieldRecognition.stop();return}
  const base=field.value.trim();
  fieldRecognition=new SR();fieldRecognition.lang=speechLocale();fieldRecognition.continuous=false;fieldRecognition.interimResults=true;activeMic=mic;mic.classList.add("listening");mic.textContent="■";
  fieldRecognition.onresult=e=>{field.value=normalizeVoiceValue(joinSpeechResult(base,e),field.type);field.dispatchEvent(new Event("input",{bubbles:true}))};
  fieldRecognition.onerror=()=>{alert("تعذر تشغيل الإملاء الصوتي. تحقق من إذن الميكروفون والاتصال.")};
  fieldRecognition.onend=()=>{if(activeMic){activeMic.classList.remove("listening");activeMic.textContent="🎙"}fieldRecognition=null;activeMic=null;field.focus()};
  fieldRecognition.start();
}
function joinSpeechResult(base,event){
  const finalParts=[],interimParts=[];
  for(let i=0;i<event.results.length;i++){
    const text=(event.results[i][0]?.transcript||"").trim();
    if(!text)continue;
    (event.results[i].isFinal?finalParts:interimParts).push(text);
  }
  return mergeSpeechParts(base,[...finalParts,...interimParts]);
}
function speechToken(value){
  return (value||"").toLowerCase().replace(/[\u064b-\u065f\u0670]/g,"").replace(/[^\p{L}\p{N}@+]/gu,"");
}
function mergeSpeechParts(base,parts){
  const words=(base||"").trim().split(/\s+/).filter(Boolean);
  for(const part of parts){
    const incoming=(part||"").trim().split(/\s+/).filter(Boolean);
    if(!incoming.length)continue;
    const currentNorm=words.map(speechToken),incomingNorm=incoming.map(speechToken);
    const recent=currentNorm.slice(-Math.max(24,incomingNorm.length*2)).join(" ");
    if(incomingNorm.length>1&&recent.includes(incomingNorm.join(" ")))continue;
    let overlap=0,max=Math.min(16,words.length,incoming.length);
    for(let size=max;size>0;size--){
      const tail=currentNorm.slice(-size).join(" "),head=incomingNorm.slice(0,size).join(" ");
      if(tail&&tail===head){overlap=size;break}
    }
    words.push(...incoming.slice(overlap));
    collapseRepeatedSpeech(words);
  }
  return words.join(" ").replace(/\s+/g," ").trim();
}
function collapseRepeatedSpeech(words){
  let changed=true;
  while(changed){
    changed=false;
    const normalized=words.map(speechToken);
    for(let size=Math.min(14,Math.floor(words.length/2));size>=1;size--){
      for(let end=words.length;end>=size*2;end--){
        const first=normalized.slice(end-size*2,end-size).join(" ");
        const second=normalized.slice(end-size,end).join(" ");
        if(first&&first===second){words.splice(end-size,size);changed=true;break}
      }
      if(changed)break;
    }
  }
}
function normalizeVoiceValue(value,type){
  let s=(value||"").replace(/[٠-٩]/g,d=>"0123456789"["٠١٢٣٤٥٦٧٨٩".indexOf(d)]).replace(/[۰-۹]/g,d=>"0123456789"["۰۱۲۳۴۵۶۷۸۹".indexOf(d)]);
  if(type==="tel"){
    const words={صفر:"0",واحد:"1",واحده:"1",اثنان:"2",اثنين:"2",ثلاثة:"3",ثلاثه:"3",اربعة:"4",أربعة:"4",خمسة:"5",خمسه:"5",ستة:"6",سته:"6",سبعة:"7",سبعه:"7",ثمانية:"8",ثمانيه:"8",تسعة:"9",تسعه:"9",zero:"0",one:"1",two:"2",three:"3",four:"4",five:"5",six:"6",seven:"7",eight:"8",nine:"9"};
    Object.entries(words).forEach(([word,digit])=>s=s.replace(new RegExp(`(^|\\s)${word}(?=\\s|$)`,"g"),`$1${digit}`));
    return s.replace(/(?:زائد|بلس)/gi,"+").replace(/[^\d+]/g,"");
  }
  if(type==="email")return s.toLowerCase().replace(/\s*(?:علامة\s*)?(?:آت|ات|at)\s*/gi,"@").replace(/\s*(?:نقطة|دوت|dot)\s*/gi,".").replace(/\s+/g,"");
  return s;
}
installVoiceFields();
async function api(path,options={}){
  const headers={"Content-Type":"application/json",...(options.headers||{})};
  if(apiCsrf)headers["X-CSRF-Token"]=apiCsrf;
  const response=await fetch(`${API_BASE}${path}`,{...options,headers});
  const data=await response.json().catch(()=>({}));
  if(!response.ok){const error=new Error(data.error||"REQUEST_FAILED");error.status=response.status;throw error}
  if(data.csrf)apiCsrf=data.csrf;
  return data;
}
async function reportAnonymousActivity(force=false){
  if(activitySendBusy||!apiCsrf||!vaultKey||document.body.classList.contains("locked")||document.body.classList.contains("renewal-only"))return;
  const now=Date.now();
  if(!force&&now-activityLastSent<ACTIVITY_INTERVAL)return;
  activitySendBusy=true;activityLastSent=now;
  try{await api("/api/activity",{method:"POST",body:"{}"})}
  catch{activityLastSent=0}
  finally{activitySendBusy=false}
}
["pointerdown","touchstart","keydown"].forEach(eventName=>{
  document.addEventListener(eventName,()=>reportAnonymousActivity(),{passive:true,capture:true});
});
const enc=new TextEncoder(),dec=new TextDecoder();
function toB64(bytes){let s="";for(let i=0;i<bytes.length;i+=0x8000)s+=String.fromCharCode(...bytes.subarray(i,i+0x8000));return btoa(s)}
function fromB64(value){const s=atob(value),out=new Uint8Array(s.length);for(let i=0;i<s.length;i++)out[i]=s.charCodeAt(i);return out}
async function passwordKey(password,salt){
  const base=await crypto.subtle.importKey("raw",enc.encode(password),"PBKDF2",false,["deriveKey"]);
  return crypto.subtle.deriveKey({name:"PBKDF2",salt,iterations:250000,hash:"SHA-256"},base,{name:"AES-GCM",length:256},false,["encrypt","decrypt"]);
}
async function createWrappedVault(password,rawVault){
  const salt=crypto.getRandomValues(new Uint8Array(16)),iv=crypto.getRandomValues(new Uint8Array(12)),key=await passwordKey(password,salt);
  const wrapped=await crypto.subtle.encrypt({name:"AES-GCM",iv},key,rawVault);
  return{salt:toB64(salt),iv:toB64(iv),wrapped_vault:toB64(new Uint8Array(wrapped))};
}
async function unlockWrappedVault(password,info){
  const key=await passwordKey(password,fromB64(info.salt));
  const raw=await crypto.subtle.decrypt({name:"AES-GCM",iv:fromB64(info.iv)},key,fromB64(info.wrapped_vault));
  return crypto.subtle.importKey("raw",raw,{name:"AES-GCM"},true,["encrypt","decrypt"]);
}
async function initializeOrUnlockVault(password,info,keyScope){
  if(info){vaultKey=await unlockWrappedVault(password,info)}
  else{
    const raw=crypto.getRandomValues(new Uint8Array(32)),wrapped=await createWrappedVault(password,raw);
    await api("/api/security/vault-init",{method:"POST",body:JSON.stringify(wrapped)});
    vaultKey=await crypto.subtle.importKey("raw",raw,{name:"AES-GCM"},true,["encrypt","decrypt"]);
  }
  if(keyScope)await trustedKeyStore.save(keyScope,vaultKey);
  await loadAndSyncState();
}
async function wrapCurrentVault(password){
  const raw=new Uint8Array(await crypto.subtle.exportKey("raw",vaultKey));
  return createWrappedVault(password,raw);
}
async function encryptObject(value){
  const iv=crypto.getRandomValues(new Uint8Array(12));
  const data=await crypto.subtle.encrypt({name:"AES-GCM",iv},vaultKey,enc.encode(JSON.stringify(value)));
  return{iv:toB64(iv),ciphertext:toB64(new Uint8Array(data))};
}
async function decryptObject(payload){
  const raw=await crypto.subtle.decrypt({name:"AES-GCM",iv:fromB64(payload.iv)},vaultKey,fromB64(payload.ciphertext));
  return JSON.parse(dec.decode(raw));
}
function emptyState(){return{memories:[],tasks:[],meetings:[],contacts:[],_deleted:{}}}
function normalizeState(value){
  const state={...emptyState(),...(value||{})};state._deleted=state._deleted||{};
  dataKinds.forEach(k=>{state[k]=Array.isArray(state[k])?state[k]:[];state._deleted[k]=state._deleted[k]||{}});
  return state;
}
function mergeStates(a,b){
  const left=normalizeState(a),right=normalizeState(b),result=emptyState();
  dataKinds.forEach(k=>{
    result._deleted[k]={...left._deleted[k],...right._deleted[k]};
    Object.entries(left._deleted[k]).forEach(([id,time])=>{if(!result._deleted[k][id]||time>result._deleted[k][id])result._deleted[k][id]=time});
    const items=new Map();
    [...left[k],...right[k]].forEach(item=>{const old=items.get(item.id);if(!old||(item._updated||"")>(old._updated||""))items.set(item.id,item)});
    result[k]=[...items.values()].filter(item=>!(result._deleted[k][item.id]&&(result._deleted[k][item.id]>(item._updated||""))));
  });
  return result;
}
function legacyState(){
  const state=emptyState(),stamp=new Date().toISOString();
  dataKinds.forEach(k=>{try{state[k]=JSON.parse(localStorage.getItem("moeen_exec_"+k)||"[]").map(x=>({...x,_updated:x._updated||stamp}))}catch{state[k]=[]}});
  return state;
}
function hasData(state){return dataKinds.some(k=>(state[k]||[]).length)}
async function loadAndSyncState(){
  let local=emptyState(),remoteLoaded=false,cache=localStorage.getItem("moeen_exec_secure_cache");
  if(cache){try{const parsed=JSON.parse(cache);local=normalizeState(await decryptObject(parsed));syncVersion=parsed.version||0}catch{local=emptyState()}}
  const legacy=legacyState();if(hasData(legacy))local=mergeStates(local,legacy);
  try{
    const remote=await api("/api/sync/state");
    remoteLoaded=true;
    syncVersion=remote.version||0;
    if(remote.state)local=mergeStates(local,await decryptObject(remote.state));
  }catch{}
  secureState=normalizeState(local);await saveEncryptedCache();render();
  if(hasData(secureState)||syncVersion===0)await pushSync();
  if(remoteLoaded)await reconcileReminders().catch(()=>{});
  await refreshMoeenPushStatus().catch(()=>{});
}
async function saveEncryptedCache(){
  if(!vaultKey)return;
  const payload=await encryptObject(secureState);localStorage.setItem("moeen_exec_secure_cache",JSON.stringify({...payload,version:syncVersion}));
}
function scheduleSecureSave(){
  if(!vaultKey)return;
  clearTimeout(syncTimer);saveEncryptedCache();setSyncStatus(navigator.onLine?"بانتظار المزامنة":"محفوظ دون اتصال",navigator.onLine?"":"offline");
  syncTimer=setTimeout(()=>pushSync(),650);
}
async function pushSync(retry=true){
  if(!vaultKey||syncBusy)return;
  if(!navigator.onLine){setSyncStatus("محفوظ دون اتصال","offline");return}
  syncBusy=true;
  try{
    const payload=await encryptObject(secureState);
    const result=await api("/api/sync/state",{method:"PUT",body:JSON.stringify({...payload,base_version:syncVersion})});
    syncVersion=result.version;await saveEncryptedCache();
    dataKinds.forEach(k=>localStorage.removeItem("moeen_exec_"+k));
    setSyncStatus("تمت المزامنة","synced");
    await reconcileReminders().catch(()=>{});
  }catch(err){
    if(err.status===409&&retry){
      const remote=await api("/api/sync/state");syncVersion=remote.version||0;
      if(remote.state)secureState=mergeStates(secureState,await decryptObject(remote.state));
      syncBusy=false;return pushSync(false);
    }
  }finally{syncBusy=false}
}
function setSyncStatus(text,state=""){const el=$("#syncStatus");if(!el)return;el.textContent=text;el.className=`sync-status ${state}`}
window.addEventListener("online",async()=>{await pushSync();await refreshMoeenPushStatus().catch(()=>{});await verifySubscriptionAccess()});
window.addEventListener("focus",()=>verifySubscriptionAccess());
document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="visible")verifySubscriptionAccess()});
function deviceId(){let id=localStorage.getItem("moeen_exec_device_id");if(!id){id=crypto.randomUUID();localStorage.setItem("moeen_exec_device_id",id)}return id}
function deviceName(){const mobile=/iPhone|iPad|Android/i.test(navigator.userAgent);return mobile?"هاتف شخصي":"حاسوب شخصي"}
async function initAuth(){
  try{
    const status=await api("/api/auth/status");
    if(status.authenticated){
      apiCsrf=status.csrf||"";applyProfile(status.profile);applySubscription(status.subscription);
      if(status.renewal_only){enterRenewalMode(status.profile,status.subscription);return}
      const remembered=await trustedKeyStore.load(status.key_scope).catch(()=>null);
      if(remembered){
        vaultKey=remembered;
        await loadAndSyncState();
        document.body.classList.remove("locked");
        startSubscriptionGuard(status.subscription);
        reportAnonymousActivity(true);
        $("#authMessage").textContent="";
        return;
      }
    }
    $("#setupPane").hidden=status.configured;$("#loginPane").hidden=!status.configured;document.body.classList.add("locked");
    if(status.authenticated)$("#authMessage").textContent="أدخل كلمة المرور لفتح الخزنة المشفرة.";
  }catch{$("#authMessage").textContent="تعذر الاتصال بخادم مُعين المحلي."}
}
$("#setupForm").onsubmit=async e=>{e.preventDefault();const p=$("#setupPassword").value,c=$("#setupPasswordConfirm").value;if(p!==c){$("#authMessage").textContent="كلمتا المرور غير متطابقتين.";return}try{const raw=crypto.getRandomValues(new Uint8Array(32)),vault=await createWrappedVault(p,raw);await api("/api/setup",{method:"POST",body:JSON.stringify({password:p,vault})});$("#authMessage").textContent="تم الإعداد. سجّل الدخول الآن.";$("#setupPane").hidden=true;$("#loginPane").hidden=false}catch(err){$("#authMessage").textContent=err.message==="WEAK_PASSWORD"?"استخدم 12 حرفًا على الأقل.":"تعذر إكمال الإعداد."}};
$("#loginForm").onsubmit=async e=>{
  e.preventDefault();
  const prefix=$("#loginPhonePrefix").value;
  let local=$("#loginPhone").value.replace(/\D/g,"");
  if(local.startsWith(`00${prefix}`))local=local.slice(prefix.length+2);
  else if(local.startsWith(prefix))local=local.slice(prefix.length);
  local=local.replace(/^0+/,"");
  if(local.length<7||local.length>10){$("#authMessage").textContent="اكتب الرقم المحلي فقط بصورة صحيحة.";return}
  const phone=`00${prefix}${local}`,password=$("#loginPassword").value;
  const payload={phone,password,device_id:deviceId(),device_name:deviceName()},code=$("#pairingCode").value.trim();
  try{
    const result=code
      ?await api("/api/auth/pair",{method:"POST",body:JSON.stringify({...payload,pairing_code:code})})
      :await api("/api/auth/login",{method:"POST",body:JSON.stringify(payload)});
    apiCsrf=result.csrf||apiCsrf;$("#authMessage").textContent="";$("#loginPassword").value="";
    if(result.renewal_only){enterRenewalMode(result.profile,result.subscription);return}
    applyProfile(result.profile);applySubscription(result.subscription);
    await initializeOrUnlockVault(password,result.vault,result.key_scope);
    document.body.classList.remove("locked","renewal-only");
    startSubscriptionGuard(result.subscription);
    reportAnonymousActivity(true);
    if(result.must_change){setView("security");alert("يرجى تغيير كلمة المرور المؤقتة.")}
  }catch(err){
    const messages={INVALID_CREDENTIALS:"بيانات الدخول غير صحيحة.",DEVICE_NOT_AUTHORIZED:"هذا الجهاز غير مصرح له. استخدم رمز ربط من الجهاز الرئيسي.",INVALID_PAIRING_CODE:"رمز الربط غير صحيح أو انتهت صلاحيته.",TEMPORARILY_BLOCKED:"تم حظر المحاولات مؤقتًا. حاول لاحقًا.",SUBSCRIPTION_INACTIVE:"الحساب موقوف أو ملغي. تواصل مع RT Studio.",OperationError:"تعذر فتح الخزنة. تحقق من كلمة المرور."};
    $("#authMessage").textContent=messages[err.message]||"تعذر تسجيل الدخول أو فتح الخزنة.";
  }
};
async function logoutNow(){try{await pushSync();await api("/api/auth/logout",{method:"POST",body:"{}"})}finally{clearInterval(renewalPollTimer);stopSubscriptionGuard();await trustedKeyStore.clear();apiCsrf="";vaultKey=null;secureState=emptyState();currentProfile=null;currentSubscription=null;document.body.classList.remove("renewal-only");document.body.classList.add("locked");$("#loginPane").hidden=false;$("#loginPassword").value="";$("#pairingCode").value=""}}
$("#logoutBtn").onclick=logoutNow;
$("#quickLogout").onclick=logoutNow;
$("#passwordForm").onsubmit=async e=>{e.preventDefault();try{const current=$("#currentPassword").value,next=$("#newPassword").value,vault=await wrapCurrentVault(next);await api("/api/security/change-password",{method:"POST",body:JSON.stringify({current_password:current,new_password:next,vault})});$("#currentPassword").value="";$("#newPassword").value="";alert("تم تغيير كلمة المرور وإعادة حماية الخزنة. أُلغي اعتماد الأجهزة الأخرى لحماية الحساب، ويمكن ربطها مجددًا عند الحاجة.")}catch(err){alert(err.message==="INVALID_CURRENT_PASSWORD"?"كلمة المرور الحالية غير صحيحة.":"تعذر تغيير كلمة المرور. يجب أن تكون الجديدة 12 حرفًا على الأقل ومختلفة.")}};
$("#pairingBtn").onclick=async()=>{try{const r=await api("/api/security/pairing-code",{method:"POST",body:"{}"});$("#pairingResult").textContent=r.code;$("#pairingResult").title="صالح لخمس دقائق"}catch{alert("تعذر إنشاء رمز الربط.")}};
$("#reviewAttempts").onclick=async()=>{await api("/api/security/attempts/review",{method:"POST",body:"{}"});loadSecurity()};
async function loadSecurity(){try{const r=await api("/api/security/overview");$("#deviceCount").textContent=r.devices.filter(d=>!d.revoked_at).length;$("#deviceList").innerHTML=r.devices.map(d=>`<div class="security-row"><div><b>${esc(d.name)}${d.id===r.current_device_id?" · هذا الجهاز":""}</b><small>آخر نشاط: ${fmt(d.last_seen_at)}</small></div>${!d.revoked_at&&d.id!==r.current_device_id?`<button class="security-secondary" data-action="revoke-device" data-id="${esc(d.id)}">إلغاء الجهاز</button>`:d.revoked_at?'<span class="tag">ملغى</span>':'<span class="tag">نشط</span>'}</div>`).join("")||'<div class="empty">لا توجد أجهزة.</div>';$("#attemptList").innerHTML=r.attempts.map(a=>`<div class="security-row alert-row ${a.reviewed?"reviewed":""}"><div><b>${attemptLabel(a.outcome)} · ${esc(a.device_name||"جهاز غير معروف")}</b><small>${fmt(a.created_at)} · ${esc(a.ip_address)}</small></div></div>`).join("")||'<div class="empty">لا توجد محاولات مريبة.</div>'}catch(err){if(err.status===401){document.body.classList.add("locked")}}}
function attemptLabel(o){return({bad_password:"كلمة مرور خاطئة",unknown_device_blocked:"جهاز غير مصرح",bad_pairing:"رمز ربط خاطئ",temporarily_blocked:"محاولة أثناء الحظر"})[o]||"محاولة مرفوضة"}
window.revokeDevice=async id=>{if(!confirm("إلغاء تصريح هذا الجهاز؟"))return;await api(`/api/security/devices/${encodeURIComponent(id)}/revoke`,{method:"POST",body:"{}"});loadSecurity()};
$("#moeenPaymentForm").onsubmit=async e=>{
  e.preventDefault();
  const form=e.currentTarget,message=$("#paymentMessage"),button=form.querySelector('button[type="submit"]');
  const data=new FormData(form);
  data.set("plan_type",document.querySelector('input[name="moeenPlan"]:checked').value);
  data.set("payment_method",document.querySelector('input[name="moeenPaymentMethod"]:checked').value);
  message.className="payment-message";message.textContent="جارٍ إرسال إثبات الدفع…";button.disabled=true;
  try{
    const response=await fetch("/moeen-executive/subscription-payment",{method:"POST",headers:{"X-CSRF-Token":apiCsrf},body:data});
    const result=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(result.error||"FAILED");
    form.reset();document.querySelector('input[name="moeenPlan"][value="monthly"]').checked=true;document.querySelector('input[name="moeenPaymentMethod"][value="reflect"]').checked=true;
    message.className="payment-message success";message.textContent=`تم إرسال الإثبات بنجاح. رقم المتابعة: ${result.invoice_code}`;
  }catch(err){
    const labels={PROOF_REQUIRED:"أدخل رقم العملية أو ارفع الإيصال.",INVALID_RECEIPT:"صيغة الإيصال غير مدعومة.",AUTH_REQUIRED:"سجّل الدخول ثم حاول مجددًا."};
    message.className="payment-message error";message.textContent=labels[err.message]||"تعذر إرسال الإثبات الآن. حاول مرة أخرى.";
  }finally{button.disabled=false}
};
if("serviceWorker" in navigator){
  navigator.serviceWorker
    .register("/moeen-executive/sw.js?v=40",{updateViaCache:"none"})
    .then(registration=>registration.update())
    .catch(()=>{});
}
audioDb.init().then(()=>{render();initAuth()});
