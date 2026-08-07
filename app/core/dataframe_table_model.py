"""
Qt table model bound to a pandas DataFrame.

This is the single source of truth the table panel renders and the
(future) Phase 4 filter pipeline mutates -- keeping it Qt-model-shaped
rather than a plain DataFrame wrapper means the table view gets live
updates, in-place editing and correct selection/undo behavior for free
from Qt's own machinery.

Row numbers (vertical header) are automatic and not part of the data --
exactly the "fixed, external" row-count column described in the spec, as
opposed to the data cells, which are always editable.
"""

from __future__ import annotations

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QFont


class DataFrameTableModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame | None = None, parent=None) -> None:
        super().__init__(parent)
        self._df: pd.DataFrame = df if df is not None else pd.DataFrame()

    # --------------------------------------------------------------- data --
    def set_dataframe(self, df: pd.DataFrame) -> None:
        self.beginResetModel()
        self._df = df
        self.endResetModel()

    def dataframe(self) -> pd.DataFrame:
        return self._df

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
        self._df.iat[index.row(), index.column()] = value
        self.dataChanged.emit(index, index, [role])
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        # Every data cell is editable at any time (per spec); Phase 4 layers
        # "this edit becomes a filter" logic on top of dataChanged, it does
        # not need this method to change.
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEditable
        )

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
