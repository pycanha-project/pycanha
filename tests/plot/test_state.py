"""The Qt-free view state: visibility, selection, coloring, filters, notifications."""

from dataclasses import replace

import pytest

from pycanha.plot.state import (
    Change,
    ColorScale,
    PickerMode,
    Selection,
    ViewState,
)


@pytest.fixture
def state() -> ViewState:
    return ViewState(item_ids=[2, 3, 4])


@pytest.fixture
def changes(state: ViewState) -> list[Change]:
    """Every notification ``state`` emits, in order."""
    recorded: list[Change] = []
    state.subscribe(recorded.append)
    return recorded


# ── visibility ────────────────────────────────────────────────────────────
def test_nothing_is_hidden_to_begin_with(state: ViewState) -> None:
    assert state.hidden == frozenset()
    assert not state.is_hidden(2)


def test_hide_accumulates_and_show_removes(state: ViewState, changes: list[Change]) -> None:
    state.hide([2])
    state.hide([3])
    assert state.hidden == {2, 3}
    assert state.is_hidden(3)

    state.show([2])
    assert state.hidden == {3}
    assert changes == [Change.VISIBILITY] * 3


def test_show_only_hides_every_other_known_item(state: ViewState) -> None:
    state.show_only([3])
    assert state.hidden == {2, 4}


def test_show_all_resets_the_hidden_set(state: ViewState) -> None:
    state.hide([2, 3, 4])
    state.show_all()
    assert state.hidden == frozenset()


def test_hiding_an_item_that_owns_no_faces_is_remembered(state: ViewState) -> None:
    # A fully-cut item is not in ``item_ids`` - it produced no geometry - but it
    # still has a tree row, and that row has to be able to grey out.
    state.hide([99])
    assert state.is_hidden(99)


def test_show_all_leaves_the_node_filter_alone(state: ViewState) -> None:
    state.set_node_range(10, 20)
    state.hide([2])
    state.show_all()
    assert state.node_range == (10, 20)


def test_a_no_op_change_notifies_nobody(state: ViewState, changes: list[Change]) -> None:
    state.show_all()
    state.show([2])
    state.hide([])
    assert changes == []


# ── selection ─────────────────────────────────────────────────────────────
def test_selection_round_trips(state: ViewState, changes: list[Change]) -> None:
    picked = Selection(item_id=3, face_id=4, node_number=110, cell=7)
    state.selection = picked
    assert state.selection == picked

    state.selection = None
    assert state.selection is None
    assert changes == [Change.SELECTION] * 2


def test_reselecting_the_same_entity_notifies_nobody(
    state: ViewState, changes: list[Change]
) -> None:
    state.selection = Selection(item_id=3)
    state.selection = Selection(item_id=3)
    assert changes == [Change.SELECTION]


def test_picker_mode_defaults_to_face(state: ViewState, changes: list[Change]) -> None:
    assert state.picker_mode is PickerMode.FACE
    state.picker_mode = PickerMode.ITEM
    assert changes == [Change.PICKER]


# ── coloring ──────────────────────────────────────────────────────────────
def test_color_by_notifies_once_per_real_change(state: ViewState, changes: list[Change]) -> None:
    assert state.color_by == "face_id"
    state.color_by = "node_number"
    state.color_by = "node_number"
    assert changes == [Change.COLORING]


def test_scale_is_replaced_wholesale_so_one_knob_is_one_notification(
    state: ViewState, changes: list[Change]
) -> None:
    assert state.scale == ColorScale()
    state.scale = replace(state.scale, log=True, limits=(0.0, 400.0), auto=False)

    assert state.scale.log
    assert state.scale.limits == (0.0, 400.0)
    assert not state.scale.auto
    # The colormap came along untouched from the previous scale.
    assert state.scale.colormap == "viridis"
    assert changes == [Change.COLORING]


# ── filters ───────────────────────────────────────────────────────────────
def test_node_range_orders_its_bounds(state: ViewState) -> None:
    state.set_node_range(300, 100)
    assert state.node_range == (100, 300)


def test_clearing_the_node_range(state: ViewState, changes: list[Change]) -> None:
    state.clear_node_range()
    state.set_node_range(1, 5)
    state.clear_node_range()
    assert state.node_range is None
    assert changes == [Change.FILTER] * 2


def test_found_node_round_trips(state: ViewState, changes: list[Change]) -> None:
    assert state.found_node is None
    state.found_node = 110
    state.found_node = 110
    assert state.found_node == 110

    state.found_node = None
    assert changes == [Change.FILTER] * 2


def test_subscribers_all_hear_the_same_change(state: ViewState) -> None:
    first: list[Change] = []
    second: list[Change] = []
    state.subscribe(first.append)
    state.subscribe(second.append)
    state.hide([2])
    assert first == second == [Change.VISIBILITY]
