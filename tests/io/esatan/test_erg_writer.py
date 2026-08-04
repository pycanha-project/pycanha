"""Writing a GeometryModel back out as ESATAN geometry.

The strongest thing that can be asserted without another tool in the room is
that a model survives being written and read again: same items, same shapes,
same numbers.  That is what most of these do, because it catches the failures
that reading alone cannot -- a radius taken from the wrong place, an angle in
the wrong units, a name that ends up meaning two objects at once.

The tolerance throughout is the format's own precision, which is not tight: what
these are looking for are errors of a factor, not of a part per million.
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import numpy as np
import pycanha_core as pcc
import pytest

from pycanha.gmm import GeometryGroup, GeometryGroupCutted, GeometryItem, GeometryModel

FEATURES = Path(__file__).resolve().parents[2] / "data" / "esatan" / "FEATURES"

#: What the format's precision is worth as a relative tolerance.
#:
#: Eight significant digits *or* seven decimal places, whichever is coarser --
#: so a number a little above 0.01 keeps only about seven significant digits,
#: and a length written that way carries roughly 1e-6 of relative error into any
#: area computed from it.  This is the guarantee, not a margin for error.
FORMAT_PRECISION = 1e-6

#: The same, for a cone.
#:
#: The format gives a cone by its apex, which a frustum does not have: it is
#: extrapolated from the two end radii, and the closer they are the further away
#: the apex is, so the eight digits each radius keeps are magnified on the way
#: out.  Still tight enough to catch a wrong radius or an angle in the wrong
#: units, which are wrong by factors, not by parts per million.
CONE_PRECISION = 1e-5

_PAINT = "OPTICAL Paint;\nDEFINE_OPTICAL (optical = Paint, ir_emiss = 0.8, solar_absorb = 0.3);\n"


def read(path: Path, name: str = "M") -> GeometryModel:
    model = GeometryModel(name)
    model.io.read_esatan_erg(path, on_diagnostic=lambda _note: None)
    return model


def round_trip(tmp_path: Path, body: str) -> tuple[GeometryModel, GeometryModel]:
    """Read a one-off model, write it, read it back; return both."""
    source = tmp_path / "source.erg"
    source.write_text(f"BEGIN_MODEL M\n{_PAINT}{body}\nEND_MODEL\n", encoding="utf-8")
    first = read(source)
    written = tmp_path / "written.erg"
    first.io.write_esatan_erg(written, name="M", on_diagnostic=lambda _note: None)
    return first, read(written)


def items(model: GeometryModel) -> dict[str, GeometryItem]:
    """Every leaf item in the model, by name."""
    found: dict[str, GeometryItem] = {}

    def walk(node: object) -> None:
        children = list(getattr(node, "children", []))
        parts = list(getattr(node, "targets", [])) + list(getattr(node, "cutters", []))
        if not children and not parts and isinstance(node, GeometryItem):
            found[node.name] = node
        for child in children + parts:
            walk(child)

    for child in model.children:
        walk(child)
    return found


def shape[T](item: GeometryItem, kind: type[T]) -> T:
    """The item's primitive as *kind*.

    ``GeometryItem.primitive`` is a union of every shape, so reaching for a
    radius or a corner point needs the shape pinned down first.  Which shape a
    round trip produced is half of what these tests are asserting anyway.  The
    core classes are the ones to name here: a reader builds its shapes in the
    core, and ``pycanha.gmm`` only wraps their constructors.
    """
    primitive = item.primitive
    assert isinstance(primitive, kind), f"{item.name}: expected a {kind.__name__}"
    return primitive


# -- the shape of the file -------------------------------------------------


def test_the_file_has_the_blocks_the_format_expects(tmp_path: Path) -> None:
    model = GeometryModel("M")
    out = tmp_path / "empty.erg"
    model.io.write_esatan_erg(out, name="EMPTY", on_diagnostic=lambda _note: None)
    text = out.read_text(encoding="utf-8")

    assert text.startswith("BEGIN_MODEL EMPTY WORKBENCH_V1 ESARAD_GENERATED")
    assert text.rstrip().endswith("END_MODEL")
    for name in ("independent variable", "bound variable", "primitive", "structure"):
        assert f"/* Start of {name} block */" in text
        assert f"/* End of {name} block - no errors */" in text


def test_an_empty_model_says_so_rather_than_writing_a_broken_file(tmp_path: Path) -> None:
    model = GeometryModel("M")
    out = tmp_path / "empty.erg"
    diagnostics = model.io.write_esatan_erg(out, on_diagnostic=lambda _note: None)
    assert "ERG_WRITE_EMPTY_MODEL" in diagnostics.codes()


def test_materials_are_written_once_each_however_many_surfaces_use_them(
    tmp_path: Path,
) -> None:
    body = (
        "BULK Alu;\nAlu = [2700.0, 900.0, 160.0];\n"
        "GEOMETRY A;\nA = SHELL_SCS_RECTANGLE(xmax = 1.0, ymax = 1.0, "
        "opt1 = Paint, opt2 = Paint, bulk = Alu, thick = 0.002);\n"
        "GEOMETRY B;\nB = SHELL_SCS_RECTANGLE(xmax = 1.0, ymax = 1.0, "
        "opt1 = Paint, opt2 = Paint, bulk = Alu, thick = 0.002);\n"
        "M = A + B;\n"
    )
    source = tmp_path / "source.erg"
    source.write_text(f"BEGIN_MODEL M\n{_PAINT}{body}\nEND_MODEL\n", encoding="utf-8")
    out = tmp_path / "written.erg"
    read(source).io.write_esatan_erg(out, name="M", on_diagnostic=lambda _note: None)
    text = out.read_text(encoding="utf-8")

    assert text.count("BULK Alu;") == 1
    assert text.count("OPTICAL Paint;") == 1
    assert text.count("DEFINE_BULK") == 1


# -- geometry survives -----------------------------------------------------


@pytest.mark.parametrize(
    ("name", "source"),
    [
        ("T", "T = SHELL_TRIANGLE(point1 = [0,0,0], point2 = [3,0,0], point3 = [0,4,0]"),
        ("R", "R = SHELL_SCS_RECTANGLE(xmax = 2.0, ymax = 3.0"),
        (
            "Q",
            "Q = SHELL_QUADRILATERAL(point1 = [0,0,0], point2 = [2,0,0], "
            "point3 = [2,1,0], point4 = [0,1,0]",
        ),
        ("D", "D = SHELL_SCS_DISC(rmax = 0.5, rmin = 0.1"),
        ("DS", "DS = SHELL_SCS_DISC(rmax = 0.5, angmax = 270.0"),
        ("C", "C = SHELL_SCS_CYLINDER(radius = 0.4, hmax = 1.2"),
        ("CS", "CS = SHELL_SCS_CYLINDER(radius = 0.4, hmax = 1.2, angmax = 90.0"),
        ("K", "K = SHELL_SCS_CONE(semi_ang = 25.0, hmin = 0.2, hmax = 1.0"),
        ("S", "S = SHELL_SCS_SPHERE(radius = 0.7"),
        ("ST", "ST = SHELL_SCS_SPHERE(radius = 0.7, lat_min = -40.0, lat_max = 55.0"),
        ("P", "P = SHELL_SCS_PARABOLOID(flength = 0.3, hmax = 0.9"),
    ],
)
def test_a_primitive_keeps_its_area_through_a_write(tmp_path: Path, name: str, source: str) -> None:
    """Area is the one number that moves if a radius or an angle is misread."""
    body = f"GEOMETRY {name};\n{source}, opt1 = Paint, opt2 = Paint);\nM = {name};\n"
    first, second = round_trip(tmp_path, body)
    before = items(first)[name].primitive.surface_area()
    after = items(second)[name].primitive.surface_area()
    tolerance = CONE_PRECISION if "CONE" in source else FORMAT_PRECISION
    assert after == pytest.approx(before, rel=tolerance)


def test_a_full_turn_is_not_written_as_a_narrow_sector(tmp_path: Path) -> None:
    """Angles are stored in radians; treating 2*pi as degrees loses 98% of the area."""
    body = (
        "GEOMETRY C;\nC = SHELL_SCS_CYLINDER(radius = 1.0, hmax = 1.0, "
        "opt1 = Paint, opt2 = Paint);\nM = C;\n"
    )
    _, second = round_trip(tmp_path, body)
    assert items(second)["C"].primitive.surface_area() == pytest.approx(2 * math.pi)


def test_a_sector_keeps_its_opening_angle(tmp_path: Path) -> None:
    body = (
        "GEOMETRY C;\nC = SHELL_SCS_CYLINDER(radius = 1.0, hmax = 1.0, angmax = 90.0, "
        "opt1 = Paint, opt2 = Paint);\nM = C;\n"
    )
    _, second = round_trip(tmp_path, body)
    cylinder = shape(items(second)["C"], pcc.gmm.Cylinder)
    assert cylinder.end_angle == pytest.approx(math.pi / 2, rel=FORMAT_PRECISION)
    assert cylinder.surface_area() == pytest.approx(math.pi / 2, rel=FORMAT_PRECISION)


def test_a_shell_coordinate_primitive_keeps_its_radius(tmp_path: Path) -> None:
    """These carry a unit datum and a separate radius; measuring the frame is wrong."""
    body = (
        "GEOMETRY C;\nC = SHELL_SCS_CYLINDER(radius = 0.1, hmax = 0.3, "
        "opt1 = Paint, opt2 = Paint);\nM = C;\n"
    )
    _, second = round_trip(tmp_path, body)
    assert shape(items(second)["C"], pcc.gmm.Cylinder).radius == pytest.approx(
        0.1, rel=FORMAT_PRECISION
    )


def test_a_placement_is_carried_into_the_points(tmp_path: Path) -> None:
    """Nothing writes ROTATE or TRANSLATE, so the transform must be baked in."""
    body = (
        "GEOMETRY R;\nR = SHELL_SCS_RECTANGLE(xmax = 1.0, ymax = 2.0, "
        "opt1 = Paint, opt2 = Paint);\n"
        "R = ROTATE(object_name = R, z_ang = 90.0);\n"
        "R = TRANSLATE(object_name = R, x_dist = 5.0);\nM = R;\n"
    )
    first, second = round_trip(tmp_path, body)
    before = np.asarray(shape(items(first)["R"], pcc.gmm.Rectangle).p2)
    before_world = np.asarray(items(first)["R"].transform.apply(before))
    after = np.asarray(shape(items(second)["R"], pcc.gmm.Rectangle).p2)
    after_world = np.asarray(items(second)["R"].transform.apply(after))
    assert after_world == pytest.approx(before_world, abs=1e-7)


# -- structure survives ----------------------------------------------------


def test_a_group_of_one_is_written_as_a_combination_not_an_alias(tmp_path: Path) -> None:
    """`A = B;` would give one object two names, and both would attach as roots."""
    body = (
        "GEOMETRY T;\nT = SHELL_TRIANGLE(point1 = [0,0,0], point2 = [1,0,0], "
        "point3 = [0,1,0], opt1 = Paint, opt2 = Paint);\n"
        "GEOMETRY S;\nS = SINGLE_COMBINATION(geometry = T);\n"
        "GEOMETRY R;\nR = SHELL_SCS_RECTANGLE(xmax = 1.0, ymax = 1.0, "
        "opt1 = Paint, opt2 = Paint);\nM = S + R;\n"
    )
    source = tmp_path / "source.erg"
    source.write_text(f"BEGIN_MODEL M\n{_PAINT}{body}\nEND_MODEL\n", encoding="utf-8")
    out = tmp_path / "written.erg"
    read(source).io.write_esatan_erg(out, name="M", on_diagnostic=lambda _note: None)
    assert "SINGLE_COMBINATION" in out.read_text(encoding="utf-8")

    again = read(out, "BACK")
    assert isinstance(again.get_group("S"), GeometryGroup)


def test_a_cut_survives_with_its_cutters(tmp_path: Path) -> None:
    body = (
        "GEOMETRY P;\nP = SHELL_SCS_RECTANGLE(xmin = -2.0, xmax = 2.0, ymin = -2.0, "
        "ymax = 2.0, opt1 = Paint, opt2 = Paint);\n"
        "GEOMETRY C;\nC = SHELL_SCS_CYLINDER(radius = 0.5, hmin = -1.0, hmax = 1.0, "
        "sense = -1, opt1 = Paint, opt2 = Paint);\n"
        "GEOMETRY X;\nX = P - C;\nM = X;\n"
    )
    _, second = round_trip(tmp_path, body)
    # Walked rather than looked up: `get_group` does not return a cut group.
    cut = next(iter(second.children))
    assert isinstance(cut, GeometryGroupCutted)
    assert cut.name == "X"
    assert [c.name for c in cut.cutters] == ["C"]


def test_a_cutter_is_written_with_the_sense_that_removes_material(tmp_path: Path) -> None:
    """The format's default keeps what the cutter encloses, which is refused here."""
    body = (
        "GEOMETRY P;\nP = SHELL_SCS_RECTANGLE(xmin = -2.0, xmax = 2.0, ymin = -2.0, "
        "ymax = 2.0, opt1 = Paint, opt2 = Paint);\n"
        "GEOMETRY C;\nC = SHELL_SCS_CYLINDER(radius = 0.5, hmin = -1.0, hmax = 1.0, "
        "sense = -1, opt1 = Paint, opt2 = Paint);\n"
        "GEOMETRY X;\nX = P - C;\nM = X;\n"
    )
    source = tmp_path / "source.erg"
    source.write_text(f"BEGIN_MODEL M\n{_PAINT}{body}\nEND_MODEL\n", encoding="utf-8")
    out = tmp_path / "written.erg"
    read(source).io.write_esatan_erg(out, name="M", on_diagnostic=lambda _note: None)
    assert "sense = -1" in out.read_text(encoding="utf-8")

    again = GeometryModel("BACK")
    diagnostics = again.io.read_esatan_erg(out, on_diagnostic=lambda _note: None)
    assert "ERG_CUTTER_SENSE" not in diagnostics.codes()


# -- attributes survive ----------------------------------------------------


def test_node_numbering_survives(tmp_path: Path) -> None:
    body = (
        "GEOMETRY C;\nC = SHELL_SCS_CYLINDER(radius = 1.0, hmax = 1.0, nodes1 = 2, "
        "nodes2 = 3, nbase1 = 100, ndelta1 = 1, nbase2 = 500, ndelta2 = 2, "
        "opt1 = Paint, opt2 = Paint);\nM = C;\n"
    )
    _, second = round_trip(tmp_path, body)
    mesh = items(second)["C"].thermal_mesh
    assert (mesh.node1_start, mesh.node1_step) == (100, 1)
    assert (mesh.node2_start, mesh.node2_step) == (500, 2)
    assert [[mesh.node_of(i, j, 1) for j in range(3)] for i in range(2)] == [
        [100, 102, 104],
        [101, 103, 105],
    ]


def test_a_non_uniform_mesh_survives_as_explicit_positions(tmp_path: Path) -> None:
    body = (
        "GEOMETRY R;\nR = SHELL_SCS_RECTANGLE(xmax = 1.0, ymax = 1.0, "
        'meshType1 = "regular", nodes1 = 3, ratio1 = 2.0, '
        "opt1 = Paint, opt2 = Paint);\nM = R;\n"
    )
    first, second = round_trip(tmp_path, body)
    before = list(items(first)["R"].thermal_mesh.dir1_mesh)
    after = list(items(second)["R"].thermal_mesh.dir1_mesh)
    assert after == pytest.approx(before, abs=1e-7)


def test_a_dual_composition_keeps_the_two_sides_apart(tmp_path: Path) -> None:
    body = (
        "BULK Alu;\nAlu = [2700.0, 900.0, 160.0];\n"
        "BULK Steel;\nSteel = [7900.0, 500.0, 15.0];\n"
        "GEOMETRY R;\nR = SHELL_SCS_RECTANGLE(xmax = 1.0, ymax = 1.0, "
        'composition = "DUAL", bulk1 = Alu, thick1 = 0.001, bulk2 = Steel, '
        "thick2 = 0.003, opt1 = Paint, opt2 = Paint);\nM = R;\n"
    )
    _, second = round_trip(tmp_path, body)
    mesh = items(second)["R"].thermal_mesh
    assert (mesh.side1_thick, mesh.side2_thick) == pytest.approx((0.001, 0.003))
    assert mesh.side1_material.name == "Alu"
    assert mesh.side2_material.name == "Steel"


def test_a_single_thickness_survives_being_halved_and_put_back(tmp_path: Path) -> None:
    """Reading splits one thickness across two sides; writing has to undo that."""
    body = (
        "BULK Alu;\nAlu = [2700.0, 900.0, 160.0];\n"
        "GEOMETRY R;\nR = SHELL_SCS_RECTANGLE(xmax = 1.0, ymax = 1.0, "
        "bulk = Alu, thick = 0.004, opt1 = Paint, opt2 = Paint);\nM = R;\n"
    )
    _, second = round_trip(tmp_path, body)
    mesh = items(second)["R"].thermal_mesh
    assert (mesh.side1_thick, mesh.side2_thick) == pytest.approx((0.002, 0.002))


def test_an_inactive_side_stays_inactive(tmp_path: Path) -> None:
    body = (
        "GEOMETRY R;\nR = SHELL_SCS_RECTANGLE(xmax = 1.0, ymax = 1.0, "
        'side2 = "Inactive", opt1 = Paint, opt2 = Paint);\nM = R;\n'
    )
    _, second = round_trip(tmp_path, body)
    mesh = items(second)["R"].thermal_mesh
    assert mesh.side1_activity is True
    assert mesh.side2_activity is False


# -- the whole feature model ----------------------------------------------


def test_the_feature_model_survives_a_write_intact() -> None:
    """Every item, every area: the broadest statement available without ESATAN."""
    source = FEATURES / "FEATURES_TAS.erg"
    first = read(source, "FEATURES_TAS")

    with tempfile.TemporaryDirectory() as directory:
        out = Path(directory) / "written.erg"
        diagnostics = first.io.write_esatan_erg(
            out, name="WRITTEN", on_diagnostic=lambda _note: None
        )
        second = read(out, "BACK")

    # The only thing the model cannot supply is the palette name of a colour.
    assert diagnostics.codes() <= {"ERG_WRITE_NO_COLOUR"}

    before, after = items(first), items(second)
    assert set(before) == set(after)
    for name, item in before.items():
        is_cone = type(item.primitive).__name__ == "Cone"
        assert after[name].primitive.surface_area() == pytest.approx(
            item.primitive.surface_area(),
            rel=CONE_PRECISION if is_cone else FORMAT_PRECISION,
        ), name
