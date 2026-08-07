"""
Modal, non-closable progress popup shown while the PDFs in the opened
folder are (re-)analyzed -- per spec: "un pop-up non richiudibile e
bloccante" with a realistic progress bar (real per-file progress, not a
fake animation; see core/extraction_worker.py).

Shown every time extraction runs: on folder open, and (from Phase 6
onward) every time an edited PDF is saved back to disk, since changing a
PDF invalidates the whole downstream table state per spec.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QVBoxLayout

from scaling import px


class AnalysisProgressDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Analisi dei documenti"))
        self.setModal(True)
        # No close button / system menu -- the dialog can only be dismissed
        # programmatically, from main_window.py, once extraction finishes.
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(16), px(16), px(16), px(16))
        layout.setSpacing(px(8))

        self._label = QLabel(self.tr("Avvio dell'analisi..."))
        layout.addWidget(self._label)

        self._bar = QProgressBar()
        self._bar.setMinimum(0)
        self._bar.setMaximum(1)
        self._bar.setValue(0)
        layout.addWidget(self._bar)

        self.setFixedSize(px(380), px(110))

    def set_progress(self, done: int, total: int, filename: str) -> None:
        self._bar.setMaximum(max(total, 1))
        self._bar.setValue(done)
        self._label.setText(
            self.tr("Analisi di {name} ({done}/{total})...").format(
                name=filename, done=done, total=total
            )
        )

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        event.ignore()  # non-closable by the user, per spec
