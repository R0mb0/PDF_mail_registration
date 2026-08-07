"""
Qt table model bound to a pandas DataFrame.

This is the single source of truth the table panel renders. Row numbers
(vertical header) are automatic and not part of the data -- exactly the
"fixed, external" row-count column described in the spec, as opposed to
the data cells, which are always editable -- with one deliberate
exception: the SOURCE_FILE_COLUMN ("File") is read-only, because it is
also the stable row identifier the filter pipeline uses to reapply manual
edits after a filter reshapes/reorders the table (core/filter_pipeline.py);
letting the user rename it in place would silently break that tracking.

Editing does NOT mutate this model's dataframe in place. Instead, setData
calls the `edit_callback(row_key, column, value)` set via
set_edit_callback() -- normally wired by TablePanel to
FilterPipeline.record_manual_edit() followed by a full model refresh, so a
manual edit always goes through the exact same "this is a filter step"
bookkeeping described in the spec, whether it is the very first change to
the raw table or the fifth one layered on top of existing filters.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QFont

from core.pdf_extraction import SOURCE_FILE_COLUMN

EditCallback = Callable[[str, str, str], None]  # (row_key, column, new_value)


class DataFrameTableModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame | None = None, parent=None) -> None:
        super().__init__(parent)
        self._df: pd.DataFrame = df if df is not None else pd.DataFrame()
        self._edit_callback: EditCallback | None = None

    # --------------------------------------------------------------- data --
    def set_dataframe(self, df: pd.DataFrame) -> None:
        self.beginResetModel()
        self._df = df
        self.endResetModel()

    def dataframe(self) -> pd.DataFrame:
        return self._df

    def set_edit_callback(self, callback: EditCallback | None) -> None:
        self._edit_callback = callback

    # ------------------------------------------------------- Qt model API --
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._df.index)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._df.columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            value = self._df.iat[index.row(), index.column()]
            return "" if pd.isna(value) else str(value)
        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False

        column_name = str(self._df.columns[index.column()])
        if column_name == SOURCE_FILE_COLUMN:
            return False  # read-only identity column, see module docstring

        if self._edit_callback is None:
            # No pipeline wired up (shouldn't normally happen past Phase 4) --
            # fall back to a direct in-place edit so the model still works
            # standalone (e.g. in isolated tests).
            self._df.iat[index.row(), index.column()] = value
            self.dataChanged.emit(index, index, [role])
            return True

        if SOURCE_FILE_COLUMN not in self._df.columns:
            return False
        row_key = str(self._df.iat[index.row(), self._df.columns.get_loc(SOURCE_FILE_COLUMN)])
        self._edit_callback(row_key, column_name, value)
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        column_name = str(self._df.columns[index.column()])
        if column_name == SOURCE_FILE_COLUMN:
            return base
        return base | Qt.ItemFlag.ItemIsEditable

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if section >= len(self._df.columns):
                return None
            if role == Qt.ItemDataRole.DisplayRole:
                return str(self._df.columns[section])
            if role == Qt.ItemDataRole.FontRole:
                font = QFont()
                font.setBold(True)
                return font
            return None
        # Vertical header: automatic 1-based row numbers, not data-bound.
        if role == Qt.ItemDataRole.DisplayRole:
            return str(section + 1)
        return None
