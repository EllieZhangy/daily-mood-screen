"""
background_prompt_builder.py

Builds a detailed, photography-style image generation prompt from the
current mood, weather, and photo context.

Two visual families are supported:

  Family A — Scenic & Atmospheric
    Mountains, lakes, coastlines, roads, city skylines, foggy valleys,
    snowy fields, rainy streets, sunsets, train window views.
    Emotional register: depth, distance, scale, solitude, movement.

  Family B — Life & Everyday Aesthetic
    Coffee and books, flowers, vintage travel objects, two cups on a table,
    morning window light, fruit, candles, bicycles, reading moments, picnics.
    Emotional register: warmth, memory, intimacy, comfort, belonging.

The output prompt is written as a brief to a photographer — specific about
subject, light, palette, and film stock. It never mentions "AI", "render",
or "digital art" (which trigger the AI-art aesthetic we want to avoid).
"""

import random

# ── Scene catalog ──────────────────────────────────────────────────────────────
#
# Each entry:
#   id           — short identifier
#   family       — "A" (scenic) or "B" (everyday)
#   weather      — list of weather categories this fits ["cold","rainy","cloudy","sunny"]
#   mood_kws     — mood name fragments that increase this scene's score
#   photo_themes — photo themes (from context.json) that increase score
#   prompt       — the full, final photographic brief
#   dark_tones   — True when scene tends toward dark (helps renderer pick text overlay)

SCENE_CATALOG = [

    # ── Family A: Scenic & Atmospheric ────────────────────────────────────────

    {
        "id":           "misty_mountain_dawn",
        "family":       "A",
        "weather":      ["cold", "cloudy"],
        "mood_kws":     ["solitude", "stillness", "calm", "reflection", "introspection", "nature"],
        "photo_themes": ["nature", "none", "self"],
        "prompt": (
            "A misty mountain range at dawn seen from a high ridge, layers of forested peaks "
            "receding into pale grey-blue haze, a single shaft of early light breaking through "
            "cloud cover on the far horizon, cold and still, no people, vast negative space in "
            "the upper sky, Fuji Pro 400H film, wide landscape orientation, muted blue-grey and "
            "sage green tones, no text, no watermarks, no logos"
        ),
        "dark_tones": False,
    },
    {
        "id":           "foggy_valley_morning",
        "family":       "A",
        "weather":      ["cloudy", "rainy"],
        "mood_kws":     ["solitude", "calm", "reflection", "quiet", "nature"],
        "photo_themes": ["nature", "none"],
        "prompt": (
            "Morning fog filling a valley between forested mountain ridges, pine trees emerging "
            "as dark silhouettes from white mist, soft pre-sunrise light diffusing through the "
            "cloud layer, blue-grey and muted sage palette, wide peaceful landscape, 35mm film "
            "photography, no people, no objects in foreground, no text, no watermarks"
        ),
        "dark_tones": False,
    },
    {
        "id":           "empty_mountain_road",
        "family":       "A",
        "weather":      ["sunny", "cloudy"],
        "mood_kws":     ["movement", "journey", "freedom", "discovery", "travel"],
        "photo_themes": ["travel", "none"],
        "prompt": (
            "Empty two-lane road winding through a pine forest toward distant snow-capped peaks, "
            "soft golden morning light raking low through the trees across the asphalt, "
            "warm amber and deep forest green tones, wide horizontal composition, "
            "Kodak Portra 400 film aesthetic, no vehicles, no people, "
            "no text, no watermarks, no logos"
        ),
        "dark_tones": False,
    },
    {
        "id":           "still_lake_reflection",
        "family":       "A",
        "weather":      ["sunny", "cloudy"],
        "mood_kws":     ["stillness", "calm", "reflection", "nature", "openness"],
        "photo_themes": ["nature", "none", "self"],
        "prompt": (
            "Perfectly still alpine lake at dawn, pale rose and blue sky mirrored in the glassy "
            "surface, dark pine trees lining the banks, one small wooden dock reaching into the "
            "water, soft pre-sunrise light, rose gold and steel blue palette, wide format, "
            "Fuji Velvia film aesthetic, no people, no text, no watermarks"
        ),
        "dark_tones": False,
    },
    {
        "id":           "snowy_open_field",
        "family":       "A",
        "weather":      ["cold"],
        "mood_kws":     ["solitude", "introspection", "stillness", "distance"],
        "photo_themes": ["none", "self"],
        "prompt": (
            "A single bare birch tree standing in a vast snow-covered field at late afternoon, "
            "long blue shadow cast across the white surface, cold flat winter light, "
            "pale grey overcast sky, monochrome palette of white and steel blue, "
            "35mm film, minimal composition with enormous negative space, "
            "no people, no text, no watermarks"
        ),
        "dark_tones": False,
    },
    {
        "id":           "lit_window_snowy_night",
        "family":       "A",
        "weather":      ["cold"],
        "mood_kws":     ["homecoming", "warmth", "shelter", "reunion", "belonging", "family"],
        "photo_themes": ["family", "friends", "none"],
        "prompt": (
            "Warm amber light glowing through a frosted window of a dark wooden house on a "
            "snowy evening, bare tree branches silhouetted against the deep blue night sky, "
            "snow accumulated on the window ledge and sill, interior warmth implied by the "
            "amber glow, deep navy and warm amber palette, analog film, "
            "no text, no watermarks, no logos"
        ),
        "dark_tones": True,
    },
    {
        "id":           "rain_cobblestone_dusk",
        "family":       "A",
        "weather":      ["rainy"],
        "mood_kws":     ["nostalgia", "discovery", "urban", "solitude", "memory"],
        "photo_themes": ["travel", "memories", "none"],
        "prompt": (
            "Quiet cobblestone street at dusk after rain, golden street lamps reflected in "
            "wet stone, light misting rain still falling, narrow alley with softly lit "
            "shop fronts on either side, charcoal and amber palette, "
            "35mm street photography, no people, no visible text or signage, no watermarks"
        ),
        "dark_tones": True,
    },
    {
        "id":           "train_window_blur",
        "family":       "A",
        "weather":      ["rainy", "cloudy"],
        "mood_kws":     ["journey", "movement", "transit", "distance", "solitude"],
        "photo_themes": ["travel", "none"],
        "prompt": (
            "Looking through a rain-streaked train window, countryside blurred in soft motion "
            "beyond the glass, rain droplets tracing diagonal lines across the pane, "
            "overcast grey light outside, faint warm interior light reflected in the glass, "
            "Fuji Pro 400H film, quiet transit mood, no visible text, no watermarks"
        ),
        "dark_tones": False,
    },
    {
        "id":           "coastal_morning_beach",
        "family":       "A",
        "weather":      ["sunny"],
        "mood_kws":     ["freedom", "openness", "movement", "connection", "simplicity"],
        "photo_themes": ["friends", "travel", "none"],
        "prompt": (
            "Wide empty beach at early morning low tide, gentle waves spreading thin across "
            "pale sand, vast open pale blue sky, a single figure walking far in the distance "
            "seen only from behind, soft warm morning light on the water, "
            "Scandinavian coastal photography, horizontal wide, no text, no watermarks"
        ),
        "dark_tones": False,
    },
    {
        "id":           "autumn_forest_trail",
        "family":       "A",
        "weather":      ["sunny", "cloudy"],
        "mood_kws":     ["journey", "nostalgia", "nature", "calm", "memory"],
        "photo_themes": ["nature", "memories", "travel"],
        "prompt": (
            "Narrow trail winding through an autumn forest, golden and amber leaves on the "
            "canopy, a few leaves drifting down, dappled afternoon light filtering through, "
            "warm amber and deep forest shadow, Kodak Gold 200 film aesthetic, "
            "shallow depth of field, no people, no text, no watermarks"
        ),
        "dark_tones": False,
    },
    {
        "id":           "city_blue_hour",
        "family":       "A",
        "weather":      ["cloudy", "cold", "rainy"],
        "mood_kws":     ["urban", "loneliness", "introspection", "movement", "distance"],
        "photo_themes": ["none", "travel", "self"],
        "prompt": (
            "City skyline at blue hour, warm building windows glowing against a fading "
            "purple-blue sky, reflected in water below, atmospheric haze over the towers, "
            "deep purple-blue and amber palette, wide cityscape, medium format film, "
            "no text, no watermarks, no logos"
        ),
        "dark_tones": True,
    },
    {
        "id":           "overcast_field_sky",
        "family":       "A",
        "weather":      ["cloudy"],
        "mood_kws":     ["calm", "solitude", "reflection", "quiet", "stillness"],
        "photo_themes": ["none", "nature", "self"],
        "prompt": (
            "Open countryside field under a dramatic overcast sky, dry golden grasses bending "
            "gently in the wind, grey cloud ceiling filling two thirds of the frame, "
            "muted warm tan and pale grey tones, 35mm film landscape, wide composition, "
            "no people, no structures, no text, no watermarks"
        ),
        "dark_tones": False,
    },
    {
        "id":           "sunset_ocean_silhouette",
        "family":       "A",
        "weather":      ["sunny"],
        "mood_kws":     ["freedom", "wonder", "journey", "evening", "openness"],
        "photo_themes": ["travel", "none"],
        "prompt": (
            "Wide ocean at sunset, tree silhouettes on a low bluff against a deep amber and "
            "crimson sky, orange light shimmering on calm water, cinematic horizontal format, "
            "Fuji Velvia saturated film, warm and vast, no text, no watermarks, no logos"
        ),
        "dark_tones": True,
    },
    {
        "id":           "frost_window_view",
        "family":       "A",
        "weather":      ["cold"],
        "mood_kws":     ["introspection", "journey", "solitude", "nostalgia", "transit"],
        "photo_themes": ["travel", "memories", "self"],
        "prompt": (
            "Intricate frost crystal patterns covering a window, the winter landscape beyond "
            "visible only as a soft blue-grey blur through the ice, close-up texture of the "
            "crystals catching weak winter light, blue-white and silver tones, "
            "35mm film, cold and quietly beautiful, no text, no watermarks"
        ),
        "dark_tones": False,
    },
    {
        "id":           "open_highway_horizon",
        "family":       "A",
        "weather":      ["sunny", "cloudy"],
        "mood_kws":     ["movement", "journey", "freedom", "discovery", "travel", "openness"],
        "photo_themes": ["travel", "none"],
        "prompt": (
            "Passenger perspective from a car on a long straight highway through open flat "
            "landscape, horizon stretching far ahead, dramatic sky with layered clouds, "
            "warm afternoon light, road documentary photography, Kodak Portra 400 film, "
            "no visible text on road signs, no watermarks"
        ),
        "dark_tones": False,
    },

    # ── Family B: Life & Everyday Aesthetic ───────────────────────────────────

    {
        "id":           "coffee_book_window",
        "family":       "B",
        "weather":      ["rainy", "cloudy"],
        "mood_kws":     ["comfort", "solitude", "nostalgia", "stillness", "warmth", "shelter",
                         "introspection"],
        "photo_themes": ["food", "self", "memories", "none"],
        "prompt": (
            "A ceramic coffee mug and a well-worn paperback on a wooden café table, soft "
            "directional morning window light casting long gentle shadows, steam rising from "
            "the coffee, warm honey and cream tones, Kinfolk magazine still life, "
            "natural light, shallow depth of field, no text visible on book spine, "
            "no watermarks, no logos"
        ),
        "dark_tones": False,
    },
    {
        "id":           "wildflowers_vase_linen",
        "family":       "B",
        "weather":      ["sunny", "cloudy"],
        "mood_kws":     ["warmth", "beauty", "calm", "comfort", "home", "simplicity"],
        "photo_themes": ["nature", "none", "family"],
        "prompt": (
            "Small bouquet of wildflowers in a clear glass vase on a linen cloth, soft diffuse "
            "daylight from the side casting gentle shadows, white and pale yellow blooms, "
            "sage green stems, warm linen background, Kinfolk editorial still life, "
            "delicate and minimal, no text, no watermarks, no logos"
        ),
        "dark_tones": False,
    },
    {
        "id":           "vintage_travel_flatlay",
        "family":       "B",
        "weather":      ["cloudy", "sunny"],
        "mood_kws":     ["nostalgia", "journey", "memories", "discovery", "travel"],
        "photo_themes": ["travel", "memories", "self"],
        "prompt": (
            "Flat lay on a worn wooden surface: an old folded map, an analog film camera, "
            "pressed wildflowers, a small travel journal, soft afternoon light, "
            "aged paper and brass tones, natural wood grain, analog nostalgia editorial, "
            "no visible brand text, no watermarks, no logos"
        ),
        "dark_tones": False,
    },
    {
        "id":           "two_cups_marble_café",
        "family":       "B",
        "weather":      ["sunny", "cloudy"],
        "mood_kws":     ["reunion", "connection", "friends", "warmth", "togetherness",
                         "homecoming"],
        "photo_themes": ["friends", "family", "food"],
        "prompt": (
            "Two ceramic coffee cups on a white marble café table, morning light from a nearby "
            "window, a small plate with a pastry beside them, warm cream and cool grey marble "
            "tones, Parisian café atmosphere, lifestyle photography, intimate, "
            "no people in frame, no text, no watermarks, no logos"
        ),
        "dark_tones": False,
    },
    {
        "id":           "morning_light_bedside",
        "family":       "B",
        "weather":      ["sunny"],
        "mood_kws":     ["warmth", "stillness", "home", "simplicity", "calm"],
        "photo_themes": ["self", "family", "none"],
        "prompt": (
            "Soft morning sunlight streaming through sheer linen curtains onto a white bedside "
            "table, a small plant, reading glasses, and a book on the surface, "
            "warm pale gold and white tones, intimate domestic photography, "
            "Kinfolk aesthetic, quiet and unhurried, no text, no watermarks"
        ),
        "dark_tones": False,
    },
    {
        "id":           "fruit_linen_daylight",
        "family":       "B",
        "weather":      ["sunny"],
        "mood_kws":     ["simplicity", "warmth", "comfort", "daily"],
        "photo_themes": ["food", "none"],
        "prompt": (
            "Seasonal fruit arranged casually on aged linen cloth in soft afternoon daylight: "
            "ripe peaches, purple figs, a small bunch of dark grapes, "
            "warm golden tones, rustic Mediterranean still life, Kinfolk editorial, "
            "natural abundance, no text, no watermarks, no logos"
        ),
        "dark_tones": False,
    },
    {
        "id":           "candle_dark_interior",
        "family":       "B",
        "weather":      ["cold", "rainy"],
        "mood_kws":     ["comfort", "intimacy", "shelter", "calm", "solitude", "quiet"],
        "photo_themes": ["self", "family", "none"],
        "prompt": (
            "Single white candle burning in a ceramic holder on a dark wooden surface, "
            "warm amber candlelight glowing against deep charcoal shadow, intimate close-up, "
            "surrounding darkness, analog film photography, slow mood, "
            "no text, no watermarks, no logos"
        ),
        "dark_tones": True,
    },
    {
        "id":           "bicycle_stone_vine",
        "family":       "B",
        "weather":      ["sunny", "cloudy"],
        "mood_kws":     ["journey", "movement", "simplicity", "morning", "discovery"],
        "photo_themes": ["travel", "none"],
        "prompt": (
            "Old bicycle with a wicker basket leaning against a sunlit stone wall with climbing "
            "vines and small flowers, dappled morning light, warm stone and faded paint tones, "
            "soft green foliage, European village lifestyle photography, "
            "quiet and charming, no text, no watermarks"
        ),
        "dark_tones": False,
    },
    {
        "id":           "picnic_blanket_afternoon",
        "family":       "B",
        "weather":      ["sunny"],
        "mood_kws":     ["connection", "friends", "reunion", "warmth", "togetherness", "joy"],
        "photo_themes": ["friends", "food", "family"],
        "prompt": (
            "Picnic arrangement on a blanket on green grass: crusty bread, soft cheese, "
            "wine in glasses, seasonal fruit, shot from slightly above, dappled afternoon "
            "sunlight filtering through nearby trees, warm and casual lifestyle photography, "
            "no people in frame, no text, no watermarks, no logos"
        ),
        "dark_tones": False,
    },
    {
        "id":           "books_tea_rainy_window",
        "family":       "B",
        "weather":      ["rainy", "cloudy"],
        "mood_kws":     ["solitude", "introspection", "shelter", "comfort", "stillness",
                         "reflection"],
        "photo_themes": ["self", "none", "memories"],
        "prompt": (
            "Stack of well-worn books beside a rain-streaked window, a porcelain teacup on a "
            "small saucer, soft grey rainy daylight filtering in, aged paper and cool grey-blue "
            "tones, quiet interior still life, Kinfolk aesthetic, no text visible on spines, "
            "no watermarks"
        ),
        "dark_tones": False,
    },
    {
        "id":           "flowers_grey_window",
        "family":       "B",
        "weather":      ["cloudy", "rainy"],
        "mood_kws":     ["warmth", "calm", "comfort", "home", "shelter", "beauty"],
        "photo_themes": ["nature", "family", "none"],
        "prompt": (
            "A small ceramic pot of pale flowers on a window ledge, grey overcast sky "
            "visible through the glass behind, soft even interior light, muted green and "
            "pale white tones, quiet domestic scene, lifestyle still life, "
            "minimal and calm, no text, no watermarks"
        ),
        "dark_tones": False,
    },
    {
        "id":           "reading_café_silhouette",
        "family":       "B",
        "weather":      ["rainy", "cloudy"],
        "mood_kws":     ["solitude", "comfort", "introspection", "reflection", "shelter"],
        "photo_themes": ["self", "none"],
        "prompt": (
            "A person seen from behind sitting alone at a window table in a quiet café, "
            "reading, grey daylight from the window, dark wood interior, a coffee cup on the "
            "table, intimate documentary photograph, analog film grain, face never visible, "
            "no text in scene, no watermarks, no logos"
        ),
        "dark_tones": False,
    },
]


# ── Family selection ───────────────────────────────────────────────────────────

# Mood keyword fragments that strongly suggest Family B (everyday life)
_FAMILY_B_SIGNALS = {
    "reunion", "homecoming", "comfort", "warmth", "shelter", "nostalgia",
    "connection", "introspection", "simplicity", "intimacy", "memories",
}

# Weather categories that lean toward Family B (more intimate/indoor)
_WEATHER_B_LEAN = {"cold", "rainy"}


def _choose_family(mood_name: str, weather_cat: str, photo_theme: str) -> str:
    """
    Return "A" or "B" for the preferred visual family.

    Logic:
      1. Mood keyword check — certain emotional registers strongly imply B
      2. Photo theme check — personal themes (food, self, family) imply B
      3. Weather — cold/rainy lean toward B; sunny/cloudy lean toward A
      4. Default: A
    """
    tokens = set(mood_name.lower().split("_"))

    if tokens & _FAMILY_B_SIGNALS:
        return "B"
    if photo_theme in ("food", "self", "family", "memories"):
        return "B"
    if photo_theme == "friends" and weather_cat in ("rainy", "cold"):
        return "B"
    if weather_cat in _WEATHER_B_LEAN and "movement" not in tokens and "journey" not in tokens:
        return "B"
    return "A"


# ── Scene scoring and selection ────────────────────────────────────────────────

def _score_scene(scene: dict, mood_name: str, weather_cat: str, photo_theme: str) -> int:
    tokens = set(mood_name.lower().split("_"))
    score  = 0
    score += sum(1 for kw in scene["mood_kws"]     if kw in tokens)
    score += sum(1 for wt in scene["weather"]       if wt == weather_cat)
    score += sum(1 for pt in scene["photo_themes"]  if pt == photo_theme)
    return score


def _select_scene(family: str, mood_name: str, weather_cat: str, photo_theme: str) -> dict:
    """Score all scenes in the chosen family and pick the best-matching one."""
    pool    = [s for s in SCENE_CATALOG if s["family"] == family]
    scored  = [(  _score_scene(s, mood_name, weather_cat, photo_theme), s) for s in pool]
    scored.sort(key=lambda x: -x[0])
    top     = scored[0][0]
    candidates = [s for sc, s in scored if sc == top]
    return random.choice(candidates)


# ── Style suffix ───────────────────────────────────────────────────────────────

_STYLE_ANCHORS = [
    "analog film photography",
    "natural light, no flash",
    "soft atmospheric depth",
    "cinematic but realistic",
    "no AI-art aesthetics",
    "no HDR, no oversaturation",
    "photo someone would keep in their camera roll",
]


def _tail() -> str:
    return (
        "analog film photography, natural light, soft atmospheric depth, cinematic but "
        "realistic, no text, no watermarks, no logos, no UI elements, no artificial sharpening, "
        "keep all important content within the central 80% of the frame, "
        "outer 10% of each edge should be soft atmospheric background only"
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def build_background_prompt(
    mood:         dict,
    weather:      dict,
    photos:       dict | None = None,
    visual_style: dict | None = None,
) -> dict:
    """
    Build a complete image generation prompt for the current context.

    Args:
        mood:         mood dict with "mood" key (e.g. {"mood": "rainy_introspection", ...})
        weather:      weather dict with "condition" and "temperature"
        photos:       optional photos dict with "theme" key
        visual_style: optional loaded visual-style preset (for atmosphere hints)

    Returns:
        dict:
            family      — "A" or "B"
            scene_id    — scene identifier from SCENE_CATALOG
            prompt      — complete prompt string ready for the image API
            dark_tones  — bool, True if scene tends toward dark
            style_note  — brief human-readable style description
    """
    from mood_engine import categorize_weather

    mood_name    = mood.get("mood", "cloudy_solitude")
    weather_cat  = categorize_weather(weather)
    photo_theme  = (photos or {}).get("theme", "none")

    family = _choose_family(mood_name, weather_cat, photo_theme)
    scene  = _select_scene(family, mood_name, weather_cat, photo_theme)

    # Combine scene prompt with universal style anchor
    full_prompt = f"{scene['prompt'].rstrip(', ')}, {_tail()}"

    return {
        "family":     family,
        "scene_id":   scene["id"],
        "prompt":     full_prompt,
        "dark_tones": scene["dark_tones"],
        "style_note": (
            f"Family {'A: Scenic' if family == 'A' else 'B: Everyday'} · "
            f"{scene['id'].replace('_', ' ')}"
        ),
    }
