const categories = [
  { id: "home", label: "الرئيسية" },
  { id: "syria", label: "سوريا" },
  { id: "palestine", label: "فلسطين" },
  { id: "articles", label: "مقالات" },
  { id: "hebrew", label: "ترجمات عبرية" },
  { id: "international", label: "ترجمات دولية" },
  { id: "middle-east", label: "الشرق الأوسط" },
  { id: "support", label: "ادعم الميزان" }
];

const categoryNames = Object.fromEntries(categories.map((category) => [category.id, category.label]));
const newsKey = "mizan_news_v3";
const adminsKey = "mizan_admins_v1";
const mizanBasePath = String(window.MIZAN_BASE_PATH || "").replace(/\/$/, "");
const mizanHomePath = mizanBasePath || "/";
const mizanUrl = (path) => location.protocol === "file:" ? path : `${mizanBasePath}${path}`;
let activeView = "home";
let currentAdmin = localStorage.getItem("mizan_current_admin") || "";
let currentAdminPassword = sessionStorage.getItem("mizan_current_admin_password") || "";
let currentAdminRole = localStorage.getItem("mizan_current_admin_role") || "admin";
let searchTerm = "";
let serverMode = false;
let serverNews = null;
let editingNewsId = "";
let activeAdminTab = "overview";

function loadInitialServerNews() {
  const initialNewsScript = document.querySelector("#initialNewsData");
  if (!initialNewsScript?.textContent) {
    return false;
  }

  try {
    const news = JSON.parse(initialNewsScript.textContent);
    if (Array.isArray(news)) {
      serverMode = true;
      serverNews = news;
      return true;
    }
  } catch (error) {
    console.warn("Initial news payload could not be parsed:", error);
  }

  return false;
}

function makeId() {
  return crypto.randomUUID?.() || `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

const fallbackImage = "data:image/svg+xml;charset=UTF-8," + encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675">
  <defs>
    <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0" stop-color="#f6faf7"/>
      <stop offset=".55" stop-color="#e8f1eb"/>
      <stop offset="1" stop-color="#fff7e2"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="675" fill="url(#g)"/>
  <rect x="90" y="92" width="1020" height="2" fill="#dfe7e2"/>
  <rect x="90" y="565" width="1020" height="2" fill="#dfe7e2"/>
  <rect x="90" y="125" width="18" height="425" fill="#c92a32"/>
  <rect x="128" y="125" width="18" height="425" fill="#247a4b"/>
  <rect x="166" y="125" width="18" height="425" fill="#d9a22b"/>
  <circle cx="820" cy="330" r="170" fill="#ffffff" opacity=".62"/>
  <path d="M560 290h420v16H560zm0 52h340v16H560zm0 52h260v16H560z" fill="#9aaaa1"/>
  <text x="600" y="206" text-anchor="middle" font-family="Tahoma, Arial" font-size="44" font-weight="700" fill="#18251f">الميزان السياسي</text>
</svg>`);

const fallbackAuthorImage = "data:image/svg+xml;charset=UTF-8," + encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160">
  <rect width="160" height="160" fill="#eef1e9"/>
  <circle cx="80" cy="58" r="30" fill="#23433a"/>
  <path d="M34 140c8-33 28-50 46-50s38 17 46 50" fill="#c9a877"/>
</svg>`);

const canonicalAuthorImages = {
  "ربيع البرغوثي": mizanUrl("/rabee-albarghouti-author.png")
};

function authorImageFor(item) {
  return canonicalAuthorImages[String(item.authorName || "").trim()]
    || item.authorImage
    || fallbackAuthorImage;
}

const seedNews = [
  {
    id: makeId(),
    title: "قراءة في تحولات الخطاب الإسرائيلي تجاه غزة والضفة",
    category: "hebrew",
    placement: "main",
    image: fallbackImage,
    summary: "ترجمة وتحليل لمسارات النقاش في الإعلام العبري حول مستقبل المواجهة والسياسة الداخلية.",
    body: "نموذج خبر تجريبي يمكن تعديله من لوحة الإدارة.",
    createdAt: Date.now() - 1000 * 60 * 12
  },
  {
    id: makeId(),
    title: "سوريا بين ترتيبات الإقليم وحسابات الداخل",
    category: "syria",
    placement: "after-main-1",
    image: fallbackImage,
    summary: "تحليل يستعرض موقع سوريا في التفاعلات الإقليمية بعيدًا عن التبسيط والانفعال.",
    body: "",
    createdAt: Date.now() - 1000 * 60 * 50
  },
  {
    id: makeId(),
    title: "فلسطين في تقارير مراكز الدراسات: بين الأمن والسياسة",
    category: "palestine",
    placement: "after-main-2",
    image: fallbackImage,
    summary: "خلاصة بحثية تضع تقارير مراكز الدراسات في سياقها السياسي والمعرفي.",
    body: "",
    createdAt: Date.now() - 1000 * 60 * 120
  },
  {
    id: makeId(),
    title: "مؤشرات الشرق الأوسط في الإعلام الدولي",
    category: "middle-east",
    placement: "normal",
    image: fallbackImage,
    summary: "رصد لأبرز الاتجاهات في تغطية المنطقة داخل الصحافة العالمية.",
    body: "",
    createdAt: Date.now() - 1000 * 60 * 240
  },
  {
    id: makeId(),
    title: "لماذا نحتاج إلى قراءة سياسية بطيئة في زمن الخبر السريع؟",
    category: "articles",
    placement: "normal",
    image: fallbackImage,
    authorName: "هيئة التحرير",
    authorImage: fallbackAuthorImage,
    summary: "مقال افتتاحي عن ضرورة التمييز بين الخبر والتحليل، وبين المعلومة المؤكدة والانطباع السياسي.",
    body: "",
    createdAt: Date.now() - 1000 * 60 * 300
  }
];

function getNews() {
  if (serverMode && Array.isArray(serverNews)) {
    return serverNews;
  }
  if (location.protocol !== "file:") {
    return Array.isArray(serverNews) ? serverNews : [];
  }
  try {
    const stored = localStorage.getItem(newsKey);
    if (!stored) {
      localStorage.setItem(newsKey, JSON.stringify(seedNews));
      return seedNews;
    }
    return JSON.parse(stored);
  } catch {
    localStorage.removeItem(newsKey);
    return seedNews;
  }
}

function setNews(news) {
  try {
    localStorage.setItem(newsKey, JSON.stringify(news));
    return true;
  } catch (error) {
    console.warn("Local news cache could not be saved:", error);
    return false;
  }
}

function getAdmins() {
  return JSON.parse(localStorage.getItem(adminsKey) || "[]");
}

function setAdmins(admins) {
  localStorage.setItem(adminsKey, JSON.stringify(admins));
}

async function apiRequest(path, options = {}) {
  const response = await fetch(mizanUrl(path), {
    ...options,
    headers: {
      "content-type": "application/json",
      ...(options.headers || {})
    }
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

async function syncNewsFromServer(includeAdminData = false) {
  if (location.protocol === "file:") {
    return false;
  }

  try {
    const news = await apiRequest("/api/news", includeAdminData ? { headers: adminHeaders() } : {});
    if (Array.isArray(news)) {
      serverMode = true;
      serverNews = news.length ? news : seedNews;
      return true;
    }
  } catch {
    serverMode = Array.isArray(serverNews);
  }
  return false;
}

async function saveNewsToServer(item) {
  if (!serverMode) {
    return false;
  }

  const savedItem = await apiRequest("/api/news", {
    method: "POST",
    headers: {
      "x-admin-user": currentAdmin,
      "x-admin-pass": currentAdminPassword
    },
    body: JSON.stringify(item)
  });
  const currentNews = Array.isArray(serverNews) ? serverNews : [];
  const exists = currentNews.some((newsItem) => newsItem.id === savedItem.id);
  serverNews = exists
    ? currentNews.map((newsItem) => newsItem.id === savedItem.id ? savedItem : newsItem)
    : [savedItem, ...currentNews];
  return true;
}

async function deleteNewsFromServer(id) {
  if (!serverMode) {
    return false;
  }

  await apiRequest(`/api/news/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: {
      "x-admin-user": currentAdmin,
      "x-admin-pass": currentAdminPassword
    }
  });
  if (Array.isArray(serverNews)) {
    serverNews = serverNews.filter((item) => item.id !== id);
  }
  return true;
}

async function publishNewsToTelegram(id) {
  if (!serverMode) {
    throw new Error("Server publishing is unavailable");
  }
  return apiRequest(`/api/news/${encodeURIComponent(id)}/telegram`, {
    method: "POST",
    headers: adminHeaders()
  });
}

function adminHeaders() {
  return {
    "x-admin-user": currentAdmin,
    "x-admin-pass": currentAdminPassword
  };
}

function hasActiveSuperAdminSession() {
  return Boolean(serverMode && currentAdmin && currentAdminPassword && currentAdminRole === "super_admin");
}

async function loginViaServer(username, password) {
  if (!serverMode) {
    return false;
  }
  return apiRequest("/api/admins/login", {
    method: "POST",
    body: JSON.stringify({ username, password })
  });
}

async function fetchAdminsFromServer() {
  if (!hasActiveSuperAdminSession()) {
    return [];
  }

  return apiRequest("/api/admins", {
    headers: adminHeaders()
  });
}

async function fetchAnalyticsFromServer() {
  if (!hasActiveSuperAdminSession()) {
    return null;
  }

  return apiRequest("/api/analytics", {
    headers: adminHeaders()
  });
}

async function createAdminOnServer(admin) {
  return apiRequest("/api/admins", {
    method: "POST",
    headers: adminHeaders(),
    body: JSON.stringify(admin)
  });
}

async function deleteAdminFromServer(username) {
  return apiRequest(`/api/admins/${encodeURIComponent(username)}`, {
    method: "DELETE",
    headers: adminHeaders()
  });
}

function visibleNews() {
  let news = getNews().sort((a, b) => b.createdAt - a.createdAt);
  if (activeView !== "home" && activeView !== "support") {
    news = news.filter((item) => item.category === activeView);
  }
  if (searchTerm) {
    const term = searchTerm.toLowerCase();
    news = news.filter((item) => `${item.title} ${item.summary} ${item.body || ""} ${item.authorName || ""}`.toLowerCase().includes(term));
  }
  return news;
}

function renderNav() {
  const nav = document.querySelector("#categoryNav");
  nav.innerHTML = categories.map((category) => `
    <button type="button" class="${activeView === category.id ? "is-active" : ""} ${category.id === "support" ? "support-nav-button" : ""}" data-view="${category.id}">
      ${category.label}
    </button>
  `).join("");
}

function renderBreakingNews() {
  const breakingText = document.querySelector("#breakingText");
  const latest = getNews()
    .slice()
    .sort((a, b) => b.createdAt - a.createdAt)
    .filter((item) => item.title)
    .slice(0, 8);

  breakingText.textContent = latest.length
    ? latest.map((item) => `${categoryNames[item.category] || "مادة"}: ${item.title}`).join(" · ")
    : "تحليل رصين لما وراء الخبر · من الترجمة الدقيقة إلى الفهم العميق · قراءة المصادر والسياقات قبل الاستنتاج";
}

function renderLeads() {
  const leadGrid = document.querySelector("#leadGrid");
  const news = visibleNews();
  const main = news.find((item) => item.placement === "main") || news[0];
  const first = news.find((item) => item.placement === "after-main-1") || news.find((item) => item.id !== main?.id);
  const second = news.find((item) => item.placement === "after-main-2") || news.find((item) => item.id !== main?.id && item.id !== first?.id);

  if (!main) {
    leadGrid.innerHTML = `<article class="main-story empty-story"><div class="story-overlay"><h2>لا توجد أخبار بعد</h2><p>ابدأ بإضافة خبر من لوحة الإدارة.</p></div></article>`;
    return;
  }

  leadGrid.innerHTML = `
    ${mainStory(main)}
    <div class="side-stories">
      ${first ? sideStory(first) : ""}
      ${second ? sideStory(second) : ""}
    </div>
  `;
}

function postPath(id) {
  return `${mizanBasePath}/post/${encodeURIComponent(id)}`;
}

function postRoute(id) {
  return location.protocol === "file:" ? `#post/${encodeURIComponent(id)}` : postPath(id);
}

function fullPostUrl(id) {
  const url = new URL(location.href);
  if (url.protocol === "file:") {
    url.hash = `post/${encodeURIComponent(id)}`;
  } else {
    url.pathname = postPath(id);
    url.hash = "";
    url.search = "";
  }
  return url.href;
}

function getPostIdFromLocation() {
  if (location.hash.startsWith("#post/")) {
    return decodeURIComponent(location.hash.replace("#post/", ""));
  }

  const postPrefix = `${mizanBasePath}/post/`;
  if (location.pathname.startsWith(postPrefix)) {
    return decodeURIComponent(location.pathname.replace(postPrefix, ""));
  }

  return "";
}

function setHomeVisibility(isHome) {
  document.querySelector(".mission-strip").classList.toggle("hidden", !isHome);
  document.querySelector("#leadGrid").classList.toggle("hidden", !isHome);
  document.querySelector(".latest-section").classList.toggle("hidden", !isHome);
  document.querySelector(".analysis-band").classList.toggle("hidden", !isHome);
  document.querySelector("#postView").classList.toggle("hidden", isHome);
  document.querySelector("#supportView").classList.add("hidden");
}

function mainStory(item) {
  return `
    <article class="main-story post-link" data-open-post="${item.id}" role="link" tabindex="0">
      <img src="${item.image || fallbackImage}" alt="">
      <div class="story-overlay">
        <span class="story-tag">${categoryNames[item.category] || "خبر"}</span>
        <h2>${item.title}</h2>
        ${authorBlock(item)}
        <p>${item.summary}</p>
      </div>
    </article>
  `;
}

function sideStory(item) {
  return `
    <article class="side-card post-link" data-open-post="${item.id}" role="link" tabindex="0">
      <img src="${item.image || fallbackImage}" alt="">
      <div>
        <span class="story-tag">${categoryNames[item.category] || "خبر"}</span>
        <h3>${item.title}</h3>
        ${authorBlock(item)}
        <div class="meta">${placementName(item.placement)}</div>
      </div>
    </article>
  `;
}

function renderNewsList() {
  const list = document.querySelector("#newsList");
  const sectionHeading = document.querySelector("#sectionHeading");
  const sectionCount = document.querySelector("#sectionCount");
  const news = visibleNews();
  sectionHeading.textContent = searchTerm ? `نتائج البحث عن: ${searchTerm}` : activeView === "home" ? "آخر الأخبار والتحليلات" : categoryNames[activeView];
  sectionCount.textContent = `${news.length} مادة`;

  list.innerHTML = news.map((item) => `
    <article class="news-card post-link" data-open-post="${item.id}" role="link" tabindex="0">
      <img src="${item.image || fallbackImage}" alt="">
      <div class="card-body">
        <span class="story-tag">${categoryNames[item.category] || "خبر"}</span>
        <h3>${item.title}</h3>
        ${authorBlock(item)}
        <p>${item.summary}</p>
        <div class="meta">${placementName(item.placement)}</div>
      </div>
    </article>
  `).join("");
}

function renderPostView(id) {
  const postView = document.querySelector("#postView");
  const item = getNews().find((newsItem) => newsItem.id === id);

  if (!item) {
    setHomeVisibility(false);
    postView.innerHTML = `
      <article class="post-full">
        <button class="ghost" type="button" data-back-home>العودة للرئيسية</button>
        <h1>المادة غير موجودة</h1>
        <p>ربما تم حذف الخبر أو تغيّر الرابط.</p>
      </article>
    `;
    return;
  }

  document.title = `${item.title} | مؤسسة الميزان السياسي`;
  setHomeVisibility(false);
  postView.innerHTML = `
    <article class="post-full">
      <div class="post-actions">
        <button class="ghost" type="button" data-back-home>العودة للرئيسية</button>
        <div>
          <button class="ghost" type="button" data-copy-link="${item.id}">نسخ الرابط</button>
          <button class="primary" type="button" data-print-post>طباعة</button>
        </div>
      </div>
      <span class="story-tag">${categoryNames[item.category] || "خبر"}</span>
      <h1>${item.title}</h1>
      ${authorBlock(item)}
      <p class="post-summary">${item.summary}</p>
      <img class="post-hero" src="${item.image || fallbackImage}" alt="">
      <div class="post-body">${formatPostBody(item.body || item.summary)}</div>
    </article>
  `;
}

function renderSupportView() {
  document.title = "ادعم مؤسسة الميزان السياسي | مؤسسة الميزان السياسي";
  setHomeVisibility(false);
  document.querySelector("#postView").classList.add("hidden");
  const supportView = document.querySelector("#supportView");
  supportView.classList.remove("hidden");
  supportView.innerHTML = `
    <section class="support-hero">
      <div>
        <span class="story-tag">دعم مستقل</span>
        <h1>ادعم مؤسسة الميزان السياسي</h1>
        <p>
          يساعدنا دعمكم في استمرار الترجمة الإعلامية والتحليل السياسي العلمي المستقل،
          بعيدًا عن الضجيج والمناكفات، وبما يضمن إنتاج مواد رصينة تعتمد على المصادر والسياقات والتحقق.
        </p>
      </div>
      <div class="support-qr-card">
        <img src="${mizanUrl("/support-qr.jpeg")}" alt="رمز QR للدعم عبر بنك فلسطين">
        <span>امسح الرمز للدعم عبر محفظة بنك فلسطين</span>
      </div>
    </section>

    <section class="support-details">
      <div class="support-info">
        <h2>التحويل البنكي بالدولار</h2>
        <dl>
          <div>
            <dt>اسم المستفيد</dt>
            <dd><code>RABE ALBARGHOUTHI</code></dd>
          </div>
          <div>
            <dt>IBAN</dt>
            <dd><code>PS72PALS045802050490013100000</code></dd>
          </div>
          <div>
            <dt>البنك</dt>
            <dd>Bank of Palestine</dd>
          </div>
          <div>
            <dt>العملة</dt>
            <dd>USD</dd>
          </div>
        </dl>
        <div class="support-actions">
          <button class="primary" type="button" data-copy-text="PS72PALS045802050490013100000">نسخ رقم IBAN</button>
          <button class="ghost" type="button" data-copy-text="RABE ALBARGHOUTHI">نسخ اسم المستفيد</button>
        </div>
      </div>
      <aside class="support-note">
        <h2>ملاحظة</h2>
        <p>
          عند إجراء تحويل، يمكن كتابة ملاحظة: دعم الميزان. هذا الدعم لا يؤثر على الخط التحريري للمؤسسة
          ولا يغيّر معيارنا الأساسي: وزن الخبر والمعلومة قبل نشرها.
        </p>
      </aside>
    </section>
  `;
}

function formatPostBody(text) {
  return String(text || "")
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
    .map((paragraph) => `<p>${linkifyText(paragraph).replace(/\n/g, "<br>")}</p>`)
    .join("");
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function linkifyText(value) {
  const escaped = escapeHtml(value);
  return escaped.replace(/(https?:\/\/[^\s<]+)/g, (url) => {
    const cleanUrl = url.replace(/[،.؛)]+$/g, "");
    const suffix = url.slice(cleanUrl.length);
    return `<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer">${cleanUrl}</a>${suffix}`;
  });
}

function authorBlock(item) {
  if (!item.authorName && item.category !== "articles") {
    return "";
  }

  return `
    <div class="author-mini">
      <img src="${authorImageFor(item)}" alt="صورة ${item.authorName || "كاتب المقال"}">
      <span>${item.authorName || "كاتب المقال"}</span>
    </div>
  `;
}

function renderSite() {
  renderBreakingNews();
  const postId = getPostIdFromLocation();
  if (postId) {
    renderPostView(postId);
    return;
  }
  if (activeView === "support") {
    renderNav();
    renderSupportView();
    return;
  }
  document.title = "مؤسسة الميزان السياسي للأبحاث والترجمة الإعلامية";
  setHomeVisibility(true);
  renderNav();
  renderLeads();
  renderNewsList();
}

function openAdmin() {
  document.querySelector("#adminDialog").showModal();
  renderAdminState();
}

function closeAdmin() {
  document.querySelector("#adminDialog").close();
  if (location.hash === "#admin") {
    history.replaceState(null, "", location.pathname + location.search);
  }
}

function renderAdminState() {
  const authView = document.querySelector("#authView");
  const dashboard = document.querySelector("#dashboard");
  const currentAdminEl = document.querySelector("#currentAdmin");
  const superPanel = document.querySelector("#superAdminPanel");
  const analyticsSection = document.querySelector("#analyticsSection");
  const superNav = document.querySelector("[data-super-admin-nav]");
  const overviewPanel = document.querySelector("#adminOverviewPanel");
  authView.classList.toggle("hidden", Boolean(currentAdmin));
  dashboard.classList.toggle("hidden", !currentAdmin);
  superPanel.classList.toggle("hidden", currentAdminRole !== "super_admin");
  analyticsSection?.classList.toggle("hidden", currentAdminRole !== "super_admin");
  superNav?.classList.toggle("hidden", currentAdminRole !== "super_admin");
  currentAdminEl.textContent = currentAdmin ? `مرحبًا، ${currentAdmin} · ${roleName(currentAdminRole)}` : "";
  if (currentAdmin) {
    if (currentAdminRole !== "super_admin" && activeAdminTab === "permissions") {
      activeAdminTab = "overview";
    }
    if (!editingNewsId) {
      setEditorMode();
    }
    if (overviewPanel && analyticsSection && analyticsSection.parentElement !== overviewPanel) {
      overviewPanel.appendChild(analyticsSection);
    }
    renderAdminTabs();
    renderAdminSummary();
    renderAdminNews();
    renderAdminUsers();
    renderAnalytics();
  }
}

function renderAdminTabs() {
  document.querySelectorAll("[data-admin-tab]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.adminTab === activeAdminTab);
  });

  document.querySelectorAll("[data-admin-panel]").forEach((panel) => {
    panel.classList.toggle("hidden", panel.dataset.adminPanel !== activeAdminTab);
  });

  if (activeAdminTab === "permissions" && currentAdminRole === "super_admin") {
    document.querySelector("#superAdminPanel")?.classList.remove("hidden");
  }

  if (activeAdminTab === "overview" && currentAdminRole === "super_admin") {
    document.querySelector("#analyticsSection")?.classList.remove("hidden");
  }
}

function renderAdminSummary() {
  const cards = document.querySelector("#adminSummaryCards");
  if (!cards) {
    return;
  }

  const news = getNews();
  const articlesCount = news.filter((item) => item.category === "articles").length;
  const mainCount = news.filter((item) => item.placement === "main" || item.placement === "after-main-1" || item.placement === "after-main-2").length;
  const latest = news.slice().sort((a, b) => b.createdAt - a.createdAt)[0];
  cards.innerHTML = `
    <div class="summary-card">
      <strong>${formatNumber(news.length)}</strong>
      <span>كل المواد المنشورة</span>
    </div>
    <div class="summary-card">
      <strong>${formatNumber(articlesCount)}</strong>
      <span>مقالات</span>
    </div>
    <div class="summary-card">
      <strong>${formatNumber(mainCount)}</strong>
      <span>مواد في الواجهة الرئيسية</span>
    </div>
    <div class="summary-card summary-card--wide">
      <strong>${latest ? latest.title : "لا توجد مواد بعد"}</strong>
      <span>آخر مادة منشورة</span>
    </div>
  `;
}

function renderAdminNews() {
  const adminList = document.querySelector("#adminNewsList");
  const news = getNews().sort((a, b) => b.createdAt - a.createdAt);
  adminList.innerHTML = news.map((item) => `
    <div class="admin-row">
      <div>
        <strong>${item.title}</strong>
        <p>${categoryNames[item.category]} · ${placementName(item.placement)}</p>
      </div>
      <div class="row-actions">
        <button class="ghost" type="button" data-telegram="${item.id}">إعادة النشر على تلغرام</button>
        <button class="ghost" type="button" data-edit="${item.id}">تعديل</button>
        <button class="danger" type="button" data-delete="${item.id}">حذف</button>
      </div>
    </div>
  `).join("");
}

function setEditorMode(item = null) {
  const state = document.querySelector("#editorState");
  const saveButton = document.querySelector("#saveMaterialButton");
  const form = document.querySelector("#newsForm");

  editingNewsId = item?.id || "";
  form.elements.id.value = editingNewsId;

  if (item) {
    state.innerHTML = `
      <strong>تعديل مادة منشورة</strong>
      <span>أنت تعدّل: ${item.title}. استخدم زر إلغاء التعديل إذا أردت نشر مادة جديدة.</span>
    `;
    saveButton.textContent = "حفظ التعديل";
    state.classList.add("is-editing");
    return;
  }

  state.innerHTML = `
    <strong>إضافة مادة جديدة</strong>
    <span>سيتم نشر مادة جديدة ولن يتم تعديل أي مادة منشورة.</span>
  `;
  saveButton.textContent = "نشر مادة جديدة";
  state.classList.remove("is-editing");
}

async function renderAdminUsers() {
  const list = document.querySelector("#adminUsersList");
  const message = document.querySelector("#adminUserMessage");

  if (currentAdminRole !== "super_admin") {
    list.innerHTML = "";
    return;
  }

  if (!currentAdminPassword) {
    list.innerHTML = "";
    message.textContent = "";
    return;
  }

  if (!serverMode) {
    list.innerHTML = `<p class="note">إدارة المدراء تعمل على النسخة المنشورة فقط.</p>`;
    return;
  }

  try {
    const admins = await fetchAdminsFromServer();
    list.innerHTML = admins.map((admin) => `
      <div class="admin-row">
        <div>
          <strong>${admin.username}</strong>
          <p>${roleName(admin.role)} · ${admin.source === "env" ? "حساب ثابت من Render" : "حساب مضاف من اللوحة"}</p>
        </div>
        <div class="row-actions">
          ${admin.source === "env" ? "" : `<button class="danger" type="button" data-delete-admin="${admin.username}">حذف الصلاحية</button>`}
        </div>
      </div>
    `).join("");
    message.textContent = "";
  } catch {
    list.innerHTML = "";
    message.textContent = "تعذر تحميل قائمة المدراء.";
  }
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("ar");
}

async function renderAnalytics() {
  const cards = document.querySelector("#analyticsCards");
  const topPostsList = document.querySelector("#topPostsList");
  const categoryStatsList = document.querySelector("#categoryStatsList");
  const message = document.querySelector("#analyticsMessage");

  if (!cards || currentAdminRole !== "super_admin") {
    return;
  }

  if (!currentAdminPassword) {
    cards.innerHTML = "";
    topPostsList.innerHTML = "";
    categoryStatsList.innerHTML = "";
    message.textContent = "";
    return;
  }

  if (!serverMode) {
    cards.innerHTML = "";
    topPostsList.innerHTML = "";
    categoryStatsList.innerHTML = "";
    message.textContent = "الإحصائيات تعمل على النسخة المنشورة المرتبطة بقاعدة البيانات فقط.";
    return;
  }

  cards.innerHTML = `
    <div class="analytics-card"><strong>...</strong><span>إجمالي الزيارات</span></div>
    <div class="analytics-card"><strong>...</strong><span>آخر 24 ساعة</span></div>
    <div class="analytics-card"><strong>...</strong><span>آخر 7 أيام</span></div>
    <div class="analytics-card"><strong>...</strong><span>آخر 30 يوماً</span></div>
  `;
  topPostsList.innerHTML = `<p class="note">جاري تحميل الأكثر قراءة...</p>`;
  categoryStatsList.innerHTML = "";
  message.textContent = "";

  try {
    const data = await fetchAnalyticsFromServer();
    const totals = data?.totals || {};
    cards.innerHTML = `
      <div class="analytics-card"><strong>${formatNumber(totals.total)}</strong><span>إجمالي الزيارات</span></div>
      <div class="analytics-card"><strong>${formatNumber(totals.last24h)}</strong><span>آخر 24 ساعة</span></div>
      <div class="analytics-card"><strong>${formatNumber(totals.last7d)}</strong><span>آخر 7 أيام</span></div>
      <div class="analytics-card"><strong>${formatNumber(totals.last30d)}</strong><span>آخر 30 يوماً</span></div>
    `;

    topPostsList.innerHTML = data.topPosts?.length
      ? data.topPosts.map((item) => `
        <div class="analytics-row">
          <div>
            <strong>${item.title}</strong>
            <span>${categoryNames[item.category] || "مادة منشورة"}</span>
          </div>
          <div class="analytics-count">${formatNumber(item.visits)}</div>
        </div>
      `).join("")
      : `<p class="note">لا توجد زيارات لمواد منشورة بعد.</p>`;

    categoryStatsList.innerHTML = data.categories?.length
      ? data.categories.map((item) => `
        <div class="analytics-row">
          <div>
            <strong>${categoryNames[item.category] || item.category || "الرئيسية"}</strong>
            <span>زيارات مسجلة</span>
          </div>
          <div class="analytics-count">${formatNumber(item.visits)}</div>
        </div>
      `).join("")
      : `<p class="note">لا توجد زيارات مسجلة بعد.</p>`;

    message.textContent = "الأرقام تستبعد زيارات المعاينة الآلية قدر الإمكان، وتدمج تكرار نفس الزائر لنفس الصفحة خلال 30 دقيقة.";
  } catch {
    cards.innerHTML = "";
    topPostsList.innerHTML = "";
    categoryStatsList.innerHTML = "";
    message.textContent = "تعذر تحميل الإحصائيات. تأكد من تسجيل الدخول كسوبر أدمن.";
  }
}

function roleName(role) {
  return role === "super_admin" ? "سوبر أدمن" : "أدمن تحرير";
}

function placementName(placement) {
  return {
    main: "رئيسي",
    "after-main-1": "أول بعد الرئيسي",
    "after-main-2": "ثاني بعد الرئيسي",
    normal: "خبر عادي"
  }[placement] || "خبر عادي";
}

function fillCategorySelect() {
  const select = document.querySelector('select[name="category"]');
  select.innerHTML = categories
    .filter((category) => category.id !== "home")
    .map((category) => `<option value="${category.id}">${category.label}</option>`)
    .join("");
}

function readImageFromFields(fields, fileFieldName, urlFieldName) {
  const file = fields[fileFieldName].files[0];
  if (!file) {
    return Promise.resolve(fields[urlFieldName].value.trim());
  }

  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.readAsDataURL(file);
  });
}

function readImage(form) {
  return readImageFromFields(form.elements, "imageFile", "imageUrl");
}

document.addEventListener("click", async (event) => {
  const postLink = event.target.closest("[data-open-post]");
  if (postLink) {
    history.pushState(null, "", postRoute(postLink.dataset.openPost));
    renderSite();
    window.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }

  if (event.target.closest("[data-back-home]")) {
    history.pushState(null, "", location.protocol === "file:" ? location.pathname + location.search : mizanHomePath);
    renderSite();
    window.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }

  const copyButton = event.target.closest("[data-copy-link]");
  if (copyButton) {
    const link = fullPostUrl(copyButton.dataset.copyLink);
    try {
      await navigator.clipboard.writeText(link);
      copyButton.textContent = "تم نسخ الرابط";
      setTimeout(() => {
        copyButton.textContent = "نسخ الرابط";
      }, 1400);
    } catch {
      prompt("انسخ الرابط:", link);
    }
    return;
  }

  const copyTextButton = event.target.closest("[data-copy-text]");
  if (copyTextButton) {
    const originalText = copyTextButton.textContent;
    try {
      await navigator.clipboard.writeText(copyTextButton.dataset.copyText);
      copyTextButton.textContent = "تم النسخ";
      setTimeout(() => {
        copyTextButton.textContent = originalText;
      }, 1400);
    } catch {
      prompt("انسخ النص:", copyTextButton.dataset.copyText);
    }
    return;
  }

  if (event.target.closest("[data-print-post]")) {
    window.print();
    return;
  }

  const viewButton = event.target.closest("[data-view]");
  if (viewButton) {
    activeView = viewButton.dataset.view;
    searchTerm = "";
    document.querySelector("#searchInput").value = "";
    if (getPostIdFromLocation()) {
      history.pushState(null, "", location.protocol === "file:" ? location.pathname + location.search : mizanHomePath);
    }
    renderSite();
  }

  if (event.target.closest("[data-close-admin]")) {
    closeAdmin();
  }

  const adminTab = event.target.closest("[data-admin-tab]");
  if (adminTab) {
    activeAdminTab = adminTab.dataset.adminTab;
    renderAdminTabs();
    if (activeAdminTab === "overview") {
      renderAdminSummary();
      renderAnalytics();
    }
    return;
  }

  if (event.target.closest("[data-logout]")) {
    currentAdmin = "";
    currentAdminPassword = "";
    currentAdminRole = "admin";
    localStorage.removeItem("mizan_current_admin");
    localStorage.removeItem("mizan_current_admin_role");
    sessionStorage.removeItem("mizan_current_admin_password");
    renderAdminState();
  }

  const deleteAdminButton = event.target.closest("[data-delete-admin]");
  if (deleteAdminButton) {
    try {
      await deleteAdminFromServer(deleteAdminButton.dataset.deleteAdmin);
      await renderAdminUsers();
    } catch {
      document.querySelector("#adminUserMessage").textContent = "تعذر حذف صلاحية هذا المدير.";
    }
    return;
  }

  const deleteButton = event.target.closest("[data-delete]");
  if (deleteButton) {
    try {
      if (serverMode) {
        await deleteNewsFromServer(deleteButton.dataset.delete);
      } else {
        setNews(getNews().filter((item) => item.id !== deleteButton.dataset.delete));
      }
    } catch {
      alert("تعذر حذف الخبر. تأكد من تسجيل الدخول للوحة الإدارة.");
    }
    renderSite();
    renderAdminNews();
    renderAdminSummary();
  }

  const telegramButton = event.target.closest("[data-telegram]");
  if (telegramButton) {
    const originalLabel = telegramButton.textContent;
    telegramButton.disabled = true;
    telegramButton.textContent = "جارٍ النشر…";
    try {
      await publishNewsToTelegram(telegramButton.dataset.telegram);
      telegramButton.textContent = "تم النشر ✓";
    } catch {
      telegramButton.disabled = false;
      telegramButton.textContent = originalLabel;
      alert("تعذر إعادة النشر على تلغرام. تحقق من إعدادات البوت ورابط الصورة.");
    }
    return;
  }

  const editButton = event.target.closest("[data-edit]");
  if (editButton) {
    const item = getNews().find((newsItem) => newsItem.id === editButton.dataset.edit);
    if (!item) {
      return;
    }
    const form = document.querySelector("#newsForm");
    const fields = form.elements;
    setEditorMode(item);
    activeAdminTab = "editor";
    renderAdminTabs();
    fields.title.value = item.title;
    fields.category.value = item.category;
    fields.placement.value = item.placement;
    fields.authorName.value = item.authorName || "";
    fields.authorImageUrl.value = item.authorImage?.startsWith("data:") ? "" : item.authorImage || "";
    fields.imageUrl.value = item.image?.startsWith("data:") ? "" : item.image;
    fields.summary.value = item.summary;
    fields.body.value = item.body || "";
    form.scrollIntoView({ behavior: "smooth", block: "start" });
  }
});

document.addEventListener("keydown", (event) => {
  const postLink = event.target.closest?.("[data-open-post]");
  if (postLink && (event.key === "Enter" || event.key === " ")) {
    event.preventDefault();
    history.pushState(null, "", postRoute(postLink.dataset.openPost));
    renderSite();
  }
});

document.querySelector("#adminDialog").addEventListener("close", () => {
  if (location.hash === "#admin") {
    history.replaceState(null, "", location.pathname + location.search);
  }
});

document.querySelector("#loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const fields = form.elements;
  const admins = getAdmins();
  const username = fields.username.value.trim();
  const password = fields.password.value;
  const admin = admins.find((item) => item.username === username && item.password === password);
  const authMessage = document.querySelector("#authMessage");

  if (serverMode) {
    try {
      const adminData = await loginViaServer(username, password);
      currentAdmin = username;
      currentAdminPassword = password;
      currentAdminRole = adminData.role || "admin";
      localStorage.setItem("mizan_current_admin", currentAdmin);
      localStorage.setItem("mizan_current_admin_role", currentAdminRole);
      sessionStorage.setItem("mizan_current_admin_password", currentAdminPassword);
      form.reset();
      await syncNewsFromServer(true);
      renderSite();
      renderAdminState();
      return;
    } catch {
      authMessage.textContent = "بيانات الدخول غير صحيحة.";
      return;
    }
  }

  if (!admins.length) {
    authMessage.textContent = "لا يوجد حساب أدمن محلي. على النسخة المنشورة اضبط ADMIN_USERNAME و ADMIN_PASSWORD من إعدادات Render.";
    return;
  }

  if (!admin) {
    authMessage.textContent = "بيانات الدخول غير صحيحة.";
    return;
  }

  currentAdmin = admin.username;
  currentAdminPassword = password;
  currentAdminRole = admin.role || "admin";
  localStorage.setItem("mizan_current_admin", currentAdmin);
  localStorage.setItem("mizan_current_admin_role", currentAdminRole);
  sessionStorage.setItem("mizan_current_admin_password", currentAdminPassword);
  form.reset();
  renderAdminState();
});

document.querySelector("#adminUserForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const fields = form.elements;
  const message = document.querySelector("#adminUserMessage");

  try {
    await createAdminOnServer({
      username: fields.username.value.trim(),
      password: fields.password.value,
      role: fields.role.value
    });
    form.reset();
    message.textContent = "تم منح الصلاحية بنجاح.";
    await renderAdminUsers();
  } catch (error) {
    message.textContent = error.message === "Admin already exists"
      ? "هذا الحساب يملك صلاحية مسبقًا."
      : "تعذر منح الصلاحية. تأكد من كلمة سر لا تقل عن 8 أحرف.";
  }
});

document.querySelector("#newsForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const fields = form.elements;
  const news = getNews();
  const isEditing = Boolean(editingNewsId);
  const id = isEditing ? editingNewsId : makeId();
  const existing = isEditing ? news.find((item) => item.id === id) : null;
  const image = await readImage(form) || existing?.image || fallbackImage;
  const authorImage = await readImageFromFields(fields, "authorImageFile", "authorImageUrl") || existing?.authorImage || "";
  const item = {
    id,
    title: fields.title.value.trim(),
    category: fields.category.value,
    placement: fields.placement.value,
    image,
    authorName: fields.authorName.value.trim(),
    authorImage,
    summary: fields.summary.value.trim(),
    body: fields.body.value.trim(),
    createdAt: existing?.createdAt || Date.now()
  };

  try {
    if (serverMode) {
      await saveNewsToServer(item);
    } else {
      setNews(existing ? news.map((newsItem) => newsItem.id === id ? item : newsItem) : [item, ...news]);
    }
  } catch (error) {
    alert(error.message || "تعذر حفظ الخبر على السيرفر. تأكد من تسجيل الدخول وحجم الصور.");
    return;
  }
  form.reset();
  setEditorMode();
  renderSite();
  renderAdminNews();
  renderAdminSummary();
});

document.querySelector("#newsForm").addEventListener("reset", (event) => {
  const form = event.currentTarget;
  setTimeout(() => {
    form.elements.id.value = "";
    setEditorMode();
  });
});

document.querySelector("#searchForm").addEventListener("submit", (event) => {
  event.preventDefault();
  searchTerm = document.querySelector("#searchInput").value.trim();
  activeView = "home";
  renderSite();
});

window.addEventListener("hashchange", () => {
  if (location.hash === "#admin") {
    openAdmin();
    return;
  }
  renderSite();
});

window.addEventListener("popstate", renderSite);

async function initApp() {
  loadInitialServerNews();
  fillCategorySelect();
  renderSite();

  const synced = await syncNewsFromServer();
  if (synced) {
    renderSite();
  }

  if (location.hash === "#admin") {
    openAdmin();
  }
}

initApp();
