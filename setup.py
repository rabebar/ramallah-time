import os
import psycopg2
from werkzeug.security import generate_password_hash
from database import get_db_connection

# في PostgreSQL، نقوم بمسح الجداول لضمان بداية نظيفة 100% كما كنت تفعل بحذف ملف .db
print("🚀 البدء في تهيئة قاعدة بيانات PostgreSQL...")

conn = get_db_connection()
cursor = conn.cursor()

# 1. حذف الجداول القديمة (للبداية من الصفر)
cursor.execute("DROP TABLE IF EXISTS transactions CASCADE;")
cursor.execute("DROP TABLE IF EXISTS products CASCADE;")
cursor.execute("DROP TABLE IF EXISTS stores CASCADE;")
cursor.execute("DROP TABLE IF EXISTS users CASCADE;")
print("🗑️ تم تنظيف قاعدة البيانات القديمة بنجاح.")

# 2. إنشاء جدول المستخدمين
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, 
        phone TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL, 
        plan_type TEXT DEFAULT 'free',
        credits INTEGER DEFAULT 10, 
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

# 3. إنشاء جدول المتاجر
cursor.execute('''CREATE TABLE IF NOT EXISTS stores (
        id SERIAL PRIMARY KEY, 
        user_id INTEGER, 
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL, 
        bio TEXT, 
        logo_url TEXT, 
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)''')

# 4. إنشاء جدول المنتجات
cursor.execute('''CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY, 
        store_id INTEGER, 
        name TEXT NOT NULL,
        description TEXT, 
        price DECIMAL, 
        original_image_url TEXT NOT NULL, 
        processed_image_url TEXT,
        template_style TEXT DEFAULT 'elegant', 
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
        FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE)''')

# 5. إنشاء جدول المعاملات المالية
cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY, 
        user_id INTEGER, 
        amount DECIMAL NOT NULL,
        transaction_code TEXT NOT NULL, 
        status TEXT DEFAULT 'pending', 
        credits_added INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)''')

# --- إدخال البيانات التجريبية الأساسية (Seed Data) ---

# ⚠️ غيّر كلمة المرور هنا قبل التشغيل
MERCHANT_PASSWORD = "12312312"

# إنشاء المستخدم الأول بكلمة مرور مشفرة
cursor.execute("INSERT INTO users (phone, password_hash, credits) VALUES (%s, %s, %s) RETURNING id", 
               ("0592776784", generate_password_hash(MERCHANT_PASSWORD), 10))

# الحصول على ID المستخدم الذي تم إنشاؤه لربط المتجر به
user_id = cursor.fetchone()['id']

# إنشاء المتجر الأول المرتبط بهذا المستخدم
cursor.execute("INSERT INTO stores (user_id, name, slug, bio) VALUES (%s, %s, %s, %s)", 
             (user_id, "متجر سارة للأزياء", "sara-fashion", "أحدث صيحات الموضة في رام الله بأسعار مناسبة"))

conn.commit()
cursor.close()
conn.close()

print("✅ تم إنشاء قاعدة بيانات (PostgreSQL) بنجاح!")
print(f"✅ تم إنشاء المستخدم (رقم: 0592776784) بكلمة مرور مشفرة ورصيد 10 صور.")
print("✅ تم إنشاء متجر (sara-fashion) جاهز للاستخدام.")