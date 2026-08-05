"""What the reader does with every ESATAN geometry construct.

This is the inventory behind the coverage table in the documentation, which is
regenerated from here on every docs build rather than kept as a checked-in file
that could quietly fall behind the code.

Only two things here are written by hand: the list of constructs, and a note
explaining each one.  **The disposition is derived** from the reader's own
mapping tables in :mod:`.mappings`, so a primitive that gains an implementation
changes its row by being implemented, not by anyone remembering to say so.
:mod:`tests.io.esatan.test_erg_coverage_table` fails if the two ever disagree.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .mappings import BOXES, PRIMITIVES, PRISMS, UNSUPPORTED_CONSTRUCTS, UNSUPPORTED_PRIMITIVES

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from pathlib import Path

__all__ = ["COLUMNS", "STATUSES", "Row", "rows", "to_csv"]

COLUMNS = ("construct", "kind", "fixture", "pycanha_status", "steptas_status", "note")

#: What the reader does with a construct.
#:
#: ``supported``   -- represented without loss
#: ``lossy``       -- represented, but something about it is dropped
#: ``dropped``     -- skipped with a diagnostic; the model loads without it
#: ``unsupported`` -- no representation at all
#: ``n/a``         -- not a geometry construct, or has no effect
STATUSES = ("supported", "lossy", "dropped", "unsupported", "n/a")


@dataclass(frozen=True)
class Row:
    """One construct's disposition."""

    construct: str
    kind: str
    fixture: str
    pycanha_status: str
    steptas_status: str
    note: str

    def as_dict(self) -> dict[str, str]:
        return {column: getattr(self, column) for column in COLUMNS}


@dataclass(frozen=True)
class _Entry:
    """Everything about a construct the reader's tables cannot tell us."""

    kind: str
    note: str = ""
    steptas: str = ""
    """``no`` where the STEP-TAS converter refuses the construct outright."""
    status: str = ""
    """Set only where the mapping tables do not decide it -- statements, attributes."""


_PIPES = "pipes generate fluid nodes and convective links, which are not modelled"
_BOX_NOTE = "six rectangles as geometry, one closed solid as a cutter"

#: Every ESATAN geometry construct, in the order the table presents them.
_INVENTORY: Mapping[str, _Entry] = {
    # -- primitives given in the shell's own coordinate system
    "SHELL_SCS_DISC": _Entry("primitive"),
    "SHELL_SCS_CYLINDER": _Entry("primitive"),
    "SHELL_SCS_CONE": _Entry("primitive", "given as semi_ang + hmin/hmax, not two radii"),
    "SHELL_SCS_SPHERE": _Entry("primitive", "latitudes become axial truncations r*sin(lat)"),
    "SHELL_SCS_RECTANGLE": _Entry("primitive"),
    "SHELL_SCS_PARABOLOID": _Entry("primitive", "a lower truncation (hmin) is dropped"),
    "SHELL_SCS_BOX": _Entry("primitive", _BOX_NOTE),
    "SHELL_SCS_TRIANGLE": _Entry("primitive", "not yet mapped", status="unsupported"),
    "SHELL_SCS_TRIANGULAR_PRISM": _Entry("primitive"),
    "SHELL_SCS_TRAPEZOID": _Entry("primitive"),
    "SHELL_SCS_TORUS": _Entry("primitive", "no STEP-TAS equivalent either", steptas="no"),
    "SHELL_SCS_PIPE": _Entry("component", _PIPES),
    "SHELL_SCS_PIPE_BEND": _Entry("component", _PIPES),
    # -- the same shapes given by points
    "SHELL_TRIANGLE": _Entry("primitive"),
    "SHELL_RECTANGLE": _Entry("primitive", "the three corners are named 1, 2 and 4"),
    "SHELL_QUADRILATERAL": _Entry("primitive", "an off-plane point4 is projected"),
    "SHELL_DISC": _Entry("primitive", "centre, axis, rim, sector, inner rim"),
    "SHELL_CYLINDER": _Entry("primitive", "origin, axis and height, radius, sector"),
    "SHELL_CONE": _Entry("primitive", "apex first; point5 makes it a frustum"),
    "SHELL_SPHERE": _Entry("primitive", "point5/6 truncate by axial height"),
    "SHELL_PARABOLOID": _Entry("primitive"),
    "SHELL_BOX": _Entry("primitive", _BOX_NOTE),
    "SHELL_TRIANGULAR_PRISM": _Entry(
        "primitive", "three side walls; the triangular ends do not exist"
    ),
    "SHELL_TORUS": _Entry("primitive", steptas="no"),
    "SHELL_HALF_SPACE": _Entry(
        "primitive", "an infinite cutter; cannot be displayed", steptas="no"
    ),
    "SHELL_PIPE": _Entry("component", _PIPES),
    "SHELL_PIPE_BEND": _Entry("component", _PIPES),
    "SOLID_CYLINDER_PARAMS": _Entry("helper", "a parameter helper rather than a primitive"),
    "SOLID_CONE_PARAMS": _Entry("helper", "a parameter helper rather than a primitive"),
    "NON_GEOMETRIC_THERMAL_NODE": _Entry("node", "a thermal node with no geometry", steptas="no"),
    "NON_GEOMETRIC_FLUID_NODE": _Entry("node", "a fluid node; no thermo-hydraulic model here"),
    # -- composition and placement
    "combine (+)": _Entry("structure", status="supported"),
    "cut (-), sense = -1": _Entry("structure", status="supported"),
    "cut (-), sense = +1": _Entry(
        "structure", "keeps what the cutter encloses; no equivalent", "no", "unsupported"
    ),
    "cut with a planar cutter": _Entry(
        "structure", "cutters must bound a solid", "no", "unsupported"
    ),
    "cut with a box": _Entry(
        "structure", "re-read as a closed solid when it appears after a -", status="supported"
    ),
    "SINGLE_COMBINATION": _Entry("structure", status="supported"),
    "ROTATE": _Entry(
        "transform",
        "X then Y then Z about fixed axes; composes with the existing placement",
        status="supported",
    ),
    "ROTATE(clear = TRUE)": _Entry(
        "transform",
        "discards the whole accumulated placement, translation included",
        status="supported",
    ),
    "TRANSLATE": _Entry("transform", status="supported"),
    "ASSEMBLE, static": _Entry("structure", "orientation NO_ORIENTATION", status="supported"),
    "ASSEMBLE, kinematic": _Entry(
        "structure", "imported in its initial pose; the motion is dropped", status="lossy"
    ),
    # -- meshing and node numbering
    'meshType "regular" + nodes/ratio': _Entry("mesh", status="supported"),
    'meshType "positions" + meshPositions': _Entry("mesh", status="supported"),
    "nbase / ndelta": _Entry("nodes", status="supported"),
    "nbase absent or zero": _Entry(
        "nodes", "auto-numbering cannot be reconstructed", status="dropped"
    ),
    "ndeltaY_X (per direction)": _Entry(
        "nodes", "a single scalar step; the first value is used", status="lossy"
    ),
    "face order within a surface": _Entry(
        "nodes", "direction 1 varies fastest, as STEP-TAS does", status="supported"
    ),
    # -- per-side attributes
    "side1 / side2 Active|Inactive": _Entry("attribute", status="supported"),
    "side1 / side2 Radiative|Conductive": _Entry(
        "attribute", "a mesh carries one activity per calculation", status="supported"
    ),
    "opt1 / opt2": _Entry("attribute", status="supported"),
    "colour1 / colour2": _Entry(
        "attribute", "resolved through the format's 32-colour palette", status="supported"
    ),
    'composition "SINGLE" + thick': _Entry(
        "attribute",
        "half the thickness to each conductively active surface; a shell with "
        "neither side conducting has no use for one and keeps none",
        status="supported",
    ),
    'composition "DUAL" + thickY': _Entry("attribute", status="supported"),
    "bulk / bulkY": _Entry("attribute", status="supported"),
    "label1 / label2": _Entry("attribute", status="dropped"),
    "criticality1 / criticality2": _Entry("attribute", status="dropped"),
    "model1 / model2 (sub-model)": _Entry(
        "attribute", "the most valuable loss for correlating results", status="dropped"
    ),
    "analysis_type Finite Element": _Entry(
        "attribute", "imported as lumped parameter, a semantic change", status="dropped"
    ),
    "through_cond / conductance / emittance": _Entry(
        "attribute", "no through-thickness couplings are generated", status="dropped"
    ),
    "insulation1 / insulation2": _Entry("attribute", status="dropped"),
    "sense on a non-cutter": _Entry("attribute", "has no effect except on cutting", status="n/a"),
    # -- materials
    "BULK + triple": _Entry(
        "material", "[density, specific heat, conductivity]", status="supported"
    ),
    "DEFINE_BULK": _Entry("material", status="supported"),
    "orthotropic bulk": _Entry("material", "only the first conductivity is kept", status="lossy"),
    "OPTICAL + 8-value row": _Entry(
        "material", "the two diffuse reflectivities are derived", status="supported"
    ),
    "DEFINE_OPTICAL": _Entry("material", status="supported"),
    "[BOL] / [EOL] rows": _Entry("material", "the default row is used", status="dropped"),
    # -- statements
    "POINT declaration": _Entry("statement", status="supported"),
    "REAL / INTEGER / CONST": _Entry("statement", status="supported"),
    "expressions and functions": _Entry(
        "statement", "evaluated eagerly; trigonometry in degrees", status="supported"
    ),
    "dynamic re-binding": _Entry(
        "statement", "values are frozen at first use, and it is reported", status="dropped"
    ),
    "INCLUDE": _Entry("statement", "spliced, keeping per-file line numbers", status="supported"),
    "DEFINE (substitution)": _Entry("statement", status="unsupported"),
    "DEFINE_GEOMETRY_ATTRIBUTES": _Entry("statement", status="supported"),
    "SET_ATTRIBUTE_RECURSIVE": _Entry("statement", status="supported"),
    "dotted attribute assignment": _Entry("statement", status="supported"),
    "REMOVE_FACE / RESTORE_FACES": _Entry(
        "statement", "the faces stay, so the surface keeps area", "no", "unsupported"
    ),
    "PROPERTY / DEFINE_PROPERTY": _Entry("statement", status="unsupported"),
    "GROUP": _Entry("statement", status="unsupported"),
    "CAVITY": _Entry("statement", status="unsupported"),
}


def _status_of(construct: str, entry: _Entry) -> tuple[str, str]:
    """The reader's disposition for *construct*, read off its own tables."""
    if construct in BOXES or construct in PRISMS:
        # Faithful either way, but the single-primitive identity is gone.
        return "lossy", entry.note or "decomposed into flat faces"
    if construct in PRIMITIVES:
        return entry.status or "supported", entry.note
    if construct in UNSUPPORTED_PRIMITIVES:
        return "unsupported", entry.note or UNSUPPORTED_PRIMITIVES[construct]
    if construct in UNSUPPORTED_CONSTRUCTS:
        return "unsupported", entry.note or UNSUPPORTED_CONSTRUCTS[construct]
    return entry.status or "unknown", entry.note


#: The two committed feature models, and whether their `.stp` is complete.
#:
#: The second is the first minus the constructs the converter refuses, so a
#: construct found in it converts and one found only in the other does not.
#: Ordered so the first match wins: being in the model whose `.stp` is complete
#: is the stronger statement.
FEATURE_MODELS: Mapping[str, bool] = {"FEATURES_TAS.erg": True, "FEATURES_ERG.erg": False}

#: How to spot a construct that is not simply a procedure call by name.
_PATTERNS: Mapping[str, str] = {
    "combine (+)": r"=\s*\w+(\s|\n)*\+",
    "cut (-), sense = -1": r"sense\s*=\s*-\s*1",
    # Named rather than matched on `sense = 1`, which also appears on a
    # primitive that never cuts anything and means nothing there.
    "cut (-), sense = +1": r"-\s*KEEP_CUTTER",
    "cut with a planar cutter": r"SHELL_HALF_SPACE",
    "cut with a box": r"-\s*BOX_CUTTER",
    "ROTATE(clear = TRUE)": r"clear\s*=\s*TRUE",
    "ASSEMBLE, static": r'orientation\s*=\s*"NO_ORIENTATION"',
    "ASSEMBLE, kinematic": r'orientation\s*=\s*"ROTATE"',
    'meshType "regular" + nodes/ratio': r'meshType\d\s*=\s*"regular"',
    'meshType "positions" + meshPositions': r'meshType\d\s*=\s*"positions"',
    "nbase / ndelta": r"nbase\d\s*=",
    "nbase absent or zero": r"AUTO_NUM\s*=\s*SHELL",
    "ndeltaY_X (per direction)": r"ndelta\d_\d\s*=",
    "face order within a surface": r"nodes1\s*=\s*[2-9]",
    "side1 / side2 Active|Inactive": r'side\d\s*=\s*"(Active|Inactive)"',
    "side1 / side2 Radiative|Conductive": r'side\d\s*=\s*"(Radiative|Conductive)"',
    "analysis_type Finite Element": r'analysis_type\s*=\s*"Finite Element"',
    "insulation1 / insulation2": r"insulation\d\s*=",
    "dynamic re-binding": r"^SEMI\s*=",
    "opt1 / opt2": r"opt\d\s*=",
    "colour1 / colour2": r"colour\d\s*=",
    'composition "SINGLE" + thick': r"^\s*thick\s*=",
    'composition "DUAL" + thickY': r'composition\s*=\s*"DUAL"',
    "bulk / bulkY": r"bulk\d?\s*=",
    "label1 / label2": r"label\d\s*=",
    "criticality1 / criticality2": r"criticality\d\s*=",
    "model1 / model2 (sub-model)": r"model\d\s*=",
    "through_cond / conductance / emittance": r"(through_cond|conductance|emittance)\s*=",
    "BULK + triple": r"^\s*\w+\s*=\s*\[[\d.]+,\s*[\d.]+,\s*[\d.]+\];",
    "orthotropic bulk": r'type\s*=\s*"Orthotropic"',
    "OPTICAL + 8-value row": r"=\s*\[([\d.]+,\s*){7}[\d.]+\]",
    "[BOL] / [EOL] rows": r"\[(BOL|EOL)\]",
    "POINT declaration": r"^POINT\s+\w+;",
    "REAL / INTEGER / CONST": r"^(CONST\s+)?(REAL|INTEGER)\s+\w+",
    "expressions and functions": r"=\s*(TAN|SQRT|SIN|COS)\s*\(",
    "dotted attribute assignment": r"^\w+\.\w+\s*=",
    "REMOVE_FACE / RESTORE_FACES": r"REMOVE_FACE\s*\(",
}


def _coverage(fixtures: Path) -> dict[str, tuple[str, str]]:
    """Which feature model exercises each construct, and whether it converts."""
    found: dict[str, tuple[str, str]] = {}
    for filename, converts in FEATURE_MODELS.items():
        path = fixtures / filename
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for construct in _INVENTORY:
            if construct in found:
                continue
            pattern = _PATTERNS.get(construct, rf"\b{re.escape(construct)}\s*\(")
            if re.search(pattern, text, re.MULTILINE):
                found[construct] = (filename, "yes" if converts else "no")
    return found


def rows(fixtures: Path | None = None) -> list[Row]:
    """The inventory, with each construct's disposition taken from the reader.

    Pass *fixtures* -- the directory holding the committed feature models -- to
    fill the ``fixture`` column by reading them; without it that column is
    empty, and nothing else changes.
    """
    covered = _coverage(fixtures) if fixtures is not None else {}
    out = []
    for construct, entry in _INVENTORY.items():
        status, note = _status_of(construct, entry)
        fixture, steptas = covered.get(construct, ("", ""))
        out.append(
            Row(
                construct=construct,
                kind=entry.kind,
                fixture=fixture,
                pycanha_status=status,
                # A recorded refusal outranks a model's presence: the model may
                # carry the construct and still convert, with that one dropped.
                steptas_status="no" if entry.steptas == "no" else steptas,
                note=note,
            )
        )
    return out


def to_csv(table: Iterable[Row], columns: Sequence[str] = COLUMNS) -> str:
    """Render the inventory as CSV, which is what the documentation renders."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in table:
        full = row.as_dict()
        writer.writerow({column: full[column] for column in columns})
    return buffer.getvalue()
