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
from pycanha.plot.state import DEFAULT_COLOR_BY, PickerMode, Selection
from pycanha.plot.window import ViewerWindow

from .test_results import CASE_NODES, CASE_TIMES, add_case, add_nodes, two_panel_model


@pytest.fixture
def solved() -> pc.ThermalModel:
    return add_case(add_nodes(two_panel_model()))


@pytest.fixture
def opened(solved: pc.ThermalModel, qtbot: object) -> Iterator[ViewerWindow]:
    """A window on a solved model, exactly as it opens."""
    del qtbot
    # Closed on the way out, so the animation timer never outlives the widgets
    # it drives.
    viewer = ViewerWindow(solved.gmm, view=QWidget(), thermal_model=solved)
    yield viewer
    viewer.close()


@pytest.fixture
def window(opened: ViewerWindow) -> ViewerWindow:
    """The same window, switched to the result colouring.

    A window opens on the colour the model carries, and the results strip is
    dead until a result is what is being drawn - so that is where nearly every
    test here has to start.
    """
    opened.state.color_by = RESULT_KEY
    return opened


def select_case(window: ViewerWindow, key: str) -> None:
    """Pick a case by key, the way clicking the combo would."""
    window.time_panel.case_combo.setCurrentIndex(window.time_panel.case_combo.findData(key))


# ── the strip is live, or it is not ───────────────────────────────────────
def test_geometry_alone_has_nothing_to_show(qtbot: object) -> None:
    del qtbot
    # D87: the geometry entry point opens the same window; the strip is there
    # so the layout does not change shape, and there is nothing in it.
    viewer = ViewerWindow(two_panel_model().gmm, view=QWidget())
    try:
        assert not viewer.has_results
        assert not viewer.time_panel.isEnabled()
        assert viewer.time_panel.case_combo.count() == 0
        assert RESULT_KEY not in viewer.properties
        assert viewer.current_series() is None
    finally:
        viewer.close()


def test_a_model_with_nothing_solved_has_nothing_to_show(qtbot: object) -> None:
    del qtbot
    model = two_panel_model()
    viewer = ViewerWindow(model.gmm, view=QWidget(), thermal_model=model)
    try:
        assert not viewer.has_results
        assert not viewer.time_panel.isEnabled()
        assert viewer.state.result is None
    finally:
        viewer.close()


def test_a_solved_model_opens_on_the_geometry_colours(opened: ViewerWindow) -> None:
    assert opened.has_results
    assert opened.state.color_by == DEFAULT_COLOR_BY
    # Read and ready, so choosing it draws it - but not drawn, and not
    # scrubbable while something else is.
    assert opened.state.result is not None
    assert opened.state.result.case == LIVE_CASE
    assert opened.properties[RESULT_KEY].label == "Temperature (current)"
    assert not opened.time_panel.isEnabled()


def test_choosing_the_result_colouring_wakes_the_strip(opened: ViewerWindow) -> None:
    opened.state.color_by = RESULT_KEY
    assert opened.time_panel.isEnabled()
    assert opened.current_property().label == "Temperature (current)"

    opened.state.color_by = DEFAULT_COLOR_BY
    assert not opened.time_panel.isEnabled()


# ── choosing what to look at ──────────────────────────────────────────────
def test_the_live_case_has_nothing_to_animate(window: ViewerWindow) -> None:
    panel = window.time_panel
    assert not panel.slider.isEnabled()
    assert not panel.play_button.isEnabled()
    assert panel.time_label.text() == "no time axis"


def test_choosing_a_stored_case_spans_its_instants(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    panel = window.time_panel
    assert panel.slider.maximum() == len(CASE_TIMES) - 1
    assert panel.slider.isEnabled()
    assert panel.time_label.text() == "t = 0 s"
    assert window.current_property().label == "Temperature (hot case)"


def test_the_attribute_survives_a_case_change_that_keeps_it(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    panel = window.time_panel
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


def test_the_scale_is_spread_over_what_is_drawn(
    window: ViewerWindow, solved: pc.ThermalModel
) -> None:
    select_case(window, "hot case")
    # Node 100 is panel 'a' and runs 300 - 302 over the series; node 110 is
    # panel 'b' and sits at 320 throughout.
    assert window.coloring().clim == (300.0, 320.0)

    window.state.hide([solved.gmm.get_item("b").id])
    # Still the whole series, and now only the panel still on screen.
    assert window.coloring().clim == (300.0, 302.0)

    window.state.show_all()
    assert window.coloring().clim == (300.0, 320.0)

    # A single node that never moves leaves nothing to scale over.
    window.state.hide([solved.gmm.get_item("a").id])
    assert window.coloring().clim is None


def test_scrubbing_does_not_move_the_scale(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    before = window.coloring().clim
    window.time_panel.go_next()
    # The other half of the same rule: hiding may rescale, time may not, or the
    # same temperature would be a different colour at every instant.
    assert window.coloring().clim == before


# ── moving through time ───────────────────────────────────────────────────
def test_stepping_changes_the_values_and_nothing_else(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    panel = window.time_panel
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

    panel.go_previous()
    assert panel.slider.value() == len(CASE_TIMES) - 1
    panel.go_next()
    assert panel.slider.value() == 0


def test_play_runs_the_timer_until_it_is_stopped(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    panel = window.time_panel

    panel.play()
    assert panel.timer.isActive()
    assert panel.play_button.isChecked()

    panel.stop()
    assert not panel.timer.isActive()
    assert not panel.play_button.isChecked()


def test_a_case_with_no_time_axis_cannot_be_played(window: ViewerWindow) -> None:
    panel = window.time_panel
    panel.play()
    assert not panel.timer.isActive()


def test_closing_the_window_stops_the_animation(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    panel = window.time_panel
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


def test_closing_the_history_window_empties_it(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    window.plot_time_history(100)
    history = window.time_history
    assert history is not None
    assert history.curve_count() == 1

    history.close()
    # Reopened, it starts a new comparison rather than continuing the old one.
    assert history.curve_count() == 0
    window.plot_time_history(100)
    assert history.curve_count() == 1


def test_the_history_marker_follows_the_slider(window: ViewerWindow) -> None:
    select_case(window, "hot case")
    window.plot_time_history(100)
    panel = window.time_panel
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


def test_item_granularity_has_no_one_node_to_plot(
    window: ViewerWindow, solved: pc.ThermalModel
) -> None:
    select_case(window, "hot case")
    window.state.selection = Selection(
        item_id=solved.gmm.get_item("a").id, face_id=0, node_number=100, cell=0
    )
    assert "Plot time history of node 100" in dict(window.context_actions())

    # The whole item is selected, so the node under the cursor is not what the
    # menu would be about.
    window.state.picker_mode = PickerMode.ITEM
    assert "Plot time history of node 100" not in dict(window.context_actions())
