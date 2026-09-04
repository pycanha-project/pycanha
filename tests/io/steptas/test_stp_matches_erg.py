"""A surface described in two formats has to come out the same either way.

The committed `.stp` and the corpus **overlap**; they are not the same model and
are not meant to become one.  The corpus grows with the ESATAN-TMS language, and
a construct that has no bearing on STEP-TAS still belongs in it; the `.stp` is
frozen and describes what it describes.  So the relation checked here is
one-directional -- every surface the `.stp` names is one the corpus names too,
and the two readings of it must agree.

That overlap is worth having because the two files state the same shapes in
almost entirely different terms -- one by parameters about a local origin, the
other by points and quantities in the model frame -- and the two readers reach
them through entirely separate tables.  Comparing them is the strongest check
available on either, and it is the check that found a cone parametrised wrongly
for every truncated cone.

Three differences are *expected* and are named below.  Anything else failing
means one of the two readers is wrong.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from pycanha.gmm import GeometryItem, GeometryModel

DATA = Path(__file__).resolve().parents[2] / "data" / "esatan"
CORPUS_ERG = DATA / "FEATURES.erg"
CORPUS_STP = DATA / "FEATURES.stp"

#: Areas match to this fraction; the shapes are rebuilt, not copied.
TOLERANCE = 1e-9

#: The one surface whose two readings are of two different shapes.
#:
#: Its half-angle is given as a variable that the file redefines further down.
#: A geometry file keeps the *reference*: the surface follows the variable, and
#: the shape the STEP-TAS form carries is the one the final value gives.
#: This reader evaluates where it reads and so builds the earlier one, reporting
#: the redefinition as it goes.
REBOUND = "SCS_CONE"

#: The one surface whose two readings are meshed differently.
#:
#: It asks for a finite-element mesh, which STEP-TAS has no form for.  What the
#: format does have is a face per node, so a finite-element surface arrives with
#: every face halved along both directions -- four faces where the `.erg` has
#: one, covering the same surface, each with a number of its own.
REFINED = {"DROPPED_ATTRS": (2, 2)}

#: The groups that arrive already split into flat faces, under the names the
#: STEP-TAS form gives them rather than the ones this reader invents.
SPLIT_GROUPS = ("SCS_BOX_", "PT_BOX_", "PT_PRISM_", "SCS_PRISM_")

#: How many surfaces the two files name alike, as a floor rather than a count.
#:
#: A ratchet: the corpus may add surfaces the frozen `.stp` knows nothing about,
#: and the number only goes up.  It going *down* means a surface stopped being
#: compared, which is the one thing this module exists to prevent.
SHARED_SURFACES = 51

#: The sides whose node numbers the `.erg` states and the STEP-TAS form omits.
#:
#: Two reasons, and no others: a side that is inactive takes no part in the
#: thermal model, and a cutting tool becomes a solid with no faces of its own at
#: all.  Neither has anything left to hang a number on.  Listed rather than
#: derived, so a surface joining them for a third reason has to be explained
#: before this passes again.
UNNUMBERED_IN_STEPTAS = [
    "ATTRS:surface2",
    "CONE_TOOL:surface1",
    "CYL_CUTTER:surface1",
    "SPHERE_TOOL:surface1",
]


def items(model: GeometryModel) -> dict[str, GeometryItem]:
    return {
        child.name: child for child in model.children_recursive() if isinstance(child, GeometryItem)
    }


@pytest.fixture(scope="module")
def both() -> tuple[dict[str, GeometryItem], dict[str, GeometryItem]]:
    in_erg = GeometryModel("in_erg")
    in_erg.io.read_esatan_erg(CORPUS_ERG, on_diagnostic=lambda _note: None)
    in_steptas = GeometryModel("in_steptas")
    in_steptas.io.read_steptas(CORPUS_STP, on_diagnostic=lambda _note: None)
    return items(in_erg), items(in_steptas)


def shared(both: tuple[dict[str, GeometryItem], ...]) -> list[str]:
    in_erg, in_steptas = both
    return sorted(set(in_erg) & set(in_steptas))


def test_the_stp_names_no_surface_the_corpus_has_lost(
    both: tuple[dict[str, GeometryItem], dict[str, GeometryItem]],
) -> None:
    """The overlap is the point, and it only ever loses surfaces one way.

    The corpus may carry surfaces the `.stp` does not -- that is what its being
    the wider of the two means.  The other direction is a defect: a surface the
    `.stp` names and the corpus does not is one the corpus dropped, and with it
    every comparison below that used to reach it.  The floor is the second half
    of the same guard: renaming the corpus's surfaces one at a time would
    satisfy the first assertion all the way down to comparing nothing.
    """
    in_erg, in_steptas = both
    only_steptas = {name for name in in_steptas if name not in in_erg}
    assert all(name.startswith(SPLIT_GROUPS) for name in only_steptas), sorted(only_steptas)
    assert len(shared(both)) >= SHARED_SURFACES


def test_every_surface_has_the_same_area_either_way(
    both: tuple[dict[str, GeometryItem], dict[str, GeometryItem]],
) -> None:
    """The one check that catches a misread parametrisation of any shape."""
    in_erg, in_steptas = both
    for name in shared(both):
        if name == REBOUND:
            continue
        expected = in_erg[name].primitive.surface_area()
        area = in_steptas[name].primitive.surface_area()
        assert area == pytest.approx(expected, rel=TOLERANCE), name


def test_a_split_group_keeps_the_same_faces_under_other_names(
    both: tuple[dict[str, GeometryItem], dict[str, GeometryItem]],
) -> None:
    """A box is six rectangles either way; only which corner starts each differs."""
    in_erg, in_steptas = both
    for prefix in SPLIT_GROUPS:
        areas = [
            sorted(
                round(item.primitive.surface_area(), 12)
                for name, item in side.items()
                if name.startswith(prefix)
            )
            for side in (in_erg, in_steptas)
        ]
        assert areas[0] == pytest.approx(areas[1]), prefix


def test_every_surface_is_meshed_the_same_way_either_way(
    both: tuple[dict[str, GeometryItem], dict[str, GeometryItem]],
) -> None:
    in_erg, in_steptas = both
    for name in shared(both):
        first = in_erg[name].thermal_mesh
        second = in_steptas[name].thermal_mesh
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

    A surface whose ``nbase`` the `.erg` leaves to be assigned has no number to
    read out of it, while the STEP-TAS form carries the number that was
    assigned.  In the other direction, a side that takes no part in the thermal
    model has its numbers dropped in STEP-TAS even though the `.erg` states
    them -- which is exactly the one surface named here.  Where both know, they
    must agree.
    """
    in_erg, in_steptas = both
    compared = 0
    dropped: list[str] = []
    for name in shared(both):
        if name in REFINED:
            continue
        for side in (1, 2):
            first = in_erg[name].thermal_mesh
            second = in_steptas[name].thermal_mesh
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
    assert sorted(dropped) == UNNUMBERED_IN_STEPTAS


def test_the_surface_built_from_a_redefined_variable_is_the_known_divergence(
    both: tuple[dict[str, GeometryItem], dict[str, GeometryItem]],
) -> None:
    """Pinned rather than skipped: the difference must stay the one explained.

    The cone's half-angle is 30 degrees where it is written and 45 by the end of
    the file, and the STEP-TAS shape is the 45-degree one.  A cone of half-angle
    *t* between two heights has area proportional to ``sin(t) / cos(t)**2``, so
    the ratio the two readings differ by is that of the two angles -- and if it
    ever stops being that, the explanation above has stopped being true.
    """
    in_erg, in_steptas = both
    ratio = in_steptas[REBOUND].primitive.surface_area() / in_erg[REBOUND].primitive.surface_area()

    def reach(degrees: float) -> float:
        angle = math.radians(degrees)
        return math.sin(angle) / math.cos(angle) ** 2

    assert ratio == pytest.approx(reach(45.0) / reach(30.0), rel=1e-12)
