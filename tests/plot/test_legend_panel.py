"""The appearance column: colour-by, the colour scale, and the interactive legend."""

from collections.abc import Iterator
from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

import pycanha as pc
from pycanha import gmm
from pycanha.plot.panels.legend_panel import (
    COLORMAPS,
    LegendPanel,
    colormap_icon,
    swatch_icon,
)
from pycanha.plot.properties import categories
from pycanha.plot.window import ViewerWindow


def _two_item_model() -> pc.ThermalModel:
    """Two 2x1 panels on their own nodes, 'a' painted white and 'b' black."""
    tm = pc.ThermalModel("legend")
    panels = []
    for index, (name, paint) in enumerate((("a", "white"), ("b", "black"))):
        thermal_mesh = gmm.ThermalMesh([0.0, 0.5, 1.0], [0.0, 1.0])
        thermal_mesh.node1_start = 100 + 10 * index
        thermal_mesh.node2_start = 200 + 10 * index
        thermal_mesh.side1_optical = gmm.OpticalMaterial(paint, 0.5 + 0.3 * index, 0.2)
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
def window(qtbot: object) -> Iterator[ViewerWindow]:
    del qtbot
    viewer = ViewerWindow(_two_item_model().gmm, view=QWidget())
    yield viewer
    viewer.close()


@pytest.fixture
def panel(window: ViewerWindow) -> LegendPanel:
    return window.legend_panel


# ── the icons ─────────────────────────────────────────────────────────────
def test_every_shortlisted_colormap_has_a_gradient_preview(qtbot: object) -> None:
    del qtbot
    for name, _ in COLORMAPS:
        assert not colormap_icon(name).isNull()
        assert not colormap_icon(name, reverse=True).isNull()


def test_a_swatch_is_a_solid_square(qtbot: object) -> None:
    del qtbot
    icon = swatch_icon((10, 20, 30))
    assert not icon.isNull()


# ── colour-by ─────────────────────────────────────────────────────────────
def test_the_combo_offers_every_property(window: ViewerWindow, panel: LegendPanel) -> None:
    assert panel.color_by_combo.count() == len(window.properties)
    assert panel.color_by_combo.itemText(0) == window.properties["item"].label


def test_choosing_a_property_recolours_the_geometry(
    window: ViewerWindow, panel: LegendPanel
) -> None:
    panel.color_by_combo.setCurrentIndex(panel.color_by_combo.findData("emissivity_ir"))
    assert window.state.color_by == "emissivity_ir"
    assert not window.coloring().rgb


def test_the_scale_controls_are_off_for_a_categorical_colouring(
    window: ViewerWindow, panel: LegendPanel
) -> None:
    window.state.color_by = "item"
    assert not panel.colormap_combo.isEnabled()
    assert not panel.log_box.isEnabled()
    assert panel.legend_list.isEnabled()

    window.state.color_by = "area"
    assert panel.colormap_combo.isEnabled()
    assert panel.log_box.isEnabled()
    assert not panel.legend_list.isEnabled()


# ── the colour scale ──────────────────────────────────────────────────────
def test_the_scale_widgets_write_through_to_the_state(
    window: ViewerWindow, panel: LegendPanel
) -> None:
    window.state.color_by = "emissivity_ir"
    panel.colormap_combo.setCurrentIndex(panel.colormap_combo.findData("plasma"))
    panel.reverse_box.setChecked(True)
    panel.log_box.setChecked(True)

    assert window.state.scale.colormap == "plasma"
    assert window.state.scale.reverse
    assert window.state.scale.log
    assert window.coloring().cmap == "plasma_r"


def test_manual_limits_are_read_off_the_two_boxes(window: ViewerWindow, panel: LegendPanel) -> None:
    window.state.color_by = "emissivity_ir"
    panel.auto_box.setChecked(False)
    panel.min_edit.setText("0.1")
    panel.max_edit.setText("0.9")
    panel.min_edit.editingFinished.emit()

    assert window.state.scale.limits == (0.1, 0.9)
    assert window.coloring().clim == (0.1, 0.9)


def test_half_typed_limits_fall_back_to_auto(window: ViewerWindow, panel: LegendPanel) -> None:
    window.state.color_by = "emissivity_ir"
    panel.auto_box.setChecked(False)
    panel.min_edit.setText("0.1")
    panel.max_edit.setText("")
    panel.min_edit.editingFinished.emit()

    assert window.state.scale.limits is None
    assert window.coloring().clim is None


def test_the_limit_boxes_follow_the_auto_toggle(window: ViewerWindow, panel: LegendPanel) -> None:
    window.state.color_by = "emissivity_ir"
    assert not panel.min_edit.isEnabled()
    panel.auto_box.setChecked(False)
    assert panel.min_edit.isEnabled()


# ── the legend ────────────────────────────────────────────────────────────
def test_the_legend_lists_one_row_per_category(window: ViewerWindow, panel: LegendPanel) -> None:
    window.state.color_by = "optical_name"
    labels = [panel.legend_list.item(row).text() for row in range(panel.legend_list.count())]
    # Side 1 of each panel is painted; side 2 of neither is.
    assert sorted(labels) == ["-", "black", "white"]


def test_the_swatch_colours_match_what_is_drawn(window: ViewerWindow) -> None:
    window.state.color_by = "node_number"
    prop = window.properties["node_number"]
    entries = categories(prop, window.scene.face_ids)
    colors = window.coloring().values

    for entry in entries:
        cells = np.flatnonzero(prop.per_cell(window.scene.face_ids) == entry.value)
        assert tuple(colors[cells[0]].tolist()) == entry.color


def test_hiding_a_category_removes_exactly_its_cells(
    window: ViewerWindow, panel: LegendPanel
) -> None:
    window.state.color_by = "node_number"
    panel.set_category_hidden(100, hidden=True)

    assert window.state.hidden_categories == {100}
    assert window.scene.visible_cells.size == 12
    assert 100 not in window.properties["node_number"].per_cell(
        window.scene.face_ids[window.scene.visible_cells]
    )


def test_isolating_a_category_hides_every_other_one(
    window: ViewerWindow, panel: LegendPanel
) -> None:
    window.state.color_by = "node_number"
    panel.isolate(110)

    assert window.state.hidden_categories == {100, 200, 210}
    assert window.scene.visible_cells.size == 4


def test_the_legend_checkboxes_show_what_is_hidden(
    window: ViewerWindow, panel: LegendPanel
) -> None:
    window.state.color_by = "node_number"
    panel.set_category_hidden(100, hidden=True)

    states = {
        panel.legend_list.item(row).data(int(Qt.ItemDataRole.UserRole) + 1): panel.legend_list.item(
            row
        ).checkState()
        for row in range(panel.legend_list.count())
    }
    assert states[100] is Qt.CheckState.Unchecked
    assert states[110] is Qt.CheckState.Checked


def test_hiding_a_category_does_not_recolour_the_rest(
    window: ViewerWindow, panel: LegendPanel
) -> None:
    # The ranked palette is built over every cell, not the visible ones, or
    # switching one category off would shift every other colour.
    window.state.color_by = "node_number"
    before = {
        entry.value: entry.color
        for entry in categories(window.properties["node_number"], window.scene.face_ids)
    }
    panel.set_category_hidden(100, hidden=True)
    after = {
        entry.value: entry.color
        for entry in categories(window.properties["node_number"], window.scene.face_ids)
    }
    assert before == after


def test_show_all_categories_puts_everything_back(window: ViewerWindow, panel: LegendPanel) -> None:
    window.state.color_by = "node_number"
    panel.isolate(110)
    panel.show_all_button.click()

    assert window.state.hidden_categories == frozenset()
    assert window.scene.visible_cells.size == window.scene.n_cells


def test_switching_the_colouring_clears_the_hidden_categories(
    window: ViewerWindow, panel: LegendPanel
) -> None:
    window.state.color_by = "node_number"
    panel.set_category_hidden(100, hidden=True)
    assert window.scene.visible_cells.size == 12

    # Category 100 means nothing under a different colouring, so it cannot
    # survive the switch.
    window.state.color_by = "item"
    assert window.state.hidden_categories == frozenset()
    assert window.scene.visible_cells.size == window.scene.n_cells


def test_geometry_and_category_hiding_compose(window: ViewerWindow, panel: LegendPanel) -> None:
    window.state.color_by = "side"
    panel.set_category_hidden(2, hidden=True)
    window.state.hide([window.model.get_item("a").id])

    # Side 1 of 'b' alone: 2 faces x 2 triangles.
    assert window.scene.visible_cells.size == 4
    window.state.show_all()
    assert window.scene.visible_cells.size == window.scene.n_cells


def test_a_numeric_colouring_has_no_categories(window: ViewerWindow, panel: LegendPanel) -> None:
    window.state.color_by = "area"
    assert panel.entries() == []
    assert window.category_mask() is None


def test_the_scale_survives_a_colour_by_change(window: ViewerWindow, panel: LegendPanel) -> None:
    window.state.scale = replace(window.state.scale, colormap="turbo")
    window.state.color_by = "emissivity_ir"
    assert panel.colormap_combo.currentData() == "turbo"
