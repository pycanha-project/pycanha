"""The ESATAN-TMS Workbench *language*: text to a typed statement tree.

This subpackage knows nothing about geometry.  It turns ``.erg`` / ``.gmm`` /
``.etms`` text into the frozen dataclasses of :mod:`~pycanha.io.esatan.lang.ast`
and evaluates constant expressions; mapping those statements onto a
:class:`~pycanha.gmm.GeometryModel` is the job of
:mod:`pycanha.io.esatan.geometry`.

Keeping the split means the grammar can be tested without importing the
compiled core, and a future reader of the non-geometry sections of an ``.etms``
file becomes a second consumer of the same statement tree rather than a second
parser.
"""

from __future__ import annotations

from .diagnostics import Diagnostic, DiagnosticCollector, Severity
from .evaluate import EvaluationError, evaluate
from .parser import parse, parse_file

__all__ = [
    "Diagnostic",
    "DiagnosticCollector",
    "EvaluationError",
    "Severity",
    "evaluate",
    "parse",
    "parse_file",
]
