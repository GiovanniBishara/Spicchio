"""A small notification near the cursor: what was created, or what went wrong.
Clicking it shows the new file in Explorer / Finder."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QWidget

from spicchio.ui import style as S
from spicchio.ui.icon import paint_mark

PAD = 12  # room for the shadow


def reveal(path: Path) -> None:
    """Open the folder and select the file."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", f"/select,{path}"])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except OSError:
        pass


class Toast(QWidget):
    def __init__(self) -> None:
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._title = ""
        self._body = ""
        self._error = False
        self._target: Path | None = None
        self._font_t = S.font(13.5, QFont.Weight.DemiBold)
        self._font_b = S.font(11.5)
        self._clock = QElapsedTimer()
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        self._anim = QTimer(self)
        self._anim.setInterval(16)
        self._anim.timeout.connect(self._step)

    def show_message(self, title: str, body: str = "", *, error: bool = False,
                     target: Path | None = None, ms: int = 3500) -> None:
        self._title, self._body, self._error, self._target = title, body, error, target
        fm_t, fm_b = QFontMetricsF(self._font_t), QFontMetricsF(self._font_b)
        text_w = max(fm_t.horizontalAdvance(title), fm_b.horizontalAdvance(body) if body else 0)
        w = min(max(text_w + 92, 240), 520)
        h = 62 if body else 46
        self.setFixedSize(round(w + 2 * PAD), h + 2 * PAD)
        pos = QCursor.pos()
        screen = self.screen().availableGeometry() if self.screen() else None
        x, y = pos.x() + 10, pos.y() + 16
        if screen is not None:
            x = min(x, screen.right() - self.width() - 4)
            y = min(y, screen.bottom() - self.height() - 4)
        self.move(x, y)
        self._clock.start()
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._anim.start()
        self._hide_timer.start(ms)

    def _step(self) -> None:
        t = min(1.0, self._clock.elapsed() / 180)
        self.setWindowOpacity(1 - (1 - t) ** 3)
        if t >= 1:
            self._anim.stop()

    def mousePressEvent(self, event) -> None:
        if self._target is not None:
            reveal(self._target)
        self.hide()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(PAD, PAD, -PAD, -PAD)
        rad = r.height() / 2
        p.setPen(Qt.PenStyle.NoPen)
        for grow, a in ((8, 14), (4, 30), (1, 50)):
            p.setBrush(QColor(0, 0, 0, a))
            p.drawRoundedRect(r.adjusted(-grow, -grow + 3, grow, grow + 3), rad + grow, rad + grow)
        p.setBrush(QColor(22, 21, 26, 246))
        p.setPen(QPen(S.HAIRLINE, 1.0))
        p.drawRoundedRect(r, rad, rad)

        icon_c = QPointF(r.left() + rad, r.center().y())
        if self._error:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(S.DANGER)
            p.drawEllipse(icon_c, 9, 9)
            pen = QPen(S.TEXT, 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(icon_c.x(), icon_c.y() - 4), QPointF(icon_c.x(), icon_c.y() + 1))
            p.drawPoint(QPointF(icon_c.x(), icon_c.y() + 4.5))
        else:
            paint_mark(p, icon_c, 10, lifted=True)

        text_x = r.left() + 2 * rad - 4
        text_w = r.right() - text_x - 16
        p.setPen(S.TEXT)
        p.setFont(self._font_t)
        if self._body:
            p.drawText(QRectF(text_x, r.top() + 10, text_w, 20), Qt.AlignmentFlag.AlignVCenter, self._title)
            p.setPen(S.TEXT_SOFT)
            p.setFont(self._font_b)
            body = QFontMetricsF(self._font_b).elidedText(self._body, Qt.TextElideMode.ElideMiddle, text_w)
            p.drawText(QRectF(text_x, r.top() + 31, text_w, 18), Qt.AlignmentFlag.AlignVCenter, body)
        else:
            p.drawText(QRectF(text_x, r.top(), text_w, r.height()), Qt.AlignmentFlag.AlignVCenter, self._title)
        p.end()
