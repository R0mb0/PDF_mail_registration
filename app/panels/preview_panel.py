"""
Right panel: PDF preview, up to two side-by-side panes (FIFO slot logic).

Phase 1 note: placeholder only. The two preview slots exist as named
attributes so Phase 3 can wire in QtPdf rendering + FIFO open/replace logic
without touching the surrounding layout.

There is deliberately no "open PDF" button here: a preview is only ever
populated by single-clicking a file over in the folder browser panel
(single click -> preview, double click -> field editor overlay, per spec).
The first click fills the primary slot, the second fills the secondary
slot, and any further click replaces whichever slot was opened longest ago
(FIFO). The secondary slot's own "✕" closes it; there is no way to close
the primary slot (by design, per spec).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from scaling import px


class _PreviewSlot(QWidget):
    """A single PDF preview pane: placeholder text until a PDF is loaded,
    plus (for the secondary slot only) a close button in the top-right."""

    def __init__(self, closable: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)

        header = QHBoxLayout()
        header.addStretch(1)
        self.close_button: QPushButton | None = None
        if closable:
            self.close_button = QPushButton("✕")
            self.close_button.setFixedSize(px(20), px(20))
            self.close_button.setToolTip(self.tr("Chiudi anteprima"))
            header.addWidget(self.close_button)
        outer.addLayout(header)

        # Real implementation (Phase 3): a QtPdf-backed page view with its
        # own scrollbars. For now: a centered placeholder label.
        self.placeholder_label = QLabel(self.tr("Anteprima"))
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("color: gray; font-style: italic;")
        outer.addWidget(self.placeholder_label, stretch=1)

        if closable:
            self.setVisible(False)  # secondary slot starts hidden (no PDF yet)


class PreviewPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PreviewPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        slots_row = QHBoxLayout()
        self.primary_slot = _PreviewSlot(closable=False)
        self.secondary_slot = _PreviewSlot(closable=True)
        slots_row.addWidget(self.primary_slot, stretch=1)
        slots_row.addWidget(self.secondary_slot, stretch=1)
        layout.addLayout(slots_row, stretch=1)
