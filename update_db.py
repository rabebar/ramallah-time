from database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

# إضافة عمود جديد يحفظ نوع القالب (استخدام الـ Cursor ليتوافق مع PostgreSQL)
try:
    cursor.execute("ALTER TABLE products ADD COLUMN template_style TEXT DEFAULT 'elegant'")
    conn.commit()
    print("✅ تم إضافة عمود القوالب بنجاح! النظام مرن الآن للتوسع.")
except Exception as e:
    # التراجع عن التغيير في حال حدوث خطأ (مثل أن العمود موجود أصلاً)
    conn.rollback()
    if "already exists" in str(e).lower():
        print("⚠️ عمود القوالب موجود مسبقاً، لا مشكلة.")
    else:
        print(f"❌ حدث خطأ غير متوقع: {e}")

cursor.close()
conn.close()