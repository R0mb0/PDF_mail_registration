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

As of Phase 6: folder open/close, PDF field extraction, the PDF preview,
the filter pipeline (Excel-subset / SQL filters, manual-edit chips,
undo/redo), the colored document classification and the in-app field
editor (double-click a file -> edit its AcroForm fields -> save re-runs
extraction) are all fully wired.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QWidget,
)

from core.classification import classify_folder
from core.extraction_worker import ExtractionWorker
from core.filter_pipeline import FilterPipeline, FilterPipelineError
from core.pdf_extraction import SOURCE_FILE_COLUMN, ExtractionResult
from dialogs.field_editor_dialog import FieldEditorDialog
from dialogs.progress_dialog import AnalysisProgressDialog
from i18n import SUPPORTED_LANGUAGES, TranslationManager
from panels.file_browser_panel import FileBrowserPanel
from panels.formula_bar_panel import ChipInfo, FormulaBarPanel
from panels.preview_panel import PreviewPanel
from panels.table_panel import TablePanel
from scaling import SCALE_PRESETS
from settings import (
    AppSettings,
    VIEW_FILE_BROWSER_KEY,
    VIEW_FORMULA_BAR_KEY,
    VIEW_PREVIEW_KEY,
    VIEW_SECONDARY_PREVIEW_KEY,
    VIEW_TABLE_KEY,
)
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
        self._folder_open = False
        self._current_folder: Path | None = None
        self._pipeline = FilterPipeline()

        self.setWindowTitle(self.tr("Gestione Iscrizioni"))
        self.resize(1280, 820)

        self._build_panels()
        self._build_central_layout()
        self._build_menu_bar()
        self._wire_preview()
        self._wire_filters()
        self._restore_window_state()

    # ------------------------------------------------------------------ UI --
    def _build_panels(self) -> None:
        self.file_browser_panel = FileBrowserPanel()
        self.preview_panel = PreviewPanel()
        self.formula_bar_panel = FormulaBarPanel()
        self.table_panel = TablePanel()

    def _wire_preview(self) -> None:
        # Single click in the file browser -> preview (FIFO slot logic
        # lives in PreviewPanel.open_pdf). Double click -> the in-app field
        # editor overlay (Phase 6) -- never the system's default PDF app.
        self.file_browser_panel.file_single_clicked.connect(
            self.preview_panel.open_pdf
        )
        self.file_browser_panel.file_double_clicked.connect(
            self._on_file_double_clicked
        )
        # Clicking a colored classification-strip button opens that PDF in
        # preview too -- the highlighting in the browser itself is already
        # handled inside FileBrowserPanel before it emits this signal.
        self.file_browser_panel.classification_file_clicked.connect(
            self.preview_panel.open_pdf
        )
        # The secondary pane's own "✕" and the View menu's checkbox must
        # stay in sync: closing via "✕" also unchecks the menu action,
        # which in turn hides the pane through the toggled connection
        # already set up in _build_view_menu.
        self.preview_panel.secondary_slot.close_button.clicked.connect(
            self._on_close_secondary_preview
        )
        # Deleting a file (from the browser, Phase 5) is a folder-contents
        # change -- re-run the same full scan, same as opening a fresh PDF
        # into the folder would require.
        self.file_browser_panel.folder_contents_changed.connect(
            self._on_folder_contents_changed
        )

    def _on_close_secondary_preview(self) -> None:
        self.preview_panel.close_secondary()
        self.action_view_secondary_preview.setChecked(False)

    def _on_folder_contents_changed(self) -> None:
        if self._current_folder is not None:
            self._run_extraction(self._current_folder)

    def _on_file_double_clicked(self, file_path: str) -> None:
        # Modal by construction (QDialog.exec()): editing one PDF while the
        # rest of the app silently keeps running underneath would risk the
        # user acting on a table that's about to be invalidated anyway.
        dialog = FieldEditorDialog(Path(file_path), self)
        if dialog.exec() == FieldEditorDialog.DialogCode.Accepted:
            # Saving changed the PDF on disk -- per spec this invalidates
            # the whole downstream table state, so re-run the same full
            # scan rather than trying to patch just this one row.
            self._on_folder_contents_changed()

    def _wire_filters(self) -> None:
        self.table_panel.set_edit_callback(self._on_cell_edited)
        self.formula_bar_panel.run_button.clicked.connect(self._on_run_filter)

    # ------------------------------------------------- Filter pipeline glue --
    # These four methods are the only bridge between the Qt layer and
    # core/filter_pipeline.py: every action that changes the table's state
    # (running a filter, editing a cell, undo, redo) goes through the
    # pipeline first and then re-renders from its current_dataframe(), so
    # the table, the chip stack and the undo/redo action states can never
    # drift out of sync with each other.
    def _on_run_filter(self) -> None:
        mode = self.formula_bar_panel.selected_mode()
        if mode is None:
            QMessageBox.warning(
                self,
                self.tr("Nessuna modalità selezionata"),
                self.tr("Seleziona prima la modalità Excel o SQL."),
            )
            return

        expression = self.formula_bar_panel.expression_text()
        try:
            self._pipeline.apply_expression_filter(mode, expression)
        except FilterPipelineError as exc:
            QMessageBox.warning(self, self.tr("Errore nel filtro"), exc.message)
            return

        self.formula_bar_panel.clear_expression()
        self._refresh_table_and_chips()

    def _on_cell_edited(self, row_key: str, column: str, value: str) -> None:
        self._pipeline.record_manual_edit(row_key, column, value)
        self._refresh_table_and_chips()

    def _on_remove_last_filter(self) -> None:
        # Same operation whether triggered by the last chip's "✕" or by
        # Ctrl+Z -- see core/filter_pipeline.py's docstring for why.
        self._pipeline.remove_last_step()
        self._refresh_table_and_chips()

    def _on_redo_filter(self) -> None:
        self._pipeline.redo()
        self._refresh_table_and_chips()

    def _refresh_table_and_chips(self) -> None:
        self.table_panel.set_dataframe(self._pipeline.current_dataframe())
        self._refresh_chips()
        self.action_undo.setEnabled(self._pipeline.can_undo())
        self.action_redo.setEnabled(self._pipeline.can_redo())

    def _refresh_chips(self) -> None:
        steps = self._pipeline.steps
        chips: list[ChipInfo] = []
        for index, step in enumerate(steps):
            is_last = index == len(steps) - 1
            label = self.tr("Filtro {n}").format(n=index + 1)
            if step.kind == "expression":
                tooltip = f"{(step.mode or '').upper()}: {step.expression}"
            else:
                tooltip = self.tr("Modifiche manuali alle celle ({count})").format(
                    count=len(step.edits)
                )
            chips.append(ChipInfo(label=label, tooltip=tooltip, removable=is_last))
        self.formula_bar_panel.set_chips(chips, self._on_remove_last_filter)

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
        # Rides on the filter-pipeline history (core/filter_pipeline.py),
        # not a generic text-editing undo stack: Ctrl+Z removes the last
        # filter chip (same operation as clicking its "✕"), Ctrl+Y/Shift+
        # Ctrl+Z brings it back. Both start disabled -- nothing to undo/
        # redo until a folder is open and at least one filter/edit exists.
        self.action_undo = QAction(self.tr("Indietro"), self)
        self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.action_undo.setEnabled(False)
        self.action_undo.triggered.connect(self._on_remove_last_filter)
        menu.addAction(self.action_undo)

        self.action_redo = QAction(self.tr("Avanti"), self)
        self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.action_redo.setEnabled(False)
        self.action_redo.triggered.connect(self._on_redo_filter)
        menu.addAction(self.action_redo)

    def _build_view_menu(self, menu_bar) -> None:
        # Initial checked state is seeded from the last saved session
        # (see _restore_window_state / closeEvent) so the app reopens
        # showing/hiding the same panels the user left it with.
        menu = menu_bar.addMenu(self.tr("&Visualizza"))

        def _toggle_action(label: str, widget: QWidget, settings_key: str, default: bool) -> QAction:
            action = QAction(label, self)
            action.setCheckable(True)
            initial = self._settings.panel_visible(settings_key, default)
            action.toggled.connect(widget.setVisible)
            # setChecked() only emits toggled on an actual change, and a
            # fresh QAction already starts unchecked -- so when the restored
            # value is False, the signal never fires and the widget would
            # stay visible. Set the widget's visibility explicitly too, to
            # not depend on that edge case.
            action.setChecked(initial)
            widget.setVisible(initial)
            menu.addAction(action)
            return action

        self.action_view_file_browser = _toggle_action(
            self.tr("Esplora cartella"),
            self.file_browser_panel,
            VIEW_FILE_BROWSER_KEY,
            True,
        )
        self.action_view_preview = _toggle_action(
            self.tr("Anteprima PDF"), self.preview_panel, VIEW_PREVIEW_KEY, True
        )
        self.action_view_formula_bar = _toggle_action(
            self.tr("Barra dei filtri"),
            self.formula_bar_panel,
            VIEW_FORMULA_BAR_KEY,
            True,
        )
        self.action_view_table = _toggle_action(
            self.tr("Tabella dati"), self.table_panel, VIEW_TABLE_KEY, True
        )
        menu.addSeparator()

        # Secondary PDF preview pane close/reopen, mirrored from the "✕"
        # button on the pane itself (Phase 3).
        self.action_view_secondary_preview = QAction(
            self.tr("Seconda anteprima PDF"), self
        )
        self.action_view_secondary_preview.setCheckable(True)
        secondary_initial = self._settings.panel_visible(
            VIEW_SECONDARY_PREVIEW_KEY, False
        )
        self.action_view_secondary_preview.toggled.connect(
            self.preview_panel.secondary_slot.setVisible
        )
        self.action_view_secondary_preview.setChecked(secondary_initial)
        self.preview_panel.secondary_slot.setVisible(secondary_initial)
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
        if self._folder_open:
            return  # button/action are disabled in this state; defensive no-op
        chosen = QFileDialog.getExistingDirectory(
            self, self.tr("Apri cartella con i PDF di iscrizione")
        )
        if not chosen:
            return
        self._open_folder(Path(chosen))

    def _open_folder(self, folder: Path) -> None:
        self._folder_open = True
        self._current_folder = folder
        self.action_open_folder.setEnabled(False)
        self.action_close_folder.setEnabled(True)
        self.file_browser_panel.open_folder(folder)
        self._run_extraction(folder)

    def _on_close_folder(self) -> None:
        if not self._folder_open:
            return
        self._folder_open = False
        self._current_folder = None
        self.action_open_folder.setEnabled(True)
        self.action_close_folder.setEnabled(False)
        self.file_browser_panel.close_folder()
        # Reset the table, the filter pipeline (chips + undo/redo history)
        # and both PDF previews to a blank state -- per spec, closing the
        # folder "è come riportare l'applicazione allo stato iniziale".
        self._pipeline.set_base_dataframe(pd.DataFrame())
        self._refresh_table_and_chips()
        self.preview_panel.reset()
        self.action_view_secondary_preview.setChecked(False)

    def _run_extraction(self, folder: Path) -> None:
        # Triggered on folder open, on file deletion, and every time an
        # edited PDF is saved back to disk from the field editor -- per
        # spec, changing a PDF invalidates the whole downstream table
        # state, so we simply re-run the same full scan rather than
        # trying to patch one row.
        dialog = AnalysisProgressDialog(self)
        worker = ExtractionWorker(folder, self)
        worker.progress.connect(dialog.set_progress)
        worker.finished_extraction.connect(
            lambda result: self._on_extraction_finished(result, dialog)
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()
        dialog.exec()

    def _on_extraction_finished(
        self, result: ExtractionResult, dialog: AnalysisProgressDialog
    ) -> None:
        dialog.accept()

        classifications = classify_folder(result.dataframe, result.errors)
        if self._current_folder is not None:
            self.file_browser_panel.set_classification(
                classifications, self._current_folder
            )

        # Red documents are excluded from the table entirely; orange ones
        # are included with their blank fields left blank (they already
        # are, extraction never fabricates values). A fresh extraction
        # always wipes any previous filter history -- per spec, a changed
        # source PDF invalidates everything downstream.
        included_files = {
            filename
            for filename, classification in classifications.items()
            if classification.color != "red"
        }
        table_df = result.dataframe[
            result.dataframe[SOURCE_FILE_COLUMN].isin(included_files)
        ].reset_index(drop=True)

        self._pipeline.set_base_dataframe(table_df)
        self._refresh_table_and_chips()

        if result.errors:
            details = "\n".join(f"- {name}: {msg}" for name, msg in result.errors.items())
            QMessageBox.warning(
                self,
                self.tr("Alcuni file non sono stati letti correttamente"),
                self.tr(
                    "{count} file nella cartella non sono stati letti e non "
                    "compaiono nella tabella:\n\n{details}"
                ).format(count=len(result.errors), details=details),
            )

    def _on_new_instance(self) -> None:
        # Launch a fresh, independent process of this same app with no
        # folder pre-opened, per spec ("apre una nuova finestra che però non
        # possiede una cartella già aperta").
        import subprocess

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

    # ---------------------------------------------------- Session persistence --
    # Window size/position, splitter proportions (e.g. how much width goes to
    # the preview vs. the file browser) and panel visibility are restored
    # here and saved in closeEvent(), so the app reopens exactly as it was
    # left -- unlike theme/language/scale, this needs no menu entry or
    # restart: it is captured/restored silently on every close/open.
    def _restore_window_state(self) -> None:
        geometry = self._settings.window_geometry()
        if geometry is not None:
            self.restoreGeometry(geometry)
        if self._settings.window_maximized():
            self.showMaximized()

        main_state = self._settings.main_splitter_state()
        if main_state is not None:
            self._main_splitter.restoreState(main_state)

        top_state = self._settings.top_splitter_state()
        if top_state is not None:
            self._top_splitter.restoreState(top_state)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._settings.set_window_maximized(self.isMaximized())
        self._settings.set_window_geometry(self.saveGeometry())
        self._settings.set_main_splitter_state(self._main_splitter.saveState())
        self._settings.set_top_splitter_state(self._top_splitter.saveState())

        self._settings.set_panel_visible(
            VIEW_FILE_BROWSER_KEY, self.action_view_file_browser.isChecked()
        )
        self._settings.set_panel_visible(
            VIEW_PREVIEW_KEY, self.action_view_preview.isChecked()
        )
        self._settings.set_panel_visible(
            VIEW_FORMULA_BAR_KEY, self.action_view_formula_bar.isChecked()
        )
        self._settings.set_panel_visible(
            VIEW_TABLE_KEY, self.action_view_table.isChecked()
        )
        self._settings.set_panel_visible(
            VIEW_SECONDARY_PREVIEW_KEY,
            self.action_view_secondary_preview.isChecked(),
        )

        super().closeEvent(event)
