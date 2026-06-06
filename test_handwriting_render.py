"""
test_handwriting_render.py

Generate 3 desktop wallpaper samples demonstrating the handwritten_note
typography engine. Each sample uses the same sentence with a different
background scene.

Output:
  outputs/handwriting_test_01.png  — sea
  outputs/handwriting_test_02.png  — window / cloudy sky
  outputs/handwriting_test_03.png  — plain paper

Run:
  python test_handwriting_render.py
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

# Allow imports from src/
sys.path.insert(0, os.path.dirname(__file__))

from src.typography_engine import (
    load_typography_style,
    choose_font,
    render_handwritten_text,
    wrap_to_lines,
)

WIDTH  = 2560
HEIGHT = 1440
TEXT   = "祝你的人生渐入佳境"
OUT_DIR = "outputs"
FONT_SIZE = 114


# ── Background generators ─────────────────────────────────────────────────────

def _make_sea_bg() -> Image.Image:
    """Open sea, clear sky — wide horizon, blue water, pale sky."""
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)

    horizon = int(HEIGHT * 0.42)

    # Sky gradient: pale dawn blue → horizon haze
    for y in range(horizon):
        t = y / horizon
        t2 = t * t * (3 - 2 * t)
        r = int(178 + t2 * (205 - 178))
        g = int(210 + t2 * (222 - 210))
        b = int(235 + t2 * (228 - 235))
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # Sea gradient: turquoise-blue → deep slate
    for y in range(horizon, HEIGHT):
        t = (y - horizon) / (HEIGHT - horizon)
        t2 = t * t * (3 - 2 * t)
        r = int(75  + t2 * (38  - 75))
        g = int(148 + t2 * (90  - 148))
        b = int(185 + t2 * (128 - 185))
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # Very light vignette on edges
    _add_vignette(img, strength=0.20)
    return img


def _make_window_bg() -> Image.Image:
    """
    View through a car window looking out at misty lake/sky.
    Frame suggested by directional darkening — heavy at top (car roof),
    lighter at bottom, thin strips at left/right (car pillars).
    No elliptical vignette.
    """
    from PIL import ImageFilter

    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)

    # Base scene: cool misty overcast — pale blue-gray, horizon slightly lighter
    for y in range(HEIGHT):
        t = y / HEIGHT
        t2 = t * t * (3 - 2 * t)
        r = int(198 + t2 * (165 - 198))
        g = int(210 + t2 * (178 - 210))
        b = int(224 + t2 * (196 - 224))
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # Directional frame: top dark band (car roof overhead)
    top_band = Image.new("L", (WIDTH, HEIGHT), 0)
    tb_draw  = ImageDraw.Draw(top_band)
    fade_h   = int(HEIGHT * 0.38)          # how far the shadow reaches down
    for y in range(fade_h):
        t = 1.0 - (y / fade_h) ** 0.6     # fast falloff — dark near top, fades quickly
        alpha = int(220 * t)
        tb_draw.line([(0, y), (WIDTH, y)], fill=alpha)
    top_band = top_band.filter(ImageFilter.GaussianBlur(radius=40))

    dark = Image.new("RGB", (WIDTH, HEIGHT), (14, 12, 10))
    img.paste(dark, mask=top_band)

    # Thin side pillars (left/right A/B posts)
    for side_x, direction in [(0, 1), (WIDTH, -1)]:
        side_band = Image.new("L", (WIDTH, HEIGHT), 0)
        sb_draw   = ImageDraw.Draw(side_band)
        fade_w    = int(WIDTH * 0.10)
        for dx in range(fade_w):
            t = 1.0 - (dx / fade_w) ** 0.5
            alpha = int(160 * t)
            lx = side_x + direction * dx
            if 0 <= lx < WIDTH:
                sb_draw.line([(lx, 0), (lx, HEIGHT)], fill=alpha)
        side_band = side_band.filter(ImageFilter.GaussianBlur(radius=60))
        img.paste(dark, mask=side_band)

    return img


def _make_paper_bg() -> Image.Image:
    """Warm cream paper — like a journal page, slight warmth gradient."""
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)

    for y in range(HEIGHT):
        t = y / HEIGHT
        t2 = t * t * (3 - 2 * t)
        r = int(248 + t2 * (228 - 248))
        g = int(243 + t2 * (220 - 243))
        b = int(232 + t2 * (205 - 232))
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # Very subtle paper texture: faint horizontal grain
    import random
    rng = random.Random(7)
    for _ in range(HEIGHT * 4):
        px = rng.randint(0, WIDTH - 1)
        py = rng.randint(0, HEIGHT - 1)
        noise = rng.randint(-4, 4)
        px_color = img.getpixel((px, py))
        nc = tuple(max(0, min(255, c + noise)) for c in px_color)
        img.putpixel((px, py), nc)

    return img


def _add_vignette(
    img: Image.Image,
    strength: float = 0.35,
    color: tuple = (0, 0, 0),
) -> None:
    """Darken the edges of img in-place, leaving the center bright."""
    from PIL import ImageFilter, ImageOps

    w, h = img.size

    # Build a bright-center mask: white oval → heavy blur → invert = dark edges
    center_mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(center_mask)
    pad_x = int(w * 0.12)
    pad_y = int(h * 0.12)
    mask_draw.ellipse([pad_x, pad_y, w - pad_x, h - pad_y], fill=255)
    center_mask = center_mask.filter(
        ImageFilter.GaussianBlur(radius=int(min(w, h) * 0.09))
    )

    # Invert: edges are now bright (255 = apply dark color)
    edge_mask = ImageOps.invert(center_mask)
    # Scale by strength so 1.0 = full black at corners
    edge_mask = edge_mask.point(lambda p: int(p * strength))

    img.paste(Image.new("RGB", (w, h), color), mask=edge_mask)


# ── Text layout helper ────────────────────────────────────────────────────────

def _natural_split(text: str, font, canvas_width: int) -> str:
    """
    Split text into two lines at the nearest midpoint.
    Returns a newline-joined string.
    """
    mid = len(text) // 2
    # Prefer splitting at midpoint — for 9 chars: 5+4 or 4+5
    line1 = text[:mid + (1 if len(text) % 2 else 0)]
    line2 = text[mid + (1 if len(text) % 2 else 0):]
    if not line2:
        return text
    return line1 + "\n" + line2


# ── Main render loop ──────────────────────────────────────────────────────────

def render_sample(
    background: Image.Image,
    text: str,
    color: tuple,
    position_hint: str,
    out_path: str,
    label: str,
) -> None:
    style = load_typography_style("handwritten_note")
    font  = choose_font("handwritten_note", FONT_SIZE)

    # Split the 9-character sentence across two lines
    lines_text = _natural_split(text, font, WIDTH)

    # Calculate text block size for positioning
    lines = lines_text.split("\n")
    from PIL import ImageDraw as _ID
    _probe = _ID.Draw(Image.new("RGBA", (1, 1)))
    char_bbox = _probe.textbbox((0, 0), "国", font=font)
    char_h = char_bbox[3] - char_bbox[1]
    char_w = char_bbox[2] - char_bbox[0]
    line_gap = int(char_h * (style["spacing"]["line_spacing"] - 1.0))

    block_h = char_h * len(lines) + line_gap * (len(lines) - 1)
    block_w = max(
        sum(
            _probe.textbbox((0, 0), c, font=font)[2]
            for c in line
        )
        for line in lines
    )

    # Position the text block
    if position_hint == "center_right":
        # Sea: sit fully inside the water zone (horizon at ~42%, text at ~50%)
        x = int(WIDTH * 0.52)
        y = int(HEIGHT * 0.50)
    elif position_hint == "center_left":
        # Window: left-center inside the view area, clear of the dark frame
        x = int(WIDTH * 0.14)
        y = int(HEIGHT * 0.36)
    else:  # center
        x = int((WIDTH - block_w) // 2)
        y = int((HEIGHT - block_h) // 2)

    # Render onto background
    bg = background.convert("RGBA")
    result = render_handwritten_text(
        bg, lines_text, (x, y), style, color=color, font=font
    )
    final = result.convert("RGB")

    os.makedirs(OUT_DIR, exist_ok=True)
    final.save(out_path)
    print(f"  saved : {out_path}  [{label}]")


def main():
    print(f"\nHandwriting render test — '{TEXT}'")
    print(f"Canvas: {WIDTH}×{HEIGHT}")
    print()

    # ── Sample 1: Sea ─────────────────────────────────────────────────────────
    print("Rendering 01 — sea background")
    render_sample(
        background     = _make_sea_bg(),
        text           = TEXT,
        color          = (255, 255, 255),
        position_hint  = "center_right",
        out_path       = os.path.join(OUT_DIR, "handwriting_test_01.png"),
        label          = "sea, white text",
    )

    # ── Sample 2: Window / cloudy sky ─────────────────────────────────────────
    print("Rendering 02 — window / cloudy background")
    render_sample(
        background     = _make_window_bg(),
        text           = TEXT,
        color          = (248, 246, 242),
        position_hint  = "center_left",
        out_path       = os.path.join(OUT_DIR, "handwriting_test_02.png"),
        label          = "window/cloudy, near-white text",
    )

    # ── Sample 3: Paper ───────────────────────────────────────────────────────
    print("Rendering 03 — paper background")
    render_sample(
        background     = _make_paper_bg(),
        text           = TEXT,
        color          = (42, 32, 16),
        position_hint  = "center",
        out_path       = os.path.join(OUT_DIR, "handwriting_test_03.png"),
        label          = "paper, dark ink text",
    )

    print("\nDone. Check outputs/ folder.")


if __name__ == "__main__":
    main()
