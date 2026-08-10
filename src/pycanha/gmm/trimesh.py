"""Triangular meshes: TriMeshD (float64) and TriMeshF (float32).

These are built and cached by the core, so nothing on the Python side ever
constructs one; they are re-exported rather than subclassed, because a subclass
would not match the objects the core hands back and any method defined on it
would be unreachable from ``GeometryModel.mesh`` and friends.

For pyvista output use the free functions, which take any mesh:
``pycanha.plot.to_polydata(mesh)`` and ``pycanha.plot.plot(mesh)``.
"""

from __future__ import annotations

import pycanha_core as pcc

TriMeshD = pcc.gmm.TriMeshD
TriMeshF = pcc.gmm.TriMeshF
