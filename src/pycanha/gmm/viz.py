"""pyvista visualization of gmm triangular meshes.

``to_polydata`` converts a ``TriMeshF`` / ``TriMeshD`` (or a ``GeometryModel``)
into a :class:`pyvista.PolyData`, attaching the per-triangle ``face_id`` and
``node_number`` as cell data. ``plot`` renders it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pycanha_core as pcc
import pyvista as pv

_TriMesh = (pcc.gmm.TriMeshD, pcc.gmm.TriMeshF)


def _resolve_mesh(obj: object) -> Any:
    """Return the TriMesh to render for a TriMesh or a GeometryModel."""
    if isinstance(obj, _TriMesh):
        return obj
    if isinstance(obj, pcc.gmm.GeometryModel):
        return obj.mesh
    msg = f"cannot visualize object of type {type(obj).__name__!r}"
    raise TypeError(msg)


def to_polydata(obj: object) -> pv.PolyData:
    """Build a :class:`pyvista.PolyData` from a TriMesh or GeometryModel.

    Cell data ``face_id`` (per triangle) and ``node_number`` (tmm node of each
    triangle's face, ``-1`` when unassigned) are attached.
    """
    mesh = _resolve_mesh(obj)
    vertices = np.ascontiguousarray(mesh.vertices, dtype=np.float64)
    triangles = np.ascontiguousarray(mesh.triangles)
    n_tri = int(triangles.shape[0])

    if n_tri == 0:
        return pv.PolyData(vertices)

    faces = np.empty((n_tri, 4), dtype=np.int64)
    faces[:, 0] = 3
    faces[:, 1:] = triangles
    poly = pv.PolyData(vertices, faces.ravel())

    face_ids = np.asarray(mesh.face_ids)
    poly.cell_data["face_id"] = face_ids

    node_numbers = np.asarray(mesh.node_numbers)
    if node_numbers.size:
        poly.cell_data["node_number"] = node_numbers[face_ids.astype(np.int64)]
    else:
        poly.cell_data["node_number"] = np.full(n_tri, -1, dtype=np.int32)
    return poly


def plot(
    obj: object,
    *,
    scalars: str | None = "face_id",
    show_edges: bool = True,
    off_screen: bool = False,
    **kwargs: Any,
) -> pv.Plotter:
    """Render a TriMesh or GeometryModel with pyvista.

    ``scalars`` selects a cell-data array to color by ("face_id" or
    "node_number"); pass ``None`` for a flat color. Returns the
    :class:`pyvista.Plotter` (useful with ``off_screen=True`` for headless
    rendering / testing).
    """
    poly = to_polydata(obj)
    active = scalars if (scalars is not None and scalars in poly.cell_data) else None
    plotter = pv.Plotter(off_screen=off_screen)
    plotter.add_mesh(poly, scalars=active, show_edges=show_edges, **kwargs)
    plotter.show()
    return plotter
