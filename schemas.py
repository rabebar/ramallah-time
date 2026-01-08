from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, EmailStr

class PlaceImageOut(BaseModel):
    id: int
    image_url: str
    caption: Optional[str] = None
    class Config:
        from_attributes = True

class PlaceCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    category: str = Field(..., min_length=2, max_length=80)
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
    
    owner_email: Optional[EmailStr] = None
    owner_password: Optional[str] = None
    owner_name: Optional[str] = None
    
    subscription_type: Optional[str] = None
    payment_method: Optional[str] = None

    @field_validator('instagram', mode='before')
    @classmethod
    def clean_instagram(cls, v):
        if not v or not isinstance(v, str): return v
        v = v.strip()
        if v.startswith('@'): return v[1:]
        if 'instagram.com/' in v: return v.split('instagram.com/')[-1].replace('/', '').split('?')[0]
        return v

# هذا هو القالب العام (ما يراه الزوار العاديون) - تم حذف كلمة السر والبريد منه
class PlaceOut(BaseModel):
    id: int
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
    is_premium: bool
    is_verified: bool
    created_at: Optional[datetime] = None
    distance: Optional[float] = None 
    images: List[PlaceImageOut] = []
    subscription_status: str = "pending"
    is_expired: bool = False
    subscription_end: Optional[datetime] = None
    payment_total: float = 0.0

    class Config:
        from_attributes = True

    # هذا القالب مخصص للأدمن والمالك فقط (يحتوي على البيانات الحساسة)
# لاحظ أنه يرث (Inherit) من القالب السابق ويضيف عليه البيانات السرية
class PlaceAuthOut(PlaceOut):
    owner_email: Optional[str] = None
    owner_password: Optional[str] = None
    owner_name: Optional[str] = None
    subscription_type: Optional[str] = None
    subscription_end: Optional[datetime] = None
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    payment_total: float = 0.0

# قالب استجابة قائمة الأماكن
class PlacesResponse(BaseModel):
    items: List[PlaceOut]
    total: int