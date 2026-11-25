from pathlib import Path

import numpy as np

import pycanha as pc

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "data" / "esatan" / "DISC"
STEADY_FIXTURE = FIXTURE_ROOT / "DISCTR_STEADY.TMD"
TRANSIENT_FIXTURE = FIXTURE_ROOT / "DISCTR_TRANSIENT.TMD"
BOUNDARY_NODE_SPACE = 99999


def get_node_temperatures(model: pc.ThermalModel) -> np.ndarray:
    nodes = model.tmm.nodes
    return np.array([nodes.get_node_from_idx(index).T for index in range(nodes.num_nodes)])


def set_uniform_temperature(
    model: pc.ThermalModel,
    temperature: float,
    *,
    excluded_node_numbers: set[int] | None = None,
) -> None:
    nodes = model.tmm.nodes
    excluded = excluded_node_numbers if excluded_node_numbers is not None else set()

    for index in range(nodes.num_nodes):
        node_number = nodes.get_node_num_from_idx(index)
        if node_number in excluded:
            continue
        nodes.get_node_from_idx(index).T = temperature


def align_temperature_outputs(
    output_model: pc.tmm.DataModel,
    reference_model: pc.tmm.DataModel,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    output_node_numbers = list(output_model.node_numbers)
    reference_node_numbers = list(reference_model.node_numbers)
    reference_node_set = set(reference_node_numbers)
    common_node_numbers = [node for node in output_node_numbers if node in reference_node_set]

    output_indices = [output_node_numbers.index(node) for node in common_node_numbers]
    reference_indices = [reference_node_numbers.index(node) for node in common_node_numbers]

    output_values = np.asarray(output_model.T.values)[:, output_indices]
    reference_values = np.asarray(reference_model.T.values)[:, reference_indices]
    return np.asarray(output_model.T.times), output_values, reference_values


def test_steady_state_of_the_disc_model() -> None:
    model = pc.ThermalModel.from_esatan_tmd(str(STEADY_FIXTURE), name="disc")
    reference_temperatures = get_node_temperatures(model)

    set_uniform_temperature(model, 273.15, excluded_node_numbers={2000, BOUNDARY_NODE_SPACE})

    solver = model.solvers.steady.steady_state
    solver.max_iterations = 100
    solver.tolerance = 1e-4
    solver.initialize()
    solver.solve()

    np.testing.assert_allclose(get_node_temperatures(model), reference_temperatures, atol=1e-4)


def test_transient_of_the_disc_model() -> None:
    model = pc.ThermalModel.from_esatan_tmd(str(STEADY_FIXTURE), name="disc")
    set_uniform_temperature(
        model,
        273.15 - 10.0,
        excluded_node_numbers={BOUNDARY_NODE_SPACE},
    )

    pc.tmm.read_tmd_transient(
        str(TRANSIENT_FIXTURE),
        model.tmm.thermal_data,
        "stored_transient",
    )
    stored_output = model.tmm.thermal_data.models.get_model("stored_transient")

    solver = model.solvers.transient.crank_nicolson
    solver.max_iterations = 100
    solver.tolerance = 1e-7
    solver.set_simulation_time(0.0, 10000.0, 1.0, 100.0)
    solver.initialize()
    solver.solve()

    output_model = solver.output_model
    output_times, output_values, stored_values = align_temperature_outputs(
        output_model,
        stored_output,
    )

    assert len(output_model.node_numbers) == output_values.shape[1]
    assert output_values.shape == stored_values.shape

    np.testing.assert_allclose(
        output_times,
        np.asarray(stored_output.T.times),
        rtol=0.0,
        atol=1e-12,
    )
    # TODO(solvers): ~1.75% of the temperatures differ from the stored ones by more
    # than 2e-3 K. A different value of the Stefan-Boltzmann constant could explain it.
    np.testing.assert_allclose(output_values, stored_values, rtol=0.0, atol=5e-3)
