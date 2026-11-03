"""Spicchio's visual language, in one place.

Neutral warm ink, warm white text, and a single accent: tangerine.
Everything else is opacity, light and spacing.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont

INK = QColor(16, 15, 19)            # the base of every surface
SURFACE = QColor(28, 27, 33, 238)   # a surface at rest
HAIRLINE = QColor(255, 255, 255, 22)
TEXT = QColor(246, 242, 236)        # warm white
TEXT_SOFT = QColor(246, 242, 236, 140)
ON_ACCENT = QColor(34, 16, 6)       # text on tangerine
TANGERINE_HI = QColor(255, 150, 82)
TANGERINE = QColor(255, 106, 36)
TANGERINE_LO = QColor(236, 78, 16)
DANGER = QColor(229, 72, 77)


def font(px: float, weight: QFont.Weight = QFont.Weight.Normal, display: bool = False) -> QFont:
    f = QFont()
    first = "Segoe UI Variable Display" if display else "Segoe UI Variable Text"
    f.setFamilies([first, "Segoe UI", "Inter", "Helvetica Neue", "Arial"])
    f.setPixelSize(round(px))
    f.setWeight(weight)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    if display:
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 99)
    return f


def mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t), round(a.alpha() + (b.alpha() - a.alpha()) * t))


def with_alpha(c: QColor, a: float) -> QColor:
    out = QColor(c)
    out.setAlphaF(max(0.0, min(1.0, c.alphaF() * a)))
    return out
