# Daily Mood Screen

Generate a daily poetic quote based on weather and photo context, then render it into a wallpaper image.

## Project Status

MVP skeleton — placeholder quotes only, no API calls, no image generation yet.

## File Overview

| File | Purpose |
|---|---|
| `context.json` | Input data: language, weather, photos, and future fields |
| `quote_generator.py` | Loads context and prints a quote |
| `requirements.txt` | Python dependencies (none yet) |

## Requirements

- Python 3.11+
- No external packages required at this stage

## How to Run

```bash
python quote_generator.py
```

To use a different context file:

```bash
python quote_generator.py my_context.json
```

## Supported Languages

| Code | Language |
|---|---|
| `zh-CN` | Chinese (Simplified) |
| `en-US` | English (United States) |

## context.json Fields

```json
{
  "language": "zh-CN",        // quote language
  "weather": {
    "condition": "cloudy",    // cloudy | sunny | rainy | snowy
    "temperature": 12         // degrees Celsius
  },
  "photos": {
    "has_recent_photos": true,
    "has_people": true,
    "theme": "friends"
  },
  "memory": {},               // reserved for future use
  "fitness": {},              // reserved for future use
  "calendar": {}              // reserved for future use
}
```

## Roadmap

- [ ] Connect to Claude API to generate real poetic quotes
- [ ] Use weather + photo context to personalise quotes
- [ ] Render quote onto a wallpaper image
- [ ] Schedule daily generation
