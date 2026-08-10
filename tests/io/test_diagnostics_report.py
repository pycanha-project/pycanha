"""The diagnostics report: one summary line in the log, the detail in a file.

The collector's own behaviour -- codes, counts, strict mode -- is exercised all
over ``tests/io/esatan``.  What is covered here is the reporting added in 0.19:
where the file goes, what it says, what severity the summary line takes, and
that neither of them is allowed to abort a read.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

import pycanha as pc
from pycanha.io.diagnostics import DiagnosticCollector, Severity

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def log_dir(tmp_path: Path) -> Iterator[Path]:
    """Point the log directory at a tmp_path, with file output on."""
    directory = tmp_path / "logs"
    pc.log.set_log_directory(str(directory))
    pc.log.set_file_output(True)
    yield directory
    pc.log.set_file_output(False)
    pc.log.set_log_directory("logs")


def collector() -> DiagnosticCollector:
    return DiagnosticCollector(source="model.erg", operation="Read ESATAN geometry")


# -- the summary line -------------------------------------------------------


def test_a_clean_operation_says_no_issues() -> None:
    assert collector().headline() == "Read ESATAN geometry model.erg -- no issues"


def test_the_headline_counts_each_severity_separately() -> None:
    diagnostics = collector()
    diagnostics.warning("A", "one")
    diagnostics.warning("A", "two")
    diagnostics.warning("B", "three")
    diagnostics.unsupported("C", "four")
    assert (
        diagnostics.headline()
        == "Read ESATAN geometry model.erg -- 3 warnings, 1 unsupported construct"
    )


def test_the_headline_is_singular_for_one() -> None:
    diagnostics = collector()
    diagnostics.warning("A", "one")
    assert diagnostics.headline().endswith("-- 1 warning")


@pytest.mark.parametrize(
    ("add", "expected"),
    [
        (None, pc.LogLevel.INFO),
        ("info", pc.LogLevel.INFO),
        ("warning", pc.LogLevel.WARN),
        ("unsupported", pc.LogLevel.WARN),
        ("error", pc.LogLevel.ERROR),
    ],
)
def test_the_summary_takes_the_severity_of_the_worst_diagnostic(
    add: str | None, expected: pc.LogLevel
) -> None:
    diagnostics = collector()
    if add is not None:
        getattr(diagnostics, add)("CODE", "something")
    pc.log.clear_records()
    diagnostics.report()

    (record,) = pc.log.records(1)
    assert record.level is expected
    assert record.origin == "pycanha"


def test_worst_severity_orders_by_seriousness_not_alphabetically() -> None:
    diagnostics = collector()
    diagnostics.error("E", "wrong")
    diagnostics.info("I", "noted")
    # "error" < "info" as text, which is exactly the trap.
    assert diagnostics.worst_severity() is Severity.ERROR


# -- the file ---------------------------------------------------------------


def test_a_file_is_written_even_for_a_clean_operation(log_dir: Path) -> None:
    """Predictable existence: its presence is not itself the signal."""
    written = collector().report()
    assert written is not None
    assert written.parent == log_dir
    assert written.name.startswith("model-")
    assert written.name.endswith(".diag.txt")
    assert "no diagnostics" in written.read_text(encoding="utf-8")


def test_the_file_holds_the_grouped_summary_and_every_diagnostic(log_dir: Path) -> None:
    diagnostics = collector()
    for index in range(4):
        diagnostics.warning("ERG_DROPPED", f"dropped attribute {index}")
    written = diagnostics.report()

    assert written is not None
    text = written.read_text(encoding="utf-8")
    # Deduplicated in the summary, so a 100k-line model is one line here...
    assert "warning: [ERG_DROPPED] x4" in text
    # ...and complete further down, which is what the file is for.
    assert text.count("dropped attribute") == 4 + 3  # 3 examples in the summary
    assert log_dir in written.parents or written.parent == log_dir


def test_the_summary_line_names_the_file(log_dir: Path) -> None:
    diagnostics = collector()
    diagnostics.warning("A", "one")
    pc.log.clear_records()
    written = diagnostics.report()

    assert written is not None
    (record,) = pc.log.records(1)
    assert str(written) in record.message


def test_file_output_off_writes_nothing_but_still_records(tmp_path: Path) -> None:
    pc.log.set_log_directory(str(tmp_path / "logs"))
    try:
        pc.log.set_file_output(False)
        diagnostics = collector()
        diagnostics.warning("A", "one")
        pc.log.clear_records()

        assert diagnostics.report() is None
        assert not (tmp_path / "logs").exists()
        # The console and the buffer still get the summary, which is what makes
        # this the mode a notebook runs in.
        (record,) = pc.log.records(1)
        assert "1 warning" in record.message
        assert "diagnostics:" not in record.message
    finally:
        pc.log.set_log_directory("logs")


def test_an_unwritable_directory_does_not_abort_the_operation(tmp_path: Path) -> None:
    """A read-only log directory costs a warning, not the analysis."""
    blocker = tmp_path / "logs"
    # A regular file where the directory should be: mkdir cannot proceed, on
    # every platform, without depending on permission semantics.
    blocker.write_text("not a directory", encoding="utf-8")
    pc.log.set_log_directory(str(blocker))
    pc.log.set_file_output(True)
    try:
        diagnostics = collector()
        diagnostics.warning("A", "one")
        pc.log.clear_records()

        assert diagnostics.report() is None
        messages = [record.message for record in pc.log.records(5)]
        assert any("could not write diagnostics" in message for message in messages)
        assert any("1 warning" in message for message in messages)
    finally:
        pc.log.set_file_output(False)
        pc.log.set_log_directory("logs")


# -- the readers call it ----------------------------------------------------


def test_reading_erg_geometry_reports(log_dir: Path, tmp_path: Path) -> None:
    source = tmp_path / "tiny.erg"
    source.write_text(
        "BEGIN_MODEL TINY\n"
        "GEOMETRY R;\n"
        "R = SHELL_RECTANGLE(point1 = [0, 0, 0], point2 = [2, 0, 0], point4 = [0, 3, 0]);\n"
        "END_MODEL\n",
        encoding="utf-8",
    )
    model = pc.gmm.GeometryModel("TINY")
    model.io.read_esatan_erg(source)

    written = list(log_dir.glob("tiny-*.diag.txt"))
    assert len(written) == 1
    assert "Read ESATAN geometry" in written[0].read_text(encoding="utf-8")
