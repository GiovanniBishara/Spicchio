"""Renders the wheel off-screen. Runs where PySide6 is installed (CI); skipped otherwise."""

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from spicchio.geometry import point_at, slices  # noqa: E402
from spicchio.ui.wheel import DEAD, REACH, RING, Wheel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def render(w):
    w.freeze()
    return w.grab().toImage()


def test_chosen_pill_is_tangerine_and_outside_is_transparent(qapp, photo):
    w = Wheel()
    w.set_files([photo])
    w.set_hover(0)
    img = render(w)
    c = w.rect().center()
    s = slices(len(w.actions))
    x, y = point_at(s[0].middle, RING + 6)
    pill = img.pixelColor(round(c.x() + x), round(c.y() + y + 9))     # lower half of the chosen pill
    rest_x, rest_y = point_at(s[2].middle, RING)
    rest = img.pixelColor(round(c.x() + rest_x), round(c.y() + rest_y + 9))
    assert pill.red() > 200 and 60 < pill.green() < 150 and pill.blue() < 90
    assert rest.alpha() > 150 and rest.red() < 90
    assert img.pixelColor(2, 2).alpha() == 0


def test_direction_beyond_the_circle_still_chooses(qapp):
    from spicchio.geometry import slice_at

    assert slice_at(0, -(RING + REACH - 5), 4, DEAD, RING + REACH) == 0
    assert slice_at(RING + 60, 0, 4, DEAD, RING + REACH) == 1
    assert slice_at(10, 10, 4, DEAD, RING + REACH) is None


def test_turning_shows_the_next_side_and_keeps_the_direction(qapp, photo):
    w = Wheel()
    w.set_files([photo])
    assert [name for name, _ in w.sides] == ["convert", "tools", "actions"]
    first = [a.id for a in w.actions]
    w._last_vec = (0.0, -(RING + 10))  # pointer resting straight up
    w.turn(1)
    assert w.side == 1 and [a.id for a in w.actions] != first
    assert w.hover == 0  # still pointing up: the first pill of the new side is chosen
    w.turn(-1)
    assert w.side == 0
