# Daily Mood Screen

A personal daily wallpaper generator for macOS. Every morning it reads your live local weather (including location), today's photos, and your mood — then generates a short poetic quote with AI and renders it over an AI-generated background, saving the result as your desktop wallpaper. Currently supports English and Chinese.

<img
  src="https://github.com/user-attachments/assets/3953efd7-f27c-4388-930c-75a4861d310c"
  alt="Example Wallpaper"
  width="500"
/>

---

## How It Works

```
8:00 AM — Daily Mood.app (or launchd) triggers the pipeline
  │
  ├─ Fetch live weather (WeatherAPI) ────── location + condition + temperature
  ├─ Load today's photos (Apple Shortcut) ─ saves real images to recent_photos/
  ├─ Classify photo theme ────────────────── vision AI reads recent_photos/ → theme
  ├─ Determine mood ──────────────────────── weather × photo theme → 32 moods
  ├─ Generate background ─────────────────── DALL-E 3 (or gradient fallback)
  ├─ Generate quote ──────────────────────── GPT-4.1-mini guided by mood + style library
  ├─ Render wallpaper ────────────────────── PIL: quote + metadata over background
  ├─ Save → output/daily_wallpaper_mac.png  (macOS reads this live)
  └─ Archive → archive/YYYY-MM-DD.png
```

---

## Option A — Daily Mood.app (Recommended)

A double-clickable macOS menu bar app. No terminal needed.

### Build

```bash
bash build_app.sh
```

This installs PyInstaller + rumps and produces `dist/Daily Mood.app`. Drag it to `/Applications`.

### First launch

1. Double-click **Daily Mood.app** — a ☀ icon appears in your menu bar
2. A welcome dialog explains setup
3. Click **☀ → Set OpenAI Key…** — enter your key (stored in macOS Keychain, never in a file)
4. Click **☀ → Set WeatherAPI Key…** — optional, for live weather
5. Click **☀ → Run Now** — generates today's wallpaper

### Menu bar options

| Item | What it does |
|---|---|
| **Run Now** | Generate today's wallpaper immediately |
| **Language** | Switch between 中文 and English |
| **Set OpenAI Key…** | Store key in macOS Keychain |
| **Set WeatherAPI Key…** | Store key in macOS Keychain |
| **Output Folder…** | Choose where `daily_wallpaper_mac.png` is saved |
| **Archive Folder…** | Choose where dated archive copies are saved |
| **Last run:** | Timestamp of the most recent successful run |

### Settings are saved to

- `~/.config/daily_mood/settings.json` — language and folder choices
- macOS Keychain — API keys (use **Keychain Access.app** to inspect)
- `~/.config/daily_mood/runtime/` — working files (context, weather, photos)

---

## Option B — Command Line

### Prerequisites

- macOS (PingFang SC / STHeiti fonts required for Chinese)
- Python 3.11+
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or any venv manager
- API keys: `OPENAI_API_KEY` and `WEATHERAPI_KEY`

### Setup

```bash
git clone https://github.com/EllieZhangy/daily-mood-screen.git
cd daily-mood-screen
pip install -r requirements.txt
```

Add API keys to `~/.zshrc`:

```bash
export OPENAI_API_KEY=sk-...
export WEATHERAPI_KEY=your-key-here
source ~/.zshrc
```

Create `city.txt` with your city:

```
Los Angeles
```

Run:

```bash
python main.py
```

### Set as wallpaper

1. **System Settings → Wallpaper → Add Folder or Photo…**
2. Select `~/Desktop/daily-mood-screen/output/daily_wallpaper_mac.png`
3. Set **Auto-rotate** to **Never**

macOS re-reads the file on each display refresh, so it updates automatically.

---

## Option C — Automated with launchd

Runs `main.py` every morning at 8:00 AM without opening any app.

### Step 1 — Shell wrapper

```bash
#!/bin/zsh
source ~/.zshrc
cd ~/Desktop/daily-mood-screen
python main.py >> logs/daily.log 2>> logs/daily.error.log
```

Save as `run.sh`, then:

```bash
chmod +x ~/Desktop/daily-mood-screen/run.sh
mkdir -p ~/Desktop/daily-mood-screen/logs
```

### Step 2 — launchd plist

Save to `~/Library/LaunchAgents/com.dailymoodscreen.morning.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dailymoodscreen.morning</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>/Users/YOUR_USERNAME/Desktop/daily-mood-screen/run_daily.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>8</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/Desktop/daily-mood-screen/logs/daily.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/Desktop/daily-mood-screen/logs/daily.error.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
```

Replace `YOUR_USERNAME` with `whoami`.

### Step 3 — Load and test

```bash
launchctl load ~/Library/LaunchAgents/com.dailymoodscreen.morning.plist
launchctl start com.dailymoodscreen.morning   # run now without waiting for 8 AM
```

| Task | Command |
|---|---|
| Enable | `launchctl load …/com.dailymoodscreen.morning.plist` |
| Disable | `launchctl unload …/com.dailymoodscreen.morning.plist` |
| Run now | `launchctl start com.dailymoodscreen.morning` |
| Status | `launchctl list \| grep dailymoodscreen` |

---

## Apple Shortcut — Daily Mood Photos

Run each morning before the pipeline fires. The shortcut exports real photos so the vision AI can classify the theme automatically — no manual selection.

### What it produces

- `recent_photos/*.jpg` — up to 5 of today's newest photos
- `photos.json` — count and presence flag (theme is determined by the vision AI)

### Shortcut actions (summary)

| Step | Action | Key setting |
|---|---|---|
| 1 | Find Photos | Last 1 day · Newest first |
| 2 | Count | → magic variable **Count** |
| 3 | If / Otherwise | Count > 0 → `has_photos = true` |
| 4 | Run Shell Script | `rm -rf ~/Desktop/daily-mood-screen/recent_photos` then `mkdir -p …` |
| 5 | Get First Items | First **5** from Step 1 |
| 6 | Repeat with each | Convert to JPEG → `cat > …/recent_photos/photo_$(date +%s%3N).jpg` (stdin) |
| 7 | Text | Build `photos.json` with `has_recent_photos` and `photo_count` |
| 8 | Run Shell Script | `cat > ~/Desktop/daily-mood-screen/photos.json` (stdin) |
| 9 | Run Shell Script | *(Optional)* `source ~/.zshrc && cd ~/Desktop/daily-mood-screen && python main.py` |

Full step-by-step instructions: **`photos_shortcuts_setup.md`**

---

## Configuration

### `context.json` — base context

```json
{
  "language": "zh-CN",
  "weather": { "condition": "cloudy", "temperature": 12 },
  "photos":  { "has_recent_photos": false, "photo_count": 0 },
  "style": {
    "tone":  ["literary", "atmospheric", "calm", "emotional"],
    "avoid": ["motivational quotes", "generic inspiration", "cheesy expressions"]
  }
}
```

| Field | Values |
|---|---|
| `language` | `zh-CN` · `en-US` |
| `weather.condition` | `sunny` · `cloudy` · `rainy` · `snowy` · `cold` |

### `style_config.json` — style engine

```json
{
  "language":           "zh",
  "writing_style":      "gentle",
  "visual_style":       "daily_mood",
  "use_ai_background":  true
}
```

| Field | Description |
|---|---|
| `use_ai_background` | `true` → DALL-E 3 · `false` → gradient fallback (no API cost) |
| `visual_style` | `daily_mood` auto-selects warm/cool/night/dusk/earth by mood |

---

## Project Structure

```
daily-mood-screen/
├── main.py                    # CLI entry point + run_with_settings() for the app
├── app_main.py                # Daily Mood.app entry point
├── app/
│   ├── keychain.py            # macOS Keychain read/write
│   ├── settings.py            # User preferences (~/.config/daily_mood/)
│   └── menu_app.py            # rumps menu bar app
├── Daily_Mood.spec            # PyInstaller bundle spec
├── build_app.sh               # One-command build → dist/Daily Mood.app
│
├── quote_generator.py         # AI quote generation (GPT-4.1-mini)
├── background_generator.py    # AI background generation (DALL-E 3)
├── wallpaper_renderer.py      # PIL rendering — text layout over background
├── mood_engine.py             # 32 moods from weather × photo theme matrix
├── weather_fetcher.py         # Live weather via WeatherAPI
├── photo_theme_engine.py      # Vision classification of recent_photos/
├── visual_engine.py           # Atmospheric gradient fallback backgrounds
│
├── src/
│   ├── style_engine.py        # Combines author + theme + preset signals
│   ├── prompt_builder.py      # Builds the quote generation prompt
│   ├── sentence_selector.py   # Picks reference sentences by scenario tags
│   ├── style_library.py       # Loads visual/writing presets
│   └── typography_engine.py   # Handwritten-note font rendering
│
├── style_library/
│   ├── writing/
│   │   ├── reference_zh.txt   # Chinese reference sentence examples
│   │   ├── reference_en.txt   # English reference sentence examples
│   │   ├── presets/           # Writing preset JSONs (zh_gentle, zh_rainy …)
│   │   ├── authors/           # Author style JSONs (mu_xin, murakami …)
│   │   └── themes/            # Theme JSONs (zh_solitude, zh_homecoming …)
│   └── visual/
│       ├── daily_mood_warm.json
│       ├── daily_mood_cool.json
│       ├── daily_mood_night.json
│       ├── daily_mood_dusk.json
│       └── daily_mood_earth.json
│
├── context.json               # Base input (language, weather fallback, style)
├── style_config.json          # Style engine selection
├── wallpaper_style.json       # Font, layout, theme defaults
├── run_daily.sh               # Shell wrapper for launchd
└── requirements.txt
```

---

## Output Files

| File | Purpose |
|---|---|
| `output/daily_wallpaper_mac.png` | Current wallpaper — overwritten each morning |
| `archive/YYYY-MM-DD.png` | Dated archive — one file per day |
| `logs/daily.log` | Standard output from each run |
| `logs/daily.error.log` | Errors from each run |

---

## Language Support

| Code | Language | Notes |
|---|---|---|
| `zh-CN` | Chinese (Simplified) | Default · PingFang SC font · literary style |
| `en-US` | English | Direct, personal tone · reference sentences from `reference_en.txt` |

Set via the app's Language menu, or in `context.json → language` for CLI use.
