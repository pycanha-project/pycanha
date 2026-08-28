"""The lines that show where one thing ends and the next begins.

Two kinds, both from one vectorised half-edge pass over the triangulation and
differing only in what they group by: **face edges** separate one face of the
thermal mesh from the next, **primitive edges** separate one primitive from the
next. An edge is drawn where the group changes across it, which covers both the
edge between two groups and the edge that only one triangle uses.

The third toggle in the toolbar - the triangle mesh lines - is not here: that
is the actor's own ``show_edges``, which VTK draws for free.

Nothing here imports Qt, and nothing here knows about pyvista: the result is an
``(n, 2)`` array of point indices, which is what the tests assert on and what
:func:`pycanha.plot.polydata.polydata_from_lines` turns into an actor.

What this cannot find
---------------------
``build_mesh_from_plan`` welds vertices by position, so on a full-revolution
primitive the ``u = 0`` and ``u = 2*pi`` vertices are **one** vertex and the
wrap seam is not a topological boundary at all. No half-edge walk can find it.
A full cylinder therefore shows its two rims and no vertical seam, a closed
sphere shows nothing, and a cube shows no corner lines - those are creases
between coplanar-in-topology triangles, not boundaries. This is accepted for
0.19: the seam has to come from the primitive's parametrisation and the crease
from an adjacent-normal angle, and both are batched with the C++ ``Edges`` work.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt


def group_boundary_edges(
    triangles: npt.ArrayLike, groups: npt.ArrayLike, *, n_points: int
) -> npt.NDArray[np.int64]:
    """The edges of ``triangles`` across which ``groups`` changes.

    ``groups`` is one label per triangle - a face, a geometry id - and
    ``n_points`` the number of points the indices address. An edge is returned
    when the two triangles sharing it are labelled differently, and also when
    it is not shared by exactly two triangles at all: an edge only one triangle
    uses is the outside of everything, and a non-manifold one is worth seeing.

    Returned as ``(n, 2)`` point indices, ascending within a row.
    """
    tris = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
    labels = np.asarray(groups, dtype=np.int64).reshape(-1)
    if tris.shape[0] == 0 or n_points <= 0:
        return np.empty((0, 2), dtype=np.int64)

    # The three edges of every triangle, each ordered low-high so that the same
    # edge seen from its two triangles is the same pair.
    pairs = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    low = np.minimum(pairs[:, 0], pairs[:, 1])
    high = np.maximum(pairs[:, 0], pairs[:, 1])
    # One integer per edge rather than sorting pairs of them: an (n, 2) unique
    # sorts a structured view and is several times slower, and the model this
    # is sized for has a million triangles.
    keys = low * np.int64(n_points) + high
    owners = np.tile(labels, 3)

    unique, inverse, counts = np.unique(keys, return_inverse=True, return_counts=True)
    order = np.argsort(inverse.reshape(-1), kind="stable")
    ordered_owners = owners[order]
    # Where each unique edge's run of users starts in the sorted order.
    starts = np.concatenate([[0], np.cumsum(counts)[:-1]])
    first = ordered_owners[starts]
    partner = ordered_owners[np.minimum(starts + 1, ordered_owners.size - 1)]
    keep = (counts != 2) | (first != partner)

    kept = unique[keep]
    return np.column_stack([kept // np.int64(n_points), kept % np.int64(n_points)])


def face_edges(
    triangles: npt.ArrayLike, face_ids: npt.ArrayLike, *, n_points: int
) -> npt.NDArray[np.int64]:
    """The outline of every face of the thermal mesh.

    ``face_ids`` is the mesh's own per-triangle face, so this is the
    boundary between two faces of the same primitive as much as between two
    primitives.
    """
    return group_boundary_edges(triangles, face_ids, n_points=n_points)


def primitive_edges(
    triangles: npt.ArrayLike, item_ids: npt.ArrayLike, *, n_points: int
) -> npt.NDArray[np.int64]:
    """The outline of every primitive, the faces inside it left out.

    ``item_ids`` is the geometry that produced each triangle. Since the mesher
    welds only within a primitive, this is in practice the boundary loops of
    each one - see the module docstring for what that does and does not show.
    """
    return group_boundary_edges(triangles, item_ids, n_points=n_points)
