# Apple Shortcuts Setup — Daily Mood Photos

Use **Apple Shortcuts** on macOS to export today's photos for AI theme classification.
The shortcut clears and refills `recent_photos/`, then writes `photos.json`.
`main.py` reads the actual image files with a vision model to classify the theme automatically — no manual selection needed.

---

## What the Shortcut Produces

**`recent_photos/`** — up to 5 of today's newest photos as JPEG files:
```
recent_photos/
  photo_1750000000000.jpg
  photo_1750000000123.jpg
  ...
```

**`photos.json`** — count and presence flag only (no theme — the vision AI decides):
```json
{
  "has_recent_photos": true,
  "photo_count": 6
}
```

---

## Prerequisites

- macOS 12 Monterey or later
- Shortcuts app → Settings → Advanced → **Allow Running Scripts** enabled
- Daily Mood Screen project at `~/Desktop/daily-mood-screen/`

---

## Build the Shortcut

Open **Shortcuts → New Shortcut**. Name it **Daily Mood Photos**.
Add the following actions in order.

---

### Action 1 — Find Recent Photos

**Action name:** `Find Photos`

| Setting | Value |
|---|---|
| Filter | Date is in the last **1** Days |
| Sort by | Date Added — Newest First |
| Limit | off |

> Change `1 Days` to `3 Days` if you photograph less frequently.

---

### Action 2 — Count the Photos

**Action name:** `Count`

- Input: Photos result from Action 1

> Shortcuts saves this as the magic variable **Count**.

---

### Action 3 — Set has\_recent\_photos

**Action name:** `If`

| Setting | Value |
|---|---|
| Input | Count (from Action 2) |
| Condition | is greater than 0 |

Inside **If**:
- `Set Variable` → Name: `has_photos` → Value: `true`

Inside **Otherwise**:
- `Set Variable` → Name: `has_photos` → Value: `false`

**Action:** `End If`

---

### Action 4 — Clear and recreate recent\_photos/

**Action name:** `Run Shell Script`

| Setting | Value |
|---|---|
| Shell | /bin/zsh |
| Pass input as | (none) |

Script:
```bash
rm -rf ~/Desktop/daily-mood-screen/recent_photos
mkdir -p ~/Desktop/daily-mood-screen/recent_photos
```

> This ensures only today's photos are ever in the folder — yesterday's are wiped first.

---

### Action 5 — Limit to 5 newest photos

**Action name:** `Get First Items`

| Setting | Value |
|---|---|
| Input | Photos result from Action 1 |
| Get | First **5** Items |

> 5 is enough for reliable vision classification and keeps the API call fast.

---

### Action 6 — Save each photo to recent\_photos/

**Action name:** `Repeat with each item in` [First Items from Action 5]

Inside the repeat loop, add two actions:

#### 6a — Convert to JPEG

**Action name:** `Convert Image`

| Setting | Value |
|---|---|
| Input | Repeat Item |
| Format | JPEG |
| Quality | Best |

#### 6b — Write the file

**Action name:** `Run Shell Script`

| Setting | Value |
|---|---|
| Shell | /bin/zsh |
| Input | Converted Image from Action 6a |
| Pass input as | **stdin** |

Script:
```bash
cat > ~/Desktop/daily-mood-screen/recent_photos/photo_$(date +%s%3N).jpg
```

> `%s%3N` appends milliseconds to the timestamp so each filename is unique even when photos are saved back-to-back.

**Action:** `End Repeat`

---

### Action 7 — Build photos.json

**Action name:** `Text`

Type the JSON below, replacing bracketed parts with variables using the variable picker (`{x}`):

```
{
  "has_recent_photos": [has_photos],
  "photo_count": [Count]
}
```

- `[has_photos]` → Variable: **has_photos** (from Action 3)
- `[Count]`      → Magic variable: **Count** (from Action 2)

---

### Action 8 — Write photos.json

**Action name:** `Run Shell Script`

| Setting | Value |
|---|---|
| Shell | /bin/zsh |
| Input | Text from Action 7 |
| Pass input as | stdin |

Script:
```bash
cat > ~/Desktop/daily-mood-screen/photos.json
```

---

### Action 9 — Run the pipeline (Optional)

**Action name:** `Run Shell Script`

| Setting | Value |
|---|---|
| Shell | /bin/zsh |
| Pass input as | (none) |

Script:
```bash
source ~/.zshrc
cd ~/Desktop/daily-mood-screen
python main.py
```

> Requires `OPENAI_API_KEY` and `WEATHERAPI_KEY` in your shell profile.

---

## How to Run the Shortcut

**From Spotlight:** `Cmd + Space` → type **Daily Mood Photos** → Enter

**From menu bar:**
1. Shortcuts → Settings → Advanced → Enable "Allow Running Scripts"
2. Right-click the shortcut → Add to Menu Bar

**Best time to run:** before 8 AM so the launchd job has fresh photos when it fires.

---

## How the Full Pipeline Uses It

```
Shortcut runs
  ├─ Clears recent_photos/
  ├─ Saves up to 5 today's photos → recent_photos/*.jpg
  └─ Writes photos.json  { has_recent_photos, photo_count }

main.py runs (8 AM or manual)
  ├─ load_photos()              reads photos.json (staleness-checked: today only)
  ├─ classify_theme_from_photos()
  │     ├─ reads recent_photos/*.jpg (newest 5)
  │     ├─ downsizes via sips
  │     └─ asks vision model → theme  (friends / nature / food / travel / …)
  │   fallback: infer_theme()  (count + time of day + weather heuristic)
  ├─ determine_mood()           weather × theme → one of 32 moods
  ├─ generate_quote()           mood shapes the AI prompt
  └─ render_wallpaper()         theme shown in metadata line
```

---

## photos.json Examples

**Active day with photos:**
```json
{
  "has_recent_photos": true,
  "photo_count": 8
}
```

**Quiet day — no photos taken:**
```json
{
  "has_recent_photos": false,
  "photo_count": 0
}
```

> No `theme` field is needed. The vision classifier in `photo_theme_engine.py` reads
> the actual image files and returns one of:
> `friends` · `nature` · `food` · `travel` · `family` · `self` · `memories` · `study` · `none`
>
> If `recent_photos/` is empty or the vision call fails, a local heuristic
> (`infer_theme`) guesses from photo count, time of day, and weather.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Photos not appearing in `recent_photos/` | Confirm "Allow Running Scripts" is on in Shortcuts → Settings → Advanced |
| `photos.json` shows `"has_recent_photos": false` despite taking photos | The shortcut looks back only 1 day — change Action 1 filter to 3 Days |
| Vision classification always returns `none` | Check `OPENAI_API_KEY` is set; check `recent_photos/` actually contains `.jpg` files |
| Filenames collide | The `%s%3N` timestamp has ms precision — collision would require saving >1000 photos/second |
