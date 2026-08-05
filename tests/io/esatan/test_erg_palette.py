"""ESATAN's colour palette, and finding the way back to it.

The format names one of thirty-two colours; a thermal mesh stores a value.  So
reading resolves a name and writing picks a name back, and the property that
matters is that those two are inverse: a model read from a file and written out
again must name the same colours it was given.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pycanha_core as pcc
import pytest

from pycanha.gmm import GeometryModel
from pycanha.gmm.materials import Color
from pycanha.io.esatan.geometry.palette import (
    DEFAULT_COLOUR,
    PALETTE,
    colour_of,
    nearest_name,
)

FEATURES = Path(__file__).resolve().parents[2] / "data" / "esatan" / "FEATURES"

_PAINT = "OPTICAL Paint;\nDEFINE_OPTICAL (optical = Paint, ir_emiss = 0.8, solar_absorb = 0.3);\n"


def entry(name: str) -> Color:
    """The palette entry for *name*, where the test means a name that is in it.

    ``colour_of`` answers ``None`` for a name the palette does not hold, which
    is its own test below; everywhere else an unresolved name is the failure,
    and saying so here keeps it from surfacing as an attribute error further on.
    """
    colour = colour_of(name)
    assert colour is not None, f"{name!r} is not a palette colour"
    return colour


# -- the table itself ------------------------------------------------------


def test_the_palette_has_the_thirty_two_colours_the_format_defines() -> None:
    assert len(PALETTE) == 32
    assert DEFAULT_COLOUR in PALETTE
    for name, fractions in PALETTE.items():
        assert name == name.upper(), name
        assert len(fractions) == 3, name
        assert all(0.0 <= channel <= 1.0 for channel in fractions), name


def test_no_two_entries_are_the_same_colour() -> None:
    """Two identical entries would make the name a coin toss on the way back."""
    values = [tuple(entry(name).rgb) for name in PALETTE]
    assert len(set(values)) == len(values)


def test_the_palette_agrees_with_the_core_to_within_one_step() -> None:
    """The core ships the same names; it truncates where this rounds.

    Not a tolerance chosen for comfort -- one part in 255 is the whole of the
    difference, and this fails if either side ever changes a colour rather than
    a rounding.
    """
    for name in PALETTE:
        mine = list(entry(name).rgb)
        theirs = list(pcc.gmm.Color(name).rgb)
        assert all(abs(a - b) <= 1 for a, b in zip(mine, theirs, strict=True)), (
            f"{name}: {mine} vs {theirs}"
        )


def test_an_unknown_name_is_not_resolved() -> None:
    assert colour_of("CHARTREUSE") is None
    assert colour_of("") is None


def test_a_name_is_matched_regardless_of_case_or_padding() -> None:
    assert list(entry(" red ").rgb) == [255, 0, 0]


# -- finding the way back --------------------------------------------------


@pytest.mark.parametrize("name", list(PALETTE))
def test_every_palette_colour_names_itself(name: str) -> None:
    """The property the whole scheme rests on, checked for all thirty-two."""
    assert nearest_name(entry(name)) == name


def test_a_colour_off_the_palette_gets_the_closest_one() -> None:
    assert nearest_name(Color(254, 1, 1)) == "RED"
    assert nearest_name(Color(2, 2, 2)) == "BLACK"
    assert nearest_name(Color(250, 250, 250)) == "WHITE"
    # Halfway up the greys: nearer 0.55 than 0.44 or 0.66.
    assert nearest_name(Color(140, 140, 140)) == "GREY"


def test_a_plain_triple_is_accepted_as_well_as_a_colour() -> None:
    assert nearest_name([255, 0, 0]) == "RED"


def test_something_that_is_not_a_colour_is_refused() -> None:
    with pytest.raises(ValueError, match="three channels"):
        nearest_name([255, 0])


def test_the_choice_does_not_depend_on_dictionary_order() -> None:
    """A tie goes to whichever entry the format lists first, every time."""
    midpoint = Color(0, 191, 191)  # equidistant from CYAN and METAL_GREY
    assert nearest_name(midpoint) == nearest_name(midpoint)
    assert nearest_name(midpoint) in {"CYAN", "METAL_GREY"}


# -- through the reader and the writer -------------------------------------


def build(tmp_path: Path, body: str) -> GeometryModel:
    source = tmp_path / "source.erg"
    source.write_text(f"BEGIN_MODEL M\n{_PAINT}{body}\nEND_MODEL\n", encoding="utf-8")
    model = GeometryModel("M")
    model.io.read_esatan_erg(source, on_diagnostic=lambda _note: None)
    return model


def test_reading_resolves_the_name_to_the_formats_own_value(tmp_path: Path) -> None:
    body = (
        "GEOMETRY R;\nR = SHELL_SCS_RECTANGLE(xmax = 1.0, ymax = 1.0, "
        'colour1 = "ORANGE", colour2 = "LAVENDER", opt1 = Paint, opt2 = Paint);\nM = R;\n'
    )
    mesh = build(tmp_path, body).get_item("R").thermal_mesh
    assert list(mesh.side1_color.rgb) == [255, 128, 0]
    assert list(mesh.side2_color.rgb) == [64, 64, 191]


def test_an_unknown_colour_name_is_reported_and_defaulted(tmp_path: Path) -> None:
    source = tmp_path / "source.erg"
    source.write_text(
        f"BEGIN_MODEL M\n{_PAINT}GEOMETRY R;\nR = SHELL_SCS_RECTANGLE(xmax = 1.0, ymax = 1.0, "
        'colour1 = "CHARTREUSE", opt1 = Paint, opt2 = Paint);\nM = R;\nEND_MODEL\n',
        encoding="utf-8",
    )
    model = GeometryModel("M")
    diagnostics = model.io.read_esatan_erg(source, on_diagnostic=lambda _note: None)
    assert "ERG_UNKNOWN_COLOUR" in diagnostics.codes()
    assert list(model.get_item("R").thermal_mesh.side1_color.rgb) == list(entry(DEFAULT_COLOUR).rgb)


def test_a_colour_survives_being_written_and_read_again(tmp_path: Path) -> None:
    body = (
        "GEOMETRY R;\nR = SHELL_SCS_RECTANGLE(xmax = 1.0, ymax = 1.0, "
        'colour1 = "REDDISH_BROWN", colour2 = "ABSINTH", opt1 = Paint, opt2 = Paint);\nM = R;\n'
    )
    first = build(tmp_path, body)
    out = tmp_path / "written.erg"
    first.io.write_esatan_erg(out, name="M", on_diagnostic=lambda _note: None)

    text = out.read_text(encoding="utf-8")
    assert 'colour1 = "REDDISH_BROWN"' in text
    assert 'colour2 = "ABSINTH"' in text

    second = GeometryModel("BACK")
    second.io.read_esatan_erg(out, on_diagnostic=lambda _note: None)
    before = first.get_item("R").thermal_mesh
    after = second.get_item("R").thermal_mesh
    assert list(after.side1_color.rgb) == list(before.side1_color.rgb)
    assert list(after.side2_color.rgb) == list(before.side2_color.rgb)


def test_a_colour_the_model_invented_is_written_as_the_nearest_name(tmp_path: Path) -> None:
    """A model built in Python, not read from a file, still writes a valid name."""
    body = (
        "GEOMETRY R;\nR = SHELL_SCS_RECTANGLE(xmax = 1.0, ymax = 1.0, "
        "opt1 = Paint, opt2 = Paint);\nM = R;\n"
    )
    model = build(tmp_path, body)
    model.get_item("R").thermal_mesh.side1_color = Color(250, 5, 5)

    out = tmp_path / "written.erg"
    model.io.write_esatan_erg(out, name="M", on_diagnostic=lambda _note: None)
    assert 'colour1 = "RED"' in out.read_text(encoding="utf-8")


def test_a_surface_nobody_coloured_is_written_without_a_colour(tmp_path: Path) -> None:
    """Otherwise a round trip repaints the back of every uncoloured surface.

    A mesh always carries a colour, and a fresh one is violet on side 2 where
    the format defaults to blue-cyan.  Writing that out would change someone's
    model for no reason, so the default is left for the format to supply.
    """
    body = (
        "GEOMETRY R;\nR = SHELL_SCS_RECTANGLE(xmax = 1.0, ymax = 1.0, "
        "opt1 = Paint, opt2 = Paint);\nM = R;\n"
    )
    model = build(tmp_path, body)
    out = tmp_path / "written.erg"
    model.io.write_esatan_erg(out, name="M", on_diagnostic=lambda _note: None)

    text = out.read_text(encoding="utf-8")
    assert "colour1" not in text
    assert "colour2" not in text
    assert "VIOLET" not in text


def test_a_colour_that_was_chosen_is_written_even_next_to_defaults(tmp_path: Path) -> None:
    """Only the default is held back; one side chosen and one not still works."""
    body = (
        "GEOMETRY R;\nR = SHELL_SCS_RECTANGLE(xmax = 1.0, ymax = 1.0, "
        'colour1 = "YELLOW", opt1 = Paint, opt2 = Paint);\nM = R;\n'
    )
    model = build(tmp_path, body)
    out = tmp_path / "written.erg"
    model.io.write_esatan_erg(out, name="M", on_diagnostic=lambda _note: None)

    text = out.read_text(encoding="utf-8")
    assert 'colour1 = "YELLOW"' in text
    assert "colour2" not in text


def test_the_feature_model_writes_no_colour_diagnostic() -> None:
    """Colour used to be dropped and reported; it is now written."""
    model = GeometryModel("FEATURES_TAS")
    model.io.read_esatan_erg(FEATURES / "FEATURES_TAS.erg", on_diagnostic=lambda _note: None)

    with tempfile.TemporaryDirectory() as directory:
        out = Path(directory) / "written.erg"
        diagnostics = model.io.write_esatan_erg(
            out, name="FEATURES_TAS", on_diagnostic=lambda _note: None
        )
    assert "ERG_WRITE_NO_COLOUR" not in diagnostics.codes()
    assert not diagnostics.codes()
