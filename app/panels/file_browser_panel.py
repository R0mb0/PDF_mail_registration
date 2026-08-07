"""
Left panel: folder open/close + a Windows-Explorer-style browser scoped to
the *.pdf files in the opened folder, plus the (still placeholder, Phase 5)
colored classification strip.

Single click on a file emits file_single_clicked (Phase 3 wires this to the
preview FIFO logic); double click emits file_double_clicked (Phase 6 wires
this to the in-app field editor overlay). Both are wired here already so
later phases only need to *connect* to these signals, not touch this
panel's internals.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDir, QModelIndex, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileSystemModel,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from scaling import px


class FileBrowserPanel(QWidget):
    file_single_clicked = Signal(str)  # absolute path -- Phase 3: open in preview
    file_double_clicked = Signal(str)  # absolute path -- Phase 6: open field editor

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
        # --- QTreeView -- both bound to the same QFileSystemModel -----------
        self._stack = QStackedWidget()

        self._icon_view = QListView()
        self._icon_view.setModel(self._model)
        self._icon_view.setUniformItemSizes(True)
        self._icon_view.setResizeMode(QListView.ResizeMode.Adjust)
        self._icon_view.clicked.connect(self._on_single_clicked)
        self._icon_view.doubleClicked.connect(self._on_double_clicked)
        self._stack.addWidget(self._icon_view)

        self._details_view = QTreeView()
        self._details_view.setModel(self._model)
        self._details_view.setRootIsDecorated(False)
        self._details_view.setSortingEnabled(True)
        self._details_view.clicked.connect(self._on_single_clicked)
        self._details_view.doubleClicked.connect(self._on_double_clicked)
        self._stack.addWidget(self._details_view)

        self._stack.setEnabled(False)
        layout.addWidget(self._stack, stretch=1)

        # --- classification strip (Phase 5) ------------------------------------
        strip_label = QLabel(self.tr("Stato documenti"))
        strip_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(strip_label)

        self.classification_strip = QScrollArea()
        self.classification_strip.setWidgetResizable(True)
        self.classification_strip.setFixedHeight(px(56))
        self.classification_strip.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.classification_strip.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.classification_strip.setWidget(QWidget())
        layout.addWidget(self.classification_strip)

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

    def current_folder(self) -> Path | None:
        return self._current_folder

    def select_and_highlight(self, file_path: str) -> None:
        """Select + scroll to a file. Used by Phase 5's colored
        classification buttons ("evidenziata nella cartella")."""
        index = self._model.index(file_path)
        current_view = self._stack.currentWidget()
        current_view.setCurrentIndex(index)
        current_view.scrollTo(index)

    # ------------------------------------------------------------- Internal --
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
