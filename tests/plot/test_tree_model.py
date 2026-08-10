"""The geometry tree: shape, cut-group tagging, greying, filtering, selection."""

import numpy as np
import pytest
from PySide6.QtCore import QModelIndex, Qt

import pycanha as pc
from pycanha import gmm
from pycanha.plot.panels import TreePanel
from pycanha.plot.scene import Scene
from pycanha.plot.state import Selection, ViewState
from pycanha.plot.tree_model import (
    GEOMETRY_ID_ROLE,
    CutRole,
    GeometryNode,
    GeometryTreeModel,
    Kind,
    build_tree,
)


def _nested_model() -> pc.ThermalModel:
    """A group of two panels, plus a cut group of one plate and one cutter."""
    tm = pc.ThermalModel("demo")
    panels = [
        gmm.GeometryItem(
            name,
            gmm.Rectangle((offset, 0, 0), (offset + 1, 0, 0), (offset, 1, 0)),
            gmm.ThermalMesh(),
        )
        for offset, name in ((0.0, "A"), (2.0, "B"))
    ]
    tm.gmm.add(gmm.GeometryGroup("wing", panels))

    plate = gmm.GeometryItem(
        "plate", gmm.Rectangle((-2, -2, 0), (-1, -2, 0), (-2, -1, 0)), gmm.ThermalMesh()
    )
    hole = gmm.GeometryItem(
        "hole",
        gmm.Cylinder((-1.5, -1.5, -1), (-1.5, -1.5, 1), (-1.3, -1.5, -1), 0.2, 0.0, 2 * np.pi),
        gmm.ThermalMesh(),
    )
    tm.gmm.add(plate - hole)
    return tm


@pytest.fixture
def model() -> gmm.GeometryModel:
    return _nested_model().gmm


@pytest.fixture
def state(model: gmm.GeometryModel) -> ViewState:
    return ViewState(item_ids=Scene(model).item_ids)


@pytest.fixture
def tree(model: gmm.GeometryModel, state: ViewState) -> GeometryTreeModel:
    return GeometryTreeModel(model, state)


def _node(tree: GeometryTreeModel, name: str) -> GeometryNode:
    for node in tree.root.walk():
        if node.name == name:
            return node
    raise AssertionError(f"no tree row named {name!r}")


# ── shape ─────────────────────────────────────────────────────────────────
def test_the_model_is_the_single_top_level_row(model: gmm.GeometryModel) -> None:
    root = build_tree(model)
    assert root.name == "demo"
    assert root.kind is Kind.MODEL
    # ``plate - hole`` builds the cut group unnamed; the core names it on add.
    assert [child.name for child in root.children] == ["wing", "geo_0"]


def test_kinds_come_from_the_geometry_type(model: gmm.GeometryModel) -> None:
    root = build_tree(model)
    wing, cut = root.children
    assert wing.kind is Kind.GROUP
    assert cut.kind is Kind.CUT_GROUP
    assert all(child.kind is Kind.ITEM for child in wing.children)


def test_a_cut_group_lists_targets_then_cutters_tagged(model: gmm.GeometryModel) -> None:
    cut = build_tree(model).children[1]
    assert [(child.name, child.cut_role) for child in cut.children] == [
        ("plate", CutRole.TARGET),
        ("hole", CutRole.CUTTER),
    ]
    assert [child.label for child in cut.children] == ["[target] plate", "[cutter] hole"]


def test_a_model_without_a_name_still_gets_a_row(model: gmm.GeometryModel) -> None:
    del model
    # Geometry added to a model is always named by the core, so only the model
    # itself can reach the tree without one.
    assert build_tree(pc.ThermalModel("").gmm).name == "<unnamed>"


def test_item_ids_gather_the_whole_subtree(model: gmm.GeometryModel) -> None:
    root = build_tree(model)
    wing, cut = root.children
    assert wing.item_ids == {model.get_item(name).id for name in ("A", "B")}
    # A cutter is a row of its own, so hiding the cut group covers it too.
    assert cut.item_ids == {model.get_item(name).id for name in ("plate", "hole")}
    assert root.item_ids == wing.item_ids | cut.item_ids


# ── the Qt model ──────────────────────────────────────────────────────────
def test_indexes_walk_down_and_back_up(tree: GeometryTreeModel) -> None:
    assert tree.rowCount(QModelIndex()) == 1
    assert tree.columnCount(QModelIndex()) == 1

    root = tree.index(0, 0, QModelIndex())
    assert tree.data(root) == "demo"
    assert tree.rowCount(root) == 2

    wing = tree.index(0, 0, root)
    assert tree.data(wing) == "wing"
    assert tree.parent(wing) == root
    assert tree.parent(root) == QModelIndex()


def test_no_argument_parent_still_means_the_qobject_parent(
    model: gmm.GeometryModel, state: ViewState
) -> None:
    # Qt spells both on the same class; the override has to keep serving both.
    tree = GeometryTreeModel(model, state)
    assert tree.parent() is None


def test_rows_carry_their_geometry_id(tree: GeometryTreeModel, model: gmm.GeometryModel) -> None:
    root = tree.index(0, 0, QModelIndex())
    wing = tree.index(0, 0, root)
    panel = tree.index(0, 0, wing)
    assert tree.data(panel, GEOMETRY_ID_ROLE) == model.get_item("A").id
    assert tree.index_of(model.get_item("A").id) == panel


def test_index_of_an_unknown_geometry_is_invalid(tree: GeometryTreeModel) -> None:
    assert not tree.index_of(9999).isValid()


def test_the_tooltip_carries_the_primitive_the_label_leaves_out(tree: GeometryTreeModel) -> None:
    root = tree.index(0, 0, QModelIndex())
    panel = tree.index(0, 0, tree.index(0, 0, root))
    assert tree.data(panel, Qt.ItemDataRole.DisplayRole) == "A"
    assert tree.data(panel, Qt.ItemDataRole.ToolTipRole) == "A - Rectangle"


def test_an_invalid_index_has_no_data(tree: GeometryTreeModel) -> None:
    assert tree.data(QModelIndex()) is None
    assert tree.flags(QModelIndex()) == Qt.ItemFlag.NoItemFlags


# ── greying ───────────────────────────────────────────────────────────────
def test_a_row_greys_once_its_whole_subtree_is_hidden(
    tree: GeometryTreeModel, state: ViewState, model: gmm.GeometryModel
) -> None:
    wing = _node(tree, "wing")
    panel_a = _node(tree, "A")
    assert not tree.is_hidden(wing)

    state.hide([model.get_item("A").id])
    assert tree.is_hidden(panel_a)
    # Half the group is still visible, so the group is not greyed yet.
    assert not tree.is_hidden(wing)

    state.hide([model.get_item("B").id])
    assert tree.is_hidden(wing)


def test_hiding_repaints_the_affected_rows(
    tree: GeometryTreeModel, state: ViewState, model: gmm.GeometryModel, qtbot: object
) -> None:
    del qtbot
    changed: list[object] = []
    tree.dataChanged.connect(lambda *args: changed.append(args))
    state.hide([model.get_item("A").id])
    assert changed


def test_the_foreground_role_is_the_only_greying(
    tree: GeometryTreeModel, state: ViewState, model: gmm.GeometryModel, qtbot: object
) -> None:
    del qtbot
    root = tree.index(0, 0, QModelIndex())
    panel = tree.index(0, 0, tree.index(0, 0, root))
    assert tree.data(panel, Qt.ItemDataRole.ForegroundRole) is None

    state.hide([model.get_item("A").id])
    brush = tree.data(panel, Qt.ItemDataRole.ForegroundRole)
    assert brush is not None
    assert brush.color() == Qt.GlobalColor.gray
    # The row is still there, and still says the same thing.
    assert tree.data(panel) == "A"


# ── the panel ─────────────────────────────────────────────────────────────
@pytest.fixture
def panel(model: gmm.GeometryModel, state: ViewState, qtbot: object) -> TreePanel:
    del qtbot
    return TreePanel(model, state)


def test_filtering_keeps_matching_rows_and_their_parents(panel: TreePanel) -> None:
    panel.filter_edit.setText("plate")
    root = panel.proxy.index(0, 0)
    assert panel.proxy.rowCount(root) == 1

    cut = panel.proxy.index(0, 0, root)
    assert panel.proxy.rowCount(cut) == 1
    assert panel.proxy.data(panel.proxy.index(0, 0, cut)) == "[target] plate"

    panel.filter_edit.setText("")
    assert panel.proxy.rowCount(root) == 2


def test_the_context_menu_actions_hide_the_whole_subtree(
    panel: TreePanel, state: ViewState, model: gmm.GeometryModel
) -> None:
    wing = panel.tree_model.index_of(model.get_group("wing").id)
    node = panel.tree_model.node(wing)

    state.hide(node.item_ids)
    assert state.hidden == {model.get_item(name).id for name in ("A", "B")}

    state.show_only(node.item_ids)
    assert model.get_item("plate").id in state.hidden
    assert model.get_item("A").id not in state.hidden


def test_selecting_a_row_selects_that_geometry(
    panel: TreePanel, state: ViewState, model: gmm.GeometryModel
) -> None:
    index = panel.proxy.mapFromSource(panel.tree_model.index_of(model.get_item("B").id))
    selection_model = panel.view.selectionModel()
    assert selection_model is not None
    selection_model.setCurrentIndex(index, selection_model.SelectionFlag.ClearAndSelect)

    assert state.selection == Selection(item_id=model.get_item("B").id)


def test_a_pick_scrolls_the_owning_row_into_view(
    panel: TreePanel, state: ViewState, model: gmm.GeometryModel
) -> None:
    state.selection = Selection(item_id=model.get_item("plate").id, face_id=0, node_number=1)
    selection_model = panel.view.selectionModel()
    assert selection_model is not None

    current = panel.tree_model.node(panel.proxy.mapToSource(selection_model.currentIndex()))
    assert current.name == "plate"
    # The sync must not overwrite the pick with a bare tree selection.
    assert state.selection is not None
    assert state.selection.face_id == 0


def test_clearing_the_selection_clears_the_tree(panel: TreePanel, state: ViewState) -> None:
    state.selection = Selection(item_id=panel.tree_model.root.children[0].geometry_id)
    state.selection = None
    selection_model = panel.view.selectionModel()
    assert selection_model is not None
    assert not selection_model.selectedIndexes()
