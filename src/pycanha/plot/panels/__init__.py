"""The docked widgets of the interactive viewer.

Each panel is a thin skin over :class:`pycanha.plot.state.ViewState`: it reads
the state to draw itself, calls the state's mutators when the user does
something, and repaints from the notifications it subscribes to. No panel talks
to another panel, and none of them owns view state of its own.
"""

from __future__ import annotations

from .info_panel import InfoPanel
from .legend_panel import LegendPanel
from .toolbar import ViewerToolBar
from .tree_panel import TreePanel

__all__ = ["InfoPanel", "LegendPanel", "TreePanel", "ViewerToolBar"]
