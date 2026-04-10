import os
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    print("🚀 Checking/Initializing Database Schema...")

    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            plan_type TEXT DEFAULT 'free',
            credits INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

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
            category TEXT DEFAULT 'الكل',
            background TEXT DEFAULT 'none',
            final_image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
        )''')

    try:
        cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS background TEXT DEFAULT 'none'")
        print("✅ background column ready.")
    except Exception as e:
        print(f"background column note: {e}")

    try:
        cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS final_image_url TEXT")
        print("✅ final_image_url column ready.")
    except Exception as e:
        print(f"final_image_url column note: {e}")

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

    cursor.execute('''CREATE TABLE IF NOT EXISTS store_visits (
            id SERIAL PRIMARY KEY,
            store_id INTEGER NOT NULL,
            visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
        )''')
    print("✅ store_visits table ready.")

    cursor.execute("SELECT id FROM users WHERE phone = %s", ("0592776784",))
    if not cursor.fetchone():
        print("🌱 Seeding initial data...")
        MERCHANT_PASSWORD = "12312312"
        cursor.execute(
            "INSERT INTO users (phone, password_hash, status, credits) VALUES (%s, %s, %s, %s) RETURNING id",
            ("0592776784", generate_password_hash(MERCHANT_PASSWORD), 'active', 100)
        )
        user_id = cursor.fetchone()['id']
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

def record_store_visit(store_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO store_visits (store_id) VALUES (%s)", (store_id,))
        conn.commit()
    except Exception as e:
        print(f"Visit record error: {e}")
    finally:
        if conn: conn.close()

def get_visit_stats():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM store_visits")
        total = cursor.fetchone()['total']
        cursor.execute("""
            SELECT COUNT(*) as today 
            FROM store_visits 
            WHERE visited_at::date = CURRENT_DATE
        """)
        today = cursor.fetchone()['today']
        cursor.execute("""
            SELECT COUNT(*) as week
            FROM store_visits
            WHERE visited_at >= NOW() - INTERVAL '7 days'
        """)
        week = cursor.fetchone()['week']
        cursor.execute("""
            SELECT s.name, s.slug, COUNT(sv.id) as visits
            FROM store_visits sv
            JOIN stores s ON sv.store_id = s.id
            GROUP BY s.id, s.name, s.slug
            ORDER BY visits DESC
            LIMIT 5
        """)
        top_stores = cursor.fetchall()
        return {'total': total, 'today': today, 'week': week, 'top_stores': top_stores}
    except Exception as e:
        print(f"Visit stats error: {e}")
        return {'total': 0, 'today': 0, 'week': 0, 'top_stores': []}
    finally:
        if conn: conn.close()

init_db()