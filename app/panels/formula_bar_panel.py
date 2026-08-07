"""
Filter / formula bar: mode toggle (Excel-subset / SQL) + run button, the
multiline expression editor, and the row of colored, removable filter chips.

Phase 1 note: placeholder only. Phase 4 wires in the actual filter engine,
chip stack, undo/redo history and error alerts.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from scaling import px
from theme import ACCENT

# Applied to the Excel/SQL mode buttons so the active mode is unmistakable
# regardless of platform/theme -- solid accent fill + bold text on top of
# Qt's own native sunken/"pressed" look for a checked QPushButton.
_MODE_BUTTON_STYLE = (
    "QPushButton:checked {{"
    "background-color: rgb({r}, {g}, {b});"
    "color: white;"
    "font-weight: bold;"
    "}}"
).format(r=ACCENT.red(), g=ACCENT.green(), b=ACCENT.blue())


class FormulaBarPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FormulaBarPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # --- mode toggle + run button -----------------------------------------
        # Positioned above the expression editor, per spec. Excel/SQL are
        # mutually exclusive (QButtonGroup, exclusive) and neither is active
        # at startup -- the user must explicitly pick a mode before running
        # an expression.
        mode_row = QHBoxLayout()
        self.excel_mode_button = QPushButton(self.tr("Excel"))
        self.excel_mode_button.setCheckable(True)
        self.excel_mode_button.setStyleSheet(_MODE_BUTTON_STYLE)

        self.sql_mode_button = QPushButton(self.tr("SQL"))
        self.sql_mode_button.setCheckable(True)
        self.sql_mode_button.setStyleSheet(_MODE_BUTTON_STYLE)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self.excel_mode_button)
        self._mode_group.addButton(self.sql_mode_button)

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
        self.expression_edit.setFixedHeight(px(70))
        layout.addWidget(self.expression_edit)

        # --- filter chip stack (Phase 4) -------------------------------------
        # Horizontal, wrapping row of colored "filtroN [x]" chips, sitting
        # between the expression editor and the table panel below it, per
        # spec. Empty placeholder frame for now so the reserved vertical
        # space is visible even before any filter has been applied.
        self.chip_stack = QFrame()
        self.chip_stack.setFixedHeight(px(28))
        self.chip_stack.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self.chip_stack)
