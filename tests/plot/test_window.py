"""The viewer window, built around a placeholder 3D view.

Qt's ``offscreen`` platform has no OpenGL context, so a real
``pyvistaqt.QtInteractor`` cannot be constructed here - it segfaults, and a
segfault cannot be caught. The window therefore takes its 3D view as an
argument, and these tests pass a plain widget: everything except the pixels
still runs, including the arrays that would have been handed to VTK.
"""

from collections.abc import Iterator
from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtWidgets import QWidget

import pycanha as pc
from pycanha import gmm
from pycanha.plot.panels.info_panel import selection_rows
from pycanha.plot.picking import geometry_map
from pycanha.plot.properties import MISSING
from pycanha.plot.state import DEFAULT_COLOR_BY, PickerMode, Selection
from pycanha.plot.window import ViewerWindow, brighten


def _two_panel_model() -> pc.ThermalModel:
    """A group of two 2x1 panels, 'a' painted white and red, and 'b' bare."""
    tm = pc.ThermalModel("viewer")
    panels = []
    for index, name in enumerate(("a", "b")):
        thermal_mesh = gmm.ThermalMesh([0.0, 0.5, 1.0], [0.0, 1.0])
        thermal_mesh.node1_start = 100 + 10 * index
        thermal_mesh.node2_start = 200 + 10 * index
        if name == "a":
            thermal_mesh.side1_optical = gmm.OpticalMaterial("white", 0.85, 0.2)
            thermal_mesh.side1_color = gmm.Color(255, 0, 0)
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
    # Closed on the way out, so the animation timer never outlives the widgets
    # it drives.
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
    assert window.info_panel.table.columnCount() == 2
    assert window.toolbar.picker_combo.count() == len(PickerMode)


def test_the_window_opens_on_the_colour_the_model_carries(window: ViewerWindow) -> None:
    assert window.state.color_by == DEFAULT_COLOR_BY
    coloring = window.coloring()
    assert coloring.rgb
    # Side 1 of 'a' was painted red; every cell of it is drawn in exactly that.
    red = np.all(coloring.values == (255, 0, 0), axis=1)
    assert red.sum() == 4


def test_the_results_strip_is_dead_without_results(window: ViewerWindow) -> None:
    # It is there so the window keeps its shape, and offers nothing to move.
    assert not window.has_results
    assert not window.time_panel.isEnabled()
    assert window.time_panel.case_combo.count() == 0


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
    assert window.highlight_colors().shape == (0, 3)
    assert window.highlight_outline().shape == (0, 2)


def test_the_highlight_is_the_drawn_colour_made_brighter(window: ViewerWindow) -> None:
    window.state.selection = Selection(item_id=window.model.get_item("a").id, face_id=0, cell=0)
    window.state.picker_mode = PickerMode.FACE

    cells = window.highlight()
    drawn = window.cell_colors()[window.scene.visible_index(cells)]
    # Side 1 of 'a' is red, and the highlight is that red, brighter.
    assert np.all(drawn == (255, 0, 0))
    assert np.array_equal(window.highlight_colors(), brighten(drawn))
    assert np.all(window.highlight_colors() > drawn.astype(int) - 1)


def test_a_numeric_colouring_is_brightened_from_its_colormap(window: ViewerWindow) -> None:
    window.state.color_by = "emissivity_ir"
    window.state.selection = Selection(item_id=window.model.get_item("a").id, face_id=0, cell=0)

    colors = window.cell_colors()
    assert colors.shape == (window.scene.n_cells, 3)
    assert np.array_equal(
        window.highlight_colors(), brighten(colors[window.scene.visible_index(window.highlight())])
    )


def test_the_outline_rings_the_selected_face_once(window: ViewerWindow) -> None:
    window.state.selection = Selection(item_id=window.model.get_item("a").id, face_id=0, cell=0)
    # One quad face, meshed as two triangles: four boundary edges, and the
    # shared diagonal is not one of them.
    assert window.highlight_outline().shape == (4, 2)


def test_the_outline_of_a_two_sided_item_is_its_own_boundary(window: ViewerWindow) -> None:
    # Both sides of every face are in the scene, coincident, so an outline
    # taken over the cells would find no boundary at all.
    window.state.picker_mode = PickerMode.ITEM
    window.state.selection = Selection(item_id=window.model.get_item("a").id)
    assert window.highlight_outline().shape[0] > 0


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


# ── the 3D context menu ───────────────────────────────────────────────────
def test_the_context_menu_over_nothing_only_resets(window: ViewerWindow) -> None:
    assert [label for label, _ in window.context_actions()] == ["Show all"]


def test_the_context_menu_names_the_owning_geometry(
    window: ViewerWindow, model: gmm.GeometryModel
) -> None:
    item = model.get_item("a").id
    window.state.selection = Selection(item_id=item, face_id=0, node_number=100, cell=0)
    assert [label for label, _ in window.context_actions()] == [
        "Hide a",
        "Show only a",
        "Show all",
    ]


def test_hiding_from_the_context_menu_acts_on_the_item(
    window: ViewerWindow, model: gmm.GeometryModel
) -> None:
    # Whatever the picker granularity, Hide acts on the whole owning item: a
    # triangle has no tree row of its own to remember a hidden state in.
    window.state.picker_mode = PickerMode.TRIANGLE
    window.state.selection = Selection(item_id=model.get_item("b").id, face_id=4, cell=2)
    actions = dict(window.context_actions())
    actions["Hide b"]()

    assert window.state.hidden == frozenset({model.get_item("b").id})
    assert window.scene.visible_cells.size == 8


def test_show_only_from_the_context_menu_hides_the_rest(
    window: ViewerWindow, model: gmm.GeometryModel
) -> None:
    window.state.selection = Selection(item_id=model.get_item("a").id)
    dict(window.context_actions())["Show only a"]()
    assert window.state.hidden == frozenset({model.get_item("b").id})


def test_selecting_a_group_offers_the_whole_subtree(
    window: ViewerWindow, model: gmm.GeometryModel
) -> None:
    window.state.selection = Selection(item_id=model.get_group("wing").id)
    dict(window.context_actions())["Hide wing"]()
    assert window.state.hidden == frozenset(window.scene.item_ids)


def test_picking_without_a_plotter_is_a_no_op(window: ViewerWindow) -> None:
    window.state.selection = Selection(item_id=window.scene.item_ids[0])
    window.pick_at(10, 10)
    assert window.state.selection is not None


# ── the property table ────────────────────────────────────────────────────
def test_item_granularity_reports_the_item_alone(
    window: ViewerWindow, model: gmm.GeometryModel
) -> None:
    # The face under the cursor is how the item was reached, not what was
    # selected, so none of its detail is reported.
    window.state.picker_mode = PickerMode.ITEM
    window.state.selection = Selection(
        item_id=model.get_item("a").id, face_id=0, node_number=100, cell=0
    )
    rows = dict(window.info_panel.rows())

    assert rows["Geometry"] == "a"
    assert rows["Kind"] == "GeometryItem"
    assert rows["Primitive"] == "Rectangle"
    assert "Face slot" not in rows
    assert "TMM node" not in rows


def test_the_colour_is_one_of_the_reported_properties(
    window: ViewerWindow, model: gmm.GeometryModel
) -> None:
    window.state.selection = Selection(item_id=model.get_item("a").id, face_id=0, cell=0)
    assert dict(window.info_panel.rows())["Colour"] == "255, 0, 0"


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


# ── lighting ──────────────────────────────────────────────────────────────
def test_the_geometry_is_drawn_flat_until_lighting_is_asked_for(window: ViewerWindow) -> None:
    assert not window.coloring().lighting

    window.toolbar.lighting_action.setChecked(True)
    assert window.state.lighting
    assert window.coloring().lighting


# ── reset ─────────────────────────────────────────────────────────────────
def test_reset_puts_every_knob_back(window: ViewerWindow, model: gmm.GeometryModel) -> None:
    window.state.hide([model.get_item("a").id])
    window.state.color_by = "node_number"
    window.state.set_node_range(100, 100)
    window.state.picker_mode = PickerMode.TRIANGLE
    window.state.lighting = True
    window.state.selection = Selection(item_id=model.get_item("b").id)

    window.toolbar.reset_action.trigger()

    assert window.state.hidden == frozenset()
    assert window.state.color_by == DEFAULT_COLOR_BY
    assert not window.state.filtered
    assert window.state.picker_mode is PickerMode.FACE
    assert not window.state.lighting
    assert window.state.selection is None
    assert window.scene.visible_cells.size == window.scene.n_cells


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
