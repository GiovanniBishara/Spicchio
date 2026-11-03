"""The tray application: wires the global listener, the wheel and the notifications together."""

from __future__ import annotations

import signal
import sys
import threading
from collections import deque
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from spicchio import __version__, autostart
from spicchio.actions import Action, ActionError, Done
from spicchio.trigger import DragShiftDetector, GlobalListener
from spicchio.ui.icon import app_icon
from spicchio.ui.toast import Toast, reveal
from spicchio.undo import undo

SLOW_MS = 600  # show "Working…" only for jobs that take longer than this


class Bridge(QObject):
    """pynput calls us from its own threads; signals hop back to the Qt thread."""

    open_wheel = Signal()
    close_wheel = Signal()
    turn_wheel = Signal(int)
    finished = Signal(object, object, object, object)  # (Action, sources, result, error)


def _summary(outputs: list[Path]) -> tuple[str, str, Path]:
    if len(outputs) == 1:
        return f"Saved {outputs[0].name}", str(outputs[0].parent), outputs[0]
    folders = {o.parent for o in outputs}
    where = next(iter(folders)) if len(folders) == 1 else outputs[0].parent
    return f"Saved {len(outputs)} files", str(where), outputs[0]


class SpicchioApp:
    def __init__(self, app: QApplication) -> None:
        from spicchio.ui.wheel import Wheel  # Qt widgets only after QApplication exists

        self.app = app
        self.bridge = Bridge()
        self.wheel = Wheel()
        self.toast = Toast()
        self.recent: deque[tuple[str, Path]] = deque(maxlen=6)
        self.detector = DragShiftDetector(on_open=lambda x, y: self.bridge.open_wheel.emit(),
                                          on_close=self.bridge.close_wheel.emit,
                                          on_turn=self.bridge.turn_wheel.emit)
        self.listener = GlobalListener(self.detector)

        self.bridge.open_wheel.connect(self.wheel.open_at_cursor)
        # The drop reaches the wheel just after the button is released: wait a moment before closing.
        self.bridge.close_wheel.connect(lambda: QTimer.singleShot(200, self.wheel.close_soon))
        self.bridge.turn_wheel.connect(self.wheel.turn)
        self.bridge.finished.connect(self._on_finished)
        self.wheel.dropped.connect(self._run)

        self.tray = QSystemTrayIcon(app_icon(64), app)
        self.tray.setToolTip("Spicchio: drag a file, press Shift, drop it on an action")
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self._fill_menu)
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        self._enabled = True
        self._busy_job = 0

    # ---------------------------------------------------------------- tray menu
    def _fill_menu(self) -> None:
        m = self.menu
        m.clear()
        title = m.addAction(f"Spicchio {__version__}")
        title.setEnabled(False)
        m.addSeparator()
        if self.recent:
            sub = m.addMenu("Recent")
            for label, path in list(self.recent)[::-1]:
                act = sub.addAction(label)
                act.triggered.connect(lambda _=False, p=path: reveal(p))
        enabled = QAction("Enabled", m)
        enabled.setCheckable(True)
        enabled.setChecked(self._enabled)
        enabled.toggled.connect(self._set_enabled)
        m.addAction(enabled)
        if autostart.supported():
            start = QAction("Start with Windows", m)
            start.setCheckable(True)
            start.setChecked(autostart.is_enabled())
            start.toggled.connect(autostart.set_enabled)
            m.addAction(start)
        m.addAction("How to use").triggered.connect(self.show_help)
        m.addSeparator()
        m.addAction("Quit").triggered.connect(self.quit)

    def _set_enabled(self, on: bool) -> None:
        self._enabled = on
        self.detector.enabled = on

    def show_help(self) -> None:
        self.toast.show_message("Drag a file and press Shift",
                                "Shift again for more actions. Drop in the middle to cancel.", ms=7000)

    def start(self) -> None:
        self.listener.start()
        self.show_help()

    def quit(self) -> None:
        self.listener.stop()
        self.tray.hide()
        self.app.quit()

    # ---------------------------------------------------------------- actions
    def _run(self, action: Action, paths: list[Path]) -> None:
        self._busy_job += 1
        job = self._busy_job
        name = paths[0].name if len(paths) == 1 else f"{len(paths)} files"

        def slow() -> None:
            # Still running: put the wheel away and keep a small "working" note instead,
            # so a long video conversion never sits in the middle of the screen.
            if self._busy_job == job:
                self.wheel.done()
                self.toast.show_message(f"{action.headline}…", name, busy=True, ms=600_000)

        QTimer.singleShot(SLOW_MS, slow)

        def work() -> None:
            try:
                self.bridge.finished.emit(action, paths, action(paths), None)
            except ActionError as exc:
                self.bridge.finished.emit(action, paths, None, str(exc))
            except Exception as exc:  # never let a worker crash silently
                self.bridge.finished.emit(action, paths, None, f"Unexpected error: {exc}")

        threading.Thread(target=work, daemon=True).start()

    def _on_finished(self, action: Action, sources: list[Path], result, error: str | None) -> None:
        self._busy_job += 1  # cancels a pending "Working…" note
        self.wheel.done()
        if error:
            self.toast.show_message(f"{action.label} failed", error, error=True, ms=6000)
            return
        if isinstance(result, Done):
            if result.clipboard is not None:
                QGuiApplication.clipboard().setText(result.clipboard)
            self.toast.show_message(result.message, result.detail)
            return
        if not result:
            return
        title, body, target = _summary(result)
        self.recent.append((f"{action.headline}: {target.name}", target))
        self.toast.show_message(title, body, target=target, undo=lambda: self._undo(result, sources), ms=6000)

    def _undo(self, outputs: list[Path], sources: list[Path]) -> None:
        try:
            n = undo(outputs, sources)
        except Exception as exc:
            self.toast.show_message("Undo failed", str(exc), error=True)
            return
        self.recent = deque([r for r in self.recent if r[1] not in outputs], maxlen=6)
        self.toast.show_message("Moved to the Recycle Bin" if sys.platform == "win32" else "Moved to the Trash",
                                f"{n} file{'s' if n != 1 else ''}")


def run_app() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Spicchio")
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("No system tray available", file=sys.stderr)
        return 1
    spicchio = SpicchioApp(app)
    spicchio.start()

    # Ctrl+C in the terminal: Qt's event loop runs in C++ and Python only handles signals
    # when it gets control back, so wake it up a few times a second.
    signal.signal(signal.SIGINT, lambda *_: spicchio.quit())
    wake = QTimer()
    wake.timeout.connect(lambda: None)
    wake.start(250)
    print("Spicchio is running. Drag a file and press Shift. Ctrl+C or the tray menu to quit.")
    return app.exec()
