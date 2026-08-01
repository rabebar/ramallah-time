(()=>{
  let timer;
  window.moeenToast=(message,tone="success")=>{
    let toast=document.getElementById("moeenToast");
    if(!toast){toast=document.createElement("div");toast.id="moeenToast";toast.className="moeen-toast";toast.setAttribute("role","status");toast.setAttribute("aria-live","polite");document.body.appendChild(toast)}
    toast.textContent=message;toast.dataset.tone=tone;toast.classList.add("visible");clearTimeout(timer);timer=setTimeout(()=>toast.classList.remove("visible"),4200);
  };
})();
