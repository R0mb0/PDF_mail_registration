"""
Persisted user preferences.

Wraps QSettings so the rest of the app never touches the registry / plist /
ini file directly. Two preferences are stored here for now: the theme mode
and the language code. Both default to "auto" (follow the OS) until the
user overrides them from the Options menu.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

ORG_NAME = "PDF_mail_registration"
APP_NAME = "RegistrationManager"

THEME_KEY = "appearance/theme_mode"     # "auto" | "light" | "dark"
LANGUAGE_KEY = "appearance/language"    # "auto" | ISO 639-1 code, e.g. "it", "en"
UI_SCALE_KEY = "appearance/ui_scale"    # int percent, e.g. 100, 125, 150

DEFAULT_THEME_MODE = "auto"
DEFAULT_LANGUAGE = "auto"
DEFAULT_UI_SCALE = 100


class AppSettings:
    """Thin, typed wrapper around QSettings for this application's prefs."""

    def __init__(self) -> None:
        self._settings = QSettings(ORG_NAME, APP_NAME)

    # --- theme -----------------------------------------------------------
    def theme_mode(self) -> str:
        return str(self._settings.value(THEME_KEY, DEFAULT_THEME_MODE))

    def set_theme_mode(self, mode: str) -> None:
        assert mode in ("auto", "light", "dark")
        self._settings.setValue(THEME_KEY, mode)

    # --- language ----------------------------------------------------------
    def language(self) -> str:
        return str(self._settings.value(LANGUAGE_KEY, DEFAULT_LANGUAGE))

    def set_language(self, code: str) -> None:
        self._settings.setValue(LANGUAGE_KEY, code)

    # --- UI scale ("zoom" of text and fixed-size elements) ------------------
    def ui_scale_percent(self) -> int:
        return int(self._settings.value(UI_SCALE_KEY, DEFAULT_UI_SCALE))

    def set_ui_scale_percent(self, percent: int) -> None:
        self._settings.setValue(UI_SCALE_KEY, percent)
