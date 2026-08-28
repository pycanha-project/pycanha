"""Per-face area and position, against values the reader did not compute.

Every other numeric test in this directory checks a *whole surface* against a
closed form. That catches a shape built to the wrong size, and misses a shape
built to the right size the wrong way round: transpose a trapezoid's two
parametric directions, or rotate which of its corners comes first, and the
total area does not move at all. What moves is which face is where -- and with
it every per-face quantity the model carries, since node numbers, thermo-optical
properties and activity flags are all indexed by face.

So this fixture gives every face a node of its own and pins two numbers per
node: the area of that face, and the position of its parametric centre. The
expected values live in ``expected_faces.csv`` beside the model. They are
independent of anything in pycanha, which is the point -- a reader and a mesher
that are wrong in the same way agree with each other and disagree with these.

See ``tests/data/esatan/FACEGEOM/README.md`` for the model itself.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from pycanha.gmm import GeometryModel
from pycanha.plot.picking import item_map
from pycanha.plot.properties import face_areas

FIXTURE = Path(__file__).resolve().parents[2] / "data" / "esatan" / "FACEGEOM"
MODEL = FIXTURE / "FACEGEOM.erg"
EXPECTED = FIXTURE / "expected_faces.csv"

#: Flat faces are meshed exactly, so their area is a plain equality.
FLAT_TOLERANCE = 1e-5

#: A curved face is triangulated by an inscribed polygon, so its meshed area is
#: systematically *below* the true one and converges as the mesh refines. The
#: annulus sector here comes in 0.13 % low; the bound is what separates that
#: from a parametrisation error, which is a whole cell out.
CURVED_TOLERANCE = 5e-3

#: The surfaces whose ``uv`` domain is the unit square, so that the midpoint of
#: a face's cut interval is the midpoint of ``to_cartesian``.
#:
#: The annulus sector's first parameter is an arc length rather than a fraction
#: of one, so its cut midpoint is not a uv midpoint and its position cannot be
#: reached this way. Its areas are still checked.
NORMALISED_UV = {"TRAP", "QUAD", "RECT", "TRI"}

CURVED = {"DISC"}


class Face:
    """One face of the model, found by the node number that names it."""

    def __init__(self, item: object, first: int, second: int) -> None:
        self.item = item
        self.first = first
        self.second = second

    def centre(self) -> np.ndarray:
        """The position of the face's parametric centre, in model coordinates."""
        mesh = self.item.thermal_mesh  # type: ignore[attr-defined]
        one, two = list(mesh.dir1_mesh), list(mesh.dir2_mesh)
        uv = np.array(
            [
                (one[self.first] + one[self.first + 1]) / 2.0,
                (two[self.second] + two[self.second + 1]) / 2.0,
            ]
        )
        local = self.item.primitive.to_cartesian(uv)  # type: ignore[attr-defined]
        return np.asarray(
            self.item.transform.apply(np.ascontiguousarray(local))  # type: ignore[attr-defined]
        )


@pytest.fixture(scope="module")
def model() -> GeometryModel:
    built = GeometryModel("FACEGEOM")
    built.io.read_esatan_erg(MODEL, on_diagnostic=lambda _note: None)
    return built


@pytest.fixture(scope="module")
def expected() -> list[dict[str, str]]:
    with EXPECTED.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def faces(model: GeometryModel) -> dict[int, Face]:
    """Every node number in the model, with the face it names.

    Built from ``node_of`` rather than from the world mesh, so a node that two
    faces share would collide here and be caught by the test below.
    """
    found: dict[int, Face] = {}
    for item in item_map(model).values():
        mesh = item.thermal_mesh
        for second in range(len(list(mesh.dir2_mesh)) - 1):
            for first in range(len(list(mesh.dir1_mesh)) - 1):
                for side in (1, 2):
                    found[int(mesh.node_of(first, second, side))] = Face(item, first, second)
    return found


def test_each_node_names_exactly_one_face(
    model: GeometryModel, faces: dict[int, Face], expected: list[dict[str, str]]
) -> None:
    """The premise the rest of the module rests on."""
    total = sum(
        (len(list(item.thermal_mesh.dir1_mesh)) - 1)
        * (len(list(item.thermal_mesh.dir2_mesh)) - 1)
        * 2
        for item in item_map(model).values()
    )
    assert len(faces) == total, "a node number is shared by two faces"
    assert set(faces) == {int(row["node"]) for row in expected}


def test_every_face_has_the_area_it_should(
    model: GeometryModel, expected: list[dict[str, str]]
) -> None:
    """Area per face, not merely per surface.

    A surface meshed the wrong way round has exactly the right total and the
    wrong distribution, which only a per-face comparison sees.
    """
    mesh = model.mesh
    nodes = np.asarray(mesh.node_numbers).astype(np.int64)
    areas = face_areas(mesh)

    for row in expected:
        node = int(row["node"])
        where = np.flatnonzero(nodes == node)
        assert where.size == 1, f"node {node} should name one face of the world mesh"
        tolerance = CURVED_TOLERANCE if row["item"] in CURVED else FLAT_TOLERANCE
        assert areas[int(where[0])] == pytest.approx(float(row["area"]), rel=tolerance), (
            f"node {node} ({row['item']})"
        )


def test_every_face_sits_where_it_should(
    faces: dict[int, Face], expected: list[dict[str, str]]
) -> None:
    """Position of each face's parametric centre.

    This is the assertion that separates a correct parametrisation from a
    plausible one. Two of these surfaces are symmetric enough that a rotated
    corner order reproduces every area exactly; none of them survives having
    its faces compared position by position.
    """
    checked = 0
    for row in expected:
        if row["item"] not in NORMALISED_UV:
            continue
        node = int(row["node"])
        wanted = np.array([float(row["x"]), float(row["y"]), float(row["z"])])
        assert faces[node].centre() == pytest.approx(wanted, abs=1e-5), (
            f"node {node} ({row['item']})"
        )
        checked += 1
    assert checked > 0
