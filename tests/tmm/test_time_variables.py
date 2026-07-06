"""Time- and temperature-driven variables.

Mirrors the pycanha-core C++ tests
(test/unit/tmm/test_thermal_mathematical_model.cpp variable helpers and
test/unit/parameters/test_variable.cpp "synchronizes time and time variables").
"""

import pytest

import pycanha as pc


def test_variable_helpers_add_query_remove() -> None:
    tmm = pc.tmm.ThermalMathematicalModel("variable-helpers")
    tmm.parameters.add_parameter("existing", 1.0)

    tmm.add_time_variable("load", [0.0, 1.0], [10.0, 20.0])
    assert tmm.has_time_variable("load")
    assert tmm.get_time_variable("load").name == "load"

    tmm.add_temperature_variable("kappa", [200.0, 300.0], [1.0, 2.0])
    assert tmm.has_temperature_variable("kappa")

    tmm.remove_time_variable("load")
    tmm.remove_temperature_variable("kappa")
    assert not tmm.has_time_variable("load")
    assert not tmm.has_temperature_variable("kappa")


def test_missing_variable_raises() -> None:
    tmm = pc.tmm.ThermalMathematicalModel("m")
    with pytest.raises(IndexError):
        tmm.get_time_variable("missing")
    with pytest.raises(IndexError):
        tmm.get_temperature_variable("missing")


def test_duplicate_and_clashing_names_raise() -> None:
    tmm = pc.tmm.ThermalMathematicalModel("dup")
    tmm.add_time_variable("schedule", [0.0, 1.0], [10.0, 20.0])
    with pytest.raises(ValueError, match="already exists"):
        tmm.add_time_variable("schedule", [0.0, 1.0], [30.0, 40.0])

    tmm.add_temperature_variable("kappa", [200.0, 300.0], [1.0, 2.0])
    with pytest.raises(ValueError, match="already used"):
        tmm.add_time_variable("kappa", [0.0, 1.0], [1.0, 2.0])


def test_temperature_variable_evaluates() -> None:
    tmm = pc.tmm.ThermalMathematicalModel("temp")
    tmm.add_temperature_variable("kappa", [200.0, 300.0, 400.0], [2.0, 3.0, 4.0])
    variable = tmm.get_temperature_variable("kappa")
    assert variable.evaluate(350.0) == pytest.approx(3.5)
    assert variable.lookup_table.size == 3


def test_time_and_variable_sync_before_formulas() -> None:
    tmm = pc.tmm.ThermalMathematicalModel("variable-model")
    tmm.add_node(1)
    tmm.nodes.set_qi(1, 0.0)

    tmm.add_time_variable("load", [0.0, 5.0, 10.0], [0.0, 50.0, 100.0])

    formula = tmm.formulas.create_formula(tmm.entity("QI1"), "load + time")
    tmm.formulas.add_formula(formula)
    tmm.formulas.validate_for_execution()
    tmm.formulas.compile_formulas()
    tmm.formulas.lock_parameters_for_execution()

    tmm.time = 6.0
    tmm.callback_solver_loop()

    assert tmm.parameters.get_parameter("time") == pytest.approx(6.0)
    assert tmm.parameters.get_parameter("load") == pytest.approx(60.0)
    assert tmm.nodes.get_qi(1) == pytest.approx(66.0)

    tmm.formulas.unlock_parameters()
