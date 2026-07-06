"""Primitive convenience subclasses: tuple construction + surface interface."""

import numpy as np
import pytest

from pycanha import gmm


def test_all_primitives_construct_from_tuples() -> None:
    tri = gmm.Triangle((0, 0, 0), (1, 0, 0), (0, 1, 0))
    rect = gmm.Rectangle((0, 0, 0), (2, 0, 0), (0, 1, 0))
    quad = gmm.Quadrilateral((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0))
    disc = gmm.Disc((0, 0, 0), (0, 0, 1), (1, 0, 0), 0.0, 1.0, 0.0, 2 * np.pi)
    cyl = gmm.Cylinder((0, 0, 0), (0, 0, 1), (1, 0, 0), 1.0, 0.0, 2 * np.pi)
    cone = gmm.Cone((0, 0, 0), (0, 0, 1), (1, 0, 0), 1.0, 0.5, 0.0, 2 * np.pi)
    sph = gmm.Sphere((0, 0, 0), (0, 0, 1), (1, 0, 0), 2.0, -1.0, 1.0, 0.0, 2 * np.pi)
    par = gmm.Paraboloid((0, 0, 0), (0, 0, 1), (1, 0, 0), 1.0, 0.0, 2 * np.pi)
    cube = gmm.Cube((0, 0, 0), (1, 1, 1))

    assert tri.surface_area() == pytest.approx(0.5)
    assert rect.surface_area() == pytest.approx(2.0)
    assert quad.surface_area() == pytest.approx(1.0)
    for primitive in (disc, cyl, cone, sph, par, cube):
        assert primitive.is_valid()
        assert primitive.surface_area() > 0.0


def test_primitive_uv_roundtrip() -> None:
    rect = gmm.Rectangle((0, 0, 0), (2, 0, 0), (0, 1, 0))
    point = np.array([1.0, 0.5, 0.0])
    uv = rect.to_uv(point)
    back = rect.to_cartesian(np.asarray(uv))
    np.testing.assert_allclose(np.asarray(back), point, atol=1e-9)


def test_primitive_rejects_wrong_point_shape() -> None:
    with pytest.raises(ValueError, match="3-component"):
        gmm.Triangle((0, 0), (1, 0, 0), (0, 1, 0))


def test_cube_accepts_orientation_quaternion() -> None:
    cube = gmm.Cube((0, 0, 0), (2, 2, 2), (1.0, 0.0, 0.0, 0.0))
    assert cube.is_valid()
    np.testing.assert_allclose(np.asarray(cube.extent), (2, 2, 2))


def test_is_closed_solid() -> None:
    assert gmm.is_closed_solid(gmm.Cube((0, 0, 0), (1, 1, 1)))
    assert gmm.is_closed_solid(gmm.Cylinder((0, 0, 0), (0, 0, 1), (1, 0, 0), 1.0, 0.0, 2 * np.pi))
    assert not gmm.is_closed_solid(gmm.Rectangle((0, 0, 0), (1, 0, 0), (0, 1, 0)))
