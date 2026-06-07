import pytest

import pycanha as pc
import pycanha.tmm as pm


@pytest.fixture
def tmm_with_params() -> pm.ThermalMathematicalModel:
    tm = pc.ThermalModel("expression_formula_test")
    tmm_model = tm.tmm

    node_1 = pm.Node(1)
    node_1.T = 300.0
    node_1.qi = 50.0
    node_2 = pm.Node(2)
    node_2.T = 200.0

    tmm_model.add_node(node_1)
    tmm_model.add_node(node_2)
    tmm_model.add_conductive_coupling(1, 2, 10.0)
    tmm_model.parameters.add_parameter("k", 25.0)
    return tmm_model


def test_expression_formula_apply_updates_entity(
    tmm_with_params: pm.ThermalMathematicalModel,
) -> None:
    tmm_model = tmm_with_params
    tmm_model.parameters.add_parameter("offset", 2.0)
    entity = tmm_model.entities.internal_heat(1)
    formula = pc.parameters.ExpressionFormula(entity, tmm_model.parameters, "k + offset")

    assert formula.expression == "k + offset"
    assert formula.parameter_dependencies == ["k", "offset"]

    formula.apply_formula()

    assert tmm_model.nodes.get_qi(1) == pytest.approx(27.0)
    assert formula.get_value() == pytest.approx(27.0)


def test_expression_formula_derivatives(
    tmm_with_params: pm.ThermalMathematicalModel,
) -> None:
    tmm_model = tmm_with_params
    tmm_model.parameters.add_parameter("offset", 2.0)
    entity = tmm_model.entities.conductive_coupling(1, 2)
    formula = pc.parameters.ExpressionFormula(entity, tmm_model.parameters, "k * offset")

    formula.compile_formula()
    formula.calculate_derivatives()

    assert formula.get_derivative_values() == pytest.approx([2.0, 25.0])
