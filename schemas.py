from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr # عدنا لاستخدام EmailStr

class PlaceImageOut(BaseModel):
    id: int
    image_url: str
    caption: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class PlaceBase(BaseModel):
    name: str # الحقول الأساسية بقيت إجبارية لضمان الجودة
    category: str
    area: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    website: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    map_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    open_hours: Optional[str] = None
    price_range: Optional[str] = None
    tags: Optional[str] = None
    is_premium: bool = False
    is_verified: bool = False

# هذه للإنشاء الجديد (صارمة جداً لضمان جودة البيانات الجديدة)
class PlaceCreate(PlaceBase):
    owner_email: EmailStr # إجباري وبصيغة صحيحة
    owner_password: str
    owner_name: Optional[str] = None
    subscription_type: Optional[str] = None
    payment_method: Optional[str] = None

# هذه للعرض (مرنة لكي لا تنهار الصفحة بسبب الأماكن القديمة)
class PlaceOut(BaseModel): 
    id: int
    name: Optional[str] = "بدون اسم" # إذا كان الاسم قديماً وفارغاً، نضع قيمة افتراضية
    category: Optional[str] = "عام"
    # بقية الحقول اختيارية لضمان العرض
    area: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    images: List[PlaceImageOut] = []
    subscription_status: str = "pending"
    is_expired: bool = False
    is_premium: bool = False
    distance: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)

class PlaceAuthOut(PlaceOut):
    owner_email: Optional[str] = None
    owner_password: Optional[str] = None

class PlacesResponse(BaseModel):
    items: List[PlaceOut]
    total: int