"""Per-primitive thermal discretization.

UV cuts + per-side properties + tmm-node assignment. Constructed either empty
(default unit square) or directly from the two UV cut vectors, e.g.
``ThermalMesh([0.0, 0.5, 1.0], [0.0, 1.0])``.

Adds nothing on top of the pycanha-core version, so it is re-exported rather
than subclassed: an empty subclass would not match the objects the core
hands back.

A mesh carries one :class:`ActiveSide` per calculation --
``radiative_active_side`` and ``conductive_active_side`` -- so a surface can
take part in one and not the other. The helpers here convert between a
selector and the pair of per-side booleans that file formats tend to store.
"""

from __future__ import annotations

import pycanha_core as pcc

ThermalMesh = pcc.gmm.ThermalMesh

#: Which of a mesh's two sides take part in one calculation.
ActiveSide = pcc.gmm.ActiveSide

_SELECTORS: dict[tuple[bool, bool], pcc.gmm.ActiveSide] = {
    (False, False): ActiveSide.NONE,
    (True, False): ActiveSide.SIDE1,
    (False, True): ActiveSide.SIDE2,
    (True, True): ActiveSide.BOTH,
}

_SIDES: dict[pcc.gmm.ActiveSide, tuple[bool, bool]] = {
    selector: sides for sides, selector in _SELECTORS.items()
}


def active_side(*, side1: bool, side2: bool) -> pcc.gmm.ActiveSide:
    """The selector naming exactly the sides that are active."""
    return _SELECTORS[side1, side2]


def active_sides(selector: pcc.gmm.ActiveSide) -> tuple[bool, bool]:
    """A selector as ``(side 1 active, side 2 active)``."""
    return _SIDES[selector]


def with_side(selector: pcc.gmm.ActiveSide, side: int, *, active: bool) -> pcc.gmm.ActiveSide:
    """``selector`` with one side switched on or off, the others untouched.

    Sides are numbered 1 and 2, as everywhere else on a mesh.
    """
    if side not in (1, 2):
        msg = f"side must be 1 or 2, not {side}"
        raise ValueError(msg)
    sides = list(active_sides(selector))
    sides[side - 1] = active
    return active_side(side1=sides[0], side2=sides[1])
