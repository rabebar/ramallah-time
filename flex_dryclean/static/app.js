document.querySelectorAll('[data-open]').forEach(button=>button.addEventListener('click',()=>document.getElementById(button.dataset.open)?.showModal()));
document.querySelectorAll('[data-close]').forEach(button=>button.addEventListener('click',()=>button.closest('dialog')?.close()));
document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close()}));
document.querySelectorAll('tr[data-href]').forEach(row=>row.addEventListener('click',()=>location.href=row.dataset.href));

const cart=document.getElementById('cart');
const cartItems=[];
const escapeHtml=value=>String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
function renderCart(){
  if(!cart)return;
  if(!cartItems.length){cart.innerHTML='<p class="empty">لم تتم إضافة قطع بعد.</p>';return;}
  cart.innerHTML=cartItems.map((item,index)=>`<div class="cart-line"><span><b>${escapeHtml(item.name)}</b><small>${Number(item.price).toFixed(2)} ₪ / ${escapeHtml(item.unit)}</small></span><input type="hidden" name="item_type[]" value="${item.manual?'manual':'catalog'}"><input type="hidden" name="service_id[]" value="${item.manual?'':item.id}"><input type="hidden" name="manual_name[]" value="${escapeHtml(item.manual?item.name:'')}"><input type="hidden" name="item_unit[]" value="${escapeHtml(item.unit)}"><input type="hidden" name="item_price[]" value="${Number(item.price)}"><input type="hidden" name="save_manual[]" value="${item.save?'1':'0'}"><input aria-label="الكمية" name="quantity[]" type="number" min="0.01" step="0.01" value="${item.quantity}"><b>${(item.price*item.quantity).toFixed(2)} ₪</b><button type="button" data-remove="${index}">×</button></div>`).join('');
  cart.querySelectorAll('input[name="quantity[]"]').forEach((input,index)=>input.addEventListener('input',()=>{cartItems[index].quantity=Number(input.value||1);renderCart()}));
  cart.querySelectorAll('[data-remove]').forEach(button=>button.addEventListener('click',()=>{cartItems.splice(Number(button.dataset.remove),1);renderCart()}));
}
const servicePicker=document.getElementById('service-picker');
if(servicePicker){
  const services=JSON.parse(servicePicker.dataset.services||'[]');
  const categorySelect=document.getElementById('service-category');
  const serviceSelect=document.getElementById('service-choice');
  const addSelected=document.getElementById('add-selected-service');
  const manualForm=document.getElementById('manual-service-form');
  categorySelect.addEventListener('change',()=>{
    const options=services.filter(service=>service.category===categorySelect.value);
    serviceSelect.innerHTML='<option value="">اختر الخدمة</option>'+options.map(service=>`<option value="${service.id}">${escapeHtml(service.name)} — ${Number(service.price).toFixed(2)} ₪ / ${escapeHtml(service.unit)}</option>`).join('');
    serviceSelect.disabled=!options.length; addSelected.disabled=true;
  });
  serviceSelect.addEventListener('change',()=>addSelected.disabled=!serviceSelect.value);
  addSelected.addEventListener('click',()=>{
    const service=services.find(item=>String(item.id)===serviceSelect.value); if(!service)return;
    const found=cartItems.find(item=>!item.manual&&item.id===service.id);
    if(found)found.quantity+=1;else cartItems.push({...service,quantity:1,manual:false,save:false});
    renderCart();
  });
  document.getElementById('show-manual-service').addEventListener('click',()=>{manualForm.hidden=!manualForm.hidden; if(!manualForm.hidden)document.getElementById('manual-service-name').focus()});
  document.getElementById('add-manual-service').addEventListener('click',()=>{
    const name=document.getElementById('manual-service-name').value.trim();
    const unit=document.getElementById('manual-service-unit').value;
    const price=Math.max(Number(document.getElementById('manual-service-price').value||0),0);
    if(!name){document.getElementById('manual-service-name').focus();return;}
    cartItems.push({id:`manual-${Date.now()}`,name,unit,price,quantity:1,manual:true,save:document.getElementById('manual-service-save').checked});
    renderCart(); document.getElementById('manual-service-name').value=''; document.getElementById('manual-service-price').value='0';
  });
}

if('serviceWorker' in navigator){
  const appScript=document.querySelector('script[src*="/static/app.js"]');
  if(appScript){
    const workerUrl=new URL('../sw.js',appScript.src);
    const workerScope=new URL('../',appScript.src).pathname;
    navigator.serviceWorker.register(workerUrl.pathname,{scope:workerScope}).catch(()=>{});
  }
}
const dueReminders=document.getElementById('due-reminders');
if(dueReminders&&'Notification' in window&&Notification.permission==='granted'){
  const noticeKey=`flex-reminder-${new Date().toISOString().slice(0,13)}`;
  if(!sessionStorage.getItem(noticeKey)){
    new Notification('FLEX — موعد تسليم قريب',{body:`لديك ${dueReminders.dataset.count} طلبات تحتاج المتابعة.`});
    sessionStorage.setItem(noticeKey,'1');
  }
}
const enableNotifications=document.getElementById('enable-notifications');
if(enableNotifications){
  if(!('Notification' in window)){enableNotifications.textContent='غير مدعوم على هذا الجهاز';enableNotifications.disabled=true}
  else if(Notification.permission==='granted')enableNotifications.textContent='التنبيهات مفعّلة';
  enableNotifications.addEventListener('click',async()=>{const result=await Notification.requestPermission();enableNotifications.textContent=result==='granted'?'التنبيهات مفعّلة':'لم يتم السماح بالتنبيهات'});
}

const scanForm=document.getElementById('scan-form');
const scanInput=document.getElementById('scan-input');
if(scanForm)scanForm.addEventListener('submit',async event=>{
  const code=scanInput.value.trim();
  if(!/^FLEX-?\d+$/i.test(code))return;
  event.preventDefault();
  const response=await fetch('api/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})});
  const data=await response.json();
  if(data.ok)location.href=data.url;else alert(data.message);
});

const newCategorySelect=document.getElementById('new-service-category-select');
if(newCategorySelect){
  const categoryField=document.getElementById('new-category-field');
  const categoryInput=document.getElementById('new-category-input');
  const categoryValue=document.getElementById('new-service-category');
  const syncCategory=()=>{
    const isNew=newCategorySelect.value==='__new__';
    categoryField.hidden=!isNew; categoryInput.required=isNew;
    categoryValue.value=isNew?categoryInput.value.trim():newCategorySelect.value;
    if(isNew)categoryInput.focus();
  };
  newCategorySelect.addEventListener('change',syncCategory);
  categoryInput.addEventListener('input',syncCategory);
}
