"""
src/observation_engine.py

Loads concrete observation contexts (places, objects, actions) and
selects one appropriate to the current situational context.
"""

import json
import os
import random

_ROOT             = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_OBSERVATIONS_DIR = os.path.join(_ROOT, "style_library", "writing", "observations")

_SEASON_TO_OBSERVATIONS = {
    "spring": ["spring"],
    "summer": ["summer"],
    "autumn": ["autumn"],
    "winter": ["winter"],
}

_WEATHER_TO_OBSERVATIONS = {
    "rain":   ["rain"],
    "rainy":  ["rain"],
    "cloudy": [],
    "sunny":  [],
    "clear":  [],
}

_TOD_TO_OBSERVATIONS = {
    "morning":   ["window"],
    "midday":    ["street"],
    "afternoon": ["street", "window"],
    "evening":   ["city_evening", "homecoming"],
    "night":     ["window", "homecoming"],
}


def load_observation(observation_id: str) -> dict:
    path = os.path.join(_OBSERVATIONS_DIR, f"{observation_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Observation not found: {observation_id}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def select_observation(context: dict, preset_sources: list[str]) -> dict:
    """
    Select one observation theme given situational context and preset sources.

    Priority:
      1. Weather-specific match (e.g. rain → rain.json)
      2. Time-of-day match against preset sources
      3. Random pick from preset sources
      4. Fallback to "window"

    Args:
        context:        dict with optional keys: weather, time_of_day
        preset_sources: list of observation ids from the preset

    Returns:
        A single loaded observation dict.
    """
    weather = context.get("weather", "").lower()
    tod     = context.get("time_of_day", "").lower()

    candidates: list[str] = []

    # 1. Weather-specific
    for key, obs_list in _WEATHER_TO_OBSERVATIONS.items():
        if key in weather:
            candidates.extend(obs_list)

    # Keep only candidates that are also in preset_sources (or all if preset is empty)
    if preset_sources:
        weather_hits = [c for c in candidates if c in preset_sources]
        if weather_hits:
            return _load_first_available(weather_hits)

    # 2. Time-of-day match within preset sources
    tod_hints = _TOD_TO_OBSERVATIONS.get(tod, [])
    tod_hits  = [t for t in tod_hints if t in preset_sources]
    if tod_hits:
        return _load_first_available(tod_hits)

    # 3. Random from preset sources
    available = [s for s in preset_sources if _exists(s)]
    if available:
        return load_observation(random.choice(available))

    # 4. Fallback
    try:
        return load_observation("window")
    except FileNotFoundError:
        return {"theme": "window", "objects": ["窗"], "actions": ["看"], "sensory": [], "contrasts": []}


def build_observation_context(preset: dict, context: dict) -> dict:
    """
    Given a loaded preset dict and situational context, pick and return
    one observation.

    Args:
        preset:   dict loaded from a preset JSON file
        context:  situational context dict (weather, time_of_day, …)

    Returns:
        A single observation dict.
    """
    sources = preset.get("observation_sources", [])
    return select_observation(context, sources)


def _exists(observation_id: str) -> bool:
    path = os.path.join(_OBSERVATIONS_DIR, f"{observation_id}.json")
    return os.path.exists(path)


def _load_first_available(ids: list[str]) -> dict:
    for oid in ids:
        if _exists(oid):
            return load_observation(oid)
    return load_observation("window")
