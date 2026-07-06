"""Per-primitive thermal discretization (thin subclass of pycanha-core)."""

from __future__ import annotations

import pycanha_core as pcc


class ThermalMesh(pcc.gmm.ThermalMesh):
    """UV cuts + per-side properties + tmm-node assignment.

    Constructed either empty (default unit square) or directly from the two UV
    cut vectors, e.g. ``ThermalMesh([0.0, 0.5, 1.0], [0.0, 1.0])``.
    """
