"""Radiative coupling collection."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pycanha_core as pcc

if TYPE_CHECKING:
    from .nodes import Nodes


class RadiativeCouplings(pcc.tmm.RadiativeCouplings):
    def __init__(self, nodes: Nodes) -> None:
        self._nodes = nodes
        super().__init__(nodes)
