# photo_theme_engine.py
#
# v3: classify today's photo theme by actually looking at the most recent
# photos. The Photos Shortcut now exports the newest few photos as image
# files into recent_photos/ (instead of just writing a "theme" guess into
# photos.json). We pick the newest 3-5 of those, downsize/convert them with
# macOS `sips`, and ask a vision-capable LLM to classify the overall theme.
#
# A lightweight local heuristic (infer_theme, v2) is kept as a fallback for
# days when recent_photos/ is empty or the vision call fails — it infers a
# plausible theme from signals that are always available locally (photo
# count, time of day, day of week, weather category).

import base64
import glob
import os
import subprocess
import tempfile
from datetime import datetime

from openai import OpenAI

SUPPORTED_THEMES = [
    "friends", "nature", "food", "travel", "family",
    "self", "memories", "study", "quiet", "none",
]

# Themes the vision classifier is asked to choose from. "quiet" depends on
# situational context (time of day, mood) rather than visual content, so it's
# left to the local heuristic fallback — but "study" (desks, screens, books,
# notes) is visually distinctive enough for the model to recognize directly.
VISION_THEMES = ["friends", "nature", "food", "travel", "family", "self", "memories", "study", "none"]

RECENT_PHOTOS_DIR = "recent_photos"
_IMAGE_EXTENSIONS = (".heic", ".jpg", ".jpeg", ".png", ".heif")


# ── Vision-based classification (primary) ────────────────────────────────────

def _newest_photos(photos_dir: str, max_photos: int) -> list[str]:
    """Return paths to the newest `max_photos` images in `photos_dir`, newest first."""
    paths = [
        p for p in glob.glob(os.path.join(photos_dir, "*"))
        if p.lower().endswith(_IMAGE_EXTENSIONS) and os.path.isfile(p)
    ]
    paths.sort(key=os.path.getmtime, reverse=True)
    return paths[:max_photos]


def _to_jpeg_data_url(src_path: str, tmp_dir: str, max_dim: int = 512) -> str | None:
    """Convert/downsize an image to JPEG via macOS `sips` and return a data: URL."""
    dst_path = os.path.join(tmp_dir, os.path.splitext(os.path.basename(src_path))[0] + ".jpg")
    try:
        subprocess.run(
            ["sips", "-s", "format", "jpeg", "-Z", str(max_dim), src_path, "--out", dst_path],
            check=True, capture_output=True,
        )
        with open(dst_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        return None


def classify_theme_from_photos(api_key: str, photos_dir: str = RECENT_PHOTOS_DIR,
                               max_photos: int = 5) -> str | None:
    """
    Look at the newest few photos in `photos_dir` and ask a vision-capable
    LLM to classify their overall theme.

    Returns one of VISION_THEMES, or None if there are no photos to look at
    or the classification couldn't be completed (caller should fall back to
    infer_theme()).
    """
    photo_paths = _newest_photos(photos_dir, max_photos)
    if not photo_paths:
        return None

    with tempfile.TemporaryDirectory() as tmp_dir:
        data_urls = [u for p in photo_paths if (u := _to_jpeg_data_url(p, tmp_dir))]

    if not data_urls:
        return None

    theme_list = "\n".join(f"- {t}" for t in VISION_THEMES)
    prompt_text = (
        f"Here are {len(data_urls)} of someone's most recent photos. "
        "Based on what they show, classify the overall theme of this batch "
        f"as EXACTLY ONE of the following:\n{theme_list}\n\n"
        "Guidelines: \"friends\" = groups/social gatherings, \"family\" = "
        "relatives/home life, \"self\" = selfies or solo/personal shots, "
        "\"study\" = desks, screens, books, notes, work/study setups, "
        "\"memories\" = old/archival/nostalgic-looking images or screenshots, "
        "\"none\" = no theme stands out clearly.\n"
        "Reply with ONLY the single category word — no punctuation, no explanation."
    )

    content = [{"type": "text", "text": prompt_text}]
    content += [{"type": "image_url", "image_url": {"url": url}} for url in data_urls]

    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": content}],
            max_tokens=10,
            temperature=0,
        )
        guess = response.choices[0].message.content.strip().lower()
    except Exception as e:
        print(f"  Vision theme classification failed: {e}")
        return None

    for theme in VISION_THEMES:
        if theme in guess:
            return theme
    return None


# ── Local heuristic (fallback, used when no photos are available to inspect) ──

def infer_theme(photo_count: int, has_recent_photos: bool,
                now: datetime = None,
                weather_category: str = None) -> str:
    """
    Guess a photo theme from contextual signals — used as a fallback when
    classify_theme_from_photos() has nothing to look at (e.g. recent_photos/
    is empty) or the vision call fails.

    Returns one of SUPPORTED_THEMES, falling back to "none" when there's
    nothing to infer from (no recent photos).
    """
    if not has_recent_photos or photo_count <= 0:
        return "none"

    now = now or datetime.now()
    hour, weekday = now.hour, now.weekday()   # weekday: 0=Mon … 6=Sun
    is_weekend = weekday >= 5

    # Late night / pre-dawn — people aren't out socialising
    if hour >= 23 or hour < 6:
        return "quiet"

    # Weekday work/school hours with a modest count — desk-and-notes territory
    if not is_weekend and 8 <= hour < 18 and photo_count <= 4:
        return "study"

    # A burst of photos in one window usually means a gathering
    if photo_count >= 8:
        return "friends"

    if is_weekend:
        if photo_count >= 4:
            # Decent weather + a handful of shots → likely an outdoor outing
            return "nature" if weather_category in ("sunny", "cloudy") else "friends"
        return "family"

    # Weekday evening — dinner and downtime
    if 18 <= hour < 23:
        return "food" if photo_count >= 3 else "self"

    # Whatever's left — a few photos with no stronger signal
    return "self" if photo_count <= 2 else "memories"
