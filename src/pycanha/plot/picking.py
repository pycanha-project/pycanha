"""Resolve the model entity behind a rendered triangle.

Right-clicking (or pressing ``P``) over the geometry casts a single ray from the
cursor with VTK's ``vtkCellPicker``, resolves the triangle it hits back to the
model, and reports the face's properties.

``face_info`` does the resolution and is free of any pyvista state, so it can be
exercised without a render window - it is also what the interactive viewer uses
to fill its property table. ``enable_face_picking`` wires it to a
:class:`pyvista.Plotter` for the one-shot plotting path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pycanha_core as pcc

from .polydata import polydata_from_triangles

if TYPE_CHECKING:
    from collections.abc import Callable

    import pyvista as pv

#: Actor name of the highlight overlay, so each pick replaces the previous one.
_HIGHLIGHT_NAME = "_picked_face"


@dataclass(frozen=True)
class FaceInfo:
    """Properties of one face slot, as reported by a pick.

    ``face_id`` is the face slot of the *reported side* (side 1 slots are even,
    side 2 slots odd), matching the ``face_id`` cell array of the polydata.
    Every model-derived field is ``None`` when it cannot be resolved - picking a
    bare TriMesh still yields the face, side and node number.
    """

    face_id: int
    side: int
    node_number: int
    item_name: str | None = None
    primitive: str | None = None
    optical_name: str | None = None
    emissivity_ir: float | None = None
    absorptivity_solar: float | None = None
    color: tuple[int, int, int] | None = None


def item_map(model: Any) -> dict[int, Any]:
    """Map each geometry id in ``model`` to its ``GeometryItem``.

    The ids match the ``geometry_id`` of the mesh's primitive ranges, which is
    how a face is traced back to the item that produced it.
    """
    return {
        int(geometry.id): geometry
        for geometry in model.children_recursive()
        if isinstance(geometry, pcc.gmm.GeometryItem)
    }


def owning_item(mesh: Any, face_id: int, items: dict[int, Any]) -> Any:
    """Return the item whose primitive range contains ``face_id`` (side-1 slot).

    Ranges are scanned back-to-front because they may overlap: an item cut away
    entirely leaves a zero-width range at the next item's offset, and the core
    resolves such an overlap as last-writer-wins.
    """
    for geometry_id, first_face_id, last_face_id in reversed(mesh.primitives):
        if first_face_id <= face_id <= last_face_id:
            return items.get(int(geometry_id))
    return None


def face_info(
    mesh: Any,
    cell_index: int,
    *,
    both_sides: bool = False,
    items: dict[int, Any] | None = None,
) -> FaceInfo:
    """Resolve the properties of the face behind polydata cell ``cell_index``.

    ``both_sides`` must match how the polydata was built: with it the cells are
    doubled, ``[0, nt)`` being side 1 and ``[nt, 2*nt)`` the side-2 copies (see
    :func:`pycanha.plot.polydata.to_polydata`).

    ``items`` is the ``{geometry id: GeometryItem}`` map of the owning model (see
    :func:`item_map`); without it only the mesh-level fields are filled in.
    """
    n_tri = int(mesh.nt())
    n_cells = 2 * n_tri if both_sides else n_tri
    if not 0 <= cell_index < n_cells:
        msg = f"cell index {cell_index} out of range for {n_cells} cells"
        raise IndexError(msg)

    side = 2 if cell_index >= n_tri else 1
    # face_ids always name the side-1 (even) slot; the side-2 partner is slot + 1.
    base_face_id = int(mesh.face_ids[cell_index % n_tri])
    face_id = base_face_id | (side - 1)

    node_numbers = np.asarray(mesh.node_numbers)
    node_number = int(node_numbers[face_id]) if face_id < node_numbers.size else -1

    item = owning_item(mesh, base_face_id, items) if items else None
    if item is None:
        return FaceInfo(face_id=face_id, side=side, node_number=node_number)

    thermal_mesh = item.thermal_mesh
    optical = thermal_mesh.side1_optical if side == 1 else thermal_mesh.side2_optical
    color = thermal_mesh.side1_color if side == 1 else thermal_mesh.side2_color
    red, green, blue = color.rgb
    return FaceInfo(
        face_id=face_id,
        side=side,
        node_number=node_number,
        item_name=item.name or "<anonymous>",
        primitive=type(item.primitive).__name__,
        optical_name=None if optical is None else optical.name,
        emissivity_ir=None if optical is None else float(optical.emissivity_ir),
        absorptivity_solar=None if optical is None else float(optical.absorptivity_solar),
        color=(int(red), int(green), int(blue)),
    )


def format_face_info(info: FaceInfo) -> str:
    """Format a :class:`FaceInfo` as the compact two-line console block."""
    item = "-" if info.item_name is None else f"'{info.item_name}' ({info.primitive})"
    head = f"face {info.face_id} (side {info.side})  node {info.node_number}  item {item}"
    if info.color is None:
        return head

    def _number(value: float | None) -> str:
        return "-" if value is None else f"{value:.3f}"

    optical = "-" if info.optical_name is None else f"'{info.optical_name}'"
    detail = (
        f"  optical {optical}"
        f"  eps_ir {_number(info.emissivity_ir)}"
        f"  alpha_sol {_number(info.absorptivity_solar)}"
        f"  color {info.color}"
    )
    return f"{head}\n{detail}"


def camera_facing_cell(
    cell_index: int,
    *,
    n_tri: int,
    triangles: np.ndarray,
    points: np.ndarray,
    view_direction: np.ndarray,
) -> int:
    """Return whichever of the two coincident side copies faces the camera.

    With ``both_sides`` the two copies of a triangle sit exactly on top of each
    other with opposite winding, and the cell picker ignores backface culling, so
    it may well return the copy hidden behind the one being looked at.
    """
    corners = points[triangles[cell_index]]
    normal = np.cross(corners[1] - corners[0], corners[2] - corners[0])
    if float(np.dot(normal, view_direction)) <= 0.0:
        return cell_index
    return cell_index - n_tri if cell_index >= n_tri else cell_index + n_tri


def highlight_face(
    plotter: pv.Plotter,
    poly: pv.PolyData,
    face_id: int,
    *,
    points: np.ndarray,
    triangles: np.ndarray,
    color: str,
    backface_culling: bool,
    name: str = _HIGHLIGHT_NAME,
) -> None:
    """Draw every triangle of face slot ``face_id`` in ``color``.

    The overlay is exactly coincident with the face it covers, so its mapper is
    put on a polygon offset towards the camera; without that the two surfaces
    z-fight and the highlight only shows in patches.
    """
    cells = np.flatnonzero(np.asarray(poly.cell_data["face_id"]) == face_id)
    if cells.size == 0:
        return
    highlight_cells(
        plotter,
        points=points,
        triangles=triangles[cells],
        color=color,
        backface_culling=backface_culling,
        name=name,
    )


def highlight_cells(
    plotter: pv.Plotter,
    *,
    points: np.ndarray,
    triangles: np.ndarray,
    color: str,
    backface_culling: bool,
    name: str = _HIGHLIGHT_NAME,
) -> None:
    """Draw an arbitrary set of triangles as a coincident overlay actor.

    The polygon-offset dance is the same as :func:`highlight_face`; this form
    takes the triangles directly so a caller can highlight a whole item or a
    node's faces rather than one slot.
    """
    if triangles.shape[0] == 0:
        return
    actor = plotter.add_mesh(
        polydata_from_triangles(points, triangles),
        color=color,
        lighting=False,
        pickable=False,
        reset_camera=False,
        backface_culling=backface_culling,
        show_scalar_bar=False,
        name=name,
    )
    mapper = actor.mapper
    mapper.SetResolveCoincidentTopologyToPolygonOffset()
    mapper.SetRelativeCoincidentTopologyPolygonOffsetParameters(-4.0, -4.0)


def clear_highlight(plotter: pv.Plotter, name: str = _HIGHLIGHT_NAME) -> None:
    """Drop the highlight overlay, if one is currently shown.

    Goes through the renderer rather than the Plotter method of the same name:
    that one is a functools.wraps forwarder that loses its bound signature, and
    it sweeps every renderer, while the overlay only ever lives on the active one.
    """
    plotter.renderer.remove_actor(name, render=True)


def enable_face_picking(
    plotter: pv.Plotter,
    poly: pv.PolyData,
    mesh: Any,
    *,
    model: Any = None,
    tolerance: float = 1e-6,
    highlight_color: str | None = "yellow",
    on_pick: Callable[[FaceInfo | None], None] | None = None,
) -> None:
    """Report the properties of the face under the cursor when it is picked.

    Must be called before :meth:`pyvista.Plotter.show`. Picking is bound to the
    right mouse button (and the ``P`` key), leaving left-drag as plain camera
    orbiting. Whether the polydata carries both ThermalMesh sides is taken from
    its ``side`` cell array.

    ``model`` is the ``GeometryModel`` the mesh belongs to; without it only the
    mesh-level fields (face, side, node) can be reported.

    ``tolerance`` is the pick radius as a fraction of the window diagonal. It has
    to stay tiny: the cell picker treats every cell within the tolerance of the
    ray as a candidate, so on coplanar geometry a large value hands back the
    neighboring face whenever the click is off-center. (pyvista defaults it to
    0.025 - about 25 px on a 1000 px window - which is far too coarse here.)

    ``highlight_color`` paints the whole picked face, so the report can be
    matched to what was clicked; picking past the geometry clears it again.
    Pass ``None`` for no visual feedback.

    ``on_pick`` receives the resolved :class:`FaceInfo`, or ``None`` when the
    click missed the geometry. It replaces the default console report, which is
    what the interactive viewer uses to drive its property table. Without it the
    face is printed to stdout as before.

    Does nothing for an off-screen plotter: there is no mouse to pick with, and
    the usage hint would end up baked into the rendered image.
    """
    n_tri = int(mesh.nt())
    if n_tri == 0 or plotter.off_screen:
        return

    both_sides = "side" in poly.cell_data
    items = item_map(model) if model is not None else None
    points = np.asarray(poly.points)
    triangles = poly.faces.reshape(-1, 4)[:, 1:]
    report = on_pick if on_pick is not None else _print_face_info

    def _report(point: Any, picker: Any) -> None:
        cell_index = int(picker.GetCellId())
        # Our plotters hold a single pickable dataset, so an in-range cell id is
        # enough to know the ray hit the geometry.
        if not 0 <= cell_index < poly.n_cells:
            # Clicking past the geometry clears the selection.
            if highlight_color is not None:
                clear_highlight(plotter)
            report(None)
            return
        if both_sides:
            camera = plotter.camera
            origin = np.asarray(camera.position, dtype=np.float64)
            if camera.parallel_projection:
                # All rays are parallel to the view axis, so the click position
                # says nothing about the ray direction.
                view_direction = np.asarray(camera.focal_point, dtype=np.float64) - origin
            else:
                view_direction = np.asarray(point, dtype=np.float64) - origin
            cell_index = camera_facing_cell(
                cell_index,
                n_tri=n_tri,
                triangles=triangles,
                points=points,
                view_direction=view_direction,
            )
        info = face_info(mesh, cell_index, both_sides=both_sides, items=items)
        if highlight_color is not None:
            highlight_face(
                plotter,
                poly,
                info.face_id,
                points=points,
                triangles=triangles,
                color=highlight_color,
                backface_culling=both_sides,
            )
        report(info)

    # Go through the picking component rather than the Plotter shim of the same
    # name: the shim is a functools.wraps forwarder, which loses the bound-method
    # signature (pyvista suppresses the resulting type errors at its own call sites).
    plotter.picking.enable_point_picking(
        callback=_report,
        picker="cell",
        tolerance=tolerance,
        use_picker=True,
        show_point=False,
        # Without this pyvista swallows the event whenever the ray hits nothing,
        # and a click past the geometry could never clear the selection.
        pickable_window=True,
        show_message="Right-click or press P to inspect a face",
    )


def _print_face_info(info: FaceInfo | None) -> None:
    """Default ``on_pick``: print the face to stdout, or nothing on a miss."""
    if info is not None:
        print(format_face_info(info))
