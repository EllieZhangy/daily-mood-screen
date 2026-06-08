"""
src/typography_engine.py

Handwritten-note typography engine for the Daily Mood Desktop wallpaper system.

Renders text character-by-character with subtle per-glyph variation:
  - baseline jitter      (y offset per character)
  - x-spacing variation  (slightly uneven tracking)
  - rotation             (very subtle tilt per character)
  - opacity variation    (ink pressure feel)

The goal is text that looks written, not typeset.
"""

import json
import os
import random
import hashlib

from PIL import Image, ImageDraw, ImageFont

# ── Paths ─────────────────────────────────────────────────────────────────────
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STYLE_DIR = os.path.join(_BASE, "style_library", "visual", "typography")
_FONTS_DIR = os.path.join(_BASE, "assets", "fonts")

# ── Font candidates (checked in order, first loadable wins) ───────────────────
# Priority: user-supplied → LXGW WenKai → HanziPen SC → Kaiti SC → fallbacks
_FONT_CANDIDATES = [
    # User-supplied fonts in assets/fonts/ — scanned dynamically in choose_font()
    # LXGW WenKai Handwriting (if user installs it)
    "/Library/Fonts/LXGWWenKaiScreen.ttf",
    "/Library/Fonts/LXGWWenKai-Regular.ttf",
    os.path.expanduser("~/Library/Fonts/LXGWWenKaiScreen.ttf"),
    os.path.expanduser("~/Library/Fonts/LXGWWenKai-Regular.ttf"),
    # HanziPen SC — Apple's casual handwriting font (macOS)
    "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/"
    "9fdda46cbe802833590494a09b2787378340c597.asset/AssetData/Hanzipen.ttc",
    # Kaiti SC — regular script, softer than Heiti
    "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/"
    "54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc",
    # STFangsong — traditional brush-influenced
    "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/"
    "1821952872c81043711aab6910052b65da8edf2c.asset/AssetData/STFANGSO.ttf",
    # System fallbacks
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
]


# ── Public API ────────────────────────────────────────────────────────────────

def load_typography_style(style_id: str) -> dict:
    """Load a typography style JSON from style_library/visual/typography/."""
    path = os.path.join(_STYLE_DIR, f"{style_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Typography style not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def choose_font(style_id: str, size: int = 96) -> ImageFont.FreeTypeFont:
    """
    Select the best available font for the given typography style.

    Checks assets/fonts/ first (user-supplied), then system font candidates.
    Returns an ImageFont ready to use at the given pixel size.
    """
    # 1. Scan user-supplied fonts in assets/fonts/
    if os.path.isdir(_FONTS_DIR):
        for fname in sorted(os.listdir(_FONTS_DIR)):
            if fname.lower().endswith((".ttf", ".ttc", ".otf")):
                path = os.path.join(_FONTS_DIR, fname)
                try:
                    font = ImageFont.truetype(path, size)
                    print(f"  font : custom  — {fname}")
                    return font
                except Exception:
                    continue

    # 2. Walk the candidate list
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                name = os.path.basename(path)
                print(f"  font : {name}")
                return font
            except Exception:
                continue

    # 3. Last resort — PIL built-in bitmap (no Chinese support, but won't crash)
    print("  font : WARNING — no suitable font found, using built-in bitmap")
    return ImageFont.load_default()


# CJK punctuation that HanziPen SC renders with incorrect glyphs (，→ ', 。→ °).
# These characters are rendered using a fallback system font when punct_font is provided.
_CJK_PUNCT = frozenset('，。、；：！？…—～「」『』【】（）〈〉《》')

# Preferred line-break points: break AFTER these so the punctuation stays
# with the phrase it closes (e.g. "他走了，" stays together).
_PREFER_BREAK_AFTER = frozenset('，。！？；：、')


def render_handwritten_text(
    image: Image.Image,
    text: str,
    position: tuple,
    style_config: dict,
    color: tuple = (255, 255, 255),
    font: ImageFont.FreeTypeFont = None,
    punct_font: ImageFont.FreeTypeFont = None,
    text_align: str = "left",
) -> Image.Image:
    """
    Render text onto image with per-character handwriting variation.

    Each character is drawn onto a small transparent layer, optionally
    rotated and shifted, then composited onto the main image.

    Args:
        image:       PIL Image (RGBA or RGB) to draw onto.
        text:        String to render. '\\n' forces a line break.
        position:    (x, y) anchor. For text_align="left" this is the top-left
                     of the block. For text_align="right" this is the RIGHT edge
                     of the block — each line starts at (x - line_width, y).
        style_config: Dict loaded from handwritten_note.json.
        color:       RGB tuple for text color.
        font:        Primary handwriting font (e.g. HanziPen SC).
        punct_font:  Fallback font for CJK punctuation that the primary font
                     renders with wrong glyphs. If None, primary font is used.
        text_align:  "left" (default) or "right". Right-aligns each line so its
                     right edge meets position[0], matching metadata alignment.
    """
    if font is None:
        font = ImageFont.load_default()

    rendering = style_config.get("rendering", {})
    spacing   = style_config.get("spacing",   {})

    base_opacity   = rendering.get("opacity",           0.88)
    opacity_var    = rendering.get("opacity_variation", 0.09)
    jitter_x_px    = rendering.get("jitter_x_px",      4)
    jitter_y_px    = rendering.get("jitter_y_px",       5)
    rotation_max   = rendering.get("rotation_max_deg",  2.2)
    do_jitter      = rendering.get("jitter",             True)
    extra_spacing  = spacing.get("character_spacing_px_extra", 3)

    # Seed RNG from text hash for deterministic but natural variation
    seed_int = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed_int)

    # Ensure image is RGBA for compositing
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    lines = text.split("\n")

    _probe_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    probe_bbox  = _probe_draw.textbbox((0, 0), "国", font=font)
    char_h      = probe_bbox[3] - probe_bbox[1]
    char_w_ref  = probe_bbox[2] - probe_bbox[0]
    line_gap    = int(char_h * (spacing.get("line_spacing", 1.52) - 1.0))

    x0, y0 = position

    def _measure_line(line: str) -> int:
        """Pixel width of a line using the same per-char measurement as the renderer."""
        total = 0
        for ch in line:
            cf = punct_font if (punct_font and ch in _CJK_PUNCT) else font
            cb = _probe_draw.textbbox((0, 0), ch, font=cf)
            total += (cb[2] - cb[0]) + extra_spacing
        return total

    for line_idx, line in enumerate(lines):
        if text_align == "right" and line:
            # Start each line so its right edge meets x0
            cursor_x = max(0, x0 - _measure_line(line))
        else:
            cursor_x = x0
        cursor_y = y0 + line_idx * (char_h + line_gap)

        for char in line:
            # Use punct_font for CJK punctuation when the primary font lacks proper glyphs
            char_font = (punct_font if (punct_font and char in _CJK_PUNCT) else font)

            char_bbox = _probe_draw.textbbox((0, 0), char, font=char_font)
            cw = char_bbox[2] - char_bbox[0]
            ch = char_bbox[3] - char_bbox[1]

            if cw <= 0 or ch <= 0:
                cursor_x += char_w_ref // 3
                continue

            if do_jitter:
                jx = rng.uniform(-jitter_x_px, jitter_x_px)
                jy = rng.uniform(-jitter_y_px, jitter_y_px)
                rot = rng.uniform(-rotation_max, rotation_max)
                alpha_factor = rng.uniform(
                    base_opacity - opacity_var,
                    min(1.0, base_opacity + opacity_var),
                )
            else:
                jx, jy, rot, alpha_factor = 0.0, 0.0, 0.0, base_opacity

            alpha = int(alpha_factor * 255)

            pad = max(int(max(cw, ch) * 0.5), 20)
            layer = Image.new("RGBA", (cw + pad * 2, ch + pad * 2), (0, 0, 0, 0))
            layer_draw = ImageDraw.Draw(layer)
            layer_draw.text(
                (pad - char_bbox[0], pad - char_bbox[1]),
                char,
                font=char_font,
                fill=(*color[:3], alpha),
            )

            if abs(rot) > 0.05:
                layer = layer.rotate(rot, expand=False, resample=Image.BICUBIC)

            paste_x = int(cursor_x - pad + jx)
            paste_y = int(cursor_y - pad + jy)
            image.paste(layer, (paste_x, paste_y), layer)

            spacing_jitter = rng.uniform(-2, 4) if do_jitter else 0
            cursor_x += cw + extra_spacing + spacing_jitter

    return image


# ── Wrap text to fit width — characters are NEVER dropped ────────────────────

def wrap_to_lines(text: str, font, max_width: int,
                  char_extra_px: int = 0) -> list[str]:
    """
    Break text into lines that each fit within max_width.

    Prefers to break AFTER CJK punctuation so phrases stay intact
    (e.g. "他走了，" stays on one line rather than "他走了" / "，...").
    Falls back to mid-phrase character breaking only when no punctuation
    break point is available.

    Post-processing: if the last line has only one character, the final
    character of the previous line is moved to the front of the last line
    to avoid typographic orphans.

    GUARANTEE: every character in the input appears in the output.
               Lines are never truncated. Callers must not drop lines.

    char_extra_px: extra pixels per character added by the renderer
                   (character_spacing_px_extra). Including this ensures the
                   wrap budget matches the actual rendered width.
    """
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    def _measure(s: str) -> int:
        total = 0
        for c in s:
            bbox = probe.textbbox((0, 0), c, font=font)
            total += (bbox[2] - bbox[0]) + char_extra_px
        return total

    result = []

    for para in text.split("\n"):
        if _measure(para) <= max_width:
            result.append(para)
            continue

        current = ""
        last_punct_pos = -1   # index within `current` of last preferred break
        last_space_pos = -1   # index within `current` of last word boundary (English etc.)

        for char in para:
            test = current + char
            if _measure(test) > max_width:
                # Prefer breaking at the most recent word boundary (space) so
                # Latin-script words stay intact (e.g. "lingers" doesn't split
                # into "li" / "ngers"). The space is kept as trailing whitespace
                # on the current line (invisible when rendered) so no character
                # is ever dropped — preserving the wrap guarantee below.
                if last_space_pos >= 0:
                    carry = current[last_space_pos + 1:]
                    result.append(current[:last_space_pos + 1])
                    current = carry + char
                    last_punct_pos = -1
                    last_space_pos = -1
                # Otherwise prefer breaking after the most recent CJK punctuation
                # so the punctuation mark stays with its preceding phrase.
                elif last_punct_pos >= 0 and last_punct_pos < len(current) - 1:
                    carry = current[last_punct_pos + 1:]
                    result.append(current[:last_punct_pos + 1])
                    current = carry + char
                    last_punct_pos = -1
                    last_space_pos = -1
                elif current:
                    result.append(current)
                    current = char      # start new line — never discard char
                    last_punct_pos = -1
                    last_space_pos = -1
                else:
                    result.append(char) # single char wider than max_width
                    current = ""
                    last_punct_pos = -1
                    last_space_pos = -1
            else:
                current = test
                if char == " ":
                    last_space_pos = len(current) - 1
                if char in _PREFER_BREAK_AFTER:
                    last_punct_pos = len(current) - 1

        if current:
            result.append(current)     # always flush remaining — never drop

    # Fix typographic orphan: if the last line has only one character,
    # steal the last character from the previous line to give the last
    # line at least two characters.
    if len(result) >= 2 and len(result[-1]) == 1:
        prev = result[-2]
        if len(prev) > 1:
            result[-2] = prev[:-1]
            result[-1] = prev[-1] + result[-1]

    return result
