"""The conduction subpackage: reaching the gmm -> tmm builder from pycanha.

The builder itself is the core's, and is tested there.  What is tested here is
the layer pycanha puts on top of it: that the whole engine is reachable without
importing ``pycanha_core``, that a build report reads in the same vocabulary as
the file readers' diagnostics, and that the conductive activity -- not the
radiative one -- is what decides which sides become nodes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pycanha_core as pcc
import pytest

import pycanha as pc
from pycanha.gmm import ActiveSide, GeometryItem, ThermalMesh
from pycanha.gmm.materials import BulkMaterial
from pycanha.gmm.primitives import Rectangle
from pycanha.io.diagnostics import Severity

if TYPE_CHECKING:
    from pycanha_core.conduction import TmmBuildReport

ALU = BulkMaterial("Alu", 2700.0, 160.0, 900.0)


def plate(*, bulk: bool = True) -> ThermalMesh:
    """A 2x2-cell square, numbered on both sides, ready to conduct."""
    mesh = ThermalMesh([0.0, 0.5, 1.0], [0.0, 0.5, 1.0])
    mesh.node1_start, mesh.node1_step = 100, 1
    mesh.node2_start, mesh.node2_step = 200, 1
    mesh.side1_thick = mesh.side2_thick = 0.002
    if bulk:
        mesh.side1_material = mesh.side2_material = ALU
    return mesh


def built(mesh: ThermalMesh) -> tuple[pc.ThermalModel, TmmBuildReport]:
    model = pc.ThermalModel()
    model.gmm.add(GeometryItem("P", Rectangle([0, 0, 0], [1, 0, 0], [0, 1, 0]), mesh))
    return model, model.build_tmm_from_gmm()


# -- reaching the builder ---------------------------------------------------


def test_a_model_builds_its_own_conductive_network() -> None:
    """``build_tmm_from_gmm`` reaches a pycanha ThermalModel, not only a core one."""
    model, report = built(plate())
    assert report.items_processed == 1
    # Four cells a side, numbered one apart, plus a conductor per adjacency and
    # one through the thickness of each face pair.
    assert report.nodes_created == 8
    assert report.conductors_created == 12
    assert model.tmm.nodes.num_nodes == 8


def test_the_builder_is_also_a_free_function() -> None:
    model = pc.ThermalModel()
    model.gmm.add(GeometryItem("P", Rectangle([0, 0, 0], [1, 0, 0], [0, 1, 0]), plate()))
    report = pc.conduction.build_tmm_from_gmm(model, pc.conduction.TmmBuildOptions())
    assert report.nodes_created == 8


def test_a_tmm_that_already_holds_nodes_is_refused() -> None:
    """There is no merge semantics, so a second build has to say so."""
    model, _ = built(plate())
    with pytest.raises(ValueError, match=r"(?i)node|coupling"):
        model.build_tmm_from_gmm()


# -- the conductive activity is what counts ---------------------------------


def test_only_conductively_active_sides_become_nodes() -> None:
    mesh = plate()
    mesh.conductive_active_side = ActiveSide.SIDE1
    _, report = built(mesh)
    assert report.nodes_created == 4
    assert "InactiveSideSkipped" in {note.code for note in pc.conduction.diagnostics(report)}


def test_radiating_without_conducting_builds_nothing() -> None:
    """The ESATAN "Radiative" surface: it is in the radiative model only.

    Reading the radiative selector here instead would give this surface a full
    conductive network it never asked for.
    """
    mesh = plate()
    mesh.radiative_active_side = ActiveSide.BOTH
    mesh.conductive_active_side = ActiveSide.NONE
    _, report = built(mesh)
    assert report.nodes_created == 0
    assert report.conductors_created == 0


# -- diagnostics read like the readers' ------------------------------------


def test_a_report_becomes_diagnostics_in_the_shared_vocabulary() -> None:
    _, report = built(plate(bulk=False))
    notes = pc.conduction.diagnostics(report)
    assert [note.code for note in notes] == ["MissingBulk", "MissingBulk"]
    assert all(note.severity is Severity.WARNING for note in notes)
    # The geometry the builder was working on becomes the diagnostic's source.
    assert all(note.source == "P" for note in notes)


def test_every_diagnostic_code_has_a_severity() -> None:
    """A code the core adds must be classified rather than silently defaulted."""
    unclassified = [
        name
        for name in dir(pcc.conduction.DiagnosticCode)
        if not name.startswith("_")
        # The enum type carries its members plus the machinery every enum has.
        and isinstance(getattr(pcc.conduction.DiagnosticCode, name), pcc.conduction.DiagnosticCode)
        and name not in pc.conduction._SEVERITIES
    ]
    assert not unclassified, f"conduction codes with no severity: {unclassified}"


def test_a_summary_counts_repeats_rather_than_repeating_them() -> None:
    _, report = built(plate(bulk=False))
    text = pc.conduction.summary(report)
    # What was built, then the diagnostics grouped by code with a count rather
    # than one line each.
    assert "8 nodes, 0 conductors from 1 items (0 skipped)" in text
    assert "warning: [MissingBulk] x2" in text
    assert text.count("[MissingBulk]") == 1


def test_a_clean_build_says_so() -> None:
    _, report = built(plate())
    assert "no diagnostics" in pc.conduction.summary(report)
