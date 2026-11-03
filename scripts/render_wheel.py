"""Renders the wheel, the notification and the icon to PNG files, to review the design
without a Windows PC (CI publishes them on the `renders` branch).

    python scripts/render_wheel.py out_dir
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform == "win32":  # the offscreen platform does not find system fonts by itself
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from spicchio.ui.icon import paint_mark  # noqa: E402
from spicchio.ui.toast import Toast  # noqa: E402
from spicchio.ui.wheel import Wheel  # noqa: E402

BACKGROUNDS = (("light", QColor(238, 237, 240)), ("dark", QColor(36, 39, 46)))


def on_backgrounds(shot: QImage, out: Path, name: str) -> None:
    for bg_name, bg in BACKGROUNDS:
        canvas = QImage(shot.size(), QImage.Format.Format_ARGB32)
        canvas.fill(bg)
        p = QPainter(canvas)
        p.drawImage(0, 0, shot)
        p.end()
        canvas.save(str(out / f"{name}-{bg_name}.png"))


def main(out: Path) -> None:
    app = QApplication.instance() or QApplication([])  # noqa: F841
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    photo = tmp / "holiday-photo.png"
    Image.new("RGB", (8, 8), (200, 120, 40)).save(photo)
    pdf = tmp / "contract.pdf"
    Image.new("RGB", (8, 8)).save(pdf, "PDF")

    states = [
        ("empty", [], None, False),
        ("image-choose", [photo], None, False),
        ("image-pdf", [photo], 0, False),
        ("image-compress", [photo], 4, False),
        ("pdf-split", [pdf], 2, False),
        ("image-busy", [photo], 0, True),
    ]
    for name, files, hover, busy in states:
        w = Wheel()
        w.set_files(files)
        w.set_hover(hover)
        w.busy = busy
        w.freeze()
        on_backgrounds(w.grab().toImage(), out, f"wheel-{name}")

    t = Toast()
    t.show_message("Saved holiday-photo.pdf", r"C:\Users\Gio\Pictures\Holidays", ms=10)
    on_backgrounds(t.grab().toImage(), out, "toast")
    t.show_message("PDF failed", "contract.pdf is password protected", error=True, ms=10)
    on_backgrounds(t.grab().toImage(), out, "toast-error")

    icon = QImage(256, 256, QImage.Format.Format_ARGB32)
    icon.fill(0)
    p = QPainter(icon)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    paint_mark(p, QPointF(128, 128), 118)
    p.end()
    on_backgrounds(icon, out, "icon")
    print(f"renders in {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "renders"))
