import json
import os
import sys

import requests

from mood_engine import determine_mood
from quote_generator import (
    load_context,
    load_photos,
    load_weather,
    resolve_photos,
    resolve_weather,
    generate_quote,
)
from src.style_library import load_writing_style, load_visual_style, auto_visual_preset
from wallpaper_renderer import load_style, render_wallpaper
from weather_fetcher import fetch_weather, read_city, save_weather


def load_style_config(path: str = "style_config.json") -> dict:
    """Load style_config.json. Returns empty dict if the file is missing."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def main():
    # ── Fetch live weather ────────────────────────────────────────────────────
    # If WEATHERAPI_KEY is set, fetch fresh data and overwrite weather.json.
    # If it is missing or the fetch fails, silently continue — the rest of the
    # pipeline will read whatever is already in weather.json (or fall back to
    # context.json["weather"] if weather.json doesn't exist either).
    print("Fetching weather...")
    ow_key = os.environ.get("WEATHERAPI_KEY", "").strip()
    if ow_key:
        try:
            city = read_city()
            if city is None:
                print("  Could not determine city — skipping live fetch")
            else:
                weather_live = fetch_weather(city, ow_key)
                save_weather(weather_live)
                print(f"  {weather_live['location']} · {weather_live['condition']} · {weather_live['temperature']}°C")
        except requests.exceptions.ConnectionError:
            print("  Warning: network error — using existing weather.json")
        except requests.exceptions.Timeout:
            print("  Warning: request timed out — using existing weather.json")
        except requests.exceptions.HTTPError as e:
            print(f"  Warning: API error ({e.response.status_code}) — using existing weather.json")
        except Exception as e:
            print(f"  Warning: {e} — using existing weather.json")
    else:
        print("  WEATHERAPI_KEY not set — skipping live fetch")

    # ── Load data ─────────────────────────────────────────────────────────────
    print("Loading context...")
    try:
        context = load_context()
    except FileNotFoundError:
        print("Error: context.json not found.")
        sys.exit(1)

    print("Loading weather...")
    weather_data = load_weather()
    if weather_data is None:
        print("  weather.json not found — using context.json fallback")

    # ── API key (needed for both photo-theme classification and the quote) ───
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("Error: OPENAI_API_KEY is not set.")
        print("Run:  export OPENAI_API_KEY=your-key-here")
        sys.exit(1)

    smart_quotes = '""'''
    if api_key[0] in smart_quotes or api_key[-1] in smart_quotes:
        print("Error: OPENAI_API_KEY contains curly quotes. Re-set it without any quotes.")
        print("Run:  export OPENAI_API_KEY=your-key-here")
        sys.exit(1)

    print("Loading photos...")
    photos_data = load_photos()
    if photos_data is None:
        print("  No photos for today — mood will be weather-only")

    # Resolve for mood determination.
    # render_wallpaper and generate_quote also resolve internally when called.
    weather = resolve_weather(context, weather_data)
    photos  = resolve_photos(context, photos_data)

    # ── Photo theme ───────────────────────────────────────────────────────────
    # The Shortcut exports the newest few photos to recent_photos/ — look at
    # them with a vision-capable LLM and classify the overall theme. If there's
    # nothing to look at (or the call fails), fall back to a lightweight local
    # heuristic so the mood doesn't just default to "none" every day.
    if photos_data is not None and photos_data.get("has_recent_photos"):
        from photo_theme_engine import classify_theme_from_photos, infer_theme
        from mood_engine import categorize_weather

        print("Classifying photo theme...")
        theme = classify_theme_from_photos(api_key)
        if theme is not None:
            print(f"  Vision classification: {theme}")
        else:
            theme = infer_theme(
                photo_count=photos_data.get("photo_count", 0),
                has_recent_photos=photos_data.get("has_recent_photos", False),
                weather_category=categorize_weather(weather),
            )
            print(f"  Vision classification unavailable — heuristic guess: {theme}")

        if theme != "none":
            photos_data["theme"] = theme
            photos["theme"]      = theme

    # ── Mood ──────────────────────────────────────────────────────────────────
    print("Determining mood...")
    mood = determine_mood(weather, photos)
    print(f"  {mood['mood']}  ({', '.join(mood['emotion_keywords'])})")

    # ── Load wallpaper_style.json (base layout/font defaults) ────────────────
    try:
        style = load_style()
    except FileNotFoundError:
        print("Error: wallpaper_style.json not found.")
        sys.exit(1)

    # ── Load style library selections from style_config.json ─────────────────
    style_cfg     = load_style_config()
    writing_style = None
    visual_style  = None
    preset_id     = None   # used by the new style-engine path

    if style_cfg:
        lang     = style_cfg.get("language",      "zh")
        ws_name  = style_cfg.get("writing_style", "gentle")
        vs_name  = style_cfg.get("visual_style",  "kinfolk")

        # Derive preset_id: explicit field wins, otherwise compose from lang+style
        preset_id = style_cfg.get("preset", f"{lang}_{ws_name}")

        try:
            from src.style_loader import list_presets
            if preset_id in list_presets():
                print(f"Writing preset: {preset_id}  (style engine active)")
            else:
                # Preset file doesn't exist — fall back to legacy writing_style
                preset_id = None
                writing_style = load_writing_style(lang, ws_name)
                print(f"Writing style : {lang}_{ws_name}  (legacy path)")
        except Exception as e:
            preset_id = None
            print(f"  Warning: style engine unavailable — {e}")

        try:
            if vs_name == "daily_mood":
                # Mood-aware auto-selection from reference DNA — preset chosen after mood is known
                from mood_engine import categorize_weather
                wcat = categorize_weather(resolve_weather(context, weather_data))
                visual_style = auto_visual_preset(mood["mood"], wcat)
                preset_label = visual_style.get("_preset", "daily_mood_auto")
                print(f"Visual style : {vs_name} → {preset_label}")
            else:
                visual_style = load_visual_style(vs_name)
                print(f"Visual style : {vs_name}")
        except FileNotFoundError as e:
            print(f"  Warning: {e}")

    # ── Generate background image ─────────────────────────────────────────────
    print("Generating background...")
    use_ai_background = bool(style_cfg.get("use_ai_background", False))
    try:
        from background_generator import generate_background as gen_bg
        gen_bg(
            mood=mood,
            weather=weather,
            photos=photos,
            visual_style=visual_style,
            text_color=tuple(visual_style.get("color_palette", {}).get(
                "text_primary", [52, 46, 40]
            )) if visual_style else (52, 46, 40),
            use_ai=use_ai_background,
        )
    except Exception as _bg_err:
        print(f"  Warning: background generation failed ({_bg_err})")
        print("  Renderer will use gradient fallback.")

    # ── Generate quote ────────────────────────────────────────────────────────
    print("Generating quote...")
    quote = generate_quote(context, api_key, weather=weather_data, photos=photos_data, mood=mood, writing_style=writing_style, preset_id=preset_id)
    print(f"  {quote}")

    # ── Render wallpaper ──────────────────────────────────────────────────────
    print("Rendering wallpaper...")
    render_wallpaper(quote, context, style, weather=weather_data, photos=photos_data, mood=mood, visual_style=visual_style)


def run_with_settings(language: str, output_dir: str, archive_dir: str) -> str:
    """
    Run the full pipeline with GUI-supplied settings.
    Called by the menu bar app instead of main().
    Returns the generated quote string.
    Raises RuntimeError on unrecoverable errors (no sys.exit).
    """
    # Expose paths to wallpaper_renderer via env vars
    os.environ["DAILY_MOOD_OUTPUT_DIR"]  = output_dir
    os.environ["DAILY_MOOD_ARCHIVE_DIR"] = archive_dir

    # ── Weather ───────────────────────────────────────────────────────────────
    print("Fetching weather...")
    ow_key = os.environ.get("WEATHERAPI_KEY", "").strip()
    if ow_key:
        try:
            city = read_city()
            if city:
                weather_live = fetch_weather(city, ow_key)
                save_weather(weather_live)
                print(f"  {weather_live['location']} · {weather_live['condition']} · {weather_live['temperature']}°C")
        except Exception as e:
            print(f"  Warning: weather fetch failed ({e})")
    else:
        print("  WEATHERAPI_KEY not set — skipping live fetch")

    # ── Context ───────────────────────────────────────────────────────────────
    print("Loading context...")
    try:
        context = load_context()
    except FileNotFoundError as e:
        raise RuntimeError(f"context.json not found: {e}") from e
    context["language"] = language   # settings override

    # ── API key ───────────────────────────────────────────────────────────────
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it via the menu bar.")

    # ── Photos ────────────────────────────────────────────────────────────────
    print("Loading photos...")
    weather_data = load_weather()
    photos_data  = load_photos()
    weather      = resolve_weather(context, weather_data)
    photos       = resolve_photos(context, photos_data)

    if photos_data is not None and photos_data.get("has_recent_photos"):
        from photo_theme_engine import classify_theme_from_photos, infer_theme
        from mood_engine import categorize_weather
        print("Classifying photo theme...")
        theme = classify_theme_from_photos(api_key)
        if theme is None:
            theme = infer_theme(
                photo_count=photos_data.get("photo_count", 0),
                has_recent_photos=photos_data.get("has_recent_photos", False),
                weather_category=categorize_weather(weather),
            )
        if theme != "none":
            photos_data["theme"] = theme
            photos["theme"]      = theme
        print(f"  theme: {theme}")

    # ── Mood ──────────────────────────────────────────────────────────────────
    print("Determining mood...")
    mood = determine_mood(weather, photos)
    print(f"  {mood['mood']}  ({', '.join(mood['emotion_keywords'])})")

    # ── Style ─────────────────────────────────────────────────────────────────
    try:
        style = load_style()
    except FileNotFoundError as e:
        raise RuntimeError(f"wallpaper_style.json not found: {e}") from e

    style_cfg     = load_style_config()
    writing_style = None
    visual_style  = None
    preset_id     = None

    if style_cfg:
        lang    = style_cfg.get("language",      "zh")
        ws_name = style_cfg.get("writing_style", "gentle")
        vs_name = style_cfg.get("visual_style",  "kinfolk")
        preset_id = style_cfg.get("preset", f"{lang}_{ws_name}")
        try:
            from src.style_loader import list_presets
            if preset_id in list_presets():
                print(f"Writing preset: {preset_id}")
            else:
                preset_id = None
                writing_style = load_writing_style(lang, ws_name)
        except Exception as e:
            preset_id = None
            print(f"  Warning: style engine unavailable — {e}")
        try:
            if vs_name == "daily_mood":
                from mood_engine import categorize_weather
                wcat = categorize_weather(resolve_weather(context, weather_data))
                visual_style = auto_visual_preset(mood["mood"], wcat)
            else:
                visual_style = load_visual_style(vs_name)
        except FileNotFoundError as e:
            print(f"  Warning: {e}")

    # ── Background ────────────────────────────────────────────────────────────
    print("Generating background...")
    use_ai = bool(style_cfg.get("use_ai_background", False))
    bg_output = os.path.join(output_dir, "background.png")
    os.makedirs(output_dir, exist_ok=True)
    try:
        from background_generator import generate_background as gen_bg
        gen_bg(
            mood=mood, weather=weather, photos=photos,
            visual_style=visual_style,
            text_color=tuple(visual_style.get("color_palette", {}).get(
                "text_primary", [52, 46, 40]
            )) if visual_style else (52, 46, 40),
            use_ai=use_ai,
            output_path=bg_output,
        )
    except Exception as e:
        print(f"  Warning: background generation failed ({e})")

    # ── Quote ─────────────────────────────────────────────────────────────────
    print("Generating quote...")
    quote = generate_quote(
        context, api_key,
        weather=weather_data, photos=photos_data, mood=mood,
        writing_style=writing_style, preset_id=preset_id,
    )
    print(f"  {quote}")

    # ── Render ────────────────────────────────────────────────────────────────
    print("Rendering wallpaper...")
    wallpaper_output = os.path.join(output_dir, "daily_wallpaper_mac.png")
    render_wallpaper(
        quote, context, style,
        weather=weather_data, photos=photos_data, mood=mood,
        visual_style=visual_style,
        output_path=wallpaper_output,
    )

    return quote


if __name__ == "__main__":
    main()
