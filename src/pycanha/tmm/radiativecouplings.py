"""Radiative coupling collection."""

from __future__ import annotations

import pycanha_core as pcc

from .nodes import Nodes


class RadiativeCouplings(pcc.tmm.RadiativeCouplings):
    def __init__(self, nodes: Nodes) -> None:
        self._nodes = nodes
        super().__init__(nodes)
