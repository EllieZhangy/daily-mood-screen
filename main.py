import os
import sys

from mood_engine import determine_mood
from quote_generator import (
    load_context,
    load_photos,
    load_weather,
    resolve_photos,
    resolve_weather,
    generate_quote,
)
from wallpaper_renderer import load_style, render_wallpaper


def main():
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

    print("Loading photos...")
    photos_data = load_photos()
    if photos_data is None:
        print("  photos.json not found — using context.json fallback")

    # Resolve for mood determination.
    # render_wallpaper and generate_quote also resolve internally when called.
    weather = resolve_weather(context, weather_data)
    photos  = resolve_photos(context, photos_data)

    # ── Mood ──────────────────────────────────────────────────────────────────
    print("Determining mood...")
    mood = determine_mood(weather, photos)
    print(f"  {mood['mood']}  ({', '.join(mood['emotion_keywords'])})")

    # ── Load style early — fail before making an API call if file is missing ──
    try:
        style = load_style()
    except FileNotFoundError:
        print("Error: wallpaper_style.json not found.")
        sys.exit(1)

    # ── API key ───────────────────────────────────────────────────────────────
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

    # ── Generate quote ────────────────────────────────────────────────────────
    print("Generating quote...")
    quote = generate_quote(context, api_key, weather=weather_data, photos=photos_data, mood=mood)
    print(f"  {quote}")

    # ── Render wallpaper ──────────────────────────────────────────────────────
    print("Rendering wallpaper...")
    render_wallpaper(quote, context, style, weather=weather_data, photos=photos_data, mood=mood)


if __name__ == "__main__":
    main()
