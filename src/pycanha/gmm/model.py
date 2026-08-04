"""Top-level geometry scene container with pyvista convenience methods."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pycanha_core as pcc
import pyvista as pv

from . import picking, viz
from .io import GeometryIo

#: Actor name of the time readout, so each frame replaces the previous one.
_TIME_LABEL = "_time_label"

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    import numpy.typing as npt


def _item_node_numbers(item: pcc.gmm.GeometryItem) -> list[int]:
    """All tmm node numbers referenced by an item's ThermalMesh (both sides)."""
    mesh = item.thermal_mesh
    ni = len(mesh.dir1_mesh) - 1
    nj = len(mesh.dir2_mesh) - 1
    return [int(mesh.node_of(i, j, side)) for side in (1, 2) for i in range(ni) for j in range(nj)]


def _describe_item(item: pcc.gmm.GeometryItem) -> str:
    """One-line descriptor of a leaf: primitive, mesh size and node range."""
    mesh = item.thermal_mesh
    ni = max(len(mesh.dir1_mesh) - 1, 0)
    nj = max(len(mesh.dir2_mesh) - 1, 0)
    primitive = type(item.primitive).__name__
    nodes = [n for n in _item_node_numbers(item) if n >= 0]
    node_span = f"nodes {min(nodes)}..{max(nodes)}" if nodes else "nodes -"
    name = item.name or "<anonymous>"
    return f"Item '{name}'  {primitive}  mesh {ni}x{nj} ({ni * nj} faces/side)  {node_span}"


def _format_geometry(
    geometry: pcc.gmm.Geometry, prefix: str, is_last: bool, label: str = ""
) -> list[str]:
    """Recursively format a scene-tree node into indented ASCII lines."""
    connector = "`-- " if is_last else "|-- "
    child_prefix = prefix + ("    " if is_last else "|   ")
    head = prefix + connector + label

    if isinstance(geometry, pcc.gmm.GeometryItem):
        return [head + _describe_item(geometry)]

    if isinstance(geometry, pcc.gmm.GeometryGroupCutted):
        name = geometry.name or "<anonymous>"
        lines = [head + f"CutGroup '{name}'"]
        tagged = [("[target] ", t) for t in geometry.targets]
        tagged += [("[cutter] ", c) for c in geometry.cutters]
        for idx, (role, child) in enumerate(tagged):
            lines.extend(_format_geometry(child, child_prefix, idx == len(tagged) - 1, role))
        return lines

    if isinstance(geometry, pcc.gmm.GeometryGroup):
        name = geometry.name or "<anonymous>"
        lines = [head + f"Group '{name}'"]
        children = list(geometry.children)
        for idx, child in enumerate(children):
            lines.extend(_format_geometry(child, child_prefix, idx == len(children) - 1))
        return lines

    return [head + type(geometry).__name__]


class GeometryModel(pcc.gmm.GeometryModel):
    """Object-centric scene container that owns the world mesh.

    Adds pyvista convenience on top of the pycanha-core model
    (:meth:`plot`, :meth:`to_polydata`, :meth:`plot_node_range`), geometry
    import/export through :attr:`io`, plus a textual view of the scene
    hierarchy (:meth:`format_tree` / :meth:`print_tree`).
    """

    # ── import / export ───────────────────────────────────────────────────
    @property
    def io(self) -> GeometryIo:
        """Geometry import and export for this model, e.g. ``model.io.read_esatan_erg(...)``."""
        # Built per access rather than cached: the accessor is a thin handle,
        # and an attribute set in __init__ would not survive the round trip
        # through the C++ base when the model is reached from a ThermalModel.
        return GeometryIo(self)

    # ── mesh visualization ────────────────────────────────────────────────
    def to_polydata(self, *, emissivity: bool = False, both_sides: bool = False) -> pv.PolyData:
        """Return a :class:`pyvista.PolyData` of the world mesh.

        With ``emissivity=True`` an extra per-face ``emissivity`` cell array is
        attached (IR emissivity of the ThermalMesh side each face belongs to;
        ``nan`` where unknown).

        With ``both_sides=True`` each triangle is emitted once per ThermalMesh
        side (see :func:`pycanha.gmm.viz.to_polydata`), so side-2 slots get their
        own cells instead of the geometry describing side 1 alone.
        """
        poly = viz.to_polydata(self, both_sides=both_sides)
        if emissivity:
            poly.cell_data["emissivity"] = self._face_emissivity(poly)
        return poly

    def plot(
        self,
        *,
        scalars: str | None = "face_id",
        show_edges: bool = True,
        off_screen: bool = False,
        both_sides: bool = True,
        pick: bool = True,
        **kwargs: Any,
    ) -> pv.Plotter:
        """Render the world mesh with pyvista.

        ``scalars`` selects the coloring:

        * ``"face_id"`` (default) - a distinct color per face (categorical).
        * ``"item"`` - a distinct color per geometry item (categorical).
        * ``"node_number"`` - a distinct color per tmm node (categorical); node
          numbers are labels, not a magnitude, so they are not put on a colormap.
        * ``"emissivity"`` - a continuous scale with colorbar.
        * ``None`` - a single flat color.

        ``both_sides`` (default) gives each ThermalMesh side its own cells, so
        the back of a surface shows the side-2 node / material instead of
        repeating side 1; backface culling then reveals whichever side faces the
        camera. Pass ``both_sides=False`` for the raw single-sided mesh.

        Categorical colorings render unshaded so the same category always reads
        as the same color; pass ``lighting=True`` to restore the shading.
        Pass ``show_edges=False`` to hide the triangular mesh edges.

        ``pick`` (default) makes right-clicking a face print its properties -
        face slot, side, node, item, optical material and color - to the console;
        pass ``pick=False`` to leave the mouse buttons alone.
        """
        poly = self.to_polydata(emissivity=scalars == "emissivity", both_sides=both_sides)
        if both_sides:
            kwargs.setdefault("backface_culling", True)
        if scalars in ("face_id", "item", "node_number"):
            if scalars == "face_id":
                ids = np.asarray(poly.cell_data["face_id"])
            elif scalars == "item":
                ids = self._face_item_index(poly)
            else:
                ids = np.asarray(poly.cell_data["node_number"])
            # Node numbers are sparse (100, 200, 300...) and would collide modulo
            # the palette size, so rank them densely before picking colors.
            name = viz.colorize_categorical(poly, ids, rank=scalars == "node_number")
            return viz.render(
                poly,
                scalars=name,
                rgb=True,
                show_edges=show_edges,
                off_screen=off_screen,
                pick=pick,
                pick_source=self,
                **kwargs,
            )
        return viz.render(
            poly,
            scalars=scalars,
            show_edges=show_edges,
            off_screen=off_screen,
            pick=pick,
            pick_source=self,
            **kwargs,
        )

    def plot_node_range(
        self,
        lo: int,
        hi: int,
        *,
        color: str = "green",
        other_color: str = "lightgray",
        show_edges: bool = True,
        off_screen: bool = False,
        both_sides: bool = True,
        pick: bool = True,
        **kwargs: Any,
    ) -> pv.Plotter:
        """Highlight faces whose tmm node number lies in ``[lo, hi]``.

        In-range faces are drawn in ``color``, the rest in ``other_color``.
        ``both_sides`` (default) resolves each ThermalMesh side separately, so a
        node on the far side of a surface is highlighted where it actually is.

        ``pick`` (default) makes right-clicking a face print its properties to
        the console; pass ``pick=False`` to leave the mouse buttons alone.
        """
        poly = viz.to_polydata(self, both_sides=both_sides)
        if both_sides:
            kwargs.setdefault("backface_culling", True)
        node_numbers = np.asarray(poly.cell_data["node_number"])
        in_range = ((node_numbers >= lo) & (node_numbers <= hi)).astype(np.float64)

        plotter = pv.Plotter(off_screen=off_screen)
        plotter.add_mesh(
            poly,
            scalars=in_range,
            cmap=[other_color, color],
            clim=[0, 1],
            show_scalar_bar=False,
            show_edges=show_edges,
            **kwargs,
        )
        if pick:
            picking.enable_face_picking(plotter, poly, self.mesh, model=self)
        plotter.show()
        return plotter

    def plot_node_data(
        self,
        data: Mapping[int, float],
        *,
        name: str = "value",
        show_edges: bool = True,
        off_screen: bool = False,
        both_sides: bool = True,
        pick: bool = True,
        **kwargs: Any,
    ) -> pv.Plotter:
        """Color the geometry by a ``{node number: value}`` mapping.

        Any per-node result - temperatures, heat loads, whatever the caller has -
        is drawn on a continuous color scale with a colorbar. Faces whose node is
        absent from ``data`` are drawn in pyvista's ``nan_color``.

        ``name`` labels the colorbar (and the underlying cell array). Extra
        keyword arguments go to ``add_mesh``, so ``cmap``, ``clim``, ``below_color``
        and friends work as usual.
        """
        return self._plot_mapped(
            viz.map_node_data,
            data,
            name=name,
            show_edges=show_edges,
            off_screen=off_screen,
            both_sides=both_sides,
            pick=pick,
            **kwargs,
        )

    def plot_face_data(
        self,
        data: Mapping[int, float],
        *,
        name: str = "value",
        show_edges: bool = True,
        off_screen: bool = False,
        both_sides: bool = True,
        pick: bool = True,
        **kwargs: Any,
    ) -> pv.Plotter:
        """Color the geometry by a ``{face slot: value}`` mapping.

        Like :meth:`plot_node_data`, but keyed by face slot rather than node, so
        the two sides of a face can show different values (side 1 slots are even,
        side 2 odd). Slot numbers are what :meth:`plot` shows as ``"face_id"`` and
        what a pick reports.
        """
        return self._plot_mapped(
            viz.map_face_data,
            data,
            name=name,
            show_edges=show_edges,
            off_screen=off_screen,
            both_sides=both_sides,
            pick=pick,
            **kwargs,
        )

    def _plot_mapped(
        self,
        mapper: Callable[[pv.PolyData, Mapping[int, float]], npt.NDArray[np.float64]],
        data: Mapping[int, float],
        *,
        name: str,
        show_edges: bool,
        off_screen: bool,
        both_sides: bool,
        pick: bool,
        **kwargs: Any,
    ) -> pv.Plotter:
        """Attach a mapped value array as cell data and render it with a colorbar."""
        poly = viz.to_polydata(self, both_sides=both_sides)
        poly.cell_data[name] = mapper(poly, data)
        if both_sides:
            kwargs.setdefault("backface_culling", True)
        return viz.render(
            poly,
            scalars=name,
            show_edges=show_edges,
            off_screen=off_screen,
            pick=pick,
            pick_source=self,
            **kwargs,
        )

    def plot_node_series(
        self,
        values: npt.ArrayLike,
        nodes: npt.ArrayLike,
        times: npt.ArrayLike,
        **kwargs: Any,
    ) -> pv.Plotter:
        """Scrub a transient ``{node: value}`` result with a time slider.

        ``values`` is a ``(len(times), len(nodes))`` array, ``nodes`` gives the
        node number of each column and ``times`` the instant of each row. Drag
        the slider to move through time; the color scale is fixed over the whole
        series so the frames stay comparable, and the current time is drawn in
        the corner.

        See :meth:`plot_data_series` for the remaining keyword arguments.
        """
        return self.plot_data_series(values, nodes, times, key="node_number", **kwargs)

    def plot_face_series(
        self,
        values: npt.ArrayLike,
        faces: npt.ArrayLike,
        times: npt.ArrayLike,
        **kwargs: Any,
    ) -> pv.Plotter:
        """Scrub a transient ``{face slot: value}`` result with a time slider.

        Like :meth:`plot_node_series`, but the columns of ``values`` are face
        slots rather than nodes (side 1 slots are even, side 2 odd).
        """
        return self.plot_data_series(values, faces, times, key="face_id", **kwargs)

    def plot_data_series(
        self,
        values: npt.ArrayLike,
        keys: npt.ArrayLike,
        times: npt.ArrayLike,
        *,
        key: str = "node_number",
        name: str = "value",
        time_format: str = "t = {time:g}",
        clim: tuple[float, float] | None = None,
        show_edges: bool = True,
        off_screen: bool = False,
        both_sides: bool = True,
        pick: bool = True,
        **kwargs: Any,
    ) -> pv.Plotter:
        """Render a time series of per-cell values behind a time slider.

        ``key`` selects what the columns of ``values`` are keyed by - the
        ``"node_number"`` or ``"face_id"`` cell array. ``time_format`` is a
        format string receiving ``time``. ``clim`` defaults to the range over the
        *whole* series; pass an explicit pair to override it. Remaining keyword
        arguments go to ``add_mesh``.

        Off-screen there is nothing to drag, so the first frame is rendered
        without a slider.
        """
        series = np.asarray(values, dtype=np.float64)
        instants = np.asarray(times, dtype=np.float64)
        key_array = np.asarray(keys)
        if series.ndim != 2:
            msg = f"values must be 2-dimensional (times x keys), got {series.ndim} dimensions"
            raise ValueError(msg)
        if series.shape != (instants.size, key_array.size):
            msg = (
                f"values has shape {series.shape}, expected "
                f"({instants.size}, {key_array.size}) from len(times) x len(keys)"
            )
            raise ValueError(msg)

        poly = viz.to_polydata(self, both_sides=both_sides)
        column, known = viz.cell_columns(poly, key_array, key)

        def frame(index: int) -> npt.NDArray[np.float64]:
            # Cells without a column index at whatever `column` holds for them,
            # so the mask is what actually keeps their value out.
            return np.where(known, series[index][column], np.nan)

        if clim is None and np.any(np.isfinite(series)):
            clim = (float(np.nanmin(series)), float(np.nanmax(series)))
        if both_sides:
            kwargs.setdefault("backface_culling", True)

        poly.cell_data[name] = frame(0)
        plotter = pv.Plotter(off_screen=off_screen)
        plotter.add_mesh(poly, scalars=name, clim=clim, show_edges=show_edges, **kwargs)
        plotter.add_text(time_format.format(time=instants[0]), name=_TIME_LABEL)

        if not off_screen and instants.size > 1:
            # Write through the existing VTK array rather than replacing it, so
            # the mapper keeps pointing at the scalars it was handed.
            scalars = np.asarray(poly.cell_data[name])

            def _scrub(value: float) -> None:
                index = int(np.argmin(np.abs(instants - value)))
                scalars[:] = frame(index)
                poly.Modified()
                plotter.add_text(time_format.format(time=instants[index]), name=_TIME_LABEL)

            # The Plotter method of this name is a functools.wraps forwarder that
            # loses its bound signature; the widget component is the real one.
            plotter.widgets.add_slider_widget(
                _scrub,
                rng=(float(instants[0]), float(instants[-1])),
                value=float(instants[0]),
                title="time",
                interaction_event="always",
                fmt="%.4g",
            )
        if pick:
            picking.enable_face_picking(plotter, poly, self.mesh, model=self)
        plotter.show()
        return plotter

    # ── raytracer scene assembly ──────────────────────────────────────────
    def mesh_parts(self, split: Sequence[str] = ()) -> list[pcc.radiative.ScenePart]:
        """Split the world mesh into rigid ``ScenePart`` pieces for the raytracer.

        Each name in ``split`` becomes its own part (that geometry's subtree, in
        its local frame); everything else forms a single remainder part in the
        world frame. Face ids stay global across parts, so results index back
        into the full mesh. The parts feed :class:`pycanha_core.radiative.RadiativeScene`.
        """
        return super().mesh_parts(list(split))

    def material_table(self) -> pcc.radiative.MaterialTable:
        """Build the per-face-slot ``MaterialTable`` from the ThermalMesh data.

        Collects each face slot's optical material and activity flag (from the
        per-side ThermalMesh optical properties) into the table the raytracer
        consumes alongside :meth:`mesh_parts`.
        """
        return super().material_table()

    def _emissivity_by_node(self) -> dict[int, float]:
        """Map each tmm node number to the IR emissivity of its ThermalMesh side."""
        mapping: dict[int, float] = {}
        for item in self.children_recursive():
            if not isinstance(item, pcc.gmm.GeometryItem):
                continue
            mesh = item.thermal_mesh
            ni = len(mesh.dir1_mesh) - 1
            nj = len(mesh.dir2_mesh) - 1
            sides = ((1, mesh.side1_optical), (2, mesh.side2_optical))
            for side, optical in sides:
                if optical is None:
                    continue
                eps = float(optical.emissivity_ir)
                for i in range(ni):
                    for j in range(nj):
                        mapping[int(mesh.node_of(i, j, side))] = eps
        return mapping

    def _face_emissivity(self, poly: pv.PolyData) -> npt.NDArray[np.float64]:
        """Per-face IR emissivity aligned with ``poly`` cells (``nan`` if unknown)."""
        node_numbers = np.asarray(poly.cell_data["node_number"])
        mapping = self._emissivity_by_node()
        return np.array([mapping.get(int(n), np.nan) for n in node_numbers], dtype=np.float64)

    def _face_item_index(self, poly: pv.PolyData) -> npt.NDArray[np.int64]:
        """Per-face index of the owning geometry item (``-1`` if unknown)."""
        item_of_node: dict[int, int] = {}
        items = (i for i in self.children_recursive() if isinstance(i, pcc.gmm.GeometryItem))
        for index, item in enumerate(items):
            for node in _item_node_numbers(item):
                item_of_node.setdefault(node, index)
        node_numbers = np.asarray(poly.cell_data["node_number"])
        return np.array([item_of_node.get(int(n), -1) for n in node_numbers], dtype=np.int64)

    # ── scene hierarchy ───────────────────────────────────────────────────
    def format_tree(self) -> str:
        """Return an ASCII rendering of the scene hierarchy.

        Shows every group / cut-group / item, with each item's primitive type,
        mesh subdivision and referenced tmm node range.
        """
        lines = [f"GeometryModel '{self.name or '<unnamed>'}'"]
        children = list(self.children)
        for idx, child in enumerate(children):
            lines.extend(_format_geometry(child, "", idx == len(children) - 1))
        return "\n".join(lines)

    def print_tree(self) -> None:
        """Print :meth:`format_tree` to stdout."""
        print(self.format_tree())
