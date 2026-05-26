"""Pure-Python implementations of ESATAN/Mortran intrinsics.

Currently **unused** by the reader: declarative ``$NODES`` / ``$CONDUCTORS``
expressions go straight to the pycanha-core formula engine, which rejects
intrinsics (the reader logs a warning and attaches no formula).  This module
is kept to back a future ``GeneralFormula`` Python backend (milestone M4) that
will evaluate the rejected intrinsic expressions.

Each registered intrinsic is a ``Callable[[list[object], dict[str, ndarray]], float]``
where the first argument is the list of evaluated positional arguments and the
second is the dictionary of ``$ARRAYS`` data.  The dictionary maps an array
name to a 2-D ``numpy.ndarray`` whose first column is the lookup variable and
remaining columns are the interpolated values (matching the ESATAN convention).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

IntrinsicFn = Callable[[list[object], dict[str, np.ndarray]], float]

INTRINSIC_NAMES: frozenset[str] = frozenset(
    {"INTRP1", "INTRP2", "NODFN1", "CNDFN1", "TAV"}
)


def _as_float(value: object) -> float:
    """Coerce a parsed intrinsic argument to ``float`` (numbers or numeric strings)."""
    if isinstance(value, (int, float, str)):
        return float(value)
    msg = f"intrinsic expected a number, got {type(value).__name__}"
    raise TypeError(msg)


def _as_int(value: object) -> int:
    """Coerce a parsed intrinsic argument to ``int``."""
    return int(_as_float(value))


def _interp_column(t: float, table: np.ndarray, col_index: int) -> float:
    if table.ndim != 2 or table.shape[1] < 2:
        msg = "intrinsic table must be 2-D with at least 2 columns"
        raise ValueError(msg)
    n_value_cols = table.shape[1] - 1
    if not 1 <= col_index <= n_value_cols:
        msg = f"intrinsic column index {col_index} out of range 1..{n_value_cols}"
        raise IndexError(msg)
    xs = table[:, 0]
    ys = table[:, col_index]
    return float(np.interp(t, xs, ys))


def _resolve_table(arg: object, arrays: dict[str, np.ndarray]) -> np.ndarray:
    if isinstance(arg, np.ndarray):
        return arg
    if isinstance(arg, str) and arg in arrays:
        return arrays[arg]
    msg = f"unknown $ARRAYS reference {arg!r}"
    raise KeyError(msg)


def _intrp1(args: list[object], arrays: dict[str, np.ndarray]) -> float:
    if len(args) != 3:
        msg = f"INTRP1 expects 3 args, got {len(args)}"
        raise TypeError(msg)
    t = _as_float(args[0])
    table = _resolve_table(args[1], arrays)
    idx = _as_int(args[2])
    return _interp_column(t, table, idx)


def _nodfn1(args: list[object], arrays: dict[str, np.ndarray]) -> float:
    return _intrp1(args, arrays)


def _cndfn1(args: list[object], arrays: dict[str, np.ndarray]) -> float:
    if len(args) != 4:
        msg = f"CNDFN1 expects 4 args, got {len(args)}"
        raise TypeError(msg)
    t1 = _as_float(args[0])
    t2 = _as_float(args[1])
    table = _resolve_table(args[2], arrays)
    idx = _as_int(args[3])
    return _interp_column(0.5 * (t1 + t2), table, idx)


def _tav(args: list[object], _arrays: dict[str, np.ndarray]) -> float:
    if len(args) != 2:
        msg = f"TAV expects 2 args, got {len(args)}"
        raise TypeError(msg)
    return 0.5 * (_as_float(args[0]) + _as_float(args[1]))


def _intrp2(_args: list[object], _arrays: dict[str, np.ndarray]) -> float:
    msg = "INTRP2 is not implemented yet"
    # TODO: 2-D interpolation support against $TABLE-style arrays once
    # ThermalData exposes them.
    raise NotImplementedError(msg)


INTRINSIC_REGISTRY: dict[str, IntrinsicFn] = {
    "INTRP1": _intrp1,
    "NODFN1": _nodfn1,
    "CNDFN1": _cndfn1,
    "TAV": _tav,
    "INTRP2": _intrp2,
}
