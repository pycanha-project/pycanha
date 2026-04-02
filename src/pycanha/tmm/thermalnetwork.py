"""Thermal network combining nodes and couplings."""

from __future__ import annotations

import pycanha_core as pcc

from .conductivecouplings import ConductiveCouplings
from .nodes import Nodes
from .radiativecouplings import RadiativeCouplings


class ThermalNetwork(pcc.tmm.ThermalNetwork):
    def __init__(
        self,
        nodes: Nodes | None = None,
        conductive: ConductiveCouplings | None = None,
        radiative: RadiativeCouplings | None = None,
    ) -> None:
        if nodes is None and (conductive is not None or radiative is not None):
            msg = "nodes must be provided when reusing coupling containers"
            raise ValueError(msg)

        nodes = nodes if nodes is not None else Nodes()
        conductive = conductive if conductive is not None else ConductiveCouplings(nodes)
        radiative = radiative if radiative is not None else RadiativeCouplings(nodes)

        if hasattr(conductive, "_nodes") and conductive._nodes is not nodes:
            msg = "conductive couplings must reference the same nodes container"
            raise ValueError(msg)
        if hasattr(radiative, "_nodes") and radiative._nodes is not nodes:
            msg = "radiative couplings must reference the same nodes container"
            raise ValueError(msg)

        self._nodes = nodes
        self._conductive = conductive
        self._radiative = radiative

        super().__init__(nodes, conductive, radiative)
