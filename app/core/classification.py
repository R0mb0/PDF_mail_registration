"""
Classifies each extracted document as green/orange/red relative to the
"typical" field structure across the whole folder, per spec:

  - green:  matches the typical field structure, no blank fields, not a
            near-duplicate of another document.
  - orange: "light" irregularities -- a near-duplicate (more than 30% of
            THIS document's filled fields are identical to another
            document's), or at least one blank field, or a field-presence
            structure that deviates from the folder's typical structure
            by up to 30%.
  - red:    anything more severe -- the PDF could not be parsed at all
            (see ExtractionResult.errors), or its field-presence structure
            deviates from the typical one by more than 30%. Red documents
            are excluded from the data table entirely; orange ones are
            included with their blank fields left blank.

"Typical structure" is deliberately a simple, small-sample-friendly
heuristic rather than a literal statistical distribution fit (with the
handful-to-few-dozen documents a single event realistically produces, a
true Gaussian fit over so few points would be more fragile than
illuminating): for each field, the "expected" state (filled vs blank) is
whatever the majority of documents actually did, and a document's
deviation score is the fraction of fields where it disagrees with that
majority.

No Qt dependency -- unit-tested headlessly (see project dev notes).
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Literal

import pandas as pd

from core.pdf_extraction import SOURCE_FILE_COLUMN

Color = Literal["green", "orange", "red"]

STRUCTURE_DEVIATION_ORANGE_MAX = 0.30   # deviation up to this -> orange, beyond -> red
DUPLICATE_FIELD_MATCH_THRESHOLD = 0.30  # fraction of this doc's filled fields matching another doc -> duplicate


@dataclass
class DocumentClassification:
    filename: str
    color: Color
    reasons: list[str] = dataclass_field(default_factory=list)


def classify_folder(
    df: pd.DataFrame, extraction_errors: dict[str, str]
) -> dict[str, DocumentClassification]:
    """One entry per PDF in `df` (which must be the raw, unfiltered
    extraction result -- one row per file, as produced by
    core.pdf_extraction.extract_folder)."""
    results: dict[str, DocumentClassification] = {}
    if SOURCE_FILE_COLUMN not in df.columns:
        return results

    field_columns = [c for c in df.columns if c != SOURCE_FILE_COLUMN]

    if df.empty:
        return results

    if not field_columns:
        # No AcroForm fields found anywhere in the folder -- nothing to
        # compare against, so nothing meaningful to flag as "deviating".
        for filename in df[SOURCE_FILE_COLUMN]:
            if filename in extraction_errors:
                results[filename] = DocumentClassification(
                    filename, "red", [f"Errore di lettura: {extraction_errors[filename]}"]
                )
            else:
                results[filename] = DocumentClassification(filename, "green", [])
        return results

    # --- presence matrix + the "typical" (majority) presence per field -----
    presence: dict[str, dict[str, bool]] = {}
    for _, row in df.iterrows():
        fname = row[SOURCE_FILE_COLUMN]
        presence[fname] = {c: _is_filled(row[c]) for c in field_columns}

    fill_rate = {
        c: sum(1 for p in presence.values() if p[c]) / len(presence) for c in field_columns
    }
    majority_filled = {c: fill_rate[c] >= 0.5 for c in field_columns}

    for _, row in df.iterrows():
        fname = row[SOURCE_FILE_COLUMN]

        if fname in extraction_errors:
            results[fname] = DocumentClassification(
                fname, "red", [f"Errore di lettura: {extraction_errors[fname]}"]
            )
            continue

        reasons: list[str] = []
        doc_presence = presence[fname]

        mismatches = sum(1 for c in field_columns if doc_presence[c] != majority_filled[c])
        deviation_ratio = mismatches / len(field_columns)

        if any(not doc_presence[c] for c in field_columns):
            reasons.append("Uno o più campi non compilati.")

        if _is_duplicate(fname, row, df, field_columns):
            reasons.append("Possibile duplicato di un'altra registrazione.")

        if deviation_ratio > STRUCTURE_DEVIATION_ORANGE_MAX:
            reasons.append(
                f"Struttura dei campi molto diversa dalla media ({deviation_ratio:.0%})."
            )
            results[fname] = DocumentClassification(fname, "red", reasons)
            continue

        if deviation_ratio > 0:
            reasons.append(
                f"Struttura dei campi leggermente diversa dalla media ({deviation_ratio:.0%})."
            )

        results[fname] = DocumentClassification(
            fname, "orange" if reasons else "green", reasons
        )

    return results


def _is_filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and pd.isna(value):
        return False
    return str(value).strip() != ""


def _is_duplicate(fname: str, row: pd.Series, df: pd.DataFrame, field_columns: list[str]) -> bool:
    filled_fields = [c for c in field_columns if _is_filled(row[c])]
    # Require at least a couple of filled fields before comparing -- a
    # document with only one filled field (e.g. a single "Yes" checkbox)
    # matching everyone else's isn't a meaningful duplicate signal, it's
    # just too little information; such a document is red anyway on
    # structural-deviation grounds.
    if len(filled_fields) < 2:
        return False
    for _, other in df.iterrows():
        if other[SOURCE_FILE_COLUMN] == fname:
            continue
        matches = sum(
            1
            for c in filled_fields
            if _is_filled(other[c]) and str(other[c]) == str(row[c])
        )
        if matches / len(filled_fields) > DUPLICATE_FIELD_MATCH_THRESHOLD:
            return True
    return False
