"""The viewer's toolbar: what a pick selects, how it is drawn, and the resets."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QIntValidator
from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QToolBar

from ..state import Change, EdgeDisplay, PickerMode

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtWidgets import QWidget

    from ..state import ViewState

#: What each picker mode means, in the order the combo offers them.
_PICKER_LABELS = {
    PickerMode.ITEM: "Item",
    PickerMode.FACE: "Face",
    PickerMode.TRIANGLE: "Triangle",
}

#: Width of the node-number entry boxes; they hold at most a few digits.
_NUMBER_BOX_WIDTH = 72


class ViewerToolBar(QToolBar):
    """Picker granularity, the edge and lighting toggles, the node filter, and
    the two resets.

    The granularity changes what a left-click in the 3D view selects,
    highlights and reports - nothing else. Hiding from the 3D view's
    right-click menu always acts on the owning geometry item whatever is chosen
    here, because a single face has no tree row of its own to remember a hidden
    state in.

    The node filter **greys** the faces it leaves out rather than hiding them:
    it is a display overlay, independent of what Hide has done, so there is one
    visibility mask and ``Show all`` means one thing. The range and the single
    node are two ways of setting the same filter, so each empties the other and
    ``Clear`` empties whichever is set.

    Two resets, because they undo different things: ``Show all`` brings back
    what is hidden, ``Reset`` puts the whole window - coloring, scale, filter,
    selection, camera - back to how it opened.
    """

    #: Emitted by ``Reset``. The state is only part of what a reset puts back,
    #: so the window is left to do it rather than the bar reaching for a
    #: plotter it has no business holding.
    reset_requested = Signal()

    def __init__(self, state: ViewState, parent: QWidget | None = None) -> None:
        super().__init__("Viewer", parent)
        self._state = state
        self._syncing = False

        self.addWidget(QLabel("Pick ", self))
        self.picker_combo = QComboBox(self)
        for mode, label in _PICKER_LABELS.items():
            self.picker_combo.addItem(label, mode)
        self.picker_combo.setCurrentIndex(list(_PICKER_LABELS).index(state.picker_mode))
        self.picker_combo.setToolTip("What a left-click in the 3D view selects and reports")
        self.picker_combo.currentIndexChanged.connect(self._on_picker_changed)
        self.addWidget(self.picker_combo)

        self.addSeparator()
        self.triangle_edges_action = self._edge_action(
            "Mesh", "Draw the triangulation of every face"
        )
        self.face_edges_action = self._edge_action(
            "Faces", "Outline every face of the thermal mesh"
        )
        self.primitive_edges_action = self._edge_action(
            "Primitives",
            "Outline every primitive.\n"
            "The mesher welds the two sides of a full-revolution seam into one "
            "set of vertices, so a closed primitive has no seam to draw: a full "
            "cylinder shows its two rims only, and a sphere shows nothing.",
        )

        self.addSeparator()
        self.lighting_action = self._action(
            "Lighting",
            "Shade the geometry.\n"
            "Off, every face shows exactly the color it stands for; on, the "
            "shading shows the shape and the colors are read less exactly.",
            self._on_lighting_changed,
            checkable=True,
        )
        self.lighting_action.setChecked(state.lighting)

        self.addSeparator()
        self.show_all_action = self._action(
            "Show all", "Show every hidden item and category again", self._on_show_all
        )
        self.reset_action = self._action(
            "Reset",
            "Put the whole view back to how it opened: coloring, scale, "
            "filter, selection, hidden geometry and camera",
            self._on_reset,
        )

        self.addSeparator()
        self.addWidget(QLabel(" Nodes ", self))
        self.node_lo_edit = self._number_box("from", "Grey every face outside this node range")
        self.addWidget(self.node_lo_edit)
        self.addWidget(QLabel("-", self))
        self.node_hi_edit = self._number_box("to", "Grey every face outside this node range")
        self.addWidget(self.node_hi_edit)
        for edit in (self.node_lo_edit, self.node_hi_edit):
            edit.editingFinished.connect(self._on_node_range_changed)

        self.addWidget(QLabel(" or node ", self))
        self.find_edit = self._number_box("node", "Grey every face except this node's")
        self.find_edit.editingFinished.connect(self._on_find_changed)
        self.addWidget(self.find_edit)
        self.clear_filter_action = self._action(
            "Clear", "Drop the node filter and un-grey everything", self._on_clear_filter
        )

        state.subscribe(self._on_state_change)
        self._sync_filters()

    def _action(
        self, text: str, tooltip: str, slot: Callable[..., None], *, checkable: bool = False
    ) -> QAction:
        """One button, added to the bar in place."""
        action = QAction(text, self)
        action.setToolTip(tooltip)
        action.setCheckable(checkable)
        if checkable:
            action.toggled.connect(slot)
        else:
            action.triggered.connect(slot)
        self.addAction(action)
        return action

    def _edge_action(self, text: str, tooltip: str) -> QAction:
        """One checkable edge toggle, added to the bar in place."""
        return self._action(text, tooltip, self._on_edges_changed, checkable=True)

    def _number_box(self, placeholder: str, tooltip: str) -> QLineEdit:
        """A narrow integer entry box, empty meaning "not set"."""
        edit = QLineEdit(self)
        edit.setPlaceholderText(placeholder)
        edit.setToolTip(tooltip)
        edit.setValidator(QIntValidator(self))
        edit.setFixedWidth(_NUMBER_BOX_WIDTH)
        edit.setClearButtonEnabled(True)
        return edit

    def current_mode(self) -> PickerMode:
        """The picker mode the combo is showing.

        Qt stores item data as a QVariant, which flattens a ``StrEnum`` to the
        plain string behind it - so the value has to be turned back into the
        enum, or every ``is PickerMode.ITEM`` downstream would quietly fail.
        """
        return PickerMode(self.picker_combo.currentData())

    def _on_picker_changed(self, index: int) -> None:
        del index
        if self._syncing:
            return
        self._state.picker_mode = self.current_mode()

    def _on_show_all(self, checked: bool = False) -> None:
        del checked
        self._state.show_all()

    def _on_reset(self, checked: bool = False) -> None:
        """Ask for the whole view back.

        A signal rather than ``state.reset()`` because a reset is more than the
        state: the camera and the results strip belong to the window, and the
        window is what puts all three back together.
        """
        del checked
        self.reset_requested.emit()

    def _on_lighting_changed(self, checked: bool = False) -> None:
        if self._syncing:
            return
        self._state.lighting = checked

    def _on_edges_changed(self, checked: bool = False) -> None:
        del checked
        if self._syncing:
            return
        self._state.edges = EdgeDisplay(
            triangles=self.triangle_edges_action.isChecked(),
            faces=self.face_edges_action.isChecked(),
            primitives=self.primitive_edges_action.isChecked(),
        )

    def _on_node_range_changed(self) -> None:
        """Apply the filter, or clear it while either end is still blank."""
        if self._syncing:
            return
        low, high = _number(self.node_lo_edit.text()), _number(self.node_hi_edit.text())
        if low is None or high is None:
            # Half a range is not a range yet - but it is also not a request to
            # drop a single node the other box is filtering on.
            if self._state.node_range is not None:
                self._state.clear_filter()
            return
        self._state.set_node_range(low, high)

    def _on_find_changed(self) -> None:
        if self._syncing:
            return
        node = _number(self.find_edit.text())
        if node is None:
            if self._state.found_node is not None:
                self._state.clear_filter()
            return
        self._state.found_node = node

    def _on_clear_filter(self, checked: bool = False) -> None:
        del checked
        self._state.clear_filter()

    def _on_state_change(self, change: Change) -> None:
        if change is Change.FILTER:
            self._sync_filters()
        elif change is Change.EDGES:
            self._sync_edges()
        elif change is Change.COLORING:
            self._sync_lighting()
        elif change is Change.PICKER:
            self._sync_picker()

    def _sync_picker(self) -> None:
        """Echo the granularity back, without coming round as a user choice."""
        self._syncing = True
        try:
            self.picker_combo.setCurrentIndex(list(_PICKER_LABELS).index(self._state.picker_mode))
        finally:
            self._syncing = False

    def _sync_lighting(self) -> None:
        """Echo the lighting toggle back, without coming round as a user click."""
        self._syncing = True
        try:
            self.lighting_action.setChecked(self._state.lighting)
        finally:
            self._syncing = False

    def _sync_edges(self) -> None:
        """Echo the edge toggles back, without coming round as a user click."""
        edges = self._state.edges
        self._syncing = True
        try:
            self.triangle_edges_action.setChecked(edges.triangles)
            self.face_edges_action.setChecked(edges.faces)
            self.primitive_edges_action.setChecked(edges.primitives)
        finally:
            self._syncing = False

    def _sync_filters(self) -> None:
        """Echo the filter into the boxes, without coming back round.

        Both boxes are written every time: the two are one filter, so setting
        either has to be seen to empty the other.
        """
        node_range = self._state.node_range
        found = self._state.found_node
        self._syncing = True
        try:
            low, high = ("", "") if node_range is None else (str(node_range[0]), str(node_range[1]))
            self.node_lo_edit.setText(low)
            self.node_hi_edit.setText(high)
            self.find_edit.setText("" if found is None else str(found))
        finally:
            self._syncing = False


def _number(text: str) -> int | None:
    """The integer typed into a box, or ``None`` when it is empty."""
    try:
        return int(text)
    except ValueError:
        return None
