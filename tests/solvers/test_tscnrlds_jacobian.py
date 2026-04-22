import numpy as np

import pycanha.parameters as parameters
import pycanha.solvers as solvers
import pycanha.tmm as tmm
from pycanha.tmm.node import NodeType


def get_temperature_output(model: tmm.ThermalMathematicalModel, model_name: str) -> np.ndarray:
    output_model = model.thermal_data.models.get_model(model_name)
    return np.column_stack((np.asarray(output_model.T.times), np.asarray(output_model.T.values)))


def get_jacobian_output(model: tmm.ThermalMathematicalModel, model_name: str) -> np.ndarray:
    output_model = model.thermal_data.models.get_model(model_name)
    jacobian = output_model.jacobian
    flattened_rows = [
        np.asarray(jacobian.at(index)).reshape(-1) for index in range(jacobian.num_timesteps)
    ]
    return np.column_stack((np.asarray(jacobian.times), np.vstack(flattened_rows)))


def make_jacobian_example_model() -> tmm.ThermalMathematicalModel:
    model = tmm.ThermalMathematicalModel("jacobian_python_example")

    diffusive_node = tmm.Node(1)
    diffusive_node.T = 0.0
    diffusive_node.capacity = 1.0
    diffusive_node.qi = 1.0

    boundary_node = tmm.Node(2)
    boundary_node.type = NodeType.BOUNDARY
    boundary_node.T = 1.0

    model.add_node(diffusive_node)
    model.add_node(boundary_node)
    model.add_conductive_coupling(1, 2, 1.0)

    model.parameters.add_parameter("k", 1.0)
    model.parameters.add_parameter("C", 1.0)

    conductive_entity = parameters.Entity.gl(model.network, 1, 2)
    capacity_entity = parameters.Entity.c(model.network, 1)

    model.formulas.add_formula(
        parameters.ParameterFormula(conductive_entity, model.parameters, "k")
    )
    model.formulas.add_formula(parameters.ParameterFormula(capacity_entity, model.parameters, "C"))
    model.formulas.apply_formulas()

    return model


def find_time_row(table: np.ndarray, time_value: float) -> int:
    matching_rows = np.where(np.isclose(table[:, 0], time_value, atol=1e-12))[0]
    if matching_rows.size == 0:
        raise AssertionError(f"Time sample {time_value} was not produced by the solver")
    return int(matching_rows[0])


def test_tscnrlds_jacobian_solver_outputs_models() -> None:
    model = make_jacobian_example_model()
    solver = solvers.TSCNRLDS_JACOBIAN(model)
    solver.MAX_ITERS = 50
    solver.abstol_temp = 1e-9
    solver.set_simulation_time(0.0, 5.0, 0.01, 0.1)

    solver.initialize()
    solver.solve()

    assert model.thermal_data.models.has_model(solver.output_model_name) is True
    assert solver.parameter_names == ["k", "C"]

    temperature_output = get_temperature_output(model, solver.output_model_name)
    jacobian_output = get_jacobian_output(model, solver.output_model_name)

    assert temperature_output.shape[1] == 3
    assert jacobian_output.shape[1] == 3
    assert jacobian_output.shape[0] >= 2

    expected_temperature_samples = np.array(
        [
            [0.0, 0.0, 1.0],
            [1.0, 1.26424718, 1.0],
            [2.0, 1.72933389, 1.0],
            [3.0, 1.90042832, 1.0],
            [4.0, 1.96336993, 1.0],
            [5.0, 1.98652466, 1.0],
        ]
    )
    expected_jacobian_samples = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.10364756, -0.73577107],
            [2.0, -0.32332125, -0.54134564],
            [3.0, -0.65149169, -0.29872244],
            [4.0, -0.83516103, -0.14652392],
            [5.0, -0.92588396, -0.06737837],
        ]
    )

    for expected_temperature, expected_jacobian in zip(
        expected_temperature_samples,
        expected_jacobian_samples,
        strict=True,
    ):
        row = find_time_row(temperature_output, expected_temperature[0])
        np.testing.assert_allclose(temperature_output[row], expected_temperature, atol=5e-6)
        np.testing.assert_allclose(jacobian_output[row], expected_jacobian, atol=5e-6)

    solver.deinitialize()
    assert solver.solver_initialized is False
