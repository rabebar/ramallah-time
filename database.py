import os
import psycopg2
from psycopg2.extras import RealDictCursor

# جلب الرابط وتصحيحه ليتوافق مع PostgreSQL الحديثة
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_db_connection():
    """فتح اتصال مع قاعدة بيانات PostgreSQL باستخدام الرابط المباشر"""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    """إنشاء الجداول في PostgreSQL لضمان جاهزية النظام على Render"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. جدول المستخدمين
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            plan_type TEXT DEFAULT 'free',
            credits INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

    # 2. جدول المتاجر
    cursor.execute('''CREATE TABLE IF NOT EXISTS stores (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            bio TEXT,
            logo_url TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )''')

    # 3. جدول المنتجات
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
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
        )''')

    # 4. جدول المعاملات
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

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ PostgreSQL: Database & Tables initialized successfully!")

if __name__ == "__main__":
    init_db()