"""The geometry tree, with a name filter and a hide/show/expand context menu."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEvent, QItemSelectionModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLineEdit, QMenu, QTreeView, QVBoxLayout, QWidget

from ..state import Change, Selection
from ..tree_model import GeometryTreeModel

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtCore import QObject, QPoint

    from ..state import ViewState
    from ..tree_model import GeometryNode


class TreePanel(QWidget):
    """Name filter above a single-column view of the geometry hierarchy.

    Selection is bidirectional and single: clicking a row selects that geometry
    in the shared state, and a 3D pick that selects an item opens the groups
    above its row and scrolls it into view. Every context-menu action acts on
    the whole subtree of the row it is invoked on - hiding a group means hiding
    what is in it, and expanding one means opening everything below it.
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
        self.view.clicked.connect(self._on_clicked)
        self._collapse_to_top_level()
        # Clicking the empty space under the last row is how a selection is
        # dropped from here, the way clicking past the geometry drops it in the
        # 3D view. A QTreeView keeps its current row on such a click, so the
        # blank space is watched for directly.
        viewport = self.view.viewport()
        if viewport is not None:
            viewport.installEventFilter(self)

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
            self._collapse_to_top_level()

    # ── selection ─────────────────────────────────────────────────────────
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Drop the selection when the click landed on no row at all.

        Qt leaves the current row where it was when the blank space below the
        tree is clicked, so there is no signal to listen to: the press is
        watched for on the viewport instead. The event is not consumed - the
        view still gets it, and does nothing with it.
        """
        if event.type() is QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
            position = event.position().toPoint()
            if not self.view.indexAt(position).isValid():
                self._state.selection = None
        return super().eventFilter(watched, event)

    def _on_clicked(self, index: QModelIndex) -> None:
        """Select the row that was clicked, even if it was current already.

        A 3D pick can move the selection while the tree's current row stays
        where it is, and then clicking that row emits no ``currentChanged``.
        """
        if self._syncing:
            return
        node = self._node_at(index)
        if node is not None:
            self._state.selection = Selection(item_id=node.geometry_id)

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
                # The tree starts collapsed, and ``scrollTo`` does nothing for a
                # row inside a collapsed group, so a 3D pick has to open the way
                # down to its row before it can be scrolled into view.
                self._expand_ancestors(index)
                self.view.scrollTo(index)
            else:
                # The current row goes too, not just the highlight: a row that
                # stayed current could not be clicked back into the selection,
                # since clicking it would change nothing.
                selection_model.clearSelection()
                selection_model.clearCurrentIndex()
        finally:
            self._syncing = False

    # ── expanding ─────────────────────────────────────────────────────────
    def _collapse_to_top_level(self) -> None:
        """Show the model row and the geometry directly under it, nothing more.

        The tree opens this way and comes back to it when the filter is
        cleared, so a big model is a short list to start from rather than every
        item at once. The model row itself stays open because collapsing it too
        would leave a single row that says only the model's name.
        """
        self.view.collapseAll()
        self.view.expand(self.proxy.index(0, 0))

    def _expand_ancestors(self, index: QModelIndex) -> None:
        """Open every group above ``index``, so that its row is on screen."""
        parent = index.parent()
        while parent.isValid():
            self.view.expand(parent)
            parent = parent.parent()

    def _collapse_subtree(self, index: QModelIndex) -> None:
        """Collapse ``index`` and every row beneath it.

        Qt has ``expandRecursively`` but no collapsing counterpart, so the
        descendants are walked here - collapsing only the row itself would
        leave the rows inside it open the next time it is expanded.
        """
        for row in range(self.proxy.rowCount(index)):
            self._collapse_subtree(self.proxy.index(row, 0, index))
        self.view.collapse(index)

    # ── context menu ──────────────────────────────────────────────────────
    def context_actions(self, index: QModelIndex) -> list[tuple[str, Callable[[], None]]]:
        """What the right-click menu offers over ``index``, as label/callback pairs.

        Pairs rather than ``QAction``s so the menu is one line of Qt and the
        behaviour can be exercised headless, as the 3D menu is.

        Expand all and Collapse all are offered only on a row that has
        something under it, and act on that whole subtree; on a leaf they would
        be actions that do nothing.
        """
        node = self._node_at(index)
        if node is None:
            return []
        actions: list[tuple[str, Callable[[], None]]] = [
            ("Hide", lambda: self._state.hide(node.item_ids)),
            ("Show", lambda: self._state.show(node.item_ids)),
            ("Show only", lambda: self._state.show_only(node.item_ids)),
        ]
        if self.proxy.rowCount(index):
            actions.append(("Expand all", lambda: self.view.expandRecursively(index)))
            actions.append(("Collapse all", lambda: self._collapse_subtree(index)))
        return actions

    def _on_context_menu(self, position: QPoint) -> None:
        actions = self.context_actions(self.view.indexAt(position))
        if not actions:
            return
        menu = QMenu(self.view)
        for label, action in actions:
            menu.addAction(label, action)
        viewport = self.view.viewport()
        if viewport is not None:
            # Shown, not run: ``popup`` leaves the action to the normal event
            # loop instead of blocking this slot in a nested one, which is what
            # the viewer's other context menu needs and keeps the two the same.
            # The menu is parented to the view, so it outlives this call.
            menu.popup(viewport.mapToGlobal(position))

    # ── helpers ───────────────────────────────────────────────────────────
    def _node_at(self, index: QModelIndex) -> GeometryNode | None:
        """The tree node behind a *proxy* index, or ``None`` if there is none."""
        if not index.isValid():
            return None
        return self.tree_model.node(self.proxy.mapToSource(index))
