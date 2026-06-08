"""
Ramallah Time - Core Engine (v3.3 - Composition + Lab Fix)
- Fix Design Lab background handling and saving.
- Standardize cutout (PNG 1200x1200 + soft shadow).
- Compose final images (WebP + JPG) on save_product for OG/share/download usage.
- Keep Public Store UI unchanged visually.

Added (Store Commerce v1):
- SKU auto-generation per store (PREFIX-SEQ).
- Optional inventory per store (no quantities shown to shoppers; only "غير متوفر" at 0).
- Cart-to-WhatsApp flow: build text-only message with SKU; deduct stock only on merchant confirm.
- Simple analytics beacon: page_view/product_view/add_to_cart/whatsapp_sent.
- Admin: list orders (sent/confirmed/canceled) + confirm/cancel endpoints.
"""

import os
import io
import uuid
import logging
import re
import base64
import hashlib
import urllib.parse
from datetime import datetime, timedelta
from collections import defaultdict
from decimal import Decimal
from xml.sax.saxutils import escape

from flask import Flask, render_template, request, redirect, session, url_for, flash, g, send_from_directory, send_file, jsonify
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from rembg import remove
from PIL import Image, ImageOps, ImageDraw, ImageFont, ImageFilter

from database import get_db_connection

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
REMOVEBG_API_KEY = os.environ.get('REMOVEBG_API_KEY', '')

# Local background assets (ensure these files exist under static/assets/bg/)
BG_ASSETS = {
    'marble':  'static/assets/bg/marble.jpg',
    'wood':    'static/assets/bg/wood.jpg',
    'studio':  'static/assets/bg/studio.jpg',
    'nature':  'static/assets/bg/nature.jpg',
    'palace':  'static/assets/bg/palace.jpg',
    'floral':  'static/assets/bg/floral.jpg',
    'stars':   'static/assets/bg/stars.jpg',
    'shelf_minimal':   'static/assets/bg/lifestyle_bg_01_shelf_minimal.png',
    'window_light':    'static/assets/bg/lifestyle_bg_02_window_light.png',
    'dark_elegant':    'static/assets/bg/lifestyle_bg_03_dark_elegant.png',
    'beige_shadow':    'static/assets/bg/lifestyle_bg_04_beige_shadow.png',
    'cabinet_frames':  'static/assets/bg/lifestyle_bg_05_cabinet_frames.png',
    'white_shelf':     'static/assets/bg/lifestyle_bg_06_white_shelf_modern.png',
    'sea_window':      'static/assets/bg/lifestyle_bg_07_sea_window.png',
    'tropical_beige':  'static/assets/bg/lifestyle_bg_08_tropical_beige.png',
    'desert_sand':     'static/assets/bg/lifestyle_bg_09_desert_sand.png',
    'curtain_shadow':  'static/assets/bg/lifestyle_bg_10_curtain_shadow.png',
    'velvet_pink':     'static/assets/bg/lifestyle_bg_11_velvet_pink.png',
    'studio_gray':     'static/assets/bg/lifestyle_bg_12_studio_gray.png',
    'golden_arch':     'static/assets/bg/lifestyle_bg_13_golden_arch.png',
    # ── خلفيات فاخرة للساعات والإكسسوار ──
    'dark_concrete':   'static/assets/bg/dark_concrete.jpg',
    'black_marble':    'static/assets/bg/black_marble.jpg',
    'dark_slate':      'static/assets/bg/dark_slate.jpg',
    'grey_marble':     'static/assets/bg/grey_marble.jpg',
    'carbon_wave':     'static/assets/bg/carbon_wave.jpg',
    'dark_gold_metal': 'static/assets/bg/dark_gold_metal.jpg',
    'velvet_teal':     'static/assets/bg/velvet_teal.jpg',
    'velvet_red':      'static/assets/bg/velvet_red.jpg',
    'navy_silk':       'static/assets/bg/navy_silk.jpg',
    'brushed_silver':  'static/assets/bg/brushed_silver.jpg',
    'rose_blur':       'static/assets/bg/rose_blur.jpg',
}

STORE_BACKGROUNDS = [
    {'key': 'none', 'label': 'بدون خلفية', 'file': None},
    {'key': 'navy_silk', 'label': 'حرير كحلي', 'file': 'navy_silk.jpg'},
    {'key': 'dark_concrete', 'label': 'خرسانة داكنة', 'file': 'dark_concrete.jpg'},
    {'key': 'velvet_teal', 'label': 'مخمل زمردي', 'file': 'velvet_teal.jpg'},
]
STORE_BACKGROUND_FILES = {item['key']: item['file'] for item in STORE_BACKGROUNDS}

def normalize_store_background(value):
    value = (value or 'none').strip()
    return value if value in STORE_BACKGROUND_FILES else 'none'

def get_store_background_url(value):
    filename = STORE_BACKGROUND_FILES.get(normalize_store_background(value))
    return f"/static/assets/bg/{filename}" if filename else None

# Theme colors
THEME_COLORS = {
    'gold':        ((242, 153, 74),  (242, 201, 76)),
    'black':       ((15, 32, 39),    (32, 58, 67)),
    'pastel':      ((102, 126, 234), (118, 75, 162)),
    'spring':      ((17, 153, 142),  (56, 239, 125)),
    'fire':        ((255, 81, 47),   (221, 36, 118)),
    'ocean':       ((33, 147, 176),  (109, 213, 237)),
    'royal':       ((79, 70, 229),   (124, 58, 237)),
    'midnight':    ((15, 23, 42),    (51, 65, 85)),
    'earth':       ((63, 98, 18),    (113, 63, 18)),
    'vibrant':     ((244, 63, 94),   (251, 146, 60)),
    'smoke':       ((20, 20, 30),    (60, 50, 80)),
    'luxury':      ((10, 10, 10),    (40, 30, 10)),
    'rose_gold':   ((183, 110, 121), (212, 175, 55)),
    'pearl':       ((245, 245, 245), (210, 210, 210)),
    'royal_gold':  ((10, 10, 10),    (212, 175, 55)),
    'silver':      ((180, 180, 195), (220, 220, 235)),
    'soft_gray':   ((200, 200, 205), (240, 240, 245)),
    'cream':       ((245, 235, 220), (255, 250, 240)),
    'blush':       ((255, 182, 193), (255, 218, 224)),
    'camel':       ((193, 154, 107), (139, 90, 43)),
    'chocolate':   ((60, 30, 10),    (120, 60, 20)),
    'beige':       ((225, 205, 180), (245, 230, 210)),
    'carbon':      ((20, 20, 25),    (50, 50, 60)),
    'gunmetal':    ((50, 55, 60),    (100, 105, 110)),
    'champagne':   ((212, 175, 55),  (245, 220, 130)),
    'tech_black':  ((5, 5, 10),      (30, 30, 40)),
    'space_gray':  ((80, 85, 90),    (140, 145, 150)),
    'clean_white': ((240, 240, 245), (255, 255, 255)),
}

CATEGORY_PRESETS = {
    'perfume':  {'themes': ['luxury','smoke','rose_gold','black','gold'],       'glow': True,  'reflection': True,  'backgrounds': ['velvet_red','velvet_teal','dark_gold_metal','black_marble','rose_blur']},
    'jewelry':  {'themes': ['pearl','royal_gold','silver','midnight','gold'],   'glow': True,  'reflection': True,  'backgrounds': ['velvet_teal','velvet_red','black_marble','rose_blur','brushed_silver','dark_gold_metal']},
    'clothes':  {'themes': ['soft_gray','cream','blush','pastel','spring'],     'glow': False, 'reflection': False, 'backgrounds': ['grey_marble','brushed_silver','rose_blur','navy_silk']},
    'bags':     {'themes': ['camel','chocolate','beige','earth','midnight'],    'glow': False, 'reflection': False, 'backgrounds': ['dark_concrete','dark_slate','black_marble','navy_silk']},
    'watches':  {'themes': ['carbon','gunmetal','champagne','black','silver'],  'glow': True,  'reflection': True,  'backgrounds': ['carbon_wave','dark_gold_metal','black_marble','dark_concrete','dark_slate','grey_marble','navy_silk','brushed_silver']},
    'mobiles':  {'themes': ['tech_black','space_gray','clean_white','midnight'],'glow': True,  'reflection': False, 'backgrounds': ['carbon_wave','dark_concrete','dark_slate','navy_silk']},
    'other':    {'themes': ['gold','black','midnight','ocean','royal'],         'glow': False, 'reflection': False, 'backgrounds': ['dark_concrete','black_marble','grey_marble','navy_silk']},
}

# Rate limiting per user per hour
RATE_LIMIT_PER_HOUR = 50
_rate_tracker = defaultdict(list)

def clean_phone_number(prefix, phone):
    """تنظيف ذكي: يمنع تكرار مفتاح الدولة ويحذف الرموز"""
    if not phone:
        return None
    
    # 1. تنظيف الرقم والمفتاح من أي رموز (+ - _ مسافات)
    phone_digits = re.sub(r'\D', '', str(phone))
    prefix_digits = re.sub(r'\D', '', str(prefix))
    
    # 2. إذا كان التاجر قد كتب المفتاح أصلاً داخل الخانة، نحذفه لكي لا يتكرر
    if phone_digits.startswith(prefix_digits):
        phone_digits = phone_digits[len(prefix_digits):]
    
    # 3. حذف أي أصفار زائدة من بداية الرقم المتبقي (مثل 059 تصبح 59)
    phone_digits = phone_digits.lstrip('0')
    
    # 4. الدمج النهائي الصحيح
    return f"{prefix_digits}{phone_digits}"

def check_rate_limit(user_id):
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=1)
    _rate_tracker[user_id] = [t for t in _rate_tracker[user_id] if t > cutoff]
    if len(_rate_tracker[user_id]) >= RATE_LIMIT_PER_HOUR:
        return False
    _rate_tracker[user_id].append(now)
    return True

def remove_bg_removebg(filepath):
    """Remove background using remove.bg API. Returns bytes or None."""
    try:
        with open(filepath, 'rb') as f:
            img_bytes = f.read()
        response = requests.post(
            "https://api.remove.bg/v1.0/removebg",
            headers={"X-Api-Key": REMOVEBG_API_KEY},
            files={"image_file": ("image.png", img_bytes, "image/png")},
            data={"size": "auto"},
            timeout=60
        )
        if response.status_code == 200:
            logging.info("✅ remove.bg success")
            return response.content
        logging.error(f"remove.bg API Error: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        logging.error(f"remove.bg exception: {e}")
        return None

def remove_bg_with_fallback(filepath):
    """remove.bg (if key) -> rembg fallback."""
    if REMOVEBG_API_KEY:
        logging.info("Trying remove.bg API...")
        result = remove_bg_removebg(filepath)
        if result:
            return result, 'remove.bg'
        logging.warning("⚠️ remove.bg failed, falling back to rembg")
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
    - RGBA, crop transparent borders first (tight bbox)
    - Scale to fill 88% of canvas (always upscale/downscale)
    - Centered on transparent canvas
    - Soft shadow underneath (from alpha)
    """
    try:
        img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")

        # ── 1. Crop transparent borders للحصول على المنتج بالضبط ──
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)

        w, h = img.size

        # ── 2. المنتج يملأ 88% من الإطار دائماً (يكبر ويصغر) ──
        target = int(size * 0.88)
        scale = min(target / w, target / h)
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)

        # ── 3. توسيط دقيق على Canvas شفاف ──
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        px = (size - new_w) // 2
        py = (size - new_h) // 2

        # ── 4. ظل ناعم من الـ alpha ──
        try:
            alpha = img.split()[-1]
            shadow = Image.new("RGBA", img.size, (0, 0, 0, 180))
            shadow.putalpha(alpha)
            shadow = shadow.filter(ImageFilter.GaussianBlur(22))
            canvas.paste(shadow, (px + 8, py + 18), shadow)
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
    """Return background Image (RGB) according to key or theme gradient.
    Asset backgrounds are blurred so the product remains the hero."""
    if background_key and background_key.lower() != 'none':
        path = BG_ASSETS.get(background_key.lower())
        if path and os.path.exists(path):
            bg = Image.open(path).convert("RGB")
            bg = bg.resize(canvas_size, Image.LANCZOS)
            # ── ضبابية خفيفة: الخلفية تخدم المنتج لا تنافسه ──
            bg = bg.filter(ImageFilter.GaussianBlur(radius=6))
            # ── تعتيم خفيف لزيادة التباين مع المنتج ──
            darkener = Image.new("RGB", canvas_size, (0, 0, 0))
            bg = Image.blend(bg, darkener, alpha=0.18)
            return bg
    c1, c2 = THEME_COLORS.get(theme.lower(), ((245, 245, 245), (230, 230, 230)))
    return make_vertical_gradient(canvas_size, c1, c2)

def draw_text_center(draw, text, center_xy, font, fill, anchor="mm"):
    draw.text(center_xy, text, font=font, fill=fill, anchor=anchor)

def remove_white_bg(img, threshold=240):
    img = img.convert("RGBA")
    data = img.getdata()
    new_data = [(r, g, b, 0) if r >= threshold and g >= threshold and b >= threshold else (r, g, b, a) for r, g, b, a in data]
    img.putdata(new_data)
    return img

def add_glow(composed, cutout, position=(0, 0)):
    try:
        alpha = cutout.split()[-1]
        glow = Image.new("RGBA", cutout.size, (255, 220, 120, 60))
        glow.putalpha(alpha)
        glow_blur = glow.filter(ImageFilter.GaussianBlur(40))
        composed.alpha_composite(glow_blur, position)
    except Exception as e:
        logging.warning(f"Glow warning: {e}")

def add_reflection(composed, cutout, position=(0, 0), canvas_size=(1200, 1200)):
    try:
        cx, cy = position
        flipped = cutout.transpose(Image.FLIP_TOP_BOTTOM)
        fade = Image.new("L", flipped.size, 0)
        fade_draw = ImageDraw.Draw(fade)
        for y in range(min(flipped.size[1], 200)):
            fade_draw.line([(0, y), (flipped.size[0], y)], fill=int(80 * (1 - y / 200)))
        flipped.putalpha(fade)
        ref_y = cy + cutout.size[1] - 60
        if ref_y < canvas_size[1]:
            composed.alpha_composite(flipped, (cx, ref_y))
    except Exception as e:
        logging.warning(f"Reflection warning: {e}")

def compose_final(cutout_path, name, price, theme, style, background_key, out_basepath,
                  pos_x=None, pos_y=None, enable_glow=False, enable_reflection=False,
                  category='other', zoom=92):
    """
    Compose final marketing image (1200x1200):
    - background (asset or theme gradient)
    - cutout auto-fitted to fill frame naturally (crop transparent borders)
    - glow + reflection effects
    - draggable position
    Saves WebP and JPG. Returns filename (webp).
    """
    CANVAS = (1200, 1200)
    try:
        bg = load_background(CANVAS, background_key, theme).copy()

        # ── تحميل الـ cutout مع crop للحدود الشفافة ──
        cutout_raw = Image.open(cutout_path).convert("RGBA")
        bbox = cutout_raw.getbbox()
        if bbox:
            cutout_raw = cutout_raw.crop(bbox)

        cw, ch = cutout_raw.size
        zoom_factor = max(0.3, min(1.5, (zoom or 92) / 100))
        max_dim = int(CANVAS[0] * zoom_factor)
        scale = min(max_dim / cw, max_dim / ch)
        new_w, new_h = int(cw * scale), int(ch * scale)
        cutout_resized = cutout_raw.resize((new_w, new_h), Image.LANCZOS)

        # Center the cutout on canvas
        default_x = (CANVAS[0] - new_w) // 2
        default_y = (CANVAS[1] - new_h) // 2

        # Apply drag offset
        px = default_x + (int(pos_x) if pos_x else 0)
        py = default_y + (int(pos_y) if pos_y else 0)
        px = max(-new_w // 2, min(CANVAS[0] - new_w // 2, px))
        py = max(-new_h // 2, min(CANVAS[1] - new_h // 2, py))

        # Build full canvas cutout for effects
        cutout = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        cutout.paste(cutout_resized, (px, py), cutout_resized)

        composed = Image.new("RGBA", CANVAS)
        composed.paste(bg, (0, 0))

        if enable_glow:
            add_glow(composed, cutout, position=(0, 0))
        if enable_reflection:
            add_reflection(composed, cutout, position=(0, 0), canvas_size=CANVAS)

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
        price_str = str(price).strip()
        price_text = f"₪ {price_str}" if price_str else "₪ 0.00"

        white = (255, 255, 255, 255)
        navy = (26, 34, 56, 255)
        glass_bg = (255, 255, 255, 130)

        # Helper: draw text with soft shadow for readability on any background
        def draw_text_shadow(draw, text, xy, font, fill, shadow_color=(0,0,0,160), offset=3):
            draw.text((xy[0]+offset, xy[1]+offset), text, font=font, fill=shadow_color, anchor="mm")
            draw.text(xy, text, font=font, fill=fill, anchor="mm")

        style = (style or 'elegant').lower()
        if style == 'modern':
            # Name top-right, price bottom-left — no boxes, just text with shadow
            draw.text((80, 70), name_text[:36], font=font_title, fill=white)
            draw.text((84, 74), name_text[:36], font=font_title, fill=(0,0,0,100))  # shadow
            pw = draw.textlength(price_text, font=font_price)
            draw.text((1200 - 80 - pw + 3, 1200 - 90 + 3), price_text, font=font_price, fill=(0,0,0,100))
            draw.text((1200 - 80 - pw, 1200 - 90), price_text, font=font_price, fill=white)
        elif style == 'minimal':
            # Name left, price right — bottom area, text only
            draw.text((51, 1200 - 91), name_text[:32], font=font_bar, fill=(0,0,0,100))
            draw.text((48, 1200 - 94), name_text[:32], font=font_bar, fill=white)
            pw = draw.textlength(price_text, font=font_bar)
            draw.text((1200 - 48 - pw + 2, 1200 - 91), price_text, font=font_bar, fill=(0,0,0,100))
            draw.text((1200 - 48 - pw, 1200 - 94), price_text, font=font_bar, fill=white)
        elif style == 'glass':
            # Centered bottom — text only with shadow
            draw_text_shadow(draw, name_text[:36], (600, 940), font_title, white)
            draw_text_shadow(draw, price_text, (600, 1020), font_price, white)
        elif style == 'bold':
            # Right side vertical — text only
            draw.text((1200 - 360 + 3, 123), name_text[:22], font=font_title, fill=(0,0,0,120))
            draw.text((1200 - 360, 120), name_text[:22], font=font_title, fill=white)
            draw.text((1200 - 360 + 3, 203), price_text, font=font_price, fill=(0,0,0,120))
            draw.text((1200 - 360, 200), price_text, font=font_price, fill=white)
        else:
            # elegant/default — centered bottom with divider line
            draw_text_shadow(draw, name_text[:34], (600, 880), font_title, white)
            draw.line([(560, 930), (640, 930)], fill=(255,255,255,180), width=3)
            draw_text_shadow(draw, price_text, (600, 980), font_price, white)

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

BOT_USER_AGENT_PATTERN = re.compile(
    r'bot|crawler|spider|slurp|bingpreview|facebookexternalhit|'
    r'whatsapp|telegrambot|discordbot|linkedinbot|preview',
    re.IGNORECASE
)


def get_public_visitor_key(store):
    """Return an anonymous stable browser key, or None for excluded traffic."""
    user_agent = request.headers.get('User-Agent', '')
    if not user_agent or BOT_USER_AGENT_PATTERN.search(user_agent):
        return None

    if session.get('is_superadmin'):
        return None

    logged_in_user_id = session.get('user_id')
    if logged_in_user_id and logged_in_user_id == store.get('user_id'):
        return None

    visitor_id = session.get('_public_visitor_id')
    if not visitor_id:
        visitor_id = uuid.uuid4().hex
        session['_public_visitor_id'] = visitor_id

    digest_source = f"{app.secret_key}:{visitor_id}".encode('utf-8')
    return hashlib.sha256(digest_source).hexdigest()
MASTER_PASSWORD = os.environ.get('MASTER_PASSWORD', 'Ruba2025!!')
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Migration: product_variants + store appearance columns
try:
    _mconn = get_db_connection()
    _mcur = _mconn.cursor()
    _mcur.execute("""
        CREATE TABLE IF NOT EXISTS product_variants (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            price NUMERIC(10,2) NOT NULL,
            image_url TEXT,
            description TEXT,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    _mcur.execute("ALTER TABLE product_variants ADD COLUMN IF NOT EXISTS description TEXT")
    _mcur.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS store_theme TEXT DEFAULT 'gold'")
    _mcur.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS store_background TEXT DEFAULT 'none'")
    _mconn.commit()
    _mconn.close()
except Exception as _me:
    logging.warning(f"Migration warning: {_me}")

logging.basicConfig(level=logging.INFO)

# =========================
# Helpers: Store/Products
# =========================
def get_store_by_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM stores WHERE user_id = %s", (user_id,))
    store = cur.fetchone()
    conn.close()
    return store

def get_store_by_id(store_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM stores WHERE id = %s", (store_id,))
    store = cur.fetchone()
    conn.close()
    return store

def slug_prefix(slug):
    s = re.sub(r'[^A-Za-z]', '', (slug or '')).upper()
    return (s[:3] or 'STO')

def generate_sku(conn, cur, store_id):
    """
    Generate SKU inside a single DB transaction:
    - Lock store row FOR UPDATE
    - Read slug + next_sku_seq
    - Build PREFIX-SEQ
    - Increment next_sku_seq
    """
    cur.execute("SELECT slug, next_sku_seq FROM stores WHERE id = %s FOR UPDATE", (store_id,))
    row = cur.fetchone()
    if not row:
        raise Exception("Store not found for SKU generation")
    prefix = slug_prefix(row['slug'])
    seq = row['next_sku_seq'] or 1001
    sku = f"{prefix}-{seq}"
    cur.execute("UPDATE stores SET next_sku_seq = %s WHERE id = %s", (seq + 1, store_id))
    return sku

def is_available(store, product):
    if not product.get('active', True):
        return False
    inv = bool(store.get('inventory_enabled'))
    if not inv:
        return True
    qty = product.get('stock_qty', 0) or 0
    return qty > 0

def to_number(n):
    if n is None:
        return 0.0
    if isinstance(n, Decimal):
        return float(n)
    try:
        return float(n)
    except:
        return 0.0

def format_money(v):
    v = to_number(v)
    return str(int(v)) if abs(v - int(v)) < 1e-9 else f"{v:.2f}"

def build_wa_text(store, lines, subtotal, customer):
    """
    Build WhatsApp message text only. No links inside the text.
    lines: list of dict(name, sku, qty, line_total)
    """
    dt_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    parts = []
    parts.append(f"🛍️ طلب جديد — {store['name']}")
    parts.append(f"📅 {dt_str}")
    parts.append("─────────────────")
    for l in lines:
        lt = format_money(l['line_total'])
        parts.append(f"{l['name']} | {l['sku']} | ×{l['qty']} | {store.get('currency', '₪')}{lt}")
    parts.append("─────────────────")
    parts.append(f"المجموع: {store.get('currency', '₪')}{format_money(subtotal)}")
    parts.append("⚠️ لا تشمل رسوم التوصيل")
    parts.append("─────────────────")
    parts.append(f"👤 {customer.get('name') or '-'} | 📞 {customer.get('phone') or '-'}")
    parts.append(f"📍 {customer.get('address') or '-'}")
    parts.append(f"📝 {customer.get('notes') or '-'}")

    msg = "\n".join(parts)
    if len(msg) > 1800:
        if customer.get('notes'):
            parts[-1] = "📝 —"
        msg = "\n".join(parts)
        if len(msg) > 2000:
            count_items = sum(1 for p in parts if ' | ' in p)
            msg = f"🛍️ طلب جديد — {store['name']}\n📅 {dt_str}\nعدد العناصر: {count_items}\nالمجموع: ₪{format_money(subtotal)}\n👤 {customer.get('name') or '-'} | 📞 {customer.get('phone') or '-'}"
    return msg

# =========================
# Context Processor
# =========================
@app.context_processor
def inject_global_vars():
    if 'user_id' in session:
        if not hasattr(g, 'user_stats_global'):
            g.user_stats_global = get_user_stats(session['user_id'])
        return {
            'store_slug': g.user_stats_global.get('store_slug'),
            'admin_pwa_store_name': g.user_stats_global.get('store_name'),
        }
    return {'store_slug': None, 'admin_pwa_store_name': None}

# =========================
# Utilities
# =========================
def get_user_stats(user_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # جلب بيانات المستخدم بالكامل (بما فيها الاشتراك)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        
        cursor.execute("SELECT id, name, slug FROM stores WHERE user_id = %s", (user_id,))
        store = cursor.fetchone()
        
        processed_count = 0
        if store:
            cursor.execute("SELECT COUNT(*) as count FROM products WHERE store_id = %s", (store['id'],))
            res = cursor.fetchone()
            processed_count = res['count'] if res else 0
            
        # حساب حالة الاشتراك لإرسالها للواجهة
        sub_status = {}
        if user_data:
             from database import get_subscription_status
             sub_status = get_subscription_status(user_data)
        
        return {
            'credits': user_data['credits'] if user_data else 0,
            'processed': processed_count,
            'store_slug': store['slug'] if store else None,
            'store_name': store['name'] if store else None,
            'sub': sub_status 
        }
    except Exception as e:
        logging.error(f"Error in get_user_stats: {e}")
        return {'credits': 0, 'processed': 0, 'store_slug': None, 'store_name': None, 'sub': {}}
    finally:
        if conn: conn.close()

# =========================
# Auth
# =========================
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
            return redirect(url_for('dashboard'))
        else:
            flash("رقم الهاتف أو كلمة المرور غير صحيحة.", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

# =========================
# Landing Page (Public)
# =========================
@app.route('/', methods=['GET', 'POST'])
def landing():
    # إذا كان الطلب رفع ملف (POST)، نمرره مباشرة للوحة التحكم
    if request.method == 'POST':
        return dashboard()

    # إذا كان المستخدم مسجل دخوله، نوجهه مباشرة للوحة التحكم
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    # إذا لم يكن مسجلاً، نعرض صفحة الهبوط
    from database import record_join_visit
    record_join_visit('home')
    return render_template('join.html')

@app.route('/join')
def join():
    # يمكن استخدام هذا الرابط أيضاً للوصول للصفحة الترويجية
    from database import record_join_visit
    record_join_visit('join')
    return render_template('join.html')

# =========================
# Dashboard (Protected)
# =========================
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
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
                    return redirect(url_for('dashboard'))
            except:
                flash("رابط غير صالح أو غير متاح.", "error")
                return redirect(url_for('dashboard'))
        elif file and file.filename != '':
            original_filename = f"orig_{unique_id}_{file.filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
            file.save(filepath)
        else:
            flash("يرجى اختيار ملف أو وضع رابط صورة.", "error")
            return redirect(url_for('dashboard'))

        # Fix EXIF orientation
        try:
            exif_transpose_inplace(filepath)
        except:
            pass

                # Subscription check
        # نتحقق مما إذا كان الاشتراك فعالاً أو في فترة السماح
        if not stats.get('sub', {}).get('is_active'):
            flash("انتهى اشتراكك أو لم يتم تفعيله بعد. يرجى التواصل مع الإدارة للتجديد.", "error")
            return redirect(url_for('dashboard'))

        # Rate limit
        if not check_rate_limit(user_id):
            flash(f"لقد تجاوزت الحد المسموح ({RATE_LIMIT_PER_HOUR} صورة/ساعة). حاول لاحقاً.", "warning")
            return redirect(url_for('dashboard'))

        keep_original = request.form.get('keep_original') == '1'

        try:
            processed_filename = f"processed_{unique_id}.png"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)

            if keep_original:
                with Image.open(filepath) as source:
                    source = ImageOps.exif_transpose(source).convert('RGBA')
                    source.thumbnail((1600, 1600), Image.LANCZOS)
                    source.save(output_path, 'PNG', optimize=True)
                engine_used = 'original'
                logging.info("Keeping original image without background removal")
            else:
                output_data, engine_used = remove_bg_with_fallback(filepath)
                logging.info(f"Background removed using: {engine_used}")
                standardize_cutout(output_data, output_path, size=1200)

            store = get_store_by_user(user_id)

            return render_template(
                'result.html',
                filename=processed_filename,
                original_filename=original_filename,
                stats=get_user_stats(user_id),
                engine_used=engine_used,
                store=store
            )
        except Exception as e:
            logging.error(f"AI Processing Error: {e}")
            flash("حدث خطأ أثناء معالجة الصورة. يرجى المحاولة مرة أخرى.", "error")
            return redirect(url_for('dashboard'))

    return render_template('index.html', stats=stats)

# =========================
# Inventory & Store Management
# =========================
@app.route('/save_product', methods=['POST'])
def save_product():
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))

        # Subscription check
    user_stats = get_user_stats(user_id)
    if not user_stats.get('sub', {}).get('is_active'):
        flash("انتهى اشتراكك. لا يمكنك حفظ منتجات جديدة.", "error")
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()

    name = request.form.get('name', 'Product')
    price = request.form.get('price', 0)
    processed_image_url = request.form.get('image_url')
    original_image_url = request.form.get('original_image_url')
    category = request.form.get('category', '').strip() or 'الكل'
    description = request.form.get('description', '').strip()
    template_style = request.form.get('template_style', 'elegant')
    theme = request.form.get('theme', 'gold')
    background = request.form.get('background', 'none')
    product_category = request.form.get('product_category', 'other')
    pos_x = request.form.get('pos_x', 0)
    pos_y = request.form.get('pos_y', 0)
    enable_glow = request.form.get('enable_glow', 'false') == 'true'
    enable_reflection = request.form.get('enable_reflection', 'false') == 'true'
    zoom = int(request.form.get('zoom', 80))
    card_ratio = request.form.get('card_ratio', 'square')
    fit_mode = request.form.get('fit_mode', 'contain')
    if card_ratio not in ('square', 'portrait', 'landscape'):
        card_ratio = 'square'
    if fit_mode not in ('cover', 'contain'):
        fit_mode = 'contain'

    # Compose final image
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
            out_basepath=base_out,
            pos_x=pos_x,
            pos_y=pos_y,
            enable_glow=enable_glow,
            enable_reflection=enable_reflection,
            category=product_category,
            zoom=zoom
        )
        if final_webp_name and background and background.lower() != 'none':
            final_fname = final_webp_name

    except Exception as e:
        logging.error(f"Final composition failed: {e}")

    cursor.execute("SELECT * FROM stores WHERE user_id = %s", (user_id,))
    store = cursor.fetchone()

    if store:
        try:
            # Inventory handling (optional)
            stock_qty = None
            if store.get('inventory_enabled'):
                try:
                    stock_qty = int(request.form.get('stock_qty') or 0)
                except:
                    stock_qty = 0
            else:
                stock_qty = 999

            # Generate SKU within same transaction
            sku = generate_sku(conn, cursor, store['id'])

            cursor.execute("""
    INSERT INTO products (store_id, name, price, processed_image_url, original_image_url, template_style, theme, category, description, background, final_image_url, sku, stock_qty, active, zoom, variants, bundles, card_ratio, fit_mode)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s, %s, %s, %s)
""", (store['id'], name, price, processed_image_url, original_image_url, template_style, theme, category, description, background, final_fname, sku, stock_qty, zoom,
        request.form.get('variants', '').strip() or None,
        request.form.get('bundles', '').strip() or None,
        card_ratio,
        fit_mode))
            
            conn.commit()
            flash("تم حفظ المنتج بنجاح في متجرك!", "success")
            return redirect(url_for('admin'))
        except Exception as e:
            conn.rollback()
            logging.error(f"Save Product Error: {e}")
            flash("حدث خطأ تقني أثناء الحفظ.", "error")
        finally:
            conn.close()

    return redirect(url_for('dashboard'))

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
    orders = []
    analytics = {}
    if store:
                # جلب المنتجات النشطة فقط (التي لم يتم إخفاؤها)
                # التاجر يرى جميع المنتجات (المخفي والمتوفر)
        
        cursor.execute("SELECT * FROM products WHERE store_id = %s ORDER BY id DESC", (store['id'],))
        products = cursor.fetchall()

        cursor.execute("""
            SELECT * FROM order_drafts
            WHERE store_id = %s
            ORDER BY created_at DESC
        """, (store['id'],))
        orders = cursor.fetchall()

        cursor.execute("""
            SELECT COUNT(*) AS c FROM analytics_events 
            WHERE store_id=%s AND event_name='page_view' AND created_at >= NOW() - INTERVAL '7 days'
        """, (store['id'],))
        last7 = cursor.fetchone()['c']
        cursor.execute("""
            SELECT COUNT(*) AS c FROM analytics_events 
            WHERE store_id=%s AND event_name='page_view' AND created_at >= NOW() - INTERVAL '30 days'
        """, (store['id'],))
        last30 = cursor.fetchone()['c']
        cursor.execute("""
            SELECT p.id, p.name, COUNT(a.id) AS views
            FROM analytics_events a
            JOIN products p ON a.product_id = p.id
            WHERE a.store_id=%s AND a.event_name='product_view' AND a.created_at >= NOW() - INTERVAL '30 days'
            GROUP BY p.id, p.name
            ORDER BY views DESC
            LIMIT 5
        """, (store['id'],))
        top5 = cursor.fetchall()
        cursor.execute("""
            SELECT COUNT(*) AS adds FROM analytics_events 
            WHERE store_id=%s AND event_name='add_to_cart' AND created_at >= NOW() - INTERVAL '30 days'
        """, (store['id'],))
        adds = cursor.fetchone()['adds']
        cursor.execute("""
            SELECT COUNT(*) AS ws FROM analytics_events 
            WHERE store_id=%s AND event_name='whatsapp_sent' AND created_at >= NOW() - INTERVAL '30 days'
        """, (store['id'],))
        ws = cursor.fetchone()['ws']

        analytics = {
            'page_views_7d': last7,
            'page_views_30d': last30,
            'top_products_30d': top5,
            'add_to_cart_30d': adds,
            'whatsapp_30d': ws,
        }

    edit_product = None
    edit_id = request.args.get('edit')
    if edit_id and store:
        cursor.execute("SELECT * FROM products WHERE id = %s AND store_id = %s", (edit_id, store['id']))
        edit_product = cursor.fetchone()

    conn.close()
    from themes import ENHANCED_THEMES, THEME_COLLECTIONS, rgb_to_hex
    theme_list = []
    for coll_key, coll_data in THEME_COLLECTIONS.items():
        themes_in_coll = []
        for t in coll_data['themes']:
            if t in ENHANCED_THEMES:
                colors = ENHANCED_THEMES[t]
                themes_in_coll.append({
                    'name': t,
                    'light': rgb_to_hex(colors[0]),
                    'dark': rgb_to_hex(colors[1]),
                })
        theme_list.append({
            'key': coll_key,
            'label': coll_data['name'],
            'themes': themes_in_coll
        })
    return render_template(
        'admin.html',
        products=products,
        stats=stats,
        store=store,
        edit_product=edit_product,
        orders=orders,
        analytics=analytics,
        theme_list=theme_list,
        store_backgrounds=STORE_BACKGROUNDS
    )

@app.route('/edit_product/<int:id>', methods=['POST'])
def edit_product_route(id):
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))

    name = request.form.get('name')
    price = request.form.get('price')
    original_price = request.form.get('original_price') or None
    discount_reason = request.form.get('discount_reason', '').strip() or None
    description = request.form.get('description')
    theme = request.form.get('theme')
    category = request.form.get('category', '').strip() or 'الكل'
    template_style = request.form.get('template_style')
    sku = request.form.get('sku')
    active = request.form.get('active') == 'on'
    stock_qty = request.form.get('stock_qty')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE products SET name=%s, price=%s, original_price=%s, discount_reason=%s, description=%s, theme=%s, template_style=%s, category=%s, active=%s, variants=%s, bundles=%s
            WHERE id=%s AND store_id = (SELECT id FROM stores WHERE user_id=%s)
        """, (name, price, original_price, discount_reason, description, theme, template_style, category, active,
               request.form.get('variants', '').strip() or None,
               request.form.get('bundles', '').strip() or None,
               id, user_id))
        if sku and sku.strip():
            cursor.execute("""
                UPDATE products SET sku=%s
                WHERE id=%s AND store_id = (SELECT id FROM stores WHERE user_id=%s)
            """, (sku.strip().upper(), id, user_id))
        if stock_qty is not None and stock_qty != '':
            try:
                sq = int(stock_qty)
            except:
                sq = 0
            cursor.execute("""
                UPDATE products SET stock_qty=%s
                WHERE id=%s AND store_id = (SELECT id FROM stores WHERE user_id=%s)
            """, (sq, id, user_id))

        conn.commit()
        flash("تم تحديث البيانات.", "success")
    except Exception as e:
        conn.rollback()
        logging.error(f"Edit Product Error: {e}")
        flash("تعذر حفظ التحديثات. تحقق من القيم.", "error")
    finally:
        conn.close()
    return redirect(url_for('admin'))

# =========================
# Product Variants API
# =========================
@app.route('/api/product/<int:product_id>/variants', methods=['GET'])
def get_variants(product_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM product_variants WHERE product_id = %s ORDER BY sort_order, id", (product_id,))
    variants = cur.fetchall()
    conn.close()
    return jsonify([dict(v) for v in variants])

@app.route('/api/product/<int:product_id>/variants/save', methods=['POST'])
def save_variants(product_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'unauthorized'}), 401
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT p.id FROM products p JOIN stores s ON p.store_id = s.id WHERE p.id = %s AND s.user_id = %s", (product_id, user_id))
    if not cur.fetchone():
        conn.close()
        return jsonify({'error': 'forbidden'}), 403
    data = request.get_json()
    variants = data.get('variants', [])
    try:
        cur.execute("DELETE FROM product_variants WHERE product_id = %s", (product_id,))
        for i, v in enumerate(variants):
            cur.execute("INSERT INTO product_variants (product_id, name, price, image_url, description, sort_order) VALUES (%s, %s, %s, %s, %s, %s)",
                (product_id, v.get('name',''), float(v.get('price', 0)), v.get('image_url') or None, v.get('description') or None, i))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'count': len(variants)})
    except Exception as e:
        conn.rollback()
        conn.close()
        logging.error(f"Save variants error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/variant/upload-image', methods=['POST'])
def upload_variant_image():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'unauthorized'}), 401
    file = request.files.get('image')
    if not file:
        return jsonify({'error': 'no file'}), 400
    try:
        ext = os.path.splitext(file.filename)[1].lower() or '.jpg'
        fname = f"variant_{uuid.uuid4().hex[:10]}{ext}"
        fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        file.save(fpath)
        return jsonify({'success': True, 'image_url': fname})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_product/<int:id>')
def delete_product_route(id):
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    # بدل الحذف، نقوم بإخفاء المنتج (Soft Delete)
    # هذا يمنع الخطأ ويحافظ على سجل الطلبات، والمنتج يختفي من المتجر واللوحة
    cursor.execute("UPDATE products SET active = FALSE WHERE id=%s AND store_id = (SELECT id FROM stores WHERE user_id=%s)", (id, user_id))
    conn.commit()
    conn.close()
    flash("تمت إزالة المنتج بنجاح.", "info")
    return redirect(url_for('admin'))
@app.route('/toggle_active/<int:id>')
def toggle_active_product(id):
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    # تبديل الحالة من مخفي إلى ظاهر والعكس
    cursor.execute("UPDATE products SET active = NOT COALESCE(active, TRUE) WHERE id=%s AND store_id = (SELECT id FROM stores WHERE user_id=%s)", (id, user_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

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
    w_prefix = request.form.get('whatsapp_prefix', '970')
    w_phone = request.form.get('whatsapp_phone')
    whatsapp_phone = clean_phone_number(w_prefix, w_phone)
    instagram_handle = request.form.get('instagram_handle')
    tiktok_handle = request.form.get('tiktok_handle')
    facebook_handle = request.form.get('facebook_handle')
    address = request.form.get('address')
    website = request.form.get('website')
    inventory_enabled = True if request.form.get('inventory_enabled') in ('on', 'true', '1') else False
    currency = request.form.get('currency', '₪')
    store_theme = request.form.get('store_theme', '').strip() or 'gold'
    store_background = normalize_store_background(request.form.get('store_background'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if logo_url:
            cursor.execute("""
                UPDATE stores SET 
                    name=%s, slug=%s, bio=%s, display_phone=%s, whatsapp_phone=%s,
                    instagram_handle=%s, tiktok_handle=%s, facebook_handle=%s, 
                    address=%s, website=%s, logo_url=%s, inventory_enabled=%s, currency=%s, store_theme=%s, store_background=%s
                WHERE user_id=%s
            """, (name, slug, bio, display_phone, whatsapp_phone,
                  instagram_handle, tiktok_handle, facebook_handle,
                  address, website, logo_url, inventory_enabled, currency, store_theme, store_background, user_id))
        else:
            cursor.execute("""
                UPDATE stores SET 
                    name=%s, slug=%s, bio=%s, display_phone=%s, whatsapp_phone=%s,
                    instagram_handle=%s, tiktok_handle=%s, facebook_handle=%s, 
                    address=%s, website=%s, inventory_enabled=%s, currency=%s, store_theme=%s, store_background=%s
                WHERE user_id=%s
            """, (name, slug, bio, display_phone, whatsapp_phone,
                  instagram_handle, tiktok_handle, facebook_handle,
                  address, website, inventory_enabled, currency, store_theme, store_background, user_id))
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

@app.route('/admin/store-preview')
def admin_store_preview():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stores WHERE user_id = %s", (user_id,))
    store = cursor.fetchone()
    if not store:
        conn.close()
        return "المتجر غير موجود.", 404

    cursor.execute("SELECT * FROM products WHERE store_id = %s AND active = TRUE ORDER BY id DESC", (store['id'],))
    products = cursor.fetchall()
    conn.close()

    from themes import ENHANCED_THEMES, rgb_to_hex
    requested_theme = request.args.get('theme', '').strip()
    theme_name = requested_theme if requested_theme in ENHANCED_THEMES else (store.get('store_theme') or 'gold')
    background_name = normalize_store_background(
        request.args.get('background', store.get('store_background'))
    )
    theme_colors = ENHANCED_THEMES.get(theme_name, ENHANCED_THEMES['gold'])
    theme_hex = {
        'light': rgb_to_hex(theme_colors[0]),
        'dark': rgb_to_hex(theme_colors[1]),
    }
    return render_template(
        'store.html',
        store=store,
        products=products,
        product_to_open=None,
        theme_hex=theme_hex,
        theme_name=theme_name,
        store_background=background_name,
        store_background_url=get_store_background_url(background_name),
        preview_mode=True
    )

@app.route('/store/<slug>')
def view_store(slug):
    decoded_slug = urllib.parse.unquote(slug)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stores WHERE slug = %s OR slug = %s", (decoded_slug.lower(), slug.lower()))
    store = cursor.fetchone()

    if store:
        visitor_key = get_public_visitor_key(store)
        if visitor_key:
            from database import record_store_visit
            record_store_visit(store['id'], visitor_key, 'store')
    else:
        conn.close()
        return "هذا المتجر غير موجود حالياً.", 404

        # جلب المنتجات النشطة فقط (المخفية لا تظهر أبداً)
    cursor.execute("SELECT * FROM products WHERE store_id = %s AND active = TRUE ORDER BY id DESC", (store['id'],))
    products = cursor.fetchall()

    open_id = request.args.get('open_product')
    product_to_open = None
    if open_id:
        cursor.execute("SELECT * FROM products WHERE id = %s AND store_id = %s", (open_id, store['id']))
        product_to_open = cursor.fetchone()

    conn.close()
    from themes import ENHANCED_THEMES, rgb_to_hex
    theme_name = store.get('store_theme') or 'gold'
    background_name = normalize_store_background(store.get('store_background'))
    theme_colors = ENHANCED_THEMES.get(theme_name, ENHANCED_THEMES['gold'])
    theme_hex = {
        'light': rgb_to_hex(theme_colors[0]),
        'dark':  rgb_to_hex(theme_colors[1]),
    }
    return render_template(
        'store.html',
        store=store,
        products=products,
        product_to_open=product_to_open,
        theme_hex=theme_hex,
        theme_name=theme_name,
        store_background=background_name,
        store_background_url=get_store_background_url(background_name),
        preview_mode=False
    )

@app.route('/store/<slug>/product/<int:product_id>')
def view_product_page(slug, product_id):
    """Dedicated product page with full details, store info, and shareable URL."""
    decoded_slug = urllib.parse.unquote(slug)

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get store
    cursor.execute("SELECT * FROM stores WHERE slug = %s OR slug = %s", (decoded_slug.lower(), slug.lower()))
    store = cursor.fetchone()
    
    if not store:
        conn.close()
        return "هذا المتجر غير موجود.", 404
    
    # Get product
    cursor.execute("SELECT * FROM products WHERE id = %s AND store_id = %s AND active = TRUE", 
                   (product_id, store['id']))
    product = cursor.fetchone()
    
    if not product:
        conn.close()
        return "المنتج غير موجود.", 404
    
    # Get other products from same store (for "More from this store")
    cursor.execute("""
        SELECT * FROM products 
        WHERE store_id = %s AND active = TRUE AND id != %s 
        ORDER BY id DESC LIMIT 12
    """, (store['id'], product_id))
    related_products = cursor.fetchall()
    
    # Record product view
    try:
        visitor_key = get_public_visitor_key(store)
        if visitor_key:
            from database import record_store_visit
            record_store_visit(store['id'], visitor_key, 'product')
    except Exception:
        pass
    
    available = is_available(store, product)
    
    conn.close()
    return render_template('product.html', 
                          store=store, 
                          product=product, 
                          related_products=related_products,
                          available=available)


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

    return redirect(url_for('view_product_page', slug=product['store_slug'], product_id=product_id))

# =========================
# Beacon Analytics
# =========================
@app.route("/e", methods=["GET", "POST"])
def beacon():
    e = request.args.get("e")
    store_id = request.args.get("store_id", type=int)
    product_id = request.args.get("product_id", type=int)
    allowed = {"page_view", "product_view", "add_to_cart", "whatsapp_sent"}
    if (not e) or (e not in allowed) or (not store_id):
        return ("", 204)
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO analytics_events(store_id, product_id, event_name) VALUES (%s, %s, %s)",
            (store_id, product_id, e)
        )
        conn.commit()
        return ("", 204)
    except Exception as ex:
        logging.warning(f"Beacon error: {ex}")
        return ("", 204)
    finally:
        try:
            conn.close()
        except:
            pass

# =========================
# Cart -> WhatsApp Order
# =========================
@app.post("/place_order")
def place_order():
    try:
        data = request.get_json(force=True, silent=False)
    except Exception:
        data = None
    if not data:
        return jsonify({"error": "بيانات غير صالحة"}), 400

    try:
        store_id = int(data.get("store_id"))
    except:
        return jsonify({"error": "store_id مفقود"}), 400
    cart = data.get("cart") or []
    if not isinstance(cart, list) or not cart:
        return jsonify({"error": "السلة فارغة"}), 400

    customer = {
        "name": data.get("customer_name"),
        "phone": data.get("customer_phone"),
        "address": data.get("customer_address"),
        "notes": data.get("customer_notes"),
    }
    # صمام أمان السيرفر: منع تسجيل الطلب إذا كانت البيانات الأساسية مفقودة
    if not customer["name"] or not customer["phone"] or not customer["address"]:
        return jsonify({"error": "الاسم، الهاتف، والعنوان حقول إجبارية"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM stores WHERE id=%s", (store_id,))
        store = cur.fetchone()
        if not store:
            return jsonify({"error": "متجر غير موجود"}), 404

        ids = tuple(int(i.get("product_id")) for i in cart if i.get("product_id"))
        if not ids:
            return jsonify({"error": "عناصر غير صالحة"}), 400

        sql = f"SELECT * FROM products WHERE id IN %s AND store_id=%s"
        cur.execute(sql, (ids, store_id))
        prows = cur.fetchall()
        products = {p['id']: p for p in prows}

        lines = []
        subtotal = 0.0
        for item in cart:
            pid = int(item.get("product_id"))
            qty = int(item.get("qty") or 1)
            if qty < 1:
                return jsonify({"error": "كمية غير صالحة"}), 400
            p = products.get(pid)
            if not p:
                return jsonify({"error": "منتج غير موجود"}), 400
            if not is_available(store, p):
                return jsonify({"error": f"المنتج '{p['name']}' غير متوفر حالياً"}), 400
            if store.get('inventory_enabled') and qty > (p.get('stock_qty') or 0):
                return jsonify({"error": f"الكمية المطلوبة لمنتج '{p['name']}' غير متوفرة"}), 400

            unit_price = to_number(p.get('price'))
            line_total = unit_price * qty
            display_sku = p.get('sku') or f"#{pid}"
            
            lines.append({
                "product_id": pid,
                "sku": display_sku,
                "name": p.get('name') or '',
                "unit_price": unit_price,
                "qty": qty,
                "line_total": line_total
            })
            subtotal += line_total

        wa_text = build_wa_text(store, lines, subtotal, customer)

        cur.execute("""
            INSERT INTO order_drafts (store_id, subtotal, grand_total, customer_name, customer_phone, customer_notes, wa_text, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'sent') RETURNING id
        """, (store_id, subtotal, subtotal, customer.get('name'), customer.get('phone'), customer.get('notes'), wa_text))
        order_id = cur.fetchone()['id']
        for l in lines:
            cur.execute("""
                INSERT INTO order_lines (order_id, product_id, sku, name_snapshot, unit_price, qty, line_total)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (order_id, l["product_id"], l["sku"], l["name"], l["unit_price"], l["qty"], l["line_total"]))

        cur.execute("INSERT INTO analytics_events(store_id, event_name) VALUES (%s, 'whatsapp_sent')", (store_id,))
        conn.commit()

        phone = (store.get('whatsapp_phone') or '').strip()
        encoded = urllib.parse.quote(wa_text)
        wa_link = f"https://wa.me/{phone}?text={encoded}" if phone else None

        return jsonify({"ok": True, "order_id": order_id, "wa_number": phone, "wa_text": wa_text, "wa_link": wa_link})
    except Exception as e:
        conn.rollback()
        logging.error(f"place_order error: {e}")
        return jsonify({"error": "تعذر إنشاء الطلب"}), 500
    finally:
        conn.close()

@app.post("/confirm_order/<int:order_id>")
def confirm_order(order_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "غير مصرّح"}), 401

    store = get_store_by_user(user_id)
    if not store:
        return jsonify({"error": "لا يوجد متجر مرتبط"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, store_id, status FROM order_drafts WHERE id=%s AND store_id=%s", (order_id, store['id']))
        order = cur.fetchone()
        if not order:
            return jsonify({"error": "طلب غير موجود"}), 404
        if order['status'] == 'confirmed':
            return jsonify({"ok": True})

        cur.execute("SELECT product_id, qty FROM order_lines WHERE order_id=%s", (order_id,))
        lines = cur.fetchall()

        if store.get('inventory_enabled'):
            for l in lines:
                cur.execute("SELECT stock_qty, active FROM products WHERE id=%s AND store_id=%s FOR UPDATE", (l['product_id'], store['id']))
                p = cur.fetchone()
                if not p or not p['active']:
                    conn.rollback()
                    return jsonify({"error": "منتج غير متاح"}), 400
                if (p['stock_qty'] or 0) < l['qty']:
                    conn.rollback()
                    return jsonify({"error": "المخزون غير كافٍ"}), 400
            for l in lines:
                cur.execute("UPDATE products SET stock_qty = stock_qty - %s WHERE id=%s AND store_id=%s", (l['qty'], l['product_id'], store['id']))

        cur.execute("UPDATE order_drafts SET status='confirmed' WHERE id=%s", (order_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        logging.error(f"confirm_order error: {e}")
        return jsonify({"error": "تعذر تأكيد الطلب"}), 500
    finally:
        conn.close()

@app.post("/cancel_order/<int:order_id>")
def cancel_order(order_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "غير مصرّح"}), 401
    store = get_store_by_user(user_id)
    if not store:
        return jsonify({"error": "لا يوجد متجر مرتبط"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE order_drafts SET status='canceled' WHERE id=%s AND store_id=%s AND status='sent'", (order_id, store['id']))
        if cur.rowcount == 0:
            conn.rollback()
            return jsonify({"error": "لا يمكن إلغاء هذا الطلب"}), 400
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        logging.error(f"cancel_order error: {e}")
        return jsonify({"error": "تعذر إلغاء الطلب"}), 500
    finally:
        conn.close()

# =========================
# Super Admin
# =========================
@app.route('/superadmin')
def super_admin():
    if not session.get('is_superadmin'): return redirect(url_for('super_admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    from database import get_visit_stats, get_join_visit_stats
    visit_stats = get_visit_stats()
    join_visit_stats = get_join_visit_stats()

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
                           visit_stats=visit_stats,
                           join_visit_stats=join_visit_stats,
                           now=datetime.utcnow())  # <--- هذا هو السطر الذي كان ناقصاً

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

@app.route('/superadmin/set_subscription', methods=['POST'])
def super_admin_set_subscription():
    if not session.get('is_superadmin'): return redirect(url_for('login'))
    try:
        user_id = int(request.form.get('user_id'))
        plan_type = request.form.get('plan_type')
        
        from database import set_subscription
        sub_end = set_subscription(user_id, plan_type)
        
        plan_labels = {'monthly': 'شهري', 'biannual': '6 أشهر', 'annual': 'سنوي'}
        flash(f"✅ تم تفعيل الاشتراك ({plan_labels[plan_type]}) بنجاح حتى {sub_end.strftime('%Y-%m-%d')}", "success")
    except Exception as e:
        logging.error(f"Subscription Error: {e}")
        flash("حدث خطأ أثناء تفعيل الاشتراك.", "error")
        
    return redirect(url_for('super_admin'))

@app.route('/superadmin/freeze/<int:user_id>')
def super_admin_freeze(user_id):
    if not session.get('is_superadmin'): return redirect(url_for('login'))
    from database import toggle_freeze
    toggle_freeze(user_id, True)
    flash("تم تجميد الحساب وتوقف المتجر عن العمل.", "warning")
    return redirect(url_for('super_admin'))

@app.route('/superadmin/unfreeze/<int:user_id>')
def super_admin_unfreeze(user_id):
    if not session.get('is_superadmin'): return redirect(url_for('login'))
    from database import toggle_freeze
    toggle_freeze(user_id, False)
    flash("تم إعادة تفعيل الحساب بنجاح.", "success")
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

# =========================
# Dynamic Store Manifest (PWA)
# =========================
@app.route('/admin-manifest/<slug>')
def admin_manifest(slug):
    import json as _json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, slug, bio FROM stores WHERE LOWER(slug) = %s", (slug.lower(),))
    store = cur.fetchone()
    conn.close()

    if not store:
        return jsonify({"error": "store not found"}), 404

    app_name = f"Admin - {store['name']}"
    manifest = {
        "id": f"/admin-app/{store['slug']}",
        "name": app_name,
        "short_name": app_name,
        "description": f"لوحة إدارة متجر {store['name']} على RT Studio",
        "start_url": "/dashboard",
        "scope": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#0A192F",
        "orientation": "portrait",
        "icons": [
            {
                "src": f"/admin-icon/{store['slug']}/192",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": f"/admin-icon/{store['slug']}/512",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    }
    from flask import Response
    response = Response(
        _json.dumps(manifest, ensure_ascii=False),
        mimetype='application/manifest+json'
    )
    response.headers['Cache-Control'] = 'no-cache'
    return response


@app.route('/admin-icon/<slug>/<int:size>')
def admin_icon(slug, size):
    if size not in (192, 512):
        return "Unsupported icon size", 404

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT logo_url FROM stores WHERE LOWER(slug) = %s", (slug.lower(),))
    store = cur.fetchone()
    conn.close()

    fallback = os.path.join(app.root_path, 'static', f'rt_logo_{size}.png')
    source_path = fallback
    if store and store.get('logo_url'):
        candidate = os.path.join(app.config['UPLOAD_FOLDER'], store['logo_url'])
        if os.path.isfile(candidate):
            source_path = candidate

    try:
        with Image.open(source_path) as source:
            source = ImageOps.exif_transpose(source).convert('RGBA')
            safe_size = int(size * 0.72)
            source.thumbnail((safe_size, safe_size), Image.LANCZOS)
            canvas = Image.new('RGBA', (size, size), '#FFFFFF')
            offset = ((size - source.width) // 2, (size - source.height) // 2)
            canvas.alpha_composite(source, offset)
            output = io.BytesIO()
            canvas.convert('RGB').save(output, format='PNG', optimize=True)
            output.seek(0)
        return send_file(output, mimetype='image/png', max_age=3600)
    except Exception as exc:
        logging.error(f"Admin PWA icon generation failed: {exc}")
        return send_file(fallback, mimetype='image/png', max_age=3600)


@app.route('/store-manifest/<slug>')
def store_manifest(slug):
    import json as _json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM stores WHERE LOWER(slug) = %s", (slug.lower(),))
    store = cur.fetchone()
    conn.close()

    if not store:
        return jsonify({"error": "store not found"}), 404

    store_url = f"/store/{store['slug']}"
    manifest = {
        "id": f"/store/{store['slug']}",
        "name": store['name'],
        "short_name": store['name'][:12],
        "description": store.get('bio') or f"متجر {store['name']} - اطلب الآن عبر واتساب",
        "start_url": store_url,
        "scope": store_url,
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#1A2238",
        "orientation": "portrait",
        "icons": [
            {
                "src": f"/store-icon/{store['slug']}/192",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": f"/store-icon/{store['slug']}/512",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    }
    from flask import Response
    response = Response(
        _json.dumps(manifest, ensure_ascii=False),
        mimetype='application/manifest+json'
    )
    response.headers['Cache-Control'] = 'no-cache'
    return response

@app.route('/store-icon/<slug>/<int:size>')
def store_icon(slug, size):
    if size not in (192, 512):
        return "Unsupported icon size", 404

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT logo_url FROM stores WHERE LOWER(slug) = %s", (slug.lower(),))
    store = cur.fetchone()
    conn.close()

    fallback = os.path.join(app.root_path, 'static', f'rt_logo_{size}.png')
    source_path = fallback
    if store and store.get('logo_url'):
        candidate = os.path.join(app.config['UPLOAD_FOLDER'], store['logo_url'])
        if os.path.isfile(candidate):
            source_path = candidate

    try:
        with Image.open(source_path) as source:
            source = ImageOps.exif_transpose(source).convert('RGBA')
            fitted = ImageOps.fit(source, (size, size), method=Image.LANCZOS)
            output = io.BytesIO()
            fitted.save(output, format='PNG', optimize=True)
            output.seek(0)
        return send_file(output, mimetype='image/png', max_age=3600)
    except Exception as exc:
        logging.error(f"PWA icon generation failed: {exc}")
        return send_file(fallback, mimetype='image/png', max_age=3600)

# =========================
# Showcase API (Landing Page)
# =========================
@app.route('/api/showcase')
def api_showcase():
    """Return one product per store (latest) from active stores for the landing page showcase."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT ON (s.id)
                s.name     AS store,
                s.slug     AS slug,
                s.currency AS currency,
                p.name     AS product,
                p.price    AS price,
                p.processed_image_url AS img
            FROM products p
            JOIN stores s ON p.store_id = s.id
            WHERE p.active = TRUE
              AND s.is_active = TRUE
            ORDER BY s.id, p.created_at DESC
        """)
        rows = cur.fetchall()
        conn.close()
        result = []
        for r in rows:
            result.append({
                'store':    r['store'],
                'slug':     r['slug'],
                'currency': r['currency'] or '₪',
                'product':  r['product'],
                'price':    str(r['price']),
                'img':      r['img'] or ''
            })
        return jsonify(result)
    except Exception as e:
        logging.error(f"showcase error: {e}")
        return jsonify([])

# =========================
# Static: Service Worker
# =========================
@app.route('/sw.js')
def sw():
    return send_from_directory(app.root_path, 'sw.js')

# =========================
# SEO: robots.txt + sitemap
# =========================
@app.route('/robots.txt')
def robots_txt():
    content = """User-agent: *
Allow: /
Allow: /store/
Allow: /join
Disallow: /superadmin
Disallow: /admin
Disallow: /login
Disallow: /register
Disallow: /api/
Disallow: /e

Sitemap: https://www.rtstudio.store/sitemap.xml
"""
    return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}

@app.route('/sitemap.xml')
def sitemap_xml():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                s.slug,
                GREATEST(s.created_at, MAX(p.created_at)) AS last_modified
            FROM stores s
            LEFT JOIN products p ON p.store_id = s.id
            WHERE s.is_active = TRUE
            GROUP BY s.id, s.slug, s.created_at
            ORDER BY s.id
        """)
        stores = cur.fetchall()
        conn.close()
    except Exception:
        stores = []

    urls = [
        ('https://www.rtstudio.store/', None),
        ('https://www.rtstudio.store/join', None),
    ]
    for s in stores:
        encoded_slug = urllib.parse.quote(s['slug'], safe='-')
        urls.append((
            f"https://www.rtstudio.store/store/{encoded_slug}",
            s.get('last_modified')
        ))

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url, last_modified in urls:
        xml += f'  <url><loc>{escape(url)}</loc>'
        if last_modified:
            xml += f'<lastmod>{last_modified.date().isoformat()}</lastmod>'
        xml += '</url>\n'
    xml += '</urlset>'
    return xml, 200, {'Content-Type': 'application/xml; charset=utf-8'}

# =========================
# Entrypoint
# =========================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 3000))
    app.run(host='0.0.0.0', port=port, threaded=True)
