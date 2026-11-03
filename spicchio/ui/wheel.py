"""The wheel: a transparent, always-on-top window that accepts file drops.

It opens under the cursor while a file is being dragged. Actions are the
segments of a tangerine: a ring of slices around a small core. They unfold
once Spicchio knows which files are coming. A slice is chosen by *direction*:
the pointer can travel past the ring, and the chosen slice lifts out, turns
tangerine, and its full name is written in the core.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from spicchio.actions import SIDE_NAMES, Action, sides_for
from spicchio.geometry import point_at, slice_at, slices
from spicchio.ui import dragimage
from spicchio.ui import style as S

INNER = 62        # inner radius of the ring of slices
RING = 150        # outer radius of the ring
CORE = 48         # radius of the central disc
GAP = 6           # width of the cut between two slices, in pixels (parallel, like a real fruit)
ROUND = 11        # corner rounding of a slice
LIFT = 7          # how far the chosen slice comes out
DEAD = 40         # inside this radius nothing is chosen: dropping there cancels
REACH = 90        # how far beyond the ring a direction still chooses a slice
LABEL_W = 80      # labels wider than this wrap on two lines
STAGGER_MS = 24
FLY_MS = 380


def _ease_out_back(t: float, s: float = 1.45) -> float:
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def _polar(r: float, a: float) -> QPointF:
    """Point at radius ``r`` and screen angle ``a`` (radians, clockwise from 3 o'clock)."""
    return QPointF(r * math.cos(a), r * math.sin(a))


@lru_cache(maxsize=16)
def segment_path(n: int, index: int) -> QPainterPath:
    """One slice of the ring, centred on (0, 0), with rounded corners and parallel cuts."""
    sweep = 360 / n
    a0 = math.radians(index * sweep - sweep / 2 - 90)
    a1 = a0 + math.radians(sweep)
    path = QPainterPath()
    if n == 1:
        path.addEllipse(QPointF(0, 0), RING, RING)
        path.addEllipse(QPointF(0, 0), INNER, INNER)
        return path

    def cut(r: float) -> float:  # the angle a gap of GAP pixels takes at radius r
        return math.asin(min(1.0, GAP / 2 / r))

    o0, o1 = a0 + cut(RING), a1 - cut(RING)
    i0, i1 = a0 + cut(INNER), a1 - cut(INNER)
    co, ci = ROUND / RING, ROUND / INNER

    def arc(r: float, start: float, end: float) -> None:
        rect = QRectF(-r, -r, 2 * r, 2 * r)
        path.arcTo(rect, -math.degrees(start), -math.degrees(end - start))  # Qt counts counter-clockwise

    path.moveTo(_polar(INNER + ROUND, i0))
    path.lineTo(_polar(RING - ROUND, o0))
    path.quadTo(_polar(RING, o0), _polar(RING, o0 + co))
    arc(RING, o0 + co, o1 - co)
    path.quadTo(_polar(RING, o1), _polar(RING - ROUND, o1))
    path.lineTo(_polar(INNER + ROUND, i1))
    path.quadTo(_polar(INNER, i1), _polar(INNER, i1 - ci))
    arc(INNER, i1 - ci, i0 + ci)
    path.quadTo(_polar(INNER, i0), _polar(INNER + ROUND, i0))
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
        side = 2 * (RING + REACH + 6)
        self.setFixedSize(side, side)

        self.paths: list[Path] = []
        self.sides: list[tuple[str, list[Action]]] = []
        self.side = 0
        self.actions: list[Action] = []
        self._last_vec: tuple[float, float] | None = None
        self.hover: int | None = None
        self.busy = False

        self._clock = QElapsedTimer()
        self._clock.start()
        self._opened_at = -10_000.0
        self._slices_at = -10_000.0
        self._still = False          # renders: skip every animation
        self.time_override: float | None = None
        self._sel: list[float] = []  # per-slice selection, eased towards 0/1
        self._last_hide = 0.0

        self._tick = QTimer(self)
        self._tick.setInterval(16)
        self._tick.timeout.connect(self._step)

        self._font_slice = S.font(13, QFont.Weight.DemiBold)
        self._font_title = S.font(15, QFont.Weight.DemiBold, display=True)
        self._font_caption = S.font(11)

    # ------------------------------------------------------------------ state
    def open_at_cursor(self) -> None:
        if self.busy:
            return
        self.set_files([])
        geo = self.frameGeometry()
        geo.moveCenter(QCursor.pos())
        self.move(geo.topLeft())
        self._opened_at = self._now()
        self.show()
        self.raise_()
        self._tick.start()

    def close_soon(self) -> None:
        """Called when the mouse button is released. If a drop is being processed, stay open."""
        if not self.busy:
            self.hide()

    def done(self) -> None:
        self.busy = False
        self.hide()

    def hideEvent(self, event) -> None:
        self._tick.stop()
        dragimage.restore()
        super().hideEvent(event)

    def set_files(self, paths: list[Path]) -> None:
        self.paths = paths
        self.sides = sides_for(paths)
        self.side = 0
        self._last_vec = None
        self._apply_side()

    def turn(self, step: int) -> None:
        """Show the next (or previous) side of the wheel: Convert, Tools, Actions."""
        if len(self.sides) < 2 or self.busy:
            return
        self.side = (self.side + step) % len(self.sides)
        self._apply_side()
        self._tick.start()

    def _apply_side(self) -> None:
        self.actions = self.sides[self.side][1] if self.sides else []
        self._sel = [0.0] * len(self.actions)
        self._slices_at = self._now()
        self.hover = None
        if self._last_vec is not None:  # the pointer may not move again before the drop
            dx, dy = self._last_vec
            self.hover = slice_at(dx, dy, len(self.actions), DEAD, RING + REACH)
        self.update()

    def set_hover(self, index: int | None) -> None:
        self.hover = index
        if self._still:
            self._sel = [1.0 if i == index else 0.0 for i in range(len(self.actions))]
        elif not self._tick.isActive():
            self._tick.start()
        self.update()

    def freeze(self) -> None:
        """Jump to the end of every animation (used for renders and tests)."""
        self._still = True
        self._sel = [1.0 if i == self.hover else 0.0 for i in range(len(self.actions))]
        self.update()

    def _now(self) -> float:
        if self.time_override is not None:  # demo videos drive the animation frame by frame
            return self.time_override
        return float(self._clock.elapsed())

    def _step(self) -> None:
        moving = self.busy or self._now() - self._slices_at < FLY_MS + STAGGER_MS * len(self.actions) + 40
        moving = moving or self._now() - self._opened_at < 260
        for i, v in enumerate(self._sel):
            target = 1.0 if i == self.hover else 0.0
            eased = v + (target - v) * 0.24
            if abs(target - eased) < 0.004:
                eased = target
            else:
                moving = True
            self._sel[i] = eased
        self.update()
        if not moving:
            self._tick.stop()

    # ------------------------------------------------------------- drag & drop
    @staticmethod
    def _local_paths(event) -> list[Path]:
        md = event.mimeData()
        if not md.hasUrls():
            return []
        return [Path(u.toLocalFile()) for u in md.urls() if u.isLocalFile()]

    def dragEnterEvent(self, event) -> None:
        self.set_files(self._local_paths(event))
        self._tick.start()
        dragimage.hide()
        if self.actions:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        now = self._now()
        if now - self._last_hide > 120:  # the shell may recreate its preview window
            dragimage.hide()
            self._last_hide = now
        p = event.position()
        c = self.rect().center()
        dx, dy = p.x() - c.x(), p.y() - c.y()
        self._last_vec = (dx, dy)
        new = slice_at(dx, dy, len(self.actions), DEAD, RING + REACH)
        if new != self.hover:
            self.set_hover(new)
        if new is None:
            event.ignore()  # the "no" cursor: dropping in the middle cancels
        else:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()

    def dragLeaveEvent(self, event) -> None:
        dragimage.restore()
        self.set_hover(None)

    def dropEvent(self, event) -> None:
        dragimage.restore()
        if self.hover is None or not self.actions:
            event.ignore()
            return
        # Always COPY: a "move" drop would make Explorer delete the original file.
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        self.busy = True
        self._tick.start()
        self.dropped.emit(self.actions[self.hover], list(self.paths))

    # ---------------------------------------------------------------- painting
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        c = QPointF(self.rect().center())
        now = self._now()

        # Invisible but not empty: on Windows fully transparent pixels let a drop fall
        # through to whatever is behind (the desktop). Alpha 1 keeps the reach a drop target.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 1))
        p.drawEllipse(c, RING + REACH, RING + REACH)

        open_t = 1.0 if self._still else _ease_out(min(1.0, (now - self._opened_at) / 240))
        self._paint_guide(p, c, open_t)
        if self.actions:
            self._paint_slices(p, c, now)
        self._paint_core(p, c, open_t, now)
        if len(self.sides) > 1:
            self._paint_sides(p, c, open_t)
        p.end()

    def _paint_guide(self, p: QPainter, c: QPointF, open_t: float) -> None:
        """Before the files are known: the empty ring, so the shape is there from the first frame."""
        if self.actions:
            return
        ring = QPainterPath()
        ring.addEllipse(c, RING * (0.85 + 0.15 * open_t), RING * (0.85 + 0.15 * open_t))
        ring.addEllipse(c, INNER, INNER)
        p.setOpacity(open_t)
        p.setPen(QPen(S.HAIRLINE, 1.0))
        p.setBrush(S.with_alpha(S.INK, 0.4))
        p.drawPath(ring)
        p.setOpacity(1.0)

    def _paint_ring_shadow(self, p: QPainter, c: QPointF, t: float) -> None:
        """One soft shadow for the whole fruit, outside it only: the cuts between slices stay clean."""
        if t <= 0:
            return
        r = RING * (0.72 + 0.28 * _ease_out_back(t, 1.2))
        outside = QPainterPath()
        outside.addRect(QRectF(self.rect()))
        disc = QPainterPath()
        disc.addEllipse(c, r, r)
        p.save()
        p.setClipPath(outside.subtracted(disc))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for width, alpha in ((18, 7), (10, 14), (4, 24)):
            p.setPen(QPen(QColor(0, 0, 0, round(alpha * _ease_out(t))), width))
            p.drawEllipse(QPointF(c.x(), c.y() + 4), r, r)
        p.restore()

    def _slice_progress(self, i: int, now: float) -> float:
        if self._still:
            return 1.0
        return max(0.0, min(1.0, (now - self._slices_at - i * STAGGER_MS) / FLY_MS))

    def _paint_slices(self, p: QPainter, c: QPointF, now: float) -> None:
        n = len(self.actions)
        anyone = self.hover is not None
        self._paint_ring_shadow(p, c, self._slice_progress(n - 1, now))
        order = sorted(range(n), key=lambda i: self._sel[i] if i < len(self._sel) else 0.0)  # chosen on top
        geometry = slices(n)
        for i in order:
            s = geometry[i]
            t = self._slice_progress(i, now)
            if t <= 0:
                continue
            g = self._sel[i] if i < len(self._sel) else 0.0
            path = segment_path(n, i)
            lift_x, lift_y = point_at(s.middle, LIFT * g)

            p.save()
            p.translate(c.x() + lift_x, c.y() + lift_y)
            grow = 0.72 + 0.28 * _ease_out_back(t, 1.2)
            p.rotate(-16 * (1 - _ease_out(t)))  # the slices unfold, like opening the fruit
            p.scale(grow, grow)
            p.setOpacity(_ease_out(t))

            # the chosen slice is lifted: its own shadow, then a tangerine glow
            p.setBrush(Qt.BrushStyle.NoBrush)
            if g > 0.01:
                for width, alpha in ((10, 14), (4, 26)):
                    p.setPen(QPen(QColor(0, 0, 0, round(alpha * g)), width, Qt.PenStyle.SolidLine,
                                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                    p.drawPath(path.translated(0, 5))
                for width, alpha in ((26, 0.10), (14, 0.16), (6, 0.24)):
                    p.setPen(QPen(S.with_alpha(S.TANGERINE, alpha * g), width, Qt.PenStyle.SolidLine,
                                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                    p.drawPath(path)

            # flesh: dark glass at rest, tangerine when chosen (darker near the core, light at the peel)
            flesh = QRadialGradient(QPointF(0, 0), RING)
            flesh.setColorAt(INNER / RING, S.mix(QColor(40, 38, 46, 246), S.TANGERINE_LO, g))
            flesh.setColorAt(1.0, S.mix(QColor(24, 23, 28, 246), S.TANGERINE_HI, g))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(flesh)
            p.drawPath(path)

            # the fine lines of the pulp, barely there
            p.save()
            p.setClipPath(path)
            p.setPen(QPen(S.mix(QColor(255, 255, 255, 9), QColor(255, 232, 205, 44), g), 1.0))
            for k in (1, 2, 3):
                a = s.start + s.sweep * k / 4
                x0, y0 = point_at(a, INNER + 14)
                x1, y1 = point_at(a, RING - 14)
                p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
            p.restore()

            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(S.mix(QColor(255, 255, 255, 24), QColor(255, 218, 190, 120), g), 1.0))
            p.drawPath(path)

            # label, upright, in the middle of the slice
            lx, ly = point_at(s.middle, (INNER + RING) / 2 + 2)
            p.setFont(self._font_slice)
            recede = 1.0 if anyone and i != self.hover else 0.0  # the others step back: softer text
            p.setPen(S.mix(S.mix(S.TEXT, S.TEXT_SOFT, recede * (1 - g)), S.ON_ACCENT, g))
            lines = self._wrap(self.actions[i].label, QFontMetricsF(self._font_slice), LABEL_W)[:2]
            line_h = QFontMetricsF(self._font_slice).height()
            top = ly - line_h * len(lines) / 2
            for k, line in enumerate(lines):
                p.drawText(QRectF(lx - 60, top + k * line_h, 120, line_h), Qt.AlignmentFlag.AlignCenter, line)
            p.restore()

    def _paint_core(self, p: QPainter, c: QPointF, open_t: float, now: float) -> None:
        r = CORE * (0.7 + 0.3 * _ease_out_back(open_t, 1.2)) if not self._still else CORE
        p.setOpacity(open_t)
        p.setPen(Qt.PenStyle.NoPen)
        for grow, a in ((7, 12), (3, 24), (1, 36)):
            p.setBrush(QColor(0, 0, 0, a))
            p.drawEllipse(QPointF(c.x(), c.y() + 3), r + grow, r + grow)
        disc = QRadialGradient(QPointF(c.x(), c.y() - r * 0.8), r * 2.0)
        disc.setColorAt(0.0, QColor(44, 41, 50, 250))
        disc.setColorAt(1.0, QColor(16, 15, 19, 250))
        p.setBrush(disc)
        p.setPen(QPen(S.HAIRLINE, 1.0))
        p.drawEllipse(c, r, r)

        if self.busy:  # a tangerine arc running around the disc
            pen = QPen(S.TANGERINE, 2.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            rr = r + 6
            spin = (now / 3.2) % 360
            p.drawArc(QRectF(c.x() - rr, c.y() - rr, 2 * rr, 2 * rr), round(-spin * 16), 100 * 16)

        title, caption = self._core_text()
        width = 2 * r - 14
        p.setPen(S.TEXT)
        p.setFont(self._font_title)
        fm = QFontMetricsF(self._font_title)
        lines = self._wrap(title, fm, width)[:2]
        line_h = fm.height() * 0.92
        top = c.y() - (len(lines) * line_h) / 2 - (5 if caption else 0)
        for k, line in enumerate(lines):
            p.drawText(QRectF(c.x() - width / 2, top + k * line_h, width, line_h), Qt.AlignmentFlag.AlignCenter, line)
        if caption:
            p.setFont(self._font_caption)
            p.setPen(S.TEXT_SOFT)
            cfm = QFontMetricsF(self._font_caption)
            text = cfm.elidedText(caption, Qt.TextElideMode.ElideMiddle, width - 4)
            p.drawText(QRectF(c.x() - width / 2, top + len(lines) * line_h + 1, width, cfm.height()),
                       Qt.AlignmentFlag.AlignCenter, text)
        p.setOpacity(1.0)

    def _paint_sides(self, p: QPainter, c: QPointF, open_t: float) -> None:
        """Under the ring, a small capsule: ⇧ + the side showing + one dot per side.

        On its own dark surface, so it reads on light and dark desktops alike.
        """
        name = SIDE_NAMES[self.sides[self.side][0]].upper()
        font = S.font(10, QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.3)
        fm = QFontMetricsF(font)
        n = len(self.sides)
        dots_w = n * 5 + (n - 1) * 4
        w = 14 + 10 + 6 + fm.horizontalAdvance(name) + 8 + dots_w + 12
        h = 22.0
        r = QRectF(c.x() - w / 2, c.y() + RING + LIFT + 12, w, h)
        p.setOpacity(open_t)
        p.setPen(QPen(S.HAIRLINE, 1.0))
        p.setBrush(QColor(22, 21, 26, 240))
        p.drawRoundedRect(r, h / 2, h / 2)
        x = r.left() + 12
        p.setFont(S.font(11, QFont.Weight.DemiBold))
        p.setPen(S.with_alpha(S.TEXT, 0.55))
        p.drawText(QRectF(x, r.top(), 12, h), Qt.AlignmentFlag.AlignCenter, "⇧")
        x += 18
        p.setFont(font)
        p.setPen(S.TANGERINE)
        tw = fm.horizontalAdvance(name)
        p.drawText(QRectF(x, r.top(), tw + 2, h), Qt.AlignmentFlag.AlignVCenter, name)
        x += tw + 8
        p.setPen(Qt.PenStyle.NoPen)
        for k in range(n):
            p.setBrush(S.TANGERINE if k == self.side else S.with_alpha(S.TEXT, 0.28))
            p.drawEllipse(QPointF(x + 2.5, r.center().y()), 2.5, 2.5)
            x += 9
        p.setOpacity(1.0)

    def _core_text(self) -> tuple[str, str]:
        if self.busy:
            return "Working", self._files_line()
        if self.hover is not None and self.hover < len(self.actions):
            return self.actions[self.hover].headline, self._files_line()
        if self.paths and not self.actions:
            return "Nothing to do", "with these files"
        if self.paths:
            return "Choose", self._files_line()
        return "Drop here", ""

    @staticmethod
    def _wrap(text: str, fm: QFontMetricsF, width: float) -> list[str]:
        words, lines, line = text.split(), [], ""
        for w in words:
            trial = f"{line} {w}".strip()
            if fm.horizontalAdvance(trial) <= width or not line:
                line = trial
            else:
                lines.append(line)
                line = w
        if line:
            lines.append(line)
        return lines

    def _files_line(self) -> str:
        if len(self.paths) == 1:
            return self.paths[0].name
        return f"{len(self.paths)} files"

