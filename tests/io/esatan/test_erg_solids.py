"""ESATAN solids that become several flat surfaces here.

A box has two readings and only the statement that *uses* it says which: six
faces as geometry, one closed solid as a cutting tool.  A prism has just one,
three side walls -- its triangular ends genuinely do not exist.

These tests pin the readings and the numbers that separate a correct
decomposition from a plausible-looking wrong one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pycanha_core as pcc
import pytest

from pycanha.gmm import GeometryGroup, GeometryGroupCutted, GeometryModel
from pycanha.gmm.mesh import ops as mesh_ops

if TYPE_CHECKING:
    from pathlib import Path

#: A plate with a 2 x 2 x 2 box straddling it, positioned to punch a clean hole.
PLATE_AND_BOX = """
GEOMETRY P;
P = SHELL_SCS_RECTANGLE(xmax = 4.0, ymax = 4.0);
GEOMETRY B;
B = SHELL_BOX(
    point1 = [1.0, 1.0, -1.0],
    point2 = [3.0, 1.0, -1.0],
    point3 = [1.0, 3.0, -1.0],
    point4 = [1.0, 1.0, 1.0],
    sense = -1);
GEOMETRY X;
X = P - B;
"""

#: The same box, but with an edge deliberately skewed off perpendicular.
SKEWED_BOX = """
GEOMETRY P;
P = SHELL_SCS_RECTANGLE(xmax = 4.0, ymax = 4.0);
GEOMETRY B;
B = SHELL_BOX(
    point1 = [0.0, 0.0, 0.0],
    point2 = [1.0, 0.0, 0.0],
    point3 = [0.5, 1.0, 0.0],
    point4 = [0.0, 0.0, 1.0],
    sense = -1);
GEOMETRY X;
X = P - B;
"""

STANDALONE_BOX = """
GEOMETRY B;
B = SHELL_SCS_BOX(xmax = 1.0, ymax = 2.0, height = 3.0);
"""

#: A prism on a 3-4-5 base triangle, extruded 2 along +Z.
PRISM = """
GEOMETRY P;
P = SHELL_TRIANGULAR_PRISM(
    point1 = [0.0, 0.0, 0.0],
    point2 = [3.0, 0.0, 0.0],
    point3 = [0.0, 4.0, 0.0],
    point4 = [0.0, 0.0, 2.0],
    nbase1 = 3000,
    ndelta1 = 1);
"""


def build(tmp_path: Path, body: str) -> tuple:
    """Write a one-off model and read it back, returning the model and diagnostics."""
    path = tmp_path / "model.erg"
    path.write_text(f"BEGIN_MODEL M\n{body}\nEND_MODEL\n", encoding="utf-8")
    model = GeometryModel("M")
    return model, model.io.read_esatan_erg(path)


def test_a_box_used_as_geometry_becomes_six_faces(tmp_path: Path) -> None:
    model, diagnostics = build(tmp_path, STANDALONE_BOX)
    group = model.get_group("B")
    assert isinstance(group, GeometryGroup)
    assert [child.name for child in group.children] == [f"B_face{n}" for n in range(1, 7)]
    total = sum(child.primitive.surface_area() for child in group.children)
    assert total == pytest.approx(2 * ((1 * 2) + (1 * 3) + (2 * 3)))
    assert "ERG_BOX_DECOMPOSED" in diagnostics.codes()
    assert "ERG_BOX_CUTTER" not in diagnostics.codes()


def test_box_faces_point_outwards(tmp_path: Path) -> None:
    """A closed shell has its inside on surface 2, so surface 1 must face out."""
    model, _ = build(tmp_path, STANDALONE_BOX)
    centre = np.array([0.5, 1.0, 1.5])
    for face in model.get_group("B").children:
        primitive = face.primitive
        outward = primitive.p1 - centre
        normal = primitive.normal_at_uv(np.array([0.5, 0.5]))
        assert float(np.dot(normal, outward)) > 0.0


def test_a_box_used_as_a_cutter_becomes_one_closed_solid(tmp_path: Path) -> None:
    """A group of surfaces cannot cut, so the cutter reading is a single solid."""
    model, diagnostics = build(tmp_path, PLATE_AND_BOX)
    cut = model.get_cut_group("X")
    assert isinstance(cut, GeometryGroupCutted)

    cutter = cut.cutters[0]
    assert cutter.name == "B"
    assert isinstance(cutter.primitive, pcc.gmm.Cube)
    assert cutter.primitive.extent == pytest.approx([2.0, 2.0, 2.0])
    # The cube is axis-aligned about its own origin, and the item's
    # transformation carries the box's frame and centre.
    assert cutter.transform.apply(np.zeros(3)) == pytest.approx([2.0, 2.0, 0.0])

    assert "ERG_BOX_CUTTER" in diagnostics.codes()
    assert "ERG_CUTTER_NOT_PRIMITIVE" not in diagnostics.codes()
    assert "ERG_BOX_DECOMPOSED" not in diagnostics.codes()


def test_a_box_cutter_removes_exactly_its_own_footprint(tmp_path: Path) -> None:
    model, _ = build(tmp_path, PLATE_AND_BOX)
    area = float(mesh_ops.compute_areas(model.get_cut_group("X").mesh).sum())
    assert area == pytest.approx((4.0 * 4.0) - (2.0 * 2.0))


def test_a_skewed_box_cutter_is_reported(tmp_path: Path) -> None:
    """A cube can only be a right box, so non-perpendicular edges are worth saying."""
    _, diagnostics = build(tmp_path, SKEWED_BOX)
    assert "ERG_BOX_NOT_ORTHOGONAL" in diagnostics.codes()


def test_the_faces_of_a_box_carry_its_attributes(tmp_path: Path) -> None:
    model, _ = build(
        tmp_path,
        "OPTICAL Paint;\nDEFINE_OPTICAL (optical = Paint, ir_emiss = 0.8, solar_absorb = 0.3);\n"
        "GEOMETRY B;\n"
        "B = SHELL_SCS_BOX(xmax = 1.0, ymax = 1.0, height = 1.0, opt1 = Paint, opt2 = Paint,"
        ' colour1 = "DARK_GREY", thick = 0.004);',
    )
    for face in model.get_group("B").children:
        mesh = face.thermal_mesh
        assert mesh.side1_optical is not None
        assert mesh.side1_optical.name == "Paint"
        assert (mesh.side1_thick, mesh.side2_thick) == pytest.approx((0.002, 0.002))


def test_a_prism_becomes_three_side_walls(tmp_path: Path) -> None:
    """The triangular ends are absent, not merely undecomposed.

    A shell prism is three rectangles and no triangles, so adding end caps would
    invent surface area the source has not got.  The wall areas are the base
    edges (3, 5, 4) times the height.
    """
    model, diagnostics = build(tmp_path, PRISM)
    group = model.get_group("P")
    assert isinstance(group, GeometryGroup)
    assert [child.name for child in group.children] == [f"P_face{n}" for n in (1, 2, 3)]
    areas = [child.primitive.surface_area() for child in group.children]
    assert areas == pytest.approx([3.0 * 2.0, 5.0 * 2.0, 4.0 * 2.0])
    assert "ERG_PRISM_DECOMPOSED" in diagnostics.codes()


def test_prism_walls_point_outwards(tmp_path: Path) -> None:
    model, _ = build(tmp_path, PRISM)
    centroid = np.array([1.0, 4.0 / 3.0, 1.0])
    for wall in model.get_group("P").children:
        primitive = wall.primitive
        normal = primitive.normal_at_uv(np.array([0.5, 0.5]))
        assert float(np.dot(normal, primitive.p1 - centroid)) > 0.0


def test_prism_walls_continue_one_node_sequence(tmp_path: Path) -> None:
    model, _ = build(tmp_path, PRISM)
    starts = [wall.thermal_mesh.node1_start for wall in model.get_group("P").children]
    assert starts == [3000, 3001, 3002]


def test_a_prism_cannot_be_used_as_a_cutter(tmp_path: Path) -> None:
    """A prism has no closed-solid reading, so it is refused rather than guessed at."""
    _, diagnostics = build(
        tmp_path,
        "GEOMETRY R;\nR = SHELL_SCS_RECTANGLE(xmax = 4.0, ymax = 4.0);\n"
        + PRISM
        + "GEOMETRY X;\nX = R - P;",
    )
    assert "ERG_CUTTER_NOT_PRIMITIVE" in diagnostics.codes()
