"""
App-wide UI scale ("zoom" of text and of the few fixed-pixel dimensions used
across the panels) -- independent from OS-level display/DPI scaling.

This exists for accessibility: a user on a small/dense monitor (or with
reduced eyesight) can bump the whole UI up, while another user on a large
24" screen can keep it at 100%. It is a per-app preference, not a display
setting.

Usage convention for the rest of the codebase: any panel that needs a fixed
pixel size (a fixed height, an icon size, ...) MUST go through `px()`
instead of hardcoding a number, so it grows/shrinks with the user's chosen
scale. Font sizes are handled separately by `apply_ui_scale()`, which scales
the QApplication's default font -- nearly everything else (layout spacing,
widget padding in the Fusion style) derives from that automatically.

Changing the scale takes effect on next launch (see main_window.py), same
as the language preference -- deliberately not live, to avoid partial
re-layout bugs from widgets that read `px()` only once, at construction
time.
"""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

SCALE_PRESETS: list[int] = [90, 100, 110, 125, 150]
DEFAULT_SCALE = 100

_current_scale = DEFAULT_SCALE
_base_point_size: float | None = None


def apply_ui_scale(app: QApplication, percent: int) -> None:
    """Scale the application's default font to `percent`% of its original
    size. Call once, early, at startup (before building any window), so
    every widget built afterwards picks up the scaled font from the start."""
    global _current_scale, _base_point_size

    if _base_point_size is None:
        _base_point_size = app.font().pointSizeF()

    font: QFont = app.font()
    font.setPointSizeF(_base_point_size * percent / 100.0)
    app.setFont(font)

    _current_scale = percent


def px(base_px: int) -> int:
    """Scale a fixed pixel dimension by the current UI scale. Use this for
    any hardcoded height/width/icon-size instead of a bare literal."""
    return round(base_px * _current_scale / 100.0)
