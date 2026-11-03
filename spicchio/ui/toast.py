"""A small notification near the cursor: what was created, or what went wrong.
Clicking it shows the new file in Explorer / Finder."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget


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
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self._font_t = QFont("Segoe UI"); self._font_t.setPixelSize(14); self._font_t.setWeight(QFont.Weight.DemiBold)
        self._font_b = QFont("Segoe UI"); self._font_b.setPixelSize(12)

    def show_message(self, title: str, body: str = "", *, error: bool = False,
                     target: Path | None = None, ms: int = 3500) -> None:
        self._title, self._body, self._error, self._target = title, body, error, target
        w = max(QFontMetrics(self._font_t).horizontalAdvance(title),
                QFontMetrics(self._font_b).horizontalAdvance(body)) + 56
        self.setFixedSize(min(max(w, 220), 460), 64 if body else 44)
        pos = QCursor.pos()
        screen = self.screen().availableGeometry() if self.screen() else None
        x, y = pos.x() + 18, pos.y() + 22
        if screen is not None:
            x = min(x, screen.right() - self.width() - 8)
            y = min(y, screen.bottom() - self.height() - 8)
        self.move(x, y)
        self.show()
        self.raise_()
        self.update()
        self._timer.start(ms)

    def mousePressEvent(self, event) -> None:
        if self._target is not None:
            reveal(self._target)
        self.hide()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(18, 17, 24, 240))
        p.drawRoundedRect(r, 14, 14)
        p.setBrush(QColor("#e5484d") if self._error else QColor("#ff5a1f"))
        p.drawEllipse(r.left() + 18, r.center().y() - 5, 10, 10)
        p.setPen(QColor(255, 255, 255))
        p.setFont(self._font_t)
        text_x = r.left() + 40
        if self._body:
            p.drawText(QRectF(text_x, r.top() + 10, r.width() - 52, 22), Qt.AlignmentFlag.AlignVCenter, self._title)
            p.setPen(QColor(255, 255, 255, 170))
            p.setFont(self._font_b)
            body = QFontMetrics(self._font_b).elidedText(self._body, Qt.TextElideMode.ElideMiddle, int(r.width() - 52))
            p.drawText(QRectF(text_x, r.top() + 32, r.width() - 52, 20), Qt.AlignmentFlag.AlignVCenter, body)
        else:
            p.drawText(QRectF(text_x, r.top(), r.width() - 52, r.height()), Qt.AlignmentFlag.AlignVCenter, self._title)
        p.end()
