"""
Bottom panel: the data table (auto row numbers, bold headers, editable
cells) + the "Esporta dati come..." button.

Phase 1 note: placeholder only. Phase 2 wires in the real QTableView bound
to the extracted PDF data; Phase 7 wires in the export dialog.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)


class TablePanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TablePanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(4)

        # Real data is bound in Phase 2. Row numbers use the table's built-in
        # vertical header (auto-numbered, not an editable column) and the
        # horizontal header is bold by default via the app-wide stylesheet.
        self.table = QTableWidget(0, 0)
        self.table.verticalHeader().setVisible(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=1)

        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch(1)
        self.export_button = QPushButton(self.tr("Esporta dati come..."))
        bottom_bar.addWidget(self.export_button)
        layout.addLayout(bottom_bar)
