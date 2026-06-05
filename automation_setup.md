# Daily Automation Setup — macOS launchd

Run Daily Mood Screen automatically every morning at 8:00 AM using macOS **launchd**.
The wallpaper is generated, saved, and ready before you open your laptop.

---

## How It Works

```
8:00 AM — launchd wakes the job
  └── run.sh is executed
        ├── loads your API keys from shell profile
        ├── changes to the project directory
        └── runs python main.py
              ├── fetches live weather
              ├── loads today's photos (from Shortcut, if run)
              ├── determines mood
              ├── generates quote via OpenAI
              ├── renders wallpaper
              ├── saves → output/daily_wallpaper_mac.png   (current)
              └── saves → archive/YYYY-MM-DD.png           (archive)
```

---

## Step 1 — Create a Wrapper Shell Script

Create a file called `run.sh` in your project folder:

```bash
#!/bin/zsh

# Load your shell profile so API keys are available
source ~/.zshrc

# Move into the project directory
cd ~/Desktop/daily-mood-screen

# Run the pipeline
python main.py >> logs/daily.log 2>> logs/daily.error.log
```

Make it executable:

```bash
chmod +x ~/Desktop/daily-mood-screen/run.sh
```

Create the logs folder:

```bash
mkdir -p ~/Desktop/daily-mood-screen/logs
```

> The wrapper script is needed because launchd runs in a minimal environment
> and does not load your shell profile or API keys automatically.

---

## Step 2 — Create the plist File

Create this file:

```
~/Library/LaunchAgents/com.dailymoodscreen.morning.plist
```

Contents:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>

    <!-- Unique identifier for this job -->
    <key>Label</key>
    <string>com.dailymoodscreen.morning</string>

    <!-- What to run -->
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>/Users/YOUR_USERNAME/Desktop/daily-mood-screen/run.sh</string>
    </array>

    <!-- Run every day at 8:00 AM -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <!-- Log output -->
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/Desktop/daily-mood-screen/logs/daily.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/Desktop/daily-mood-screen/logs/daily.error.log</string>

    <!-- Do not run immediately when loaded — wait for 8 AM -->
    <key>RunAtLoad</key>
    <false/>

</dict>
</plist>
```

Replace `YOUR_USERNAME` with your actual macOS username.
Find it by running: `whoami`

---

## Step 3 — Load the Job

```bash
launchctl load ~/Library/LaunchAgents/com.dailymoodscreen.morning.plist
```

To verify it is loaded:

```bash
launchctl list | grep dailymoodscreen
```

You should see a line with `com.dailymoodscreen.morning`.

---

## Step 4 — Test It Manually

Run the job right now without waiting for 8 AM:

```bash
launchctl start com.dailymoodscreen.morning
```

Check the log to see what happened:

```bash
cat ~/Desktop/daily-mood-screen/logs/daily.log
cat ~/Desktop/daily-mood-screen/logs/daily.error.log
```

---

## Step 5 — Set the Wallpaper in System Settings

Point macOS to the generated file once — it will always reflect the latest render:

1. Open **System Settings → Wallpaper**
2. Click **Add Folder or Photo…**
3. Select: `~/Desktop/daily-mood-screen/output/daily_wallpaper_mac.png`
4. Set **Auto-rotate** to **Never**

macOS reads the file fresh each time it displays the wallpaper,
so the image updates automatically when `main.py` overwrites it.

---

## Optional — Set Wallpaper Automatically via Script

Add this line to the end of `run.sh` to set the wallpaper programmatically
right after it is generated:

```bash
osascript -e 'tell application "System Events"
    tell every desktop
        set picture to "/Users/YOUR_USERNAME/Desktop/daily-mood-screen/output/daily_wallpaper_mac.png"
    end tell
end tell'
```

---

## Managing the Job

| Task | Command |
|---|---|
| Load (enable) | `launchctl load ~/Library/LaunchAgents/com.dailymoodscreen.morning.plist` |
| Unload (disable) | `launchctl unload ~/Library/LaunchAgents/com.dailymoodscreen.morning.plist` |
| Run now | `launchctl start com.dailymoodscreen.morning` |
| Check status | `launchctl list \| grep dailymoodscreen` |

---

## Output Files

| File | Purpose |
|---|---|
| `output/daily_wallpaper_mac.png` | Current wallpaper — overwritten each day |
| `archive/YYYY-MM-DD.png` | Dated archive — one file per day, never overwritten |
| `logs/daily.log` | Standard output from each run |
| `logs/daily.error.log` | Errors from each run |

---

## Photos and the Daily Shortcut

Run the **Daily Mood Photos** Apple Shortcut (see `photos_shortcuts_setup.md`)
before 8 AM each morning for the best result.

- If the Shortcut was run today → `photos.json` reflects today's photos
- If it was not run → the pipeline uses weather alone for the mood

The system checks the modification date of `photos.json` automatically.
Yesterday's photos are never used for today's wallpaper.
