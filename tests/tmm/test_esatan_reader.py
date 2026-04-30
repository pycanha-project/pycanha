from pathlib import Path

import pytest

import pycanha as pc

FIXTURE = Path(__file__).resolve().parents[1] / "data" / "esatan" / "DISCTR_TRANSIENT.TMD"


@pytest.mark.parametrize("engine", ["cpp", "python"])
def test_from_esatan_tmd_builds_model(engine: str) -> None:
    model = pc.ThermalModel.from_esatan_tmd(
        str(FIXTURE),
        name="disc",
        engine=engine,
    )

    assert isinstance(model, pc.ThermalModel)
    assert model.name == "disc"
    assert model.tmm.nodes.num_nodes == 102
    assert model.tmm.nodes.num_diff_nodes == 100
    assert model.tmm.nodes.num_bound_nodes == 2


@pytest.mark.parametrize("engine", ["cpp", "python"])
def test_read_tmd_populates_existing_model(engine: str) -> None:
    model = pc.ThermalModel("existing")

    model.read_tmd(str(FIXTURE), engine=engine)

    assert model.name == "existing"
    assert model.tmm.nodes.num_nodes == 102


@pytest.mark.parametrize("engine", ["cpp", "python"])
def test_load_tmd_returns_self(engine: str) -> None:
    model = pc.ThermalModel("existing")

    returned = model.load_tmd(str(FIXTURE), engine=engine)

    assert returned is model
    assert model.tmm.nodes.num_nodes == 102
