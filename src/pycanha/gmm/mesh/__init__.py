"""Mesh utilities subpackage.

Exposes :mod:`pycanha.gmm.mesh.ops` (the six mesh operations kept in 0.15).

.. note::
   The ``Edges`` class is intentionally deferred in pycanha-core 0.15 (build +
   inspect + visualize iteration) and is therefore not available here yet.
"""

from __future__ import annotations

from . import ops

__all__ = ["ops"]
