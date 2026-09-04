"""Object-centric scene tree with Python ``+`` / ``-`` composition sugar.

``GeometryItem`` / ``GeometryGroup`` / ``GeometryGroupCutted`` subclass their
pycanha-core counterparts and add operator overloads:

* ``a + b`` -> a new anonymous ``GeometryGroup`` whose children are the flattened
  operands (never mutating the operands).
* ``target - cutter`` -> a new ``GeometryGroupCutted``; chaining ``- cutter``
  appends further cutters to the same cut group. That flattening is sugar, not
  a requirement: since core 0.20 a cut group may itself be cut, so
  ``(a - c1) - c2`` is a legal nested pair and resolves the same way.

Only ``GeometryItem`` whose primitive is a closed solid (Sphere, Cylinder, Cone,
Cube, TriangularPrism) may be a cutter; this is enforced by the C++ side.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pycanha_core as pcc

if TYPE_CHECKING:
    from types import NotImplementedType

# Abstract base of the scene tree; re-exported for isinstance checks.
Geometry = pcc.gmm.Geometry


def _flatten(geometry: pcc.gmm.Geometry) -> list[pcc.gmm.Geometry]:
    """Unwrap an anonymous group into its children, else return ``[geometry]``."""
    if isinstance(geometry, pcc.gmm.GeometryGroup) and geometry.name == "":
        return list(geometry.children)
    return [geometry]


def _union(left: pcc.gmm.Geometry, right: pcc.gmm.Geometry) -> GeometryGroup:
    group: GeometryGroup = GeometryGroup("", _flatten(left) + _flatten(right))
    return group


def _cut(target: pcc.gmm.Geometry, cutter: pcc.gmm.GeometryItem) -> GeometryGroupCutted:
    if isinstance(target, GeometryGroupCutted):
        target.cut_with(cutter)
        return target
    cut: GeometryGroupCutted = GeometryGroupCutted("", [target], [cutter])
    return cut


class GeometryItem(pcc.gmm.GeometryItem):
    """A single meshable primitive plus its ThermalMesh (a scene-tree leaf)."""

    def __add__(self, other: object) -> GeometryGroup | NotImplementedType:
        if not isinstance(other, pcc.gmm.Geometry):
            return NotImplemented
        return _union(self, other)

    def __sub__(self, other: object) -> GeometryGroupCutted | NotImplementedType:
        if not isinstance(other, pcc.gmm.GeometryItem):
            return NotImplemented
        return _cut(self, other)


class GeometryGroup(pcc.gmm.GeometryGroup):
    """A transform applied to a collection of child geometries."""

    def __add__(self, other: object) -> GeometryGroup | NotImplementedType:
        if not isinstance(other, pcc.gmm.Geometry):
            return NotImplemented
        return _union(self, other)

    def __sub__(self, other: object) -> GeometryGroupCutted | NotImplementedType:
        if not isinstance(other, pcc.gmm.GeometryItem):
            return NotImplemented
        return _cut(self, other)


class GeometryGroupCutted(pcc.gmm.GeometryGroupCutted):
    """Boolean-subtract group: targets cut by the union of all cutters."""

    def __add__(self, other: object) -> GeometryGroup | NotImplementedType:
        if not isinstance(other, pcc.gmm.Geometry):
            return NotImplemented
        return _union(self, other)

    def __sub__(self, other: object) -> GeometryGroupCutted | NotImplementedType:
        if not isinstance(other, pcc.gmm.GeometryItem):
            return NotImplemented
        return _cut(self, other)
