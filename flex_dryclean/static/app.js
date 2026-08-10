document.querySelectorAll('[data-open]').forEach(button=>button.addEventListener('click',()=>document.getElementById(button.dataset.open)?.showModal()));
document.querySelectorAll('[data-close]').forEach(button=>button.addEventListener('click',()=>button.closest('dialog')?.close()));
document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close()}));
document.querySelectorAll('tr[data-href]').forEach(row=>row.addEventListener('click',()=>location.href=row.dataset.href));
document.querySelector('dialog[data-auto-open="1"]')?.showModal();

const cart=document.getElementById('cart');
const cartItems=[];
const escapeHtml=value=>String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
const appScript=document.querySelector('script[src*="/static/app.js"]');
const appBase=appScript?new URL('../',appScript.src).pathname:'./';
const quantityRules=unit=>unit==='قطعة'?{min:1,step:1}:{min:0.1,step:0.1};
const applyQuantityRules=(input,unit)=>{const rules=quantityRules(unit);input.min=String(rules.min);input.step=String(rules.step);if(Number(input.value)<rules.min)input.value=String(rules.min)};
function renderCart(){
  if(!cart)return;
  if(!cartItems.length){cart.innerHTML='<p class="empty">لم تتم إضافة قطع بعد.</p>';return;}
  cart.innerHTML=cartItems.map((item,index)=>{const rules=quantityRules(item.unit);return `<div class="cart-line"><span><b>${escapeHtml(item.name)}${item.treatment&&item.treatment!=='حسب الوصف'?` — ${escapeHtml(item.treatment)}`:''}</b><small>${Number(item.price).toFixed(2)} ₪ / ${escapeHtml(item.unit)}</small>${item.note?`<small class="item-note">ملاحظة: ${escapeHtml(item.note)}</small>`:''}</span><input type="hidden" name="item_type[]" value="${item.manual?'manual':'catalog'}"><input type="hidden" name="service_id[]" value="${item.manual?'':item.id}"><input type="hidden" name="manual_name[]" value="${escapeHtml(item.manual?item.name:'')}"><input type="hidden" name="item_treatment[]" value="${escapeHtml(item.treatment||'حسب الوصف')}"><input type="hidden" name="item_unit[]" value="${escapeHtml(item.unit)}"><input type="hidden" name="item_price[]" value="${Number(item.price)}"><input type="hidden" name="item_note[]" value="${escapeHtml(item.note||'')}"><input type="hidden" name="save_manual[]" value="${item.save?'1':'0'}"><input aria-label="الكمية" name="quantity[]" type="number" min="${rules.min}" step="${rules.step}" value="${item.quantity}"><b>${(item.price*item.quantity).toFixed(2)} ₪</b><button type="button" data-remove="${index}">×</button></div>`}).join('');
  cart.querySelectorAll('input[name="quantity[]"]').forEach((input,index)=>input.addEventListener('input',()=>{cartItems[index].quantity=Number(input.value||1);renderCart()}));
  cart.querySelectorAll('[data-remove]').forEach(button=>button.addEventListener('click',()=>{cartItems.splice(Number(button.dataset.remove),1);renderCart()}));
}
const servicePicker=document.getElementById('service-picker');
if(servicePicker){
  const services=JSON.parse(servicePicker.dataset.services||'[]');
  const categorySelect=document.getElementById('service-category');
  const serviceSelect=document.getElementById('service-choice');
  const serviceQuantity=document.getElementById('service-quantity');
  const serviceNote=document.getElementById('service-note');
  const addSelected=document.getElementById('add-selected-service');
  const manualForm=document.getElementById('manual-service-form');
  categorySelect.addEventListener('change',()=>{
    const options=services.filter(service=>service.category===categorySelect.value);
    serviceSelect.innerHTML='<option value="">اختر الخدمة</option>'+options.map(service=>`<option value="${service.id}">${escapeHtml(service.name)}${service.treatment&&service.treatment!=='حسب الوصف'?` — ${escapeHtml(service.treatment)}`:''} — ${Number(service.price).toFixed(2)} ₪ / ${escapeHtml(service.unit)}</option>`).join('');
    serviceSelect.disabled=!options.length; addSelected.disabled=true;
  });
  serviceSelect.addEventListener('change',()=>{const service=services.find(item=>String(item.id)===serviceSelect.value);addSelected.disabled=!service;if(service)applyQuantityRules(serviceQuantity,service.unit)});
  addSelected.addEventListener('click',()=>{
    const service=services.find(item=>String(item.id)===serviceSelect.value); if(!service)return;
    const quantity=Math.max(Number(serviceQuantity.value||1),0.01);
    const note=serviceNote.value.trim();
    const found=cartItems.find(item=>!item.manual&&item.id===service.id&&item.note===note);
    if(found)found.quantity+=quantity;else cartItems.push({...service,quantity,note,manual:false,save:false});
    renderCart(); serviceQuantity.value='1'; serviceNote.value='';
  });
  document.getElementById('show-manual-service').addEventListener('click',()=>{manualForm.hidden=!manualForm.hidden; if(!manualForm.hidden)document.getElementById('manual-service-name').focus()});
  const manualUnit=document.getElementById('manual-service-unit');
  const manualQuantity=document.getElementById('manual-service-quantity');
  manualUnit.addEventListener('change',()=>applyQuantityRules(manualQuantity,manualUnit.value));
  document.getElementById('add-manual-service').addEventListener('click',()=>{
    const name=document.getElementById('manual-service-name').value.trim();
    const treatment=document.getElementById('manual-service-treatment').value;
    const unit=document.getElementById('manual-service-unit').value;
    const price=Math.max(Number(document.getElementById('manual-service-price').value||0),0);
    const quantity=Math.max(Number(manualQuantity.value||1),quantityRules(unit).min);
    const note=document.getElementById('manual-service-note').value.trim();
    if(!name){document.getElementById('manual-service-name').focus();return;}
    cartItems.push({id:`manual-${Date.now()}`,name,treatment,unit,price,quantity,note,manual:true,save:document.getElementById('manual-service-save').checked});
    renderCart(); document.getElementById('manual-service-name').value=''; document.getElementById('manual-service-price').value='0'; document.getElementById('manual-service-quantity').value='1'; document.getElementById('manual-service-note').value='';
  });
}

const customerLookupInput=document.getElementById('customer-lookup-input');
const customerLookupResults=document.getElementById('customer-lookup-results');
const orderCustomerName=document.getElementById('order-customer-name');
const orderCustomerPhone=document.getElementById('order-customer-phone');
const orderCustomerSuggestions=document.getElementById('order-customer-suggestions');
const selectedCustomerId=document.getElementById('selected-customer-id');
let customerTimer;
const fetchCustomers=async query=>{
  if(query.trim().length<2)return [];
  const response=await fetch(`${appBase}api/customers?q=${encodeURIComponent(query.trim())}`);
  return response.ok?(await response.json()).customers:[];
};
const customerMarkup=(customers,compact=false)=>customers.length?customers.map(customer=>`<article class="customer-result" data-customer-id="${customer.id}" data-customer-name="${escapeHtml(customer.name)}" data-customer-phone="${escapeHtml(customer.phone)}"><div><b>${escapeHtml(customer.name)}</b><span>${escapeHtml(customer.phone)} · ${customer.open_count} طلب مفتوح</span></div>${compact?'<button type="button" class="soft customer-select">اختيار</button>':`<div class="customer-open-orders">${customer.orders.length?customer.orders.map(order=>`<a href="${appBase}orders/${order.id}">${escapeHtml(order.order_no)} · ${escapeHtml(order.status)}${order.due_date?` · ${escapeHtml(order.due_date.replace('T',' '))}`:''}</a>`).join(''):'<span>لا توجد طلبات مفتوحة</span>'}</div><button type="button" class="soft customer-new-order">طلب جديد</button>`}</article>`).join(''):'<p class="empty">لم يُعثر على زبون مطابق. يمكنك إنشاء زبون جديد.</p>';
const runCustomerSearch=(input,results,compact=false)=>{
  clearTimeout(customerTimer);
  const query=input.value;
  if(query.trim().length<2){results.hidden=true;results.innerHTML='';return;}
  customerTimer=setTimeout(async()=>{const customers=await fetchCustomers(query);results.innerHTML=customerMarkup(customers,compact);results.hidden=false;},220);
};
if(customerLookupInput)customerLookupInput.addEventListener('input',()=>runCustomerSearch(customerLookupInput,customerLookupResults));
[orderCustomerName,orderCustomerPhone].filter(Boolean).forEach(input=>input.addEventListener('input',()=>{selectedCustomerId.value='';runCustomerSearch(input,orderCustomerSuggestions,true)}));
document.addEventListener('click',event=>{
  const card=event.target.closest('.customer-result'); if(!card)return;
  if(event.target.closest('.customer-select,.customer-new-order')){
    selectedCustomerId.value=card.dataset.customerId;
    orderCustomerName.value=card.dataset.customerName;
    orderCustomerPhone.value=card.dataset.customerPhone;
    orderCustomerSuggestions.hidden=true;
    document.getElementById('new-order')?.showModal();
  }
});

if('serviceWorker' in navigator){
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
const serviceTableSearch=document.getElementById('service-table-search');
if(serviceTableSearch)serviceTableSearch.addEventListener('input',()=>{const query=serviceTableSearch.value.trim().toLowerCase();document.querySelectorAll('[data-service-row]').forEach(row=>{const values=[row.textContent,...[...row.querySelectorAll('input,select')].map(field=>field.value)].join(' ').toLowerCase();row.hidden=Boolean(query&&!values.includes(query))})});
const customerDirectorySearch=document.getElementById('customer-directory-search');
if(customerDirectorySearch)customerDirectorySearch.addEventListener('input',()=>{const query=customerDirectorySearch.value.trim().toLowerCase();document.querySelectorAll('[data-customer-card]').forEach(card=>card.hidden=Boolean(query&&!card.textContent.toLowerCase().includes(query)))});
