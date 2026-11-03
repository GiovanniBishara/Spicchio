"""The Spicchio mark: a tangerine seen in section, one slice lifted out."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient

from spicchio.ui import style as S

SEGMENTS = 8


def paint_mark(p: QPainter, c: QPointF, r: float, *, lifted: bool = True) -> None:
    """Draw the mark centred in ``c`` with radius ``r``."""
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    peel = QRadialGradient(QPointF(c.x() - r * 0.3, c.y() - r * 0.35), r * 1.5)
    peel.setColorAt(0.0, S.TANGERINE_HI)
    peel.setColorAt(1.0, S.TANGERINE_LO)
    p.setBrush(peel)
    p.drawEllipse(c, r, r)

    sweep = 360 / SEGMENTS
    inner = r * 0.84
    for i in range(SEGMENTS):
        start = i * sweep + 2.5
        span = sweep - 5
        path = QPainterPath(c)
        rect = QRectF(c.x() - inner, c.y() - inner, 2 * inner, 2 * inner)
        path.arcTo(rect, 90 - start, -span)
        path.closeSubpath()
        offset = QPointF(0, 0)
        if lifted and i == 0:
            mid = math.radians(start + span / 2)
            offset = QPointF(math.sin(mid) * r * 0.16, -math.cos(mid) * r * 0.16)
            p.setBrush(QColor(255, 236, 214))
        else:
            p.setBrush(QColor(255, 196, 140))
        p.drawPath(path.translated(offset))
    p.setBrush(QColor(255, 236, 214))
    p.drawEllipse(c, r * 0.09, r * 0.09)
    p.setPen(QPen(QColor(255, 255, 255, 60), max(1.0, r * 0.04)))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(c, r - r * 0.02, r - r * 0.02)
    p.restore()


def app_icon(size: int = 64) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    paint_mark(p, QPointF(size / 2, size / 2), size * 0.46)
    p.end()
    return QIcon(pm)
