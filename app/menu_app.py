"""
app/menu_app.py

macOS menu bar app built with rumps.
Runs the Daily Mood pipeline silently on launch and on demand.
Settings (language, folders, API keys) are reachable from the menu bar icon.
"""

import os
import subprocess
import sys
import threading
from datetime import datetime

import rumps

from app import keychain
from app.settings import Settings


# ── Native macOS dialog helpers (no tkinter needed) ──────────────────────────

def _osascript(script: str, timeout: int = 60) -> tuple[int, str]:
    r = subprocess.run(["osascript", "-e", script],
                       capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip()

def _ask_secret(prompt: str) -> str | None:
    """Native macOS text dialog with hidden input. Returns text or None if cancelled."""
    code, out = _osascript(
        f'display dialog "{prompt}" default answer "" with hidden answer '
        f'buttons {{"Cancel", "Save"}} default button "Save"'
    )
    if code != 0:
        return None
    for part in out.split(","):
        part = part.strip()
        if part.startswith("text returned:"):
            return part[len("text returned:"):]
    return None

def _ask_folder(prompt: str) -> str | None:
    """Native macOS folder-picker dialog. Returns POSIX path or None if cancelled."""
    code, out = _osascript(f'POSIX path of (choose folder with prompt "{prompt}:")')
    return out.rstrip("/") if code == 0 and out else None

def _notify(subtitle: str, message: str) -> None:
    rumps.notification(title="Daily Mood", subtitle=subtitle, message=message)


# ── Menu bar app ──────────────────────────────────────────────────────────────

class DailyMoodApp(rumps.App):

    def __init__(self, settings: Settings):
        super().__init__("☀", quit_button=None)
        self.settings  = settings
        self._running  = False

        # Keep named references so we can update titles later
        self._run_item  = rumps.MenuItem("Run Now",   callback=self.on_run_now)
        self._last_item = rumps.MenuItem("Last run: —")

        # Language submenu
        self._zh_item = rumps.MenuItem("中文 (Simplified Chinese)", callback=self.set_zh)
        self._en_item = rumps.MenuItem("English",                   callback=self.set_en)
        lang_menu = rumps.MenuItem("Language")
        lang_menu.update([self._zh_item, self._en_item])

        self.menu = [
            self._run_item,
            None,
            lang_menu,
            None,
            rumps.MenuItem("Set OpenAI Key…",    callback=self.on_set_openai),
            rumps.MenuItem("Set WeatherAPI Key…", callback=self.on_set_weatherapi),
            None,
            rumps.MenuItem("Output Folder…",  callback=self.on_output_folder),
            rumps.MenuItem("Archive Folder…", callback=self.on_archive_folder),
            None,
            self._last_item,
            None,
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]
        self._refresh_lang_checkmarks()

    # ── Language ──────────────────────────────────────────────────────────────

    def _refresh_lang_checkmarks(self):
        is_zh = self.settings.language == "zh-CN"
        self._zh_item.title = ("✓ 中文 (Simplified Chinese)" if is_zh
                                else "  中文 (Simplified Chinese)")
        self._en_item.title = ("✓ English" if not is_zh else "  English")

    def set_zh(self, _):
        self.settings.language = "zh-CN"
        self.settings.save()
        self._refresh_lang_checkmarks()

    def set_en(self, _):
        self.settings.language = "en-US"
        self.settings.save()
        self._refresh_lang_checkmarks()

    # ── API keys ──────────────────────────────────────────────────────────────

    def on_set_openai(self, _):
        key = _ask_secret("Enter your OpenAI API key:")
        if key is not None:
            keychain.set_key(keychain.OPENAI_SERVICE, key.strip())

    def on_set_weatherapi(self, _):
        key = _ask_secret("Enter your WeatherAPI key (optional):")
        if key is not None:
            keychain.set_key(keychain.WEATHERAPI_SERVICE, key.strip())

    # ── Folder pickers ────────────────────────────────────────────────────────

    def on_output_folder(self, _):
        folder = _ask_folder("Choose the folder for today's wallpaper")
        if folder:
            self.settings.output_folder = folder
            self.settings.save()

    def on_archive_folder(self, _):
        folder = _ask_folder("Choose the archive folder for past wallpapers")
        if folder:
            self.settings.archive_folder = folder
            self.settings.save()

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def on_run_now(self, _):
        if self._running:
            rumps.alert("Already running — please wait.")
            return
        threading.Thread(target=self._run_pipeline, daemon=True).start()

    def _run_pipeline(self):
        self._running = True
        self._run_item.title = "Running…"
        try:
            openai_key  = keychain.get_key(keychain.OPENAI_SERVICE)
            weather_key = keychain.get_key(keychain.WEATHERAPI_SERVICE) or ""

            if not openai_key:
                _notify("Setup needed",
                        "Open Daily Mood → Set OpenAI Key… to get started.")
                return

            os.environ["OPENAI_API_KEY"] = openai_key
            os.environ["WEATHERAPI_KEY"] = weather_key

            # run_with_settings is added to main.py
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)

            from main import run_with_settings
            quote = run_with_settings(
                language    = self.settings.language,
                output_dir  = self.settings.output_folder,
                archive_dir = self.settings.archive_folder,
            )

            now_str = datetime.now().strftime("%H:%M")
            self._last_item.title = f"Last run: {now_str}"
            _notify("Wallpaper updated ✓", (quote or "")[:100])

        except Exception as exc:
            _notify("Error", str(exc)[:120])
        finally:
            self._running = False
            self._run_item.title = "Run Now"
