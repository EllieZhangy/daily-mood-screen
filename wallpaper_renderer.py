import json
import os
import re
import sys
from datetime import date

from PIL import Image, ImageDraw, ImageFont

from mood_engine import determine_mood
from quote_generator import (
    generate_quote,
    load_context,
    load_photos, resolve_photos,
    load_weather, resolve_weather,
)
from src.typography_engine import (
    load_typography_style,
    choose_font,
    render_handwritten_text,
    wrap_to_lines,
)

# ── Canvas — 16:9 desktop (2560×1440) ────────────────────────────────────────
WIDTH  = 2560
HEIGHT = 1440
STYLE_PATH  = "wallpaper_style.json"
OUTPUT_PATH = "output/daily_wallpaper_mac.png"

# ── Named background themes ───────────────────────────────────────────────────
# Each theme defines gradient top/bottom colors and text colors.
# Add new entries here to support more themes in wallpaper_style.json.
THEMES = {
    "warm_light": {
        "bg_top":    (245, 240, 235),
        "bg_bottom": (224, 216, 206),
        "text":      (42,  37,  32),
        "meta":      (115, 105, 95),
    },
    "cool_light": {
        "bg_top":    (238, 242, 246),
        "bg_bottom": (215, 223, 232),
        "text":      (30,  40,  55),
        "meta":      (100, 115, 130),
    },
    "dark": {
        "bg_top":    (28,  25,  22),
        "bg_bottom": (16,  14,  12),
        "text":      (228, 222, 214),
        "meta":      (130, 120, 110),
    },
}

# ── Font name → macOS file path (tries each path in order, uses first found) ──
FONT_PATHS = {
    "PingFang SC": [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",   # fallback if PingFang missing
    ],
    "STHeiti Light": [
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
    ],
    "STHeiti Medium": [
        "/System/Library/Fonts/STHeiti Medium.ttc",
    ],
    "SFNS": [
        "/System/Library/Fonts/SFNS.ttf",
    ],
}


# ── Loaders ───────────────────────────────────────────────────────────────────
def load_style(path: str = STYLE_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a font by friendly name using the FONT_PATHS lookup above."""
    candidates = FONT_PATHS.get(name, [])

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    # If the named font wasn't found, try any known font as a last resort
    for paths in FONT_PATHS.values():
        for path in paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue

    print(f"Warning: could not load font '{name}', using built-in bitmap font.")
    return ImageFont.load_default()


# ── Drawing helpers ───────────────────────────────────────────────────────────
def make_gradient(width: int, height: int, top: tuple, bottom: tuple) -> Image.Image:
    """
    Render a vertical gradient with an ease-in curve (darker at bottom).
    The non-linear curve matches the atmospheric character of the reference
    collection: open and airy at the top (text zone), grounded at the bottom.
    """
    image = Image.new("RGB", (width, height))
    draw  = ImageDraw.Draw(image)
    for y in range(height):
        t = y / height
        # Ease-in-out: slow at top, faster in middle, slow at bottom
        t_curved = t * t * (3.0 - 2.0 * t)
        r = int(top[0] + t_curved * (bottom[0] - top[0]))
        g = int(top[1] + t_curved * (bottom[1] - top[1]))
        b = int(top[2] + t_curved * (bottom[2] - top[2]))
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return image


def measure_h(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    """Pixel height of one line of text."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def _sample_region_avg(image: Image.Image, box: tuple) -> tuple:
    """Return the average RGB color of an image region via 1-pixel resize."""
    x0, y0, x1, y1 = box
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(image.width, x1), min(image.height, y1)
    region = image.crop((x0, y0, x1, y1)).convert("RGB").resize((1, 1), Image.LANCZOS)
    return region.getpixel((0, 0))


def _readable_meta_color(bg_rgb: tuple, text_rgb: tuple, opacity: float = 0.72) -> tuple:
    """
    Return a meta text color that is always lighter than the primary text.

    Blends text_rgb toward bg_rgb at (1 - opacity): the meta carries 72% of
    the text's darkness while 28% bleeds back toward the background.

    This guarantees: meta < quote in visual prominence on any background,
    meta is clearly readable (≈72% of quote visibility), hierarchy is preserved.
    """
    br, bg, bb = bg_rgb
    tr, tg, tb = text_rgb
    return (
        round(tr * opacity + br * (1 - opacity)),
        round(tg * opacity + bg * (1 - opacity)),
        round(tb * opacity + bb * (1 - opacity)),
    )


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    """
    Fit text into max_width, breaking on newlines first, then character by
    character (so it works for Chinese as well as English).
    """
    lines = []
    for paragraph in text.split("\n"):
        if draw.textbbox((0, 0), paragraph, font=font)[2] <= max_width:
            lines.append(paragraph)
            continue
        current = ""
        for char in paragraph:
            if draw.textbbox((0, 0), current + char, font=font)[2] > max_width:
                if current:
                    lines.append(current)
                current = char
            else:
                current += char
        if current:
            lines.append(current)
    return lines


# ── Chinese translation tables ────────────────────────────────────────────────
_CONDITION_ZH = {
    "clear": "晴",
    "sunny": "晴",
    "partly cloudy": "多云",
    "partly_cloudy": "多云",
    "cloudy": "阴",
    "overcast": "阴云密布",
    "mist": "薄雾",
    "fog": "大雾",
    "foggy": "大雾",
    "haze": "霾",
    "drizzle": "细雨",
    "light drizzle": "细雨",
    "freezing drizzle": "冻雨",
    "heavy drizzle": "大雨",
    "rain": "雨",
    "light rain": "小雨",
    "moderate rain": "中雨",
    "heavy rain": "大雨",
    "torrential rain": "暴雨",
    "shower": "阵雨",
    "showers": "阵雨",
    "patchy rain": "局部小雨",
    "thunderstorm": "雷雨",
    "thunder": "雷雨",
    "blizzard": "暴雪",
    "snow": "雪",
    "light snow": "小雪",
    "moderate snow": "中雪",
    "heavy snow": "大雪",
    "patchy snow": "局部小雪",
    "sleet": "雨夹雪",
    "freezing rain": "冻雨",
    "hail": "冰雹",
    "wind": "大风",
    "windy": "大风",
    "tornado": "龙卷风",
}

_MOOD_ZH = {
    "cold_reunion":        "寒日重逢",
    "cold_solitude":       "冬日独处",
    "cold_stillness":      "寒意静谧",
    "cold_nostalgia":      "冬日念旧",
    "cold_homecoming":     "归家温暖",
    "cold_journey":        "冬日旅途",
    "cold_introspection":  "冬日沉思",
    "cold_comfort":        "冬日慰藉",
    "rainy_connection":    "雨中相聚",
    "rainy_solitude":      "雨中独行",
    "rainy_reflection":    "雨日沉思",
    "rainy_nostalgia":     "雨日怀旧",
    "rainy_shelter":       "雨中避风",
    "rainy_discovery":     "雨中探索",
    "rainy_introspection": "雨日内省",
    "rainy_comfort":       "雨日温暖",
    "cloudy_reunion":      "阴日重逢",
    "cloudy_solitude":     "阴日独处",
    "cloudy_calm":         "阴云静好",
    "cloudy_nostalgia":    "阴日思绪",
    "cloudy_warmth":       "阴云暖意",
    "cloudy_movement":     "阴日远行",
    "cloudy_reflection":   "阴日沉思",
    "cloudy_comfort":      "阴日慰藉",
    "sunny_connection":    "晴日相聚",
    "sunny_solitude":      "晴日独行",
    "calm_reflection":     "静心沉思",
    "sunny_nostalgia":     "晴日怀旧",
    "sunny_warmth":        "晴日温暖",
    "sunny_movement":      "晴日出发",
    "sunny_stillness":     "晴日静好",
    "sunny_simplicity":    "晴日简单",
    "cold_focus":          "冬日专注",
    "cold_quietude":       "冬日宁静",
    "rainy_focus":         "雨日专注",
    "rainy_quietude":      "雨日宁静",
    "cloudy_focus":        "阴日专注",
    "cloudy_quietude":     "阴日宁静",
    "sunny_focus":         "晴日专注",
    "sunny_quietude":      "晴日宁静",
}

_THEME_ZH = {
    "friends":      "朋友",
    "family":       "家人",
    "travel":       "旅行",
    "food":         "美食",
    "nature":       "自然",
    "self":         "自我",
    "memories":     "回忆",
    "study":        "学习",
    "quiet":        "宁静",
    "city":         "城市",
    "work":         "工作",
    "art":          "艺术",
    "music":        "音乐",
    "sports":       "运动",
    "pets":         "宠物",
    "events":       "活动",
    "landscape":    "风景",
    "portrait":     "人像",
    "street":       "街拍",
    "architecture": "建筑",
    "night":        "夜景",
    "beach":        "海边",
    "mountain":     "山野",
}

_LOCATION_ZH = {
    # United States
    "los angeles":      "洛杉矶",
    "new york":         "纽约",
    "new york city":    "纽约",
    "san francisco":    "旧金山",
    "chicago":          "芝加哥",
    "seattle":          "西雅图",
    "boston":           "波士顿",
    "washington":       "华盛顿",
    "washington dc":    "华盛顿",
    "miami":            "迈阿密",
    "las vegas":        "拉斯维加斯",
    "houston":          "休斯顿",
    "dallas":           "达拉斯",
    "austin":           "奥斯汀",
    "denver":           "丹佛",
    "portland":         "波特兰",
    "san diego":        "圣地亚哥",
    "phoenix":          "凤凰城",
    "atlanta":          "亚特兰大",
    "minneapolis":      "明尼阿波利斯",
    # China
    "beijing":          "北京",
    "shanghai":         "上海",
    "guangzhou":        "广州",
    "shenzhen":         "深圳",
    "chengdu":          "成都",
    "hangzhou":         "杭州",
    "wuhan":            "武汉",
    "xi'an":            "西安",
    "xian":             "西安",
    "nanjing":          "南京",
    "chongqing":        "重庆",
    "tianjin":          "天津",
    "suzhou":           "苏州",
    "qingdao":          "青岛",
    "kunming":          "昆明",
    "hong kong":        "香港",
    "macau":            "澳门",
    "taipei":           "台北",
    # Other major cities
    "tokyo":            "东京",
    "osaka":            "大阪",
    "kyoto":            "京都",
    "seoul":            "首尔",
    "singapore":        "新加坡",
    "london":           "伦敦",
    "paris":            "巴黎",
    "berlin":           "柏林",
    "sydney":           "悉尼",
    "melbourne":        "墨尔本",
    "toronto":          "多伦多",
    "vancouver":        "温哥华",
}


def _is_english(language: str) -> bool:
    return language.lower().startswith("en")


# ── Weather string builder ────────────────────────────────────────────────────
def format_weather_str(weather: dict, language: str = "zh-CN") -> str:
    """
    Build the weather metadata line shown on the wallpaper.

    Examples:
      zh, weather.json present  →  "洛杉矶 · 晴 · 22℃"
      zh, context.json fallback →  "晴 · 22℃"
      en, weather.json present  →  "Los Angeles · Cloudy · 22°C"
    """
    parts = []
    location  = weather.get("location", "")
    condition = weather.get("condition", "")
    temp      = weather.get("temperature", "")
    unit      = weather.get("unit", "C")

    if _is_english(language):
        if location:
            parts.append(location)
        if condition:
            parts.append(condition.replace("_", " ").title())
        if temp != "":
            parts.append(f"{temp}°{unit}")
    else:
        if location:
            parts.append(_LOCATION_ZH.get(location.lower(), location))
        if condition:
            zh = _CONDITION_ZH.get(condition.lower(), condition)
            parts.append(zh)
        if temp != "":
            unit_glyph = {"C": "℃", "F": "℉"}.get(unit, f"°{unit}")
            parts.append(f"{temp}{unit_glyph}")

    return " · ".join(parts)


# ── Photos string builder ─────────────────────────────────────────────────────
def format_photos_str(photos: dict, language: str = "zh-CN") -> str:
    """
    Build the photos metadata line shown below the weather line.

    Examples:
      zh, theme=friends, count=6  →  "朋友 · 6 张照片"
      en, theme=friends, count=6  →  "Friends · 6 photos"
      theme=none, count=0         →  ""  (nothing drawn)
    """
    theme = photos.get("theme", "none")
    count = photos.get("photo_count", 0)

    parts = []
    if _is_english(language):
        if theme and theme != "none":
            parts.append(theme.replace("_", " ").title())
        if count:
            parts.append(f"{count} photo" if count == 1 else f"{count} photos")
    else:
        if theme and theme != "none":
            zh_theme = _THEME_ZH.get(theme.lower(), theme)
            parts.append(zh_theme)
        if count:
            parts.append(f"{count} 张照片")

    return " · ".join(parts)


# ── Mood string builder ───────────────────────────────────────────────────────
def format_mood_str(mood: dict, language: str = "zh-CN") -> str:
    """
    Build the mood metadata line shown below the photos line.
    "cold_reunion" → "心情 · 寒日重逢"  /  "Mood · Cold Reunion"
    Returns empty string if mood is empty.
    """
    mood_name = mood.get("mood", "")
    if not mood_name:
        return ""
    if _is_english(language):
        label = mood_name.replace("_", " ").title()
        return f"Mood · {label}"
    label = _MOOD_ZH.get(mood_name, mood_name.replace("_", " ").title())
    return f"心情 · {label}"


# ── Main render ───────────────────────────────────────────────────────────────
def render_wallpaper(quote: str, context: dict, style: dict, weather: dict | None = None, photos: dict | None = None, mood: dict | None = None, visual_style: dict | None = None, output_path: str = OUTPUT_PATH, typography_style: str | None = None) -> None:
    # ── Read base values from wallpaper_style.json ────────────────────────────
    font_cfg   = style.get("font", {})
    layout_cfg = style.get("layout", {})
    theme_cfg  = style.get("theme", {})

    font_name        = font_cfg.get("primary", "STHeiti Light")
    quote_size       = font_cfg.get("quote_size", 68)
    meta_size        = font_cfg.get("metadata_size", 30)

    # Typography style: parameter wins, then style JSON, then None (standard)
    if typography_style is None:
        typography_style = font_cfg.get("typography_style", None)

    text_width_ratio = layout_cfg.get("text_width_ratio", 0.6)
    line_spacing     = layout_cfg.get("line_spacing", 1.5)
    meta_gap         = layout_cfg.get("meta_gap", 72)
    meta_line_gap    = layout_cfg.get("meta_line_gap", 20)
    vertical_offset  = layout_cfg.get("vertical_offset", 0)

    theme_name = theme_cfg.get("background", "warm_light")
    alignment  = theme_cfg.get("alignment", "center")

    # ── Resolve base theme colors ─────────────────────────────────────────────
    theme = dict(THEMES.get(theme_name, THEMES["warm_light"]))  # copy — we may override below

    # ── Apply visual style overrides (if a library style was loaded) ──────────
    # Visual style values take priority over wallpaper_style.json.
    position = "center"   # "center" | "bottom_left"
    margin   = 0.0        # fraction of canvas — used when position == "bottom_left"

    if visual_style:
        vs_typo    = visual_style.get("typography",    {})
        vs_layout  = visual_style.get("layout",        {})
        vs_bg      = visual_style.get("background",    {})
        vs_palette = visual_style.get("color_palette", {})

        font_name        = vs_typo.get("font",          font_name)
        quote_size       = vs_typo.get("quote_size",    quote_size)
        meta_size        = vs_typo.get("metadata_size", meta_size)
        line_spacing     = vs_typo.get("line_spacing",  line_spacing)

    # Handwriting renders at its own larger size — don't let visual presets
    # shrink it (presets target typeset text at ~44px, handwriting needs ~96px).
    if typography_style == "handwritten_note":
        quote_size = font_cfg.get("quote_size", 96)

        text_width_ratio = vs_layout.get("text_width_ratio", text_width_ratio)
        vertical_offset  = vs_layout.get("vertical_offset",  vertical_offset)
        meta_gap         = vs_layout.get("meta_gap",          meta_gap)
        meta_line_gap    = vs_layout.get("meta_line_gap",     meta_line_gap)
        alignment        = vs_layout.get("alignment",         alignment)
        position         = vs_layout.get("position",          position)
        margin           = vs_layout.get("margin",            margin)

        if vs_bg.get("type") == "gradient":
            if "top"    in vs_bg: theme["bg_top"]    = tuple(vs_bg["top"])
            if "bottom" in vs_bg: theme["bg_bottom"]  = tuple(vs_bg["bottom"])

        if "text_primary"   in vs_palette: theme["text"] = tuple(vs_palette["text_primary"])
        if "text_secondary" in vs_palette: theme["meta"] = tuple(vs_palette["text_secondary"])

    # ── Build display strings ─────────────────────────────────────────────────
    language         = context.get("language", "zh-CN")
    resolved_weather = resolve_weather(context, weather)
    resolved_photos  = resolve_photos(context, photos)
    resolved_mood    = mood if mood is not None else determine_mood(resolved_weather, resolved_photos)
    if _is_english(language):
        today_str    = date.today().strftime("%B %-d, %Y")
    else:
        today_str    = date.today().strftime("%Y年%m月%d日")
    weather_str      = format_weather_str(resolved_weather, language)
    photos_str       = format_photos_str(resolved_photos, language)
    mood_str         = format_mood_str(resolved_mood, language)

    # ── Fonts ─────────────────────────────────────────────────────────────────
    font_quote = get_font(font_name, quote_size)
    font_meta  = get_font(font_name, meta_size)

    # ── Background ────────────────────────────────────────────────────────────
    # Priority 1: output/background.png  (pre-generated by background_generator.py)
    # Priority 2: visual_engine atmospheric gradient
    # Priority 3: make_gradient flat fallback
    _BG_PATH = "output/background.png"
    image    = None

    if os.path.exists(_BG_PATH):
        try:
            _loaded = Image.open(_BG_PATH).convert("RGB")
            if _loaded.size == (WIDTH, HEIGHT):
                image = _loaded
                print(f"  bg   : {_BG_PATH}")
            else:
                print(f"  bg   : {_BG_PATH} wrong size {_loaded.size} — regenerating")
        except Exception as _load_err:
            print(f"  bg   : could not load {_BG_PATH} ({_load_err})")

    if image is None:
        from mood_engine import categorize_weather as _categorize
        _mood_name   = resolved_mood.get("mood", "cloudy_solitude") if resolved_mood else "cloudy_solitude"
        _weather_cat = _categorize(resolved_weather)
        try:
            from visual_engine import make_atmospheric_background
            image = make_atmospheric_background(_mood_name, _weather_cat, WIDTH, HEIGHT)
            print(f"  bg   : visual engine ({_mood_name})")
        except Exception as _ve_err:
            print(f"  bg   : gradient fallback ({_ve_err})")
            image = make_gradient(WIDTH, HEIGHT, theme["bg_top"], theme["bg_bottom"])

    # Sample background at the metadata region and set a contrast-aware color.
    if position == "bottom_right":
        _sbx = (WIDTH - 550, HEIGHT - 550, WIDTH - 30, HEIGHT - 30)
    elif position == "bottom_left":
        _sbx = (30, HEIGHT - 550, 550, HEIGHT - 30)
    else:
        _sbx = (WIDTH // 4, HEIGHT // 4, 3 * WIDTH // 4, 3 * HEIGHT // 4)
    theme["meta"] = _readable_meta_color(_sample_region_avg(image, _sbx), theme["text"])

    draw  = ImageDraw.Draw(image)

    # ── Wrap and measure ──────────────────────────────────────────────────────
    max_quote_width = int(WIDTH * text_width_ratio)
    quote_lines = wrap_text(draw, quote, font_quote, max_quote_width)

    line_gap  = int(quote_size * (line_spacing - 1.0))

    date_h    = measure_h(draw, today_str,   font_meta)
    weather_h = measure_h(draw, weather_str, font_meta)
    photos_h  = measure_h(draw, photos_str,  font_meta) if photos_str else 0
    mood_h    = measure_h(draw, mood_str,    font_meta) if mood_str   else 0
    quote_h   = (
        sum(measure_h(draw, line, font_quote) for line in quote_lines)
        + line_gap * (len(quote_lines) - 1)
    )

    total_h = (
        date_h + meta_line_gap
        + weather_h
        + (meta_line_gap + photos_h if photos_str else 0)
        + (meta_line_gap + mood_h   if mood_str   else 0)
        + meta_gap + quote_h
    )

    # ── Position and anchor ───────────────────────────────────────────────────
    if position == "bottom_right":
        margin_px = int(WIDTH  * margin)
        margin_by = int(HEIGHT * margin)
        x  = WIDTH - margin_px
        y  = HEIGHT - margin_by - total_h
        anchor = "rt"
    elif position == "bottom_left":
        margin_px = int(WIDTH  * margin)
        margin_by = int(HEIGHT * margin)
        x  = margin_px
        y  = HEIGHT - margin_by - total_h
        anchor = "lt"
    elif alignment == "left":
        x      = (WIDTH - max_quote_width) // 2
        anchor = "lt"
        y      = (HEIGHT - total_h) // 2 + vertical_offset
    else:
        x      = WIDTH // 2
        anchor = "mt"
        y      = (HEIGHT - total_h) // 2 + vertical_offset

    # ── Draw: date → weather → photos → mood → gap → quote ───────────────────
    draw.text((x, y), today_str, font=font_meta, fill=theme["meta"], anchor=anchor)
    y += date_h + meta_line_gap

    draw.text((x, y), weather_str, font=font_meta, fill=theme["meta"], anchor=anchor)
    y += weather_h

    if photos_str:
        y += meta_line_gap
        draw.text((x, y), photos_str, font=font_meta, fill=theme["meta"], anchor=anchor)
        y += photos_h

    if mood_str:
        y += meta_line_gap
        draw.text((x, y), mood_str, font=font_meta, fill=theme["meta"], anchor=anchor)
        y += mood_h

    y += meta_gap

    # ── Quote text: handwritten_note style or standard typeset ────────────────
    if typography_style == "handwritten_note":
        try:
            hw_style  = load_typography_style("handwritten_note")
            hw_max_width_ratio = hw_style.get("layout", {}).get("max_width_ratio", 0.27)
            hw_max_width = int(WIDTH * hw_max_width_ratio)
            hw_extra_px  = hw_style.get("spacing", {}).get("character_spacing_px_extra", 3)

            # ── Wrap with font-size reduction fallback ────────────────────────
            # Start at quote_size; if the text needs more than 3 lines, reduce
            # font size by 10% and retry — never drop characters.
            hw_size = quote_size
            hw_font = choose_font("handwritten_note", hw_size)
            hw_lines = wrap_to_lines(quote, hw_font, hw_max_width,
                                     char_extra_px=hw_extra_px)
            while len(hw_lines) > 3 and hw_size > 40:
                hw_size = max(40, int(hw_size * 0.9))
                hw_font = choose_font("handwritten_note", hw_size)
                hw_lines = wrap_to_lines(quote, hw_font, hw_max_width,
                                         char_extra_px=hw_extra_px)

            # If wrapping still produces a single-char orphan on the last line,
            # try expanding the text area width in small steps (shifts the block
            # left, keeping it right-aligned) before accepting the wrap.
            if len(hw_lines) > 1 and len(hw_lines[-1]) == 1:
                for _expand in (1.06, 1.10, 1.15):
                    _wider = int(hw_max_width * _expand)
                    if _wider > int(WIDTH * 0.40):   # cap at 40 % of canvas
                        break
                    _trial = wrap_to_lines(quote, hw_font, _wider,
                                           char_extra_px=hw_extra_px)
                    if len(_trial[-1]) > 1:
                        hw_max_width = _wider
                        hw_lines = _trial
                        break

            # ── Validate: no non-whitespace characters may be dropped ─────────
            # Wrapping intentionally restructures whitespace (paragraph breaks
            # collapse, word-boundary spaces become line breaks), so compare
            # with whitespace stripped — only real content loss should fail this.
            _strip_ws = lambda s: re.sub(r"\s+", "", s)
            if _strip_ws("".join(hw_lines)) != _strip_ws(quote):
                raise RuntimeError(
                    f"Typography engine dropped characters!\n"
                    f"  expected ({len(quote)}): {quote!r}\n"
                    f"  got      ({len(''.join(hw_lines))}): {''.join(hw_lines)!r}"
                )

            # Replace CJK commas/periods with a half-width space for rendering only.
            # The original text was already validated above — nothing is dropped.
            # HanziPen SC renders ，as a tiny tick; a breath of space reads more
            # naturally in the handwriting aesthetic.
            _PUNCT_SPACE = str.maketrans('，。、；：', '     ')
            hw_text = "\n".join(
                line.translate(_PUNCT_SPACE) for line in hw_lines
            )

            hw_color   = theme["text"]
            # PingFang SC renders CJK punctuation correctly where HanziPen SC fails
            punct_font = get_font(font_name, hw_size)

            # Position and alignment: pass the right edge x so each line's
            # right edge meets the same x as the metadata (right-aligned cluster).
            # For center/left layouts, fall back to block-left positioning.
            if anchor == "rt":
                hw_pos       = (x, y)
                hw_text_align = "right"
            elif anchor == "mt":
                hw_pos       = (max(0, x - hw_max_width // 2), y)
                hw_text_align = "left"
            else:
                hw_pos       = (max(0, min(x, WIDTH - hw_max_width)), y)
                hw_text_align = "left"

            rgba_image = image.convert("RGBA") if image.mode != "RGBA" else image
            rgba_image = render_handwritten_text(
                rgba_image, hw_text, hw_pos, hw_style,
                color=hw_color, font=hw_font, punct_font=punct_font,
                text_align=hw_text_align,
            )
            image = rgba_image.convert("RGB")
            print(f"  typo : handwritten_note ({len(hw_lines)} lines, size={hw_size})")
        except Exception as hw_err:
            print(f"  typo : handwritten_note failed ({hw_err}), using standard")
            for i, line in enumerate(quote_lines):
                draw.text((x, y), line, font=font_quote, fill=theme["text"], anchor=anchor)
                y += measure_h(draw, line, font_quote)
                if i < len(quote_lines) - 1:
                    y += line_gap
    else:
        for i, line in enumerate(quote_lines):
            draw.text((x, y), line, font=font_quote, fill=theme["text"], anchor=anchor)
            y += measure_h(draw, line, font_quote)
            if i < len(quote_lines) - 1:
                y += line_gap

    # ── Save current wallpaper (overwritten each day) ────────────────────────
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    image.save(output_path)
    print(f"Current   → {output_path}")

    # ── Save dated archive copy ───────────────────────────────────────────────
    archive_date = date.today().strftime("%Y-%m-%d")
    archive_path = os.path.join("archive", f"{archive_date}.png")
    os.makedirs("archive", exist_ok=True)
    image.save(archive_path)
    print(f"Archive   → {archive_path}")


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    context_path = sys.argv[1] if len(sys.argv) > 1 else "context.json"

    try:
        context = load_context(context_path)
    except FileNotFoundError:
        print(f"Error: context file not found at '{context_path}'")
        sys.exit(1)

    try:
        style = load_style()
    except FileNotFoundError:
        print("Error: wallpaper_style.json not found.")
        sys.exit(1)

    # Try to load weather.json; fall back to context.json["weather"] if missing
    weather_data = load_weather()
    if weather_data is not None:
        print("Weather  : loaded from weather.json")
    else:
        print("Weather  : weather.json not found, using context.json fallback")

    # Try to load photos.json; fall back to context.json["photos"] if missing
    photos_data = load_photos()
    if photos_data is not None:
        print("Photos   : loaded from photos.json")
    else:
        print("Photos   : photos.json not found, using context.json fallback")

    # Determine mood from resolved weather + photos
    weather  = resolve_weather(context, weather_data)
    photos   = resolve_photos(context, photos_data)
    mood     = determine_mood(weather, photos)
    print(f"Mood     : {mood['mood']}  ({', '.join(mood['emotion_keywords'])})")

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("Error: OPENAI_API_KEY is not set.")
        print("Run:  export OPENAI_API_KEY=your-key-here")
        sys.exit(1)

    print("Generating quote...")
    quote = generate_quote(context, api_key, weather=weather_data, photos=photos_data, mood=mood)
    print(f"  {quote}\n")

    print("Rendering wallpaper...")
    render_wallpaper(quote, context, style, weather=weather_data, photos=photos_data, mood=mood)


if __name__ == "__main__":
    main()
