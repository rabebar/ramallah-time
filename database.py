import os
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash

# جلب الرابط وتصحيحه ليتوافق مع PostgreSQL الحديثة
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_db_connection():
    """فتح اتصال مع قاعدة بيانات PostgreSQL"""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    """إنشاء الجداول وبيانات تجريبية (للمرة الأولى)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("🚀 Checking/Initializing Database Schema...")
    
    # 1. إنشاء جدول المستخدمين (مع حقل status)
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            plan_type TEXT DEFAULT 'free',
            credits INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

    # 2. إنشاء جدول المتاجر (مع حقول التواصل)
    cursor.execute('''CREATE TABLE IF NOT EXISTS stores (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            bio TEXT,
            logo_url TEXT,
            display_phone TEXT,
            whatsapp_phone TEXT,
            instagram_handle TEXT,
            tiktok_handle TEXT,
            facebook_handle TEXT,
            address TEXT,
            website TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )''')

    # 3. إنشاء جدول المنتجات (مع حقل theme)
    cursor.execute('''CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            store_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            price DECIMAL,
            original_image_url TEXT NOT NULL,
            processed_image_url TEXT,
            template_style TEXT DEFAULT 'elegant',
            theme TEXT DEFAULT 'gold',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
        )''')

    # 4. إنشاء جدول المعاملات
    cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            amount DECIMAL NOT NULL,
            transaction_code TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            credits_added INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )''')

    # --- إدخال بيانات تجريبية (Seed Data) إذا لم تكن موجودة ---
    cursor.execute("SELECT id FROM users WHERE phone = %s", ("0592776784",))
    if not cursor.fetchone():
        print("🌱 Seeding initial data...")
        MERCHANT_PASSWORD = "12312312"
        # إنشاء المستخدم (Active مباشرة)
        cursor.execute(
            "INSERT INTO users (phone, password_hash, status, credits) VALUES (%s, %s, %s, %s) RETURNING id",
            ("0592776784", generate_password_hash(MERCHANT_PASSWORD), 'active', 100)
        )
        user_id = cursor.fetchone()['id']
        
        # إنشاء المتجر
        cursor.execute(
            "INSERT INTO stores (user_id, name, slug, bio) VALUES (%s, %s, %s, %s)",
            (user_id, "متجر سارة للأزياء", "sara-fashion", "أحدث صيحات الموضة بأسعار مناسبة")
        )
        print("✅ Initial user and store created.")
    else:
        print("✅ User already exists.")

    conn.commit()
    cursor.close()
    conn.close()

# يتم تنفيذ هذا الكود عند استيراد الملف في app.py
# هذا يضمن تجهيز القاعدة عند تشغيل السيرفر
init_db()
