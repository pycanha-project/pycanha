"""Turn gmm triangular meshes into pyvista datasets.

``to_polydata`` converts a ``TriMeshF`` / ``TriMeshD`` (or a ``GeometryModel``)
into a :class:`pyvista.PolyData`, attaching the per-triangle ``face_id`` and
``node_number`` as cell data. The rest of this module maps model-keyed values
onto those cells: :func:`map_node_data` / :func:`map_face_data` for a single
mapping, :func:`cell_columns` for a whole time series, and
:func:`categorical_colors` for labels that are names rather than magnitudes.

Nothing here renders; see :mod:`pycanha.plot.render` for the free-function
plotting path and :mod:`pycanha.plot.window` for the interactive viewer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import matplotlib as mpl
import numpy as np
import pycanha_core as pcc
import pyvista as pv

if TYPE_CHECKING:
    from collections.abc import Mapping

    import numpy.typing as npt

_TriMesh = (pcc.gmm.TriMeshD, pcc.gmm.TriMeshF)

#: Cell-data name used to stash the per-face RGB colors for categorical plots.
RGB_NAME = "_rgb"

#: What a category the model has nothing to assign is drawn in - a face slot
#: with no material, no colour, no node. Grey, so it reads as "nothing here"
#: rather than as one more value.
MISSING_RGB: tuple[int, int, int] = (153, 153, 153)


def resolve_mesh(obj: object) -> Any:
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
    mesh = resolve_mesh(obj)
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

    poly = polydata_from_triangles(vertices, triangles)
    poly.cell_data["face_id"] = face_ids

    node_numbers = np.asarray(mesh.node_numbers)
    if node_numbers.size:
        poly.cell_data["node_number"] = node_numbers[face_ids]
    else:
        poly.cell_data["node_number"] = np.full(n_cells, -1, dtype=np.int32)

    if both_sides:
        poly.cell_data["side"] = np.repeat([1, 2], n_tri).astype(np.int32)
    return poly


def polydata_from_triangles(
    points: npt.NDArray[np.float64],
    triangles: npt.NDArray[Any],
) -> pv.PolyData:
    """Build a triangle-only :class:`pyvista.PolyData` from points and indices.

    VTK wants a flat connectivity array of ``[3, i, j, k]`` runs rather than an
    ``(n, 3)`` index matrix, so build it once here. ``points`` may hold vertices
    no triangle references - VTK tolerates that, which is what lets a subset of
    the triangles be drawn without re-indexing the shared point array.
    """
    faces = np.empty((triangles.shape[0], 4), dtype=np.int64)
    faces[:, 0] = 3
    faces[:, 1:] = triangles
    return pv.PolyData(points, faces.ravel())


def polydata_from_lines(
    points: npt.NDArray[np.float64],
    edges: npt.NDArray[Any],
) -> pv.PolyData:
    """Build a line-only :class:`pyvista.PolyData` from points and vertex pairs.

    The counterpart of :func:`polydata_from_triangles` for the edge overlays:
    VTK wants ``[2, i, j]`` runs, and the same tolerance of unreferenced points
    lets the lines share the master point array.
    """
    lines = np.empty((edges.shape[0], 3), dtype=np.int64)
    lines[:, 0] = 2
    lines[:, 1:] = edges
    return pv.PolyData(points, lines=lines.ravel())


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


def key_columns(
    wanted: npt.ArrayLike,
    keys: npt.ArrayLike,
) -> tuple[npt.NDArray[np.intp], npt.NDArray[np.bool_]]:
    """Match each entry of ``wanted`` to its position in ``keys``.

    Returns the position of each one and a mask of the entries that have one at
    all. Doing this once turns every later frame of a time series into a single
    fancy-index instead of a lookup per entry.
    """
    wanted_array = np.asarray(wanted).astype(np.int64)
    key_array = np.asarray(keys).astype(np.int64)
    if key_array.size == 0:
        return (
            np.zeros(wanted_array.size, dtype=np.intp),
            np.zeros(wanted_array.size, dtype=np.bool_),
        )
    order = np.argsort(key_array)
    position = np.clip(np.searchsorted(key_array[order], wanted_array), 0, key_array.size - 1)
    found = key_array[order][position] == wanted_array
    return order[position], found


def cell_columns(
    poly: pv.PolyData,
    keys: npt.ArrayLike,
    key: str,
) -> tuple[npt.NDArray[np.intp], npt.NDArray[np.bool_]]:
    """Match each cell of ``poly`` to its column in a ``keys``-ordered series.

    The cells are keyed by their ``key`` cell array - ``node_number`` for a
    node-indexed series, ``face_id`` for a face-indexed one.
    """
    return key_columns(np.asarray(poly.cell_data[key]), keys)


def categorical_colors(
    ids: npt.ArrayLike,
    *,
    palette: str = "tab20",
    missing: tuple[int, int, int] = MISSING_RGB,
    rank: bool = False,
) -> npt.NDArray[np.uint8]:
    """Map integer category ids to distinct RGB colors from a qualitative palette.

    Ids cycle through the palette; negative ids (unassigned) get ``missing``,
    as 0-255 channels.
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
    colors[id_array < 0] = np.array(missing, dtype=np.uint8)
    return colors


def colorize_categorical(poly: pv.PolyData, ids: npt.ArrayLike, *, rank: bool = False) -> str:
    """Attach categorical RGB cell colors for ``ids`` and return the array name."""
    poly.cell_data[RGB_NAME] = categorical_colors(ids, rank=rank)
    return RGB_NAME
