"""Material and color types (thin subclasses of the pycanha-core versions)."""

from __future__ import annotations

import pycanha_core as pcc


class Color(pcc.gmm.Color):
    """A 3-channel (RGB) color, 0-255 per channel."""


class BulkMaterial(pcc.gmm.BulkMaterial):
    """Structural / thermal bulk properties (density, conductivity, specific heat)."""


class OpticalMaterial(pcc.gmm.OpticalMaterial):
    """Thermo-optical surface properties (emissivity, absorptivity, ...)."""
