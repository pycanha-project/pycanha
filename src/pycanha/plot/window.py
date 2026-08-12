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

import matplotlib as mpl
import numpy as np
import pycanha_core as pcc
from matplotlib.colors import LogNorm, Normalize
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QMainWindow,
    QMenu,
    QWidget,
)
from pyvistaqt import QtInteractor

from .. import log
from . import edges, results
from .icons import apply_window_icon
from .panels.info_panel import InfoPanel
from .panels.legend_panel import LegendPanel
from .panels.time_panel import TimePanel
from .panels.toolbar import ViewerToolBar
from .panels.tree_panel import TreePanel
from .picking import clear_highlight, face_info, item_map
from .polydata import polydata_from_lines, polydata_from_triangles
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

#: Actor names of the selection overlay: the brightened copy of what is
#: selected, and the line around it.
SELECTION_HIGHLIGHT = "_selection"
SELECTION_OUTLINE = "_selection_outline"

#: How far the selection is brightened towards white, as a fraction. The
#: highlight is the geometry's *own* colour made brighter rather than a colour
#: of its own: a flat wash replaces the data with the fact that it is selected.
BRIGHTEN = 0.45

#: The line drawn around the selection, so a pale or already-bright face is
#: still unmistakable. Magenta, and thinner than the primitive outlines: it is
#: the one overlay that is not part of the technical drawing, so it does not
#: share the drawing's black.
SELECTION_OUTLINE_COLOR = "magenta"
SELECTION_OUTLINE_WIDTH = 2.0

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

#: How far towards the camera a coincident overlay is pushed, in the units
#: VTK's polygon offset takes (negative is towards the camera). Lines are
#: pushed further than surfaces, so a line is never swallowed by the selection
#: overlay lying on the same geometry - and every line uses the same value, so
#: the mesh, the outlines and the selection ring cannot z-fight each other.
SURFACE_OFFSET = -4.0
LINE_OFFSET = -8.0

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
    lighting: bool = False


def _plotter_of(view: QWidget | None) -> Any:
    """The pyvista plotter behind the 3D view, or ``None`` if it is a placeholder.

    Duck-typed on purpose: ``pyvistaqt.QtInteractor`` is both a ``QWidget`` and
    a plotter, and a test passes a widget that is only the former.
    """
    return view if hasattr(view, "add_mesh") else None


class ViewerWindow(QMainWindow):
    """Toolbar, the geometry tree and property table, the 3D view, and the
    appearance and results panes.

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
        apply_window_icon(self)
        self.toolbar = ViewerToolBar(self.state, self)
        self.toolbar.reset_requested.connect(self.reset_view)
        self.addToolBar(self.toolbar)
        self.setCentralWidget(self.view)

        # One left column: the tree, and under it what the selected row is.
        # They are read together - you click a row to find out what it is - and
        # the properties are a short table, so they take the bottom third.
        self.tree_panel = TreePanel(model, self.state, self)
        self.info_panel = InfoPanel(self.scene, self.properties, self.state, self)
        left = Qt.DockWidgetArea.LeftDockWidgetArea
        tree_dock = self._add_dock("Geometry", self.tree_panel, left)
        properties_dock = self._add_dock("Properties", self.info_panel, left)
        self.splitDockWidget(tree_dock, properties_dock, Qt.Orientation.Vertical)
        self.resizeDocks([tree_dock, properties_dock], [2, 1], Qt.Orientation.Vertical)

        self.legend_panel = LegendPanel(self.scene, self.properties, self.state, self)
        self._add_dock("Appearance", self.legend_panel, Qt.DockWidgetArea.RightDockWidgetArea)

        # The results strip is always there so the window keeps its shape, and
        # is live only while the geometry is coloured by a result: what it
        # controls is which instant of that colouring is on screen.
        self.time_panel = TimePanel(thermal_model, self.state, self)
        self._add_dock("Results", self.time_panel, Qt.DockWidgetArea.BottomDockWidgetArea)

        self.state.subscribe(self._on_state_change)
        self._enable_picking()
        # The panel published its default case while the window was still being
        # built, before anything was subscribed to hear it, so the result
        # colouring is filled in here - ready for the moment it is chosen.
        self.refresh_result()
        self._sync_results_strip()
        self.rebuild_geometry()

    def _add_dock(self, title: str, widget: QWidget, area: Qt.DockWidgetArea) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        return dock

    def _sync_results_strip(self) -> None:
        """Leave the strip live only while a result is what is being drawn."""
        self.time_panel.setEnabled(self.has_results and self.state.color_by == RESULT_KEY)

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
        lighting = self.state.lighting
        if prop.categorical:
            # Colours resolved over *every* cell rather than the visible ones,
            # so hiding something does not recolour what is left.
            colors = self.scene.visible_scalars(prop.colors_of(master))
            if filtered is not None:
                colors = colors.copy()
                colors[filtered] = FILTERED_RGB
            return Coloring(colors, rgb=True, title=prop.label, lighting=lighting)

        scale = self.state.scale
        numbers = self.scene.visible_scalars(master).astype(np.float64)
        if filtered is not None:
            # nan is what the actor draws in ``nan_color``, which is the grey.
            numbers = np.where(filtered, np.nan, numbers)
        title = f"{prop.label} [{prop.unit}]" if prop.unit else prop.label
        # A property that knows its own range says so - a frame of a time
        # series is drawn on the scale of the whole series, or the colours
        # would mean something different at every instant. Either way the range
        # covers only what is drawn: the property is rebuilt against the visible
        # nodes, and the values here are the visible cells'.
        automatic = prop.clim if prop.clim is not None else _finite_range(numbers)
        return Coloring(
            numbers,
            rgb=False,
            title=title,
            cmap=scale.colormap + ("_r" if scale.reverse else ""),
            clim=automatic if scale.auto else scale.limits,
            log_scale=scale.log,
            lighting=lighting,
        )

    def cell_colors(self) -> npt.NDArray[np.uint8]:
        """The RGB every visible cell is actually drawn in, ``(n, 3)`` ``uint8``.

        The categorical path already holds them. The numeric one is the same
        colormap, limits and log setting the mapper was given, resolved here so
        the highlight can brighten what is on screen rather than paint over it;
        ``nan`` - a value the model does not have, or one the filter greyed -
        keeps the grey the actor draws it in.
        """
        coloring = self.coloring()
        if coloring.rgb:
            return coloring.values.astype(np.uint8, copy=False)
        values = np.asarray(coloring.values, dtype=np.float64)
        colors = np.full((values.size, 3), FILTERED_RGB, dtype=np.uint8)
        finite = np.isfinite(values)
        if not finite.any():
            return colors
        colors[finite] = _colormap_colors(
            values[finite], coloring.cmap, coloring.clim, log_scale=coloring.log_scale
        )
        return colors

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

    def visible_nodes(self) -> npt.NDArray[np.int64]:
        """The tmm nodes of the geometry currently drawn, ascending and distinct.

        What the automatic colour scale of a result is spent on: a node no
        longer on screen has no say in the range its colours are spread over.
        """
        return np.unique(self.scene.node_numbers[self.scene.visible_cells])

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
                series,
                selection.time_index,
                self.scene.slot_nodes,
                visible_nodes=self.visible_nodes(),
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
        visibility mask and one meaning for ``Show all``. One node found and a
        range typed in are the same filter set two ways, so both arrive here as
        one pair of bounds.
        """
        bounds = self.state.node_bounds()
        if bounds is None:
            return None
        return ~self.scene.visible_scalars(self.scene.node_range_mask(*bounds))

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
            lighting=coloring.lighting,
            cmap=coloring.cmap,
            clim=coloring.clim,
            log_scale=coloring.log_scale,
            show_scalar_bar=not coloring.rgb,
            scalar_bar_args={"title": coloring.title},
            nan_color=FILTERED_COLOR,
            backface_culling=self.scene.both_sides,
            show_edges=self.state.edges.triangles,
            edge_color=EDGE_COLOR,
            reset_camera=not self._camera_reset,
        )
        if not self._camera_reset:
            # The camera has been placed, and every later rebuild has to leave
            # it alone: a renderer whose ``camera_set`` is still False resets
            # itself whenever an actor is added or removed with no explicit
            # instruction, and hiding one item would re-frame the whole model.
            self.plotter.renderer.camera_set = True
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
            and coloring.lighting == drawn.lighting
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

    def highlight_colors(self) -> npt.NDArray[np.uint8]:
        """What the highlighted cells are drawn in: their own colour, brighter.

        The selection keeps saying what it said - its material, its node, its
        temperature - and adds only that it is selected. A wash of one colour
        would take the answer away just as the answer is being asked for.
        """
        cells = self.highlight()
        if cells.size == 0:
            return np.empty((0, 3), dtype=np.uint8)
        return brighten(self.cell_colors()[self.scene.visible_index(cells)])

    def highlight_outline(self) -> npt.NDArray[np.int64]:
        """Point-index pairs ringing the highlighted cells.

        Taken over the triangles rather than the cells: with ``both_sides``
        every triangle is in the scene twice, and a patch made of both copies
        has every edge used twice from the inside, so its own boundary would
        come out empty.
        """
        cells = self.highlight()
        if cells.size == 0:
            return np.empty((0, 2), dtype=np.int64)
        triangles = np.unique(cells % self._n_triangles()) if self.scene.both_sides else cells
        return edges.group_boundary_edges(
            self.scene.triangles[triangles],
            np.zeros(triangles.size, dtype=np.int64),
            n_points=int(self.scene.points.shape[0]),
        )

    def _n_triangles(self) -> int:
        """How many triangles the master mesh holds, sides not counted twice."""
        return self.scene.n_cells // 2 if self.scene.both_sides else self.scene.n_cells

    # ── edges ─────────────────────────────────────────────────────────────
    def visible_triangles(self) -> npt.NDArray[np.intp]:
        """The side-1 cells currently drawn - one entry per rendered triangle.

        With ``both_sides`` every triangle is in the scene twice, coincident
        and wound the other way, so a half-edge pass over all of them would see
        every edge four times. The side-1 copies are the triangulation.
        """
        n_tri = self._n_triangles()
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
        self._draw_lines(name, lines, color=EDGE_COLOR, width=width)

    def _draw_lines(
        self, name: str, lines: npt.NDArray[np.int64], *, color: str, width: float
    ) -> None:
        """Put one set of lines over the geometry, or take it away.

        The lines lie exactly on the surface they outline, so they are pushed
        towards the camera by more than any surface is (:data:`LINE_OFFSET`
        against :data:`SURFACE_OFFSET`). Without that ordering the selection
        overlay - itself a surface pushed forward - swallows whichever lines
        happen to land behind it, which is a stripe of the mesh here and a
        piece of a face outline there rather than anything that reads as a
        rule.
        """
        if self.plotter is None:
            return
        if lines.shape[0] == 0:
            clear_highlight(self.plotter, name)
            return
        actor = self.plotter.add_mesh(
            polydata_from_lines(self.scene.points, lines),
            color=color,
            line_width=width,
            lighting=False,
            pickable=False,
            reset_camera=False,
            show_scalar_bar=False,
            name=name,
        )
        mapper = actor.mapper
        mapper.SetResolveCoincidentTopologyToPolygonOffset()
        mapper.SetRelativeCoincidentTopologyLineOffsetParameters(LINE_OFFSET, LINE_OFFSET)

    def _draw_highlight(self) -> None:
        """Draw the selection: the same cells, brighter, ringed in one line."""
        if self.plotter is None:
            return
        cells = self.highlight()
        if cells.size == 0:
            clear_highlight(self.plotter, SELECTION_HIGHLIGHT)
            clear_highlight(self.plotter, SELECTION_OUTLINE)
            return
        poly = polydata_from_triangles(self.scene.points, self.scene.triangles[cells])
        poly.cell_data[SCALARS_NAME] = self.highlight_colors()
        actor = self.plotter.add_mesh(
            poly,
            scalars=SCALARS_NAME,
            rgb=True,
            lighting=self.state.lighting,
            pickable=False,
            reset_camera=False,
            backface_culling=self.scene.both_sides,
            show_scalar_bar=False,
            show_edges=self.state.edges.triangles,
            edge_color=EDGE_COLOR,
            name=SELECTION_HIGHLIGHT,
        )
        # Coincident with the surface it covers, so it is pushed towards the
        # camera - but by less than the lines, which have to stay on top of it.
        mapper = actor.mapper
        mapper.SetResolveCoincidentTopologyToPolygonOffset()
        mapper.SetRelativeCoincidentTopologyPolygonOffsetParameters(SURFACE_OFFSET, SURFACE_OFFSET)
        self._draw_lines(
            SELECTION_OUTLINE,
            self.highlight_outline(),
            color=SELECTION_OUTLINE_COLOR,
            width=SELECTION_OUTLINE_WIDTH,
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

        The right button is taken away from the camera entirely (see
        :meth:`_claim_the_right_button`): it selects and opens the menu, and
        that is all it does.
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
        interactor.add_observer("LeftButtonReleaseEvent", self._on_left_release)
        self._claim_the_right_button()

    def _claim_the_right_button(self) -> None:
        """Take the right button off the camera, on the interactor *style*.

        ``vtkInteractorStyle`` dispatches a button event to its own handler
        only while nothing is observing that event **on the style**; with an
        observer there it invokes the event instead. So an observer registered
        on the style, which never calls ``OnRightButtonDown``, is how the dolly
        is prevented rather than undone.

        It also has to be both halves of the gesture. Registering the release
        alone - which is what ``iren.add_observer`` does by itself, since
        release events are the ones it has to route through the style - leaves
        the press starting a dolly that the release then never ends, and the
        camera goes on zooming with the button already up until some other
        gesture resets the style.
        """
        style = self.plotter.iren.style
        if style is None or not hasattr(style, "add_observer"):
            return
        style.add_observer("RightButtonPressEvent", self._on_button_press)
        style.add_observer("RightButtonReleaseEvent", self._on_right_release)

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

        The node history is the exception the other way round: in Item mode the
        selection is a whole item, so there is no one node the menu could mean
        and it is not offered.
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
        node_number = None if self.state.picker_mode is PickerMode.ITEM else self._selected_node()
        series = self.current_series()
        if node_number is not None and node_number >= 0 and series is not None and series.animated:
            number = int(node_number)
            actions.append(
                (f"Plot time history of node {number}", lambda: self.plot_time_history(number))
            )
        actions.append(("Show all", self.state.show_all))
        return actions

    def _selected_node(self) -> int | None:
        """The tmm node of the current selection, if it names one."""
        selection = self.state.selection
        return None if selection is None else selection.node_number

    def show_context_menu(self) -> None:
        """Pop the right-click menu up under the cursor.

        ``popup`` and not ``exec``: the menu goes up from inside a VTK
        interactor observer, and ``exec`` would run a nested Qt event loop
        there - re-entering the render window's event handling from within one
        of its own callbacks, and holding the callback open until the user
        picks something. ``popup`` returns at once and the action fires from
        the normal event loop. The menu is parented, so it stays alive after
        this returns; nothing here wants the triggered action back.
        """
        menu = QMenu(self)
        for label, action in self.context_actions():
            menu.addAction(label, action)
        menu.popup(QCursor.pos())

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
            # An automatic scale is spread over the geometry that is drawn, so
            # what is drawn changing is what changes it.
            self.refresh_result()
            self.rebuild_geometry()
            self._draw_highlight()
            self._draw_edges()
            log.info(
                f"viewer: {len(self.state.hidden)} geometry item(s) and "
                f"{len(self.state.hidden_categories)} categor(ies) hidden"
            )
        elif change is Change.COLORING:
            # Switching the colouring resets the legend's hidden categories, so
            # what is drawn changes along with what colour it is drawn in.
            self.apply_visibility()
            self._sync_results_strip()
            self.rebuild_geometry()
            self._draw_highlight()
            self._draw_edges()
        elif change is Change.EDGES:
            # The triangle lines belong to the geometry actor, the other two
            # are overlays of their own.
            self.rebuild_geometry()
            self._draw_highlight()
            self._draw_edges()
        elif change is Change.FILTER:
            # The filter greys rather than hides, so it is a recolour - and the
            # highlight is drawn in the colours it just changed.
            self.rebuild_geometry()
            self._draw_highlight()
        elif change is Change.RESULTS:
            self.refresh_result()
            if self.state.color_by == RESULT_KEY:
                self.rebuild_geometry()
                self._draw_highlight()
        elif change in (Change.SELECTION, Change.PICKER):
            self._draw_highlight()
        log.flush()

    def reset_view(self) -> None:
        """Put the whole window back to how it opened, camera included.

        The one action that needs no explanation: whatever combination of
        hidden items, isolated categories, filters and scales has been arrived
        at, this is the way out of it.
        """
        self.time_panel.rewind()
        self.state.reset()
        if self.plotter is not None:
            self.plotter.reset_camera()
        log.info("viewer: the view was reset")
        log.flush()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop the animation timer before the widgets it drives are gone."""
        self.time_panel.stop()
        super().closeEvent(event)


def _colormap_colors(
    values: npt.NDArray[np.float64],
    cmap: str | None,
    clim: tuple[float, float] | None,
    *,
    log_scale: bool,
) -> npt.NDArray[np.uint8]:
    """Put finite ``values`` through a colormap exactly as the mapper would.

    A log scale with a non-positive lower limit falls back to a linear one:
    that is a scale the mapper cannot draw either, and guessing a positive
    floor here would put the highlight on a different scale from the geometry.
    """
    colormap = mpl.colormaps[cmap or "viridis"]
    low, high = clim if clim is not None else (float(values.min()), float(values.max()))
    if log_scale and low > 0.0:
        norm: Normalize = LogNorm(vmin=low, vmax=high)
    else:
        norm = Normalize(vmin=low, vmax=high)
    rgba = np.asarray(colormap(norm(values)), dtype=np.float64)
    return (rgba[:, :3] * 255).astype(np.uint8)


def brighten(colors: npt.ArrayLike, fraction: float = BRIGHTEN) -> npt.NDArray[np.uint8]:
    """Move colours ``fraction`` of the way to white.

    Towards white in both directions: a dark face lightens a lot and a pale one
    a little, so the selection always reads as *more* of what it already was.
    White itself cannot brighten, which is what the outline is there for.
    """
    values = np.asarray(colors, dtype=np.float64)
    return np.clip(values + (255.0 - values) * float(fraction), 0.0, 255.0).astype(np.uint8)


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
