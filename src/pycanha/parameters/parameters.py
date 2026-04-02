"""Named parameter storage."""

from __future__ import annotations

import pycanha_core as pcc


class Parameters(pcc.parameters.Parameters):
    def __init__(self) -> None:
        super().__init__()
