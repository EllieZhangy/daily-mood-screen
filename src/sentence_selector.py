"""
src/sentence_selector.py

Selects weighted reference sentences from author libraries
based on the active preset's scenario (derived from theme_weights + tone).

Author names are NEVER returned — only their sentences, stripped of attribution.
The caller decides how to present them in the prompt (as style reference only).
"""

from src.style_loader import load_author_style

# ── Tag map: preset theme_id → sentence tags to prioritise ────────────────────
THEME_TO_TAGS: dict[str, list[str]] = {
    "zh_homecoming":      ["homecoming", "evening", "city", "connection"],
    "zh_ordinary_life":   ["ordinary_life", "daily", "food"],
    "zh_solitude":        ["solitude", "inner_life", "reflective"],
    "zh_passage_of_time": ["time", "nostalgic", "passage_of_time", "memory"],
    "zh_nature":          ["nature", "seasons", "weather"],
    "zh_hopeful":         ["hopeful", "resilience", "gentle"],
}

# ── Tag map: preset tone label → extra sentence tags ─────────────────────────
TONE_TO_TAGS: dict[str, list[str]] = {
    "黄昏感": ["evening"],
    "城市感": ["city"],
    "安静":   ["solitude"],
    "怀旧":   ["nostalgic", "memory"],
    "生活感": ["ordinary_life", "daily"],
    "温柔":   ["gentle"],
    "雨天":   ["rainy", "weather"],
    "收束":   ["evening", "homecoming"],
}


def get_scenario_tags(
    theme_weights: dict[str, float],
    preset_tone: list[str] | None = None,
) -> set[str]:
    """
    Derive a set of sentence tags from the preset's theme/tone mix.
    Only the top-3 themes by weight are expanded (keeps focus tight).
    """
    tags: set[str] = set()

    ranked = sorted(theme_weights.items(), key=lambda x: -x[1])
    for i, (theme_id, weight) in enumerate(ranked):
        if i >= 3 and weight < 0.15:
            break
        tags.update(THEME_TO_TAGS.get(theme_id, []))

    for tone in (preset_tone or []):
        tags.update(TONE_TO_TAGS.get(tone, []))

    return tags


def select_sentences(
    author_weights: dict[str, float],
    scenario_tags: set[str],
    custom_sentences: list[str] | None = None,
    top_n: int = 5,
) -> list[str]:
    """
    Select the most scenario-relevant reference sentences across all weighted authors.

    Scoring formula:
        score = author_weight × sentence_weight × (0.3 + 0.7 × tag_overlap_ratio)

    custom_sentences (from the preset's own pool) are injected first at max score,
    then filled with author sentences up to top_n.

    Returns:
        A plain list of sentence strings, ordered by relevance.
        Author names are NOT included.
    """
    total_w = sum(author_weights.values()) or 1.0
    weights = {k: v / total_w for k, v in author_weights.items()}

    candidates: list[tuple[float, str]] = []   # (score, text)

    for author_id, author_weight in weights.items():
        try:
            author = load_author_style(author_id)
        except FileNotFoundError:
            continue

        for sentence in author.get("reference_sentences", []):
            text   = sentence.get("text", "").strip()
            tags   = set(sentence.get("tags", []))
            weight = float(sentence.get("weight", 1.0))

            if not text:
                continue

            if scenario_tags:
                overlap = len(tags & scenario_tags) / len(scenario_tags)
                if overlap == 0:
                    continue   # discard sentences with zero tag match
            else:
                overlap = 0.5

            score = author_weight * weight * (0.3 + 0.7 * overlap)
            candidates.append((score, text))

    # Sort by score, deduplicate
    seen: set[str] = set()
    ranked: list[str] = []

    # Custom preset sentences go first (highest priority)
    for text in (custom_sentences or []):
        if text and text not in seen:
            seen.add(text)
            ranked.append(text)

    for score, text in sorted(candidates, key=lambda x: -x[0]):
        if text not in seen:
            seen.add(text)
            ranked.append(text)
        if len(ranked) >= top_n:
            break

    return ranked[:top_n]
