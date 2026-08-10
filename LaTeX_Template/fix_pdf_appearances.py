#!/usr/bin/env python3
"""
Post-processing step for registration_form.pdf, run once right after
pdflatex compiles it. Fixes two independent problems, neither of which
LaTeX/hyperref gets right on its own:

1. hyperref sets the PDF's AcroForm /NeedAppearances flag to true by
   default for any form it creates -- this tells a PDF reader "don't
   trust whatever appearance is already baked into a field, regenerate
   it yourself before displaying it". Full interactive editors (Adobe
   Acrobat, Preview, ...) handle this fine: when a person actually types
   into a field, the editor draws its own appearance for what was typed,
   independently of this flag, and usually clears it on save. But
   several lighter-weight PDF renderers take the flag at face value and
   don't actually regenerate anything, which can leave a filled-in field
   looking blank even though the value is saved correctly.

2. hyperref has a real, independently-documented bug of its own
   (https://github.com/latex3/hyperref/issues/94, open since 2019): a
   \\CheckBox's "checked" appearance is written into the PDF as a
   syntactically *empty* object instead of a real content stream. With
   no actual content, no renderer -- none, this isn't a "lightweight
   viewer" problem like #1 -- can draw a checkmark for it, no matter how
   correctly everything else about the field is set.

Both were found and fixed via the Python app's own PDF preview (see
app/core/pdf_field_io.py's docstring for the full story, and its
repair_checkbox_appearances()/build_flattened_preview_copy() for the
same fix applied there -- the checkbox-repair logic below is
deliberately duplicated rather than imported, since this script is
meant to run standalone with no dependency on the app/ package; keep the
two in sync by hand if either one changes).

Verified (see project dev notes) by rendering the page to an image with
every annotation stripped out entirely -- forcing the render to rely
purely on the page's own content -- both before and after these fixes,
each time confirming what's expected: fields and checkmarks appear (or
don't) exactly according to what's actually baked into the page, not
merely what the field's underlying /V value says.

Usage:
    pdflatex registration_form.tex
    pdflatex registration_form.tex
    python3 fix_pdf_appearances.py registration_form.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, FloatObject, NameObject, NumberObject, StreamObject


def repair_checkbox_appearances(writer: PdfWriter) -> int:
    """See module docstring, point 2. Replaces any empty checkbox
    "checked" appearance with a real, minimal checkmark drawing sized to
    the widget's own rectangle, in the template's own accent green (RGB
    74/124/60, see event-form-style.sty). Returns how many appearances
    were repaired."""
    repaired = 0
    for page in writer.pages:
        for annot in page.get("/Annots") or []:
            obj = annot.get_object()
            if obj.get("/FT") != "/Btn":
                continue
            ap = obj.get("/AP")
            if not ap or "/N" not in ap:
                continue
            n_obj = ap["/N"]
            if not hasattr(n_obj, "items"):
                continue  # already a single, direct stream -- nothing to repair
            rect = obj.get("/Rect")
            if rect is None:
                continue
            width = float(rect[2]) - float(rect[0])
            height = float(rect[3]) - float(rect[1])
            for state_name in list(n_obj.keys()):
                if state_name == "/Off":
                    continue  # a blank appearance is correct when unchecked
                appearance = n_obj[state_name]
                is_empty = not hasattr(appearance, "get_data") or len(appearance.get_data()) == 0
                if not is_empty:
                    continue
                stream = _build_checkmark_stream(width, height)
                n_obj[NameObject(state_name)] = writer._add_object(stream)
                repaired += 1
    return repaired


def _build_checkmark_stream(width: float, height: float) -> StreamObject:
    margin = min(width, height) * 0.2
    x0, y0 = margin, height * 0.45
    x1, y1 = width * 0.42, margin
    x2, y2 = width - margin, height - margin
    line_width = max(1.0, min(width, height) * 0.12)

    content = (
        f"{line_width:.2f} w 1 J 1 j\n"
        f"0.29 0.49 0.24 RG\n"
        f"{x0:.2f} {y0:.2f} m\n"
        f"{x1:.2f} {y1:.2f} l\n"
        f"{x2:.2f} {y2:.2f} l\n"
        f"S\n"
    ).encode("latin-1")

    stream = StreamObject()
    stream.set_data(content)
    stream[NameObject("/Type")] = NameObject("/XObject")
    stream[NameObject("/Subtype")] = NameObject("/Form")
    stream[NameObject("/FormType")] = NumberObject(1)
    stream[NameObject("/BBox")] = ArrayObject(
        [FloatObject(0), FloatObject(0), FloatObject(width), FloatObject(height)]
    )
    return stream


def fix_appearances(pdf_path: Path) -> None:
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    writer.append(reader)

    repaired = repair_checkbox_appearances(writer)
    writer.update_page_form_field_values(None, {}, auto_regenerate=False)

    tmp_path = pdf_path.with_name(pdf_path.name + ".tmp")
    with open(tmp_path, "wb") as handle:
        writer.write(handle)
    tmp_path.replace(pdf_path)

    if repaired:
        print(f"Repaired {repaired} broken checkbox appearance(s) (hyperref#94).")


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
