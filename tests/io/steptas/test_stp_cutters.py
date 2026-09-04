"""Cutting tools, which STEP-TAS writes as solids rather than as surfaces.

The corpus cuts with a cylinder and a box.  This module covers the other shapes
a tool can be, and it does so without a committed file: the model is built here,
written, and read back, so a shape that has no `.erg` spelling is testable the
same way as one that has.

Two things are asserted, and they need different machinery.  That a tool
*survives* is a round trip -- write, read, compare the shape that comes back.
That a tool is written *the way the format says* is a statement about the file
itself, so the entity and everything it refers to are written out here and
compared against what the writer produced.  Reading a file back cannot catch a
misunderstanding the writer and the reader share; stating the expected text can.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
import pycanha_core as pcc
import pytest

from pycanha.gmm import (
    Cone,
    GeometryGroupCutted,
    GeometryItem,
    GeometryModel,
    OpticalMaterial,
    Paraboloid,
    Rectangle,
    Sphere,
    ThermalMesh,
    TriangularPrism,
)
from pycanha.io.part21 import Reference, read_part21

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from pycanha.io.diagnostics import DiagnosticCollector
    from pycanha.io.part21 import Part21File, Value
    from pycanha.io.steptas.mappings import Primitive

#: The four points of the prism tool, in the order the primitive defines them.
PRISM_CORNERS = ((-0.2, -0.7, -0.2), (0.2, -0.7, -0.2), (0.0, -0.4, -0.2), (0.0, 0.0, 0.4))


def quiet(_note: object) -> None:
    """Diagnostics are asserted on where they matter, not printed everywhere."""


def point(*values: float) -> np.ndarray:
    return np.ascontiguousarray(np.array(values, dtype=np.float64))


def tools() -> Mapping[str, Primitive]:
    """One tool of every solid shape a cut can be made with, less the two the corpus has.

    A cone truncated to an apex, a whole sphere and a prism.  Each is placed so
    that it meets the plate it cuts, because a tool that misses removes nothing
    and a cut that removes nothing is not a cut anyone would notice breaking.
    """
    return {
        "CONE_TOOL": Cone(
            point(-0.5, 0.0, -0.2),
            point(-0.5, 0.0, 0.1),
            point(-0.4, 0.0, -0.2),
            0.1,
            0.3,
            0.0,
            math.tau,
        ),
        "SPHERE_TOOL": Sphere(
            point(0.5, 0.0, 0.0),
            point(0.5, 0.0, 1.0),
            point(0.7, 0.0, 0.0),
            0.2,
            -0.2,
            0.2,
            0.0,
            math.tau,
        ),
        "PRISM_TOOL": TriangularPrism(*(point(*corner) for corner in PRISM_CORNERS)),
    }


def plate(name: str, node: int) -> GeometryItem:
    """A 2 x 2 plate for a tool to cut, carrying enough to be exchangeable."""
    black = OpticalMaterial("Black", [0.9, 0.0, 0.0, 0.9, 0.0, 0.0])
    mesh = ThermalMesh()
    mesh.node1_start = node
    mesh.node1_step = 1
    mesh.side1_optical = black
    mesh.side2_optical = black
    return GeometryItem(
        name,
        Rectangle(point(-1.0, -1.0, 0.0), point(1.0, -1.0, 0.0), point(-1.0, 1.0, 0.0)),
        mesh,
    )


def cut_model() -> GeometryModel:
    """One plate per tool, each cut by its own.

    Separately rather than as a chain: the format removes one solid per
    difference surface either way, and one cut per plate keeps which tool did
    what unambiguous when a shape fails to come back.
    """
    model = GeometryModel("CUTTERS")
    for index, (name, primitive) in enumerate(tools().items()):
        model.add(
            GeometryGroupCutted(
                f"CUT_{index}",
                [plate(f"SLAB_{index}", 1000 + 100 * index)],
                [GeometryItem(name, primitive, ThermalMesh())],
            )
        )
    return model


@pytest.fixture(scope="module")
def round_trip(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, GeometryModel, DiagnosticCollector]:
    """The model written out and read back, with the file kept for inspection."""
    target = tmp_path_factory.mktemp("cutters") / "cutters.stp"
    cut_model().io.write_steptas(target, on_diagnostic=quiet)
    reread = GeometryModel("back")
    return target, reread, reread.io.read_steptas(target, on_diagnostic=quiet)


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


# -- the tools that come back ------------------------------------------------


def test_a_cone_and_a_sphere_can_both_cut(round_trip: tuple) -> None:
    """Both enclose a volume, so both arrive as usable tools."""
    _, model, _ = round_trip
    cone = shape(item(model, "CONE_TOOL"), pcc.gmm.Cone)
    sphere = shape(item(model, "SPHERE_TOOL"), pcc.gmm.Sphere)
    assert (cone.radius1, cone.radius2) == pytest.approx((0.1, 0.3))
    assert sphere.surface_area() == pytest.approx(4 * math.pi * 0.2**2)


def test_a_tool_carries_its_own_placement(round_trip: tuple) -> None:
    """The tool is written about its own origin and placed separately.

    Reading the shape and dropping the placement leaves a tool that cuts the
    middle of whatever it was aimed at, which is a hole in the right model in
    the wrong place -- so the placement is checked, not merely the shape.
    """
    _, model, _ = round_trip
    cone = item(model, "CONE_TOOL")
    assert list(cone.transform.apply(np.zeros(3))) == pytest.approx([0.0, 0.0, 0.0])
    # Placement and shape together: the cone's own first end centre is where the
    # model put it, whichever of the two carried the offset through the file.
    first_end = np.ascontiguousarray(np.asarray(shape(cone, pcc.gmm.Cone).p1))
    assert list(cone.transform.apply(first_end)) == pytest.approx([-0.5, 0.0, -0.2])


def test_a_prism_solid_cuts_rather_than_being_named_as_unreadable(round_trip: tuple) -> None:
    """``MGM_SOLID_TRIANGULAR_PRISM`` has a closed prism to become since 0.20.

    It carries its four corners in the file's own frame, so unlike the box
    there is no placement split out of it.
    """
    _, model, diagnostics = round_trip
    assert not [note for note in diagnostics if note.code == "TAS_CUTTER_UNSUPPORTED"]

    prism = shape(item(model, "PRISM_TOOL"), pcc.gmm.TriangularPrism)
    assert list(prism.p1) == pytest.approx(PRISM_CORNERS[0])
    assert list(prism.p4) == pytest.approx(PRISM_CORNERS[3])


def test_every_cut_survives_with_its_tool(round_trip: tuple) -> None:
    """Three tools, three cut groups, and every plate still 2 x 2."""
    _, model, _ = round_trip
    groups = [
        child for child in model.children_recursive() if isinstance(child, GeometryGroupCutted)
    ]
    assert len(groups) == 3
    assert all(len(group.cutters) == 1 for group in groups)
    for index in range(3):
        assert item(model, f"SLAB_{index}").primitive.surface_area() == pytest.approx(4.0)


def test_a_shape_that_encloses_nothing_cannot_cut() -> None:
    """A paraboloid is an open surface however it is written.

    Refused where the model is built, which is before any file exists: the
    alternative -- accepting it and discovering on the way out that there is no
    solid to write -- would leave a model claiming a cut that never happens.
    """
    open_tool = GeometryItem(
        "PARA_TOOL",
        Paraboloid(
            point(0.0, 0.5, -0.15),
            point(0.0, 0.5, 0.15),
            point(0.2, 0.5, -0.15),
            0.2,
            0.0,
            math.tau,
        ),
        ThermalMesh(),
    )
    with pytest.raises(ValueError, match="closed solid"):
        GeometryGroupCutted("HOLED", [plate("SLAB", 1000)], [open_tool])


def test_a_solid_that_encloses_nothing_cannot_cut(round_trip: tuple, tmp_path: Path) -> None:
    """The format has a solid paraboloid; pycanha refuses to cut with one.

    No file pycanha writes can carry this, because a model refuses an open
    cutter before a file is reached -- so the entity gets into one the only way
    it ever does, from a producer that allowed it.  A solid paraboloid is
    written exactly as a solid cone is, eight attributes in the same order, so
    retyping the entity is the whole of the difference between the two files.

    The plate has to survive whole rather than be dropped with the tool: the
    file says it is there, and only the cut is impossible.
    """
    source, _, _ = round_trip
    target = tmp_path / "open_tool.stp"
    text = source.read_text(encoding="utf-8")
    assert text.count("=MGM_SOLID_CONE(") == 1
    target.write_text(text.replace("=MGM_SOLID_CONE(", "=MGM_SOLID_PARABOLOID("), encoding="utf-8")

    model = GeometryModel("open")
    diagnostics = model.io.read_steptas(target, on_diagnostic=quiet)
    refusals = [note for note in diagnostics if note.code == "TAS_CUTTER_NOT_SOLID"]
    assert len(refusals) == 1
    assert "CONE_TOOL" in refusals[0].message
    assert not model.get_item("CONE_TOOL")
    # Two cuts applied and one did not, and the plate the third aimed at is
    # still the whole 2 x 2.
    groups = [
        child for child in model.children_recursive() if isinstance(child, GeometryGroupCutted)
    ]
    assert len(groups) == 2
    assert item(model, "SLAB_0").primitive.surface_area() == pytest.approx(4.0)


# -- what the file says ------------------------------------------------------


#: How much of each entity a solid refers to is the entity itself.
#:
#: A point is a name, three coordinates and the unit they are in; a quantity is
#: the unit, the value and an empty list of qualifiers.  The units are the
#: file's own, shared by everything in it and asserted where the units are, so
#: what is left in both cases is the numbers.
_MEANING = {
    "MGM_3D_CARTESIAN_POINT": slice(1, 4),
    "NRF_REAL_QUANTITY_VALUE_LITERAL": slice(1, 2),
}


def solid(parsed: Part21File, kind: str) -> list[tuple[str, tuple[Value, ...]]]:
    """The one entity of *kind* in *parsed*, with each reference resolved.

    A reference is replaced by the kind of what it names and the numbers in it,
    so an expectation can be written as the shape it describes rather than as
    instance numbers, which are an artefact of how the file is laid out.
    """
    entities = parsed.of_kind(kind)
    assert len(entities) == 1, f"expected one {kind}, found {len(entities)}"
    resolved: list[tuple[str, tuple[Value, ...]]] = []
    # The first parameter is the back-reference to the owning difference surface.
    for index, parameter in enumerate(entities[0].params[1:], start=1):
        assert isinstance(parameter, Reference), f"{kind}[{index}]: expected a reference"
        named = parsed.entity(parameter)
        assert named is not None, f"{kind}[{index}]: dangling reference"
        assert named.kind in _MEANING, f"{kind}[{index}]: unexpected {named.kind}"
        resolved.append((named.kind, tuple(named.params[_MEANING[named.kind]])))
    return resolved


def coordinates(*values: float) -> tuple[str, tuple[Value, ...]]:
    """An ``MGM_3D_CARTESIAN_POINT``, as its three coordinates."""
    return ("MGM_3D_CARTESIAN_POINT", values)


def quantity(value: float) -> tuple[str, tuple[Value, ...]]:
    """An ``NRF_REAL_QUANTITY_VALUE_LITERAL``, as the one number it carries."""
    return ("NRF_REAL_QUANTITY_VALUE_LITERAL", ((value,),))


def test_a_prism_is_written_as_its_four_corners(round_trip: tuple) -> None:
    """The whole entity, stated rather than read back.

    A prism has no placement of its own in the format, so the four points *are*
    the shape and their order is the whole of its orientation: the base winds
    p1-p2-p3 and the edge to p4 leaves the base on the side that winding points
    to.  A file with them in another order describes a prism turned inside out,
    which reads back as the same four points and is not the same solid.
    """
    target, _, _ = round_trip
    written = solid(read_part21(target), "MGM_SOLID_TRIANGULAR_PRISM")
    assert written == [coordinates(*corner) for corner in PRISM_CORNERS]


def test_a_cone_is_written_as_two_end_centres_and_the_radius_at_each(round_trip: tuple) -> None:
    """The frustum spelling, including the datum the format requires.

    The third point is the datum fixing where the angular sweep starts.  The
    format wants it perpendicular to the axis and at unit distance, which is not
    what the primitive carries, so the writer rebuilds it -- and that rebuilding
    is the part an assertion about the file catches and a round trip does not.
    """
    target, _, _ = round_trip
    written = solid(read_part21(target), "MGM_SOLID_CONE")
    assert written == [
        coordinates(-0.5, 0.0, -0.2),
        coordinates(-0.5, 0.0, 0.1),
        coordinates(0.5, 0.0, -0.2),
        quantity(0.1),
        quantity(0.3),
        quantity(0.0),
        quantity(math.degrees(math.tau)),
    ]
