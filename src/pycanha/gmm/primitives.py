"""Geometric primitives with array-like point/vector coercion.

Each class subclasses its ``pycanha_core.gmm`` counterpart so instances behave
like the native C++ primitives while accepting tuples/lists (not just strict
float64 arrays) for point, vector and quaternion arguments.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pycanha_core as pcc

from ._convert import as_point, as_quaternion

if TYPE_CHECKING:
    import numpy.typing as npt


class Triangle(pcc.gmm.Triangle):
    """Triangular flat surface defined by three 3D vertices."""

    def __init__(self, p1: npt.ArrayLike, p2: npt.ArrayLike, p3: npt.ArrayLike) -> None:
        super().__init__(as_point(p1), as_point(p2), as_point(p3))


class Rectangle(pcc.gmm.Rectangle):
    """Rectangular flat surface: p1->p2 is one edge, p1->p3 the adjacent edge."""

    def __init__(self, p1: npt.ArrayLike, p2: npt.ArrayLike, p3: npt.ArrayLike) -> None:
        super().__init__(as_point(p1), as_point(p2), as_point(p3))


class Quadrilateral(pcc.gmm.Quadrilateral):
    """General quadrilateral surface defined by four vertices."""

    def __init__(
        self,
        p1: npt.ArrayLike,
        p2: npt.ArrayLike,
        p3: npt.ArrayLike,
        p4: npt.ArrayLike,
    ) -> None:
        super().__init__(as_point(p1), as_point(p2), as_point(p3), as_point(p4))


class Disc(pcc.gmm.Disc):
    """Annular disc segment defined by center, normal, radii and angular extent."""

    def __init__(
        self,
        p1: npt.ArrayLike,
        p2: npt.ArrayLike,
        p3: npt.ArrayLike,
        inner_radius: float,
        outer_radius: float,
        start_angle: float,
        end_angle: float,
    ) -> None:
        super().__init__(
            as_point(p1),
            as_point(p2),
            as_point(p3),
            inner_radius,
            outer_radius,
            start_angle,
            end_angle,
        )


class Cylinder(pcc.gmm.Cylinder):
    """Cylindrical surface segment defined by axis, radius and angular extent."""

    def __init__(
        self,
        p1: npt.ArrayLike,
        p2: npt.ArrayLike,
        p3: npt.ArrayLike,
        radius: float,
        start_angle: float,
        end_angle: float,
    ) -> None:
        super().__init__(as_point(p1), as_point(p2), as_point(p3), radius, start_angle, end_angle)


class Cone(pcc.gmm.Cone):
    """Conical (frustum) surface segment defined by axis, two radii and angles."""

    def __init__(
        self,
        p1: npt.ArrayLike,
        p2: npt.ArrayLike,
        p3: npt.ArrayLike,
        radius1: float,
        radius2: float,
        start_angle: float,
        end_angle: float,
    ) -> None:
        super().__init__(
            as_point(p1),
            as_point(p2),
            as_point(p3),
            radius1,
            radius2,
            start_angle,
            end_angle,
        )


class Sphere(pcc.gmm.Sphere):
    """Spherical surface segment with optional base/apex truncation."""

    def __init__(
        self,
        p1: npt.ArrayLike,
        p2: npt.ArrayLike,
        p3: npt.ArrayLike,
        radius: float,
        base_truncation: float,
        apex_truncation: float,
        start_angle: float,
        end_angle: float,
    ) -> None:
        super().__init__(
            as_point(p1),
            as_point(p2),
            as_point(p3),
            radius,
            base_truncation,
            apex_truncation,
            start_angle,
            end_angle,
        )


class Paraboloid(pcc.gmm.Paraboloid):
    """Paraboloidal surface segment defined by axis, radius and angular extent."""

    def __init__(
        self,
        p1: npt.ArrayLike,
        p2: npt.ArrayLike,
        p3: npt.ArrayLike,
        radius: float,
        start_angle: float,
        end_angle: float,
    ) -> None:
        super().__init__(as_point(p1), as_point(p2), as_point(p3), radius, start_angle, end_angle)


class Cube(pcc.gmm.Cube):
    """Axis-aligned box (rotated by an orientation quaternion), a closed solid."""

    def __init__(
        self,
        center: npt.ArrayLike,
        extent: npt.ArrayLike,
        orientation: npt.ArrayLike = (1.0, 0.0, 0.0, 0.0),
    ) -> None:
        super().__init__(as_point(center), as_point(extent), as_quaternion(orientation))
