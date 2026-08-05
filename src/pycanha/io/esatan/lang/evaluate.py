"""Constant-folding evaluation of ESATAN expressions.

Geometry attributes in practice hold literals, vectors and symbol references,
but the language allows arithmetic anywhere, and hand-authored models use it.
Expressions are therefore evaluated eagerly against the variables declared so
far, which is faithful as long as a variable is not redefined after geometry has
been built from it -- ESATAN binds variables *dynamically*, so a later
redefinition retroactively changes that geometry.  That case is detected by the
caller and reported rather than silently mismodelled.

Two things about the function library are easy to get wrong and are handled
here: **trigonometry works in degrees** (``SIN``/``COS``/``TAN`` take degrees,
``ASIN``/``ACOS``/``ATAN``/``ATAN2`` return them), and ``EVAL`` freezes a value
rather than computing anything -- under eager evaluation it is the identity.
"""

from __future__ import annotations

import math
import operator
from typing import TYPE_CHECKING

from . import ast

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

__all__ = [
    "EvaluationError",
    "Value",
    "as_float",
    "as_int",
    "as_sequence",
    "as_vector",
    "evaluate",
]

#: ``ATAN2`` is the only predefined function taking two arguments.
_ATAN2_ARITY = 2

type Value = float | int | str | bool | tuple[Value, ...]


class EvaluationError(Exception):
    """An expression could not be reduced to a constant."""


def _to_number(value: Value) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        msg = f"expected a number, got {value!r}"
        raise EvaluationError(msg)
    return float(value)


def _degrees_in(func: Callable[[float], float]) -> Callable[[float], float]:
    return lambda value: func(math.radians(value))


def _degrees_out(func: Callable[[float], float]) -> Callable[[float], float]:
    return lambda value: math.degrees(func(value))


def _length(value: Value) -> int:
    if isinstance(value, str | tuple):
        return len(value)
    msg = f"LEN expects a string or a vector, got {value!r}"
    raise EvaluationError(msg)


#: Single-argument predefined functions (Workbench "functions", positional).
_UNARY_FUNCTIONS: dict[str, Callable[[Value], Value]] = {
    "ABS": lambda v: abs(_to_number(v)),
    "ACOS": lambda v: _degrees_out(math.acos)(_to_number(v)),
    "ALOG10": lambda v: math.log10(_to_number(v)),
    "ASIN": lambda v: _degrees_out(math.asin)(_to_number(v)),
    "ATAN": lambda v: _degrees_out(math.atan)(_to_number(v)),
    "COS": lambda v: _degrees_in(math.cos)(_to_number(v)),
    "DEG": lambda v: math.degrees(_to_number(v)),
    "EVAL": lambda v: v,
    "EXP": lambda v: math.exp(_to_number(v)),
    "INT": lambda v: int(_to_number(v)),
    "LEN": _length,
    "LOG": lambda v: math.log(_to_number(v)),
    "LOG10": lambda v: math.log10(_to_number(v)),
    "RAD": lambda v: math.radians(_to_number(v)),
    "REAL": _to_number,
    "SIN": lambda v: _degrees_in(math.sin)(_to_number(v)),
    "SQRT": lambda v: math.sqrt(_to_number(v)),
    "TAN": lambda v: _degrees_in(math.tan)(_to_number(v)),
}

_BINARY_OPERATORS: dict[str, Callable[[float, float], float]] = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "**": operator.pow,
}

_COMPARISONS: dict[str, Callable[[Value, Value], bool]] = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": lambda a, b: _to_number(a) > _to_number(b),
    ">=": lambda a, b: _to_number(a) >= _to_number(b),
    "<": lambda a, b: _to_number(a) < _to_number(b),
    "<=": lambda a, b: _to_number(a) <= _to_number(b),
}


def evaluate(expr: ast.Expr, variables: Mapping[str, Value] | None = None) -> Value:
    """Reduce *expr* to a constant, resolving names through *variables*.

    Raises :class:`EvaluationError` for anything that cannot be reduced -- an
    unknown symbol, a dotted attribute path, or an unsupported function.
    """
    known: Mapping[str, Value] = {} if variables is None else variables
    return _evaluate(expr, known)


def _evaluate(expr: ast.Expr, variables: Mapping[str, Value]) -> Value:
    if isinstance(expr, ast.Num | ast.Str | ast.Bool):
        return expr.value
    if isinstance(expr, ast.Vector | ast.Array):
        return tuple(_evaluate(item, variables) for item in expr.items)
    if isinstance(expr, ast.Ref):
        return _evaluate_ref(expr, variables)
    if isinstance(expr, ast.UnaryOp):
        return _evaluate_unary(expr, variables)
    if isinstance(expr, ast.BinOp):
        return _evaluate_binary(expr, variables)
    return _evaluate_call(expr, variables)


def _evaluate_ref(expr: ast.Ref, variables: Mapping[str, Value]) -> Value:
    if len(expr.path) > 1:
        msg = f"attribute access is not supported in expressions: {'.'.join(expr.path)}"
        raise EvaluationError(msg)
    try:
        return variables[expr.name]
    except KeyError:
        msg = f"unknown symbol: {expr.name}"
        raise EvaluationError(msg) from None


def _evaluate_unary(expr: ast.UnaryOp, variables: Mapping[str, Value]) -> Value:
    operand = _evaluate(expr.operand, variables)
    if expr.op == "!":
        return not operand
    if expr.op == "-":
        return -_to_number(operand)
    return _to_number(operand)


def _evaluate_binary(expr: ast.BinOp, variables: Mapping[str, Value]) -> Value:
    left = _evaluate(expr.left, variables)
    if expr.op == "&&":
        return bool(left) and bool(_evaluate(expr.right, variables))
    if expr.op == "||":
        return bool(left) or bool(_evaluate(expr.right, variables))
    right = _evaluate(expr.right, variables)
    if expr.op in _COMPARISONS:
        return _COMPARISONS[expr.op](left, right)
    if expr.op == "+" and isinstance(left, str) and isinstance(right, str):
        return left + right
    operation = _BINARY_OPERATORS.get(expr.op)
    if operation is None:
        msg = f"unsupported operator: {expr.op}"
        raise EvaluationError(msg)
    return operation(_to_number(left), _to_number(right))


def _evaluate_call(expr: ast.Call, variables: Mapping[str, Value]) -> Value:
    name = expr.name.upper()
    arguments = [_evaluate(argument, variables) for argument in expr.positional]
    if name == "ATAN2" and len(arguments) == _ATAN2_ARITY:
        return math.degrees(math.atan2(_to_number(arguments[0]), _to_number(arguments[1])))
    function = _UNARY_FUNCTIONS.get(name)
    if function is None or len(arguments) != 1:
        msg = f"unsupported function call: {expr.name}"
        raise EvaluationError(msg)
    return function(arguments[0])


def as_float(value: Value) -> float:
    """Coerce an evaluated value to a float, or raise :class:`EvaluationError`."""
    return _to_number(value)


def as_int(value: Value) -> int:
    """Coerce an evaluated value to an int, rejecting a non-integral float."""
    number = _to_number(value)
    if number != int(number):
        msg = f"expected an integer, got {value!r}"
        raise EvaluationError(msg)
    return int(number)


def as_vector(value: Value, size: int = 3) -> tuple[float, ...]:
    """Coerce an evaluated value to a fixed-length tuple of floats."""
    if not isinstance(value, tuple) or len(value) != size:
        msg = f"expected a {size}-element vector, got {value!r}"
        raise EvaluationError(msg)
    return tuple(_to_number(item) for item in value)


def as_sequence(value: Value) -> Sequence[float]:
    """Coerce an evaluated value to a sequence of floats of any length."""
    if not isinstance(value, tuple):
        msg = f"expected a list of numbers, got {value!r}"
        raise EvaluationError(msg)
    return [_to_number(item) for item in value]
