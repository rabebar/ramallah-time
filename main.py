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
from pydantic import BaseModel

from fastapi import (
    FastAPI, Depends, HTTPException, Query, 
    UploadFile, File, Form, Header
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from passlib.context import CryptContext
from openai import OpenAI

from database import SessionLocal, init_db, Place, PlaceImage
import schemas

# --- الإعدادات والمفاتيح ---
ADMIN_SECRET_KEY = os.environ.get("ADMIN_SECRET_KEY", "ADMIN123123123")
api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

# --- نظام التشفير ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- الحسابات الجغرافية ---
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
        return round(R * c, 2)
    except:
        return None

# --- دورة حياة التطبيق ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- نظام رام الله تايم يعمل الآن ---")
    init_db()
    yield

app = FastAPI(title="Ramallah Time API", version="3.6.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- إدارة المجلدات والملفات الثابتة ---
FRONTEND_DIR = "frontend"
IMAGES_DIR = "images"
PLACE_IMAGES_DIR = os.path.join(IMAGES_DIR, "places")

for directory in [IMAGES_DIR, PLACE_IMAGES_DIR]:
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

# --- توجيه الصفحات الرئيسية ---
@app.get("/")
def home(user_agent: Optional[str] = Header(None)):
    ua = user_agent.lower() if user_agent else ""
    mobile_indicators = ["iphone", "android", "phone", "mobile"]
    if any(ind in ua for ind in mobile_indicators):
        mobile_path = os.path.join(FRONTEND_DIR, "mobile.html")
        if os.path.exists(mobile_path): return FileResponse(mobile_path)
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/places")
def places_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "places.html"))

@app.get("/add-place")
def add_place_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "add-place.html"))

@app.get("/owner-login")
def owner_login_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "owner-login.html"))

@app.get("/owner-dashboard")
def owner_dashboard_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "owner-dashboard.html"))

@app.get("/manifest.json")
def get_manifest():
    return FileResponse(os.path.join(FRONTEND_DIR, "manifest.json"), media_type="application/json")

@app.get("/sw.js")
def get_sw():
    return FileResponse(os.path.join(FRONTEND_DIR, "sw.js"), media_type="application/javascript")

# --- التحقق من الصور ---
ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png", "webp"}
def _validate_extension(filename: str) -> str:
    ext = (filename.split(".")[-1] if "." in filename else "").lower().strip()
    if ext not in ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=400, detail="نوع الملف غير مدعوم")
    return ext

# --- دوال المساعدة للحالة ---
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

# --- [مصحح] الماسح الذكي بالذكاء الاصطناعي ---
@app.post("/api/ai-scan")
async def scan_place_with_ai(image: UploadFile = File(...)):
    if not client:
        raise HTTPException(status_code=503, detail="مفتاح OpenAI مفقود")
    _validate_extension(image.filename or "")
    image_data = await image.read()
    base64_image = base64.b64encode(image_data).decode("utf-8")

    system_prompt = (
        "أنت مساعد ذكي لاستخراج بيانات الأعمال. استخرج المعلومات التالية من الصورة: "
        "(name, category, phone, area, address, description, whatsapp, instagram, facebook). "
        "أعد النتيجة حصراً بتنسيق JSON. اترك الحقول المفقودة فارغة."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": "Extract business info from this image:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في التحليل: {str(e)}")

# --- إضافة منشأة جديدة (مع تشفير كلمة السر) ---
@app.post("/api/places", response_model=schemas.PlaceAuthOut)
def create_place(
    payload: schemas.PlaceCreate,
    db: Session = Depends(get_db),
    x_admin_token: Optional[str] = Header(None),
):
    is_admin = (x_admin_token == ADMIN_SECRET_KEY)
    
    if not is_admin:
        if not payload.owner_email or not payload.owner_password:
            raise HTTPException(status_code=400, detail="البريد وكلمة السر مطلوبان للتسجيل")
        existing = db.query(Place).filter(Place.owner_email == payload.owner_email).first()
        if existing:
            raise HTTPException(status_code=400, detail="هذا البريد مسجل مسبقاً")

    # تشفير كلمة السر باستخدام Bcrypt
    hashed_password = pwd_context.hash(payload.owner_password) if payload.owner_password else None

    new_place = Place(
        name=payload.name, category=payload.category, area=payload.area,
        address=payload.address, description=payload.description,
        phone=payload.phone, whatsapp=payload.whatsapp,
        website=payload.website, instagram=payload.instagram,
        facebook=payload.facebook, map_url=payload.map_url,
        latitude=payload.latitude, longitude=payload.longitude,
        open_hours=payload.open_hours, price_range=payload.price_range,
        tags=payload.tags, owner_email=payload.owner_email,
        owner_password=hashed_password, owner_name=payload.owner_name,
        subscription_type=payload.subscription_type,
        payment_method=payload.payment_method,
        subscription_status="active" if is_admin else "pending",
        payment_status="pending",
        is_premium=payload.is_premium if is_admin else False,
        is_verified=payload.is_verified if is_admin else False,
        created_at=datetime.utcnow(),
    )

    if is_admin:
        now = datetime.utcnow()
        new_place.subscription_start = now
        new_place.subscription_end = now + timedelta(days=365)

    db.add(new_place)
    db.commit()
    db.refresh(new_place)
    return schemas.PlaceAuthOut.model_validate(new_place)

# --- [معدل ومحصن] جلب كافة الأماكن ---
@app.get("/api/places", response_model=schemas.PlacesResponse)
def get_all_places(
    q: Optional[str] = Query(None),
    cat: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    include_hidden: bool = Query(False),
    db: Session = Depends(get_db),
    x_admin_token: Optional[str] = Header(None),
):
    is_admin = (x_admin_token == ADMIN_SECRET_KEY)
    query = db.query(Place).options(joinedload(Place.images))

    if cat: query = query.filter(Place.category == cat)
    if q:
        search = f"%{q.strip()}%"
        query = query.filter(or_(Place.name.ilike(search), Place.area.ilike(search), Place.tags.ilike(search)))

    items_db = query.all()
    results = []

    for p in items_db:
        try:
            status = get_place_status(p)
            # حصانة ضد القيم الفارغة في كلمة المرور (سبب الخطأ 500)
            is_owner = (x_admin_token and p.owner_password and x_admin_token == p.owner_password)

            # سياسة العرض
            if not (include_hidden and is_admin) and not is_owner:
                if status in ("pending", "expired"): continue

            # اختيار القالب المناسب
            schema_model = schemas.PlaceAuthOut if (is_admin or is_owner) else schemas.PlaceOut
            p_out = schema_model.model_validate(p)
            
            p_out.subscription_status = status
            p_out.is_expired = is_expired(p)

            if lat and lng and p.latitude:
                p_out.distance = calculate_haversine(lat, lng, p.latitude, p.longitude)
            
            results.append(p_out)
        except:
            continue # تخطي أي سجل يحتوي على بيانات تالفة بدلاً من تعطيل التطبيق

    # الترتيب: المميز أولاً، ثم المسافة
    results.sort(key=lambda x: (not getattr(x, 'is_premium', False), getattr(x, 'distance', 99999) or 99999))

    return {"items": results, "total": len(results)}

# --- [معدل] جلب مكان واحد ---
@app.get("/api/places/{place_id}", response_model=schemas.PlaceAuthOut)
def get_single_place(place_id: int, db: Session = Depends(get_db), x_admin_token: Optional[str] = Header(None)):
    place = db.query(Place).options(joinedload(Place.images)).filter(Place.id == place_id).first()
    if not place: raise HTTPException(status_code=404, detail="المكان غير موجود")
    
    is_admin = (x_admin_token == ADMIN_SECRET_KEY)
    is_owner = (x_admin_token and place.owner_password and x_admin_token == place.owner_password)
    
    if not is_admin and not is_owner:
        if get_place_status(place) in ("pending", "expired"):
            raise HTTPException(status_code=404, detail="المكان غير متاح حالياً")
        return schemas.PlaceOut.model_validate(place)
    
    p_out = schemas.PlaceAuthOut.model_validate(place)
    p_out.subscription_status = get_place_status(place)
    p_out.is_expired = is_expired(place)
    return p_out

# --- التحقق من الأدمن وتسجيل دخول المالك ---
@app.get("/api/admin/verify")
def verify_admin(x_admin_token: Optional[str] = Header(None)):
    if x_admin_token != ADMIN_SECRET_KEY: raise HTTPException(status_code=401)
    return {"status": "success"}

@app.post("/api/owner-login")
def owner_login(data: dict, db: Session = Depends(get_db)):
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()
    place = db.query(Place).filter(Place.owner_email == email).first()
    
    if not place or not place.owner_password:
        raise HTTPException(status_code=401, detail="معلومات الدخول خاطئة")
    
    # التحقق من كلمة السر المشفرة
    try:
        if not pwd_context.verify(password, place.owner_password):
            raise HTTPException(status_code=401, detail="معلومات الدخول خاطئة")
    except:
        # في حال كانت قديمة جداً وغير مشفرة
        if password != place.owner_password:
            raise HTTPException(status_code=401, detail="معلومات الدخول خاطئة")
    
    return {
        "place_id": place.id, "place_name": place.name,
        "owner_password": place.owner_password,
        "subscription_status": get_place_status(place), "is_expired": is_expired(place)
    }

# --- التعديل الشامل المرن ---
@app.put("/api/places/{place_id}", response_model=schemas.PlaceAuthOut)
def update_place(place_id: int, payload: dict, db: Session = Depends(get_db), x_admin_token: Optional[str] = Header(None)):
    p = db.query(Place).filter(Place.id == place_id).first()
    if not p: raise HTTPException(status_code=404)
    
    is_admin = (x_admin_token == ADMIN_SECRET_KEY)
    is_owner = (x_admin_token and p.owner_password and x_admin_token == p.owner_password)
    if not is_admin and not is_owner: raise HTTPException(status_code=401)

    for key, value in payload.items():
        if hasattr(p, key):
            if key == "owner_password" and value and not str(value).startswith("$2b$"):
                value = pwd_context.hash(str(value)) 
            setattr(p, key, value)
    
    db.commit()
    db.refresh(p)
    return schemas.PlaceAuthOut.model_validate(p)

# --- إدارة الصور ---
@app.post("/api/places/{place_id}/images")
async def upload_images(place_id: int, images: List[UploadFile] = File(...), db: Session = Depends(get_db), x_admin_token: Optional[str] = Header(None)):
    p = db.query(Place).filter(Place.id == place_id).first()
    is_admin = (x_admin_token == ADMIN_SECRET_KEY)
    is_owner = (x_admin_token and p.owner_password and x_admin_token == p.owner_password)
    
    if not p or not (is_admin or is_owner):
        raise HTTPException(status_code=401)
    
    uploaded = []
    for file in images:
        ext = _validate_extension(file.filename or "")
        filename = f"{uuid.uuid4()}.{ext}"
        path = os.path.join(PLACE_IMAGES_DIR, filename)
        with open(path, "wb") as f: f.write(await file.read())
        db_img = PlaceImage(place_id=place_id, image_url=f"/images/places/{filename}")
        db.add(db_img)
        uploaded.append(db_img.image_url)
    db.commit()
    return {"uploaded": uploaded}

@app.delete("/api/places/images/{image_id}")
def delete_image(image_id: int, db: Session = Depends(get_db), x_admin_token: Optional[str] = Header(None)):
    img = db.query(PlaceImage).filter(PlaceImage.id == image_id).first()
    if not img: raise HTTPException(status_code=404)
    p = db.query(Place).filter(Place.id == img.place_id).first()
    
    is_admin = (x_admin_token == ADMIN_SECRET_KEY)
    is_owner = (x_admin_token and p.owner_password and x_admin_token == p.owner_password)
    
    if not (is_admin or is_owner):
        raise HTTPException(status_code=401)
    
    try:
        path = os.path.join(IMAGES_DIR, img.image_url.lstrip("/images/"))
        if os.path.exists(path): os.remove(path)
    except: pass
    db.delete(img)
    db.commit()
    return {"status": "deleted"}

# --- المساعد الذكي ---
class ChatRequest(BaseModel):
    message: str

@app.post("/api/ai-guide")
async def ramallah_ai_guide(req: ChatRequest, db: Session = Depends(get_db)):
    if not client: return {"reply": "المساعد غير مفعل حالياً."}
    
    places = db.query(Place).filter(Place.subscription_status == "active").all()
    context = "\n".join([f"- {p.name}: في {p.area}, وصفه: {p.description}" for p in places])
    
    instruction = (
        "أنت 'مساعد رام الله تايم الذكي'. خبير في مدينة رام الله. "
        "استخدم هذه البيانات حصراً للإجابة: \n" + context + 
        "\nكن ودوداً، مختصراً، وباللهجة الفلسطينية."
    )
    try:
        res = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": instruction}, {"role": "user", "content": req.message}]
        )
        return {"reply": res.choices[0].message.content}
    except: return {"reply": "عذراً، واجهت مشكلة في التفكير، حاول ثانية."}

# --- الحذف والتفعيل ---
@app.delete("/api/places/{place_id}")
def delete_place(place_id: int, db: Session = Depends(get_db), x_admin_token: Optional[str] = Header(None)):
    p = db.query(Place).filter(Place.id == place_id).first()
    is_admin = (x_admin_token == ADMIN_SECRET_KEY)
    is_owner = (x_admin_token and p.owner_password and x_admin_token == p.owner_password)
    
    if not p or not (is_admin or is_owner):
        raise HTTPException(status_code=401)
    db.delete(p)
    db.commit()
    return {"status": "deleted"}

@app.post("/api/places/{place_id}/activate")
def activate_subscription(place_id: int, payload: dict, db: Session = Depends(get_db), x_admin_token: Optional[str] = Header(None)):
    if x_admin_token != ADMIN_SECRET_KEY: raise HTTPException(status_code=401)
    p = db.query(Place).filter(Place.id == place_id).first()
    now = datetime.utcnow()
    p.subscription_start = now
    p.subscription_end = now + timedelta(days=int(payload.get("months", 12)) * 30)
    p.subscription_status = "active"
    p.payment_total = (p.payment_total or 0) + float(payload.get("amount", 0))
    db.commit()
    return {"status": "activated"}