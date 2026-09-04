"""How close the written file is to the canonical form of the format.

The canonical form is what the format looks like once every default is spelled
out, floats are normalised, and each primitive's attributes are in the one fixed
order: two files describing the same model that way differ only in content.

The writer does not aim to reproduce a whole model byte for byte -- it would
have to invent values for concepts a :class:`~pycanha.gmm.GeometryModel` has no
field for.  What it does aim at is that the *only* differences are those
concepts.  These tests pin that down from both sides: the attributes written are
in the format's order, and the attributes not written are exactly the known
list.

The comparison is a round trip on the corpus -- read it, write it, and compare
what was written against what the corpus itself carries.  The corpus states
every attribute in the format, including the ones pycanha cannot hold, which is
what makes the second half of that comparison mean anything.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pycanha.gmm import GeometryModel
from pycanha.io.esatan.geometry.canonical import ATTRIBUTE_ORDER, sort_attributes

CORPUS = Path(__file__).resolve().parents[2] / "data" / "esatan" / "FEATURES.erg"

#: Attributes the format has that a GeometryModel has nowhere to hold.
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
    "insulation2",
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

#: The surface whose mesh the writer says in fewer words, and what it says.
#:
#: The corpus spells this one as explicit cut positions that happen to divide
#: the range evenly.  Reading keeps the cuts; writing recognises them as uniform
#: and says so.  Not a gap and not something to close -- the same mesh, stated
#: the shorter way -- but it has to stay a *recognition* rather than a writer
#: that has forgotten how to say positions at all, which the surface below
#: proves it has not.
UNIFORM_POSITIONS = "SCS_RECT"
KEPT_POSITIONS = "BANK_POSITIONS"

#: Attributes the corpus states in a spelling this comparison cannot see.
#:
#: ``attributes_of`` reads each ``NAME = SHELL_*(...)`` call, and these are given
#: on their own line afterwards instead -- by ``SET_ATTRIBUTE_RECURSIVE`` or by a
#: dotted assignment.  Both spellings are deliberate: they are the two other ways
#: the format has of saying the same thing, and they are covered where the
#: reader is tested rather than here.
SET_ELSEWHERE = {"nbase1", "nbase2", "ndelta1", "ndelta2", "colour1", "colour2", "thick", "bulk"}

_CALL = re.compile(r"^(?P<name>\w+) = (?P<function>SHELL_\w+) ?\((?P<body>.*?)\);", re.S | re.M)


def attributes_of(text: str) -> dict[str, list[str]]:
    """Every ``NAME = SHELL_*(...)`` in *text*, as its list of attribute names."""
    found = {}
    for match in _CALL.finditer(text):
        keys = re.findall(r"^\s*(\w+)\s*=", match.group("body"), re.M)
        found[match.group("name")] = keys
    return found


@pytest.fixture(scope="module")
def written(tmp_path_factory: pytest.TempPathFactory) -> dict[str, list[str]]:
    model = GeometryModel("FEATURES")
    model.io.read_esatan_erg(CORPUS, on_diagnostic=lambda _note: None)
    out = tmp_path_factory.mktemp("canonical") / "written.erg"
    model.io.write_esatan_erg(out, name="FEATURES", on_diagnostic=lambda _note: None)
    return attributes_of(out.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def source() -> dict[str, list[str]]:
    return attributes_of(CORPUS.read_text(encoding="utf-8"))


def test_the_corpus_parses_as_a_list_of_calls(source: dict[str, list[str]]) -> None:
    """Guards the parsing the rest of this module depends on."""
    assert len(source) > 15
    assert source["PT_RECT"][:3] == ["point1", "point2", "point4"]


def test_the_same_primitives_are_written(
    written: dict[str, list[str]], source: dict[str, list[str]]
) -> None:
    """A box and a prism are several surfaces here, so they are named apart."""
    # A box or a prism *used as geometry* becomes several named faces.  The one
    # used as a cutting tool stays a single solid, so it keeps its own name.
    decomposed = {"SCS_BOX", "PT_BOX", "PT_PRISM", "SCS_PRISM"}
    expected = set(source) - decomposed
    faces = {name for name in written if re.search(r"_face\d$", name)}
    assert set(written) - faces == expected


def test_every_attribute_written_is_one_the_format_has(written: dict[str, list[str]]) -> None:
    """A misspelling here produces a file the format does not have."""
    for name, keys in written.items():
        for key in keys:
            if key.startswith("point"):
                continue
            assert key in ATTRIBUTE_ORDER, f"{name}: {key}"


def test_attributes_are_written_in_the_formats_order(written: dict[str, list[str]]) -> None:
    """Same order as a canonical file, so a diff shows content, not arrangement."""
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
    written: dict[str, list[str]], source: dict[str, list[str]]
) -> None:
    """The exit criterion: the difference from the corpus is only those.

    Stated as "never written *anywhere*" rather than per surface.  Per surface
    would conflate two unrelated things -- a surface that simply has no node
    number, and a model with nowhere to put one -- and only the second is a gap.

    Shape arguments are excluded: those differ because the writer always uses
    the by-points spelling, which is a choice recorded as an accepted
    divergence, not something the model cannot hold.
    """
    in_source = {key for keys in source.values() for key in keys if key in ATTRIBUTE_ORDER}
    ever_written = {key for keys in written.values() for key in keys if key in ATTRIBUTE_ORDER}

    missing = in_source - ever_written
    expected = UNMODELLED
    assert missing == expected, (
        f"no longer missing: {sorted(expected - missing)}; "
        f"newly missing: {sorted(missing - expected)}"
    )
    # Nothing may leave this comparison by being spelled somewhere the reader of
    # the corpus does not look: everything set on its own line afterwards has to
    # come back out in the call the writer emits.
    assert ever_written >= SET_ELSEWHERE


def test_an_even_position_list_is_written_as_the_regular_mesh_it_is(
    written: dict[str, list[str]], source: dict[str, list[str]]
) -> None:
    """One surface's cuts divide its range evenly, and one surface's do not.

    Both are given as positions in the corpus.  The even one comes back out as
    ``regular`` with a node count, which is the same mesh in fewer words; the
    uneven one has no shorter form and keeps its positions.  Checking only the
    first would pass just as well on a writer that could not say positions.
    """
    assert "meshPositions2" in source[UNIFORM_POSITIONS]
    assert "meshPositions2" not in written[UNIFORM_POSITIONS]
    assert "meshType2" in written[UNIFORM_POSITIONS]
    assert "nodes2" in written[UNIFORM_POSITIONS]

    assert "meshPositions2" in source[KEPT_POSITIONS]
    assert "meshPositions2" in written[KEPT_POSITIONS]


def test_the_written_file_agrees_with_the_recorded_order(written: dict[str, list[str]]) -> None:
    """The order table against a file written from it -- self-consistency only.

    ``ATTRIBUTE_ORDER`` governs the order the writer sorts attributes into, and
    this compares a file the writer produced against that same table.  It cannot
    catch a wrong table; only a writer that stopped consulting it.  A wrong table
    shows up the moment a model in canonical form is read, which is what the
    ``.erg`` reader tests do continuously.
    """
    for name, keys in written.items():
        rest = [key for key in keys if not key.startswith("point") and key in ATTRIBUTE_ORDER]
        positions = [ATTRIBUTE_ORDER[key] for key in rest]
        assert positions == sorted(positions), f"{name}: {rest}"


def test_sorting_refuses_an_attribute_the_format_does_not_have() -> None:
    with pytest.raises(KeyError, match="not ESATAN geometry attributes"):
        sort_attributes([("sense", "1"), ("nonsense", "1")])
