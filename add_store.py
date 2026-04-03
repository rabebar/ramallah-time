from database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

# استخدام %s بدلاً من ? ليتوافق مع PostgreSQL على Render
cursor.execute("INSERT INTO stores (user_id, name, slug, bio) VALUES (%s, %s, %s, %s)", 
             (1, "متجر سارة للأزياء", "sara-fashion", "أحدث صيحات الموضة بأسعار مناسبة"))

conn.commit()
cursor.close()
conn.close()

print("✅ تم إنشاء المتجر بنجاح!")