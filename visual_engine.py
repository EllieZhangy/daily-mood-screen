"""
visual_engine.py

Atmospheric background generation from the Daily Mood visual DNA.
Translates mood × weather → PIL image using the recipe system in
style_library/visual/moods.json.

All rendering uses Pillow only (no numpy required).

Rendering pipeline per image:
  1. multi-stop gradient      — color foundation, ease-in-out curved
  2. light source             — soft radial glow at implied light position
  3. vignette                 — edge-darkening for compositional depth
  4. grain                    — photographic noise at reduced scale, bilinear up
"""

import copy
import json
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFilter, ImageChops

_VISUAL_DIR = os.path.join(os.path.dirname(__file__), "style_library", "visual")
_MOODS_PATH = os.path.join(_VISUAL_DIR, "moods.json")


# ── Loaders ────────────────────────────────────────────────────────────────────

def _load_moods() -> dict:
    with open(_MOODS_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── Color math ─────────────────────────────────────────────────────────────────

def _clamp(v) -> int:
    return max(0, min(255, int(v)))


def _ease(t: float) -> float:
    """Smooth-step: slow at both ends, fastest at midpoint."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _lerp_rgb(a: list, b: list, t: float) -> tuple:
    return (_clamp(a[0] + t * (b[0] - a[0])),
            _clamp(a[1] + t * (b[1] - a[1])),
            _clamp(a[2] + t * (b[2] - a[2])))


def _apply_warm_shift(stops: list, delta: list) -> list:
    return [
        {"pos": s["pos"],
         "rgb": [_clamp(s["rgb"][i] + delta[i]) for i in range(3)]}
        for s in stops
    ]


def _apply_darken(stops: list, factor: float) -> list:
    return [
        {"pos": s["pos"],
         "rgb": [_clamp(s["rgb"][i] * factor) for i in range(3)]}
        for s in stops
    ]


def _apply_desaturate(stops: list, amount: float) -> list:
    result = []
    for s in stops:
        r, g, b = s["rgb"]
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        result.append({"pos": s["pos"], "rgb": [
            _clamp(r + (lum - r) * amount),
            _clamp(g + (lum - g) * amount),
            _clamp(b + (lum - b) * amount),
        ]})
    return result


# ── Gradient ───────────────────────────────────────────────────────────────────

def _multi_gradient(width: int, height: int, stops: list) -> Image.Image:
    """
    Vertical multi-stop gradient with ease-in-out curve between each pair of
    stops. Each stop is {"pos": 0.0-1.0, "rgb": [r, g, b]}.
    """
    stops_s = sorted(stops, key=lambda s: s["pos"])
    img  = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        t = _ease(y / height)

        lo = stops_s[0]
        hi = stops_s[-1]
        for i in range(len(stops_s) - 1):
            if stops_s[i]["pos"] <= t <= stops_s[i + 1]["pos"]:
                lo, hi = stops_s[i], stops_s[i + 1]
                break

        span = hi["pos"] - lo["pos"]
        local_t = _ease((t - lo["pos"]) / span) if span > 1e-6 else 0.0
        color = _lerp_rgb(lo["rgb"], hi["rgb"], local_t)
        draw.line([(0, y), (width, y)], fill=color)

    return img


# ── Vignette ───────────────────────────────────────────────────────────────────

def _add_vignette(img: Image.Image, strength: float) -> Image.Image:
    """
    Darken edges by 'strength' (0.0 = no effect, 1.0 = edges go black).
    Works at 1/4 scale for performance, then upsamples.
    """
    if strength <= 0:
        return img
    w, h = img.size
    sf = 4
    mw, mh = max(1, w // sf), max(1, h // sf)

    mask = Image.new("L", (mw, mh), 0)
    draw = ImageDraw.Draw(mask)
    px, py = int(mw * 0.08), int(mh * 0.08)
    draw.ellipse([px, py, mw - px, mh - py], fill=255)

    blur_r = max(10, int(min(mw, mh) * 0.28))
    mask = mask.filter(ImageFilter.BoxBlur(blur_r))
    mask = mask.resize((w, h), Image.BILINEAR)

    # composite(img1, img2, mask): result = img1*(mask/255) + img2*(1-mask/255)
    # img1=original, img2=darkened → center stays original, edges darken
    dark = img.point(lambda px_v: _clamp(px_v * (1.0 - strength)))
    return Image.composite(img, dark, mask)


# ── Grain ──────────────────────────────────────────────────────────────────────

def _add_grain(img: Image.Image, intensity: float) -> Image.Image:
    """
    Photographic grain via low-res noise upsampled with bilinear interpolation.
    Uses os.urandom for fast C-level randomness. No numpy required.
    """
    if intensity <= 0:
        return img
    w, h = img.size
    gw, gh = max(1, w // 6), max(1, h // 6)

    spread     = max(1, int(intensity * 22))
    half_range = 2 * spread + 1

    raw = os.urandom(gw * gh)
    # Center noise at 128: values in [128-spread, 128+spread]
    data = bytes([_clamp(128 + (b % half_range) - spread) for b in raw])

    small     = Image.frombytes("L", (gw, gh), data)
    grain_rgb = small.resize((w, h), Image.BILINEAR).convert("RGB")

    # add(a, b, scale=1, offset=-128) → clip8(a + b - 128)
    # grain centered at 128 → net offset ≈ 0, spread adds ±spread brightness shift
    return ImageChops.add(img, grain_rgb, scale=1, offset=-128)


# ── Light source ───────────────────────────────────────────────────────────────

def _add_light_source(img: Image.Image, x: float, y: float,
                      rgb: tuple, intensity: float, radius: float) -> Image.Image:
    """
    Soft radial glow at canvas position (x, y) where 0.0=left/top, 1.0=right/bottom.
    Rendered at 1/4 scale with Gaussian blur, then upsampled.
    """
    if intensity <= 0:
        return img
    w, h = img.size
    sf = 4
    lw, lh = max(1, w // sf), max(1, h // sf)

    cx = int(x * lw)
    cy = int(y * lh)
    r  = max(4, int(radius * lw))

    light = Image.new("RGB", (lw, lh), (0, 0, 0))
    draw  = ImageDraw.Draw(light)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=rgb)

    blur_r = max(r // 3, 10)
    light  = light.filter(ImageFilter.GaussianBlur(radius=blur_r))
    light  = light.resize((w, h), Image.BILINEAR)

    # Scale by intensity, then add: clip8(img + light * intensity)
    light_scaled = light.point(lambda px_v: _clamp(px_v * intensity))
    return ImageChops.add(img, light_scaled)


# ── Recipe resolution ──────────────────────────────────────────────────────────

def _resolve_recipe(mood_name: str, weather_category: str, moods_data: dict) -> dict:
    """
    Select and modify a rendering recipe based on time-of-day, weather, and mood.

    Priority:
      1. Dusk time override (17–20h) → always returns dusk recipe
      2. Weather category → base recipe
      3. Mood name keywords → apply modifiers on top
    """
    recipes       = moods_data["recipes"]
    hour          = datetime.now().hour
    dusk_hours    = moods_data.get("time_override", {}).get("dusk_hours", [17, 18, 19, 20])

    if hour in dusk_hours:
        return copy.deepcopy(recipes["dusk"])

    mood_lower = mood_name.lower()
    w2r        = moods_data.get("weather_to_recipe", {})

    if weather_category == "cold":
        base_key = "cold"
    elif weather_category == "rainy":
        base_key = "rainy"
    elif weather_category == "cloudy":
        base_key = "cloudy"
    else:
        cool_kws = w2r.get("sunny", {}).get("_keywords_for_cool", [])
        base_key = "sunny_cool" if any(kw in mood_lower for kw in cool_kws) else "sunny_warm"

    recipe = copy.deepcopy(recipes.get(base_key, recipes["cloudy"]))

    for mod_key, mod in moods_data.get("mood_modifiers", {}).items():
        if not isinstance(mod, dict):
            continue
        if mod_key not in mood_lower:
            continue

        stops = recipe["gradient_stops"]

        if "warm_shift" in mod:
            stops = _apply_warm_shift(stops, mod["warm_shift"])
        if "darken" in mod:
            stops = _apply_darken(stops, mod["darken"])
        if "desaturate" in mod:
            stops = _apply_desaturate(stops, mod["desaturate"])

        recipe["gradient_stops"] = stops

        if "vignette_boost" in mod:
            recipe["vignette"] = min(0.75, recipe.get("vignette", 0.0) + mod["vignette_boost"])

        boost = mod.get("light_source_boost", 0.0)
        if boost > 0:
            ls = recipe.get("light_source", {})
            if ls.get("enabled", False):
                ls["intensity"] = min(0.25, ls.get("intensity", 0.05) + boost)
            else:
                recipe["light_source"] = {
                    "enabled":   True,
                    "x":         0.20,
                    "y":         0.10,
                    "rgb":       [255, 228, 185],
                    "intensity": boost,
                    "radius":    0.38,
                }

    return recipe


# ── Public entry point ─────────────────────────────────────────────────────────

def make_atmospheric_background(mood_name: str, weather_category: str,
                                width: int, height: int) -> Image.Image:
    """
    Generate a mood-aware atmospheric background image.

    Args:
        mood_name:        e.g. "cloudy_solitude", "sunny_nostalgia"
        weather_category: one of "cold" | "rainy" | "cloudy" | "sunny"
        width, height:    canvas size in pixels

    Returns:
        PIL.Image.Image (RGB)

    Falls back to a safe neutral gradient if moods.json can't be loaded.
    """
    try:
        moods_data = _load_moods()
        recipe     = _resolve_recipe(mood_name, weather_category, moods_data)
    except Exception as e:
        print(f"  visual_engine: fallback ({e})")
        return _multi_gradient(width, height, [
            {"pos": 0.0, "rgb": [242, 238, 232]},
            {"pos": 1.0, "rgb": [218, 212, 204]},
        ])

    img = _multi_gradient(width, height, recipe["gradient_stops"])

    ls = recipe.get("light_source", {})
    if ls.get("enabled", False):
        img = _add_light_source(
            img,
            x=ls.get("x",         0.2),
            y=ls.get("y",         0.1),
            rgb=tuple(ls.get("rgb", [255, 235, 195])),
            intensity=ls.get("intensity", 0.08),
            radius=ls.get("radius",    0.40),
        )

    img = _add_vignette(img, recipe.get("vignette", 0.0))
    img = _add_grain(img,    recipe.get("grain",    0.0))

    return img
