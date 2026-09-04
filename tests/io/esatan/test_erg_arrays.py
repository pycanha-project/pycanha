"""Arrays: declaring one, writing an element, and reading one back.

The subscript is the interesting part. One bracketed suffix spells two
unrelated things -- the property environment in ``material[EOL] = ...`` and the
array element in ``grid[1] = ...`` -- and since an index may be a variable, the
two cannot be told apart by shape.  Only the declaration separates them, so
most of what is asserted here is that the reader asks it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pycanha_core as pcc
import pytest

from pycanha.gmm import GeometryModel

CORPUS = Path(__file__).resolve().parents[2] / "data" / "esatan" / "FEATURES.erg"

_PAINT = "OPTICAL Paint;\nDEFINE_OPTICAL (optical = Paint, ir_emiss = 0.8, solar_absorb = 0.3);\n"

_TRIANGLE = """
GEOMETRY T;
T = SHELL_TRIANGLE(point1 = {p1}, point2 = {p2}, point3 = {p3},
    nodes1 = 1, nodes2 = 1, nbase1 = 1000, ndelta1 = 1, opt1 = Paint, opt2 = Paint);
M = T;
"""


def build(tmp_path: Path, body: str, *, name: str = "M") -> tuple:
    """Write a one-off model and read it back, returning the model and diagnostics."""
    path = tmp_path / "model.erg"
    path.write_text(f"BEGIN_MODEL {name}\n{body}\nEND_MODEL\n", encoding="utf-8")
    model = GeometryModel(name)
    return model, model.io.read_esatan_erg(path)


def corners(model: GeometryModel, name: str = "T") -> list[np.ndarray]:
    """The three defining points of the named triangle.

    ``GeometryItem.primitive`` is a union of every shape, so which one arrived
    has to be pinned down before its corners can be read -- and here that is
    itself part of what is asserted: a corner taken from an array has to reach
    the same primitive a literal one would.
    """
    primitive = model.get_item(name).primitive
    assert isinstance(primitive, pcc.gmm.Triangle), name
    return [np.asarray(primitive.p1), np.asarray(primitive.p2), np.asarray(primitive.p3)]


# -- the corpus ------------------------------------------------------------


@pytest.fixture(scope="module")
def corpus() -> GeometryModel:
    """The corpus, whose array block is the one on disk that uses arrays."""
    model = GeometryModel("FEATURES")
    model.io.read_esatan_erg(CORPUS, on_diagnostic=lambda _note: None)
    return model


def test_the_corpus_takes_corners_out_of_an_array(corpus: GeometryModel) -> None:
    """Two surfaces built entirely from array elements, in a whole model.

    The tests below each isolate one thing in a model of a few lines.  This one
    is here because a subscript is resolved against everything else the file
    declares: an array named among five hundred other lines, and read after them,
    is a different question from one read three lines after it was written.
    """
    assert {item.name for item in corpus.children_recursive()} >= {"T1", "T2"}
    assert np.allclose(corners(corpus, "T1"), [[0, 0, 0], [1, 0, 0], [1, 1, 0]])
    # The third corner of T2 mixes a literal with a REAL vector element.
    assert np.allclose(corners(corpus, "T2"), [[0, 0, 0], [0, 1, 0], [0, 1, 0.75]])


def test_the_corpus_reports_nothing_about_its_arrays(corpus: GeometryModel) -> None:
    """The array block loads clean; the model's other reports are not about it."""
    model = GeometryModel("FEATURES")
    diagnostics = model.io.read_esatan_erg(CORPUS, on_diagnostic=lambda _note: None)
    about_arrays = {
        note.code
        for note in diagnostics
        if note.code.startswith("ERG_ARRAY_") or "grid" in note.message or "heights" in note.message
    }
    assert about_arrays == set()


# -- reading an element ----------------------------------------------------


def test_indices_count_from_one(tmp_path: Path) -> None:
    body = (
        _PAINT
        + """
POINT grid[3];
grid[1] = [1.0, 0.0, 0.0];
grid[2] = [0.0, 2.0, 0.0];
grid[3] = [0.0, 0.0, 3.0];
"""
        + _TRIANGLE.format(p1="grid[1]", p2="grid[2]", p3="grid[3]")
    )
    model, diagnostics = build(tmp_path, body)

    assert [d.code for d in diagnostics] == []
    assert np.allclose(corners(model), [[1, 0, 0], [0, 2, 0], [0, 0, 3]])


def test_an_index_may_be_computed(tmp_path: Path) -> None:
    body = (
        _PAINT
        + """
POINT grid[3];
grid[1] = [1.0, 0.0, 0.0];
grid[2] = [0.0, 2.0, 0.0];
grid[3] = [0.0, 0.0, 3.0];
INTEGER i;
i = 2;
"""
        + _TRIANGLE.format(p1="grid[i - 1]", p2="grid[i]", p3="grid[i + 1]")
    )
    model, diagnostics = build(tmp_path, body)

    assert [d.code for d in diagnostics] == []
    assert np.allclose(corners(model), [[1, 0, 0], [0, 2, 0], [0, 0, 3]])


def test_a_real_vector_element_is_a_number(tmp_path: Path) -> None:
    body = (
        _PAINT
        + """
REAL z[2];
z[1] = 0.25;
z[2] = 0.75;
"""
        + _TRIANGLE.format(p1="[0.0, 0.0, z[1]]", p2="[1.0, 0.0, 0.0]", p3="[0.0, 1.0, z[2]]")
    )
    model, diagnostics = build(tmp_path, body)

    assert [d.code for d in diagnostics] == []
    assert np.allclose(corners(model), [[0, 0, 0.25], [1, 0, 0], [0, 1, 0.75]])


@pytest.mark.parametrize(
    "declaration",
    [
        "REAL cuts[3] = {0.25, 0.5, 0.75};",
        "REAL cuts[3];\ncuts[1] = 0.25;\ncuts[2] = 0.5;\ncuts[3] = 0.75;",
    ],
    ids=["initialised", "filled element by element"],
)
def test_an_array_is_still_usable_whole(tmp_path: Path, declaration: str) -> None:
    """A mesh-position list is passed by name, not indexed.

    However the elements got there: an array that can be indexed still has to
    read as a whole value where one is asked for.
    """
    body = (
        _PAINT
        + declaration
        + """
GEOMETRY R;
R = SHELL_RECTANGLE(point1 = [0.0, 0.0, 0.0], point2 = [1.0, 0.0, 0.0],
    point4 = [0.0, 1.0, 0.0], meshType2 = "positions", meshPositions2 = cuts,
    nodes1 = 1, nbase1 = 1000, ndelta1 = 1, opt1 = Paint, opt2 = Paint);
M = R;
"""
    )
    model, diagnostics = build(tmp_path, body)

    assert [d.code for d in diagnostics] == []
    # meshPositions are the interior cuts, so the mesh carries them between the
    # two edges -- which only holds if the array was read as a whole value.
    mesh = model.get_item("R").thermal_mesh
    assert list(mesh.dir2_mesh) == pytest.approx([0.0, 0.25, 0.5, 0.75, 1.0])


# -- what the reader refuses or reports ------------------------------------


def test_reading_an_unassigned_element_warns_and_uses_zero(tmp_path: Path) -> None:
    """The value is what the source format would use; the warning is ours.

    An index one past the end of what was filled is otherwise invisible: the
    corner lands at the origin and the model loads.
    """
    body = (
        _PAINT
        + """
POINT grid[3];
grid[1] = [1.0, 0.0, 0.0];
grid[2] = [0.0, 2.0, 0.0];
"""
        + _TRIANGLE.format(p1="grid[1]", p2="grid[2]", p3="grid[3]")
    )
    model, diagnostics = build(tmp_path, body)

    assert "ERG_ARRAY_UNASSIGNED" in {d.code for d in diagnostics}
    assert np.allclose(corners(model)[2], [0, 0, 0])


def test_writing_outside_the_declared_size_is_an_error(tmp_path: Path) -> None:
    _, diagnostics = build(tmp_path, "POINT grid[2];\ngrid[5] = [1.0, 2.0, 3.0];\nM = 0;\n")

    assert "ERG_ARRAY_INDEX_RANGE" in {d.code for d in diagnostics}


def test_reading_outside_the_declared_size_is_reported(tmp_path: Path) -> None:
    body = (
        _PAINT
        + """
POINT grid[2];
grid[1] = [1.0, 0.0, 0.0];
grid[2] = [0.0, 2.0, 0.0];
"""
        + _TRIANGLE.format(p1="grid[1]", p2="grid[2]", p3="grid[9]")
    )
    _, diagnostics = build(tmp_path, body)

    assert "ERG_UNRESOLVED_VALUE" in {d.code for d in diagnostics}


def test_a_multi_dimensional_array_cannot_be_indexed(tmp_path: Path) -> None:
    _, diagnostics = build(tmp_path, "REAL m[2, 3];\nm[1, 2] = 4.0;\nM = 0;\n")

    assert "ERG_ARRAY_DIMENSIONS" in {d.code for d in diagnostics}


def test_a_multi_dimensional_array_survives_whole(tmp_path: Path) -> None:
    """Property tables are declared two-dimensional and passed by name.

    Refusing to index one must not cost the far commoner use of it.
    """
    body = """
REAL table[2, 2] = {10.0, 1.6, 20.0, 8.9};
BULK Steel;
DEFINE_BULK (bulk = Steel, type = "Isotropic", density = 7800.0,
    conductivity = 50.0, specific_heat_data = table);
M = 0;
"""
    _, diagnostics = build(tmp_path, body)

    assert "ERG_ARRAY_DIMENSIONS" not in {d.code for d in diagnostics}


# -- the subscript that is not an index ------------------------------------


def test_a_property_environment_is_not_an_array_write(tmp_path: Path) -> None:
    body = """
OPTICAL Kep;
Kep = [0.1, 0.1, 0.8, 0.2, 0.2, 0.6, 0.0, 0.0];
Kep[EOL] = [0.3, 0.3, 0.4, 0.4, 0.4, 0.2, 0.0, 0.0];
M = 0;
"""
    _, diagnostics = build(tmp_path, body)
    codes = {d.code for d in diagnostics}

    assert "ERG_PROPERTY_ENVIRONMENT" in codes
    assert "ERG_ARRAY_INDEX_RANGE" not in codes
    assert "ERG_ARRAY_DIMENSIONS" not in codes


def test_an_array_write_is_not_a_property_environment(tmp_path: Path) -> None:
    """The mirror of the test above, in one model that does both."""
    body = (
        _PAINT
        + """
OPTICAL Kep;
Kep = [0.1, 0.1, 0.8, 0.2, 0.2, 0.6, 0.0, 0.0];
Kep[EOL] = [0.3, 0.3, 0.4, 0.4, 0.4, 0.2, 0.0, 0.0];
POINT grid[1];
grid[1] = [7.0, 8.0, 9.0];
"""
        + _TRIANGLE.format(p1="grid[1]", p2="[1.0, 0.0, 0.0]", p3="[0.0, 1.0, 0.0]")
    )
    model, diagnostics = build(tmp_path, body)

    environments = [d for d in diagnostics if d.code == "ERG_PROPERTY_ENVIRONMENT"]
    assert len(environments) == 1
    assert "Kep" in environments[0].message
    assert np.allclose(corners(model)[0], [7, 8, 9])


@pytest.mark.parametrize("subscript", ["[1]", "[i]", "[i + 1]"])
def test_an_undeclared_name_keeps_the_environment_reading(tmp_path: Path, subscript: str) -> None:
    """A subscript on something never declared an array is not an element write."""
    body = f"INTEGER i;\ni = 1;\nSomething{subscript} = 3.0;\nM = 0;\n"
    _, diagnostics = build(tmp_path, body)

    assert "ERG_ARRAY_INDEX_RANGE" not in {d.code for d in diagnostics}
