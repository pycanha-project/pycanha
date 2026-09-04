"""The language corpus, read end to end, and the constructs it may not carry.

The per-construct tests elsewhere each isolate one thing. The first half of this
module reads the whole corpus instead, which is the only way to catch the
failures that need several constructs at once: a name defined early and
overridden late, or a primitive that another statement later re-reads as a
cutting tool.

The second half covers the six constructs the reader **refuses**. Those cannot
live in the corpus: each one changes the geometry around it -- a refused cutter
leaves its target uncut, a refused primitive leaves the combination that names
it short an operand -- so a corpus carrying them would be a different model from
one that does not. Each is written here instead, as the smallest model that
provokes it, and each asserts the same two things: the diagnostic is raised, and
the geometry the construct describes is not silently invented.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pycanha_core as pcc
import pytest

from pycanha.gmm import (
    ActiveSide,
    GeometryGroup,
    GeometryGroupCutted,
    GeometryItem,
    GeometryModel,
)

if TYPE_CHECKING:
    from pycanha.io.diagnostics import DiagnosticCollector

CORPUS = Path(__file__).resolve().parents[2] / "data" / "esatan" / "FEATURES.erg"

#: Every code the corpus must report, and why each one is unavoidable.
#:
#: A construct that stops being reported has either been implemented -- in which
#: case its entry belongs in the supported tests instead -- or has started being
#: dropped in silence, which is the failure this list exists to catch.
EXPECTED_CODES = {
    "ERG_BOX_CUTTER",
    "ERG_BOX_DECOMPOSED",
    "ERG_DROPPED_CRITICALITY",
    "ERG_DROPPED_LABEL",
    "ERG_DROPPED_SUBMODEL",
    "ERG_FINITE_ELEMENT",
    "ERG_KINEMATIC_ASSEMBLY",
    "ERG_NO_NODE_NUMBERS",
    "ERG_ORTHOTROPIC_BULK",
    "ERG_PER_DIRECTION_NDELTA",
    "ERG_PRISM_DECOMPOSED",
    "ERG_PROPERTY_ENVIRONMENT",
    "ERG_REBOUND_VARIABLE",
}


def read(path: Path) -> tuple[GeometryModel, DiagnosticCollector]:
    model = GeometryModel(path.stem)
    return model, model.io.read_esatan_erg(path, on_diagnostic=lambda _note: None)


@pytest.fixture(scope="module")
def corpus() -> tuple[GeometryModel, DiagnosticCollector]:
    return read(CORPUS)


# -- what gets built -------------------------------------------------------


def test_every_supported_primitive_is_built(corpus: tuple) -> None:
    """Nine shell-coordinate primitives and ten by-points ones, all present."""
    model, _ = corpus
    for name in ("SCS_DISC", "SCS_CYL", "SCS_CONE", "SCS_SPHERE", "SCS_RECT", "SCS_PARA"):
        assert isinstance(model.get_item(name), GeometryItem), name
    assert isinstance(model.get_item("SCS_TRAP"), GeometryItem)
    for name in ("PT_TRIANGLE", "PT_RECT", "PT_QUAD", "PT_DISC", "PT_CYL", "PT_CONE"):
        assert isinstance(model.get_item(name), GeometryItem), name
    for name in ("PT_SPHERE", "PT_PARA"):
        assert isinstance(model.get_item(name), GeometryItem), name
    # The four that have no single-primitive reading become groups of faces.
    assert isinstance(model.get_group("SCS_BOX"), GeometryGroup)
    assert isinstance(model.get_group("SCS_PRISM"), GeometryGroup)
    assert isinstance(model.get_group("PT_PRISM"), GeometryGroup)
    assert isinstance(model.get_group("PT_BOX"), GeometryGroup)


def test_primitive_geometry_is_numerically_right(corpus: tuple) -> None:
    """Areas, not merely types: a wrong parametrisation still builds a shape.

    Every area below is the closed form for the shape the file describes,
    written out here rather than taken from ``surface_area()`` on the other
    side of the comparison.  That distinction is the whole point: the
    quadrilateral was wrong for years because the mesher and the primitive
    agreed with each other.
    """
    model, _ = corpus

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

    # A paraboloid z = r^2 / (4f) up to height h has area
    # (8 pi f^2 / 3) * ((1 + h/f)^(3/2) - 1); here f = 0.1 and h = 0.2.
    assert model.get_item("SCS_PARA").primitive.surface_area() == pytest.approx(
        (8 * math.pi * 0.1**2 / 3) * ((1 + 0.2 / 0.1) ** 1.5 - 1)
    )

    # A trapezoid parallel to the XY-plane: its two edges parallel to X are
    # 2 * beta * cot(60) long at beta = 0.1 and at beta = 0.3, spanning 0.2.
    cot60 = 1.0 / math.tan(math.radians(60.0))
    assert model.get_item("SCS_TRAP").primitive.surface_area() == pytest.approx(
        (2 * 0.3 * cot60 + 2 * 0.1 * cot60) / 2 * (0.3 - 0.1)
    )

    # By points: a right triangle with legs 0.3 and 0.4.
    assert model.get_item("PT_TRIANGLE").primitive.surface_area() == pytest.approx(0.5 * 0.3 * 0.4)
    assert model.get_item("PT_RECT").primitive.surface_area() == pytest.approx(0.3 * 0.4)

    # A genuine trapezoid, and the one the reader used to get wrong: its
    # parallel sides are 0.30 and 0.35 across a span of 0.40, so the area is
    # 0.13.  Read as the rectangle spanned by two of its edges it comes to
    # 0.12, which is a plausible number and the wrong one.
    assert model.get_item("PT_QUAD").primitive.surface_area() == pytest.approx(
        (0.30 + 0.35) / 2 * 0.40
    )

    # A full cone: apex 0.4 above a base of radius 0.2, so pi * r * slant.
    assert model.get_item("PT_CONE").primitive.surface_area() == pytest.approx(
        math.pi * 0.2 * math.hypot(0.2, 0.4)
    )

    assert model.get_item("SCS_RECT").primitive.surface_area() == pytest.approx(0.2 * 0.3)

    # A half cone (angmax 180) of semi-angle 30, between heights 0.05 and 0.25
    # measured from the apex: pi * (r1 + r2) * slant, halved.  ``SEMI`` is 30
    # where this surface is read and 45 by the end of the file; the reader
    # evaluates where it reads, which is the divergence ERG_REBOUND_VARIABLE
    # reports.
    semi = math.radians(30.0)
    assert model.get_item("SCS_CONE").primitive.surface_area() == pytest.approx(
        0.5 * math.pi * (0.05 * math.tan(semi) + 0.25 * math.tan(semi)) * (0.20 / math.cos(semi))
    )

    assert model.get_item("PT_DISC").primitive.surface_area() == pytest.approx(math.pi * 0.2**2)
    assert model.get_item("PT_CYL").primitive.surface_area() == pytest.approx(
        2 * math.pi * 0.15 * 0.30
    )
    assert model.get_item("PT_SPHERE").primitive.surface_area() == pytest.approx(
        4 * math.pi * 0.2**2
    )
    # Same formula as SCS_PARA, but the focal length is implied by the rim:
    # R = 0.2 at h = 0.2 gives f = R^2 / (4h) = 0.05.
    assert model.get_item("PT_PARA").primitive.surface_area() == pytest.approx(
        (8 * math.pi * 0.05**2 / 3) * ((1 + 0.2 / 0.05) ** 1.5 - 1)
    )


#: The surfaces whose area the test above checks against a closed form.
#:
#: Kept beside the test so the guard below can compare what is asserted with
#: what the model actually holds.
NUMERICALLY_ASSERTED = (
    "SCS_DISC",
    "SCS_CYL",
    "SCS_CONE",
    "SCS_SPHERE",
    "SCS_RECT",
    "SCS_PARA",
    "SCS_TRAP",
    "PT_TRIANGLE",
    "PT_RECT",
    "PT_QUAD",
    "PT_DISC",
    "PT_CYL",
    "PT_CONE",
    "PT_SPHERE",
    "PT_PARA",
)

#: The primitives that exist only to cut with: never meshed, radiated or
#: conducted, so an area of theirs would mean nothing.  What they remove is
#: asserted where the cut is instead.
CUT_ONLY = (pcc.gmm.Cube, pcc.gmm.TriangularPrism)


def surface_constructors(source: Path, model: GeometryModel) -> dict[str, str]:
    """Each ESATAN constructor in *source* that built a surface, to one item.

    Read from the file text rather than from the reader's tables, so this stays
    a statement about the fixture and not about the code under test.
    """
    built = dict(re.findall(r"^(\w+)\s*=\s*(SHELL_\w+)\s*\(", source.read_text("utf-8"), re.M))
    found: dict[str, str] = {}
    for item in model.children_recursive():
        if not isinstance(item, GeometryItem) or isinstance(item.primitive, CUT_ONLY):
            continue
        constructor = built.get(item.name)
        if constructor is not None:
            found.setdefault(constructor, item.name)
    return found


def test_every_surface_constructor_has_a_closed_form_area(corpus: tuple) -> None:
    """No constructor may build a surface nobody checked the area of.

    This is the guard for the gap the quadrilateral came through.  ``PT_QUAD``
    was in this fixture from the start, was a real trapezoid, and was the one
    primitive the numeric test never asserted on -- everywhere else it appeared,
    the assertion was ``isinstance(..., GeometryItem)``.  Adding a constructor
    the reader can build now fails here until somebody writes down what its area
    ought to be.

    The unit is the **constructor**, not the shape class: ``SHELL_CONE`` and
    ``SHELL_SCS_CONE`` both make a ``Cone`` from entirely different parameters,
    and the SCS one was once wrong for every truncated cone while the by-points
    one was right.  Checking one ``Cone`` would have missed it.
    """
    model, _ = corpus
    built = surface_constructors(CORPUS, model)
    asserted = {constructor for constructor, name in built.items() if name in NUMERICALLY_ASSERTED}
    missing = sorted(set(built) - asserted)
    assert not missing, f"surface constructors with no closed-form area: {missing}"


def test_a_box_becomes_six_faces_and_a_prism_three(corpus: tuple) -> None:
    model, _ = corpus

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


def test_the_box_used_as_a_cutter_stays_a_solid(corpus: tuple) -> None:
    """The same primitive has two readings, and only the cut statement picks."""
    model, _ = corpus
    assembly = model.get_group("KINEMATIC_ASM")
    cut = next(child for child in assembly.children if isinstance(child, GeometryGroupCutted))
    assert cut.name == "DRILLED"
    # A cylinder and a box, the second of which is six flat faces everywhere
    # else in this model and a single closed solid only here.
    assert [cutter.name for cutter in cut.cutters] == ["CYL_CUTTER", "BOX_CUTTER"]


# -- attributes ------------------------------------------------------------


def test_every_per_side_attribute_lands_on_the_right_side(corpus: tuple) -> None:
    model, _ = corpus
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


def test_a_single_thickness_is_split_between_two_active_sides(corpus: tuple) -> None:
    mesh = corpus[0].get_item("SCS_CYL").thermal_mesh
    assert (mesh.side1_thick, mesh.side2_thick) == pytest.approx((0.001, 0.001))


def test_both_mesh_forms_produce_the_cuts_they_describe(corpus: tuple) -> None:
    mesh = corpus[0].get_item("SCS_RECT").thermal_mesh
    # Three faces with each one twice the last: 1 : 2 : 4 of a total 7.
    assert list(mesh.dir1_mesh) == pytest.approx([0.0, 1 / 7, 3 / 7, 1.0])
    # meshPositions are the interior cuts, given directly.
    assert list(mesh.dir2_mesh) == pytest.approx([0.0, 0.25, 0.5, 0.75, 1.0])


def test_faces_are_numbered_with_direction_one_fastest(corpus: tuple) -> None:
    """`node = nbase + (i1 + i2 * n1) * ndelta`, the order the format uses."""
    mesh = corpus[0].get_item("ATTRS").thermal_mesh
    n1 = len(mesh.dir1_mesh) - 1
    for i2 in range(len(mesh.dir2_mesh) - 1):
        for i1 in range(n1):
            assert mesh.node_of(i1, i2, 1) == 3000 + (i1 + i2 * n1)


def test_the_three_override_forms_all_take_effect(corpus: tuple) -> None:
    model, _ = corpus

    # DEFINE_GEOMETRY_ATTRIBUTES, applied to a single combination.
    solo = model.get_group("SOLO")
    item = next(iter(solo.children)) if isinstance(solo, GeometryGroup) else solo
    assert item.thermal_mesh.node1_start == 8000

    # SET_ATTRIBUTE_RECURSIVE reaches every descendant of a combination.
    mesh = model.get_item("PT_DISC").thermal_mesh
    assert (mesh.side1_thick, mesh.side2_thick) == pytest.approx((0.00075, 0.00075))

    # A dotted assignment names one surface of one primitive.
    assert model.get_item("AUTO_NUM").thermal_mesh.node1_start == 9000


def test_a_rotation_composes_with_the_placement_it_finds(corpus: tuple) -> None:
    """`clear = TRUE` discards the accumulated placement; without it they compose."""
    model, _ = corpus

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
#
# Each block below is one construct, spelled exactly as a model spells it.  The
# spelling is the thing under test: a reader that stopped recognising the
# construct at all would refuse it just as loudly and for the wrong reason.

#: Enough of a model for a refused construct to sit in: one optical property, one
#: bulk, and one ordinary surface for a combination to keep when the refused
#: operand is dropped out of it.
PREAMBLE = """CONST REAL FULL_TURN = 360.00000000;

OPTICAL Black;
Black = [0.90, 0.10, 0.00, 0.90, 0.10, 0.00, 0.00, 0.00];

BULK Steel;
Steel = [7900.00000000, 500.00000000, 15.00000000];

GEOMETRY KEEPER;
KEEPER = SHELL_SCS_RECTANGLE(
    xmax = 0.10000000,
    ymax = 0.10000000,
    nodes1 = 1,
    nodes2 = 1,
    nbase1 = 100,
    ndelta1 = 1,
    opt1 = Black,
    opt2 = Black);
"""

SCS_TORUS = """
GEOMETRY SCS_TORUS;
SCS_TORUS = SHELL_SCS_TORUS(
    major_radius = 0.30000000,
    minor_radius = 0.05000000,
    major_angmin = 0.00000000,
    major_angmax = FULL_TURN,
    minor_angmin = 0.00000000,
    minor_angmax = FULL_TURN,
    nodes1 = 4,
    nodes2 = 3,
    nbase1 = 10000,
    ndelta1 = 1,
    opt1 = Black,
    opt2 = Black);
"""

PT_TORUS = """
GEOMETRY PT_TORUS;
PT_TORUS = SHELL_TORUS(
    point1 = [6.00000000, 0.00000000, 0.00000000],
    point2 = [6.00000000, 0.00000000, 1.00000000],
    point3 = [6.30000000, 0.00000000, 0.00000000],
    point4 = [6.35000000, 0.00000000, 0.00000000],
    nbase1 = 10100,
    ndelta1 = 1,
    opt1 = Black,
    opt2 = Black);
"""

HALF_SPACE_CUT = """
GEOMETRY SLICED;
SLICED = SHELL_SCS_SPHERE(
    radius = 0.20000000,
    nodes1 = 4,
    nodes2 = 4,
    nbase1 = 10200,
    ndelta1 = 1,
    opt1 = Black,
    opt2 = Black);

GEOMETRY PLANE_CUTTER;
PLANE_CUTTER = SHELL_HALF_SPACE(
    height = 0.05000000,
    sense = -1);

GEOMETRY HALVED;
HALVED = SLICED - PLANE_CUTTER;
"""

#: A cut that keeps what the cutter encloses rather than removing it.
KEEPING_CUT = """
GEOMETRY KEPT_TARGET;
KEPT_TARGET = SHELL_SCS_RECTANGLE(
    xmin = -0.20000000,
    xmax = 0.20000000,
    ymin = -0.20000000,
    ymax = 0.20000000,
    height = 3.00000000,
    nodes1 = 4,
    nodes2 = 4,
    nbase1 = 10300,
    ndelta1 = 1,
    opt1 = Black,
    opt2 = Black);

GEOMETRY KEEP_CUTTER;
KEEP_CUTTER = SHELL_SCS_CYLINDER(
    radius = 0.10000000,
    hmin = 2.90000000,
    hmax = 3.10000000,
    sense = 1,
    nbase1 = 10400,
    ndelta1 = 1,
    opt1 = Black,
    opt2 = Black);

GEOMETRY PUNCHED;
PUNCHED = KEPT_TARGET - KEEP_CUTTER;
"""

#: A thermal node with no geometry at all.
LUMP = """
GEOMETRY LUMP;
LUMP = NON_GEOMETRIC_THERMAL_NODE(
    model_name = "EQUIPMENT",
    node_number = 10500,
    bulk = Steel,
    volume = 0.00100000,
    label1 = "lump",
    origin = [7.00000000, 0.00000000, 0.00000000],
    radius = 0.05000000);
"""

#: A hole punched by deleting a face pair.
REMOVED_FACE = """
GEOMETRY HOLED;
HOLED = SHELL_SCS_RECTANGLE(
    xmax = 0.40000000,
    ymax = 0.40000000,
    nodes1 = 2,
    nodes2 = 2,
    nbase1 = 10600,
    ndelta1 = 1,
    opt1 = Black,
    opt2 = Black);
REMOVE_FACE(face = "HOLED:face1");
"""


def build(tmp_path: Path, body: str, assembly: str) -> tuple[GeometryModel, DiagnosticCollector]:
    """Write a one-off model around *body* and read it back."""
    path = tmp_path / "model.erg"
    path.write_text(
        f"BEGIN_MODEL M\n{PREAMBLE}{body}\nM = {assembly};\n\nEND_MODEL\n", encoding="utf-8"
    )
    model = GeometryModel("M")
    return model, model.io.read_esatan_erg(path, on_diagnostic=lambda _note: None)


def names(model: GeometryModel) -> set[str]:
    return {child.name for child in model.children_recursive()}


def test_the_corpus_reports_every_construct_it_cannot_represent(corpus: tuple) -> None:
    _, diagnostics = corpus
    assert diagnostics.codes() >= EXPECTED_CODES


def test_nothing_unrecognised_is_ignored_in_silence(corpus: tuple) -> None:
    """A statement with no mapping must be named, not merely skipped."""
    _, diagnostics = corpus
    assert "ERG_UNHANDLED_STATEMENT" not in diagnostics.codes()


@pytest.mark.parametrize(
    ("body", "name", "constructor"),
    [
        (SCS_TORUS, "SCS_TORUS", "SHELL_SCS_TORUS"),
        (PT_TORUS, "PT_TORUS", "SHELL_TORUS"),
    ],
    ids=["by parameters", "by points"],
)
def test_a_torus_is_refused_by_either_spelling(
    tmp_path: Path, body: str, name: str, constructor: str
) -> None:
    """There is no torus primitive, so neither spelling may quietly become one."""
    model, diagnostics = build(tmp_path, body, f"KEEPER + {name}")
    unsupported = [note for note in diagnostics if note.code == "ERG_UNSUPPORTED_PRIMITIVE"]
    assert len(unsupported) == 1
    assert constructor in unsupported[0].message
    assert name not in names(model)
    # The surface that is buildable still is: a refusal drops one operand, not
    # the combination that names it.
    assert isinstance(model.get_item("KEEPER"), GeometryItem)


def test_a_skipped_name_is_not_reported_twice_when_it_is_referred_to(tmp_path: Path) -> None:
    """The reason is already recorded; a second error would double-count it."""
    _, diagnostics = build(tmp_path, SCS_TORUS, "KEEPER + SCS_TORUS")
    skipped = {note.code for note in diagnostics if "SCS_TORUS" in note.message}
    assert skipped == {"ERG_UNSUPPORTED_PRIMITIVE", "ERG_SKIPPED_OPERAND"}
    assert "ERG_UNKNOWN_GEOMETRY" not in diagnostics.codes()


def test_an_infinite_planar_cutter_leaves_its_target_whole(tmp_path: Path) -> None:
    """A half space bounds no volume, so the cut cannot be applied at all.

    Dropping the target along with the cutter would lose a surface the file has;
    leaving it uncut keeps it, with the difference reported.
    """
    model, diagnostics = build(tmp_path, HALF_SPACE_CUT, "KEEPER + HALVED")
    assert diagnostics.codes() == {"ERG_UNSUPPORTED_PRIMITIVE", "ERG_SKIPPED_OPERAND"}
    assert "PLANE_CUTTER" in next(
        note.message for note in diagnostics if note.code == "ERG_UNSUPPORTED_PRIMITIVE"
    )
    assert "PLANE_CUTTER" not in names(model)
    # A whole sphere of radius 0.2: nothing was taken off it.
    assert model.get_item("SLICED").primitive.surface_area() == pytest.approx(4 * math.pi * 0.2**2)


def test_a_cut_that_keeps_what_the_cutter_encloses_is_an_error(tmp_path: Path) -> None:
    """A `sense = 1` cut inverts what a cut means, and there is no way to say it."""
    model, diagnostics = build(tmp_path, KEEPING_CUT, "KEEPER + PUNCHED")
    refusals = [note for note in diagnostics if note.code == "ERG_CUTTER_SENSE"]
    assert len(refusals) == 1
    assert refusals[0].severity.value == "error"
    assert "KEEP_CUTTER" in refusals[0].message
    # The 0.4 x 0.4 target survives, uncut and undrilled.
    assert model.get_item("KEPT_TARGET").primitive.surface_area() == pytest.approx(0.16)
    assert not [
        child for child in model.children_recursive() if isinstance(child, GeometryGroupCutted)
    ]


def test_a_node_without_geometry_has_nowhere_to_go(tmp_path: Path) -> None:
    """A geometry model holds shapes, and this construct describes none."""
    model, diagnostics = build(tmp_path, LUMP, "KEEPER + LUMP")
    unsupported = [note for note in diagnostics if note.code == "ERG_UNSUPPORTED_CONSTRUCT"]
    assert len(unsupported) == 1
    assert "NON_GEOMETRIC_THERMAL_NODE" in unsupported[0].message
    assert "LUMP" not in names(model)


def test_a_removed_face_is_an_error_because_the_area_is_wrong(tmp_path: Path) -> None:
    """Skipping REMOVE_FACE leaves more surface than the source model has."""
    model, diagnostics = build(tmp_path, REMOVED_FACE, "KEEPER + HOLED")
    edits = [note for note in diagnostics if note.code == "ERG_FACE_EDIT"]
    assert len(edits) == 1
    assert edits[0].severity.value == "error"
    # The whole 0.4 x 0.4 rectangle is still there, which is what the error says.
    assert model.get_item("HOLED").primitive.surface_area() == pytest.approx(0.16)


def test_the_corpus_drops_no_geometry_at_all(corpus: tuple) -> None:
    """Its remaining diagnostics leave every surface built, if not every meaning."""
    _, diagnostics = corpus
    serious = [note.code for note in diagnostics if note.severity.value in ("error", "unsupported")]
    # Neither of these removes a surface: the assembly keeps its initial pose
    # and loses only the motion, and the finite-element primitive is built as a
    # lumped-parameter one of the same shape.
    assert sorted(serious) == ["ERG_FINITE_ELEMENT", "ERG_KINEMATIC_ASSEMBLY"]


def test_a_variable_rebound_after_use_does_not_change_what_was_built(
    corpus: tuple,
) -> None:
    """Values freeze where they are read, and the redefinition is reported."""
    model, diagnostics = corpus
    assert "ERG_REBOUND_VARIABLE" in diagnostics.codes()
    # Both cones take `semi_ang = SEMI`, the first at 30 degrees and the second
    # after the rebinding to 45.  Equal areas would mean one of them had picked
    # up the other's value.
    early = model.get_item("SCS_CONE").primitive.surface_area()
    late = model.get_item("LATE_CONE").primitive.surface_area()
    assert early != pytest.approx(late)


def test_the_one_sided_activities_survive_whole(corpus: tuple) -> None:
    """ "Radiative" and "Conductive" each land on their own selector.

    A mesh carries one activity per calculation, so the surface that radiates
    without conducting and the one that conducts without radiating are both
    stated exactly -- and neither costs a diagnostic.
    """
    model, diagnostics = corpus
    mesh = model.get_item("DROPPED_ATTRS").thermal_mesh
    assert mesh.radiative_active_side is ActiveSide.SIDE1
    assert mesh.conductive_active_side is ActiveSide.SIDE2
    assert "ERG_ACTIVITY_REDUCED" not in diagnostics.codes()
