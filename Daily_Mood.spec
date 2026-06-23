# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for Daily Mood.app
# Build with:  bash build_app.sh
#
# Data files (style_library, JSON configs) are bundled read-only inside the .app.
# The pipeline writes output to user-configured folders (default: ~/Desktop/daily-mood-screen/).
# Runtime working files (context.json copy, weather.json) go to ~/.config/daily_mood/runtime/.

import os

block_cipher = None

# ── Collect all data files the pipeline reads at runtime ─────────────────────
datas = [
    ("style_library",        "style_library"),
    ("context.json",         "."),
    ("wallpaper_style.json", "."),
    ("style_config.json",    "."),
]

# ── Hidden imports PyInstaller might miss ────────────────────────────────────
hidden = [
    # rumps / PyObjC
    "rumps",
    "objc",
    "AppKit",
    "Foundation",
    "Cocoa",
    # PIL
    "PIL._tkinter_finder",
    "PIL.ImageDraw",
    "PIL.ImageFont",
    "PIL.ImageFilter",
    "PIL.ImageChops",
    "PIL.ImageEnhance",
    # network / API
    "openai",
    "openai.resources",
    "openai.resources.chat",
    "requests",
    "httpx",
    "certifi",
    # project modules loaded conditionally in main.py
    "photo_theme_engine",
    "background_generator",
    "background_prompt_builder",
    "visual_engine",
    "src.style_loader",
    "src.style_engine",
    "src.prompt_builder",
    "src.discovery_engine",
    "src.observation_engine",
    "src.sentence_selector",
    "src.typography_engine",
]

a = Analysis(
    ["app_main.py"],
    pathex=[os.path.abspath(".")],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "email", "html", "http", "urllib",
              "xml", "pydoc", "doctest", "argparse", "difflib", "inspect"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Daily Mood",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Daily Mood",
)

app = BUNDLE(
    coll,
    name="Daily Mood.app",
    icon=None,              # replace with "app/icon.icns" when you have one
    bundle_identifier="com.dailymood.app",
    info_plist={
        "NSHighResolutionCapable": True,
        "LSUIElement": True,          # hides from Dock — menu bar only
        "NSAppleEventsUsageDescription": "Daily Mood uses AppleScript for folder selection and API key input.",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1",
        "CFBundleName": "Daily Mood",
    },
)
