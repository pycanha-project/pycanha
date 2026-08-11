"""Face and primitive outlines, and the seam the mesher cannot give them.

The extraction is plain numpy over a triangulation, so most of this needs no
model at all; the rest builds one and asserts on the line segments that would
have been handed to VTK.
"""

from collections.abc import Iterator

import numpy as np
import pytest
from PySide6.QtWidgets import QWidget

import pycanha as pc
from pycanha import gmm
from pycanha.plot.edges import face_edges, group_boundary_edges, primitive_edges
from pycanha.plot.polydata import polydata_from_lines
from pycanha.plot.state import EdgeDisplay
from pycanha.plot.window import FACE_EDGES, PRIMITIVE_EDGES, ViewerWindow

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
    window.toolbar.face_edges_action.setChecked(True)
    assert window.state.edges == EdgeDisplay(faces=True)

    window.toolbar.primitive_edges_action.setChecked(True)
    window.toolbar.triangle_edges_action.setChecked(True)
    assert window.state.edges == EdgeDisplay(triangles=True, faces=True, primitives=True)

    window.toolbar.face_edges_action.setChecked(False)
    assert window.state.edges == EdgeDisplay(triangles=True, faces=False, primitives=True)


def test_the_toggles_echo_state_set_elsewhere(window: ViewerWindow) -> None:
    window.state.edges = EdgeDisplay(triangles=True, primitives=True)
    assert window.toolbar.triangle_edges_action.isChecked()
    assert not window.toolbar.face_edges_action.isChecked()
    assert window.toolbar.primitive_edges_action.isChecked()


def test_drawing_edges_without_a_plotter_is_a_no_op(window: ViewerWindow) -> None:
    window.state.edges = EdgeDisplay(faces=True, primitives=True)
    assert window.plotter is None
    # The overlay names exist for the live path to manage; nothing to assert
    # here but that turning them on did not raise.
    assert FACE_EDGES != PRIMITIVE_EDGES
