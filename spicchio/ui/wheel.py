"""The wheel: a transparent, always-on-top window that accepts file drops.

It opens under the cursor while a file is being dragged. Actions are light
pills arranged on a circle; they fly out from the centre once Spicchio knows
which files are coming. A pill is chosen by *direction*: the pointer can travel
past the circle, and the name of the chosen action is written in the middle.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from spicchio.actions import Action, actions_for
from spicchio.geometry import angle_of, point_at, slice_at, slices
from spicchio.ui import dragimage
from spicchio.ui import style as S

RING = 124        # radius of the circle the pills sit on
CORE = 50         # radius of the central disc
DEAD = 40         # inside this radius nothing is chosen: dropping there cancels
REACH = 112       # how far beyond the circle a direction still chooses a pill
PILL_H = 34
STAGGER_MS = 26
FLY_MS = 360


def _ease_out_back(t: float, s: float = 1.45) -> float:
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


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
        self.actions: list[Action] = []
        self.hover: int | None = None
        self.pointer_angle: float | None = None
        self.busy = False

        self._clock = QElapsedTimer()
        self._clock.start()
        self._opened_at = -10_000.0
        self._pills_at = -10_000.0
        self._still = False          # renders: skip every animation
        self._sel: list[float] = []  # per-pill selection, eased towards 0/1
        self._last_hide = 0.0

        self._tick = QTimer(self)
        self._tick.setInterval(16)
        self._tick.timeout.connect(self._step)

        self._font_pill = S.font(13, QFont.Weight.DemiBold)
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
        self.actions = actions_for(paths)
        self.hover = None
        self.pointer_angle = None
        self._sel = [0.0] * len(self.actions)
        self._pills_at = self._now()
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
        return float(self._clock.elapsed())

    def _step(self) -> None:
        moving = self.busy or self._now() - self._pills_at < FLY_MS + STAGGER_MS * len(self.actions) + 40
        moving = moving or self._now() - self._opened_at < 260
        for i, v in enumerate(self._sel):
            target = 1.0 if i == self.hover else 0.0
            v += (target - v) * 0.24
            if abs(target - v) < 0.004:
                v = target
            else:
                moving = True
            self._sel[i] = v
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
        new = slice_at(dx, dy, len(self.actions), DEAD, RING + REACH)
        self.pointer_angle = angle_of(dx, dy) if new is not None else None
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
            self._paint_pills(p, c, now)
        self._paint_core(p, c, open_t, now)
        p.end()

    def _paint_guide(self, p: QPainter, c: QPointF, open_t: float) -> None:
        """The thin circle the pills hang on."""
        r = RING * (0.6 + 0.4 * open_t)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(S.with_alpha(S.HAIRLINE, open_t), 1.0))
        p.drawEllipse(c, r, r)

    def _pill_progress(self, i: int, now: float) -> float:
        if self._still:
            return 1.0
        return max(0.0, min(1.0, (now - self._pills_at - i * STAGGER_MS) / FLY_MS))

    def _paint_pills(self, p: QPainter, c: QPointF, now: float) -> None:
        fm = QFontMetricsF(self._font_pill)
        anyone = self.hover is not None
        for s in slices(len(self.actions)):
            i = s.index
            t = self._pill_progress(i, now)
            if t <= 0:
                continue
            g = self._sel[i] if i < len(self._sel) else 0.0
            radius = RING * (0.25 + 0.75 * _ease_out_back(t)) + 6 * g
            dx, dy = point_at(s.middle, radius)
            centre = QPointF(c.x() + dx, c.y() + dy)
            label = self.actions[i].label
            w = max(64.0, fm.horizontalAdvance(label) + 30)
            scale = (0.82 + 0.18 * _ease_out(t)) * (1 + 0.07 * g)
            alpha = _ease_out(t)
            recede = 1.0 if anyone and i != self.hover else 0.0  # others step back: softer text, no fading

            p.save()
            p.translate(centre)
            p.scale(scale, scale)
            p.setOpacity(alpha)
            rect = QRectF(-w / 2, -PILL_H / 2, w, PILL_H)
            rad = PILL_H / 2

            # soft shadow, then a warm glow when chosen
            p.setPen(Qt.PenStyle.NoPen)
            for grow, a in ((6, 18), (3, 34), (1, 50)):
                p.setBrush(QColor(0, 0, 0, a))
                p.drawRoundedRect(rect.adjusted(-grow, -grow + 3, grow, grow + 3), rad + grow, rad + grow)
            if g > 0.01:
                glow = QRadialGradient(QPointF(0, 4), w * 0.75)
                glow.setColorAt(0.0, S.with_alpha(S.TANGERINE, 0.38 * g))
                glow.setColorAt(1.0, S.with_alpha(S.TANGERINE, 0.0))
                p.setBrush(glow)
                p.drawEllipse(QPointF(0, 4), w * 0.75, w * 0.42)

            # body: resting surface fading into a tangerine gradient
            body = QLinearGradient(0, -PILL_H / 2, 0, PILL_H / 2)
            body.setColorAt(0.0, S.mix(S.SURFACE, S.TANGERINE_HI, g))
            body.setColorAt(1.0, S.mix(S.SURFACE, S.TANGERINE_LO, g))
            p.setBrush(body)
            p.setPen(QPen(S.mix(S.HAIRLINE, QColor(255, 210, 180, 90), g), 1.0))
            p.drawRoundedRect(rect, rad, rad)
            # a whisper of light on the top edge
            p.setPen(QPen(QColor(255, 255, 255, round(14 + 40 * g)), 1.0))
            p.drawLine(QPointF(-w / 2 + rad, -PILL_H / 2 + 1.5), QPointF(w / 2 - rad, -PILL_H / 2 + 1.5))

            p.setFont(self._font_pill)
            p.setPen(S.mix(S.mix(S.TEXT, S.TEXT_SOFT, recede * (1 - g)), S.ON_ACCENT, g))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
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

