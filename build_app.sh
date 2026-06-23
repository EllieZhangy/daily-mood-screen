#!/bin/bash
# build_app.sh — Build Daily Mood.app with PyInstaller
#
# Usage:  bash build_app.sh
#
# Output: dist/Daily Mood.app
# Then drag dist/Daily Mood.app to /Applications.

set -e
cd "$(dirname "$0")"

echo "═══════════════════════════════════════"
echo "  Daily Mood — build"
echo "═══════════════════════════════════════"

# ── 1. Install / upgrade build dependencies ───────────────────────────────────
echo ""
echo "▸ Installing build dependencies..."
pip install --quiet --upgrade pyinstaller rumps

# ── 2. Clean previous build ───────────────────────────────────────────────────
echo "▸ Cleaning previous build..."
rm -rf build dist

# ── 3. Run PyInstaller ────────────────────────────────────────────────────────
echo "▸ Building Daily Mood.app..."
pyinstaller Daily_Mood.spec --noconfirm

# ── 4. Confirm output ─────────────────────────────────────────────────────────
if [ -d "dist/Daily Mood.app" ]; then
    echo ""
    echo "═══════════════════════════════════════"
    echo "  ✓  Built → dist/Daily Mood.app"
    echo "═══════════════════════════════════════"
    echo ""
    echo "Next steps:"
    echo "  1. Drag 'dist/Daily Mood.app' to /Applications"
    echo "  2. Double-click to launch"
    echo "  3. Click ☀ in the menu bar → Set OpenAI Key…"
    echo "  4. Click Run Now"
    echo ""
else
    echo "✗  Build failed — check output above."
    exit 1
fi
