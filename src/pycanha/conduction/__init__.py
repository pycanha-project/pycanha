"""Conduction subpackage - building a tmm's conductive network from the gmm.

Re-exports the compiled ``pycanha_core.conduction`` builder so user code never
has to import ``pycanha_core`` directly::

    import pycanha as pc

    model = pc.ThermalModel()
    ...                                    # build the gmm, number the faces
    report = model.build_tmm_from_gmm()
    print(pc.conduction.summary(report))

The builder walks the geometry model and, for every active face that carries a
node number, creates one thermal node plus the in-plane and through-thickness
conductors those faces imply.  Whether a side conducts is
``ThermalMesh.conductive_active_side``, which is independent of the radiative
one: a surface can conduct without radiating and the other way round.

Every geometry item builds its own :class:`NetworkPart` from its definition --
exact capacities, never a triangulation unless the item is cut -- and the parts
are written with the bulk calls.  :func:`build_network_part` and
:func:`commit_network_parts` expose the two steps.  The node area ``a`` is the
triangulated one and is not set by the build: call :func:`assign_node_areas`
when it is needed.

Radiative couplings, parameters, formulas and thermal data are left untouched,
and the build refuses to run on a tmm that already holds nodes or conductive
couplings -- there is no merge semantics.

The builder types are re-exported verbatim (the bindings are a 1:1, policy-free
exposure of the C++ core).  :func:`diagnostics` and :func:`summary` are added on
top so a report reads in the same vocabulary as the file readers'
:class:`pycanha.io.diagnostics.Diagnostic`, which is where most callers have
already met the idea of "converted, but here is what it cost".
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from pycanha.io.diagnostics import Diagnostic, DiagnosticCollector, Severity

if TYPE_CHECKING:
    from pycanha_core.conduction import (
        BuildDiagnostic,
        DiagnosticCode,
        FacePairLink,
        MeridianProfile,
        NetworkPart,
        TmmBuildOptions,
        TmmBuildReport,
        assign_node_areas,
        build_network_part,
        build_tmm_from_gmm,
        commit_network_parts,
        diagnostic_code_name,
        for_each_intra_primitive_link,
        intra_primitive_links,
        profile_of,
        through_thickness_conductance,
    )

__all__ = [
    "BuildDiagnostic",
    "DiagnosticCode",
    "FacePairLink",
    "MeridianProfile",
    "NetworkPart",
    "TmmBuildOptions",
    "TmmBuildReport",
    "assign_node_areas",
    "build_network_part",
    "build_tmm_from_gmm",
    "commit_network_parts",
    "diagnostic_code_name",
    "diagnostics",
    "for_each_intra_primitive_link",
    "intra_primitive_links",
    "profile_of",
    "summary",
    "through_thickness_conductance",
]

# Builder types re-exported verbatim from the compiled pycanha_core.conduction module.
_CORE_CONDUCTION_EXPORTS = frozenset(__all__) - {"diagnostics", "summary"}

#: How seriously to take each builder diagnostic.
#:
#: A build never fails on a diagnostic, so the severity says how much of the
#: model it costs.  ``INFO`` is a deliberate choice of the model's or of the
#: builder's -- an inactive side, a cutter-only primitive, the near-axis
#: conductance form.  ``WARNING`` is a conductively active side that ends up
#: contributing less than it asked to, including the in-plane conductors a cut
#: removes and the nodes it leaves uncoupled.
_SEVERITIES: dict[str, Severity] = {
    "CutFacePairs": Severity.WARNING,
    "UncoupledNodes": Severity.WARNING,
    "UnmeshedPrimitive": Severity.INFO,
    "InactiveSideSkipped": Severity.INFO,
    "DiscreteLinkFallback": Severity.INFO,
    "AxisSingularity": Severity.INFO,
    "MissingBulk": Severity.WARNING,
    "ZeroThickness": Severity.WARNING,
    "ZeroConductivity": Severity.WARNING,
    "MixedBulkOnNode": Severity.WARNING,
    "NoNodeNumbers": Severity.WARNING,
    "DegenerateFacePair": Severity.WARNING,
}


def diagnostics(report: TmmBuildReport) -> list[Diagnostic]:
    """A build report's diagnostics in the form the file readers produce.

    The code is the :class:`DiagnosticCode` member's own name, so it stays
    stable and greppable the way the reader codes are, and the geometry the
    builder was working on becomes the diagnostic's ``source``.
    """
    core = import_module("pycanha_core").conduction
    return [
        Diagnostic(
            severity=_SEVERITIES.get(core.diagnostic_code_name(item.code), Severity.WARNING),
            code=core.diagnostic_code_name(item.code),
            message=item.message,
            source=item.geometry_name,
        )
        for item in report.diagnostics
    ]


def summary(report: TmmBuildReport) -> str:
    """A short report of what the build produced and what it cost.

    Grouped by code with counts: a model that hits the same approximation on
    every primitive should read as one line, not as thousands of identical
    ones.  A build that cut geometry adds a line with what the cuts did to the
    network.
    """
    counted = DiagnosticCollector(on_diagnostic=lambda _: None)
    for item in diagnostics(report):
        counted.add(item.severity, item.code, item.message, source=item.source)
    cuts = ""
    if report.face_pairs_cut or report.face_pairs_removed:
        cuts = (
            f"cuts: {report.face_pairs_cut} face pairs cut, "
            f"{report.face_pairs_removed} removed, "
            f"{report.links_removed} in-plane conductors removed\n"
        )
    return (
        f"{report.nodes_created} nodes, {report.conductors_created} conductors "
        f"from {report.items_processed} items ({report.items_skipped} skipped)\n"
        f"{cuts}{counted.summary()}"
    )


def __getattr__(name: str) -> Any:
    # Resolved lazily so importing pycanha does not pull in the compiled
    # builder unless it is actually used.
    if name in _CORE_CONDUCTION_EXPORTS:
        value = getattr(import_module("pycanha_core").conduction, name)
        globals()[name] = value
        return value

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
