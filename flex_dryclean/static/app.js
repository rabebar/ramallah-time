document.querySelectorAll('[data-open]').forEach(button=>button.addEventListener('click',()=>document.getElementById(button.dataset.open)?.showModal()));
document.querySelectorAll('[data-close]').forEach(button=>button.addEventListener('click',()=>button.closest('dialog')?.close()));
document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close()}));
document.querySelectorAll('tr[data-href]').forEach(row=>row.addEventListener('click',()=>location.href=row.dataset.href));
document.querySelector('dialog[data-auto-open="1"]')?.showModal();

const flexNavToggle=document.querySelector('[data-flex-nav-toggle]');
const flexMainNav=document.getElementById('flex-main-nav');
if(flexNavToggle&&flexMainNav){
  flexNavToggle.addEventListener('click',()=>{
    const open=flexMainNav.classList.toggle('is-open');
    flexNavToggle.setAttribute('aria-expanded',String(open));
  });
  document.addEventListener('click',event=>{
    if(!flexMainNav.classList.contains('is-open')||flexMainNav.contains(event.target)||flexNavToggle.contains(event.target))return;
    flexMainNav.classList.remove('is-open');
    flexNavToggle.setAttribute('aria-expanded','false');
  });
}

let flexInstallPrompt=null;
const flexInstallButtons=[...document.querySelectorAll('[data-flex-install]')];
const flexStandalone=window.matchMedia('(display-mode: standalone)').matches||window.navigator.standalone===true;
const updateFlexInstallButtons=()=>flexInstallButtons.forEach(button=>button.hidden=flexStandalone);
window.addEventListener('beforeinstallprompt',event=>{
  event.preventDefault();
  flexInstallPrompt=event;
  updateFlexInstallButtons();
});
window.addEventListener('appinstalled',()=>flexInstallButtons.forEach(button=>button.hidden=true));
flexInstallButtons.forEach(button=>button.addEventListener('click',async()=>{
  if(flexInstallPrompt){
    await flexInstallPrompt.prompt();
    await flexInstallPrompt.userChoice;
    flexInstallPrompt=null;
  }else{
    button.textContent='من قائمة المتصفح اختر «تثبيت FLEX»';
    setTimeout(()=>button.textContent='تثبيت FLEX على الكمبيوتر',5000);
  }
}));
updateFlexInstallButtons();

const cart=document.getElementById('cart');
const cartItems=[];
const escapeHtml=value=>String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
const appScript=document.querySelector('script[src*="/static/app.js"]');
const appBase=appScript?new URL('../',appScript.src).pathname:'./';
const quantityRules=unit=>unit==='قطعة'?{min:1,step:1}:{min:0.1,step:0.1};
const applyQuantityRules=(input,unit)=>{const rules=quantityRules(unit);input.min=String(rules.min);input.step=String(rules.step);if(Number(input.value)<rules.min)input.value=String(rules.min)};
const money=value=>`${Math.max(Number(value)||0,0).toFixed(2)} ₪`;
function updateOrderTotal(){
  const subtotal=cartItems.reduce((sum,item)=>sum+(Number(item.price)||0)*(Number(item.quantity)||0),0);
  const discount=Math.max(Number(document.querySelector('#new-order [name="discount"]')?.value)||0,0);
  const paid=Math.max(Number(document.querySelector('#new-order [name="paid"]')?.value)||0,0);
  const total=Math.max(subtotal-discount,0);
  const balance=Math.max(total-paid,0);
  const subtotalView=document.getElementById('live-subtotal'); if(subtotalView)subtotalView.textContent=money(subtotal);
  const totalView=document.getElementById('live-total'); if(totalView)totalView.textContent=money(total);
  const balanceView=document.getElementById('live-balance'); if(balanceView)balanceView.textContent=money(balance);
}
function renderCart(){
  if(!cart)return;
  if(!cartItems.length){cart.innerHTML='<p class="empty">لم تتم إضافة قطع بعد.</p>';updateOrderTotal();return;}
  cart.innerHTML=cartItems.map((item,index)=>{const rules=quantityRules(item.unit);return `<div class="cart-line"><span><b>${escapeHtml(item.name)}${item.treatment&&item.treatment!=='حسب الوصف'?` — ${escapeHtml(item.treatment)}`:''}</b><small>${Number(item.price).toFixed(2)} ₪ / ${escapeHtml(item.unit)}</small>${item.note?`<small class="item-note">ملاحظة: ${escapeHtml(item.note)}</small>`:''}</span><input type="hidden" name="item_type[]" value="${item.manual?'manual':'catalog'}"><input type="hidden" name="service_id[]" value="${item.manual?'':item.id}"><input type="hidden" name="manual_name[]" value="${escapeHtml(item.manual?item.name:'')}"><input type="hidden" name="item_treatment[]" value="${escapeHtml(item.treatment||'حسب الوصف')}"><input type="hidden" name="item_unit[]" value="${escapeHtml(item.unit)}"><input type="hidden" name="item_price[]" value="${Number(item.price)}"><input type="hidden" name="item_note[]" value="${escapeHtml(item.note||'')}"><input type="hidden" name="save_manual[]" value="${item.save?'1':'0'}"><input aria-label="الكمية" name="quantity[]" type="number" min="${rules.min}" step="${rules.step}" value="${item.quantity}"><b>${(item.price*item.quantity).toFixed(2)} ₪</b><button type="button" data-remove="${index}">×</button></div>`}).join('');
  cart.querySelectorAll('input[name="quantity[]"]').forEach((input,index)=>input.addEventListener('input',()=>{cartItems[index].quantity=Number(input.value||1);renderCart()}));
  cart.querySelectorAll('[data-remove]').forEach(button=>button.addEventListener('click',()=>{cartItems.splice(Number(button.dataset.remove),1);renderCart()}));
  updateOrderTotal();
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
document.querySelectorAll('#new-order [name="discount"],#new-order [name="paid"]').forEach(input=>input.addEventListener('input',updateOrderTotal));
updateOrderTotal();

const cashClosingForm=document.getElementById('cash-closing-form');
if(cashClosingForm){
  const openingInput=document.getElementById('opening-cash');
  const actualInput=document.getElementById('actual-cash');
  const expectedView=document.getElementById('expected-cash');
  const differenceView=document.getElementById('cash-difference');
  const differenceBox=differenceView?.closest('.cash-difference');
  const cashReceived=Number(cashClosingForm.dataset.cashReceived)||0;
  const expenses=Number(cashClosingForm.dataset.expenses)||0;
  const updateCashClosing=()=>{
    const opening=Math.max(Number(openingInput?.value)||0,0);
    const expected=opening+cashReceived-expenses;
    if(expectedView)expectedView.textContent=money(expected);
    if(!actualInput?.value){
      if(differenceView)differenceView.textContent='—';
      differenceBox?.classList.remove('is-balanced','has-difference');
      return;
    }
    const difference=(Number(actualInput.value)||0)-expected;
    if(differenceView)differenceView.textContent=money(difference);
    differenceBox?.classList.toggle('is-balanced',Math.abs(difference)<0.01);
    differenceBox?.classList.toggle('has-difference',Math.abs(difference)>=0.01);
  };
  openingInput?.addEventListener('input',updateCashClosing);
  actualInput?.addEventListener('input',updateCashClosing);
  updateCashClosing();
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
const formatDateTime=value=>{const match=String(value||'').match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}:\d{2}))?/);return match?`${match[3]}/${match[2]}/${match[1]}${match[4]?` · ${match[4]}`:''}`:String(value||'')};
const customerMarkup=customers=>customers.length?customers.map(customer=>`<article class="customer-result"><div><b>${escapeHtml(customer.name)}</b><span><bdi class="phone-ltr">${escapeHtml(customer.phone)}</bdi> · ${escapeHtml(customer.address||'')} · ${customer.open_count} طلب مفتوح</span></div><div class="customer-open-orders">${customer.orders.length?customer.orders.map(order=>`<a href="${appBase}orders/${order.id}">${escapeHtml(order.order_no)} · ${escapeHtml(order.status)}${order.due_date?` · ${escapeHtml(formatDateTime(order.due_date))}`:''}</a>`).join(''):'<span>لا توجد طلبات مفتوحة</span>'}</div><a class="soft" href="${appBase}customers/${customer.id}">فتح ملف الزبون</a></article>`).join(''):'<p class="empty">لم يُعثر على زبون مطابق. أضفه أولاً من زر «زبون جديد».</p>';
const runCustomerSearch=(input,results,compact=false)=>{
  clearTimeout(customerTimer);
  const query=input.value;
  if(query.trim().length<2){results.hidden=true;results.innerHTML='';return;}
  customerTimer=setTimeout(async()=>{const customers=await fetchCustomers(query);results.innerHTML=customerMarkup(customers);results.hidden=false;},220);
};
if(customerLookupInput)customerLookupInput.addEventListener('input',()=>runCustomerSearch(customerLookupInput,customerLookupResults));
[orderCustomerName,orderCustomerPhone].filter(Boolean).forEach(input=>input.addEventListener('input',()=>{selectedCustomerId.value='';runCustomerSearch(input,orderCustomerSuggestions,true)}));

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
if(customerDirectorySearch){
  const normalizeArabic=value=>String(value||'').toLowerCase().normalize('NFKD').replace(/[\u064b-\u065f\u0670]/g,'').replace(/[إأآٱ]/g,'ا').replace(/ى/g,'ي').replace(/ة/g,'ه');
  const phoneDigits=value=>String(value||'').replace(/\D/g,'').replace(/^0+/,'').replace(/^(970|972)/,'');
  const emptyResult=document.getElementById('customer-search-empty');
  customerDirectorySearch.addEventListener('input',()=>{
    const query=customerDirectorySearch.value.trim();
    const normalizedQuery=normalizeArabic(query);
    const queryPhone=phoneDigits(query);
    let visible=0;
    document.querySelectorAll('[data-customer-card]').forEach(card=>{
      const textMatch=!query||normalizeArabic(card.textContent).includes(normalizedQuery);
      const phoneMatch=Boolean(queryPhone.length>=3&&phoneDigits(card.textContent).includes(queryPhone));
      card.hidden=!(textMatch||phoneMatch);
      if(!card.hidden)visible+=1;
    });
    if(emptyResult)emptyResult.hidden=!query||visible>0;
  });
}

const invoiceEditList=document.getElementById('invoice-edit-list');
const updateInvoiceEditTotal=()=>{
  if(!invoiceEditList)return;
  let subtotal=0;
  invoiceEditList.querySelectorAll('.invoice-edit-row').forEach(row=>{
    const quantity=Math.max(Number(row.querySelector('[name="quantity[]"]').value)||0,0);
    const price=Math.max(Number(row.querySelector('[name="unit_price[]"]').value)||0,0);
    const lineTotal=quantity*price; subtotal+=lineTotal;
    row.querySelector('.invoice-edit-line-total').textContent=money(lineTotal);
  });
  const discount=Math.max(Number(document.querySelector('#edit-invoice [name="discount"]')?.value)||0,0);
  document.getElementById('edit-invoice-subtotal').textContent=money(subtotal);
  document.getElementById('edit-invoice-total').textContent=money(Math.max(subtotal-discount,0));
};
if(invoiceEditList){
  invoiceEditList.addEventListener('input',updateInvoiceEditTotal);
  invoiceEditList.addEventListener('change',event=>{if(event.target.matches('[name="unit[]"]'))applyQuantityRules(event.target.closest('.invoice-edit-row').querySelector('[name="quantity[]"]'),event.target.value);updateInvoiceEditTotal()});
  invoiceEditList.addEventListener('click',event=>{const remove=event.target.closest('.remove-invoice-row');if(remove){remove.closest('.invoice-edit-row').remove();updateInvoiceEditTotal()}});
  document.querySelector('#edit-invoice [name="discount"]')?.addEventListener('input',updateInvoiceEditTotal);
  document.getElementById('add-invoice-row')?.addEventListener('click',()=>{invoiceEditList.insertAdjacentHTML('beforeend','<div class="invoice-edit-row"><input name="item_name[]" aria-label="الخدمة" placeholder="اسم الخدمة" required><input name="quantity[]" type="number" min="1" step="1" value="1" aria-label="الكمية" required><select name="unit[]" aria-label="الوحدة"><option>قطعة</option><option>كيلو</option><option>متر</option><option>متر مربع</option></select><input name="unit_price[]" type="number" min="0" step="0.01" value="0" aria-label="السعر" required><input name="item_note[]" aria-label="الملاحظة" placeholder="ملاحظة"><b class="invoice-edit-line-total">0.00 ₪</b><button type="button" class="icon-close remove-invoice-row" aria-label="حذف البند">×</button></div>');updateInvoiceEditTotal()});
  updateInvoiceEditTotal();
}
