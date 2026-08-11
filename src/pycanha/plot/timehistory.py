"""A window of node histories, one curve per node picked.

Separate from the viewer and non-modal, so the 3D window stays usable while it
is open, and **accumulating**: every node added draws another line with its own
legend entry until *Clear* is pressed. Comparing two nodes is the point of
plotting a history at all, and a window that replaced its curve on each pick
would make that two screenshots.

A vertical marker follows the time the viewer's slider is on, so the curve and
the coloured geometry always say the same thing about the same instant.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

if TYPE_CHECKING:
    import numpy.typing as npt
    from matplotlib.lines import Line2D

#: Colour of the line marking the instant the viewer is showing.
MARKER_COLOR = "0.4"


class TimeHistoryWindow(QWidget):
    """Node value against time, one line per node, with a *Clear* button."""

    def __init__(self, parent: QWidget | None = None) -> None:
        # A Window rather than a child widget: it is a second top-level window
        # that happens to be owned by the viewer, so closing the viewer closes
        # it too but it does not dock into anything.
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("pycanha - time history")
        self.resize(640, 420)

        self.figure = Figure(figsize=(6.0, 3.6), layout="constrained")
        self.axes = self.figure.add_subplot()
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.clear_button = QPushButton("Clear", self)
        self.clear_button.clicked.connect(self._on_clear)

        layout = QVBoxLayout(self)
        layout.addWidget(NavigationToolbar2QT(self.canvas, self))
        layout.addWidget(self.canvas)
        layout.addWidget(self.clear_button)

        self._marker: Line2D | None = None
        self._axis_label = ""
        self.clear()

    def add_history(
        self,
        label: str,
        times: npt.ArrayLike,
        values: npt.ArrayLike,
        *,
        axis_label: str = "",
    ) -> None:
        """Add one node's history, keeping every curve already drawn."""
        self.axes.plot(times, values, label=label, marker=".", markersize=3)
        if axis_label and axis_label != self._axis_label:
            self._axis_label = axis_label
            self.axes.set_ylabel(axis_label)
        self.axes.legend(loc="best", fontsize="small")
        self.canvas.draw_idle()

    def set_marker(self, time: float | None) -> None:
        """Move the vertical marker to the instant the viewer is showing."""
        if self._marker is not None:
            self._marker.remove()
            self._marker = None
        if time is not None:
            self._marker = self.axes.axvline(float(time), color=MARKER_COLOR, linewidth=1.0)
        self.canvas.draw_idle()

    def curve_count(self) -> int:
        """How many node histories are currently drawn."""
        return len(self.axes.lines) - (1 if self._marker is not None else 0)

    def clear(self) -> None:
        """Drop every curve and start again."""
        self.axes.clear()
        self._marker = None
        self.axes.set_xlabel("Time [s]")
        if self._axis_label:
            self.axes.set_ylabel(self._axis_label)
        self.axes.grid(visible=True, alpha=0.3)
        self.canvas.draw_idle()

    def _on_clear(self, checked: bool = False) -> None:
        del checked
        self.clear()
