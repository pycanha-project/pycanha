"""Errors raised while reading STEP-TAS geometry."""

from __future__ import annotations

from ..errors import ModelReadError

__all__ = ["StepTasError"]


class StepTasError(ModelReadError):
    """Raised for a STEP-TAS file this reader cannot make a model from.

    Anything the file merely says that pycanha cannot hold is reported as a
    diagnostic instead; this is for a file that does not describe a geometric
    model at all, or for the first serious diagnostic under ``strict``.
    """
