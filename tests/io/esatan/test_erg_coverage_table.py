"""The published coverage table has to agree with the reader.

The table in the documentation is generated from
:mod:`pycanha.io.esatan.geometry.coverage` on every docs build, so it cannot go
stale on disk.  What it *can* do is disagree with the code: the inventory is a
hand-written list of constructs, and nothing about adding a mapping forces
anyone to add the row that announces it.

These check both directions of that -- a construct the table calls supported
must be in the reader's tables, and every refusal in the reader's tables must be
listed -- which is what makes an unannounced change go red instead of quietly
publishing something untrue.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pycanha.io.esatan.geometry import coverage, mappings

FEATURES = Path(__file__).resolve().parents[2] / "data" / "esatan" / "FEATURES"

#: Statuses under which a primitive must be something the reader can build.
_BUILDABLE = frozenset({"supported", "lossy"})


@pytest.fixture(scope="module")
def table() -> list[coverage.Row]:
    return coverage.rows(FEATURES)


def primitives(table: list[coverage.Row]) -> list[coverage.Row]:
    """The rows naming a shell primitive, which are the checkable ones.

    The other kinds -- statements, attributes, materials -- have no single table
    in the reader to compare against, so a row-by-row check there would only
    restate the inventory.
    """
    return [row for row in table if row.kind == "primitive"]


def test_the_inventory_is_populated_and_well_formed(table: list[coverage.Row]) -> None:
    assert len(table) > 50
    assert len({row.construct for row in table}) == len(table), "a construct is listed twice"
    for row in table:
        assert row.pycanha_status in coverage.STATUSES, row.construct
        assert row.kind, row.construct
        assert row.steptas_status in ("", "yes", "no"), row.construct


def test_nothing_is_left_undecided(table: list[coverage.Row]) -> None:
    """`unknown` means the inventory named something the reader has no view on."""
    undecided = [row.construct for row in table if row.pycanha_status == "unknown"]
    assert not undecided, f"no disposition derived for: {undecided}"


def test_every_buildable_primitive_is_in_the_readers_tables(table: list[coverage.Row]) -> None:
    known = set(mappings.PRIMITIVES) | set(mappings.BOXES) | set(mappings.PRISMS)
    claimed = {row.construct for row in primitives(table) if row.pycanha_status in _BUILDABLE}
    missing = claimed - known
    assert not missing, f"the table claims these are built, and they are not: {missing}"


def test_every_refused_primitive_is_refused_with_a_reason(table: list[coverage.Row]) -> None:
    """A refusal has to carry an explanation, not just a failure to match."""
    refused = {row.construct for row in primitives(table) if row.pycanha_status == "unsupported"}
    excused = set(mappings.UNSUPPORTED_PRIMITIVES) | set(mappings.UNSUPPORTED_CONSTRUCTS)
    # SHELL_SCS_TRIANGLE is the one construct with no entry either way: it is
    # simply not mapped yet, and falls through to the unknown-primitive path.
    unexplained = refused - excused - {"SHELL_SCS_TRIANGLE"}
    assert not unexplained, f"refused with no reason recorded: {unexplained}"


def test_the_readers_refusals_all_appear_in_the_table(table: list[coverage.Row]) -> None:
    """The other direction: a construct refused in code must be published.

    This is the one that earns its keep -- three constructs were refused by the
    reader and missing from the inventory entirely the first time it ran.
    """
    listed = {row.construct for row in table}
    refused = set(mappings.UNSUPPORTED_PRIMITIVES) | set(mappings.UNSUPPORTED_CONSTRUCTS)
    assert refused <= listed, f"refused but missing from the table: {refused - listed}"


def test_no_primitive_is_claimed_supported_and_decomposed_at_once(
    table: list[coverage.Row],
) -> None:
    """A box or a prism becomes several surfaces, so it is lossy, never supported."""
    decomposed = set(mappings.BOXES) | set(mappings.PRISMS)
    for row in primitives(table):
        if row.construct in decomposed:
            assert row.pycanha_status == "lossy", row.construct


# -- the fixture column ----------------------------------------------------


def test_the_fixture_column_names_models_that_exist(table: list[coverage.Row]) -> None:
    for row in table:
        if row.fixture:
            assert (FEATURES / row.fixture).is_file(), row.construct


def test_most_constructs_are_exercised_by_a_committed_model(table: list[coverage.Row]) -> None:
    """A construct with no fixture should be one with no representation either."""
    unexercised = [row for row in table if not row.fixture]
    for row in unexercised:
        assert row.pycanha_status in ("unsupported", "n/a", "supported"), row.construct
    # `supported` is allowed above only for INCLUDE, which resolves paths
    # relative to the working directory and so is covered by its own tests.
    supported = {row.construct for row in unexercised if row.pycanha_status == "supported"}
    assert supported == {"INCLUDE"}


def test_a_construct_only_the_wider_model_carries_does_not_convert(
    table: list[coverage.Row],
) -> None:
    """The two models differ by exactly the constructs STEP-TAS refuses."""
    by_construct = {row.construct: row for row in table}
    for construct in ("SHELL_SCS_TORUS", "REMOVE_FACE / RESTORE_FACES"):
        assert by_construct[construct].steptas_status == "no"
    assert by_construct["SHELL_SCS_DISC"].steptas_status == "yes"


def test_the_one_sided_activities_are_no_longer_a_reduction(table: list[coverage.Row]) -> None:
    """A mesh holds one activity per calculation, so nothing is dropped.

    This row was ``lossy`` while a mesh had a single flag and "Radiative" and
    "Conductive" both had to collapse onto it.
    """
    by_construct = {row.construct: row for row in table}
    assert by_construct["side1 / side2 Radiative|Conductive"].pycanha_status == "supported"


# -- rendering -------------------------------------------------------------


def test_the_csv_has_a_header_and_one_line_per_construct(table: list[coverage.Row]) -> None:
    text = coverage.to_csv(table)
    lines = text.strip().splitlines()
    assert lines[0] == ",".join(coverage.COLUMNS)
    assert len(lines) == len(table) + 1


def test_the_csv_can_be_narrowed_to_chosen_columns(table: list[coverage.Row]) -> None:
    text = coverage.to_csv(table, ("construct", "pycanha_status"))
    assert text.splitlines()[0] == "construct,pycanha_status"
