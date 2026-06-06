import json
import os
from datetime import datetime

# style_library/ lives at the project root, one level up from src/
_ROOT         = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_WRITING_DIR  = os.path.join(_ROOT, "style_library", "writing")
_VISUAL_DIR   = os.path.join(_ROOT, "style_library", "visual")
_V_PRESETS    = _VISUAL_DIR   # presets live flat in visual/
_AUTHORS_DIR  = os.path.join(_WRITING_DIR, "authors")
_THEMES_DIR   = os.path.join(_WRITING_DIR, "themes")
_PRESETS_DIR  = os.path.join(_WRITING_DIR, "presets")


def _load_json(path: str, label: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"{label} not found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Writing styles (presets) ──────────────────────────────────────────────────

def load_writing_style(language: str, style: str) -> dict:
    """
    Load a preset writing style from style_library/writing/presets/.

    Args:
        language:  "zh" or "en"
        style:     "gentle", "rainy", "nostalgic", "evening", "weekend"

    Example:
        load_writing_style("zh", "gentle")  →  zh_gentle.json
    """
    filename = f"{language}_{style}.json"
    path = os.path.join(_PRESETS_DIR, filename)
    if not os.path.exists(path):
        # Backward-compat: also check writing/ root
        path = os.path.join(_WRITING_DIR, filename)
    return _load_json(path, f"Writing preset '{language}_{style}'")


# ── Author styles ─────────────────────────────────────────────────────────────

def load_author_style(author: str) -> dict:
    """
    Load an author style from style_library/writing/authors/.

    Args:
        author:  filename without extension, e.g. "mu_xin", "murakami", "wang_zengqi"

    Example:
        load_author_style("mu_xin")  →  authors/mu_xin.json
    """
    path = os.path.join(_AUTHORS_DIR, f"{author}.json")
    return _load_json(path, f"Author style '{author}'")


# ── Theme styles ──────────────────────────────────────────────────────────────

def load_theme_style(theme: str) -> dict:
    """
    Load a topic/mood theme from style_library/writing/themes/.

    Args:
        theme:  filename without extension, e.g. "zh_solitude", "zh_homecoming"

    Example:
        load_theme_style("zh_solitude")  →  themes/zh_solitude.json
    """
    path = os.path.join(_THEMES_DIR, f"{theme}.json")
    return _load_json(path, f"Theme style '{theme}'")


# ── Visual styles ─────────────────────────────────────────────────────────────

def load_visual_style(style: str) -> dict:
    """Load a visual style JSON from style_library/visual/."""
    path = os.path.join(_VISUAL_DIR, f"{style}.json")
    return _load_json(path, f"Visual style '{style}'")


def load_visual_preset(preset: str) -> dict:
    """Load a named preset from style_library/visual/presets/."""
    path = os.path.join(_V_PRESETS, f"{preset}.json")
    return _load_json(path, f"Visual preset '{preset}'")


# ── Mood-to-preset mapping ────────────────────────────────────────────────────
# Keys are substrings matched against the mood name.
# The first match wins. Order matters: most specific first.
_MOOD_PRESET_RULES: list[tuple[list[str], str]] = [
    # Cold weather moods → night (deep, interior)
    (["cold_"],       "daily_mood_night"),
    # Rainy moods → night (reflective, inward)
    (["rainy_"],      "daily_mood_night"),
    # Nostalgia / warmth / reunion / homecoming → warm amber
    (["nostalgia", "warmth", "reunion", "homecoming", "comfort", "shelter"], "daily_mood_warm"),
    # Solitude / introspection / journey → night
    (["solitude", "introspection", "journey"],  "daily_mood_night"),
    # Cloudy moods → earth (muted, quiet)
    (["cloudy_"],     "daily_mood_earth"),
    # Sunny movement / discovery / openness → cool
    (["movement", "discovery", "simplicity", "stillness"], "daily_mood_cool"),
    # Default sunny → warm
    (["sunny_"],      "daily_mood_warm"),
]

_DUSK_HOURS = range(17, 21)   # 17:00–20:59 → dusk preset


def auto_visual_preset(mood_name: str, weather_category: str) -> dict:
    """
    Return the best-fit visual preset dict for the given mood and weather.

    Uses _MOOD_PRESET_RULES for base selection, then overrides to dusk
    preset during evening hours (17–20).
    """
    hour = datetime.now().hour

    # Evening override — dusk wins regardless of mood
    if hour in _DUSK_HOURS:
        return load_visual_preset("daily_mood_dusk")

    combined = f"{weather_category}_{mood_name}".lower()
    for keywords, preset_name in _MOOD_PRESET_RULES:
        if any(kw in combined for kw in keywords):
            return load_visual_preset(preset_name)

    # Absolute fallback
    return load_visual_preset("daily_mood_warm")


# ── List helpers ──────────────────────────────────────────────────────────────

def list_available_writing_styles() -> list[str]:
    """Preset styles — e.g. zh_gentle, zh_rainy."""
    return _list_json_names(_PRESETS_DIR) or _list_json_names(_WRITING_DIR)

def list_available_author_styles() -> list[str]:
    """Author styles — e.g. mu_xin, murakami."""
    return _list_json_names(_AUTHORS_DIR)

def list_available_theme_styles() -> list[str]:
    """Theme styles — e.g. zh_solitude, zh_homecoming."""
    return _list_json_names(_THEMES_DIR)

def list_available_visual_styles() -> list[str]:
    """Visual styles — e.g. kinfolk, muji."""
    return _list_json_names(_VISUAL_DIR)

def _list_json_names(folder: str) -> list[str]:
    if not os.path.isdir(folder):
        return []
    return sorted(f[:-5] for f in os.listdir(folder) if f.endswith(".json"))
