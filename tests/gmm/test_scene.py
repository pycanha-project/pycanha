"""Scene-tree composition sugar (+ / -) and model registration/round-trip."""

import numpy as np
import pytest

import pycanha as pc
from pycanha import gmm


def _rect_item(name: str) -> gmm.GeometryItem:
    return gmm.GeometryItem(name, gmm.Rectangle((0, 0, 0), (1, 0, 0), (0, 1, 0)), gmm.ThermalMesh())


def _cutter(name: str) -> gmm.GeometryItem:
    solid = gmm.Cylinder((0, 0, -1), (0, 0, 1), (0.3, 0, -1), 0.3, 0.0, 2 * np.pi)
    return gmm.GeometryItem(name, solid, gmm.ThermalMesh())


def test_union_builds_flat_group() -> None:
    a, b, c = _rect_item("a"), _rect_item("b"), _rect_item("c")
    group = a + b + c
    assert isinstance(group, gmm.GeometryGroup)
    assert [child.name for child in group.children] == ["a", "b", "c"]


def test_union_does_not_mutate_operands() -> None:
    a, b = _rect_item("a"), _rect_item("b")
    _ = a + b
    # Standalone items have no children of their own.
    assert list(a.children) == []
    assert list(b.children) == []


def test_subtraction_builds_cut_group() -> None:
    cut = _rect_item("panel") - _cutter("hole")
    assert isinstance(cut, gmm.GeometryGroupCutted)
    assert [c.name for c in cut.cutters] == ["hole"]
    assert [t.name for t in cut.targets] == ["panel"]


def test_chained_subtraction_appends_cutters() -> None:
    cut = _rect_item("panel") - _cutter("hole1") - _cutter("hole2")
    assert isinstance(cut, gmm.GeometryGroupCutted)
    assert [c.name for c in cut.cutters] == ["hole1", "hole2"]


def test_non_closed_solid_cutter_raises() -> None:
    with pytest.raises(ValueError, match="closed"):
        _rect_item("panel") - _rect_item("not_a_solid")


def test_model_registration_roundtrip_keeps_subclass() -> None:
    tm = pc.ThermalModel("scene")
    assert isinstance(tm.gmm, gmm.GeometryModel)

    panel = _rect_item("panel")
    tm.gmm.add(panel)
    assert tm.gmm.contains("panel")

    fetched = tm.gmm.get("panel")
    assert isinstance(fetched, gmm.GeometryItem)
    assert fetched.name == "panel"
    assert [child.name for child in tm.gmm.children] == ["panel"]
