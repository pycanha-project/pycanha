"""pyvista visualization of the world mesh."""

import numpy as np
import pytest

import pycanha as pc
from pycanha import gmm

pv = pytest.importorskip("pyvista")


def _panel_model() -> pc.ThermalModel:
    tm = pc.ThermalModel("viz")
    thermal_mesh = gmm.ThermalMesh()
    thermal_mesh.node1_start = 5
    thermal_mesh.node2_start = 6
    rect = gmm.Rectangle((0, 0, 0), (2, 0, 0), (0, 1, 0))
    tm.gmm.add(gmm.GeometryItem("panel", rect, thermal_mesh))
    return tm


def test_to_polydata_structure() -> None:
    tm = _panel_model()
    mesh = tm.gmm.mesh
    poly = gmm.to_polydata(mesh)

    assert isinstance(poly, pv.PolyData)
    assert poly.n_points == mesh.np()
    assert poly.n_cells == mesh.nt()
    assert set(poly.cell_data.keys()) == {"face_id", "node_number"}
    np.testing.assert_array_equal(np.asarray(poly.cell_data["face_id"]), np.asarray(mesh.face_ids))
    # Side-1 triangles (even face id 0) map to node 5.
    assert set(np.asarray(poly.cell_data["node_number"]).tolist()) == {5}


def test_model_and_free_function_agree() -> None:
    tm = _panel_model()
    assert tm.gmm.to_polydata().n_cells == gmm.to_polydata(tm.gmm).n_cells


def test_to_polydata_from_model() -> None:
    tm = _panel_model()
    poly = gmm.to_polydata(tm.gmm)
    assert poly.n_cells == tm.gmm.mesh.nt()


def test_to_polydata_both_sides_resolves_side2() -> None:
    tm = _panel_model()  # node 5 on side 1, node 6 on side 2
    mesh = tm.gmm.mesh

    single = gmm.to_polydata(mesh)
    # The mesh has one sheet of triangles and its face_ids name side-1 slots, so
    # the single-sided polydata cannot show side 2 at all.
    assert single.n_cells == mesh.nt()
    assert set(np.asarray(single.cell_data["node_number"]).tolist()) == {5}

    both = gmm.to_polydata(mesh, both_sides=True)
    assert both.n_cells == 2 * mesh.nt()
    assert set(np.asarray(both.cell_data["node_number"]).tolist()) == {5, 6}

    side = np.asarray(both.cell_data["side"])
    node_numbers = np.asarray(both.cell_data["node_number"])
    assert set(node_numbers[side == 1].tolist()) == {5}
    assert set(node_numbers[side == 2].tolist()) == {6}


def test_to_polydata_both_sides_reverses_winding() -> None:
    tm = _panel_model()
    mesh = tm.gmm.mesh
    both = gmm.to_polydata(mesh, both_sides=True)
    triangles = both.faces.reshape(-1, 4)[:, 1:]
    n_tri = mesh.nt()
    # The side-2 copy is the same triangle wound the other way, so it faces the
    # opposite direction and backface culling can separate the two.
    np.testing.assert_array_equal(triangles[n_tri:], triangles[:n_tri][:, ::-1])


def test_categorical_colors() -> None:
    colors = gmm.viz.categorical_colors([0, 1, 2, -1, 20])
    assert colors.shape == (5, 3)
    assert colors.dtype == np.uint8
    # ids cycle through the 20-color palette, so 20 wraps back to 0.
    np.testing.assert_array_equal(colors[4], colors[0])
    # negative ids get the "missing" grey.
    assert colors[3].tolist() == [153, 153, 153]


def test_categorical_colors_rank_separates_sparse_labels() -> None:
    # Node numbers are sparse: 100/200/300/400 are all 0 modulo the 20-color
    # palette and would otherwise render identically.
    labels = [100, 200, 300, 400]
    unranked = gmm.viz.categorical_colors(labels)
    assert len({tuple(c) for c in unranked}) == 1

    ranked = gmm.viz.categorical_colors(labels, rank=True)
    assert len({tuple(c) for c in ranked}) == len(labels)


def test_categorical_colors_rank_keeps_missing_grey() -> None:
    colors = gmm.viz.categorical_colors([100, -1, 200], rank=True)
    assert colors[1].tolist() == [153, 153, 153]
    # The unassigned entry must not consume a palette slot of its own.
    assert colors[0].tolist() != colors[2].tolist()


# NOTE: actual rendering (``gmm.plot`` -> ``pyvista.Plotter.show``) is intentionally
# NOT exercised here. VTK's OpenGL backend segfaults on headless CI runners without a
# GL context, and a segfault cannot be caught, so it would crash the whole test run.
# The data path used for visualization (``to_polydata``) is fully covered above.
