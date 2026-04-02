"""Conductive coupling collection."""

from __future__ import annotations

import pycanha_core as pcc

from .nodes import Nodes


class ConductiveCouplings(pcc.tmm.ConductiveCouplings):
    def __init__(self, nodes: Nodes) -> None:
        self._nodes = nodes
        super().__init__(nodes)
