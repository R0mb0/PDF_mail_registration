"""
Persisted user preferences.

Wraps QSettings so the rest of the app never touches the registry / plist /
ini file directly. Covers two groups of preferences:

  - "appearance/*": theme mode, language, UI scale -- set from the Options
    menu, all default to "auto"/100% until the user overrides them.
  - "window/*" and "view/*": window geometry, splitter (panel) proportions,
    and per-panel visibility -- captured automatically on close and restored
    on next launch, so the app reopens exactly as the user left it. These
    are not user-facing "settings" in a menu; they are saved/loaded by
    MainWindow itself (see main_window.py _restore_window_state /
    closeEvent).
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSettings

ORG_NAME = "PDF_mail_registration"
APP_NAME = "RegistrationManager"

THEME_KEY = "appearance/theme_mode"     # "auto" | "light" | "dark"
LANGUAGE_KEY = "appearance/language"    # "auto" | ISO 639-1 code, e.g. "it", "en"
UI_SCALE_KEY = "appearance/ui_scale"    # int percent, e.g. 100, 125, 150

DEFAULT_THEME_MODE = "auto"
DEFAULT_LANGUAGE = "auto"
DEFAULT_UI_SCALE = 100

WINDOW_GEOMETRY_KEY = "window/geometry"
WINDOW_MAXIMIZED_KEY = "window/maximized"
MAIN_SPLITTER_STATE_KEY = "window/main_splitter_state"
TOP_SPLITTER_STATE_KEY = "window/top_splitter_state"

# Panel visibility (View menu). All default to visible except the secondary
# PDF preview pane, which only appears once a second document is opened.
VIEW_FILE_BROWSER_KEY = "view/file_browser_visible"
VIEW_PREVIEW_KEY = "view/preview_visible"
VIEW_FORMULA_BAR_KEY = "view/formula_bar_visible"
VIEW_TABLE_KEY = "view/table_visible"
VIEW_SECONDARY_PREVIEW_KEY = "view/secondary_preview_visible"


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

    # --- window geometry + splitter proportions ------------------------------
    def window_geometry(self) -> QByteArray | None:
        value = self._settings.value(WINDOW_GEOMETRY_KEY)
        return value if isinstance(value, QByteArray) else None

    def set_window_geometry(self, data: QByteArray) -> None:
        self._settings.setValue(WINDOW_GEOMETRY_KEY, data)

    def window_maximized(self) -> bool:
        return bool(self._settings.value(WINDOW_MAXIMIZED_KEY, False, type=bool))

    def set_window_maximized(self, maximized: bool) -> None:
        self._settings.setValue(WINDOW_MAXIMIZED_KEY, maximized)

    def main_splitter_state(self) -> QByteArray | None:
        value = self._settings.value(MAIN_SPLITTER_STATE_KEY)
        return value if isinstance(value, QByteArray) else None

    def set_main_splitter_state(self, data: QByteArray) -> None:
        self._settings.setValue(MAIN_SPLITTER_STATE_KEY, data)

    def top_splitter_state(self) -> QByteArray | None:
        value = self._settings.value(TOP_SPLITTER_STATE_KEY)
        return value if isinstance(value, QByteArray) else None

    def set_top_splitter_state(self, data: QByteArray) -> None:
        self._settings.setValue(TOP_SPLITTER_STATE_KEY, data)

    # --- panel visibility (View menu) -----------------------------------------
    def panel_visible(self, key: str, default: bool) -> bool:
        return bool(self._settings.value(key, default, type=bool))

    def set_panel_visible(self, key: str, visible: bool) -> None:
        self._settings.setValue(key, visible)
