"""Pure geometry of the wheel, kept apart from Qt so it can be unit tested.

Angles are in degrees, measured clockwise from 12 o'clock, because that is how
people read a wheel: slice 0 is at the top, the next one is to its right.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Slice:
    index: int
    start: float  # degrees, clockwise from 12 o'clock
    sweep: float

    @property
    def middle(self) -> float:
        return (self.start + self.sweep / 2) % 360


def slices(n: int) -> list[Slice]:
    """``n`` equal slices, the first one centred on 12 o'clock."""
    if n <= 0:
        return []
    sweep = 360 / n
    return [Slice(i, (i * sweep - sweep / 2) % 360, sweep) for i in range(n)]


def angle_of(dx: float, dy: float) -> float:
    """Clockwise angle from 12 o'clock of a point relative to the centre (screen y grows downwards)."""
    return math.degrees(math.atan2(dx, -dy)) % 360


def slice_at(dx: float, dy: float, n: int, inner: float, outer: float) -> int | None:
    """Index of the slice under the point, or None in the hole / outside the ring."""
    if n <= 0:
        return None
    r = math.hypot(dx, dy)
    if r < inner or r > outer:
        return None
    sweep = 360 / n
    return int(((angle_of(dx, dy) + sweep / 2) % 360) // sweep)


def point_at(angle: float, radius: float) -> tuple[float, float]:
    """Offset from the centre of the point at ``angle`` (clockwise from 12 o'clock) and ``radius``."""
    a = math.radians(angle)
    return radius * math.sin(a), -radius * math.cos(a)


def label_point(s: Slice, radius: float) -> tuple[float, float]:
    """Where to draw a slice's label: on its middle direction, at ``radius`` from the centre."""
    return point_at(s.middle, radius)
