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
import json
import threading
import time
from datetime import datetime, timedelta
from collections import defaultdict
from decimal import Decimal
from xml.sax.saxutils import escape

from flask import Flask, render_template, request, redirect, session, url_for, flash, g, send_from_directory, send_file, jsonify
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from rembg import remove
from PIL import Image, ImageOps, ImageDraw, ImageFont, ImageFilter

from database import get_db_connection
from shipping import ShiplyClient, ShiplyError, decrypt_api_key, encrypt_api_key

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
REMOVEBG_API_KEY = os.environ.get('REMOVEBG_API_KEY', '')
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '').strip()
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '').replace('\\n', '\n').strip()
VAPID_SUBJECT = os.environ.get('VAPID_SUBJECT', 'mailto:admin@rtstudio.store').strip()

SHIPLY_STATUS_NAMES = {
    1: 'مسودة',
    2: 'جاهز للإرسال',
    3: 'مشحون',
    4: 'محاولة تسليم',
    5: 'عالق',
    6: 'واصل',
    7: 'راجع',
    8: 'منتهي',
    9: 'تم التبديل',
    10: 'تمت المعالجة',
}

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
    'luxury_lilac_marble':      'static/assets/bg/luxury_lilac_marble.png',
    'luxury_champagne_silk':    'static/assets/bg/luxury_champagne_silk.png',
    'luxury_sky_stone':         'static/assets/bg/luxury_sky_stone.png',
    'luxury_dusty_pink_velvet': 'static/assets/bg/luxury_dusty_pink_velvet.png',
}

STORE_BACKGROUNDS = [
    {'key': 'none', 'label': 'بدون خلفية', 'file': None},
    {'key': 'luxury_lilac_marble', 'label': 'رخام ليلكي', 'file': 'luxury_lilac_marble.png'},
    {'key': 'luxury_champagne_silk', 'label': 'حرير شمبانيا', 'file': 'luxury_champagne_silk.png'},
    {'key': 'luxury_sky_stone', 'label': 'حجر سماوي', 'file': 'luxury_sky_stone.png'},
    {'key': 'luxury_dusty_pink_velvet', 'label': 'مخمل وردي', 'file': 'luxury_dusty_pink_velvet.png'},
    {'key': 'rose_blur', 'label': 'وردي ضبابي', 'file': 'rose_blur.jpg'},
    {'key': 'grey_marble', 'label': 'رخام رمادي', 'file': 'grey_marble.jpg'},
    {'key': 'brushed_silver', 'label': 'فضي ناعم', 'file': 'brushed_silver.jpg'},
    {'key': 'velvet_red', 'label': 'مخمل نبيذي', 'file': 'velvet_red.jpg'},
    {'key': 'velvet_teal', 'label': 'مخمل زمردي', 'file': 'velvet_teal.jpg'},
    {'key': 'navy_silk', 'label': 'حرير كحلي', 'file': 'navy_silk.jpg'},
    {'key': 'black_marble', 'label': 'رخام أسود', 'file': 'black_marble.jpg'},
    {'key': 'dark_concrete', 'label': 'خرسانة داكنة', 'file': 'dark_concrete.jpg'},
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

    digit_map = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
    phone = str(phone).translate(digit_map)
    prefix = str(prefix).translate(digit_map)

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


def normalize_customer_phone(prefix, phone):
    digit_map = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
    if not prefix:
        legacy_phone = re.sub(r'\D', '', str(phone or '').translate(digit_map))
        if legacy_phone.startswith('00'):
            legacy_phone = legacy_phone[2:]
        return legacy_phone if 8 <= len(legacy_phone) <= 15 else None

    allowed_prefixes = {
        '970', '972', '962', '966', '971', '965', '974', '973', '968',
        '964', '963', '961', '20', '212', '213', '216', '218', '249',
        '90', '44', '49', '1'
    }
    prefix_digits = re.sub(r'\D', '', str(prefix or ''))
    if prefix_digits not in allowed_prefixes:
        return None

    normalized = clean_phone_number(prefix_digits, phone)
    local_digits = normalized[len(prefix_digits):] if normalized else ''
    if not 7 <= len(local_digits) <= 12 or not 8 <= len(normalized) <= 15:
        return None
    return normalized

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
    from database import get_app_setting

    removebg_enabled = get_app_setting('removebg_enabled', 'true') == 'true'
    if removebg_enabled and REMOVEBG_API_KEY:
        logging.info("Trying remove.bg API...")
        result = remove_bg_removebg(filepath)
        if result:
            return result, 'remove.bg'
        logging.warning("⚠️ remove.bg failed, falling back to rembg")
    elif not removebg_enabled:
        logging.info("remove.bg is disabled by the super admin; using rembg directly")
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
from moeen_multi import moeen_bp
app.register_blueprint(moeen_bp)

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


TRAFFIC_SOURCE_LABELS = {
    'facebook': 'فيسبوك',
    'instagram': 'إنستغرام',
    'whatsapp': 'واتساب',
    'google': 'جوجل',
    'tiktok': 'تيك توك',
    'youtube': 'يوتيوب',
    'telegram': 'تلغرام',
    'twitter': 'إكس / تويتر',
    'direct': 'رابط مباشر',
    'other': 'مصدر آخر',
    'unknown': 'غير معروف',
}


def detect_traffic_source():
    """Classify the public visit source using campaign params and referrer."""
    args_text = ' '.join(
        str(request.args.get(key, '')).lower()
        for key in ('utm_source', 'source', 'ref')
    )
    referrer = request.referrer or ''
    referrer_host = urllib.parse.urlparse(referrer).netloc.lower()
    combined = f"{args_text} {referrer_host}".lower()

    if request.args.get('fbclid') or 'facebook' in combined or 'fb.com' in combined:
        return 'facebook', referrer or None
    if request.args.get('igshid') or 'instagram' in combined:
        return 'instagram', referrer or None
    if 'whatsapp' in combined or 'wa.me' in combined:
        return 'whatsapp', referrer or None
    if 'google' in combined:
        return 'google', referrer or None
    if 'tiktok' in combined:
        return 'tiktok', referrer or None
    if 'youtube' in combined or 'youtu.be' in combined:
        return 'youtube', referrer or None
    if 'telegram' in combined or 't.me' in combined:
        return 'telegram', referrer or None
    if 'twitter' in combined or 'x.com' in combined or 't.co' in combined:
        return 'twitter', referrer or None
    if referrer_host:
        return 'other', referrer
    return 'direct', None


def attach_traffic_labels(rows):
    labeled = []
    for row in rows or []:
        item = dict(row)
        source = item.get('source') or 'unknown'
        item['source'] = source
        item['label'] = TRAFFIC_SOURCE_LABELS.get(source, source)
        labeled.append(item)
    return labeled


MASTER_PASSWORD = os.environ.get('MASTER_PASSWORD', 'Ruba2025!!')
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

SUBSCRIPTION_PLANS = {
    'monthly': {'label': 'اشتراك شهري', 'days': 30, 'amount': Decimal('100.00'), 'currency': '₪'},
    'biannual': {'label': 'اشتراك 6 أشهر', 'days': 180, 'amount': Decimal('510.00'), 'currency': '₪'},
    'annual': {'label': 'اشتراك سنوي', 'days': 365, 'amount': Decimal('960.00'), 'currency': '₪'},
}

PAYMENT_METHOD_LABELS = {
    'wallet': 'محفظة إلكترونية',
    'buraq': 'تحويل براق',
    'iban': 'تحويل إلى الإيبان',
}

MOEEN_SUBSCRIPTION_PLANS = {
    'monthly': {'label': 'اشتراك شهري', 'days': 30, 'amount': Decimal('60.00'), 'currency': '₪'},
    'quarterly': {'label': 'اشتراك 3 أشهر', 'days': 90, 'amount': Decimal('160.00'), 'currency': '₪'},
    'annual': {'label': 'اشتراك سنوي', 'days': 365, 'amount': Decimal('540.00'), 'currency': '₪'},
}
MOEEN_TERMS_VERSION = "2026-07-28"

PAYMENT_SETTING_KEYS = [
    'payment_account_name',
    'payment_wallet_name',
    'payment_wallet_number',
    'payment_bank_name',
    'payment_iban',
    'payment_note',
]

RECEIPT_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'pdf'}


def get_subscription_plan(plan_type):
    return SUBSCRIPTION_PLANS.get(plan_type, SUBSCRIPTION_PLANS['monthly'])


def get_payment_settings():
    from database import get_app_setting
    defaults = {
        'payment_account_name': 'RT Studio',
        'payment_wallet_name': '',
        'payment_wallet_number': '',
        'payment_bank_name': '',
        'payment_iban': '',
        'payment_note': 'بعد التحويل، أرسل رقم العملية أو صورة الإيصال وسيتم تفعيل الاشتراك بعد المراجعة.',
    }
    return {key: get_app_setting(key, defaults[key]) for key in PAYMENT_SETTING_KEYS}


def allowed_receipt_file(filename):
    return bool(filename and '.' in filename and filename.rsplit('.', 1)[1].lower() in RECEIPT_EXTENSIONS)


def make_invoice_code(user_id):
    return f"RT-{datetime.utcnow().strftime('%Y%m%d')}-{user_id}-{uuid.uuid4().hex[:6].upper()}"

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
    _mcur.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS product_gallery_enabled BOOLEAN DEFAULT FALSE")
    _mcur.execute("""
        CREATE TABLE IF NOT EXISTS product_images (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            image_url TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    _mcur.execute("""
        CREATE INDEX IF NOT EXISTS ix_product_images_product_sort
        ON product_images(product_id, sort_order, id)
    """)
    _mcur.execute("""
        UPDATE stores
        SET product_gallery_enabled = TRUE
        WHERE LOWER(slug) = 'chrono-watches'
          AND product_gallery_enabled = FALSE
    """)
    _mcur.execute("""
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id SERIAL PRIMARY KEY,
            store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
            endpoint TEXT NOT NULL UNIQUE,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            user_agent TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    _mcur.execute("""
        CREATE INDEX IF NOT EXISTS ix_push_subscriptions_store
        ON push_subscriptions(store_id)
    """)
    _mcur.execute("""
        CREATE TABLE IF NOT EXISTS superadmin_push_subscriptions (
            id SERIAL PRIMARY KEY,
            endpoint TEXT NOT NULL UNIQUE,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            user_agent TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    _mcur.execute("""
        CREATE TABLE IF NOT EXISTS subscription_payments (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            store_id INTEGER REFERENCES stores(id) ON DELETE SET NULL,
            invoice_code TEXT NOT NULL UNIQUE,
            plan_type TEXT NOT NULL DEFAULT 'monthly',
            amount NUMERIC(12,2) NOT NULL,
            currency TEXT NOT NULL DEFAULT '₪',
            payment_method TEXT NOT NULL,
            transaction_ref TEXT,
            receipt_url TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            admin_note TEXT,
            reviewed_at TIMESTAMP,
            reviewed_by TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    _mcur.execute("ALTER TABLE subscription_payments ADD COLUMN IF NOT EXISTS store_id INTEGER")
    _mcur.execute("""
        CREATE TABLE IF NOT EXISTS moeen_subscription_payments (
            id SERIAL PRIMARY KEY,
            account_id INTEGER NOT NULL REFERENCES moeen_accounts(id) ON DELETE CASCADE,
            invoice_code TEXT NOT NULL UNIQUE,
            plan_type TEXT NOT NULL,
            amount NUMERIC(12,2) NOT NULL,
            currency TEXT NOT NULL DEFAULT '₪',
            payment_method TEXT NOT NULL,
            transaction_ref TEXT,
            receipt_url TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            admin_note TEXT,
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    _mcur.execute("""
        CREATE TABLE IF NOT EXISTS moeen_expiry_notifications (
            id BIGSERIAL PRIMARY KEY,
            account_id INTEGER NOT NULL REFERENCES moeen_accounts(id) ON DELETE CASCADE,
            reminder_key TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(account_id, reminder_key)
        )
    """)
    _mcur.execute("ALTER TABLE moeen_accounts ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMP")
    _mcur.execute("ALTER TABLE moeen_accounts ADD COLUMN IF NOT EXISTS terms_version TEXT")
    _mcur.execute("ALTER TABLE subscription_payments ADD COLUMN IF NOT EXISTS admin_note TEXT")
    _mcur.execute("ALTER TABLE subscription_payments ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP")
    _mcur.execute("ALTER TABLE subscription_payments ADD COLUMN IF NOT EXISTS reviewed_by TEXT")
    _mcur.execute("""
        CREATE INDEX IF NOT EXISTS ix_subscription_payments_status_created
        ON subscription_payments(status, created_at DESC)
    """)
    _mcur.execute("""
        CREATE INDEX IF NOT EXISTS ix_subscription_payments_user_created
        ON subscription_payments(user_id, created_at DESC)
    """)
    for _key, _value in {
        'payment_account_name': 'RT Studio',
        'payment_wallet_name': '',
        'payment_wallet_number': '',
        'payment_bank_name': '',
        'payment_iban': '',
        'payment_note': 'بعد التحويل، أرسل رقم العملية أو صورة الإيصال وسيتم تفعيل الاشتراك بعد المراجعة.',
    }.items():
        _mcur.execute("""
            INSERT INTO app_settings (setting_key, setting_value)
            VALUES (%s, %s)
            ON CONFLICT (setting_key) DO NOTHING
        """, (_key, _value))
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


def send_order_push_notifications(store_id, store_name, store_slug, order_id, total, currency):
    """Best-effort push delivery. Notification failures never affect the order."""
    if not (VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY):
        return

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logging.warning("Push notifications disabled: pywebpush is not installed")
        return

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, endpoint, p256dh, auth
            FROM push_subscriptions
            WHERE store_id = %s
        """, (store_id,))
        subscriptions = cur.fetchall()
    finally:
        conn.close()

    payload = json.dumps({
        "title": f"طلب جديد في {store_name}",
        "body": f"الطلب #{order_id} بقيمة {currency} {float(total):.2f}",
        "tag": f"store-{store_id}-order-{order_id}",
        "url": f"/admin?active_tab=orders&order_id={order_id}",
        "icon": f"/admin-icon/{urllib.parse.quote(str(store_slug), safe='')}/192",
        "badge": "/static/rt_logo_192.png",
        "order_id": order_id,
    }, ensure_ascii=False)

    expired_ids = []
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription['endpoint'],
                    "keys": {
                        "p256dh": subscription['p256dh'],
                        "auth": subscription['auth'],
                    },
                },
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_SUBJECT},
                timeout=5,
            )
        except WebPushException as exc:
            status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
            if status_code in (404, 410):
                expired_ids.append(subscription['id'])
            else:
                logging.warning(f"Push delivery failed for store {store_id}: {exc}")
        except Exception as exc:
            logging.warning(f"Push delivery error for store {store_id}: {exc}")

    if expired_ids:
        cleanup_conn = get_db_connection()
        cleanup_cur = cleanup_conn.cursor()
        try:
            cleanup_cur.execute(
                "DELETE FROM push_subscriptions WHERE id = ANY(%s)",
                (expired_ids,)
            )
            cleanup_conn.commit()
        finally:
            cleanup_conn.close()

def send_superadmin_push_notification(title, body, tag, url, icon="/static/rt_logo_192.png"):
    """Deliver an RT Studio platform notification to subscribed superadmin devices."""
    if not (VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY):
        return {"sent": 0, "failed": 0, "configured": False}
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return {"sent": 0, "failed": 0, "configured": False}
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, endpoint, p256dh, auth FROM superadmin_push_subscriptions")
        subscriptions = cur.fetchall()
    finally:
        conn.close()
    payload = json.dumps({
        "title": title,
        "body": body,
        "tag": tag,
        "url": url,
        "icon": icon,
        "badge": "/static/rt_logo_192.png",
    }, ensure_ascii=False)
    expired = []
    sent = 0
    failed = 0
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription["endpoint"],
                    "keys": {"p256dh": subscription["p256dh"], "auth": subscription["auth"]},
                },
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_SUBJECT},
                timeout=5,
            )
            sent += 1
        except WebPushException as exc:
            failed += 1
            if getattr(getattr(exc, "response", None), "status_code", None) in (404, 410):
                expired.append(subscription["id"])
            logging.warning("Superadmin push failed: %s", exc)
        except Exception as exc:
            failed += 1
            logging.warning("Superadmin push failed: %s", exc)
    if expired:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM superadmin_push_subscriptions WHERE id = ANY(%s)", (expired,))
            conn.commit()
        finally:
            conn.close()
    return {"sent": sent, "failed": failed, "configured": True}


def send_moeen_signup_notifications(account_id, full_name, job_title):
    """Notify subscribed superadmin devices about a new active Moeen trial."""
    send_superadmin_push_notification(
        "بدأت تجربة جديدة في مُعين التنفيذي",
        f"{full_name} · تجربة مجانية لمدة 48 ساعة · {job_title or 'دون مسمى وظيفي'}",
        f"moeen-signup-{account_id}",
        "/superadmin#moeen-executive",
        "/static/moeen_exec/icon-192.png",
    )


def send_rt_signup_notification(user_id, store_name, phone):
    """Notify subscribed superadmin devices about a new RT Studio signup."""
    send_superadmin_push_notification(
        "تسجيل متجر جديد في RT Studio",
        f"{store_name} · {phone}",
        f"rt-signup-{user_id}",
        "/superadmin",
    )


def send_rt_payment_notification(invoice_code, store_name, plan_label):
    """Notify subscribed superadmin devices about a submitted payment proof."""
    send_superadmin_push_notification(
        "إثبات دفع جديد في RT Studio",
        f"{store_name} · {plan_label} · {invoice_code}",
        f"rt-payment-{invoice_code}",
        "/superadmin",
    )

def send_moeen_payment_notification(invoice_code, full_name, plan_label):
    send_superadmin_push_notification(
        "إثبات دفع جديد في مُعين التنفيذي",
        f"{full_name} · {plan_label} · {invoice_code}",
        f"moeen-payment-{invoice_code}",
        "/superadmin#moeen-payments",
        "/static/moeen_exec/icon-192.png",
    )

_moeen_expiry_check_lock = threading.Lock()
_moeen_expiry_last_check = 0.0


def check_moeen_expiry_notifications():
    """Send each expiry milestone once; invoked opportunistically by normal web traffic."""
    conn = get_db_connection()
    cursor = conn.cursor()
    reminders = []
    try:
        cursor.execute("""
            SELECT id, full_name, plan_type, subscription_end,
                   EXTRACT(EPOCH FROM (subscription_end - NOW())) / 3600 AS hours_left
            FROM moeen_accounts
            WHERE status='active' AND subscription_end IS NOT NULL
              AND subscription_end BETWEEN NOW() - INTERVAL '7 days' AND NOW() + INTERVAL '7 days'
        """)
        for account in cursor.fetchall():
            hours = float(account["hours_left"])
            if hours <= 0:
                key, timing = "expired", "انتهى الاشتراك"
            elif account["plan_type"] == "trial" and hours <= 24:
                key, timing = "trial_24h", f"تنتهي التجربة خلال {max(1, round(hours))} ساعة"
            elif account["plan_type"] != "trial" and hours <= 24:
                key, timing = "paid_1d", f"ينتهي الاشتراك خلال {max(1, round(hours))} ساعة"
            elif account["plan_type"] != "trial" and hours <= 168:
                key, timing = "paid_7d", f"ينتهي الاشتراك خلال {max(1, round(hours / 24))} أيام"
            else:
                continue
            cursor.execute("""
                INSERT INTO moeen_expiry_notifications(account_id, reminder_key)
                VALUES(%s,%s) ON CONFLICT(account_id, reminder_key) DO NOTHING
                RETURNING id
            """, (account["id"], key))
            if cursor.fetchone():
                reminders.append((account, key, timing))
        conn.commit()
    except Exception:
        conn.rollback()
        logging.exception("Moeen expiry reminder scan failed")
    finally:
        cursor.close()
        conn.close()
    for account, key, timing in reminders:
        send_superadmin_push_notification(
            "تنبيه اشتراك مُعين التنفيذي",
            f"{account['full_name']} · {timing}",
            f"moeen-expiry-{account['id']}-{key}",
            "/superadmin#moeen-executive",
            "/static/moeen_exec/icon-192.png",
        )


@app.before_request
def schedule_moeen_expiry_check():
    global _moeen_expiry_last_check
    now = time.monotonic()
    if now - _moeen_expiry_last_check < 1800:
        return
    if not _moeen_expiry_check_lock.acquire(blocking=False):
        return
    _moeen_expiry_last_check = now
    def worker():
        try:
            check_moeen_expiry_notifications()
        finally:
            _moeen_expiry_check_lock.release()
    threading.Thread(target=worker, daemon=True, name="moeen-expiry-check").start()


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


def format_customer_phone_for_message(phone):
    """Show Palestinian numbers locally and other numbers internationally."""
    digits = re.sub(r'\D', '', str(phone or ''))
    if digits.startswith('970'):
        return f"0{digits[3:]}"
    if digits.startswith('972'):
        return f"0{digits[3:]}"
    return f"+{digits}" if digits else '-'


def get_shiply_integration(store_id, require_enabled=True):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM shipping_integrations
            WHERE store_id = %s AND provider = 'shiply'
        """, (store_id,))
        integration = cursor.fetchone()
    finally:
        conn.close()

    if not integration or (require_enabled and not integration.get('enabled')):
        raise ShiplyError('تكامل Shiply غير مفعّل لهذا المتجر')
    api_key = decrypt_api_key(integration.get('api_key_encrypted'))
    if not api_key:
        raise ShiplyError('مفتاح Shiply غير محفوظ')
    return integration, ShiplyClient(
        api_key,
        integration.get('country') or 'palestine',
        integration.get('environment') or 'testing',
    )


def build_wa_text(store, lines, subtotal, customer):
    """
    Build WhatsApp message text only. No links inside the text.
    lines: list of dict(name, sku, qty, line_total)
    """
    dt_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    display_phone = format_customer_phone_for_message(customer.get('phone'))

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
    parts.append(f"👤 {customer.get('name') or '-'} | 📞 {display_phone}")
    parts.append(f"📍 {customer.get('address') or '-'}")
    parts.append(f"📝 {customer.get('notes') or '-'}")

    msg = "\n".join(parts)
    if len(msg) > 1800:
        if customer.get('notes'):
            parts[-1] = "📝 —"
        msg = "\n".join(parts)
        if len(msg) > 2000:
            count_items = sum(1 for p in parts if ' | ' in p)
            msg = f"🛍️ طلب جديد — {store['name']}\n📅 {dt_str}\nعدد العناصر: {count_items}\nالمجموع: ₪{format_money(subtotal)}\n👤 {customer.get('name') or '-'} | 📞 {display_phone}"
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
    signup_plans = {
        'monthly': 'الاشتراك الشهري — 100₪',
        'biannual': 'اشتراك 6 أشهر — 510₪',
        'annual': 'الاشتراك السنوي — 960₪',
        'four_year': 'عرض 4 سنوات — 3200₪',
    }
    selected_plan = (request.form.get('plan_type') or request.args.get('plan') or 'monthly').strip()
    if selected_plan not in signup_plans:
        selected_plan = 'monthly'
    if request.method == 'POST':
        phone = (request.form.get('phone') or '').strip()
        password = request.form.get('password')
        store_name = (request.form.get('store_name') or '').strip()
        if len(store_name) < 2 or len(phone) < 7 or len(password or '') < 8:
            flash("أدخل اسم متجر ورقم هاتف صحيحين، وكلمة مرور من 8 أحرف على الأقل.", "error")
            return render_template(
                'register.html',
                selected_plan=selected_plan,
                selected_plan_label=signup_plans[selected_plan],
            )
        raw_slug = store_name.lower().strip().replace(' ', '-')
        slug = re.sub(r'[^a-z0-9؀-ۿ-]', '', raw_slug) or 'store'[:30]

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO users (phone, password_hash, status, credits, plan_type)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (phone, generate_password_hash(password), 'pending', 10, selected_plan)
            )
            user_id = cursor.fetchone()['id']
            cursor.execute(
                "INSERT INTO stores (user_id, name, slug) VALUES (%s, %s, %s)",
                (user_id, store_name, slug)
            )
            conn.commit()
            threading.Thread(
                target=send_rt_signup_notification,
                args=(user_id, store_name, phone),
                daemon=True,
                name=f"rt-signup-push-{user_id}",
            ).start()
            flash("تم استلام طلبك بنجاح! سيتم تفعيل الحساب من قبل الإدارة قريباً.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            logging.error(f"Register Error: {e}")
            flash("فشل التسجيل: رقم الهاتف أو اسم المتجر مستخدم بالفعل.", "error")
        finally:
            conn.close()
    return render_template(
        'register.html',
        selected_plan=selected_plan,
        selected_plan_label=signup_plans[selected_plan],
    )

@app.route('/moeen-executive/register', methods=['GET', 'POST'])
def moeen_public_register():
    if request.method == 'POST':
        full_name = (request.form.get('full_name') or '').strip()
        job_title = (request.form.get('job_title') or '').strip()
        phone = re.sub(r'\s+', '', (request.form.get('phone') or '').strip())
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        password_confirm = request.form.get('password_confirm') or ''
        terms_accepted = request.form.get('terms_accepted') == 'yes'

        if len(full_name) < 3 or len(phone) < 7:
            flash("يرجى إدخال الاسم ورقم الهاتف بصورة صحيحة.", "error")
            return render_template('moeen_register.html')
        if len(password) < 12:
            flash("يجب أن تتكون كلمة المرور من 12 حرفًا على الأقل.", "error")
            return render_template('moeen_register.html')
        if password != password_confirm:
            flash("كلمتا المرور غير متطابقتين.", "error")
            return render_template('moeen_register.html')
        if not terms_accepted:
            flash("يجب الموافقة على شروط الاستخدام وسياسة الخصوصية لإنشاء الحساب.", "error")
            return render_template('moeen_register.html')

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO moeen_accounts
                    (full_name, job_title, phone, email, password_hash, status,
                     plan_type, subscription_start, subscription_end,
                     must_change_password, terms_accepted_at, terms_version)
                VALUES (%s, %s, %s, %s, %s, 'active', 'trial',
                        NOW(), NOW() + INTERVAL '48 hours', FALSE, NOW(), %s)
                RETURNING id
            """, (
                full_name, job_title or None, phone, email or None,
                generate_password_hash(password, method='scrypt'),
                MOEEN_TERMS_VERSION,
            ))
            account_id = cursor.fetchone()["id"]
            conn.commit()
            threading.Thread(
                target=send_moeen_signup_notifications,
                args=(account_id, full_name, job_title),
                daemon=True,
                name=f"moeen-signup-push-{account_id}",
            ).start()
            return redirect(url_for('moeen_multi.index', registered='1'))
        except Exception as exc:
            conn.rollback()
            logging.warning("public Moeen registration failed: %s", exc)
            flash("تعذر إنشاء الحساب. قد يكون رقم الهاتف مستخدمًا بالفعل.", "error")
        finally:
            cursor.close()
            conn.close()

    return render_template('moeen_register.html')

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
    shipping_integration = None
    subscription_payments = []
    latest_order_id = 0
    pending_order_count = 0
    if store:
                # جلب المنتجات النشطة فقط (التي لم يتم إخفاؤها)
                # التاجر يرى جميع المنتجات (المخفي والمتوفر)
        
        cursor.execute("SELECT * FROM products WHERE store_id = %s ORDER BY id DESC", (store['id'],))
        products = cursor.fetchall()

        cursor.execute("""
            SELECT od.*,
                   ss.parcel_code,
                   ss.qr_code,
                   ss.shipping_status_id,
                   ss.shipping_status_name,
                   ss.shipping_position_id,
                   ss.shipping_cost,
                   ss.city_id AS shipping_city_id,
                   ss.village_id AS shipping_village_id,
                   ss.street_name AS shipping_street_name,
                   ss.last_error AS shipping_last_error
            FROM order_drafts od
            LEFT JOIN shipping_shipments ss
              ON ss.order_id = od.id AND ss.provider = 'shiply'
            WHERE od.store_id = %s
            ORDER BY od.created_at DESC
        """, (store['id'],))
        orders = cursor.fetchall()
        if orders:
            latest_order_id = max(order['id'] for order in orders)
            pending_order_count = sum(1 for order in orders if order['status'] == 'sent')

        cursor.execute("""
            SELECT enabled, environment, country,
                   (api_key_encrypted IS NOT NULL) AS has_api_key,
                   webhook_configured,
                   last_tested_at, last_test_success, last_error
            FROM shipping_integrations
            WHERE store_id = %s AND provider = 'shiply'
        """, (store['id'],))
        shipping_integration = cursor.fetchone()

        cursor.execute("""
            SELECT *
            FROM subscription_payments
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 8
        """, (user_id,))
        subscription_payments = cursor.fetchall()

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

        analytics_periods = []
        period_defs = [
            ('today', 'اليوم', "sv.visit_date = CURRENT_DATE", "od.created_at::date = CURRENT_DATE"),
            ('week', 'آخر 7 أيام', "sv.visit_date >= CURRENT_DATE - INTERVAL '6 days'", "od.created_at >= NOW() - INTERVAL '7 days'"),
            ('month', 'آخر 30 يوم', "sv.visit_date >= CURRENT_DATE - INTERVAL '29 days'", "od.created_at >= NOW() - INTERVAL '30 days'"),
            ('all', 'كل الوقت', "TRUE", "TRUE"),
        ]
        for period_key, period_label, visit_where, order_where in period_defs:
            cursor.execute(f"""
                SELECT COUNT(DISTINCT sv.visitor_key) AS visits
                FROM store_visits sv
                WHERE sv.store_id = %s AND {visit_where}
            """, (store['id'],))
            visits = cursor.fetchone()['visits'] or 0
            cursor.execute(f"""
                SELECT
                    COUNT(*) AS total_orders,
                    COUNT(*) FILTER (WHERE od.status = 'confirmed') AS confirmed_orders,
                    COALESCE(SUM(od.grand_total) FILTER (WHERE od.status = 'confirmed'), 0) AS confirmed_value
                FROM order_drafts od
                WHERE od.store_id = %s AND {order_where}
            """, (store['id'],))
            order_row = cursor.fetchone()
            analytics_periods.append({
                'key': period_key,
                'label': period_label,
                'visits': visits,
                'total_orders': order_row['total_orders'] or 0,
                'confirmed_orders': order_row['confirmed_orders'] or 0,
                'confirmed_value': order_row['confirmed_value'] or 0,
            })

        cursor.execute("""
            SELECT COALESCE(source, 'unknown') AS source, COUNT(DISTINCT visitor_key) AS visits
            FROM store_visits
            WHERE store_id = %s AND visit_date >= CURRENT_DATE - INTERVAL '29 days'
            GROUP BY COALESCE(source, 'unknown')
            ORDER BY visits DESC
            LIMIT 8
        """, (store['id'],))
        traffic_sources = attach_traffic_labels(cursor.fetchall())

        analytics = {
            'page_views_7d': last7,
            'page_views_30d': last30,
            'top_products_30d': top5,
            'add_to_cart_30d': adds,
            'whatsapp_30d': ws,
            'periods': analytics_periods,
            'traffic_sources_30d': traffic_sources,
        }

    edit_product = None
    edit_product_images = []
    edit_id = request.args.get('edit')
    if edit_id and store:
        cursor.execute("SELECT * FROM products WHERE id = %s AND store_id = %s", (edit_id, store['id']))
        edit_product = cursor.fetchone()
        if edit_product and store.get('product_gallery_enabled'):
            cursor.execute("""
                SELECT id, image_url, sort_order
                FROM product_images
                WHERE product_id = %s
                ORDER BY sort_order, id
            """, (edit_product['id'],))
            edit_product_images = cursor.fetchall()

    conn.close()
    from themes import ENHANCED_THEMES, THEME_COLLECTIONS, rgb_to_hex
    theme_labels = {
        'gold': 'ذهبي دافئ',
        'black': 'أسود كلاسيكي',
        'ocean': 'أزرق بحري',
        'royal': 'ملكي بنفسجي',
        'earth': 'أرضي طبيعي',
        'minimal_light': 'فاتح بسيط',
        'minimal_black': 'أسود بسيط',
        'minimal_gray': 'رمادي هادئ',
        'minimal_sage': 'أخضر سيج',
        'minimal_stone': 'حجري ناعم',
        'luxury_dark': 'داكن فاخر',
        'luxury_pearl': 'لؤلؤي راقي',
        'luxury_rose_gold': 'وردي ذهبي',
        'luxury_champagne': 'شمبانيا فاخر',
        'luxury_emerald': 'زمردي فاخر',
        'luxury_sapphire': 'ياقوت أزرق',
        'vibrant_red': 'أحمر جريء',
        'vibrant_pink': 'وردي حيوي',
        'vibrant_orange': 'برتقالي مشرق',
        'vibrant_green': 'أخضر حيوي',
        'vibrant_purple': 'بنفسجي حيوي',
        'dark_elegant': 'كحلي أنيق',
        'dark_smoke': 'دخاني داكن',
        'dark_carbon': 'كربون داكن',
        'dark_midnight': 'منتصف الليل',
        'dark_slate': 'رصاصي داكن',
        'soft_blush': 'خدود وردية',
        'soft_sage': 'سيج ناعم',
        'soft_lavender': 'لافندر ناعم',
        'soft_peach': 'خوخي ناعم',
        'soft_mint': 'نعناع ناعم',
        'industrial_steel': 'فولاذي',
        'industrial_copper': 'نحاسي',
        'industrial_bronze': 'برونزي',
        'industrial_gunmetal': 'معدني داكن',
        'neon_cyan': 'نيون سماوي',
        'neon_magenta': 'نيون وردي',
        'neon_lime': 'نيون أخضر',
    }
    theme_list = []
    for coll_key, coll_data in THEME_COLLECTIONS.items():
        themes_in_coll = []
        for t in coll_data['themes']:
            if t in ENHANCED_THEMES:
                colors = ENHANCED_THEMES[t]
                themes_in_coll.append({
                    'name': t,
                    'label': theme_labels.get(t, t.replace('_', ' ')),
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
        edit_product_images=edit_product_images,
        orders=orders,
        analytics=analytics,
        shipping_integration=shipping_integration,
        subscription_payments=subscription_payments,
        subscription_plans=SUBSCRIPTION_PLANS,
        payment_methods=PAYMENT_METHOD_LABELS,
        payment_settings=get_payment_settings(),
        latest_order_id=latest_order_id,
        pending_order_count=pending_order_count,
        push_configured=bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY),
        vapid_public_key=VAPID_PUBLIC_KEY,
        theme_list=theme_list,
        store_backgrounds=STORE_BACKGROUNDS
    )

@app.route('/admin/subscription-payment', methods=['POST'])
def admin_subscription_payment():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM stores WHERE user_id = %s", (user_id,))
        store = cursor.fetchone()
        if not store:
            flash("لا يوجد متجر مرتبط بالحساب.", "error")
            return redirect(url_for('admin', active_tab='settings'))

        plan_type = request.form.get('plan_type', 'monthly')
        if plan_type not in SUBSCRIPTION_PLANS:
            flash("الباقة المختارة غير صحيحة.", "error")
            return redirect(url_for('admin', active_tab='settings'))

        payment_method = request.form.get('payment_method', 'wallet')
        if payment_method not in PAYMENT_METHOD_LABELS:
            flash("طريقة الدفع غير صحيحة.", "error")
            return redirect(url_for('admin', active_tab='settings'))

        transaction_ref = (request.form.get('transaction_ref') or '').strip()
        notes = (request.form.get('notes') or '').strip()
        receipt = request.files.get('receipt')
        receipt_url = None

        if receipt and receipt.filename:
            if not allowed_receipt_file(receipt.filename):
                flash("صيغة الإيصال غير مدعومة. استخدم صورة أو PDF.", "error")
                return redirect(url_for('admin', active_tab='settings'))
            receipt_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'payment_receipts')
            os.makedirs(receipt_dir, exist_ok=True)
            ext = secure_filename(receipt.filename).rsplit('.', 1)[1].lower()
            receipt_filename = f"receipt_{user_id}_{uuid.uuid4().hex[:10]}.{ext}"
            receipt.save(os.path.join(receipt_dir, receipt_filename))
            receipt_url = f"payment_receipts/{receipt_filename}"

        if not transaction_ref and not receipt_url:
            flash("أدخل رقم العملية أو ارفع صورة الإيصال حتى نتمكن من مراجعة الدفع.", "error")
            return redirect(url_for('admin', active_tab='settings'))

        plan = get_subscription_plan(plan_type)
        invoice_code = make_invoice_code(user_id)
        cursor.execute("""
            INSERT INTO subscription_payments (
                user_id, store_id, invoice_code, plan_type, amount, currency,
                payment_method, transaction_ref, receipt_url, notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, store['id'], invoice_code, plan_type, plan['amount'], plan['currency'],
            payment_method, transaction_ref or None, receipt_url, notes or None
        ))
        conn.commit()
        threading.Thread(
            target=send_rt_payment_notification,
            args=(invoice_code, store['name'], plan['label']),
            daemon=True,
            name=f"rt-payment-push-{invoice_code}",
        ).start()
        flash(f"تم إرسال إثبات الدفع بنجاح. رقم الفاتورة: {invoice_code}", "success")
    except Exception as exc:
        conn.rollback()
        logging.exception("Subscription payment proof failed")
        flash("تعذر إرسال إثبات الدفع حالياً. حاول مرة أخرى.", "error")
    finally:
        conn.close()

    return redirect(url_for('admin', active_tab='settings'))

@app.post('/moeen-executive/subscription-payment')
def moeen_subscription_payment():
    account_id = session.get('moeen_account_id')
    if not account_id:
        return jsonify(error="AUTH_REQUIRED"), 401
    if request.headers.get("X-CSRF-Token") != session.get("moeen_csrf"):
        return jsonify(error="INVALID_CSRF"), 403

    plan_type = (request.form.get('plan_type') or 'monthly').strip()
    payment_method = (request.form.get('payment_method') or 'reflect').strip()
    if plan_type not in MOEEN_SUBSCRIPTION_PLANS or payment_method not in {'reflect', 'iban'}:
        return jsonify(error="INVALID_PAYMENT_DATA"), 400

    transaction_ref = (request.form.get('transaction_ref') or '').strip()[:160]
    notes = (request.form.get('notes') or '').strip()[:1000]
    receipt = request.files.get('receipt')
    receipt_url = None
    if receipt and receipt.filename:
        if not allowed_receipt_file(receipt.filename):
            return jsonify(error="INVALID_RECEIPT"), 400
        receipt_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'moeen_payment_receipts')
        os.makedirs(receipt_dir, exist_ok=True)
        ext = secure_filename(receipt.filename).rsplit('.', 1)[1].lower()
        filename = f"moeen_{account_id}_{uuid.uuid4().hex[:10]}.{ext}"
        receipt.save(os.path.join(receipt_dir, filename))
        receipt_url = f"moeen_payment_receipts/{filename}"
    if not transaction_ref and not receipt_url:
        return jsonify(error="PROOF_REQUIRED"), 400

    plan = MOEEN_SUBSCRIPTION_PLANS[plan_type]
    invoice_code = f"MOEEN-{datetime.utcnow().strftime('%Y%m%d')}-{account_id}-{uuid.uuid4().hex[:6].upper()}"
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT full_name FROM moeen_accounts WHERE id=%s", (account_id,))
        account = cursor.fetchone()
        if not account:
            return jsonify(error="ACCOUNT_NOT_FOUND"), 404
        cursor.execute("""
            INSERT INTO moeen_subscription_payments
                (account_id, invoice_code, plan_type, amount, currency,
                 payment_method, transaction_ref, receipt_url, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            account_id, invoice_code, plan_type, plan['amount'], plan['currency'],
            payment_method, transaction_ref or None, receipt_url, notes or None,
        ))
        conn.commit()
        threading.Thread(
            target=send_moeen_payment_notification,
            args=(invoice_code, account['full_name'], plan['label']),
            daemon=True,
            name=f"moeen-payment-push-{invoice_code}",
        ).start()
        return jsonify(ok=True, invoice_code=invoice_code)
    except Exception:
        conn.rollback()
        logging.exception("Moeen payment proof failed")
        return jsonify(error="PAYMENT_SUBMISSION_FAILED"), 500
    finally:
        cursor.close()
        conn.close()

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
    new_original_filename = None
    new_processed_filename = None
    new_gallery_filenames = []
    try:
        cursor.execute("""
            SELECT p.id, s.product_gallery_enabled
            FROM products p
            JOIN stores s ON s.id = p.store_id
            WHERE p.id = %s AND s.user_id = %s
        """, (id, user_id))
        owned_product = cursor.fetchone()
        if not owned_product:
            flash("المنتج غير موجود أو لا تملك صلاحية تعديله.", "error")
            return redirect(url_for('admin'))

        replacement_image = request.files.get('replacement_image')
        if replacement_image and replacement_image.filename:
            unique_id = uuid.uuid4().hex[:10]
            new_original_filename = f"orig_edit_{unique_id}.png"
            new_processed_filename = f"processed_edit_{unique_id}.png"
            original_path = os.path.join(app.config['UPLOAD_FOLDER'], new_original_filename)
            processed_path = os.path.join(app.config['UPLOAD_FOLDER'], new_processed_filename)

            with Image.open(replacement_image.stream) as source:
                source = ImageOps.exif_transpose(source).convert('RGBA')
                source.thumbnail((2000, 2000), Image.LANCZOS)
                source.save(original_path, 'PNG', optimize=True)

            keep_replacement_original = request.form.get('keep_replacement_original') == '1'
            if keep_replacement_original:
                with Image.open(original_path) as source:
                    source = source.convert('RGBA')
                    source.thumbnail((1600, 1600), Image.LANCZOS)
                    source.save(processed_path, 'PNG', optimize=True)
            else:
                output_data, engine_used = remove_bg_with_fallback(original_path)
                logging.info(f"Replacement image background removed using: {engine_used}")
                standardize_cutout(output_data, processed_path, size=1200)

        gallery_uploads = [
            image for image in request.files.getlist('gallery_images')
            if image and image.filename
        ]
        if gallery_uploads:
            if not owned_product.get('product_gallery_enabled'):
                raise ValueError("معرض الصور غير مفعل لهذا المتجر.")

            cursor.execute("SELECT COUNT(*) AS count FROM product_images WHERE product_id = %s", (id,))
            gallery_count = cursor.fetchone()['count']
            available_slots = max(0, 5 - gallery_count)
            if len(gallery_uploads) > available_slots:
                raise ValueError(f"يمكن إضافة {available_slots} صور إضافية فقط لهذا المنتج.")

            cursor.execute(
                "SELECT COALESCE(MAX(sort_order), -1) AS max_order FROM product_images WHERE product_id = %s",
                (id,)
            )
            next_sort_order = cursor.fetchone()['max_order'] + 1

            for offset, gallery_upload in enumerate(gallery_uploads):
                gallery_filename = f"gallery_{id}_{uuid.uuid4().hex[:10]}.jpg"
                gallery_path = os.path.join(app.config['UPLOAD_FOLDER'], gallery_filename)
                with Image.open(gallery_upload.stream) as source:
                    source = ImageOps.exif_transpose(source).convert('RGB')
                    source.thumbnail((1800, 1800), Image.LANCZOS)
                    source.save(gallery_path, 'JPEG', quality=88, optimize=True)
                new_gallery_filenames.append(gallery_filename)
                cursor.execute("""
                    INSERT INTO product_images (product_id, image_url, sort_order)
                    VALUES (%s, %s, %s)
                """, (id, gallery_filename, next_sort_order + offset))

        cursor.execute("""
            UPDATE products SET name=%s, price=%s, original_price=%s, discount_reason=%s, description=%s, theme=%s, template_style=%s, category=%s, active=%s, variants=%s, bundles=%s
            WHERE id=%s AND store_id = (SELECT id FROM stores WHERE user_id=%s)
        """, (name, price, original_price, discount_reason, description, theme, template_style, category, active,
               request.form.get('variants', '').strip() or None,
               request.form.get('bundles', '').strip() or None,
               id, user_id))
        if new_processed_filename:
            cursor.execute("""
                UPDATE products
                SET original_image_url=%s,
                    processed_image_url=%s,
                    final_image_url=NULL,
                    background='none'
                WHERE id=%s
                  AND store_id = (SELECT id FROM stores WHERE user_id=%s)
            """, (new_original_filename, new_processed_filename, id, user_id))
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
        for filename in (new_original_filename, new_processed_filename, *new_gallery_filenames):
            if filename:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                except OSError:
                    pass
        logging.error(f"Edit Product Error: {e}")
        flash(str(e) if isinstance(e, ValueError) else "تعذر حفظ التحديثات. تحقق من القيم.", "error")
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

# =========================
# Product Gallery API
# =========================
@app.route('/api/product/<int:product_id>/gallery/<int:image_id>/delete', methods=['POST'])
def delete_product_gallery_image(product_id, image_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'unauthorized'}), 401

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT pi.image_url
        FROM product_images pi
        JOIN products p ON p.id = pi.product_id
        JOIN stores s ON s.id = p.store_id
        WHERE pi.id = %s AND pi.product_id = %s AND s.user_id = %s
    """, (image_id, product_id, user_id))
    image = cur.fetchone()
    if not image:
        conn.close()
        return jsonify({'error': 'not found'}), 404

    cur.execute("DELETE FROM product_images WHERE id = %s", (image_id,))
    cur.execute("""
        WITH ordered AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY sort_order, id) - 1 AS new_order
            FROM product_images WHERE product_id = %s
        )
        UPDATE product_images pi
        SET sort_order = ordered.new_order
        FROM ordered
        WHERE pi.id = ordered.id
    """, (product_id,))
    conn.commit()
    conn.close()

    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], image['image_url']))
    except OSError:
        pass
    return jsonify({'success': True})


@app.route('/api/product/<int:product_id>/gallery/<int:image_id>/move', methods=['POST'])
def move_product_gallery_image(product_id, image_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'unauthorized'}), 401
    direction = (request.get_json(silent=True) or {}).get('direction')
    if direction not in ('up', 'down'):
        return jsonify({'error': 'invalid direction'}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT pi.id, pi.sort_order
        FROM product_images pi
        JOIN products p ON p.id = pi.product_id
        JOIN stores s ON s.id = p.store_id
        WHERE pi.id = %s AND pi.product_id = %s AND s.user_id = %s
    """, (image_id, product_id, user_id))
    current = cur.fetchone()
    if not current:
        conn.close()
        return jsonify({'error': 'not found'}), 404

    operator = '<' if direction == 'up' else '>'
    ordering = 'DESC' if direction == 'up' else 'ASC'
    cur.execute(f"""
        SELECT id, sort_order
        FROM product_images
        WHERE product_id = %s AND sort_order {operator} %s
        ORDER BY sort_order {ordering}, id {ordering}
        LIMIT 1
    """, (product_id, current['sort_order']))
    neighbour = cur.fetchone()
    if neighbour:
        temporary_order = -1000000 - image_id
        cur.execute("UPDATE product_images SET sort_order = %s WHERE id = %s", (temporary_order, current['id']))
        cur.execute("UPDATE product_images SET sort_order = %s WHERE id = %s", (current['sort_order'], neighbour['id']))
        cur.execute("UPDATE product_images SET sort_order = %s WHERE id = %s", (neighbour['sort_order'], current['id']))
        conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/product/<int:product_id>/gallery/<int:image_id>/primary', methods=['POST'])
def set_product_gallery_primary(product_id, image_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'unauthorized'}), 401

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT pi.image_url,
                   COALESCE(p.final_image_url, p.processed_image_url) AS current_main
            FROM product_images pi
            JOIN products p ON p.id = pi.product_id
            JOIN stores s ON s.id = p.store_id
            WHERE pi.id = %s AND pi.product_id = %s AND s.user_id = %s
              AND s.product_gallery_enabled = TRUE
            FOR UPDATE
        """, (image_id, product_id, user_id))
        selected = cur.fetchone()
        if not selected:
            return jsonify({'error': 'not found'}), 404
        if not selected.get('current_main'):
            return jsonify({'error': 'main image missing'}), 409

        cur.execute("""
            UPDATE products
            SET original_image_url = %s,
                processed_image_url = %s,
                final_image_url = NULL,
                background = 'none'
            WHERE id = %s
        """, (selected['image_url'], selected['image_url'], product_id))
        cur.execute(
            "UPDATE product_images SET image_url = %s WHERE id = %s",
            (selected['current_main'], image_id)
        )
        conn.commit()
        return jsonify({'success': True})
    except Exception as exc:
        conn.rollback()
        logging.error(f"Set gallery primary error: {exc}")
        return jsonify({'error': 'تعذر تغيير الصورة الرئيسية'}), 500
    finally:
        conn.close()

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
            traffic_source, traffic_source_url = detect_traffic_source()
            record_store_visit(store['id'], visitor_key, 'store', traffic_source, traffic_source_url)
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

    product_images = []
    if store.get('product_gallery_enabled'):
        cursor.execute("""
            SELECT id, image_url, sort_order
            FROM product_images
            WHERE product_id = %s
            ORDER BY sort_order, id
        """, (product_id,))
        product_images = cursor.fetchall()
    
    # Record product view
    try:
        visitor_key = get_public_visitor_key(store)
        if visitor_key:
            from database import record_store_visit
            traffic_source, traffic_source_url = detect_traffic_source()
            record_store_visit(store['id'], visitor_key, 'product', traffic_source, traffic_source_url)
    except Exception:
        pass
    
    available = is_available(store, product)
    
    conn.close()
    return render_template('product.html', 
                          store=store, 
                          product=product, 
                          product_images=product_images,
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

    customer_phone = normalize_customer_phone(
        data.get("customer_phone_prefix"),
        data.get("customer_phone")
    )
    customer = {
        "name": data.get("customer_name"),
        "phone": customer_phone,
        "address": data.get("customer_address"),
        "notes": data.get("customer_notes"),
    }
    # صمام أمان السيرفر: منع تسجيل الطلب إذا كانت البيانات الأساسية مفقودة
    if not customer["name"] or not customer["phone"] or not customer["address"]:
        if not customer_phone and data.get("customer_phone"):
            return jsonify({"error": "رقم الهاتف غير صحيح. اختر مفتاح الدولة واكتب الرقم المحلي دون مفتاح مكرر."}), 400
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
            INSERT INTO order_drafts (
                store_id, subtotal, grand_total, customer_name, customer_phone,
                customer_address, customer_notes, wa_text, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'sent') RETURNING id
        """, (
            store_id, subtotal, subtotal, customer.get('name'), customer.get('phone'),
            customer.get('address'), customer.get('notes'), wa_text
        ))
        order_id = cur.fetchone()['id']
        for l in lines:
            cur.execute("""
                INSERT INTO order_lines (order_id, product_id, sku, name_snapshot, unit_price, qty, line_total)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (order_id, l["product_id"], l["sku"], l["name"], l["unit_price"], l["qty"], l["line_total"]))

        cur.execute("INSERT INTO analytics_events(store_id, event_name) VALUES (%s, 'whatsapp_sent')", (store_id,))
        conn.commit()

        try:
            threading.Thread(
                target=send_order_push_notifications,
                args=(
                    store['id'],
                    store['name'],
                    store['slug'],
                    order_id,
                    subtotal,
                    store.get('currency') or '₪',
                ),
                daemon=True,
                name=f"order-push-{order_id}",
            ).start()
        except Exception as push_error:
            logging.warning(f"Order {order_id} saved, but push dispatch failed: {push_error}")

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


@app.get("/admin/orders/notification-state")
def admin_order_notification_state():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "غير مصرّح"}), 401
    store = get_store_by_user(user_id)
    if not store:
        return jsonify({"error": "لا يوجد متجر مرتبط"}), 404

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT
                COALESCE(MAX(id), 0) AS latest_order_id,
                COUNT(*) FILTER (WHERE status = 'sent') AS pending_count
            FROM order_drafts
            WHERE store_id = %s
        """, (store['id'],))
        state = cur.fetchone()
        cur.execute("""
            SELECT id, grand_total, created_at
            FROM order_drafts
            WHERE store_id = %s
            ORDER BY id DESC
            LIMIT 1
        """, (store['id'],))
        latest = cur.fetchone()
        return jsonify({
            "latest_order_id": state['latest_order_id'] or 0,
            "pending_count": state['pending_count'] or 0,
            "latest_total": float(latest['grand_total']) if latest else 0,
            "currency": store.get('currency') or '₪',
        })
    finally:
        conn.close()


@app.post("/admin/push/subscribe")
def subscribe_admin_push():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "غير مصرّح"}), 401
    if not (VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY):
        return jsonify({"error": "خدمة إشعارات الهاتف غير مضبوطة بعد"}), 503

    store = get_store_by_user(user_id)
    if not store:
        return jsonify({"error": "لا يوجد متجر مرتبط"}), 404

    data = request.get_json(silent=True) or {}
    endpoint = str(data.get('endpoint') or '').strip()
    keys = data.get('keys') or {}
    p256dh = str(keys.get('p256dh') or '').strip()
    auth = str(keys.get('auth') or '').strip()
    if not endpoint.startswith('https://') or not p256dh or not auth:
        return jsonify({"error": "بيانات اشتراك الإشعارات غير صالحة"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO push_subscriptions (
                store_id, endpoint, p256dh, auth, user_agent, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (endpoint) DO UPDATE SET
                store_id = EXCLUDED.store_id,
                p256dh = EXCLUDED.p256dh,
                auth = EXCLUDED.auth,
                user_agent = EXCLUDED.user_agent,
                updated_at = NOW()
        """, (
            store['id'], endpoint, p256dh, auth,
            request.headers.get('User-Agent', '')[:500],
        ))
        conn.commit()
        return jsonify({"ok": True})
    except Exception:
        conn.rollback()
        logging.exception("Failed to save push subscription")
        return jsonify({"error": "تعذر حفظ اشتراك الإشعارات"}), 500
    finally:
        conn.close()


@app.post("/admin/push/unsubscribe")
def unsubscribe_admin_push():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "غير مصرّح"}), 401
    store = get_store_by_user(user_id)
    if not store:
        return jsonify({"error": "لا يوجد متجر مرتبط"}), 404

    endpoint = str((request.get_json(silent=True) or {}).get('endpoint') or '').strip()
    if not endpoint:
        return jsonify({"error": "اشتراك غير صالح"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM push_subscriptions WHERE store_id = %s AND endpoint = %s",
            (store['id'], endpoint)
        )
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


# =========================
# Optional Shipping Integrations
# =========================
@app.post("/admin/shipping/shiply/settings")
def save_shiply_settings():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    store = get_store_by_user(user_id)
    if not store:
        flash("لا يوجد متجر مرتبط بهذا الحساب.", "error")
        return redirect(url_for('admin', active_tab='settings'))

    enabled = request.form.get('enabled') in ('on', 'true', '1')
    environment = request.form.get('environment', 'testing')
    country = request.form.get('country', 'palestine')
    api_key = (request.form.get('api_key') or '').strip()
    if environment not in ('testing', 'production'):
        environment = 'testing'
    if country not in ('palestine', 'jordan'):
        country = 'palestine'

    try:
        encrypted_key = encrypt_api_key(api_key) if api_key else None
    except Exception as exc:
        logging.error(f"encrypt shipping key error: {exc}")
        flash("تعذر تشفير مفتاح Shiply. تحقق من إعداد مفتاح التشفير في الخادم.", "error")
        return redirect(url_for('admin', active_tab='settings'))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if enabled and not encrypted_key:
            cursor.execute("""
                SELECT api_key_encrypted FROM shipping_integrations
                WHERE store_id = %s AND provider = 'shiply'
            """, (store['id'],))
            existing = cursor.fetchone()
            if not existing or not existing.get('api_key_encrypted'):
                flash("أدخل مفتاح Shiply قبل تفعيل الربط.", "error")
                return redirect(url_for('admin', active_tab='settings'))

        cursor.execute("""
            INSERT INTO shipping_integrations (
                store_id, provider, enabled, environment, country, api_key_encrypted, updated_at
            )
            VALUES (%s, 'shiply', %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (store_id, provider)
            DO UPDATE SET
                enabled = EXCLUDED.enabled,
                environment = EXCLUDED.environment,
                country = EXCLUDED.country,
                api_key_encrypted = COALESCE(
                    EXCLUDED.api_key_encrypted,
                    shipping_integrations.api_key_encrypted
                ),
                updated_at = CURRENT_TIMESTAMP
        """, (store['id'], enabled, environment, country, encrypted_key))
        conn.commit()
        flash("تم حفظ إعدادات Shiply. اختبر الاتصال قبل استخدامها.", "success")
    except Exception as exc:
        conn.rollback()
        logging.error(f"save_shiply_settings error: {exc}")
        flash("تعذر حفظ إعدادات Shiply.", "error")
    finally:
        conn.close()
    return redirect(url_for('admin', active_tab='settings'))


@app.post("/admin/shipping/shiply/test")
def test_shiply_connection():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "غير مصرّح"}), 401
    store = get_store_by_user(user_id)
    if not store:
        return jsonify({"error": "لا يوجد متجر مرتبط"}), 400

    success = False
    error = None
    try:
        _, client = get_shiply_integration(store['id'], require_enabled=False)
        cities = client.cities()
        success = isinstance(cities, list)
        if not success:
            error = "لم تعد Shiply قائمة مدن صالحة"
        else:
            webhook_conn = get_db_connection()
            webhook_cursor = webhook_conn.cursor()
            try:
                webhook_cursor.execute("""
                    SELECT webhook_token FROM shipping_integrations
                    WHERE store_id = %s AND provider = 'shiply'
                """, (store['id'],))
                row = webhook_cursor.fetchone()
                webhook_token = row.get('webhook_token') if row else None
                if not webhook_token:
                    webhook_token = uuid.uuid4().hex + uuid.uuid4().hex
                    webhook_cursor.execute("""
                        UPDATE shipping_integrations
                        SET webhook_token = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE store_id = %s AND provider = 'shiply'
                    """, (webhook_token, store['id']))
                    webhook_conn.commit()
            finally:
                webhook_conn.close()
            client.update_webhook(
                url_for('shiply_webhook', token=webhook_token, _external=True)
            )
    except Exception as exc:
        error = str(exc)
        success = False

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE shipping_integrations
            SET last_tested_at = CURRENT_TIMESTAMP,
                last_test_success = %s,
                last_error = %s,
                webhook_configured = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE store_id = %s AND provider = 'shiply'
        """, (success, error, success, store['id']))
        conn.commit()
    finally:
        conn.close()

    if not success:
        return jsonify({"error": error or "فشل اختبار الاتصال"}), 400
    return jsonify({"ok": True, "message": "تم الاتصال بـ Shiply بنجاح"})


@app.get("/admin/shipping/shiply/cities")
def shiply_cities():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "غير مصرّح"}), 401
    store = get_store_by_user(user_id)
    if not store:
        return jsonify({"error": "لا يوجد متجر مرتبط"}), 400
    try:
        _, client = get_shiply_integration(store['id'])
        return jsonify({"ok": True, "cities": client.cities()})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/admin/shipping/shiply/fees")
def shiply_fees():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "غير مصرّح"}), 401
    store = get_store_by_user(user_id)
    if not store:
        return jsonify({"error": "لا يوجد متجر مرتبط"}), 400
    data = request.get_json(silent=True) or {}
    try:
        village_id = int(data.get('village_id'))
        price = float(data.get('price') or 0)
        _, client = get_shiply_integration(store['id'])
        return jsonify({"ok": True, **client.fees(village_id, price)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/admin/orders/<int:order_id>/shiply/create")
def create_shiply_shipment(order_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "غير مصرّح"}), 401
    store = get_store_by_user(user_id)
    if not store:
        return jsonify({"error": "لا يوجد متجر مرتبط"}), 400
    data = request.get_json(silent=True) or {}

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (order_id,))
        cursor.execute("""
            SELECT od.*,
                   COALESCE(
                       string_agg(ol.name_snapshot || ' x' || ol.qty::text, ', ' ORDER BY ol.id),
                       'طلب متجر'
                   ) AS contents_description
            FROM order_drafts od
            LEFT JOIN order_lines ol ON ol.order_id = od.id
            WHERE od.id = %s AND od.store_id = %s
            GROUP BY od.id
        """, (order_id, store['id']))
        order = cursor.fetchone()
        if not order:
            return jsonify({"error": "الطلب غير موجود"}), 404
        if order.get('status') != 'confirmed':
            return jsonify({"error": "يجب تأكيد الطلب قبل إرساله للشحن"}), 400

        cursor.execute("""
            SELECT parcel_code FROM shipping_shipments
            WHERE order_id = %s AND provider = 'shiply'
        """, (order_id,))
        existing = cursor.fetchone()
        if existing and existing.get('parcel_code'):
            return jsonify({"error": "تم إنشاء شحنة Shiply لهذا الطلب مسبقًا"}), 409

        city_id = int(data.get('city_id'))
        village_id = int(data.get('village_id'))
        street_name = (data.get('street_name') or order.get('customer_address') or '').strip()
        description = (data.get('description') or order.get('contents_description') or 'طلب متجر').strip()[:255]
        if not street_name:
            return jsonify({"error": "العنوان التفصيلي مطلوب"}), 400
        if len(description) < 3:
            return jsonify({"error": "وصف الطرد يجب أن يكون 3 أحرف على الأقل"}), 400

        integration, client = get_shiply_integration(store['id'])
        fee_data = client.fees(village_id, float(order.get('subtotal') or 0))
        shipping_cost = float(fee_data.get('delivery_cost') or 0)
        if shipping_cost <= 0:
            raise ShiplyError('تعذر اعتماد تكلفة شحن صالحة لهذه المنطقة')
        actual_price = float(order.get('subtotal') or 0)
        total_price = actual_price + shipping_cost
        if integration.get('country') == 'palestine':
            actual_price = int(round(actual_price))
            total_price = int(round(total_price))

        payload = {
            'recipient': {
                'first_name': order.get('customer_name') or 'مستلم',
                'phone': format_customer_phone_for_message(order.get('customer_phone')),
            },
            'address': {
                'city_id': city_id,
                'village_id': village_id,
                'street_name': street_name,
            },
            'total_price': total_price,
            'actual_price': actual_price,
            'description': description,
            'note': (order.get('customer_notes') or '')[:1023],
            'reference_number': str(order_id),
            'parcel_type': 1,
        }
        result = client.create_parcel(payload)
        parcel_code = result.get('parcel_code')
        if not parcel_code:
            raise ShiplyError('لم ترجع Shiply رقم شحنة')

        cursor.execute("""
            INSERT INTO shipping_shipments (
                order_id, store_id, provider, parcel_code, shipping_status_id,
                shipping_status_name, shipping_cost, city_id, village_id,
                street_name, description, provider_response, updated_at
            )
            VALUES (%s, %s, 'shiply', %s, 1, 'مسودة', %s, %s, %s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP)
            ON CONFLICT (order_id, provider)
            DO UPDATE SET
                parcel_code = EXCLUDED.parcel_code,
                shipping_status_id = EXCLUDED.shipping_status_id,
                shipping_status_name = EXCLUDED.shipping_status_name,
                shipping_cost = EXCLUDED.shipping_cost,
                city_id = EXCLUDED.city_id,
                village_id = EXCLUDED.village_id,
                street_name = EXCLUDED.street_name,
                description = EXCLUDED.description,
                provider_response = EXCLUDED.provider_response,
                last_error = NULL,
                updated_at = CURRENT_TIMESTAMP
        """, (
            order_id, store['id'], parcel_code, shipping_cost, city_id, village_id,
            street_name, description, json.dumps(result)
        ))
        conn.commit()
        return jsonify({
            "ok": True,
            "parcel_code": parcel_code,
            "shipping_cost": shipping_cost,
            "status_id": 1,
            "status_name": "مسودة",
        })
    except (ValueError, TypeError):
        conn.rollback()
        return jsonify({"error": "اختر المدينة والمنطقة بصورة صحيحة"}), 400
    except Exception as exc:
        conn.rollback()
        logging.error(f"create_shiply_shipment error: {exc}")
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


def _shiply_parcel_action(order_id, action):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "غير مصرّح"}), 401
    store = get_store_by_user(user_id)
    if not store:
        return jsonify({"error": "لا يوجد متجر مرتبط"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    shipment = None
    try:
        cursor.execute("""
            SELECT * FROM shipping_shipments
            WHERE order_id = %s AND store_id = %s AND provider = 'shiply'
        """, (order_id, store['id']))
        shipment = cursor.fetchone()
        if not shipment or not shipment.get('parcel_code'):
            return jsonify({"error": "لا توجد شحنة Shiply لهذا الطلب"}), 404

        _, client = get_shiply_integration(store['id'])
        if action == 'submit':
            result = client.submit_parcel(shipment['parcel_code'])
            status_id = result.get('status_id', 2)
            status_name = 'جاهز للإرسال'
            qr_code = result.get('qr_code')
        elif action == 'cancel':
            result = client.cancel_parcel(shipment['parcel_code'])
            status_id = result.get('parcel_status_id', 1)
            status_name = 'مسودة'
            qr_code = result.get('qr_code') or shipment.get('qr_code')
        else:
            result = client.get_parcel(shipment['parcel_code'])
            status = result.get('parcel_status') or {}
            status_id = result.get('parcel_status_id')
            status_name = status.get('ar_aliase') or status.get('en_aliase') or status.get('name')
            qr_code = result.get('qr_code')

        cursor.execute("""
            UPDATE shipping_shipments
            SET qr_code = COALESCE(%s, qr_code),
                shipping_status_id = %s,
                shipping_status_name = %s,
                shipping_position_id = %s,
                shipping_cost = COALESCE(%s, shipping_cost),
                provider_response = %s::jsonb,
                last_error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            qr_code, status_id, status_name, result.get('parcel_position_id'),
            result.get('parcel_delivery_cost'), json.dumps(result), shipment['id']
        ))
        conn.commit()
        return jsonify({
            "ok": True,
            "parcel_code": shipment['parcel_code'],
            "qr_code": qr_code,
            "status_id": status_id,
            "status_name": status_name,
        })
    except Exception as exc:
        conn.rollback()
        if shipment:
            try:
                cursor.execute("""
                    UPDATE shipping_shipments
                    SET last_error = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (str(exc)[:1000], shipment['id']))
                conn.commit()
            except Exception:
                conn.rollback()
        logging.error(f"shiply parcel {action} error: {exc}")
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@app.post("/admin/orders/<int:order_id>/shiply/submit")
def submit_shiply_shipment(order_id):
    return _shiply_parcel_action(order_id, 'submit')


@app.post("/admin/orders/<int:order_id>/shiply/cancel")
def cancel_shiply_shipment(order_id):
    return _shiply_parcel_action(order_id, 'cancel')


@app.post("/admin/orders/<int:order_id>/shiply/refresh")
def refresh_shiply_shipment(order_id):
    return _shiply_parcel_action(order_id, 'refresh')


@app.post("/webhooks/shiply/<token>")
def shiply_webhook(token):
    data = request.get_json(silent=True) or {}
    if data.get('event') != 'parcel' or not data.get('parcel_code'):
        return jsonify({"ok": True}), 200

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT store_id
            FROM shipping_integrations
            WHERE provider = 'shiply'
              AND enabled = TRUE
              AND webhook_token = %s
        """, (token,))
        integration = cursor.fetchone()
        if not integration:
            return jsonify({"error": "not found"}), 404

        cursor.execute("""
            UPDATE shipping_shipments
            SET shipping_status_id = %s,
                shipping_status_name = %s,
                shipping_position_id = %s,
                last_error = NULL,
                provider_response = %s::jsonb,
                updated_at = CURRENT_TIMESTAMP
            WHERE store_id = %s
              AND provider = 'shiply'
              AND parcel_code = %s
        """, (
            data.get('parcel_status_id'),
            SHIPLY_STATUS_NAMES.get(data.get('parcel_status_id'), 'تم تحديث الحالة'),
            data.get('parcel_position_id'),
            json.dumps(data),
            integration['store_id'],
            data.get('parcel_code'),
        ))
        conn.commit()
        return jsonify({"ok": True}), 200
    except Exception as exc:
        conn.rollback()
        logging.error(f"shiply_webhook error: {exc}")
        return jsonify({"error": "failed"}), 500
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
    from database import get_visit_stats, get_join_visit_stats, get_app_setting
    visit_stats = get_visit_stats()
    visit_stats['sources_30d'] = attach_traffic_labels(visit_stats.get('sources_30d', []))
    join_visit_stats = get_join_visit_stats()
    removebg_enabled = get_app_setting('removebg_enabled', 'true') == 'true'

    cursor.execute("SELECT COUNT(*) as count FROM users")
    t_users = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM products")
    t_products = cursor.fetchone()['count']
    cursor.execute("SELECT SUM(credits) as sum_c FROM users")
    t_credits = cursor.fetchone()['sum_c'] or 0

    order_period = request.args.get('order_period', '30')
    if order_period not in {'today', '7', '30', 'all'}:
        order_period = '30'
    try:
        order_store_id = int(request.args.get('order_store_id', '') or 0)
    except (TypeError, ValueError):
        order_store_id = 0

    order_filters = []
    order_params = []
    if order_period == 'today':
        order_filters.append("od.created_at >= CURRENT_DATE")
    elif order_period in {'7', '30'}:
        order_filters.append(f"od.created_at >= NOW() - INTERVAL '{int(order_period)} days'")
    if order_store_id:
        order_filters.append("od.store_id = %s")
        order_params.append(order_store_id)
    order_where = f"WHERE {' AND '.join(order_filters)}" if order_filters else ""

    cursor.execute(f"""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE od.status = 'sent') AS new_count,
            COUNT(*) FILTER (WHERE od.status = 'confirmed') AS confirmed_count,
            COUNT(*) FILTER (WHERE od.status = 'canceled') AS canceled_count
        FROM order_drafts od
        {order_where}
    """, tuple(order_params))
    order_summary = cursor.fetchone()
    total_orders = order_summary['total'] or 0
    confirmed_orders = order_summary['confirmed_count'] or 0
    order_stats = {
        'total': total_orders,
        'new': order_summary['new_count'] or 0,
        'confirmed': confirmed_orders,
        'canceled': order_summary['canceled_count'] or 0,
        'confirmation_rate': round((confirmed_orders / total_orders) * 100, 1) if total_orders else 0,
    }

    cursor.execute(f"""
        SELECT
            COALESCE(NULLIF(s.currency, ''), '₪') AS currency,
            COALESCE(SUM(od.grand_total), 0) AS confirmed_value
        FROM order_drafts od
        JOIN stores s ON s.id = od.store_id
        {order_where}{' AND' if order_where else ' WHERE'} od.status = 'confirmed'
        GROUP BY COALESCE(NULLIF(s.currency, ''), '₪')
        ORDER BY currency
    """, tuple(order_params))
    order_values_by_currency = cursor.fetchall()

    cursor.execute(f"""
        SELECT
            s.id,
            s.name,
            s.slug,
            COALESCE(NULLIF(s.currency, ''), '₪') AS currency,
            COUNT(od.id) AS total_orders,
            COUNT(od.id) FILTER (WHERE od.status = 'confirmed') AS confirmed_orders,
            COUNT(od.id) FILTER (WHERE od.status = 'canceled') AS canceled_orders,
            COALESCE(SUM(od.grand_total) FILTER (WHERE od.status = 'confirmed'), 0) AS confirmed_value
        FROM order_drafts od
        JOIN stores s ON s.id = od.store_id
        {order_where}
        GROUP BY s.id, s.name, s.slug
        ORDER BY total_orders DESC, confirmed_orders DESC, s.name
        LIMIT 20
    """, tuple(order_params))
    order_store_rows = cursor.fetchall()

    cursor.execute("SELECT id, name, slug FROM stores ORDER BY name")
    order_store_options = cursor.fetchall()

    cursor.execute("""
        SELECT users.*, stores.name as store_name, stores.slug as store_slug
        FROM users LEFT JOIN stores ON users.id = stores.user_id 
        ORDER BY users.created_at DESC
    """)
    users = cursor.fetchall()

    cursor.execute("""
        SELECT sp.*,
               users.phone AS user_phone,
               stores.name AS store_name,
               stores.slug AS store_slug
        FROM subscription_payments sp
        JOIN users ON users.id = sp.user_id
        LEFT JOIN stores ON stores.id = sp.store_id
        ORDER BY
            CASE WHEN sp.status = 'pending' THEN 0 ELSE 1 END,
            sp.created_at DESC
        LIMIT 30
    """)
    subscription_payments = cursor.fetchall()
    cursor.execute("""
        SELECT ma.*,
               COUNT(md.id) FILTER (WHERE md.authorized = TRUE) AS device_count,
               MAX(md.last_seen) AS last_device_activity
        FROM moeen_accounts ma
        LEFT JOIN moeen_devices md ON md.account_id = ma.id
        GROUP BY ma.id
        ORDER BY ma.created_at DESC
    """)
    moeen_accounts = cursor.fetchall()
    cursor.execute("""
        SELECT mp.*, ma.full_name, ma.phone
        FROM moeen_subscription_payments mp
        JOIN moeen_accounts ma ON ma.id = mp.account_id
        ORDER BY CASE WHEN mp.status='pending' THEN 0 ELSE 1 END, mp.created_at DESC
        LIMIT 30
    """)
    moeen_payments = cursor.fetchall()
    active_moeen_trial_count = sum(
        1 for account in moeen_accounts
        if account["status"] == "active"
        and account["plan_type"] == "trial"
        and account["subscription_end"]
        and account["subscription_end"] >= datetime.utcnow()
    )
    conn.close()

    return render_template('superadmin.html',
                           stats={'total_users': t_users, 'total_products': t_products, 'total_credits': t_credits},
                           users=users,
                           visit_stats=visit_stats,
                           join_visit_stats=join_visit_stats,
                           order_stats=order_stats,
                           order_values_by_currency=order_values_by_currency,
                           order_store_rows=order_store_rows,
                           order_store_options=order_store_options,
                           order_period=order_period,
                           order_store_id=order_store_id,
                           subscription_payments=subscription_payments,
                           moeen_accounts=moeen_accounts,
                           moeen_payments=moeen_payments,
                           moeen_subscription_plans=MOEEN_SUBSCRIPTION_PLANS,
                           active_moeen_trial_count=active_moeen_trial_count,
                           push_configured=bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY),
                           vapid_public_key=VAPID_PUBLIC_KEY,
                           subscription_plans=SUBSCRIPTION_PLANS,
                           payment_methods=PAYMENT_METHOD_LABELS,
                           payment_settings=get_payment_settings(),
                           removebg_enabled=removebg_enabled,
                           removebg_configured=bool(REMOVEBG_API_KEY),
                           now=datetime.utcnow())  # <--- هذا هو السطر الذي كان ناقصاً

@app.post('/superadmin/push/subscribe')
def superadmin_push_subscribe():
    if not session.get('is_superadmin'):
        return jsonify(error="UNAUTHORIZED"), 401
    if not (VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY):
        return jsonify(error="PUSH_NOT_CONFIGURED"), 503
    data = request.get_json(silent=True) or {}
    keys = data.get("keys") or {}
    endpoint = str(data.get("endpoint") or "").strip()
    p256dh = str(keys.get("p256dh") or "").strip()
    auth = str(keys.get("auth") or "").strip()
    if not endpoint.startswith("https://") or not p256dh or not auth:
        return jsonify(error="INVALID_SUBSCRIPTION"), 400
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO superadmin_push_subscriptions(endpoint,p256dh,auth,user_agent,updated_at)
            VALUES(%s,%s,%s,%s,NOW())
            ON CONFLICT(endpoint) DO UPDATE SET
                p256dh=EXCLUDED.p256dh,auth=EXCLUDED.auth,
                user_agent=EXCLUDED.user_agent,updated_at=NOW()
        """, (endpoint, p256dh, auth, request.headers.get("User-Agent", "")[:500]))
        conn.commit()
        return jsonify(ok=True)
    finally:
        conn.close()

@app.post('/superadmin/push/test')
def superadmin_push_test():
    if not session.get('is_superadmin'):
        return jsonify(error="UNAUTHORIZED"), 401
    result = send_superadmin_push_notification(
        "اختبار إشعارات RT Studio",
        "الإشعارات تعمل بنجاح على هذا الجهاز.",
        f"rt-studio-test-{int(time.time())}",
        "/superadmin",
    )
    if not result.get("configured"):
        return jsonify(error="PUSH_NOT_CONFIGURED"), 503
    if result.get("sent", 0) < 1:
        return jsonify(error="NO_ACTIVE_SUBSCRIPTIONS", **result), 409
    return jsonify(ok=True, **result)

@app.post('/superadmin/moeen/accounts')
def super_admin_create_moeen_account():
    if not session.get('is_superadmin'):
        return redirect(url_for('super_admin_login'))
    full_name = (request.form.get('full_name') or '').strip()
    job_title = (request.form.get('job_title') or '').strip()
    phone = (request.form.get('phone') or '').strip()
    email = (request.form.get('email') or '').strip()
    temporary_password = request.form.get('temporary_password') or ''
    plan_type = (request.form.get('plan_type') or 'monthly').strip()
    try:
        months = max(1, min(int(request.form.get('months') or 1), 36))
    except ValueError:
        months = 1
    if not full_name or not phone or len(temporary_password) < 12:
        flash("الاسم والهاتف وكلمة مرور مؤقتة من 12 حرفًا مطلوبة.", "error")
        return redirect(url_for('super_admin') + '#moeen-executive')
    start = datetime.utcnow()
    end = start + timedelta(days=30 * months)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO moeen_accounts
                (full_name, job_title, phone, email, password_hash, plan_type,
                 subscription_start, subscription_end, must_change_password)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
        """, (
            full_name, job_title or None, phone, email or None,
            generate_password_hash(temporary_password, method='scrypt'),
            plan_type, start, end,
        ))
        conn.commit()
        flash("تم إنشاء حساب مُعين التنفيذي. يجب تغيير كلمة المرور عند أول دخول.", "success")
    except Exception as exc:
        conn.rollback()
        logging.error("create Moeen account failed: %s", exc)
        flash("تعذر إنشاء الحساب. تأكد أن رقم الهاتف غير مستخدم.", "error")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('super_admin') + '#moeen-executive')

@app.post('/superadmin/moeen/accounts/<int:account_id>/subscription')
def super_admin_update_moeen_subscription(account_id):
    if not session.get('is_superadmin'):
        return redirect(url_for('super_admin_login'))
    action = (request.form.get('action') or '').strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if action == 'renew':
            plan_type = (request.form.get('plan_type') or 'monthly').strip()
            plan_days = {'monthly': 30, 'quarterly': 90, 'annual': 365}
            if plan_type not in plan_days:
                raise ValueError("unknown plan")
            cursor.execute("""
                UPDATE moeen_accounts
                SET subscription_end =
                    GREATEST(COALESCE(subscription_end, NOW()), NOW())
                    + (%s * INTERVAL '1 day'),
                    plan_type = %s,
                    status = 'active', updated_at = NOW()
                WHERE id = %s
            """, (plan_days[plan_type], plan_type, account_id))
            message = "تم تفعيل الباقة المدفوعة بعد نهاية المدة الحالية دون خسارة الوقت المتبقي."
        elif action == 'active':
            cursor.execute("""
                UPDATE moeen_accounts
                SET status = 'active',
                    plan_type = CASE WHEN plan_type = 'pending' THEN 'trial' ELSE plan_type END,
                    subscription_start = CASE WHEN plan_type = 'pending' THEN NOW() ELSE subscription_start END,
                    subscription_end = CASE WHEN plan_type = 'pending' THEN NOW() + INTERVAL '48 hours' ELSE subscription_end END,
                    updated_at = NOW()
                WHERE id = %s
            """, (account_id,))
            message = "تم تفعيل الحساب. بدأت التجربة المجانية لمدة 48 ساعة."
        elif action in {'suspended', 'cancelled'}:
            cursor.execute("""
                UPDATE moeen_accounts SET status = %s, updated_at = NOW() WHERE id = %s
            """, (action, account_id))
            message = "تم تحديث حالة الاشتراك."
        elif action == 'revoke_devices':
            cursor.execute("DELETE FROM moeen_devices WHERE account_id = %s", (account_id,))
            message = "تم إلغاء اعتماد جميع أجهزة الحساب."
        else:
            raise ValueError("unknown action")
        conn.commit()
        flash(message, "success")
    except Exception as exc:
        conn.rollback()
        logging.error("update Moeen subscription failed: %s", exc)
        flash("تعذر تحديث حساب مُعين التنفيذي.", "error")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('super_admin') + '#moeen-executive')

@app.post('/superadmin/moeen/accounts/<int:account_id>/delete')
def super_admin_delete_moeen_account(account_id):
    if not session.get('is_superadmin'):
        return redirect(url_for('super_admin_login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    receipt_paths = []
    try:
        cursor.execute("SELECT full_name FROM moeen_accounts WHERE id=%s FOR UPDATE", (account_id,))
        account = cursor.fetchone()
        if not account:
            flash("حساب مُعين غير موجود.", "error")
            return redirect(url_for('super_admin') + '#moeen-executive')
        cursor.execute(
            "SELECT receipt_url FROM moeen_subscription_payments WHERE account_id=%s AND receipt_url IS NOT NULL",
            (account_id,),
        )
        receipt_paths = [row["receipt_url"] for row in cursor.fetchall()]
        cursor.execute("DELETE FROM moeen_accounts WHERE id=%s", (account_id,))
        conn.commit()
        uploads_root = os.path.abspath(app.config['UPLOAD_FOLDER'])
        for relative_path in receipt_paths:
            target = os.path.abspath(os.path.join(uploads_root, relative_path))
            if target.startswith(uploads_root + os.sep) and os.path.isfile(target):
                try:
                    os.remove(target)
                except OSError:
                    logging.warning("Could not remove Moeen receipt file: %s", target)
        flash(f"تم حذف حساب {account['full_name']} وبياناته نهائيًا.", "success")
    except Exception:
        conn.rollback()
        logging.exception("Delete Moeen account failed")
        flash("تعذر حذف حساب مُعين.", "error")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('super_admin') + '#moeen-executive')

@app.route('/superadmin/toggle-removebg', methods=['POST'])
def super_admin_toggle_removebg():
    if not session.get('is_superadmin'):
        return redirect(url_for('super_admin_login'))

    from database import set_app_setting
    enabled = request.form.get('enabled') == 'true'
    set_app_setting('removebg_enabled', 'true' if enabled else 'false')

    if enabled:
        flash("تم تفعيل remove.bg لجميع المتاجر.", "success")
    else:
        flash("تم إيقاف remove.bg. ستستخدم معالجة rembg المحلية مباشرة دون طلب الخدمة المدفوعة.", "success")
    return redirect(url_for('super_admin'))

@app.route('/superadmin/payment-settings', methods=['POST'])
def super_admin_payment_settings():
    if not session.get('is_superadmin'):
        return redirect(url_for('super_admin_login'))

    from database import set_app_setting
    for key in PAYMENT_SETTING_KEYS:
        set_app_setting(key, (request.form.get(key) or '').strip())
    flash("تم حفظ إعدادات مركز الدفع.", "success")
    return redirect(url_for('super_admin'))

@app.route('/superadmin/subscription-payment/<int:payment_id>/<action>', methods=['POST'])
def super_admin_review_subscription_payment(payment_id, action):
    if not session.get('is_superadmin'):
        return redirect(url_for('super_admin_login'))
    if action not in {'approve', 'reject'}:
        flash("إجراء غير معروف.", "error")
        return redirect(url_for('super_admin'))

    admin_note = (request.form.get('admin_note') or '').strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM subscription_payments WHERE id = %s", (payment_id,))
        payment = cursor.fetchone()
        if not payment:
            flash("دفعة الاشتراك غير موجودة.", "error")
            return redirect(url_for('super_admin'))
        if payment['status'] != 'pending':
            flash("تمت مراجعة هذه الدفعة سابقاً.", "error")
            return redirect(url_for('super_admin'))

        new_status = 'approved' if action == 'approve' else 'rejected'
        cursor.execute("""
            UPDATE subscription_payments
            SET status = %s,
                admin_note = %s,
                reviewed_at = NOW(),
                reviewed_by = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (new_status, admin_note or None, 'superadmin', payment_id))
        conn.commit()

        if action == 'approve':
            from database import set_subscription
            sub_end = set_subscription(payment['user_id'], payment['plan_type'])
            plan_label = get_subscription_plan(payment['plan_type'])['label']
            flash(f"تم تأكيد الدفع وتفعيل {plan_label} حتى {sub_end.strftime('%Y-%m-%d')}.", "success")
        else:
            flash("تم رفض إثبات الدفع وتسجيل الملاحظة.", "success")
    except Exception as exc:
        conn.rollback()
        logging.exception("Payment review failed")
        flash("حدث خطأ أثناء مراجعة الدفعة.", "error")
    finally:
        conn.close()

    return redirect(url_for('super_admin'))

@app.post('/superadmin/moeen-payment/<int:payment_id>/<action>')
def super_admin_review_moeen_payment(payment_id, action):
    if not session.get('is_superadmin'):
        return redirect(url_for('super_admin_login'))
    if action not in {'approve', 'reject'}:
        return redirect(url_for('super_admin') + '#moeen-payments')
    note = (request.form.get('admin_note') or '').strip()[:1000]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM moeen_subscription_payments WHERE id=%s FOR UPDATE", (payment_id,))
        payment = cursor.fetchone()
        if not payment or payment['status'] != 'pending':
            flash("طلب الدفع غير موجود أو تمت مراجعته سابقًا.", "error")
            return redirect(url_for('super_admin') + '#moeen-payments')
        status = 'approved' if action == 'approve' else 'rejected'
        cursor.execute("""
            UPDATE moeen_subscription_payments
            SET status=%s,admin_note=%s,reviewed_at=NOW() WHERE id=%s
        """, (status, note or None, payment_id))
        if action == 'approve':
            plan = MOEEN_SUBSCRIPTION_PLANS[payment['plan_type']]
            cursor.execute("""
                UPDATE moeen_accounts
                SET status='active',plan_type=%s,
                    subscription_start=NOW(),
                    subscription_end=GREATEST(COALESCE(subscription_end,NOW()),NOW()) + (%s * INTERVAL '1 day'),
                    updated_at=NOW()
                WHERE id=%s
            """, (payment['plan_type'], plan['days'], payment['account_id']))
        conn.commit()
        flash("تم قبول الدفعة وتجديد اشتراك مُعين." if action == 'approve' else "تم رفض إثبات الدفع.", "success")
    except Exception:
        conn.rollback()
        logging.exception("Moeen payment review failed")
        flash("تعذرت مراجعة دفعة مُعين.", "error")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('super_admin') + '#moeen-payments')

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
    admin_start_url = f"/admin?app={urllib.parse.quote(store['slug'], safe='')}"
    manifest = {
        "id": f"/admin-app/{store['slug']}",
        "name": app_name,
        "short_name": app_name,
        "description": f"لوحة إدارة متجر {store['name']} على RT Studio",
        "start_url": admin_start_url,
        "scope": "/admin",
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
    """Return active stores for the landing page logo showcase."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT name AS store, slug
            FROM stores
            WHERE is_active = TRUE
            ORDER BY id
        """)
        rows = cur.fetchall()
        conn.close()
        result = [
            {
                'store': r['store'],
                'slug': r['slug'],
                'logo': f"/store-icon/{urllib.parse.quote(r['slug'], safe='-')}/192",
            }
            for r in rows
        ]
        return jsonify(result)
    except Exception as e:
        logging.error(f"showcase error: {e}")
        return jsonify([])

# =========================
# Static: Service Worker
# =========================
@app.route('/sw.js')
def sw():
    response = send_from_directory(app.root_path, 'sw.js')
    response.headers["Cache-Control"] = "no-cache"
    return response

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
