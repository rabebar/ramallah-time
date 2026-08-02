(()=>{
  let timer;
  const details={success:{icon:"✓",title:"تم بنجاح"},warning:{icon:"!",title:"تنبيه"},error:{icon:"×",title:"تعذر الإجراء"},info:{icon:"م",title:"رسالة من مُعين"}};
  window.moeenToast=(message,tone="success",title="")=>{
    let toast=document.getElementById("moeenToast");
    if(!toast){
      toast=document.createElement("div");toast.id="moeenToast";toast.className="moeen-toast";toast.setAttribute("role","status");toast.setAttribute("aria-live","polite");
      toast.innerHTML='<span class="moeen-toast-icon" aria-hidden="true"></span><span class="moeen-toast-copy"><strong></strong><small></small></span><button type="button" aria-label="إغلاق">×</button><i aria-hidden="true"></i>';
      toast.querySelector("button").onclick=()=>toast.classList.remove("visible");document.body.appendChild(toast);
    }
    const current=details[tone]||details.info;toast.querySelector(".moeen-toast-icon").textContent=current.icon;toast.querySelector("strong").textContent=title||current.title;toast.querySelector("small").textContent=message;toast.dataset.tone=tone;toast.classList.remove("visible");void toast.offsetWidth;toast.classList.add("visible");clearTimeout(timer);timer=setTimeout(()=>toast.classList.remove("visible"),5200);
  };
})();
