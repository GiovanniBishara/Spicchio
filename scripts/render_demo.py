"""Renders the README demo, frame by frame, with the real wheel and notification.

    python scripts/render_demo.py out_dir        # out_dir/frames/0000.png ...

A file is dragged out of a folder, Shift opens the wheel, Shift again turns it
to Tools, the file is dropped on "Under 1 MB" and the notification appears.
Assemble with:  ffmpeg -framerate 30 -i frames/%04d.png -pix_fmt yuv420p demo.mp4
"""

from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from spicchio.geometry import slice_at  # noqa: E402
from spicchio.ui import style as S  # noqa: E402
from spicchio.ui.toast import Toast  # noqa: E402
from spicchio.ui.wheel import DEAD, REACH, RING, Wheel  # noqa: E402

W, H, FPS = 1280, 720, 30
DESK = QPointF(800, 360)          # where the wheel opens
ROW0 = QPointF(196, 262)          # first file row in the folder window


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a: QPointF, b: QPointF, t: float) -> QPointF:
    t = ease(t)
    return QPointF(a.x() + (b.x() - a.x()) * t, a.y() + (b.y() - a.y()) * t)


def font(px: float, weight=QFont.Weight.Normal, display=False) -> QFont:
    return S.font(px, weight, display)


def desktop(p: QPainter) -> None:
    g = QLinearGradient(0, 0, W, H)
    g.setColorAt(0, QColor(236, 232, 226))
    g.setColorAt(1, QColor(214, 208, 200))
    p.fillRect(0, 0, W, H, g)


def folder(p: QPainter, files: list[tuple[str, str, QColor]], highlight: int | None, dragging: int | None) -> None:
    r = QRectF(120, 150, 420, 400)
    p.setPen(Qt.PenStyle.NoPen)
    for grow, a in ((14, 10), (6, 22), (2, 30)):
        p.setBrush(QColor(60, 40, 20, a))
        p.drawRoundedRect(r.adjusted(-grow, -grow + 6, grow, grow + 6), 16 + grow, 16 + grow)
    p.setBrush(QColor(252, 251, 249))
    p.drawRoundedRect(r, 16, 16)
    p.setPen(QColor(30, 28, 34))
    p.setFont(font(17, QFont.Weight.DemiBold, True))
    p.drawText(QRectF(r.left() + 28, r.top() + 22, 300, 28), Qt.AlignmentFlag.AlignVCenter, "Pictures")
    p.setPen(QPen(QColor(0, 0, 0, 18), 1))
    p.drawLine(QPointF(r.left(), r.top() + 70), QPointF(r.right(), r.top() + 70))
    for i, (name, size, col) in enumerate(files):
        y = ROW0.y() + i * 58
        row = QRectF(r.left() + 12, y - 24, r.width() - 24, 48)
        if i == highlight:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 106, 36, 34))
            p.drawRoundedRect(row, 10, 10)
        p.setOpacity(0.35 if i == dragging else 1.0)
        thumb(p, QPointF(r.left() + 52, y), col, 34)
        p.setPen(QColor(30, 28, 34))
        p.setFont(font(14.5, QFont.Weight.Medium))
        p.drawText(QRectF(r.left() + 84, y - 12, 220, 24), Qt.AlignmentFlag.AlignVCenter, name)
        p.setPen(QColor(30, 28, 34, 120))
        p.setFont(font(13))
        p.drawText(QRectF(r.right() - 120, y - 12, 96, 24), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, size)
        p.setOpacity(1.0)


def thumb(p: QPainter, c: QPointF, col: QColor, size: float) -> None:
    """A photo thumbnail: coloured square with a little sun and hill."""
    r = QRectF(c.x() - size / 2, c.y() - size / 2, size, size)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(col)
    p.drawRoundedRect(r, size * 0.18, size * 0.18)
    p.setBrush(QColor(255, 255, 255, 200))
    p.drawEllipse(QPointF(r.left() + size * 0.68, r.top() + size * 0.32), size * 0.11, size * 0.11)
    hill = QPainterPath(QPointF(r.left(), r.bottom() - size * 0.12))
    hill.quadTo(QPointF(r.left() + size * 0.4, r.top() + size * 0.45), QPointF(r.right(), r.bottom() - size * 0.2))
    hill.lineTo(r.right(), r.bottom() - size * 0.18)
    hill.lineTo(r.left(), r.bottom() - size * 0.18)
    p.setBrush(QColor(255, 255, 255, 110))
    p.drawPath(hill)


def cursor(p: QPainter, at: QPointF, pressed: bool) -> None:
    pts = [(0, 0), (0, 26), (6.5, 20), (11, 30.5), (15.5, 28.5), (11, 18.5), (19.5, 18.5)]
    path = QPainterPath(QPointF(at.x(), at.y()))
    for x, y in pts[1:]:
        path.lineTo(at.x() + x, at.y() + y)
    path.closeSubpath()
    p.setPen(QPen(QColor(20, 20, 20), 1.6))
    p.setBrush(QColor(255, 255, 255))
    p.drawPath(path)
    if pressed:
        p.setPen(QPen(S.with_alpha(S.TANGERINE, 0.6), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(at, 14, 14)


def keycap(p: QPainter, pressed: float, visible: float) -> None:
    if visible <= 0:
        return
    p.setOpacity(visible)
    r = QRectF(W - 210, H - 112, 150, 62).translated(0, 3 * pressed)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 40 - round(25 * pressed)))
    p.drawRoundedRect(r.translated(0, 5 - 4 * pressed), 14, 14)
    p.setBrush(S.mix(QColor(252, 251, 249), S.TANGERINE, pressed))
    p.setPen(QPen(QColor(0, 0, 0, 30), 1))
    p.drawRoundedRect(r, 14, 14)
    p.setPen(S.mix(QColor(30, 28, 34), S.ON_ACCENT, pressed))
    p.setFont(font(20, QFont.Weight.DemiBold, True))
    p.drawText(r, Qt.AlignmentFlag.AlignCenter, "⇧  Shift")
    p.setOpacity(1.0)


def caption(p: QPainter, n: int, text: str, alpha: float) -> None:
    if alpha <= 0:
        return
    p.setOpacity(alpha)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(22, 21, 26, 235))
    fm_text = text
    p.setFont(font(17, QFont.Weight.DemiBold, True))
    w = p.fontMetrics().horizontalAdvance(fm_text) + 86
    r = QRectF((W - w) / 2, 46, w, 48)
    p.drawRoundedRect(r, 24, 24)
    p.setBrush(S.TANGERINE)
    p.drawEllipse(QPointF(r.left() + 26, r.center().y()), 13, 13)
    p.setPen(S.ON_ACCENT)
    p.setFont(font(14, QFont.Weight.Bold))
    p.drawText(QRectF(r.left() + 13, r.top(), 26, r.height()), Qt.AlignmentFlag.AlignCenter, str(n))
    p.setPen(S.TEXT)
    p.setFont(font(17, QFont.Weight.DemiBold, True))
    p.drawText(QRectF(r.left() + 50, r.top(), w - 60, r.height()), Qt.AlignmentFlag.AlignVCenter, text)
    p.setOpacity(1.0)


def main(out: Path) -> None:
    app = QApplication.instance() or QApplication([])  # noqa: F841
    frames = out / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    photo = tmp / "holiday.heic"
    Image.new("RGB", (8, 8), (200, 120, 40)).save(tmp / "holiday.png")
    (tmp / "holiday.png").rename(photo)

    files = [("holiday.heic", "4.8 MB", QColor(232, 124, 64)), ("team-dinner.jpg", "3.1 MB", QColor(84, 120, 196)),
             ("whiteboard.png", "2.2 MB", QColor(96, 160, 120)), ("passport-scan.pdf", "860 KB", QColor(150, 140, 170))]
    result_row = ("holiday-email.jpg", "980 KB", QColor(255, 106, 36))

    wheel = Wheel()
    wheel.time_override = 0.0
    toast = Toast()
    total = int(6.4 * FPS)
    start, grab = QPointF(250, 450), ROW0 + QPointF(10, 6)
    jpg_dir = QPointF(DESK.x() + 120, DESK.y() - 92)   # towards "JPG" (2nd pill on Convert)
    tools_dir = QPointF(DESK.x() + 168, DESK.y() + 6)   # towards "Under 1 MB" (2nd pill on Tools)

    opened = turned = dropped = False
    for f in range(total):
        t = f / FPS
        ms = t * 1000
        img = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        desktop(p)

        # pointer path
        if t < 0.7:
            pos = lerp(start, grab, t / 0.7)
        elif t < 1.5:
            pos = lerp(grab, DESK + QPointF(0, 30), (t - 0.7) / 0.8)
        elif t < 2.5:
            pos = lerp(DESK + QPointF(0, 30), jpg_dir, (t - 1.7) / 0.7)
        elif t < 4.0:
            pos = lerp(jpg_dir, tools_dir, (t - 3.0) / 0.6)
        else:
            pos = tools_dir
        pressed = 0.7 <= t < 4.1
        dragging = 0.75 <= t < 4.1

        shown = files + ([result_row] if t > 4.35 else [])
        folder(p, shown, highlight=4 if 4.35 < t < 6.4 else (0 if 0.6 < t < 4.1 else None), dragging=0 if dragging else None)

        # the wheel
        if t >= 1.55 and not opened:
            wheel.time_override = ms
            wheel._opened_at = ms
            wheel.set_files([photo])
            opened = True
        if t >= 3.0 and not turned:
            wheel.time_override = ms
            wheel.turn(1)
            turned = True
        if opened and not dropped:
            wheel.time_override = ms
            c = QPointF(wheel.width() / 2, wheel.height() / 2)
            v = pos - DESK
            wheel._last_vec = (v.x(), v.y())
            hover = slice_at(v.x(), v.y(), len(wheel.actions), DEAD, RING + REACH)
            if hover != wheel.hover:
                wheel.set_hover(hover)
            for _ in range(2):
                wheel._step()
            if t >= 4.1:
                wheel.busy = True
            if t >= 4.35:
                dropped = True
            if not dropped:
                fade = 1.0 if t < 4.15 else max(0.0, 1 - (t - 4.15) / 0.2)
                p.setOpacity(fade)
                wheel.render(p, QPoint(round(DESK.x() - c.x()), round(DESK.y() - c.y())))
                p.setOpacity(1.0)

        # the dragged file (small: Spicchio hides the big shell preview over the wheel)
        if dragging:
            thumb(p, pos + QPointF(22, 30), files[0][2], 30 if not opened else 22)

        # notification
        if t > 4.35:
            a = min(1.0, (t - 4.35) / 0.18)
            if not toast.isVisible():
                toast.show_message("Saved holiday-email.jpg", r"C:\Users\Gio\Pictures", undo=lambda: None, ms=60_000)
            p.setOpacity(a)
            toast.render(p, QPoint(round(DESK.x() - 150), round(DESK.y() - 40)))
            p.setOpacity(1.0)

        cursor(p, pos if not (4.35 < t) else pos, pressed)

        shift = 0.0
        for when in (1.45, 2.9):
            if when <= t < when + 0.28:
                shift = math.sin((t - when) / 0.28 * math.pi)
        keycap(p, shift, min(1.0, max(0.0, (t - 1.1) / 0.3)) * (1.0 if t < 4.3 else max(0.0, 1 - (t - 4.3) / 0.3)))

        steps = [(0.2, 1.4, 1, "Drag a file"), (1.4, 2.85, 2, "Tap Shift: the wheel opens"),
                 (2.85, 4.2, 3, "Shift again: Tools"), (4.2, 6.4, 4, "Drop. Saved next to the original")]
        for a0, a1, n, text in steps:
            if a0 <= t < a1:
                caption(p, n, text, min(1.0, (t - a0) / 0.2, (a1 - t) / 0.2 if a1 < 6.4 else 1.0))
        p.end()
        img.save(str(frames / f"{f:04d}.png"))
    print(f"{total} frames in {frames}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "demo"))
