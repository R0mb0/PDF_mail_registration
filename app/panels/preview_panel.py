"""
Right panel: PDF preview, up to two side-by-side panes with FIFO slot
logic, rendered via PySide6's own QtPdf/QtPdfWidgets (QPdfDocument +
QPdfView -- bundled with PySide6, no extra dependency). QPdfView is a
QAbstractScrollArea subclass, so vertical/horizontal scrollbars and
continuous multi-page scrolling come for free.

There is deliberately no "open PDF" button here: a preview is only ever
populated by single-clicking a file over in the folder browser panel
(single click -> preview, double click -> field editor overlay, per spec).
See open_pdf() below for the exact FIFO rule:

  - 1st click ever (both slots empty)      -> fills the primary (left) slot
  - 2nd click (primary filled, 2nd empty)  -> fills the secondary (right) slot
  - further clicks (both slots filled)     -> replaces whichever slot was
                                               filled longest ago
  - clicking a file already shown in a slot just brings that slot to the
    front of the recency order, instead of reloading it into the other one

The secondary slot's own "✕" clears + hides it (wired to the View menu's
"Seconda anteprima PDF" toggle in main_window.py, so both stay in sync).
There is no way to close the primary slot, by design, per spec.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from scaling import px

_MIN_ZOOM = 0.2
_MAX_ZOOM = 4.0
_ZOOM_STEP = 0.15


class _PreviewSlot(QWidget):
    """A single PDF preview pane: a placeholder until a PDF is loaded, then
    a scrollable/zoomable QPdfView. `closable` adds a "✕" button in the
    top-right corner (secondary slot only)."""

    def __init__(self, closable: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._document = QPdfDocument(self)
        self._current_path: str | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        # --- header: filename + zoom controls + (optional) close button ------
        header = QHBoxLayout()
        self._name_label = QLabel("")
        self._name_label.setStyleSheet("font-weight: bold;")
        header.addWidget(self._name_label)
        header.addStretch(1)

        zoom_out = QPushButton("-")
        zoom_out.setFixedWidth(px(26))
        zoom_out.setToolTip(self.tr("Riduci zoom"))
        zoom_out.clicked.connect(lambda: self._adjust_zoom(-_ZOOM_STEP))
        header.addWidget(zoom_out)

        zoom_in = QPushButton("+")
        zoom_in.setFixedWidth(px(26))
        zoom_in.setToolTip(self.tr("Aumenta zoom"))
        zoom_in.clicked.connect(lambda: self._adjust_zoom(_ZOOM_STEP))
        header.addWidget(zoom_in)

        self.close_button: QPushButton | None = None
        if closable:
            self.close_button = QPushButton("✕")
            self.close_button.setFixedSize(px(20), px(20))
            self.close_button.setToolTip(self.tr("Chiudi anteprima"))
            header.addWidget(self.close_button)
        outer.addLayout(header)

        # --- body: placeholder label stacked with the actual PDF view --------
        body = QWidget()
        self._body_stack = QStackedLayout(body)

        self._placeholder_label = QLabel(self.tr("Anteprima"))
        self._placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_label.setStyleSheet("color: gray; font-style: italic;")
        self._body_stack.addWidget(self._placeholder_label)

        self._view = QPdfView()
        self._view.setDocument(self._document)
        self._view.setPageMode(QPdfView.PageMode.MultiPage)
        self._view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._view.setZoomFactor(1.0)
        self._body_stack.addWidget(self._view)

        self._body_stack.setCurrentWidget(self._placeholder_label)
        outer.addWidget(body, stretch=1)

        if closable:
            self.setVisible(False)  # secondary slot starts hidden (no PDF yet)

    # ---------------------------------------------------------------- API --
    def load(self, file_path: str) -> None:
        self._current_path = file_path
        self._document.load(file_path)
        self._name_label.setText(Path(file_path).name)
        self._view.setZoomFactor(1.0)
        self._body_stack.setCurrentWidget(self._view)

    def clear(self) -> None:
        self._current_path = None
        self._document.close()
        self._name_label.setText("")
        self._body_stack.setCurrentWidget(self._placeholder_label)

    def current_path(self) -> str | None:
        return self._current_path

    def _adjust_zoom(self, delta: float) -> None:
        if self._current_path is None:
            return
        new_zoom = max(_MIN_ZOOM, min(_MAX_ZOOM, self._view.zoomFactor() + delta))
        self._view.setZoomFactor(new_zoom)


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

        # Recency order of *filled* slots, oldest first -- drives the FIFO
        # replacement rule. main_window.py connects the secondary "✕" to
        # close_secondary() and keeps the View-menu checkbox in sync.
        self._fill_order: list[str] = []

    # ---------------------------------------------------------------- API --
    def open_pdf(self, file_path: str) -> None:
        if self.primary_slot.current_path() == file_path:
            self._touch("primary")
            return
        if self.secondary_slot.current_path() == file_path:
            self._touch("secondary")
            return

        if self.primary_slot.current_path() is None:
            self._load_into("primary", file_path)
        elif self.secondary_slot.current_path() is None:
            self._load_into("secondary", file_path)
            self.secondary_slot.setVisible(True)
        else:
            oldest_slot = self._fill_order[0]
            self._load_into(oldest_slot, file_path)

    def close_secondary(self) -> None:
        """Clears the secondary slot's content. Visibility is intentionally
        left to the caller (main_window.py keeps it in sync with the View
        menu's checkable action)."""
        self.secondary_slot.clear()
        if "secondary" in self._fill_order:
            self._fill_order.remove("secondary")

    def reset(self) -> None:
        """Full reset, e.g. when the folder is closed."""
        self.primary_slot.clear()
        self.close_secondary()
        self.secondary_slot.setVisible(False)
        self._fill_order = []

    # ------------------------------------------------------------- Internal --
    def _load_into(self, slot_key: str, file_path: str) -> None:
        slot = self.primary_slot if slot_key == "primary" else self.secondary_slot
        slot.load(file_path)
        self._touch(slot_key)

    def _touch(self, slot_key: str) -> None:
        if slot_key in self._fill_order:
            self._fill_order.remove(slot_key)
        self._fill_order.append(slot_key)
