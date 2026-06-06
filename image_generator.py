"""
image_generator.py

Photographic background generation for Daily Mood Screen.

Uses DALL-E 3 to generate a real photograph matched to the current mood +
weather. Both visual families from the reference library are covered:

  Family A — Atmospheric Landscape: mountains, coastlines, roads, city dusk,
             rainy streets, foggy valleys, snowy fields, sunsets
  Family B — Everyday Life: café, books, flowers, travel objects, fruit,
             bicycle, candle, cherry blossom, morning light

After downloading, the image is processed through a short analog pipeline:
  1. Resize/crop to canvas (cover-fit)
  2. Light desaturation + contrast reduction (removes AI-sheen)
  3. Film grain
  4. Readability scrim over the text zone (bottom-left)

Results are cached by mood + weather + date so repeated runs within a day
cost nothing.
"""

import io
import os
import random
from datetime import date as _date
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageChops


# ── Scene library ─────────────────────────────────────────────────────────────
# Each entry:
#   id        — short identifier (used in cache filenames)
#   family    — "landscape" | "still_life"
#   tags      — mood/weather tokens that match this scene
#   prompt    — complete DALL-E 3 prompt
#   dark_bg   — True if the scene tends toward dark tones (hint for scrim direction)
#
# Prompts are written as photographic briefs: scene, light, palette, style.
# "no visible text, no watermarks" ends every prompt.

SCENES = [

    # ── Landscape family ──────────────────────────────────────────────────────

    {
        "id": "rainy_window_city",
        "family": "landscape",
        "tags": ["rainy", "solitude", "introspection", "reflection", "urban", "shelter"],
        "prompt": (
            "Rain droplets on a glass window pane, blurred city rooftops and wet slate tiles "
            "visible beyond, overcast grey sky, warm indoor glow reflecting faintly in the glass, "
            "cool grey-green and charcoal tones, 35mm film photography, shallow focus on the rain "
            "drops, soft bokeh background, quiet and contemplative, no visible text, no watermarks"
        ),
        "dark_bg": True,
    },
    {
        "id": "foggy_mountain_valley",
        "family": "landscape",
        "tags": ["cloudy", "solitude", "calm", "nature", "stillness", "reflection"],
        "prompt": (
            "Morning fog filling a mountain valley, layers of pine-covered ridgelines emerging "
            "from white mist, soft pre-dawn atmospheric light, blue-grey and sage green palette, "
            "wide landscape composition, 35mm film photography, vast empty sky, peaceful and "
            "solitary, no people, no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "mountain_road_golden",
        "family": "landscape",
        "tags": ["sunny", "movement", "journey", "freedom", "travel", "discovery"],
        "prompt": (
            "Empty winding asphalt road disappearing into pine forest toward distant mountain "
            "peaks, soft golden morning light raking low through the trees, warm amber and deep "
            "forest green tones, horizontal landscape composition, Kodak Portra 400 film "
            "aesthetic, no people, no vehicles, cinematic widescreen, no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "still_lake_dawn",
        "family": "landscape",
        "tags": ["sunny", "stillness", "nature", "calm", "reflection", "openness"],
        "prompt": (
            "Perfectly still mountain lake at dawn reflecting the pale rose and blue sky, "
            "surrounding pine trees mirrored in glassy water, soft pre-sunrise light, rose gold "
            "and pale blue palette, wide format landscape, Fuji Velvia analog film aesthetic, "
            "tranquil and minimal, no people, no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "snowy_field_lone_tree",
        "family": "landscape",
        "tags": ["cold", "solitude", "introspection", "stillness", "distance"],
        "prompt": (
            "Single bare birch tree in an expansive snow-covered field at late afternoon, long "
            "blue shadow cast across white snow, cold flat winter light, pale grey sky, "
            "near-monochrome palette of white and steel blue, 35mm film photography, minimal "
            "sparse composition, vast empty negative space, no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "warm_window_snow_night",
        "family": "landscape",
        "tags": ["cold", "homecoming", "warmth", "shelter", "family", "reunion", "belonging"],
        "prompt": (
            "Warm amber light glowing through a frosted window of a wooden house, dark blue "
            "snowy evening outside, bare tree branches silhouetted against the night sky, "
            "intimate and sheltered feeling, deep navy blue and warm amber palette, analog film, "
            "evening domestic scene, no visible text, no watermarks"
        ),
        "dark_bg": True,
    },
    {
        "id": "rainy_cobblestone_reflections",
        "family": "landscape",
        "tags": ["rainy", "nostalgia", "discovery", "urban", "memory", "melancholy"],
        "prompt": (
            "Quiet rain-washed cobblestone street at dusk, golden street lamp reflections "
            "shimmering in wet stone, soft rain falling, narrow alley with warm lit shopfronts, "
            "amber and dark charcoal tones, 35mm film street photography, cinematic, "
            "no people visible, no visible text, no watermarks"
        ),
        "dark_bg": True,
    },
    {
        "id": "train_window_countryside",
        "family": "landscape",
        "tags": ["rainy", "movement", "journey", "transit", "cloudy", "distance"],
        "prompt": (
            "View through a train window with rain streaks on glass, blurred passing countryside "
            "in soft motion beyond, overcast grey light outside, warm amber interior reflection "
            "visible in the glass, gentle motion blur on the landscape, Fuji Pro 400H film "
            "aesthetic, quiet transit mood, no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "coastal_beach_morning",
        "family": "landscape",
        "tags": ["sunny", "freedom", "openness", "connection", "movement", "friends"],
        "prompt": (
            "Wide empty beach at early morning low tide, gentle waves spreading across pale sand, "
            "vast open pale blue sky with soft clouds, warm pale gold morning light, far horizon, "
            "a single distant figure walking near the water seen from far behind, "
            "Scandinavian coastal photography aesthetic, no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "autumn_forest_path",
        "family": "landscape",
        "tags": ["sunny", "journey", "nostalgia", "nature", "calm", "memory"],
        "prompt": (
            "Narrow winding path through an autumn forest, golden and amber leaves falling from "
            "the canopy, dappled afternoon sunlight filtering through the trees, warm amber and "
            "burnt orange with deep forest shadow, analog film photography, shallow depth of "
            "field on falling leaves, Kodak Gold 200 aesthetic, no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "city_dusk_skyline",
        "family": "landscape",
        "tags": ["cloudy", "cold", "urban", "loneliness", "introspection", "movement", "evening"],
        "prompt": (
            "City skyline at blue hour dusk, buildings lit warmly against fading purple-blue sky, "
            "atmospheric haze over the river below, city lights beginning to glow, "
            "deep purple-blue and amber palette, medium format film photography, wide cityscape, "
            "emotional distance and scale, no visible text, no watermarks"
        ),
        "dark_bg": True,
    },
    {
        "id": "countryside_grey_field",
        "family": "landscape",
        "tags": ["cloudy", "solitude", "calm", "nature", "reflection", "quiet"],
        "prompt": (
            "Open countryside field under dramatic overcast sky, dry golden grasses bending in "
            "gentle wind, soft grey cloud ceiling, warm muted tan and grey tones, no harsh "
            "shadows, wide composition with sky dominating two thirds, 35mm film landscape, "
            "quiet and contemplative, no people, no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "cherry_blossoms_path",
        "family": "landscape",
        "tags": ["sunny", "cloudy", "journey", "spring", "beauty", "movement", "simplicity"],
        "prompt": (
            "Cherry blossom branches arching over a stone path in a quiet garden, pale pink "
            "petals drifting down, soft even spring light under slight overcast, grey stone "
            "path, fresh green grass, Fuji Superia 400 film aesthetic, delicate and transient, "
            "no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "sunset_silhouette_ocean",
        "family": "landscape",
        "tags": ["sunny", "evening", "freedom", "journey", "wonder", "vast"],
        "prompt": (
            "Tropical sunset over the ocean, tree silhouettes against amber and deep crimson sky, "
            "glowing horizon reflected on calm water, cinematic wide composition, "
            "Fuji Velvia rich saturated film aesthetic, emotional and vast, "
            "no visible text, no watermarks"
        ),
        "dark_bg": True,
    },
    {
        "id": "frost_train_window",
        "family": "landscape",
        "tags": ["cold", "journey", "solitude", "introspection", "nostalgia", "transit"],
        "prompt": (
            "Intricate frost crystal patterns on a window, winter landscape barely visible as "
            "a blur beyond the frozen glass, blue-white and silver tones, close-up texture of "
            "ice crystals, 35mm film, cold and quietly beautiful, no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "open_highway_sky",
        "family": "landscape",
        "tags": ["sunny", "cloudy", "movement", "journey", "freedom", "travel", "discovery"],
        "prompt": (
            "View from a car passenger seat of a long straight highway through vast open "
            "landscape, horizon stretching far ahead, dramatic sky with clouds above, warm "
            "afternoon light, road trip documentary photography, Kodak Portra 400 aesthetic, "
            "sense of distance and possibility, no visible text, no watermarks"
        ),
        "dark_bg": False,
    },

    # ── Still life family ─────────────────────────────────────────────────────

    {
        "id": "café_coffee_book",
        "family": "still_life",
        "tags": ["cloudy", "rainy", "memory", "nostalgia", "warmth", "comfort", "simplicity",
                 "solitude", "stillness"],
        "prompt": (
            "Ceramic coffee mug and a well-worn paperback book on a wooden café table, soft "
            "directional morning window light casting gentle shadows, warm honey wood tones, "
            "steam rising from the coffee, Kinfolk magazine aesthetic, natural light still life, "
            "shallow depth of field, no visible text on book, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "wildflowers_vase",
        "family": "still_life",
        "tags": ["sunny", "cloudy", "warmth", "calm", "comfort", "home", "beauty", "simplicity"],
        "prompt": (
            "Small bunch of wildflowers in a clear glass vase on a linen cloth, soft diffuse "
            "daylight from the side casting gentle shadows, white and pale yellow blooms, "
            "sage green stems, warm linen background, still life photography, "
            "Kinfolk editorial aesthetic, delicate and minimal, no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "vintage_travel_flatlay",
        "family": "still_life",
        "tags": ["cloudy", "sunny", "journey", "nostalgia", "memories", "travel", "longing",
                 "discovery"],
        "prompt": (
            "Flat lay of vintage travel objects on a wooden surface: worn map, analog film "
            "camera, small souvenirs, pressed wildflowers, soft warm afternoon light, aged "
            "paper and brass tones, natural wood grain, analog nostalgia aesthetic, "
            "editorial still life, no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "books_rainy_window",
        "family": "still_life",
        "tags": ["rainy", "cloudy", "solitude", "introspection", "stillness", "calm", "shelter",
                 "comfort"],
        "prompt": (
            "Stack of well-worn books beside a rain-streaked window, soft grey rainy daylight "
            "filtering in, a half-empty cup of tea on a saucer, cool grey-blue and aged paper "
            "tones, quiet interior scene, still life photography, Kinfolk aesthetic, "
            "contemplative mood, no visible text on spines, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "café_two_cups",
        "family": "still_life",
        "tags": ["sunny", "cloudy", "connection", "friends", "reunion", "warmth", "togetherness"],
        "prompt": (
            "Two ceramic coffee cups on a marble café table by a window, morning light, a "
            "small plate with a croissant, warm cream and grey marble tones, Parisian café "
            "atmosphere, lifestyle photography, editorial, intimate and welcoming, "
            "no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "fruit_summer_table",
        "family": "still_life",
        "tags": ["sunny", "simplicity", "warmth", "food", "comfort", "home", "daily"],
        "prompt": (
            "Fresh seasonal fruit casually arranged on a linen cloth in soft afternoon daylight: "
            "peaches, figs, a small bunch of grapes, warm golden-yellow and deep tones, "
            "rustic Mediterranean still life, Kinfolk editorial aesthetic, natural abundance, "
            "no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "candle_evening",
        "family": "still_life",
        "tags": ["cold", "rainy", "solitude", "intimacy", "calm", "shelter", "quiet", "evening"],
        "prompt": (
            "Single white candle burning in a ceramic holder on a dark wooden surface, warm "
            "amber candlelight glowing against deep charcoal shadow, intimate close-up, "
            "surrounding darkness, analog film photography, slow mood, quietly meditative, "
            "no visible text, no watermarks"
        ),
        "dark_bg": True,
    },
    {
        "id": "bicycle_stone_wall",
        "family": "still_life",
        "tags": ["sunny", "cloudy", "journey", "movement", "simplicity", "morning", "discovery"],
        "prompt": (
            "Old bicycle leaning against a sunlit stone wall with climbing vines and small "
            "flowers, dappled morning light, warm stone and faded paint tones, soft green, "
            "European village atmosphere, analog lifestyle photography, quiet and charming, "
            "no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "picnic_afternoon",
        "family": "still_life",
        "tags": ["sunny", "connection", "friends", "reunion", "warmth", "food", "togetherness",
                 "joy"],
        "prompt": (
            "Picnic arrangement on a blanket on green grass: crusty bread, soft cheese, wine "
            "glasses, seasonal fruit, shot from slightly above, dappled afternoon sunlight "
            "through trees, warm and casual lifestyle photography, editorial weekend atmosphere, "
            "no people visible in frame, no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "morning_light_bedside",
        "family": "still_life",
        "tags": ["sunny", "warmth", "stillness", "calm", "home", "simplicity", "morning"],
        "prompt": (
            "Soft morning sunlight streaming through sheer linen curtains, warm golden light "
            "on a white bedside table, a book and reading glasses, a small plant, "
            "warm white and pale gold tones, intimate domestic photography, "
            "Kinfolk aesthetic, peaceful and unhurried, no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "reading_café_moment",
        "family": "still_life",
        "tags": ["rainy", "cloudy", "solitude", "comfort", "introspection", "shelter",
                 "stillness", "reflection"],
        "prompt": (
            "Person seen from behind sitting alone in a quiet café, reading, window beside them "
            "with soft grey light, warm dark wood interior, coffee cup on table, intimate "
            "documentary photograph, film grain, unhurried observation, "
            "no visible text on book, no watermarks"
        ),
        "dark_bg": False,
    },
    {
        "id": "flowers_window_grey_day",
        "family": "still_life",
        "tags": ["cloudy", "rainy", "calm", "home", "stillness", "comfort", "warmth"],
        "prompt": (
            "Small bouquet of pale flowers in a simple vase on a window ledge, grey overcast "
            "day outside the window, soft even light inside, muted green and pale white tones, "
            "quiet terracotta pot alongside, interior lifestyle photography, minimal and calm, "
            "no visible text, no watermarks"
        ),
        "dark_bg": False,
    },
]


# ── Scene selection ────────────────────────────────────────────────────────────

def _select_scene(mood_name: str, weather_cat: str) -> dict:
    """
    Score scenes by tag overlap with mood tokens + weather category.
    Among equally-scoring scenes, pick at random for variety.
    """
    tokens = set(mood_name.lower().split("_")) | {weather_cat.lower()}
    scored = []
    for s in SCENES:
        score = sum(1 for t in s["tags"] if t in tokens)
        scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    top = scored[0][0]
    candidates = [s for sc, s in scored if sc == top]
    return random.choice(candidates)


# ── Image utilities ────────────────────────────────────────────────────────────

def _resize_cover(img: Image.Image, width: int, height: int) -> Image.Image:
    """Scale and center-crop to fill the canvas exactly (like CSS object-fit:cover)."""
    sw, sh = img.size
    scale  = max(width / sw, height / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    img    = img.resize((nw, nh), Image.LANCZOS)
    x      = (nw - width)  // 2
    y      = (nh - height) // 2
    return img.crop((x, y, x + width, y + height))


def _add_film_grain(img: Image.Image, intensity: float) -> Image.Image:
    """PIL-only grain: low-res urandom noise upsampled with bilinear."""
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
    Reduce the 'digital sheen' of AI-generated images:
    slight desaturation, slight contrast reduction, film grain.
    """
    img = ImageEnhance.Color(img).enhance(0.82)       # pull back saturation
    img = ImageEnhance.Contrast(img).enhance(0.90)    # soften tonal range
    img = _add_film_grain(img, 0.10)                  # subtle grain
    return img


def _measure_zone_luminance(img: Image.Image, x_frac=0.30, y_frac=0.38) -> float:
    """Sample average luminance of the bottom-left text zone (0–255)."""
    w, h   = img.size
    zone   = img.crop((0, int(h * (1 - y_frac)), int(w * x_frac), h))
    pixels = list(zone.getdata())
    if not pixels:
        return 128.0
    if isinstance(pixels[0], tuple):
        total = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in pixels)
    else:
        total = sum(pixels)
    return total / len(pixels)


def _apply_text_scrim(img: Image.Image, is_light_text: bool, zone_lum: float) -> Image.Image:
    """
    Gradient scrim over the bottom-left text zone to ensure readability.

    is_light_text: True when quote text is bright (white-ish)
    zone_lum:      average luminance of the text area (0=black, 255=white)

    Logic:
      - Light text on bright area  → dark scrim (contrast needed)
      - Dark text on dark area     → light scrim (contrast needed)
      - Otherwise                  → minimal touch-up scrim
    """
    w, h = img.size
    sw   = int(w * 0.36)   # scrim zone width  — slightly wider than text column
    sh   = int(h * 0.44)   # scrim zone height — covers text + breathing room

    # Determine scrim color and opacity
    if is_light_text and zone_lum > 110:
        scrim_color, opacity = (0, 0, 0), 0.52      # dark scrim — needed
    elif not is_light_text and zone_lum < 120:
        scrim_color, opacity = (255, 255, 255), 0.42  # light scrim — needed
    elif is_light_text:
        scrim_color, opacity = (0, 0, 0), 0.28      # dark scrim — minor
    else:
        scrim_color, opacity = (255, 255, 255), 0.22  # light scrim — minor

    # Build gradient mask at 1/8 scale for speed
    mw, mh = max(4, sw // 8), max(4, sh // 8)
    data   = []
    for y in range(mh):
        for x in range(mw):
            fx = (mw - 1 - x) / (mw - 1) if mw > 1 else 1.0   # 1.0 at left edge
            fy = y / (mh - 1)             if mh > 1 else 1.0   # 1.0 at bottom
            t  = fx * fy
            t  = t * t * (3 - 2 * t)                            # ease
            data.append(int(t * opacity * 255))

    mask   = Image.frombytes("L", (mw, mh), bytes(data))
    mask   = mask.resize((sw, sh), Image.BILINEAR)

    scrim  = Image.new("RGB", (sw, sh), scrim_color)
    region = img.crop((0, h - sh, sw, h))

    # composite(img1, img2, mask) = img1*(mask/255) + img2*(1-mask/255)
    blended = Image.composite(scrim, region, mask)

    result = img.copy()
    result.paste(blended, (0, h - sh))
    return result


# ── Cache helpers ──────────────────────────────────────────────────────────────

def _cache_path(mood_name: str, weather_cat: str) -> str:
    today = _date.today().strftime("%Y-%m-%d")
    safe  = f"{mood_name}_{weather_cat}".replace(" ", "_")
    return os.path.join("output", f"bg_{safe}_{today}.png")


# ── Main entry point ───────────────────────────────────────────────────────────

def generate_background(
    mood_name:      str,
    weather_cat:    str,
    width:          int,
    height:         int,
    text_color:     tuple = (52, 46, 40),
) -> Image.Image:
    """
    Generate (or load from cache) a photographic background for the given mood.

    Args:
        mood_name:    e.g. "rainy_introspection", "sunny_nostalgia"
        weather_cat:  "cold" | "rainy" | "cloudy" | "sunny"
        width:        canvas width in pixels
        height:       canvas height in pixels
        text_color:   RGB tuple of the quote text color (used for scrim direction)

    Returns:
        PIL.Image.Image (RGB, size == (width, height))

    Raises:
        Exception on DALL-E failure / network error — caller should catch and
        fall back to visual_engine.
    """
    cache = _cache_path(mood_name, weather_cat)

    # ── Cache hit ──────────────────────────────────────────────────────────────
    if os.path.exists(cache):
        cached = Image.open(cache).convert("RGB")
        if cached.size == (width, height):
            print(f"  bg   : cache ({os.path.basename(cache)})")
            return cached

    # ── Scene selection ────────────────────────────────────────────────────────
    scene  = _select_scene(mood_name, weather_cat)
    prompt = scene["prompt"]
    print(f"  bg   : generating '{scene['id']}' (DALL-E 3) …")

    # ── DALL-E 3 call ──────────────────────────────────────────────────────────
    from openai import OpenAI
    import requests

    client   = OpenAI()
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1792x1024",
        quality="standard",
        style="natural",
        n=1,
    )
    url = response.data[0].url

    # ── Download ───────────────────────────────────────────────────────────────
    r   = requests.get(url, timeout=30)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("RGB")

    # ── Resize to canvas ───────────────────────────────────────────────────────
    img = _resize_cover(img, width, height)

    # ── Analog post-processing ─────────────────────────────────────────────────
    img = _process_photo(img)

    # ── Readability scrim ──────────────────────────────────────────────────────
    tr, tg, tb    = text_color
    text_lum      = 0.299 * tr + 0.587 * tg + 0.114 * tb
    is_light_text = text_lum > 128
    zone_lum      = _measure_zone_luminance(img)
    img           = _apply_text_scrim(img, is_light_text, zone_lum)

    # ── Cache and return ───────────────────────────────────────────────────────
    os.makedirs("output", exist_ok=True)
    img.save(cache)
    print(f"  bg   : saved → {cache}")
    return img
