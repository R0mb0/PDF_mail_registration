"""
Bottom panel: the data table (auto row numbers, bold headers, editable
cells) + the "Esporta dati come..." button.

As of Phase 4, edits are routed through whatever edit_callback main_window
wires in via set_edit_callback() -- normally FilterPipeline.record_manual_
edit() followed by a full refresh -- rather than mutating this panel's
dataframe directly. Phase 7 wires the export button to main_window's export
handler and adds the Edit menu's Cut/Copy/Paste/Select all/Select none,
implemented here since they operate directly on the QTableView's selection.
Cut/Copy/Paste use tab-separated text on the system clipboard, matching
Excel/LibreOffice/Sheets' own clipboard format, so round-tripping through
an external spreadsheet just works. Paste routes every cell it writes
through the exact same edit_callback as a manual edit typed in-place (and
is silently skipped for the read-only "File" column), so pasted data is
indistinguishable from hand-typed data to the filter pipeline's undo/redo.
"""

from __future__ import annotations

import pandas as pd
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from core.clipboard_format import rows_to_tsv, tsv_to_rows
from core.dataframe_table_model import DataFrameTableModel, EditCallback


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

    def set_edit_callback(self, callback: EditCallback | None) -> None:
        self._model.set_edit_callback(callback)

    # ------------------------------------------------------ Edit menu (Phase 7) --
    def _selected_indexes(self):
        return sorted(
            self.table.selectionModel().selectedIndexes(),
            key=lambda index: (index.row(), index.column()),
        )

    def copy_selection(self) -> None:
        indexes = self._selected_indexes()
        if not indexes:
            return
        by_row: dict[int, dict[int, str]] = {}
        for index in indexes:
            by_row.setdefault(index.row(), {})[index.column()] = (
                self._model.data(index) or ""
            )
        rows = sorted(by_row)
        cols = sorted({col for row in by_row.values() for col in row})
        grid = [[by_row[r].get(c, "") for c in cols] for r in rows]
        QGuiApplication.clipboard().setText(rows_to_tsv(grid))

    def cut_selection(self) -> None:
        indexes = self._selected_indexes()
        if not indexes:
            return
        self.copy_selection()
        for index in indexes:
            # setData() already refuses to touch the read-only "File"
            # column on its own (see DataFrameTableModel docstring), so no
            # separate flags check is needed here.
            self._model.setData(index, "")

    def paste_at_selection(self) -> None:
        indexes = self._selected_indexes()
        text = QGuiApplication.clipboard().text()
        grid = tsv_to_rows(text)
        if not indexes or not grid:
            return
        anchor = indexes[0]
        for row_offset, row_values in enumerate(grid):
            target_row = anchor.row() + row_offset
            if target_row >= self._model.rowCount():
                break
            for col_offset, value in enumerate(row_values):
                target_col = anchor.column() + col_offset
                if target_col >= self._model.columnCount():
                    continue
                index = self._model.index(target_row, target_col)
                self._model.setData(index, value)

    def select_all(self) -> None:
        self.table.selectAll()

    def select_none(self) -> None:
        self.table.clearSelection()
