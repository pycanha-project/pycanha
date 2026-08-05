"""The published list of diagnostic codes has to match the reader's own.

A code is part of the interface -- callers branch on it -- so a code that the
reader emits and the documentation does not mention is an undocumented part of
that interface, and a code the documentation promises and the reader never
emits is a promise nothing keeps.  Both drift silently; this notices.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
READER = ROOT / "src" / "pycanha" / "io" / "steptas"
PAGE = ROOT / "doc" / "user_guide" / "steptas_geometry.rst"

CODE = re.compile(r"TAS_[A-Z_]+")


def codes_in_source() -> set[str]:
    """Every code the reader can report, as a string literal in its own source."""
    found: set[str] = set()
    for module in READER.glob("*.py"):
        text = module.read_text(encoding="utf-8")
        found.update(re.findall(r'"(TAS_[A-Z_]+)"', text))
    return found


def test_every_code_the_reader_emits_is_documented() -> None:
    documented = set(CODE.findall(PAGE.read_text(encoding="utf-8")))
    assert codes_in_source() - documented == set()


def test_no_documented_code_has_gone_away() -> None:
    documented = set(CODE.findall(PAGE.read_text(encoding="utf-8")))
    assert documented - codes_in_source() == set()
