"""
app_main.py

Entry point for Daily Mood.app (PyInstaller target).
Also runnable directly for development: `python app_main.py`

On launch:
  1. Load (or create) user settings
  2. Set up the runtime working directory with bundled config files
  3. If first run → prompt to set API keys before continuing
  4. Start the menu bar app (blocks until Quit)
"""

import os
import sys

# Ensure the project root is on sys.path so `main`, `src`, etc. are importable
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from app.settings import Settings, RUNTIME_DIR
from app.menu_app import DailyMoodApp


def main():
    settings = Settings.load()

    # Seed ~/.config/daily_mood/runtime/ with bundled config files
    settings.setup_runtime_dir()

    # Change to runtime dir so the pipeline finds context.json, weather.json, etc.
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    os.chdir(RUNTIME_DIR)

    # First-run hint (shown before menu bar launches)
    if settings.is_first_run:
        settings.save()  # write defaults so next launch isn't "first run"
        import rumps
        rumps.alert(
            title="Welcome to Daily Mood",
            message=(
                "Before your first run, open the ☀ menu and set your API keys:\n\n"
                "• Set OpenAI Key…  (required)\n"
                "• Set WeatherAPI Key…  (optional — for live weather)\n\n"
                "Then click Run Now to generate today's wallpaper."
            ),
        )

    DailyMoodApp(settings).run()


if __name__ == "__main__":
    main()
