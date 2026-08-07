"""
Filter / formula bar: mode toggle (Excel-subset / SQL) + run button, the
multiline expression editor, and the row of colored, removable filter chips.

Phase 1 note: placeholder only. Phase 4 wires in the actual filter engine,
chip stack, undo/redo history and error alerts.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class FormulaBarPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FormulaBarPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # --- mode toggle + run button -----------------------------------------
        # Positioned above the expression editor, per spec.
        mode_row = QHBoxLayout()
        self.excel_mode_button = QPushButton(self.tr("Excel"))
        self.excel_mode_button.setCheckable(True)
        self.excel_mode_button.setChecked(True)
        self.sql_mode_button = QPushButton(self.tr("SQL"))
        self.sql_mode_button.setCheckable(True)
        self.run_button = QPushButton(self.tr("Esegui ▶"))
        mode_row.addWidget(self.excel_mode_button)
        mode_row.addWidget(self.sql_mode_button)
        mode_row.addStretch(1)
        mode_row.addWidget(self.run_button)
        layout.addLayout(mode_row)

        # --- expression editor (Phase 4: syntax highlighting) -----------------
        self.expression_edit = QPlainTextEdit()
        self.expression_edit.setPlaceholderText(
            self.tr("Scrivi qui una formula Excel o una espressione SQL...")
        )
        self.expression_edit.setFixedHeight(70)
        layout.addWidget(self.expression_edit)

        # --- filter chip stack (Phase 4) -------------------------------------
        # Horizontal, wrapping row of colored "filtroN [x]" chips, sitting
        # between the expression editor and the table panel below it, per
        # spec. Empty placeholder frame for now so the reserved vertical
        # space is visible even before any filter has been applied.
        self.chip_stack = QFrame()
        self.chip_stack.setFixedHeight(28)
        self.chip_stack.setFrameShape(QFrame.NoFrame)
        layout.addWidget(self.chip_stack)
