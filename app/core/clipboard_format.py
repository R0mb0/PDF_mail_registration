"""
Tab-separated-value formatting for the Edit menu's Copy/Cut/Paste, matching
the layout Excel/LibreOffice/Sheets themselves put on the clipboard, so
copying out of this app's table and pasting into a spreadsheet (or vice
versa) just works.

No Qt dependency on purpose: the actual QClipboard access lives in
panels/table_panel.py, this module only formats/parses the text, so the
logic itself is unit-testable headlessly.
"""

from __future__ import annotations


def rows_to_tsv(rows: list[list[str]]) -> str:
    return "\n".join("\t".join(cell for cell in row) for row in rows)


def tsv_to_rows(text: str) -> list[list[str]]:
    """Splits on \\n (and tolerates \\r\\n). A trailing empty line (common
    when text was copied with a final newline) is dropped; a single blank
    string decodes to no rows at all rather than one row with one empty
    cell, since that's never a paste anyone actually wants."""
    if text == "":
        return []
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return [line.split("\t") for line in lines]
