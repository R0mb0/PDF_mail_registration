"""
Main application window: menu bar (File / Edit / View / Options) + the four
panels arranged in nested, freely-resizable splitters:

    +-------------------------------------------+
    |  file browser   |     PDF preview          |
    |  (+ classific.  |     (1 or 2 panes)        |
    |   strip)         |                          |
    +-------------------------------------------+
    |     filter / formula bar + chip stack       |
    +-------------------------------------------+
    |                 data table                   |
    +-------------------------------------------+

Every internal border is a QSplitter handle, so the user can drag-resize any
panel, matching the spec ("se con il mouse si tocca un lato o un bordo, si
può ridimensionare l'elemento"). Show/hide per panel is driven by the View
menu (checkable actions bound to panel.setVisible()).

Phase 1 scope: the shell only. Every action below is created and enabled/
disabled/checked according to spec, but most are still no-ops (marked with
a "# Phase N" comment) until their phase lands.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QWidget,
)

from i18n import SUPPORTED_LANGUAGES, TranslationManager
from panels.file_browser_panel import FileBrowserPanel
from panels.formula_bar_panel import FormulaBarPanel
from panels.preview_panel import PreviewPanel
from panels.table_panel import TablePanel
from scaling import SCALE_PRESETS
from settings import AppSettings
from theme import apply_theme


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: AppSettings,
        translation_manager: TranslationManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._translations = translation_manager
        self._folder_open = False  # Phase 2 sets this from real folder state

        self.setWindowTitle(self.tr("Gestione Iscrizioni"))
        self.resize(1280, 820)

        self._build_panels()
        self._build_central_layout()
        self._build_menu_bar()

    # ------------------------------------------------------------------ UI --
    def _build_panels(self) -> None:
        self.file_browser_panel = FileBrowserPanel()
        self.preview_panel = PreviewPanel()
        self.formula_bar_panel = FormulaBarPanel()
        self.table_panel = TablePanel()

    def _build_central_layout(self) -> None:
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.addWidget(self.file_browser_panel)
        top_splitter.addWidget(self.preview_panel)
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 2)

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(self.formula_bar_panel)
        main_splitter.addWidget(self.table_panel)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 3)

        self._top_splitter = top_splitter
        self._main_splitter = main_splitter
        self.setCentralWidget(main_splitter)

    # ------------------------------------------------------------- Menu bar --
    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        self._build_file_menu(menu_bar)
        self._build_edit_menu(menu_bar)
        self._build_view_menu(menu_bar)
        self._build_options_menu(menu_bar)

    def _build_file_menu(self, menu_bar) -> None:
        menu = menu_bar.addMenu(self.tr("&File"))

        self.action_open_folder = QAction(self.tr("Apri cartella"), self)
        self.action_open_folder.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open_folder.triggered.connect(self._on_open_folder)  # Phase 2
        menu.addAction(self.action_open_folder)

        self.action_close_folder = QAction(self.tr("Chiudi cartella"), self)
        self.action_close_folder.setEnabled(False)
        self.action_close_folder.triggered.connect(self._on_close_folder)  # Phase 2
        menu.addAction(self.action_close_folder)

        menu.addSeparator()

        self.action_new_instance = QAction(self.tr("Apri nuova istanza"), self)
        self.action_new_instance.triggered.connect(self._on_new_instance)
        menu.addAction(self.action_new_instance)

        menu.addSeparator()

        self.action_quit = QAction(self.tr("Esci"), self)
        self.action_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self.action_quit.triggered.connect(QApplication.instance().quit)
        menu.addAction(self.action_quit)

        # Keep the two folder actions mutually exclusive, per spec: "se una
        # cartella è già aperta il tasto si disabilita".
        self.file_browser_panel.open_folder_button.setEnabled(
            not self._folder_open
        )
        self.file_browser_panel.close_folder_button.setEnabled(self._folder_open)
        self.file_browser_panel.open_folder_button.clicked.connect(
            self._on_open_folder
        )
        self.file_browser_panel.close_folder_button.clicked.connect(
            self._on_close_folder
        )

    def _build_edit_menu(self, menu_bar) -> None:
        menu = menu_bar.addMenu(self.tr("&Modifica"))

        def _add(label: str, shortcut, slot_name: str) -> QAction:
            action = QAction(label, self)
            if shortcut is not None:
                action.setShortcut(shortcut)
            action.triggered.connect(lambda: self._not_yet_implemented(slot_name))
            menu.addAction(action)
            return action

        self.action_cut = _add(self.tr("Taglia"), QKeySequence.StandardKey.Cut, "cut")
        self.action_copy = _add(self.tr("Copia"), QKeySequence.StandardKey.Copy, "copy")
        self.action_paste = _add(
            self.tr("Incolla"), QKeySequence.StandardKey.Paste, "paste"
        )
        menu.addSeparator()
        self.action_select_all = _add(
            self.tr("Seleziona tutto"), QKeySequence.StandardKey.SelectAll, "select_all"
        )
        self.action_select_none = _add(
            self.tr("Seleziona niente"), QKeySequence("Ctrl+Shift+A"), "select_none"
        )
        menu.addSeparator()
        # Phase 4: rides on the filter-pipeline history, not a generic
        # text-editing undo stack.
        self.action_undo = _add(self.tr("Indietro"), QKeySequence.StandardKey.Undo, "undo")
        self.action_redo = _add(self.tr("Avanti"), QKeySequence.StandardKey.Redo, "redo")

    def _build_view_menu(self, menu_bar) -> None:
        menu = menu_bar.addMenu(self.tr("&Visualizza"))

        def _toggle_action(label: str, widget: QWidget) -> QAction:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(widget.setVisible)
            menu.addAction(action)
            return action

        self.action_view_file_browser = _toggle_action(
            self.tr("Esplora cartella"), self.file_browser_panel
        )
        self.action_view_preview = _toggle_action(
            self.tr("Anteprima PDF"), self.preview_panel
        )
        self.action_view_formula_bar = _toggle_action(
            self.tr("Barra dei filtri"), self.formula_bar_panel
        )
        self.action_view_table = _toggle_action(
            self.tr("Tabella dati"), self.table_panel
        )
        menu.addSeparator()

        # Secondary PDF preview pane close/reopen, mirrored from the "✕"
        # button on the pane itself (Phase 3).
        self.action_view_secondary_preview = QAction(
            self.tr("Seconda anteprima PDF"), self
        )
        self.action_view_secondary_preview.setCheckable(True)
        self.action_view_secondary_preview.setChecked(False)
        self.action_view_secondary_preview.toggled.connect(
            self.preview_panel.secondary_slot.setVisible
        )
        menu.addAction(self.action_view_secondary_preview)

    def _build_options_menu(self, menu_bar) -> None:
        menu = menu_bar.addMenu(self.tr("&Opzioni"))

        theme_menu = menu.addMenu(self.tr("Tema"))
        from PySide6.QtGui import QActionGroup

        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        self._theme_actions: dict[str, QAction] = {}
        for mode, label in (
            ("auto", self.tr("Automatico (segui il sistema)")),
            ("light", self.tr("Chiaro")),
            ("dark", self.tr("Scuro")),
        ):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(self._settings.theme_mode() == mode)
            action.triggered.connect(lambda _checked, m=mode: self._set_theme(m))
            theme_group.addAction(action)
            theme_menu.addAction(action)
            self._theme_actions[mode] = action

        language_menu = menu.addMenu(self.tr("Lingua"))
        language_group = QActionGroup(self)
        language_group.setExclusive(True)
        self._language_actions: dict[str, QAction] = {}

        auto_action = QAction(self.tr("Automatico (segui il sistema)"), self)
        auto_action.setCheckable(True)
        auto_action.setChecked(self._settings.language() == "auto")
        auto_action.triggered.connect(lambda: self._set_language("auto"))
        language_group.addAction(auto_action)
        language_menu.addAction(auto_action)
        self._language_actions["auto"] = auto_action
        language_menu.addSeparator()

        for lang in SUPPORTED_LANGUAGES:
            action = QAction(lang.label, self)
            action.setCheckable(True)
            action.setChecked(self._settings.language() == lang.code)
            action.triggered.connect(
                lambda _checked, code=lang.code: self._set_language(code)
            )
            language_group.addAction(action)
            language_menu.addAction(action)
            self._language_actions[lang.code] = action

        # --- text/UI scale ----------------------------------------------------
        # Accessibility: independent from OS display scaling. Lets each user
        # adjust to their own screen and eyesight rather than one fixed size
        # for everyone.
        scale_menu = menu.addMenu(self.tr("Dimensione testo"))
        scale_group = QActionGroup(self)
        scale_group.setExclusive(True)
        self._scale_actions: dict[int, QAction] = {}
        current_scale = self._settings.ui_scale_percent()
        for percent in SCALE_PRESETS:
            label = "100% (predefinito)" if percent == 100 else f"{percent}%"
            action = QAction(self.tr(label), self)
            action.setCheckable(True)
            action.setChecked(current_scale == percent)
            action.triggered.connect(
                lambda _checked, p=percent: self._set_ui_scale(p)
            )
            scale_group.addAction(action)
            scale_menu.addAction(action)
            self._scale_actions[percent] = action

    # -------------------------------------------------------------- Slots --
    def _on_open_folder(self) -> None:
        self._not_yet_implemented("open_folder")  # Phase 2

    def _on_close_folder(self) -> None:
        self._not_yet_implemented("close_folder")  # Phase 2

    def _on_new_instance(self) -> None:
        # Launch a fresh, independent process of this same app with no
        # folder pre-opened, per spec ("apre una nuova finestra che però non
        # possiede una cartella già aperta").
        import subprocess
        from pathlib import Path

        main_script = Path(__file__).with_name("main.py")
        subprocess.Popen([sys.executable, str(main_script)])

    def _set_theme(self, mode: str) -> None:
        self._settings.set_theme_mode(mode)
        apply_theme(QApplication.instance(), mode)

    def _set_language(self, pref: str) -> None:
        self._settings.set_language(pref)
        # Applying a language change live (re-translating an already-built
        # UI) is handled properly starting Phase 7; for now we persist the
        # preference and ask for a restart, which is honest and simple.
        self._show_restart_required(self.tr("Lingua"))

    def _set_ui_scale(self, percent: int) -> None:
        self._settings.set_ui_scale_percent(percent)
        # Same reasoning as language: fonts and scaling.px() values are read
        # once at startup by every widget, so a clean restart avoids partial
        # re-layout glitches instead of trying to live-rescale everything.
        self._show_restart_required(self.tr("Dimensione testo"))

    def _show_restart_required(self, title: str) -> None:
        QMessageBox.information(
            self,
            title,
            self.tr(
                "La modifica verrà applicata al prossimo avvio "
                "dell'applicazione."
            ),
        )

    def _not_yet_implemented(self, feature: str) -> None:
        QMessageBox.information(
            self,
            self.tr("In arrivo"),
            self.tr("\"{feature}\" sarà disponibile in una prossima fase.").format(
                feature=feature
            ),
        )
