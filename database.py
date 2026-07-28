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
    cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS store_background TEXT DEFAULT 'none'")
    cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS announcement TEXT")
    cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS product_gallery_enabled BOOLEAN DEFAULT FALSE")

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

    cursor.execute('''CREATE TABLE IF NOT EXISTS product_images (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL,
            image_url TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        )''')
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_product_images_product_sort
        ON product_images(product_id, sort_order, id)
    """)

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

    # Manual subscription payment proofs. This keeps wallet/Buraq/IBAN transfers
    # separate from the existing subscription logic until the super admin approves.
    cursor.execute('''CREATE TABLE IF NOT EXISTS subscription_payments (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            store_id INTEGER,
            invoice_code TEXT NOT NULL UNIQUE,
            plan_type TEXT NOT NULL DEFAULT 'monthly',
            amount NUMERIC(12,2) NOT NULL,
            currency TEXT NOT NULL DEFAULT '₪',
            payment_method TEXT NOT NULL,
            transaction_ref TEXT,
            receipt_url TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            admin_note TEXT,
            reviewed_at TIMESTAMP,
            reviewed_by TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE SET NULL
        )''')
    cursor.execute("ALTER TABLE subscription_payments ADD COLUMN IF NOT EXISTS store_id INTEGER")
    cursor.execute("ALTER TABLE subscription_payments ADD COLUMN IF NOT EXISTS admin_note TEXT")
    cursor.execute("ALTER TABLE subscription_payments ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP")
    cursor.execute("ALTER TABLE subscription_payments ADD COLUMN IF NOT EXISTS reviewed_by TEXT")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_subscription_payments_status_created
        ON subscription_payments(status, created_at DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_subscription_payments_user_created
        ON subscription_payments(user_id, created_at DESC)
    """)

    # store_visits
    cursor.execute('''CREATE TABLE IF NOT EXISTS store_visits (
            id SERIAL PRIMARY KEY,
            store_id INTEGER NOT NULL,
            visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
        )''')
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'store_visits'
              AND column_name = 'visitor_key'
        ) AS exists
    """)
    has_unique_visitor_tracking = cursor.fetchone()['exists']
    cursor.execute("ALTER TABLE store_visits ADD COLUMN IF NOT EXISTS visitor_key TEXT")
    cursor.execute("ALTER TABLE store_visits ADD COLUMN IF NOT EXISTS visit_date DATE DEFAULT CURRENT_DATE")
    cursor.execute("ALTER TABLE store_visits ADD COLUMN IF NOT EXISTS page_type TEXT DEFAULT 'store'")
    cursor.execute("ALTER TABLE store_visits ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'unknown'")
    cursor.execute("ALTER TABLE store_visits ADD COLUMN IF NOT EXISTS source_url TEXT")

    # Reset inflated legacy counts once when unique visitor tracking is installed.
    if not has_unique_visitor_tracking:
        cursor.execute("DELETE FROM store_visits")

    cursor.execute("ALTER TABLE store_visits ALTER COLUMN visitor_key SET NOT NULL")
    cursor.execute("ALTER TABLE store_visits ALTER COLUMN visit_date SET NOT NULL")
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_store_visits_daily_visitor
        ON store_visits(store_id, visitor_key, visit_date)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_store_visits_source_date
        ON store_visits(source, visit_date)
    """)
    print("✅ store_visits table ready.")

    # join_page_visits
    cursor.execute('''CREATE TABLE IF NOT EXISTS join_page_visits (
            id SERIAL PRIMARY KEY,
            source TEXT,
            visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    print("✅ join_page_visits table ready.")

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
    cursor.execute("ALTER TABLE order_drafts ADD COLUMN IF NOT EXISTS customer_address TEXT")
    print("✅ order_drafts table ready.")

    # Browser push subscriptions for merchant admin PWAs.
    cursor.execute('''CREATE TABLE IF NOT EXISTS push_subscriptions (
            id SERIAL PRIMARY KEY,
            store_id INTEGER NOT NULL,
            endpoint TEXT NOT NULL UNIQUE,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            user_agent TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
        )''')
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_push_subscriptions_store
        ON push_subscriptions(store_id)
    """)
    print("✅ push_subscriptions table ready.")

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

    # Optional shipping integrations, isolated per store and order.
    cursor.execute('''CREATE TABLE IF NOT EXISTS shipping_integrations (
            id SERIAL PRIMARY KEY,
            store_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            environment TEXT NOT NULL DEFAULT 'testing',
            country TEXT NOT NULL DEFAULT 'palestine',
            api_key_encrypted TEXT,
            webhook_token TEXT,
            webhook_configured BOOLEAN NOT NULL DEFAULT FALSE,
            last_tested_at TIMESTAMP,
            last_test_success BOOLEAN,
            last_error TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE,
            UNIQUE(store_id, provider)
        )''')
    cursor.execute("ALTER TABLE shipping_integrations ADD COLUMN IF NOT EXISTS webhook_token TEXT")
    cursor.execute("ALTER TABLE shipping_integrations ADD COLUMN IF NOT EXISTS webhook_configured BOOLEAN NOT NULL DEFAULT FALSE")
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_shipping_integrations_webhook_token
        ON shipping_integrations(webhook_token)
        WHERE webhook_token IS NOT NULL
    """)
    cursor.execute('''CREATE TABLE IF NOT EXISTS shipping_shipments (
            id SERIAL PRIMARY KEY,
            order_id INTEGER NOT NULL,
            store_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            parcel_code TEXT,
            qr_code TEXT,
            shipping_status_id INTEGER,
            shipping_status_name TEXT,
            shipping_position_id INTEGER,
            shipping_cost NUMERIC(12,2),
            city_id INTEGER,
            village_id INTEGER,
            street_name TEXT,
            description TEXT,
            last_error TEXT,
            provider_response JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(order_id) REFERENCES order_drafts(id) ON DELETE CASCADE,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE,
            UNIQUE(order_id, provider)
        )''')
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_shipping_shipments_provider_code
        ON shipping_shipments(provider, parcel_code)
        WHERE parcel_code IS NOT NULL
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_shipping_shipments_store_status
        ON shipping_shipments(store_id, shipping_status_id)
    """)

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

    # Global application settings controlled by the super admin.
    cursor.execute('''CREATE TABLE IF NOT EXISTS app_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
    cursor.execute("""
        INSERT INTO app_settings (setting_key, setting_value)
        VALUES ('removebg_enabled', 'true')
        ON CONFLICT (setting_key) DO NOTHING
    """)
    for key, value in {
        'payment_account_name': 'RT Studio',
        'payment_wallet_name': '',
        'payment_wallet_number': '',
        'payment_bank_name': '',
        'payment_iban': '',
        'payment_note': 'بعد التحويل، أرسل رقم العملية أو صورة الإيصال وسيتم تفعيل الاشتراك بعد المراجعة.',
    }.items():
        cursor.execute("""
            INSERT INTO app_settings (setting_key, setting_value)
            VALUES (%s, %s)
            ON CONFLICT (setting_key) DO NOTHING
        """, (key, value))

    # Moeen Executive: isolated multi-tenant accounts and encrypted vaults.
    cursor.execute('''CREATE TABLE IF NOT EXISTS moeen_accounts (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            job_title TEXT,
            phone TEXT UNIQUE NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'suspended', 'cancelled')),
            plan_type TEXT NOT NULL DEFAULT 'monthly',
            subscription_start TIMESTAMP,
            subscription_end TIMESTAMP,
            must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS moeen_vaults (
            account_id INTEGER PRIMARY KEY REFERENCES moeen_accounts(id) ON DELETE CASCADE,
            ciphertext TEXT,
            iv TEXT,
            vault_salt TEXT,
            wrapped_vault TEXT,
            wrap_iv TEXT,
            version INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS moeen_devices (
            id SERIAL PRIMARY KEY,
            account_id INTEGER NOT NULL REFERENCES moeen_accounts(id) ON DELETE CASCADE,
            device_id TEXT NOT NULL,
            device_name TEXT NOT NULL,
            authorized BOOLEAN NOT NULL DEFAULT TRUE,
            revoked_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, device_id)
        )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS moeen_login_attempts (
            id BIGSERIAL PRIMARY KEY,
            account_id INTEGER REFERENCES moeen_accounts(id) ON DELETE CASCADE,
            phone TEXT,
            device_id TEXT,
            device_name TEXT,
            ip_address TEXT,
            outcome TEXT NOT NULL,
            reviewed BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS moeen_pairing_codes (
            id BIGSERIAL PRIMARY KEY,
            account_id INTEGER NOT NULL REFERENCES moeen_accounts(id) ON DELETE CASCADE,
            code_hash TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
    cursor.execute("ALTER TABLE moeen_devices ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMP")
    cursor.execute("ALTER TABLE moeen_login_attempts ADD COLUMN IF NOT EXISTS device_name TEXT")
    cursor.execute("ALTER TABLE moeen_login_attempts ADD COLUMN IF NOT EXISTS reviewed BOOLEAN NOT NULL DEFAULT FALSE")
    cursor.execute('''CREATE TABLE IF NOT EXISTS moeen_audio_blobs (
            account_id INTEGER NOT NULL REFERENCES moeen_accounts(id) ON DELETE CASCADE,
            audio_id TEXT NOT NULL,
            ciphertext BYTEA NOT NULL,
            iv TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(account_id, audio_id)
        )''')
    cursor.execute("""CREATE INDEX IF NOT EXISTS ix_moeen_attempts_account_created
                      ON moeen_login_attempts(account_id, created_at DESC)""")
    cursor.execute("""CREATE INDEX IF NOT EXISTS ix_moeen_accounts_subscription
                      ON moeen_accounts(status, subscription_end)""")

    conn.commit()
    cursor.close()
    conn.close()


def get_app_setting(setting_key, default=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key = %s",
            (setting_key,)
        )
        row = cursor.fetchone()
        return row['setting_value'] if row else default
    finally:
        cursor.close()
        conn.close()


def set_app_setting(setting_key, setting_value):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO app_settings (setting_key, setting_value, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (setting_key)
            DO UPDATE SET setting_value = EXCLUDED.setting_value,
                          updated_at = CURRENT_TIMESTAMP
        """, (setting_key, str(setting_value)))
        conn.commit()
    finally:
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


def record_store_visit(store_id, visitor_key, page_type='store', source='unknown', source_url=None):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO store_visits (store_id, visitor_key, page_type, source, source_url)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (store_id, visitor_key, visit_date) DO UPDATE SET
                page_type = COALESCE(EXCLUDED.page_type, store_visits.page_type),
                source = CASE
                    WHEN store_visits.source IS NULL OR store_visits.source IN ('unknown', 'direct')
                    THEN COALESCE(EXCLUDED.source, store_visits.source)
                    ELSE store_visits.source
                END,
                source_url = COALESCE(store_visits.source_url, EXCLUDED.source_url)
        """, (store_id, visitor_key, page_type, source or 'unknown', source_url))
        conn.commit()
    except Exception as e:
        print(f"Visit record error: {e}")
    finally:
        if conn:
            conn.close()


def record_join_visit(source='join'):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO join_page_visits (source) VALUES (%s)", (source,))
        conn.commit()
    except Exception as e:
        print(f"Join visit record error: {e}")
    finally:
        if conn:
            conn.close()


def get_join_visit_stats():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM join_page_visits")
        total = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as today FROM join_page_visits WHERE visited_at::date = CURRENT_DATE")
        today = cursor.fetchone()['today']
        cursor.execute("SELECT COUNT(*) as week FROM join_page_visits WHERE visited_at >= NOW() - INTERVAL '7 days'")
        week = cursor.fetchone()['week']
        cursor.execute("""
            SELECT COALESCE(source, 'join') as source, COUNT(*) as visits
            FROM join_page_visits
            GROUP BY COALESCE(source, 'join')
            ORDER BY visits DESC
        """)
        sources = cursor.fetchall()
        return {'total': total, 'today': today, 'week': week, 'sources': sources}
    except Exception as e:
        print(f"Join visit stats error: {e}")
        return {'total': 0, 'today': 0, 'week': 0, 'sources': []}
    finally:
        if conn:
            conn.close()


def get_visit_stats():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT visitor_key) as total FROM store_visits")
        total = cursor.fetchone()['total']
        cursor.execute("""
            SELECT COUNT(DISTINCT visitor_key) as today
            FROM store_visits
            WHERE visit_date = CURRENT_DATE
        """)
        today = cursor.fetchone()['today']
        cursor.execute("""
            SELECT COUNT(DISTINCT visitor_key) as week
            FROM store_visits
            WHERE visit_date >= CURRENT_DATE - INTERVAL '6 days'
        """)
        week = cursor.fetchone()['week']
        cursor.execute("""
            SELECT COUNT(DISTINCT visitor_key) as month
            FROM store_visits
            WHERE visit_date >= CURRENT_DATE - INTERVAL '29 days'
        """)
        month = cursor.fetchone()['month']
        cursor.execute("""
            SELECT
                s.name,
                s.slug,
                COUNT(DISTINCT sv.visitor_key) as visits,
                COUNT(DISTINCT sv.visitor_key) FILTER (WHERE sv.visit_date = CURRENT_DATE) as today_visits,
                COUNT(DISTINCT sv.visitor_key) FILTER (WHERE sv.visit_date >= CURRENT_DATE - INTERVAL '6 days') as week_visits,
                COUNT(DISTINCT sv.visitor_key) FILTER (WHERE sv.visit_date >= CURRENT_DATE - INTERVAL '29 days') as month_visits
            FROM store_visits sv JOIN stores s ON sv.store_id = s.id
            GROUP BY s.id, s.name, s.slug ORDER BY visits DESC LIMIT 5
        """)
        top_stores = cursor.fetchall()
        cursor.execute("""
            SELECT COALESCE(source, 'unknown') as source, COUNT(DISTINCT visitor_key) as visits
            FROM store_visits
            WHERE visit_date >= CURRENT_DATE - INTERVAL '29 days'
            GROUP BY COALESCE(source, 'unknown')
            ORDER BY visits DESC
            LIMIT 8
        """)
        sources_30d = cursor.fetchall()
        return {
            'total': total,
            'today': today,
            'week': week,
            'month': month,
            'top_stores': top_stores,
            'sources_30d': sources_30d,
        }
    except Exception as e:
        print(f"Visit stats error: {e}")
        return {'total': 0, 'today': 0, 'week': 0, 'month': 0, 'top_stores': [], 'sources_30d': []}
    finally:
        if conn:
            conn.close()

init_db()
