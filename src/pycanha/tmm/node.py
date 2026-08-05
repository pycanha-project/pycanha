"""Node and NodeType definitions.

Neither adds anything on top of the pycanha-core versions, so both are
re-exported rather than subclassed: an empty subclass would not match the
objects the core hands back.
"""

from __future__ import annotations

import pycanha_core as pcc

NodeType = pcc.tmm.NodeType
Node = pcc.tmm.Node
