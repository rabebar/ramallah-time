"""
Enhanced Themes System (v1.0)
===============================
Professional theme collection with 30+ curated themes organized by style.
Fully backward compatible with existing products.

Features:
- 8 theme collections (Classic, Minimal, Luxury, Vibrant, Dark, Soft, Industrial, Neon)
- 10 category presets with recommendations
- 8 pre-configured theme sets
- Easy API access
- Arabic descriptions for all themes
"""

# ═══════════════════════════════════════════════════════════════════
# ENHANCED THEME COLORS (RGB tuples: light_gradient, dark_gradient)
# ═══════════════════════════════════════════════════════════════════

ENHANCED_THEMES = {
    # ──────────────────────────────────────────────────────────────
    # 🎯 CLASSIC COLLECTION - محسّن من الأصلية
    # ──────────────────────────────────────────────────────────────
    'gold':        ((242, 153, 74),  (242, 201, 76)),
    'black':       ((15, 32, 39),    (32, 58, 67)),
    'ocean':       ((33, 147, 176),  (109, 213, 237)),
    'royal':       ((79, 70, 229),   (124, 58, 237)),
    'earth':       ((63, 98, 18),    (113, 63, 18)),
    
    # ──────────────────────────────────────────────────────────────
    # ✨ MINIMAL COLLECTION - بسيطة وأنيقة
    # ──────────────────────────────────────────────────────────────
    'minimal_light':      ((240, 240, 245), (250, 250, 255)),
    'minimal_black':      ((20, 20, 25),    (40, 40, 50)),
    'minimal_gray':       ((200, 200, 205), (230, 230, 235)),
    'minimal_sage':       ((150, 170, 150), (180, 200, 180)),
    'minimal_stone':      ((180, 175, 170), (210, 205, 195)),
    
    # ──────────────────────────────────────────────────────────────
    # 👑 LUXURY COLLECTION - فاخرة وراقية
    # ──────────────────────────────────────────────────────────────
    'luxury_dark':        ((10, 10, 15),    (25, 25, 35)),
    'luxury_pearl':       ((245, 245, 250), (220, 220, 225)),
    'luxury_rose_gold':   ((183, 110, 121), (212, 175, 55)),
    'luxury_champagne':   ((212, 175, 55),  (245, 220, 130)),
    'luxury_emerald':     ((20, 80, 60),    (60, 150, 120)),
    'luxury_sapphire':    ((15, 45, 120),   (50, 120, 200)),
    
    # ──────────────────────────────────────────────────────────────
    # 🔥 VIBRANT COLLECTION - ألوان حية وجريئة
    # ──────────────────────────────────────────────────────────────
    'vibrant_red':        ((255, 50, 80),   (255, 100, 130)),
    'vibrant_pink':       ((255, 105, 180), (255, 150, 200)),
    'vibrant_orange':     ((255, 140, 0),   (255, 180, 50)),
    'vibrant_green':      ((50, 200, 100),  (100, 255, 150)),
    'vibrant_purple':     ((180, 50, 200),  (220, 100, 255)),
    
    # ──────────────────────────────────────────────────────────────
    # 🌙 DARK COLLECTION - أنيقة ومظلمة
    # ──────────────────────────────────────────────────────────────
    'dark_elegant':       ((20, 30, 50),    (50, 70, 100)),
    'dark_smoke':         ((40, 40, 50),    (80, 80, 100)),
    'dark_carbon':        ((20, 20, 25),    (60, 60, 70)),
    'dark_midnight':      ((10, 15, 35),    (30, 40, 70)),
    'dark_slate':         ((45, 50, 65),    (75, 85, 110)),
    
    # ──────────────────────────────────────────────────────────────
    # 🎨 SOFT COLLECTION - ناعمة وعصرية
    # ──────────────────────────────────────────────────────────────
    'soft_blush':         ((255, 200, 210), (255, 230, 235)),
    'soft_sage':          ((180, 200, 180), (210, 235, 210)),
    'soft_lavender':      ((200, 180, 220), (230, 210, 245)),
    'soft_peach':         ((255, 200, 150), (255, 230, 200)),
    'soft_mint':          ((150, 230, 200), (180, 255, 230)),
    
    # ──────────────────────────────────────────────────────────────
    # ⚙️ INDUSTRIAL COLLECTION - معادن وملمس
    # ──────────────────────────────────────────────────────────────
    'industrial_steel':   ((120, 130, 140), (180, 190, 200)),
    'industrial_copper':  ((184, 115, 51),  (220, 160, 100)),
    'industrial_bronze':  ((150, 100, 50),  (200, 150, 100)),
    'industrial_gunmetal':((70, 75, 85),    (120, 130, 145)),
    
    # ──────────────────────────────────────────────────────────────
    # ⚡ NEON COLLECTION - حديثة وملفتة
    # ──────────────────────────────────────────────────────────────
    'neon_cyan':          ((0, 255, 255),   (100, 200, 255)),
    'neon_magenta':       ((255, 0, 255),   (255, 100, 200)),
    'neon_lime':          ((0, 255, 0),     (150, 255, 100)),
}

# ═══════════════════════════════════════════════════════════════════
# THEME COLLECTIONS (تصنيف الثيمات)
# ═══════════════════════════════════════════════════════════════════

THEME_COLLECTIONS = {
    'classic': {
        'name': '🎯 كلاسيكية محسّنة',
        'description': 'ألوان كلاسيكية مختبرة وموثوقة',
        'themes': ['gold', 'black', 'ocean', 'royal', 'earth']
    },
    'minimal': {
        'name': '✨ بسيطة وأنيقة',
        'description': 'تصاميم بسيطة تركز على المنتج',
        'themes': ['minimal_light', 'minimal_black', 'minimal_gray', 'minimal_sage', 'minimal_stone']
    },
    'luxury': {
        'name': '👑 فاخرة وراقية',
        'description': 'ثيمات فاخرة للمنتجات الراقية',
        'themes': ['luxury_dark', 'luxury_pearl', 'luxury_rose_gold', 'luxury_champagne', 'luxury_emerald', 'luxury_sapphire']
    },
    'vibrant': {
        'name': '🔥 حية وجريئة',
        'description': 'ألوان قوية وملفتة للانتباه',
        'themes': ['vibrant_red', 'vibrant_pink', 'vibrant_orange', 'vibrant_green', 'vibrant_purple']
    },
    'dark': {
        'name': '🌙 مظلمة وأنيقة',
        'description': 'ثيمات مظلمة احترافية وحديثة',
        'themes': ['dark_elegant', 'dark_smoke', 'dark_carbon', 'dark_midnight', 'dark_slate']
    },
    'soft': {
        'name': '🎨 ناعمة وعصرية',
        'description': 'ألوان ناعمة وهادئة',
        'themes': ['soft_blush', 'soft_sage', 'soft_lavender', 'soft_peach', 'soft_mint']
    },
    'industrial': {
        'name': '⚙️ صناعية',
        'description': 'معادن وملمس احترافي',
        'themes': ['industrial_steel', 'industrial_copper', 'industrial_bronze', 'industrial_gunmetal']
    },
    'neon': {
        'name': '⚡ نيون حديثة',
        'description': 'ألوان نيون عصرية وملفتة',
        'themes': ['neon_cyan', 'neon_magenta', 'neon_lime']
    }
}

# ═══════════════════════════════════════════════════════════════════
# CATEGORY PRESETS - اقتراحات لكل فئة منتجات
# ═══════════════════════════════════════════════════════════════════

CATEGORY_PRESETS_ENHANCED = {
    'perfume': {
        'themes': ['luxury_dark', 'luxury_rose_gold', 'luxury_sapphire', 'gold', 'dark_elegant'],
        'glow': True,
        'reflection': True,
        'backgrounds': ['velvet_red', 'velvet_teal', 'dark_gold_metal', 'black_marble', 'rose_blur']
    },
    'jewelry': {
        'themes': ['luxury_pearl', 'luxury_champagne', 'luxury_dark', 'industrial_bronze', 'gold'],
        'glow': True,
        'reflection': True,
        'backgrounds': ['velvet_teal', 'velvet_red', 'black_marble', 'rose_blur', 'brushed_silver']
    },
    'watches': {
        'themes': ['industrial_steel', 'industrial_gunmetal', 'luxury_dark', 'dark_carbon', 'black'],
        'glow': True,
        'reflection': True,
        'backgrounds': ['carbon_wave', 'dark_gold_metal', 'black_marble', 'dark_concrete', 'dark_slate']
    },
    'clothes': {
        'themes': ['soft_blush', 'soft_sage', 'soft_lavender', 'minimal_light', 'pastel'],
        'glow': False,
        'reflection': False,
        'backgrounds': ['grey_marble', 'brushed_silver', 'rose_blur', 'navy_silk', 'studio_gray']
    },
    'bags': {
        'themes': ['camel', 'chocolate', 'beige', 'earth', 'industrial_bronze'],
        'glow': False,
        'reflection': False,
        'backgrounds': ['dark_concrete', 'dark_slate', 'black_marble', 'navy_silk', 'brushed_silver']
    },
    'mobiles': {
        'themes': ['tech_black', 'space_gray', 'clean_white', 'dark_carbon', 'industrial_steel'],
        'glow': True,
        'reflection': False,
        'backgrounds': ['carbon_wave', 'dark_concrete', 'dark_slate', 'navy_silk', 'brushed_silver']
    },
    'cosmetics': {
        'themes': ['vibrant_pink', 'soft_peach', 'luxury_rose_gold', 'soft_blush', 'vibrant_red'],
        'glow': True,
        'reflection': False,
        'backgrounds': ['rose_blur', 'velvet_pink', 'grey_marble', 'white_shelf', 'studio_gray']
    },
    'home_decor': {
        'themes': ['soft_sage', 'soft_lavender', 'minimal_stone', 'camel', 'earth'],
        'glow': False,
        'reflection': False,
        'backgrounds': ['beige_shadow', 'tropical_beige', 'desert_sand', 'cabinet_frames', 'sea_window']
    },
    'electronics': {
        'themes': ['dark_elegant', 'tech_black', 'industrial_steel', 'minimal_black', 'dark_carbon'],
        'glow': True,
        'reflection': False,
        'backgrounds': ['dark_concrete', 'carbon_wave', 'dark_slate', 'studio_gray', 'brushed_silver']
    },
    'food': {
        'themes': ['vibrant_orange', 'soft_peach', 'warm_gold', 'vibrant_red', 'camel'],
        'glow': False,
        'reflection': False,
        'backgrounds': ['white_shelf', 'cream', 'beige_shadow', 'studio_gray', 'tropical_beige']
    },
    'other': {
        'themes': ['gold', 'black', 'minimal_light', 'ocean', 'royal'],
        'glow': False,
        'reflection': False,
        'backgrounds': ['dark_concrete', 'black_marble', 'grey_marble', 'navy_silk', 'studio_gray']
    }
}

# ═══════════════════════════════════════════════════════════════════
# PRESET COMBINATIONS - مجموعات جاهزة الاستخدام
# ═══════════════════════════════════════════════════════════════════

THEME_PRESETS = {
    'luxury_gold': {
        'name': '👑 ذهب فاخر',
        'description': 'مزيج فاخر مع ذهب وتأثيرات',
        'theme': 'luxury_champagne',
        'background': 'dark_gold_metal',
        'glow': True,
        'reflection': True,
        'style': 'elegant'
    },
    'luxury_dark': {
        'name': '👑 أسود فاخر',
        'description': 'أناقة داكنة مع لمسات فاخرة',
        'theme': 'luxury_dark',
        'background': 'black_marble',
        'glow': True,
        'reflection': True,
        'style': 'elegant'
    },
    'minimal_clean': {
        'name': '✨ نظيفة بسيطة',
        'description': 'تصميم بسيط وأنيق',
        'theme': 'minimal_light',
        'background': 'white_shelf',
        'glow': False,
        'reflection': False,
        'style': 'minimal'
    },
    'dark_modern': {
        'name': '🌙 داكنة حديثة',
        'description': 'ثيم حديث مظلم احترافي',
        'theme': 'dark_elegant',
        'background': 'dark_concrete',
        'glow': False,
        'reflection': False,
        'style': 'modern'
    },
    'vibrant_pop': {
        'name': '🔥 ملفتة وحية',
        'description': 'ألوان حية وجريئة',
        'theme': 'vibrant_pink',
        'background': 'rose_blur',
        'glow': True,
        'reflection': False,
        'style': 'bold'
    },
    'industrial_pro': {
        'name': '⚙️ احترافية صناعية',
        'description': 'معادن واحترافية',
        'theme': 'industrial_steel',
        'background': 'carbon_wave',
        'glow': True,
        'reflection': False,
        'style': 'modern'
    },
    'soft_elegant': {
        'name': '🎨 ناعمة أنيقة',
        'description': 'ألوان ناعمة وهادئة',
        'theme': 'soft_sage',
        'background': 'beige_shadow',
        'glow': False,
        'reflection': False,
        'style': 'elegant'
    },
    'neon_future': {
        'name': '⚡ نيون مستقبلية',
        'description': 'نيون حديثة وعصرية',
        'theme': 'neon_cyan',
        'background': 'dark_concrete',
        'glow': True,
        'reflection': False,
        'style': 'modern'
    }
}

# ═══════════════════════════════════════════════════════════════════
# API HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def get_all_themes():
    """جلب جميع الثيمات مع البيانات الوصفية"""
    result = []
    for theme_name, color_tuple in ENHANCED_THEMES.items():
        result.append({
            'name': theme_name,
            'light': color_tuple[0],
            'dark': color_tuple[1],
            'hex_light': rgb_to_hex(color_tuple[0]),
            'hex_dark': rgb_to_hex(color_tuple[1])
        })
    return result

def get_theme_by_name(theme_name):
    """جلب ثيم محدد"""
    if theme_name in ENHANCED_THEMES:
        color_tuple = ENHANCED_THEMES[theme_name]
        return {
            'name': theme_name,
            'light': color_tuple[0],
            'dark': color_tuple[1],
            'hex_light': rgb_to_hex(color_tuple[0]),
            'hex_dark': rgb_to_hex(color_tuple[1])
        }
    return None

def get_collection(collection_name):
    """جلب مجموعة كاملة"""
    if collection_name in THEME_COLLECTIONS:
        coll = THEME_COLLECTIONS[collection_name]
        themes_data = []
        for theme_name in coll['themes']:
            if theme_name in ENHANCED_THEMES:
                color_tuple = ENHANCED_THEMES[theme_name]
                themes_data.append({
                    'name': theme_name,
                    'light': color_tuple[0],
                    'dark': color_tuple[1]
                })
        return {
            'collection_name': collection_name,
            'name': coll['name'],
            'description': coll['description'],
            'themes': themes_data
        }
    return None

def get_category_suggestions(category):
    """اقتراحات لفئة منتجات"""
    if category in CATEGORY_PRESETS_ENHANCED:
        preset = CATEGORY_PRESETS_ENHANCED[category]
        themes_data = []
        for theme_name in preset['themes']:
            if theme_name in ENHANCED_THEMES:
                color_tuple = ENHANCED_THEMES[theme_name]
                themes_data.append({
                    'name': theme_name,
                    'light': color_tuple[0],
                    'dark': color_tuple[1]
                })
        return {
            'category': category,
            'themes': themes_data,
            'glow': preset['glow'],
            'reflection': preset['reflection'],
            'backgrounds': preset['backgrounds']
        }
    return None

def get_preset(preset_name):
    """جلب مجموعة معدة مسبقاً"""
    if preset_name in THEME_PRESETS:
        preset = THEME_PRESETS[preset_name]
        theme_color = ENHANCED_THEMES.get(preset['theme'], ((255, 255, 255), (0, 0, 0)))
        return {
            'preset_name': preset_name,
            'name': preset['name'],
            'description': preset['description'],
            'theme': preset['theme'],
            'theme_colors': {
                'light': theme_color[0],
                'dark': theme_color[1]
            },
            'background': preset['background'],
            'glow': preset['glow'],
            'reflection': preset['reflection'],
            'style': preset['style']
        }
    return None

def get_all_presets():
    """جلب جميع المجموعات المعدة مسبقاً"""
    result = []
    for preset_name, preset_data in THEME_PRESETS.items():
        theme_color = ENHANCED_THEMES.get(preset_data['theme'], ((255, 255, 255), (0, 0, 0)))
        result.append({
            'preset_name': preset_name,
            'name': preset_data['name'],
            'description': preset_data['description'],
            'theme': preset_data['theme'],
            'background': preset_data['background']
        })
    return result

def rgb_to_hex(rgb):
    """تحويل RGB إلى HEX"""
    r, g, b = rgb
    return f'#{r:02x}{g:02x}{b:02x}'

def hex_to_rgb(hex_color):
    """تحويل HEX إلى RGB"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
