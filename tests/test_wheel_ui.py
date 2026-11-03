"""Renders the wheel off-screen. Runs where PySide6 is installed (CI); skipped otherwise."""

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from spicchio.ui.wheel import INNER, OUTER, Wheel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_wheel_paints_slices_and_highlight(qapp, photo):
    w = Wheel()
    w.set_files([photo])
    w.set_hover(0, instant=True)
    w._open = 1.0
    img = w.grab().toImage()
    c = w.rect().center()
    r = (INNER + OUTER) // 2
    top = img.pixelColor(c.x() + 22, c.y() - r)      # slice 0, chosen: orange
    side = img.pixelColor(c.x() + r, c.y() + 30)      # another slice: dark glass
    corner = img.pixelColor(2, 2)                     # outside the reach: transparent
    assert top.red() > 200 and top.green() < 150
    assert side.alpha() > 200 and side.red() < 70
    assert corner.alpha() == 0


def test_direction_beyond_the_ring_still_selects(qapp, photo):
    from spicchio.geometry import slice_at
    from spicchio.ui.wheel import REACH

    n = 4
    assert slice_at(0, -(OUTER + REACH - 5), n, INNER, OUTER + REACH) == 0
    assert slice_at(OUTER + 60, 0, n, INNER, OUTER + REACH) == 1
