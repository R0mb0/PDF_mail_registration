"""
Detailed AcroForm field read/write for the in-app field editor (Phase 6).

`core.pdf_extraction` already reads field values for the data table, but it
deliberately flattens everything to plain strings (it doesn't need to know a
field is a checkbox vs. free text -- a table cell is a table cell). The
field editor needs more: it has to render a checkbox as a checkbox, a
dropdown as a dropdown, and know a checkbox's actual "on" state name (which
is not always "/Yes", even though that's what our own LaTeX template uses)
so it can write a value pypdf/Acrobat will actually recognize.

No Qt dependency on purpose -- unit-tested headlessly against a real
generated PDF (see project dev notes), same convention as pdf_extraction.py.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Literal

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

FieldType = Literal["text", "checkbox", "choice", "other"]


@dataclass
class FieldInfo:
    name: str
    field_type: FieldType
    value: str  # normalized: "" / "Yes" for checkboxes, plain text/choice otherwise
    on_state: str = "Yes"  # checkbox only -- the real PDF name meaning "checked"
    choices: list[str] = dataclass_field(default_factory=list)  # choice fields only


def read_fields_detailed(pdf_path: Path) -> list[FieldInfo]:
    """Read every AcroForm field of `pdf_path` with enough type information
    to build an editing widget for it. Field order matches the PDF's own
    field dictionary order (insertion order), same as get_fields()."""
    reader = PdfReader(str(pdf_path))
    fields = reader.get_fields() or {}

    result: list[FieldInfo] = []
    for name, field_obj in fields.items():
        field_type = field_obj.get("/FT")
        raw_value = field_obj.get("/V")

        if field_type == "/Btn":
            states = field_obj.get("/_States_") or []
            on_state = "Yes"
            for state in states:
                state_name = str(state).lstrip("/")
                if state_name != "Off":
                    on_state = state_name
                    break
            checked = isinstance(raw_value, str) and raw_value.lstrip("/") == on_state
            result.append(
                FieldInfo(
                    name=str(name),
                    field_type="checkbox",
                    value="Yes" if checked else "",
                    on_state=on_state,
                )
            )
        elif field_type == "/Ch":
            choices: list[str] = []
            for opt in field_obj.get("/Opt") or []:
                choices.append(str(opt[-1]) if isinstance(opt, (list, tuple)) else str(opt))
            value = "" if raw_value is None else str(raw_value)
            result.append(
                FieldInfo(name=str(name), field_type="choice", value=value, choices=choices)
            )
        elif field_type == "/Tx":
            value = "" if raw_value is None else str(raw_value)
            result.append(FieldInfo(name=str(name), field_type="text", value=value))
        else:
            # Signature fields and anything else we don't have a sensible
            # editor for -- surfaced as read-only "other" so the dialog can
            # show it without offering to edit it.
            value = "" if raw_value is None else str(raw_value)
            result.append(FieldInfo(name=str(name), field_type="other", value=value))

    return result


def write_fields(pdf_path: Path, fields: list[FieldInfo]) -> None:
    """Write `fields` (as returned by read_fields_detailed, with `.value`
    updated by the caller) back into `pdf_path`.

    Writes to a temporary file in the same directory first and only
    replaces the original via os.replace() once the write fully succeeds,
    so a crash or a locked file never leaves a half-written/corrupt PDF
    behind.
    """
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    writer.append(reader)

    pdf_values: dict[str, str] = {}
    for info in fields:
        if info.field_type == "checkbox":
            pdf_values[info.name] = f"/{info.on_state}" if info.value == "Yes" else "/Off"
        elif info.field_type in ("text", "choice"):
            pdf_values[info.name] = info.value
        # "other" (e.g. signature) fields are never written back.

    # auto_regenerate=False is deliberate and load-bearing, not just a
    # style choice: it tells pypdf to bake a real, immediately-visible
    # appearance stream into each field's /AP right now, and to clear the
    # PDF's /NeedAppearances flag (which the original LaTeX_Template
    # already ships as true, since hyperref sets it by default). If that
    # flag is left/set true instead, the file's *data* is still correct --
    # the app's own table reads /V directly and was never affected -- but
    # any viewer that takes the flag at face value and doesn't actually
    # regenerate appearances itself (this app's own PDF preview included,
    # since it's a lightweight embedded renderer, not a full interactive
    # form engine -- and pypdf's own docs note several common viewers
    # behave this way) renders the field as blank, even though the value
    # is genuinely saved. This was a real bug: an earlier version of this
    # function forced auto_regenerate=False and then immediately re-set
    # the flag anyway via set_need_appearances_writer(True) right after,
    # which undid the whole point and left every field invisible in this
    # app's own preview pane despite being saved correctly.
    writer.update_page_form_field_values(None, pdf_values, auto_regenerate=False)

    tmp_path = pdf_path.with_name(pdf_path.name + ".tmp")
    try:
        with open(tmp_path, "wb") as handle:
            writer.write(handle)
        os.replace(tmp_path, pdf_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


class FieldWriteError(Exception):
    """Raised by write_fields callers on any I/O or PDF-parsing failure --
    a thin, dialog-friendly wrapper so the GUI layer doesn't need to know
    about pypdf's own exception types."""


def safe_write_fields(pdf_path: Path, fields: list[FieldInfo]) -> None:
    try:
        write_fields(pdf_path, fields)
    except (PdfReadError, OSError, ValueError) as exc:
        raise FieldWriteError(str(exc)) from exc
