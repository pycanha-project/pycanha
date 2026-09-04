"""Test setup for the visualization layer.

Qt must be told to use the ``offscreen`` platform *before* any QApplication is
created, and an environment variable is the only way to say so. Setting it here
rather than in CI keeps a local ``pytest`` run identical to the runner's.

``setdefault`` so an explicit ``QT_QPA_PLATFORM`` from the environment still
wins - that is how you run the ``gui``-marked tests against a real window.

Note that ``offscreen`` provides no OpenGL context: plain Qt widgets work, but a
``pyvistaqt.QtInteractor`` segfaults under it. Almost every test here asserts the
arrays that would be handed to VTK directly rather than drawing anything. The few
that do draw go through :class:`tests.plot.offscreen.OffscreenView`, whose plotter
is VTK's own off-screen path and owes nothing to Qt's platform - but which still
needs an OpenGL implementation on the machine, and skips itself where there is
none.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
