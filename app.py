"""
Ramallah Time - Core Engine (v3.3 - Composition + Lab Fix)
- Fix Design Lab background handling and saving.
- Standardize cutout (PNG 1200x1200 + soft shadow).
- Compose final images (WebP + JPG) on save_product for OG/share/download usage.
- Keep Public Store UI unchanged visually.
"""

import os
import io
import uuid
import logging
import re
import base64
from datetime import datetime, timedelta
from collections import defaultdict

from flask import Flask, render_template, request, redirect, session, url_for, flash, g, send_from_directory
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from rembg import remove
from PIL import Image, ImageOps, ImageDraw, ImageFont, ImageFilter

from database import get_db_connection

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# Local background assets (ensure these files exist under static/assets/bg/)
BG_ASSETS = {
    'marble':  'static/assets/bg/marble.jpg',
    'wood':    'static/assets/bg/wood.jpg',
    'studio':  'static/assets/bg/studio.jpg',
    'nature':  'static/assets/bg/nature.jpg',
    'palace':  'static/assets/bg/palace.jpg',
    'floral':  'static/assets/bg/floral.jpg',
    'stars':   'static/assets/bg/stars.jpg'
}

# Theme colors (for gradient fallback if no background selected)
THEME_COLORS = {
    'gold':     ((242, 153, 74), (242, 201, 76)),
    'black':    ((15, 32, 39),   (32, 58, 67)),
    'pastel':   ((102, 126, 234), (118, 75, 162)),
    'spring':   ((17, 153, 142), (56, 239, 125)),
    'fire':     ((255, 81, 47),  (221, 36, 118)),
    'ocean':    ((33, 147, 176), (109, 213, 237)),
    'royal':    ((79, 70, 229),  (124, 58, 237)),
    'midnight': ((15, 23, 42),   (51, 65, 85)),
    'earth':    ((63, 98, 18),   (113, 63, 18)),
    'vibrant':  ((244, 63, 94),  (251, 146, 60)),
}

# Rate limiting per user per hour
RATE_LIMIT_PER_HOUR = 50
_rate_tracker = defaultdict(list)

def check_rate_limit(user_id):
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=1)
    _rate_tracker[user_id] = [t for t in _rate_tracker[user_id] if t > cutoff]
    if len(_rate_tracker[user_id]) >= RATE_LIMIT_PER_HOUR:
        return False
    _rate_tracker[user_id].append(now)
    return True

def remove_bg_openai(filepath):
    """Try OpenAI background removal. Returns bytes or None."""
    try:
        with open(filepath, 'rb') as f:
            img_bytes = f.read()

        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        w, h = img.size
        mask = Image.new("RGBA", (w, h), (255, 255, 255, 255))

        img_buf = io.BytesIO()
        img.save(img_buf, format='PNG')
        img_buf.seek(0)

        mask_buf = io.BytesIO()
        mask.save(mask_buf, format='PNG')
        mask_buf.seek(0)

        response = requests.post(
            "https://api.openai.com/v1/images/edits",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={
                "image": ("image.png", img_buf, "image/png"),
                "mask": ("mask.png", mask_buf, "image/png"),
            },
            data={
                "model": "dall-e-2",
                "prompt": "Remove the background completely, keep only the product on a transparent background",
                "n": "1",
                "size": "1024x1024",
                "response_format": "b64_json"
            },
            timeout=60
        )
        if response.status_code == 200:
            b64 = response.json()['data'][0]['b64_json']
            return base64.b64decode(b64)
        logging.error(f"OpenAI API Error: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        logging.error(f"OpenAI remove_bg exception: {e}")
        return None

def remove_bg_with_fallback(filepath):
    """OpenAI (if key) -> rembg fallback."""
    if OPENAI_API_KEY:
        logging.info("Trying OpenAI background removal...")
        result = remove_bg_openai(filepath)
        if result:
            logging.info("✅ OpenAI success")
            return result, 'openai'
        logging.warning("⚠️ OpenAI failed, falling back to rembg")
    logging.info("Using rembg fallback...")
    with open(filepath, 'rb') as f:
        input_data = f.read()
    output_data = remove(input_data)
    return output_data, 'rembg'

def exif_transpose_inplace(image_path):
    """Fix EXIF orientation in-place if present."""
    try:
        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)
        img.save(image_path)
    except Exception as e:
        logging.warning(f"EXIF transpose warning: {e}")

def standardize_cutout(png_bytes, out_path, size=1200):
    """
    Standardize cutout PNG:
    - RGBA, fit within 1200x1200
    - Centered on transparent canvas
    - Soft shadow underneath (from alpha)
    """
    try:
        img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        w, h = img.size
        scale = min(size / w, size / h, 1.0)
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)

        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        px = (size - new_w) // 2
        py = (size - new_h) // 2

        # soft shadow from alpha
        try:
            alpha = img.split()[-1]
            shadow = Image.new("RGBA", img.size, (0, 0, 0, 190))
            shadow.putalpha(alpha)
            shadow = shadow.filter(ImageFilter.GaussianBlur(18))
            canvas.paste(shadow, (px, py + 14), shadow)
        except Exception as e:
            logging.warning(f"Shadow creation warning: {e}")

        canvas.paste(img, (px, py), img)
        canvas.save(out_path, "PNG")
    except Exception as e:
        logging.error(f"standardize_cutout error: {e}")
        with open(out_path, 'wb') as f:
            f.write(png_bytes)

def make_vertical_gradient(size, c1, c2):
    """Create vertical gradient image."""
    w, h = size
    base = Image.new('RGB', (w, h), c1)
    top = Image.new('RGB', (w, h), c2)
    mask = Image.linear_gradient("L").resize((w, h))
    return Image.composite(top, base, mask)

def load_background(canvas_size, background_key, theme):
    """Return background Image (RGB) according to key or theme gradient."""
    if background_key and background_key.lower() != 'none':
        path = BG_ASSETS.get(background_key.lower())
        if path and os.path.exists(path):
            bg = Image.open(path).convert("RGB")
            return bg.resize(canvas_size, Image.LANCZOS)
    c1, c2 = THEME_COLORS.get(theme.lower(), ((245, 245, 245), (230, 230, 230)))
    return make_vertical_gradient(canvas_size, c1, c2)

def draw_text_center(draw, text, center_xy, font, fill, anchor="mm"):
    draw.text(center_xy, text, font=font, fill=fill, anchor=anchor)

def compose_final(cutout_path, name, price, theme, style, background_key, out_basepath):
    """
    Compose final marketing image (1200x1200):
    - background (asset or theme gradient)
    - cutout with shadow (already baked into cutout)
    - style overlays (title/price)
    Saves WebP and JPG. Returns filename (webp).
    """
    CANVAS = (1200, 1200)
    try:
        bg = load_background(CANVAS, background_key, theme).copy()
        cutout = Image.open(cutout_path).convert("RGBA")  # cutout already 1200x1200

        composed = Image.new("RGBA", CANVAS)
        composed.paste(bg, (0, 0))
        composed.paste(cutout, (0, 0), cutout)

        draw = ImageDraw.Draw(composed)
        # Fonts (fallback to default if TTF not provided)
        try:
            font_title = ImageFont.truetype("static/assets/fonts/Inter-SemiBold.ttf", 60)
            font_price = ImageFont.truetype("static/assets/fonts/Inter-Bold.ttf", 52)
            font_bar = ImageFont.truetype("static/assets/fonts/Inter-SemiBold.ttf", 40)
        except:
            font_title = ImageFont.load_default()
            font_price = ImageFont.load_default()
            font_bar = ImageFont.load_default()

        name_text = name.strip() if (name and name.strip()) else "Product Name"
        price_text = f"₪ {price}" if str(price).strip() else "₪ 0.00"

        white = (255, 255, 255, 255)
        navy = (26, 34, 56, 255)
        glass_bg = (255, 255, 255, 130)

        style = (style or 'elegant').lower()
        if style == 'modern':
            # name pill (top-right)
            name_box = Image.new("RGBA", (900, 110), (255, 255, 255, 220))
            composed.alpha_composite(name_box, (1200 - 120 - 900, 60))
            draw.text((1200 - 120 - 900 + 28, 60 + 30), name_text[:42], font=font_title, fill=navy)
            # price pill (bottom-left)
            price_box = Image.new("RGBA", (360, 90), navy)
            composed.alpha_composite(price_box, (60, 1200 - 60 - 90))
            draw.text((60 + 24, 1200 - 60 - 90 + 22), price_text, font=font_price, fill=white)
        elif style == 'minimal':
            bar_h = 140
            glass = Image.new("RGBA", (1200, bar_h), glass_bg)
            composed.alpha_composite(glass, (0, 1200 - bar_h))
            draw.text((48, 1200 - bar_h + 48), name_text[:36], font=font_bar, fill=white)
            w = draw.textlength(price_text, font=font_bar)
            draw.text((1200 - 48 - w, 1200 - bar_h + 48), price_text, font=font_bar, fill=white)
        elif style == 'glass':
            box_w, box_h = 900, 180
            glass = Image.new("RGBA", (box_w, box_h), glass_bg)
            x = (1200 - box_w)//2
            y = 1200 - 60 - box_h
            composed.alpha_composite(glass, (x, y))
            draw_text_center(draw, name_text[:40], (1200//2, y + 60), font_title, navy)
            draw_text_center(draw, price_text, (1200//2, y + 130), font_price, navy)
        elif style == 'bold':
            panel = Image.new("RGBA", (380, 1200), (0, 0, 0, 80))
            composed.alpha_composite(panel, (1200 - 380, 0))
            draw.text((1200 - 350, 120), name_text[:26], font=font_title, fill=white)
            draw.text((1200 - 350, 200), price_text, font=font_price, fill=white)
        else:
            # elegant/default
            draw_text_center(draw, name_text[:34], (600, 880), font_title, white)
            draw.line([(560, 930), (640, 930)], fill=white, width=4)
            draw_text_center(draw, price_text, (600, 980), font_price, white)

        # Save outputs
        out_webp = f"{out_basepath}.webp"
        out_jpg = f"{out_basepath}.jpg"
        composed_rgb = composed.convert("RGB")
        composed_rgb.save(out_webp, "WEBP", quality=90)
        composed_rgb.save(out_jpg, "JPEG", quality=90)
        return os.path.basename(out_webp)
    except Exception as e:
        logging.error(f"compose_final error: {e}")
        return None

app = Flask(__name__)

# Config
app.secret_key = os.environ.get('SECRET_KEY', 'rt_studio_secure_2025_palestine_#99')
MASTER_PASSWORD = os.environ.get('MASTER_PASSWORD', 'Ruba2025!!')
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

logging.basicConfig(level=logging.INFO)

# Context Processor
@app.context_processor
def inject_global_vars():
    if 'user_id' in session:
        if not hasattr(g, 'user_stats_global'):
            g.user_stats_global = get_user_stats(session['user_id'])
        return {'store_slug': g.user_stats_global.get('store_slug')}
    return {'store_slug': None}

# Utilities
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

# Auth
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        store_name = request.form.get('store_name')
        raw_slug = store_name.lower().strip().replace(' ', '-')
        slug = re.sub(r'[^a-z0-9؀-ۿ-]', '', raw_slug) or 'store'[:30]

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

# AI Engine
@app.route('/', methods=['GET', 'POST'])
def index():
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))

    stats = get_user_stats(user_id)

    if request.method == 'POST':
        file = request.files.get('image')
        image_url = request.form.get('image_url')
        unique_id = uuid.uuid4().hex[:8]

        # Source: URL or uploaded file
        if image_url and image_url.strip() != '':
            original_filename = f"orig_{unique_id}.png"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
            try:
                response = requests.get(image_url, timeout=10)
                if response.status_code == 200 and response.content:
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

        # Fix EXIF orientation
        try:
            exif_transpose_inplace(filepath)
        except:
            pass

        # Credits check
        if stats['credits'] <= 0:
            flash("رصيدك غير كافٍ. تواصل مع الإدارة لشحن رصيدك.", "error")
            return redirect(url_for('index'))

        # Rate limit
        if not check_rate_limit(user_id):
            flash(f"لقد تجاوزت الحد المسموح ({RATE_LIMIT_PER_HOUR} صورة/ساعة). حاول لاحقاً.", "warning")
            return redirect(url_for('index'))

        try:
            output_data, engine_used = remove_bg_with_fallback(filepath)
            logging.info(f"Background removed using: {engine_used}")

            # Standardize cutout size + soft shadow
            processed_filename = f"processed_{unique_id}.png"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)
            standardize_cutout(output_data, output_path, size=1200)

            return render_template(
                'result.html',
                filename=processed_filename,
                original_filename=original_filename,
                stats=get_user_stats(user_id),  # refresh after processing
                engine_used=engine_used
            )
        except Exception as e:
            logging.error(f"AI Processing Error: {e}")
            flash("حدث خطأ أثناء معالجة الصورة. يرجى المحاولة مرة أخرى.", "error")
            return redirect(url_for('index'))

    return render_template('index.html', stats=stats)

# Inventory & Store Management
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

    name = request.form.get('name', 'Product')
    price = request.form.get('price', 0)
    processed_image_url = request.form.get('image_url')  # Must be the cutout PNG
    original_image_url = request.form.get('original_image_url')
    category = request.form.get('category', '').strip() or 'الكل'
    template_style = request.form.get('template_style', 'elegant')
    theme = request.form.get('theme', 'gold')
    background = request.form.get('background', 'none')

    # Compose final image for OG/share
    final_fname = None
    try:
        cutout_path = os.path.join(app.config['UPLOAD_FOLDER'], processed_image_url)
        base_out = os.path.join(app.config['UPLOAD_FOLDER'], f"final_{uuid.uuid4().hex[:8]}")
        final_webp_name = compose_final(
            cutout_path=cutout_path,
            name=name,
            price=price,
            theme=theme,
            style=template_style,
            background_key=background,
            out_basepath=base_out
        )
        if final_webp_name:
            final_fname = final_webp_name  # stored under static/uploads/
    except Exception as e:
        logging.error(f"Final composition failed: {e}")

    cursor.execute("SELECT id FROM stores WHERE user_id = %s", (user_id,))
    store = cursor.fetchone()

    if store:
        try:
            cursor.execute("""
                INSERT INTO products (store_id, name, price, processed_image_url, original_image_url, template_style, theme, category, background, final_image_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (store['id'], name, price, processed_image_url, original_image_url, template_style, theme, category, background, final_fname))
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

# Store Settings & Public View
@app.route('/update_store', methods=['POST'])
def update_store():
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))

    name = request.form.get('name')
    logo_file = request.files.get('logo')
    logo_url = None
    if logo_file and logo_file.filename != '':
        unique_id = uuid.uuid4().hex[:6]
        logo_filename = f"logo_{unique_id}_{logo_file.filename}"
        logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo_filename)
        logo_file.save(logo_path)
        logo_url = logo_filename

    raw_slug = request.form.get('slug', '').strip()
    if '/' in raw_slug:
        raw_slug = raw_slug.rstrip('/').split('/')[-1]
    slug = re.sub(r'[^a-z0-9؀-ۿ-]', '', raw_slug.lower().replace(' ', '-'))
    if not slug:
        slug = request.form.get('name', 'store').lower().replace(' ', '-')[:30]

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
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))

    new_phone = request.form.get('phone')
    new_password = request.form.get('password')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if new_phone:
            cursor.execute("UPDATE users SET phone = %s WHERE id = %s", (new_phone, user_id))
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
    decoded_slug = urllib.parse.unquote(slug)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stores WHERE slug = %s OR slug = %s", (decoded_slug, slug))
    store = cursor.fetchone()

    if store:
        from database import record_store_visit
        record_store_visit(store['id'])
    else:
        conn.close()
        return "هذا المتجر غير موجود حالياً.", 404

    cursor.execute("SELECT * FROM products WHERE store_id = %s ORDER BY id DESC", (store['id'],))
    products = cursor.fetchall()

    open_id = request.args.get('open_product')
    product_to_open = None
    if open_id:
        cursor.execute("SELECT * FROM products WHERE id = %s", (open_id,))
        product_to_open = cursor.fetchone()

    conn.close()
    return render_template('store.html', store=store, products=products, product_to_open=product_to_open)

@app.route('/product/<int:product_id>')
def view_product_direct(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
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

    return redirect(url_for('view_store', slug=product['store_slug'], open_product=product_id))

# Super Admin
@app.route('/superadmin')
def super_admin():
    if not session.get('is_superadmin'): return redirect(url_for('super_admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor()
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
    if not session.get('is_superadmin'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
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
        amount = int(request.form.get('amount') or 0)
    except:
        flash("خطأ في القيمة المدخلة", "error")
        return redirect(url_for('super_admin'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET credits = %s WHERE id = %s", (amount, user_id))
    conn.commit()
    conn.close()
    flash(f"تم تحديث رصيد التاجر إلى {amount} صورة بنجاح", "success")
    return redirect(url_for('super_admin'))

@app.route('/sw.js')
def sw():
    return send_from_directory(app.root_path, 'sw.js')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 3000))
    app.run(host='0.0.0.0', port=port, threaded=True)