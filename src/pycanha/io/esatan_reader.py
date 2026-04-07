"""ESATAN TMD readers backed by either pycanha-core or h5py."""

# pyright: reportMissingTypeStubs=false

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np
import pycanha_core as pcc

if TYPE_CHECKING:
    from pycanha.tmm.thermalmathematicalmodel import ThermalMathematicalModel

_KELVIN_OFFSET: Final[float] = 273.15
_ANALYSIS_GROUP: Final[str] = "AnalysisSet1"
_DATA_GROUP: Final[str] = "DataGroup1"
_NODE_ATTRIBUTE_INDICES: Final[dict[str, int]] = {
    "T": 0,
    "C": 1,
    "qa": 2,
    "qe": 3,
    "qi": 4,
    "qr": 5,
    "qs": 6,
    "a": 7,
    "aph": 8,
    "eps": 9,
    "fx": 13,
    "fy": 14,
    "fz": 15,
}


class ESATANReader:
    def __init__(self, model: ThermalMathematicalModel) -> None:
        self._model = model
        self._logger = pcc.get_python_logger()

    def read_tmd(
        self,
        filepath: str | Path,
        engine: str = "cpp",
        verbose: bool = False,
    ) -> None:
        path = Path(filepath)

        if engine == "cpp":
            self._read_tmd_cpp(path, verbose=verbose)
            return
        if engine == "python":
            self._read_tmd_python(path, verbose=verbose)
            return

        msg = f"Unsupported ESATAN reader engine: {engine!r}"
        raise ValueError(msg)

    def _read_tmd_cpp(self, filepath: Path, *, verbose: bool) -> None:
        reader = pcc.tmm.ESATANReader(self._model)
        reader.verbose = verbose
        if verbose:
            self._logger.info(f"Reading ESATAN TMD with C++ engine: {filepath}")
        reader.read_tmd(str(filepath))

    def _read_tmd_python(self, filepath: Path, *, verbose: bool) -> None:
        import h5py  # type: ignore[import-untyped]

        if verbose:
            self._logger.info(f"Reading ESATAN TMD with Python engine: {filepath}")

        with h5py.File(filepath, "r") as handle:
            analysis_group = handle[_ANALYSIS_GROUP]
            data_group = analysis_group[_DATA_GROUP]

            node_numbers_with_inactive = np.asarray(analysis_group["thermalNodes"])[:, 0]
            node_real_data = np.asarray(data_group["thermalNodesRealData"])[0]
            node_string_data = np.asarray(data_group["thermalNodesStringData"])[0]
            node_types = node_string_data[:, 0].astype("U")

            active_node_mask = node_types != "X"
            active_node_numbers = node_numbers_with_inactive[active_node_mask]
            active_node_types = node_types[active_node_mask]
            active_node_real_data = node_real_data[active_node_mask]

            if verbose:
                inactive_numbers = node_numbers_with_inactive[~active_node_mask]
                self._logger.info(
                    "Loaded ESATAN node table: "
                    f"{active_node_numbers.size} active, {inactive_numbers.size} inactive"
                )

            self._add_nodes(active_node_numbers, active_node_types, active_node_real_data)
            self._add_conductive_couplings(analysis_group, data_group, active_node_mask)
            self._add_radiative_couplings(analysis_group, data_group, active_node_mask)

    def _add_nodes(
        self,
        node_numbers: np.ndarray,
        node_types: np.ndarray,
        node_real_data: np.ndarray,
    ) -> None:
        for node_number, node_type, node_values in zip(
            node_numbers,
            node_types,
            node_real_data,
            strict=True,
        ):
            node = pcc.tmm.Node(int(node_number))
            if node_type == "B":
                node.type = pcc.NodeType.BOUNDARY

            for attribute_name, attribute_index in _NODE_ATTRIBUTE_INDICES.items():
                value = float(node_values[attribute_index])
                if attribute_name == "T":
                    value += _KELVIN_OFFSET
                setattr(node, attribute_name, value)

            self._model.add_node(node)

    def _add_conductive_couplings(
        self,
        analysis_group: Any,
        data_group: Any,
        active_node_mask: np.ndarray,
    ) -> None:
        node_numbers = np.asarray(analysis_group["thermalNodes"])[:, 0]
        pair_indices = np.asarray(analysis_group["conductorsGL"])[:, :2] - 1
        values = np.asarray(data_group["conductorDataGL"])[0, :, 0]

        valid_pair_mask = (
            active_node_mask[pair_indices[:, 0]] & active_node_mask[pair_indices[:, 1]]
        )
        for (idx_1, idx_2), value in zip(
            pair_indices[valid_pair_mask],
            values[valid_pair_mask],
            strict=True,
        ):
            self._add_sum_conductive_coupling(
                int(node_numbers[idx_1]),
                int(node_numbers[idx_2]),
                float(value),
            )

    def _add_radiative_couplings(
        self,
        analysis_group: Any,
        data_group: Any,
        active_node_mask: np.ndarray,
    ) -> None:
        node_numbers = np.asarray(analysis_group["thermalNodes"])[:, 0]
        pair_indices = np.asarray(analysis_group["conductorsGR"])[:, :2] - 1
        values = np.asarray(data_group["conductorDataGR"])[0, :, 0]

        valid_pair_mask = (
            active_node_mask[pair_indices[:, 0]] & active_node_mask[pair_indices[:, 1]]
        )
        for (idx_1, idx_2), value in zip(
            pair_indices[valid_pair_mask],
            values[valid_pair_mask],
            strict=True,
        ):
            self._model.radiative_couplings.add_coupling(
                int(node_numbers[idx_1]),
                int(node_numbers[idx_2]),
                float(value),
            )

    def _add_sum_conductive_coupling(
        self,
        node_1: int,
        node_2: int,
        value: float,
    ) -> None:
        couplings = self._model.conductive_couplings
        add_sum_coupling = getattr(couplings, "add_sum_coupling", None)
        if callable(add_sum_coupling):
            add_sum_coupling(node_1, node_2, value)
            return

        try:
            current_value = float(couplings.get_coupling_value(node_1, node_2))
        except Exception:
            couplings.add_coupling(node_1, node_2, value)
            return

        couplings.set_coupling_value(node_1, node_2, current_value + value)
