"""The rendered geometry of the viewer: master mesh, indices, visible subset.

A :class:`Scene` converts a ``GeometryModel`` once into the arrays the 3D view
needs and then only ever *selects* from them. The master
:class:`pyvista.PolyData` - points, triangles, ``face_id`` / ``node_number`` /
``side`` cell arrays - is built by :func:`pycanha.plot.polydata.to_polydata`
and never changes while the window is open. What changes is which of its cells
are drawn: hiding geometry rebuilds a *subset* polydata that reuses the master
point array, so the whole model stays one actor and one draw call, which is
what keeps rotating a large model smooth. The rebuild happens only on a
discrete user action, never per frame.

Nothing here imports Qt: the subset cell ids, the coloring inputs and the
pick round-trip are all plain numpy and are tested directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from .picking import camera_facing_cell
from .polydata import polydata_from_triangles, to_polydata

if TYPE_CHECKING:
    from collections.abc import Collection

    import numpy.typing as npt
    import pyvista as pv


def face_items(mesh: Any) -> npt.NDArray[np.int64]:
    """Map every face of ``mesh`` to the geometry id that produced it.

    Faces no primitive claims get ``-1``. The ranges are given in side-1 (even)
    faces, first and last, so the slice runs to ``last + 2`` to take in the odd
    side-2 partner of the last face as well - both faces of a pair belong to the
    item that produced it.

    The ranges are written in order so that a later one wins. They can overlap:
    an item cut away entirely keeps a range, collapsed onto the offset where the
    next item starts, and the core resolves the overlap as last-writer-wins.
    That is the same answer :func:`pycanha.plot.picking.owning_item` reaches by
    scanning the ranges backwards.
    """
    items = np.full(int(mesh.nf()), -1, dtype=np.int64)
    for geometry_id, first_face_id, last_face_id in mesh.primitives:
        items[int(first_face_id) : int(last_face_id) + 2] = int(geometry_id)
    return items


def face_nodes(mesh: Any) -> npt.NDArray[np.int64]:
    """The tmm node number of every face of ``mesh``, ``-1`` where unset.

    Indexed by face, like every property array, rather than by cell: the two
    faces of a pair carry two different nodes. A mesh that
    has not been given node numbers reports ``-1`` throughout rather than a
    short array.
    """
    numbers = np.asarray(mesh.node_numbers).astype(np.int64)
    n_faces = int(mesh.nf())
    if numbers.size != n_faces:
        return np.full(n_faces, -1, dtype=np.int64)
    return numbers


def _same_mask(left: npt.NDArray[np.bool_] | None, right: npt.NDArray[np.bool_] | None) -> bool:
    """Whether two optional per-cell masks say the same thing."""
    if left is None or right is None:
        return left is None and right is None
    return bool(np.array_equal(left, right))


def _group_by_value(values: npt.NDArray[np.int64]) -> dict[int, npt.NDArray[np.intp]]:
    """Invert ``values`` into ``{value: indices}`` in one sort rather than a scan per key."""
    if values.size == 0:
        return {}
    order = np.argsort(values, kind="stable")
    ordered = values[order]
    starts = np.concatenate([[0], np.flatnonzero(ordered[1:] != ordered[:-1]) + 1])
    return {
        int(ordered[start]): group
        for start, group in zip(starts, np.split(order, starts[1:]), strict=True)
    }


class Scene:
    """The master mesh of a model plus the indices the viewer selects with.

    ``both_sides`` doubles the cells so each ThermalMesh side carries its own
    face, node and material (see
    :func:`pycanha.plot.polydata.to_polydata`); the two copies are coincident,
    so the actor drawing :meth:`visible_polydata` needs ``backface_culling``.
    """

    def __init__(self, model: Any, *, both_sides: bool = True) -> None:
        self.model = model
        self.mesh = model.mesh
        self.both_sides = both_sides
        self.poly = to_polydata(model, both_sides=both_sides)

        n_tri = int(self.mesh.nt())
        #: Number of cells of the master polydata, doubled by ``both_sides``.
        self.n_cells = 2 * n_tri if both_sides else n_tri
        self.points = np.asarray(self.poly.points)
        if self.n_cells:
            # VTK stores connectivity as [3, i, j, k] runs; drop the leading count.
            faces = self.poly.faces.reshape(-1, 4)[:, 1:]
            self.triangles = faces.astype(np.int64, copy=False)
            self.face_ids = np.asarray(self.poly.cell_data["face_id"]).astype(np.int64)
            self.node_numbers = np.asarray(self.poly.cell_data["node_number"]).astype(np.int64)
        else:
            # A model with no triangles still has points, and pyvista turns those
            # into vertex cells - so the cell count comes from the mesh, not the
            # polydata, and every cell array is empty rather than point-shaped.
            self.triangles = np.empty((0, 3), dtype=np.int64)
            self.face_ids = np.empty(0, dtype=np.int64)
            self.node_numbers = np.empty(0, dtype=np.int64)
        # Without the side-2 copies every cell describes side 1, and the array is
        # kept anyway so callers never have to branch on ``both_sides``.
        sides = (
            self.poly.cell_data["side"] if both_sides and self.n_cells else np.ones(self.n_cells)
        )
        self.sides = np.asarray(sides).astype(np.int64)

        #: Geometry id owning each face (``-1`` when unclaimed).
        self.face_items = face_items(self.mesh)
        #: Tmm node number of each face (``-1`` when unassigned).
        self.face_nodes = face_nodes(self.mesh)
        #: Geometry id owning each cell (``-1`` when unclaimed).
        self.cell_items = self._resolve_cell_items()
        #: Master cell indices of each geometry id, for visibility and highlighting.
        self.item_cells = _group_by_value(self.cell_items)
        #: Geometry ids that own at least one cell, ascending.
        self.item_ids = sorted(item_id for item_id in self.item_cells if item_id >= 0)

        self._hidden: frozenset[int] = frozenset()
        self._keep: npt.NDArray[np.bool_] | None = None
        #: Master cell index of each cell currently drawn, ascending.
        self.visible_cells = np.arange(self.n_cells, dtype=np.intp)
        self._subset: pv.PolyData | None = None

    def _resolve_cell_items(self) -> npt.NDArray[np.int64]:
        """Geometry id of every cell, via its face."""
        if self.n_cells == 0 or self.face_items.size == 0:
            return np.full(self.n_cells, -1, dtype=np.int64)
        # Side-2 cells name the odd partner face; clearing the low bit gives the
        # side-1 face the primitive ranges are expressed in.
        base = self.face_ids & ~np.int64(1)
        inside = base < self.face_items.size
        return np.where(inside, self.face_items[np.where(inside, base, 0)], -1)

    # ── visibility ────────────────────────────────────────────────────────
    @property
    def hidden(self) -> frozenset[int]:
        """Geometry ids currently excluded from the drawn subset."""
        return self._hidden

    def set_hidden(
        self, hidden: Collection[int], keep: npt.NDArray[np.bool_] | None = None
    ) -> bool:
        """Restrict the drawn cells to the geometry that is *not* in ``hidden``.

        ``keep`` is an optional second, per-master-cell condition a cell has to
        satisfy to be drawn - what the legend's hidden categories are, since
        those hide by *value* rather than by geometry.

        Returns whether anything changed, so a caller can skip the subset
        rebuild and the re-render when it did not.
        """
        wanted = frozenset(int(item_id) for item_id in hidden)
        mask = None if keep is None else np.asarray(keep, dtype=np.bool_)
        if wanted == self._hidden and _same_mask(mask, self._keep):
            return False
        self._hidden = wanted
        self._keep = mask
        self.visible_cells = self._compute_visible()
        self._subset = None
        return True

    def _compute_visible(self) -> npt.NDArray[np.intp]:
        if not self._hidden and self._keep is None:
            return np.arange(self.n_cells, dtype=np.intp)
        visible = np.ones(self.n_cells, dtype=np.bool_)
        if self._hidden:
            hidden = np.fromiter(self._hidden, dtype=np.int64, count=len(self._hidden))
            visible &= ~np.isin(self.cell_items, hidden)
        if self._keep is not None:
            visible &= self._keep
        return np.flatnonzero(visible).astype(np.intp)

    def visible_polydata(self) -> pv.PolyData:
        """The polydata of the currently visible cells, rebuilt on demand.

        Shares the master point array rather than re-indexing it: VTK tolerates
        points no triangle references, so hiding geometry costs one connectivity
        array and no vertex copy. The ``face_id`` / ``node_number`` / ``side``
        cell arrays come along, so picking and the value mappers work on the
        subset exactly as they do on the master.
        """
        if self._subset is None:
            subset = polydata_from_triangles(self.points, self.triangles[self.visible_cells])
            subset.cell_data["face_id"] = self.face_ids[self.visible_cells]
            subset.cell_data["node_number"] = self.node_numbers[self.visible_cells]
            if self.both_sides:
                subset.cell_data["side"] = self.sides[self.visible_cells]
            self._subset = subset
        return self._subset

    # ── master <-> subset ─────────────────────────────────────────────────
    def master_cell(self, subset_cell: int) -> int:
        """Master cell index of cell ``subset_cell`` of :meth:`visible_polydata`.

        A pick reports a cell of the rendered subset; everything else in the
        viewer - faces, nodes, items, scalars - is indexed by master cell.
        """
        if not 0 <= subset_cell < self.visible_cells.size:
            msg = f"cell index {subset_cell} out of range for {self.visible_cells.size} cells"
            raise IndexError(msg)
        return int(self.visible_cells[subset_cell])

    def pick_cell(self, subset_cell: int, view_direction: npt.ArrayLike) -> int:
        """Master cell a pick on the visible subset actually landed on.

        With ``both_sides`` the two copies of a triangle are coincident and the
        cell picker ignores backface culling, so it may hand back the copy
        hidden behind the one being looked at; ``view_direction`` decides which
        of the two faces the camera.
        """
        master = self.master_cell(subset_cell)
        if not self.both_sides:
            return master
        return camera_facing_cell(
            master,
            n_tri=self.n_cells // 2,
            triangles=self.triangles,
            points=self.points,
            view_direction=np.asarray(view_direction, dtype=np.float64),
        )

    def restrict_to_visible(self, cells: npt.ArrayLike) -> npt.NDArray[np.intp]:
        """Drop the cells of ``cells`` that are not currently drawn.

        Highlight overlays go through this: they are actors of their own, so
        without it a highlight would draw geometry that Hide just removed.
        """
        wanted = np.asarray(cells, dtype=np.intp)
        if self.visible_cells.size == self.n_cells:
            return wanted
        visible = np.zeros(self.n_cells, dtype=np.bool_)
        visible[self.visible_cells] = True
        return wanted[visible[wanted]]

    def visible_index(self, cells: npt.ArrayLike) -> npt.NDArray[np.intp]:
        """Where each of ``cells`` sits in the drawn subset.

        The inverse of :attr:`visible_cells`, which is what turns a set of
        master cells into rows of a per-visible-cell array - the colors a
        highlight has to read to brighten what is on screen. Every cell must be
        visible; :meth:`restrict_to_visible` is what drops the ones that are not.
        """
        wanted = np.asarray(cells, dtype=np.intp)
        if self.visible_cells.size == self.n_cells:
            return wanted
        rows = np.searchsorted(self.visible_cells, wanted)
        inside = rows < self.visible_cells.size
        if not bool(np.all(inside)) or not bool(
            np.all(self.visible_cells[np.where(inside, rows, 0)] == wanted)
        ):
            msg = "every cell must be one of the cells currently drawn"
            raise ValueError(msg)
        return rows.astype(np.intp)

    def visible_scalars(self, master: npt.ArrayLike) -> npt.NDArray[Any]:
        """Restrict a per-master-cell array to the cells currently drawn."""
        values = np.asarray(master)
        if values.shape[0] != self.n_cells:
            msg = f"expected {self.n_cells} values, one per master cell, got {values.shape[0]}"
            raise ValueError(msg)
        return values[self.visible_cells]

    # ── lookups ───────────────────────────────────────────────────────────
    def cells_of_item(self, item_id: int) -> npt.NDArray[np.intp]:
        """Master cells produced by geometry ``item_id`` (empty if it owns none)."""
        return self.item_cells.get(int(item_id), np.empty(0, dtype=np.intp))

    def cells_of_face(self, face_id: int) -> npt.NDArray[np.intp]:
        """Master cells of face ``face_id`` - the triangles of one side of one face."""
        return np.flatnonzero(self.face_ids == int(face_id)).astype(np.intp)

    def cells_of_node(self, node_number: int) -> npt.NDArray[np.intp]:
        """Master cells whose face belongs to tmm node ``node_number``."""
        return np.flatnonzero(self.node_numbers == int(node_number)).astype(np.intp)

    def item_of_cell(self, cell: int) -> int:
        """Geometry id that produced master cell ``cell`` (``-1`` if unclaimed)."""
        return int(self.cell_items[cell])

    def node_range_mask(self, lo: int, hi: int) -> npt.NDArray[np.bool_]:
        """Per-master-cell mask of the cells whose node lies in ``[lo, hi]``.

        The node filter greys rather than hides, so this is a coloring input
        and deliberately not part of :attr:`visible_cells`.
        """
        return (self.node_numbers >= int(lo)) & (self.node_numbers <= int(hi))
