from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, EmailStr

class PlaceImageOut(BaseModel):
    id: int
    image_url: str
    caption: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# القالب الأساسي لكافة الحقول (بدون البيانات الحساسة)
class PlaceBase(BaseModel):
    name: str
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

# يستخدم عند إنشاء أو تحديث مكان
class PlaceCreate(PlaceBase):
    owner_email: Optional[EmailStr] = None
    owner_password: Optional[str] = None
    owner_name: Optional[str] = None
    subscription_type: Optional[str] = None
    payment_method: Optional[str] = None

# ما يراه الزوار في الموقع العام
class PlaceOut(PlaceBase):
    id: int
    created_at: Optional[datetime] = None
    distance: Optional[float] = None 
    images: List[PlaceImageOut] = []
    subscription_status: str = "pending"
    is_expired: bool = False
    subscription_end: Optional[datetime] = None
    payment_total: float = 0.0
    model_config = ConfigDict(from_attributes=True)

# ما يراه الأدمن والمالك (يحتوي على كلمات السر والإيميلات)
class PlaceAuthOut(PlaceOut):
    owner_email: Optional[str] = None
    owner_password: Optional[str] = None
    owner_name: Optional[str] = None
    subscription_type: Optional[str] = None
    payment_status: Optional[str] = None

# القالب الذي تسبب في الخطأ (تمت إعادته الآن)
class PlacesResponse(BaseModel):
    items: List[PlaceOut]
    total: int