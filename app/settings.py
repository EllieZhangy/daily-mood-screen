"""
app/settings.py

Non-sensitive user preferences stored at ~/.config/daily_mood/settings.json.
API keys are never stored here — they live in the macOS Keychain (app/keychain.py).

Runtime working directory:
  ~/.config/daily_mood/runtime/
  Bundled config files (context.json, wallpaper_style.json, style_config.json)
  are copied here on first launch so the pipeline can read/write freely.
"""

import json
import os
import shutil
import sys

CONFIG_DIR   = os.path.expanduser("~/.config/daily_mood")
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.json")
RUNTIME_DIR  = os.path.join(CONFIG_DIR, "runtime")

_PROJECT_DEFAULT = os.path.expanduser("~/Desktop/daily-mood-screen")


def _default_output() -> str:
    if os.path.isdir(_PROJECT_DEFAULT):
        return os.path.join(_PROJECT_DEFAULT, "output")
    return os.path.expanduser("~/Pictures/Daily Mood")


def _default_archive() -> str:
    if os.path.isdir(_PROJECT_DEFAULT):
        return os.path.join(_PROJECT_DEFAULT, "archive")
    return os.path.expanduser("~/Pictures/Daily Mood/Archive")


class Settings:
    def __init__(self, language: str = "zh-CN",
                 output_folder: str = "", archive_folder: str = "",
                 is_first_run: bool = True):
        self.language       = language
        self.output_folder  = output_folder  or _default_output()
        self.archive_folder = archive_folder or _default_archive()
        self.is_first_run   = is_first_run

    # ── Persistence ───────────────────────────────────────────────────────────

    @classmethod
    def load(cls) -> "Settings":
        if not os.path.exists(SETTINGS_PATH):
            return cls()
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            s = cls(
                language       = data.get("language",       "zh-CN"),
                output_folder  = data.get("output_folder",  ""),
                archive_folder = data.get("archive_folder", ""),
                is_first_run   = False,
            )
            return s
        except Exception:
            return cls()

    def save(self) -> None:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "language":       self.language,
                "output_folder":  self.output_folder,
                "archive_folder": self.archive_folder,
            }, f, indent=2, ensure_ascii=False)

    # ── Runtime directory setup ───────────────────────────────────────────────

    def setup_runtime_dir(self) -> None:
        """
        Create the runtime working directory and seed it with bundled config
        files the pipeline expects to find (context.json, wallpaper_style.json,
        style_config.json).  Existing user-edited copies are never overwritten.
        """
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        data_dir = _bundle_data_dir()
        for fname in ("context.json", "wallpaper_style.json", "style_config.json"):
            dst = os.path.join(RUNTIME_DIR, fname)
            if not os.path.exists(dst):
                src = os.path.join(data_dir, fname)
                if os.path.exists(src):
                    shutil.copy(src, dst)


def _bundle_data_dir() -> str:
    """Return the directory that contains the bundled data files."""
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
