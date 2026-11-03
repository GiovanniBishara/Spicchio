"""Renders the wheel off-screen. Runs where PySide6 is installed (CI); skipped otherwise."""

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from spicchio.actions import actions_for  # noqa: E402
from spicchio.ui.wheel import INNER, OUTER, Wheel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_wheel_paints_slices_and_highlight(qapp, photo):
    w = Wheel()
    w.paths = [photo]
    w.actions = actions_for([photo])
    w.hover = 0
    w._scale = 1.0
    img = w.grab().toImage()
    c = w.rect().center()
    r = (INNER + OUTER) // 2
    top = img.pixelColor(c.x(), c.y() - r)          # slice 0, hovered: orange
    right = img.pixelColor(c.x() + r, c.y() + 20)   # another slice: dark ink
    corner = img.pixelColor(2, 2)                    # outside the ring: transparent
    assert top.red() > 200 and top.green() < 140
    assert right.alpha() > 200 and right.red() < 60
    assert corner.alpha() == 0
