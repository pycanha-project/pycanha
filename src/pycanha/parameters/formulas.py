"""Formula collection managed by a thermal model."""

from __future__ import annotations

import pycanha_core as pcc


class Formulas(pcc.parameters.Formulas):
    def __init__(
        self,
        network: pcc.tmm.ThermalNetwork | None = None,
        parameters: pcc.parameters.Parameters | None = None,
    ) -> None:
        if (network is None) != (parameters is None):
            msg = "network and parameters must be provided together"
            raise ValueError(msg)

        if network is None:
            super().__init__()
        else:
            assert parameters is not None
            super().__init__(network, parameters)
