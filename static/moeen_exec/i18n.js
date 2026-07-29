(() => {
  const KEY = "moeen_language";
  const SHARED_KEY = "rt_lang";
  const queryLanguage = new URLSearchParams(location.search).get("lang");
  const selected = queryLanguage || localStorage.getItem(KEY) || localStorage.getItem(SHARED_KEY) || "ar";
  let language = selected === "en" ? "en" : "ar";

  const english = {
    "مُعين — الذاكرة التنفيذية": "Moeen — Executive Memory",
    "إنشاء حساب مُعين التنفيذي | RT Studio": "Create a Moeen Executive Account | RT Studio",
    "مُعين": "Moeen",
    "م": "M",
    "و": "and",
    "دخول آمن": "Secure Access",
    "إعداد الجهاز الرئيسي": "Primary Device Setup",
    "أنشئ كلمة المرور الأولى": "Create Your First Password",
    "سيصبح هذا الجهاز الجهاز الرئيسي المصرح له.": "This device will become your authorized primary device.",
    "كلمة مرور من 12 حرفًا على الأقل": "Password of at least 12 characters",
    "تأكيد كلمة المرور": "Confirm Password",
    "تهيئة مُعين": "Set Up Moeen",
    "مساحة خاصة": "Private Workspace",
    "أهلًا بعودتك": "Welcome Back",
    "أدخل رقم الهاتف وكلمة المرور للمتابعة.": "Enter your phone number and password to continue.",
    "المفتاح الدولي": "Country Code",
    "الرقم المحلي": "Local Number",
    "كلمة المرور": "Password",
    "رمز ربط جهاز جديد (عند الحاجة)": "New Device Pairing Code (if needed)",
    "ليس لديك حساب؟": "Don’t have an account?",
    "أنشئ حسابك وابدأ التجربة المجانية": "Create an account and start your free trial",
    "مُعين التنفيذي · RT Studio": "Moeen Executive · RT Studio",
    "لديك حساب؟ تسجيل الدخول": "Already Have an Account? Sign In",
    "ذاكرة تنفيذية خاصة بك": "Your Private Executive Memory",
    "حوّل الملاحظات والقرارات إلى متابعة منظّمة.": "Turn Notes and Decisions into Organized Follow-ups.",
    "تطبيق ويب شخصي ومشفّر للمسؤولين والمديرين، يعمل بسلاسة على الهاتف واللابتوب ويحافظ على تزامن العمل بين أجهزتك.": "A private encrypted web app for executives and managers, designed to work smoothly across mobile and desktop while keeping your work synchronized.",
    "تسجيل صوتي وتحويل الحديث إلى نص": "Voice Recording and Speech-to-Text",
    "اجتماعات ومتابعات وجهات اتصال في مكان واحد": "Meetings, Follow-ups, and Contacts in One Place",
    "تشفير المحتوى وربط الأجهزة برمز آمن": "Content Encryption and Secure Device Pairing",
    "إنشاء حساب مُعين": "Create a Moeen Account",
    "أنشئ حسابك وابدأ تجربتك المجانية لمدة 48 ساعة فورًا، دون انتظار موافقة.": "Create your account and start your 48-hour free trial immediately, with no approval required.",
    "شهريًا": "Monthly",
    "كل 3 أشهر": "Every 3 Months",
    "سنويًا": "Annually",
    "المسمى الوظيفي": "Job Title",
    "مثال: مدير عام": "Example: General Manager",
    "اكتب الرقم المحلي فقط دون المفتاح الدولي.": "Enter the local number only, without the country code.",
    "البريد الإلكتروني (اختياري)": "Email Address (Optional)",
    "قرأت وأوافق على": "I Have Read and Agree to",
    "إنشاء الحساب وبدء التجربة": "Create Account and Start Trial",
    "بياناتك التنفيذية مشفرة ولا يستطيع مدير المنصة قراءة محتواها.": "Your executive data is encrypted, and platform administrators cannot read its content.",
    "سياسة الخصوصية | مُعين التنفيذي": "Privacy Policy | Moeen Executive",
    "شروط الاستخدام | مُعين التنفيذي": "Terms of Use | Moeen Executive",
    "مُعين التنفيذي · RT Studio": "Moeen Executive · RT Studio",
    "العودة إلى التطبيق": "Back to the App",
    "هذه سياسة تشغيلية أولية تصف عمل مُعين فعليًا، ويُنصح بمراجعتها مع مستشار قانوني محلي قبل التوسع التجاري.": "This initial operational policy describes how Moeen currently works. Local legal review is recommended before broader commercial expansion.",
    "1. نطاق السياسة": "1. Scope",
    "توضح هذه السياسة كيف تجمع RT Studio البيانات اللازمة لتقديم مُعين التنفيذي، وكيف تُخزن وتُستخدم وتُحمى.": "This policy explains how RT Studio collects, stores, uses, and protects the data required to provide Moeen Executive.",
    "2. البيانات التي نجمعها": "2. Data We Collect",
    "بيانات الحساب: الاسم، المسمى الوظيفي، الهاتف، البريد الإلكتروني الاختياري.": "Account data: name, job title, phone number, and optional email address.",
    "بيانات الأمان: الأجهزة الموثوقة، عنوان الاتصال، محاولات الدخول، وبيانات الجلسة.": "Security data: trusted devices, connection address, sign-in attempts, and session information.",
    "بيانات الاشتراك والدفع: الباقة، رقم العملية، الملاحظات، وصورة الإيصال عند رفعها.": "Subscription and payment data: plan, transaction number, notes, and uploaded receipt.",
    "المحتوى التنفيذي الذي يضيفه المستخدم، بما يشمل الملاحظات والاجتماعات والمتابعات وجهات الاتصال والتسجيلات.": "Executive content added by the user, including notes, meetings, follow-ups, contacts, and recordings.",
    "3. تشفير المحتوى": "3. Content Encryption",
    "يُشفّر المحتوى التنفيذي قبل حفظه، ولا تملك إدارة المنصة وسيلة اعتيادية لقراءة محتوى الخزنة. تبقى حماية كلمة المرور وأجهزة الدخول مسؤولية المستخدم.": "Executive content is encrypted before storage, and platform administrators have no ordinary means of reading the vault. Users remain responsible for protecting passwords and authorized devices.",
    "4. التسجيل الصوتي وتحويل الكلام إلى نص": "4. Voice Recording and Speech-to-Text",
    "التسجيلات المحفوظة داخل مُعين تُخزن مشفرة. أما ميزة تحويل الكلام مباشرة إلى نص فتعتمد على قدرات وخدمات المتصفح، وقد يعالج مزود المتصفح الصوت وفق سياسته؛ لذلك ينبغي عدم إملاء معلومات شديدة الحساسية دون فهم إعدادات المتصفح المستخدم.": "Recordings saved in Moeen are encrypted. Live speech-to-text relies on browser capabilities and services, and the browser provider may process audio under its own policy. Avoid dictating highly sensitive information without understanding your browser settings.",
    "5. أغراض الاستخدام": "5. Purposes of Use",
    "نستخدم البيانات لإنشاء الحساب، تأمين الدخول، مزامنة الخزنة المشفرة، إدارة الاشتراك والدفعات، إرسال التنبيهات، منع إساءة الاستخدام، وتقديم الدعم.": "We use data to create accounts, secure access, synchronize the encrypted vault, manage subscriptions and payments, send alerts, prevent misuse, and provide support.",
    "6. المشاركة والاستضافة": "6. Sharing and Hosting",
    "لا نبيع البيانات الشخصية. قد تُعالج بيانات تقنية محدودة عبر مزود الاستضافة وخدمات إشعارات المتصفح بالقدر اللازم لتشغيل الخدمة، أو عند وجود التزام قانوني نافذ.": "We do not sell personal data. Limited technical data may be processed by hosting and browser-notification providers as necessary to operate the service or comply with applicable legal obligations.",
    "7. مدة الاحتفاظ والحذف": "7. Retention and Deletion",
    "تُحفظ بيانات الحساب أثناء نشاطه أو إيقافه لتسهيل الاستعادة والتجديد. عند الحذف النهائي تُحذف الخزنة والأجهزة والدفعات والإيصالات المرتبطة من النظام التشغيلي، وقد تبقى نسخ مؤقتة ضمن نسخ الاستضافة الاحتياطية حتى انتهاء دورة الاحتفاظ الخاصة بالمزود.": "Account data is retained while active or suspended to support recovery and renewal. After final deletion, the vault, devices, payments, and receipts are removed from the operational system. Temporary copies may remain in hosting backups until the provider’s retention cycle ends.",
    "8. حقوق المستخدم": "8. User Rights",
    "يمكن طلب تصحيح بيانات الحساب أو حذف الحساب نهائيًا بالتواصل مع RT Studio. قد يُطلب التحقق من الهوية قبل تنفيذ الطلب.": "Users may request account correction or final deletion by contacting RT Studio. Identity verification may be required.",
    "9. ملفات المتصفح": "9. Browser Storage",
    "يستخدم مُعين ملفات الجلسة والتخزين المحلي وخدمة العامل البرمجي لتسجيل الدخول الموثوق، تشغيل التطبيق، حفظ النسخة المشفرة محليًا، والمزامنة.": "Moeen uses session storage, local storage, and a service worker for trusted access, app operation, encrypted local storage, and synchronization.",
    "10. الأمان والتغييرات": "10. Security and Changes",
    "نطبق تدابير فنية معقولة، لكن لا يوجد نظام إلكتروني يضمن أمانًا مطلقًا. قد تُحدّث هذه السياسة، ويُعرض تاريخ الإصدار عند التحديث.": "We apply reasonable technical safeguards, but no electronic system can guarantee absolute security. This policy may be updated, with the current version date displayed.",
    "شروط استخدام مُعين التنفيذي": "Moeen Executive Terms of Use",
    "هذه شروط تشغيلية أولية وليست بديلًا عن مراجعة قانونية محلية قبل التوسع التجاري.": "These are initial operational terms and do not replace local legal review before broader commercial expansion.",
    "1. قبول الشروط": "1. Acceptance of Terms",
    "بإنشاء الحساب أو استخدام مُعين، يوافق المستخدم على هذه الشروط وعلى": "By creating an account or using Moeen, the user agrees to these terms and the",
    "2. وصف الخدمة": "2. Service Description",
    "مُعين تطبيق ويب شخصي لإدارة الملاحظات والاجتماعات والمتابعات وجهات الاتصال، مع مزامنة مشفرة بين الأجهزة الموثوقة.": "Moeen is a personal web app for managing notes, meetings, follow-ups, and contacts, with encrypted synchronization between trusted devices.",
    "3. الحساب والأمان": "3. Account and Security",
    "يلتزم المستخدم بتقديم بيانات صحيحة، وحماية كلمة المرور، وعدم مشاركة رموز ربط الأجهزة. يتحمل المستخدم مسؤولية النشاط الصادر من أجهزته الموثوقة.": "Users must provide accurate information, protect their passwords, and never share device pairing codes. Users are responsible for activity from their trusted devices.",
    "4. التجربة والاشتراكات": "4. Trial and Subscriptions",
    "تبدأ تجربة مجانية لمدة 48 ساعة عند التسجيل العام. الباقات والأسعار المعروضة وقت الدفع هي المعتمدة. لا يوجد خصم تلقائي؛ تُراجع التحويلات يدويًا ويبدأ أو يتجدد الاشتراك بعد اعتماد الدفع.": "A 48-hour free trial starts upon public registration. The plans and prices shown at payment apply. There is no automatic charge; transfers are reviewed manually, and the subscription starts or renews after approval.",
    "5. الدفع والاسترداد": "5. Payment and Refunds",
    "يجب إرسال مرجع صحيح أو إيصال واضح. لا تُعد الدفعة مقبولة قبل اعتمادها في لوحة الإدارة. المبالغ المفعّلة غير مستردة مبدئيًا بعد بدء مدة الاشتراك، إلا إذا تطلب القانون النافذ خلاف ذلك أو وافقت RT Studio كتابةً.": "A valid reference or clear receipt must be submitted. Payment is not accepted until approved in the administration dashboard. Activated payments are generally non-refundable after the subscription period begins unless applicable law requires otherwise or RT Studio agrees in writing.",
    "6. انتهاء الاشتراك": "6. Subscription Expiry",
    "عند انتهاء الاشتراك ينتقل الحساب إلى وضع التجديد فقط وتبقى الخزنة مقفلة. لا تُحذف البيانات تلقائيًا، ويمكن استعادة الوصول بعد اعتماد التجديد.": "When a subscription expires, the account enters renewal-only mode and the vault remains locked. Data is not deleted automatically, and access can be restored after renewal approval.",
    "7. الاستخدام المقبول": "7. Acceptable Use",
    "يُحظر استخدام الخدمة لأغراض غير قانونية، أو محاولة اختراقها، أو الوصول إلى حسابات الآخرين، أو رفع ملفات ضارة. المستخدم مسؤول عن امتثاله لسياسات مؤسسته بشأن المعلومات السرية والرسمية.": "The service must not be used for unlawful purposes, intrusion attempts, access to other users’ accounts, or uploading harmful files. Users are responsible for complying with their organization’s policies on confidential and official information.",
    "8. توفر الخدمة": "8. Service Availability",
    "نسعى إلى استمرارية الخدمة، وقد تحدث فترات صيانة أو أعطال خارجة عن السيطرة. على المستخدم الاحتفاظ بما يلزم من إجراءات عمل بديلة للمعلومات شديدة الأهمية.": "We aim to maintain service continuity, but maintenance or events beyond our control may occur. Users should maintain appropriate alternative procedures for highly important information.",
    "9. الإيقاف والحذف": "9. Suspension and Deletion",
    "يجوز إيقاف الحساب عند مخالفة الشروط أو الاشتباه بإساءة الاستخدام. الإلغاء يبقي البيانات لإمكان التجديد، بينما الحذف النهائي يزيل الحساب وبياناته المرتبطة ولا يمكن التراجع عنه.": "An account may be suspended for violating these terms or suspected misuse. Cancellation retains data for possible renewal, while final deletion permanently removes the account and related data.",
    "10. المسؤولية والتعديلات": "10. Liability and Amendments",
    "تُقدم الخدمة كأداة تنظيم ومساندة ولا تستبدل القرار المهني أو الإداري. قد تُحدّث الشروط عند تطوير الخدمة، ويُعتمد الإصدار المنشور في هذه الصفحة.": "The service is provided as an organizational support tool and does not replace professional or administrative judgment. These terms may be updated as the service develops, and the version published on this page applies.",
    "للاستفسار أو طلب حذف الحساب، تواصل مع RT Studio عبر قنوات التواصل المنشورة في الموقع الرسمي.": "For inquiries or account-deletion requests, contact RT Studio through the channels published on the official website.",
    "تم إنشاء حسابك وبدأت تجربتك المجانية لمدة 48 ساعة. سجّل الدخول الآن.": "Your account has been created and your 48-hour free trial has started. Sign in now.",
    "تثبيت مُعين على هذا الجهاز": "Install Moeen on This Device",
    "مُعين مثبت بالفعل على هذا الجهاز.": "Moeen Is Already Installed on This Device.",
    "على iPhone: اضغط زر المشاركة في Safari، ثم اختر «إضافة إلى الشاشة الرئيسية»، وبعدها اضغط «إضافة».": "On iPhone: tap Share in Safari, choose “Add to Home Screen,” then tap “Add.”",
    "من قائمة المتصفح اختر «تثبيت التطبيق» أو «إضافة إلى الشاشة الرئيسية».": "From your browser menu, choose “Install App” or “Add to Home Screen.”",
    "اتصال مشفّر عند النشر": "Encrypted Connection",
    "🔒 اتصال مشفّر عند النشر · جلسة مقفلة تلقائيًا ·": "🔒 Encrypted Connection · Automatic Session Lock ·",
    "جلسة مقفلة تلقائيًا": "Automatic Session Lock",
    "الخصوصية": "Privacy",
    "الشروط": "Terms",
    "الذاكرة التنفيذية": "Executive Memory",
    "اليوم": "Today",
    "الذاكرة": "Memory",
    "المتابعات": "Follow-ups",
    "الاجتماعات": "Meetings",
    "الاتصالات": "Contacts",
    "الاشتراك": "Subscription",
    "الأمان": "Security",
    "البيانات محفوظة على هذا الجهاز": "Data is Stored on This Device",
    "🔒 البيانات محفوظة على هذا الجهاز": "🔒 Data is Stored on This Device",
    "أهلًا بك": "Welcome",
    "كل ما يحتاج انتباهك، في مكان واحد.": "Everything that needs your attention, in one place.",
    "محفوظ محليًا": "Saved Locally",
    "تثبيت التطبيق": "Install App",
    "تسجيل الخروج": "Sign Out",
    "خروج": "Sign Out",
    "ملاحظة صوتية": "Voice Note",
    "موجز اليوم": "Today’s Brief",
    "بداية واضحة ليومٍ أكثر تركيزًا": "A Clear Start to a More Focused Day",
    "ابدأ بإضافة أول ملاحظة أو متابعة.": "Start by adding your first note or follow-up.",
    "تحدث الآن": "Speak Now",
    "ذاكرتك التنفيذية": "Your Executive Memory",
    "الخصوصية وربط الأجهزة": "Privacy and Device Pairing",
    "محتواك الشخصي مشفّر": "Your Personal Content Is Encrypted",
    "الملاحظات والاجتماعات والمتابعات وجهات الاتصال والتسجيلات الصوتية تُشفّر على جهازك قبل المزامنة، ولا يظهر محتواها في لوحة إدارة RT Studio.": "Notes, meetings, follow-ups, contacts, and voice recordings are encrypted on your device before syncing. Their content is never visible in the RT Studio dashboard.",
    "استخدم مُعين على الهاتف والكمبيوتر": "Use Moeen on Mobile and Desktop",
    "اربط جهازًا آخر برمز مؤقت من مركز الأمان لتظهر بياناتك المشفّرة على الجهازين.": "Pair another device with a temporary code from the Security Center to access your encrypted data on both devices.",
    "طريقة ربط جهاز آخر": "How to Pair Another Device",
    "طريقة ربط جهاز آخر ←": "How to Pair Another Device →",
    "يتطلب انتباهك": "Needs Your Attention",
    "مواعيد وتنبيهات اليوم": "Today’s Events and Alerts",
    "متابعات مفتوحة": "Open Follow-ups",
    "تستحق اليوم": "Due Today",
    "ملاحظات محفوظة": "Saved Notes",
    "الأولوية اليوم": "Today’s Priority",
    "عرض الكل": "View All",
    "لا توجد متابعات بعد.": "No follow-ups yet.",
    "آخر ما حفظته": "Recently Saved",
    "فتح الذاكرة": "Open Memory",
    "ذاكرتك جاهزة لأول ملاحظة.": "Your memory is ready for its first note.",
    "ذاكرتك الشخصية": "Your Personal Memory",
    "الملاحظات الصوتية والنصية": "Voice and Text Notes",
    "+ إضافة ملاحظة": "+ Add Note",
    "بحث فقط في الملاحظات المحفوظة…": "Search saved notes…",
    "لا تدع شيئًا يسقط": "Let Nothing Slip",
    "المتابعات والالتزامات": "Follow-ups and Commitments",
    "+ متابعة جديدة": "+ New Follow-up",
    "قبل الاجتماع وبعده": "Before and After the Meeting",
    "دفتر الاجتماعات": "Meeting Journal",
    "+ اجتماع جديد": "+ New Meeting",
    "دليل شخصي آمن": "Your Secure Personal Directory",
    "جهات الاتصال": "Contacts",
    "+ جهة اتصال": "+ Add Contact",
    "ابحث بالاسم أو الجهة أو الرقم…": "Search by name, organization, or number…",
    "تجديد آمن وواضح": "Secure and Transparent Renewal",
    "دفع اشتراك مُعين": "Moeen Subscription Payment",
    "اختر الباقة وطريقة التحويل": "Choose a Plan and Payment Method",
    "يتم تفعيل الاشتراك بعد مراجعة إثبات الدفع من RT Studio.": "Your subscription is activated after RT Studio reviews the payment proof.",
    "شهري": "Monthly",
    "3 أشهر": "3 Months",
    "سنوي": "Annual",
    "30 يومًا": "30 Days",
    "90 يومًا": "90 Days",
    "365 يومًا": "365 Days",
    "محفظة Reflect": "Reflect Wallet",
    "تحويل بنكي عبر IBAN": "Bank Transfer via IBAN",
    "بيانات البنك": "Bank Details",
    "سيتم توفير رقم المحفظة قريبًا": "Wallet number will be available soon",
    "سيتم توفير رقم الإيبان قريبًا": "IBAN will be available soon",
    "رقم العملية أو مرجع التحويل": "Transaction Number or Transfer Reference",
    "صورة الإيصال أو ملف PDF (اختياري عند إدخال رقم العملية)": "Receipt image or PDF (optional when entering a transaction number)",
    "بنك فلسطين-حساب شيقل · RT Studio": "Bank of Palestine — Shekel Account · RT Studio",
    "بعد التحويل، أرسل رقم العملية أو صورة الإيصال وسيتم تفعيل الاشتراك بعد المراجعة.": "After transferring, submit the transaction number or a receipt image. Your subscription will be activated after review.",
    "ملاحظة اختيارية للإدارة": "Optional Note for Administration",
    "إرسال إثبات الدفع": "Submit Payment Proof",
    "الحساب والأجهزة": "Account and Devices",
    "مركز الأمان": "Security Center",
    "تغيير كلمة المرور": "Change Password",
    "استخدم كلمة مرور طويلة وفريدة لهذا التطبيق.": "Use a long, unique password for this app.",
    "كلمة المرور الحالية": "Current Password",
    "كلمة المرور الجديدة": "New Password",
    "ربط الهاتف والكمبيوتر": "Pair Mobile and Desktop",
    "من هذا الجهاز اضغط «إنشاء رمز ربط».": "On this device, select “Create Pairing Code.”",
    "افتح مُعين على الجهاز الآخر وسجّل بنفس رقم الهاتف وكلمة المرور.": "Open Moeen on the other device and sign in with the same phone number and password.",
    "أدخل رمز الربط في خانته؛ الرمز صالح لخمس دقائق فقط.": "Enter the pairing code. It is valid for five minutes only.",
    "1. من هذا الجهاز اضغط «إنشاء رمز ربط».": "1. On this device, select “Create Pairing Code.”",
    "2. افتح مُعين على الجهاز الآخر وسجّل بنفس رقم الهاتف وكلمة المرور.": "2. Open Moeen on the other device and sign in with the same phone number and password.",
    "3. أدخل رمز الربط في خانته؛ الرمز صالح لخمس دقائق فقط.": "3. Enter the pairing code. It is valid for five minutes only.",
    "إنشاء رمز ربط لجهاز آخر": "Create a Pairing Code",
    "إشعارات المواعيد": "Schedule Notifications",
    "استقبل تنبيهات الاجتماعات والمتابعات والاتصالات على هذا الجهاز حتى عند إغلاق التطبيق.": "Receive meeting, follow-up, and call alerts on this device even when the app is closed.",
    "تفعيل الإشعارات على هذا الجهاز": "Enable Notifications on This Device",
    "الأجهزة المصرح بها": "Authorized Devices",
    "محاولات الدخول": "Sign-in Attempts",
    "تحديد كمراجعة": "Mark as Reviewed",
    "سياسة الخصوصية": "Privacy Policy",
    "شروط الاستخدام": "Terms of Use",
    "ملاحظة سريعة": "Quick Note",
    "تحدّث، وسأتولى ترتيبها": "Speak, and I’ll Organize It",
    "ابدأ التسجيل": "Start Recording",
    "تحويل الكلام مباشرة": "Live Speech to Text",
    "يمكنك التسجيل فقط، أو استخدام الإملاء لتحويل العربية إلى نص.": "You can save a recording or use dictation to convert speech into text.",
    "سيظهر النص هنا، ويمكنك مراجعته قبل الحفظ…": "Your text will appear here for review before saving…",
    "عنوان مختصر (اختياري)": "Short Title (Optional)",
    "مكان الحفظ": "Save To",
    "سيُحدد تلقائيًا من مضمون الكلام.": "Automatically selected from the content.",
    "إلغاء": "Cancel",
    "حفظ في الذاكرة": "Save to Memory",
    "اسحب للتحديث": "Pull to Refresh",
    "اترك للتحديث": "Release to Refresh",
    "جارٍ التحديث…": "Refreshing…",
    "هذا المتصفح لا يدعم الإشعارات الخلفية.": "This browser does not support background notifications.",
    "لم يتم السماح بالإشعارات من إعدادات الجهاز.": "Notifications were not allowed in device settings.",
    "الإشعارات مفعّلة على هذا الجهاز.": "Notifications are enabled on this device.",
    "الإشعارات مفعّلة": "Notifications Enabled",
    "تعذر تفعيل الإشعارات. تحقق من إعدادات المتصفح ثم حاول مجددًا.": "Could not enable notifications. Check your browser settings and try again.",
    "حان الآن": "Due Now",
    "خلال ساعة": "Within an Hour",
    "صباح الخير": "Good Morning",
    "طاب يومك": "Good Afternoon",
    "مساء الخير": "Good Evening",
    "أهلًا بعودتك": "Welcome Back",
    "جدول المتابعة هادئ. سجّل ما يستحق التذكر.": "Your follow-up list is clear. Capture what deserves attention.",
    "ملاحظة": "Note",
    "لا توجد نتائج.": "No Results.",
    "أضف أول متابعة أو التزام.": "Add Your First Follow-up or Commitment.",
    "سجّل اجتماعك الأول.": "Save Your First Meeting.",
    "أضف أول جهة اتصال إلى دليلك الشخصي.": "Add Your First Contact.",
    "اتصال": "Call",
    "متابعة": "Follow-up",
    "تذكير اتصال": "Call Reminder",
    "اجتماع": "Meeting",
    "بلا موعد": "No Date",
    "مشاركة": "Share",
    "إعادة": "Reopen",
    "تم": "Done",
    "تم الاجتماع": "Meeting Completed",
    "حذف": "Delete",
    "اتصال الآن": "Call Now",
    "إرسال بريد": "Send Email",
    "تذكير بالاتصال": "Call Reminder",
    "صوت ونص": "Audio and Text",
    "نص": "Text",
    "دون عنوان": "Untitled",
    "التاريخ": "Date",
    "الحاضرون": "Attendees",
    "المعني": "Assigned To",
    "متابعة جديدة": "New Follow-up",
    "اجتماع جديد": "New Meeting",
    "ما الذي يجب متابعته؟": "What Needs Follow-up?",
    "ما الاجتماع الذي تريد حفظه؟": "Which Meeting Would You Like to Save?",
    "عنوان المتابعة": "Follow-up Title",
    "عنوان الاجتماع": "Meeting Title",
    "الشخص أو الإدارة": "Person or Department",
    "التاريخ والوقت": "Date and Time",
    "موعد الإشعار": "Notification Time",
    "عند الموعد": "At Event Time",
    "قبل 15 دقيقة": "15 Minutes Before",
    "قبل 30 دقيقة": "30 Minutes Before",
    "قبل ساعة": "1 Hour Before",
    "قبل يوم": "1 Day Before",
    "دون إشعار": "No Notification",
    "ملاحظات مختصرة": "Short Notes",
    "حفظ": "Save",
    "دفتر الاتصالات": "Contact Directory",
    "جهة اتصال جديدة": "New Contact",
    "الاسم الكامل": "Full Name",
    "المنصب": "Job Title",
    "الجهة أو الإدارة": "Organization or Department",
    "رقم الهاتف": "Phone Number",
    "يمكنك قول الرقم بالصوت، ثم مراجعته قبل الحفظ.": "You can dictate the number and review it before saving.",
    "البريد الإلكتروني": "Email Address",
    "قل مثلًا: name آت example نقطة com": "For example, say: name at example dot com",
    "ملاحظات الاتصال": "Contact Notes",
    "حفظ جهة الاتصال": "Save Contact",
    "إعادة التسجيل": "Record Again",
    "إيقاف التسجيل": "Stop Recording",
    "التسجيل جارٍ…": "Recording…",
    "إيقاف الإملاء": "Stop Dictation",
    "انتهى الإملاء. راجع النص قبل الحفظ.": "Dictation finished. Review the text before saving.",
    "أتحدث الآن… سيظهر النص أثناء كلامك.": "Listening… Your text will appear as you speak.",
    "تم التعرف على مضمون متعلق باجتماع.": "Meeting-related content detected.",
    "تم التعرف على التزام أو متابعة.": "A commitment or follow-up was detected.",
    "تم التعرف على بيانات اتصال.": "Contact information was detected.",
    "ستُحفظ كملاحظة في الذاكرة.": "This will be saved as a memory note.",
    "تحدث لتحويل الصوت إلى نص": "Speak to Convert Voice into Text",
    "إملاء صوتي": "Voice Dictation",
    "بانتظار المزامنة": "Waiting to Sync",
    "محفوظ دون اتصال": "Saved Offline",
    "تمت المزامنة": "Synced",
    "هاتف شخصي": "Personal Phone",
    "حاسوب شخصي": "Personal Computer",
    "أدخل كلمة المرور لفتح الخزنة المشفرة.": "Enter your password to unlock the encrypted vault.",
    "تعذر الاتصال بخادم مُعين المحلي.": "Could not connect to the Moeen server.",
    "كلمتا المرور غير متطابقتين.": "Passwords Do Not Match.",
    "تم الإعداد. سجّل الدخول الآن.": "Setup Complete. Sign In Now.",
    "استخدم 12 حرفًا على الأقل.": "Use at Least 12 Characters.",
    "تعذر إكمال الإعداد.": "Could Not Complete Setup.",
    "اكتب الرقم المحلي فقط بصورة صحيحة.": "Enter a Valid Local Number Only.",
    "بيانات الدخول غير صحيحة.": "Incorrect Sign-in Details.",
    "هذا الجهاز غير مصرح له. استخدم رمز ربط من الجهاز الرئيسي.": "This Device Is Not Authorized. Use a Pairing Code from the Primary Device.",
    "رمز الربط غير صحيح أو انتهت صلاحيته.": "The Pairing Code Is Invalid or Has Expired.",
    "تم حظر المحاولات مؤقتًا. حاول لاحقًا.": "Attempts Are Temporarily Blocked. Try Again Later.",
    "الحساب موقوف أو ملغي. تواصل مع RT Studio.": "This Account Is Suspended or Cancelled. Contact RT Studio.",
    "تعذر فتح الخزنة. تحقق من كلمة المرور.": "Could Not Unlock the Vault. Check Your Password.",
    "تعذر تسجيل الدخول أو فتح الخزنة.": "Could Not Sign In or Unlock the Vault.",
    "يرجى تغيير كلمة المرور المؤقتة.": "Please Change Your Temporary Password.",
    "تم تغيير كلمة المرور وإعادة حماية الخزنة بنجاح.": "Your Password Was Changed and the Vault Was Secured Successfully.",
    "كلمة المرور الحالية غير صحيحة.": "The Current Password Is Incorrect.",
    "تعذر تغيير كلمة المرور. يجب أن تكون الجديدة 12 حرفًا على الأقل ومختلفة.": "Could Not Change the Password. The New Password Must Be Different and at Least 12 Characters.",
    "صالح لخمس دقائق": "Valid for Five Minutes",
    "تعذر إنشاء رمز الربط.": "Could Not Create a Pairing Code.",
    "هذا الجهاز": "This Device",
    "آخر نشاط": "Last Activity",
    "إلغاء الجهاز": "Revoke Device",
    "ملغى": "Revoked",
    "نشط": "Active",
    "لا توجد أجهزة.": "No Devices.",
    "جهاز غير معروف": "Unknown Device",
    "لا توجد محاولات مريبة.": "No Suspicious Attempts.",
    "كلمة مرور خاطئة": "Incorrect Password",
    "جهاز غير مصرح": "Unauthorized Device",
    "رمز ربط خاطئ": "Incorrect Pairing Code",
    "محاولة أثناء الحظر": "Attempt While Blocked",
    "محاولة مرفوضة": "Rejected Attempt",
    "جارٍ إرسال إثبات الدفع…": "Submitting Payment Proof…",
    "أدخل رقم العملية أو ارفع الإيصال.": "Enter a Transaction Number or Upload a Receipt.",
    "صيغة الإيصال غير مدعومة.": "The Receipt Format Is Not Supported.",
    "سجّل الدخول ثم حاول مجددًا.": "Sign In and Try Again.",
    "تعذر إرسال الإثبات الآن. حاول مرة أخرى.": "Could Not Submit the Proof. Try Again.",
    "انتهى اشتراكك. بياناتك محفوظة ومقفلة حتى اعتماد التجديد.": "Your Subscription Has Expired. Your Data Remains Safely Stored and Locked Until Renewal Is Approved.",
    "تنتهي تجربتك المجانية": "Your Free Trial Ends",
    "ينتهي اشتراكك": "Your Subscription Ends",
    "· اضغط لعرض خيارات التجديد والدفع.": "· Select to View Renewal and Payment Options.",
    "إلغاء تصريح هذا الجهاز؟": "Revoke Authorization for This Device?",
    "حذف هذا العنصر؟": "Delete This Item?",
    "حذف الملاحظة وتسجيلها الصوتي؟": "Delete This Note and Its Audio Recording?",
    "سجّل صوتًا أو اكتب ملاحظة أولًا.": "Record Audio or Write a Note First.",
    "ملاحظة صوتية": "Voice Note",
    "جهة اتصال صوتية": "Voice Contact",
    "تعذر الوصول إلى الميكروفون. اسمح للتطبيق باستخدامه ثم حاول مجددًا.": "Could Not Access the Microphone. Allow Access and Try Again.",
    "الإملاء الصوتي غير متاح في هذا المتصفح. لا يزال بإمكانك حفظ التسجيل.": "Voice Dictation Is Not Available in This Browser. You Can Still Save the Recording.",
    "تعذر تشغيل الإملاء. تحقق من الميكروفون والاتصال.": "Could Not Start Dictation. Check the Microphone and Connection.",
    "تحويل الصوت إلى نص غير متاح في هذا المتصفح.": "Voice-to-Text Is Not Available in This Browser.",
    "تعذر تشغيل الإملاء الصوتي. تحقق من إذن الميكروفون والاتصال.": "Could Not Start Voice Dictation. Check Microphone Permission and Connection."
  };

  const patterns = [
    [/^الاسم:\s*(.+)$/u, "Name: $1"],
    [/^الإصدار:\s*(.+)$/u, "Version: $1"],
    [/^لديك\s+(\d+)\s+متابعة مفتوحة\. ركّز على الأكثر إلحاحًا أولًا\.$/u, "You have $1 open follow-ups. Focus on the most urgent first."],
    [/^لديك\s+(\d+)\s+حدث حان موعده$/u, "$1 events are due"],
    [/^(\d+)\s+تنبيه$/u, "$1 alerts"],
    [/^تنتهي تجربتك المجانية خلال\s+(.+)$/u, "Your free trial ends in $1"],
    [/^ينتهي اشتراكك خلال\s+(.+)$/u, "Your subscription ends in $1"],
    [/^تم حفظ التسجيل مؤقتًا \((\d+) كيلوبايت\)\.$/u, "Recording saved temporarily ($1 KB)."],
    [/^تم ضبط الموعد والتنبيه تلقائيًا:\s*(.+)$/u, "The event and reminder were set automatically: $1"],
    [/^تم إرسال الإثبات بنجاح\. رقم المتابعة:\s*(.+)$/u, "Payment proof submitted successfully. Reference: $1"],
    [/^آخر نشاط:\s*(.+)$/u, "Last Activity: $1"],
    [/^الاتصال بـ\s*(.+)$/u, "Call $1"],
    [/^حفظ في\s*(.+)$/u, "Save to $1"],
    [/^(\d+)\s+ساعة$/u, "$1 hours"],
    [/^(\d+)\s+أيام$/u, "$1 days"]
  ];

  function translate(value) {
    if (language !== "en" || typeof value !== "string") return value;
    const leading = value.match(/^\s*/u)?.[0] || "";
    const trailing = value.match(/\s*$/u)?.[0] || "";
    const clean = value.trim();
    if (!clean) return value;
    let result = english[clean];
    if (!result) {
      for (const [pattern, replacement] of patterns) {
        if (pattern.test(clean)) {
          result = clean.replace(pattern, replacement);
          break;
        }
      }
    }
    if (result) {
      result = result
        .replace(/(\d+)\s+ساعة/gu, "$1 hours")
        .replace(/(\d+)\s+أيام/gu, "$1 days");
    }
    return result ? `${leading}${result}${trailing}` : value;
  }

  function translateNode(root) {
    if (language !== "en" || !root) return;
    if (root.nodeType === Node.TEXT_NODE) {
      const translated = translate(root.nodeValue);
      if (translated !== root.nodeValue) root.nodeValue = translated;
      return;
    }
    if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_NODE) return;
    const elements = root.nodeType === Node.ELEMENT_NODE ? [root, ...root.querySelectorAll("*")] : [...root.querySelectorAll("*")];
    for (const element of elements) {
      for (const attribute of ["placeholder", "title", "aria-label"]) {
        if (!element.hasAttribute?.(attribute)) continue;
        const current = element.getAttribute(attribute);
        const translated = translate(current);
        if (translated !== current) element.setAttribute(attribute, translated);
      }
      for (const child of [...element.childNodes]) {
        if (child.nodeType === Node.TEXT_NODE) translateNode(child);
      }
    }
  }

  function applyLanguage() {
    document.documentElement.lang = language;
    document.documentElement.dir = language === "en" ? "ltr" : "rtl";
    document.body?.classList.toggle("language-en", language === "en");
    if (language === "en") {
      document.title = english[document.title] || translate(document.title);
      translateNode(document);
    }
    document.querySelectorAll("[data-language-toggle]").forEach(button => {
      button.textContent = language === "en" ? "عربي" : "EN";
      button.setAttribute("aria-label", language === "en" ? "Switch to Arabic" : "التبديل إلى الإنجليزية");
    });
  }

  function setLanguage(next) {
    language = next === "en" ? "en" : "ar";
    localStorage.setItem(KEY, language);
    localStorage.setItem(SHARED_KEY, language);
    location.reload();
  }

  localStorage.setItem(KEY, language);
  localStorage.setItem(SHARED_KEY, language);
  window.MoeenI18n = {
    get language() { return language; },
    get locale() { return language === "en" ? "en-GB" : "ar-PS"; },
    get speechLocale() { return language === "en" ? "en-US" : "ar-PS"; },
    t: translate,
    apply: applyLanguage,
    set: setLanguage
  };

  document.querySelectorAll("[data-language-toggle]").forEach(button => {
    button.addEventListener("click", () => setLanguage(language === "en" ? "ar" : "en"));
  });
  applyLanguage();

  const observer = new MutationObserver(records => {
    if (language !== "en") return;
    for (const record of records) {
      if (record.type === "characterData") translateNode(record.target);
      record.addedNodes.forEach(translateNode);
    }
  });
  observer.observe(document.documentElement, {subtree: true, childList: true, characterData: true});

  const nativeAlert = window.alert.bind(window);
  const nativeConfirm = window.confirm.bind(window);
  window.alert = message => nativeAlert(translate(String(message)));
  window.confirm = message => nativeConfirm(translate(String(message)));
})();
