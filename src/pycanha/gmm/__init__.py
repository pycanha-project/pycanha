"""Geometric Mathematical Model subpackage."""

import pycanha_core as pcc

from .primitives import (
    Cylinder,
    Quadrilateral,
    Rectangle,
    Triangle,
)

GeometryModel = pcc.gmm.GeometryModel

__all__ = [
    "Cylinder",
    "GeometryModel",
    "Quadrilateral",
    "Rectangle",
    "Triangle",
]
