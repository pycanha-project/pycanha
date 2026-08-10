"""The bottom pane: what is selected, and what the run has had to say.

Two tabs. **Properties** describes the current selection - the geometry it
belongs to, the face slot and node behind it, and every colour-by property's
value there - which is the detail the tree deliberately leaves out of its one
column. **Log** is append-only and carries the history the console ``print``
used to: it is a handler on the ``pycanha`` stdlib logger, so what lands in it
is exactly what the run recorded, from the C++ core as much as from here.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QWidget,
)

from ..picking import geometry_map
from ..properties import MISSING
from ..state import Change

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from ..properties import FaceProperty
    from ..scene import Scene
    from ..state import Selection, ViewState

#: stdlib logger every pycanha record reaches, C++ core records included.
LOGGER_NAME = "pycanha"

#: Properties the header rows already spell out, so not repeated below them.
_HEADER_KEYS = frozenset({"item", "node_number", "face_id", "side"})


def selection_rows(
    geometries: dict[int, Any],
    properties: dict[str, FaceProperty],
    selection: Selection | None,
) -> list[tuple[str, str]]:
    """The key/value rows describing ``selection``, in display order.

    A tree selection names a geometry and nothing else, so it gets the geometry
    rows alone. A pick also names a face slot, and everything the colour-by
    properties can say about that slot follows.
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
    if selection.face_id is None:
        return rows

    slot = int(selection.face_id)
    node = selection.node_number
    rows.append(("Face slot", str(slot)))
    # Side 1 slots are even, side 2 odd - the parity is the side.
    rows.append(("Side", str(1 + slot % 2)))
    rows.append(("TMM node", MISSING if node is None else str(node)))
    rows += [
        (prop.label, prop.format(slot))
        for key, prop in properties.items()
        if key not in _HEADER_KEYS
    ]
    return rows


class LogHandler(logging.Handler):
    """A ``logging`` handler that appends formatted records through a callback."""

    def __init__(self, append: Callable[[str], None]) -> None:
        super().__init__()
        self._append = append

    def emit(self, record: logging.LogRecord) -> None:
        self._append(self.format(record))


class InfoPanel(QTabWidget):
    """Properties of the current selection, and the log, as two tabs."""

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

        self.log_view = QPlainTextEdit(self)
        self.log_view.setReadOnly(True)
        # The log is a running trail, not an archive; the file on disk is that.
        self.log_view.setMaximumBlockCount(2000)

        self.addTab(self.table, "Properties")
        self.addTab(self.log_view, "Log")

        # The logger is process-global, so the handler is a resource this panel
        # holds for its lifetime: attached here, dropped by ``detach`` when the
        # window closes, and dropped again by the destroyed backstop if it never
        # does. Leaving it attached would eventually deliver a record to a
        # widget Qt has already deleted. The lambda captures the handler alone
        # for exactly that reason - by then there is no panel left to reach.
        self.handler = LogHandler(self.append_log)
        self.handler.setFormatter(logging.Formatter("%(levelname)s  %(message)s"))
        handler = self.handler
        self.destroyed.connect(lambda: logging.getLogger(LOGGER_NAME).removeHandler(handler))
        logging.getLogger(LOGGER_NAME).addHandler(self.handler)

        state.subscribe(self._on_state_change)
        self.refresh()

    def append_log(self, message: str) -> None:
        """Add one line to the log tab."""
        self.log_view.appendPlainText(message)

    def rows(self) -> list[tuple[str, str]]:
        """The key/value rows the table is currently showing."""
        return selection_rows(self._geometries, self._properties, self._state.selection)

    def refresh(self) -> None:
        """Rebuild the property table from the current selection."""
        rows = self.rows()
        self.table.setRowCount(len(rows))
        for index, (key, value) in enumerate(rows):
            self.table.setItem(index, 0, QTableWidgetItem(key))
            self.table.setItem(index, 1, QTableWidgetItem(value))

    def detach(self) -> None:
        """Stop receiving log records, before the widget goes away."""
        logging.getLogger(LOGGER_NAME).removeHandler(self.handler)

    def _on_state_change(self, change: Change) -> None:
        if change is Change.SELECTION:
            self.refresh()
