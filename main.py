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
from wallpaper_renderer import load_style, render_wallpaper
from weather_fetcher import fetch_weather, read_city, save_weather


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

    print("Loading photos...")
    photos_data = load_photos()
    if photos_data is None:
        print("  No photos for today — mood will be weather-only")

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
