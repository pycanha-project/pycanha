"""Reading a primitive's own frame, for the exchange formats that write one.

Every surface of revolution pycanha holds carries the same three-point frame --
an origin, a point along the axis, and a point fixing where the angular sweep
starts -- with its radii in separate fields.  Both exchange formats have to take
that frame apart in the same way, and neither should have to import the other to
do it, so the arithmetic lives here.

The subtlety these helpers exist for is that the *distance* to the third point
means nothing.  A primitive built from shell-coordinate parameters carries a
unit vector there and its true size in a radius field, so measuring a radius off
the frame is right for one spelling and wrong by a factor of the radius for the
other.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Protocol

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

__all__ = ["Revolved", "axis_of", "full_turn", "rim_of", "rim_point", "unit_rim"]

#: How near a sweep has to be to a whole turn to count as one, in radians.
_FULL_TURN_TOL: Final = 1e-9


class Revolved(Protocol):
    """The frame every surface of revolution carries: origin, axis, datum, sector.

    Declared as properties rather than attributes because that is what the
    compiled primitives expose, and a protocol asking for a settable attribute
    is not satisfied by a read-only one.
    """

    @property
    def p1(self) -> npt.NDArray[np.float64]:
        """The origin: a centre, a base centre or a vertex."""
        ...

    @property
    def p2(self) -> npt.NDArray[np.float64]:
        """A point along the axis, at the far end."""
        ...

    @property
    def p3(self) -> npt.NDArray[np.float64]:
        """A point fixing where the angular sweep starts."""
        ...

    @property
    def start_angle(self) -> float:
        """Where the sweep begins, in radians."""
        ...

    @property
    def end_angle(self) -> float:
        """Where the sweep ends, in radians."""
        ...


def axis_of(primitive: Revolved) -> npt.NDArray[np.float64]:
    """The axis vector of a surface of revolution, from its three-point frame."""
    far: npt.NDArray[np.float64] = np.asarray(primitive.p2, dtype=float)
    near: npt.NDArray[np.float64] = np.asarray(primitive.p1, dtype=float)
    return far - near


def rim_of(primitive: Revolved) -> npt.NDArray[np.float64]:
    """The datum vector of a surface of revolution, from its three-point frame."""
    datum: npt.NDArray[np.float64] = np.asarray(primitive.p3, dtype=float)
    origin: npt.NDArray[np.float64] = np.asarray(primitive.p1, dtype=float)
    return datum - origin


def unit_rim(primitive: Revolved) -> npt.NDArray[np.float64]:
    """The unit radius direction: where angles start, squared up against the axis."""
    axis = axis_of(primitive)
    rim = rim_of(primitive)
    perpendicular = rim - axis * (float(np.dot(rim, axis)) / float(np.dot(axis, axis)))
    return perpendicular / np.linalg.norm(perpendicular)


def rim_point(primitive: Revolved, radius: float) -> npt.NDArray[np.float64]:
    """The point at *radius* from ``p1``, in the primitive's angular datum direction."""
    origin: npt.NDArray[np.float64] = np.asarray(primitive.p1, dtype=float)
    return origin + unit_rim(primitive) * radius


def full_turn(primitive: Revolved) -> bool:
    """Whether the sweep covers a whole revolution.

    Angles are stored in radians, so a full turn is ``2*pi``.  Comparing against
    360 would make every full surface of revolution look like a sector a few
    degrees wide -- correct-looking geometry with a hundredth of the area.
    """
    return abs(float(primitive.end_angle) - float(primitive.start_angle) - 2.0 * np.pi) < (
        _FULL_TURN_TOL
    )
