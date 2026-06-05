"""
test_style_library.py

Run: python test_style_library.py

Tests:
  1. List available writing styles
  2. List available visual styles
  3. Generate one quote using zh + gentle  (requires OPENAI_API_KEY)
  4. Render one wallpaper using kinfolk visual style
"""

import os
import sys

from src.style_library import (
    list_available_writing_styles,
    list_available_visual_styles,
    load_writing_style,
    load_visual_style,
)
from quote_generator import (
    load_context,
    load_weather,
    load_photos,
    resolve_weather,
    resolve_photos,
    generate_quote,
)
from wallpaper_renderer import load_style, render_wallpaper
from mood_engine import determine_mood


def separator(title: str) -> None:
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print('─' * 50)


def main():
    print("Daily Mood Screen — Style Library Test")

    # ── 1. List writing styles ────────────────────────────────────────────────
    separator("1. Available writing styles")
    for name in list_available_writing_styles():
        print(f"  {name}")

    # ── 2. List visual styles ─────────────────────────────────────────────────
    separator("2. Available visual styles")
    for name in list_available_visual_styles():
        print(f"  {name}")

    # ── 3. Load and inspect zh + gentle ──────────────────────────────────────
    separator("3. Writing style: zh + gentle")
    ws = load_writing_style("zh", "gentle")
    print(f"  Language  : {ws['language']}")
    print(f"  Style     : {ws['style']}")
    print(f"  Features  : {ws['features'][0]}")
    print(f"  Avoid     : {ws['do_not_use'][0]}")
    print(f"  Example   : {ws['examples'][0]}")

    # ── 4. Generate quote with zh + gentle (needs API key) ────────────────────
    separator("4. Generate quote — zh + gentle")
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("  OPENAI_API_KEY not set — skipping live generation")
        quote = ws["examples"][0]   # use an example as stand-in for the render test
        print(f"  Using example: {quote}")
    else:
        context      = load_context()
        weather_data = load_weather()
        photos_data  = load_photos()
        w    = resolve_weather(context, weather_data)
        p    = resolve_photos(context, photos_data)
        mood = determine_mood(w, p)

        print(f"  Mood: {mood['mood']}")
        print("  Calling OpenAI...")
        quote = generate_quote(
            context, api_key,
            weather=weather_data, photos=photos_data, mood=mood,
            writing_style=ws,
        )
        print(f"  Quote: {quote}")

    # ── 5. Render with kinfolk visual style ───────────────────────────────────
    separator("5. Render wallpaper — kinfolk visual style")
    vs      = load_visual_style("kinfolk")
    context = load_context()
    style   = load_style()
    weather_data = load_weather()
    photos_data  = load_photos()
    w    = resolve_weather(context, weather_data)
    p    = resolve_photos(context, photos_data)
    mood = determine_mood(w, p)

    print(f"  Visual style : {vs['style']}")
    print(f"  Font         : {vs['typography']['font']}, {vs['typography']['quote_size']}px")
    print(f"  Alignment    : {vs['layout']['alignment']}")
    print(f"  Rendering...")

    render_wallpaper(
        quote, context, style,
        weather=weather_data, photos=photos_data, mood=mood,
        visual_style=vs,
        output_path="output/test_kinfolk.png",
    )

    separator("Done")
    print("  output/test_kinfolk.png — rendered with kinfolk style")
    print("  Swap visual_style in style_config.json to try other styles.")


if __name__ == "__main__":
    main()
