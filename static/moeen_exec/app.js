const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let apiCsrf="";
const API_BASE="/moeen-executive";
const dataKinds=["memories","tasks","meetings","contacts"];
let secureState={memories:[],tasks:[],meetings:[],contacts:[],_deleted:{}};
let vaultKey=null,syncVersion=0,syncTimer=null,syncBusy=false;
const trustedKeyStore={
  async open(){return new Promise((resolve,reject)=>{const r=indexedDB.open("moeen_exec_trusted_device",1);r.onupgradeneeded=()=>r.result.createObjectStore("session");r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)})},
  async save(scope,key){const db=await this.open();return new Promise((resolve,reject)=>{const q=db.transaction("session","readwrite").objectStore("session").put({scope,key},"vault");q.onsuccess=()=>resolve();q.onerror=()=>reject(q.error)})},
  async load(scope){const db=await this.open();return new Promise((resolve,reject)=>{const q=db.transaction("session").objectStore("session").get("vault");q.onsuccess=()=>resolve(q.result?.scope===scope?q.result.key:null);q.onerror=()=>reject(q.error)})},
  async clear(){const db=await this.open();return new Promise(resolve=>{const q=db.transaction("session","readwrite").objectStore("session").delete("vault");q.onsuccess=()=>resolve();q.onerror=()=>resolve()})}
};
let installPrompt=null;
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
let fieldRecognition=null, activeMic=null;
const fmt=d=>new Intl.DateTimeFormat("ar-PS",{dateStyle:"medium"}).format(new Date(d));
const esc=s=>(s||"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
function setView(id){$$(".view,.nav").forEach(x=>x.classList.remove("active"));$("#"+id).classList.add("active");$(`.nav[data-view="${id}"]`).classList.add("active");render();installVoiceFields();}
$$(".nav").forEach(b=>b.onclick=()=>setView(b.dataset.view));$$("[data-view-jump]").forEach(b=>b.onclick=()=>setView(b.dataset.viewJump));
const now=new Date();$("#date").textContent=new Intl.DateTimeFormat("ar-PS",{weekday:"long",day:"numeric",month:"long",year:"numeric"}).format(now);
const hour=now.getHours();
const timeGreeting=hour>=5&&hour<12?"صباح الخير":hour>=12&&hour<17?"طاب يومك":hour>=17&&hour<23?"مساء الخير":"أهلًا بعودتك";
$("#greeting").textContent=timeGreeting;
function applyProfile(profile){
  if(!profile)return;
  const label=[profile.title,profile.name].filter(Boolean).join(" ");
  $("#greeting").textContent=`${timeGreeting}، ${label}`;
}

function render(){
  const memories=store.get("memories"),tasks=store.get("tasks"),meetings=store.get("meetings");
  const open=tasks.filter(t=>!t.done), today=new Date().toISOString().slice(0,10);
  $("#openTasks").textContent=open.length;$("#dueTasks").textContent=open.filter(t=>t.due===today).length;$("#memoryCount").textContent=memories.length;
  $("#dailyLine").textContent=open.length?`لديك ${open.length} متابعة مفتوحة. ركّز على الأكثر إلحاحًا أولًا.`:"جدول المتابعة هادئ. سجّل ما يستحق التذكر.";
  $("#todayTasks").innerHTML=open.slice(0,4).map(taskRow).join("")||'<div class="empty">لا توجد متابعات بعد.</div>';
  $("#recentMemories").innerHTML=memories.slice(0,3).map(m=>`<div class="card-top"><div><b>${esc(m.title)}</b><div class="meta">${fmt(m.created)}</div></div><span class="tag">ملاحظة</span></div>`).join("")||'<div class="empty">ذاكرتك جاهزة لأول ملاحظة.</div>';
  renderMemories();$("#taskList").innerHTML=tasks.map(taskCard).join("")||'<div class="empty">أضف أول متابعة أو التزام.</div>';
  $("#meetingList").innerHTML=meetings.map(meetingCard).join("")||'<div class="empty">سجّل اجتماعك الأول.</div>';
  renderContacts();
  bindAudioPlayers();
  if($("#security").classList.contains("active"))loadSecurity();
}
function taskRow(t){return `<div class="card-top ${t.done?"done":""}"><div><b>${esc(t.title)}</b><div class="meta">${t.due?fmt(t.due):"بلا موعد"} · ${esc(t.person||"")}</div></div><button class="icon-btn" onclick="toggleTask('${t.id}')">${t.done?"↩":"✓"}</button></div>`}
function taskCard(t){return `<article class="card ${t.done?"done":""}"><div class="card-top"><div><h3>${esc(t.title)}</h3><div class="meta"><span>${t.due?fmt(t.due):"بلا موعد"}</span><span>${esc(t.person||"")}</span></div></div><div class="card-actions"><button class="icon-btn" onclick="toggleTask('${t.id}')">${t.done?"إعادة":"تم"}</button><button class="icon-btn" onclick="removeItem('tasks','${t.id}')">حذف</button></div></div><p>${esc(t.notes||"")}</p>${t.audioId?`<audio controls data-audio="${t.audioId}"></audio>`:""}</article>`}
function meetingCard(m){return `<article class="card"><div class="card-top"><div><h3>${esc(m.title)}</h3><div class="meta">${fmt(m.date)} · ${esc(m.people||"")}</div></div><button class="icon-btn" onclick="removeItem('meetings','${m.id}')">حذف</button></div><p>${esc(m.notes||"")}</p>${m.audioId?`<audio controls data-audio="${m.audioId}"></audio>`:""}</article>`}
function renderContacts(){
  if(!$("#contactList"))return;
  const q=($("#contactSearch")?.value||"").toLowerCase();
  const list=store.get("contacts").filter(c=>(`${c.name} ${c.role} ${c.org} ${c.phone} ${c.email}`).toLowerCase().includes(q));
  $("#contactList").innerHTML=list.map(c=>`<article class="contact-card"><div class="contact-head"><div class="contact-avatar">${esc((c.name||"؟").trim()[0])}</div><div><h3>${esc(c.name)}</h3><p>${esc([c.role,c.org].filter(Boolean).join(" · "))}</p></div></div><div class="contact-details">${c.phone?`<a href="tel:${esc(c.phone)}">☎ ${esc(c.phone)}</a>`:""}${c.email?`<a href="mailto:${esc(c.email)}">✉ ${esc(c.email)}</a>`:""}${c.notes?`<p>${esc(c.notes)}</p>`:""}${c.audioId?`<audio controls data-audio="${c.audioId}"></audio>`:""}</div><div class="contact-actions">${c.phone?`<a class="call" href="tel:${esc(c.phone)}">اتصال الآن</a>`:""}${c.email?`<a href="mailto:${esc(c.email)}">إرسال بريد</a>`:""}<button onclick="addCallTask('${c.id}')">تذكير بالاتصال</button><button onclick="removeItem('contacts','${c.id}')">حذف</button></div></article>`).join("")||'<div class="empty">أضف أول جهة اتصال إلى دليلك الشخصي.</div>';
}
function renderMemories(){
  const q=($("#search").value||"").toLowerCase(), list=store.get("memories").filter(m=>(m.title+" "+m.text).toLowerCase().includes(q));
  $("#memories").innerHTML=list.map(m=>`<article class="card"><div class="card-top"><div><h3>${esc(m.title)}</h3><div class="meta">${fmt(m.created)} · ${m.hasAudio?"صوت ونص":"نص"}</div></div><button class="icon-btn" onclick="removeMemory('${m.id}')">حذف</button></div><p>${esc(m.text)}</p>${m.hasAudio?`<audio controls data-audio="${m.id}"></audio>`:""}</article>`).join("")||'<div class="empty">لا توجد نتائج.</div>';
  $$("audio[data-audio]").forEach(async a=>{const blob=await audioDb.get(a.dataset.audio);if(blob)a.src=URL.createObjectURL(blob)});
}
function bindAudioPlayers(){$$("audio[data-audio]").forEach(async a=>{if(a.src)return;const blob=await audioDb.get(a.dataset.audio);if(blob)a.src=URL.createObjectURL(blob)})}
$("#search").oninput=renderMemories;
window.toggleTask=id=>{let a=store.get("tasks"),t=a.find(x=>x.id===id);if(t)t.done=!t.done;store.set("tasks",a);render()};
window.removeItem=(k,id)=>{if(confirm("حذف هذا العنصر؟")){store.set(k,store.get(k).filter(x=>x.id!==id));render()}};
window.removeMemory=async id=>{if(confirm("حذف الملاحظة وتسجيلها الصوتي؟")){store.set("memories",store.get("memories").filter(x=>x.id!==id));await audioDb.remove(id);render()}};

function openSimple(kind){
  const task=kind==="task", title=task?"متابعة جديدة":"اجتماع جديد";
  $("#simpleForm").innerHTML=`<button type="button" class="close" data-close-simple>×</button><p class="eyebrow">${title}</p><h2>${task?"ما الذي يجب متابعته؟":"ما الاجتماع الذي تريد حفظه؟"}</h2><input name="title" required placeholder="${task?"عنوان المتابعة":"عنوان الاجتماع"}"><input name="person" placeholder="${task?"الشخص أو الإدارة":"الحاضرون"}"><input name="date" type="date"><textarea name="notes" rows="5" placeholder="ملاحظات مختصرة"></textarea><div class="modal-actions"><button type="button" data-close-simple>إلغاء</button><button type="submit" class="primary">حفظ</button></div>`;
  $("#simpleForm").querySelectorAll("[data-close-simple]").forEach(button=>button.onclick=()=>$("#simpleDialog").close());
  $("#simpleForm").onsubmit=e=>{e.preventDefault();const f=new FormData(e.target),key=task?"tasks":"meetings",arr=store.get(key);arr.unshift({id:crypto.randomUUID(),title:f.get("title"),[task?"person":"people"]:f.get("person"),[task?"due":"date"]:f.get("date")||new Date().toISOString(),notes:f.get("notes"),done:false});store.set(key,arr);$("#simpleDialog").close();render()};
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
window.addCallTask=id=>{const c=store.get("contacts").find(x=>x.id===id);if(!c)return;const arr=store.get("tasks");arr.unshift({id:crypto.randomUUID(),title:`الاتصال بـ ${c.name}`,person:c.org||c.role||"",due:new Date().toISOString().slice(0,10),notes:c.phone||c.email||"",done:false});store.set("tasks",arr);render();alert("تمت إضافة تذكير الاتصال إلى متابعات اليوم.")};
function openRecorder(){$("#noteText").value="";$("#noteTitle").value="";$("#noteCategory").value="memory";audioBlob=null;updateSmartRoute();$("#recordStatus").textContent="يمكنك التسجيل فقط، أو استخدام الإملاء لتحويل العربية إلى نص.";$("#recordDialog").showModal()}
$("#quickRecord").onclick=openRecorder;
$("#addMemory").onclick=openRecorder;
$("#recordBtn").onclick=async()=>{
  if(mediaRecorder?.state==="recording"){mediaRecorder.stop();return}
  try{const stream=await navigator.mediaDevices.getUserMedia({audio:true});chunks=[];mediaRecorder=new MediaRecorder(stream);mediaRecorder.ondataavailable=e=>chunks.push(e.data);mediaRecorder.onstop=()=>{audioBlob=new Blob(chunks,{type:mediaRecorder.mimeType});stream.getTracks().forEach(t=>t.stop());$("#recordBtn").textContent="إعادة التسجيل";$("#pulse").classList.remove("live");$("#recordStatus").textContent=`تم حفظ التسجيل مؤقتًا (${Math.ceil(audioBlob.size/1024)} كيلوبايت).`;};mediaRecorder.start();$("#recordBtn").textContent="إيقاف التسجيل";$("#pulse").classList.add("live");$("#recordStatus").textContent="التسجيل جارٍ…";}catch(e){$("#recordStatus").textContent="تعذر الوصول إلى الميكروفون. اسمح للتطبيق باستخدامه ثم حاول مجددًا."}
};
$("#transcribeBtn").onclick=()=>{
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){$("#recordStatus").textContent="الإملاء الصوتي غير متاح في هذا المتصفح. لا يزال بإمكانك حفظ التسجيل.";return}
  if(recognition){recognition.stop();recognition=null;return}
  recognition=new SR();recognition.lang="ar";recognition.continuous=true;recognition.interimResults=true;const baseText=$("#noteText").value.trim();
  recognition.onresult=e=>{$("#noteText").value=joinSpeechResult(baseText,e);updateSmartRoute()};
  recognition.onend=()=>{recognition=null;$("#transcribeBtn").textContent="تحويل الكلام مباشرة";$("#pulse").classList.remove("live");$("#recordStatus").textContent="انتهى الإملاء. راجع النص قبل الحفظ."};
  recognition.onerror=()=>{$("#recordStatus").textContent="تعذر تشغيل الإملاء. تحقق من الميكروفون والاتصال.";};recognition.start();$("#transcribeBtn").textContent="إيقاف الإملاء";$("#pulse").classList.add("live");$("#recordStatus").textContent="أتحدث الآن… سيظهر النص أثناء كلامك.";
};
$("#saveNote").onclick=async()=>{
  const text=$("#noteText").value.trim();if(!text&&!audioBlob){alert("سجّل صوتًا أو اكتب ملاحظة أولًا.");return}
  const id=crypto.randomUUID(),title=$("#noteTitle").value.trim()||text.slice(0,45)||"ملاحظة صوتية",category=$("#noteCategory").value;
  if(category==="meeting"){const arr=store.get("meetings");arr.unshift({id,title,people:"",date:new Date().toISOString(),notes:text,audioId:audioBlob?id:null});store.set("meetings",arr)}
  else if(category==="task"){const arr=store.get("tasks");arr.unshift({id,title,person:"",due:new Date().toISOString().slice(0,10),notes:text,done:false,audioId:audioBlob?id:null});store.set("tasks",arr)}
  else if(category==="contact"){const arr=store.get("contacts"),phone=(text.match(/(?:\\+?\\d[\\d\\s-]{6,}\\d)/)||[""])[0].replace(/[\\s-]/g,""),email=(text.match(/[\\w.+-]+@[\\w.-]+\\.[a-z]{2,}/i)||[""])[0];arr.unshift({id,name:$("#noteTitle").value.trim()||"جهة اتصال صوتية",role:"",org:"",phone,email,notes:text,audioId:audioBlob?id:null});store.set("contacts",arr)}
  else{const mem=store.get("memories");mem.unshift({id,title,text,created:new Date().toISOString(),hasAudio:!!audioBlob});store.set("memories",mem)}
  if(audioBlob)await audioDb.put(id,audioBlob);$("#recordDialog").close();setView(category==="memory"?"memory":category==="meeting"?"meetings":category==="task"?"tasks":"contacts");
};
$("#noteText").oninput=updateSmartRoute;
$("#noteCategory").onchange=updateSaveLabel;
function classifyText(text){
  const t=(text||"").toLowerCase();
  if(/اجتماع|اجتمعت|اجتمعنا|الحاضرون|ناقشنا|محضر|جلسة/.test(t))return{type:"meeting",reason:"تم التعرف على مضمون متعلق باجتماع."};
  if(/ذكّرني|ذكرني|متابعة|تابع|يجب|موعد|إنجاز|انجاز|مطلوب/.test(t))return{type:"task",reason:"تم التعرف على التزام أو متابعة."};
  if(/هاتف|رقم|اتصال|ايميل|إيميل|بريد|@|\\+?\\d[\\d\\s-]{6,}/.test(t))return{type:"contact",reason:"تم التعرف على بيانات اتصال."};
  return{type:"memory",reason:"ستُحفظ كملاحظة في الذاكرة."};
}
function updateSmartRoute(){const result=classifyText($("#noteText").value);$("#noteCategory").value=result.type;$("#routeReason").textContent=result.reason;updateSaveLabel()}
function updateSaveLabel(){const names={memory:"الذاكرة",meeting:"الاجتماعات",task:"المتابعات",contact:"الاتصالات"};$("#saveNote").textContent=`حفظ في ${names[$("#noteCategory").value]}`}
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
  fieldRecognition=new SR();fieldRecognition.lang="ar";fieldRecognition.continuous=true;fieldRecognition.interimResults=true;activeMic=mic;mic.classList.add("listening");mic.textContent="■";
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
  return [base,...finalParts,...interimParts].filter(Boolean).join(" ").replace(/\s+/g," ").trim();
}
function normalizeVoiceValue(value,type){
  let s=(value||"").replace(/[٠-٩]/g,d=>"0123456789"["٠١٢٣٤٥٦٧٨٩".indexOf(d)]).replace(/[۰-۹]/g,d=>"0123456789"["۰۱۲۳۴۵۶۷۸۹".indexOf(d)]);
  if(type==="tel"){
    const words={صفر:"0",واحد:"1",واحده:"1",اثنان:"2",اثنين:"2",ثلاثة:"3",ثلاثه:"3",اربعة:"4",أربعة:"4",خمسة:"5",خمسه:"5",ستة:"6",سته:"6",سبعة:"7",سبعه:"7",ثمانية:"8",ثمانيه:"8",تسعة:"9",تسعه:"9"};
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
  let local=emptyState(),cache=localStorage.getItem("moeen_exec_secure_cache");
  if(cache){try{const parsed=JSON.parse(cache);local=normalizeState(await decryptObject(parsed));syncVersion=parsed.version||0}catch{local=emptyState()}}
  const legacy=legacyState();if(hasData(legacy))local=mergeStates(local,legacy);
  try{
    const remote=await api("/api/sync/state");
    syncVersion=remote.version||0;
    if(remote.state)local=mergeStates(local,await decryptObject(remote.state));
  }catch{}
  secureState=normalizeState(local);await saveEncryptedCache();render();
  if(hasData(secureState)||syncVersion===0)await pushSync();
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
  }catch(err){
    if(err.status===409&&retry){
      const remote=await api("/api/sync/state");syncVersion=remote.version||0;
      if(remote.state)secureState=mergeStates(secureState,await decryptObject(remote.state));
      syncBusy=false;return pushSync(false);
    }
  }finally{syncBusy=false}
}
function setSyncStatus(text,state=""){const el=$("#syncStatus");if(!el)return;el.textContent=text;el.className=`sync-status ${state}`}
window.addEventListener("online",()=>pushSync());
function deviceId(){let id=localStorage.getItem("moeen_exec_device_id");if(!id){id=crypto.randomUUID();localStorage.setItem("moeen_exec_device_id",id)}return id}
function deviceName(){const mobile=/iPhone|iPad|Android/i.test(navigator.userAgent);return mobile?"هاتف شخصي":"حاسوب شخصي"}
async function initAuth(){
  try{
    const status=await api("/api/auth/status");
    if(status.authenticated){
      apiCsrf=status.csrf||"";applyProfile(status.profile);
      const remembered=await trustedKeyStore.load(status.key_scope).catch(()=>null);
      if(remembered){
        vaultKey=remembered;
        await loadAndSyncState();
        document.body.classList.remove("locked");
        $("#authMessage").textContent="";
        return;
      }
    }
    $("#setupPane").hidden=status.configured;$("#loginPane").hidden=!status.configured;document.body.classList.add("locked");
    if(status.authenticated)$("#authMessage").textContent="أدخل كلمة المرور لفتح الخزنة المشفرة.";
  }catch{$("#authMessage").textContent="تعذر الاتصال بخادم مُعين المحلي."}
}
$("#setupForm").onsubmit=async e=>{e.preventDefault();const p=$("#setupPassword").value,c=$("#setupPasswordConfirm").value;if(p!==c){$("#authMessage").textContent="كلمتا المرور غير متطابقتين.";return}try{const raw=crypto.getRandomValues(new Uint8Array(32)),vault=await createWrappedVault(p,raw);await api("/api/setup",{method:"POST",body:JSON.stringify({password:p,vault})});$("#authMessage").textContent="تم الإعداد. سجّل الدخول الآن.";$("#setupPane").hidden=true;$("#loginPane").hidden=false}catch(err){$("#authMessage").textContent=err.message==="WEAK_PASSWORD"?"استخدم 12 حرفًا على الأقل.":"تعذر إكمال الإعداد."}};
$("#loginForm").onsubmit=async e=>{e.preventDefault();const phone=$("#loginPhone").value.trim(),password=$("#loginPassword").value,payload={phone,password,device_id:deviceId(),device_name:deviceName()},code=$("#pairingCode").value.trim();try{const result=code?await api("/api/auth/pair",{method:"POST",body:JSON.stringify({...payload,pairing_code:code})}):await api("/api/auth/login",{method:"POST",body:JSON.stringify(payload)});apiCsrf=result.csrf||apiCsrf;applyProfile(result.profile);await initializeOrUnlockVault(password,result.vault,result.key_scope);document.body.classList.remove("locked");$("#authMessage").textContent="";$("#loginPassword").value="";if(result.must_change){setView("security");alert("يرجى تغيير كلمة المرور المؤقتة.")}}catch(err){const messages={INVALID_CREDENTIALS:"بيانات الدخول غير صحيحة.",DEVICE_NOT_AUTHORIZED:"هذا الجهاز غير مصرح له. استخدم رمز ربط من الجهاز الرئيسي.",INVALID_PAIRING_CODE:"رمز الربط غير صحيح أو انتهت صلاحيته.",TEMPORARILY_BLOCKED:"تم حظر المحاولات مؤقتًا. حاول لاحقًا.",SUBSCRIPTION_INACTIVE:"الاشتراك غير نشط. تواصل مع RT Studio.",OperationError:"تعذر فتح الخزنة. تحقق من كلمة المرور."};$("#authMessage").textContent=messages[err.message]||"تعذر تسجيل الدخول أو فتح الخزنة."}};
async function logoutNow(){try{await pushSync();await api("/api/auth/logout",{method:"POST",body:"{}"})}finally{await trustedKeyStore.clear();apiCsrf="";vaultKey=null;secureState=emptyState();document.body.classList.add("locked");$("#loginPane").hidden=false;$("#loginPassword").value="";$("#pairingCode").value=""}}
$("#logoutBtn").onclick=logoutNow;
$("#quickLogout").onclick=logoutNow;
$("#passwordForm").onsubmit=async e=>{e.preventDefault();try{const current=$("#currentPassword").value,next=$("#newPassword").value,vault=await wrapCurrentVault(next);await api("/api/security/change-password",{method:"POST",body:JSON.stringify({current_password:current,new_password:next,vault})});$("#currentPassword").value="";$("#newPassword").value="";alert("تم تغيير كلمة المرور وإعادة حماية الخزنة بنجاح.")}catch(err){alert(err.message==="INVALID_CURRENT_PASSWORD"?"كلمة المرور الحالية غير صحيحة.":"تعذر تغيير كلمة المرور. يجب أن تكون الجديدة 12 حرفًا على الأقل ومختلفة.")}};
$("#pairingBtn").onclick=async()=>{try{const r=await api("/api/security/pairing-code",{method:"POST",body:"{}"});$("#pairingResult").textContent=r.code;$("#pairingResult").title="صالح لخمس دقائق"}catch{alert("تعذر إنشاء رمز الربط.")}};
$("#reviewAttempts").onclick=async()=>{await api("/api/security/attempts/review",{method:"POST",body:"{}"});loadSecurity()};
async function loadSecurity(){try{const r=await api("/api/security/overview");$("#deviceCount").textContent=r.devices.filter(d=>!d.revoked_at).length;$("#deviceList").innerHTML=r.devices.map(d=>`<div class="security-row"><div><b>${esc(d.name)}${d.id===r.current_device_id?" · هذا الجهاز":""}</b><small>آخر نشاط: ${fmt(d.last_seen_at)}</small></div>${!d.revoked_at&&d.id!==r.current_device_id?`<button class="security-secondary" onclick="revokeDevice('${d.id}')">إلغاء الجهاز</button>`:d.revoked_at?'<span class="tag">ملغى</span>':'<span class="tag">نشط</span>'}</div>`).join("")||'<div class="empty">لا توجد أجهزة.</div>';$("#attemptList").innerHTML=r.attempts.map(a=>`<div class="security-row alert-row ${a.reviewed?"reviewed":""}"><div><b>${attemptLabel(a.outcome)} · ${esc(a.device_name||"جهاز غير معروف")}</b><small>${fmt(a.created_at)} · ${esc(a.ip_address)}</small></div></div>`).join("")||'<div class="empty">لا توجد محاولات مريبة.</div>'}catch(err){if(err.status===401){document.body.classList.add("locked")}}}
function attemptLabel(o){return({bad_password:"كلمة مرور خاطئة",unknown_device_blocked:"جهاز غير مصرح",bad_pairing:"رمز ربط خاطئ",temporarily_blocked:"محاولة أثناء الحظر"})[o]||"محاولة مرفوضة"}
window.revokeDevice=async id=>{if(!confirm("إلغاء تصريح هذا الجهاز؟"))return;await api(`/api/security/devices/${encodeURIComponent(id)}/revoke`,{method:"POST",body:"{}"});loadSecurity()};
audioDb.init().then(()=>{render();initAuth()});
