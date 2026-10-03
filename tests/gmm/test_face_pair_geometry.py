"""Exact face-pair geometry through pycanha.gmm."""

import numpy as np
import pycanha_core as pcc
import pytest

from pycanha import gmm


def test_names_are_the_core_ones() -> None:
    assert gmm.FacePairGeometryEvaluator is pcc.gmm.FacePairGeometryEvaluator
    assert gmm.FacePairGeometry is pcc.gmm.FacePairGeometry
    assert gmm.face_pair_geometry is pcc.gmm.face_pair_geometry


def test_works_on_pycanha_primitives() -> None:
    cone = gmm.Cone((0, 0, 0), (0, 0, 1), (1, 0, 0), 1.0, 0.5, 0.0, 2 * np.pi)
    mesh = gmm.ThermalMesh([0.0, 0.25, 0.5, 1.0], [0.0, 0.4, 1.0])
    evaluator = gmm.FacePairGeometryEvaluator(cone, mesh)
    areas, centroids = evaluator.all()
    assert areas.shape == (6,)
    assert centroids.shape == (6, 3)
    assert areas.sum() == pytest.approx(cone.surface_area(), rel=1e-12)
    single = gmm.face_pair_geometry(cone, mesh, 2, 1)
    assert single.area == areas[2 + 3 * 1]
    with pytest.raises(IndexError):
        evaluator(3, 0)
