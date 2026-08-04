"""Reading and writing STEP-TAS geometry.

STEP-TAS is the space-thermal application protocol of ISO 10303, and is how
thermal geometry moves between the tools that speak it.  The file syntax is
ordinary part 21 and is read by :mod:`pycanha.io.part21`; this package puts
meaning on the entities that syntax carries.

The layering is deliberate.  The syntax layer is tool-agnostic and complete;
the entity layer here is grown from files that have actually been seen, and
treats anything it has not seen as something to report rather than something to
fail on.  That is what leaves room for a file from a tool this reader has never
met to still produce most of its geometry.

Writing goes the other way through the same tables, around the fixed reference
dictionary of :mod:`.dictionary`.
"""

from __future__ import annotations

from .diagnostics import Diagnostic, DiagnosticCollector, Severity
from .errors import StepTasError
from .reader import read_steptas_into
from .writer import write_steptas_from

__all__ = [
    "Diagnostic",
    "DiagnosticCollector",
    "Severity",
    "StepTasError",
    "read_steptas_into",
    "write_steptas_from",
]
