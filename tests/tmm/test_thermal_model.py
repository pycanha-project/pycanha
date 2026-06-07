import pytest

import pycanha as pc
import pycanha.tmm as pm


def build_basic_tm() -> pc.ThermalModel:
    tm = pc.ThermalModel("test_model")
    tmm = tm.tmm

    node_10 = pm.Node(10)
    node_15 = pm.Node(15)
    node_20 = pm.Node(20)
    node_25 = pm.Node(25)
    env_node = pm.Node(99)

    init_temp = 273.15
    for node in (node_10, node_15, node_20, node_25):
        node.T = init_temp
        node.capacity = 2e5

    env_node.T = 3.15
    env_node.type = pm.NodeType.BOUNDARY
    node_15.qi = 500.0

    for node in (node_10, node_15, node_20, node_25, env_node):
        tmm.add_node(node)

    tmm.add_conductive_coupling(10, 15, 0.1)
    tmm.add_conductive_coupling(20, 25, 0.1)

    tmm.add_radiative_coupling(10, 99, 1.0)
    tmm.add_radiative_coupling(20, 99, 1.0)
    tmm.add_radiative_coupling(15, 25, 0.2)
    tmm.add_radiative_coupling(15, 99, 0.8)
    tmm.add_radiative_coupling(25, 99, 0.8)

    return tm


def run_transient_solver(tm: pc.ThermalModel):
    solver = tm.solvers.tscnrlds
    solver.max_iters = 20
    solver.abstol_temp = 1e-9
    solver.set_simulation_time(0.0, 2.0, 0.1, 0.5)
    solver.initialize()
    solver.solve()
    solver.deinitialize()
    return solver


def test_default_owner_exposes_stable_wrapped_subsystems() -> None:
    tm = pc.ThermalModel("overview_root")

    assert tm.name == "overview_root"
    assert tm.tmm is tm.tmm
    assert tm.tmm is tm._tmm
    assert tm.solvers is tm.solvers
    assert tm.callbacks is tm.callbacks
    assert tm.solvers.sslu is tm.solvers.sslu
    assert tm.tmm.nodes is tm.tmm._nodes
    assert tm.tmm.network is tm.tmm._network

    tm.parameters.add_parameter("k", 10.0)
    assert tm.tmm.parameters.get_parameter("k") == pytest.approx(10.0)
    assert tm.solvers.tmm is tm.tmm


def test_entities_and_string_lookup_roundtrip() -> None:
    tm = build_basic_tm()
    tmm = tm.tmm

    assert tmm.entities.temperature(10).string_representation() == "T10"
    assert tmm.entities.capacity(10).string_representation() == "C10"
    assert tmm.entities.internal_heat(15).string_representation() == "QI15"
    assert tmm.entities.conductive_coupling(15, 10).string_representation() == "GL(10,15)"

    assert tmm.find_entity("QI15") is not None
    assert tmm.entity("QI15").string_representation() == "QI15"
    assert tmm.find_entity("not_an_entity") is None

    with pytest.raises(ValueError, match="Unknown thermal entity"):
        tmm.entity("not_an_entity")


def test_general_formula_updates_value_on_apply() -> None:
    tm = pc.ThermalModel("general_formula")
    tmm = tm.tmm
    tmm.add_node(1)

    history: list[str] = []

    def heater_power(current_tm: pc.ThermalModel) -> float:
        history.append(current_tm.name)
        return 42.0

    formula = tmm.formulas.add_general_formula(
        "QI1",
        update=heater_power,
        initial_value=5.0,
        name="heater_profile",
    )

    assert isinstance(formula, pc.parameters.GeneralFormula)
    assert tmm.nodes.get_qi(1) == pytest.approx(5.0)

    tmm.formulas.apply_formulas()

    assert history == ["general_formula"]
    assert formula.get_value() == pytest.approx(42.0)
    assert tmm.nodes.get_qi(1) == pytest.approx(42.0)


def test_after_timestep_receives_callback_context() -> None:
    tm = build_basic_tm()
    seen = []

    def after_timestep(context):
        seen.append(
            (
                type(context).__name__,
                context.tm.name,
                context.tmm.name,
                type(context.solver).__name__,
                context.time,
            )
        )

    tm.callbacks.after_timestep = after_timestep

    run_transient_solver(tm)

    assert seen
    assert seen[0][0] == "CallbackContext"
    assert seen[0][1] == tm.name
    assert seen[0][2] == tm.tmm.name
    assert seen[0][3] == "TSCNRLDS"
    assert seen[-1][4] > 0.0
