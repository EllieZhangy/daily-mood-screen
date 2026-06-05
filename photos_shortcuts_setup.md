# Apple Shortcuts Setup — Daily Mood Photos

Use **Apple Shortcuts** on macOS to count recent photos and pick a theme.
The shortcut writes `photos.json` directly, which `main.py` reads automatically.

No face recognition. No image classification. Just a count and a category you choose.

---

## What the Shortcut Produces

```json
{
  "has_recent_photos": true,
  "photo_count": 6,
  "theme": "friends"
}
```

---

## Prerequisites

- macOS 12 Monterey or later
- Shortcuts app (pre-installed)
- Daily Mood Screen project saved somewhere on your Mac
- Photos app with your photos library

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

> Pulls every photo added or taken in the last 24 hours.
> Change `1 Days` to `3 Days` if you photograph less frequently.

---

### Action 2 — Count the Photos

**Action name:** `Count`

- Input: the Photos result from Action 1

> Shortcuts saves the result as the magic variable **Count**.

---

### Action 3 — Set has_recent_photos

**Action name:** `If`

| Setting | Value |
|---|---|
| Input | Count (magic variable from Action 2) |
| Condition | is greater than 0 |

Inside **If**:
- **Action:** `Set Variable`
  - Name: `has_photos`
  - Value: `true`

Inside **Otherwise**:
- **Action:** `Set Variable`
  - Name: `has_photos`
  - Value: `false`

**Action:** `End If`

---

### Action 4 — Choose a Theme

**Action name:** `Choose from List`

| Setting | Value |
|---|---|
| Prompt | What's the theme of your recent photos? |
| Select Multiple | off |

List items (add one per line):
```
friends
travel
family
self
food
nature
memories
none
```

> The item you tap becomes the magic variable **Chosen Item**.

---

### Action 5 — Build the JSON

**Action name:** `Text`

Type this into the text field, then replace each bracketed part
with the matching Shortcuts variable using the variable picker (`{x}`):

```
{
  "has_recent_photos": [has_photos],
  "photo_count": [Count],
  "theme": "[Chosen Item]"
}
```

- `[has_photos]`   → Variable: **has_photos** (from Action 3)
- `[Count]`        → Magic variable: **Count** (from Action 2)
- `[Chosen Item]`  → Magic variable: **Chosen Item** (from Action 4)

The result looks like:

```json
{
  "has_recent_photos": true,
  "photo_count": 6,
  "theme": "friends"
}
```

---

### Action 6 — Write photos.json

**Action name:** `Run Shell Script`

| Setting | Value |
|---|---|
| Shell | /bin/zsh |
| Input | Text from Action 5 |
| Pass input as | stdin |

Script:
```bash
cat > ~/Desktop/daily-mood-screen/photos.json
```

> Adjust the path if your project folder is not on the Desktop.
> Example for a different location:
> `cat > ~/Projects/daily-mood-screen/photos.json`

---

### Action 7 — Run the Pipeline (Optional)

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

> This runs the full pipeline right after the theme is chosen.
> Requires `OPENAI_API_KEY` and `WEATHERAPI_KEY` to be set in your shell profile.

---

## How to Run the Shortcut

**From Shortcuts app:** click ▶ Run

**From menu bar:**
1. Open Shortcuts → Settings → Advanced
2. Enable "Allow Running Scripts"
3. Right-click the shortcut → Add to Menu Bar

**From Spotlight:**
- Press `Cmd + Space`, type `Daily Mood Photos`, press Enter

**On a schedule (optional):**
- Use the macOS Automator app with a Calendar alarm
- Or add a cron job: `0 8 * * * shortcuts run "Daily Mood Photos"`

---

## How photos.json Is Generated

```
Shortcuts app
  │
  ├─ Find Photos (last 24h)  →  photo_count
  ├─ If count > 0            →  has_photos = true / false
  ├─ Choose from List        →  theme
  ├─ Text (build JSON)       →  JSON string
  └─ Run Shell Script        →  writes photos.json
```

---

## How main.py Uses It Automatically

```
python main.py
  │
  ├─ load_photos()        reads photos.json
  ├─ resolve_photos()     uses photos.json (falls back to context.json if missing)
  ├─ determine_mood()     theme shapes the mood direction
  ├─ generate_quote()     mood influences the OpenAI prompt
  └─ render_wallpaper()   theme appears in the metadata line
```

No changes to `main.py` needed — it already reads `photos.json` on every run.

---

## Supported Themes

| Theme | Mood direction |
|---|---|
| `friends` | nostalgia, connection, reunion |
| `travel` | movement, discovery, distance |
| `family` | warmth, belonging, roots |
| `self` | introspection, stillness, solitude |
| `food` | daily life, simplicity, warmth |
| `nature` | calm, seasons, reflection |
| `memories` | tenderness, time, nostalgia |
| `none` | quiet moments, solitude |

---

## Example photos.json Files

**Friends gathering**
```json
{
  "has_recent_photos": true,
  "photo_count": 12,
  "theme": "friends"
}
```

**Travel day**
```json
{
  "has_recent_photos": true,
  "photo_count": 34,
  "theme": "travel"
}
```

**Nature walk**
```json
{
  "has_recent_photos": true,
  "photo_count": 8,
  "theme": "nature"
}
```

**Quiet day — no photos taken**
```json
{
  "has_recent_photos": false,
  "photo_count": 0,
  "theme": "none"
}
```

---

## Changing Your Location

To change the look-back window from 1 day to 3 days,
edit Action 1: `Date is in the last` → change `1` to `3`.

To add a new theme, add a new line to the list in Action 4,
then add a matching entry to `THEME_MOODS` in `mood_engine.py`.
