import json
import os
import sys
from datetime import date

from PIL import Image, ImageDraw, ImageFont

from quote_generator import generate_quote, load_context, load_weather, resolve_weather

# ── Canvas (fixed — these are the target screen dimensions, not style choices) ─
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
    """Render a soft vertical gradient."""
    image = Image.new("RGB", (width, height))
    draw  = ImageDraw.Draw(image)
    for y in range(height):
        t = y / height
        r = int(top[0] + t * (bottom[0] - top[0]))
        g = int(top[1] + t * (bottom[1] - top[1]))
        b = int(top[2] + t * (bottom[2] - top[2]))
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


# ── Main render ───────────────────────────────────────────────────────────────
def render_wallpaper(quote: str, context: dict, style: dict, weather: dict | None = None, output_path: str = OUTPUT_PATH) -> None:
    # ── Read every value from style ───────────────────────────────────────────
    font_cfg   = style.get("font", {})
    layout_cfg = style.get("layout", {})
    theme_cfg  = style.get("theme", {})

    font_name        = font_cfg.get("primary", "STHeiti Light")
    quote_size       = font_cfg.get("quote_size", 68)
    meta_size        = font_cfg.get("metadata_size", 30)

    text_width_ratio = layout_cfg.get("text_width_ratio", 0.6)
    line_spacing     = layout_cfg.get("line_spacing", 1.5)
    meta_gap         = layout_cfg.get("meta_gap", 72)       # px between meta and quote
    meta_line_gap    = layout_cfg.get("meta_line_gap", 20)  # px between date and weather
    vertical_offset  = layout_cfg.get("vertical_offset", 0) # px shift from center

    theme_name  = theme_cfg.get("background", "warm_light")
    alignment   = theme_cfg.get("alignment", "center")

    # ── Resolve theme colors ──────────────────────────────────────────────────
    theme = THEMES.get(theme_name, THEMES["warm_light"])

    # ── Build display strings ─────────────────────────────────────────────────
    # resolve_weather picks weather.json data if provided, else falls back to context.json
    resolved_weather = resolve_weather(context, weather)
    today_str        = date.today().strftime("%Y · %m · %d")
    weather_str      = format_weather_str(resolved_weather)

    # ── Fonts ─────────────────────────────────────────────────────────────────
    font_quote = get_font(font_name, quote_size)
    font_meta  = get_font(font_name, meta_size)

    # ── Background ────────────────────────────────────────────────────────────
    image = make_gradient(WIDTH, HEIGHT, theme["bg_top"], theme["bg_bottom"])
    draw  = ImageDraw.Draw(image)

    # ── Wrap and measure ──────────────────────────────────────────────────────
    max_quote_width = int(WIDTH * text_width_ratio)
    quote_lines = wrap_text(draw, quote, font_quote, max_quote_width)

    # Gap between wrapped quote lines = (line_spacing - 1) × font size
    line_gap = int(quote_size * (line_spacing - 1.0))

    date_h    = measure_h(draw, today_str,   font_meta)
    weather_h = measure_h(draw, weather_str, font_meta)
    quote_h   = (
        sum(measure_h(draw, line, font_quote) for line in quote_lines)
        + line_gap * (len(quote_lines) - 1)
    )

    total_h = date_h + meta_line_gap + weather_h + meta_gap + quote_h

    # ── Alignment anchor and x position ──────────────────────────────────────
    if alignment == "left":
        x      = (WIDTH - max_quote_width) // 2   # left edge of the text block
        anchor = "lt"                              # left-top
    else:
        x      = WIDTH // 2                        # horizontal center
        anchor = "mt"                              # middle-top

    # ── Starting y: vertical center + offset ─────────────────────────────────
    y = (HEIGHT - total_h) // 2 + vertical_offset

    # ── Draw date ─────────────────────────────────────────────────────────────
    draw.text((x, y), today_str, font=font_meta, fill=theme["meta"], anchor=anchor)
    y += date_h + meta_line_gap

    # ── Draw weather ──────────────────────────────────────────────────────────
    draw.text((x, y), weather_str, font=font_meta, fill=theme["meta"], anchor=anchor)
    y += weather_h + meta_gap

    # ── Draw quote ────────────────────────────────────────────────────────────
    for i, line in enumerate(quote_lines):
        draw.text((x, y), line, font=font_quote, fill=theme["text"], anchor=anchor)
        y += measure_h(draw, line, font_quote)
        if i < len(quote_lines) - 1:
            y += line_gap

    # ── Save ──────────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    image.save(output_path)
    print(f"Wallpaper saved → {output_path}")


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

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("Error: OPENAI_API_KEY is not set.")
        print("Run:  export OPENAI_API_KEY=your-key-here")
        sys.exit(1)

    print("Generating quote...")
    quote = generate_quote(context, api_key, weather=weather_data)
    print(f"  {quote}\n")

    print("Rendering wallpaper...")
    render_wallpaper(quote, context, style, weather=weather_data)


if __name__ == "__main__":
    main()
