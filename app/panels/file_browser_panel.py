"""
Left panel: folder open/close + the file browser + the colored classification
strip described in the spec.

Phase 1 note: this is a placeholder. Only the static layout exists; folder
opening, the actual file listing, view-mode switching (large/medium/small
icons, list, details), search, and the colored per-document classification
strip are all built in Phase 2 / Phase 5. Keeping the placeholder here (with
the future widgets already named as attributes) means later phases only add
behavior, not restructure the layout.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from scaling import px


class FileBrowserPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FileBrowserPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # --- top buttons: open folder / close folder ------------------------
        # Wired up in Phase 2: open_folder disables itself once a folder is
        # active, close_folder resets the whole application state.
        self.open_folder_button = QPushButton(self.tr("Apri cartella"))
        self.close_folder_button = QPushButton(self.tr("Chiudi cartella"))
        self.close_folder_button.setEnabled(False)
        layout.addWidget(self.open_folder_button)
        layout.addWidget(self.close_folder_button)

        # --- search box (Phase 2) -------------------------------------------
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(self.tr("Cerca nella cartella..."))
        layout.addWidget(self.search_box)

        # --- file listing area (Phase 2) ------------------------------------
        # Real implementation: QListView/QTreeView with a switchable view
        # model (large/medium/small icons, list, details), Explorer-style.
        self.file_list_placeholder = QListView()
        self.file_list_placeholder.setEnabled(False)
        layout.addWidget(self.file_list_placeholder, stretch=1)

        # --- classification strip (Phase 5) ----------------------------------
        # Horizontal scrollable strip of colored per-document buttons.
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
        placeholder = QWidget()
        self.classification_strip.setWidget(placeholder)
        layout.addWidget(self.classification_strip)
