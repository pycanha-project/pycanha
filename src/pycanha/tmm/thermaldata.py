"""Thermal data storage for simulation results."""

from __future__ import annotations

import numpy as np
import pycanha_core as pcc


class ThermalData(pcc.tmm.ThermalData):
    def __init__(self, network: pcc.tmm.ThermalNetwork | None = None) -> None:
        if network is None:
            super().__init__()
        else:
            super().__init__(network)

    def has_table(self, name: str) -> bool:
        return self.has_dense_time_series(name)

    def get_table(self, name: str) -> np.ndarray:
        series = self.get_dense_time_series(name)
        values = np.asarray(series.values)
        if values.ndim == 1:
            values = values[:, np.newaxis]
        return np.column_stack((np.asarray(series.times), values))

    def remove_table(self, name: str) -> None:
        self.remove_dense_time_series(name)
