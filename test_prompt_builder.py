"""
test_prompt_builder.py

Run:  python test_prompt_builder.py

Tests the full style engine + prompt builder pipeline for the zh_evening preset.
Does NOT require OPENAI_API_KEY — returns a placeholder quote.
Set OPENAI_API_KEY if you want a real generated quote at the end.
"""

import os
from src.style_loader import (
    list_authors, list_themes, list_presets,
    load_preset_style,
)
from src.style_engine import (
    merge_author_styles,
    merge_theme_styles,
    build_style_context,
)
from src.prompt_builder import build_quote_prompt, generate_quote_with_style


def section(title: str) -> None:
    print(f"\n{'━' * 54}")
    print(f"  {title}")
    print('━' * 54)


def main():
    context = {
        "language":    "zh-CN",
        "weather":     "cloudy",
        "temperature": 18,
        "time_of_day": "evening",
        "mood":        "calm",
    }
    preset_id = "zh_evening"

    # ── 1. Library overview ───────────────────────────────────────────────────
    section("1 · Available styles")
    print(f"  Authors  ({len(list_authors())}): {', '.join(list_authors())}")
    print(f"  Themes   ({len(list_themes())}): {', '.join(list_themes())}")
    print(f"  Presets  ({len(list_presets())}): {', '.join(list_presets())}")

    # ── 2. Loaded preset ──────────────────────────────────────────────────────
    section("2 · Loaded preset")
    preset = load_preset_style(preset_id)
    print(f"  ID           : {preset.get('preset')}")
    print(f"  Display name : {preset.get('display_name')}")
    print(f"  Tone         : {', '.join(preset.get('tone', []))}")
    print(f"  Author weights:")
    for a, w in sorted(preset["author_weights"].items(), key=lambda x: -x[1]):
        print(f"    {a:<20} {w:.2f}")
    print(f"  Theme weights:")
    for t, w in sorted(preset["theme_weights"].items(), key=lambda x: -x[1]):
        print(f"    {t:<28} {w:.2f}")

    # ── 3. Merged author context ──────────────────────────────────────────────
    section("3 · Merged author style context")
    author_ctx = merge_author_styles(preset["author_weights"])
    print(f"  Voice traits   : {', '.join(author_ctx['voice_traits'])}")
    print(f"  Language style : {', '.join(author_ctx['language_style'])}")
    print(f"  Imagery        : {', '.join(author_ctx['imagery'])}")
    print(f"  Avoid          : {', '.join(author_ctx['avoid'][:5])} …")
    print(f"  Top fragments  :")
    for frag in author_ctx["prompt_fragments"]:
        print(f"    · {frag}")

    # ── 4. Merged theme context ───────────────────────────────────────────────
    section("4 · Merged theme style context")
    theme_ctx = merge_theme_styles(preset["theme_weights"])
    print(f"  Moods            : {', '.join(theme_ctx['moods'])}")
    print(f"  Imagery          : {', '.join(theme_ctx['imagery'])}")
    print(f"  Sentence patterns: {theme_ctx['sentence_patterns']}")
    print(f"  Top fragments    :")
    for frag in theme_ctx["prompt_fragments"]:
        print(f"    · {frag}")

    # ── 5. Full style context ─────────────────────────────────────────────────
    section("5 · Full style context (build_style_context)")
    style_ctx = build_style_context(preset_id)
    print(f"  Merged imagery   : {', '.join(style_ctx['imagery'])}")
    print(f"  All avoid items  : {len(style_ctx['avoid'])}")
    print(f"  Style fragments  : {len(style_ctx['style_fragments'])}")

    # ── 6. Final prompt ───────────────────────────────────────────────────────
    section("6 · Final prompt")
    prompt = build_quote_prompt(context, preset_id)
    print(prompt)

    # ── 7. Generated quote ────────────────────────────────────────────────────
    section("7 · Generated quote")
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    quote = generate_quote_with_style(context, preset_id, api_key=api_key or None)
    print(f"\n  {quote}\n")


if __name__ == "__main__":
    main()
