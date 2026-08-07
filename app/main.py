"""
Entry point.

    python main.py

Wires together settings (QSettings-backed preferences), the translation
manager (language auto-detect + manual override) and the theme (light/dark
auto-detect + manual override + live OS-change tracking), then shows the
main window.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from i18n import TranslationManager, resolve_effective_language
from main_window import MainWindow
from scaling import apply_ui_scale
from settings import AppSettings
from theme import apply_theme, watch_system_theme_changes


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("PDF_mail_registration")
    app.setApplicationName("RegistrationManager")

    settings = AppSettings()

    # Applied before anything else is built, so every widget constructed
    # afterwards (including MainWindow and all panels) picks up the scaled
    # font and reads the correct scaling.px() values from the start.
    apply_ui_scale(app, settings.ui_scale_percent())

    translations = TranslationManager(app)
    effective_language = translations.apply(settings.language())

    apply_theme(app, settings.theme_mode())
    watch_system_theme_changes(
        app,
        get_mode=settings.theme_mode,
        on_change=lambda: None,  # nothing extra to refresh yet in Phase 1
    )

    window = MainWindow(settings, translations)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
