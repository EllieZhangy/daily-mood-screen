"""
Quick test: render one background per mood family + dusk.
Bypasses the full wallpaper pipeline — just exercises visual_engine directly.
"""
import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from visual_engine import make_atmospheric_background

CASES = [
    ("cloudy_solitude",      "cloudy",  "test_cloudy_solitude.png"),
    ("sunny_nostalgia",      "sunny",   "test_sunny_nostalgia.png"),
    ("rainy_introspection",  "rainy",   "test_rainy_introspection.png"),
    ("cold_homecoming",      "cold",    "test_cold_homecoming.png"),
    ("sunny_movement",       "sunny",   "test_sunny_movement.png"),
]

os.makedirs("output", exist_ok=True)

for mood, weather, fname in CASES:
    print(f"Rendering {mood} / {weather} …", end=" ", flush=True)
    img = make_atmospheric_background(mood, weather, 2560, 1600)
    path = os.path.join("output", fname)
    img.save(path)
    print(f"→ {path}")

print("Done.")
