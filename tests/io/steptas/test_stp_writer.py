"""Writing STEP-TAS, checked by reading back what was written.

A written file has two things to get right and they are checked separately.
The *geometry* is checked by round trip: a model read from one format, written
out and read back has to be the same model, shape by shape and number by
number.  The *file* is checked structurally -- the reference dictionary intact,
the instances the protocol requires present, and every reference resolving --
because a file can describe the right geometry and still not be one another
tool would accept.

The fixtures are the ones the reader is tested on, so a failure here is about
writing rather than about a fixture nobody else uses.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from pycanha.gmm import GeometryItem, GeometryModel
from pycanha.gmm.materials import BulkMaterial, Color, OpticalMaterial
from pycanha.gmm.primitives import Cube, Disc, Rectangle
from pycanha.gmm.scene import GeometryGroup, GeometryGroupCutted
from pycanha.gmm.thermalmesh import ActiveSide, ThermalMesh
from pycanha.io.part21 import Reference, read_part21
from pycanha.io.steptas.dictionary import reference_dictionary

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pycanha.io.part21 import Value

DATA = Path(__file__).resolve().parents[2] / "data" / "esatan"
FEATURES = DATA / "FEATURES.erg"

#: Areas match to this fraction; the shapes are rebuilt, not copied.
TOLERANCE = 1e-9


def quiet(_note: object) -> None:
    """Diagnostics are asserted on where they matter, not printed everywhere."""


def listed(value: Value) -> tuple[Value, ...]:
    """*value* as the aggregate it is meant to be.

    An attribute read back out of a file is any part-21 value at all, so an
    assertion about a list of them has to say which shape it expects.  Saying
    it here means a wrongly-written attribute fails as itself rather than as an
    index error several lines further down.
    """
    assert isinstance(value, tuple), f"expected an aggregate, got {value!r}"
    return value


def number(value: Value) -> float:
    """*value* as the real or integer it is meant to be."""
    assert isinstance(value, (int, float)), f"expected a number, got {value!r}"
    # `.T.` parses to a bool, which is an int in Python and a different literal here.
    assert not isinstance(value, bool), f"expected a number, got {value!r}"
    return float(value)


def numbers(value: Value) -> list[float]:
    """*value* as the list of numbers it is meant to be."""
    return [number(item) for item in listed(value)]


def count(value: Value) -> int:
    """*value* as the integer count it is meant to be."""
    assert isinstance(value, int), f"expected an integer, got {value!r}"
    assert not isinstance(value, bool), f"expected an integer, got {value!r}"
    return value


def reference(value: Value) -> Reference:
    """*value* as the instance reference it is meant to be."""
    assert isinstance(value, Reference), f"expected a reference, got {value!r}"
    return value


def items(model: GeometryModel) -> dict[str, GeometryItem]:
    return {
        child.name: child for child in model.children_recursive() if isinstance(child, GeometryItem)
    }


def cutters(model: GeometryModel) -> set[str]:
    """The items used as cutting tools, found rather than named.

    A tool becomes a solid in the format, and a solid has no faces: no node
    numbers, no per-side materials, nothing but its shape and where it is.  So
    every comparison of what survives a round trip has to leave them out -- and
    reading which items they are off the model is what stops that exemption
    quietly covering a surface as well, or missing a tool nobody renamed.
    """
    return {
        cutter.name
        for group in model.children_recursive()
        if isinstance(group, GeometryGroupCutted)
        for cutter in group.cutters
    }


def written(source: Path, target: Path, name: str) -> tuple[GeometryModel, GeometryModel]:
    """The model from *source*, and the model its written file reads back as."""
    original = GeometryModel(name)
    original.io.read_esatan_erg(source, on_diagnostic=quiet)
    original.io.write_steptas(target, name=name, on_diagnostic=quiet)
    reread = GeometryModel(name)
    reread.io.read_steptas(target, on_diagnostic=quiet)
    return original, reread


@pytest.fixture(scope="module")
def feature_round_trip(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, GeometryModel, GeometryModel]:
    target = tmp_path_factory.mktemp("steptas") / "FEATURES.stp"
    original, reread = written(FEATURES, target, "FEATURES")
    return target, original, reread


# -- the geometry ------------------------------------------------------------


def test_every_item_survives_the_round_trip_under_its_own_name(
    feature_round_trip: tuple[Path, GeometryModel, GeometryModel],
) -> None:
    _, original, reread = feature_round_trip
    assert sorted(items(original)) == sorted(items(reread))


def test_every_surface_keeps_its_area(
    feature_round_trip: tuple[Path, GeometryModel, GeometryModel],
) -> None:
    """The strongest single check: shapes are rebuilt from points, not copied."""
    _, original, reread = feature_round_trip
    before, after = items(original), items(reread)
    for name in sorted(before):
        one = before[name].primitive.surface_area()
        two = after[name].primitive.surface_area()
        assert one == pytest.approx(two, rel=TOLERANCE), name


def test_every_mesh_keeps_its_cuts(
    feature_round_trip: tuple[Path, GeometryModel, GeometryModel],
) -> None:
    """Including the two whose directions are exchanged by the format."""
    _, original, reread = feature_round_trip
    before, after = items(original), items(reread)
    for name in sorted(before):
        one, two = before[name].thermal_mesh, after[name].thermal_mesh
        assert list(one.dir1_mesh) == pytest.approx(list(two.dir1_mesh)), name
        assert list(one.dir2_mesh) == pytest.approx(list(two.dir2_mesh)), name


def test_every_node_numbering_survives(
    feature_round_trip: tuple[Path, GeometryModel, GeometryModel],
) -> None:
    """Which is what pins the face ordering: a transposed mesh moves the numbers.

    A cutting tool is the exception and is checked below: it becomes a solid,
    which has no faces to number.
    """
    _, original, reread = feature_round_trip
    before, after = items(original), items(reread)
    tools = cutters(original)
    for name in sorted(before):
        if name in tools:
            continue
        one, two = before[name].thermal_mesh, after[name].thermal_mesh
        for side in (1, 2):
            start = getattr(one, f"node{side}_start")
            if start < 0:
                continue
            assert start == getattr(two, f"node{side}_start"), (name, side)
            assert getattr(one, f"node{side}_step") == getattr(two, f"node{side}_step"), (
                name,
                side,
            )


def test_the_faces_are_written_in_the_order_the_numbering_runs(tmp_path: Path) -> None:
    """The check on the face ordering, which the start and step alone would hide.

    The format lists faces with its own first direction varying fastest, and on
    a surface of revolution that direction is the other one.  Writing them in
    this model's order instead would leave every number on the wrong face, and
    the reader would find a sequence no single increment reproduces.
    """
    model = GeometryModel("ORDER")
    model.io.read_esatan_erg(FEATURES, on_diagnostic=quiet)
    target = tmp_path / "order.stp"
    model.io.write_steptas(target, on_diagnostic=quiet)
    reread = GeometryModel("back")
    notes = reread.io.read_steptas(target, on_diagnostic=quiet)
    assert "TAS_NODE_ORDER_IRREGULAR" not in notes.codes()
    # The surface this is really about: meshed in both directions, revolved, and
    # numbered, so a transposed order would show up as an irregular sequence.
    disc = items(reread)["SCS_DISC"].thermal_mesh
    assert len(disc.dir1_mesh) > 2
    assert len(disc.dir2_mesh) > 2
    assert disc.node1_start >= 0


def test_materials_and_thicknesses_survive_where_the_format_keeps_them(
    feature_round_trip: tuple[Path, GeometryModel, GeometryModel],
) -> None:
    """A bulk needs a thickness beside it, and only then does either survive."""
    _, original, reread = feature_round_trip
    before, after = items(original), items(reread)
    tools = cutters(original)
    for name in sorted(before):
        one, two = before[name].thermal_mesh, after[name].thermal_mesh
        for side in (1, 2):
            optical = getattr(one, f"side{side}_optical")
            if optical is not None and name not in tools:
                assert getattr(two, f"side{side}_optical").name == optical.name, (name, side)
            bulk = getattr(one, f"side{side}_material")
            thick = getattr(one, f"side{side}_thick")
            if bulk is not None and thick > 0.0:
                assert getattr(two, f"side{side}_material").name == bulk.name, (name, side)
                assert getattr(two, f"side{side}_thick") == pytest.approx(thick), (name, side)


def test_optical_values_survive_the_specularity_conversion(
    feature_round_trip: tuple[Path, GeometryModel, GeometryModel],
) -> None:
    """The format states a specular *share*; the value has to come back whole."""
    _, original, reread = feature_round_trip
    before, after = items(original), items(reread)
    tools = cutters(original)
    checked = 0
    for name in sorted(before):
        optical = before[name].thermal_mesh.side1_optical
        if optical is None or name in tools:
            continue
        other = after[name].thermal_mesh.side1_optical
        assert list(other.th_optical_properties) == pytest.approx(
            list(optical.th_optical_properties)
        ), name
        checked += 1
    assert checked > 0


def test_a_cut_survives_with_its_tools(
    feature_round_trip: tuple[Path, GeometryModel, GeometryModel],
) -> None:
    """Three targets cut by six tools between them, all still there afterwards.

    The format removes one solid per difference surface, so a shape cut by
    several becomes a chain of them -- and reading that chain back gives one
    cut group per tool rather than one holding them all.  A group holding two
    would mean the chain had been flattened, which is a different model with
    the same silhouette.

    One of the three targets is a combination rather than a single surface, and
    it goes through the format the same way: the difference is taken against the
    compound, so it still arrives back as one cut group with one tool.
    """
    _, original, reread = feature_round_trip
    before, after = items(original), items(reread)
    assert sorted(before) == sorted(after)
    assert cutters(original) == cutters(reread)
    assert len(cutters(original)) == 6
    cuts = [
        child for child in reread.children_recursive() if isinstance(child, GeometryGroupCutted)
    ]
    assert len(cuts) == 6
    assert all(len(cut.cutters) == 1 for cut in cuts)


# -- the file ----------------------------------------------------------------


def test_the_reference_dictionary_is_written_unchanged(
    feature_round_trip: tuple[Path, GeometryModel, GeometryModel],
) -> None:
    """Line for line: it is carried, not rebuilt, and nothing may edit it."""
    target, _, _ = feature_round_trip
    dictionary = dict(reference_dictionary().lines())
    body = set(target.read_text(encoding="utf-8").splitlines())
    assert set(dictionary.values()) <= body


def test_the_dictionary_supplies_every_number_the_writer_pins(
    feature_round_trip: tuple[Path, GeometryModel, GeometryModel],
) -> None:
    """The instances the dictionary refers to and does not define are all there."""
    target, _, _ = feature_round_trip
    parsed = read_part21(target)
    for identifier in reference_dictionary().reserved:
        assert identifier in parsed.entities


def test_no_reference_in_a_written_file_dangles(
    feature_round_trip: tuple[Path, GeometryModel, GeometryModel],
) -> None:
    target, _, _ = feature_round_trip
    parsed = read_part21(target)

    def references(value: object) -> Iterator[Reference]:
        if isinstance(value, Reference):
            yield value
        elif isinstance(value, tuple):
            for item in value:
                yield from references(item)

    for entity in parsed:
        for record in entity.records:
            for reference in references(record.params):
                assert reference.id in parsed.entities, (entity, reference)


def test_the_model_lists_every_item_and_names_one_root(
    feature_round_trip: tuple[Path, GeometryModel, GeometryModel],
) -> None:
    target, _, _ = feature_round_trip
    parsed = read_part21(target)
    model = parsed.of_kind("MGM_MESHED_GEOMETRIC_MODEL")[0]
    members = {reference(value).id for value in listed(model.params[6])}
    built = {
        entity.id
        for kind in (
            "MGM_COMPOUND_MESHED_GEOMETRIC_ITEM",
            "MGM_MESHED_PRIMITIVE_BOUNDED_SURFACE",
            "MGM_MESHED_BOOLEAN_DIFFERENCE_SURFACE",
        )
        for entity in parsed.of_kind(kind)
    }
    assert members == built
    assert isinstance(model.params[19], Reference)


def test_every_shape_names_the_item_that_uses_it(
    feature_round_trip: tuple[Path, GeometryModel, GeometryModel],
) -> None:
    """The format states this inverse both ways round, and a file must too."""
    target, _, _ = feature_round_trip
    parsed = read_part21(target)
    for surface in parsed.of_kind("MGM_MESHED_PRIMITIVE_BOUNDED_SURFACE"):
        shape = parsed.entity(surface.params[6])
        assert shape is not None
        assert shape.params[0] == Reference(surface.id)
    for difference in parsed.of_kind("MGM_MESHED_BOOLEAN_DIFFERENCE_SURFACE"):
        half_space = parsed.entity(difference.params[7])
        assert half_space is not None
        solid = parsed.entity(half_space.params[4])
        assert solid is not None
        assert solid.params[0] == Reference(difference.id)


def test_a_surface_has_as_many_faces_as_its_mesh_says(
    feature_round_trip: tuple[Path, GeometryModel, GeometryModel],
) -> None:
    target, _, _ = feature_round_trip
    parsed = read_part21(target)
    for surface in parsed.of_kind("MGM_MESHED_PRIMITIVE_BOUNDED_SURFACE"):
        expected = count(surface.params[16]) * count(surface.params[17])
        assert len(listed(surface.params[22])) == expected
        assert len(listed(surface.params[23])) == expected


def test_a_grid_is_written_only_where_the_division_is_uneven(
    feature_round_trip: tuple[Path, GeometryModel, GeometryModel],
) -> None:
    """An absent grid means an even division, so writing one would repeat it."""
    target, _, _ = feature_round_trip
    parsed = read_part21(target)
    grids = [
        grid
        for surface in parsed.of_kind("MGM_MESHED_PRIMITIVE_BOUNDED_SURFACE")
        for grid in (surface.params[20], surface.params[21])
        if grid is not None
    ]
    assert grids
    for value in grids:
        grid = numbers(value)
        assert grid[0] == 0.0
        assert grid[-1] == 1.0
        assert grid != pytest.approx([index / (len(grid) - 1) for index in range(len(grid))])


def test_a_node_number_is_one_instance_however_many_faces_carry_it(
    feature_round_trip: tuple[Path, GeometryModel, GeometryModel],
) -> None:
    """Node merging: a number may be defined once in a network model."""
    target, _, _ = feature_round_trip
    parsed = read_part21(target)
    numbers = [entity.params[0] for entity in parsed.of_kind("NRF_NETWORK_NODE")]
    assert len(numbers) == len(set(numbers))


def test_angles_are_written_in_the_unit_the_file_declares(
    feature_round_trip: tuple[Path, GeometryModel, GeometryModel],
) -> None:
    """A whole sweep is 360 of them, not two pi: the file's unit is degrees."""
    target, _, _ = feature_round_trip
    parsed = read_part21(target)
    angle = reference_dictionary().context_quantity_type("plane_angle")
    sweeps = [
        number(listed(entity.params[1])[0])
        for entity in parsed.of_kind("NRF_REAL_QUANTITY_VALUE_LITERAL")
        if entity.params[0] == Reference(angle)
    ]
    assert 360.0 in sweeps
    assert all(-360.0 <= value <= 360.0 for value in sweeps)


# -- what a model holds and the format does not ------------------------------


def one_surface(mesh: ThermalMesh) -> GeometryModel:
    model = GeometryModel("ONE")
    model.add(GeometryItem("PLATE", Rectangle([0, 0, 0], [1, 0, 0], [0, 1, 0]), mesh))
    return model


def codes(model: GeometryModel, path: Path) -> set[str]:
    return set(model.io.write_steptas(path, on_diagnostic=quiet).codes())


def test_an_active_side_with_no_optical_is_written_inactive(tmp_path: Path) -> None:
    mesh = ThermalMesh()
    mesh.radiative_active_side = ActiveSide.BOTH
    target = tmp_path / "active.stp"
    assert "TAS_WRITE_ACTIVE_WITHOUT_OPTICAL" in codes(one_surface(mesh), target)
    back = GeometryModel("back")
    back.io.read_steptas(target, on_diagnostic=quiet)
    plate = items(back)["PLATE"].thermal_mesh
    assert plate.radiative_active_side is ActiveSide.NONE


def test_a_thickness_with_no_bulk_material_is_left_out(tmp_path: Path) -> None:
    mesh = ThermalMesh()
    mesh.side1_thick = 0.002
    assert "TAS_WRITE_THICKNESS_DROPPED" in codes(one_surface(mesh), tmp_path / "thick.stp")


def test_a_bulk_material_with_no_thickness_is_left_out(tmp_path: Path) -> None:
    mesh = ThermalMesh()
    mesh.side1_material = BulkMaterial("Alu", 2700.0, 160.0, 900.0)
    assert "TAS_WRITE_BULK_DROPPED" in codes(one_surface(mesh), tmp_path / "bulk.stp")


def test_a_thickness_and_a_bulk_together_are_both_written(tmp_path: Path) -> None:
    mesh = ThermalMesh()
    mesh.side1_thick = 0.002
    mesh.side1_material = BulkMaterial("Alu", 2700.0, 160.0, 900.0)
    target = tmp_path / "pair.stp"
    assert not {"TAS_WRITE_BULK_DROPPED", "TAS_WRITE_THICKNESS_DROPPED"} & codes(
        one_surface(mesh), target
    )
    back = GeometryModel("back")
    back.io.read_steptas(target, on_diagnostic=quiet)
    plate = items(back)["PLATE"].thermal_mesh
    assert plate.side1_thick == pytest.approx(0.002)
    assert plate.side1_material.name == "Alu"
    assert plate.side1_material.density == pytest.approx(2700.0)
    assert plate.side1_material.conductivity == pytest.approx(160.0)
    assert plate.side1_material.specific_heat == pytest.approx(900.0)


def test_one_name_carries_an_optical_and_a_bulk_at_once(tmp_path: Path) -> None:
    """The format keeps both under one material; a model keeps two objects."""
    mesh = ThermalMesh()
    mesh.radiative_active_side = ActiveSide.SIDE1
    mesh.side1_optical = OpticalMaterial("Skin", [0.9, 0.0, 0.0, 0.3, 0.0, 0.0])
    mesh.side1_thick = 0.001
    mesh.side1_material = BulkMaterial("Skin", 1000.0, 5.0, 800.0)
    target = tmp_path / "one_material.stp"
    one_surface(mesh).io.write_steptas(target, on_diagnostic=quiet)
    parsed = read_part21(target)
    assert [entity.params[0] for entity in parsed.of_kind("NRF_MATERIAL")] == ["Skin"]
    back = GeometryModel("back")
    back.io.read_steptas(target, on_diagnostic=quiet)
    plate = items(back)["PLATE"].thermal_mesh
    assert plate.side1_optical.name == "Skin"
    assert plate.side1_material.density == pytest.approx(1000.0)


def test_a_cube_used_as_geometry_has_no_surface_to_be_written_as(tmp_path: Path) -> None:
    """It is a solid, and the format's solids exist only to cut with."""
    model = GeometryModel("BOXY")
    model.add(GeometryItem("BOX", Cube([0, 0, 0], [1, 1, 1]), ThermalMesh()))
    assert "TAS_WRITE_UNSUPPORTED_PRIMITIVE" in codes(model, tmp_path / "cube.stp")


def test_a_cutting_tool_says_what_it_leaves_behind(tmp_path: Path) -> None:
    mesh = ThermalMesh()
    mesh.node1_start = 100
    target = GeometryItem("PLATE", Rectangle([0, 0, 0], [1, 0, 0], [0, 1, 0]), ThermalMesh())
    tool = GeometryItem("TOOL", Cube([0, 0, 0], [0.5, 0.5, 0.5]), mesh)
    model = GeometryModel("CUT")
    model.add(GeometryGroupCutted("HOLED", [target], [tool]))
    assert "TAS_WRITE_CUTTER_ATTRIBUTES" in codes(model, tmp_path / "tool.stp")


def test_a_name_the_writer_needs_and_cannot_have_is_suffixed(tmp_path: Path) -> None:
    """An identifier has to be unique in a written model.

    Several top-level items are collected under one named after the model, and
    nothing stops an item from having that name already.
    """
    model = GeometryModel("TWINS")
    for name in ("TWINS", "OTHER"):
        model.add(GeometryItem(name, Rectangle([0, 0, 0], [1, 0, 0], [0, 1, 0]), ThermalMesh()))
    target = tmp_path / "twins.stp"
    assert "TAS_WRITE_RENAMED" in codes(model, target)
    parsed = read_part21(target)
    root = parsed.entity(parsed.of_kind("MGM_MESHED_GEOMETRIC_MODEL")[0].params[19])
    assert root is not None
    assert root.params[0] == "TWINS_2"


def test_a_model_with_no_geometry_says_so(tmp_path: Path) -> None:
    assert "TAS_WRITE_EMPTY_MODEL" in codes(GeometryModel("NOTHING"), tmp_path / "empty.stp")


def test_several_top_level_items_are_collected_under_one_root(tmp_path: Path) -> None:
    """The format names exactly one root item and a model may hold several."""
    model = GeometryModel("MANY")
    for index in range(3):
        model.add(
            GeometryItem(f"PLATE{index}", Rectangle([0, 0, 0], [1, 0, 0], [0, 1, 0]), ThermalMesh())
        )
    target = tmp_path / "many.stp"
    model.io.write_steptas(target, on_diagnostic=quiet)
    parsed = read_part21(target)
    root = parsed.entity(parsed.of_kind("MGM_MESHED_GEOMETRIC_MODEL")[0].params[19])
    assert root is not None
    assert root.kind == "MGM_COMPOUND_MESHED_GEOMETRIC_ITEM"
    assert len(listed(root.params[6])) == 3


def test_a_colour_becomes_the_nearest_one_the_protocol_names(tmp_path: Path) -> None:
    """The dictionary carries a fixed table; a mesh carries any colour at all."""
    mesh = ThermalMesh()
    mesh.side1_color = Color(254, 1, 2)
    target = tmp_path / "colour.stp"
    one_surface(mesh).io.write_steptas(target, on_diagnostic=quiet)
    back = GeometryModel("back")
    back.io.read_steptas(target, on_diagnostic=quiet)
    assert tuple(items(back)["PLATE"].thermal_mesh.side1_color.rgb) == (255, 0, 0)


def test_a_group_of_groups_keeps_its_shape(tmp_path: Path) -> None:
    model = GeometryModel("NESTED")
    disc = Disc([0, 0, 0], [0, 0, 1], [1, 0, 0], 0.0, 1.0, 0.0, 2.0 * math.pi)
    leaf = GeometryItem("PLATE", disc, ThermalMesh())
    model.add(GeometryGroup("OUTER", [GeometryGroup("INNER", [leaf])]))
    target = tmp_path / "nested.stp"
    model.io.write_steptas(target, on_diagnostic=quiet)
    back = GeometryModel("back")
    back.io.read_steptas(target, on_diagnostic=quiet)
    names = [child.name for child in back.children_recursive()]
    assert names[:3] == ["OUTER", "INNER", "PLATE"]
