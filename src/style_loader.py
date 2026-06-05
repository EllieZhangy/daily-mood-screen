"""
src/style_loader.py

Pure file I/O layer for the style library.
No business logic here — just load and list.
"""

import json
import os

_ROOT       = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_AUTHORS    = os.path.join(_ROOT, "style_library", "writing", "authors")
_THEMES     = os.path.join(_ROOT, "style_library", "writing", "themes")
_PRESETS    = os.path.join(_ROOT, "style_library", "writing", "presets")


def load_json(path: str) -> dict:
    """Load any JSON file by absolute or relative path."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_author_style(author_id: str) -> dict:
    """
    Load an author style file.
    author_id is the filename without extension, e.g. 'mu_xin'.
    """
    path = os.path.join(_AUTHORS, f"{author_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Author '{author_id}' not found. Available: {list_authors()}"
        )
    return load_json(path)


def load_theme_style(theme_id: str) -> dict:
    """
    Load a theme style file.
    theme_id is the filename without extension, e.g. 'zh_homecoming'.
    """
    path = os.path.join(_THEMES, f"{theme_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Theme '{theme_id}' not found. Available: {list_themes()}"
        )
    return load_json(path)


def load_preset_style(preset_id: str) -> dict:
    """
    Load a preset style file.
    preset_id is the filename without extension, e.g. 'zh_evening'.
    """
    path = os.path.join(_PRESETS, f"{preset_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Preset '{preset_id}' not found. Available: {list_presets()}"
        )
    return load_json(path)


def list_authors() -> list[str]:
    """Return sorted list of available author IDs."""
    return _list_names(_AUTHORS)


def list_themes() -> list[str]:
    """Return sorted list of available theme IDs."""
    return _list_names(_THEMES)


def list_presets() -> list[str]:
    """Return sorted list of available preset IDs."""
    return _list_names(_PRESETS)


def _list_names(folder: str) -> list[str]:
    if not os.path.isdir(folder):
        return []
    return sorted(f[:-5] for f in os.listdir(folder) if f.endswith(".json"))
