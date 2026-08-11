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
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QMainWindow,
    QMenu,
    QVBoxLayout,
    QWidget,
)
from pyvistaqt import QtInteractor

from .. import log
from . import edges, results
from .panels.info_panel import InfoPanel
from .panels.legend_panel import LegendPanel
from .panels.time_panel import TimePanel
from .panels.toolbar import ViewerToolBar
from .panels.tree_panel import TreePanel
from .picking import clear_highlight, face_info, highlight_cells, item_map
from .polydata import categorical_colors, polydata_from_lines
from .properties import face_properties
from .results import RESULT_KEY
from .scene import Scene
from .state import Change, PickerMode, Selection, ViewState
from .timehistory import TimeHistoryWindow

if TYPE_CHECKING:
    from collections.abc import Callable

    import numpy.typing as npt
    from PySide6.QtGui import QCloseEvent

    from .properties import FaceProperty
    from .results import ResultSeries

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

#: Actor names of the two edge overlays.
FACE_EDGES = "_face_edges"
PRIMITIVE_EDGES = "_primitive_edges"

#: Colour of both edge overlays. The two are told apart by weight rather than
#: by hue: they are a technical drawing over the colouring, and a second colour
#: would read as a third piece of data.
EDGE_COLOR = "black"

#: Line width of the face and the primitive outlines.
FACE_EDGE_WIDTH = 1.0
PRIMITIVE_EDGE_WIDTH = 3.0

#: What a face outside the node filter is drawn in - greyed, never hidden.
FILTERED_COLOR = "lightgray"
FILTERED_RGB = (211, 211, 211)

#: Pick radius, as a fraction of the window diagonal. It has to stay tiny:
#: every cell within it is a candidate, so on coplanar geometry a generous
#: value hands back the neighbouring face. (VTK's own default is 0.025 - some
#: 25 px on a 1000 px window - which is far too coarse here.)
PICK_TOLERANCE = 1e-6

#: How far, in pixels, the cursor may travel between press and release for the
#: gesture to still count as a click. Both buttons drive the camera as well as
#: the selection - left orbits, right dollies - so a drag must not also pick.
CLICK_SLOP = 4


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
        thermal_model: Any = None,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.thermal_model = thermal_model
        self.scene = Scene(model)
        self.state = ViewState(item_ids=self.scene.item_ids)
        self.properties = face_properties(model)
        self.view = view if view is not None else QWidget(self)
        self.plotter = _plotter_of(view)
        self._items = item_map(model)
        self._camera_reset = False
        self._press_position: tuple[int, int] = (0, 0)
        self._series: ResultSeries | None = None
        self._drawn: Coloring | None = None
        self._drawn_poly: Any = None
        self._edge_cache: dict[str, npt.NDArray[np.int64]] = {}
        self._drawn_edges = False
        self.time_history: TimeHistoryWindow | None = None

        # Offered as one more colour-by option, so the legend, the colour scale
        # and the property table need to know nothing about results.
        self.has_results = bool(results.cases(thermal_model))
        if self.has_results:
            self.properties[RESULT_KEY] = results.empty_property(int(self.scene.mesh.nf()))

        self.setWindowTitle(f"pycanha - {model.name or 'geometry'}")
        self.toolbar = ViewerToolBar(self.state, self)
        self.addToolBar(self.toolbar)
        self.setCentralWidget(self.view)

        self.tree_panel = TreePanel(model, self.state, self)
        self._add_dock("Geometry", self.tree_panel, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.legend_panel = LegendPanel(self.scene, self.properties, self.state, self)
        self._add_dock("Appearance", self.legend_panel, Qt.DockWidgetArea.RightDockWidgetArea)

        # The results strip sits directly above the property tabs, in the same
        # dock: they are one bottom pane, and a model with no results simply
        # has no strip.
        self.info_panel = InfoPanel(self.scene, self.properties, self.state, self)
        self.time_panel = TimePanel(thermal_model, self.state, self) if self.has_results else None
        bottom = QWidget(self)
        layout = QVBoxLayout(bottom)
        layout.setContentsMargins(0, 0, 0, 0)
        if self.time_panel is not None:
            layout.addWidget(self.time_panel)
        layout.addWidget(self.info_panel)
        self._add_dock("Info", bottom, Qt.DockWidgetArea.BottomDockWidgetArea)

        self.state.subscribe(self._on_state_change)
        self._enable_picking()
        if self.time_panel is not None:
            # The panel published its default case while the window was still
            # being built, before anything was subscribed to hear it. A model
            # that has results opens showing them - that is what it was opened
            # for - and the geometry colourings stay one combo click away.
            self.refresh_result()
            if self.state.result is not None:
                self.state.color_by = RESULT_KEY
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
        # A property that knows its own range says so - a frame of a time
        # series is drawn on the scale of the whole series, or the colours
        # would mean something different at every instant.
        automatic = prop.clim if prop.clim is not None else _finite_range(numbers)
        return Coloring(
            numbers,
            rgb=False,
            title=title,
            cmap=scale.colormap + ("_r" if scale.reverse else ""),
            clim=automatic if scale.auto else scale.limits,
            log_scale=scale.log,
        )

    # ── results ───────────────────────────────────────────────────────────
    def current_series(self) -> ResultSeries | None:
        """The case and attribute currently selected, read from the model.

        Cached against the selection, so scrubbing the slider re-reads
        nothing: a solved transient can be hundreds of megabytes and the
        instant is only an index into it.
        """
        selection = self.state.result
        if selection is None:
            return None
        if (
            self._series is None
            or self._series.case != selection.case
            or self._series.attribute != selection.attribute
        ):
            self._series = results.series(self.thermal_model, selection.case, selection.attribute)
        return self._series

    def refresh_result(self) -> None:
        """Rebuild the result colouring from the case, attribute and instant."""
        if not self.has_results:
            return
        selection = self.state.result
        series = self.current_series()
        n_slots = int(self.scene.mesh.nf())
        if selection is None or series is None:
            self.properties[RESULT_KEY] = results.empty_property(n_slots)
        else:
            self.properties[RESULT_KEY] = results.result_property(
                series, selection.time_index, self.scene.slot_nodes
            )
        if self.time_panel is not None:
            self.time_panel.set_series(series)
        self._sync_time_history()

    def _sync_time_history(self) -> None:
        """Keep the history window's marker on the instant being shown."""
        if self.time_history is None:
            return
        selection, series = self.state.result, self.current_series()
        if selection is None or series is None or not series.times.size:
            self.time_history.set_marker(None)
            return
        index = int(np.clip(selection.time_index, 0, series.times.size - 1))
        self.time_history.set_marker(float(series.times[index]))

    def plot_time_history(self, node_number: int) -> None:
        """Add one node's history to the (accumulating) time-history window.

        Opens the window on first use and leaves it open in
        :attr:`time_history`: every node picked afterwards adds another curve,
        which is the whole point of plotting a history rather than reading one
        number off the colour bar.
        """
        series = self.current_series()
        if series is None or not series.times.size:
            return
        history = series.history(int(node_number))
        if history is None:
            log.warning(f"viewer: node {node_number} is not in case '{series.case}'")
            log.flush()
            return
        if self.time_history is None:
            self.time_history = TimeHistoryWindow(self)
        unit = f" [{series.unit}]" if series.unit else ""
        self.time_history.add_history(
            f"{series.case} - node {int(node_number)}",
            series.times,
            history,
            axis_label=f"{series.label}{unit}",
        )
        self.time_history.show()
        self._sync_time_history()

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
        if self._can_update_in_place(coloring, poly):
            # Scrubbing a time series changes the values and nothing else, so
            # the array the actor already holds is written through instead of
            # the actor being replaced. Everything else about the mapper - the
            # colormap, the limits, the scalar bar - is already right.
            np.asarray(poly.cell_data[SCALARS_NAME])[...] = coloring.values
            poly.Modified()
            self._drawn = coloring
            self.plotter.render()
            return
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
            show_edges=self.state.edges.triangles,
            reset_camera=not self._camera_reset,
        )
        self._camera_reset = True
        self._drawn = coloring
        self._drawn_poly = poly
        self._drawn_edges = self.state.edges.triangles

    def _can_update_in_place(self, coloring: Coloring, poly: Any) -> bool:
        """Whether ``coloring`` differs from what is drawn only in its values.

        Everything but the values is baked into the mapper when the actor is
        added, so anything else changing means adding it again. The polydata is
        compared by identity: the scene builds a new one whenever the visible
        subset changes, and then the connectivity has to be handed over too.
        """
        drawn = self._drawn
        if drawn is None or poly is not self._drawn_poly:
            return False
        if self._drawn_edges != self.state.edges.triangles:
            return False
        if SCALARS_NAME not in poly.cell_data:
            return False
        return (
            coloring.values.shape == drawn.values.shape
            and coloring.values.dtype == drawn.values.dtype
            and coloring.rgb == drawn.rgb
            and coloring.cmap == drawn.cmap
            and coloring.clim == drawn.clim
            and coloring.log_scale == drawn.log_scale
            and coloring.title == drawn.title
        )

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
        item_ids = self._subtree_items(geometry_id)
        parts = [self.scene.cells_of_item(item_id) for item_id in sorted(item_ids)]
        return np.concatenate(parts) if parts else np.empty(0, dtype=np.intp)

    def _subtree_items(self, geometry_id: int) -> frozenset[int]:
        """Ids of every item under a geometry - what Hide and Show only act on."""
        node = self.tree_panel.tree_model.node_of(geometry_id)
        return node.item_ids if node is not None else frozenset({int(geometry_id)})

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

    # ── edges ─────────────────────────────────────────────────────────────
    def visible_triangles(self) -> npt.NDArray[np.intp]:
        """The side-1 cells currently drawn - one entry per rendered triangle.

        With ``both_sides`` every triangle is in the scene twice, coincident
        and wound the other way, so a half-edge pass over all of them would see
        every edge four times. The side-1 copies are the triangulation.
        """
        n_tri = self.scene.n_cells // 2 if self.scene.both_sides else self.scene.n_cells
        return self.scene.visible_cells[self.scene.visible_cells < n_tri]

    def edge_lines(self, kind: str) -> npt.NDArray[np.int64]:
        """Point-index pairs of one set of edges over the geometry now drawn.

        ``kind`` is ``"faces"`` or ``"primitives"``. Computed over the visible
        triangles rather than filtered afterwards, so hiding half a model
        outlines what is left rather than leaving the removed part's outline
        hanging in space. Cached, since the pass is the one O(n log n) step in
        the viewer and neither hiding nor a colour change happens per frame.
        """
        cached = self._edge_cache.get(kind)
        if cached is not None:
            return cached
        cells = self.visible_triangles()
        triangles = self.scene.triangles[cells]
        groups = self.scene.face_ids[cells] if kind == "faces" else self.scene.cell_items[cells]
        found = edges.group_boundary_edges(
            triangles, groups, n_points=int(self.scene.points.shape[0])
        )
        self._edge_cache[kind] = found
        return found

    def _draw_edges(self) -> None:
        """Put the two edge overlays up, or take them away."""
        if self.plotter is None:
            return
        display = self.state.edges
        self._draw_edge_overlay(FACE_EDGES, "faces", width=FACE_EDGE_WIDTH, drawn=display.faces)
        self._draw_edge_overlay(
            PRIMITIVE_EDGES, "primitives", width=PRIMITIVE_EDGE_WIDTH, drawn=display.primitives
        )

    def _draw_edge_overlay(self, name: str, kind: str, *, width: float, drawn: bool) -> None:
        lines = self.edge_lines(kind) if drawn else np.empty((0, 2), dtype=np.int64)
        if lines.shape[0] == 0:
            clear_highlight(self.plotter, name)
            return
        actor = self.plotter.add_mesh(
            polydata_from_lines(self.scene.points, lines),
            color=EDGE_COLOR,
            line_width=width,
            lighting=False,
            pickable=False,
            reset_camera=False,
            show_scalar_bar=False,
            name=name,
        )
        # The lines lie exactly on the surface they outline, so the same
        # polygon offset the highlight overlay uses keeps them from z-fighting.
        mapper = actor.mapper
        mapper.SetResolveCoincidentTopologyToPolygonOffset()
        mapper.SetRelativeCoincidentTopologyLineOffsetParameters(-4.0, -4.0)

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
        """Bind left-click to selecting and right-click to the context menu.

        Not ``Plotter.enable_point_picking``: that binds the pick to a button
        *press*, so the click that starts a camera drag would select whatever
        it started over - and the camera is dragged far more often than
        anything is picked. The pick is therefore driven from the *release*,
        and only when the cursor stayed put (:data:`CLICK_SLOP`). What that
        costs is the picking component's on-screen usage hint, which is no
        loss: the window has a toolbar to say the same thing.
        """
        if self.plotter is None or self.scene.n_cells == 0:
            return
        interactor = self.plotter.iren
        # The setter takes the name and hands back the VTK picker it built, so
        # the name is kept in a variable of its own: assigning the literal
        # straight in narrows the attribute to that string for the type
        # checkers, and the next line reads the picker back off it.
        picker_name: Any = "cell"
        interactor.picker = picker_name
        interactor.picker.SetTolerance(PICK_TOLERANCE)
        interactor.add_observer("LeftButtonPressEvent", self._on_button_press)
        interactor.add_observer("RightButtonPressEvent", self._on_button_press)
        interactor.add_observer("LeftButtonReleaseEvent", self._on_left_release)
        interactor.add_observer("RightButtonReleaseEvent", self._on_right_release)

    def _event_position(self) -> tuple[int, int]:
        """Where the mouse event being handled happened, in window coordinates.

        Read off the interactor rather than the object VTK hands the observer:
        pyvista registers *release* events on the interactor **style** because
        the interactor swallows them, so the caller is not the same class for a
        press and for a release, and only one of the two has the position.
        """
        x, y = self.plotter.iren.get_event_position()
        return int(x), int(y)

    def _on_button_press(self, *args: object) -> None:
        """Remember where a drag started, so a release can tell it from a click."""
        del args
        self._press_position = self._event_position()

    def _on_left_release(self, *args: object) -> None:
        del args
        if self._was_click():
            self.pick_at(*self._event_position())

    def _on_right_release(self, *args: object) -> None:
        """Select what is under the cursor, then offer what can be done to it."""
        del args
        if not self._was_click():
            return
        self.pick_at(*self._event_position())
        self.show_context_menu()

    def _was_click(self) -> bool:
        """Whether the button went down and up in the same place."""
        x, y = self._event_position()
        pressed_x, pressed_y = self._press_position
        return abs(x - pressed_x) <= CLICK_SLOP and abs(y - pressed_y) <= CLICK_SLOP

    def pick_at(self, x: int, y: int) -> None:
        """Select whatever is under window position ``(x, y)``, or clear it.

        ``(x, y)`` is in VTK's window coordinates - the interactor's own event
        position, origin bottom left.
        """
        if self.plotter is None:
            return
        picker = self.plotter.iren.picker
        picker.Pick(float(x), float(y), 0.0, self.plotter.iren.get_poked_renderer())
        subset_cell = int(picker.GetCellId())
        if not 0 <= subset_cell < self.scene.visible_cells.size:
            # Clicking past the geometry clears the selection. Only one actor is
            # pickable, so an in-range cell id means the ray hit the geometry.
            self.state.selection = None
            return
        cell = self.scene.pick_cell(subset_cell, self._view_direction(picker.GetPickPosition()))
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

    # ── the 3D context menu ───────────────────────────────────────────────
    def context_actions(self) -> list[tuple[str, Callable[[], None]]]:
        """What the 3D right-click menu offers over the current selection.

        Returned as label/callback pairs rather than ``QAction``s so the menu
        is one line of Qt and the *behaviour* can be exercised headless.

        Hide and Show only always act on the owning geometry item, whatever the
        picker granularity says (D73): a single triangle has no tree row to
        remember a hidden state in.
        """
        selection = self.state.selection
        item_id = None if selection is None else selection.item_id
        actions: list[tuple[str, Callable[[], None]]] = []
        if item_id is not None and item_id >= 0:
            node = self.tree_panel.tree_model.node_of(item_id)
            name = node.name if node is not None else str(item_id)
            item_ids = self._subtree_items(item_id)
            actions.append((f"Hide {name}", lambda: self.state.hide(item_ids)))
            actions.append((f"Show only {name}", lambda: self.state.show_only(item_ids)))
        node_number = None if selection is None else selection.node_number
        series = self.current_series()
        if node_number is not None and node_number >= 0 and series is not None and series.animated:
            number = int(node_number)
            actions.append(
                (f"Plot time history of node {number}", lambda: self.plot_time_history(number))
            )
        actions.append(("Show all", self.state.show_all))
        return actions

    def show_context_menu(self) -> None:
        """Pop the right-click menu up under the cursor."""
        menu = QMenu(self)
        for label, action in self.context_actions():
            menu.addAction(label, action)
        menu.exec(QCursor.pos())

    # ── reacting to the state ─────────────────────────────────────────────
    def apply_visibility(self) -> bool:
        """Push both sources of invisibility into the scene's drawn subset.

        Geometry hidden from the tree, and categories switched off in the
        legend, compose into one mask - so there is one ``visible_cells`` and
        one meaning for ``Show all``.
        """
        changed = self.scene.set_hidden(self.state.hidden, self.category_mask())
        if changed:
            # The edges are those of what is drawn, so they are not the same
            # lines once something is no longer drawn.
            self._edge_cache.clear()
        return changed

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
            self._draw_edges()
            log.info(
                f"viewer: {len(self.state.hidden)} geometry item(s) and "
                f"{len(self.state.hidden_categories)} categor(ies) hidden"
            )
        elif change is Change.COLORING:
            # Switching the colouring resets the legend's hidden categories, so
            # what is drawn changes along with what colour it is drawn in.
            self.apply_visibility()
            self.rebuild_geometry()
            self._draw_edges()
        elif change is Change.EDGES:
            # The triangle lines belong to the geometry actor, the other two
            # are overlays of their own.
            self.rebuild_geometry()
            self._draw_edges()
        elif change is Change.FILTER:
            # The node range greys rather than hides, so it is a recolour; find
            # is an overlay of its own.
            self.rebuild_geometry()
            self._draw_found()
        elif change is Change.RESULTS:
            self.refresh_result()
            if self.state.color_by == RESULT_KEY:
                self.rebuild_geometry()
            else:
                # Choosing a case, or scrubbing, is a request to look at it.
                # The setter notifies COLORING, which redraws.
                self.state.color_by = RESULT_KEY
        elif change in (Change.SELECTION, Change.PICKER):
            self._draw_highlight()
        log.flush()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Let go of the log, and of the timer, before the widgets are gone."""
        if self.time_panel is not None:
            self.time_panel.stop()
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

    The ThermalModel form is the fuller one: results live in its ``tmm``, so
    only it can offer the case and time controls. The geometry form opens the
    same window with the results strip simply absent.

    Not usable from a test or from inside another Qt application's event loop -
    build a :class:`ViewerWindow` directly there.
    """
    thermal_model = obj if isinstance(obj, pcc.tmm.ThermalModel) else None
    model = obj.gmm if thermal_model is not None else obj
    app = QApplication.instance() or QApplication([])
    window = ViewerWindow(model, view=QtInteractor(), thermal_model=thermal_model)
    log.info(f"explore: opened the viewer on '{model.name}'")
    window.show()
    app.exec()
    return window
