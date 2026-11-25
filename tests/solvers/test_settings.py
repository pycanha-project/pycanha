"""Solver settings, reached through pycanha.

The settings themselves are tested in pycanha-core-python. What is tested here
is that they are reachable as pycanha names, that a model's own solvers take
them, and that a model built with the bulk calls solves through them.
"""

from __future__ import annotations

import numpy as np
import pycanha_core as pcc
import pytest

import pycanha as pc
from pycanha import solvers
from pycanha.tmm import NodeType

requires_mkl = pytest.mark.skipif(not pc.MKL_ENABLED, reason="needs a build with MKL")
requires_accelerate = pytest.mark.skipif(
    not solvers.accelerate_available(), reason="needs Accelerate"
)

# Every storage and backend that can factorize the matrix.
CONFIGURATIONS = [
    {"storage": solvers.Storage.SPARSE, "backend": solvers.Backend.EIGEN},
    {"storage": solvers.Storage.DENSE, "backend": solvers.Backend.EIGEN},
    pytest.param(
        {"storage": solvers.Storage.SPARSE, "backend": solvers.Backend.PARDISO}, marks=requires_mkl
    ),
    pytest.param(
        {"storage": solvers.Storage.DENSE, "backend": solvers.Backend.LAPACK}, marks=requires_mkl
    ),
    pytest.param(
        {"storage": solvers.Storage.SPARSE, "backend": solvers.Backend.ACCELERATE},
        marks=requires_accelerate,
    ),
]

# Plate strip: diffusive nodes 1..N in a chain, node N joined to boundary node
# 1000, heat into node 1. Each link carries all of it.
N = 200
G = 2.0
Q = 5.0
T_BOUNDARY = 290.0


def strip_model() -> pc.ThermalModel:
    """A conduction chain built with the bulk calls, with a known steady state."""
    tm = pc.ThermalModel("strip")
    tmm = tm.tmm
    numbers = np.arange(1, N + 1, dtype=np.int32)
    qi = np.zeros(N)
    qi[0] = Q
    tmm.add_nodes(numbers, T=np.full(N, 273.15), C=np.full(N, 1.0), qi=qi)
    tmm.add_nodes(np.array([1000]), type=NodeType.BOUNDARY, T=np.array([T_BOUNDARY]))
    report = tmm.add_conductive_couplings(numbers, np.append(numbers[1:], 1000), np.full(N, G))
    assert report.accepted == N
    return tm


def expected_strip() -> np.ndarray:
    return T_BOUNDARY + (N + 1 - np.arange(1, N + 1)) * Q / G


def solved_temperatures(tm: pc.ThermalModel, solver: solvers.Solver) -> np.ndarray:
    solver.set("tolerance", 1e-8)
    solver.initialize()
    solver.solve()
    solver.deinitialize()
    return tm.tmm.nodes.get_values(pc.tmm.NodeAttribute.T, np.arange(1, N + 1, dtype=np.int32))


def test_settings_are_pycanha_names() -> None:
    assert solvers.Settings is pcc.solvers.Settings
    assert solvers.Backend is pcc.solvers.Backend
    assert solvers.Storage is pcc.solvers.Storage
    assert solvers.Factorization is pcc.solvers.Factorization


def test_a_model_hands_back_the_pycanha_solver_classes() -> None:
    tm = pc.ThermalModel("registry")
    registry = tm.solvers
    assert type(registry) is solvers.SolverRegistry
    assert type(registry.steady.steady_state) is solvers.steady.SteadyState
    assert type(registry.transient.crank_nicolson) is solvers.transient.CrankNicolson
    assert (
        type(registry.sensitivity.jacobian_propagation) is solvers.sensitivity.JacobianPropagation
    )
    assert isinstance(registry.steady.steady_state, solvers.Solver)


def test_bulk_built_model_solves_with_the_defaults() -> None:
    tm = strip_model()
    solver = tm.solvers.steady.steady_state
    np.testing.assert_allclose(solved_temperatures(tm, solver), expected_strip(), rtol=1e-12)
    # Linear model: the confirming pass reuses the factors.
    assert solver.num_factorizations == 1


@pytest.mark.parametrize("config", CONFIGURATIONS)
def test_every_backend_gives_the_same_answer(config: dict[str, object]) -> None:
    tm = strip_model()
    solver = tm.solvers.steady.steady_state
    for name, value in config.items():
        solver.set(name, value)
    np.testing.assert_allclose(solved_temperatures(tm, solver), expected_strip(), rtol=1e-12)


def test_invalid_combination_raises_value_error() -> None:
    tm = strip_model()
    tm.tmm.add_radiative_coupling(1, 1000, 0.1)
    solver = tm.solvers.steady.steady_state
    solver.factorization = solvers.Factorization.CHOLESKY
    with pytest.raises(ValueError, match="CHOLESKY"):
        solver.initialize()


def test_transient_takes_the_same_settings() -> None:
    def run(backend: solvers.Backend | None) -> np.ndarray:
        tm = strip_model()
        solver = tm.solvers.transient.crank_nicolson
        solver.backend = backend
        solver.set_simulation_time(0.0, 50.0, 5.0, 5.0)
        return solved_temperatures(tm, solver)

    np.testing.assert_allclose(run(solvers.Backend.EIGEN), run(None), atol=1e-9)


def test_a_structure_change_after_initialize_raises() -> None:
    tm = strip_model()
    solver = tm.solvers.steady.steady_state
    solver.initialize()
    tm.tmm.add_conductive_coupling(1, 1000, G)
    with pytest.raises(solvers.ModelChangedError):
        solver.solve()
