"""Side 1 and side 2 stay where the model put them, on every committed model.

A face is one-sided. The two faces of a **pair** share geometry and have
opposite normals, and the even/odd face id is how that relation is stored: side
1 takes the even id, side 2 the odd one. A triangle always defines *both* faces
of its pair and its winding normal is side 1, so a triangle is never tagged with
an odd id and ``face_id % 2`` *is* the side.

Nothing asserted any of that, which is how a Disc shipped wound against its own
axis: every disc in every model had its two sides exchanged, so node numbers and
thermo-optical properties were attached to the wrong physical face. The defect
was invisible wherever both sides happened to carry the same material -- these
tests look at the parity itself rather than at what it happened to select.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pycanha_core as pcc
import pytest

from pycanha.gmm import GeometryModel
from pycanha.plot.picking import item_map

DATA = Path(__file__).resolve().parents[2] / "data" / "esatan"

MODELS = (
    "FEATURES/FEATURES_ERG.erg",
    "FEATURES/FEATURES_TAS.erg",
    "CUTTERS/CUTTERS.erg",
    "DISC/DISC.erg",
    "FACEGEOM/FACEGEOM.erg",
)


#: The primitives that exist only to cut with, and so are never triangulated.
CUT_ONLY = (pcc.gmm.Cube, pcc.gmm.TriangularPrism)


def read(name: str) -> GeometryModel:
    path = DATA / name
    model = GeometryModel(path.stem)
    model.io.read_esatan_erg(path, on_diagnostic=lambda _note: None)
    return model


@pytest.mark.parametrize("name", MODELS)
def test_no_triangle_carries_an_odd_face_id(name: str) -> None:
    """Parity is the side, so an odd-tagged triangle is a swapped side.

    A cut classifier that compared a triangle's winding against the primitive's
    normal and returned the odd id when they disagreed produced exactly this,
    and for a cut disc it did so for *every* triangle.
    """
    face_ids = np.asarray(read(name).mesh.face_ids).astype(np.int64)
    odd = np.flatnonzero(face_ids % 2 != 0)
    assert odd.size == 0, f"{odd.size} triangles tagged with an odd (side-2) face id"


@pytest.mark.parametrize("name", MODELS)
def test_every_item_starts_on_an_even_face(name: str) -> None:
    """An item whose base is odd has side 1 and side 2 exchanged throughout.

    This is what a face count taken from the surviving triangles used to break:
    a trailing cut-away pair took the maximum down with it, the item reported an
    odd number of faces, and every later item was shifted by an odd amount.
    """
    mesh = read(name).mesh
    for geometry_id, first_face_id, last_face_id in mesh.primitives:
        assert int(first_face_id) % 2 == 0, f"geometry {geometry_id} starts on an odd face"
        assert int(last_face_id) % 2 == 0, f"geometry {geometry_id} ends on an odd face"


@pytest.mark.parametrize("name", MODELS)
def test_the_face_count_is_even(name: str) -> None:
    """Faces come in pairs, so an odd total means one lost its partner."""
    assert int(read(name).mesh.nf()) % 2 == 0


@pytest.mark.parametrize("name", MODELS)
def test_side_one_faces_carry_the_side_one_node_numbers(name: str) -> None:
    """The even face of each pair holds what the ThermalMesh calls side 1.

    Read off the world mesh and compared against the item's own ``side1_*`` /
    ``side2_*`` fields -- the two ends of the path that the disc defect broke in
    the middle of.
    """
    model = read(name)
    mesh = model.mesh
    node_numbers = np.asarray(mesh.node_numbers).astype(np.int64)
    by_id = item_map(model)

    checked = 0
    for geometry_id, first_face_id, _last in mesh.primitives:
        item = by_id.get(int(geometry_id))
        if item is None:
            continue
        thermal_mesh = item.thermal_mesh
        first = int(first_face_id)
        if first + 1 >= node_numbers.size:
            continue
        for side, face in ((1, first), (2, first + 1)):
            start = int(getattr(thermal_mesh, f"node{side}_start"))
            if start < 0:
                continue
            assert int(node_numbers[face]) == start, (
                f"{item.name}: face {face} should hold side-{side} node {start}"
            )
            checked += 1
    assert checked > 0


@pytest.mark.parametrize("name", MODELS)
def test_triangle_winding_agrees_with_the_primitive_normal(name: str) -> None:
    """The assertion whose absence hid the disc defect, run on real models.

    A triangle's winding normal *defines* side 1, so every primitive must wind
    its triangulation to agree with its own ``normal_at_uv``. The disc did not:
    ``normal_at_uv`` returned its axis while the mesher wound the other way, so
    the raytracer took a disc's -axis face as side 1 while the reader and the
    conduction builder took the +axis one. Node numbers, thermo-optical
    properties and activity flags all follow the face id, so all of them sat on
    the wrong physical face -- on every disc, cut or not.

    The two are independent descriptions of the same surface, so comparing them
    needs nothing else. Each item is meshed on its own, because the world mesh's
    primitive ranges may overlap and attribute a triangle to a later item.

    The expected normal is averaged over the triangle's three *vertices*, which
    lie exactly on the surface, rather than taken at its centroid, which for a
    curved surface does not. What is left is discretisation: a flat triangle
    across a curved patch tilts away from the surface it spans, worst at a cone
    apex. A reversed primitive gives -1, so the sign is decisive and the
    measured worst legitimate case is +0.86.
    """
    model = read(name)
    checked = 0
    for item in item_map(model).values():
        primitive = item.primitive
        if isinstance(primitive, CUT_ONLY):
            continue  # a cutter-only solid is never meshed
        inverse = item.transform.inverse()
        vertices = np.asarray(item.mesh.vertices, dtype=np.float64)
        for triangle in np.asarray(item.mesh.triangles):
            # Into the primitive's own frame; item.mesh is in its parent's.
            corners = [np.ascontiguousarray(inverse.apply(vertices[i])) for i in triangle[:3]]
            winding = np.cross(corners[1] - corners[0], corners[2] - corners[0])
            length = float(np.linalg.norm(winding))
            if length < 1e-12:
                continue
            expected = np.mean(
                [
                    np.asarray(primitive.normal_at_uv(np.asarray(primitive.to_uv(corner))))
                    for corner in corners
                ],
                axis=0,
            )
            scale = float(np.linalg.norm(expected))
            if scale < 1e-9:
                continue  # the three vertex normals cancel: a full closed sweep
            assert float(winding / length @ (expected / scale)) > 0.0, (
                f"{item.name}: a triangle is wound against its own normal_at_uv"
            )
            checked += 1
    assert checked > 0
