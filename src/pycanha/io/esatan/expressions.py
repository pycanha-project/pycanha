"""Safe arithmetic evaluator for ESATAN ``$CONSTANTS`` expressions.

The declarative blocks (``$NODES``, ``$CONDUCTORS``) no longer classify
expressions here: non-numeric expressions are handed straight to the
pycanha-core formula engine (``ExpressionFormula``), which parses them and
attaches the right formula (or rejects intrinsic / entity-referencing
expressions).  See :mod:`pycanha.io.esatan_reader`.

What remains is a small, ``eval``-free arithmetic evaluator used only to
fold ``$CONSTANTS`` definitions such as ``X = k * 2.0`` into a Python
``float`` for parameter registration.  An explicit AST visitor whitelists
``+ - * / ** %``, unary minus / plus, parentheses, numeric literals and
named parameter substitutions.
"""

from __future__ import annotations

import ast
import operator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["SafeEvalError", "safe_arithmetic"]


class SafeEvalError(Exception):
    """Raised when :func:`safe_arithmetic` cannot evaluate an expression."""


_SafeEvalError = SafeEvalError  # legacy alias used inside this module

_BIN_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_UNARY_OPS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def safe_arithmetic(
    text: str,
    *,
    parameters: dict[str, float] | None = None,
) -> float:
    """Evaluate arithmetic over numbers and named parameter values.

    ``parameters`` maps name -> float value.  Any name not present raises
    :class:`SafeEvalError`.  Function calls, attribute access and other
    non-arithmetic syntax are rejected.
    """
    params = parameters or {}
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        msg = f"could not parse arithmetic expression {text!r}: {exc}"
        raise _SafeEvalError(msg) from exc

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            msg = f"unsupported literal {node.value!r}"
            raise _SafeEvalError(msg)
        if isinstance(node, ast.Name):
            if node.id in params:
                return float(params[node.id])
            msg = f"undefined name {node.id!r}"
            raise _SafeEvalError(msg)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return _BIN_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        msg = f"unsupported expression element: {ast.dump(node)}"
        raise _SafeEvalError(msg)

    return _eval(tree)
