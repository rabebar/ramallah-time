import os
from dotenv import load_dotenv
load_dotenv()
import uuid
import base64
import json
import math
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Query,
    UploadFile,
    File,
    Form,
    Header
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from openai import OpenAI

from database import SessionLocal, init_db, Place, PlaceImage
import schemas

ADMIN_SECRET_KEY = os.environ.get("ADMIN_SECRET_KEY", "ADMIN123123123")

api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

def calculate_haversine(lat1, lon1, lat2, lon2):
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None
    try:
        R = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = (math.sin(delta_phi / 2.0) ** 2 +
             math.cos(phi1) * math.cos(phi2) *
             math.sin(delta_lambda / 2.0) ** 2)
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        distance = R * c
        return round(distance, 2)
    except Exception as e:
        print(f"Error calculating distance: {e}")
        return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- جارٍ تشغيل نظام رام الله تايم (النسخة المحدثة) ---")
    init_db()
    yield
    print("--- جارٍ إغلاق النظام ---")

app = FastAPI(
    title="Ramallah Time API",
    version="3.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = "frontend"
IMAGES_DIR = "images"
UPLOADS_DIR = "uploads"
PLACE_IMAGES_DIR = os.path.join(IMAGES_DIR, "places")

for directory in [IMAGES_DIR, UPLOADS_DIR, PLACE_IMAGES_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def home(user_agent: Optional[str] = Header(None)):
    ua = user_agent.lower() if user_agent else ""
    
    # قائمة شاملة لكافة الأجهزة المحمولة
    mobile_indicators = [
        "iphone", "android", "phone", "mobile", 
        "up.browser", "up.link", "mmp", "midp", "wap"
    ]
    
    # فحص إذا كان الزائر يستخدم موبايل
    is_mobile = any(indicator in ua for indicator in mobile_indicators)

    if is_mobile:
        mobile_path = os.path.join(FRONTEND_DIR, "mobile.html")
        if os.path.exists(mobile_path):
            return FileResponse(mobile_path)

    # إذا كان كمبيوتر أو لم يتأكد النظام، يفتح الموقع الرئيسي
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    return FileResponse(index_path)

@app.get("/places")
def places_page():
    path = os.path.join(FRONTEND_DIR, "places.html")
    return FileResponse(path if os.path.exists(path) else os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/add-place")
def add_place_page():
    path = os.path.join(FRONTEND_DIR, "add-place.html")
    return FileResponse(path if os.path.exists(path) else os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/owner-login")
def owner_login_page():
    path = os.path.join(FRONTEND_DIR, "owner-login.html")
    return FileResponse(path if os.path.exists(path) else os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/owner-dashboard")
def owner_dashboard_page():
    path = os.path.join(FRONTEND_DIR, "owner-dashboard.html")
    return FileResponse(path if os.path.exists(path) else os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/manifest.json")
def get_manifest():
    manifest_path = os.path.join(FRONTEND_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        raise HTTPException(status_code=404, detail="manifest.json غير موجود داخل مجلد frontend")
    return FileResponse(manifest_path, media_type="application/json")

@app.get("/sw.js")
def get_sw():
    sw_path = os.path.join(FRONTEND_DIR, "sw.js")
    if not os.path.exists(sw_path):
        raise HTTPException(status_code=404, detail="sw.js غير موجود داخل مجلد frontend")
    return FileResponse(sw_path, media_type="application/javascript")

ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png", "webp"}

def _validate_extension(filename: str) -> str:
    extension = (filename.split(".")[-1] if "." in filename else "").lower().strip()
    if extension not in ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=400, detail="نوع الملف غير مدعوم. يرجى رفع صور فقط.")
    return extension

@app.post("/api/ai-scan")
async def scan_place_with_ai(image: UploadFile = File(...)):
    if not client:
        raise HTTPException(status_code=503, detail="خدمة الذكاء الاصطناعي غير مفعلة (مفتاح API مفقود).")

    # ✅ تحقّق سريع من الامتداد (حتى لو AI يقدر يقرأ، احنا نمنع ملفات مش صور)
    _validate_extension(image.filename or "")

    image_data = await image.read()
    base64_image = base64.b64encode(image_data).decode("utf-8")

    system_instruction = (
        
        "أنت 'مساعد رام الله تايم الذكي'. خبير متخصص في مدينة رام الله. "
        "لديك مصدرين للمعلومات:\n"
        "1. بياناتنا الخاصة (الأولوية لها): \n" + context_data + "\n"
        "2. معلوماتك العامة عن مدينة رام الله ومعالمها الشهيرة.\n\n"
        "إذا سألك المستخدم عن مكان موجود في 'بياناتنا الخاصة'، قدم له التفاصيل وشجعه على التواصل معهم عبر واتساب التطبيق.\n"
        "إذا سألك عن مكان شهير في رام الله وغير موجود في بياناتنا، قدم له معلوماتك العامة عنه بأسلوب ودود وأخبره أننا نسعى لإضافته لدليلنا قريباً.\n"
        "اجعل ردودك قصيرة، جذابة، وباللهجة الفلسطينية البيضاء المحببة."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": [
                    {"type": "text", "text": "Extract business details."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        ai_json = response.choices[0].message.content
        return json.loads(ai_json)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"فشل التحليل: {str(error)}")

def is_expired(place: Place) -> bool:
    if place.subscription_status == "pending":
        return False
    if not place.subscription_end:
        return True
    return datetime.utcnow() > place.subscription_end

def get_place_status(place: Place) -> str:
    if place.subscription_status == "pending":
        return "pending"
    if is_expired(place):
        return "expired"
    return "active"

@app.post("/api/places", response_model=schemas.PlaceAuthOut)
def create_place(
    payload: schemas.PlaceCreate,
    db: Session = Depends(get_db),
    x_admin_token: Optional[str] = Header(None),
):
    # 1. التحقق هل السائل هو الأدمن
    is_admin = (x_admin_token == ADMIN_SECRET_KEY)

    # 2. التحقق من وجود البريد وكلمة السر للمستخدم العادي
    if not is_admin:
        if not payload.owner_email:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مطلوب")
        if not payload.owner_password:
            raise HTTPException(status_code=400, detail="كلمة السر مطلوبة لكي تتمكن من إدارة مكانك لاحقاً")

    # 3. منع تكرار البريد الإلكتروني
    if payload.owner_email:
        existing = db.query(Place).filter(Place.owner_email == payload.owner_email).first()
        if existing:
            raise HTTPException(status_code=400, detail="هذا البريد مسجل مسبقاً، يرجى تسجيل الدخول")

    # 4. إنشاء الكائن الجديد في قاعدة البيانات
    new_place = Place(
        name=payload.name.strip(),
        category=payload.category.strip(),
        area=payload.area,
        address=payload.address,
        description=payload.description,
        phone=payload.phone,
        whatsapp=payload.whatsapp,
        website=payload.website,
        instagram=payload.instagram,
        facebook=payload.facebook,
        map_url=payload.map_url,
        latitude=payload.latitude,
        longitude=payload.longitude,
        open_hours=payload.open_hours,
        price_range=payload.price_range,
        tags=payload.tags,
        owner_email=payload.owner_email.lower().strip() if payload.owner_email else None,
        owner_password=payload.owner_password,
        owner_name=payload.owner_name,
        subscription_type=payload.subscription_type,
        payment_method=payload.payment_method,
        subscription_status="active" if is_admin else "pending", # الأدمن يفعّل فوراً
        payment_status="pending",
        is_premium=payload.is_premium if is_admin else False,
        is_verified=payload.is_verified if is_admin else False,
        created_at=datetime.utcnow(),
    )

    # 5. إذا كان المنشئ هو الأدمن، نمنح سنة اشتراك مجانية فوراً
    if is_admin:
        now = datetime.utcnow()
        new_place.subscription_start = now
        new_place.subscription_end = now + timedelta(days=365)

    db.add(new_place)
    db.commit()
    db.refresh(new_place)
    
    # 6. إرجاع البيانات باستخدام القالب الجديد "AuthOut" لكي يرى المالك كلمة سره فوراً
    return schemas.PlaceAuthOut.from_orm(new_place)

@app.get("/api/places", response_model=schemas.PlacesResponse)
def get_all_places(
    q: Optional[str] = Query(None),
    cat: Optional[str] = Query(None),
    area: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    limit: int = Query(40, ge=1, le=2000),
    include_hidden: bool = Query(False),
    db: Session = Depends(get_db),
    x_admin_token: Optional[str] = Header(None),
):
    is_admin = (x_admin_token == ADMIN_SECRET_KEY)
    if include_hidden and not is_admin:
        include_hidden = False

    query = db.query(Place).options(joinedload(Place.images))

    if cat:
        query = query.filter(Place.category == cat)
    if area:
        query = query.filter(Place.area == area)
    if q:
        search = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Place.name.ilike(search),
                Place.area.ilike(search),
                Place.description.ilike(search),
                Place.tags.ilike(search),
            )
        )

    items_db = query.all()
    results = []

    for p in items_db:
        status = get_place_status(p)

        if not include_hidden and (status == "expired" or status == "pending"):
            continue

        p_out = schemas.PlaceOut.from_orm(p)
        p_out.subscription_status = status
        p_out.is_expired = is_expired(p)

        if (
            lat is not None and lng is not None
            and p.latitude is not None and p.longitude is not None
        ):
            p_out.distance = calculate_haversine(lat, lng, p.latitude, p.longitude)

        results.append(p_out)

    if lat is not None and lng is not None:
        results.sort(key=lambda x: (not x.is_premium, x.distance if x.distance is not None else 9999))
    else:
        results.sort(key=lambda x: (not x.is_premium, x.id), reverse=True)

    return {"items": results[:limit], "total": len(results)}


@app.get("/api/places/{place_id}", response_model=schemas.PlaceAuthOut)
def get_single_place(
    place_id: int,
    db: Session = Depends(get_db),
    x_admin_token: Optional[str] = Header(None),
):
    place = (
        db.query(Place)
        .options(joinedload(Place.images))
        .filter(Place.id == place_id)
        .first()
    )
    if not place:
        raise HTTPException(status_code=404, detail="المكان غير موجود")

    status = get_place_status(place)

    # التحقق: هل السائل هو الأدمن أو صاحب المكان؟
    is_admin = (x_admin_token == ADMIN_SECRET_KEY)
    is_owner = (x_admin_token == place.owner_password)

    # إذا لم يكن أدمن ولا صاحب المكان، وكان المكان مخفياً (معلق أو منتهي)
    if not is_admin and not is_owner:
        if status in ("pending", "expired"):
            raise HTTPException(status_code=404, detail="المكان غير موجود")
        
        # الأهم هنا: إذا كان زائر عادي، سنقوم بمسح البيانات الحساسة قبل إرسالها
        # رغم أننا نستخدم PlaceAuthOut كقالب، سنفرغ الحقول يدوياً للأمان
        p_out = schemas.PlaceAuthOut.from_orm(place)
        p_out.owner_password = None
        p_out.owner_email = None
        return p_out

    # إذا وصل الكود هنا، يعني السائل هو (أدمن) أو (صاحب مكان)، نرسل له البيانات كاملة
    p_out = schemas.PlaceAuthOut.from_orm(place)
    p_out.subscription_status = status
    p_out.is_expired = is_expired(place)
    return p_out

@app.get("/api/admin/verify")
def verify_admin(x_admin_token: Optional[str] = Header(None)):
    if x_admin_token != ADMIN_SECRET_KEY:
        raise HTTPException(status_code=401, detail="كود الأمان خاطئ")
    return {"status": "success"}

@app.post("/api/owner-login")
def owner_login(data: dict, db: Session = Depends(get_db)):
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()
    if not email or not password:
        raise HTTPException(status_code=400, detail="البيانات ناقصة")

    place = (
        db.query(Place)
        .filter(Place.owner_email == email, Place.owner_password == password)
        .first()
    )
    if not place:
        raise HTTPException(status_code=401, detail="معلومات الدخول خاطئة")

    return {
        "place_id": place.id,
        "place_name": place.name,
        "owner_password": place.owner_password, # أضفنا هذا السطر
        "subscription_status": get_place_status(place),
        "is_expired": is_expired(place),
    }


@app.post("/api/places/{place_id}/request-renew")
def request_renewal(
    place_id: int,
    db: Session = Depends(get_db),
    x_admin_token: Optional[str] = Header(None),
):
    p = db.query(Place).filter(Place.id == place_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="المكان غير موجود")

    if x_admin_token != ADMIN_SECRET_KEY and x_admin_token != p.owner_password:
        raise HTTPException(status_code=401, detail="غير مصرح لك")

    p.subscription_status = "pending"
    db.commit()
    return {"msg": "تم استلام الطلب، سيتم التواصل معك للتفعيل."}


@app.put("/api/places/{place_id}", response_model=schemas.PlaceAuthOut)
def update_place(
    place_id: int,
    payload: schemas.PlaceCreate,
    db: Session = Depends(get_db),
    x_admin_token: Optional[str] = Header(None),
):
    p = db.query(Place).filter(Place.id == place_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="المكان غير موجود")

    is_admin = (x_admin_token == ADMIN_SECRET_KEY)
    is_owner = (x_admin_token == p.owner_password)
    
    if not is_admin and not is_owner:
        raise HTTPException(status_code=401, detail="كلمة المرور خاطئة أو غير مصرح لك")

    # منع صاحب المحل من التعديل إذا انتهى اشتراكه (الأدمن مستثنى)
    if is_owner and is_expired(p) and not is_admin:
        raise HTTPException(status_code=403, detail="انتهى الاشتراك. لا يمكنك التعديل حالياً.")

    # تحديث البيانات الأساسية
    p.name = payload.name
    p.category = payload.category
    p.area = payload.area
    p.address = payload.address
    p.description = payload.description
    p.phone = payload.phone
    p.whatsapp = payload.whatsapp
    p.website = payload.website
    p.instagram = payload.instagram
    p.facebook = payload.facebook
    p.map_url = payload.map_url
    p.latitude = payload.latitude
    p.longitude = payload.longitude
    p.open_hours = payload.open_hours
    p.price_range = payload.price_range
    p.tags = payload.tags

    if is_admin:
        p.is_premium = payload.is_premium
        p.is_verified = payload.is_verified

    db.commit()
    db.refresh(p)
    
    # تحويل النتيجة للقالب الجديد لضمان رجوع البيانات كاملة للمالك/الأدمن
    return schemas.PlaceAuthOut.from_orm(p)

@app.delete("/api/places/{place_id}")
def delete_place(
    place_id: int,
    db: Session = Depends(get_db),
    x_admin_token: Optional[str] = Header(None),
):
    p = db.query(Place).options(joinedload(Place.images)).filter(Place.id == place_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="غير موجود")

    is_admin = (x_admin_token == ADMIN_SECRET_KEY)
    is_owner = (x_admin_token == p.owner_password)
    if not is_admin and not is_owner:
        raise HTTPException(status_code=401, detail="ممنوع")

    for img in p.images:
        try:
            filename = os.path.basename(img.image_url)
            full_path = os.path.join(PLACE_IMAGES_DIR, filename)
            if os.path.exists(full_path):
                os.remove(full_path)
        except Exception as e:
            print(f"Error deleting file: {e}")

    db.delete(p)
    db.commit()
    return {"status": "deleted"}


@app.post("/api/places/{place_id}/images")
async def upload_images(
    place_id: int,
    images: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    x_admin_token: Optional[str] = Header(None),
):
    p = (
        db.query(Place)
        .options(joinedload(Place.images))
        .filter(Place.id == place_id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="غير موجود")

    is_admin = (x_admin_token == ADMIN_SECRET_KEY)
    is_owner = (x_admin_token == p.owner_password)

    if not is_admin and not is_owner:
        raise HTTPException(status_code=401, detail="ممنوع")

    if is_owner and is_expired(p):
        raise HTTPException(status_code=403, detail="انتهى الاشتراك. لا يمكنك رفع صور حالياً.")

    saved_files = []
    for file in images:
        ext = _validate_extension(file.filename or "")
        new_name = f"{uuid.uuid4()}.{ext}"
        path = os.path.join(PLACE_IMAGES_DIR, new_name)

        contents = await file.read()
        if not contents:
            continue

        with open(path, "wb") as f:
            f.write(contents)

        db_img = PlaceImage(place_id=place_id, image_url=f"/images/places/{new_name}")
        db.add(db_img)
        saved_files.append(db_img.image_url)

    db.commit()
    return {"uploaded": saved_files}

@app.delete("/api/places/images/{image_id}")
def delete_image(
    image_id: int,
    db: Session = Depends(get_db),
    x_admin_token: Optional[str] = Header(None),
):
    img = db.query(PlaceImage).filter(PlaceImage.id == image_id).first()
    if not img:
        raise HTTPException(status_code=404, detail="الصورة غير موجودة")

    p = db.query(Place).options(joinedload(Place.images)).filter(Place.id == img.place_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="غير موجود")

    is_admin = (x_admin_token == ADMIN_SECRET_KEY)
    is_owner = (x_admin_token == p.owner_password)
    if not is_admin and not is_owner:
        raise HTTPException(status_code=401, detail="ممنوع")

    if is_owner and is_expired(p):
        raise HTTPException(status_code=403, detail="انتهى الاشتراك. لا يمكنك حذف صور حالياً.")

    try:
        filename = os.path.basename((img.image_url or "").strip("/"))
        full_path = os.path.join(PLACE_IMAGES_DIR, filename)
        if filename and os.path.exists(full_path):
            os.remove(full_path)
    except Exception:
        pass

    db.delete(img)
    db.commit()
    return {"status": "deleted"}

from pydantic import BaseModel

class ActivationRequest(BaseModel):
    months: int
    amount: float

@app.post("/api/places/{place_id}/activate")
def activate_subscription(
    place_id: int,
    payload: ActivationRequest,
    db: Session = Depends(get_db),
    x_admin_token: Optional[str] = Header(None),
):
    if x_admin_token != ADMIN_SECRET_KEY:
        raise HTTPException(status_code=401, detail="غير مصرح لك (أدمن فقط)")

    place = db.query(Place).filter(Place.id == place_id).first()
    if not place:
        raise HTTPException(status_code=404, detail="المكان غير موجود")

    now = datetime.utcnow()
    start_date = place.subscription_end if place.subscription_end and place.subscription_end > now else now

    if not place.subscription_end or place.subscription_end <= now:
        place.subscription_start = now

    days_to_add = payload.months * 30
    place.subscription_end = start_date + timedelta(days=days_to_add)

    place.subscription_status = "active"
    place.is_verified = True
    place.payment_status = "completed"

    place.payment_total = (place.payment_total or 0.0) + payload.amount

    db.commit()
    return {
        "msg": f"تم التفعيل لمدة {payload.months} أشهر",
        "end_date": place.subscription_end.strftime("%Y-%m-%d"),
        "total_revenue": place.payment_total,
    }

class ChatRequest(BaseModel):
    message: str

@app.post("/api/ai-guide")
async def ramallah_ai_guide(req: ChatRequest, db: Session = Depends(get_db)):
    if not client:
        raise HTTPException(status_code=503, detail="خدمة الذكاء الاصطناعي غير متوفرة")

    # جلب أسماء المنشآت وتصنيفاتها ومناطقها ليعرفها الـ AI
    places = db.query(Place).filter(Place.subscription_status == "active").all()
    context_data = ""
    for p in places:
        context_data += f"- اسم المكان: {p.name}, التصنيف: {p.category}, المنطقة: {p.area}, الوصف: {p.description}\n"

    system_instruction = (
        "أنت 'مساعد رام الله تايم الذكي'. مهمتك مساعدة الزوار في العثور على أفضل الأماكن في مدينة رام الله. "
        "استخدم البيانات التالية فقط للإجابة على المستخدم: \n" + context_data + 
        "\nإذا سألك المستخدم عن مكان غير موجود في القائمة، أخبره بلباقة أنك لا تملك معلومات عنه حالياً وتمنى له يوماً سعيداً في رام الله."
        "\nاجعل أسلوبك ودوداً وصبوراً واقترح عليهم التواصل مع المكان عبر واتساب (الموجود في تطبيقنا)."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": req.message}
            ],
            temperature=0.7
        )
        return {"reply": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))