"""
Bottom panel: the data table (auto row numbers, bold headers, editable
cells) + the "Esporta dati come..." button.

Phase 2: bound to a real DataFrameTableModel, populated after each folder
scan. Phase 4 will feed it the *filtered* dataframe instead of the raw
extraction result; Phase 7 wires the export button to the export dialog.
"""

from __future__ import annotations

import pandas as pd
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from core.dataframe_table_model import DataFrameTableModel


class TablePanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TablePanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(4)

        self._model = DataFrameTableModel()

        self.table = QTableView()
        self.table.setModel(self._model)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=1)

        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch(1)
        self.export_button = QPushButton(self.tr("Esporta dati come..."))
        bottom_bar.addWidget(self.export_button)
        layout.addLayout(bottom_bar)

    def set_dataframe(self, df: pd.DataFrame) -> None:
        self._model.set_dataframe(df)
        self.table.resizeColumnsToContents()

    def dataframe(self) -> pd.DataFrame:
        return self._model.dataframe()
