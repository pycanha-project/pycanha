"""The node filter: one filter, set as a range or as a single node, that greys
what it leaves out and never hides it."""

from collections.abc import Iterator

import numpy as np
import pytest
from PySide6.QtWidgets import QWidget

import pycanha as pc
from pycanha import gmm
from pycanha.plot.panels.toolbar import ViewerToolBar
from pycanha.plot.window import FILTERED_RGB, ViewerWindow


def _two_item_model() -> pc.ThermalModel:
    """Two 2x1 panels: 'a' on nodes 100/200, 'b' on 110/210."""
    tm = pc.ThermalModel("filters")
    for index, name in enumerate(("a", "b")):
        thermal_mesh = gmm.ThermalMesh([0.0, 0.5, 1.0], [0.0, 1.0])
        thermal_mesh.node1_start = 100 + 10 * index
        thermal_mesh.node2_start = 200 + 10 * index
        height = float(index)
        tm.gmm.add(
            gmm.GeometryItem(
                name,
                gmm.Rectangle((0, 0, height), (2, 0, height), (0, 1, height)),
                thermal_mesh,
            )
        )
    return tm


@pytest.fixture
def window(qtbot: object) -> Iterator[ViewerWindow]:
    del qtbot
    viewer = ViewerWindow(_two_item_model().gmm, view=QWidget())
    yield viewer
    viewer.close()


@pytest.fixture
def toolbar(window: ViewerWindow) -> ViewerToolBar:
    return window.toolbar


# ── the node filter ───────────────────────────────────────────────────────
def test_the_filter_greys_and_never_hides(window: ViewerWindow) -> None:
    window.state.set_node_range(100, 100)

    # Every cell is still drawn - that is the whole point of greying.
    assert window.scene.visible_cells.size == window.scene.n_cells
    filtered = window.filtered_out()
    assert filtered is not None
    assert filtered.sum() == 12
    assert not np.any(filtered[window.scene.node_numbers == 100])


def test_a_categorical_colouring_greys_the_filtered_cells(window: ViewerWindow) -> None:
    window.state.color_by = "node_number"
    window.state.set_node_range(100, 100)
    colors = window.coloring().values

    in_range = window.scene.node_numbers == 100
    assert np.all(colors[~in_range] == FILTERED_RGB)
    assert not np.any(np.all(colors[in_range] == FILTERED_RGB, axis=1))


def test_a_numeric_colouring_greys_through_nan(window: ViewerWindow) -> None:
    window.state.color_by = "area"
    window.state.set_node_range(110, 210)
    values = window.coloring().values

    # nan is what the actor draws in its nan_color, which is the grey.
    out_of_range = (window.scene.node_numbers < 110) | (window.scene.node_numbers > 210)
    assert np.all(np.isnan(values[out_of_range]))
    assert not np.any(np.isnan(values[~out_of_range]))


def test_the_filter_is_independent_of_hiding(
    window: ViewerWindow,
) -> None:
    window.state.hide([window.model.get_item("a").id])
    window.state.set_node_range(110, 110)

    filtered = window.filtered_out()
    assert filtered is not None
    # Only 'b' is drawn, and only its side-1 cells are in range.
    assert filtered.size == 8
    assert filtered.sum() == 4

    # Show all is about visibility; the filter is a separate overlay.
    window.state.show_all()
    assert window.state.node_range == (110, 110)
    assert window.scene.visible_cells.size == window.scene.n_cells


def test_clearing_the_filter_ungreys_everything(window: ViewerWindow) -> None:
    window.state.set_node_range(100, 100)
    window.state.clear_filter()
    assert window.filtered_out() is None


def test_the_toolbar_boxes_drive_the_filter(window: ViewerWindow, toolbar: ViewerToolBar) -> None:
    toolbar.node_lo_edit.setText("100")
    toolbar.node_hi_edit.setText("110")
    toolbar.node_hi_edit.editingFinished.emit()
    assert window.state.node_range == (100, 110)

    # A half-filled range is not a range yet.
    toolbar.node_hi_edit.setText("")
    toolbar.node_hi_edit.editingFinished.emit()
    assert window.state.node_range is None


def test_the_clear_button_drops_whichever_filter_is_set(
    window: ViewerWindow, toolbar: ViewerToolBar
) -> None:
    window.state.set_node_range(100, 110)
    toolbar.clear_filter_action.trigger()
    assert not window.state.filtered
    assert toolbar.node_lo_edit.text() == ""
    assert toolbar.node_hi_edit.text() == ""

    window.state.found_node = 110
    toolbar.clear_filter_action.trigger()
    assert not window.state.filtered
    assert toolbar.find_edit.text() == ""


def test_the_boxes_echo_a_filter_set_elsewhere(
    window: ViewerWindow, toolbar: ViewerToolBar
) -> None:
    window.state.set_node_range(210, 110)
    # The bounds are ordered, so a range typed backwards still selects one.
    assert toolbar.node_lo_edit.text() == "110"
    assert toolbar.node_hi_edit.text() == "210"


# ── one node ──────────────────────────────────────────────────────────────
def test_one_node_greys_everything_else(window: ViewerWindow) -> None:
    window.state.color_by = "node_number"
    window.state.found_node = 110
    colors = window.coloring().values

    # Exactly the same rule the range follows: the node keeps the colour it is
    # drawn in and the rest go grey. Nothing is hidden, and nothing is painted
    # a colour of its own.
    on_node = window.scene.node_numbers == 110
    assert on_node.sum() == 4
    assert window.scene.visible_cells.size == window.scene.n_cells
    assert np.all(colors[~on_node] == FILTERED_RGB)
    assert not np.any(np.all(colors[on_node] == FILTERED_RGB, axis=1))


def test_a_node_and_a_range_are_the_same_filter(window: ViewerWindow) -> None:
    window.state.set_node_range(100, 110)
    window.state.found_node = 110
    # Setting one drops the other; the bounds are what both come down to.
    assert window.state.node_range is None
    assert window.state.node_bounds() == (110, 110)

    window.state.set_node_range(100, 110)
    assert window.state.found_node is None
    assert window.state.node_bounds() == (100, 110)


def test_a_node_that_is_not_there_greys_everything(window: ViewerWindow) -> None:
    window.state.found_node = 9999
    filtered = window.filtered_out()
    assert filtered is not None
    assert bool(np.all(filtered))


def test_clearing_the_find_box_ungreys_everything(
    window: ViewerWindow, toolbar: ViewerToolBar
) -> None:
    toolbar.find_edit.setText("110")
    toolbar.find_edit.editingFinished.emit()
    assert window.state.found_node == 110

    toolbar.find_edit.setText("")
    toolbar.find_edit.editingFinished.emit()
    assert window.state.found_node is None
    assert window.filtered_out() is None


def test_the_boxes_show_which_way_the_filter_was_set(
    window: ViewerWindow, toolbar: ViewerToolBar
) -> None:
    window.state.found_node = 210
    assert toolbar.find_edit.text() == "210"
    assert toolbar.node_lo_edit.text() == ""

    window.state.set_node_range(100, 110)
    assert toolbar.find_edit.text() == ""
    assert (toolbar.node_lo_edit.text(), toolbar.node_hi_edit.text()) == ("100", "110")
