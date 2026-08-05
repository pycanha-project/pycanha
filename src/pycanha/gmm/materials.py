"""Material and color types.

These add nothing on top of the pycanha-core versions, so they are re-exported
rather than subclassed: an object handed back by the core is then already an
instance of the ``pycanha.gmm`` name, which an empty subclass would not be.
"""

from __future__ import annotations

import pycanha_core as pcc

#: A 3-channel (RGB) color, 0-255 per channel.
Color = pcc.gmm.Color

#: Structural / thermal bulk properties (density, conductivity, specific heat).
BulkMaterial = pcc.gmm.BulkMaterial

#: Thermo-optical surface properties (emissivity, absorptivity, ...).
OpticalMaterial = pcc.gmm.OpticalMaterial
