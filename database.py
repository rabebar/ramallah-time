# database.py

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

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

    # users
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            plan_type TEXT DEFAULT 'monthly',
            subscription_start TIMESTAMP,
            subscription_end TIMESTAMP,
            is_frozen BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

    # Migration: add new columns if upgrading from old schema
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_start TIMESTAMP")
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_end TIMESTAMP")
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_frozen BOOLEAN DEFAULT FALSE")
    # Credits column kept for compatibility
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS credits INTEGER DEFAULT 0")


    # stores
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

    cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS inventory_enabled BOOLEAN DEFAULT FALSE")
    cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS next_sku_seq INTEGER DEFAULT 1001")
    cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS timezone TEXT")
    cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS currency TEXT")
    cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS store_theme TEXT DEFAULT 'classic'")
    cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS announcement TEXT")

    # products
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

    cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS sku TEXT")
    cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS stock_qty INTEGER DEFAULT 999")
    cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE")
    cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS background TEXT DEFAULT 'none'")
    cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS final_image_url TEXT")
    
    # === الإصلاح: إضافة الأعمدة الناقصة بأمان ===
    cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS card_ratio TEXT DEFAULT 'square'")
    cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS original_price DECIMAL DEFAULT NULL")
    cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS fit_mode TEXT DEFAULT 'contain'")

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_products_store_sku
        ON products(store_id, sku) WHERE sku IS NOT NULL
    """)

    # transactions
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

    # store_visits
    cursor.execute('''CREATE TABLE IF NOT EXISTS store_visits (
            id SERIAL PRIMARY KEY,
            store_id INTEGER NOT NULL,
            visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
        )''')
    print("✅ store_visits table ready.")

    # order_drafts
    cursor.execute('''CREATE TABLE IF NOT EXISTS order_drafts (
            id SERIAL PRIMARY KEY,
            store_id INTEGER NOT NULL,
            subtotal NUMERIC(12,2) NOT NULL DEFAULT 0,
            grand_total NUMERIC(12,2) NOT NULL DEFAULT 0,
            customer_name TEXT,
            customer_phone TEXT,
            customer_notes TEXT,
            wa_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'sent',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
        )''')
    print("✅ order_drafts table ready.")

    # order_lines
    cursor.execute('''CREATE TABLE IF NOT EXISTS order_lines (
            id SERIAL PRIMARY KEY,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            sku TEXT NOT NULL,
            name_snapshot TEXT NOT NULL,
            unit_price NUMERIC(12,2) NOT NULL,
            qty INTEGER NOT NULL,
            line_total NUMERIC(12,2) NOT NULL,
            FOREIGN KEY(order_id) REFERENCES order_drafts(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE RESTRICT
        )''')
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_order_lines_order ON order_lines(order_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_order_lines_product ON order_lines(product_id)")
    print("✅ order_lines table and indexes ready.")

    # analytics_events
    cursor.execute('''CREATE TABLE IF NOT EXISTS analytics_events (
            id SERIAL PRIMARY KEY,
            store_id INTEGER NOT NULL,
            product_id INTEGER,
            event_name TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE SET NULL
        )''')
    cursor.execute("""CREATE INDEX IF NOT EXISTS ix_analytics_store_event_ts
                      ON analytics_events(store_id, event_name, created_at)""")
    print("✅ analytics_events table and index ready.")

   
    conn.commit()
    cursor.close()
    conn.close()


def get_subscription_status(user):
    now = datetime.utcnow()
    sub_end = user.get('subscription_end')
    is_frozen = bool(user.get('is_frozen'))

    if is_frozen:
        return {
            'is_active': False, 'is_expired': False,
            'is_blocked': True, 'is_frozen': True,
            'days_left': 0, 'warn_renew': False, 'grace_msg': False
        }

    if not sub_end:
        return {
            'is_active': False, 'is_expired': False,
            'is_blocked': True, 'is_frozen': False,
            'days_left': 0, 'warn_renew': False, 'grace_msg': False
        }

    days_left = (sub_end - now).days
    grace_end = sub_end + timedelta(days=3)

    if now <= sub_end:
        warn_renew = days_left <= 1
        return {
            'is_active': True, 'is_expired': False,
            'is_blocked': False, 'is_frozen': False,
            'days_left': days_left, 'warn_renew': warn_renew, 'grace_msg': False
        }
    elif now <= grace_end:
        return {
            'is_active': True, 'is_expired': True,
            'is_blocked': False, 'is_frozen': False,
            'days_left': days_left, 'warn_renew': False, 'grace_msg': True
        }
    else:
        return {
            'is_active': False, 'is_expired': True,
            'is_blocked': True, 'is_frozen': False,
            'days_left': days_left, 'warn_renew': False, 'grace_msg': False
        }


def set_subscription(user_id, plan_type):
    PLAN_DAYS = {
        'monthly': 30,
        'biannual': 180,
        'annual': 365,
    }
    days = PLAN_DAYS.get(plan_type, 30)
    now = datetime.utcnow()
    sub_end = now + timedelta(days=days)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """UPDATE users
               SET plan_type = %s, subscription_start = %s, subscription_end = %s, is_frozen = FALSE
               WHERE id = %s""",
            (plan_type, now, sub_end, user_id)
        )
        conn.commit()
        return sub_end
    finally:
        cursor.close()
        conn.close()


def toggle_freeze(user_id, freeze: bool):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET is_frozen = %s WHERE id = %s", (freeze, user_id))
        conn.commit()
    finally:
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
        if conn:
            conn.close()


def get_visit_stats():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM store_visits")
        total = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as today FROM store_visits WHERE visited_at::date = CURRENT_DATE")
        today = cursor.fetchone()['today']
        cursor.execute("SELECT COUNT(*) as week FROM store_visits WHERE visited_at >= NOW() - INTERVAL '7 days'")
        week = cursor.fetchone()['week']
        cursor.execute("""
            SELECT s.name, s.slug, COUNT(sv.id) as visits
            FROM store_visits sv JOIN stores s ON sv.store_id = s.id
            GROUP BY s.id, s.name, s.slug ORDER BY visits DESC LIMIT 5
        """)
        top_stores = cursor.fetchall()
        return {'total': total, 'today': today, 'week': week, 'top_stores': top_stores}
    except Exception as e:
        print(f"Visit stats error: {e}")
        return {'total': 0, 'today': 0, 'week': 0, 'top_stores': []}
    finally:
        if conn:
            conn.close()

init_db()