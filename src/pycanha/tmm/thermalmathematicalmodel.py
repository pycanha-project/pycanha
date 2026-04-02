"""Top-level Thermal Mathematical Model."""

from __future__ import annotations

from typing import Self

import pycanha_core as pcc

from pycanha.parameters.formulas import Formulas
from pycanha.parameters.parameters import Parameters
from pycanha.tmm.conductivecouplings import ConductiveCouplings
from pycanha.tmm.nodes import Nodes
from pycanha.tmm.radiativecouplings import RadiativeCouplings
from pycanha.tmm.thermaldata import ThermalData


class ThermalMathematicalModel(pcc.tmm.ThermalMathematicalModel):
    def __init__(
        self,
        name: str = "",
        nodes: Nodes | None = None,
        conductive: ConductiveCouplings | None = None,
        radiative: RadiativeCouplings | None = None,
        parameters: Parameters | None = None,
        formulas: Formulas | None = None,
        thermal_data: ThermalData | None = None,
    ) -> None:
        if nodes is None and (conductive is not None or radiative is not None):
            msg = "nodes must be provided when reusing coupling containers"
            raise ValueError(msg)

        nodes = nodes if nodes is not None else Nodes()
        conductive = conductive if conductive is not None else ConductiveCouplings(nodes)
        radiative = radiative if radiative is not None else RadiativeCouplings(nodes)
        parameters = parameters if parameters is not None else Parameters()
        formulas = formulas if formulas is not None else Formulas()
        thermal_data = thermal_data if thermal_data is not None else ThermalData()

        if hasattr(conductive, "_nodes") and conductive._nodes is not nodes:
            msg = "conductive couplings must reference the same nodes container"
            raise ValueError(msg)
        if hasattr(radiative, "_nodes") and radiative._nodes is not nodes:
            msg = "radiative couplings must reference the same nodes container"
            raise ValueError(msg)

        self._nodes = nodes
        self._conductive = conductive
        self._radiative = radiative
        self._parameters = parameters
        self._formulas = formulas
        self._thermal_data = thermal_data

        super().__init__(
            name,
            nodes,
            conductive,
            radiative,
            parameters,
            formulas,
            thermal_data,
        )

    def load_tmd(self, filepath: str, *, verbose: bool = False) -> Self:
        super().read_tmd(filepath, verbose=verbose)
        return self

    @classmethod
    def from_esatan_tmd(
        cls,
        filepath: str,
        name: str = "",
        *,
        verbose: bool = False,
    ) -> Self:
        model = cls(name=name)
        return model.load_tmd(filepath, verbose=verbose)
