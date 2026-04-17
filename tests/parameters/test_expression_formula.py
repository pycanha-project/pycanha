import pytest

import pycanha.parameters as parameters
import pycanha.tmm as tmm


@pytest.fixture
def tmm_with_params() -> tmm.ThermalMathematicalModel:
    tmm_model = tmm.ThermalMathematicalModel("expression_formula_test")

    node_1 = tmm.Node(1)
    node_1.T = 300.0
    node_1.qi = 50.0
    node_2 = tmm.Node(2)
    node_2.T = 200.0

    tmm_model.add_node(node_1)
    tmm_model.add_node(node_2)
    tmm_model.add_conductive_coupling(1, 2, 10.0)
    tmm_model.parameters.add_parameter("k", 25.0)
    return tmm_model


def test_expression_formula_apply_updates_entity(
    tmm_with_params: tmm.ThermalMathematicalModel,
) -> None:
    tmm_model = tmm_with_params
    tmm_model.parameters.add_parameter("offset", 2.0)
    entity = parameters.Entity.qi(tmm_model.network, 1)
    formula = parameters.ExpressionFormula(entity, tmm_model.parameters, "k + offset")

    assert formula.expression == "k + offset"
    assert formula.parameter_dependencies == ["k", "offset"]

    formula.apply_formula()

    assert tmm_model.nodes.get_qi(1) == pytest.approx(27.0)
    assert formula.get_value() == pytest.approx(27.0)


def test_expression_formula_derivatives(
    tmm_with_params: tmm.ThermalMathematicalModel,
) -> None:
    tmm_model = tmm_with_params
    tmm_model.parameters.add_parameter("offset", 2.0)
    entity = parameters.Entity.gl(tmm_model.network, 1, 2)
    formula = parameters.ExpressionFormula(entity, tmm_model.parameters, "k * offset")

    formula.compile_formula()
    formula.calculate_derivatives()

    assert formula.get_derivative_values() == pytest.approx([2.0, 25.0])
