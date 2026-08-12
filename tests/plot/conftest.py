"""Test setup for the visualization layer.

Qt must be told to use the ``offscreen`` platform *before* any QApplication is
created, and an environment variable is the only way to say so. Setting it here
rather than in CI keeps a local ``pytest`` run identical to the runner's.

``setdefault`` so an explicit ``QT_QPA_PLATFORM`` from the environment still
wins - that is how you run the ``gui``-marked tests against a real window.

Note that ``offscreen`` provides no OpenGL context: plain Qt widgets work, but a
``pyvistaqt.QtInteractor`` segfaults under it. No test in this repo renders; the
arrays that would be handed to VTK are asserted directly instead.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
