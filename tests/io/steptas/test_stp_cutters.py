"""Cutting tools, which STEP-TAS writes as solids rather than as surfaces.

The feature model cuts with a cylinder and a box.  This one cuts with the other
four shapes a tool can be, one of which pycanha cannot cut with at all -- and
the interesting part of the fixture is that it is reported and leaves its
target whole, rather than half-applied.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pycanha_core as pcc
import pytest

from pycanha.gmm import GeometryGroupCutted, GeometryItem, GeometryModel

FIXTURE = Path(__file__).resolve().parents[2] / "data" / "esatan" / "CUTTERS"
CUTTERS = FIXTURE / "CUTTERS.stp"
SOURCE = FIXTURE / "CUTTERS.erg"


@pytest.fixture(scope="module")
def cut() -> tuple[GeometryModel, object]:
    model = GeometryModel("CUTTERS")
    return model, model.io.read_steptas(CUTTERS, on_diagnostic=lambda _note: None)


def item(model: GeometryModel, name: str) -> GeometryItem:
    found = model.get_item(name)
    assert isinstance(found, GeometryItem), name
    return found


def shape[T](item: GeometryItem, kind: type[T]) -> T:
    """The item's primitive as *kind*.

    ``GeometryItem.primitive`` is a union of every shape, so reaching for a
    radius needs the shape pinned down first -- and which shape a tool arrived
    as is part of what these tests are asserting.  The core classes are the ones
    to name here: a reader builds its shapes in the core, and ``pycanha.gmm``
    only wraps their constructors.
    """
    primitive = item.primitive
    assert isinstance(primitive, kind), f"{item.name}: expected a {kind.__name__}"
    return primitive


def test_a_cone_and_a_sphere_can_both_cut(cut: tuple) -> None:
    """Both enclose a volume, so both arrive as usable tools."""
    model, _ = cut
    cone = shape(item(model, "CUTTERS_CONE_TOOL"), pcc.gmm.Cone)
    sphere = shape(item(model, "CUTTERS_SPHERE_TOOL"), pcc.gmm.Sphere)
    assert (cone.radius1, cone.radius2) == pytest.approx(
        (0.1 * math.tan(math.radians(30.0)), 0.4 * math.tan(math.radians(30.0)))
    )
    assert sphere.surface_area() == pytest.approx(4 * math.pi * 0.2**2)


def test_a_tool_carries_its_own_placement(cut: tuple) -> None:
    """The tool is written about its own origin and placed separately.

    Reading the shape and dropping the placement leaves a tool that cuts the
    middle of whatever it was aimed at, which is a hole in the right model in
    the wrong place -- so the placement is checked, not merely the shape.
    """
    model, _ = cut
    cone = item(model, "CUTTERS_CONE_TOOL")
    assert list(cone.transform.apply(np.zeros(3))) == pytest.approx([-0.5, 0.0, -0.2])
    sphere = item(model, "CUTTERS_SPHERE_TOOL")
    assert list(sphere.transform.apply(np.zeros(3))) == pytest.approx([0.5, 0.0, 0.0])


def test_a_shape_that_encloses_nothing_cannot_cut(cut: tuple) -> None:
    """A paraboloid is an open surface however it is written."""
    _, diagnostics = cut
    reported = [note for note in diagnostics if note.code == "TAS_CUTTER_NOT_SOLID"]
    assert len(reported) == 1
    assert "PARA_TOOL" in reported[0].message


def test_a_prism_solid_cuts_rather_than_being_named_as_unreadable(cut: tuple) -> None:
    """``MGM_SOLID_TRIANGULAR_PRISM`` has a closed prism to become since 0.20.

    It carries its four corners in the file's own frame, so unlike the box
    there is no placement split out of it.
    """
    model, diagnostics = cut
    assert not [note for note in diagnostics if note.code == "TAS_CUTTER_UNSUPPORTED"]

    prism = shape(item(model, "CUTTERS_PRISM_TOOL"), pcc.gmm.TriangularPrism)
    assert list(prism.p1) == pytest.approx([-0.2, -0.7, -0.2])
    assert list(prism.p4) == pytest.approx([-0.2, -0.7, 0.4])


def test_the_two_readers_refuse_the_same_tool(cut: tuple) -> None:
    """The same model read from its own format reaches the same conclusion.

    Which tools can cut is a question about pycanha, not about either file, so
    the two readers must answer it the same way -- and they arrive at it from
    entirely different descriptions of the same four shapes.
    """
    model, _ = cut
    source = GeometryModel("source")
    diagnostics = source.io.read_esatan_erg(SOURCE, on_diagnostic=lambda _note: None)
    # Only the paraboloid is refused now; it encloses no volume however written.
    assert "ERG_CUTTER_NOT_SOLID" in diagnostics.codes()
    assert "ERG_CUTTER_NOT_PRIMITIVE" not in diagnostics.codes()

    def cutters(built: GeometryModel) -> set[str]:
        return {
            child.name.removeprefix("CUTTERS_")
            for group in built.children_recursive()
            if isinstance(group, GeometryGroupCutted)
            for child in group.cutters
        }

    assert cutters(model) == cutters(source) == {"CONE_TOOL", "SPHERE_TOOL", "PRISM_TOOL"}


def test_a_refused_cut_leaves_its_target_whole(cut: tuple) -> None:
    """Three cuts apply and one does not, so three cut groups and no more.

    The alternative -- dropping the shape that could not be cut -- would lose
    geometry the file has; leaving it uncut keeps it, with the difference
    reported.
    """
    model, _ = cut
    groups = [
        child for child in model.children_recursive() if isinstance(child, GeometryGroupCutted)
    ]
    assert len(groups) == 3
    plate = item(model, "CUTTERS_SLAB")
    assert plate.primitive.surface_area() == pytest.approx(4.0)
