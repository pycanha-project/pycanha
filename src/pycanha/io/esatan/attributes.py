"""Single source of truth for the ESATAN node-attribute mapping.

ESATAN attribute names (case-insensitive; stored upper-case here) map to the
Python attribute on :class:`pycanha_core.tmm.Node`.  Everything else the parser
needs is derived from this one table:

* the ``Nodes`` setter is ``"set_" + python_attr`` (e.g. ``set_T``, ``set_qi``);
* the formula ``Entity`` factory is ``python_attr.lower()`` (e.g. ``Entity.t``,
  ``Entity.qi``), and exists only for the attributes the C++ formula engine can
  target (:data:`FORMULA_ENTITY_ATTRS`).
"""

from __future__ import annotations

from typing import Final

# ESATAN attribute (upper-case) -> Python attribute on pycanha_core.tmm.Node.
ESATAN_NODE_ATTRS: Final[dict[str, str]] = {
    "T": "T",
    "C": "C",
    "QI": "qi",
    "QS": "qs",
    "QA": "qa",
    "QE": "qe",
    "QR": "qr",
    "EPS": "eps",
    "ALP": "aph",
    "A": "a",
    "FX": "fx",
    "FY": "fy",
    "FZ": "fz",
}

# Attributes that can carry a formula (the engine has an Entity factory for them).
FORMULA_ENTITY_ATTRS: Final[frozenset[str]] = frozenset(
    {"T", "C", "QI", "QS", "QA", "QE", "QR"}
)
