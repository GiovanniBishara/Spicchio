"""Draws the app icon and the README illustration with Pillow (no Qt needed).

    python scripts/make_assets.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spicchio.geometry import label_point, slices  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INK = (18, 17, 24)
ORANGE = (255, 90, 31)
VIOLET = (108, 60, 255)
S = 3  # supersampling


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", "arialbd.ttf" if bold else "arial.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


def icon() -> None:
    big = Image.new("RGBA", (256 * S, 256 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle((8 * S, 8 * S, 248 * S, 248 * S), radius=60 * S, fill=INK)
    for cy, col in ((86, VIOLET), (170, ORANGE)):
        d.ellipse(((128 - 34) * S, (cy - 34) * S, (128 + 34) * S, (cy + 34) * S), fill=col)
    img = big.resize((256, 256), Image.Resampling.LANCZOS)
    (ROOT / "assets").mkdir(exist_ok=True)
    img.save(ROOT / "assets" / "spicchio.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
    img.save(ROOT / "assets" / "spicchio.png")


def sector(d: ImageDraw.ImageDraw, c, r_in, r_out, start, sweep, fill) -> None:
    """Clockwise degrees from 12 o'clock, drawn as a polygon."""
    pts = []
    steps = max(8, int(sweep))
    for i in range(steps + 1):
        a = math.radians(start + sweep * i / steps)
        pts.append((c[0] + r_out * math.sin(a), c[1] - r_out * math.cos(a)))
    for i in range(steps, -1, -1):
        a = math.radians(start + sweep * i / steps)
        pts.append((c[0] + r_in * math.sin(a), c[1] - r_in * math.cos(a)))
    d.polygon(pts, fill=fill)


def illustration() -> None:
    W, H = 1280, 640
    img = Image.new("RGB", (W * S, H * S), (244, 243, 247))
    d = ImageDraw.Draw(img)
    # a desktop-ish background: a folder window on the left
    d.rounded_rectangle((70 * S, 120 * S, 520 * S, 540 * S), radius=22 * S, fill=(255, 255, 255),
                        outline=(226, 224, 232), width=2 * S)
    d.text((100 * S, 150 * S), "Documents", font=font(22 * S), fill=INK)
    files = [("invoice.png", ORANGE), ("contract.pdf", (225, 72, 77)),
             ("holiday.mov", VIOLET), ("guests.csv", (30, 150, 90))]
    for i, (name, col) in enumerate(files):
        y = 210 + i * 76
        d.rounded_rectangle((100 * S, y * S, 146 * S, (y + 56) * S), radius=8 * S, fill=col)
        d.text((166 * S, (y + 14) * S), name, font=font(20 * S, False), fill=(60, 58, 70))

    # the wheel
    c = (880 * S, 330 * S)
    labels = ["PDF", "JPG", "WebP", "Compress", "Half size", "No metadata", "ZIP", "SHA-256"]
    shadow = Image.new("L", img.size, 0)
    ImageDraw.Draw(shadow).ellipse((c[0] - 175 * S, c[1] - 160 * S, c[0] + 175 * S, c[1] + 190 * S), fill=90)
    shadow = shadow.filter(ImageFilter.GaussianBlur(30 * S))
    img.paste((180, 176, 190), mask=shadow)
    d = ImageDraw.Draw(img)
    inner, outer = 52 * S, 165 * S
    for s in slices(len(labels)):
        hovered = s.index == 0
        sector(d, c, inner, outer + (9 * S if hovered else 0), s.start + 0.8, s.sweep - 1.6,
               ORANGE if hovered else INK)
        dx, dy = label_point(s, (inner + outer) / 2)
        d.text((c[0] + dx, c[1] + dy), labels[s.index], font=font(13 * S), fill=INK if hovered else (255, 255, 255),
               anchor="mm")
    d.ellipse((c[0] - 46 * S, c[1] - 46 * S, c[0] + 46 * S, c[1] + 46 * S), fill=(38, 35, 46))
    d.ellipse((c[0] - 7 * S, c[1] - 17 * S, c[0] + 7 * S, c[1] - 3 * S), fill=VIOLET)
    d.ellipse((c[0] - 7 * S, c[1] + 3 * S, c[0] + 7 * S, c[1] + 17 * S), fill=ORANGE)

    # the dragged file and the cursor, over the PDF slice
    fx, fy = 866 * S, 146 * S
    d.rounded_rectangle((fx, fy, fx + 46 * S, fy + 56 * S), radius=8 * S, fill=ORANGE,
                        outline=(255, 255, 255), width=3 * S)
    cur = [(0, 0), (0, 34), (9, 26), (15, 40), (21, 37), (15, 24), (27, 24)]
    ox, oy = fx + 30 * S, fy + 30 * S
    d.polygon([(ox + x * S, oy + y * S) for x, y in cur], fill=(255, 255, 255), outline=INK)
    # the Shift key
    d.rounded_rectangle((1080 * S, 470 * S, 1210 * S, 530 * S), radius=12 * S, fill=(255, 255, 255),
                        outline=(206, 203, 214), width=3 * S)
    d.text((1145 * S, 500 * S), "⇧ Shift", font=font(20 * S), fill=INK, anchor="mm")
    (ROOT / "docs").mkdir(exist_ok=True)
    img.resize((W, H), Image.Resampling.LANCZOS).save(ROOT / "docs" / "wheel.png", optimize=True)


if __name__ == "__main__":
    icon()
    illustration()
    print("assets/spicchio.ico, assets/spicchio.png, docs/wheel.png")
