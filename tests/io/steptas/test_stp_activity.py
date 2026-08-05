"""Which sides are active, across the STEP-TAS boundary.

A mesh states its radiative and its conductive activity separately, and the
format states only the first: ``mgm_active_side_type`` says which sides
*radiate*.  So the two directions are asymmetric, and each asymmetry is a place
a model can quietly lose something.

* Reading, the conductive activity has to come from somewhere.  Copying the
  radiative one would drop every conductive-only side, so it is inferred from
  the only conduction-related thing a STEP-TAS surface carries -- a bulk
  material and a thickness to conduct through -- and the inference is reported.
* Writing, a side that conducts without radiating has nowhere to go, and that
  is reported too.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pycanha.gmm import GeometryItem, GeometryModel
from pycanha.gmm.materials import BulkMaterial, OpticalMaterial
from pycanha.gmm.primitives import Rectangle
from pycanha.gmm.thermalmesh import ActiveSide, ThermalMesh

if TYPE_CHECKING:
    from pathlib import Path

    from pycanha.io.diagnostics import DiagnosticCollector

#: Where a written surface keeps side 1's thickness, mirroring the reader's
#: ``_THICKNESS[0]``.  Not taken on trust: the test that uses it asserts the
#: field it blanked was the thickness and not something else.
_THICKNESS1 = 8

ALU = BulkMaterial("Alu", 2700.0, 160.0, 900.0)
PAINT = OpticalMaterial("Paint", [0.8, 0.0, 0.0, 0.3, 0.0, 0.0])


def quiet(_note: object) -> None:
    """Swallow diagnostics; the tests that care collect them themselves."""


def one_surface(mesh: ThermalMesh) -> GeometryModel:
    model = GeometryModel("ONE")
    model.add(GeometryItem("PLATE", Rectangle([0, 0, 0], [1, 0, 0], [0, 1, 0]), mesh))
    return model


def write(mesh: ThermalMesh, path: Path) -> set[str]:
    """Write a one-surface model, returning the codes reported."""
    return set(one_surface(mesh).io.write_steptas(path, on_diagnostic=quiet).codes())


def read_back(path: Path) -> tuple[ThermalMesh, DiagnosticCollector]:
    """Read a one-surface file, returning its mesh and the diagnostics."""
    model = GeometryModel("back")
    diagnostics = model.io.read_steptas(path, on_diagnostic=quiet)
    return model.get_item("PLATE").thermal_mesh, diagnostics


# -- reading: the conductive activity is inferred ---------------------------


@pytest.mark.parametrize(
    ("thickness", "material", "conducts"),
    [
        (0.002, ALU, True),
        (0.0, None, False),
    ],
)
def test_a_side_conducts_when_it_has_something_to_conduct_through(
    tmp_path: Path, thickness: float, material: BulkMaterial | None, conducts: bool
) -> None:
    mesh = ThermalMesh()
    mesh.side1_optical = PAINT
    mesh.side1_thick = thickness
    if material is not None:
        mesh.side1_material = material
    target = tmp_path / "surface.stp"
    write(mesh, target)

    back, _ = read_back(target)
    assert back.is_conductive_active(1) is conducts
    # Side 2 has neither, throughout, so it never conducts.
    assert back.is_conductive_active(2) is False


def test_a_bulk_material_without_a_thickness_does_not_conduct(tmp_path: Path) -> None:
    """One of the two is not enough: there is no length to conduct along.

    The writer will not produce this on its own -- it carries the pair or
    neither -- so the file is edited to hold what another tool might write.
    """
    mesh = ThermalMesh()
    mesh.side1_optical = PAINT
    mesh.side1_thick = 0.002
    mesh.side1_material = ALU
    target = tmp_path / "surface.stp"
    write(mesh, target)

    edited = tmp_path / "edited.stp"
    edited.write_text(_blank_field(target.read_text(encoding="utf-8")), encoding="utf-8")

    back, _ = read_back(edited)
    # The blanked field really was the thickness, and only it: the bulk survives.
    assert back.side1_thick == pytest.approx(0.0)
    assert back.side1_material is not None
    assert back.is_conductive_active(1) is False


def test_the_inference_is_reported_rather_than_passed_off_as_read(tmp_path: Path) -> None:
    mesh = ThermalMesh()
    mesh.side1_optical = PAINT
    mesh.side1_thick = 0.002
    mesh.side1_material = ALU
    target = tmp_path / "surface.stp"
    write(mesh, target)

    _, diagnostics = read_back(target)
    assert "TAS_CONDUCTIVE_INFERRED" in diagnostics.codes()


def test_the_radiative_activity_is_read_and_not_inferred(tmp_path: Path) -> None:
    """A side that radiates without conducting stays that way.

    Inferring the conductive activity from the radiative one would make this
    surface conduct, which is the mistake the inference exists to avoid.
    """
    mesh = ThermalMesh()
    mesh.side1_optical = PAINT
    mesh.radiative_active_side = ActiveSide.SIDE1
    mesh.conductive_active_side = ActiveSide.NONE
    target = tmp_path / "surface.stp"
    write(mesh, target)

    back, _ = read_back(target)
    assert back.radiative_active_side is ActiveSide.SIDE1
    assert back.conductive_active_side is ActiveSide.NONE


# -- writing: a conductive-only side has nowhere to go ----------------------


def test_a_side_that_conducts_without_radiating_is_reported(tmp_path: Path) -> None:
    mesh = ThermalMesh()
    mesh.radiative_active_side = ActiveSide.NONE
    mesh.conductive_active_side = ActiveSide.SIDE1
    mesh.side1_thick = 0.002
    mesh.side1_material = ALU
    assert "TAS_CONDUCTIVE_ONLY_DROPPED" in write(mesh, tmp_path / "surface.stp")


def test_a_side_that_does_both_is_not_reported(tmp_path: Path) -> None:
    """Only the half that cannot be written is worth saying anything about."""
    mesh = ThermalMesh()
    mesh.side1_optical = PAINT
    mesh.radiative_active_side = ActiveSide.SIDE1
    mesh.conductive_active_side = ActiveSide.SIDE1
    mesh.side1_thick = 0.002
    mesh.side1_material = ALU
    assert "TAS_CONDUCTIVE_ONLY_DROPPED" not in write(mesh, tmp_path / "surface.stp")


def _blank_field(text: str) -> str:
    """Unset side 1's thickness on the one meshed surface in *text*."""
    marker = "MGM_MESHED_PRIMITIVE_BOUNDED_SURFACE("
    out = []
    for line in text.splitlines(keepends=True):
        if marker not in line:
            out.append(line)
            continue
        head, _, rest = line.partition(marker)
        params, _, tail = rest.rpartition(")")
        fields = params.split(",")
        fields[_THICKNESS1] = "$"
        out.append(f"{head}{marker}{','.join(fields)}){tail}")
    return "".join(out)
