"""Builds assets/spicchio.ico from assets/spicchio.png.

The PNG itself is the mark drawn by spicchio/ui/icon.py: `python scripts/render_wheel.py renders`
writes renders/icon.png, copy it to assets/spicchio.png and run this script.
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    png = Image.open(ROOT / "assets" / "spicchio.png").convert("RGBA")
    png.save(ROOT / "assets" / "spicchio.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("assets/spicchio.ico")
