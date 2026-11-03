"""The wheel: a transparent, always-on-top window that accepts file drops.

It opens under the cursor while a file is being dragged. Slices are picked by
*direction*: the pointer can travel well past the ring, so the drag image that
Windows draws next to the cursor never covers the labels. The name of the
chosen action is written in the middle, where the cursor never is.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from spicchio.actions import Action, actions_for
from spicchio.geometry import angle_of, label_point, point_at, slice_at, slices

OUTER = 150   # radius of the visible ring (logical px)
INNER = 66    # radius of the hole with the action name
REACH = 120   # how far beyond the ring a direction still selects a slice
SHADOW = 26
GROW = 12     # how much the chosen slice grows outwards
GAP_DEG = 1.4

INK = QColor(14, 13, 19)
RING_IN = QColor(34, 31, 42, 246)
RING_OUT = QColor(20, 19, 26, 246)
ORANGE = QColor(255, 90, 31)
ORANGE_HI = QColor(255, 128, 74)
VIOLET = QColor(108, 60, 255)
WHITE = QColor(255, 255, 255)


def _ui_font(px: int, weight: QFont.Weight) -> QFont:
    f = QFont()
    f.setFamilies(["Segoe UI Variable Display", "Segoe UI", "Inter", "Helvetica Neue", "Arial"])
    f.setPixelSize(px)
    f.setWeight(weight)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return f


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


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t), round(a.alpha() + (b.alpha() - a.alpha()) * t))


class Wheel(QWidget):
    dropped = Signal(object, list)  # (Action, list[Path])

    def __init__(self) -> None:
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAcceptDrops(True)
        side = 2 * (OUTER + REACH + 8)
        self.setFixedSize(side, side)

        self.paths: list[Path] = []
        self.actions: list[Action] = []
        self.hover: int | None = None
        self.pointer_angle: float | None = None
        self.busy = False
        self._grow: list[float] = []   # per-slice highlight, animated towards 0/1
        self._open = 1.0

        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(240)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_open)

        self._tick = QTimer(self)
        self._tick.setInterval(16)
        self._tick.timeout.connect(self._step)

    # ---------------------------------------------------------------- show/hide
    def open_at_cursor(self) -> None:
        if self.busy:
            return
        self.set_files([])
        geo = self.frameGeometry()
        geo.moveCenter(QCursor.pos())
        self.move(geo.topLeft())
        self._open = 0.0
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._anim.start()

    def close_soon(self) -> None:
        """Called when the mouse button is released. If a drop is being processed, stay open."""
        if not self.busy:
            self.hide()

    def done(self) -> None:
        self.busy = False
        self.hide()

    def hideEvent(self, event) -> None:
        self._tick.stop()
        super().hideEvent(event)

    def set_files(self, paths: list[Path]) -> None:
        self.paths = paths
        self.actions = actions_for(paths)
        self.hover = None
        self.pointer_angle = None
        self._grow = [0.0] * len(self.actions)
        self.update()

    def set_hover(self, index: int | None, *, instant: bool = False) -> None:
        self.hover = index
        if instant:
            self._grow = [1.0 if i == index else 0.0 for i in range(len(self.actions))]
        elif not self._tick.isActive():
            self._tick.start()
        self.update()

    def _on_open(self, v: float) -> None:
        self._open = v
        self.setWindowOpacity(v)
        self.update()

    def _step(self) -> None:
        settled = True
        for i, g in enumerate(self._grow):
            target = 1.0 if i == self.hover else 0.0
            g += (target - g) * 0.28
            if abs(target - g) < 0.01:
                g = target
            else:
                settled = False
            self._grow[i] = g
        self.update()
        if settled:
            self._tick.stop()

    # ---------------------------------------------------------------- drag & drop
    @staticmethod
    def _local_paths(event) -> list[Path]:
        md = event.mimeData()
        if not md.hasUrls():
            return []
        return [Path(u.toLocalFile()) for u in md.urls() if u.isLocalFile()]

    def dragEnterEvent(self, event) -> None:
        self.set_files(self._local_paths(event))
        if self.actions:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        p = event.position()
        c = self.rect().center()
        dx, dy = p.x() - c.x(), p.y() - c.y()
        new = slice_at(dx, dy, len(self.actions), INNER, OUTER + REACH)
        self.pointer_angle = angle_of(dx, dy) if new is not None else None
        if new != self.hover:
            self.set_hover(new)
        else:
            self.update()
        if new is None:
            event.ignore()  # the "no" cursor: dropping in the middle cancels
        else:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()

    def dragLeaveEvent(self, event) -> None:
        self.set_hover(None)

    def dropEvent(self, event) -> None:
        if self.hover is None or not self.actions:
            event.ignore()
            return
        # Always COPY: a "move" drop would make Explorer delete the original file.
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        self.busy = True
        self.update()
        self.dropped.emit(self.actions[self.hover], list(self.paths))

    # ---------------------------------------------------------------- painting
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        c = QPointF(self.rect().center())

        # Invisible, but not empty: on Windows fully transparent pixels let the drop fall through
        # to whatever is behind (the desktop!). Alpha 1 keeps the whole reach area a drop target.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 1))
        p.drawEllipse(c, OUTER + REACH, OUTER + REACH)

        s = 0.86 + 0.14 * self._open
        p.translate(c)
        p.scale(s, s)
        p.translate(-c)

        self._paint_ring(p, c)
        if self.actions:
            self._paint_slices(p, c)
        self._paint_centre(p, c)
        p.end()

    def _paint_ring(self, p: QPainter, c: QPointF) -> None:
        shadow = QRadialGradient(c, OUTER + SHADOW)
        shadow.setColorAt((OUTER - 6) / (OUTER + SHADOW), QColor(0, 0, 0, 70))
        shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(shadow)
        p.drawEllipse(QPointF(c.x(), c.y() + 8), OUTER + SHADOW, OUTER + SHADOW)

        body = QRadialGradient(c, OUTER)
        body.setColorAt(INNER / OUTER, RING_IN)
        body.setColorAt(1.0, RING_OUT)
        p.setBrush(body)
        p.drawEllipse(c, OUTER, OUTER)  # a full disc: no see-through gap around the centre

        # hairlines: light from above on the outer edge, a darker lip on the inner one
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 34), 1.0))
        p.drawEllipse(c, OUTER - 0.5, OUTER - 0.5)
        p.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
        p.drawEllipse(c, INNER + 0.5, INNER + 0.5)

    def _paint_slices(self, p: QPainter, c: QPointF) -> None:
        n = len(self.actions)
        parts = slices(n)
        # separators between slices
        p.setPen(QPen(QColor(255, 255, 255, 16), 1.0))
        for s in parts:
            a, b = point_at(s.start, INNER + 6), point_at(s.start, OUTER - 6)
            p.drawLine(QPointF(c.x() + a[0], c.y() + a[1]), QPointF(c.x() + b[0], c.y() + b[1]))

        label_font = _ui_font(14 if n <= 6 else 13, QFont.Weight.DemiBold)
        for s in parts:
            g = self._grow[s.index] if s.index < len(self._grow) else 0.0
            if g > 0.001:
                r_out = OUTER + GROW * g
                fill = QRadialGradient(c, r_out)
                fill.setColorAt(INNER / r_out, _mix(QColor(255, 90, 31, 0), ORANGE, g))
                fill.setColorAt(1.0, _mix(QColor(255, 128, 74, 0), ORANGE_HI, g))
                p.fillPath(_sector(c, INNER + 3, r_out, s.start + GAP_DEG / 2, s.sweep - GAP_DEG), fill)
            dx, dy = label_point(s, (INNER + OUTER) / 2 + 4 + GROW * 0.4 * g)
            box = QRectF(c.x() + dx - 56, c.y() + dy - 13, 112, 26)
            p.setFont(label_font)
            p.setPen(_mix(QColor(255, 255, 255, 225), INK, g))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, self.actions[s.index].label)

        # a small notch on the rim that follows the pointer direction
        if self.pointer_angle is not None:
            dx, dy = point_at(self.pointer_angle, OUTER + GROW + 9)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(WHITE)
            p.drawEllipse(QPointF(c.x() + dx, c.y() + dy), 3.2, 3.2)

    def _paint_centre(self, p: QPainter, c: QPointF) -> None:
        r = INNER - 9
        p.setPen(QPen(QColor(255, 255, 255, 20), 1.0))
        hole = QRadialGradient(QPointF(c.x(), c.y() - r * 0.6), r * 1.6)
        hole.setColorAt(0.0, QColor(36, 33, 45))
        hole.setColorAt(1.0, INK)
        p.setBrush(hole)
        p.drawEllipse(c, r, r)

        # the two dots of the brand, top of the hole
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(VIOLET)
        p.drawEllipse(QPointF(c.x() - 6, c.y() - r + 15), 3.6, 3.6)
        p.setBrush(ORANGE)
        p.drawEllipse(QPointF(c.x() + 6, c.y() - r + 15), 3.6, 3.6)

        if self.busy:
            title, sub = "Working…", ""
        elif self.hover is not None and self.hover < len(self.actions):
            title, sub = self.actions[self.hover].headline, self._files_line()
        elif self.paths and not self.actions:
            title, sub = "Nothing to do", "with these files"
        elif self.paths:
            title, sub = "Pick a slice", self._files_line()
        else:
            title, sub = "Drop on", "a slice"

        p.setPen(WHITE)
        p.setFont(_ui_font(14, QFont.Weight.DemiBold))
        flags = (Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom).value | Qt.TextFlag.TextWordWrap.value
        p.drawText(QRectF(c.x() - r + 8, c.y() - 22, 2 * r - 16, 36), flags, title)
        p.setPen(QColor(255, 255, 255, 140))
        small = _ui_font(11, QFont.Weight.Normal)
        p.setFont(small)
        p.drawText(QRectF(c.x() - r + 10, c.y() + 16, 2 * r - 20, 16), Qt.AlignmentFlag.AlignHCenter,
                   p.fontMetrics().elidedText(sub, Qt.TextElideMode.ElideMiddle, int(2 * r - 20)))

    def _files_line(self) -> str:
        if len(self.paths) == 1:
            return self.paths[0].name
        return f"{len(self.paths)} files"
