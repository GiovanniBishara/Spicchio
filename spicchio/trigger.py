"""When should the wheel appear?

Rule: the left button is held, the mouse has moved more than a few pixels
(so the user is dragging something), and Shift is pressed. The wheel opens
under the cursor; releasing the button closes it (after the drop has been
handled by the wheel window itself). While it is open, Shift again, Tab or the
mouse wheel turn it to its next side (Convert, Tools, Actions).

The logic is a small state machine fed with plain events, so it can be
tested without a mouse. ``GlobalListener`` connects it to the real mouse
and keyboard through pynput.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

DRAG_THRESHOLD = 12  # px the pointer must travel before a press counts as a drag


@dataclass
class DragShiftDetector:
    on_open: Callable[[int, int], None]
    on_close: Callable[[], None]
    on_turn: Callable[[int], None] = lambda step: None  # next/previous side of the wheel
    threshold: float = DRAG_THRESHOLD
    enabled: bool = True

    _down_at: tuple[int, int] | None = None
    _dragging: bool = False
    _open: bool = False
    _pos: tuple[int, int] = (0, 0)
    _shift_held: bool = False

    # --- mouse ---
    def press(self, x: int, y: int) -> None:
        self._down_at = (x, y)
        self._dragging = False
        self._pos = (x, y)

    def move(self, x: int, y: int) -> None:
        self._pos = (x, y)
        if self._down_at and not self._dragging and math.dist(self._down_at, (x, y)) >= self.threshold:
            self._dragging = True

    def release(self) -> None:
        self._down_at = None
        self._dragging = False
        if self._open:
            self._open = False
            self.on_close()

    # --- keyboard ---
    def shift_down(self) -> None:
        if self._shift_held:
            return  # ignore key repeat while Shift stays down
        self._shift_held = True
        if not self.enabled or not self._dragging:
            return
        if self._open:
            self.on_turn(1)  # Shift again: turn the wheel to its next side
        else:
            self._open = True
            self.on_open(*self._pos)

    def shift_up(self) -> None:
        self._shift_held = False

    def tab(self) -> None:
        if self._open:
            self.on_turn(1)

    def scroll(self, dy: int) -> None:
        if self._open and dy:
            self.on_turn(-1 if dy > 0 else 1)

    def escape(self) -> None:
        if self._open:
            self._open = False
            self.on_close()

    @property
    def is_open(self) -> bool:
        return self._open


class GlobalListener:
    """Feeds a DragShiftDetector from system-wide mouse and keyboard hooks (pynput)."""

    def __init__(self, detector: DragShiftDetector) -> None:
        self.detector = detector
        self._mouse = None
        self._keyboard = None

    def start(self) -> None:
        from pynput import keyboard, mouse

        d = self.detector

        def on_click(x, y, button, pressed):
            if button != mouse.Button.left:
                return
            d.press(int(x), int(y)) if pressed else d.release()

        def on_move(x, y):
            d.move(int(x), int(y))

        def on_scroll(x, y, dx, dy):
            d.scroll(dy)

        shifts = {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r}

        def on_press(key):
            if key in shifts:
                d.shift_down()
            elif key == keyboard.Key.tab:
                d.tab()
            elif key == keyboard.Key.esc:
                d.escape()

        def on_release(key):
            if key in shifts:
                d.shift_up()

        self._mouse = mouse.Listener(on_click=on_click, on_move=on_move, on_scroll=on_scroll)
        self._keyboard = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._mouse.start()
        self._keyboard.start()

    def stop(self) -> None:
        for listener in (self._mouse, self._keyboard):
            if listener is not None:
                listener.stop()
