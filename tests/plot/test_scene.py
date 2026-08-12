"""The master mesh, its indices, and the visible subset handed to VTK."""

import numpy as np
import pytest

import pycanha as pc
from pycanha import gmm
from pycanha.plot.picking import item_map, owning_item
from pycanha.plot.scene import Scene, slot_items


def _two_panel_model() -> pc.ThermalModel:
    """Two 2x1-meshed rectangles: 'a' on nodes 100/200, 'b' on 110/210.

    Each panel is 2 faces, so 4 triangles per side and 8 master cells with
    ``both_sides``; the two panels give 16.
    """
    tm = pc.ThermalModel("scene")
    for index, name in enumerate(("a", "b")):
        thermal_mesh = gmm.ThermalMesh()
        thermal_mesh.dir1_mesh = [0.0, 0.5, 1.0]
        thermal_mesh.dir2_mesh = [0.0, 1.0]
        thermal_mesh.node1_start = 100 + 10 * index
        thermal_mesh.node2_start = 200 + 10 * index
        height = float(index)
        rect = gmm.Rectangle((0, 0, height), (2, 0, height), (0, 1, height))
        tm.gmm.add(gmm.GeometryItem(name, rect, thermal_mesh))
    return tm


def _cut_away_model() -> pc.ThermalModel:
    """A rectangle cut away entirely by a cube, followed by an untouched one.

    The cut item keeps a primitive range, collapsed onto the offset where the
    next item starts - so both ranges claim slot 0 and only the later one is
    right about it.
    """
    tm = pc.ThermalModel("cut")
    target_mesh = gmm.ThermalMesh()
    target_mesh.node1_start = 100
    target_mesh.node2_start = 200
    target = gmm.GeometryItem("target", gmm.Rectangle((0, 0, 0), (1, 0, 0), (0, 1, 0)), target_mesh)
    cutter_mesh = gmm.ThermalMesh()
    cutter_mesh.node1_start = 300
    cutter_mesh.node2_start = 400
    cutter = gmm.GeometryItem("cutter", gmm.Cube((0.5, 0.5, 0.0), (10, 10, 10)), cutter_mesh)
    tm.gmm.add(gmm.GeometryGroupCutted("cut", [target], [cutter]))

    plain_mesh = gmm.ThermalMesh()
    plain_mesh.node1_start = 500
    plain_mesh.node2_start = 600
    tm.gmm.add(
        gmm.GeometryItem("plain", gmm.Rectangle((0, 0, 9), (1, 0, 9), (0, 1, 9)), plain_mesh)
    )
    return tm


@pytest.fixture
def scene() -> Scene:
    return Scene(_two_panel_model().gmm)


# ── construction ──────────────────────────────────────────────────────────
def test_master_arrays_cover_both_sides(scene: Scene) -> None:
    assert scene.n_cells == 16
    assert scene.triangles.shape == (16, 3)
    # The first half is side 1, the second the reversed-winding side-2 copies.
    assert np.array_equal(scene.sides, np.repeat([1, 2], 8))
    # Side-2 cells name the odd partner of the side-1 slot the triangle carries.
    assert np.array_equal(scene.face_ids[8:], scene.face_ids[:8] ^ 1)
    assert set(scene.node_numbers.tolist()) == {100, 110, 200, 210}


def test_single_sided_scene_has_no_side_two_cells() -> None:
    scene = Scene(_two_panel_model().gmm, both_sides=False)
    assert scene.n_cells == 8
    assert np.all(scene.sides == 1)
    assert "side" not in scene.visible_polydata().cell_data


def test_item_index_matches_the_owning_item_scan(scene: Scene) -> None:
    mesh = scene.mesh
    items = item_map(scene.model)
    for cell in range(scene.n_cells):
        base_slot = int(scene.face_ids[cell]) & ~1
        expected = owning_item(mesh, base_slot, items)
        assert scene.item_of_cell(cell) == expected.id


def test_item_cells_partition_the_master_cells(scene: Scene) -> None:
    ids = [item.id for item in (scene.model.get_item("a"), scene.model.get_item("b"))]
    assert scene.item_ids == sorted(ids)
    grouped = np.concatenate([scene.cells_of_item(item_id) for item_id in scene.item_ids])
    assert np.array_equal(np.sort(grouped), np.arange(scene.n_cells))
    # Each item owns both sides of its own faces: 2 faces x 2 triangles x 2 sides.
    assert all(scene.cells_of_item(item_id).size == 8 for item_id in scene.item_ids)


def test_slot_items_claims_both_slots_of_every_face(scene: Scene) -> None:
    # The primitive ranges are expressed in side-1 slots, so the side-2 partner
    # of the last face of a range is only covered because the slice runs past it.
    assert not np.any(scene.slot_items < 0)


def test_a_cut_away_item_owns_no_cells() -> None:
    model = _cut_away_model().gmm
    scene = Scene(model)
    target = model.get_item("target")
    plain = model.get_item("plain")

    assert scene.cells_of_item(target.id).size == 0
    assert scene.item_ids == [plain.id]
    # Both ranges claim slot 0; the later one is the one that actually made it.
    assert np.all(scene.cell_items == plain.id)
    assert set(scene.node_numbers.tolist()) == {500, 600}


def test_empty_model_yields_no_cells() -> None:
    scene = Scene(pc.ThermalModel("empty").gmm)
    assert scene.n_cells == 0
    assert scene.item_ids == []
    assert scene.visible_polydata().n_cells == 0
    assert scene.visible_cells.size == 0


def test_slot_items_of_a_bare_mesh() -> None:
    # Geometry ids come from a global counter, so read them off the model.
    model = _two_panel_model().gmm
    expected = [model.get_item(name).id for name in ("a", "b")]
    assert np.array_equal(slot_items(model.mesh), np.repeat(expected, 4))


# ── visibility ────────────────────────────────────────────────────────────
def test_hiding_an_item_drops_exactly_its_cells(scene: Scene) -> None:
    hidden = scene.model.get_item("a").id
    assert scene.set_hidden([hidden])

    assert scene.visible_cells.size == 8
    assert np.all(scene.cell_items[scene.visible_cells] != hidden)
    # The subset keeps the master order, so it is still ascending.
    assert np.array_equal(scene.visible_cells, np.sort(scene.visible_cells))


def test_setting_the_same_hidden_set_reports_no_change(scene: Scene) -> None:
    hidden = [scene.model.get_item("a").id]
    assert scene.set_hidden(hidden)
    assert not scene.set_hidden(hidden)
    assert scene.hidden == frozenset(hidden)


def test_showing_everything_again_restores_every_cell(scene: Scene) -> None:
    scene.set_hidden([scene.model.get_item("a").id])
    scene.set_hidden([])
    assert np.array_equal(scene.visible_cells, np.arange(scene.n_cells))


def test_hiding_an_unknown_id_hides_nothing(scene: Scene) -> None:
    scene.set_hidden([999])
    assert scene.visible_cells.size == scene.n_cells


# ── the visible subset ────────────────────────────────────────────────────
def test_visible_polydata_carries_the_subset_arrays(scene: Scene) -> None:
    scene.set_hidden([scene.model.get_item("a").id])
    subset = scene.visible_polydata()

    assert subset.n_cells == 8
    assert np.array_equal(subset.cell_data["face_id"], scene.face_ids[scene.visible_cells])
    assert np.array_equal(subset.cell_data["node_number"], np.repeat([110, 210], 4))
    assert np.array_equal(subset.cell_data["side"], np.repeat([1, 2], 4))
    # The point array is shared whole rather than re-indexed: VTK tolerates
    # points no triangle references, so hiding costs no vertex copy.
    assert subset.n_points == scene.points.shape[0]


def test_visible_polydata_is_rebuilt_only_when_visibility_changes(scene: Scene) -> None:
    first = scene.visible_polydata()
    assert scene.visible_polydata() is first

    scene.set_hidden([scene.model.get_item("a").id])
    assert scene.visible_polydata() is not first


def test_pick_round_trips_from_the_subset_to_the_master(scene: Scene) -> None:
    hidden = scene.model.get_item("a").id
    scene.set_hidden([hidden])
    subset = scene.visible_polydata()

    for subset_cell in range(subset.n_cells):
        master = scene.master_cell(subset_cell)
        assert scene.face_ids[master] == subset.cell_data["face_id"][subset_cell]
        assert scene.item_of_cell(master) != hidden


def test_master_cell_rejects_a_cell_outside_the_subset(scene: Scene) -> None:
    scene.set_hidden([scene.model.get_item("a").id])
    with pytest.raises(IndexError):
        scene.master_cell(8)
    with pytest.raises(IndexError):
        scene.master_cell(-1)


def test_visible_scalars_selects_the_drawn_cells(scene: Scene) -> None:
    values = np.arange(scene.n_cells, dtype=np.float64)
    scene.set_hidden([scene.model.get_item("a").id])
    assert np.array_equal(scene.visible_scalars(values), scene.visible_cells.astype(np.float64))


def test_visible_scalars_rejects_a_mismatched_length(scene: Scene) -> None:
    with pytest.raises(ValueError, match="one per master cell"):
        scene.visible_scalars(np.zeros(3))


def test_visible_index_finds_a_cell_s_row_in_the_subset(scene: Scene) -> None:
    scene.set_hidden([scene.model.get_item("a").id])
    cells = scene.visible_cells[[0, 3]]
    # The inverse of visible_cells: what a per-drawn-cell array is indexed with.
    assert np.array_equal(scene.visible_index(cells), [0, 3])
    everything = np.arange(scene.visible_cells.size)
    assert np.array_equal(scene.visible_index(scene.visible_cells), everything)


def test_visible_index_rejects_a_cell_that_is_not_drawn(scene: Scene) -> None:
    hidden = scene.cells_of_item(scene.model.get_item("a").id)
    scene.set_hidden([scene.model.get_item("a").id])
    with pytest.raises(ValueError, match="currently drawn"):
        scene.visible_index(hidden[:1])


# ── lookups ───────────────────────────────────────────────────────────────
def test_cells_of_face_are_the_triangles_of_one_side_of_one_face(scene: Scene) -> None:
    cells = scene.cells_of_face(0)
    assert cells.size == 2
    assert np.all(scene.face_ids[cells] == 0)
    assert np.all(scene.sides[cells] == 1)
    # The odd partner slot is the same face seen from the other side.
    assert np.all(scene.sides[scene.cells_of_face(1)] == 2)


def test_cells_of_node_span_every_face_of_that_node(scene: Scene) -> None:
    cells = scene.cells_of_node(100)
    assert cells.size == 4
    assert np.all(scene.node_numbers[cells] == 100)
    assert scene.cells_of_node(999).size == 0


def test_node_range_mask_greys_by_node_number(scene: Scene) -> None:
    mask = scene.node_range_mask(100, 110)
    assert mask.sum() == 8
    assert set(scene.node_numbers[mask].tolist()) == {100, 110}
    assert not scene.node_range_mask(1, 2).any()
