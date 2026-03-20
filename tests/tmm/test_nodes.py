import pytest

import pycanha as pc


def test_nodes_add_and_get():
    nodes = pc.tmm.Nodes()
    node = pc.tmm.Node(101)
    node.T = 273.15
    node.C = 42.0

    nodes.add_node(node)

    assert nodes.num_nodes == 1
    assert nodes.get_T(101) == pytest.approx(273.15)
    assert nodes.get_C(101) == pytest.approx(42.0)
    assert nodes.get_idx_from_node_num(101) == 0


def test_couplings_store_values():
    nodes = pc.tmm.Nodes()
    nodes.add_node(pc.tmm.Node(1))
    nodes.add_node(pc.tmm.Node(2))

    couplings = pc.tmm.Couplings(nodes)
    couplings.add_coupling(1, 2, 15.0)

    assert couplings.get_coupling_value(1, 2) == pytest.approx(15.0)
    assert couplings.coupling_exists(1, 2)


def test_thermal_network_links_resources():
    network = pc.tmm.ThermalNetwork()
    network.add_node(pc.tmm.Node(1))
    network.add_node(pc.tmm.Node(2))

    assert network.nodes.num_nodes == 2
    network.conductive_couplings.add_coupling(1, 2, 5.0)
    assert network.conductive_couplings.get_coupling_value(1, 2) == pytest.approx(5.0)
