"""Converting between an ``ActiveSide`` and the pair of sides it names.

A mesh states activity as one selector per calculation; every file format
states it as something else -- two words, or one enumeration covering only half
the question.  These helpers are the hinge between the two, so they are worth
pinning independently of any one format.

What the selectors *mean* is the core's own business and is tested there.  What
is tested here is that the two calculations stay independent through the
conversions, because collapsing them is the failure mode that reads as
plausible.
"""

from __future__ import annotations

import pytest

from pycanha.gmm import ActiveSide, ThermalMesh, active_side, active_sides, with_side

PAIRS = [
    (ActiveSide.NONE, (False, False)),
    (ActiveSide.SIDE1, (True, False)),
    (ActiveSide.SIDE2, (False, True)),
    (ActiveSide.BOTH, (True, True)),
]


@pytest.mark.parametrize(("selector", "sides"), PAIRS)
def test_a_selector_and_its_pair_of_sides_convert_both_ways(
    selector: ActiveSide, sides: tuple[bool, bool]
) -> None:
    assert active_side(side1=sides[0], side2=sides[1]) is selector
    assert active_sides(selector) == sides


@pytest.mark.parametrize(("selector", "_sides"), PAIRS)
@pytest.mark.parametrize("side", [1, 2])
@pytest.mark.parametrize("active", [True, False])
def test_switching_one_side_leaves_the_other_alone(
    selector: ActiveSide, _sides: tuple[bool, bool], side: int, *, active: bool
) -> None:
    before = active_sides(selector)
    after = active_sides(with_side(selector, side, active=active))
    assert after[side - 1] is active
    other = 2 if side == 1 else 1
    assert after[other - 1] is before[other - 1]


def test_a_side_that_is_neither_one_nor_two_is_refused() -> None:
    with pytest.raises(ValueError, match="side must be 1 or 2"):
        with_side(ActiveSide.BOTH, 3, active=True)


def test_the_two_calculations_are_independent_on_a_mesh() -> None:
    """The state ESATAN calls "Conductive": conducting without radiating."""
    mesh = ThermalMesh()
    mesh.radiative_active_side = ActiveSide.NONE
    mesh.conductive_active_side = ActiveSide.SIDE1

    assert mesh.is_radiative_active(1) is False
    assert mesh.is_conductive_active(1) is True
    # Either one makes the side "active" in the general sense.
    assert mesh.is_side_active(1) is True
    assert mesh.is_side_active(2) is False
