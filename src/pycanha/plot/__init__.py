"""Visualization of gmm geometry: pyvista datasets, one-shot plots, picking.

Two paths share one data layer:

* the **free functions** - :func:`to_polydata`, :func:`plot`, :func:`render` -
  build a dataset and show it in a single blocking call. They work in a notebook,
  and are what :class:`pycanha.gmm.GeometryModel`'s ``plot*`` methods call.
* the **interactive viewer** (:func:`explore`, added in the window module) opens a
  desktop window with a scene tree, visibility control, switchable coloring and a
  property panel.

:mod:`~pycanha.plot.polydata` holds the mesh-to-pyvista conversion and the
value-mapping helpers; :mod:`~pycanha.plot.picking` resolves a rendered triangle
back to its face slot, node and geometry item.
"""

from __future__ import annotations

from . import picking, polydata
from .picking import FaceInfo, face_info, format_face_info
from .polydata import (
    categorical_colors,
    cell_columns,
    colorize_categorical,
    map_face_data,
    map_node_data,
    to_polydata,
)
from .render import build_plotter, plot, render

__all__ = [
    "FaceInfo",
    "build_plotter",
    "categorical_colors",
    "cell_columns",
    "colorize_categorical",
    "face_info",
    "format_face_info",
    "map_face_data",
    "map_node_data",
    "picking",
    "plot",
    "polydata",
    "render",
    "to_polydata",
]
