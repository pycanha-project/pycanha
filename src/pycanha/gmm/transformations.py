"""Rigid coordinate transformation with array-like coercion."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pycanha_core as pcc

from ._convert import as_matrix3, as_point, as_quaternion

if TYPE_CHECKING:
    import numpy.typing as npt


class CoordinateTransformation(pcc.gmm.CoordinateTransformation):
    """Rigid 3D transformation (translation + 3x3 rotation matrix).

    Accepts array-likes for the translation, rotation matrix and quaternion
    arguments, coercing them to the float64 layout the bindings require.
    """

    def __init__(
        self,
        translation: npt.ArrayLike | None = None,
        rotation: npt.ArrayLike | None = None,
    ) -> None:
        if translation is None and rotation is None:
            super().__init__()
        elif translation is None or rotation is None:
            msg = "translation and rotation must be provided together"
            raise ValueError(msg)
        else:
            super().__init__(as_point(translation), as_matrix3(rotation))

    @staticmethod
    def from_translation(translation: npt.ArrayLike) -> pcc.gmm.CoordinateTransformation:
        """Pure-translation transformation."""
        return pcc.gmm.CoordinateTransformation.from_translation(as_point(translation))

    @staticmethod
    def from_euler(
        translation: npt.ArrayLike,
        euler_xyz: npt.ArrayLike,
    ) -> pcc.gmm.CoordinateTransformation:
        """Transformation from a translation and XYZ Euler angles."""
        return pcc.gmm.CoordinateTransformation.from_euler(
            as_point(translation), as_point(euler_xyz)
        )

    @staticmethod
    def from_rotation(rotation: npt.ArrayLike) -> pcc.gmm.CoordinateTransformation:
        """Pure-rotation transformation from an (w, x, y, z) quaternion."""
        return pcc.gmm.CoordinateTransformation.from_rotation(as_quaternion(rotation))
