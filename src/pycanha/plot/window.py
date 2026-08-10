"""The interactive viewer window, and the ``explore()`` entry point.

:class:`ViewerWindow` assembles the panels around a **3D view that is passed
in**. That is not indirection for its own sake: Qt's ``offscreen`` platform
provides no OpenGL context, so a ``pyvistaqt.QtInteractor`` segfaults under it
and a headless test cannot build one. Injecting the view lets a test pass a
plain widget and still exercise the tree, the selection sync, the property
table and - the part where the bugs actually live - the arrays that would have
been handed to VTK. :func:`explore` is what passes a real ``QtInteractor``.

The window owns no view state: it reads :class:`~pycanha.plot.state.ViewState`,
mutates it in response to the panels, and repaints from the notifications it
subscribes to. It never mutates the model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pycanha_core as pcc
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow, QWidget
from pyvistaqt import QtInteractor

from .. import log
from .panels.info_panel import InfoPanel
from .panels.legend_panel import LegendPanel
from .panels.toolbar import ViewerToolBar
from .panels.tree_panel import TreePanel
from .picking import clear_highlight, face_info, highlight_cells, item_map
from .polydata import categorical_colors
from .properties import face_properties
from .scene import Scene
from .state import Change, PickerMode, Selection, ViewState

if TYPE_CHECKING:
    import numpy.typing as npt
    from PySide6.QtGui import QCloseEvent

    from .properties import FaceProperty

#: Actor name of the geometry, so a rebuild replaces it instead of stacking.
MESH_ACTOR = "_geometry"

#: Cell-data name the current colouring is written to on the visible subset.
SCALARS_NAME = "_coloring"

#: Actor name of the selection overlay.
SELECTION_HIGHLIGHT = "_selection"

#: Colour of the selection overlay.
SELECTION_COLOR = "yellow"

#: Actor name of the find-node overlay, drawn alongside the selection one.
FOUND_HIGHLIGHT = "_found_node"

#: Colour of the find-node overlay.
FOUND_COLOR = "magenta"

#: What a face outside the node filter is drawn in - greyed, never hidden.
FILTERED_COLOR = "lightgray"
FILTERED_RGB = (211, 211, 211)


@dataclass(frozen=True)
class Coloring:
    """Everything the actor needs to draw one colour-by choice.

    ``rgb`` distinguishes the two paths: categorical colourings are per-cell
    RGB with no colour bar, because a node number is a label and a colormap
    would suggest it is a magnitude; numeric ones go on a real colormap.
    """

    values: npt.NDArray[Any]
    rgb: bool
    title: str
    cmap: str | None = None
    clim: tuple[float, float] | None = None
    log_scale: bool = False


def _plotter_of(view: QWidget | None) -> Any:
    """The pyvista plotter behind the 3D view, or ``None`` if it is a placeholder.

    Duck-typed on purpose: ``pyvistaqt.QtInteractor`` is both a ``QWidget`` and
    a plotter, and a test passes a widget that is only the former.
    """
    return view if hasattr(view, "add_mesh") else None


class ViewerWindow(QMainWindow):
    """Toolbar, geometry tree, 3D view, and the property/log pane.

    ``view`` is the 3D widget. Pass a ``pyvistaqt.QtInteractor`` for a real
    window; pass a plain ``QWidget`` (or nothing) and everything except the
    rendering still works, which is how the viewer is tested headless.
    """

    def __init__(
        self,
        model: Any,
        *,
        view: QWidget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.scene = Scene(model)
        self.state = ViewState(item_ids=self.scene.item_ids)
        self.properties = face_properties(model)
        self.view = view if view is not None else QWidget(self)
        self.plotter = _plotter_of(view)
        self._items = item_map(model)
        self._camera_reset = False

        self.setWindowTitle(f"pycanha - {model.name or 'geometry'}")
        self.toolbar = ViewerToolBar(self.state, self)
        self.addToolBar(self.toolbar)
        self.setCentralWidget(self.view)

        self.tree_panel = TreePanel(model, self.state, self)
        self._add_dock("Geometry", self.tree_panel, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.legend_panel = LegendPanel(self.scene, self.properties, self.state, self)
        self._add_dock("Appearance", self.legend_panel, Qt.DockWidgetArea.RightDockWidgetArea)
        self.info_panel = InfoPanel(self.scene, self.properties, self.state, self)
        self._add_dock("Info", self.info_panel, Qt.DockWidgetArea.BottomDockWidgetArea)

        self.state.subscribe(self._on_state_change)
        self._enable_picking()
        self.rebuild_geometry()

    def _add_dock(self, title: str, widget: QWidget, area: Qt.DockWidgetArea) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        return dock

    # ── colouring ─────────────────────────────────────────────────────────
    def current_property(self) -> FaceProperty:
        """The property the geometry is currently coloured by."""
        return self.properties[self.state.color_by]

    def coloring(self) -> Coloring:
        """The colours of the currently visible cells, ready for the actor.

        This is the array a headless test asserts on: it is what VTK would be
        handed, and every colouring decision - categorical versus numeric,
        the limits, the reversed colormap - has already been made in it.
        """
        prop = self.current_property()
        master = prop.per_cell(self.scene.face_ids)
        filtered = self.filtered_out()
        if prop.categorical:
            # Ranked first: labels are sparse (node numbers run 100, 200, 300)
            # and would otherwise collide modulo the palette size. Ranked over
            # *every* cell rather than the visible ones, so hiding something
            # does not recolour what is left.
            colors = self.scene.visible_scalars(categorical_colors(master, rank=True))
            if filtered is not None:
                colors = colors.copy()
                colors[filtered] = FILTERED_RGB
            return Coloring(colors, rgb=True, title=prop.label)

        scale = self.state.scale
        numbers = self.scene.visible_scalars(master).astype(np.float64)
        if filtered is not None:
            # nan is what the actor draws in ``nan_color``, which is the grey.
            numbers = np.where(filtered, np.nan, numbers)
        title = f"{prop.label} [{prop.unit}]" if prop.unit else prop.label
        return Coloring(
            numbers,
            rgb=False,
            title=title,
            cmap=scale.colormap + ("_r" if scale.reverse else ""),
            clim=_finite_range(numbers) if scale.auto else scale.limits,
            log_scale=scale.log,
        )

    def filtered_out(self) -> npt.NDArray[np.bool_] | None:
        """Per-visible-cell mask of the cells the node filter greys out.

        ``None`` when no filter is set. The filter never *hides*: it is a
        display overlay over whatever is drawn, which is what keeps one
        visibility mask and one meaning for ``Show all``.
        """
        node_range = self.state.node_range
        if node_range is None:
            return None
        return ~self.scene.visible_scalars(self.scene.node_range_mask(*node_range))

    # ── the 3D view ───────────────────────────────────────────────────────
    def rebuild_geometry(self) -> None:
        """Redraw the single actor over the cells that are currently visible.

        One actor, so one draw call: rotating a large model is the interaction
        that happens continuously, and hiding something is a discrete action
        that can afford to rebuild a connectivity array.
        """
        if self.plotter is None:
            return
        coloring = self.coloring()
        poly = self.scene.visible_polydata()
        poly.cell_data[SCALARS_NAME] = coloring.values
        self.plotter.add_mesh(
            poly,
            name=MESH_ACTOR,
            scalars=SCALARS_NAME,
            rgb=coloring.rgb,
            lighting=not coloring.rgb,
            cmap=coloring.cmap,
            clim=coloring.clim,
            log_scale=coloring.log_scale,
            show_scalar_bar=not coloring.rgb,
            scalar_bar_args={"title": coloring.title},
            nan_color=FILTERED_COLOR,
            backface_culling=self.scene.both_sides,
            show_edges=False,
            reset_camera=not self._camera_reset,
        )
        self._camera_reset = True

    def highlight(self) -> npt.NDArray[np.intp]:
        """Master cells the current selection highlights, at the current granularity.

        Restricted to what is drawn: the overlay is an actor of its own, so
        without that it would put hidden geometry back on the screen.
        """
        selection = self.state.selection
        if selection is None:
            return np.empty(0, dtype=np.intp)
        mode = self.state.picker_mode
        if mode is PickerMode.TRIANGLE and selection.cell is not None:
            cells = np.array([selection.cell], dtype=np.intp)
        elif mode is not PickerMode.ITEM and selection.face_id is not None:
            cells = self.scene.cells_of_face(selection.face_id)
        else:
            cells = self._subtree_cells(selection.item_id)
        return self.scene.restrict_to_visible(cells)

    def _subtree_cells(self, geometry_id: int | None) -> npt.NDArray[np.intp]:
        """Cells of every item under a geometry, so a group highlights whole."""
        if geometry_id is None:
            return np.empty(0, dtype=np.intp)
        node = self.tree_panel.tree_model.node_of(geometry_id)
        item_ids = node.item_ids if node is not None else frozenset({geometry_id})
        parts = [self.scene.cells_of_item(item_id) for item_id in sorted(item_ids)]
        return np.concatenate(parts) if parts else np.empty(0, dtype=np.intp)

    def found_cells(self) -> npt.NDArray[np.intp]:
        """Master cells of the node typed into the find box.

        Answered by the model's own ``faces_of_node``, which returns face
        slots. Only the cells are highlighted - the camera stays where the user
        put it.
        """
        node = self.state.found_node
        if node is None:
            return np.empty(0, dtype=np.intp)
        slots = np.asarray(self.model.faces_of_node(int(node)), dtype=np.int64)
        cells = np.flatnonzero(np.isin(self.scene.face_ids, slots)).astype(np.intp)
        return self.scene.restrict_to_visible(cells)

    def _draw_highlight(self) -> None:
        self._draw_overlay(SELECTION_HIGHLIGHT, SELECTION_COLOR, self.highlight())

    def _draw_found(self) -> None:
        self._draw_overlay(FOUND_HIGHLIGHT, FOUND_COLOR, self.found_cells())

    def _draw_overlay(self, name: str, color: str, cells: npt.NDArray[np.intp]) -> None:
        """Put one coincident overlay actor over ``cells``, or take it away."""
        if self.plotter is None:
            return
        if cells.size == 0:
            clear_highlight(self.plotter, name)
            return
        highlight_cells(
            self.plotter,
            points=self.scene.points,
            triangles=self.scene.triangles[cells],
            color=color,
            backface_culling=self.scene.both_sides,
            name=name,
        )

    # ── picking ───────────────────────────────────────────────────────────
    def _enable_picking(self) -> None:
        """Bind right-click / ``P`` to selecting whatever is under the cursor."""
        if self.plotter is None or self.scene.n_cells == 0:
            return
        self.plotter.picking.enable_point_picking(
            callback=self._on_pick,
            picker="cell",
            # The pick radius is a fraction of the window diagonal, and has to
            # stay tiny: every cell within it is a candidate, so on coplanar
            # geometry a generous value hands back the neighbouring face.
            tolerance=1e-6,
            use_picker=True,
            show_point=False,
            pickable_window=True,
            show_message="Right-click or press P to select",
        )

    def _on_pick(self, point: Any, picker: Any) -> None:
        subset_cell = int(picker.GetCellId())
        if not 0 <= subset_cell < self.scene.visible_cells.size:
            # Clicking past the geometry clears the selection.
            self.state.selection = None
            return
        cell = self.scene.pick_cell(subset_cell, self._view_direction(point))
        info = face_info(self.scene.mesh, cell, both_sides=self.scene.both_sides, items=self._items)
        self.state.selection = Selection(
            item_id=self.scene.item_of_cell(cell),
            face_id=info.face_id,
            node_number=info.node_number,
            cell=cell,
        )

    def _view_direction(self, point: Any) -> npt.NDArray[np.float64]:
        """Direction of the ray that produced a pick, for the two-sided lookup."""
        camera = self.plotter.camera
        origin = np.asarray(camera.position, dtype=np.float64)
        if camera.parallel_projection:
            # Every ray is parallel to the view axis, so where the click landed
            # says nothing about the direction it came from.
            return np.asarray(camera.focal_point, dtype=np.float64) - origin
        return np.asarray(point, dtype=np.float64) - origin

    # ── reacting to the state ─────────────────────────────────────────────
    def apply_visibility(self) -> bool:
        """Push both sources of invisibility into the scene's drawn subset.

        Geometry hidden from the tree, and categories switched off in the
        legend, compose into one mask - so there is one ``visible_cells`` and
        one meaning for ``Show all``.
        """
        return self.scene.set_hidden(self.state.hidden, self.category_mask())

    def category_mask(self) -> npt.NDArray[np.bool_] | None:
        """Per-master-cell mask of the categories the legend leaves switched on.

        ``None`` when nothing is switched off, or when the current colouring is
        numeric and so has no categories to switch off.
        """
        hidden = self.state.hidden_categories
        prop = self.current_property()
        if not hidden or not prop.categorical:
            return None
        values = prop.per_cell(self.scene.face_ids)
        return ~np.isin(values, np.fromiter(hidden, dtype=np.int64, count=len(hidden)))

    def _on_state_change(self, change: Change) -> None:
        if change is Change.VISIBILITY:
            self.apply_visibility()
            self.rebuild_geometry()
            self._draw_highlight()
            self._draw_found()
            log.info(
                f"viewer: {len(self.state.hidden)} geometry item(s) and "
                f"{len(self.state.hidden_categories)} categor(ies) hidden"
            )
        elif change is Change.COLORING:
            # Switching the colouring resets the legend's hidden categories, so
            # what is drawn changes along with what colour it is drawn in.
            self.apply_visibility()
            self.rebuild_geometry()
        elif change is Change.FILTER:
            # The node range greys rather than hides, so it is a recolour; find
            # is an overlay of its own.
            self.rebuild_geometry()
            self._draw_found()
        elif change in (Change.SELECTION, Change.PICKER):
            self._draw_highlight()
        log.flush()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Let go of the log before the widgets behind the handler are gone."""
        self.info_panel.detach()
        super().closeEvent(event)


def _finite_range(values: npt.NDArray[np.float64]) -> tuple[float, float] | None:
    """Range of the finite entries, or ``None`` when there is nothing to scale."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return None
    low, high = float(finite.min()), float(finite.max())
    return None if low == high else (low, high)


def explore(obj: Any) -> ViewerWindow:
    """Open the interactive viewer on a model and block until it is closed.

    ``obj`` may be a :class:`~pycanha.ThermalModel` or a
    :class:`~pycanha.gmm.GeometryModel`. Blocking matches every other
    ``plot*`` entry point and keeps the event loop out of the REPL; the window
    is returned afterwards so a script can read what was selected.

    Not usable from a test or from inside another Qt application's event loop -
    build a :class:`ViewerWindow` directly there.
    """
    model = obj.gmm if isinstance(obj, pcc.tmm.ThermalModel) else obj
    app = QApplication.instance() or QApplication([])
    window = ViewerWindow(model, view=QtInteractor())
    log.info(f"explore: opened the viewer on '{model.name}'")
    window.show()
    app.exec()
    return window
