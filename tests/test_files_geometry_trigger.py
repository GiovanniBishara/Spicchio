from pathlib import Path

import pytest

from spicchio.files import Kind, kind_of, output_path, unique_path
from spicchio.geometry import angle_of, slice_at, slices
from spicchio.trigger import DragShiftDetector


# --- files ---------------------------------------------------------------

@pytest.mark.parametrize("name,kind", [
    ("a.PNG", Kind.IMAGE), ("b.jpeg", Kind.IMAGE), ("c.pdf", Kind.PDF), ("d.MOV", Kind.VIDEO),
    ("e.flac", Kind.AUDIO), ("f.csv", Kind.DATA), ("g.docx", Kind.OTHER), ("noext", Kind.OTHER),
])
def test_kind_of(tmp_path: Path, name: str, kind: Kind):
    assert kind_of(tmp_path / name) is kind


def test_unique_path_never_overwrites(tmp_path: Path):
    target = tmp_path / "photo.pdf"
    assert unique_path(target) == target
    target.touch()
    assert unique_path(target) == tmp_path / "photo (1).pdf"
    (tmp_path / "photo (1).pdf").touch()
    assert unique_path(target) == tmp_path / "photo (2).pdf"


def test_output_path_tag(tmp_path: Path):
    assert output_path(tmp_path / "photo.jpg", ".jpg", "compressed").name == "photo-compressed.jpg"
    assert output_path(tmp_path / "photo.jpg", ".pdf").name == "photo.pdf"


# --- geometry ------------------------------------------------------------

def test_angles_are_clockwise_from_noon():
    assert angle_of(0, -1) == pytest.approx(0)      # up
    assert angle_of(1, 0) == pytest.approx(90)      # right
    assert angle_of(0, 1) == pytest.approx(180)     # down
    assert angle_of(-1, 0) == pytest.approx(270)    # left


def test_four_slices_follow_the_compass():
    n, inner, outer = 4, 30, 150
    assert slice_at(0, -100, n, inner, outer) == 0   # up
    assert slice_at(100, 0, n, inner, outer) == 1    # right
    assert slice_at(0, 100, n, inner, outer) == 2    # down
    assert slice_at(-100, 0, n, inner, outer) == 3   # left


def test_hole_and_outside_select_nothing():
    assert slice_at(5, 5, 6, 30, 150) is None
    assert slice_at(300, 0, 6, 30, 150) is None


def test_first_slice_is_centred_on_top():
    s = slices(8)
    assert s[0].middle == pytest.approx(0)
    assert s[2].middle == pytest.approx(90)
    # just left and just right of 12 o'clock both belong to slice 0
    assert slice_at(-10, -100, 8, 30, 150) == 0
    assert slice_at(10, -100, 8, 30, 150) == 0


# --- trigger -------------------------------------------------------------

class Recorder:
    def __init__(self):
        self.events = []

    def open(self, x, y):
        self.events.append(("open", x, y))

    def close(self):
        self.events.append(("close",))


def make():
    r = Recorder()
    return DragShiftDetector(on_open=r.open, on_close=r.close), r


def test_shift_while_dragging_opens_under_cursor():
    d, r = make()
    d.press(100, 100)
    d.move(140, 120)
    d.shift_down()
    assert r.events == [("open", 140, 120)]
    d.release()
    assert r.events[-1] == ("close",)


def test_shift_without_drag_does_nothing():
    d, r = make()
    d.shift_down()          # no button
    d.shift_up()
    d.press(10, 10)
    d.move(14, 12)          # below threshold: a click, not a drag
    d.shift_down()
    assert r.events == []


def test_key_repeat_and_escape():
    d, r = make()
    d.press(0, 0)
    d.move(50, 0)
    d.shift_down()
    d.shift_down()          # auto-repeat must not reopen
    assert len(r.events) == 1
    d.escape()
    assert r.events[-1] == ("close",)
    d.release()             # already closed: no second close
    assert r.events.count(("close",)) == 1


def test_disabled_detector_stays_closed():
    d, r = make()
    d.enabled = False
    d.press(0, 0)
    d.move(50, 0)
    d.shift_down()
    assert r.events == []
