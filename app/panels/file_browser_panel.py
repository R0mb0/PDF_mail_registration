"""
Left panel: folder open/close + a Windows-Explorer-style browser scoped to
the *.pdf files in the opened folder, the colored classification strip
(Phase 5), and file deletion (Delete key / right-click, also Phase 5).

Single click on a file emits file_single_clicked (wired to the preview FIFO
logic); double click emits file_double_clicked (wired to the in-app field
editor overlay, Phase 6).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDir, QEvent, QModelIndex, QSize, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileSystemModel,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from core.classification import Color, DocumentClassification
from scaling import px

# Traffic-light palette -- immediately recognizable regardless of theme.
_CLASSIFICATION_COLORS: dict[Color, str] = {
    "green": "#66BB6A",
    "orange": "#FFA726",
    "red": "#EF5350",
}


class FileBrowserPanel(QWidget):
    file_single_clicked = Signal(str)   # absolute path -- Phase 3: open in preview
    file_double_clicked = Signal(str)   # absolute path -- Phase 6: open field editor
    classification_file_clicked = Signal(str)  # absolute path -- clicking a strip button
    folder_contents_changed = Signal()  # a file was deleted -- main_window re-extracts

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FileBrowserPanel")

        self._current_folder: Path | None = None

        self._model = QFileSystemModel(self)
        self._model.setNameFilters(["*.pdf"])
        self._model.setNameFilterDisables(False)  # hide non-matching, don't just grey out
        self._model.setFilter(QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # --- top buttons: open folder / close folder ------------------------
        buttons_row = QHBoxLayout()
        self.open_folder_button = QPushButton(self.tr("Apri cartella"))
        self.close_folder_button = QPushButton(self.tr("Chiudi cartella"))
        self.close_folder_button.setEnabled(False)
        buttons_row.addWidget(self.open_folder_button)
        buttons_row.addWidget(self.close_folder_button)
        layout.addLayout(buttons_row)

        # --- search box -------------------------------------------------------
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(self.tr("Cerca nella cartella..."))
        self.search_box.setEnabled(False)
        self.search_box.textChanged.connect(self._apply_search_filter)
        layout.addWidget(self.search_box)

        # --- view mode selector (Explorer-style) -------------------------------
        view_row = QHBoxLayout()
        self._view_group = QButtonGroup(self)
        self._view_group.setExclusive(True)
        self._view_buttons: dict[str, QToolButton] = {}
        for key, label in (
            ("large", self.tr("Icone grandi")),
            ("medium", self.tr("Icone medie")),
            ("small", self.tr("Icone piccole")),
            ("list", self.tr("Elenco")),
            ("details", self.tr("Dettagli")),
        ):
            button = QToolButton()
            button.setText(label)
            button.setCheckable(True)
            button.setEnabled(False)
            button.clicked.connect(lambda _checked, k=key: self._set_view_mode(k))
            self._view_group.addButton(button)
            view_row.addWidget(button)
            self._view_buttons[key] = button
        self._view_buttons["list"].setChecked(True)
        view_row.addStretch(1)
        layout.addLayout(view_row)

        # --- file view: icon/list modes share a QListView, "details" uses a --
        # --- QTreeView -- both bound to the same QFileSystemModel, both --
        # --- support delete via Delete key / right-click context menu ------
        self._stack = QStackedWidget()

        self._icon_view = QListView()
        self._icon_view.setModel(self._model)
        self._icon_view.setUniformItemSizes(True)
        self._icon_view.setResizeMode(QListView.ResizeMode.Adjust)
        self._icon_view.clicked.connect(self._on_single_clicked)
        self._icon_view.doubleClicked.connect(self._on_double_clicked)
        self._install_delete_support(self._icon_view)
        self._stack.addWidget(self._icon_view)

        self._details_view = QTreeView()
        self._details_view.setModel(self._model)
        self._details_view.setRootIsDecorated(False)
        self._details_view.setSortingEnabled(True)
        self._details_view.clicked.connect(self._on_single_clicked)
        self._details_view.doubleClicked.connect(self._on_double_clicked)
        self._install_delete_support(self._details_view)
        self._stack.addWidget(self._details_view)

        self._stack.setEnabled(False)
        layout.addWidget(self._stack, stretch=1)

        # --- classification strip (Phase 5) ------------------------------------
        # Horizontal, scrollable row of tall colored buttons, one per PDF in
        # the folder (including "red" ones, which are excluded from the
        # table but still shown/openable here). Clicking one opens it in
        # preview and selects/highlights it above.
        strip_label = QLabel(self.tr("Stato documenti"))
        strip_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(strip_label)

        self.classification_strip = QScrollArea()
        self.classification_strip.setWidgetResizable(True)
        self.classification_strip.setFixedHeight(px(64))
        self.classification_strip.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.classification_strip.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._strip_content = QWidget()
        self._strip_layout = QHBoxLayout(self._strip_content)
        self._strip_layout.setContentsMargins(2, 2, 2, 2)
        self._strip_layout.setSpacing(4)
        self._strip_layout.addStretch(1)
        self.classification_strip.setWidget(self._strip_content)
        layout.addWidget(self.classification_strip)

        self._strip_group = QButtonGroup(self)
        self._strip_group.setExclusive(True)

        self._set_view_mode("list")

    # ---------------------------------------------------------------- API --
    def open_folder(self, folder: Path) -> None:
        self._current_folder = folder
        self._model.setRootPath(str(folder))
        root_index = self._model.index(str(folder))
        self._icon_view.setRootIndex(root_index)
        self._details_view.setRootIndex(root_index)

        self.open_folder_button.setEnabled(False)
        self.close_folder_button.setEnabled(True)
        self.search_box.setEnabled(True)
        self._stack.setEnabled(True)
        for button in self._view_buttons.values():
            button.setEnabled(True)

    def close_folder(self) -> None:
        self._current_folder = None
        self._model.setRootPath("")
        self.search_box.blockSignals(True)
        self.search_box.clear()
        self.search_box.blockSignals(False)
        self._model.setNameFilters(["*.pdf"])
        self.search_box.setEnabled(False)

        self.open_folder_button.setEnabled(True)
        self.close_folder_button.setEnabled(False)
        self._stack.setEnabled(False)
        for button in self._view_buttons.values():
            button.setEnabled(False)

        self.clear_classification()

    def current_folder(self) -> Path | None:
        return self._current_folder

    def select_and_highlight(self, file_path: str) -> None:
        """Select + scroll to a file. Used by Phase 5's colored
        classification buttons ("evidenziata nella cartella")."""
        index = self._model.index(file_path)
        current_view = self._stack.currentWidget()
        current_view.setCurrentIndex(index)
        current_view.scrollTo(index)

    def set_classification(
        self, results: dict[str, DocumentClassification], folder: Path
    ) -> None:
        self.clear_classification()
        for index, (filename, classification) in enumerate(results.items(), start=1):
            button = self._build_classification_button(classification, folder, index)
            self._strip_group.addButton(button)
            self._strip_layout.insertWidget(self._strip_layout.count() - 1, button)

    def clear_classification(self) -> None:
        # Explicitly drop buttons from the group rather than relying on
        # deleteLater()'s deferred cleanup -- QButtonGroup.buttons() would
        # otherwise still report the old (pending-deletion) buttons if
        # queried before the next event-loop iteration.
        while self._strip_layout.count() > 1:  # keep the trailing stretch
            item = self._strip_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                self._strip_group.removeButton(widget)
                widget.deleteLater()

    # ------------------------------------------------------------- Internal --
    def _build_classification_button(
        self, classification: DocumentClassification, folder: Path, index: int
    ) -> QPushButton:
        color = _CLASSIFICATION_COLORS[classification.color]
        button = QPushButton(str(index))
        button.setCheckable(True)
        button.setFixedSize(px(30), px(56))
        button.setStyleSheet(
            f"QPushButton {{ background-color: {color}; color: #1a1a1a; "
            f"font-weight: bold; border-radius: {px(4)}px; border: none; }}"
            f"QPushButton:checked {{ border: {px(2)}px solid #1a1a1a; }}"
        )
        tooltip_lines = [classification.filename]
        tooltip_lines.extend(classification.reasons)
        button.setToolTip("\n".join(tooltip_lines))

        file_path = str(folder / classification.filename)
        button.clicked.connect(lambda: self._on_classification_button_clicked(file_path))
        return button

    def _on_classification_button_clicked(self, file_path: str) -> None:
        self.select_and_highlight(file_path)
        self.classification_file_clicked.emit(file_path)

    def _apply_search_filter(self, text: str) -> None:
        pattern = f"*{text}*.pdf" if text else "*.pdf"
        self._model.setNameFilters([pattern])

    def _icon_size(self, base_px: int) -> QSize:
        return QSize(px(base_px), px(base_px))

    def _set_view_mode(self, key: str) -> None:
        if key == "details":
            self._stack.setCurrentWidget(self._details_view)
            return

        self._stack.setCurrentWidget(self._icon_view)
        if key == "large":
            self._icon_view.setViewMode(QListView.ViewMode.IconMode)
            self._icon_view.setIconSize(self._icon_size(96))
            self._icon_view.setGridSize(self._icon_size(116))
        elif key == "medium":
            self._icon_view.setViewMode(QListView.ViewMode.IconMode)
            self._icon_view.setIconSize(self._icon_size(48))
            self._icon_view.setGridSize(self._icon_size(66))
        elif key == "small":
            self._icon_view.setViewMode(QListView.ViewMode.IconMode)
            self._icon_view.setIconSize(self._icon_size(24))
            self._icon_view.setGridSize(self._icon_size(40))
        else:  # "list"
            self._icon_view.setViewMode(QListView.ViewMode.ListMode)
            self._icon_view.setIconSize(self._icon_size(16))
            self._icon_view.setGridSize(QSize())

    def _on_single_clicked(self, index: QModelIndex) -> None:
        path = self._model.filePath(index)
        if path:
            self.file_single_clicked.emit(path)

    def _on_double_clicked(self, index: QModelIndex) -> None:
        path = self._model.filePath(index)
        if path:
            self.file_double_clicked.emit(path)

    # ------------------------------------------------ Delete (Phase 5) ------
    # Per spec: a file can be excluded from processing entirely by deleting
    # it -- either after clicking its colored strip button (which selects +
    # highlights it here) or just by selecting it directly in the browser.
    def _install_delete_support(self, view) -> None:
        view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        view.customContextMenuRequested.connect(
            lambda pos, v=view: self._show_context_menu(v, pos)
        )
        view.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt override)
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                if watched in (self._icon_view, self._details_view):
                    self._delete_current_file(watched)
                    return True
        return super().eventFilter(watched, event)

    def _show_context_menu(self, view, position) -> None:
        index = view.indexAt(position)
        if not index.isValid():
            return
        menu = QMenu(self)
        delete_action = menu.addAction(self.tr("Elimina"))
        delete_action.triggered.connect(lambda: self._delete_current_file(view))
        menu.exec(view.viewport().mapToGlobal(position))

    def _delete_current_file(self, view) -> None:
        index = view.currentIndex()
        if not index.isValid():
            return
        file_path = self._model.filePath(index)
        filename = Path(file_path).name

        confirmed = QMessageBox.question(
            self,
            self.tr("Eliminare il file?"),
            self.tr(
                '"{name}" verrà eliminato definitivamente dal disco ed '
                "escluso dall'elaborazione."
            ).format(name=filename),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        if self._model.remove(index):
            self.folder_contents_changed.emit()
        else:
            QMessageBox.warning(
                self,
                self.tr("Eliminazione non riuscita"),
                self.tr('Non è stato possibile eliminare "{name}".').format(name=filename),
            )
