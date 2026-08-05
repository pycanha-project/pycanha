"""Diagnostics produced while reading STEP-TAS geometry.

The machinery is shared with the other formats -- see
:mod:`pycanha.io.diagnostics` -- and only the exception raised under ``strict``
belongs to STEP-TAS.
"""

from __future__ import annotations

from ..diagnostics import Diagnostic, Severity
from ..diagnostics import DiagnosticCollector as _BaseCollector
from .errors import StepTasError

__all__ = ["Diagnostic", "DiagnosticCollector", "Severity"]


class DiagnosticCollector(_BaseCollector):
    """Collects diagnostics, raising :class:`StepTasError` under ``strict``."""

    error_type = StepTasError
