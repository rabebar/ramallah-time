"use strict";

(function () {
  const q = document.getElementById("q");
  const searchBtn = document.getElementById("searchBtn");
  const nearBtn = document.getElementById("nearBtn");

  function toast(msg) {
    // Toast صغير وخفيف بدون اعتماد على CSS خارجي
    const el = document.createElement("div");
    el.textContent = msg;
    el.style.position = "fixed";
    el.style.top = "14px";
    el.style.left = "14px";
    el.style.zIndex = "99999";
    el.style.background = "rgba(2,6,23,0.92)";
    el.style.border = "1px solid rgba(255,255,255,0.10)";
    el.style.color = "#fff";
    el.style.padding = "10px 12px";
    el.style.borderRadius = "12px";
    el.style.fontWeight = "900";
    el.style.boxShadow = "0 12px 30px rgba(0,0,0,0.35)";
    el.style.maxWidth = "85vw";
    el.style.direction = "rtl";
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2200);
  }

  function goSearch() {
    const term = (q && q.value ? q.value : "").trim();
    const url = term ? `/places?q=${encodeURIComponent(term)}` : `/places`;
    window.location.href = url;
  }

  // --- Search events ---
  if (searchBtn) {
    searchBtn.addEventListener("click", goSearch);
  }

  if (q) {
    q.addEventListener("keydown", (e) => {
      if (e.key === "Enter") goSearch();
    });
  }

  // --- Near me ---
  let nearBusy = false;

  function goNearFallback() {
    window.location.href = "/places?near=1";
  }

  function goNear() {
    if (nearBusy) return;
    nearBusy = true;

    if (nearBtn) nearBtn.disabled = true;
    toast("جاري تحديد موقعك...");

    if (!("geolocation" in navigator)) {
      toast("المتصفح لا يدعم تحديد الموقع. سيتم فتح الأماكن.");
      setTimeout(goNearFallback, 600);
      return;
    }

    const opts = {
      enableHighAccuracy: false, // أسرع وأخف
      timeout: 8000,
      maximumAge: 60000
    };

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;

        // نمرّر الإحداثيات للباك-إند/صفحة الأماكن
        const url = `/places?near=1&lat=${encodeURIComponent(lat)}&lng=${encodeURIComponent(lng)}`;
        window.location.href = url;
      },
      (err) => {
        // رفض المستخدم/timeout/أي خطأ => fallback
        if (err && err.code === 1) toast("تم رفض إذن الموقع. سيتم فتح الأماكن.");
        else toast("تعذر تحديد الموقع. سيتم فتح الأماكن.");
        setTimeout(goNearFallback, 600);
      },
      opts
    );
  }

  if (nearBtn) {
    nearBtn.addEventListener("click", goNear);
  }
})();
// --- جلب الأماكن الحقيقية وعرضها في الصفحة الرئيسية ---
  async function loadFeatured() {
    const featuredGrid = document.querySelector(".featured");
    if (!featuredGrid) return;

    try {
      // نطلب أول 3 أماكن موجودة في النظام
      const res = await fetch("/api/places?limit=3"); 
      const data = await res.json();
      const items = data.items || [];

      if (items.length > 0) {
        featuredGrid.innerHTML = ""; // مسح الأماكن التجريبية
        
        items.forEach(p => {
          // استخدام أول صورة للمكان أو صورة افتراضية إذا لم توجد
          const img = (p.images && p.images.length > 0) ? p.images[0].image_url : "https://via.placeholder.com/600x400";
          
          featuredGrid.innerHTML += `
            <a class="place" href="/places">
              <div class="img" style="background-image:url('${img}'); background-size:cover; background-position:center; height:180px;"></div>
              <div class="body">
                <p class="name" style="font-weight:900; color:#fff;">${p.name}</p>
                <p class="meta" style="font-size:13px; color:#94a3b8;"><i class="fa-solid fa-location-dot"></i> ${p.area || 'رام الله'} • ${p.category}</p>
                <div class="actions" style="margin-top:10px; display:flex; gap:8px;">
                  <span class="pill whatsapp" style="font-size:11px; padding:5px 10px;"><i class="fa-brands fa-whatsapp"></i> واتساب</span>
                  <span class="pill" style="font-size:11px; padding:5px 10px;"><i class="fa-solid fa-eye"></i> عرض</span>
                </div>
              </div>
            </a>`;
        });
      }
    } catch (e) { 
        console.log("خطأ في جلب بيانات الصفحة الرئيسية"); 
    }
  }

  // تشغيل الجلب التلقائي عند فتح الصفحة
  document.addEventListener("DOMContentLoaded", loadFeatured);
