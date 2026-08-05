"""Errors shared by the model readers and writers."""

from __future__ import annotations

__all__ = ["ModelReadError"]


class ModelReadError(Exception):
    """Raised when a model file cannot be read as the format it claims to be.

    Every format's own error derives from this one, so a caller that does not
    care which format failed can catch the base and a caller that does can
    catch the specific one.
    """
