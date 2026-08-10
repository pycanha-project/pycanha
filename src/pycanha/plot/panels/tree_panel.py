"""The geometry tree, with a name filter and a hide/show context menu."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import QLineEdit, QMenu, QTreeView, QVBoxLayout, QWidget

from ..state import Change, Selection
from ..tree_model import GeometryTreeModel

if TYPE_CHECKING:
    from PySide6.QtCore import QPoint

    from ..state import ViewState
    from ..tree_model import GeometryNode


class TreePanel(QWidget):
    """Name filter above a single-column view of the geometry hierarchy.

    Selection is bidirectional and single: clicking a row selects that geometry
    in the shared state, and a 3D pick that selects an item scrolls its row
    into view. Hide, Show and Show only act on the whole subtree of the row
    they are invoked on - hiding a group means hiding what is in it.
    """

    def __init__(self, model: Any, state: ViewState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._syncing = False

        self.tree_model = GeometryTreeModel(model, state, self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.tree_model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        # Without this a matching child would be hidden along with its
        # non-matching parents, and filtering a nested model would show nothing.
        self.proxy.setRecursiveFilteringEnabled(True)

        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText("Filter by name")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._on_filter_changed)

        self.view = QTreeView(self)
        self.view.setModel(self.proxy)
        self.view.setHeaderHidden(True)
        self.view.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._on_context_menu)
        self.view.expandAll()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.filter_edit)
        layout.addWidget(self.view)

        selection_model = self.view.selectionModel()
        if selection_model is not None:
            selection_model.currentChanged.connect(self._on_current_changed)
        state.subscribe(self._on_state_change)

    # ── filtering ─────────────────────────────────────────────────────────
    def _on_filter_changed(self, text: str) -> None:
        self.proxy.setFilterFixedString(text)
        # A filtered tree is only useful with the matches on screen, and an
        # unfiltered one is only useful collapsed back to its top level.
        if text:
            self.view.expandAll()
        else:
            self.view.collapseAll()
            self.view.expand(self.proxy.index(0, 0))

    # ── selection ─────────────────────────────────────────────────────────
    def _on_current_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        del previous
        if self._syncing:
            return
        node = self._node_at(current)
        self._state.selection = None if node is None else Selection(item_id=node.geometry_id)

    def _on_state_change(self, change: Change) -> None:
        if change is not Change.SELECTION:
            return
        selection = self._state.selection
        selection_model = self.view.selectionModel()
        if selection_model is None:
            return
        index = (
            QModelIndex()
            if selection is None or selection.item_id is None
            else self.proxy.mapFromSource(self.tree_model.index_of(selection.item_id))
        )
        # Guarded, or setting the row here would come straight back as a user
        # selection and overwrite the pick that caused it.
        self._syncing = True
        try:
            if index.isValid():
                selection_model.setCurrentIndex(
                    index, QItemSelectionModel.SelectionFlag.ClearAndSelect
                )
                self.view.scrollTo(index)
            else:
                selection_model.clearSelection()
        finally:
            self._syncing = False

    # ── context menu ──────────────────────────────────────────────────────
    def _on_context_menu(self, position: QPoint) -> None:
        node = self._node_at(self.view.indexAt(position))
        if node is None:
            return
        menu = QMenu(self.view)
        menu.addAction("Hide", lambda: self._state.hide(node.item_ids))
        menu.addAction("Show", lambda: self._state.show(node.item_ids))
        menu.addAction("Show only", lambda: self._state.show_only(node.item_ids))
        viewport = self.view.viewport()
        if viewport is not None:
            menu.exec(viewport.mapToGlobal(position))

    # ── helpers ───────────────────────────────────────────────────────────
    def _node_at(self, index: QModelIndex) -> GeometryNode | None:
        """The tree node behind a *proxy* index, or ``None`` if there is none."""
        if not index.isValid():
            return None
        return self.tree_model.node(self.proxy.mapToSource(index))
