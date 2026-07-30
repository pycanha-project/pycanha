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

from . import picking

if TYPE_CHECKING:
    from collections.abc import Mapping

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


def to_polydata(obj: object, *, both_sides: bool = False) -> pv.PolyData:
    """Build a :class:`pyvista.PolyData` from a TriMesh or GeometryModel.

    Cell data ``face_id`` (per triangle) and ``node_number`` (tmm node of each
    triangle's face, ``-1`` when unassigned) are attached.

    A ThermalMesh face has two sides, each with its own face slot, node number
    and optical material, but the mesh carries only **one** sheet of triangles
    per face and its ``face_ids`` always name the side-1 slot. So the default
    single-sided polydata describes side 1 only, and looking at the geometry from
    behind still shows side-1 data.

    With ``both_sides=True`` every triangle is emitted twice - once as-is for
    side 1 and once with reversed winding (so it faces the other way) carrying
    the side-2 slot's data - and a ``side`` cell array (1 or 2) is added. The two
    copies are coincident, so render them with ``backface_culling=True`` to see
    exactly the side that faces the camera.
    """
    mesh = _resolve_mesh(obj)
    vertices = np.ascontiguousarray(mesh.vertices, dtype=np.float64)
    triangles = np.ascontiguousarray(mesh.triangles)
    n_tri = int(triangles.shape[0])

    if n_tri == 0:
        return pv.PolyData(vertices)

    face_ids = np.asarray(mesh.face_ids).astype(np.int64)
    if both_sides:
        # Reversed winding flips the normal, so the copy faces the other way.
        triangles = np.vstack([triangles, triangles[:, ::-1]])
        # Slots are interleaved per face as [side 1, side 2], so the partner slot
        # of an even side-1 id is id + 1; XOR keeps that pairing symmetric.
        face_ids = np.concatenate([face_ids, face_ids ^ 1])
        n_cells = 2 * n_tri
    else:
        n_cells = n_tri

    faces = np.empty((n_cells, 4), dtype=np.int64)
    faces[:, 0] = 3
    faces[:, 1:] = triangles
    poly = pv.PolyData(vertices, faces.ravel())

    poly.cell_data["face_id"] = face_ids

    node_numbers = np.asarray(mesh.node_numbers)
    if node_numbers.size:
        poly.cell_data["node_number"] = node_numbers[face_ids]
    else:
        poly.cell_data["node_number"] = np.full(n_cells, -1, dtype=np.int32)

    if both_sides:
        poly.cell_data["side"] = np.repeat([1, 2], n_tri).astype(np.int32)
    return poly


def _map_cell_data(
    poly: pv.PolyData,
    data: Mapping[int, float],
    key: str,
    default: float,
) -> npt.NDArray[np.float64]:
    """Spread ``data`` over the cells of ``poly``, keyed by the ``key`` cell array."""
    keys = np.asarray(poly.cell_data[key]).astype(np.int64)
    if not data:
        return np.full(keys.size, default, dtype=np.float64)
    lookup = np.fromiter(data.keys(), dtype=np.int64, count=len(data))
    values = np.fromiter(data.values(), dtype=np.float64, count=len(data))
    order = np.argsort(lookup)
    lookup, values = lookup[order], values[order]
    # searchsorted gives the insertion point, so an exact-match test is needed to
    # tell "this key is in the mapping" from "it would go here".
    position = np.clip(np.searchsorted(lookup, keys), 0, lookup.size - 1)
    return np.where(lookup[position] == keys, values[position], default)


def map_node_data(
    poly: pv.PolyData,
    data: Mapping[int, float],
    *,
    default: float = np.nan,
) -> npt.NDArray[np.float64]:
    """Spread a ``{node number: value}`` mapping over the cells of ``poly``.

    Returns an array aligned with ``poly``'s cells, ready to be attached as cell
    data and plotted on a color scale. Cells whose node is missing from ``data``
    get ``default`` (``nan``, which pyvista draws in its ``nan_color``).
    """
    return _map_cell_data(poly, data, "node_number", default)


def map_face_data(
    poly: pv.PolyData,
    data: Mapping[int, float],
    *,
    default: float = np.nan,
) -> npt.NDArray[np.float64]:
    """Spread a ``{face slot: value}`` mapping over the cells of ``poly``.

    Like :func:`map_node_data` but keyed by face slot, so the two sides of a face
    can carry different values (side 1 slots are even, side 2 odd).
    """
    return _map_cell_data(poly, data, "face_id", default)


def cell_columns(
    poly: pv.PolyData,
    keys: npt.ArrayLike,
    key: str,
) -> tuple[npt.NDArray[np.intp], npt.NDArray[np.bool_]]:
    """Match each cell of ``poly`` to its column in a ``keys``-ordered series.

    Returns the per-cell column index and a mask of the cells that have one at
    all. Doing this once turns every later frame of a time series into a single
    fancy-index instead of a per-cell dict lookup.
    """
    cell_keys = np.asarray(poly.cell_data[key]).astype(np.int64)
    key_array = np.asarray(keys).astype(np.int64)
    if key_array.size == 0:
        return (
            np.zeros(cell_keys.size, dtype=np.intp),
            np.zeros(cell_keys.size, dtype=np.bool_),
        )
    order = np.argsort(key_array)
    position = np.clip(np.searchsorted(key_array[order], cell_keys), 0, key_array.size - 1)
    found = key_array[order][position] == cell_keys
    return order[position], found


def categorical_colors(
    ids: npt.ArrayLike,
    *,
    palette: str = "tab20",
    missing: tuple[float, float, float] = (0.6, 0.6, 0.6),
    rank: bool = False,
) -> npt.NDArray[np.uint8]:
    """Map integer category ids to distinct RGB colors from a qualitative palette.

    Ids cycle through the palette; negative ids (unassigned) get ``missing``.
    Returns an ``(n, 3)`` ``uint8`` array suitable for pyvista ``rgb=True``.

    With ``rank=True`` the ids are first replaced by their dense rank (the
    position of each distinct value in sorted order), so *sparse* labels such as
    tmm node numbers get adjacent palette entries instead of colliding: raw ids
    100, 200, 300 and 400 all share ``id % 20 == 0`` and would otherwise come out
    the same color.
    """
    id_array = np.asarray(ids).astype(np.int64)
    keys = id_array
    if rank:
        assigned = id_array[id_array >= 0]
        distinct = np.unique(assigned)
        keys = np.searchsorted(distinct, id_array)
    cmap = mpl.colormaps[palette]
    lut = (np.array([cmap(k)[:3] for k in range(cmap.N)]) * 255).astype(np.uint8)
    colors = lut[np.mod(keys, cmap.N)]
    colors[id_array < 0] = (np.array(missing) * 255).astype(np.uint8)
    return colors


def colorize_categorical(poly: pv.PolyData, ids: npt.ArrayLike, *, rank: bool = False) -> str:
    """Attach categorical RGB cell colors for ``ids`` and return the array name."""
    poly.cell_data[_RGB_NAME] = categorical_colors(ids, rank=rank)
    return _RGB_NAME


def render(
    poly: pv.PolyData,
    *,
    scalars: str | None = "face_id",
    show_edges: bool = True,
    off_screen: bool = False,
    rgb: bool = False,
    scalar_bar: bool = True,
    lighting: bool | None = None,
    pick: bool = True,
    pick_source: object | None = None,
    **kwargs: Any,
) -> pv.Plotter:
    """Render a prepared :class:`pyvista.PolyData` and show it.

    With ``rgb=True`` the ``scalars`` array is interpreted as per-cell RGB colors
    and no scalar bar is drawn. Otherwise ``scalars`` names a cell-data array to
    color by (ignored if absent); pass ``None`` for a flat color. Returns the
    :class:`pyvista.Plotter` (useful with ``off_screen=True`` for headless
    rendering / testing).

    ``lighting=False`` renders flat, unshaded faces. Categorical plots default to
    that, because the default specular shading darkens faces by orientation and
    makes two patches of the same category look like different colors.

    ``pick_source`` is the TriMesh or GeometryModel ``poly`` was built from; when
    given (and ``pick``), right-clicking a face prints its properties to the
    console (see :func:`pycanha.gmm.picking.enable_face_picking`).
    """
    if lighting is None:
        lighting = not rgb
    plotter = pv.Plotter(off_screen=off_screen)
    if rgb:
        plotter.add_mesh(
            poly,
            scalars=scalars,
            rgb=True,
            show_edges=show_edges,
            show_scalar_bar=False,
            lighting=lighting,
            **kwargs,
        )
    else:
        active = scalars if (scalars is not None and scalars in poly.cell_data) else None
        plotter.add_mesh(
            poly,
            scalars=active,
            show_edges=show_edges,
            show_scalar_bar=scalar_bar,
            lighting=lighting,
            **kwargs,
        )
    if pick and pick_source is not None:
        model = pick_source if isinstance(pick_source, pcc.gmm.GeometryModel) else None
        picking.enable_face_picking(plotter, poly, _resolve_mesh(pick_source), model=model)
    plotter.show()
    return plotter


def plot(
    obj: object,
    *,
    scalars: str | None = "face_id",
    show_edges: bool = True,
    off_screen: bool = False,
    both_sides: bool = True,
    pick: bool = True,
    **kwargs: Any,
) -> pv.Plotter:
    """Render a TriMesh or GeometryModel with pyvista.

    ``scalars="face_id"`` (the default) colors each face a distinct color;
    ``"node_number"`` colors each tmm node distinctly; ``None`` is a flat color.
    Returns the :class:`pyvista.Plotter` (useful with ``off_screen=True`` for
    headless rendering / testing).

    ``both_sides`` (default) draws each ThermalMesh side with its own data, so
    the far side of a surface shows *its* face slot rather than the near side's.

    ``pick`` (default) makes right-clicking a face print its properties to the
    console; pass ``pick=False`` to leave the mouse buttons alone.
    """
    poly = to_polydata(obj, both_sides=both_sides)
    if both_sides:
        kwargs.setdefault("backface_culling", True)
    if scalars in ("face_id", "node_number") and scalars in poly.cell_data:
        name = colorize_categorical(
            poly, np.asarray(poly.cell_data[scalars]), rank=scalars == "node_number"
        )
        return render(
            poly,
            scalars=name,
            rgb=True,
            show_edges=show_edges,
            off_screen=off_screen,
            pick=pick,
            pick_source=obj,
            **kwargs,
        )
    return render(
        poly,
        scalars=scalars,
        show_edges=show_edges,
        off_screen=off_screen,
        pick=pick,
        pick_source=obj,
        **kwargs,
    )
