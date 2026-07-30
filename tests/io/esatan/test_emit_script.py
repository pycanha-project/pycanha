"""End-to-end test: parse a .d file and emit the <basename>.py script."""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

import pycanha as pc
from pycanha.io.esatan_reader import ESATANReader

FIXTURE = Path(__file__).resolve().parents[2] / "data" / "esatan" / "DISC" / "DISCTR_TRANSIENT.d"


def _parse_with_emit(tmp_path: Path) -> Path:
    work = tmp_path / FIXTURE.name
    shutil.copy(FIXTURE, work)
    tmm = pc.tmm.ThermalMathematicalModel("DISCTR_TRANSIENT")
    reader = ESATANReader(tmm)
    reader.parse_analysis_file(work, emit_python_script=True)
    return work.with_suffix(".py")


def test_script_emitted_next_to_source(tmp_path: Path) -> None:
    generated = _parse_with_emit(tmp_path)
    assert generated.exists()
    assert generated.name == "DISCTR_TRANSIENT.py"


def test_generated_script_is_valid_python(tmp_path: Path) -> None:
    generated = _parse_with_emit(tmp_path)
    tree = ast.parse(generated.read_text(encoding="utf-8"))
    funcs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert {"initial", "execution", "variables1", "variables2"} <= funcs


def test_initial_block_translates_heater_assignments(tmp_path: Path) -> None:
    text = _parse_with_emit(tmp_path).read_text(encoding="utf-8")
    assert "model.nodes.set_qi(1060, 1.0)" in text
    assert "model.nodes.set_T(2000, -10.0)" in text


def test_execution_block_comments_call_and_keeps_globals(tmp_path: Path) -> None:
    text = _parse_with_emit(tmp_path).read_text(encoding="utf-8")
    assert "# CALL SLCRNC" in text
    assert "STEFAN = 5.670374419184429E-8" in text


def test_explicit_output_path(tmp_path: Path) -> None:
    work = tmp_path / FIXTURE.name
    shutil.copy(FIXTURE, work)
    target = tmp_path / "custom_name.py"
    tmm = pc.tmm.ThermalMathematicalModel("X")
    reader = ESATANReader(tmm)
    reader.parse_analysis_file(work, emit_python_script=True, python_script_path=target)
    assert target.exists()
    ast.parse(target.read_text(encoding="utf-8"))


def test_no_script_emitted_by_default(tmp_path: Path) -> None:
    work = tmp_path / FIXTURE.name
    shutil.copy(FIXTURE, work)
    tmm = pc.tmm.ThermalMathematicalModel("X")
    reader = ESATANReader(tmm)
    reader.parse_analysis_file(work)
    assert not work.with_suffix(".py").exists()
