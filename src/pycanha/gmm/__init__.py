"""Geometric Mathematical Model subpackage.

Object-centric scene graph mirroring ``pycanha-core`` 0.18: primitives,
materials, thermal meshes, transformations, the scene tree
(``GeometryItem`` / ``GeometryGroup`` / ``GeometryGroupCutted``), the
``GeometryModel`` (incl. ``mesh_parts`` / ``material_table`` raytracer scene
assembly), ``ops`` / ``mesh.ops`` operations, and pyvista visualization with
click-to-inspect face picking.

A thermal mesh states its activity once per calculation -- ``ActiveSide``
selectors for the radiative and the conductive model separately -- so a surface
can take part in one and not the other.  :func:`active_side`,
:func:`active_sides` and :func:`with_side` convert between a selector and the
pair of per-side flags that file formats tend to store.
"""

from __future__ import annotations

import pycanha_core as pcc

from . import mesh, ops, picking, viz
from .materials import BulkMaterial, Color, OpticalMaterial
from .model import GeometryModel
from .primitives import (
    Cone,
    Cube,
    Cylinder,
    Disc,
    Paraboloid,
    Quadrilateral,
    Rectangle,
    Sphere,
    Triangle,
)
from .scene import Geometry, GeometryGroup, GeometryGroupCutted, GeometryItem
from .thermalmesh import ActiveSide, ThermalMesh, active_side, active_sides, with_side
from .transformations import CoordinateTransformation
from .trimesh import TriMeshD, TriMeshF
from .viz import plot, to_polydata

# These add nothing on top of the pycanha-core versions, so they are
# re-exported rather than subclassed: an empty subclass would not match the
# objects the core hands back.
#: Meshing tolerances (chordal deviation).
MeshOptions = pcc.gmm.MeshOptions

#: Meshes a single primitive against a ThermalMesh into a TriMeshD.
UvMesher = pcc.gmm.UvMesher

is_closed_solid = pcc.gmm.is_closed_solid

__all__ = [
    "ActiveSide",
    "BulkMaterial",
    "Color",
    "Cone",
    "CoordinateTransformation",
    "Cube",
    "Cylinder",
    "Disc",
    "Geometry",
    "GeometryGroup",
    "GeometryGroupCutted",
    "GeometryItem",
    "GeometryModel",
    "MeshOptions",
    "OpticalMaterial",
    "Paraboloid",
    "Quadrilateral",
    "Rectangle",
    "Sphere",
    "ThermalMesh",
    "TriMeshD",
    "TriMeshF",
    "Triangle",
    "UvMesher",
    "active_side",
    "active_sides",
    "is_closed_solid",
    "mesh",
    "ops",
    "picking",
    "plot",
    "to_polydata",
    "viz",
    "with_side",
]
