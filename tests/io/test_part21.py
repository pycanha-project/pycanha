"""The ISO 10303-21 syntax layer, on hand-written files.

These use tiny made-up exchange structures rather than a real model: the point
is the *syntax*, and every literal form and every malformed case is easier to
pin down one at a time than to find in a file a tool happened to produce.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from pycanha.io.part21 import (
    DERIVED,
    Enumeration,
    Part21Error,
    Record,
    Reference,
    TypedValue,
    format_entity,
    format_real,
    format_value,
    parse_part21,
    read_part21,
    write_part21,
)

if TYPE_CHECKING:
    from pycanha.io.part21 import Value


def wrap(*records: str) -> str:
    """A minimal exchange structure around the given data-section records."""
    body = "\n".join(records)
    return (
        "ISO-10303-21;\nHEADER;\nFILE_NAME('x','2026-01-01T00:00:00',(''),(''),'','','');\n"
        f"ENDSEC;\nDATA;\n{body}\nENDSEC;\nEND-ISO-10303-21;\n"
    )


def test_a_file_is_read_as_a_header_and_a_table_of_instances() -> None:
    parsed = parse_part21(wrap("#1=POINT(0.0,1.5,-2.0);", "#2=THING(#1);"))
    assert len(parsed) == 2
    assert parsed.entities[1].kind == "POINT"
    assert parsed.entities[1].params == (0.0, 1.5, -2.0)
    header = parsed.header_record("FILE_NAME")
    assert header is not None
    assert header.params[0] == "x"


def test_references_are_left_unresolved_until_asked_for() -> None:
    """Forward references are the norm, so nothing may be resolved while parsing."""
    parsed = parse_part21(wrap("#1=THING(#2);", "#2=POINT(0.0,0.0,0.0);"))
    reference = parsed.entities[1].params[0]
    assert reference == Reference(2)
    assert parsed.entity(reference) is parsed.entities[2]


def test_a_dangling_reference_resolves_to_nothing_rather_than_failing() -> None:
    parsed = parse_part21(wrap("#1=THING(#99);"))
    assert parsed.entity(parsed.entities[1].params[0]) is None


def test_every_literal_form_maps_onto_a_python_value() -> None:
    parsed = parse_part21(
        wrap("#1=EVERYTHING(1,-2.5,1.0E-3,'text',$,*,.T.,.F.,.BOTH.,#7,(1,2),KIND(3.0));")
    )
    assert parsed.entities[1].params == (
        1,
        -2.5,
        1.0e-3,
        "text",
        None,
        DERIVED,
        True,
        False,
        Enumeration("BOTH"),
        Reference(7),
        (1, 2),
        TypedValue("KIND", 3.0),
    )


def test_an_integer_and_a_real_stay_apart() -> None:
    """A count and a measurement are different things, and 3 is not 3.0."""
    parsed = parse_part21(wrap("#1=COUNTS(3,3.0);"))
    count, measure = parsed.entities[1].params
    assert isinstance(count, int)
    assert isinstance(measure, float)


def test_a_quote_inside_a_string_is_written_twice() -> None:
    parsed = parse_part21(wrap("#1=NAMED('it''s here');"))
    assert parsed.entities[1].params[0] == "it's here"


def test_comments_and_line_breaks_inside_a_record_are_ignored() -> None:
    parsed = parse_part21(wrap("#1=SPREAD(/* why not */\n  1.0,\n  2.0);"))
    assert parsed.entities[1].params == (1.0, 2.0)


def test_lists_nest_as_deeply_as_the_file_nests_them() -> None:
    parsed = parse_part21(wrap("#1=DEEP(((1,2),(3)),());"))
    assert parsed.entities[1].params == (((1, 2), (3,)), ())


def test_a_complex_instance_keeps_every_record() -> None:
    """Several entity types can make one instance, and each brings attributes."""
    parsed = parse_part21(wrap("#1=(FIRST(1.0)SECOND('two'));"))
    entity = parsed.entities[1]
    assert entity.kind == "FIRST"
    assert entity.params == (1.0,)
    second = entity.record("second")
    assert second is not None
    assert second.params == ("two",)


def test_instances_can_be_found_by_type() -> None:
    parsed = parse_part21(wrap("#1=POINT(0.0);", "#2=LINE(1.0);", "#3=POINT(2.0);"))
    assert [entity.id for entity in parsed.of_kind("POINT")] == [1, 3]
    assert parsed.kinds() == {"LINE": 1, "POINT": 2}


def test_the_line_a_record_started_on_is_kept() -> None:
    """Diagnostics point at a place in the file, so the position has to survive."""
    parsed = parse_part21(wrap("#1=A(0.0);", "#2=B(0.0);"))
    assert parsed.entities[1].line == 6
    assert parsed.entities[2].line == 7


def test_several_data_sections_land_in_one_table() -> None:
    text = (
        "ISO-10303-21;\nHEADER;\nENDSEC;\n"
        "DATA;\n#1=A(1);\nENDSEC;\n"
        "DATA(('context'));\n#2=B(2);\nENDSEC;\nEND-ISO-10303-21;\n"
    )
    parsed = parse_part21(text)
    assert sorted(parsed.entities) == [1, 2]


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("HEADER;\nENDSEC;\nEND-ISO-10303-21;\n", "no opening magic"),
        ("ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\n#1=A(1);\n", "no end"),
        (wrap("#1=A(1)"), "no closing semicolon"),
        (wrap("#1=A(1);", "#1=B(2);"), "the same instance twice"),
        (wrap("A(1);"), "an instance with no name"),
        (wrap("#1=A(1,);"), "a missing value"),
        ("ISO-10303-21;\nSOMETHING;\nENDSEC;\nEND-ISO-10303-21;\n", "an unknown section"),
    ],
)
def test_a_malformed_file_is_refused_rather_than_half_read(text: str, reason: str) -> None:
    """Syntax is the one thing a permissive reader cannot be permissive about."""
    with pytest.raises(Part21Error):
        parse_part21(text)
    assert reason


def test_a_file_is_read_from_a_path(tmp_path) -> None:
    path = tmp_path / "tiny.stp"
    path.write_text(wrap("#1=A(1);"), encoding="utf-8")
    assert len(read_part21(path)) == 1


# -- writing ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "written"),
    [
        (0.4, "0.4"),
        (360.0, "360.0"),
        (1.0, "1.0"),
        (-0.0, "0.0"),
        (0.0, "0.0"),
        (1e-5, "1.0E-05"),
        (1.79e308, "1.79E+308"),
        (6.123233995736766e-17, "6.123233995736766E-17"),
    ],
)
def test_a_real_always_carries_a_decimal_point(value: float, written: str) -> None:
    """The one form the syntax insists on and ``repr`` will not always give."""
    assert format_real(value) == written


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_a_real_that_is_not_a_number_is_refused(value: float) -> None:
    with pytest.raises(Part21Error):
        format_real(value)


@pytest.mark.parametrize(
    ("value", "written"),
    [
        (None, "$"),
        (DERIVED, "*"),
        (True, ".T."),
        (False, ".F."),
        (42, "42"),
        (-7, "-7"),
        ("plain", "'plain'"),
        ("it's", "'it''s'"),
        (Reference(9), "#9"),
        (Enumeration("BOTH"), ".BOTH."),
        (TypedValue("LENGTH", 2.0), "LENGTH(2.0)"),
        ((), "()"),
        ((1, None, (2.0, Reference(3))), "(1,$,(2.0,#3))"),
    ],
)
def test_every_value_form_is_written_as_the_syntax_spells_it(value, written: str) -> None:
    assert format_value(value) == written


def test_a_boolean_is_not_written_as_the_integer_it_subclasses() -> None:
    """``True`` is ``1`` in Python and ``.T.`` here, and the two are not the same."""
    assert format_value(True) != format_value(1)


def test_an_unwritable_value_is_refused() -> None:
    # Deliberately outside the value model: the cast is how the test says so,
    # since the whole point is what happens when a caller gets it wrong.
    with pytest.raises(Part21Error):
        format_value(cast("Value", object()))


def test_an_instance_is_written_as_a_numbered_record() -> None:
    assert format_entity(42, "MGM_FACE", [Reference(7)]) == "#42=MGM_FACE(#7);"


def test_what_is_written_reads_back_as_what_it_was(tmp_path) -> None:
    """The two halves of the syntax layer against each other, on every form."""
    params = (
        "a name",
        2.5,
        -3,
        None,
        DERIVED,
        Reference(2),
        Enumeration("INSIDE"),
        (1.0, 2.0),
        (),
        True,
    )
    path = tmp_path / "written.stp"
    write_part21(
        path,
        header=[Record("FILE_SCHEMA", (("some_schema",),))],
        data=[format_entity(1, "THING", params), format_entity(2, "OTHER", ())],
    )
    parsed = read_part21(path)
    assert parsed.entities[1].params == params
    assert parsed.entities[2].params == ()
    schema = parsed.header_record("FILE_SCHEMA")
    assert schema is not None
    assert schema.params == (("some_schema",),)


def test_a_written_file_has_the_same_line_endings_everywhere(tmp_path) -> None:
    """A file written on one platform has to be the file written on any other."""
    path = tmp_path / "written.stp"
    write_part21(path, header=(), data=[format_entity(1, "A", (1,))])
    assert b"\r\n" not in path.read_bytes()
