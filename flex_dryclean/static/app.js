document.querySelectorAll('[data-open]').forEach(button=>button.addEventListener('click',()=>document.getElementById(button.dataset.open)?.showModal()));
document.querySelectorAll('[data-close]').forEach(button=>button.addEventListener('click',()=>button.closest('dialog')?.close()));
document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close()}));
document.querySelectorAll('tr[data-href]').forEach(row=>row.addEventListener('click',()=>location.href=row.dataset.href));

const cart=document.getElementById('cart');
const cartItems=[];
function renderCart(){
  if(!cart)return;
  if(!cartItems.length){cart.innerHTML='<p class="empty">لم تتم إضافة قطع بعد.</p>';return;}
  cart.innerHTML=cartItems.map((item,index)=>`<div class="cart-line"><span><b>${item.name}</b><small>${Number(item.price).toFixed(2)} ₪ / ${item.unit}</small></span><input type="hidden" name="service_id[]" value="${item.id}"><input aria-label="الكمية" name="quantity[]" type="number" min="0.01" step="0.01" value="${item.quantity}"><b>${(item.price*item.quantity).toFixed(2)} ₪</b><button type="button" data-remove="${index}">×</button></div>`).join('');
  cart.querySelectorAll('input[name="quantity[]"]').forEach((input,index)=>input.addEventListener('input',()=>{cartItems[index].quantity=Number(input.value||1);renderCart()}));
  cart.querySelectorAll('[data-remove]').forEach(button=>button.addEventListener('click',()=>{cartItems.splice(Number(button.dataset.remove),1);renderCart()}));
}
document.querySelectorAll('.service-chip').forEach(button=>button.addEventListener('click',()=>{const service=JSON.parse(button.dataset.service);const found=cartItems.find(item=>item.id===service.id);if(found)found.quantity+=1;else cartItems.push({...service,quantity:1});renderCart()}));

if('serviceWorker' in navigator)navigator.serviceWorker.register('sw.js',{scope:'./'}).catch(()=>{});
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
  const response=await fetch('/api/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})});
  const data=await response.json();
  if(data.ok)location.href=data.url;else alert(data.message);
});
