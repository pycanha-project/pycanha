"""GeometryModel convenience: hierarchy tree + emissivity / node-range data."""

import numpy as np
import pytest

import pycanha as pc
from pycanha import gmm
from pycanha.plot.scene import face_items

pv = pytest.importorskip("pyvista")


def _optical(emissivity: float) -> gmm.OpticalMaterial:
    optical = gmm.OpticalMaterial()
    optical.emissivity_ir = emissivity
    return optical


def _nested_model() -> pc.ThermalModel:
    tm = pc.ThermalModel("demo")

    mesh_a = gmm.ThermalMesh([0.0, 0.5, 1.0], [0.0, 0.5, 1.0])
    mesh_a.node1_start = 10
    mesh_a.node2_start = 10
    mesh_a.side1_optical = _optical(0.2)
    mesh_a.side2_optical = _optical(0.2)
    item_a = gmm.GeometryItem("A", gmm.Rectangle((0, 0, 0), (1, 0, 0), (0, 1, 0)), mesh_a)

    mesh_b = gmm.ThermalMesh([0.0, 0.5, 1.0], [0.0, 0.5, 1.0])
    mesh_b.node1_start = 100
    mesh_b.node2_start = 100
    mesh_b.side1_optical = _optical(0.9)
    mesh_b.side2_optical = _optical(0.9)
    item_b = gmm.GeometryItem("B", gmm.Rectangle((2, 0, 0), (3, 0, 0), (2, 1, 0)), mesh_b)

    tm.gmm.add(gmm.GeometryGroup("wing", [item_a, item_b]))

    plate = gmm.GeometryItem(
        "plate", gmm.Rectangle((-2, -2, 0), (-1, -2, 0), (-2, -1, 0)), gmm.ThermalMesh()
    )
    hole = gmm.GeometryItem(
        "hole",
        gmm.Cylinder((-1.5, -1.5, -1), (-1.5, -1.5, 1), (-1.3, -1.5, -1), 0.2, 0.0, 2 * np.pi),
        gmm.ThermalMesh(),
    )
    tm.gmm.add(plate - hole)
    return tm


def test_format_tree_shows_hierarchy() -> None:
    tree = _nested_model().gmm.format_tree()
    assert "GeometryModel 'demo'" in tree
    assert "Group 'wing'" in tree
    assert "Item 'A'  Rectangle" in tree
    assert "nodes 10..10" in tree
    assert "CutGroup" in tree
    assert "[target] Item 'plate'" in tree
    assert "[cutter] Item 'hole'  Cylinder" in tree
    # ASCII connectors so it prints on any console encoding.
    assert "`-- " in tree
    assert "|-- " in tree


def test_to_polydata_emissivity_opt_in() -> None:
    model = _nested_model().gmm

    plain = model.to_polydata()
    assert "emissivity" not in plain.cell_data

    poly = model.to_polydata(emissivity=True)
    assert "emissivity" in poly.cell_data
    emissivity = np.asarray(poly.cell_data["emissivity"])
    assigned = emissivity[~np.isnan(emissivity)]
    assert set(np.round(assigned, 3).tolist()) == {0.2, 0.9}


def test_emissivity_nan_when_side_has_no_optical() -> None:
    tm = pc.ThermalModel("bare")
    tm.gmm.add(
        gmm.GeometryItem("p", gmm.Rectangle((0, 0, 0), (1, 0, 0), (0, 1, 0)), gmm.ThermalMesh())
    )
    emissivity = np.asarray(tm.gmm.to_polydata(emissivity=True).cell_data["emissivity"])
    assert np.all(np.isnan(emissivity))


def test_item_coloring_partitions_by_item() -> None:
    # The data path behind plot(scalars="item"): the mesh's primitive ranges say
    # which item produced each face.
    model = _nested_model().gmm
    poly = model.to_polydata()
    face_ids = np.asarray(poly.cell_data["face_id"]).astype(np.intp)
    owners = face_items(model.mesh)[face_ids]

    expected = {model.get_item(name).id for name in ("A", "B", "plate")}
    assert set(owners.tolist()) == expected


def test_node_range_partition() -> None:
    # The data path behind plot_node_range: split cells by node-number window.
    poly = _nested_model().gmm.to_polydata()
    node_numbers = np.asarray(poly.cell_data["node_number"])
    in_range = (node_numbers >= 10) & (node_numbers <= 20)
    # Item A nodes (10) fall in [10, 20]; item B nodes (100) do not.
    assert in_range.any()
    assert (~in_range).any()
