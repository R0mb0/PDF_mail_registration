"""
SQL filter-bar mode: runs an arbitrary user SQL query against the current
table state.

Uses Python's built-in `sqlite3` (no extra dependency -- swapped in place
of the `duckdb` package originally listed in requirements.txt, since a
plain sqlite3 in-memory table does the job with one less thing that can
fail to install on the user's machine) plus pandas' own to_sql/read_sql,
which work directly against a raw sqlite3 connection without SQLAlchemy.

The table is always exposed to the query as `data`, e.g.:
    SELECT * FROM data WHERE consent_gdpr = 'Yes' ORDER BY reg_last_name
"""

from __future__ import annotations

import sqlite3

import pandas as pd

TABLE_NAME = "data"


class SqlFilterError(Exception):
    """Raised on any invalid SQL -- message is safe to show to the user."""


def evaluate_sql(df: pd.DataFrame, query: str) -> pd.DataFrame:
    if not query or not query.strip():
        raise SqlFilterError("La query è vuota.")

    conn = sqlite3.connect(":memory:")
    try:
        df.to_sql(TABLE_NAME, conn, index=False, if_exists="replace")
        try:
            result = pd.read_sql_query(query, conn)
        except (sqlite3.OperationalError, sqlite3.Warning, pd.errors.DatabaseError) as exc:
            raise SqlFilterError(f"Errore SQL: {exc}") from exc
    finally:
        conn.close()

    return result.reset_index(drop=True)
