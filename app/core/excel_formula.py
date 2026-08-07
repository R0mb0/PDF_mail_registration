"""
Safe evaluator for the "Excel-subset" filter-bar mode.

Deliberately NOT a general Python eval(): expressions are parsed with the
standard `ast` module and walked by hand, only permitting a small
whitelisted grammar (comparisons, and/or/not, +/-/*//, and a fixed set of
Excel-like functions). Anything outside that grammar raises FormulaError
with a message meant to be shown directly to the user in an alert, per
spec ("deve presentare i soliti messaggi nel caso in cui la sintassi non
sia corretta").

Column references use Excel-style bracket syntax: [Column Name]. Supports
column names containing spaces or any other characters, since Phase 2's
extraction does not constrain what a PDF's field names look like.

No Qt dependency -- unit-tested headlessly (see project dev notes).
"""

from __future__ import annotations

import ast
import re
from typing import Any

import pandas as pd


class FormulaError(Exception):
    """Raised on any invalid formula -- message is safe to show to the user."""


_COLUMN_REF_RE = re.compile(r"\[([^\]]+)\]")


def _transpile_column_refs(expression: str) -> tuple[str, dict[str, str]]:
    """Replace every [Column Name] with a safe synthetic identifier so the
    result is valid Python syntax, and return the synthetic->real mapping."""
    mapping: dict[str, str] = {}
    reverse: dict[str, str] = {}

    def _replace(match: "re.Match[str]") -> str:
        original = match.group(1)
        if original in reverse:
            return reverse[original]
        synthetic = f"_col_{len(mapping)}"
        mapping[synthetic] = original
        reverse[original] = synthetic
        return synthetic

    transpiled = _COLUMN_REF_RE.sub(_replace, expression)
    return transpiled, mapping


def _normalize_operators(expression: str) -> str:
    # Excel "not equal" -> Python.
    expression = expression.replace("<>", "!=")
    # Excel "&" (string concat only) -> Python "+".
    expression = expression.replace("&", "+")
    # Bare "=" (equality) -> "==", but don't touch <=, >=, ==, != which
    # already contain "=".
    expression = re.sub(r"(?<![<>=!])=(?!=)", "==", expression)
    return expression


_ALLOWED_FUNCTIONS = {
    "IF": lambda cond, a, b: a if cond else b,
    "AND": lambda *args: all(args),
    "OR": lambda *args: any(args),
    "NOT": lambda x: not x,
    "ISBLANK": lambda x: x is None or (isinstance(x, str) and x.strip() == ""),
    "TRIM": lambda x: str(x).strip(),
    "CONCAT": lambda *args: "".join(str(a) for a in args),
    "LEFT": lambda x, n: str(x)[: int(n)],
    "RIGHT": lambda x, n: str(x)[-int(n):] if int(n) > 0 else "",
    "LEN": lambda x: len(str(x)),
    "UPPER": lambda x: str(x).upper(),
    "LOWER": lambda x: str(x).lower(),
}


class _SafeEvaluator:
    """Hand-written recursive evaluator over a restricted AST subset -- no
    eval()/exec() anywhere, so a formula has no way to reach outside this
    whitelist (verified: attribute access, imports, comprehensions, etc.
    all fall through to the final "unsupported syntax" branch)."""

    def __init__(self, row_values: dict[str, Any]) -> None:
        self._row_values = row_values

    def eval(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return self.eval(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in self._row_values:
                return self._row_values[node.id]
            raise FormulaError(f"Riferimento sconosciuto: {node.id}")
        if isinstance(node, ast.BoolOp):
            values = [self.eval(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)
            raise FormulaError("Operatore logico non supportato")
        if isinstance(node, ast.UnaryOp):
            operand = self.eval(node.operand)
            if isinstance(node.op, ast.Not):
                return not operand
            if isinstance(node.op, ast.USub):
                return -operand
            raise FormulaError("Operatore unario non supportato")
        if isinstance(node, ast.BinOp):
            left = self.eval(node.left)
            right = self.eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            raise FormulaError("Operatore aritmetico non supportato")
        if isinstance(node, ast.Compare):
            left = self.eval(node.left)
            result = True
            for op, comparator in zip(node.ops, node.comparators):
                right = self.eval(comparator)
                result = result and self._compare(left, op, right)
                left = right
            return result
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise FormulaError("Chiamata di funzione non valida")
            func = _ALLOWED_FUNCTIONS.get(node.func.id.upper())
            if func is None:
                raise FormulaError(f"Funzione sconosciuta: {node.func.id}")
            args = [self.eval(a) for a in node.args]
            try:
                return func(*args)
            except FormulaError:
                raise
            except Exception as exc:  # noqa: BLE001 -- surfaced to the user as-is
                raise FormulaError(f"Errore in {node.func.id}(...): {exc}") from exc
        raise FormulaError(f"Sintassi non supportata: {type(node).__name__}")

    @staticmethod
    def _compare(left: Any, op: ast.cmpop, right: Any) -> bool:
        try:
            if isinstance(op, ast.Eq):
                if isinstance(left, str) or isinstance(right, str):
                    return str(left) == str(right)
                return left == right
            if isinstance(op, ast.NotEq):
                return not _SafeEvaluator._compare(left, ast.Eq(), right)
            if isinstance(op, ast.Lt):
                return left < right
            if isinstance(op, ast.LtE):
                return left <= right
            if isinstance(op, ast.Gt):
                return left > right
            if isinstance(op, ast.GtE):
                return left >= right
        except TypeError as exc:
            raise FormulaError(f"Confronto non valido tra {left!r} e {right!r}") from exc
        raise FormulaError("Operatore di confronto non supportato")


def evaluate_filter(df: pd.DataFrame, expression: str) -> pd.DataFrame:
    """Evaluate `expression` as a per-row boolean predicate over `df` and
    return the filtered DataFrame (rows where the predicate is truthy).
    Raises FormulaError with a user-facing message on bad syntax/refs."""
    if not expression or not expression.strip():
        raise FormulaError("La formula è vuota.")

    transpiled, column_map = _transpile_column_refs(expression)
    normalized = _normalize_operators(transpiled)

    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"Errore di sintassi: {exc.msg}") from exc

    unknown_columns = [c for c in column_map.values() if c not in df.columns]
    if unknown_columns:
        raise FormulaError("Colonna non trovata: " + ", ".join(unknown_columns))

    keep_mask: list[bool] = []
    for _, row in df.iterrows():
        row_values = {syn: row[real] for syn, real in column_map.items()}
        try:
            result = _SafeEvaluator(row_values).eval(tree)
        except FormulaError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise FormulaError(f"Errore di valutazione: {exc}") from exc
        keep_mask.append(bool(result))

    return df[keep_mask].reset_index(drop=True)
