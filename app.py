"""
Ramallah Time - Core Engine (v2.0 - English SaaS Edition)
Updated: April 2025 - Full PostgreSQL Version
"""

import os
import io
import uuid
from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from rembg import remove
from PIL import Image
from database import get_db_connection

app = Flask(__name__)

# --- SECURITY CONFIGURATION ---
app.secret_key = os.environ.get('SECRET_KEY', 'rt_secure_dev_key_2025_#99')
MASTER_PASSWORD = os.environ.get('MASTER_PASSWORD', 'Ruba2025!!')

# --- STORAGE CONFIGURATION ---
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# -------------------------------------------------------
# HELPER FUNCTIONS (PostgreSQL Logic)
# -------------------------------------------------------

def get_user_stats(user_id):
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
    
    cursor.close()
    conn.close()
    return {
        'credits': user_data['credits'] if user_data else 0,
        'processed': processed_count,
        'store_slug': store['slug'] if store else None
    }

# -------------------------------------------------------
# 0. REGISTRATION (New Merchants)
# -------------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        store_name = request.form.get('store_name')
        # تحويل اسم المتجر لـ slug (رابط) بسيط
        slug = store_name.lower().replace(" ", "-")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # 1. إنشاء المستخدم بحالة pending (انتظار) ورصيد 10 صور
            cursor.execute(
                "INSERT INTO users (phone, password_hash, status, credits) VALUES (%s, %s, %s, %s) RETURNING id",
                (phone, generate_password_hash(password), 'pending', 10)
            )
            user_id = cursor.fetchone()['id']
            
            # 2. إنشاء المتجر الأولي المرتبط بالمستخدم
            cursor.execute(
                "INSERT INTO stores (user_id, name, slug) VALUES (%s, %s, %s)",
                (user_id, store_name, slug)
            )
            conn.commit()
            return "<h1>✅ Request Sent!</h1><p>Your account is pending approval by admin.</p><a href='/login'>Back to Login</a>"
        except Exception as e:
            conn.rollback()
            return f"<h1>❌ Error</h1><p>Phone number or store name might already exist.</p>"
        finally:
            cursor.close()
            conn.close()
    return render_template('register.html')

# -------------------------------------------------------
# 1. AUTHENTICATION
# -------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor()
        # التعديل هنا: جلب حقل الحالة (status) من قاعدة البيانات
        cursor.execute("SELECT id, password_hash, status FROM users WHERE phone = %s", (phone,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            # التعديل هنا: منع التاجر من الدخول إذا لم تكن حالته active
            if user['status'] != 'active':
                return "<h1>⏳ Account Pending</h1><p>Your account is not yet active. Please wait for admin approval.</p><a href='/login'>Try Again</a>"
            
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        else:
            return "<h1>❌ Invalid phone number or password!</h1>"
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------------------------------------------
# 2. MAIN DASHBOARD (AI Background Removal)
# -------------------------------------------------------

@app.route('/', methods=['GET', 'POST'])
def index():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    stats = get_user_stats(user_id)

    if request.method == 'POST':
        if 'image' not in request.files:
            return redirect(request.url)
        
        file = request.files['image']
        if file.filename == '':
            return redirect(request.url)
        
        if file:
            if stats['credits'] <= 0:
                return "<h1>❌ Insufficient Credits!</h1>"
            
            unique_id = uuid.uuid4().hex[:8]
            filename = f"{unique_id}_{file.filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                with open(filepath, "rb") as f:
                    input_data = f.read()
                
                output_data = remove(input_data)
                img_no_bg = Image.open(io.BytesIO(output_data)).convert("RGBA")
                
                output_filename = f"processed_{unique_id}.png"
                output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
                img_no_bg.save(output_path, "PNG")
                
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET credits = credits - 1 WHERE id = %s", (user_id,))
                conn.commit()
                cursor.close()
                conn.close()
                
                return render_template('result.html',
                                       original=filename,
                                       processed=output_filename,
                                       stats=get_user_stats(user_id))
                
            except Exception as e:
                return f"<h1>System Error: {str(e)}</h1>"

    return render_template('index.html', stats=stats)

# -------------------------------------------------------
# 3. PRODUCT MANAGEMENT
# -------------------------------------------------------

@app.route('/save_product', methods=['POST'])
def save_product():
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))

    name = request.form.get('name', 'New Product')
    price = request.form.get('price', '0')
    description = request.form.get('description', '')
    original_image = request.form.get('original_image')
    processed_image = request.form.get('processed_image')
    template_style = request.form.get('template_style', 'elegant')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, slug FROM stores WHERE user_id = %s", (user_id,))
    store = cursor.fetchone()
    
    if store:
        cursor.execute(
            "INSERT INTO products (store_id, name, description, price, original_image_url, processed_image_url, template_style) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (store['id'], name, description, price, original_image, processed_image, template_style)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin'))
    
    cursor.close()
    conn.close()
    return "<h1>❌ Error: Store not found!</h1>"

@app.route('/admin')
def admin():
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))
    
    stats = get_user_stats(user_id)
    conn = get_db_connection()
    cursor = conn.cursor()

    # جلب بيانات المتجر كاملة لصفحة الإعدادات
    cursor.execute("SELECT * FROM stores WHERE user_id = %s", (user_id,))
    store = cursor.fetchone()
    
    products = []
    if store:
        cursor.execute("SELECT * FROM products WHERE store_id = %s ORDER BY id DESC", (store['id'],))
        products = cursor.fetchall()

    # edit mode
    edit_product = None
    edit_id = request.args.get('edit')
    if edit_id and store:
        cursor.execute("SELECT * FROM products WHERE id = %s AND store_id = %s", (edit_id, store['id']))
        edit_product = cursor.fetchone()

    cursor.close()
    conn.close()
    return render_template('admin.html', products=products, stats=stats, store=store, edit_product=edit_product)

@app.route('/edit_product/<int:id>', methods=['POST'])
def edit_product_route(id):
    if not session.get('user_id'): return redirect(url_for('login'))
    name = request.form.get('name')
    price = request.form.get('price')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET name = %s, price = %s WHERE id = %s", (name, price, id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/delete_product/<int:id>')
def delete_product_route(id):
    if not session.get('user_id'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin'))

# -------------------------------------------------------
# 4. UPDATE STORE SETTINGS (الجديد)
# -------------------------------------------------------

@app.route('/update_store', methods=['POST'])
def update_store():
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))

    name             = request.form.get('name', '').strip()
    bio              = request.form.get('bio', '').strip()
    display_phone    = request.form.get('display_phone', '').strip()
    whatsapp_phone   = request.form.get('whatsapp_phone', '').strip()
    instagram_handle = request.form.get('instagram_handle', '').strip()
    tiktok_handle    = request.form.get('tiktok_handle', '').strip()
    facebook_handle  = request.form.get('facebook_handle', '').strip()
    address          = request.form.get('address', '').strip()
    website          = request.form.get('website', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE stores SET
            name             = %s,
            bio              = %s,
            display_phone    = %s,
            whatsapp_phone   = %s,
            instagram_handle = %s,
            tiktok_handle    = %s,
            facebook_handle  = %s,
            address          = %s,
            website          = %s
        WHERE user_id = %s
    """, (name, bio, display_phone, whatsapp_phone,
          instagram_handle, tiktok_handle, facebook_handle,
          address, website, user_id))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin') + '?saved=1')

# -------------------------------------------------------
# 5. PUBLIC STORE
# -------------------------------------------------------

@app.route('/store/<slug>')
def view_store(slug):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT stores.*, users.phone 
        FROM stores 
        JOIN users ON stores.user_id = users.id 
        WHERE stores.slug = %s
    """, (slug,))
    store = cursor.fetchone()
    
    if not store:
        cursor.close()
        conn.close()
        return "<h1>Store Not Found</h1>", 404
        
    cursor.execute("SELECT * FROM products WHERE store_id = %s ORDER BY id DESC", (store['id'],))
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('store.html', store=store, products=products)

# -------------------------------------------------------
# 6. SUPER ADMIN
# -------------------------------------------------------

@app.route('/superadmin')
def super_admin():
    if not session.get('is_superadmin'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM users")
    total_users = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM products")
    total_products = cursor.fetchone()['count']
    
    cursor.execute("SELECT SUM(credits) as sum_credits FROM users")
    res_credits = cursor.fetchone()
    total_credits = res_credits['sum_credits'] if res_credits['sum_credits'] else 0
    
    cursor.execute("SELECT users.*, stores.name as store_name FROM users LEFT JOIN stores ON users.id = stores.user_id ORDER BY users.created_at DESC")
    users = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('superadmin.html', stats={
        'total_users': total_users,
        'total_products': total_products,
        'total_credits': total_credits
    }, users=users)
@app.route('/superadmin/approve/<int:user_id>')
def approve_user(user_id):
    if not session.get('is_superadmin'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    # تحديث حالة المستخدم إلى active لتمكينه من الدخول
    cursor.execute("UPDATE users SET status = 'active' WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('super_admin'))

@app.route('/superadmin/reject/<int:user_id>')
def reject_user(user_id):
    if not session.get('is_superadmin'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    # حذف المستخدم تماماً في حال رفض الطلب
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('super_admin'))
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)