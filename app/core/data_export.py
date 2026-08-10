"""
"Esporta dati come..." (Phase 7): writes the current table -- whatever the
filter pipeline currently shows, not necessarily the raw extraction -- to
CSV, Excel, a standalone SQLite database file, or plain tab-separated text.
Entirely local, no server, matching the rest of the app's design.

No Qt dependency -- unit-tested headlessly against real pandas DataFrames,
round-tripping every format back through its own reader.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable

import pandas as pd

# Same table-name convention as core/sql_filter.py's in-memory filter table.
SQL_TABLE_NAME = "data"

EXTENSION_BY_FORMAT: dict[str, str] = {
    "csv": ".csv",
    "excel": ".xlsx",
    "sql": ".db",
    "text": ".txt",
}
FORMAT_BY_EXTENSION: dict[str, str] = {ext: fmt for fmt, ext in EXTENSION_BY_FORMAT.items()}


class ExportError(Exception):
    """Wraps any pandas/sqlite3/openpyxl failure so the GUI layer only
    needs to catch one exception type; str(exc) is safe to show as-is."""


def export_csv(df: pd.DataFrame, path: Path) -> None:
    try:
        df.to_csv(path, index=False, encoding="utf-8-sig")
    except OSError as exc:
        raise ExportError(str(exc)) from exc


def export_excel(df: pd.DataFrame, path: Path) -> None:
    try:
        df.to_excel(path, index=False, engine="openpyxl")
    except (OSError, ValueError) as exc:
        raise ExportError(str(exc)) from exc


def export_sql(df: pd.DataFrame, path: Path) -> None:
    try:
        # A fresh export replaces the file outright -- otherwise a leftover
        # database from a previous export at the same path could keep an
        # old, stale copy of the table sitting alongside/instead of the new
        # one depending on to_sql's if_exists behaviour.
        if path.exists():
            path.unlink()
        with sqlite3.connect(str(path)) as conn:
            df.to_sql(SQL_TABLE_NAME, conn, index=False)
    except (OSError, ValueError, sqlite3.Error) as exc:
        raise ExportError(str(exc)) from exc


def export_plain_text(df: pd.DataFrame, path: Path) -> None:
    try:
        df.to_csv(path, index=False, sep="\t", encoding="utf-8-sig")
    except OSError as exc:
        raise ExportError(str(exc)) from exc


_EXPORTERS: dict[str, Callable[[pd.DataFrame, Path], None]] = {
    "csv": export_csv,
    "excel": export_excel,
    "sql": export_sql,
    "text": export_plain_text,
}


def export_dataframe(df: pd.DataFrame, path: Path, fmt: str) -> None:
    exporter = _EXPORTERS.get(fmt)
    if exporter is None:
        raise ExportError(f"Formato di esportazione sconosciuto: {fmt}")
    exporter(df, path)
