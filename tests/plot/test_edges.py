"""Face and primitive outlines, and the seam the mesher cannot give them.

The extraction is plain numpy over a triangulation, so most of this needs no
model at all; the rest builds one and asserts on the line segments that would
have been handed to VTK.
"""

from collections.abc import Iterator
from typing import Any

import numpy as np
import pytest
from PySide6.QtWidgets import QWidget
from vtkmodules.vtkCommonCore import reference

import pycanha as pc
from pycanha import gmm
from pycanha.plot.edges import face_edges, group_boundary_edges, primitive_edges
from pycanha.plot.polydata import polydata_from_lines
from pycanha.plot.state import EdgeDisplay, Selection
from pycanha.plot.window import (
    FACE_EDGES,
    MESH_ACTOR,
    PRIMITIVE_EDGES,
    SELECTION_HIGHLIGHT,
    ViewerWindow,
)

from .offscreen import OffscreenView, skip_without_a_renderer

#: Two triangles making a unit square, sharing the diagonal 1-2.
SQUARE = np.array([[0, 1, 2], [1, 3, 2]])

#: Its four corners.
SQUARE_POINTS = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [1.0, 1.0, 0.0]])


def as_set(edges: np.ndarray) -> set[tuple[int, int]]:
    """The edges as an order-independent set of vertex pairs."""
    return {(int(low), int(high)) for low, high in edges}


# ── the half-edge pass ────────────────────────────────────────────────────
def test_one_group_leaves_only_the_outline() -> None:
    # The shared diagonal has the same group on both sides, so it is inside.
    found = group_boundary_edges(SQUARE, [7, 7], n_points=4)
    assert as_set(found) == {(0, 1), (0, 2), (1, 3), (2, 3)}


def test_a_group_change_is_an_edge() -> None:
    found = group_boundary_edges(SQUARE, [7, 8], n_points=4)
    assert as_set(found) == {(0, 1), (0, 2), (1, 3), (2, 3), (1, 2)}


def test_the_pairs_come_back_ascending() -> None:
    found = group_boundary_edges(SQUARE, [7, 8], n_points=4)
    assert np.all(found[:, 0] < found[:, 1])


def test_an_empty_triangulation_has_no_edges() -> None:
    assert group_boundary_edges(np.empty((0, 3)), [], n_points=4).shape == (0, 2)
    assert group_boundary_edges(SQUARE, [7, 7], n_points=0).shape == (0, 2)


def test_a_non_manifold_edge_is_kept() -> None:
    # Three triangles round one edge: whatever it is, it is worth seeing.
    triangles = np.array([[0, 1, 2], [1, 0, 3], [0, 1, 4]])
    found = group_boundary_edges(triangles, [1, 1, 1], n_points=5)
    assert (0, 1) in as_set(found)


def test_the_two_kinds_are_the_same_pass_over_different_labels() -> None:
    assert np.array_equal(
        face_edges(SQUARE, [7, 8], n_points=4),
        group_boundary_edges(SQUARE, [7, 8], n_points=4),
    )
    assert np.array_equal(
        primitive_edges(SQUARE, [1, 2], n_points=4),
        group_boundary_edges(SQUARE, [1, 2], n_points=4),
    )


def test_lines_become_a_vtk_line_polydata() -> None:
    poly = polydata_from_lines(SQUARE_POINTS, np.array([[0, 1], [2, 3]]))
    assert poly.n_cells == 2
    assert poly.n_points == 4
    assert np.array_equal(np.asarray(poly.lines), [2, 0, 1, 2, 2, 3])


# ── over a real model ─────────────────────────────────────────────────────
def two_panel_model() -> gmm.GeometryModel:
    """Two 2x1 panels, each meshed into two faces."""
    tm = pc.ThermalModel("edges")
    panels = []
    for index, name in enumerate(("a", "b")):
        thermal_mesh = gmm.ThermalMesh([0.0, 0.5, 1.0], [0.0, 1.0])
        thermal_mesh.node1_start = 100 + 10 * index
        height = float(index)
        panels.append(
            gmm.GeometryItem(
                name,
                gmm.Rectangle((0, 0, height), (2, 0, height), (0, 1, height)),
                thermal_mesh,
            )
        )
    tm.gmm.add(gmm.GeometryGroup("wing", panels))
    return tm.gmm


@pytest.fixture
def window(qtbot: object) -> Iterator[ViewerWindow]:
    del qtbot
    # Closed on the way out: the log tab holds a handler on the process-wide
    # ``pycanha`` logger for as long as the window is open.
    viewer = ViewerWindow(two_panel_model(), view=QWidget())
    yield viewer
    viewer.close()


def test_face_edges_outline_every_face(window: ViewerWindow) -> None:
    lines = window.edge_lines("faces")
    # Four square faces of four edges each, and the two faces of a panel share
    # the edge between them: 4 x 4 - 2.
    assert lines.shape[1] == 2
    assert lines.shape[0] == 14
    assert len(as_set(lines)) == lines.shape[0]


def test_primitive_edges_leave_the_face_divisions_out(window: ViewerWindow) -> None:
    faces = window.edge_lines("faces")
    primitives = window.edge_lines("primitives")
    # Six per panel, not four: the long sides are each split in two where the
    # face division meets them. These are triangle edges, not whole sides.
    assert primitives.shape[0] == 12
    # Every primitive edge is also a face edge, and the two the faces add are
    # the divisions inside the panels.
    assert as_set(primitives) < as_set(faces)


def test_the_edges_follow_what_is_drawn(window: ViewerWindow) -> None:
    window.state.hide([window.scene.item_ids[0]])
    assert window.edge_lines("primitives").shape[0] == 6


def test_only_the_side_one_triangles_are_walked(window: ViewerWindow) -> None:
    # Both sides are in the scene, coincident and wound the other way, so a
    # pass over every cell would see each edge four times and find nothing.
    assert window.scene.both_sides
    assert window.visible_triangles().size == window.scene.n_cells // 2
    assert window.edge_lines("primitives").shape[0] > 0


def test_a_full_revolution_shows_no_seam(qtbot: object) -> None:
    del qtbot
    # D84, and this is the decision rather than a regression: the mesher welds
    # vertices by position, so the u=0 and u=2*pi vertices of a closed
    # primitive are one vertex and the seam is not a boundary at all. A full
    # cylinder therefore outlines its two rims and nothing else.
    tm = pc.ThermalModel("cylinder")
    thermal_mesh = gmm.ThermalMesh([0.0, 1.0], [0.0, 1.0])
    cylinder = gmm.Cylinder((0, 0, 0), (0, 0, 1), (1, 0, 0), 1.0, 0.0, 2 * np.pi)
    tm.gmm.add(gmm.GeometryItem("drum", cylinder, thermal_mesh))
    viewer = ViewerWindow(tm.gmm, view=QWidget())
    try:
        lines = viewer.edge_lines("primitives")
        points = viewer.scene.points[np.unique(lines)]
        # Every point of every edge is on one of the two rims: nothing runs
        # down the side.
        heights = np.unique(np.round(points[:, 2], 6))
        assert lines.shape[0] > 0
        assert np.array_equal(heights, [0.0, 1.0])
    finally:
        viewer.close()


# ── the toggles ───────────────────────────────────────────────────────────
def test_the_toolbar_drives_the_three_toggles(window: ViewerWindow) -> None:
    window.toolbar.face_edges_action.setChecked(False)
    assert window.state.edges == EdgeDisplay(faces=False)

    window.toolbar.face_edges_action.setChecked(True)
    assert window.state.edges == EdgeDisplay(faces=True)

    window.toolbar.primitive_edges_action.setChecked(True)
    window.toolbar.triangle_edges_action.setChecked(True)
    assert window.state.edges == EdgeDisplay(triangles=True, faces=True, primitives=True)

    window.toolbar.face_edges_action.setChecked(False)
    assert window.state.edges == EdgeDisplay(triangles=True, faces=False, primitives=True)


def test_the_toggles_echo_state_set_elsewhere(window: ViewerWindow) -> None:
    # Every field named, so the assertions below read against what this set
    # rather than against whichever way EdgeDisplay's defaults happen to fall.
    window.state.edges = EdgeDisplay(triangles=True, faces=False, primitives=True)
    assert window.toolbar.triangle_edges_action.isChecked()
    assert not window.toolbar.face_edges_action.isChecked()
    assert window.toolbar.primitive_edges_action.isChecked()


def test_drawing_edges_without_a_plotter_is_a_no_op(window: ViewerWindow) -> None:
    window.state.edges = EdgeDisplay(faces=True, primitives=True)
    assert window.plotter is None
    # The overlay names exist for the live path to manage; nothing to assert
    # here but that turning them on did not raise.
    assert FACE_EDGES != PRIMITIVE_EDGES


def test_the_toggles_open_showing_what_the_state_says(window: ViewerWindow) -> None:
    """A toggle that opens unchecked over an on-by-default state does nothing.

    Its first click would set what is already set, emit no change, and read as
    a button that has gone blue and done nothing.
    """
    assert window.state.edges.faces
    assert window.toolbar.face_edges_action.isChecked()
    assert window.toolbar.primitive_edges_action.isChecked() == window.state.edges.primitives
    assert window.toolbar.triangle_edges_action.isChecked() == window.state.edges.triangles


def test_the_first_click_on_a_default_on_toggle_turns_it_off(window: ViewerWindow) -> None:
    window.toolbar.face_edges_action.trigger()
    assert not window.state.edges.faces


# ── what actually reaches the renderer ────────────────────────────────────
@pytest.fixture
def drawn(qtbot: object) -> Iterator[ViewerWindow]:
    del qtbot
    skip_without_a_renderer()
    viewer = ViewerWindow(two_panel_model(), view=OffscreenView())
    yield viewer
    viewer.close()


def test_the_default_edges_are_up_as_soon_as_the_window_opens(drawn: ViewerWindow) -> None:
    """The overlays are only ever drawn in response to a change, and a default
    that is on never produces one - so opening the window has to draw them."""
    assert drawn.state.edges.faces
    assert FACE_EDGES in drawn.plotter.renderer.actors
    assert PRIMITIVE_EDGES not in drawn.plotter.renderer.actors


def _offset(mapper: object, kind: str) -> tuple[float, float]:
    """The polygon offset a mapper ends up with: slope factor, then constant."""
    # The getters take their two results as out-parameters. Held as ``Any``
    # because the runtime class behind ``reference`` is a numeric subclass
    # whose ``get`` the type stub does not carry.
    factor: Any = reference(0.0)
    units: Any = reference(0.0)
    getattr(mapper, f"GetCoincidentTopology{kind}OffsetParameters")(factor, units)
    return float(factor.get()), float(units.get())


def test_the_overlays_are_pushed_forward_by_a_constant_only(drawn: ViewerWindow) -> None:
    """No slope term, and the ladder in the order :mod:`pycanha.plot.depth` sets out.

    The slope term scales with how steeply a surface recedes from the camera,
    so with one an outline lifts off distant, edge-on geometry far enough to
    show through whatever is in front of it - and does it only from some
    directions, which is what made it look like a rendering lottery.
    """
    drawn.state.selection = Selection(item_id=drawn.scene.item_ids[0])
    actors = drawn.plotter.renderer.actors
    outline = _offset(actors[FACE_EDGES].mapper, "Line")
    wash = _offset(actors[SELECTION_HIGHLIGHT].mapper, "Polygon")
    geometry = _offset(actors[MESH_ACTOR].mapper, "Line")

    assert outline[0] == wash[0] == 0.0
    # Negative is towards the camera. The outlines take the same push as the
    # triangle edges the geometry actor draws itself - VTK's own, the least
    # that keeps a line clear of its surface - and both sit over the wash, so
    # that a selection cannot eat a line that falls on it.
    assert outline[1] == geometry[1] < wash[1] < 0.0
