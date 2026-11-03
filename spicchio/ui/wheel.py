"""The wheel: a transparent, always-on-top window that accepts file drops.

It opens under the cursor while a file is being dragged. Each slice is an
action; the file is processed by the slice it is dropped on.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from spicchio.actions import Action, actions_for
from spicchio.geometry import label_point, slice_at, slices

OUTER = 150  # radius of the ring, logical pixels
INNER = 48   # radius of the hole in the middle
MARGIN = 24  # room for the opening animation and the shadow
GAP_DEG = 1.6

INK = QColor(18, 17, 24, 235)
INK_SOFT = QColor(38, 35, 46, 235)
ORANGE = QColor("#ff5a1f")
VIOLET = QColor("#6c3cff")
WHITE = QColor(255, 255, 255)
MUTED = QColor(255, 255, 255, 150)


def _sector(c: QPointF, r_in: float, r_out: float, start: float, sweep: float) -> QPainterPath:
    """Ring sector. ``start``/``sweep`` are clockwise degrees from 12 o'clock (see geometry.py)."""
    qt_start = 90 - start  # Qt: counter-clockwise from 3 o'clock
    outer = QRectF(c.x() - r_out, c.y() - r_out, 2 * r_out, 2 * r_out)
    inner = QRectF(c.x() - r_in, c.y() - r_in, 2 * r_in, 2 * r_in)
    path = QPainterPath()
    path.arcMoveTo(outer, qt_start)
    path.arcTo(outer, qt_start, -sweep)
    path.arcTo(inner, qt_start - sweep, sweep)
    path.closeSubpath()
    return path


class Wheel(QWidget):
    dropped = Signal(object, list)  # (Action, list[Path])

    def __init__(self) -> None:
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAcceptDrops(True)
        side = 2 * (OUTER + MARGIN)
        self.setFixedSize(side, side)

        self.paths: list[Path] = []
        self.actions: list[Action] = []
        self.hover: int | None = None
        self.busy = False
        self._scale = 1.0
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._anim.valueChanged.connect(self._on_anim)

    # ---------------------------------------------------------------- show/hide
    def open_at_cursor(self) -> None:
        if self.busy:
            return
        self.paths, self.actions, self.hover = [], [], None
        pos = QCursor.pos()
        geo = self.frameGeometry()
        geo.moveCenter(pos)
        self.move(geo.topLeft())
        self._scale = 0.0
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._anim.start()

    def close_soon(self) -> None:
        """Called when the mouse button is released. If a drop is being processed, stay open."""
        if not self.busy:
            self.hide()

    def _on_anim(self, v: float) -> None:
        self._scale = 0.75 + 0.25 * v
        self.setWindowOpacity(min(1.0, max(0.0, v)))
        self.update()

    # ---------------------------------------------------------------- drag & drop
    @staticmethod
    def _local_paths(event) -> list[Path]:
        md = event.mimeData()
        if not md.hasUrls():
            return []
        return [Path(u.toLocalFile()) for u in md.urls() if u.isLocalFile()]

    def dragEnterEvent(self, event) -> None:
        self.paths = self._local_paths(event)
        self.actions = actions_for(self.paths)
        self.update()
        if self.actions:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        p = event.position()
        c = self.rect().center()
        new = slice_at(p.x() - c.x(), p.y() - c.y(), len(self.actions), INNER, OUTER)
        if new != self.hover:
            self.hover = new
            self.update()
        if new is None:
            event.ignore()  # the "no" cursor tells the user the middle cancels
        else:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()

    def dragLeaveEvent(self, event) -> None:
        self.hover = None
        self.update()

    def dropEvent(self, event) -> None:
        if self.hover is None or not self.actions:
            event.ignore()
            return
        # Always COPY: a "move" drop would make Explorer delete the original file.
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        action = self.actions[self.hover]
        self.busy = True
        self.update()
        self.dropped.emit(action, list(self.paths))

    def done(self) -> None:
        self.busy = False
        self.hide()

    # ---------------------------------------------------------------- painting
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        c = QPointF(self.rect().center())
        p.translate(c)
        p.scale(self._scale, self._scale)
        p.translate(-c)

        n = len(self.actions)
        if n == 0:
            self._paint_empty(p, c)
        else:
            self._paint_slices(p, c)
        self._paint_centre(p, c)
        p.end()

    def _paint_empty(self, p: QPainter, c: QPointF) -> None:
        ring = _sector(c, INNER, OUTER, 0, 359.99)
        p.fillPath(ring, INK)
        pen = QPen(MUTED, 1.5, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawEllipse(c, OUTER - 10, OUTER - 10)
        p.setPen(MUTED)
        p.setFont(self._font(12, QFont.Weight.Medium))
        text = "Nothing to do with these files" if self.paths else "Drop here"
        p.drawText(QRectF(c.x() - OUTER, c.y() + INNER + 6, 2 * OUTER, 40), Qt.AlignmentFlag.AlignHCenter, text)

    def _paint_slices(self, p: QPainter, c: QPointF) -> None:
        font = self._font(13 if len(self.actions) <= 6 else 12, QFont.Weight.DemiBold)
        for s in slices(len(self.actions)):
            hovered = s.index == self.hover
            path = _sector(c, INNER, OUTER + (8 if hovered else 0), s.start + GAP_DEG / 2, s.sweep - GAP_DEG)
            p.fillPath(path, ORANGE if hovered else INK)
            dx, dy = label_point(s, (INNER + OUTER) / 2 + (4 if hovered else 0))
            box = QRectF(c.x() + dx - 52, c.y() + dy - 12, 104, 24)
            p.setFont(font)
            p.setPen(QColor(18, 17, 24) if hovered else WHITE)
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, self.actions[s.index].label)

    def _paint_centre(self, p: QPainter, c: QPointF) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(INK_SOFT)
        p.drawEllipse(c, INNER - 6, INNER - 6)
        # the two dots: the brand mark, and a hint that the middle cancels
        p.setBrush(VIOLET)
        p.drawEllipse(QPointF(c.x(), c.y() - 9), 6, 6)
        p.setBrush(ORANGE if not self.busy else WHITE)
        p.drawEllipse(QPointF(c.x(), c.y() + 9), 6, 6)

    @staticmethod
    def _font(size: int, weight: QFont.Weight) -> QFont:
        f = QFont("Segoe UI")
        f.setPixelSize(size)
        f.setWeight(weight)
        return f
