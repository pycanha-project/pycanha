"""Pure-Python implementations of ESATAN/Mortran intrinsics.

Used **only** for parse-time snapshot evaluation of expressions in the
$NODES and $CONDUCTORS blocks.  When pycanha-core exposes a C++
ExpressionFormula that understands these intrinsics, the snapshot path
can be replaced with a real formula attached to the entity.

Each registered intrinsic is a ``Callable[[Sequence[float], dict[str, ndarray]], float]``
where the first argument is the list of evaluated positional arguments
and the second is the dictionary of ``$ARRAYS`` data parsed earlier.
The dictionary maps an array name to a 2-D ``numpy.ndarray`` whose first
column is the lookup variable and remaining columns are the interpolated
values (matching the ESATAN convention).

# TODO: replace the snapshot path with a C++ ExpressionFormula once the
# core supports intrinsic dispatch over ThermalData tables.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

IntrinsicFn = Callable[[list[object], dict[str, np.ndarray]], float]

INTRINSIC_NAMES: frozenset[str] = frozenset(
    {"INTRP1", "INTRP2", "NODFN1", "CNDFN1", "TAV"}
)


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
    t = float(args[0])  # type: ignore[arg-type]
    table = _resolve_table(args[1], arrays)
    idx = int(args[2])  # type: ignore[arg-type]
    return _interp_column(t, table, idx)


def _nodfn1(args: list[object], arrays: dict[str, np.ndarray]) -> float:
    return _intrp1(args, arrays)


def _cndfn1(args: list[object], arrays: dict[str, np.ndarray]) -> float:
    if len(args) != 4:
        msg = f"CNDFN1 expects 4 args, got {len(args)}"
        raise TypeError(msg)
    t1 = float(args[0])  # type: ignore[arg-type]
    t2 = float(args[1])  # type: ignore[arg-type]
    table = _resolve_table(args[2], arrays)
    idx = int(args[3])  # type: ignore[arg-type]
    return _interp_column(0.5 * (t1 + t2), table, idx)


def _tav(args: list[object], _arrays: dict[str, np.ndarray]) -> float:
    if len(args) != 2:
        msg = f"TAV expects 2 args, got {len(args)}"
        raise TypeError(msg)
    return 0.5 * (float(args[0]) + float(args[1]))  # type: ignore[arg-type]


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
