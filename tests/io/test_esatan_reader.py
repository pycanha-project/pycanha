from pathlib import Path

import pytest

import pycanha as pc

FIXTURE = Path(__file__).resolve().parents[1] / "data" / "esatan" / "DISCTR_TRANSIENT.TMD"


@pytest.mark.parametrize("engine", ["cpp", "python"])
def test_esatan_reader_populates_model(engine: str) -> None:
    tmm = pc.tmm.ThermalMathematicalModel(f"reader-{engine}")
    reader = pc.io.ESATANReader(tmm)

    reader.read_tmd(str(FIXTURE), engine=engine, verbose=False)

    assert tmm.nodes.num_nodes == 102
    assert tmm.nodes.num_diff_nodes == 100
    assert tmm.nodes.num_bound_nodes == 2
    assert tmm.nodes.get_T(1000) == pytest.approx(263.15)


def test_esatan_reader_rejects_unknown_engine() -> None:
    tmm = pc.tmm.ThermalMathematicalModel("reader-invalid")
    reader = pc.io.ESATANReader(tmm)

    with pytest.raises(ValueError, match="Unsupported ESATAN reader engine"):
        reader.read_tmd(str(FIXTURE), engine="invalid", verbose=False)
