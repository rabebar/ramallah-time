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

# نظام التشفير (إصلاح: Argon2 يحتاج Text في القاعدة)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# --- الحسابات الجغرافية ---
def calculate_haversine(lat1, lon1, lat2, lon2):
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None
    try:
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        d_phi, d_lam = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
        a = (math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2.0) ** 2)
        return round(R * (2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))), 2)
    except: return None

# --- دورة حياة التطبيق ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # تشغيل تهيئة القاعدة مرة واحدة فقط عند الإقلاع
    try:
        init_db()
        print("--- [OK] Database Initialized ---")
    except Exception as e:
        print(f"--- [Error] DB Init: {e} ---")
    yield

app = FastAPI(title="Ramallah Time API", version="4.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# إدارة المجلدات
IMAGES_DIR = "images"
PLACE_IMAGES_DIR = os.path.join(IMAGES_DIR, "places")
os.makedirs(PLACE_IMAGES_DIR, exist_ok=True)

# ربط الملفات الثابتة
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- توجيه الصفحات ---
@app.get("/")
def home(user_agent: Optional[str] = Header(None)):
    ua = user_agent.lower() if user_agent else ""
    is_mobile = any(x in ua for x in ["iphone", "android", "mobile"])
    path = "frontend/mobile.html" if is_mobile else "frontend/index.html"
    return FileResponse(path)

@app.get("/places")
def places_page(): return FileResponse("frontend/places.html")

@app.get("/add-place")
def add_place_page(): return FileResponse("frontend/add-place.html")

@app.get("/owner-login")
def owner_login_page(): return FileResponse("frontend/owner-login.html")

@app.get("/owner-dashboard")
def owner_dashboard_page(): return FileResponse("frontend/owner-dashboard.html")

@app.get("/manifest.json")
def get_manifest(): return FileResponse("frontend/manifest.json")

@app.get("/sw.js")
def get_sw(): return FileResponse("frontend/sw.js")

@app.get("/favicon.ico")
def get_favicon(): return {"status": "no-icon"}

# --- دوال المساعدة للحالة ---
def is_expired(place: Place) -> bool:
    if place.subscription_status == "pending": return False
    if not place.subscription_end: return True
    return datetime.utcnow() > place.subscription_end

def get_place_status(place: Place) -> str:
    if place.subscription_status == "pending": return "pending"
    return "expired" if is_expired(place) else "active"

# --- [ميزة] الماسح الذكي بالذكاء الاصطناعي ---
@app.post("/api/ai-scan")
async def scan_place_with_ai(image: UploadFile = File(...)):
    if not client: raise HTTPException(status_code=503, detail="OpenAI Key Missing")
    image_data = await image.read()
    base64_image = base64.b64encode(image_data).decode("utf-8")
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Extract business info (name, category, phone, area, description) in JSON format."},
                {"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- [إصلاح] إضافة منشأة مع تشفير سليم ---
@app.post("/api/places", response_model=schemas.PlaceAuthOut)
def create_place(payload: schemas.PlaceCreate, db: Session = Depends(get_db), x_admin_token: Optional[str] = Header(None)):
    is_admin = (x_admin_token == ADMIN_SECRET_KEY)
    
    # تحويل الإيميل ليكون دائماً بحروف صغيرة لتجنب مشاكل الدخول
    email_lower = payload.owner_email.lower()
    
    if not is_admin:
        existing = db.query(Place).filter(Place.owner_email == email_lower).first()
        if existing:
            raise HTTPException(status_code=400, detail="هذا البريد مسجل مسبقاً")

    # تشفير كلمة السر بشكل آمن
    hashed_password = pwd_context.hash(payload.owner_password[:72]) if payload.owner_password else None

    # الحقن المصحح: استبعاد الباسورد والإيميل من القاموس لمنع التكرار
    data = payload.model_dump(exclude={"owner_password", "owner_email"})

    new_place = Place(
        **data,
        owner_password=hashed_password,
        owner_email=email_lower,
        subscription_status="active" if is_admin else "pending",
        created_at=datetime.utcnow()
    )

    if is_admin:
        new_place.subscription_start = datetime.utcnow()
        new_place.subscription_end = datetime.utcnow() + timedelta(days=365)

    try:
        db.add(new_place)
        db.commit()
        db.refresh(new_place)
        return new_place
    except Exception as e:
        db.rollback()
        print(f"Database Error: {e}")
        raise HTTPException(status_code=500, detail="حدث خطأ أثناء حفظ البيانات في القاعدة")

# --- [إصلاح] جلب كافة الأماكن وحماية الخصوصية ---
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
    # استخدام selectinload لضمان جلب كافة الصور لكل مكان دفعة واحدة
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
            is_owner = (x_admin_token and p.owner_password and x_admin_token == p.owner_password)

            if not (include_hidden and is_admin) and not is_owner:
                if status in ("pending", "expired"): continue

            schema_model = schemas.PlaceAuthOut if (is_admin or is_owner) else schemas.PlaceOut
            p_out = schema_model.model_validate(p)
            
            p_out.subscription_status = status
            p_out.is_expired = (status == "expired")

            # إصلاح حساب المسافة: التأكد من تحويل القيم لأرقام عشرية دقيقة
            if lat is not None and lng is not None and p.latitude is not None and p.longitude is not None:
                p_out.distance = calculate_haversine(float(lat), float(lng), float(p.latitude), float(p.longitude))
            else:
                p_out.distance = None
            
            results.append(p_out)
        except Exception as e:
            print(f"Error: {e}")
            continue

    # الترتيب: المميز أولاً، ثم الأقرب مسافة (99999 للأماكن التي بلا مسافة)
    results.sort(key=lambda x: (not getattr(x, 'is_premium', False), x.distance if x.distance is not None else 99999))

    return {"items": results, "total": len(results)}

# --- [إصلاح] تسجيل دخول المالك (التحقق العلمي) ---
@app.post("/api/owner-login")
def owner_login(data: dict, db: Session = Depends(get_db)):
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()
    
    # جلب المكان بناءً على البريد الإلكتروني
    place = db.query(Place).filter(Place.owner_email == email).first()
    
    # الإصلاح: التحقق العلمي من كلمة السر المشفرة
    if not place or not place.owner_password or not pwd_context.verify(password, place.owner_password):
        raise HTTPException(status_code=401, detail="البريد الإلكتروني أو كلمة السر غير صحيحة")

    return {
        "place_id": place.id,
        "place_name": place.name,
        "owner_password": place.owner_password,  # نرسل الهاش ليتم استخدامه كـ Token أمني
        "subscription_status": get_place_status(place),
        "is_expired": is_expired(place)
    }

# --- [إصلاح] تحديث البيانات ---
@app.put("/api/places/{place_id}", response_model=schemas.PlaceAuthOut)
def update_place(place_id: int, payload: dict, db: Session = Depends(get_db), x_admin_token: Optional[str] = Header(None)):
    p = db.query(Place).filter(Place.id == place_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="المكان غير موجود")

    # --- 1. نظام التحقق المرن (Auth) ---
    is_admin = (x_admin_token == ADMIN_SECRET_KEY)
    is_owner_hash = (x_admin_token and p.owner_password and x_admin_token == p.owner_password)
    
    # محاولة التحقق إذا كانت كلمة سر عادية (نص)
    is_owner_raw = False
    if x_admin_token and p.owner_password and not is_admin and not is_owner_hash:
        try:
            if pwd_context.verify(x_admin_token, p.owner_password):
                is_owner_raw = True
        except: pass

    if not (is_admin or is_owner_hash or is_owner_raw):
        raise HTTPException(status_code=401, detail="كلمة السر غير صحيحة")

    # --- 2. تنظيف البيانات (منع خطأ 500) ---
    # الحقول التي يمنع تعديلها يدوياً لأنها تسبب انهيار السيرفر
    forbidden = ["id", "images", "created_at", "subscription_start", "subscription_end"]

    try:
        for key, value in payload.items():
            if key in forbidden: continue 
            
            if hasattr(p, key):
                # التعامل مع كلمة المرور بذكاء
                if key == "owner_password" and value:
                    if value == p.owner_password: continue
                    try:
                        pwd_context.identify(str(value))
                        setattr(p, key, value)
                    except:
                        setattr(p, key, pwd_context.hash(str(value)[:72]))
                else:
                    setattr(p, key, value)

        db.commit()
        db.refresh(p)
        return p
    except Exception as e:
        db.rollback()
        print(f"Update Error: {e}")
        raise HTTPException(status_code=500, detail="خطأ داخلي أثناء تحديث القاعدة")

# --- [ميزة] المساعد الذكي ---
class ChatRequest(BaseModel): message: str
@app.post("/api/ai-guide")
async def ramallah_ai_guide(req: ChatRequest, db: Session = Depends(get_db)):
    if not client: return {"reply": "المساعد غير متاح."}
    places = db.query(Place).filter(Place.subscription_status == "active").all()
    context = "\n".join([f"- {p.name}: في {p.area}, {p.description}" for p in places])
    try:
        res = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": f"أنت مساعد رام الله تايم. استخدم البيانات: {context}"}, {"role": "user", "content": req.message}]
        )
        return {"reply": res.choices[0].message.content}
    except: return {"reply": "عذراً، حدث خطأ."}

# --- إدارة الصور والاشتراكات ---
@app.post("/api/places/{place_id}/images")
async def upload_images(place_id: int, images: List[UploadFile]=File(...), db: Session=Depends(get_db), x_admin_token: str=Header(None)):
    p = db.query(Place).filter(Place.id == place_id).first()
    if not p or (x_admin_token != ADMIN_SECRET_KEY and x_admin_token != p.owner_password):
        raise HTTPException(status_code=401)
    for img in images:
        fname = f"{uuid.uuid4()}.{img.filename.split('.')[-1]}"
        with open(os.path.join(PLACE_IMAGES_DIR, fname), "wb") as f: f.write(await img.read())
        db.add(PlaceImage(place_id=place_id, image_url=f"/images/places/{fname}"))
    db.commit()
    return {"status": "ok"}

@app.delete("/api/places/images/{image_id}")
def delete_image(image_id: int, db: Session=Depends(get_db), x_admin_token: str=Header(None)):
    img = db.query(PlaceImage).filter(PlaceImage.id == image_id).first()
    p = db.query(Place).filter(Place.id == img.place_id).first() if img else None
    if not img or (x_admin_token != ADMIN_SECRET_KEY and x_admin_token != p.owner_password):
        raise HTTPException(status_code=401)
    db.delete(img); db.commit()
    return {"status": "ok"}

@app.post("/api/places/{place_id}/activate")
def activate_place(place_id: int, data: dict, db: Session=Depends(get_db), x_admin_token: str=Header(None)):
    if x_admin_token != ADMIN_SECRET_KEY: raise HTTPException(status_code=401)
    p = db.query(Place).filter(Place.id == place_id).first()
    p.subscription_start = datetime.utcnow()
    p.subscription_end = (p.subscription_end or datetime.utcnow()) + timedelta(days=int(data.get("months", 12))*30)
    p.subscription_status = "active"
    p.payment_total += float(data.get("amount", 0))
    db.commit()
    return {"status": "ok"}

@app.get("/api/admin/verify")
def verify_admin(x_admin_token: str=Header(None)):
    if x_admin_token != ADMIN_SECRET_KEY: raise HTTPException(status_code=401)
    return {"status": "ok"}
@app.delete("/api/places/{place_id}")
def delete_place(place_id: int, db: Session = Depends(get_db), x_admin_token: Optional[str] = Header(None)):
    p = db.query(Place).filter(Place.id == place_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="المكان غير موجود")

    # التحقق من الصلاحية (أدمن أو صاحب المكان)
    is_admin = (x_admin_token == ADMIN_SECRET_KEY)
    is_owner = (x_admin_token and p.owner_password and x_admin_token == p.owner_password)

    if not is_admin and not is_owner:
        raise HTTPException(status_code=401, detail="غير مخول بالحذف")

    try:
        db.delete(p)
        db.commit()
        return {"status": "deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="خطأ في قاعدة البيانات أثناء الحذف")