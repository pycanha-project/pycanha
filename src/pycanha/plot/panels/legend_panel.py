"""The appearance column: what the geometry is coloured by, and what that means.

The colour controls sit next to the colour bar and the legend they govern
rather than in the toolbar, which would otherwise overflow.

For a **numeric** property the column offers a curated colormap shortlist with
gradient previews, a reverse toggle, manual limits with an Auto override, and a
log toggle. For a **categorical** one those are meaningless - a node number is
a label, not a magnitude - so they are disabled and the legend list below takes
over: one row per category, with its colour, its name, a checkbox that hides
everything sharing that value, and a click that isolates it.

An in-scene ``add_legend`` box was rejected for the job: it does not scroll,
and colouring by node number routinely has hundreds of entries.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

import matplotlib as mpl
import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..properties import categories
from ..state import Change

if TYPE_CHECKING:
    from ..properties import FaceProperty
    from ..state import ViewState

#: The colormap shortlist, as (matplotlib name, label). The full matplotlib
#: list is ~170 entries of mostly noise; these are the ones worth offering.
COLORMAPS: tuple[tuple[str, str], ...] = (
    ("viridis", "viridis"),
    ("plasma", "plasma"),
    ("inferno", "inferno"),
    ("coolwarm", "coolwarm"),
    ("turbo", "turbo"),
    ("jet", "jet"),
    ("gray", "gray"),
    ("tab20", "categorical"),
)

#: Size of the gradient preview drawn beside each colormap name.
_PREVIEW = QSize(64, 12)

#: Size of the solid colour swatch beside each legend entry.
_SWATCH = QSize(12, 12)

#: The value carried by a legend row, so a click can find its category back.
_CATEGORY_ROLE = int(Qt.ItemDataRole.UserRole) + 1


def colormap_icon(name: str, *, reverse: bool = False) -> QIcon:
    """A horizontal gradient preview of a matplotlib colormap."""
    colormap = mpl.colormaps[name + ("_r" if reverse else "")]
    width, height = _PREVIEW.width(), _PREVIEW.height()
    ramp = (np.asarray(colormap(np.linspace(0.0, 1.0, width)))[:, :3] * 255).astype(np.uint8)
    pixels = np.ascontiguousarray(np.repeat(ramp[None, :, :], height, axis=0))
    image = QImage(pixels.data, width, height, 3 * width, QImage.Format.Format_RGB888)
    # QImage wraps the buffer rather than owning it, and ``pixels`` dies here.
    return QIcon(QPixmap.fromImage(image.copy()))


def swatch_icon(color: tuple[int, int, int]) -> QIcon:
    """A solid square in ``color``, for one legend row."""
    pixmap = QPixmap(_SWATCH)
    pixmap.fill(QColor(*color))
    return QIcon(pixmap)


class LegendPanel(QWidget):
    """Colour-by, colour scale, and the interactive legend."""

    def __init__(
        self,
        scene: Any,
        properties: dict[str, FaceProperty],
        state: ViewState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._scene = scene
        self._properties = properties
        self._state = state
        self._syncing = False
        self._toggling = False

        self.color_by_combo = QComboBox(self)
        for key, prop in properties.items():
            self.color_by_combo.addItem(prop.label, key)
        self.color_by_combo.currentIndexChanged.connect(self._on_color_by_changed)

        self.colormap_combo = QComboBox(self)
        self.colormap_combo.setIconSize(_PREVIEW)
        for name, label in COLORMAPS:
            self.colormap_combo.addItem(colormap_icon(name), label, name)
        self.colormap_combo.currentIndexChanged.connect(self._on_scale_changed)

        self.reverse_box = QCheckBox("Reverse", self)
        self.reverse_box.toggled.connect(self._on_scale_changed)
        self.auto_box = QCheckBox("Auto", self)
        self.auto_box.setChecked(True)
        self.auto_box.setToolTip("Take the limits from the data")
        self.auto_box.toggled.connect(self._on_scale_changed)
        self.log_box = QCheckBox("Log scale", self)
        self.log_box.toggled.connect(self._on_scale_changed)

        self.min_edit = QLineEdit(self)
        self.max_edit = QLineEdit(self)
        for edit in (self.min_edit, self.max_edit):
            edit.setPlaceholderText("auto")
            edit.editingFinished.connect(self._on_scale_changed)

        self.legend_list = QListWidget(self)
        self.legend_list.setToolTip("Click a category to isolate it, uncheck it to hide it")
        self.legend_list.itemChanged.connect(self._on_item_changed)
        self.legend_list.itemClicked.connect(self._on_item_clicked)
        self.show_all_button = QPushButton("Show all categories", self)
        self.show_all_button.clicked.connect(self._on_show_all_categories)

        form = QFormLayout()
        form.addRow("Colour by", self.color_by_combo)
        form.addRow("Colormap", self.colormap_combo)
        form.addRow("", self.reverse_box)
        form.addRow("Min", self.min_edit)
        form.addRow("Max", self.max_edit)
        form.addRow("", self.auto_box)
        form.addRow("", self.log_box)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Legend", self))
        layout.addWidget(self.legend_list)
        layout.addWidget(self.show_all_button)

        state.subscribe(self._on_state_change)
        self.refresh()

    # ── what is on screen ─────────────────────────────────────────────────
    def current_property(self) -> FaceProperty:
        """The property the geometry is currently coloured by."""
        return self._properties[self._state.color_by]

    def entries(self) -> list[Any]:
        """The legend rows for the current colouring - empty when it is numeric."""
        return categories(self.current_property(), self._scene.face_ids)

    def refresh(self) -> None:
        """Rebuild every control from the state, without echoing back into it."""
        self._syncing = True
        try:
            self._refresh_controls()
            self._refresh_legend()
        finally:
            self._syncing = False

    def _refresh_controls(self) -> None:
        prop = self.current_property()
        scale = self._state.scale
        self.color_by_combo.setCurrentIndex(self.color_by_combo.findData(prop.key))
        self.colormap_combo.setCurrentIndex(self.colormap_combo.findData(scale.colormap))
        self.reverse_box.setChecked(scale.reverse)
        self.auto_box.setChecked(scale.auto)
        self.log_box.setChecked(scale.log)
        low, high = scale.limits if scale.limits is not None else ("", "")
        self.min_edit.setText(str(low))
        self.max_edit.setText(str(high))

        # A categorical colouring has no scale to speak of: the numbers are
        # labels, and a colormap over them would read as a magnitude.
        numeric = not prop.categorical
        for widget in (
            self.colormap_combo,
            self.reverse_box,
            self.auto_box,
            self.log_box,
            self.min_edit,
            self.max_edit,
        ):
            widget.setEnabled(numeric)
        self.min_edit.setEnabled(numeric and not scale.auto)
        self.max_edit.setEnabled(numeric and not scale.auto)
        self.legend_list.setEnabled(not numeric)
        self.show_all_button.setEnabled(not numeric)

    def _refresh_legend(self) -> None:
        hidden = self._state.hidden_categories
        self.legend_list.clear()
        for entry in self.entries():
            item = QListWidgetItem(swatch_icon(entry.color), entry.label)
            item.setData(_CATEGORY_ROLE, entry.value)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Unchecked if entry.value in hidden else Qt.CheckState.Checked
            )
            self.legend_list.addItem(item)

    # ── legend actions ────────────────────────────────────────────────────
    def isolate(self, value: int) -> None:
        """Show only the category ``value``, hiding every other one."""
        self._state.hidden_categories = {
            entry.value for entry in self.entries() if entry.value != int(value)
        }

    def set_category_hidden(self, value: int, hidden: bool) -> None:
        """Hide or show everything whose current colour-by value is ``value``."""
        categories_hidden = set(self._state.hidden_categories)
        if hidden:
            categories_hidden.add(int(value))
        else:
            categories_hidden.discard(int(value))
        self._state.hidden_categories = categories_hidden

    # ── widget signals ────────────────────────────────────────────────────
    def _on_color_by_changed(self, index: int) -> None:
        if self._syncing:
            return
        self._state.color_by = str(self.color_by_combo.itemData(index))

    def _on_scale_changed(self, *args: object) -> None:
        del args
        if self._syncing:
            return
        self._state.scale = replace(
            self._state.scale,
            colormap=str(self.colormap_combo.currentData()),
            reverse=self.reverse_box.isChecked(),
            log=self.log_box.isChecked(),
            auto=self.auto_box.isChecked(),
            limits=self._limits(),
        )

    def _limits(self) -> tuple[float, float] | None:
        """The typed limits, or ``None`` when either box is empty or not a number."""
        try:
            return (float(self.min_edit.text()), float(self.max_edit.text()))
        except ValueError:
            return None

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        if self._syncing:
            return
        # Qt toggles the check state before it emits itemClicked, so this flag
        # is how a click on the checkbox is told from a click on the label.
        self._toggling = True
        self.set_category_hidden(
            int(item.data(_CATEGORY_ROLE)), item.checkState() is Qt.CheckState.Unchecked
        )

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        if self._toggling:
            self._toggling = False
            return
        self.isolate(int(item.data(_CATEGORY_ROLE)))

    def _on_show_all_categories(self, checked: bool = False) -> None:
        del checked
        self._state.hidden_categories = frozenset()

    def _on_state_change(self, change: Change) -> None:
        if change is Change.COLORING:
            self.refresh()
        elif change is Change.VISIBILITY:
            self._syncing = True
            try:
                self._refresh_legend()
            finally:
                self._syncing = False
