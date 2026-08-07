"""
Runs pdf_extraction.extract_folder() on a background QThread so the modal
progress popup can repaint/animate while the analysis runs, instead of
freezing (Qt can't process paint events while the GUI thread is busy).

Signals crossing from this worker thread to the main thread are delivered
through Qt's automatic queued-connection mechanism -- the receiving slots
(in main_window.py) still run safely on the GUI thread, no manual locking
needed.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from core.pdf_extraction import ExtractionResult, extract_folder


class ExtractionWorker(QThread):
    progress = Signal(int, int, str)       # done, total, current_filename
    finished_extraction = Signal(object)   # ExtractionResult

    def __init__(self, folder: Path, parent=None) -> None:
        super().__init__(parent)
        self._folder = folder

    def run(self) -> None:
        result: ExtractionResult = extract_folder(
            self._folder,
            progress_callback=lambda done, total, name: self.progress.emit(
                done, total, name
            ),
        )
        self.finished_extraction.emit(result)
