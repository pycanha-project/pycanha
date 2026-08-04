"""Grammar-level tests for the ESATAN geometry language.

These exercise the parser alone -- no geometry is built -- and concentrate on
the lexical traps, because those are what a whole-file parse gets wrong
silently: an unterminated string swallows the rest of the model, and an escaped
backslash quietly corrupts every Windows path in the file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pycanha.io.esatan.errors import EsatanParseError
from pycanha.io.esatan.lang import ast, parse, parse_file

if TYPE_CHECKING:
    from pathlib import Path


def test_model_header_and_markers() -> None:
    parsed = parse("BEGIN_MODEL SAT WORKBENCH_V1 ESARAD_GENERATED\nEND_MODEL\n")
    assert parsed.name == "SAT"
    assert parsed.markers == ("WORKBENCH_V1", "ESARAD_GENERATED")


def test_declaration_and_assignment() -> None:
    parsed = parse("BEGIN_MODEL M\nGEOMETRY D;\nD = SHELL_SCS_DISC(rmax = 0.5);\nEND_MODEL\n")
    declaration, assignment = parsed.statements
    assert isinstance(declaration, ast.Declaration)
    assert (declaration.kind, declaration.name) == ("GEOMETRY", "D")
    assert isinstance(assignment, ast.Assignment)
    assert isinstance(assignment.value, ast.Call)
    assert assignment.value.name == "SHELL_SCS_DISC"
    assert assignment.value.args["rmax"] == ast.Num(0.5, line=3, end_line=3, source="<string>")


def test_attribute_names_are_case_insensitive() -> None:
    """The same attribute appears lower-cased in constructors and upper in overrides."""
    parsed = parse("BEGIN_MODEL M\nX = F(NBASE1 = 10, nbase2 = 20);\nEND_MODEL\n")
    assignment = parsed.statements[0]
    assert isinstance(assignment, ast.Assignment)
    assert isinstance(assignment.value, ast.Call)
    assert set(assignment.value.args) == {"nbase1", "nbase2"}


def test_dotted_override_keeps_its_attribute() -> None:
    parsed = parse("BEGIN_MODEL M\nPLATE.NBASE1 = 101620;\nEND_MODEL\n")
    assignment = parsed.statements[0]
    assert isinstance(assignment, ast.Assignment)
    assert assignment.target.name == "PLATE"
    assert assignment.target.attribute == "nbase1"


def test_several_statements_on_one_line() -> None:
    """Statements are semicolon-delimited, not line-delimited."""
    parsed = parse("BEGIN_MODEL M\nA.NBASE1 = 1; A.NBASE2 = 2;\nEND_MODEL\n")
    assert len(parsed.statements) == 2
    assert all(statement.line == 2 for statement in parsed.statements)


def test_backslashes_in_strings_are_literal() -> None:
    r"""A Windows path must survive: ``\u`` is not an escape in this language."""
    parsed = parse('BEGIN_MODEL M\nINCLUDE "C:\\usr\\models\\bound.gmm"\nEND_MODEL\n')
    include = parsed.statements[0]
    assert isinstance(include, ast.Include)
    assert include.path == "C:\\usr\\models\\bound.gmm"


def test_multiline_string_holds_code_without_ending_the_statement() -> None:
    """Model files embed whole routines inside one string, statement-looking lines and all."""
    text = (
        "BEGIN_MODEL M\n"
        "GENERATE_TEMPLATE (\n"
        '    execution_block = "\n'
        "      CALL SOLCYC(\\'SLCRNC\\',0.05D0,500)\n"
        "      X = 1;\n"
        '");\n'
        "END_MODEL\n"
    )
    parsed = parse(text)
    call = parsed.statements[0]
    assert isinstance(call, ast.CallStmt)
    assert call.name == "GENERATE_TEMPLATE"
    block = call.args["execution_block"]
    assert isinstance(block, ast.Str)
    assert "CALL SOLCYC" in block.value


def test_block_comments_are_ignored_including_hash_banners() -> None:
    text = "BEGIN_MODEL M\n/*#*#*#*#*#*#*#*#*/\n/* multi\n   line */\nGEOMETRY D;\nEND_MODEL\n"
    parsed = parse(text)
    assert len(parsed.statements) == 1
    assert parsed.statements[0].line == 5


def test_geometry_composition_is_left_associated() -> None:
    """``A - B - C`` must read as A cut by B, then by C."""
    parsed = parse("BEGIN_MODEL M\nX = A - B - C;\nEND_MODEL\n")
    assignment = parsed.statements[0]
    assert isinstance(assignment, ast.Assignment)
    outer = assignment.value
    assert isinstance(outer, ast.BinOp)
    assert outer.op == "-"
    assert isinstance(outer.right, ast.Ref)
    assert outer.right.name == "C"
    assert isinstance(outer.left, ast.BinOp)


def test_negative_numbers_and_exponents() -> None:
    parsed = parse("BEGIN_MODEL M\nP = [-90.0, 2.0e-03, 6.958E8];\nEND_MODEL\n")
    assignment = parsed.statements[0]
    assert isinstance(assignment, ast.Assignment)
    vector = assignment.value
    assert isinstance(vector, ast.Vector)
    first, second, third = vector.items
    assert isinstance(first, ast.UnaryOp)
    assert first.op == "-"
    assert isinstance(second, ast.Num)
    assert second.value == pytest.approx(2.0e-03)
    assert isinstance(third, ast.Num)
    assert third.value == pytest.approx(6.958e8)


def test_property_environment_suffix() -> None:
    parsed = parse("BEGIN_MODEL M\nPaint [EOL] = [0.7, 0.3];\nEND_MODEL\n")
    assignment = parsed.statements[0]
    assert isinstance(assignment, ast.Assignment)
    assert assignment.target.environment == "EOL"


def test_control_flow_is_accepted() -> None:
    text = (
        "BEGIN_MODEL M\n"
        "IF (flag == 0) THEN\n"
        "FOR (i = 1; i <= 3; i = EVAL(i + 1))\n"
        "CALCULATE (pos_index = i);\n"
        "END_FOR\n"
        "ELSE\n"
        "X = 1;\n"
        "END_IF\n"
        "END_MODEL\n"
    )
    parsed = parse(text)
    block = parsed.statements[0]
    assert isinstance(block, ast.IfBlock)
    assert len(block.body) == 1
    assert isinstance(block.body[0], ast.ForBlock)
    assert len(block.orelse) == 1


def test_keywords_do_not_swallow_longer_identifiers() -> None:
    """``DEFINE_OPTICAL`` starts with ``DEFINE`` but is an ordinary procedure name."""
    parsed = parse("BEGIN_MODEL M\nDEFINE_OPTICAL (optical = Low_e);\nEND_MODEL\n")
    call = parsed.statements[0]
    assert isinstance(call, ast.CallStmt)
    assert call.name == "DEFINE_OPTICAL"


def test_bare_fragment_without_a_header() -> None:
    """An included fragment carries no model header of its own."""
    parsed = parse("GEOMETRY D;\nD = SHELL_TRIANGLE(point1 = [0, 0, 0]);\n")
    assert parsed.name == ""
    assert len(parsed.statements) == 2


def test_syntax_error_reports_the_position() -> None:
    with pytest.raises(EsatanParseError) as excinfo:
        parse(
            "BEGIN_MODEL M\nGEOMETRY D;\nD = SHELL_SCS_DISC(rmax = );\nEND_MODEL\n",
            source_name="m.erg",
        )
    assert "m.erg:3" in str(excinfo.value)


def test_include_is_spliced_keeping_each_file_line_numbers(tmp_path: Path) -> None:
    fragment = tmp_path / "part.gmm"
    fragment.write_text("\n\nGEOMETRY INNER;\n", encoding="utf-8")
    main = tmp_path / "main.erg"
    main.write_text(
        f'BEGIN_MODEL M\nGEOMETRY OUTER;\nINCLUDE "{fragment}"\nEND_MODEL\n', encoding="utf-8"
    )

    parsed = parse_file(main)
    kinds = [type(statement).__name__ for statement in parsed.statements]
    assert kinds == ["Declaration", "Include", "Declaration"]
    outer, _, inner = parsed.statements
    assert (outer.line, outer.source) == (2, str(main))
    assert (inner.line, inner.source) == (3, str(fragment))
