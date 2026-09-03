"""A 3D view that really renders, for the tests that need the actors themselves.

The viewer duck-types its view: pass it a plain ``QWidget`` and it takes the
headless path where nothing is drawn at all, which is what most of these tests
want. Pass it one of these and the same widget has a real off-screen plotter
behind it, so what reaches the renderer - which actors are up, what offsets
their mappers carry, where the clipping planes end up - can be asserted.

Qt's ``offscreen`` platform has no OpenGL context, but this does not use it:
the plotter renders through VTK's own off-screen path.
"""

from __future__ import annotations

from typing import Any

import pyvista as pv
from PySide6.QtWidgets import QWidget


class OffscreenView(QWidget):
    """A ``QWidget`` that answers every plotter call from a real plotter."""

    def __init__(self) -> None:
        super().__init__()
        self._plotter = pv.Plotter(off_screen=True, window_size=[400, 300])

    def render(self, *args: Any, **kwargs: Any) -> None:
        """Draw a frame, for real.

        Spelled out for two reasons: ``QWidget`` has a ``render`` of its own
        that would otherwise win - hence the widget's argument list, which is
        not used - and pyvista's ``Plotter.render`` does nothing at all on a
        plotter that was never shown. The render window is asked directly
        instead, which runs the pipeline and fires the renderer's own events.
        """
        del args, kwargs
        window = self._plotter.ren_win
        if window is not None:
            window.Render()

    def close(self) -> bool:
        """Let go of the render window, not just the widget."""
        self._plotter.close()
        return super().close()

    def __getattr__(self, name: str) -> Any:
        # Only reached for what QWidget does not already have.
        return getattr(object.__getattribute__(self, "_plotter"), name)
