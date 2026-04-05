"""
Ramallah Time - Core Engine (v3.1 - Production Ready)
---------------------------------------------------
قواعد العمل المطبقة:
1. PostgreSQL placeholders (%s)
2. نظام الخصم الصارم للرصيد عند الحفظ فقط.
3. التوافق الكامل مع التصميم الفاتح والـ PWA.
4. معالجة كافة حقول التواصل الاجتماعي والعناوين.
"""

import os
import io
import uuid
import logging
from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from rembg import remove
from PIL import Image
from database import get_db_connection

# إعداد التطبيق
app = Flask(__name__)

# --- الإعدادات الأمنية والمفاتيح ---
app.secret_key = os.environ.get('SECRET_KEY', 'rt_studio_secure_2025_palestine_#99')
MASTER_PASSWORD = os.environ.get('MASTER_PASSWORD', 'Ruba2025!!')

# --- إعدادات المجلدات وتخزين الصور ---
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# إعداد السجلات (Logs) لمراقبة الأخطاء في Render.com
logging.basicConfig(level=logging.INFO)

# -------------------------------------------------------
# وظائف مساعدة (Utility Functions)
# -------------------------------------------------------

def get_user_stats(user_id):
    """
    جلب كافة بيانات التاجر الحيوية في استعلام واحد لتقليل الضغط على قاعدة البيانات.
    تعيد: الرصيد، عدد المنتجات، ورابط المتجر (Slug).
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # جلب الرصيد
        cursor.execute("SELECT credits FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        
        # جلب بيانات المتجر
        cursor.execute("SELECT id, slug FROM stores WHERE user_id = %s", (user_id,))
        store = cursor.fetchone()
        
        processed_count = 0
        if store:
            cursor.execute("SELECT COUNT(*) as count FROM products WHERE store_id = %s", (store['id'],))
            res = cursor.fetchone()
            processed_count = res['count'] if res else 0
            
        return {
            'credits': user_data['credits'] if user_data else 0,
            'processed': processed_count,
            'store_slug': store['slug'] if store else None
        }
    except Exception as e:
        logging.error(f"Error in get_user_stats: {e}")
        return {'credits': 0, 'processed': 0, 'store_slug': None}
    finally:
        if conn: conn.close()

# -------------------------------------------------------
# 0. نظام التسجيل والدخول (Auth System)
# -------------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    """إنشاء حساب تاجر جديد بحالة 'pending'"""
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        store_name = request.form.get('store_name')
        # تحويل اسم المتجر لرابط (Slug)
        slug = store_name.lower().strip().replace(" ", "-")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # 1. إضافة المستخدم برصيد ترحيبي 10 صور
            cursor.execute(
                "INSERT INTO users (phone, password_hash, status, credits) VALUES (%s, %s, %s, %s) RETURNING id",
                (phone, generate_password_hash(password), 'pending', 10)
            )
            user_id = cursor.fetchone()['id']
            
            # 2. إنشاء المتجر المرتبط بالمستخدم
            cursor.execute(
                "INSERT INTO stores (user_id, name, slug) VALUES (%s, %s, %s)",
                (user_id, store_name, slug)
            )
            conn.commit()
            flash("تم استلام طلبك بنجاح! سيتم تفعيل الحساب من قبل الإدارة قريباً.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            flash("فشل التسجيل: رقم الهاتف أو اسم المتجر مستخدم بالفعل.", "error")
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """تسجيل دخول التاجر مع التحقق من حالة الحساب (Active/Pending)"""
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash, status FROM users WHERE phone = %s", (phone,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            if user['status'] != 'active':
                flash("حسابك بانتظار تفعيل الإدارة. شكراً لصبرك.", "warning")
                return render_template('login.html')
            
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        else:
            flash("رقم الهاتف أو كلمة المرور غير صحيحة.", "error")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------------------------------------------
# 1. المحرك الذكي (AI Background Removal)
# -------------------------------------------------------

@app.route('/', methods=['GET', 'POST'])
def index():
    """اللوحة الرئيسية: رفع الصور ومعالجتها بالذكاء الاصطناعي"""
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))

    stats = get_user_stats(user_id)

    if request.method == 'POST':
        file = request.files.get('image')
        if not file or file.filename == '':
            flash("يرجى اختيار صورة أولاً", "error")
            return redirect(request.url)
            
        # إنشاء أسماء فريدة للملفات
        unique_id = uuid.uuid4().hex[:8]
        filename = f"orig_{unique_id}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # بدء عملية الذكاء الاصطناعي (rembg)
            with open(filepath, "rb") as f:
                input_data = f.read()
            
            output_data = remove(input_data)
            
            # تحويل النتيجة لصورة PNG شفافة
            img_no_bg = Image.open(io.BytesIO(output_data)).convert("RGBA")
            output_filename = f"processed_{unique_id}.png"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
            img_no_bg.save(output_path, "PNG")
            
            # الانتقال لصفحة المعمل (Result) دون خصم رصيد حتى الآن
            return render_template('result.html', filename=output_filename, stats=stats)
            
        except Exception as e:
            logging.error(f"AI Processing Error: {e}")
            flash("حدث خطأ أثناء معالجة الصورة. يرجى المحاولة مرة أخرى.", "error")
            return redirect(url_for('index'))

    return render_template('index.html', stats=stats)

# -------------------------------------------------------
# 2. إدارة المنتجات وحفظها (Inventory & Store)
# -------------------------------------------------------

@app.route('/save_product', methods=['POST'])
def save_product():
    """حفظ المنتج في المتجر وخصم رصيد (1) من التاجر"""
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. التحقق الدفاعي من الرصيد
    cursor.execute("SELECT credits FROM users WHERE id = %s", (user_id,))
    user_credits = cursor.fetchone()['credits']
    
    if user_credits <= 0:
        conn.close()
        flash("رصيدك غير كافٍ لحفظ هذا المنتج. يرجى التواصل مع الإدارة لشحن الرصيد.", "error")
        return redirect(url_for('index'))

    # 2. استلام بيانات التصميم من الـ Result.html
    name = request.form.get('name', 'منتج جديد')
    price = request.form.get('price', 0)
    image_url = request.form.get('image_url')
    template_style = request.form.get('template_style', 'elegant')
    theme = request.form.get('theme', 'gold')

    # 3. جلب معرف المتجر
    cursor.execute("SELECT id FROM stores WHERE user_id = %s", (user_id,))
    store = cursor.fetchone()

    if store:
        try:
            # حفظ المنتج في قاعدة البيانات
            cursor.execute("""
                INSERT INTO products (store_id, name, price, processed_image_url, template_style, theme)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (store['id'], name, price, image_url, template_style, theme))
            
            # خصم الرصيد رسمياً
            cursor.execute("UPDATE users SET credits = credits - 1 WHERE id = %s", (user_id,))
            
            conn.commit()
            flash("تم حفظ المنتج بنجاح في متجرك!", "success")
            return redirect(url_for('admin'))
        except Exception as e:
            conn.rollback()
            logging.error(f"Save Product Error: {e}")
            flash("حدث خطأ تقني أثناء الحفظ.", "error")
        finally:
            conn.close()

    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    """عرض المخزون وإعدادات المتجر للتاجر"""
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))
    
    stats = get_user_stats(user_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # جلب بيانات المتجر والمنتجات
    cursor.execute("SELECT * FROM stores WHERE user_id = %s", (user_id,))
    store = cursor.fetchone()
    
    products = []
    if store:
        cursor.execute("SELECT * FROM products WHERE store_id = %s ORDER BY id DESC", (store['id'],))
        products = cursor.fetchall()
        
    # التعامل مع طلب التعديل (Edit Mode)
    edit_product = None
    edit_id = request.args.get('edit')
    if edit_id and store:
        cursor.execute("SELECT * FROM products WHERE id = %s AND store_id = %s", (edit_id, store['id']))
        edit_product = cursor.fetchone()
        
    conn.close()
    return render_template('admin.html', products=products, stats=stats, store=store, edit_product=edit_product)

@app.route('/edit_product/<int:id>', methods=['POST'])
def edit_product_route(id):
    """تحديث بيانات منتج موجود مسبقاً"""
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))
    
    name = request.form.get('name')
    price = request.form.get('price')
    description = request.form.get('description')
    theme = request.form.get('theme')
    template_style = request.form.get('template_style')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE products SET name=%s, price=%s, description=%s, theme=%s, template_style=%s
            WHERE id=%s AND store_id = (SELECT id FROM stores WHERE user_id=%s)
        """, (name, price, description, theme, template_style, id, user_id))
        conn.commit()
        flash("تم تحديث بيانات المنتج بنجاح.", "success")
    except Exception as e:
        logging.error(f"Edit Product Error: {e}")
    finally:
        conn.close()
    return redirect(url_for('admin'))

@app.route('/delete_product/<int:id>')
def delete_product_route(id):
    """حذف منتج من المتجر"""
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id=%s AND store_id = (SELECT id FROM stores WHERE user_id=%s)", (id, user_id))
    conn.commit()
    conn.close()
    flash("تم حذف المنتج من المتجر.", "info")
    return redirect(url_for('admin'))

# -------------------------------------------------------
# 3. تحديث الملف الشخصي للمتجر (Store Settings)
# -------------------------------------------------------

@app.route('/update_store', methods=['POST'])
def update_store():
    """تحديث كافة بيانات التواصل الاجتماعي والعنوان للمتجر"""
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))

    # استلام كافة الحقول العشرة المطلوبة في الميثاق
    name = request.form.get('name')
    slug = request.form.get('slug')
    bio = request.form.get('bio')
    display_phone = request.form.get('display_phone')
    whatsapp_phone = request.form.get('whatsapp_phone')
    instagram_handle = request.form.get('instagram_handle')
    tiktok_handle = request.form.get('tiktok_handle')
    facebook_handle = request.form.get('facebook_handle')
    address = request.form.get('address')
    website = request.form.get('website')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE stores SET 
                name=%s, slug=%s, bio=%s, display_phone=%s, whatsapp_phone=%s,
                instagram_handle=%s, tiktok_handle=%s, facebook_handle=%s, 
                address=%s, website=%s
            WHERE user_id=%s
        """, (name, slug, bio, display_phone, whatsapp_phone, 
              instagram_handle, tiktok_handle, facebook_handle, 
              address, website, user_id))
        conn.commit()
        flash("تم حفظ إعدادات المتجر بنجاح.", "success")
    except Exception as e:
        conn.rollback()
        logging.error(f"Update Store Error: {e}")
        flash("حدث خطأ أثناء تحديث الإعدادات. الرابط (Slug) قد يكون مستخدماً.", "error")
    finally:
        conn.close()
    return redirect(url_for('admin'))

# -------------------------------------------------------
# 4. المتجر العام والواجهة الإدارية (Public & Super Admin)
# -------------------------------------------------------

@app.route('/store/<slug>')
def view_store(slug):
    """عرض المتجر العام للزبائن بالثيم الفاخر"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stores WHERE slug = %s", (slug,))
    store = cursor.fetchone()
    
    if not store:
        conn.close()
        return "هذا المتجر غير موجود حالياً.", 404
    
    cursor.execute("SELECT * FROM products WHERE store_id = %s ORDER BY id DESC", (store['id'],))
    products = cursor.fetchall()
    conn.close()
    return render_template('store.html', store=store, products=products)

@app.route('/superadmin')
def super_admin():
    """لوحة التحكم العليا لإدارة التجار وتفعيل الحسابات"""
    if not session.get('is_superadmin'): return redirect(url_for('super_admin_login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # إحصائيات النظام الكلية
    cursor.execute("SELECT COUNT(*) as count FROM users")
    t_users = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM products")
    t_products = cursor.fetchone()['count']
    cursor.execute("SELECT SUM(credits) as sum_c FROM users")
    t_credits = cursor.fetchone()['sum_c'] or 0
    
    # قائمة التجار مع أسماء متاجرهم
    cursor.execute("""
        SELECT users.*, stores.name as store_name 
        FROM users LEFT JOIN stores ON users.id = stores.user_id 
        ORDER BY users.created_at DESC
    """)
    users = cursor.fetchall()
    conn.close()
    
    return render_template('superadmin.html', 
                           stats={'total_users': t_users, 'total_products': t_products, 'total_credits': t_credits}, 
                           users=users)

@app.route('/superadmin/login', methods=['GET', 'POST'])
def super_admin_login():
    """دخول الإدارة العليا بكلمة المرور الرئيسية"""
    if request.method == 'POST':
        if request.form.get('password') == MASTER_PASSWORD:
            session['is_superadmin'] = True
            return redirect(url_for('super_admin'))
    return render_template('login.html', superadmin=True)

@app.route('/superadmin/approve/<int:user_id>')
def approve_user(user_id):
    """تفعيل حساب تاجر جديد"""
    if not session.get('is_superadmin'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = 'active' WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('super_admin'))

@app.route('/superadmin/reject/<int:user_id>')
def reject_user(user_id):
    """حذف طلب اشتراك تاجر"""
    if not session.get('is_superadmin'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('super_admin'))

@app.route('/superadmin/add_credits', methods=['POST'])
def super_admin_add_credits():
    """شحن رصيد إضافي لتاجر محدد"""
    if not session.get('is_superadmin'): return redirect(url_for('login'))
    user_id = request.form.get('user_id')
    amount = int(request.form.get('amount', 0))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET credits = credits + %s WHERE id = %s", (amount, user_id))
    conn.commit()
    conn.close()
    return redirect(url_for('super_admin'))

# --- خدمة ملفات الـ PWA ---
@app.route('/sw.js')
def sw():
    return app.send_static_file('sw.js')

# --- تشغيل التطبيق ---
if __name__ == '__main__':
    # الحصول على المنفذ من بيئة Render أو استخدام 5000 محلياً
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)