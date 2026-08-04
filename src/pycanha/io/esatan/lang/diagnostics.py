"""Diagnostics produced while reading or writing an ESATAN model.

The machinery is shared with the other formats -- see
:mod:`pycanha.io.diagnostics` -- and only the exception raised under ``strict``
belongs to ESATAN.  The names are re-exported here so that the ESATAN reader's
callers keep one obvious import.
"""

from __future__ import annotations

from ...diagnostics import Diagnostic, Severity
from ...diagnostics import DiagnosticCollector as _BaseCollector
from ..errors import EsatanParseError

__all__ = ["Diagnostic", "DiagnosticCollector", "Severity"]


class DiagnosticCollector(_BaseCollector):
    """Collects diagnostics, raising :class:`EsatanParseError` under ``strict``."""

    error_type = EsatanParseError
