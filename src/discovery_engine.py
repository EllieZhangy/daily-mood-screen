"""
src/discovery_engine.py

Loads discovery patterns (thinking modes) and merges them by weight
into a context dict that can be fed to the prompt builder.
"""

import json
import os
import random

_ROOT           = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_DISCOVERIES_DIR = os.path.join(_ROOT, "style_library", "writing", "discoveries")
_PRESETS_DIR    = os.path.join(_ROOT, "style_library", "writing", "presets")


def load_discovery(discovery_id: str) -> dict:
    path = os.path.join(_DISCOVERIES_DIR, f"{discovery_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Discovery not found: {discovery_id}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def merge_discoveries(weights: dict[str, float]) -> dict:
    """
    Load all referenced discoveries, weighted-sample one core_question per
    discovery, and return a merged context.

    Returns:
        primary_id       — discovery id with highest weight
        primary          — that discovery's full data
        core_question    — one question sampled from the primary discovery
        all_descriptions — list of (id, description) sorted by weight
    """
    if not weights:
        return {
            "primary_id": "ordinary_revelation",
            "primary": load_discovery("ordinary_revelation"),
            "core_question": "这个平凡之物，现在正在发生什么？",
            "all_descriptions": [],
        }

    # Normalize weights
    total = sum(weights.values())
    norm = {k: v / total for k, v in weights.items()}

    # Load all discoveries
    loaded = {}
    for did in norm:
        try:
            loaded[did] = load_discovery(did)
        except FileNotFoundError:
            pass

    # Sort by weight descending
    sorted_ids = sorted(norm, key=lambda k: -norm[k])
    sorted_ids = [d for d in sorted_ids if d in loaded]

    if not sorted_ids:
        fallback = load_discovery("ordinary_revelation")
        return {
            "primary_id": "ordinary_revelation",
            "primary": fallback,
            "core_question": fallback.get("core_questions", ["什么值得被注意？"])[0],
            "all_descriptions": [],
        }

    primary_id = sorted_ids[0]
    primary = loaded[primary_id]
    questions = primary.get("core_questions", ["什么值得被注意？"])
    core_question = random.choice(questions)

    all_descriptions = [
        (did, loaded[did].get("description", ""))
        for did in sorted_ids
    ]

    return {
        "primary_id": primary_id,
        "primary": primary,
        "core_question": core_question,
        "all_descriptions": all_descriptions,
    }


def build_discovery_context(preset: dict) -> dict:
    """
    Given a loaded preset dict, build the discovery context.

    Args:
        preset: dict loaded from a preset JSON file

    Returns:
        merged discovery context (see merge_discoveries)
    """
    weights = preset.get("discoveries", {})
    return merge_discoveries(weights)
