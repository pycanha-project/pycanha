"""ESATAN geometry: statement tree to :class:`~pycanha.gmm.GeometryModel`.

This subpackage knows nothing about parsing -- it consumes the statement tree
built by :mod:`pycanha.io.esatan.lang` -- and it is the only place that knows
both vocabularies, so the conversion tables cannot drift from the code that
uses them.
"""

from __future__ import annotations

from .builder import read_erg_into
from .canonical import format_real, format_vector
from .mappings import cuts_to_esatan_mesh, esatan_mesh_to_cuts
from .writer import write_erg_from

__all__ = [
    "cuts_to_esatan_mesh",
    "esatan_mesh_to_cuts",
    "format_real",
    "format_vector",
    "read_erg_into",
    "write_erg_from",
]
