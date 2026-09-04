"""The properties of whatever is selected.

A two-column table describing the current selection - the geometry it belongs
to, the face and node behind it, and every color-by property's value
there - which is the detail the tree deliberately leaves out of its one column.

What it shows follows the **picker granularity**, not what the pick happened to
resolve. In Item mode the selection is a whole item, so the table says what the
item is and stops: the face under the cursor is how the item was reached, not
what was selected, and reporting its material would be answering a question
nobody asked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..picking import geometry_map
from ..properties import MISSING
from ..state import Change, PickerMode

if TYPE_CHECKING:
    from typing import Any

    from ..properties import FaceProperty
    from ..scene import Scene
    from ..state import Selection, ViewState

#: Properties the header rows already spell out, so not repeated below them.
_HEADER_KEYS = frozenset({"item", "node_number", "face_id", "side"})


def selection_rows(
    geometries: dict[int, Any],
    properties: dict[str, FaceProperty],
    selection: Selection | None,
    *,
    face_detail: bool = True,
) -> list[tuple[str, str]]:
    """The key/value rows describing ``selection``, in display order.

    A tree selection names a geometry and nothing else, so it gets the geometry
    rows alone. A pick also names a face, and everything the color-by
    properties can say about that face follows - unless ``face_detail`` is off,
    which is what an item-granularity selection asks for.
    """
    if selection is None:
        return []
    rows: list[tuple[str, str]] = []
    geometry = geometries.get(int(selection.item_id)) if selection.item_id is not None else None
    if geometry is not None:
        rows.append(("Geometry", str(geometry.name) or MISSING))
        rows.append(("Kind", type(geometry).__name__))
        primitive = getattr(geometry, "primitive", None)
        if primitive is not None:
            rows.append(("Primitive", type(primitive).__name__))
    if selection.face_id is None or not face_detail:
        return rows

    face = int(selection.face_id)
    node = selection.node_number
    rows.append(("Face", str(face)))
    # Side 1 faces are even, side 2 odd - the parity is the side.
    rows.append(("Side", str(1 + face % 2)))
    rows.append(("TMM node", MISSING if node is None else str(node)))
    rows += [
        (prop.label, prop.format(face))
        for key, prop in properties.items()
        if key not in _HEADER_KEYS
    ]
    return rows


class InfoPanel(QWidget):
    """The property table of the current selection."""

    def __init__(
        self,
        scene: Scene,
        properties: dict[str, FaceProperty],
        state: ViewState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._geometries = geometry_map(scene.model)
        self._properties = properties
        self._state = state

        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["Property", "Value"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        vertical = self.table.verticalHeader()
        if vertical is not None:
            vertical.setVisible(False)
        horizontal = self.table.horizontalHeader()
        if horizontal is not None:
            horizontal.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)

        state.subscribe(self._on_state_change)
        self.refresh()

    def rows(self) -> list[tuple[str, str]]:
        """The key/value rows the table is currently showing."""
        return selection_rows(
            self._geometries,
            self._properties,
            self._state.selection,
            face_detail=self._state.picker_mode is not PickerMode.ITEM,
        )

    def refresh(self) -> None:
        """Rebuild the property table from the current selection."""
        rows = self.rows()
        self.table.setRowCount(len(rows))
        for index, (key, value) in enumerate(rows):
            self.table.setItem(index, 0, QTableWidgetItem(key))
            self.table.setItem(index, 1, QTableWidgetItem(value))

    def _on_state_change(self, change: Change) -> None:
        # The granularity is part of what the table says, so a change of it is
        # a repaint as much as a change of selection is.
        if change in (Change.SELECTION, Change.PICKER, Change.RESULTS):
            self.refresh()
