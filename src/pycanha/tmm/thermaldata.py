"""Thermal data storage for simulation results."""

from __future__ import annotations

import pycanha_core as pcc


class ThermalData(pcc.tmm.ThermalData):
    def __init__(self, network: pcc.tmm.ThermalNetwork | None = None) -> None:
        if network is None:
            super().__init__()
        else:
            super().__init__(network)
