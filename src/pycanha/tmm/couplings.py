"""Generic coupling collection."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pycanha_core as pcc

if TYPE_CHECKING:
    from .nodes import Nodes


class Couplings(pcc.tmm.Couplings):
    def __init__(self, nodes: Nodes) -> None:
        self._nodes = nodes
        super().__init__(nodes)
