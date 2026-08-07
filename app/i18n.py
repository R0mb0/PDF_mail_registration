"""
Language detection and switching.

Source strings in the UI are written in Italian (wrapped in self.tr(...)),
which is this app's "home" language. The other five languages are provided
as compiled Qt translation files (.qm, built from .ts files with Qt
Linguist) in translations/. Until those are produced (later polish phase),
selecting a language other than Italian simply falls back to the Italian
source strings -- the switching mechanism itself is already fully wired.

Supported languages: Italian, English, French, German, Spanish, Portuguese.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QLocale, QTranslator
from PySide6.QtWidgets import QApplication

TRANSLATIONS_DIR = Path(__file__).parent / "translations"


@dataclass(frozen=True)
class Language:
    code: str    # ISO 639-1
    label: str   # name shown in the Options > Language menu, in its own language


SUPPORTED_LANGUAGES: list[Language] = [
    Language("it", "Italiano"),
    Language("en", "English"),
    Language("fr", "Français"),
    Language("de", "Deutsch"),
    Language("es", "Español"),
    Language("pt", "Português"),
]

FALLBACK_LANGUAGE = "it"
_SUPPORTED_CODES = {lang.code for lang in SUPPORTED_LANGUAGES}


def detect_system_language() -> str:
    """Return the best-matching supported language code for the OS locale."""
    system_code = QLocale.system().name().split("_")[0].lower()
    if system_code in _SUPPORTED_CODES:
        return system_code
    return FALLBACK_LANGUAGE


def resolve_effective_language(pref: str) -> str:
    """Turn 'auto'/<code> into a concrete supported language code."""
    if pref == "auto":
        return detect_system_language()
    if pref in _SUPPORTED_CODES:
        return pref
    return FALLBACK_LANGUAGE


class TranslationManager:
    """Loads/unloads the Qt translator for the active language."""

    def __init__(self, app: QApplication) -> None:
        self._app = app
        self._translator = QTranslator(app)
        self._installed = False

    def apply(self, pref: str) -> str:
        """Apply the given language preference ('auto' | code). Returns the
        effective language code actually applied."""
        effective = resolve_effective_language(pref)

        if self._installed:
            self._app.removeTranslator(self._translator)
            self._installed = False

        if effective != FALLBACK_LANGUAGE:
            qm_path = TRANSLATIONS_DIR / f"registration_app_{effective}.qm"
            if qm_path.exists() and self._translator.load(str(qm_path)):
                self._app.installTranslator(self._translator)
                self._installed = True
            # else: no compiled translation yet -> silently fall back to the
            # Italian source strings (expected for now, see module docstring).

        return effective
