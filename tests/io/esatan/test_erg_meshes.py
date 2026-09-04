"""Every committed model meshes, and the mesh has the area the shapes do.

This is the gap a whole class of defects came through. Reading a model
"succeeded" and no test ever called ``model.mesh``, so a chained cut reached a
``ValueError`` at viewer-open time and a quadrilateral meshed as a rectangle
for years -- both in files the reader had been reporting as read cleanly.

The area check is deliberately a *cross*-check: the total triangulated area is
compared against the sum of the primitives' own ``surface_area()``, which the
mesher does not consult. Where a model is cut the two legitimately differ, so
those models assert only that meshing happens at all; ``test_erg_solids`` pins
what a cut removes against the closed form instead.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pycanha_core as pcc
import pytest

from pycanha.gmm import GeometryItem, GeometryModel
from pycanha.gmm.mesh import ops as mesh_ops

DATA = Path(__file__).resolve().parents[2] / "data" / "esatan"

#: Every committed ``.erg``, found rather than listed.
#:
#: A hand-written list is a list somebody has to remember to extend, and one
#: fixture was already missing from this one -- exempt from the guard for as
#: long as nobody noticed.
MODELS: tuple[Path, ...] = tuple(sorted(DATA.rglob("*.erg")))


def is_cut(path: Path) -> bool:
    """Whether anything in the model at *path* is cut away.

    A cut model's triangulated area is *less* than the sum of its primitives by
    however much was removed, which is the point of the cut and not a defect.
    Read off the model's own text, so adding a cut to a fixture moves it into
    the weaker check by itself.
    """
    return bool(re.search(r"=\s*\w+\s*-\s*\w+", path.read_text(encoding="utf-8")))


#: Triangulating a curved surface inscribes it, so the mesh is systematically
#: *under* the analytic area and converges as the mesh refines. Flat shapes are
#: exact. This bounds the shortfall well below the 8 % a rectangle-for-trapezoid
#: reading of the feature model's quadrilateral produced.
TRIANGULATION_TOLERANCE = 0.02


def read(path: Path) -> GeometryModel:
    model = GeometryModel(path.stem)
    model.io.read_esatan_erg(path, on_diagnostic=lambda _note: None)
    return model


@pytest.mark.parametrize("path", MODELS, ids=lambda path: path.stem)
def test_every_committed_model_meshes(path: Path) -> None:
    """The assertion whose absence let a chained cut ship broken."""
    mesh = read(path).mesh
    assert mesh.nt() > 0
    assert mesh.nf() > 0
    assert np.isfinite(np.asarray(mesh.vertices)).all()


@pytest.mark.parametrize(
    "path", [path for path in MODELS if not is_cut(path)], ids=lambda path: path.stem
)
def test_an_uncut_model_meshes_the_area_its_shapes_have(path: Path) -> None:
    """Total triangulated area against the sum of the primitives' own areas.

    Two independent computations: the mesher walks each primitive's
    parametrisation, ``surface_area()`` evaluates a formula. A parametrisation
    that disagrees with its own shape shows up here as a total that does not
    close.
    """
    model = read(path)
    meshed = float(mesh_ops.compute_areas(model.mesh).sum())
    analytic = sum(
        item.primitive.surface_area()
        for item in model.children_recursive()
        if isinstance(item, GeometryItem)
        and not isinstance(item.primitive, (pcc.gmm.Cube, pcc.gmm.TriangularPrism))
    )
    assert meshed == pytest.approx(analytic, rel=TRIANGULATION_TOLERANCE)
    # Inscribed, never circumscribed: a mesh larger than the surface would mean
    # area invented rather than approximated.
    assert meshed <= analytic * (1 + 1e-9)
