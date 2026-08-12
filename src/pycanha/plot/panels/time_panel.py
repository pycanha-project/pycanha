"""The results strip: which case, which attribute, and which instant.

One row under the 3D view. The case combo lists the solved cases already in the
model plus the live node state; the attribute combo lists what that case has
data for. The slider **snaps to stored instants** - there is no position
between two of them - and play, prev and next move between the same instants.

The panel only writes a :class:`~pycanha.plot.state.ResultSelection` into the
shared state. Reading the values out of the model and turning them into a
colouring is :mod:`pycanha.plot.results`' job, and painting them is the
window's.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider, QWidget

from ..results import ATTRIBUTES, attributes, cases
from ..state import ResultSelection

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..results import ResultSeries
    from ..state import ViewState

#: How long one frame of an animation is shown, in milliseconds.
FRAME_INTERVAL_MS = 200

#: Width of the transport buttons, which hold one glyph each.
_BUTTON_WIDTH = 32


class TimePanel(QWidget):
    """Case, attribute, transport controls and the time slider.

    Always built, so the window keeps its shape whatever it was opened on, and
    left **disabled** by the window until a result is what the geometry is
    coloured by: what this strip controls is which instant of that colouring is
    on screen, so with anything else drawn there is nothing for it to move. A
    model with nothing solved simply offers no cases, and it never enables.
    """

    def __init__(
        self,
        thermal_model: Any,
        state: ViewState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._thermal_model = thermal_model
        self._state = state
        self._syncing = False
        #: What the window read for the current case and attribute.
        self.series: ResultSeries | None = None

        self.case_combo = QComboBox(self)
        for case in cases(thermal_model):
            self.case_combo.addItem(case.label, case.key)
        self.case_combo.setToolTip("Which solved case, or the live node state")
        self.case_combo.currentIndexChanged.connect(self._on_case_changed)

        self.attribute_combo = QComboBox(self)
        self.attribute_combo.setToolTip("Which stored attribute colours the geometry")
        self.attribute_combo.currentIndexChanged.connect(self._on_attribute_changed)

        self.prev_button = self._button("<", "Previous instant", self.go_previous)
        self.play_button = self._button(">", "Play through the stored instants", self._on_play)
        self.play_button.setCheckable(True)
        self.next_button = self._button(">", "Next instant", self.go_next)

        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setToolTip("Stored instants only - values are never interpolated")
        self.slider.setPageStep(1)
        self.slider.valueChanged.connect(self._on_slider_moved)

        self.time_label = QLabel("", self)
        self.time_label.setMinimumWidth(140)

        self.timer = QTimer(self)
        self.timer.setInterval(FRAME_INTERVAL_MS)
        self.timer.timeout.connect(self.go_next)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.addWidget(QLabel("Case", self))
        layout.addWidget(self.case_combo)
        layout.addWidget(QLabel("Attribute", self))
        layout.addWidget(self.attribute_combo)
        for button in (self.prev_button, self.play_button, self.next_button):
            layout.addWidget(button)
        layout.addWidget(self.slider, stretch=1)
        layout.addWidget(self.time_label)

        self._refresh_attributes()
        self.publish()

    def _button(self, text: str, tooltip: str, action: Callable[..., None]) -> QPushButton:
        button = QPushButton(text, self)
        button.setToolTip(tooltip)
        button.setFixedWidth(_BUTTON_WIDTH)
        button.clicked.connect(action)
        return button

    # ── what is selected ──────────────────────────────────────────────────
    def current_case(self) -> str:
        """The case key the combo is showing; empty when there are no cases.

        Empty rather than the live case: a model with nothing solved offers no
        cases at all, and answering with one that is not in the list would have
        the panel publish a result nothing can read.
        """
        data = self.case_combo.currentData()
        return "" if data is None else str(data)

    def rewind(self) -> None:
        """Go back to the first case, its first attribute and its first instant.

        What a reset of the whole window does to this strip. The animation is
        stopped as well: a reset that left it playing would immediately move
        off the instant it just went back to.
        """
        self.stop()
        self._syncing = True
        try:
            if self.case_combo.count():
                self.case_combo.setCurrentIndex(0)
            self.slider.setValue(0)
        finally:
            self._syncing = False
        self._refresh_attributes(keep=False)
        self.publish()

    def current_attribute(self) -> str:
        """The attribute name the combo is showing; empty if the case has none."""
        data = self.attribute_combo.currentData()
        return "" if data is None else str(data)

    def _refresh_attributes(self, *, keep: bool = True) -> None:
        """Repopulate the attribute combo for the case now selected.

        The attribute survives a case change when the new case also carries it:
        switching between two solved cases to compare the same temperature is
        the normal thing to do with two cases. ``keep`` off is what a rewind
        asks for: the first attribute of the first case, whatever was showing.
        """
        wanted = self.current_attribute() if keep else ""
        names = attributes(self._thermal_model, self.current_case())
        self._syncing = True
        try:
            self.attribute_combo.clear()
            for name in names:
                label, unit = ATTRIBUTES.get(name, (name, ""))
                self.attribute_combo.addItem(f"{label} [{unit}]" if unit else label, name)
            if wanted in names:
                self.attribute_combo.setCurrentIndex(names.index(wanted))
        finally:
            self._syncing = False

    def publish(self) -> None:
        """Write the current case, attribute and instant into the shared state."""
        attribute = self.current_attribute()
        self._state.result = (
            None
            if not attribute
            else ResultSelection(
                case=self.current_case(),
                attribute=attribute,
                time_index=self.slider.value(),
            )
        )

    # ── the transport ─────────────────────────────────────────────────────
    def set_series(self, series: ResultSeries | None) -> None:
        """Tell the panel what the window read, so the slider can span it.

        The window owns the reading: it needs the series for the colouring
        anyway, and reading a hundred-megabyte transient twice is the one place
        this panel could cost anything.
        """
        self.series = series
        last = 0 if series is None else max(series.num_steps - 1, 0)
        animated = series is not None and series.animated
        self._syncing = True
        try:
            self.slider.setMaximum(last)
            self.slider.setValue(min(self.slider.value(), last))
        finally:
            self._syncing = False
        for widget in (self.slider, self.prev_button, self.play_button, self.next_button):
            widget.setEnabled(animated)
        if not animated:
            self.stop()
        self.time_label.setText("" if series is None else series.time_label(self.slider.value()))

    def go_previous(self, checked: bool = False) -> None:
        """Step back one stored instant, wrapping at the start."""
        del checked
        value = self.slider.value()
        self.slider.setValue(self.slider.maximum() if value <= 0 else value - 1)

    def go_next(self, checked: bool = False) -> None:
        """Step forward one stored instant, wrapping at the end."""
        del checked
        value = self.slider.value()
        self.slider.setValue(0 if value >= self.slider.maximum() else value + 1)

    def play(self) -> None:
        """Start stepping through the instants on a timer."""
        if not self.slider.isEnabled():
            return
        self.play_button.setChecked(True)
        self.play_button.setText("||")
        self.timer.start()

    def stop(self) -> None:
        """Stop the animation, wherever it got to."""
        self.timer.stop()
        self.play_button.setChecked(False)
        self.play_button.setText(">")

    # ── widget signals ────────────────────────────────────────────────────
    def _on_play(self, checked: bool = False) -> None:
        if checked:
            self.play()
        else:
            self.stop()

    def _on_case_changed(self, index: int) -> None:
        del index
        if self._syncing:
            return
        self._refresh_attributes()
        self.publish()

    def _on_attribute_changed(self, index: int) -> None:
        del index
        if self._syncing:
            return
        self.publish()

    def _on_slider_moved(self, value: int) -> None:
        del value
        if self._syncing:
            return
        self.publish()
