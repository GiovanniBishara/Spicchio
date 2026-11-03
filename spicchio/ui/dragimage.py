"""Hide the big file preview Windows draws next to the cursor while the wheel is in use.

During a drag, the shell shows a thumbnail in a top-level window of class
``SysDragImage``. Over the wheel it only gets in the way, so we hide it while
the pointer is on the wheel and show it again when the pointer leaves.
Everything here is best effort: if the window is not found, nothing happens.
"""

from __future__ import annotations

import sys

_hidden: list[int] = []

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _ENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _SW_HIDE, _SW_SHOWNA = 0, 8

    def _drag_windows() -> list[int]:
        found: list[int] = []

        def visit(hwnd, _lparam):
            buf = ctypes.create_unicode_buffer(32)
            _user32.GetClassNameW(hwnd, buf, 32)
            if buf.value == "SysDragImage" and _user32.IsWindowVisible(hwnd):
                found.append(hwnd)
            return True

        _user32.EnumWindows(_ENUM(visit), 0)
        return found

    def hide() -> None:
        try:
            for hwnd in _drag_windows():
                _user32.ShowWindow(hwnd, _SW_HIDE)
                if hwnd not in _hidden:
                    _hidden.append(hwnd)
        except Exception:
            pass

    def restore() -> None:
        try:
            while _hidden:
                hwnd = _hidden.pop()
                if _user32.IsWindow(hwnd):
                    _user32.ShowWindow(hwnd, _SW_SHOWNA)
        except Exception:
            _hidden.clear()

else:

    def hide() -> None:
        pass

    def restore() -> None:
        pass
