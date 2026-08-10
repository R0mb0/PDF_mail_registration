"""
Classifies each extracted document as green/orange/red relative to the
"typical" field structure across the whole folder, per spec:

  - green:  matches the folder's own typical field structure, not a
            near-duplicate of another document.
  - orange: "light" irregularities -- a near-duplicate (more than 30% of
            THIS document's filled fields are identical to another
            document's), or a field structure that deviates from the
            folder's typical structure by up to 30%.
  - red:    anything more severe -- the PDF could not be parsed at all
            (see ExtractionResult.errors), or its field structure deviates
            from the typical one by more than 30%. Red documents are
            excluded from the data table entirely; orange ones are
            included with their blank fields left blank.

"Typical structure" is deliberately a simple, small-sample-friendly
heuristic rather than a literal statistical distribution fit (with the
handful-to-few-dozen documents a single event realistically produces, a
true Gaussian fit over so few points would be more fragile than
illuminating): for most fields (free text, expected to differ per person)
the "expected" state is just filled-vs-blank, majority vote; for
low-cardinality fields (checkboxes -- see below) it's the exact majority
*value*. A document's deviation score is the fraction of fields where it
disagrees with whichever of those two applies.

An earlier version of this module also flagged *any* document with *any*
blank field as orange, regardless of whether that field was blank in
every other document too -- e.g. an optional consent checkbox that's
legitimately left unchecked by nearly everyone made nearly the entire
folder orange, purely because "blank" was treated as inherently
suspicious rather than compared against the folder's own norm (caught via
real test data: see project dev notes). A blank/unchecked field is only
ever a signal here if it deviates from what the rest of the folder did --
which the majority-vote deviation score above already captures on its
own, so there is no separate standalone "has a blank field" rule anymore.

Duplicate detection deliberately ignores low-cardinality fields (at most
2 distinct non-blank values across the whole folder -- in practice almost
always a Yes/Off checkbox): two unrelated people both accepting the same
consent checkbox is expected and carries essentially no evidence that
they're the same registration, whereas two people sharing the same email
address or date of birth actually does. Without this exclusion, once
checkbox fields count as "filled" (see core/pdf_extraction.py's docstring
for why "Off" is a real value now, not blank), nearly every document in a
folder ends up superficially "matching" nearly every other one on its
checkbox answers alone, which is noise, not a real duplicate signal.

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
    # Free-text fields (first name, email, ...) are compared on presence
    # alone -- filled vs blank -- since everyone's exact value is expected
    # to differ; comparing exact text would flag nearly every document as
    # deviating from whichever one value happened to be "most common".
    presence: dict[str, dict[str, bool]] = {}
    for _, row in df.iterrows():
        fname = row[SOURCE_FILE_COLUMN]
        presence[fname] = {c: _is_filled(row[c]) for c in field_columns}

    fill_rate = {
        c: sum(1 for p in presence.values() if p[c]) / len(presence) for c in field_columns
    }
    majority_filled = {c: fill_rate[c] >= 0.5 for c in field_columns}

    # Low-cardinality fields (at most 2 distinct non-blank values
    # folder-wide -- in practice almost always a Yes/Off checkbox) are the
    # opposite case: "filled or not" is meaningless once "Off" is a real,
    # non-blank value (see core/pdf_extraction.py's docstring) -- a
    # checkbox is *always* "filled", whichever way it's set. What actually
    # matters for these is the *exact* value, e.g. whether this document's
    # Yes/Off matches whatever the rest of the folder mostly answered.
    # They're also excluded from duplicate detection entirely (see module
    # docstring) -- matching on a shared checkbox answer alone is noise,
    # not evidence of a duplicate registration.
    low_cardinality_columns = _low_cardinality_columns(df, field_columns)
    typical_value = {c: _column_typical_value(df, c) for c in low_cardinality_columns}
    duplicate_comparable_columns = [
        c for c in field_columns if c not in low_cardinality_columns
    ]

    for _, row in df.iterrows():
        fname = row[SOURCE_FILE_COLUMN]

        if fname in extraction_errors:
            results[fname] = DocumentClassification(
                fname, "red", [f"Errore di lettura: {extraction_errors[fname]}"]
            )
            continue

        reasons: list[str] = []
        doc_presence = presence[fname]

        mismatches = 0
        for c in field_columns:
            if c in low_cardinality_columns:
                actual = str(row[c]) if _is_filled(row[c]) else ""
                if actual != typical_value[c]:
                    mismatches += 1
            elif doc_presence[c] != majority_filled[c]:
                mismatches += 1
        deviation_ratio = mismatches / len(field_columns)

        if _is_duplicate(fname, row, df, duplicate_comparable_columns):
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


def _low_cardinality_columns(df: pd.DataFrame, field_columns: list[str]) -> set[str]:
    """Columns with at most 2 distinct non-blank values across the whole
    folder -- almost always a Yes/Off-style checkbox, or any other field
    everyone effectively answers the same handful of ways. See module
    docstring for why these are excluded from duplicate detection and
    compared by exact value (not just presence) for structural deviation."""
    low_card: set[str] = set()
    for c in field_columns:
        distinct_values = {str(v) for v in df[c] if _is_filled(v)}
        if len(distinct_values) <= 2:
            low_card.add(c)
    return low_card


def _column_typical_value(df: pd.DataFrame, column: str) -> str:
    """The most common exact value in `column` across the folder -- blank
    counts as a value in its own right (so "mostly left unchecked" is a
    perfectly valid typical value). Only meaningful for low-cardinality
    (checkbox-like) columns -- see _low_cardinality_columns."""
    values = df[column].apply(lambda v: str(v) if _is_filled(v) else "")
    counts = values.value_counts()
    return str(counts.idxmax()) if not counts.empty else ""


def _is_duplicate(
    fname: str, row: pd.Series, df: pd.DataFrame, comparable_columns: list[str]
) -> bool:
    """`comparable_columns` should already exclude low-cardinality fields
    (see _low_cardinality_columns) -- everything passed in here is treated
    as a potentially identifying value."""
    filled_fields = [c for c in comparable_columns if _is_filled(row[c])]
    # Require at least a couple of filled fields before comparing -- a
    # document with only one comparable filled field matching everyone
    # else's isn't a meaningful duplicate signal, it's just too little
    # information.
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
