"""The tray application: wires the global listener, the wheel and the notifications together."""

from __future__ import annotations

import signal
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from spicchio import __version__, autostart
from spicchio.actions import Action, ActionError
from spicchio.trigger import DragShiftDetector, GlobalListener
from spicchio.ui.icon import app_icon
from spicchio.ui.toast import Toast
from spicchio.ui.wheel import Wheel


class Bridge(QObject):
    """pynput calls us from its own threads; signals hop back to the Qt thread."""

    open_wheel = Signal()
    close_wheel = Signal()
    finished = Signal(object, object, object)  # (Action, list[Path] | None, error str | None)


def _summary(outputs: list[Path]) -> tuple[str, str, Path | None]:
    if len(outputs) == 1:
        return f"Saved {outputs[0].name}", str(outputs[0].parent), outputs[0]
    folders = {o.parent for o in outputs}
    where = next(iter(folders)) if len(folders) == 1 else outputs[0].parent
    return f"Saved {len(outputs)} files", str(where), outputs[0]


class SpicchioApp:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.bridge = Bridge()
        self.wheel = Wheel()
        self.toast = Toast()
        self.detector = DragShiftDetector(on_open=lambda x, y: self.bridge.open_wheel.emit(),
                                          on_close=self.bridge.close_wheel.emit)
        self.listener = GlobalListener(self.detector)

        self.bridge.open_wheel.connect(self.wheel.open_at_cursor)
        # The drop reaches the wheel just after the button is released: wait a moment before closing.
        self.bridge.close_wheel.connect(lambda: QTimer.singleShot(200, self.wheel.close_soon))
        self.bridge.finished.connect(self._on_finished)
        self.wheel.dropped.connect(self._run)

        self.tray = QSystemTrayIcon(app_icon(64), app)
        self.tray.setToolTip("Spicchio: drag a file, press Shift, drop it on a slice")
        self.tray.setContextMenu(self._menu())
        self.tray.show()

    def _menu(self) -> QMenu:
        menu = QMenu()
        title = QAction(f"Spicchio {__version__}", menu)
        title.setEnabled(False)
        menu.addAction(title)
        menu.addSeparator()
        enabled = QAction("Enabled", menu)
        enabled.setCheckable(True)
        enabled.setChecked(True)
        enabled.toggled.connect(lambda on: setattr(self.detector, "enabled", on))
        menu.addAction(enabled)
        if autostart.supported():
            start = QAction("Start with Windows", menu)
            start.setCheckable(True)
            start.setChecked(autostart.is_enabled())
            start.toggled.connect(autostart.set_enabled)
            menu.addAction(start)
        how = QAction("How to use", menu)
        how.triggered.connect(self.show_help)
        menu.addAction(how)
        menu.addSeparator()
        quit_ = QAction("Quit", menu)
        quit_.triggered.connect(self.quit)
        menu.addAction(quit_)
        self._menu_ref = menu  # keep a reference, Qt does not own it
        return menu

    def show_help(self) -> None:
        self.toast.show_message("Drag a file and press Shift", "Drop it on a slice. The middle cancels.", ms=6000)

    def start(self) -> None:
        self.listener.start()
        self.show_help()

    def quit(self) -> None:
        self.listener.stop()
        self.tray.hide()
        self.app.quit()

    # ---------------------------------------------------------------- actions
    def _run(self, action: Action, paths: list[Path]) -> None:
        def work() -> None:
            try:
                outputs = action(paths)
                self.bridge.finished.emit(action, outputs, None)
            except ActionError as exc:
                self.bridge.finished.emit(action, None, str(exc))
            except Exception as exc:  # never let a worker crash silently
                self.bridge.finished.emit(action, None, f"Unexpected error: {exc}")

        threading.Thread(target=work, daemon=True).start()

    def _on_finished(self, action: Action, outputs: list[Path] | None, error: str | None) -> None:
        self.wheel.done()
        if error:
            self.toast.show_message(f"{action.label} failed", error, error=True, ms=6000)
        elif outputs:
            title, body, target = _summary(outputs)
            self.toast.show_message(title, body, target=target)


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
