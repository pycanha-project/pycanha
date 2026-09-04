"""Result discovery, frames and their mapping onto faces.

Everything in :mod:`pycanha.plot.results` is plain numpy over the public
thermal model, so all of it is exercised without a widget. The panel and the
window that drive it are in ``test_time_panel.py``.
"""

import numpy as np
import pycanha_core as pcc
import pytest
import scipy.sparse as sp

import pycanha as pc
from pycanha import gmm
from pycanha.plot import results
from pycanha.plot.results import LIVE_CASE, RESULT_KEY

#: The nodes the stored case carries, in the order it stores them.
CASE_NODES = [100, 101, 110, 111]

#: Three instants, 100 s apart.
CASE_TIMES = [0.0, 100.0, 200.0]


def two_panel_model() -> pc.ThermalModel:
    """Two 2x1 panels, four faces, eight faces, eight tmm nodes."""
    tm = pc.ThermalModel("results")
    panels = []
    for index, name in enumerate(("a", "b")):
        thermal_mesh = gmm.ThermalMesh([0.0, 0.5, 1.0], [0.0, 1.0])
        thermal_mesh.node1_start = 100 + 10 * index
        thermal_mesh.node2_start = 200 + 10 * index
        height = float(index)
        panels.append(
            gmm.GeometryItem(
                name,
                gmm.Rectangle((0, 0, height), (2, 0, height), (0, 1, height)),
                thermal_mesh,
            )
        )
    tm.gmm.add(gmm.GeometryGroup("wing", panels))
    return tm


def add_nodes(tm: pc.ThermalModel) -> pc.ThermalModel:
    """Give the network the eight nodes the two panels name, node 100 at 300 K."""
    for node in (100, 101, 110, 111, 200, 201, 210, 211):
        tm.tmm.add_node(node)
    tm.tmm.nodes.set_T(100, 300.0)
    tm.tmm.nodes.set_T(101, 310.0)
    return tm


def add_case(tm: pc.ThermalModel, name: str = "hot case") -> pc.ThermalModel:
    """Store a three-instant transient over the four side-1 nodes of panel 'a'."""
    model = pcc.tmm.DataModel(CASE_NODES)
    temperature = model.T
    temperature.resize(len(CASE_TIMES), len(CASE_NODES))
    for step, time in enumerate(CASE_TIMES):
        temperature.set_row(step, time, np.array([300.0 + step, 310.0 + step, 320.0, 330.0]))
    load = model.QI
    load.resize(len(CASE_TIMES), len(CASE_NODES))
    for step, time in enumerate(CASE_TIMES):
        load.set_row(step, time, np.array([1.0, 2.0, 3.0, 4.0]))
    tm.tmm.thermal_data.models.add_model(name, model)
    return tm


@pytest.fixture
def solved() -> pc.ThermalModel:
    return add_case(add_nodes(two_panel_model()))


# ── discovery ─────────────────────────────────────────────────────────────
def test_the_cases_are_the_stored_models_plus_the_live_one(solved: pc.ThermalModel) -> None:
    found = results.cases(solved)
    assert [case.key for case in found] == [LIVE_CASE, "hot case"]
    assert found[0].live
    assert not found[1].live


def test_a_model_with_nothing_solved_has_no_cases() -> None:
    # No nodes and no stored model: nothing to show, so the viewer leaves the
    # whole results strip out.
    assert results.cases(two_panel_model()) == []
    assert results.cases(None) == []


def test_a_network_with_no_results_still_offers_the_live_state() -> None:
    assert [case.key for case in results.cases(add_nodes(two_panel_model()))] == [LIVE_CASE]


def test_only_populated_dense_attributes_are_offered(solved: pc.ThermalModel) -> None:
    # In the declared order, not the order they were written in.
    assert results.attributes(solved, "hot case") == ["T", "QI"]
    # The live state answers for temperature alone.
    assert results.attributes(solved, LIVE_CASE) == ["T"]
    assert results.attributes(solved, "no such case") == []


def test_a_coupling_history_is_not_a_coloring(solved: pc.ThermalModel) -> None:
    # KL is a matrix per instant, not a value per node, so it cannot color a
    # face and must not reach the attribute combo.
    model = solved.tmm.thermal_data.models.get_model("hot case")
    model.conductive_couplings.push_back(0.0, sp.csr_matrix(np.eye(len(CASE_NODES))))
    assert pcc.tmm.DataModelAttribute.KL in model.populated_attributes
    assert "KL" not in results.attributes(solved, "hot case")


# ── reading a series ──────────────────────────────────────────────────────
def test_a_stored_series_carries_its_nodes_times_and_values(solved: pc.ThermalModel) -> None:
    series = results.series(solved, "hot case", "T")
    assert series is not None
    assert series.num_steps == 3
    assert series.animated
    assert series.label == "Temperature"
    assert series.unit == "K"
    assert np.array_equal(series.node_numbers, CASE_NODES)
    assert np.array_equal(series.times, CASE_TIMES)
    assert np.array_equal(series.frame(1), [301.0, 311.0, 320.0, 330.0])


def test_the_live_series_is_one_instant_with_no_time_axis(solved: pc.ThermalModel) -> None:
    series = results.series(solved, LIVE_CASE, "T")
    assert series is not None
    assert series.num_steps == 1
    assert not series.animated
    assert series.times.size == 0
    assert series.time_label(0) == "no time axis"
    values = dict(zip(series.node_numbers.tolist(), series.frame(0).tolist(), strict=True))
    assert values[100] == 300.0
    assert values[101] == 310.0


def test_an_unreadable_series_is_none(solved: pc.ThermalModel) -> None:
    assert results.series(solved, "no such case", "T") is None
    assert results.series(solved, "hot case", "EPS") is None
    # The live state has nothing but temperature to say.
    assert results.series(solved, LIVE_CASE, "QI") is None


def test_the_frame_index_is_clamped_never_interpolated(solved: pc.ThermalModel) -> None:
    series = results.series(solved, "hot case", "T")
    assert series is not None
    assert np.array_equal(series.frame(99), series.frame(2))
    assert np.array_equal(series.frame(-3), series.frame(0))
    # Every frame is a row the solver wrote, so it is one of the stored rows.
    for index in range(series.num_steps):
        assert np.array_equal(series.frame(index), series.values[index])


def test_the_color_limits_span_the_whole_series(solved: pc.ThermalModel) -> None:
    series = results.series(solved, "hot case", "T")
    assert series is not None
    # Not the range of one frame: the same temperature has to be the same
    # color at every instant.
    assert series.clim() == (300.0, 330.0)


def test_the_limits_can_be_narrowed_to_the_nodes_still_drawn(solved: pc.ThermalModel) -> None:
    series = results.series(solved, "hot case", "T")
    assert series is not None
    # Still the whole series - both instants of node 100 - but only the nodes
    # asked for. Hiding geometry may rescale; scrubbing may not.
    assert series.clim([100, 101]) == (300.0, 312.0)
    assert series.clim([110, 111]) == (320.0, 330.0)
    # A node the case never carried simply is not in the range.
    assert series.clim([100, 9999]) == (300.0, 302.0)
    assert series.clim([9999]) is None
    # A single node that never moves has no range to scale over, as ever.
    assert series.clim([110]) is None


def test_a_constant_series_has_no_range_to_scale(solved: pc.ThermalModel) -> None:
    for node in (100, 101, 110, 111, 200, 201, 210, 211):
        solved.tmm.nodes.set_T(node, 300.0)
    series = results.series(solved, LIVE_CASE, "T")
    assert series is not None
    assert series.clim() is None


def test_the_time_label_names_the_stored_instant(solved: pc.ThermalModel) -> None:
    series = results.series(solved, "hot case", "T")
    assert series is not None
    assert series.time_label(1) == "t = 100 s"
    assert series.time_label(99) == "t = 200 s"


def test_a_history_is_one_nodes_column(solved: pc.ThermalModel) -> None:
    series = results.series(solved, "hot case", "T")
    assert series is not None
    history = series.history(101)
    assert history is not None
    assert np.array_equal(history, [310.0, 311.0, 312.0])
    assert series.history(9999) is None


# ── onto the geometry ─────────────────────────────────────────────────────
def test_values_land_on_the_faces_of_their_node(solved: pc.ThermalModel) -> None:
    series = results.series(solved, "hot case", "T")
    assert series is not None
    face_nodes = np.asarray(solved.gmm.mesh.node_numbers)
    values = results.face_values(series, 0, face_nodes)

    assert values.shape == face_nodes.shape
    for face, node in enumerate(face_nodes.tolist()):
        if node in CASE_NODES:
            assert values[face] == series.frame(0)[CASE_NODES.index(node)]
        else:
            # Panel 'b' is not in the case at all, and neither is any side-2
            # node: those faces read as absent rather than as zero.
            assert np.isnan(values[face])


def test_a_result_coloring_keeps_the_title_still(solved: pc.ThermalModel) -> None:
    series = results.series(solved, "hot case", "T")
    assert series is not None
    face_nodes = np.asarray(solved.gmm.mesh.node_numbers)
    first = results.result_property(series, 0, face_nodes)
    last = results.result_property(series, 2, face_nodes)

    assert first.key == RESULT_KEY
    assert first.label == "Temperature (hot case)"
    # The instant is deliberately not in the label: it is the color bar's
    # title, and a title that changed per frame would stack color bars.
    assert last.label == first.label
    assert first.clim == last.clim == series.clim()
    assert not np.array_equal(first.values, last.values)


def test_the_placeholder_coloring_is_all_missing() -> None:
    placeholder = results.empty_property(8)
    assert placeholder.key == RESULT_KEY
    assert placeholder.values.shape == (8,)
    assert np.all(np.isnan(placeholder.values))
