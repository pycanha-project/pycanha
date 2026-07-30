"""Resolving a picked polydata cell back to the face's model properties."""

import numpy as np
import pytest

import pycanha as pc
from pycanha import gmm
from pycanha.gmm.picking import (
    FaceInfo,
    _camera_facing_cell,
    face_info,
    format_face_info,
    item_map,
)


def _panel_model() -> pc.ThermalModel:
    """A single 1x1 rectangle: node 5 on side 1, node 6 on side 2."""
    tm = pc.ThermalModel("picking")
    thermal_mesh = gmm.ThermalMesh()
    thermal_mesh.node1_start = 5
    thermal_mesh.node2_start = 6
    thermal_mesh.side1_optical = gmm.OpticalMaterial("white", 0.85, 0.2)
    thermal_mesh.side2_color = gmm.Color(10, 20, 30)
    rect = gmm.Rectangle((0, 0, 0), (2, 0, 0), (0, 1, 0))
    tm.gmm.add(gmm.GeometryItem("panel", rect, thermal_mesh))
    return tm


def _two_panel_model() -> pc.ThermalModel:
    """Two rectangles that deliberately share the same node numbers."""
    tm = pc.ThermalModel("picking")
    for name, origin in (("left", (0.0, 0.0, 0.0)), ("right", (0.0, 0.0, 1.0))):
        thermal_mesh = gmm.ThermalMesh()
        thermal_mesh.node1_start = 5
        thermal_mesh.node2_start = 6
        thermal_mesh.side1_optical = gmm.OpticalMaterial(f"{name}-paint", 0.5, 0.3)
        rect = gmm.Rectangle(origin, (origin[0] + 2, origin[1], origin[2]), (0, 1, origin[2]))
        tm.gmm.add(gmm.GeometryItem(name, rect, thermal_mesh))
    return tm


def test_face_info_single_sided() -> None:
    tm = _panel_model()
    mesh = tm.gmm.mesh
    info = face_info(mesh, 0, items=item_map(tm.gmm))

    assert info.face_id == 0
    assert info.side == 1
    assert info.node_number == 5
    assert info.item_name == "panel"
    assert info.primitive == "Rectangle"
    assert info.optical_name == "white"
    assert info.emissivity_ir == pytest.approx(0.85)
    assert info.absorptivity_solar == pytest.approx(0.2)
    assert info.color == (0, 127, 255)


def test_face_info_both_sides_reports_each_side() -> None:
    tm = _panel_model()
    mesh = tm.gmm.mesh
    items = item_map(tm.gmm)
    n_tri = mesh.nt()

    side1 = face_info(mesh, 0, both_sides=True, items=items)
    side2 = face_info(mesh, n_tri, both_sides=True, items=items)

    assert (side1.side, side1.node_number, side1.face_id) == (1, 5, 0)
    # The side-2 slot is the odd partner of the side-1 slot the triangle names.
    assert (side2.side, side2.node_number, side2.face_id) == (2, 6, 1)

    # Only side 1 was given an optical material, and the sides carry their own colors.
    assert side1.optical_name == "white"
    assert side2.optical_name is None
    assert side2.emissivity_ir is None
    assert side1.color == (0, 127, 255)
    assert side2.color == (10, 20, 30)


def test_face_info_without_items_still_resolves_the_mesh_fields() -> None:
    tm = _panel_model()
    info = face_info(tm.gmm.mesh, 0)

    assert (info.face_id, info.side, info.node_number) == (0, 1, 5)
    assert info.item_name is None
    assert info.primitive is None
    assert info.optical_name is None
    assert info.color is None


def test_face_info_resolves_items_sharing_node_numbers() -> None:
    # Both panels use nodes 5/6, so a node-based lookup cannot tell them apart;
    # the primitive ranges can.
    tm = _two_panel_model()
    mesh = tm.gmm.mesh
    items = item_map(tm.gmm)

    names = {face_info(mesh, cell, items=items).optical_name for cell in range(mesh.nt())}
    assert names == {"left-paint", "right-paint"}

    for cell in range(mesh.nt()):
        info = face_info(mesh, cell, items=items)
        assert info.optical_name == f"{info.item_name}-paint"


def test_face_info_rejects_out_of_range_cells() -> None:
    tm = _panel_model()
    mesh = tm.gmm.mesh
    with pytest.raises(IndexError):
        face_info(mesh, mesh.nt())
    with pytest.raises(IndexError):
        face_info(mesh, -1)


def test_camera_facing_cell_picks_the_visible_copy() -> None:
    # One triangle in the z=0 plane plus its reversed-winding side-2 copy: cell 0
    # has a +z normal, cell 1 a -z normal.
    points = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    triangles = np.array([[0, 1, 2], [2, 1, 0]])
    kwargs = {"n_tri": 1, "triangles": triangles, "points": points}

    from_front = np.array([0.0, 0.0, -1.0])  # camera at +z looking down
    from_behind = np.array([0.0, 0.0, 1.0])  # camera at -z looking up

    assert _camera_facing_cell(0, view_direction=from_front, **kwargs) == 0
    assert _camera_facing_cell(1, view_direction=from_front, **kwargs) == 0
    # The cell picker ignores backface culling, so it may hand back the hidden
    # side-1 copy even when side 2 is the one being looked at.
    assert _camera_facing_cell(0, view_direction=from_behind, **kwargs) == 1
    assert _camera_facing_cell(1, view_direction=from_behind, **kwargs) == 1


def test_format_face_info_full() -> None:
    info = FaceInfo(
        face_id=12,
        side=1,
        node_number=5,
        item_name="panel",
        primitive="Rectangle",
        optical_name="white",
        emissivity_ir=0.85,
        absorptivity_solar=0.2,
        color=(0, 127, 255),
    )
    assert format_face_info(info) == (
        "face 12 (side 1)  node 5  item 'panel' (Rectangle)\n"
        "  optical 'white'  eps_ir 0.850  alpha_sol 0.200  color (0, 127, 255)"
    )


def test_format_face_info_without_item_is_one_line() -> None:
    info = FaceInfo(face_id=3, side=2, node_number=-1)
    assert format_face_info(info) == "face 3 (side 2)  node -1  item -"


def test_format_face_info_item_without_optical_material() -> None:
    info = FaceInfo(
        face_id=0,
        side=2,
        node_number=6,
        item_name="panel",
        primitive="Rectangle",
        color=(10, 20, 30),
    )
    assert format_face_info(info) == (
        "face 0 (side 2)  node 6  item 'panel' (Rectangle)\n"
        "  optical -  eps_ir -  alpha_sol -  color (10, 20, 30)"
    )


def test_plot_data_series_validates_shapes() -> None:
    tm = _panel_model()
    nodes = [5, 6]
    times = [0.0, 1.0, 2.0]

    with pytest.raises(ValueError, match="2-dimensional"):
        tm.gmm.plot_data_series(np.zeros(2), nodes, times, off_screen=True)
    with pytest.raises(ValueError, match="expected"):
        tm.gmm.plot_data_series(np.zeros((2, 2)), nodes, times, off_screen=True)
    with pytest.raises(ValueError, match="expected"):
        tm.gmm.plot_data_series(np.zeros((3, 5)), nodes, times, off_screen=True)
