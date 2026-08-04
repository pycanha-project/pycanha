"""Reading a STEP-TAS file into a geometry model.

The fixture is a converted feature model, so one file exercises every shape,
both kinds of mesh spacing, the placements, a cut and the material table.  The
assertions are numeric and written out by hand: a shape read with the wrong
parametrisation is still a shape, and only its measurements give it away.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pycanha_core as pcc
import pytest

from pycanha.gmm import GeometryGroup, GeometryGroupCutted, GeometryItem, GeometryModel
from pycanha.io.steptas import StepTasError

FEATURES = Path(__file__).resolve().parents[2] / "data" / "esatan" / "FEATURES"
CONVERTED = FEATURES / "FEATURES_TAS.stp"

#: Every code the fixture must report, and why each one is unavoidable.
#:
#: A code that stops being reported has either been implemented -- in which case
#: its entry belongs in the supported tests instead -- or has started being
#: dropped in silence, which is the failure this list exists to catch.
EXPECTED_CODES = {
    # The file defines its materials for three environments and a mesh holds one.
    "TAS_PROPERTY_ENVIRONMENT",
    # Three surfaces number their faces per direction, which a single increment
    # cannot reproduce.
    "TAS_NODE_ORDER_IRREGULAR",
    # One surface is inactive on its second side, so that side has no nodes.
    "TAS_SIDE_NOT_NUMBERED",
    # One surface carries a name for its first side, which a mesh cannot hold.
    "TAS_LABEL_DROPPED",
}


@pytest.fixture(scope="module")
def converted() -> tuple[GeometryModel, object]:
    model = GeometryModel("FEATURES_TAS")
    return model, model.io.read_steptas(CONVERTED, on_diagnostic=lambda _note: None)


def item(model: GeometryModel, name: str) -> GeometryItem:
    found = model.get_item(name)
    assert isinstance(found, GeometryItem), name
    return found


def shape[T](model: GeometryModel, name: str, kind: type[T]) -> T:
    """The named item's primitive as *kind*.

    ``GeometryItem.primitive`` is a union of every shape, so reaching for a
    radius or a defining point needs the shape pinned down first -- and which
    shape the file was read as is half of what these tests assert.  The core
    classes are the ones to name here: a reader builds its shapes in the core,
    and ``pycanha.gmm`` only wraps their constructors.
    """
    primitive = item(model, name).primitive
    assert isinstance(primitive, kind), f"{name}: expected a {kind.__name__}"
    return primitive


# -- what gets built --------------------------------------------------------


def test_the_whole_hierarchy_is_rebuilt(converted: tuple) -> None:
    """Groups inside groups, and the cut at the bottom of one of them."""
    model, _ = converted
    assert isinstance(model.get_group("FEATURES_TAS"), GeometryGroup)
    assert isinstance(model.get_group("STATIC_ASM"), GeometryGroup)
    assert isinstance(model.get_group("SCS_SHAPES"), GeometryGroup)
    assert isinstance(model.get_cut_group("DRILLED"), GeometryGroupCutted)


def test_every_shape_type_is_built(converted: tuple) -> None:
    model, _ = converted
    for name in ("SCS_DISC", "SCS_CYL", "SCS_CONE", "SCS_SPHERE", "SCS_RECT", "SCS_PARA"):
        assert isinstance(model.get_item(name), GeometryItem), name
    for name in ("PT_RECT", "PT_QUAD", "PT_DISC", "PT_CYL", "PT_CONE", "PT_SPHERE", "PT_PARA"):
        assert isinstance(model.get_item(name), GeometryItem), name
    assert isinstance(model.get_item("PT_TRIANGLE"), GeometryItem)
    # A box and a prism arrive already split into their flat faces.
    assert isinstance(model.get_group("SCS_BOX"), GeometryGroup)
    assert isinstance(model.get_group("PT_BOX"), GeometryGroup)
    assert isinstance(model.get_group("PT_PRISM"), GeometryGroup)


def test_only_the_expected_losses_are_reported(converted: tuple) -> None:
    _, diagnostics = converted
    assert diagnostics.codes() == EXPECTED_CODES


# -- shapes, numerically ----------------------------------------------------


def test_a_disc_keeps_its_radii_and_its_sector(converted: tuple) -> None:
    """A washer three quarters of the way round, lifted along its axis."""
    model, _ = converted
    disc = shape(model, "SCS_DISC", pcc.gmm.Disc)
    assert disc.surface_area() == pytest.approx(0.75 * math.pi * (0.1**2 - 0.02**2))
    assert list(disc.p1) == pytest.approx([0.0, 0.0, 0.05])


def test_a_cylinder_takes_its_height_from_its_axis(converted: tuple) -> None:
    model, _ = converted
    cylinder = shape(model, "SCS_CYL", pcc.gmm.Cylinder)
    assert cylinder.surface_area() == pytest.approx(2 * math.pi * 0.1 * 0.3)


def test_a_cone_is_given_as_a_frustum(converted: tuple) -> None:
    """Two end radii and the two centres, rather than a half-angle."""
    model, _ = converted
    cone = shape(model, "LATE_CONE", pcc.gmm.Cone)
    assert (cone.radius1, cone.radius2) == pytest.approx((0.05, 0.25))
    slant = math.hypot(0.2, 0.2)
    assert cone.surface_area() == pytest.approx(math.pi * (0.05 + 0.25) * slant)


def test_a_sphere_is_truncated_by_axial_height(converted: tuple) -> None:
    """The band between two latitudes, whose area is the hat-box theorem's."""
    model, _ = converted
    sphere = shape(model, "SCS_SPHERE", pcc.gmm.Sphere)
    height = 2 * 0.1 * math.sin(math.radians(60.0))
    assert sphere.surface_area() == pytest.approx(2 * math.pi * 0.1 * height)


def test_a_paraboloid_keeps_its_rim_radius(converted: tuple) -> None:
    model, _ = converted
    paraboloid = shape(model, "SCS_PARA", pcc.gmm.Paraboloid)
    focal, height = 0.1, 0.2
    rim = 2.0 * math.sqrt(focal * height)
    assert list(paraboloid.p2) == pytest.approx([0.0, 0.0, height])
    # The area of z = r^2/(4f) out to the rim, in closed form.
    reach = (1.0 + rim**2 / (4.0 * focal**2)) ** 1.5 - 1.0
    assert paraboloid.surface_area() == pytest.approx(8.0 * math.pi * focal**2 * reach / 3.0)


def test_a_rectangle_keeps_its_two_edge_directions(converted: tuple) -> None:
    model, _ = converted
    rectangle = shape(model, "PT_RECT", pcc.gmm.Rectangle)
    assert list(rectangle.p1) == pytest.approx([1.0, 0.0, 0.5])
    assert rectangle.surface_area() == pytest.approx(0.3 * 0.4)


# -- mesh and node numbers --------------------------------------------------


def test_a_surface_of_revolution_has_its_mesh_directions_exchanged(converted: tuple) -> None:
    """The file counts the axial direction first; this model counts around.

    The disc is meshed four ways round and three deep.  Read without the
    exchange it would come out three by four -- a mesh of the right size on the
    wrong axes, which is only visible in a count like this one.
    """
    model, _ = converted
    mesh = item(model, "SCS_DISC").thermal_mesh
    assert len(mesh.dir1_mesh) - 1 == 4
    assert len(mesh.dir2_mesh) - 1 == 3


def test_a_planar_surface_keeps_the_order_it_was_written_in(converted: tuple) -> None:
    model, _ = converted
    mesh = item(model, "SCS_RECT").thermal_mesh
    assert len(mesh.dir1_mesh) - 1 == 3
    assert len(mesh.dir2_mesh) - 1 == 4


def test_uneven_mesh_spacing_is_carried_by_its_positions(converted: tuple) -> None:
    """One direction is a geometric progression, the other explicit cuts."""
    model, _ = converted
    mesh = item(model, "SCS_RECT").thermal_mesh
    assert list(mesh.dir1_mesh) == pytest.approx([0.0, 1 / 7, 3 / 7, 1.0])
    assert list(mesh.dir2_mesh) == pytest.approx([0.0, 0.25, 0.5, 0.75, 1.0])


def test_node_numbers_come_back_as_a_start_and_a_step(converted: tuple) -> None:
    model, _ = converted
    mesh = item(model, "SCS_DISC").thermal_mesh
    assert (mesh.node1_start, mesh.node1_step) == (1000, 1)
    assert (mesh.node2_start, mesh.node2_step) == (1000, 1)


def test_a_surface_numbered_per_direction_is_reported_not_guessed(converted: tuple) -> None:
    """Two increments cannot become one, so the surface says so.

    ``SPLIT_DELTA`` advances by one along its first direction and by ten along
    its second.  A single step cannot reproduce that, and quietly keeping the
    first would leave most of its faces holding another face's number.
    """
    _, diagnostics = converted
    reported = [note for note in diagnostics if note.code == "TAS_NODE_ORDER_IRREGULAR"]
    assert any("SPLIT_DELTA" in note.message for note in reported)


# -- attributes -------------------------------------------------------------


def test_activity_comes_from_the_active_side(converted: tuple) -> None:
    model, _ = converted
    both = item(model, "SCS_DISC").thermal_mesh
    assert (both.side1_activity, both.side2_activity) == (True, True)
    one = item(model, "ATTRS").thermal_mesh
    assert (one.side1_activity, one.side2_activity) == (True, False)


def test_optical_properties_are_rebuilt_from_the_material_table(converted: tuple) -> None:
    """Specularity is a fraction of what is reflected, not the reflectivity.

    The mirror absorbs 0.12 of the solar band and reflects the rest, of which
    the file says 0.9659 is specular.  Multiplying the two gives back the 0.85
    the model was built with; taking the fraction for the value itself would
    leave the surface far too specular.
    """
    model, _ = converted
    optical = item(model, "SCS_CYL").thermal_mesh.side2_optical
    assert optical.name == "Mirror"
    ir_emiss, ir_spec, ir_transm, solar_absorb, solar_spec, solar_transm = (
        optical.th_optical_properties
    )
    assert (ir_emiss, ir_transm) == pytest.approx((0.05, 0.0))
    assert (solar_absorb, solar_transm) == pytest.approx((0.12, 0.0))
    assert (ir_spec, solar_spec) == pytest.approx((0.90, 0.85))


def test_bulk_properties_keep_the_argument_order_straight(converted: tuple) -> None:
    """Density, specific heat and conductivity, two of which are transposed."""
    model, _ = converted
    bulk = item(model, "SCS_CYL").thermal_mesh.side1_material
    assert bulk.name == "Alu"
    assert bulk.density == pytest.approx(2700.0)
    assert bulk.specific_heat == pytest.approx(900.0)
    assert bulk.conductivity == pytest.approx(160.0)


def test_thickness_is_kept_per_side(converted: tuple) -> None:
    """The source shares one thickness between the two active sides."""
    model, _ = converted
    mesh = item(model, "SCS_CYL").thermal_mesh
    assert mesh.side1_thick == pytest.approx(0.001)
    assert mesh.side2_thick == pytest.approx(0.001)


def test_colours_arrive_as_values_rather_than_names(converted: tuple) -> None:
    model, _ = converted
    mesh = item(model, "ATTRS").thermal_mesh
    assert tuple(mesh.side1_color.rgb) == (255, 0, 0)
    assert tuple(mesh.side2_color.rgb) == (0, 0, 255)


# -- placement --------------------------------------------------------------


def test_a_placement_sequence_is_composed_in_the_order_it_is_written(converted: tuple) -> None:
    """Three fixed-axis rotations and two translations, in file order.

    Composing them the other way round also lands the surface somewhere
    plausible, which is why the corner is checked and not merely the area.
    """
    model, _ = converted
    moved = item(model, "MOVED")
    corner = moved.transform.apply(np.zeros(3))
    assert list(corner) == pytest.approx([5.0, 1.0, 0.0])
    edge = moved.transform.apply(np.array([0.1, 0.0, 0.0])) - corner
    angles = [math.radians(value) for value in (15.0, 30.0, 45.0)]
    cx, cy, cz = (math.cos(angle) for angle in angles)
    sx, sy, sz = (math.sin(angle) for angle in angles)
    rotation = (
        np.array([[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]])
        @ np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]])
        @ np.array([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]])
    )
    assert list(edge) == pytest.approx(list(rotation @ np.array([0.1, 0.0, 0.0])))


def test_an_axis_placement_becomes_the_frame_it_names(converted: tuple) -> None:
    """A group is placed by its own axes: local X onto global Y, and a shift."""
    model, _ = converted
    placed = model.get_group("PT_SHAPES")
    assert list(placed.transform.apply(np.zeros(3))) == pytest.approx([0.0, 3.0, 0.0])
    moved = placed.transform.apply(np.array([1.0, 0.0, 0.0]))
    assert list(moved) == pytest.approx([0.0, 4.0, 0.0])


# -- cutting ----------------------------------------------------------------


def test_a_difference_surface_becomes_a_cut_group(converted: tuple) -> None:
    """Two successive cuts arrive as one difference nested inside another."""
    model, _ = converted
    outer = model.get_cut_group("DRILLED")
    assert isinstance(outer, GeometryGroupCutted)
    inner = model.get_cut_group("DRILLED_1")
    assert isinstance(inner, GeometryGroupCutted)
    assert isinstance(model.get_item("CYL_CUTTER"), GeometryItem)
    assert isinstance(model.get_item("BOX_CUTTER"), GeometryItem)


def test_a_box_used_as_a_cutter_is_read_as_a_closed_solid(converted: tuple) -> None:
    """A cutting tool has to bound a volume, so the box arrives as a cube."""
    model, _ = converted
    cutter = item(model, "BOX_CUTTER")
    assert cutter.primitive.surface_area() == pytest.approx(2 * (0.2 * 0.2 + 2 * 0.2 * 2.1))
    centre = cutter.transform.apply(np.zeros(3))
    assert list(centre) == pytest.approx([0.25, 0.25, 1.05])


# -- refusals ---------------------------------------------------------------


def test_a_file_without_geometry_is_refused(tmp_path: Path) -> None:
    """A part-21 file that describes something else is not a model to read."""
    path = tmp_path / "empty.stp"
    path.write_text(
        "ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\n#1=NRF_PERSON('x','y','z',$,$,$);\n"
        "ENDSEC;\nEND-ISO-10303-21;\n",
        encoding="utf-8",
    )
    model = GeometryModel("empty")
    with pytest.raises(StepTasError):
        model.io.read_steptas(path)


def test_strict_reading_stops_at_the_first_serious_loss() -> None:
    model = GeometryModel("strict")
    with pytest.raises(StepTasError):
        model.io.read_steptas(CONVERTED, strict=True, on_diagnostic=lambda _note: None)
