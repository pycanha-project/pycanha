"""Errors for the ESATAN .d parser."""

from __future__ import annotations

from ..errors import ModelReadError


class EsatanParseError(ModelReadError):
    """Raised for unrecoverable structural problems in a .d file.

    Lenient errors (unsupported intrinsic, unresolved symbol, malformed line)
    are logged and skipped instead of raising.
    """
