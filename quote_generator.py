import json
import os
import sys
from datetime import date as _date, datetime as _datetime

from openai import OpenAI

from mood_engine import determine_mood

SUPPORTED_LANGUAGES = {"zh-CN", "en-US"}


def load_context(path: str = "context.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_weather(path: str = "weather.json") -> dict | None:
    """
    Try to load weather.json.
    Returns the weather dict if the file exists, or None if it doesn't.
    The caller decides what to do when None is returned (usually fall back
    to context.json["weather"]).
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def load_photos(path: str = "photos.json") -> dict | None:
    """
    Try to load photos.json, but only if it was written today.

    Photos are personal and time-sensitive — yesterday's outing shouldn't
    colour today's wallpaper. If the file exists but is from a previous day,
    treat it as stale and return None so the pipeline uses the no-photos default.

    Returns the photos dict, or None if the file is missing or stale.
    """
    try:
        # Check modification date before reading content
        mtime      = os.path.getmtime(path)
        file_date  = _date.fromtimestamp(mtime)
        today      = _date.today()

        if file_date != today:
            return None   # stale — from a previous day

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except FileNotFoundError:
        return None


def resolve_photos(context: dict, photos_data: dict | None) -> dict:
    """
    Return the photos dict that should be used everywhere.

    Priority:
      1. photos.json  (if it was loaded successfully — photos_data is not None)
      2. context.json["photos"]  (fallback when photos.json doesn't exist)
    """
    if photos_data is not None:
        return photos_data
    # photos.json was missing — fall back to the photos block in context.json
    return context.get("photos", {})


def resolve_weather(context: dict, weather_data: dict | None) -> dict:
    """
    Return the weather dict that should be used everywhere.

    Priority:
      1. weather.json  (if it was loaded successfully — weather_data is not None)
      2. context.json["weather"]  (fallback when weather.json doesn't exist)
    """
    if weather_data is not None:
        return weather_data
    # weather.json was missing — fall back to the weather block in context.json
    return context.get("weather", {})


def build_prompt(context: dict, weather: dict, photos: dict, mood: dict, writing_style: dict | None = None) -> str:
    """Turn context fields into a natural-language description for the AI."""
    language = context.get("language", "en-US")
    style    = context.get("style", {})

    # ── Weather ───────────────────────────────────────────────────────────────
    condition   = weather.get("condition", "unknown")
    temperature = weather.get("temperature", "unknown")
    location    = weather.get("location", "")   # only present in weather.json

    # ── Photos ────────────────────────────────────────────────────────────────
    photo_theme = photos.get("theme", "none")
    photo_count = photos.get("photo_count", 0)

    # ── Mood (from mood_engine) ───────────────────────────────────────────────
    mood_name     = mood.get("mood", "unknown")
    emotion_words = ", ".join(mood.get("emotion_keywords", []))
    visual_words  = ", ".join(mood.get("visual_keywords",  []))

    # ── Base style (from context.json) ────────────────────────────────────────
    tone_words  = ", ".join(style.get("tone",  ["calm", "literary"]))
    avoid_words = ", ".join(style.get("avoid", []))

    # ── Language instruction ──────────────────────────────────────────────────
    if language == "zh-CN":
        language_instruction = "Write in Chinese (Simplified). The quote must be in Chinese."
    else:
        language_instruction = "Write in English."

    # Build context lines
    weather_line = f"{condition}, {temperature}°C"
    if location:
        weather_line = f"{location} — {weather_line}"
    photo_line = f"{photo_count} recent photos, {photo_theme} theme"

    # ── Writing style block (injected from style_library when available) ──────
    # This section gives the AI specific stylistic guidance, overriding the
    # generic style requirements above with more precise instructions.
    writing_style_block = ""
    if writing_style:
        features    = "\n".join(f"  - {f}" for f in writing_style.get("features",    []))
        avoid_list  = "\n".join(f"  - {d}" for d in writing_style.get("do_not_use",  []))
        examples    = "\n".join(f"  - {e}" for e in writing_style.get("examples",    []))
        instruction = writing_style.get("prompt_instruction", "")

        writing_style_block = f"""
Writing style: {writing_style.get("style", "")}
Style features:
{features}
Do not use:
{avoid_list}
Reference examples (study the style only — do not copy these):
{examples}
Core instruction: {instruction}"""

    prompt = f"""You are a poetic writer creating a daily mood quote for a personal screen wallpaper.

Context for today:
- Weather: {weather_line}
- Photos: {photo_line}
- Mood: {mood_name}
- Emotional direction: {emotion_words}
- Visual atmosphere: {visual_words}

General style:
- Tone: {tone_words}
- Avoid: {avoid_words}
- Let the mood and visual atmosphere shape the quote
- The quote should evoke a feeling, not give advice
- Emotionally restrained, modern, subtle — not dramatic or over-the-top
{writing_style_block}
Format:
- Output exactly 1 to 2 short lines
- No title, no label, no explanation — just the quote itself
- {language_instruction}"""

    return prompt


def _time_of_day() -> str:
    """Derive a time-of-day label from the current hour."""
    h = _datetime.now().hour
    if 6  <= h < 12: return "morning"
    if 12 <= h < 14: return "midday"
    if 14 <= h < 18: return "afternoon"
    if 18 <= h < 22: return "evening"
    return "night"


def _make_style_context(context: dict, weather: dict, mood: dict) -> dict:
    """
    Build the simplified context dict expected by build_quote_prompt.
    Maps from the richer internal data model to the compact prompt context.
    """
    return {
        "language":    context.get("language", "zh-CN"),
        "weather":     weather.get("condition", ""),
        "temperature": weather.get("temperature", ""),
        "location":    weather.get("location", ""),
        "time_of_day": _time_of_day(),
        "mood":        mood.get("emotion_keywords", ["calm"])[0] if mood else "calm",
    }


def generate_quote(context: dict, api_key: str, weather: dict | None = None, photos: dict | None = None, mood: dict | None = None, writing_style: dict | None = None, preset_id: str | None = None) -> str:
    """
    Call the OpenAI API and return the generated quote.

    When preset_id is provided the new style engine is used to build the prompt.
    Otherwise the existing build_prompt pipeline is used (backward compatible).
    """
    client = OpenAI(api_key=api_key)

    resolved_weather = resolve_weather(context, weather)
    resolved_photos  = resolve_photos(context, photos)

    # Compute mood if not already provided by the caller
    if mood is None:
        mood = determine_mood(resolved_weather, resolved_photos)

    if preset_id:
        # ── New style-engine path ─────────────────────────────────────────────
        from src.prompt_builder import build_quote_prompt
        style_ctx = _make_style_context(context, resolved_weather, mood)
        prompt    = build_quote_prompt(style_ctx, preset_id)
    else:
        # ── Legacy path (backward compatible) ────────────────────────────────
        prompt = build_prompt(context, resolved_weather, resolved_photos, mood, writing_style=writing_style)

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "user", "content": prompt}
        ],
        # Keep the response short and focused
        max_tokens=100,
        temperature=0.85,
    )

    # Extract the text from the response
    quote = response.choices[0].message.content.strip()
    return quote


def main():
    # Allow passing a custom context file path as a command-line argument
    context_path = sys.argv[1] if len(sys.argv) > 1 else "context.json"

    # Load context.json
    try:
        context = load_context(context_path)
    except FileNotFoundError:
        print(f"Error: context file not found at '{context_path}'")
        sys.exit(1)

    # Read the API key from environment — never hardcode it
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        print("Run:  export OPENAI_API_KEY=your-key-here")
        sys.exit(1)

    # Guard against smart/curly quotes wrapping the key (common copy-paste issue)
    smart_quotes = '“”‘’'  # " " ' '
    if api_key[0] in smart_quotes or api_key[-1] in smart_quotes:
        print("Error: OPENAI_API_KEY contains curly quotes (“”) instead of straight quotes.")
        print("Re-set it without any quotes:")
        print("  export OPENAI_API_KEY=sk-your-key-here")
        sys.exit(1)

    # Try to load weather.json; fall back to context.json["weather"] if missing
    weather_data = load_weather()
    weather = resolve_weather(context, weather_data)

    if weather_data is not None:
        print("Weather  : loaded from weather.json")
    else:
        print("Weather  : weather.json not found, using context.json fallback")

    # Try to load photos.json; fall back to context.json["photos"] if missing
    photos_data = load_photos()
    photos = resolve_photos(context, photos_data)

    if photos_data is not None:
        print("Photos   : loaded from photos.json")
    else:
        print("Photos   : photos.json not found, using context.json fallback")

    # Validate language
    language = context.get("language", "en-US")
    if language not in SUPPORTED_LANGUAGES:
        print(f"Warning: unsupported language '{language}', falling back to en-US.")
        context["language"] = "en-US"
        language = "en-US"

    # Determine mood from the resolved weather and photos
    mood = determine_mood(weather, photos)

    print("=" * 50)
    print(f"Language : {language}")
    if weather.get("location"):
        print(f"Location : {weather['location']}")
    print(f"Weather  : {weather.get('condition', 'unknown')}, {weather.get('temperature', '?')}°{weather.get('unit', 'C')}")
    print(f"Photos   : theme={photos.get('theme', 'none')}, count={photos.get('photo_count', 0)}, people={photos.get('has_people', False)}")
    print(f"Mood     : {mood['mood']}  ({', '.join(mood['emotion_keywords'])})")
    print("=" * 50)
    print("\nGenerating quote...\n")

    quote = generate_quote(context, api_key, weather=weather_data, photos=photos_data, mood=mood)

    print(f"  {quote}\n")
    print("=" * 50)


if __name__ == "__main__":
    main()
