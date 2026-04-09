"""
Ramallah Time - Core Engine (v3.2 - Production Hotfix)
---------------------------------------------------
Fixes:
1. Added Context Processor for global 'store_slug' access.
2. Fixed 'original_image_url' missing error in save_product.
"""

import os
import io
import uuid
import logging
from flask import Flask, render_template, request, redirect, session, url_for, flash, g, send_from_directory
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from rembg import remove
from PIL import Image
from database import get_db_connection

app = Flask(__name__)

# --- Config ---
app.secret_key = os.environ.get('SECRET_KEY', 'rt_studio_secure_2025_palestine_#99')
MASTER_PASSWORD = os.environ.get('MASTER_PASSWORD', 'Ruba2025!!')
UPLOAD_FOLDER = 'static/uploads'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

logging.basicConfig(level=logging.INFO)

# -------------------------------------------------------
# Context Processor (Global Template Variables)
# -------------------------------------------------------

@app.context_processor
def inject_global_vars():
    """يجعل store_slug متاحاً في جميع القوالب (base.html) تلقائياً"""
    if 'user_id' in session:
        # نستخدم g لتخزين البيانات مؤقتاً ومنع تكرار الاستعلام في نفس الطلب
        if not hasattr(g, 'user_stats_global'):
            g.user_stats_global = get_user_stats(session['user_id'])
        return {'store_slug': g.user_stats_global.get('store_slug')}
    return {'store_slug': None}

# -------------------------------------------------------
# Utility Functions
# -------------------------------------------------------

def get_user_stats(user_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT credits FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        
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
# Auth System
# -------------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        store_name = request.form.get('store_name')
        slug = store_name.lower().strip().replace(" ", "-")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (phone, password_hash, status, credits) VALUES (%s, %s, %s, %s) RETURNING id",
                (phone, generate_password_hash(password), 'pending', 10)
            )
            user_id = cursor.fetchone()['id']
            
            cursor.execute(
                "INSERT INTO stores (user_id, name, slug) VALUES (%s, %s, %s)",
                (user_id, store_name, slug)
            )
            conn.commit()
            flash("تم استلام طلبك بنجاح! سيتم تفعيل الحساب من قبل الإدارة قريباً.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            logging.error(f"Register Error: {e}")
            flash("فشل التسجيل: رقم الهاتف أو اسم المتجر مستخدم بالفعل.", "error")
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
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
# AI Engine
# -------------------------------------------------------

@app.route('/', methods=['GET', 'POST'])
def index():
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))

    stats = get_user_stats(user_id)

    if request.method == 'POST':
        file = request.files.get('image')
        image_url = request.form.get('image_url')
        unique_id = uuid.uuid4().hex[:8]

        # التحقق: هل المصدر رابط أم ملف مرفوع؟
        if image_url and image_url.strip() != '':
            original_filename = f"orig_{unique_id}.png"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
            try:
                response = requests.get(image_url, timeout=10)
                if response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                else:
                    flash("فشل سحب الصورة من الرابط.", "error")
                    return redirect(url_for('index'))
            except:
                flash("رابط غير صالح أو غير متاح.", "error")
                return redirect(url_for('index'))
        elif file and file.filename != '':
            original_filename = f"orig_{unique_id}_{file.filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
            file.save(filepath)
        else:
            flash("يرجى اختيار ملف أو وضع رابط صورة.", "error")
            return redirect(url_for('index'))
        
        try:
            with open(filepath, "rb") as f:
                input_data = f.read()
            
            output_data = remove(input_data)
            
            img_no_bg = Image.open(io.BytesIO(output_data)).convert("RGBA")
            processed_filename = f"processed_{unique_id}.png"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)
            img_no_bg.save(output_path, "PNG")
            
            # إرسال اسم الملف الأصلي والمعالج
            return render_template('result.html', 
                                   filename=processed_filename, 
                                   original_filename=original_filename, 
                                   stats=stats)
            
        except Exception as e:
            logging.error(f"AI Processing Error: {e}")
            flash("حدث خطأ أثناء معالجة الصورة.", "error")
            return redirect(url_for('index'))

    return render_template('index.html', stats=stats)

# -------------------------------------------------------
# Inventory & Store Management
# -------------------------------------------------------

@app.route('/save_product', methods=['POST'])
def save_product():
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT credits FROM users WHERE id = %s", (user_id,))
    user_credits = cursor.fetchone()['credits']
    
    if user_credits <= 0:
        conn.close()
        flash("رصيدك غير كافٍ لحفظ هذا المنتج.", "error")
        return redirect(url_for('index'))

    # استلام البيانات (تمت إضافة original_image_url)
    name = request.form.get('name', 'Product')
    price = request.form.get('price', 0)
    processed_image_url = request.form.get('image_url')
    original_image_url = request.form.get('original_image_url') # الحقل الجديد
    # جلب القسم من الخانة الجديدة (ووضع كلمة 'الكل' كخيار افتراضي إذا تركها فارغة)
    category = request.form.get('category', '').strip() or 'الكل'
    template_style = request.form.get('template_style', 'elegant')
    theme = request.form.get('theme', 'gold')

    cursor.execute("SELECT id FROM stores WHERE user_id = %s", (user_id,))
    store = cursor.fetchone()

    if store:
        try:
            # تحديث الاستعلام ليشمل العمود الجديد
            cursor.execute("""
                INSERT INTO products (store_id, name, price, processed_image_url, original_image_url, template_style, theme, category)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (store['id'], name, price, processed_image_url, original_image_url, template_style, theme, category))
            
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
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))
    
    stats = get_user_stats(user_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM stores WHERE user_id = %s", (user_id,))
    store = cursor.fetchone()
    
    products = []
    if store:
        cursor.execute("SELECT * FROM products WHERE store_id = %s ORDER BY id DESC", (store['id'],))
        products = cursor.fetchall()
        
    edit_product = None
    edit_id = request.args.get('edit')
    if edit_id and store:
        cursor.execute("SELECT * FROM products WHERE id = %s AND store_id = %s", (edit_id, store['id']))
        edit_product = cursor.fetchone()
        
    conn.close()
    return render_template('admin.html', products=products, stats=stats, store=store, edit_product=edit_product)

@app.route('/edit_product/<int:id>', methods=['POST'])
def edit_product_route(id):
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))
    
    name = request.form.get('name')
    price = request.form.get('price')
    description = request.form.get('description')
    theme = request.form.get('theme')
    category = request.form.get('category', '').strip() or 'الكل'
    template_style = request.form.get('template_style')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE products SET name=%s, price=%s, description=%s, theme=%s, template_style=%s, category=%s
            WHERE id=%s AND store_id = (SELECT id FROM stores WHERE user_id=%s)
        """, (name, price, description, theme, template_style, category, id, user_id))
        conn.commit()
        flash("تم تحديث البيانات.", "success")
    except Exception as e:
        logging.error(f"Edit Product Error: {e}")
    finally:
        conn.close()
    return redirect(url_for('admin'))

@app.route('/delete_product/<int:id>')
def delete_product_route(id):
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id=%s AND store_id = (SELECT id FROM stores WHERE user_id=%s)", (id, user_id))
    conn.commit()
    conn.close()
    flash("تم الحذف.", "info")
    return redirect(url_for('admin'))

# -------------------------------------------------------
# Store Settings & Public View
# -------------------------------------------------------

@app.route('/update_store', methods=['POST'])
def update_store():
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))

    name = request.form.get('name')
    # معالجة رفع شعار المتجر (Logo)
    logo_file = request.files.get('logo')
    logo_url = None
    if logo_file and logo_file.filename != '':
        unique_id = uuid.uuid4().hex[:6]
        logo_filename = f"logo_{unique_id}_{logo_file.filename}"
        logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo_filename)
        logo_file.save(logo_path)
        logo_url = logo_filename
    slug = request.form.get('slug', '').strip().replace(" ", "-") # تنظيف الرابط من المسافات
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
        # تحديث البيانات مع إضافة الشعار إذا تم رفعه
        if logo_url:
            cursor.execute("""
                UPDATE stores SET 
                    name=%s, slug=%s, bio=%s, display_phone=%s, whatsapp_phone=%s,
                    instagram_handle=%s, tiktok_handle=%s, facebook_handle=%s, 
                    address=%s, website=%s, logo_url=%s
                WHERE user_id=%s
            """, (name, slug, bio, display_phone, whatsapp_phone, 
                  instagram_handle, tiktok_handle, facebook_handle, 
                  address, website, logo_url, user_id))
        else:
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
        flash("تم تحديث الإعدادات.", "success")
    except Exception as e:
        conn.rollback()
        logging.error(f"Update Store Error: {e}")
        flash("خطأ في التحديث. الرابط قد يكون مستخدماً.", "error")
    finally:
        conn.close()
        
    return redirect(url_for('admin'))
@app.route('/update_login_info', methods=['POST'])
def update_login_info():
    """تعديل رقم الهاتف أو كلمة المرور من قبل صاحب المتجر"""
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))

    new_phone = request.form.get('phone')
    new_password = request.form.get('password')

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # تحديث رقم الهاتف إذا تم إدخاله
        if new_phone:
            cursor.execute("UPDATE users SET phone = %s WHERE id = %s", (new_phone, user_id))
        
        # تحديث كلمة المرور إذا تم إدخالها
        if new_password and new_password.strip() != '':
            hashed_pw = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hashed_pw, user_id))
            
        conn.commit()
        flash("تم تحديث بيانات الدخول بنجاح.", "success")
    except Exception as e:
        conn.rollback()
        flash("خطأ: قد يكون رقم الهاتف مستخدماً من قبل حساب آخر.", "error")
    finally:
        conn.close()
        
    return redirect(url_for('admin', active_tab='settings'))

@app.route('/store/<slug>')
def view_store(slug):
    import urllib.parse
    # فك تشفير الرابط لضمان التعامل الصحيح مع الحروف العربية
    decoded_slug = urllib.parse.unquote(slug)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    # البحث باستخدام الرابط الأصلي أو المشفر لزيادة الدقة
    cursor.execute("SELECT * FROM stores WHERE slug = %s OR slug = %s", (decoded_slug, slug))
    store = cursor.fetchone()
    # تسجيل الزيارة في قاعدة البيانات فور دخول الزبون للمتجر
    if store:
        from database import record_store_visit
        record_store_visit(store['id'])
    
    if not store:
        
        conn.close()
        return "هذا المتجر غير موجود حالياً.", 404
    
    cursor.execute("SELECT * FROM products WHERE store_id = %s ORDER BY id DESC", (store['id'],))
    products = cursor.fetchall()
    # جلب تفاصيل المنتج المطلوب فتحه (للمعاينة في الواتساب)
    open_id = request.args.get('open_product')
    product_to_open = None
    if open_id:
        cursor.execute("SELECT * FROM products WHERE id = %s", (open_id,))
        product_to_open = cursor.fetchone()
    conn.close()
    return render_template('store.html', store=store, products=products, product_to_open=product_to_open)
@app.route('/product/<int:product_id>')
def view_product_direct(product_id):
    """رابط مباشر لمنتج معين لسهولة المشاركة"""
    conn = get_db_connection()
    cursor = conn.cursor()
    # جلب بيانات المنتج والمتجر التابع له
    cursor.execute("""
        SELECT p.*, s.slug as store_slug, s.name as store_name 
        FROM products p 
        JOIN stores s ON p.store_id = s.id 
        WHERE p.id = %s
    """, (product_id,))
    product = cursor.fetchone()
    conn.close()

    if not product:
        return "المنتج غير موجود.", 404
    
    # توجيه الزبون لصفحة المتجر مع إخبار الصفحة بفتح هذا المنتج تلقائياً
    return redirect(url_for('view_store', slug=product['store_slug'], open_product=product_id))

# -------------------------------------------------------
# Super Admin
# -------------------------------------------------------

@app.route('/superadmin')
def super_admin():
    if not session.get('is_superadmin'): return redirect(url_for('super_admin_login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    # جلب إحصائيات الزيارات الجديدة من قاعدة البيانات
    from database import get_visit_stats
    visit_stats = get_visit_stats()
    
    cursor.execute("SELECT COUNT(*) as count FROM users")
    t_users = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM products")
    t_products = cursor.fetchone()['count']
    cursor.execute("SELECT SUM(credits) as sum_c FROM users")
    t_credits = cursor.fetchone()['sum_c'] or 0
    cursor.execute("""
        SELECT users.*, stores.name as store_name, stores.slug as store_slug
        FROM users LEFT JOIN stores ON users.id = stores.user_id 
        ORDER BY users.created_at DESC
    """)
    users = cursor.fetchall()
    conn.close()
    
    return render_template('superadmin.html', 
                           stats={'total_users': t_users, 'total_products': t_products, 'total_credits': t_credits}, 
                           users=users, 
                           visit_stats=visit_stats)

@app.route('/superadmin/login', methods=['GET', 'POST'])
def super_admin_login():
    if request.method == 'POST':
        if request.form.get('password') == MASTER_PASSWORD:
            session['is_superadmin'] = True
            return redirect(url_for('super_admin'))
    return render_template('login.html', superadmin=True)

@app.route('/superadmin/approve/<int:user_id>')
def approve_user(user_id):
    if not session.get('is_superadmin'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = 'active' WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('super_admin'))

@app.route('/superadmin/reject/<int:user_id>')
def reject_user(user_id):
    if not session.get('is_superadmin'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('super_admin'))

@app.route('/superadmin/delete_user/<int:user_id>')
def delete_user_permanent(user_id):
    """حذف حساب التاجر وكافة بياناته نهائياً من قبل السوبر أدمن"""
    if not session.get('is_superadmin'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    # بفضل ON DELETE CASCADE في قاعدة البيانات، سيتم حذف المتجر والمنتجات تلقائياً
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    flash("تم حذف الحساب وكافة بياناته نهائياً.", "info")
    return redirect(url_for('super_admin'))

@app.route('/superadmin/add_credits', methods=['POST'])
def super_admin_add_credits():
    if not session.get('is_superadmin'): return redirect(url_for('login'))
    
    try:
        user_id = int(request.form.get('user_id'))
        # نأخذ الرقم الذي كتبته في الخانة
        amount = int(request.form.get('amount') or 0)
    except:
        flash("خطأ في القيمة المدخلة", "error")
        return redirect(url_for('super_admin'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # هنا "التثبيت": نجعل الرصيد يساوي القيمة التي كتبتها بالضبط
    cursor.execute("UPDATE users SET credits = %s WHERE id = %s", (amount, user_id))
    
    conn.commit()
    conn.close()
    
    # هذه الرسالة ستظهر لك لتؤكد نجاح العملية
    flash(f"تم تحديث رصيد التاجر إلى {amount} صورة بنجاح", "success")
    return redirect(url_for('super_admin'))
@app.route('/sw.js')
def sw():
    return send_from_directory(app.root_path, 'sw.js')

if __name__ == '__main__':
   # تشغيل الموقع مع خاصية (threaded) لزيادة السرعة والتعامل مع أكثر من مستخدم
    port = int(os.environ.get("PORT", 3000))
    app.run(host='0.0.0.0', port=port, threaded=True)