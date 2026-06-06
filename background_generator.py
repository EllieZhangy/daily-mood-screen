"""
background_generator.py

Generates the wallpaper background image and saves it to output/background.png.

Pipeline:
  1. Build prompt   — background_prompt_builder.build_background_prompt()
  2. Call image API — _call_image_api()   ← plug your API in here
  3. Post-process   — desaturate, reduce contrast, add film grain
  4. Save           — output/background.png  (read by wallpaper_renderer.py)

When no API key is set, a gradient placeholder is used so the rest of the
pipeline always works.
"""

import io
import os
from PIL import Image, ImageDraw, ImageEnhance, ImageChops

OUTPUT_PATH = "output/background.png"
WIDTH, HEIGHT = 2560, 1440


# ─────────────────────────────────────────────────────────────────────────────
# IMAGE API INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────
# Replace _call_image_api() to connect to any image generation provider.
#
# Current implementation: OpenAI DALL-E 3
#   Reads OPENAI_API_KEY from the environment — never hardcoded.
#   Raises RuntimeError if the key is not set (triggers placeholder fallback).
#
# To switch providers:
#   - Stability AI:  call the REST API with requests, return Image.open(io.BytesIO(r.content))
#   - Midjourney:    use their API wrapper, download the URL, return Image.open(...)
#   - Replicate:     replicate.run("stability-ai/sdxl", ...), download output URL
#   - Local model:   call subprocess / local server, return PIL Image directly
# ─────────────────────────────────────────────────────────────────────────────

def _call_image_api(prompt: str) -> Image.Image:
    """
    ── PLUG YOUR IMAGE API IN HERE ──────────────────────────────────────────

    Input:  prompt (str)  — complete photographic brief
    Output: PIL.Image.Image (RGB, any size — will be resized by caller)
    Raises: any Exception on failure (caller falls back to placeholder)

    ─────────────────────────────────────────────────────────────────────────
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    # ── OpenAI DALL-E 3 ───────────────────────────────────────────────────
    import base64
    from openai import OpenAI

    client   = OpenAI(api_key=api_key)
    response = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1536x1024",    # closest 3:2 landscape available
        quality="medium",
        n=1,
    )
    b64 = response.data[0].b64_json
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")


# ── Image processing ──────────────────────────────────────────────────────────

def _resize_cover(img: Image.Image, width: int, height: int) -> Image.Image:
    """Scale + center-crop to fill canvas exactly (CSS object-fit: cover)."""
    sw, sh = img.size
    scale  = max(width / sw, height / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    img    = img.resize((nw, nh), Image.LANCZOS)
    x, y   = (nw - width) // 2, (nh - height) // 2
    return img.crop((x, y, x + width, y + height))


def _add_film_grain(img: Image.Image, intensity: float = 0.10) -> Image.Image:
    """Photographic grain via low-res noise + bilinear upscale. No numpy."""
    if intensity <= 0:
        return img
    w, h   = img.size
    gw, gh = max(1, w // 6), max(1, h // 6)
    spread = max(1, int(intensity * 22))
    raw    = os.urandom(gw * gh)
    hr     = 2 * spread + 1
    data   = bytes([max(0, min(255, 128 + (b % hr) - spread)) for b in raw])
    grain  = Image.frombytes("L", (gw, gh), data).resize((w, h), Image.BILINEAR).convert("RGB")
    return ImageChops.add(img, grain, scale=1, offset=-128)


def _process_photo(img: Image.Image) -> Image.Image:
    """
    Remove the AI-generated sheen: slight desaturation, softened contrast,
    and a touch of film grain so the image feels photographic.
    """
    img = ImageEnhance.Color(img).enhance(0.82)      # -18% saturation
    img = ImageEnhance.Contrast(img).enhance(0.90)   # -10% contrast
    img = _add_film_grain(img, intensity=0.10)
    return img


# ── Text-zone readability overlay ─────────────────────────────────────────────

def _apply_text_overlay(
    img:            Image.Image,
    dark_tones:     bool  = False,
    is_light_text:  bool  = False,
) -> Image.Image:
    """
    Apply a soft gradient overlay to the bottom-left text zone so the quote
    always reads cleanly against the photo.

    The overlay fades from opaque at the bottom-left corner to transparent.

      dark_tones=True  (night/rainy photo) + is_light_text=True  → minimal dark touch
      dark_tones=False (bright photo)      + is_light_text=False → light scrim to brighten
      dark_tones=False (bright photo)      + is_light_text=True  → dark scrim for contrast
    """
    w, h = img.size
    sw   = int(w * 0.36)    # scrim zone width  (~text column + breathing room)
    sh   = int(h * 0.44)    # scrim zone height

    # Determine scrim parameters
    if is_light_text and not dark_tones:
        color, opacity = (0, 0, 0), 0.50       # dark photo area for light text
    elif is_light_text and dark_tones:
        color, opacity = (0, 0, 0), 0.20       # already dark enough, minor boost
    elif not is_light_text and not dark_tones:
        color, opacity = (255, 255, 255), 0.28  # lighten area for dark text
    else:
        color, opacity = (255, 255, 255), 0.18  # dark photo with dark text — minimal

    # Build gradient mask at 1/8 scale — fades from right edge inward
    mw, mh = max(4, sw // 8), max(4, sh // 8)
    data   = []
    for y in range(mh):
        for x in range(mw):
            fx = x / (mw - 1) if mw > 1 else 1.0   # 1.0 at right edge
            fy = y / (mh - 1) if mh > 1 else 1.0   # 1.0 at bottom
            t  = fx * fy
            t  = t * t * (3 - 2 * t)                # smooth-step
            data.append(int(t * opacity * 255))

    mask    = Image.frombytes("L", (mw, mh), bytes(data)).resize((sw, sh), Image.BILINEAR)
    scrim   = Image.new("RGB", (sw, sh), color)
    x_off   = w - sw                                # right-aligned
    region  = img.crop((x_off, h - sh, w, h))
    blended = Image.composite(scrim, region, mask)

    result = img.copy()
    result.paste(blended, (x_off, h - sh))
    return result


# ── Gradient placeholder ───────────────────────────────────────────────────────

def _gradient_placeholder(mood_name: str, weather_cat: str) -> Image.Image:
    """
    Fallback background when no image API is available.
    A multi-stop gradient calibrated to the mood/weather palette.
    Matches the visual_engine.py atmosphere system.
    """
    # Palette per weather category (top → bottom)
    PALETTES = {
        "cold":   [(20, 24, 34),   (24, 28, 40),   (10, 12, 18)],
        "rainy":  [(26, 30, 28),   (20, 22, 22),   (10, 12, 12)],
        "cloudy": [(240, 236, 230), (226, 222, 215), (210, 205, 198)],
        "sunny":  [(248, 243, 235), (238, 230, 216), (218, 206, 188)],
    }
    stops = PALETTES.get(weather_cat, PALETTES["cloudy"])

    img  = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        t  = y / HEIGHT
        t  = t * t * (3 - 2 * t)

        # Find enclosing stops (3-stop interpolation)
        if t < 0.5:
            a, b, local_t = stops[0], stops[1], t / 0.5
        else:
            a, b, local_t = stops[1], stops[2], (t - 0.5) / 0.5
        local_t = local_t * local_t * (3 - 2 * local_t)

        r = int(a[0] + local_t * (b[0] - a[0]))
        g = int(a[1] + local_t * (b[1] - a[1]))
        b_ = int(a[2] + local_t * (b[2] - a[2]))
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b_))

    return img


# ── Main entry point ───────────────────────────────────────────────────────────

def generate_background(
    mood:         dict,
    weather:      dict,
    photos:       dict | None = None,
    visual_style: dict | None = None,
    text_color:   tuple       = (52, 46, 40),
    output_path:  str         = OUTPUT_PATH,
    use_ai:       bool        = False,
) -> Image.Image:
    """
    Full pipeline: prompt → (optionally) API → resize → post-process → text overlay → save.

    Args:
        mood:         mood dict (from mood_engine.determine_mood)
        weather:      resolved weather dict
        photos:       resolved photos dict
        visual_style: loaded visual preset (for overlay direction hint)
        text_color:   RGB of the quote text (used to pick scrim direction)
        output_path:  where to save the result
        use_ai:       if True, call DALL-E 3; if False, use gradient placeholder directly

    Returns:
        PIL.Image.Image (RGB, 2560×1440)
    """
    from background_prompt_builder import build_background_prompt
    from mood_engine import categorize_weather

    weather_cat = categorize_weather(weather)
    mood_name   = mood.get("mood", "cloudy_solitude")

    # ── Build prompt ─────────────────────────────────────────────────────────
    prompt_data = build_background_prompt(
        mood=mood,
        weather=weather,
        photos=photos,
        visual_style=visual_style,
    )
    print(f"  scene : {prompt_data['style_note']}")

    # ── Generate image ────────────────────────────────────────────────────────
    used_api = False
    if use_ai:
        try:
            raw = _call_image_api(prompt_data["prompt"])
            used_api = True
            print("  source: DALL-E 3")
        except Exception as e:
            print(f"  source: gradient placeholder (API failed: {e})")
            raw = _gradient_placeholder(mood_name, weather_cat)
    else:
        print("  source: gradient placeholder (use_ai_background=false)")
        raw = _gradient_placeholder(mood_name, weather_cat)

    # ── Resize to canvas ──────────────────────────────────────────────────────
    img = _resize_cover(raw, WIDTH, HEIGHT)

    # ── Analog post-processing (only for API-generated images) ────────────────
    if used_api:
        img = _process_photo(img)

    # ── Readability overlay ───────────────────────────────────────────────────
    tr, tg, tb    = text_color
    is_light_text = (0.299 * tr + 0.587 * tg + 0.114 * tb) > 128
    img = _apply_text_overlay(
        img,
        dark_tones=prompt_data["dark_tones"],
        is_light_text=is_light_text,
    )

    # ── Save ──────────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    img.save(output_path)
    print(f"  saved : {output_path}")
    return img
