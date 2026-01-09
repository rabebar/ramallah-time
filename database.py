from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# تغيير اسم القاعدة لضمان إقلاع نظيف بنسبة 100%
DB_FILENAME = os.getenv("DB_FILENAME", "ramallah_final.db")
DB_PATH = os.path.join(BASE_DIR, DB_FILENAME)

# جلب رابط قاعدة البيانات من البيئة (Render) أو استخدام المحلي
DATABASE_URL = os.getenv("DATABASE_URL", f: "sqlite:///{DB_PATH}")

# تصحيح الرابط إذا كان يبدأ بـ postgres:// ليصبح postgresql:// (مطلوب لريندر)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# إعداد المحرك (Engine) مع مراعاة نوع القاعدة
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Place(Base):
    __tablename__ = "places"

    id = Column(Integer, primary_key=True, index=True)

    # ---------------- Basic Info ---------------- #
    name = Column(String(200), nullable=False, index=True)
    category = Column(String(80), nullable=False, index=True)

    area = Column(String(120), nullable=True, index=True)
    address = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    phone = Column(String(50), nullable=True)
    whatsapp = Column(String(50), nullable=True)
    website = Column(String(255), nullable=True)
    instagram = Column(String(100), nullable=True)
    facebook = Column(String(255), nullable=True)

    map_url = Column(String(500), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    open_hours = Column(String(255), nullable=True)
    price_range = Column(String(50), nullable=True)
    tags = Column(String(255), nullable=True)

    # ---------------- Owner Account ---------------- #
    owner_email = Column(String(255), nullable=True, unique=True, index=True)
    owner_password = Column(String(100), nullable=True)
    owner_name = Column(String(200), nullable=True)

    # ---------------- Subscription System ---------------- #
    subscription_status = Column(String(20), default="pending", nullable=False)
    subscription_type = Column(String(50), nullable=True)
    subscription_start = Column(DateTime, nullable=True)
    subscription_end = Column(DateTime, nullable=True)
    payment_method = Column(String(50), nullable=True)
    payment_status = Column(String(50), default="pending", nullable=True)
    payment_total = Column(Float, default=0.0)

    # ---------------- Admin Controls ---------------- #
    is_premium = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # ---------------- Images ---------------- #
    images = relationship(
        "PlaceImage",
        back_populates="place",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PlaceImage(Base):
    __tablename__ = "place_images"

    id = Column(Integer, primary_key=True, index=True)
    place_id = Column(Integer, ForeignKey("places.id", ondelete="CASCADE"), nullable=False, index=True)

    image_url = Column(String(600), nullable=False)
    caption = Column(String(255), nullable=True)

    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    place = relationship("Place", back_populates="images")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)