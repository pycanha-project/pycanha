"""The viewer's toolbar: what a pick selects, and the global visibility reset."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction, QIntValidator
from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QToolBar

from ..state import Change, PickerMode

if TYPE_CHECKING:
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
    """Picker granularity, ``Show all``, the node filter and find-node.

    The granularity changes what a pick selects, highlights and reports -
    nothing else. Hiding from the 3D view always acts on the owning geometry
    item whatever is chosen here, because a single face has no tree row of its
    own to remember a hidden state in.

    The node filter **greys** the faces outside its range rather than hiding
    them: it is a display overlay, independent of what Hide has done, so there
    is one visibility mask and ``Show all`` means one thing. Find-node
    highlights a node's faces and deliberately leaves the camera alone.
    """

    def __init__(self, state: ViewState, parent: QWidget | None = None) -> None:
        super().__init__("Viewer", parent)
        self._state = state
        self._syncing = False

        self.addWidget(QLabel("Pick ", self))
        self.picker_combo = QComboBox(self)
        for mode, label in _PICKER_LABELS.items():
            self.picker_combo.addItem(label, mode)
        self.picker_combo.setCurrentIndex(list(_PICKER_LABELS).index(state.picker_mode))
        self.picker_combo.setToolTip("What a pick selects and reports")
        self.picker_combo.currentIndexChanged.connect(self._on_picker_changed)
        self.addWidget(self.picker_combo)

        self.addSeparator()
        self.show_all_action = QAction("Show all", self)
        self.show_all_action.setToolTip("Show every hidden item and category again")
        self.show_all_action.triggered.connect(self._on_show_all)
        self.addAction(self.show_all_action)

        self.addSeparator()
        self.addWidget(QLabel(" Nodes ", self))
        self.node_lo_edit = self._number_box("from", "Grey every face outside this node range")
        self.addWidget(self.node_lo_edit)
        self.addWidget(QLabel("-", self))
        self.node_hi_edit = self._number_box("to", "Grey every face outside this node range")
        self.addWidget(self.node_hi_edit)
        for edit in (self.node_lo_edit, self.node_hi_edit):
            edit.editingFinished.connect(self._on_node_range_changed)

        self.addSeparator()
        self.addWidget(QLabel(" Find node ", self))
        self.find_edit = self._number_box("node", "Highlight the faces of one node")
        self.find_edit.editingFinished.connect(self._on_find_changed)
        self.addWidget(self.find_edit)

        state.subscribe(self._on_state_change)

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

    def _on_node_range_changed(self) -> None:
        """Apply the filter, or clear it while either end is still blank."""
        if self._syncing:
            return
        low, high = _number(self.node_lo_edit.text()), _number(self.node_hi_edit.text())
        if low is None or high is None:
            self._state.clear_node_range()
        else:
            self._state.set_node_range(low, high)

    def _on_find_changed(self) -> None:
        if self._syncing:
            return
        self._state.found_node = _number(self.find_edit.text())

    def _on_state_change(self, change: Change) -> None:
        if change is Change.FILTER:
            self._sync_filters()
            return
        if change is not Change.PICKER:
            return
        # Guarded, or echoing the state back into the combo would come round
        # again as a user choice.
        self._syncing = True
        try:
            self.picker_combo.setCurrentIndex(list(_PICKER_LABELS).index(self._state.picker_mode))
        finally:
            self._syncing = False

    def _sync_filters(self) -> None:
        """Echo the filter state into the boxes, without coming back round."""
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
