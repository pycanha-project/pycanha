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

import os
import subprocess
import sys
from functools import cache
from typing import Any

import pytest
import pyvista as pv
from PySide6.QtWidgets import QWidget

#: Draws one frame the way the tests do, and reports whether it got one.
_PROBE = """import pyvista as pv

plotter = pv.Plotter(off_screen=True, window_size=[64, 48])
plotter.background_color = "black"
plotter.add_mesh(pv.Sphere(), color="white", lighting=False)
frame = plotter.screenshot(return_img=True)
# The frame itself is the answer, rather than what the driver says about
# itself: something drawn is not one flat colour. Which OpenGL a machine ends
# up with differs per platform - EGL over llvmpipe on the Linux runner, Cocoa
# on macOS, Mesa's off-screen window on Windows - and this asks none of them.
raise SystemExit(0 if frame.max() > frame.min() else 1)
"""


@cache
def can_draw_a_frame() -> bool:
    """Whether VTK can put a frame together on this machine.

    Off-screen rendering is not software rendering: VTK still needs a real
    OpenGL 3.2 implementation behind the render window, and a machine without
    one - a CI runner with no GPU and no software rasteriser - does not raise
    on the first ``Render``. It takes the interpreter down with an access
    violation, which ends the whole session rather than the tests that asked to
    draw. So the question is put to a separate process, where a crash is only a
    return code, and put once.
    """
    # S603 fires on every subprocess call and there is no form of the call that
    # satisfies it: what runs here is this same interpreter over a literal
    # script, with nothing from outside the file in the command line.
    try:
        probe = subprocess.run(  # noqa: S603
            [sys.executable, "-c", _PROBE],
            capture_output=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        # A driver that hangs on the first frame, or an interpreter that will
        # not start at all, is as good as one that cannot draw.
        return False
    return probe.returncode == 0


#: Set where a renderer is known to be there, so its absence is a failure.
REQUIRE_RENDERER = "PYCANHA_REQUIRE_RENDERER"


def skip_without_a_renderer() -> None:
    """Skip the calling test unless a frame can actually be drawn.

    A developer without an OpenGL implementation gets a skip. CI sets
    :data:`REQUIRE_RENDERER`, because every runner is given one - the Windows
    job installs Mesa for it - and there the skip becomes a failure: a runner
    that quietly loses its renderer should turn the job red rather than stop
    running these tests with nobody the wiser.
    """
    if can_draw_a_frame():
        return
    complaint = "no OpenGL implementation here: VTK cannot render off screen"
    if os.environ.get(REQUIRE_RENDERER):
        pytest.fail(complaint)
    pytest.skip(complaint)


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
