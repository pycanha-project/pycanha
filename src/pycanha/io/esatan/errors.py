"""Errors and logging helpers for the ESATAN .d parser."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pycanha_core as pcc

from ..errors import ModelReadError

if TYPE_CHECKING:
    from pycanha_core import Logger


class EsatanParseError(ModelReadError):
    """Raised for unrecoverable structural problems in a .d file.

    Lenient errors (unsupported intrinsic, unresolved symbol, malformed line)
    are logged and skipped instead of raising.
    """


def get_parser_logger() -> Logger:
    """Return the shared pycanha-core Python logger used by the parser."""
    return pcc.get_python_logger()
