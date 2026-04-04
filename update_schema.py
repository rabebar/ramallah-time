from database import get_db_connection

def update_schema():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("🚀 Starting schema update for stores table...")
    
    try:
        # إضافة جميع حقول التواصل والمعلومات
        cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS display_phone TEXT;")
        cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS whatsapp_phone TEXT;")
        cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS instagram_handle TEXT;")
        cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS tiktok_handle TEXT;")
        cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS facebook_handle TEXT;")
        cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS address TEXT;")
        cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS website TEXT;")

        conn.commit()
        print("✅ Schema updated successfully!")
        print("   + display_phone")
        print("   + whatsapp_phone")
        print("   + instagram_handle")
        print("   + tiktok_handle")
        print("   + facebook_handle")
        print("   + address")
        print("   + website")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error during update: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    update_schema()