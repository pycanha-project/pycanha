"""The same model, read from two formats, has to come out the same.

One feature model exists both as ESATAN geometry and as the STEP-TAS export of
it.  The two files describe the same shapes in almost entirely different terms
-- one by parameters about a local origin, the other by points and quantities
in the model frame -- so reading both and comparing is the strongest check
available on either reader.  A parametrisation misread in one of them shows up
here as an area that does not match.

Three differences are *expected* and are named below.  Anything else failing
means one of the two readers is wrong.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from pycanha.gmm import GeometryItem, GeometryModel

FEATURES = Path(__file__).resolve().parents[2] / "data" / "esatan" / "FEATURES"
SOURCE = FEATURES / "FEATURES_TAS.erg"
CONVERTED = FEATURES / "FEATURES_TAS.stp"

#: Areas match to this fraction; the shapes are rebuilt, not copied.
TOLERANCE = 1e-9

#: The one surface whose two readings are of two different shapes.
#:
#: Its half-angle is given as a variable that the file redefines further down.
#: A geometry file keeps the *reference*: the surface follows the variable, and
#: the shape that reaches the STEP-TAS export is the one the final value gives.
#: This reader evaluates where it reads and so builds the earlier one, reporting
#: the redefinition as it goes.
REBOUND = "SCS_CONE"

#: The one surface whose two readings are meshed differently.
#:
#: It asks for a finite-element mesh, which STEP-TAS has no form for, so the
#: converter halves every face along both directions to give each resulting face
#: a node of its own.  Four faces where the source has one, covering the same
#: surface.
REFINED = {"DROPPED_ATTRS": (2, 2)}

#: The groups that arrive already split into flat faces, under names of the
#: exporter's choosing rather than the ones this reader invents.
SPLIT_GROUPS = ("SCS_BOX_", "PT_BOX_", "PT_PRISM_", "SCS_PRISM_")

#: The sides whose node numbers the source states and the export leaves out.
#:
#: Both have nothing to hang a number on once converted: one side is inactive
#: and takes no part in the thermal model, and a cutting tool becomes a solid
#: with no faces of its own at all.
UNNUMBERED_ON_EXPORT = ["ATTRS:surface2", "CYL_CUTTER:surface1"]


def items(model: GeometryModel) -> dict[str, GeometryItem]:
    return {
        child.name: child for child in model.children_recursive() if isinstance(child, GeometryItem)
    }


@pytest.fixture(scope="module")
def both() -> tuple[dict[str, GeometryItem], dict[str, GeometryItem]]:
    source = GeometryModel("source")
    source.io.read_esatan_erg(SOURCE, on_diagnostic=lambda _note: None)
    converted = GeometryModel("converted")
    converted.io.read_steptas(CONVERTED, on_diagnostic=lambda _note: None)
    return items(source), items(converted)


def shared(both: tuple[dict[str, GeometryItem], ...]) -> list[str]:
    source, converted = both
    return sorted(set(source) & set(converted))


def test_the_two_readings_hold_the_same_surfaces(
    both: tuple[dict[str, GeometryItem], dict[str, GeometryItem]],
) -> None:
    """Same count, and the same names but for the groups that were split."""
    source, converted = both
    assert len(source) == len(converted)
    only_source = {name for name in source if name not in converted}
    only_converted = {name for name in converted if name not in source}
    assert all(name.startswith(SPLIT_GROUPS) for name in only_source | only_converted)


def test_every_surface_has_the_same_area_either_way(
    both: tuple[dict[str, GeometryItem], dict[str, GeometryItem]],
) -> None:
    """The one check that catches a misread parametrisation of any shape."""
    source, converted = both
    for name in shared(both):
        if name == REBOUND:
            continue
        expected = source[name].primitive.surface_area()
        assert converted[name].primitive.surface_area() == pytest.approx(expected, rel=TOLERANCE), (
            name
        )


def test_a_split_group_keeps_the_same_faces_under_other_names(
    both: tuple[dict[str, GeometryItem], dict[str, GeometryItem]],
) -> None:
    """A box is six rectangles either way; only which corner starts each differs."""
    source, converted = both
    for prefix in SPLIT_GROUPS:
        areas = [
            sorted(
                round(item.primitive.surface_area(), 12)
                for name, item in side.items()
                if name.startswith(prefix)
            )
            for side in (source, converted)
        ]
        assert areas[0] == pytest.approx(areas[1]), prefix


def test_every_surface_is_meshed_the_same_way_either_way(
    both: tuple[dict[str, GeometryItem], dict[str, GeometryItem]],
) -> None:
    source, converted = both
    for name in shared(both):
        first = source[name].thermal_mesh
        second = converted[name].thermal_mesh
        counts = (len(second.dir1_mesh) - 1, len(second.dir2_mesh) - 1)
        expected = REFINED.get(name)
        if expected is not None:
            assert counts == (expected[0] * 2, expected[1] * 2), name
            continue
        assert (len(first.dir1_mesh) - 1, len(first.dir2_mesh) - 1) == counts, name
        assert list(first.dir1_mesh) == pytest.approx(list(second.dir1_mesh)), name
        assert list(first.dir2_mesh) == pytest.approx(list(second.dir2_mesh)), name


def test_node_numbers_agree_wherever_both_readings_have_them(
    both: tuple[dict[str, GeometryItem], dict[str, GeometryItem]],
) -> None:
    """Each reading knows numbers the other does not, so both gaps are allowed.

    A surface whose ``nbase`` the source leaves to be assigned has no number to
    read out of it, while the export writes the number that was assigned.  In
    the other direction, a side that takes no part in the thermal model has its
    numbers dropped on export even though the source states them -- which is
    exactly the one surface named here.  Where both know, they must agree.
    """
    source, converted = both
    compared = 0
    dropped: list[str] = []
    for name in shared(both):
        if name in REFINED:
            continue
        for side in (1, 2):
            first = source[name].thermal_mesh
            second = converted[name].thermal_mesh
            start = getattr(first, f"node{side}_start")
            if start < 0:
                continue
            if getattr(second, f"node{side}_start") < 0:
                dropped.append(f"{name}:surface{side}")
                continue
            assert getattr(second, f"node{side}_start") == start, name
            assert getattr(second, f"node{side}_step") == getattr(first, f"node{side}_step"), name
            compared += 1
    assert compared > 20
    assert sorted(dropped) == UNNUMBERED_ON_EXPORT


def test_the_surface_built_from_a_redefined_variable_is_the_known_divergence(
    both: tuple[dict[str, GeometryItem], dict[str, GeometryItem]],
) -> None:
    """Pinned rather than skipped: the difference must stay the one explained.

    The cone's half-angle is 30 degrees where it is written and 45 by the end of
    the file, and the exported shape is the 45-degree one.  A cone of half-angle
    *t* between two heights has area proportional to ``sin(t) / cos(t)**2``, so
    the ratio the two readings differ by is that of the two angles -- and if it
    ever stops being that, the explanation above has stopped being true.
    """
    source, converted = both
    ratio = converted[REBOUND].primitive.surface_area() / source[REBOUND].primitive.surface_area()

    def reach(degrees: float) -> float:
        angle = math.radians(degrees)
        return math.sin(angle) / math.cos(angle) ** 2

    assert ratio == pytest.approx(reach(45.0) / reach(30.0), rel=1e-12)
