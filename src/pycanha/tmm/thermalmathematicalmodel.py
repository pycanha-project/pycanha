"""Top-level Thermal Mathematical Model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import numpy as np
import pycanha_core as pcc

from pycanha.io import ESATANReader
from pycanha.parameters.formulas import Formulas
from pycanha.parameters.parameters import Parameters
from pycanha.tmm.conductivecouplings import ConductiveCouplings
from pycanha.tmm.nodes import Nodes
from pycanha.tmm.radiativecouplings import RadiativeCouplings
from pycanha.tmm.thermaldata import ThermalData
from pycanha.tmm.thermalnetwork import ThermalNetwork

if TYPE_CHECKING:
    from collections.abc import Sequence

    import numpy.typing as npt

InterpolationMethod = pcc.tmm.InterpolationMethod
ExtrapolationMethod = pcc.tmm.ExtrapolationMethod


def _as_1d(values: npt.ArrayLike) -> npt.NDArray[np.float64]:
    array = np.ascontiguousarray(values, dtype=np.float64)
    if array.ndim != 1:
        msg = f"expected a 1-D sequence, got shape {array.shape}"
        raise ValueError(msg)
    return array


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
        network = ThermalNetwork(nodes, conductive, radiative)
        formulas = formulas if formulas is not None else Formulas(network, parameters)
        thermal_data = thermal_data if thermal_data is not None else ThermalData(network)

        if hasattr(conductive, "_nodes") and conductive._nodes is not nodes:
            msg = "conductive couplings must reference the same nodes container"
            raise ValueError(msg)
        if hasattr(radiative, "_nodes") and radiative._nodes is not nodes:
            msg = "radiative couplings must reference the same nodes container"
            raise ValueError(msg)

        self._nodes = nodes
        self._conductive = conductive
        self._radiative = radiative
        self._network = network
        self._parameters = parameters
        self._formulas = formulas
        self._thermal_data = thermal_data

        formulas.associate(network, parameters)
        thermal_data.associate(network)

        super().__init__(
            name,
            network,
            parameters,
            formulas,
            thermal_data,
        )

        self._root_model: object = self
        self._formulas._bind_model(self)

    def _set_root_model(self, root_model: object) -> None:
        self._root_model = root_model
        self._formulas._bind_model(self, root_model)

    def read_tmd(
        self,
        filepath: str,
        verbose: bool = False,
        **kwargs: object,
    ) -> None:
        engine = kwargs.pop("engine", "cpp")
        if kwargs:
            unexpected = ", ".join(sorted(kwargs))
            msg = f"Unexpected keyword arguments: {unexpected}"
            raise TypeError(msg)

        if not isinstance(engine, str):
            msg = "engine must be a string"
            raise TypeError(msg)

        ESATANReader(self).read_tmd(filepath, engine=engine, verbose=verbose)

    def load_tmd(
        self,
        filepath: str,
        *,
        engine: str = "cpp",
        verbose: bool = False,
    ) -> Self:
        self.read_tmd(filepath, engine=engine, verbose=verbose)
        return self

    def add_time_variable(
        self,
        name: str,
        x_data: npt.ArrayLike,
        y_data: npt.ArrayLike,
        interpolation: InterpolationMethod = InterpolationMethod.LINEAR,
        extrapolation: ExtrapolationMethod = ExtrapolationMethod.CONSTANT,
    ) -> None:
        """Add a time-driven variable from a lookup table of time.

        Accepts any array-like for ``x_data`` / ``y_data`` (coerced to float64).
        """
        super().add_time_variable(
            name, _as_1d(x_data), _as_1d(y_data), interpolation, extrapolation
        )

    def add_temperature_variable(
        self,
        name: str,
        x_data: npt.ArrayLike,
        y_data: npt.ArrayLike,
        interpolation: InterpolationMethod = InterpolationMethod.LINEAR,
        extrapolation: ExtrapolationMethod = ExtrapolationMethod.CONSTANT,
    ) -> None:
        """Add a temperature-driven variable from a lookup table of temperature.

        Accepts any array-like for ``x_data`` / ``y_data`` (coerced to float64).
        """
        super().add_temperature_variable(
            name, _as_1d(x_data), _as_1d(y_data), interpolation, extrapolation
        )

    def read_tmd_transient(
        self,
        filepath: str,
        model_name: str = "transient",
        *,
        overwrite: bool = False,
        attributes: Sequence[pcc.tmm.DataModelAttribute] | None = None,
    ) -> list[int]:
        """Read ESATAN TMD transient results into a named DataModel.

        Returns the list of node numbers found in the file.
        """
        thermal_data = self.thermal_data
        if attributes is None:
            return pcc.tmm.read_tmd_transient(filepath, thermal_data, model_name, overwrite)
        return pcc.tmm.read_tmd_transient(
            filepath, thermal_data, model_name, overwrite, list(attributes)
        )

    @classmethod
    def from_esatan_tmd(
        cls,
        filepath: str,
        name: str = "",
        *,
        engine: str = "cpp",
        verbose: bool = False,
    ) -> Self:
        model = cls(name=name)
        return model.load_tmd(filepath, engine=engine, verbose=verbose)
