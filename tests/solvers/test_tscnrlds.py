import numpy as np
import pytest

import pycanha as pc


@pytest.fixture
def five_node_model():
    """Create a 5-node model with conductive and radiative couplings."""
    tmm = pc.tmm.ThermalMathematicalModel("test_model")

    node_10 = pc.tmm.Node(10)
    node_15 = pc.tmm.Node(15)
    node_20 = pc.tmm.Node(20)
    node_25 = pc.tmm.Node(25)
    env_node = pc.tmm.Node(99)

    init_temp = 273.15
    node_10.T = init_temp
    node_15.T = init_temp
    node_20.T = init_temp
    node_25.T = init_temp
    env_node.T = 3.15

    node_10.capacity = 2e5
    node_15.capacity = 2e5
    node_20.capacity = 2e5
    node_25.capacity = 2e5

    node_15.qi = 500.0

    env_node.type = pc.NodeType.BOUNDARY

    tmm.add_node(node_10)
    tmm.add_node(node_15)
    tmm.add_node(node_20)
    tmm.add_node(node_25)
    tmm.add_node(env_node)

    tmm.add_conductive_coupling(10, 15, 0.1)
    tmm.add_conductive_coupling(20, 25, 0.1)

    tmm.add_radiative_coupling(10, 99, 1.0)
    tmm.add_radiative_coupling(20, 99, 1.0)
    tmm.add_radiative_coupling(15, 25, 0.2)
    tmm.add_radiative_coupling(15, 99, 0.8)
    tmm.add_radiative_coupling(25, 99, 0.8)

    return tmm


def test_tscnrlds_transient(five_node_model):
    tmm = five_node_model

    solver = pc.solvers.TSCNRLDS(tmm)
    solver.MAX_ITERS = 100
    solver.abstol_temp = 1e-6
    solver.set_simulation_time(0.0, 100000.0, 1000.0, 10000.0)

    solver.initialize()
    solver.solve()

    results = tmm.thermal_data.get_table("TSCNRLDS_OUTPUT")
    calculated_times = results[:, 0]
    calculated_temps = results[:, 1:]

    expected_times = np.array([
        0.0, 10000.0, 20000.0, 30000.0, 40000.0,
        50000.0, 60000.0, 70000.0, 80000.0, 90000.0, 100000.0,
    ])

    expected_temps = np.array([
        [273.14999, 273.14999, 273.14999, 273.14999, 3.14999],
        [259.03552, 283.85105, 258.98241, 262.06791, 3.14999],
        [247.56014, 291.67014, 247.37629, 253.45623, 3.14999],
        [237.98527, 297.25685, 237.62266, 246.62735, 3.14999],
        [229.83503, 301.16946, 229.26392, 241.11244, 3.14999],
        [222.78667, 303.85891, 221.98896, 236.58283, 3.14999],
        [216.61234, 305.67267, 215.57742, 232.80415, 3.14999],
        [211.14591, 306.86934, 209.86801, 229.60718, 3.14999],
        [206.26295, 307.63674, 204.73939, 226.86828, 3.14999],
        [201.86811, 308.10888, 200.09819, 224.49601, 3.14999],
        [197.88691, 308.38019, 195.87117, 222.42185, 3.14999],
    ])

    np.testing.assert_allclose(calculated_times, expected_times, atol=1e-1)
    np.testing.assert_allclose(calculated_temps, expected_temps, atol=1e-2)
