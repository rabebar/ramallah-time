from database import get_db_connection
from werkzeug.security import generate_password_hash

conn = get_db_connection()
cursor = conn.cursor()

# استخدام %s بدلاً من ? ليتوافق مع PostgreSQL
phone = "0590000000"
password_hash = generate_password_hash("12312312")

cursor.execute("INSERT INTO users (phone, password_hash, plan_type, credits) VALUES (%s, %s, %s, %s)", 
             (phone, password_hash, "free", 10))

conn.commit()
cursor.close()
conn.close()

print("✅ تم إنشاء المستخدم ورصيده 10 صور بنجاح!")