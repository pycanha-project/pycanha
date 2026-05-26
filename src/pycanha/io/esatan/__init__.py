"""ESATAN .d analysis file parsing utilities.

The public entry point lives in :mod:`pycanha.io.esatan_reader`; this package
holds the implementation modules used by :class:`ESATANReader`.
"""

from .errors import EsatanParseError

__all__ = ["EsatanParseError"]
