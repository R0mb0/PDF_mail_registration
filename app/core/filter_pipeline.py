"""
The filter pipeline: an ordered, append-only-except-for-the-last-item
stack of "steps" applied on top of the raw extraction table, plus
undo/redo over that same stack.

Two kinds of step, exactly matching the spec:

  - "expression": the result of running an Excel-subset or SQL filter
    (core/excel_formula.py / core/sql_filter.py).
  - "manual_edits": a bag of {(row_key, column): new_value} overrides
    collecting every manual cell edit made *while at least one step is
    already active* -- per spec, editing a cell when the stack is empty
    just mutates the raw table directly and creates no chip. Once a step
    exists, the first manual edit opens a new manual_edits step; further
    edits are folded into that same step until another expression filter
    is run, at which point the *next* manual edit opens a fresh one.

Integrity rule (spec): only the *last* step may ever be removed --
remove_last_step() is exactly what both "click the X on the last chip"
and Ctrl+Z do; redo() is Ctrl+Y. Recomputation always replays the full
step list from the base table rather than trying to patch the cached
result in place -- correctness over micro-optimizing tables of this size
(a few dozen rows).

No Qt dependency -- unit-tested headlessly (see project dev notes).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd

from core.excel_formula import FormulaError, evaluate_filter
from core.pdf_extraction import SOURCE_FILE_COLUMN
from core.sql_filter import SqlFilterError, evaluate_sql

StepKind = Literal["expression", "manual_edits"]
ExpressionMode = Literal["excel", "sql"]


class FilterPipelineError(Exception):
    """Wraps FormulaError/SqlFilterError so callers only need to catch one
    exception type; .message is always safe to show to the user."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class FilterStep:
    kind: StepKind
    mode: ExpressionMode | None = None          # only for "expression"
    expression: str | None = None                # only for "expression"
    edits: dict[tuple[str, str], Any] = field(default_factory=dict)  # only for "manual_edits"


class FilterPipeline:
    def __init__(self) -> None:
        self._base_df: pd.DataFrame = pd.DataFrame()
        self._steps: list[FilterStep] = []
        self._redo_stack: list[FilterStep] = []

    # ---------------------------------------------------------------- setup --
    def set_base_dataframe(self, df: pd.DataFrame) -> None:
        """Called with a fresh extraction result -- on folder open, and
        again (from Phase 6 onward) whenever a PDF is re-saved, per spec:
        changing the source data discards the whole filter history."""
        self._base_df = df.copy()
        self._steps = []
        self._redo_stack = []

    # -------------------------------------------------------------- queries --
    @property
    def steps(self) -> list[FilterStep]:
        return list(self._steps)

    def can_undo(self) -> bool:
        return len(self._steps) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def current_dataframe(self) -> pd.DataFrame:
        return self._replay(self._steps)

    # -------------------------------------------------------------- actions --
    def apply_expression_filter(self, mode: ExpressionMode, expression: str) -> None:
        """Raises FilterPipelineError (message is user-facing) on bad
        syntax; the pipeline is left completely unchanged in that case."""
        step = FilterStep(kind="expression", mode=mode, expression=expression)
        self._apply_step(self.current_dataframe(), step)  # validates by actually running it
        self._steps.append(step)
        self._redo_stack.clear()

    def record_manual_edit(self, row_key: str, column: str, value: Any) -> None:
        # Any manual edit is new forward progress -- whether it mutates the
        # raw table directly, extends the current chip, or opens a new one,
        # it invalidates whatever used to be redo-able, same as running a
        # new filter does. Standard undo/redo semantics: any fresh change
        # after an undo drops the redo history.
        self._redo_stack.clear()

        if not self._steps:
            # No active filter: edit the raw table directly, no chip --
            # per spec.
            mask = self._base_df[SOURCE_FILE_COLUMN] == row_key
            self._base_df.loc[mask, column] = value
            return

        last = self._steps[-1]
        if last.kind == "manual_edits":
            last.edits[(row_key, column)] = value
        else:
            new_step = FilterStep(kind="manual_edits", edits={(row_key, column): value})
            self._steps.append(new_step)

    def remove_last_step(self) -> None:
        """Same operation as Ctrl+Z -- removing a manual_edits step
        restores those cells to whatever the step before it produced,
        simply by no longer replaying it."""
        if self._steps:
            self._redo_stack.append(self._steps.pop())

    def undo(self) -> None:
        self.remove_last_step()

    def redo(self) -> None:
        if self._redo_stack:
            self._steps.append(self._redo_stack.pop())

    # ------------------------------------------------------------- internal --
    def _replay(self, steps: list[FilterStep]) -> pd.DataFrame:
        df = self._base_df.copy()
        for step in steps:
            df = self._apply_step(df, step)
        return df

    @staticmethod
    def _apply_step(df: pd.DataFrame, step: FilterStep) -> pd.DataFrame:
        if step.kind == "expression":
            try:
                if step.mode == "excel":
                    return evaluate_filter(df, step.expression or "")
                if step.mode == "sql":
                    return evaluate_sql(df, step.expression or "")
            except FormulaError as exc:
                raise FilterPipelineError(exc.args[0]) from exc
            except SqlFilterError as exc:
                raise FilterPipelineError(exc.args[0]) from exc
            raise FilterPipelineError(f"Modalità filtro sconosciuta: {step.mode}")

        if step.kind == "manual_edits":
            if SOURCE_FILE_COLUMN not in df.columns:
                return df
            df = df.copy()
            for (row_key, column), value in step.edits.items():
                if column not in df.columns:
                    continue
                mask = df[SOURCE_FILE_COLUMN] == row_key
                df.loc[mask, column] = value
            return df

        return df
