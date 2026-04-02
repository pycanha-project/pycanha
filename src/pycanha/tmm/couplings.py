"""Generic coupling collection."""

from __future__ import annotations

import pycanha_core as pcc

from .nodes import Nodes


class Couplings(pcc.tmm.Couplings):
    def __init__(self, nodes: Nodes) -> None:
        self._nodes = nodes
        super().__init__(nodes)
