"""Tests for the parse-time ESATAN intrinsic implementations."""

from __future__ import annotations

import numpy as np
import pytest

from pycanha.io.esatan.intrinsics import INTRINSIC_NAMES, INTRINSIC_REGISTRY


@pytest.fixture
def cp_table() -> np.ndarray:
    # Linear ramp 1000 -> 1100 between T=0 and T=100.
    return np.array([[0.0, 1000.0], [100.0, 1100.0]])


@pytest.fixture
def two_column_table() -> np.ndarray:
    # Two value columns so we can exercise idx = 1 and idx = 2.
    return np.array(
        [
            [0.0, 1.0, 10.0],
            [100.0, 2.0, 20.0],
        ]
    )


def test_known_intrinsic_names() -> None:
    assert "INTRP1" in INTRINSIC_NAMES
    assert "NODFN1" in INTRINSIC_NAMES
    assert "CNDFN1" in INTRINSIC_NAMES
    assert "TAV" in INTRINSIC_NAMES


def test_intrp1(cp_table: np.ndarray) -> None:
    fn = INTRINSIC_REGISTRY["INTRP1"]
    assert fn([25.0, cp_table, 1], {}) == pytest.approx(1025.0)
    assert fn([0.0, cp_table, 1], {}) == pytest.approx(1000.0)
    assert fn([100.0, cp_table, 1], {}) == pytest.approx(1100.0)


def test_intrp1_clamps_outside_range(cp_table: np.ndarray) -> None:
    # numpy.interp clamps to endpoints by default.
    fn = INTRINSIC_REGISTRY["INTRP1"]
    assert fn([-50.0, cp_table, 1], {}) == pytest.approx(1000.0)
    assert fn([200.0, cp_table, 1], {}) == pytest.approx(1100.0)


def test_intrp1_index_out_of_range(cp_table: np.ndarray) -> None:
    fn = INTRINSIC_REGISTRY["INTRP1"]
    with pytest.raises(IndexError):
        fn([25.0, cp_table, 2], {})


def test_intrp1_picks_correct_column(two_column_table: np.ndarray) -> None:
    fn = INTRINSIC_REGISTRY["INTRP1"]
    assert fn([50.0, two_column_table, 1], {}) == pytest.approx(1.5)
    assert fn([50.0, two_column_table, 2], {}) == pytest.approx(15.0)


def test_nodfn1_is_intrp1_alias(cp_table: np.ndarray) -> None:
    assert INTRINSIC_REGISTRY["NODFN1"]([25.0, cp_table, 1], {}) == pytest.approx(1025.0)


def test_cndfn1(cp_table: np.ndarray) -> None:
    fn = INTRINSIC_REGISTRY["CNDFN1"]
    # Average T1=0, T2=50 -> 25; same as INTRP1(25, ...) = 1025.
    assert fn([0.0, 50.0, cp_table, 1], {}) == pytest.approx(1025.0)


def test_tav() -> None:
    fn = INTRINSIC_REGISTRY["TAV"]
    assert fn([10.0, 20.0], {}) == pytest.approx(15.0)


def test_intrinsic_registry_resolves_array_by_name(cp_table: np.ndarray) -> None:
    arrays = {"Cp_DUT": cp_table}
    assert INTRINSIC_REGISTRY["INTRP1"]([25.0, "Cp_DUT", 1], arrays) == pytest.approx(1025.0)


def test_intrp2_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        INTRINSIC_REGISTRY["INTRP2"]([], {})
