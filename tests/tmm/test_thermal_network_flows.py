import math

import pytest

import pycanha.tmm as tmm
from pycanha.tmm.node import NodeType

STEFAN_BOLTZMANN = 5.670374419e-8


def make_flow_network() -> tuple[
    tmm.ThermalNetwork,
    dict[int, float],
    dict[frozenset[int], float],
    dict[frozenset[int], float],
]:
    network = tmm.ThermalNetwork()

    temperatures = {
        17: 290.0,
        11: 300.0,
        40: 315.0,
        2: 305.0,
        55: 280.0,
    }

    for node_num, temperature in temperatures.items():
        node = tmm.Node(node_num)
        node.T = temperature
        if node_num in {40, 55}:
            node.type = NodeType.BOUNDARY
        network.add_node(node)

    conductive_links = {
        frozenset((17, 2)): 1.2,
        frozenset((17, 55)): 0.8,
        frozenset((11, 2)): 1.5,
        frozenset((11, 55)): 2.0,
        frozenset((40, 2)): 0.6,
        frozenset((40, 55)): 1.1,
        frozenset((17, 11)): 3.0,
        frozenset((11, 40)): 0.4,
        frozenset((2, 55)): 4.4,
    }
    radiative_links = {
        frozenset((17, 2)): 0.10,
        frozenset((17, 55)): 0.05,
        frozenset((11, 2)): 0.07,
        frozenset((11, 55)): 0.09,
        frozenset((40, 2)): 0.11,
        frozenset((40, 55)): 0.04,
        frozenset((17, 11)): 0.08,
        frozenset((11, 40)): 0.06,
        frozenset((2, 55)): 0.03,
    }

    for nodes, value in conductive_links.items():
        node_1, node_2 = tuple(nodes)
        network.conductive_couplings.add_coupling(node_1, node_2, value)

    for nodes, value in radiative_links.items():
        node_1, node_2 = tuple(nodes)
        network.radiative_couplings.add_coupling(node_1, node_2, value)

    return network, temperatures, conductive_links, radiative_links


def conductive_flow(
    temperatures: dict[int, float],
    links: dict[frozenset[int], float],
    node_1: int,
    node_2: int,
) -> float:
    return links[frozenset((node_1, node_2))] * (temperatures[node_2] - temperatures[node_1])


def radiative_flow(
    temperatures: dict[int, float],
    links: dict[frozenset[int], float],
    node_1: int,
    node_2: int,
) -> float:
    return (
        links[frozenset((node_1, node_2))]
        * STEFAN_BOLTZMANN
        * (math.pow(temperatures[node_2], 4) - math.pow(temperatures[node_1], 4))
    )


def test_flow_conductive_for_nodes_and_groups() -> None:
    network, temperatures, conductive_links, _ = make_flow_network()
    group_1 = [17, 11, 40]
    group_2 = [2, 55]

    assert network.flow_conductive(17, 2) == pytest.approx(
        conductive_flow(temperatures, conductive_links, 17, 2)
    )
    assert network.flow_conductive(40, 55) == pytest.approx(
        conductive_flow(temperatures, conductive_links, 40, 55)
    )

    expected_group_flow = sum(
        conductive_flow(temperatures, conductive_links, node_1, node_2)
        for node_1 in group_1
        for node_2 in group_2
    )
    assert network.flow_conductive(group_1, group_2) == pytest.approx(expected_group_flow)


def test_flow_radiative_for_nodes_and_groups() -> None:
    network, temperatures, _, radiative_links = make_flow_network()
    group_1 = [17, 11, 40]
    group_2 = [2, 55]

    assert network.flow_radiative(17, 2) == pytest.approx(
        radiative_flow(temperatures, radiative_links, 17, 2)
    )
    assert network.flow_radiative(40, 55) == pytest.approx(
        radiative_flow(temperatures, radiative_links, 40, 55)
    )

    expected_group_flow = sum(
        radiative_flow(temperatures, radiative_links, node_1, node_2)
        for node_1 in group_1
        for node_2 in group_2
    )
    assert network.flow_radiative(group_1, group_2) == pytest.approx(expected_group_flow)
