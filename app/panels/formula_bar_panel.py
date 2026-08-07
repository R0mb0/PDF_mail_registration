"""
Filter / formula bar: mode toggle (Excel-subset / SQL) + run button, the
multiline expression editor, and the row of colored, removable filter chips.

The actual filter *logic* (core/filter_pipeline.py) knows nothing about
Qt; this panel is purely presentational plus a couple of signals that
main_window.py listens to and drives the pipeline with.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from panels.flow_layout import FlowLayout
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

# Distinct, readable pastel colors for successive filter chips -- cycles
# if there are more filters than colors. Text stays dark on all of them.
_CHIP_COLORS = [
    "#AEDFF7",  # soft blue
    "#FFD8A8",  # soft orange
    "#D6C3F5",  # soft purple
    "#B7E4C7",  # soft teal-green
    "#FFC9DE",  # soft pink
    "#FFF3A0",  # soft yellow
    "#F5B7B1",  # soft red
    "#C3D4F5",  # soft indigo
]


@dataclass
class ChipInfo:
    label: str
    tooltip: str
    removable: bool


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

        # --- expression editor (Phase 7 polish: syntax highlighting) ----------
        self.expression_edit = QPlainTextEdit()
        self.expression_edit.setPlaceholderText(
            self.tr(
                'Excel: [colonna] = "valore"   AND(...)   OR(...)   '
                "ISBLANK([colonna])\n"
                "SQL: SELECT * FROM data WHERE ..."
            )
        )
        self.expression_edit.setFixedHeight(px(70))
        layout.addWidget(self.expression_edit)

        # --- filter chip stack --------------------------------------------------
        # Wrapping row of colored "FiltroN [x]" chips, between the
        # expression editor and the table panel below it, per spec. Only
        # the last chip's "x" is ever enabled (integrity rule: you can only
        # remove the most recently applied filter).
        self._chip_container = QWidget()
        self._chip_layout = FlowLayout(self._chip_container, margin=0, spacing=6)
        self._chip_container.setMinimumHeight(px(30))
        layout.addWidget(self._chip_container)

    # ---------------------------------------------------------------- API --
    def selected_mode(self) -> str | None:
        if self.excel_mode_button.isChecked():
            return "excel"
        if self.sql_mode_button.isChecked():
            return "sql"
        return None

    def expression_text(self) -> str:
        return self.expression_edit.toPlainText()

    def clear_expression(self) -> None:
        self.expression_edit.clear()

    def set_chips(self, chips: list[ChipInfo], on_remove_last) -> None:
        """Rebuild the chip row from scratch -- simple and cheap at the
        scale of a few dozen filters. `on_remove_last` is called with no
        arguments when the last chip's "x" is clicked."""
        while self._chip_layout.count():
            item = self._chip_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for index, chip in enumerate(chips):
            self._chip_layout.addWidget(
                self._build_chip_widget(chip, index, on_remove_last)
            )

    # ------------------------------------------------------------- Internal --
    def _build_chip_widget(self, chip: ChipInfo, index: int, on_remove_last) -> QWidget:
        color = _CHIP_COLORS[index % len(_CHIP_COLORS)]

        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background-color: {color}; border-radius: {px(10)}px; }}"
        )
        frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        row = QHBoxLayout(frame)
        row.setContentsMargins(px(10), px(4), px(6), px(4))
        row.setSpacing(px(6))

        label = QLabel(chip.label)
        label.setStyleSheet("color: #1a1a1a; font-weight: 600;")
        label.setToolTip(chip.tooltip)
        row.addWidget(label)

        remove_button = QToolButton()
        remove_button.setText("✕")
        remove_button.setAutoRaise(True)
        if chip.removable:
            remove_button.setEnabled(True)
            remove_button.setToolTip(self.tr("Rimuovi questo filtro"))
            remove_button.clicked.connect(on_remove_last)
        else:
            remove_button.setEnabled(False)
            remove_button.setToolTip(
                self.tr("Puoi rimuovere solo l'ultimo filtro applicato")
            )
        row.addWidget(remove_button)

        return frame
