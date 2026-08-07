"""
Light / dark theme handling.

Three modes are supported, matching the Options menu:
  - "auto"  -> follow the OS setting, and keep following it live if the
              user changes their OS theme while the app is open.
  - "light" -> force light theme regardless of the OS.
  - "dark"  -> force dark theme regardless of the OS.

We build our own QPalette for light/dark instead of relying purely on the
native Qt style, so the app looks consistent across Windows/macOS/Linux and
so we can use the same soft-green accent color as the LaTeX registration
form (LaTeX_Template/event-form-style.sty) for a bit of brand consistency.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# Same accent family as LaTeX_Template/event-form-style.sty
ACCENT = QColor(74, 124, 60)         # "accent" green
ACCENT_SOFT = QColor(233, 241, 224)  # "accentSoft"


def system_theme() -> str:
    """Return 'light' or 'dark' based on the current OS setting."""
    hints = QApplication.styleHints()
    try:
        scheme = hints.colorScheme()
    except AttributeError:
        # Qt < 6.5 has no colorScheme(); fall back to a light default.
        return "light"

    # Qt.ColorScheme is an enum: Unknown, Light, Dark
    if scheme == Qt.ColorScheme.Dark:
        return "dark"
    return "light"


def _light_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(250, 250, 248))
    p.setColor(QPalette.ColorRole.WindowText, QColor(30, 30, 28))
    p.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(243, 246, 240))
    p.setColor(QPalette.ColorRole.Text, QColor(30, 30, 28))
    p.setColor(QPalette.ColorRole.Button, QColor(240, 242, 236))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(30, 30, 28))
    p.setColor(QPalette.ColorRole.Highlight, ACCENT)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.ToolTipBase, ACCENT_SOFT)
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(30, 30, 28))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(150, 150, 145))
    return p


def _dark_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(35, 38, 33))
    p.setColor(QPalette.ColorRole.WindowText, QColor(230, 232, 226))
    p.setColor(QPalette.ColorRole.Base, QColor(28, 30, 26))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(42, 45, 38))
    p.setColor(QPalette.ColorRole.Text, QColor(230, 232, 226))
    p.setColor(QPalette.ColorRole.Button, QColor(48, 51, 44))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(230, 232, 226))
    p.setColor(QPalette.ColorRole.Highlight, ACCENT)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(60, 66, 52))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(230, 232, 226))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(140, 143, 136))
    return p


def resolve_effective_theme(mode: str) -> str:
    """Turn 'auto'/'light'/'dark' into a concrete 'light' or 'dark'."""
    if mode == "auto":
        return system_theme()
    return mode


def apply_theme(app: QApplication, mode: str) -> None:
    """Apply the given theme mode ('auto' | 'light' | 'dark') to the app."""
    effective = resolve_effective_theme(mode)
    app.setStyle("Fusion")  # consistent cross-platform base style
    app.setPalette(_light_palette() if effective == "light" else _dark_palette())
    app.setProperty("effectiveTheme", effective)


def watch_system_theme_changes(app: QApplication, get_mode, on_change) -> None:
    """
    Wire live updates: if the user's theme preference is 'auto' and the OS
    theme changes while the app is running, re-apply immediately.

    get_mode: callable returning the current AppSettings.theme_mode()
    on_change: callable invoked (no args) after re-applying the theme
    """
    hints = app.styleHints()
    if not hasattr(hints, "colorSchemeChanged"):
        return  # Qt < 6.5, no live OS theme signal available

    def _handle(_scheme):
        if get_mode() == "auto":
            apply_theme(app, "auto")
            on_change()

    hints.colorSchemeChanged.connect(_handle)
