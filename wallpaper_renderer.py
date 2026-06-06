import json
import os
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


# ── Weather string builder ────────────────────────────────────────────────────
def format_weather_str(weather: dict) -> str:
    """
    Build the weather metadata line shown on the wallpaper.
    Includes location only when the weather dict has one (i.e. from weather.json).

    Examples:
      weather.json present  →  "Los Angeles · Cloudy · 12°C"
      context.json fallback →  "Cloudy · 12°C"
    """
    parts = []
    location  = weather.get("location", "")
    condition = weather.get("condition", "")
    temp      = weather.get("temperature", "")
    unit      = weather.get("unit", "C")

    if location:
        parts.append(location)
    if condition:
        parts.append(condition.capitalize())
    if temp != "":
        # ℃/℉ are single Unicode glyphs — avoids the kerning gap that °C produces in STHeiti
        unit_glyph = {"C": "℃", "F": "℉"}.get(unit, f"°{unit}")
        parts.append(f"{temp}{unit_glyph}")

    return " · ".join(parts)


# ── Photos string builder ─────────────────────────────────────────────────────
def format_photos_str(photos: dict) -> str:
    """
    Build the photos metadata line shown below the weather line.

    Examples:
      theme=friends, count=6  →  "Friends · 6 Photos"
      theme=none, count=0     →  ""  (nothing drawn)
    """
    theme = photos.get("theme", "none")
    count = photos.get("photo_count", 0)

    parts = []
    if theme and theme != "none":
        parts.append(theme.capitalize())
    if count:
        parts.append(f"{count} Photos")

    return " · ".join(parts)


# ── Mood string builder ───────────────────────────────────────────────────────
def format_mood_str(mood: dict) -> str:
    """
    Build the mood metadata line shown below the photos line.
    "cold_reunion" → "Mood · Cold Reunion"
    Returns empty string if mood is empty.
    """
    mood_name = mood.get("mood", "")
    if not mood_name:
        return ""
    label = mood_name.replace("_", " ").title()
    return f"Mood · {label}"


# ── Main render ───────────────────────────────────────────────────────────────
def render_wallpaper(quote: str, context: dict, style: dict, weather: dict | None = None, photos: dict | None = None, mood: dict | None = None, visual_style: dict | None = None, output_path: str = OUTPUT_PATH) -> None:
    # ── Read base values from wallpaper_style.json ────────────────────────────
    font_cfg   = style.get("font", {})
    layout_cfg = style.get("layout", {})
    theme_cfg  = style.get("theme", {})

    font_name        = font_cfg.get("primary", "STHeiti Light")
    quote_size       = font_cfg.get("quote_size", 68)
    meta_size        = font_cfg.get("metadata_size", 30)

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
    resolved_weather = resolve_weather(context, weather)
    resolved_photos  = resolve_photos(context, photos)
    resolved_mood    = mood if mood is not None else determine_mood(resolved_weather, resolved_photos)
    today_str        = date.today().strftime("%Y · %m · %d")
    weather_str      = format_weather_str(resolved_weather)
    photos_str       = format_photos_str(resolved_photos)
    mood_str         = format_mood_str(resolved_mood)

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
