"""Free operations over primitives (distance, transform)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pycanha_core as pcc

from ._convert import as_point

if TYPE_CHECKING:
    import numpy.typing as npt


def distance(primitive: Any, point: npt.ArrayLike) -> float:
    """Signed distance from a point to a primitive's surface."""
    return pcc.gmm.distance(primitive, as_point(point))


def transform(primitive: Any, transformation: Any) -> Any:
    """Return a copy of the primitive with the transformation applied."""
    return pcc.gmm.transform(primitive, transformation)
