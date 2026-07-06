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


def test_plot_off_screen() -> None:
    tm = _panel_model()
    try:
        plotter = gmm.plot(tm.gmm.mesh, off_screen=True)
    except (RuntimeError, OSError) as exc:  # no GL / render backend in this env
        pytest.skip(f"pyvista rendering unavailable: {exc}")
    plotter.close()
