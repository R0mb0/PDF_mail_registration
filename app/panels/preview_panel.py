"""
Right panel: PDF preview, up to two side-by-side panes with FIFO slot
logic, rendered via PySide6's own QtPdf module (bundled with PySide6, no
extra dependency).

Each pane renders the current page itself, via QPdfDocument.render(page,
size, options) -> QImage, shown in a QLabel inside a QScrollArea, instead
of using QPdfWidgets.QPdfView. This is a deliberate change, not the
original design: QPdfView is a known, widely-reported limitation --
confirmed via Qt's own forums and multiple independent bug reports -- it
does not draw annotations (which is what AcroForm field values actually
are, visually) at all, with no public option to turn that on. A field
saved by this app's own editor (core/pdf_field_io.py) or filled by hand in
a fully-featured reader like Adobe Acrobat is stored correctly either way
-- this app's data table, which reads the raw field value directly, was
never affected -- but QPdfView would silently render the page as if the
form were still blank. QPdfDocument.render() does not have that
limitation: QPdfDocumentRenderOptions has a documented Annotations render
flag that makes it draw field values same as any other page content.

The trade-off: QPdfView's continuous multi-page scrolling ("comes for
free" from being a QAbstractScrollArea) doesn't apply to a manually
rendered single QImage per page, so multi-page PDFs get simple Previous/
Next navigation instead of one continuous scroll -- perfectly fine for
this app's target documents (this project's own registration form is a
single page), and still shows every page, just one at a time.

There is deliberately no "open PDF" button here: a preview is only ever
populated by single-clicking a file over in the folder browser panel
(single click -> preview, double click -> field editor overlay, per spec).

The secondary slot is opt-in, off by default: it only ever gets used once
the user has explicitly turned it on from the View menu's "Seconda
anteprima PDF" checkbox (main_window.py calls set_secondary_enabled()
whenever that checkbox is toggled). Until then there is effectively only
one usable slot -- every click just replaces whatever the primary slot is
showing. See open_pdf() below for the exact rule:

  - secondary disabled                     -> every click replaces the
                                               primary slot's content
  - secondary enabled, 1st click (both
    slots empty)                           -> fills the primary (left) slot
  - secondary enabled, 2nd click (primary
    filled, 2nd empty)                     -> fills the secondary (right) slot
  - secondary enabled, further clicks
    (both slots filled)                    -> replaces whichever slot was
                                               filled longest ago
  - clicking a file already shown in a slot just brings that slot to the
    front of the recency order, instead of reloading it into the other one

The secondary slot's own "✕" also unchecks the View menu's "Seconda
anteprima PDF" action (main_window.py), which in turn calls
set_secondary_enabled(False) here -- same single code path either way, so
the slot's visibility and its FIFO eligibility can never drift apart.
There is no way to close the primary slot, by design, per spec.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtPdf import QPdfDocument, QPdfDocumentRenderOptions
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from scaling import px

_MIN_ZOOM = 0.2
_MAX_ZOOM = 4.0
_ZOOM_STEP = 0.15
# Page geometry from QPdfDocument.pageSize() comes back in points (1/72
# inch); rendering straight at that many pixels would look blurry on any
# reasonably dense screen, so this is the base pixels-per-point multiplier
# at 100% zoom -- 2.0 gives a comfortably sharp starting resolution.
_BASE_RENDER_SCALE = 2.0


class _PreviewSlot(QWidget):
    """A single PDF preview pane: a placeholder until a PDF is loaded, then
    the current page rendered as an image (see module docstring for why
    this isn't QPdfView) inside a scroll area, with simple Previous/Next
    page navigation. `closable` adds a "✕" button in the top-right corner
    (secondary slot only)."""

    def __init__(self, closable: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._document = QPdfDocument(self)
        self._document.statusChanged.connect(self._on_status_changed)
        self._current_path: str | None = None
        self._current_page = 0
        self._zoom_factor = 1.0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        # --- header: filename + page nav + zoom + (optional) close button ----
        header = QHBoxLayout()
        self._name_label = QLabel("")
        self._name_label.setStyleSheet("font-weight: bold;")
        header.addWidget(self._name_label)
        header.addStretch(1)

        self._prev_button = QPushButton("‹")
        self._prev_button.setFixedWidth(px(26))
        self._prev_button.setToolTip(self.tr("Pagina precedente"))
        self._prev_button.clicked.connect(lambda: self._change_page(-1))
        header.addWidget(self._prev_button)

        self._page_label = QLabel("")
        header.addWidget(self._page_label)

        self._next_button = QPushButton("›")
        self._next_button.setFixedWidth(px(26))
        self._next_button.setToolTip(self.tr("Pagina successiva"))
        self._next_button.clicked.connect(lambda: self._change_page(1))
        header.addWidget(self._next_button)

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

        # --- body: placeholder label stacked with the rendered page ----------
        body = QWidget()
        self._body_stack = QStackedLayout(body)

        self._placeholder_label = QLabel(self.tr("Anteprima"))
        self._placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_label.setStyleSheet("color: gray; font-style: italic;")
        self._body_stack.addWidget(self._placeholder_label)

        # Rendered page as a plain QLabel pixmap inside a non-resizable
        # QScrollArea -- the label is kept at the rendered image's native
        # pixel size, so the scroll area shows scrollbars instead of
        # squashing/stretching the page to fit, same as any standard
        # Qt image-viewer layout.
        self._page_view_label = QLabel()
        self._page_view_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setWidget(self._page_view_label)
        self._body_stack.addWidget(self._scroll_area)

        self._body_stack.setCurrentWidget(self._placeholder_label)
        outer.addWidget(body, stretch=1)

        self._update_page_controls()

        if closable:
            self.setVisible(False)  # secondary slot starts hidden (no PDF yet)

    # ---------------------------------------------------------------- API --
    def load(self, file_path: str) -> None:
        self._current_path = file_path
        self._current_page = 0
        self._zoom_factor = 1.0
        self._name_label.setText(Path(file_path).name)
        self._document.load(file_path)
        # Local files typically finish loading synchronously, but fall
        # back on statusChanged (below) for anything that doesn't --
        # either way this call is a harmless no-op if the document isn't
        # ready yet (pageCount() would just be 0).
        self._render_current_page()
        self._update_page_controls()
        self._body_stack.setCurrentWidget(self._scroll_area)

    def clear(self) -> None:
        self._current_path = None
        self._current_page = 0
        self._document.close()
        self._name_label.setText("")
        self._page_view_label.clear()
        self._update_page_controls()
        self._body_stack.setCurrentWidget(self._placeholder_label)

    def current_path(self) -> str | None:
        return self._current_path

    # ------------------------------------------------------------- Internal --
    def _on_status_changed(self, status: QPdfDocument.Status) -> None:
        if status == QPdfDocument.Status.Ready and self._current_path is not None:
            self._render_current_page()
            self._update_page_controls()

    def _change_page(self, delta: int) -> None:
        page_count = self._document.pageCount()
        if page_count <= 0:
            return
        new_page = max(0, min(page_count - 1, self._current_page + delta))
        if new_page != self._current_page:
            self._current_page = new_page
            self._render_current_page()
            self._update_page_controls()

    def _adjust_zoom(self, delta: float) -> None:
        if self._current_path is None:
            return
        self._zoom_factor = max(_MIN_ZOOM, min(_MAX_ZOOM, self._zoom_factor + delta))
        self._render_current_page()

    def _update_page_controls(self) -> None:
        page_count = self._document.pageCount()
        if page_count <= 0:
            self._page_label.setText("")
            self._prev_button.setVisible(False)
            self._next_button.setVisible(False)
            return
        # Single-page documents (this project's own registration form,
        # most of the time) don't need navigation controls cluttering the
        # header at all.
        multi_page = page_count > 1
        self._prev_button.setVisible(multi_page)
        self._next_button.setVisible(multi_page)
        self._page_label.setText(f"{self._current_page + 1}/{page_count}")
        self._prev_button.setEnabled(self._current_page > 0)
        self._next_button.setEnabled(self._current_page < page_count - 1)

    def _render_current_page(self) -> None:
        page_count = self._document.pageCount()
        if self._current_path is None or page_count <= 0:
            return
        page_index = max(0, min(page_count - 1, self._current_page))

        point_size = self._document.pageSize(page_index)  # QSizeF, in points
        target_size = QSize(
            max(1, round(point_size.width() * _BASE_RENDER_SCALE * self._zoom_factor)),
            max(1, round(point_size.height() * _BASE_RENDER_SCALE * self._zoom_factor)),
        )

        options = QPdfDocumentRenderOptions()
        # This is the actual fix for the "compiled fields not visible in
        # preview" bug (see module docstring): without this flag,
        # QPdfDocument.render() -- like QPdfView -- omits form field
        # values from the rendered image entirely.
        options.setRenderFlags(QPdfDocumentRenderOptions.RenderFlag.Annotations)

        image = self._document.render(page_index, target_size, options)
        pixmap = QPixmap.fromImage(image)
        self._page_view_label.setPixmap(pixmap)
        self._page_view_label.resize(pixmap.size())


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
        # replacement rule. Only relevant once the secondary slot is
        # enabled; see set_secondary_enabled().
        self._fill_order: list[str] = []
        self._secondary_enabled = False

    # ---------------------------------------------------------------- API --
    def open_pdf(self, file_path: str) -> None:
        if self.primary_slot.current_path() == file_path:
            self._touch("primary")
            return

        if not self._secondary_enabled:
            # Only one usable slot while the secondary preview is off --
            # every new document replaces the primary's content, full stop.
            self._load_into("primary", file_path)
            return

        if self.secondary_slot.current_path() == file_path:
            self._touch("secondary")
            return

        if self.primary_slot.current_path() is None:
            self._load_into("primary", file_path)
        elif self.secondary_slot.current_path() is None:
            self._load_into("secondary", file_path)
        else:
            oldest_slot = self._fill_order[0]
            self._load_into(oldest_slot, file_path)

    def set_secondary_enabled(self, enabled: bool) -> None:
        """The single entry point for turning the secondary slot on/off --
        wired to the View menu's "Seconda anteprima PDF" checkbox and to
        the slot's own "✕" (via that same checkbox) in main_window.py.
        Disabling always clears the slot's content too, so re-enabling it
        later never resurrects a stale PDF, and open_pdf() never has to
        guess whether a "filled but hidden" slot is actually eligible."""
        self._secondary_enabled = enabled
        self.secondary_slot.setVisible(enabled)
        if not enabled:
            self.close_secondary()

    def close_secondary(self) -> None:
        """Clears the secondary slot's content only -- visibility is
        controlled exclusively by set_secondary_enabled()."""
        self.secondary_slot.clear()
        if "secondary" in self._fill_order:
            self._fill_order.remove("secondary")

    def reset(self) -> None:
        """Full reset, e.g. when the folder is closed."""
        self.primary_slot.clear()
        self.set_secondary_enabled(False)
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
