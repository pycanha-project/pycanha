"""The number format an ESATAN geometry file uses.

Every expectation here is the format's own rendering of the number, stated
rather than derived.  It matters more than it looks: the writer's whole premise
is that its output can be compared against a canonical file as text, and a
number rendered one digit differently makes every such comparison fail.
"""

from __future__ import annotations

import pytest

from pycanha.io.esatan.geometry.canonical import (
    BLOCKS,
    block,
    format_real,
    format_vector,
    indent_arguments,
)

#: (value, rendering).  Grouped by the rule each one pins down.
MEASURED = [
    # Zero, and ordinary magnitudes in fixed notation.
    (0.0, "0.0"),
    (1.0, "1.0"),
    (0.4, "0.4"),
    (0.01, "0.01"),
    (0.02, "0.02"),
    (0.010001, "0.010001"),
    (360.0, "360.0"),
    (2700.0, "2700.0"),
    (-10000.0, "-10000.0"),
    (-0.3, "-0.3"),
    (1000000.0, "1000000.0"),
    # Below 0.01 the exponent form takes over -- 0.0099 is not written 0.0099.
    (0.0099, "9.9e-03"),
    (0.009999, "9.999e-03"),
    (0.009, "9.0e-03"),
    (0.003, "3.0e-03"),
    (0.0035, "3.5e-03"),
    (0.001, "1.0e-03"),
    (0.0015, "1.5e-03"),
    (0.0001, "1.0e-04"),
    (0.0000001, "1.0e-07"),
    (-0.005, "-5.0e-03"),
    # At 1e7 it takes over again at the other end.
    (10000000.0, "1.0e+07"),
    (99999999.0, "9.9999999e+07"),
    (12345678.0, "1.2345678e+07"),
    (123456789.0, "1.2345679e+08"),
    (-12345678900.0, "-1.2345679e+10"),
    # Eight significant digits, and never more than seven decimal places.
    (1.23456789012345, "1.2345679"),
    (0.12345678901234, "0.1234568"),
    (0.33333333333333, "0.3333333"),
    (0.66666666666667, "0.6666667"),
    (0.01234567890123, "0.0123457"),
    (123456.789, "123456.79"),
    (1234567.891, "1234567.9"),
    (9999999.5, "9999999.5"),
]


@pytest.mark.parametrize(("value", "expected"), MEASURED)
def test_reals_are_rendered_as_the_format_writes_them(value: float, expected: str) -> None:
    assert format_real(value) == expected


def test_every_rendering_reads_back_as_a_real() -> None:
    """Whatever is written has to parse, and has to parse close to the input.

    Not exactly: the format keeps eight significant digits and at most seven
    decimal places, so a small value with many decimals loses relative precision
    on the way out.  The tolerance is that limit, not a fudge -- half of the
    smallest decimal the format can carry.
    """
    for value, _ in MEASURED:
        assert float(format_real(value)) == pytest.approx(value, rel=1e-7, abs=5e-8)


def test_a_rendering_always_carries_a_decimal_point() -> None:
    """An integer-valued real written bare would read back as an INTEGER."""
    for value, _ in MEASURED:
        text = format_real(value)
        mantissa = text.split("e")[0]
        assert "." in mantissa, text


def test_integers_and_negative_zero_do_not_produce_surprises() -> None:
    assert format_real(-0.0) == "0.0"
    assert format_real(5) == "5.0"


def test_vectors_are_bracketed_and_comma_separated() -> None:
    assert format_vector([0.0, 1.0, 0.002]) == "[0.0, 1.0, 2.0e-03]"


def test_a_block_is_wrapped_even_when_it_is_empty() -> None:
    """The format writes every block; a missing one reads as a truncated file."""
    assert block("primitive") == [
        "/* Start of primitive block */",
        "",
        "/* End of primitive block - no errors */",
    ]


def test_a_block_keeps_its_body_between_the_markers() -> None:
    lines = block("structure", ["GEOMETRY A;", "A = B + C;"])
    assert lines[0] == "/* Start of structure block */"
    assert lines[-1] == "/* End of structure block - no errors */"
    assert "A = B + C;" in lines


def test_the_blocks_are_in_the_order_the_format_writes_them() -> None:
    assert BLOCKS[0] == "independent variable"
    assert BLOCKS.index("primitive") < BLOCKS.index("structure")
    assert BLOCKS[-1] == "contact zone"


def test_a_call_is_laid_out_one_argument_per_line() -> None:
    assert indent_arguments("D = SHELL_SCS_DISC", [("rmax", "0.1"), ("rmin", "0.0")]) == [
        "D = SHELL_SCS_DISC (",
        "    rmax = 0.1,",
        "    rmin = 0.0);",
    ]


def test_a_call_with_no_arguments_is_still_closed() -> None:
    assert indent_arguments("X = F", []) == ["X = F ();"]
