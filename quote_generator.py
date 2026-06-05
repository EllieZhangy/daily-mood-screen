import json
import os
import sys

from openai import OpenAI

SUPPORTED_LANGUAGES = {"zh-CN", "en-US"}


def load_context(path: str = "context.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_prompt(context: dict) -> str:
    """Turn context fields into a natural-language description for the AI."""
    language = context.get("language", "en-US")
    weather = context.get("weather", {})
    photos = context.get("photos", {})
    style = context.get("style", {})

    condition = weather.get("condition", "unknown")
    temperature = weather.get("temperature", "unknown")
    photo_theme = photos.get("theme", "none")
    has_people = photos.get("has_people", False)

    tone_words = ", ".join(style.get("tone", ["calm", "literary"]))
    avoid_words = ", ".join(style.get("avoid", []))

    # Choose output language instruction
    if language == "zh-CN":
        language_instruction = "Write in Chinese (Simplified). The quote must be in Chinese."
    else:
        language_instruction = "Write in English."

    prompt = f"""You are a poetic writer creating a daily mood quote for a personal screen wallpaper.

Context for today:
- Weather: {condition}, {temperature}°C
- Recent photos theme: {photo_theme}
- Photos include people: {has_people}

Style requirements:
- Tone: {tone_words}
- Avoid: {avoid_words}
- The quote should create a feeling or mood, not give advice
- Suitable for a calm, literary, Xiaohongshu-style aesthetic
- Visually evocative and emotionally restrained
- Modern, subtle — not dramatic or over-the-top

Format:
- Output exactly 1 to 2 short lines
- No title, no label, no explanation — just the quote itself
- {language_instruction}"""

    return prompt


def generate_quote(context: dict, api_key: str) -> str:
    """Call the OpenAI API and return the generated quote."""
    client = OpenAI(api_key=api_key)

    prompt = build_prompt(context)

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

    # Validate language
    language = context.get("language", "en-US")
    if language not in SUPPORTED_LANGUAGES:
        print(f"Warning: unsupported language '{language}', falling back to en-US.")
        context["language"] = "en-US"
        language = "en-US"

    weather = context.get("weather", {})
    photos = context.get("photos", {})

    print("=" * 50)
    print(f"Language : {language}")
    print(f"Weather  : {weather.get('condition', 'unknown')}, {weather.get('temperature', '?')}°C")
    print(f"Photos   : theme={photos.get('theme', 'none')}, people={photos.get('has_people', False)}")
    print("=" * 50)
    print("\nGenerating quote...\n")

    quote = generate_quote(context, api_key)

    print(f"  {quote}\n")
    print("=" * 50)


if __name__ == "__main__":
    main()
