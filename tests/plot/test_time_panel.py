"""The results strip, and what the window does with it.

Built around a placeholder 3D view, like ``test_window.py``: what is asserted
is the values that would have been handed to VTK and the state behind the
controls, not pixels.
"""

from collections.abc import Iterator

import numpy as np
import pytest
from PySide6.QtWidgets import QWidget

import pycanha as pc
from pycanha.plot.results import LIVE_CASE, RESULT_KEY
from pycanha.plot.state import Selection
from pycanha.plot.window import ViewerWindow

from .test_results import CASE_NODES, CASE_TIMES, add_case, add_nodes, two_panel_model


@pytest.fixture
def solved() -> pc.ThermalModel:
    return add_case(add_nodes(two_panel_model()))


@pytest.fixture
def window(solved: pc.ThermalModel, qtbot: object) -> Iterator[ViewerWindow]:
    del qtbot
    # Closed on the way out: the log tab holds a handler on the process-wide
    # ``pycanha`` logger for as long as the window is open.
    viewer = ViewerWindow(solved.gmm, view=QWidget(), thermal_model=solved)
    yield viewer
    viewer.close()


def select_case(window: ViewerWindow, key: str) -> None:
    """Pick a case by key, the way clicking the combo would."""
    assert window.time_panel is not None
    window.time_panel.case_combo.setCurrentIndex(window.time_panel.case_combo.findData(key))


# ── the panel is there, or is not ─────────────────────────────────────────
def test_geometry_alone_has_no_results_strip(qtbot: object) -> None:
    del qtbot
    # D87: the geometry entry point opens the same window with the results
    # panel simply absent.
    viewer = ViewerWindow(two_panel_model().gmm, view=QWidget())
    try:
        assert viewer.time_panel is None
        assert not viewer.has_results
        assert RESULT_KEY not in viewer.properties
        assert viewer.current_series() is None
    finally:
        viewer.close()


def test_a_model_with_nothing_solved_has_no_results_strip(qtbot: object) -> None:
    del qtbot
    model = two_panel_model()
    viewer = ViewerWindow(model.gmm, view=QWidget(), thermal_model=model)
    try:
        assert viewer.time_panel is None
    finally:
        viewer.close()


def test_a_solved_model_opens_showing_its_results(window: ViewerWindow) -> None:
    assert window.has_results
    assert window.state.color_by == RESULT_KEY
    # The live state is the default case, since it is always there.
    assert window.state.result is not None
    assert window.state.result.case == LIVE_CASE
    assert window.current_property().label == "Temperature (current)"


# ── choosing what to look at ──────────────────────────────────────────────
def test_the_live_case_has_nothing_to_animate(window: ViewerWindow) -> None:
    panel = window.time_panel
    assert panel is not None
    assert not panel.slider.isEnabled()
    assert not panel.play_button.isEnabled()
    assert panel.time_label.text() == "no time axis"


def test_choosing_a_stored_case_spans_its_instants(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    panel = window.time_panel
    assert panel is not None
    assert panel.slider.maximum() == len(CASE_TIMES) - 1
    assert panel.slider.isEnabled()
    assert panel.time_label.text() == "t = 0 s"
    assert window.current_property().label == "Temperature (hot case)"


def test_the_attribute_survives_a_case_change_that_keeps_it(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    panel = window.time_panel
    assert panel is not None
    panel.attribute_combo.setCurrentIndex(panel.attribute_combo.findData("QI"))
    assert window.current_property().label == "Internal heat load (hot case)"

    # The live case has no QI, so it falls back to what it does have.
    select_case(window, LIVE_CASE)
    assert panel.current_attribute() == "T"

    select_case(window, "hot case")
    assert panel.current_attribute() == "T"


def test_the_colouring_is_the_values_of_the_selected_node(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    coloring = window.coloring()
    slot_nodes = np.asarray(window.scene.slot_nodes)
    face_ids = window.scene.face_ids

    assert not coloring.rgb
    assert coloring.title == "Temperature (hot case) [K]"
    for cell, face_id in enumerate(face_ids.tolist()):
        node = int(slot_nodes[face_id])
        if node in CASE_NODES:
            assert coloring.values[cell] == 300.0 + CASE_NODES.index(node) * 10
        else:
            assert np.isnan(coloring.values[cell])


# ── moving through time ───────────────────────────────────────────────────
def test_stepping_changes_the_values_and_nothing_else(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    panel = window.time_panel
    assert panel is not None
    first = window.coloring()

    panel.go_next()
    second = window.coloring()

    assert panel.time_label.text() == "t = 100 s"
    assert not np.array_equal(np.nan_to_num(first.values), np.nan_to_num(second.values))
    # Everything the actor bakes in stays put, which is what lets the values be
    # written through the array it already holds.
    assert second.clim == first.clim
    assert second.title == first.title
    assert second.cmap == first.cmap


def test_the_steps_wrap_at_both_ends(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    panel = window.time_panel
    assert panel is not None

    panel.go_previous()
    assert panel.slider.value() == len(CASE_TIMES) - 1
    panel.go_next()
    assert panel.slider.value() == 0


def test_play_runs_the_timer_until_it_is_stopped(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    panel = window.time_panel
    assert panel is not None

    panel.play()
    assert panel.timer.isActive()
    assert panel.play_button.isChecked()

    panel.stop()
    assert not panel.timer.isActive()
    assert not panel.play_button.isChecked()


def test_a_case_with_no_time_axis_cannot_be_played(window: ViewerWindow) -> None:
    panel = window.time_panel
    assert panel is not None
    panel.play()
    assert not panel.timer.isActive()


def test_closing_the_window_stops_the_animation(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    panel = window.time_panel
    assert panel is not None
    panel.play()

    window.close()
    assert not panel.timer.isActive()


# ── the time history window ───────────────────────────────────────────────
def test_the_history_window_accumulates_a_curve_per_node(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    window.plot_time_history(100)
    window.plot_time_history(101)
    history = window.time_history
    assert history is not None
    assert history.curve_count() == 2

    history.clear()
    assert history.curve_count() == 0


def test_the_history_marker_follows_the_slider(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    window.plot_time_history(100)
    panel = window.time_panel
    assert panel is not None
    panel.go_next()

    history = window.time_history
    assert history is not None
    assert history._marker is not None
    assert np.asarray(history._marker.get_xdata())[0] == CASE_TIMES[1]


def test_a_node_outside_the_case_plots_nothing(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    # Node 200 is side 2 of panel 'a', which the case never carried.
    window.plot_time_history(200)
    assert window.time_history is None


def test_the_live_case_has_no_history_to_plot(window: ViewerWindow) -> None:
    window.plot_time_history(100)
    assert window.time_history is None


def test_the_context_menu_offers_a_history_only_when_there_is_one(
    window: ViewerWindow, solved: pc.ThermalModel
) -> None:
    item = solved.gmm.get_item("a").id
    window.state.selection = Selection(item_id=item, face_id=0, node_number=100, cell=0)
    # The live case has one instant, so there is no history to draw.
    assert "Plot time history of node 100" not in dict(window.context_actions())

    select_case(window, "hot case")
    assert "Plot time history of node 100" in dict(window.context_actions())

    dict(window.context_actions())["Plot time history of node 100"]()
    assert window.time_history is not None
