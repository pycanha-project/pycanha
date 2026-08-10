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
back to its face slot, node and geometry item. The viewer's own machinery is
split so that everything except the widgets is testable without a display:
:mod:`~pycanha.plot.state` holds what is being shown,
:mod:`~pycanha.plot.scene` turns that into the cells VTK draws, and
:mod:`~pycanha.plot.properties` supplies the values they are colored by.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from . import picking, polydata, properties, scene, state
from .picking import FaceInfo, face_info, format_face_info
from .polydata import (
    categorical_colors,
    cell_columns,
    colorize_categorical,
    map_face_data,
    map_node_data,
    to_polydata,
)
from .properties import FaceProperty, face_properties
from .render import build_plotter, plot, render
from .scene import Scene
from .state import Change, ColorScale, PickerMode, Selection, ViewState

if TYPE_CHECKING:
    from .window import ViewerWindow, explore

#: Names that live in :mod:`~pycanha.plot.window`, which pulls in the Qt
#: widgets. Reached lazily so that a plain ``model.plot()`` - this package is
#: imported for that - never has to build a widget toolkit it will not use.
_WINDOW_EXPORTS = ("ViewerWindow", "explore")


def __getattr__(name: str) -> Any:
    """Import the viewer only when something actually asks for it."""
    if name in _WINDOW_EXPORTS:
        value = getattr(import_module(".window", __name__), name)
        globals()[name] = value
        return value
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


__all__ = [
    "Change",
    "ColorScale",
    "FaceInfo",
    "FaceProperty",
    "PickerMode",
    "Scene",
    "Selection",
    "ViewState",
    "ViewerWindow",
    "build_plotter",
    "categorical_colors",
    "cell_columns",
    "colorize_categorical",
    "explore",
    "face_info",
    "face_properties",
    "format_face_info",
    "map_face_data",
    "map_node_data",
    "picking",
    "plot",
    "polydata",
    "properties",
    "render",
    "scene",
    "state",
    "to_polydata",
]
