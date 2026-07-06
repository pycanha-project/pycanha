"""World-mesh building and mesh.ops over a small model."""

import numpy as np
import pytest

import pycanha as pc
from pycanha import gmm
from pycanha.gmm.mesh import ops as mesh_ops


def _unit_panel_model(node_start: int = -1) -> pc.ThermalModel:
    tm = pc.ThermalModel("mesh")
    thermal_mesh = gmm.ThermalMesh()
    thermal_mesh.node1_start = node_start
    thermal_mesh.node2_start = node_start
    rect = gmm.Rectangle((0, 0, 0), (2, 0, 0), (0, 1, 0))
    tm.gmm.add(gmm.GeometryItem("panel", rect, thermal_mesh))
    return tm


def test_world_mesh_shapes_and_ids() -> None:
    tm = _unit_panel_model()
    mesh = tm.gmm.mesh

    assert mesh.np() == 4
    assert mesh.nt() == 2
    assert mesh.nf() == 2
    assert mesh.vertices.shape == (4, 3)
    assert mesh.triangles.shape == (2, 3)
    assert mesh.face_ids.shape == (2,)
    # Two triangles of the same (side-1, even) face.
    assert np.all(mesh.face_ids == 0)
    assert mesh.node_numbers.shape == (2,)


def test_node_numbers_follow_thermalmesh() -> None:
    tm = _unit_panel_model(node_start=100)
    mesh = tm.gmm.mesh
    # Side-1 face (id 0) maps to node 100; side-2 (id 1) also 100 here.
    assert int(mesh.node_numbers[0]) == 100
    assert list(tm.gmm.faces_of_node(100))  # reverse lookup is populated


def test_mesh_ops() -> None:
    tm = _unit_panel_model()
    mesh = tm.gmm.mesh

    areas = np.asarray(mesh_ops.compute_areas(mesh))
    assert areas.sum() == pytest.approx(2.0)

    centroids = np.asarray(mesh_ops.compute_centroids(mesh))
    assert centroids.shape == (2, 3)

    normals = np.asarray(mesh_ops.compute_face_normals(mesh))
    assert normals.shape == (2, 3)

    min_xyz, max_xyz = mesh_ops.bounding_box(mesh)
    np.testing.assert_allclose(np.asarray(min_xyz), (0, 0, 0), atol=1e-6)
    np.testing.assert_allclose(np.asarray(max_xyz), (2, 1, 0), atol=1e-6)

    assert isinstance(mesh_ops.has_consistent_face_ids(mesh), bool)
    assert mesh_ops.has_consistent_face_ids(mesh)
