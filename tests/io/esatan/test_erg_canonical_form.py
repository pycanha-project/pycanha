"""How close the written file is to the form ESATAN itself writes.

A committed reference export sits beside the feature models, so the comparison
is against a real file rather than against a belief about one.

The writer does not aim to reproduce that file byte for byte -- it would have to
invent values for concepts a :class:`~pycanha.gmm.GeometryModel` has no field
for.  What it does aim at is that the *only* differences are those concepts.
These tests pin that down from both sides: the attributes written are in the
format's order, and the attributes not written are exactly the known list.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pycanha.gmm import GeometryModel
from pycanha.io.esatan.geometry.canonical import ATTRIBUTE_ORDER, sort_attributes

FEATURES = Path(__file__).resolve().parents[2] / "data" / "esatan" / "FEATURES"
SOURCE = FEATURES / "FEATURES_TAS.erg"
REFERENCE = FEATURES / "FEATURES_TAS_export.erg"

#: The canonical form of the wider feature model, used only for the order check.
#:
#: It covers the constructs the other one leaves out -- the torus, the
#: half-space cutter, the removed face -- so the attribute order is checked
#: against every construct there is a canonical form for, not just the subset
#: the writer is compared against.
WIDER_REFERENCE = FEATURES / "FEATURES_ERG_export.erg"

#: Attributes ESATAN writes that a GeometryModel has nowhere to hold.
#:
#: Each is a row in the coverage table, and closing any of them means a field in
#: the model or in the core -- not a change to the writer.  A name leaving this
#: set is good news that should still be noticed, so the test asserts equality
#: rather than containment.
UNMODELLED = {
    # Per-side bookkeeping the model has no field for.
    "label1",
    "label2",
    "criticality1",
    "criticality2",
    "model1",
    "model2",
    "insulation1",
    # Lumped-parameter is the only analysis type represented.
    "analysis_type",
    # No through-thickness couplings are generated from geometry.
    "through_cond",
    "conductance",
    "emittance",
    # A node-number increment is one scalar here, so a source giving a different
    # one per direction is reduced and reported.
    "ndelta1_1",
    "ndelta1_2",
    # Only a box (three) and a prism (four) have more than two mesh directions,
    # and both become flat faces here, each with two.
    "meshType3",
    "nodes3",
    "ratio3",
    "meshType4",
    "nodes4",
    "ratio4",
}

#: Written, but said another way -- not a gap, and not something to close.
#:
#: The source spells one mesh as explicit cut positions that happen to divide
#: the range evenly.  Reading it keeps the cuts, and writing recognises them as
#: uniform and says so, which is the same mesh in fewer words.
EXPRESSED_DIFFERENTLY = {"meshPositions2"}

_CALL = re.compile(r"^(?P<name>\w+) = (?P<function>SHELL_\w+) \((?P<body>.*?)\);", re.S | re.M)


def attributes_of(text: str) -> dict[str, list[str]]:
    """Every ``NAME = SHELL_*(...)`` in *text*, as its list of attribute names."""
    found = {}
    for match in _CALL.finditer(text):
        keys = re.findall(r"^\s*(\w+)\s*=", match.group("body"), re.M)
        found[match.group("name")] = keys
    return found


@pytest.fixture(scope="module")
def written(tmp_path_factory: pytest.TempPathFactory) -> dict[str, list[str]]:
    model = GeometryModel("FEATURES_TAS")
    model.io.read_esatan_erg(SOURCE, on_diagnostic=lambda _note: None)
    out = tmp_path_factory.mktemp("canonical") / "written.erg"
    model.io.write_esatan_erg(out, name="FEATURES_TAS", on_diagnostic=lambda _note: None)
    return attributes_of(out.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def reference() -> dict[str, list[str]]:
    return attributes_of(REFERENCE.read_text(encoding="utf-8"))


def test_the_reference_export_is_readable(reference: dict[str, list[str]]) -> None:
    """Guards the parsing the rest of this module depends on."""
    assert len(reference) > 15
    assert reference["PT_RECT"][:3] == ["point1", "point2", "point4"]


def test_the_same_primitives_are_written(
    written: dict[str, list[str]], reference: dict[str, list[str]]
) -> None:
    """A box and a prism are several surfaces here, so they are named apart."""
    # A box or a prism *used as geometry* becomes several named faces.  The one
    # used as a cutting tool stays a single solid, so it keeps its own name.
    decomposed = {"SCS_BOX", "PT_BOX", "PT_PRISM", "SCS_PRISM"}
    expected = set(reference) - decomposed
    faces = {name for name in written if re.search(r"_face\d$", name)}
    assert set(written) - faces == expected


def test_every_attribute_written_is_one_the_format_has(written: dict[str, list[str]]) -> None:
    """A misspelling here produces a file ESATAN rejects."""
    for name, keys in written.items():
        for key in keys:
            if key.startswith("point"):
                continue
            assert key in ATTRIBUTE_ORDER, f"{name}: {key}"


def test_attributes_are_written_in_the_formats_order(written: dict[str, list[str]]) -> None:
    """Same order as an export, so a diff shows content rather than arrangement."""
    for name, keys in written.items():
        rest = [key for key in keys if not key.startswith("point")]
        positions = [ATTRIBUTE_ORDER[key] for key in rest]
        assert positions == sorted(positions), f"{name}: {rest}"


def test_the_leading_arguments_are_the_shape(written: dict[str, list[str]]) -> None:
    """Points come first, before anything the sort touches."""
    for name, keys in written.items():
        leading = [key for key in keys if key.startswith("point")]
        assert keys[: len(leading)] == leading, name


def test_what_is_never_written_is_exactly_what_the_model_cannot_hold(
    written: dict[str, list[str]], reference: dict[str, list[str]]
) -> None:
    """The exit criterion: the difference from a real export is only those.

    Stated as "never written *anywhere*" rather than per surface.  Per surface
    would conflate two unrelated things -- a surface that simply has no node
    number, and a model with nowhere to put one -- and only the second is a gap.

    Shape arguments are excluded: those differ because the writer always uses
    the by-points spelling, which is a choice recorded as an accepted
    divergence, not something the model cannot hold.
    """
    in_reference = {key for keys in reference.values() for key in keys if key in ATTRIBUTE_ORDER}
    ever_written = {key for keys in written.values() for key in keys if key in ATTRIBUTE_ORDER}

    missing = in_reference - ever_written
    expected = UNMODELLED | EXPRESSED_DIFFERENTLY
    assert missing == expected, (
        f"no longer missing: {sorted(expected - missing)}; "
        f"newly missing: {sorted(missing - expected)}"
    )


@pytest.mark.parametrize("path", [REFERENCE, WIDER_REFERENCE], ids=["tas", "erg"])
def test_the_reference_exports_agree_with_the_recorded_order(path: Path) -> None:
    """The order table is a claim about the canonical form; check it against one.

    Both models are checked, because between them they use every construct that
    has a canonical form -- an attribute that only ever appears on a torus or a
    removed face would otherwise never be looked at.
    """
    for name, keys in attributes_of(path.read_text(encoding="utf-8")).items():
        rest = [key for key in keys if not key.startswith("point") and key in ATTRIBUTE_ORDER]
        positions = [ATTRIBUTE_ORDER[key] for key in rest]
        assert positions == sorted(positions), f"{name}: {rest}"


def test_sorting_refuses_an_attribute_the_format_does_not_have() -> None:
    with pytest.raises(KeyError, match="not ESATAN geometry attributes"):
        sort_attributes([("sense", "1"), ("nonsense", "1")])
