"""Transient ESATAN TMD reads (time-dependent output series).

Mirrors pycanha-core test/unit/tmm/test_esatan_reader.cpp using the DISC
transient fixture re-synced from the C++ test data.
"""

from pathlib import Path

import numpy as np
import pytest

import pycanha as pc

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "data" / "esatan" / "DISC"
TRANSIENT_FIXTURE = FIXTURE_ROOT / "DISCTR_TRANSIENT.TMD"


def test_read_tmd_transient_imports_default_attributes() -> None:
    model = pc.ThermalModel.from_esatan_tmd(str(TRANSIENT_FIXTURE), name="disc")
    assert model.tmm.nodes.num_nodes == 102

    node_numbers = model.tmm.read_tmd_transient(str(TRANSIENT_FIXTURE), "transient")
    assert len(node_numbers) == 103

    models = model.tmm.thermal_data.models
    assert models.has_model("transient")
    data_model = models.get_model("transient")
    assert data_model.T.num_columns == len(node_numbers)
    assert data_model.T.num_timesteps > 1


def test_read_tmd_transient_temperature_matches_import_first_step() -> None:
    # Mirror the C++ reader test: the node temperatures imported from the
    # transient TMD equal the first timestep of the transient series.
    model = pc.ThermalModel.from_esatan_tmd(str(TRANSIENT_FIXTURE), name="disc")
    imported_temperatures = {
        model.tmm.nodes.get_node_num_from_idx(index): model.tmm.nodes.get_node_from_idx(index).T
        for index in range(model.tmm.nodes.num_nodes)
    }

    node_numbers = model.tmm.read_tmd_transient(str(TRANSIENT_FIXTURE), "transient")
    temperature_series = np.asarray(model.tmm.thermal_data.models.get_model("transient").T.values)

    first_step = temperature_series[0, :]
    for column, node_number in enumerate(node_numbers):
        if node_number in imported_temperatures:
            assert first_step[column] == pytest.approx(imported_temperatures[node_number], abs=1e-3)


def test_read_tmd_transient_only_requested_attributes() -> None:
    model = pc.ThermalModel.from_esatan_tmd(str(TRANSIENT_FIXTURE), name="disc")
    node_numbers = model.tmm.read_tmd_transient(
        str(TRANSIENT_FIXTURE),
        "single",
        attributes=[pc.tmm.DataModelAttribute.T],
    )
    assert node_numbers

    data_model = model.tmm.thermal_data.models.get_model("single")
    assert data_model.T.num_timesteps > 0
    assert data_model.QS.num_timesteps == 0
