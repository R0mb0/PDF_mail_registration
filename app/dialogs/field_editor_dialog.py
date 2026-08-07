"""
Phase 6: the in-app field editor, opened by double-clicking a PDF in the
file browser (never the system's default PDF viewer, per spec: "non deve
aprire il pdf con l'app di sistema, ma con un editor interno").

Shows every AcroForm field of one PDF as a proper editing widget (text box,
checkbox, dropdown) rather than a generic text grid, saves back to the same
file on disk via core.pdf_field_io, and reports success back to the caller
so main_window can re-run the full folder extraction -- per spec, changing
a PDF invalidates the whole downstream table state, so there is no attempt
to patch just one row in place.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.pdf_field_io import FieldWriteError, read_fields_detailed, safe_write_fields
from scaling import px


class FieldEditorDialog(QDialog):
    def __init__(self, pdf_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._fields = read_fields_detailed(pdf_path)

        self.setWindowTitle(pdf_path.name)
        self.resize(px(480), px(560))

        layout = QVBoxLayout(self)

        if not self._fields:
            layout.addWidget(
                QLabel(self.tr("Questo PDF non contiene campi compilabili."))
            )
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            form_container = QWidget()
            form = QFormLayout(form_container)
            form.setSpacing(px(8))

            self._widgets: dict[str, QWidget] = {}
            for info in self._fields:
                label = QLabel(info.name)
                if info.field_type == "text":
                    editor = QLineEdit(info.value)
                    form.addRow(label, editor)
                    self._widgets[info.name] = editor
                elif info.field_type == "checkbox":
                    editor = QCheckBox()
                    editor.setChecked(info.value == "Yes")
                    form.addRow(label, editor)
                    self._widgets[info.name] = editor
                elif info.field_type == "choice":
                    editor = QComboBox()
                    editor.setEditable(True)
                    choices = list(info.choices)
                    if info.value and info.value not in choices:
                        choices.insert(0, info.value)
                    editor.addItems(choices)
                    editor.setCurrentText(info.value)
                    form.addRow(label, editor)
                    self._widgets[info.name] = editor
                else:  # "other" (e.g. signature) -- shown, not editable
                    value_label = QLabel(info.value or self.tr("(non modificabile)"))
                    value_label.setEnabled(False)
                    value_label.setToolTip(
                        self.tr("Questo tipo di campo non è modificabile da qui.")
                    )
                    form.addRow(label, value_label)

            scroll.setWidget(form_container)
            layout.addWidget(scroll, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_save(self) -> None:
        for info in self._fields:
            widget = self._widgets.get(info.name)
            if widget is None:
                continue
            if info.field_type == "text" and isinstance(widget, QLineEdit):
                info.value = widget.text()
            elif info.field_type == "checkbox" and isinstance(widget, QCheckBox):
                info.value = "Yes" if widget.isChecked() else ""
            elif info.field_type == "choice" and isinstance(widget, QComboBox):
                info.value = widget.currentText()

        try:
            safe_write_fields(self._pdf_path, self._fields)
        except FieldWriteError as exc:
            QMessageBox.critical(
                self,
                self.tr("Salvataggio non riuscito"),
                self.tr("Non è stato possibile salvare \"{name}\":\n{error}").format(
                    name=self._pdf_path.name, error=str(exc)
                ),
            )
            return  # keep the dialog open so nothing is lost

        self.accept()
