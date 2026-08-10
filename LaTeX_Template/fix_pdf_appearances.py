#!/usr/bin/env python3
"""
Post-processing step for registration_form.pdf, run once right after
pdflatex compiles it.

hyperref sets the PDF's AcroForm /NeedAppearances flag to true by default
for any form it creates -- this tells a PDF reader "don't trust whatever
appearance is already baked into a field, regenerate it yourself before
displaying it". Full interactive editors (Adobe Acrobat, Preview, ...)
handle this fine: when a person actually types into a field, the editor
draws its own appearance for what was typed, independently of this flag,
and usually clears it on save. But several lighter-weight PDF renderers
take the flag at face value and don't actually regenerate anything, which
can leave a filled-in field looking blank even though the value is saved
correctly (this exact symptom was reported and fixed on the Python app's
own PDF preview -- see app/core/pdf_field_io.py's docstring for the other
half of this same underlying issue).

This script re-runs pypdf's own field-value write pass with
auto_regenerate=False and no value changes -- which is what actually
clears the flag and bakes a real (if visually empty, since the fields are
unfilled at this stage) appearance stream for every field -- so the
shipped template starts from a clean baseline regardless of which tool
someone later uses to fill it in.

Verified to be a purely cosmetic-metadata change: field names, field
values and the rendered page image are byte-for-byte/pixel-for-pixel
identical before and after running this (see project dev notes) -- this
only touches how confidently a PDF reader trusts the appearances already
on the page, never the page content itself.

Usage:
    pdflatex registration_form.tex
    pdflatex registration_form.tex
    python3 fix_pdf_appearances.py registration_form.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def fix_appearances(pdf_path: Path) -> None:
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    writer.append(reader)
    writer.update_page_form_field_values(None, {}, auto_regenerate=False)

    tmp_path = pdf_path.with_name(pdf_path.name + ".tmp")
    with open(tmp_path, "wb") as handle:
        writer.write(handle)
    tmp_path.replace(pdf_path)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 fix_pdf_appearances.py <path-to-pdf>", file=sys.stderr)
        return 1

    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    fix_appearances(path)
    print(f"Cleared /NeedAppearances and baked field appearances in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
