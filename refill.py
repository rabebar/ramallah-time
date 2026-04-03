from database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

# تحديث رصيد المستخدم رقم 1 بوضع 100 صورة (استخدام %s للقيم)
cursor.execute("UPDATE users SET credits = %s WHERE id = %s", (100, 1))

conn.commit()
cursor.close()
conn.close()

print("💰 تم إعادة تعبئة الرصيد: 100 صورة بنجاح!")