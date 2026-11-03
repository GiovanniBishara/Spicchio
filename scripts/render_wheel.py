"""Renders the wheel off-screen to PNG files, to look at the design without a Windows PC.

    QT_QPA_PLATFORM=offscreen python scripts/render_wheel.py out_dir
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from spicchio.ui.wheel import Wheel  # noqa: E402


def main(out: Path) -> None:
    app = QApplication.instance() or QApplication([])  # noqa: F841
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    photo = tmp / "holiday-photo.png"
    Image.new("RGB", (8, 8), (200, 120, 40)).save(photo)
    pdf = tmp / "contract.pdf"
    Image.new("RGB", (8, 8)).save(pdf, "PDF")

    states = [
        ("empty", [], None, None),
        ("image-pdf", [photo], 0, 4.0),
        ("image-compress", [photo], 4, 182.0),
        ("pdf-split", [pdf], 3, 250.0),
        ("image-none", [photo], None, None),
    ]
    for name, files, hover, angle in states:
        w = Wheel()
        w.set_files(files)
        w.set_hover(hover, instant=True)
        w.pointer_angle = angle
        w._open = 1.0
        shot = w.grab().toImage()
        # put it on a light and a dark desktop so both can be judged
        for bg_name, bg in (("light", QColor(236, 236, 240)), ("dark", QColor(40, 44, 52))):
            canvas = QImage(shot.size(), QImage.Format.Format_ARGB32)
            canvas.fill(bg)
            p = QPainter(canvas)
            p.drawImage(0, 0, shot)
            p.end()
            canvas.save(str(out / f"wheel-{name}-{bg_name}.png"))
    print(f"renders in {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "renders"))
