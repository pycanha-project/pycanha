from pathlib import Path

import pycanha as pc

FIXTURE = Path(__file__).resolve().parents[1] / "data" / "esatan" / "DISCTR_TRANSIENT.TMD"


def test_from_esatan_tmd_builds_model() -> None:
    tmm = pc.tmm.ThermalMathematicalModel.from_esatan_tmd(str(FIXTURE), name="disc")

    assert isinstance(tmm, pc.tmm.ThermalMathematicalModel)
    assert tmm.name == "disc"
    assert tmm.nodes.num_nodes == 102
    assert tmm.nodes.num_diff_nodes == 100
    assert tmm.nodes.num_bound_nodes == 2


def test_read_tmd_populates_existing_model() -> None:
    tmm = pc.tmm.ThermalMathematicalModel("existing")

    tmm.read_tmd(str(FIXTURE))

    assert tmm.name == "existing"
    assert tmm.nodes.num_nodes == 102


def test_load_tmd_returns_self() -> None:
    tmm = pc.tmm.ThermalMathematicalModel("existing")

    returned = tmm.load_tmd(str(FIXTURE))

    assert returned is tmm
    assert tmm.nodes.num_nodes == 102
