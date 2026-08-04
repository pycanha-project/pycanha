"""Crank-Nicolson transient solver with relaxation and direct sparse.

Adds nothing on top of the pycanha-core version, so it is re-exported rather
than subclassed: an empty subclass would not match the objects the core
hands back.
"""

from __future__ import annotations

import pycanha_core as pcc

TSCNRLDS = pcc.solvers.TSCNRLDS
