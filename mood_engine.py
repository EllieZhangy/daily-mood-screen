# mood_engine.py
# Converts weather + photo context into a named mood with keyword hints.
# The mood is passed to the AI as creative direction — the AI decides the wording.

# ── Mood rules ────────────────────────────────────────────────────────────────
# Keyed by (weather_category, photo_theme).
# emotion_keywords → shape the feeling of the quote
# visual_keywords  → give the AI concrete imagery to draw from
MOOD_RULES = {
    ("cold",   "friends"):   {
        "mood": "cold_reunion",
        "emotion_keywords": ["nostalgia", "connection", "quiet warmth"],
        "visual_keywords":  ["cold air", "old light", "city evening"],
    },
    ("cold",   "none"):      {
        "mood": "cold_solitude",
        "emotion_keywords": ["stillness", "distance", "isolation"],
        "visual_keywords":  ["frost", "bare branches", "grey sky"],
    },
    ("cold",   "nature"):    {
        "mood": "cold_stillness",
        "emotion_keywords": ["quiet", "peace", "solitude"],
        "visual_keywords":  ["frozen field", "pale light", "silence"],
    },
    ("cold",   "memories"):  {
        "mood": "cold_nostalgia",
        "emotion_keywords": ["nostalgia", "longing", "tenderness"],
        "visual_keywords":  ["winter light", "faded warmth", "time passing"],
    },
    ("cold",   "family"):    {
        "mood": "cold_homecoming",
        "emotion_keywords": ["warmth", "belonging", "shelter"],
        "visual_keywords":  ["indoor light", "familiar faces", "winter outside"],
    },
    ("cold",   "travel"):    {
        "mood": "cold_journey",
        "emotion_keywords": ["distance", "discovery", "solitude"],
        "visual_keywords":  ["frost on windows", "unfamiliar streets", "grey city"],
    },
    ("cold",   "self"):      {
        "mood": "cold_introspection",
        "emotion_keywords": ["introspection", "quiet", "stillness"],
        "visual_keywords":  ["cold window", "grey light", "inner quiet"],
    },
    ("cold",   "food"):      {
        "mood": "cold_comfort",
        "emotion_keywords": ["comfort", "simplicity", "daily warmth"],
        "visual_keywords":  ["steam rising", "warm bowl", "small rituals"],
    },

    ("rainy",  "friends"):   {
        "mood": "rainy_connection",
        "emotion_keywords": ["closeness", "shelter", "warmth"],
        "visual_keywords":  ["rain on glass", "indoor light", "shared space"],
    },
    ("rainy",  "none"):      {
        "mood": "rainy_solitude",
        "emotion_keywords": ["solitude", "quiet", "introspection"],
        "visual_keywords":  ["rain sound", "empty street", "soft grey"],
    },
    ("rainy",  "nature"):    {
        "mood": "rainy_reflection",
        "emotion_keywords": ["calm", "impermanence", "seasons"],
        "visual_keywords":  ["wet leaves", "puddles", "soft mist"],
    },
    ("rainy",  "memories"):  {
        "mood": "rainy_nostalgia",
        "emotion_keywords": ["nostalgia", "longing", "tenderness"],
        "visual_keywords":  ["old rain", "blurred lights", "the past"],
    },
    ("rainy",  "family"):    {
        "mood": "rainy_shelter",
        "emotion_keywords": ["warmth", "belonging", "shelter"],
        "visual_keywords":  ["indoor warmth", "rain outside", "familiar voices"],
    },
    ("rainy",  "travel"):    {
        "mood": "rainy_discovery",
        "emotion_keywords": ["discovery", "movement", "uncertainty"],
        "visual_keywords":  ["unfamiliar rain", "foreign streets", "wet pavement"],
    },
    ("rainy",  "self"):      {
        "mood": "rainy_introspection",
        "emotion_keywords": ["introspection", "solitude", "stillness"],
        "visual_keywords":  ["window in rain", "reflection", "quiet room"],
    },
    ("rainy",  "food"):      {
        "mood": "rainy_comfort",
        "emotion_keywords": ["comfort", "warmth", "small pleasures"],
        "visual_keywords":  ["warm tea", "rain sound", "simple meal"],
    },

    ("cloudy", "friends"):   {
        "mood": "cloudy_reunion",
        "emotion_keywords": ["nostalgia", "connection", "gentle warmth"],
        "visual_keywords":  ["soft light", "familiar faces", "quiet afternoon"],
    },
    ("cloudy", "none"):      {
        "mood": "cloudy_solitude",
        "emotion_keywords": ["solitude", "quiet", "calm"],
        "visual_keywords":  ["diffused light", "grey sky", "stillness"],
    },
    ("cloudy", "nature"):    {
        "mood": "cloudy_calm",
        "emotion_keywords": ["calm", "reflection", "seasons"],
        "visual_keywords":  ["soft clouds", "muted colors", "quiet field"],
    },
    ("cloudy", "memories"):  {
        "mood": "cloudy_nostalgia",
        "emotion_keywords": ["nostalgia", "tenderness", "time"],
        "visual_keywords":  ["old light", "faded scenes", "the past"],
    },
    ("cloudy", "family"):    {
        "mood": "cloudy_warmth",
        "emotion_keywords": ["warmth", "belonging", "togetherness"],
        "visual_keywords":  ["soft light", "indoor warmth", "home"],
    },
    ("cloudy", "travel"):    {
        "mood": "cloudy_movement",
        "emotion_keywords": ["movement", "discovery", "wandering"],
        "visual_keywords":  ["overcast road", "new city", "light drizzle"],
    },
    ("cloudy", "self"):      {
        "mood": "cloudy_reflection",
        "emotion_keywords": ["introspection", "quiet", "solitude"],
        "visual_keywords":  ["grey light", "stillness", "inner space"],
    },
    ("cloudy", "food"):      {
        "mood": "cloudy_comfort",
        "emotion_keywords": ["comfort", "simplicity", "daily ritual"],
        "visual_keywords":  ["warm kitchen", "soft light", "simple meal"],
    },

    ("sunny",  "friends"):   {
        "mood": "sunny_connection",
        "emotion_keywords": ["joy", "connection", "lightness"],
        "visual_keywords":  ["golden light", "laughter", "open space"],
    },
    ("sunny",  "none"):      {
        "mood": "sunny_solitude",
        "emotion_keywords": ["solitude", "calm", "openness"],
        "visual_keywords":  ["bright sky", "stillness", "wide light"],
    },
    ("sunny",  "nature"):    {
        "mood": "calm_reflection",
        "emotion_keywords": ["calm", "seasons", "reflection"],
        "visual_keywords":  ["sunlight through leaves", "open field", "morning light"],
    },
    ("sunny",  "memories"):  {
        "mood": "sunny_nostalgia",
        "emotion_keywords": ["nostalgia", "warmth", "distant time"],
        "visual_keywords":  ["warm afternoon light", "golden haze", "the past"],
    },
    ("sunny",  "family"):    {
        "mood": "sunny_warmth",
        "emotion_keywords": ["warmth", "belonging", "joy"],
        "visual_keywords":  ["sunlit home", "shared light", "lightness"],
    },
    ("sunny",  "travel"):    {
        "mood": "sunny_movement",
        "emotion_keywords": ["movement", "discovery", "freedom"],
        "visual_keywords":  ["open road", "bright sky", "new horizon"],
    },
    ("sunny",  "self"):      {
        "mood": "sunny_stillness",
        "emotion_keywords": ["stillness", "openness", "peace"],
        "visual_keywords":  ["morning light", "quiet self", "clarity"],
    },
    ("sunny",  "food"):      {
        "mood": "sunny_simplicity",
        "emotion_keywords": ["simplicity", "daily life", "warmth"],
        "visual_keywords":  ["morning table", "sunlight", "small joy"],
    },
}

# ── Fallbacks used when the exact combination is not in MOOD_RULES ────────────
WEATHER_FALLBACKS = {
    "cold":   {
        "emotion_keywords": ["stillness", "quiet cold"],
        "visual_keywords":  ["cold air", "pale sky"],
    },
    "rainy":  {
        "emotion_keywords": ["introspection", "quiet"],
        "visual_keywords":  ["rain on glass", "grey light"],
    },
    "cloudy": {
        "emotion_keywords": ["calm", "solitude"],
        "visual_keywords":  ["soft clouds", "diffused light"],
    },
    "sunny":  {
        "emotion_keywords": ["warmth", "openness"],
        "visual_keywords":  ["golden light", "open sky"],
    },
}

THEME_FALLBACKS = {
    "friends":  "reunion",
    "travel":   "movement",
    "family":   "homecoming",
    "self":     "quiet_self",
    "food":     "daily_warmth",
    "nature":   "calm_reflection",
    "memories": "nostalgia",
    "none":     "solitude",
}


# ── Weather categorizer ───────────────────────────────────────────────────────
def categorize_weather(weather: dict) -> str:
    """
    Convert a weather dict into one of four broad categories:
    cold | rainy | sunny | cloudy

    Uses the condition string first, then falls back to temperature.
    """
    condition = weather.get("condition", "").lower()
    temp      = weather.get("temperature", 20)

    # Snow / freezing conditions are always "cold"
    if any(w in condition for w in ["snow", "sleet", "freeze", "frost", "blizzard", "hail"]):
        return "cold"

    # Low temperature overrides the condition label
    if isinstance(temp, (int, float)) and temp < 8:
        return "cold"

    if any(w in condition for w in ["rain", "drizzle", "storm", "shower", "thunder"]):
        return "rainy"

    if any(w in condition for w in ["sun", "clear", "bright", "fair"]):
        return "sunny"

    # cloudy / overcast / fog / mist / haze all map to cloudy
    return "cloudy"


# ── Main function ─────────────────────────────────────────────────────────────
def determine_mood(weather: dict, photos: dict) -> dict:
    """
    Combine weather and photo context into a mood descriptor.

    Returns a dict with:
      mood              — a short name like "cold_reunion" or "rainy_solitude"
      emotion_keywords  — feeling/atmosphere words passed to the AI as hints
      visual_keywords   — concrete imagery words passed to the AI as hints

    The AI uses these hints to shape the quote — it decides the final wording.
    """
    weather_cat = categorize_weather(weather)
    photo_theme = photos.get("theme", "none")

    # Exact match in the rules table
    key = (weather_cat, photo_theme)
    if key in MOOD_RULES:
        rule = MOOD_RULES[key]
        return {
            "mood":             rule["mood"],
            "emotion_keywords": rule["emotion_keywords"],
            "visual_keywords":  rule["visual_keywords"],
        }

    # Fallback: compose from separate weather and theme defaults
    theme_word      = THEME_FALLBACKS.get(photo_theme, "solitude")
    weather_default = WEATHER_FALLBACKS.get(weather_cat, WEATHER_FALLBACKS["cloudy"])

    return {
        "mood":             f"{weather_cat}_{theme_word}",
        "emotion_keywords": weather_default["emotion_keywords"],
        "visual_keywords":  weather_default["visual_keywords"],
    }
