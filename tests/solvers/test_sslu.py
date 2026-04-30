import numpy as np
import pytest

import pycanha as pc
import pycanha.tmm as pm


@pytest.fixture
def five_node_model():
    """Create a 5-node model with conductive and radiative couplings."""
    tm = pc.ThermalModel("test_model")
    tmm = tm.tmm

    node_10 = pm.Node(10)
    node_15 = pm.Node(15)
    node_20 = pm.Node(20)
    node_25 = pm.Node(25)
    env_node = pm.Node(99)

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

    env_node.type = pm.NodeType.BOUNDARY

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

    return tm


def test_sslu_steady_state(five_node_model):
    tm = five_node_model
    tmm = tm.tmm

    solver = tm.solvers.sslu
    solver.max_iters = 100
    solver.abstol_temp = 1e-6

    solver.initialize()
    solver.solve()

    calculated_temps = np.array(
        [
            tmm.nodes.get_T(10),
            tmm.nodes.get_T(15),
            tmm.nodes.get_T(20),
            tmm.nodes.get_T(25),
            tmm.nodes.get_T(99),
        ]
    )

    expected_temps = np.array([132.38706, 306.56526, 111.78443, 200.32387, 3.14999])

    np.testing.assert_allclose(calculated_temps, expected_temps, atol=1e-2)
