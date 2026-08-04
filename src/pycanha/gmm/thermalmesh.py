"""Per-primitive thermal discretization.

UV cuts + per-side properties + tmm-node assignment. Constructed either empty
(default unit square) or directly from the two UV cut vectors, e.g.
``ThermalMesh([0.0, 0.5, 1.0], [0.0, 1.0])``.

Adds nothing on top of the pycanha-core version, so it is re-exported rather
than subclassed: an empty subclass would not match the objects the core
hands back.
"""

from __future__ import annotations

import pycanha_core as pcc

ThermalMesh = pcc.gmm.ThermalMesh
