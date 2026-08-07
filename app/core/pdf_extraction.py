"""
Generic AcroForm field extraction for the registration PDFs in a folder.

Deliberately does NOT hardcode the field schema from LaTeX_Template -- per
the project's own design premise, the app must treat whatever fields it
finds as data, not assume a fixed shape in advance (Phase 5 builds the
"average structure" / outlier detection on top of exactly this
generality). Every AcroForm field found in any PDF becomes a column; a PDF
that lacks a given field simply gets an empty cell for it.

This module has no Qt dependency on purpose, so it can be unit-tested and
run headlessly (see the project's dev notes) independently of the GUI.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Callable, Optional

import pandas as pd
from pypdf import PdfReader
from pypdf.errors import PdfReadError

# Column holding the originating filename. Kept as a plain, human-readable
# header (shown as-is in the table) rather than a hidden/internal key --
# none of our own form fields are named "File", and even a third-party PDF
# with a same-named field would just collide visibly, which is preferable
# to a silent hidden mismatch.
SOURCE_FILE_COLUMN = "File"

ProgressCallback = Callable[[int, int, str], None]


@dataclass
class ExtractionResult:
    dataframe: pd.DataFrame
    errors: dict[str, str] = dataclass_field(default_factory=dict)  # filename -> message


def _read_pdf_fields(pdf_path: Path) -> dict[str, str]:
    """Read one PDF's AcroForm field values as a flat {name: value} dict.

    Checkbox/radio values come back from pypdf as PDF name objects (e.g.
    "/Yes", "/Off"); normalized here to "Yes"/"" so the raw table is
    directly readable without the caller needing to know PDF internals.
    """
    reader = PdfReader(str(pdf_path))
    fields = reader.get_fields() or {}

    row: dict[str, str] = {}
    for name, field_obj in fields.items():
        value = field_obj.get("/V", "")
        if isinstance(value, str) and value.startswith("/"):
            value = value[1:]
            if value == "Off":
                value = ""
        row[str(name)] = "" if value is None else str(value)
    return row


def extract_folder(
    folder: Path,
    progress_callback: Optional[ProgressCallback] = None,
) -> ExtractionResult:
    """Scan `folder` (non-recursive) for .pdf files and extract their form
    fields into one row per file.

    `progress_callback(done, total, filename)` is invoked after each file
    if given, so the caller can drive a real progress bar rather than a
    fake animation. A PDF that fails to parse contributes an (otherwise
    empty) row plus an entry in `ExtractionResult.errors`, rather than
    aborting the whole folder.
    """
    pdf_paths = sorted(folder.glob("*.pdf"))
    total = len(pdf_paths)

    rows: list[dict[str, str]] = []
    errors: dict[str, str] = {}
    column_order: list[str] = []

    for i, pdf_path in enumerate(pdf_paths, start=1):
        try:
            row = _read_pdf_fields(pdf_path)
        except (PdfReadError, OSError, ValueError) as exc:
            errors[pdf_path.name] = str(exc)
            row = {}

        row[SOURCE_FILE_COLUMN] = pdf_path.name
        for name in row:
            if name not in column_order:
                column_order.append(name)
        rows.append(row)

        if progress_callback is not None:
            progress_callback(i, total, pdf_path.name)

    # Source-file column first for readability, then every field
    # encountered, in first-seen order across the folder.
    ordered_columns = [SOURCE_FILE_COLUMN] + [
        c for c in column_order if c != SOURCE_FILE_COLUMN
    ]
    df = pd.DataFrame(rows, columns=ordered_columns)
    return ExtractionResult(dataframe=df, errors=errors)
