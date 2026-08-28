"""The per-face property arrays behind the color-by combo."""

import numpy as np
import pytest

import pycanha as pc
from pycanha import gmm
from pycanha.plot.polydata import MISSING_RGB
from pycanha.plot.properties import (
    MISSING,
    OPTICAL_KEYS,
    categories,
    face_areas,
    face_properties,
    optical_properties,
)


def _two_item_model() -> pc.ThermalModel:
    """Two 2x1 panels that deliberately share node numbers 100 / 200.

    'left' is aluminium with white paint on side 1 and nothing on side 2;
    'right' is titanium with black paint on both sides and radiates from side 1
    only. Sharing the node numbers is the case a node-keyed item lookup gets
    wrong, and it is why every property here is keyed by face.
    """
    tm = pc.ThermalModel("properties")

    left_mesh = gmm.ThermalMesh([0.0, 0.5, 1.0], [0.0, 1.0])
    left_mesh.node1_start = 100
    left_mesh.node2_start = 200
    left_mesh.side1_optical = gmm.OpticalMaterial("white", 0.85, 0.2)
    left_mesh.side1_material = gmm.BulkMaterial("aluminium", 2700.0, 200.0, 900.0)
    left_mesh.side1_thick = 0.002
    left_mesh.side2_thick = 0.003
    left_mesh.side1_color = gmm.Color(255, 0, 0)
    left_mesh.side2_color = gmm.Color(0, 0, 255)
    tm.gmm.add(gmm.GeometryItem("left", gmm.Rectangle((0, 0, 0), (2, 0, 0), (0, 1, 0)), left_mesh))

    right_mesh = gmm.ThermalMesh([0.0, 0.5, 1.0], [0.0, 1.0])
    right_mesh.node1_start = 100
    right_mesh.node2_start = 200
    black = gmm.OpticalMaterial("black", 0.9, 0.95)
    right_mesh.side1_optical = black
    right_mesh.side2_optical = black
    titanium = gmm.BulkMaterial("titanium", 4500.0, 22.0, 520.0)
    right_mesh.side1_material = titanium
    right_mesh.side2_material = titanium
    right_mesh.radiative_active_side = gmm.ActiveSide.SIDE1
    right_mesh.conductive_active_side = gmm.ActiveSide.NONE
    # Side 1 the same red as 'left', so the two share one category.
    right_mesh.side1_color = gmm.Color(255, 0, 0)
    right_mesh.side2_color = gmm.Color(0, 255, 0)
    tm.gmm.add(
        gmm.GeometryItem("right", gmm.Rectangle((0, 0, 1), (2, 0, 1), (0, 1, 1)), right_mesh)
    )
    return tm


@pytest.fixture
def model() -> gmm.GeometryModel:
    return _two_item_model().gmm


@pytest.fixture
def properties(model: gmm.GeometryModel) -> dict:
    return face_properties(model)


def _faces_of(model: gmm.GeometryModel, name: str) -> slice:
    """Every face of item ``name``, both sides."""
    item_id = model.get_item(name).id
    for geometry_id, first, last in model.mesh.primitives:
        if geometry_id == item_id:
            return slice(int(first), int(last) + 2)
    raise AssertionError(f"item {name!r} owns no faces")


# ── color ────────────────────────────────────────────────────────────────
def test_each_side_carries_its_own_color(model: gmm.GeometryModel, properties: dict) -> None:
    color = properties["color"]
    left, right = _faces_of(model, "left"), _faces_of(model, "right")

    assert color.categorical
    # Three distinct colors over four sides: both side 1s are the same red.
    assert set(color.palette.values()) == {(255, 0, 0), (0, 0, 255), (0, 255, 0)}
    assert color.values[left][0] == color.values[right][0]
    assert color.values[left][1] != color.values[right][1]


def test_a_color_is_drawn_in_itself_rather_than_a_stand_in(properties: dict) -> None:
    color = properties["color"]
    colors = color.colors_of(color.values)
    # The palette is pinned, so what reaches the actor is the stored channels.
    assert set(map(tuple, colors.tolist())) == {(255, 0, 0), (0, 0, 255), (0, 255, 0)}
    assert colors.dtype == np.uint8


def test_a_face_no_item_owns_is_grey(properties: dict) -> None:
    color = properties["color"]
    assert tuple(color.colors_of([-1])[0].tolist()) == MISSING_RGB
    assert color.format(-1) == MISSING


def test_a_color_is_named_by_its_channels(properties: dict) -> None:
    color = properties["color"]
    assert set(color.categories.values()) == {"255, 0, 0", "0, 0, 255", "0, 255, 0"}
    assert color.format(0) == "255, 0, 0"


def test_the_legend_of_a_coloring_uses_the_colors_themselves(
    model: gmm.GeometryModel, properties: dict
) -> None:
    color = properties["color"]
    entries = categories(color, model.mesh.face_ids)
    # Only side 1 is meshed into cells here, and both items are red there.
    assert [(entry.label, entry.color) for entry in entries] == [("255, 0, 0", (255, 0, 0))]


# ── topology ──────────────────────────────────────────────────────────────
def test_item_property_tells_apart_items_that_share_node_numbers(
    model: gmm.GeometryModel, properties: dict
) -> None:
    item = properties["item"]
    left, right = (model.get_item(name).id for name in ("left", "right"))

    assert np.all(item.values[_faces_of(model, "left")] == left)
    assert np.all(item.values[_faces_of(model, "right")] == right)
    assert item.categories == {left: "left", right: "right"}
    assert item.categorical


def test_node_and_side_follow_face_parity(model: gmm.GeometryModel, properties: dict) -> None:
    assert np.array_equal(properties["side"].values, np.tile([1, 2], model.mesh.nf() // 2))
    # Both panels use nodes 100 (side 1) and 200 (side 2).
    assert np.array_equal(properties["node_number"].values[0::2], np.full(4, 100))
    assert np.array_equal(properties["node_number"].values[1::2], np.full(4, 200))


def test_face_id_property_is_the_face_itself(properties: dict) -> None:
    values = properties["face_id"].values
    assert np.array_equal(values, np.arange(values.size))


# ── optical ───────────────────────────────────────────────────────────────
def test_optical_family_covers_the_six_degrees_of_freedom(
    model: gmm.GeometryModel, properties: dict
) -> None:
    assert [key for key, _ in OPTICAL_KEYS] == [
        "emissivity_ir",
        "specularity_ir",
        "transmissivity_ir",
        "absorptivity_solar",
        "specularity_solar",
        "transmissivity_solar",
    ]
    for key, _ in OPTICAL_KEYS:
        assert not properties[key].categorical
        assert properties[key].values.size == model.mesh.nf()


def test_each_side_carries_its_own_optical_material(model: gmm.GeometryModel) -> None:
    values = optical_properties(model)
    left, right = _faces_of(model, "left"), _faces_of(model, "right")

    # 'left' is painted on side 1 only, so its odd faces have nothing to report.
    assert np.all(values[left][0::2, 0] == pytest.approx(0.85))
    assert np.all(np.isnan(values[left][1::2]))
    # 'right' is painted on both sides.
    assert np.all(values[right][:, 0] == pytest.approx(0.9))
    assert np.all(values[right][:, 3] == pytest.approx(0.95))
    # The unset degrees of freedom are zero, not missing.
    assert np.all(values[right][:, 1] == 0.0)


def test_optical_properties_of_a_model_without_materials() -> None:
    tm = pc.ThermalModel("bare")
    tm.gmm.add(
        gmm.GeometryItem("p", gmm.Rectangle((0, 0, 0), (1, 0, 0), (0, 1, 0)), gmm.ThermalMesh())
    )
    assert np.all(np.isnan(optical_properties(tm.gmm)))


# ── bulk and geometric ────────────────────────────────────────────────────
def test_thickness_and_bulk_are_broadcast_per_side(
    model: gmm.GeometryModel, properties: dict
) -> None:
    left = _faces_of(model, "left")
    thickness = properties["thickness"].values[left]
    assert np.all(thickness[0::2] == pytest.approx(0.002))
    assert np.all(thickness[1::2] == pytest.approx(0.003))

    # 'left' has a bulk material on side 1 only.
    density = properties["density"].values[left]
    assert np.all(density[0::2] == pytest.approx(2700.0))
    assert np.all(np.isnan(density[1::2]))
    assert np.all(properties["conductivity"].values[left][0::2] == pytest.approx(200.0))
    assert np.all(properties["specific_heat"].values[left][0::2] == pytest.approx(900.0))


def test_face_area_is_shared_by_the_two_faces_of_a_face(model: gmm.GeometryModel) -> None:
    areas = face_areas(model.mesh)
    # Each panel is 2 m x 1 m split into two faces along the first direction.
    assert np.all(areas == pytest.approx(1.0))
    assert np.array_equal(areas[0::2], areas[1::2])


def test_face_area_of_an_empty_mesh() -> None:
    assert face_areas(pc.ThermalModel("empty").gmm.mesh).size == 0


# ── names and activity ────────────────────────────────────────────────────
def test_material_names_are_interned_as_categories(
    model: gmm.GeometryModel, properties: dict
) -> None:
    optical = properties["optical_name"]
    assert set(optical.categories.values()) == {"white", "black"}
    # Side 2 of 'left' has no optical material, so it falls outside every category.
    assert np.all(optical.values[_faces_of(model, "left")][1::2] == -1)

    bulk = properties["bulk_name"]
    assert set(bulk.categories.values()) == {"aluminium", "titanium"}
    assert np.all(
        bulk.values[_faces_of(model, "right")] == bulk.values[_faces_of(model, "right")][0]
    )


def test_activity_flags_follow_the_active_side_selectors(
    model: gmm.GeometryModel, properties: dict
) -> None:
    left, right = _faces_of(model, "left"), _faces_of(model, "right")
    radiative = properties["radiative_active"].values
    conductive = properties["conductive_active"].values

    # 'left' keeps the default: both sides active for both physics.
    assert np.all(radiative[left] == 1)
    assert np.all(conductive[left] == 1)
    # 'right' radiates from side 1 only and conducts from neither.
    assert np.all(radiative[right][0::2] == 1)
    assert np.all(radiative[right][1::2] == 0)
    assert np.all(conductive[right] == 0)
    assert properties["radiative_active"].categories == {0: "inactive", 1: "active"}


# ── presentation ──────────────────────────────────────────────────────────
def test_per_cell_spreads_a_property_over_the_polydata_cells(
    model: gmm.GeometryModel, properties: dict
) -> None:
    poly = model.to_polydata(both_sides=True)
    face_ids = np.asarray(poly.cell_data["face_id"])
    values = properties["item"].per_cell(face_ids)

    assert values.size == poly.n_cells
    assert np.array_equal(values, properties["item"].values[face_ids])


def test_the_five_families_are_offered_in_order(properties: dict) -> None:
    keys = list(properties)
    # The color first: it is what a window opens on.
    assert keys[:5] == ["color", "item", "node_number", "face_id", "side"]
    assert keys[5:11] == [key for key, _ in OPTICAL_KEYS]
    assert set(keys[11:]) == {
        "thickness",
        "density",
        "conductivity",
        "specific_heat",
        "optical_name",
        "bulk_name",
        "radiative_active",
        "conductive_active",
        "area",
    }


def test_numeric_properties_carry_their_unit(properties: dict) -> None:
    assert properties["area"].unit == "m^2"
    assert properties["density"].unit == "kg/m^3"
    assert properties["emissivity_ir"].unit == ""


def test_properties_of_an_empty_model() -> None:
    properties = face_properties(pc.ThermalModel("empty").gmm)
    assert all(prop.values.size == 0 for prop in properties.values())
