"""pyvista visualization of gmm triangular meshes.

``to_polydata`` converts a ``TriMeshF`` / ``TriMeshD`` (or a ``GeometryModel``)
into a :class:`pyvista.PolyData`, attaching the per-triangle ``face_id`` and
``node_number`` as cell data. ``plot`` renders it, coloring each face with a
distinct (categorical) color by default.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import matplotlib as mpl
import numpy as np
import pycanha_core as pcc
import pyvista as pv

if TYPE_CHECKING:
    import numpy.typing as npt

_TriMesh = (pcc.gmm.TriMeshD, pcc.gmm.TriMeshF)

#: Cell-data name used to stash the per-face RGB colors for categorical plots.
_RGB_NAME = "_rgb"


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


def categorical_colors(
    ids: npt.ArrayLike,
    *,
    palette: str = "tab20",
    missing: tuple[float, float, float] = (0.6, 0.6, 0.6),
) -> npt.NDArray[np.uint8]:
    """Map integer category ids to distinct RGB colors from a qualitative palette.

    Ids cycle through the palette; negative ids (unassigned) get ``missing``.
    Returns an ``(n, 3)`` ``uint8`` array suitable for pyvista ``rgb=True``.
    """
    id_array = np.asarray(ids).astype(np.int64)
    cmap = mpl.colormaps[palette]
    lut = (np.array([cmap(k)[:3] for k in range(cmap.N)]) * 255).astype(np.uint8)
    colors = lut[np.mod(id_array, cmap.N)]
    colors[id_array < 0] = (np.array(missing) * 255).astype(np.uint8)
    return colors


def colorize_categorical(poly: pv.PolyData, ids: npt.ArrayLike) -> str:
    """Attach categorical RGB cell colors for ``ids`` and return the array name."""
    poly.cell_data[_RGB_NAME] = categorical_colors(ids)
    return _RGB_NAME


def render(
    poly: pv.PolyData,
    *,
    scalars: str | None = "face_id",
    show_edges: bool = True,
    off_screen: bool = False,
    rgb: bool = False,
    scalar_bar: bool = True,
    **kwargs: Any,
) -> pv.Plotter:
    """Render a prepared :class:`pyvista.PolyData` and show it.

    With ``rgb=True`` the ``scalars`` array is interpreted as per-cell RGB colors
    and no scalar bar is drawn. Otherwise ``scalars`` names a cell-data array to
    color by (ignored if absent); pass ``None`` for a flat color. Returns the
    :class:`pyvista.Plotter` (useful with ``off_screen=True`` for headless
    rendering / testing).
    """
    plotter = pv.Plotter(off_screen=off_screen)
    if rgb:
        plotter.add_mesh(
            poly, scalars=scalars, rgb=True, show_edges=show_edges, show_scalar_bar=False, **kwargs
        )
    else:
        active = scalars if (scalars is not None and scalars in poly.cell_data) else None
        plotter.add_mesh(
            poly, scalars=active, show_edges=show_edges, show_scalar_bar=scalar_bar, **kwargs
        )
    plotter.show()
    return plotter


def plot(
    obj: object,
    *,
    scalars: str | None = "face_id",
    show_edges: bool = True,
    off_screen: bool = False,
    **kwargs: Any,
) -> pv.Plotter:
    """Render a TriMesh or GeometryModel with pyvista.

    ``scalars="face_id"`` (the default) colors each face a distinct color;
    ``"node_number"`` uses a continuous scale; ``None`` is a flat color. Returns
    the :class:`pyvista.Plotter` (useful with ``off_screen=True`` for headless
    rendering / testing).
    """
    poly = to_polydata(obj)
    if scalars == "face_id" and "face_id" in poly.cell_data:
        name = colorize_categorical(poly, np.asarray(poly.cell_data["face_id"]))
        return render(
            poly, scalars=name, rgb=True, show_edges=show_edges, off_screen=off_screen, **kwargs
        )
    return render(poly, scalars=scalars, show_edges=show_edges, off_screen=off_screen, **kwargs)
