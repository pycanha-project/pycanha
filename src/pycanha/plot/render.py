"""One-shot pyvista rendering of a prepared dataset.

This is the *free-function* plotting path: it builds a plotter, shows it, and
returns when the window is closed. It stays usable from a notebook, where
pyvista renders inline through its own backend.

The interactive viewer (:mod:`pycanha.plot.window`) does not go through here -
it embeds a plotter in a Qt window instead - but both share
:func:`build_plotter`, which configures a plotter *without* showing it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pycanha_core as pcc
import pyvista as pv

from . import picking
from .polydata import colorize_categorical, resolve_mesh, to_polydata


def build_plotter(
    poly: pv.PolyData,
    *,
    scalars: str | None = "face_id",
    show_edges: bool = True,
    off_screen: bool = False,
    rgb: bool = False,
    scalar_bar: bool = True,
    lighting: bool | None = None,
    pick: bool = True,
    pick_source: object | None = None,
    **kwargs: Any,
) -> pv.Plotter:
    """Configure a :class:`pyvista.Plotter` for ``poly`` without showing it.

    Split out of :func:`render` so a caller that owns the event loop - the
    interactive viewer, or a test - can obtain a fully wired plotter and decide
    for itself when (or whether) to display it. See :func:`render` for the
    argument meanings.
    """
    if lighting is None:
        lighting = not rgb
    plotter = pv.Plotter(off_screen=off_screen)
    if rgb:
        plotter.add_mesh(
            poly,
            scalars=scalars,
            rgb=True,
            show_edges=show_edges,
            show_scalar_bar=False,
            lighting=lighting,
            **kwargs,
        )
    else:
        active = scalars if (scalars is not None and scalars in poly.cell_data) else None
        plotter.add_mesh(
            poly,
            scalars=active,
            show_edges=show_edges,
            show_scalar_bar=scalar_bar,
            lighting=lighting,
            **kwargs,
        )
    if pick and pick_source is not None:
        model = pick_source if isinstance(pick_source, pcc.gmm.GeometryModel) else None
        picking.enable_face_picking(plotter, poly, resolve_mesh(pick_source), model=model)
    return plotter


def render(
    poly: pv.PolyData,
    *,
    scalars: str | None = "face_id",
    show_edges: bool = True,
    off_screen: bool = False,
    rgb: bool = False,
    scalar_bar: bool = True,
    lighting: bool | None = None,
    pick: bool = True,
    pick_source: object | None = None,
    show: bool = True,
    **kwargs: Any,
) -> pv.Plotter:
    """Render a prepared :class:`pyvista.PolyData` and show it.

    With ``rgb=True`` the ``scalars`` array is interpreted as per-cell RGB colors
    and no scalar bar is drawn. Otherwise ``scalars`` names a cell-data array to
    color by (ignored if absent); pass ``None`` for a flat color. Returns the
    :class:`pyvista.Plotter` (useful with ``off_screen=True`` for headless
    rendering / testing).

    ``lighting=False`` renders flat, unshaded faces. Categorical plots default to
    that, because the default specular shading darkens faces by orientation and
    makes two patches of the same category look like different colors.

    ``pick_source`` is the TriMesh or GeometryModel ``poly`` was built from; when
    given (and ``pick``), right-clicking a face prints its properties to the
    console (see :func:`pycanha.plot.picking.enable_face_picking`).

    ``show=False`` returns the configured plotter without displaying it, which is
    what :func:`build_plotter` does directly.
    """
    plotter = build_plotter(
        poly,
        scalars=scalars,
        show_edges=show_edges,
        off_screen=off_screen,
        rgb=rgb,
        scalar_bar=scalar_bar,
        lighting=lighting,
        pick=pick,
        pick_source=pick_source,
        **kwargs,
    )
    if show:
        plotter.show()
    return plotter


def plot(
    obj: object,
    *,
    scalars: str | None = "face_id",
    show_edges: bool = True,
    off_screen: bool = False,
    both_sides: bool = True,
    pick: bool = True,
    **kwargs: Any,
) -> pv.Plotter:
    """Render a TriMesh or GeometryModel with pyvista.

    ``scalars="face_id"`` (the default) colors each face a distinct color;
    ``"node_number"`` colors each tmm node distinctly; ``None`` is a flat color.
    Returns the :class:`pyvista.Plotter` (useful with ``off_screen=True`` for
    headless rendering / testing).

    ``both_sides`` (default) draws each ThermalMesh side with its own data, so
    the far side of a surface shows *its* face rather than the near side's.

    ``pick`` (default) makes right-clicking a face print its properties to the
    console; pass ``pick=False`` to leave the mouse buttons alone.

    For an interactive window with a scene tree, visibility control and
    switchable coloring, use :func:`pycanha.plot.explore` instead.
    """
    poly = to_polydata(obj, both_sides=both_sides)
    if both_sides:
        kwargs.setdefault("backface_culling", True)
    if scalars in ("face_id", "node_number") and scalars in poly.cell_data:
        name = colorize_categorical(
            poly, np.asarray(poly.cell_data[scalars]), rank=scalars == "node_number"
        )
        return render(
            poly,
            scalars=name,
            rgb=True,
            show_edges=show_edges,
            off_screen=off_screen,
            pick=pick,
            pick_source=obj,
            **kwargs,
        )
    return render(
        poly,
        scalars=scalars,
        show_edges=show_edges,
        off_screen=off_screen,
        pick=pick,
        pick_source=obj,
        **kwargs,
    )
