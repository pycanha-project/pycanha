"""Array-like coercion helpers for the gmm convenience layer.

The pycanha-core primitive and transformation constructors take strict
``numpy.float64`` arrays (nanobind rejects Python tuples/lists). These helpers
let the pycanha-side subclasses accept any array-like (tuple, list, ndarray)
and coerce it to the exact layout the bindings expect.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt


def _as_vector(value: npt.ArrayLike, size: int, what: str) -> npt.NDArray[np.float64]:
    arr = np.ascontiguousarray(value, dtype=np.float64)
    if arr.shape != (size,):
        msg = f"expected a {size}-component {what}, got shape {arr.shape}"
        raise ValueError(msg)
    return arr


def as_point(value: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """Coerce an array-like to a contiguous ``(3,)`` float64 point/vector."""
    return _as_vector(value, 3, "point/vector")


def as_quaternion(value: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """Coerce an array-like to a contiguous ``(4,)`` float64 (w, x, y, z)."""
    return _as_vector(value, 4, "quaternion")


def as_matrix3(value: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """Coerce an array-like to a contiguous ``(3, 3)`` float64 matrix."""
    arr = np.ascontiguousarray(value, dtype=np.float64)
    if arr.shape != (3, 3):
        msg = f"expected a 3x3 rotation matrix, got shape {arr.shape}"
        raise ValueError(msg)
    return arr
