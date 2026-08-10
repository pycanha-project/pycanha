"""The viewer window, built around a placeholder 3D view.

Qt's ``offscreen`` platform has no OpenGL context, so a real
``pyvistaqt.QtInteractor`` cannot be constructed here - it segfaults, and a
segfault cannot be caught. The window therefore takes its 3D view as an
argument, and these tests pass a plain widget: everything except the pixels
still runs, including the arrays that would have been handed to VTK.
"""

import logging
from collections.abc import Iterator
from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtWidgets import QWidget

import pycanha as pc
from pycanha import gmm
from pycanha.plot.panels.info_panel import LOGGER_NAME, selection_rows
from pycanha.plot.picking import geometry_map
from pycanha.plot.properties import MISSING
from pycanha.plot.state import PickerMode, Selection
from pycanha.plot.window import ViewerWindow


def _two_panel_model() -> pc.ThermalModel:
    """A group of two 2x1 panels, 'a' painted white and 'b' bare."""
    tm = pc.ThermalModel("viewer")
    panels = []
    for index, name in enumerate(("a", "b")):
        thermal_mesh = gmm.ThermalMesh([0.0, 0.5, 1.0], [0.0, 1.0])
        thermal_mesh.node1_start = 100 + 10 * index
        thermal_mesh.node2_start = 200 + 10 * index
        if name == "a":
            thermal_mesh.side1_optical = gmm.OpticalMaterial("white", 0.85, 0.2)
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


@pytest.fixture
def model() -> gmm.GeometryModel:
    return _two_panel_model().gmm


@pytest.fixture
def window(model: gmm.GeometryModel, qtbot: object) -> Iterator[ViewerWindow]:
    del qtbot
    # Closed on the way out: the log tab holds a handler on the process-wide
    # ``pycanha`` logger for as long as the window is open.
    viewer = ViewerWindow(model, view=QWidget())
    yield viewer
    viewer.close()


# ── assembly ──────────────────────────────────────────────────────────────
def test_the_window_builds_without_a_3d_view(model: gmm.GeometryModel, qtbot: object) -> None:
    del qtbot
    window = ViewerWindow(model)
    try:
        assert window.plotter is None
        assert window.scene.n_cells == 16
        assert window.state.item_ids == frozenset(window.scene.item_ids)
    finally:
        window.close()


def test_a_placeholder_widget_is_not_mistaken_for_a_plotter(window: ViewerWindow) -> None:
    assert window.plotter is None
    # Everything that does not need pixels is still wired up.
    assert window.tree_panel.tree_model.root.name == "viewer"
    assert window.info_panel.count() == 2
    assert window.toolbar.picker_combo.count() == len(PickerMode)


def test_rebuilding_the_geometry_without_a_plotter_is_a_no_op(window: ViewerWindow) -> None:
    window.rebuild_geometry()
    window.state.hide([window.scene.item_ids[0]])
    assert window.scene.visible_cells.size == 8


# ── colouring ─────────────────────────────────────────────────────────────
def test_categorical_colouring_is_per_cell_rgb(window: ViewerWindow) -> None:
    window.state.color_by = "node_number"
    coloring = window.coloring()

    assert coloring.rgb
    assert coloring.values.shape == (window.scene.n_cells, 3)
    assert coloring.values.dtype == np.uint8
    # Four nodes, four colours - ranked first, or the sparse numbers would
    # collide modulo the palette size.
    assert len({tuple(row) for row in coloring.values}) == 4


def test_numeric_colouring_carries_a_colormap_and_limits(window: ViewerWindow) -> None:
    window.state.color_by = "area"
    coloring = window.coloring()

    assert not coloring.rgb
    assert coloring.values.shape == (window.scene.n_cells,)
    assert coloring.cmap == "viridis"
    assert coloring.title == "Face area [m^2]"
    # Every face here is 1 m2, so there is no range to scale over.
    assert coloring.clim is None


def test_a_reversed_log_scale_reaches_the_actor(window: ViewerWindow) -> None:
    window.state.color_by = "emissivity_ir"
    window.state.scale = replace(window.state.scale, reverse=True, log=True, colormap="plasma")
    coloring = window.coloring()

    assert coloring.cmap == "plasma_r"
    assert coloring.log_scale


def test_manual_limits_win_over_the_data(window: ViewerWindow) -> None:
    window.state.color_by = "emissivity_ir"
    window.state.scale = replace(window.state.scale, auto=False, limits=(0.0, 1.0))
    assert window.coloring().clim == (0.0, 1.0)


def test_hiding_narrows_the_colouring_to_what_is_drawn(
    window: ViewerWindow, model: gmm.GeometryModel
) -> None:
    window.state.color_by = "node_number"
    assert window.coloring().values.shape[0] == 16

    window.state.hide([model.get_item("a").id])
    assert window.coloring().values.shape[0] == 8


def test_an_all_missing_numeric_property_has_no_limits(window: ViewerWindow) -> None:
    # Nothing in this model has a bulk material.
    window.state.color_by = "density"
    coloring = window.coloring()
    assert np.all(np.isnan(coloring.values))
    assert coloring.clim is None


# ── highlighting ──────────────────────────────────────────────────────────
def test_the_highlight_follows_the_picker_granularity(
    window: ViewerWindow, model: gmm.GeometryModel
) -> None:
    item = model.get_item("a").id
    window.state.selection = Selection(item_id=item, face_id=0, node_number=100, cell=0)

    window.state.picker_mode = PickerMode.TRIANGLE
    assert np.array_equal(window.highlight(), [0])

    window.state.picker_mode = PickerMode.FACE
    assert np.array_equal(window.highlight(), window.scene.cells_of_face(0))

    window.state.picker_mode = PickerMode.ITEM
    assert np.array_equal(window.highlight(), window.scene.cells_of_item(item))


def test_selecting_a_group_highlights_its_whole_subtree(
    window: ViewerWindow, model: gmm.GeometryModel
) -> None:
    window.state.selection = Selection(item_id=model.get_group("wing").id)
    assert window.highlight().size == window.scene.n_cells


def test_the_highlight_never_shows_hidden_geometry(
    window: ViewerWindow, model: gmm.GeometryModel
) -> None:
    item = model.get_item("a").id
    window.state.picker_mode = PickerMode.ITEM
    window.state.selection = Selection(item_id=item)
    assert window.highlight().size == 8

    window.state.hide([item])
    assert window.highlight().size == 0


def test_nothing_selected_highlights_nothing(window: ViewerWindow) -> None:
    assert window.highlight().size == 0


# ── the toolbar ───────────────────────────────────────────────────────────
def test_show_all_from_the_toolbar_resets_visibility(
    window: ViewerWindow, model: gmm.GeometryModel
) -> None:
    window.state.hide([model.get_item("a").id])
    window.toolbar.show_all_action.trigger()
    assert window.state.hidden == frozenset()
    assert window.scene.visible_cells.size == window.scene.n_cells


def test_the_picker_combo_and_the_state_stay_in_step(window: ViewerWindow) -> None:
    window.toolbar.picker_combo.setCurrentIndex(0)
    # Qt flattens the StrEnum stored as item data, so the combo has to hand
    # back the enum rather than the bare string it kept.
    assert window.state.picker_mode is PickerMode.ITEM

    window.state.picker_mode = PickerMode.TRIANGLE
    assert window.toolbar.current_mode() is PickerMode.TRIANGLE


# ── the property table ────────────────────────────────────────────────────
def test_a_tree_selection_describes_the_geometry_alone(
    window: ViewerWindow, model: gmm.GeometryModel
) -> None:
    window.state.selection = Selection(item_id=model.get_group("wing").id)
    rows = dict(window.info_panel.rows())
    assert rows["Geometry"] == "wing"
    assert rows["Kind"] == "GeometryGroup"
    assert "Face slot" not in rows


def test_a_pick_describes_the_face_slot_too(window: ViewerWindow, model: gmm.GeometryModel) -> None:
    window.state.selection = Selection(
        item_id=model.get_item("a").id, face_id=0, node_number=100, cell=0
    )
    rows = dict(window.info_panel.rows())

    assert rows["Geometry"] == "a"
    assert rows["Primitive"] == "Rectangle"
    assert rows["Face slot"] == "0"
    assert rows["Side"] == "1"
    assert rows["TMM node"] == "100"
    assert rows["IR emissivity"] == "0.85"
    assert rows["Optical material"] == "white"
    # No bulk material anywhere in this model.
    assert rows["Density"] == MISSING


def test_the_odd_slot_of_a_face_reports_side_two(
    window: ViewerWindow, model: gmm.GeometryModel
) -> None:
    window.state.selection = Selection(item_id=model.get_item("a").id, face_id=1, node_number=200)
    rows = dict(window.info_panel.rows())
    assert rows["Side"] == "2"
    # Only side 1 of 'a' is painted.
    assert rows["Optical material"] == MISSING


def test_no_selection_is_an_empty_table(window: ViewerWindow) -> None:
    assert window.info_panel.rows() == []
    assert window.info_panel.table.rowCount() == 0


def test_the_table_repaints_when_the_selection_changes(
    window: ViewerWindow, model: gmm.GeometryModel
) -> None:
    window.state.selection = Selection(item_id=model.get_item("b").id)
    assert window.info_panel.table.rowCount() == len(window.info_panel.rows())
    cell = window.info_panel.table.item(0, 1)
    assert cell is not None
    assert cell.text() == "b"


def test_selection_rows_of_an_unknown_geometry(
    window: ViewerWindow, model: gmm.GeometryModel
) -> None:
    rows = selection_rows(geometry_map(model), window.properties, Selection(item_id=9999))
    assert rows == []


def test_formatting_a_slot_outside_the_property(window: ViewerWindow) -> None:
    assert window.properties["area"].format(999) == MISSING
    assert window.properties["area"].format(-1) == MISSING


# ── the log tab ───────────────────────────────────────────────────────────
def test_the_log_tab_receives_pycanha_records(window: ViewerWindow) -> None:
    logging.getLogger(LOGGER_NAME).warning("something to say")
    assert "something to say" in window.info_panel.log_view.toPlainText()


def test_closing_the_window_detaches_the_log_handler(window: ViewerWindow) -> None:
    logger = logging.getLogger(LOGGER_NAME)
    assert window.info_panel.handler in logger.handlers

    window.close()
    assert window.info_panel.handler not in logger.handlers


# ── an empty model ────────────────────────────────────────────────────────
def test_a_model_with_no_geometry_still_opens(qtbot: object) -> None:
    del qtbot
    window = ViewerWindow(pc.ThermalModel("empty").gmm, view=QWidget())
    try:
        assert window.scene.n_cells == 0
        assert window.coloring().values.shape[0] == 0
        assert window.highlight().size == 0
    finally:
        window.close()
