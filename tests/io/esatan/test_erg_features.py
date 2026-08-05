"""The two feature-exercise models, read end to end.

The per-construct tests elsewhere each isolate one thing. These read whole
models instead, which is the only way to catch the failures that need several
constructs at once: a name defined early and overridden late, a primitive that
another statement later re-reads as a cutting tool, or a construct that is
skipped and then referred to.

The second model is the first one minus the constructs that have no pycanha
equivalent, so the pair also pins the boundary itself: reading them must differ
by exactly those refusals and nothing else.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from pycanha.gmm import (
    ActiveSide,
    GeometryGroup,
    GeometryGroupCutted,
    GeometryItem,
    GeometryModel,
)

FEATURES = Path(__file__).resolve().parents[2] / "data" / "esatan" / "FEATURES"
FULL = FEATURES / "FEATURES_ERG.erg"
CONVERTIBLE = FEATURES / "FEATURES_TAS.erg"

#: Every code the full model must report, and why each one is unavoidable.
#:
#: A construct that stops being reported has either been implemented -- in which
#: case its entry belongs in the supported tests instead -- or has started being
#: dropped in silence, which is the failure this list exists to catch.
EXPECTED_CODES = {
    "ERG_BOX_CUTTER",
    "ERG_BOX_DECOMPOSED",
    "ERG_CUTTER_SENSE",
    "ERG_DROPPED_CRITICALITY",
    "ERG_DROPPED_LABEL",
    "ERG_DROPPED_SUBMODEL",
    "ERG_FACE_EDIT",
    "ERG_FINITE_ELEMENT",
    "ERG_KINEMATIC_ASSEMBLY",
    "ERG_NO_NODE_NUMBERS",
    "ERG_ORTHOTROPIC_BULK",
    "ERG_PER_DIRECTION_NDELTA",
    "ERG_PRISM_DECOMPOSED",
    "ERG_PROPERTY_ENVIRONMENT",
    "ERG_REBOUND_VARIABLE",
    "ERG_SKIPPED_OPERAND",
    "ERG_UNSUPPORTED_CONSTRUCT",
    "ERG_UNSUPPORTED_PRIMITIVE",
}

#: The codes the convertible model must *not* report, being the ones its six
#: removed constructs are solely responsible for.
ONLY_IN_FULL = {
    "ERG_CUTTER_SENSE",
    "ERG_FACE_EDIT",
    "ERG_SKIPPED_OPERAND",
    "ERG_UNSUPPORTED_CONSTRUCT",
    "ERG_UNSUPPORTED_PRIMITIVE",
}


def read(path: Path) -> tuple[GeometryModel, object]:
    model = GeometryModel(path.stem)
    return model, model.io.read_esatan_erg(path, on_diagnostic=lambda _note: None)


@pytest.fixture(scope="module")
def full() -> tuple[GeometryModel, object]:
    return read(FULL)


@pytest.fixture(scope="module")
def convertible() -> tuple[GeometryModel, object]:
    return read(CONVERTIBLE)


# -- what gets built -------------------------------------------------------


def test_every_supported_primitive_is_built(convertible: tuple) -> None:
    """Seven shell-coordinate primitives and ten by-points ones, all present."""
    model, _ = convertible
    for name in ("SCS_DISC", "SCS_CYL", "SCS_CONE", "SCS_SPHERE", "SCS_RECT", "SCS_PARA"):
        assert isinstance(model.get_item(name), GeometryItem), name
    for name in ("PT_TRIANGLE", "PT_RECT", "PT_QUAD", "PT_DISC", "PT_CYL", "PT_CONE"):
        assert isinstance(model.get_item(name), GeometryItem), name
    for name in ("PT_SPHERE", "PT_PARA"):
        assert isinstance(model.get_item(name), GeometryItem), name
    # The two that have no single-primitive reading become groups of faces.
    assert isinstance(model.get_group("SCS_BOX"), GeometryGroup)
    assert isinstance(model.get_group("PT_PRISM"), GeometryGroup)
    assert isinstance(model.get_group("PT_BOX"), GeometryGroup)


def test_primitive_geometry_is_numerically_right(convertible: tuple) -> None:
    """Areas, not merely types: a wrong parametrisation still builds a shape."""
    model, _ = convertible

    # A 270-degree annulus between r = 0.02 and r = 0.1.
    annulus = model.get_item("SCS_DISC").primitive.surface_area()
    assert annulus == pytest.approx(0.75 * math.pi * (0.1**2 - 0.02**2))

    # A full cylinder of radius 0.1 and height 0.3.
    assert model.get_item("SCS_CYL").primitive.surface_area() == pytest.approx(
        2 * math.pi * 0.1 * 0.3
    )

    # Latitudes +/-60 truncate the sphere at +/-r sin(60); the remaining band
    # has area 2 pi r h, with h the axial extent.  Mapping latitude straight to
    # a truncation height instead would give a plausible but wrong number.
    band = model.get_item("SCS_SPHERE").primitive.surface_area()
    assert band == pytest.approx(2 * math.pi * 0.1 * (2 * 0.1 * math.sin(math.radians(60))))

    # By points: a right triangle with legs 0.3 and 0.4.
    assert model.get_item("PT_TRIANGLE").primitive.surface_area() == pytest.approx(0.5 * 0.3 * 0.4)
    assert model.get_item("PT_RECT").primitive.surface_area() == pytest.approx(0.3 * 0.4)


def test_a_box_becomes_six_faces_and_a_prism_three(convertible: tuple) -> None:
    model, _ = convertible

    box = model.get_group("PT_BOX")
    assert [child.name for child in box.children] == [f"PT_BOX_face{n}" for n in range(1, 7)]
    total = sum(child.primitive.surface_area() for child in box.children)
    assert total == pytest.approx(2 * ((0.3 * 0.4) + (0.3 * 0.2) + (0.4 * 0.2)))

    prism = model.get_group("PT_PRISM")
    assert len(list(prism.children)) == 3
    walls = sorted(child.primitive.surface_area() for child in prism.children)
    # The three base edges are 0.3, 0.4 and 0.5, each extruded 0.2.  A fourth
    # and fifth wall would mean the triangular ends had been invented.
    assert walls == pytest.approx([0.3 * 0.2, 0.4 * 0.2, 0.5 * 0.2])


def test_the_box_used_as_a_cutter_stays_a_solid(convertible: tuple) -> None:
    """The same primitive has two readings, and only the cut statement picks."""
    model, _ = convertible
    assembly = model.get_group("KINEMATIC_ASM")
    cut = next(child for child in assembly.children if isinstance(child, GeometryGroupCutted))
    assert cut.name == "DRILLED"
    # A cylinder and a box, the second of which is six flat faces everywhere
    # else in this model and a single closed solid only here.
    assert [cutter.name for cutter in cut.cutters] == ["CYL_CUTTER", "BOX_CUTTER"]


# -- attributes ------------------------------------------------------------


def test_every_per_side_attribute_lands_on_the_right_side(convertible: tuple) -> None:
    model, _ = convertible
    mesh = model.get_item("ATTRS").thermal_mesh

    assert mesh.radiative_active_side is ActiveSide.SIDE1
    assert mesh.conductive_active_side is ActiveSide.SIDE1
    assert mesh.side1_optical is not None
    assert mesh.side1_optical.name == "Black"
    assert mesh.side2_optical is not None
    assert mesh.side2_optical.name == "Mirror"

    # composition = "DUAL" keeps the two thicknesses apart; a SINGLE reading
    # would halve one number onto both sides.
    assert (mesh.side1_thick, mesh.side2_thick) == pytest.approx((0.001, 0.003))
    assert mesh.side1_material is not None
    assert mesh.side1_material.name == "Alu"
    assert mesh.side2_material is not None
    assert mesh.side2_material.name == "Steel"

    assert (mesh.node1_start, mesh.node1_step) == (3000, 1)
    assert (mesh.node2_start, mesh.node2_step) == (4000, 2)


def test_a_single_thickness_is_split_between_two_active_sides(convertible: tuple) -> None:
    mesh = convertible[0].get_item("SCS_CYL").thermal_mesh
    assert (mesh.side1_thick, mesh.side2_thick) == pytest.approx((0.001, 0.001))


def test_both_mesh_forms_produce_the_cuts_they_describe(convertible: tuple) -> None:
    mesh = convertible[0].get_item("SCS_RECT").thermal_mesh
    # Three faces with each one twice the last: 1 : 2 : 4 of a total 7.
    assert list(mesh.dir1_mesh) == pytest.approx([0.0, 1 / 7, 3 / 7, 1.0])
    # meshPositions are the interior cuts, given directly.
    assert list(mesh.dir2_mesh) == pytest.approx([0.0, 0.25, 0.5, 0.75, 1.0])


def test_faces_are_numbered_with_direction_one_fastest(convertible: tuple) -> None:
    """`node = nbase + (i1 + i2 * n1) * ndelta`, the order the format uses."""
    mesh = convertible[0].get_item("ATTRS").thermal_mesh
    n1 = len(mesh.dir1_mesh) - 1
    for i2 in range(len(mesh.dir2_mesh) - 1):
        for i1 in range(n1):
            assert mesh.node_of(i1, i2, 1) == 3000 + (i1 + i2 * n1)


def test_the_three_override_forms_all_take_effect(convertible: tuple) -> None:
    model, _ = convertible

    # DEFINE_GEOMETRY_ATTRIBUTES, applied to a single combination.
    solo = model.get_group("SOLO")
    item = next(iter(solo.children)) if isinstance(solo, GeometryGroup) else solo
    assert item.thermal_mesh.node1_start == 8000

    # SET_ATTRIBUTE_RECURSIVE reaches every descendant of a combination.
    mesh = model.get_item("PT_DISC").thermal_mesh
    assert (mesh.side1_thick, mesh.side2_thick) == pytest.approx((0.00075, 0.00075))

    # A dotted assignment names one surface of one primitive.
    assert model.get_item("AUTO_NUM").thermal_mesh.node1_start == 9000


def test_a_rotation_composes_with_the_placement_it_finds(convertible: tuple) -> None:
    """`clear = TRUE` discards the accumulated placement; without it they compose."""
    model, _ = convertible

    # MOVED rotates and then translates, so the translation survives intact.
    assert model.get_item("MOVED").transform.translation == pytest.approx(
        [5.0, 1.0, 0.0], abs=1e-12
    )

    # CLEARED rotates, translates, then rotates again with `clear`.  What is
    # left is that last rotation alone: the translation is gone, not merely
    # rotated, and the placement is not identity either.
    cleared = model.get_item("CLEARED").transform
    assert cleared.translation == pytest.approx([0.0, 0.0, 0.0], abs=1e-12)
    assert not cleared.is_identity()
    turn = math.radians(20.0)
    assert np.asarray(cleared.rotation) == pytest.approx(
        np.array(
            [
                [math.cos(turn), 0.0, math.sin(turn)],
                [0.0, 1.0, 0.0],
                [-math.sin(turn), 0.0, math.cos(turn)],
            ]
        ),
        abs=1e-12,
    )


# -- what is refused, and how ----------------------------------------------


def test_the_full_model_reports_every_construct_it_cannot_represent(full: tuple) -> None:
    _, diagnostics = full
    assert diagnostics.codes() >= EXPECTED_CODES


def test_nothing_unrecognised_is_ignored_in_silence(full: tuple) -> None:
    """A statement with no mapping must be named, not merely skipped."""
    _, diagnostics = full
    assert "ERG_UNHANDLED_STATEMENT" not in diagnostics.codes()


def test_a_removed_face_is_an_error_because_the_area_is_wrong(full: tuple) -> None:
    """Skipping REMOVE_FACE leaves more surface than the source model has."""
    _, diagnostics = full
    edits = [note for note in diagnostics if note.code == "ERG_FACE_EDIT"]
    assert len(edits) == 1
    assert edits[0].severity.value == "error"
    assert isinstance(full[0].get_item("HOLED"), GeometryItem)


def test_a_skipped_name_is_not_reported_twice_when_it_is_referred_to(full: tuple) -> None:
    """The reason is already recorded; a second error would double-count it."""
    _, diagnostics = full
    skipped = {note.code for note in diagnostics if "TORUS" in note.message}
    assert skipped == {"ERG_UNSUPPORTED_PRIMITIVE", "ERG_SKIPPED_OPERAND"}
    assert "ERG_UNKNOWN_GEOMETRY" not in diagnostics.codes()


def test_the_convertible_model_is_the_full_one_minus_exactly_those_refusals(
    full: tuple, convertible: tuple
) -> None:
    """The pair defines the boundary, so the difference must be only the six."""
    assert full[1].codes() - convertible[1].codes() == ONLY_IN_FULL
    assert not convertible[1].codes() - full[1].codes()


def test_the_convertible_model_drops_no_geometry_at_all(convertible: tuple) -> None:
    """Its remaining diagnostics leave every surface built, if not every meaning."""
    _, diagnostics = convertible
    serious = [note.code for note in diagnostics if note.severity.value in ("error", "unsupported")]
    # Neither of these removes a surface: the assembly keeps its initial pose
    # and loses only the motion, and the finite-element primitive is built as a
    # lumped-parameter one of the same shape.
    assert sorted(serious) == ["ERG_FINITE_ELEMENT", "ERG_KINEMATIC_ASSEMBLY"]


def test_a_variable_rebound_after_use_does_not_change_what_was_built(
    convertible: tuple,
) -> None:
    """Values freeze where they are read, and the redefinition is reported."""
    model, diagnostics = convertible
    assert "ERG_REBOUND_VARIABLE" in diagnostics.codes()
    # Both cones take `semi_ang = SEMI`, the first at 30 degrees and the second
    # after the rebinding to 45.  Equal areas would mean one of them had picked
    # up the other's value.
    early = model.get_item("SCS_CONE").primitive.surface_area()
    late = model.get_item("LATE_CONE").primitive.surface_area()
    assert early != pytest.approx(late)


def test_the_one_sided_activities_survive_whole(convertible: tuple) -> None:
    """ "Radiative" and "Conductive" each land on their own selector.

    A mesh carries one activity per calculation, so the surface that radiates
    without conducting and the one that conducts without radiating are both
    stated exactly -- and neither costs a diagnostic.
    """
    model, diagnostics = convertible
    mesh = model.get_item("DROPPED_ATTRS").thermal_mesh
    assert mesh.radiative_active_side is ActiveSide.SIDE1
    assert mesh.conductive_active_side is ActiveSide.SIDE2
    assert "ERG_ACTIVITY_REDUCED" not in diagnostics.codes()
