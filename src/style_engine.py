"""
src/style_engine.py

Weighted merging of author styles and theme styles into a compressed
style context that can be injected into a prompt.

Author names never appear in the output — they are translated into
abstract traits (voice, imagery, rhythm) before reaching the prompt.
"""

from src.style_loader import (
    load_author_style,
    load_theme_style,
    load_preset_style,
)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _accumulate(items: list[tuple[str, float]]) -> list[str]:
    """
    items: [(text, weight), ...]
    When the same text appears from multiple sources, their weights are summed.
    Returns texts sorted by accumulated weight, highest first.
    """
    totals: dict[str, float] = {}
    for text, weight in items:
        totals[text] = totals.get(text, 0.0) + weight
    return [k for k, _ in sorted(totals.items(), key=lambda x: -x[1])]


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    """Normalize a weight dict so values sum to 1.0."""
    total = sum(weights.values())
    if total == 0:
        return weights
    return {k: v / total for k, v in weights.items()}


def _dedup(items: list[str]) -> list[str]:
    """Remove duplicates while preserving order."""
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# ── Public API ────────────────────────────────────────────────────────────────

def merge_author_styles(author_weights: dict[str, float]) -> dict:
    """
    Load all referenced authors and merge their style signals.

    Author names are NEVER included in the output — only abstract traits.
    Each field is sorted by accumulated weight (traits shared by high-weight
    authors bubble to the top).

    Returns:
        voice_traits    — personality/tone adjectives, top 6
        language_style  — sentence-level characteristics, top 4
        imagery         — concrete image words, top 8
        avoid           — union of all avoid lists from referenced authors
        prompt_fragments — top 3 authors' prompt_fragment strings (abstract instructions)
    """
    weights = _normalize(author_weights)

    voice_items:    list[tuple[str, float]] = []
    lang_items:     list[tuple[str, float]] = []
    imagery_items:  list[tuple[str, float]] = []
    avoid_set:      list[str]               = []
    frag_items:     list[tuple[str, float]] = []

    for author_id, weight in weights.items():
        try:
            author = load_author_style(author_id)
        except FileNotFoundError:
            continue

        for v in author.get("voice", []):
            voice_items.append((v, weight))
        for l in author.get("language", []):
            lang_items.append((l, weight))
        for img in author.get("imagery", []):
            imagery_items.append((img, weight))

        avoid_set.extend(author.get("avoid", []))

        frag = author.get("prompt_fragment", "")
        if frag:
            frag_items.append((frag, weight))

    # Sort fragments by weight and take top 3
    top_frags = [f for f, _ in sorted(frag_items, key=lambda x: -x[1])[:3]]

    return {
        "voice_traits":    _accumulate(voice_items)[:6],
        "language_style":  _accumulate(lang_items)[:4],
        "imagery":         _accumulate(imagery_items)[:8],
        "avoid":           _dedup(avoid_set),
        "prompt_fragments": top_frags,
    }


def merge_theme_styles(theme_weights: dict[str, float]) -> dict:
    """
    Load all referenced themes and merge their imagery, mood, and pattern signals.

    Returns:
        moods            — emotional territory words, top 5
        imagery          — concrete image words from imagery_pool, top 8
        sentence_patterns — example patterns, top 2 (from highest-weight themes)
        prompt_fragments  — top 2 themes' prompt_fragment strings
    """
    weights = _normalize(theme_weights)

    mood_items:     list[tuple[str, float]] = []
    imagery_items:  list[tuple[str, float]] = []
    pattern_items:  list[tuple[str, float]] = []
    frag_items:     list[tuple[str, float]] = []

    for theme_id, weight in weights.items():
        try:
            theme = load_theme_style(theme_id)
        except FileNotFoundError:
            continue

        for m in theme.get("moods", []):
            mood_items.append((m, weight))
        for img in theme.get("imagery_pool", []):
            imagery_items.append((img, weight))
        for p in theme.get("sentence_patterns", []):
            pattern_items.append((p, weight))

        frag = theme.get("prompt_fragment", "")
        if frag:
            frag_items.append((frag, weight))

    top_frags = [f for f, _ in sorted(frag_items, key=lambda x: -x[1])[:2]]

    return {
        "moods":            _accumulate(mood_items)[:5],
        "imagery":          _accumulate(imagery_items)[:8],
        "sentence_patterns": _accumulate(pattern_items)[:2],
        "prompt_fragments":  top_frags,
    }


def build_style_context(preset_id: str, sentence_count: int = 5) -> dict:
    """
    Full pipeline: load preset → merge authors → merge themes → compress.

    Returns a single dict ready to be consumed by the prompt builder.
    Author names do not appear anywhere in this dict.

    Keys:
        preset_id, display_name, tone
        voice_traits, language_style
        imagery          (author + theme merged, capped at 12)
        moods
        sentence_patterns
        avoid            (author avoid + preset do_not_use, deduped)
        style_fragments  (prompt_fragment strings from top authors + themes)
        output_rules
        prompt_instruction
    """
    preset = load_preset_style(preset_id)

    author_ctx = merge_author_styles(preset.get("author_weights", {}))
    theme_ctx  = merge_theme_styles(preset.get("theme_weights",  {}))

    # Merge imagery: theme first (more specific), then author (broader mood)
    merged_imagery = _dedup(theme_ctx["imagery"] + author_ctx["imagery"])[:12]

    # Merge avoid: authors first, then preset-level overrides
    merged_avoid = _dedup(author_ctx["avoid"] + preset.get("do_not_use", []))

    # Merge prompt fragments: theme-specific first, then author voice
    all_frags = theme_ctx["prompt_fragments"] + author_ctx["prompt_fragments"]

    # ── Weighted sentence selection ───────────────────────────────────────────
    from src.sentence_selector import get_scenario_tags, select_sentences

    scenario_tags = get_scenario_tags(
        preset.get("theme_weights", {}),
        preset.get("tone", []),
    )
    reference_sentences = select_sentences(
        preset.get("author_weights", {}),
        scenario_tags,
        custom_sentences=preset.get("custom_sentences", []),
        top_n=sentence_count,
    )

    return {
        "preset_id":          preset_id,
        "display_name":       preset.get("display_name", preset_id),
        "tone":               preset.get("tone", []),
        "voice_traits":       author_ctx["voice_traits"],
        "language_style":     author_ctx["language_style"],
        "imagery":            merged_imagery,
        "moods":              theme_ctx["moods"],
        "sentence_patterns":  theme_ctx["sentence_patterns"],
        "avoid":              merged_avoid,
        "style_fragments":    all_frags,
        "reference_sentences": reference_sentences,
        "output_rules":       preset.get("output_rules", {}),
        "prompt_instruction": preset.get("prompt_instruction", ""),
    }
