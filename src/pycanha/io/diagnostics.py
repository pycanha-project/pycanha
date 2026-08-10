"""Diagnostics produced while reading or writing a model file.

Exchanging a model is lossy by nature: every format carries modelling concepts
some other one has no place for.  Rather than failing, a reader converts what
it can and reports the rest, one :class:`Diagnostic` per lost or altered
construct.

Two properties matter for callers:

* the ``code`` is stable and greppable, and is what tests assert on -- message
  wording is free to change;
* repetitive diagnostics are counted rather than repeated, so a 100k-line model
  that drops one unsupported attribute per primitive produces a single summary
  line instead of thousands.

Diagnostics are not log records.  Each is kept in the collector the operation
returns, and the whole set is rendered to its own file beside the log; the log
itself carries a single line naming that file, at the severity of the worst
diagnostic in it.  This is the compiler model -- a short summary where you are
looking, the full report where you can go read it -- and it is what makes a
100k-line model tolerable.  :func:`pycanha.log.set_file_output` turns the files
off along with the log file.
"""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from .. import log
from .errors import ModelReadError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

__all__ = ["Diagnostic", "DiagnosticCollector", "Severity"]

#: How many distinct examples of a repeated diagnostic the summary keeps.
_MAX_EXAMPLES = 3


class Severity(StrEnum):
    """How badly a construct fared on the way in."""

    INFO = "info"
    """Converted faithfully, but in a way worth knowing about."""

    WARNING = "warning"
    """An attribute was dropped; the geometry itself is unaffected."""

    UNSUPPORTED = "unsupported"
    """A whole construct was skipped because pycanha cannot represent it."""

    ERROR = "error"
    """The resulting model is likely wrong, not merely incomplete."""


#: Severities from least to most serious. A :class:`StrEnum` compares as text,
#: which orders them alphabetically -- ``error`` before ``info`` -- so "the
#: worst one" needs this rather than :func:`max`.
_SEVERITY_ORDER = (Severity.INFO, Severity.WARNING, Severity.UNSUPPORTED, Severity.ERROR)

#: The log level a summary line takes, given the worst severity in it. Only
#: ERROR says the result is wrong; everything else at most says something was
#: dropped, which is what WARN means, and a clean read is one INFO line.
_SUMMARY_LEVEL = {
    Severity.INFO: log.LogLevel.INFO,
    Severity.WARNING: log.LogLevel.WARN,
    Severity.UNSUPPORTED: log.LogLevel.WARN,
    Severity.ERROR: log.LogLevel.ERROR,
}

#: Singular / plural noun for each severity, used to phrase the summary line.
_SEVERITY_NOUNS = {
    Severity.INFO: ("note", "notes"),
    Severity.WARNING: ("warning", "warnings"),
    Severity.UNSUPPORTED: ("unsupported construct", "unsupported constructs"),
    Severity.ERROR: ("error", "errors"),
}


@dataclass(frozen=True)
class Diagnostic:
    """One reported deviation between the source model and the built one."""

    severity: Severity
    code: str
    message: str
    source: str = ""
    line: int = 0

    def __str__(self) -> str:
        where = f"{self.source}:{self.line}: " if self.source else ""
        return f"{where}{self.severity.value}: [{self.code}] {self.message}"


class DiagnosticCollector:
    """Collects diagnostics, optionally raising on the first serious one.

    With ``strict``, the first ``UNSUPPORTED`` or ``ERROR`` raises
    :attr:`error_type` -- useful in tests and for callers who would rather not
    discover a silently reduced model later.  ``on_diagnostic`` receives every
    diagnostic as it is produced; without it, each one is recorded at DEBUG,
    where it costs nothing in a released wheel and stays out of the way of the
    one summary line :meth:`report` writes.

    ``operation`` names what produced these, as a verb phrase ("Read ESATAN
    geometry"); it is what the summary line and the diagnostics file are headed
    with.

    Each format subclasses this and overrides :attr:`error_type` so that a
    caller can catch that one format's error, or :class:`ModelReadError` for
    any of them.
    """

    error_type: type[Exception] = ModelReadError

    def __init__(
        self,
        *,
        source: str = "",
        strict: bool = False,
        operation: str = "",
        on_diagnostic: Callable[[Diagnostic], None] | None = None,
    ) -> None:
        self.source = source
        self.strict = strict
        self.operation = operation
        self._on_diagnostic = on_diagnostic
        self._items: list[Diagnostic] = []

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[Diagnostic]:
        return iter(self._items)

    @property
    def items(self) -> Sequence[Diagnostic]:
        """Every diagnostic collected so far, in the order it was produced."""
        return tuple(self._items)

    def add(
        self,
        severity: Severity,
        code: str,
        message: str,
        *,
        line: int = 0,
        source: str | None = None,
    ) -> Diagnostic:
        """Record one diagnostic and return it."""
        diagnostic = Diagnostic(
            severity=severity,
            code=code,
            message=message,
            source=self.source if source is None else source,
            line=line,
        )
        self._items.append(diagnostic)
        if self._on_diagnostic is not None:
            self._on_diagnostic(diagnostic)
        else:
            self._log(diagnostic)
        if self.strict and severity in (Severity.UNSUPPORTED, Severity.ERROR):
            raise self.error_type(str(diagnostic))
        return diagnostic

    def info(self, code: str, message: str, *, line: int = 0) -> Diagnostic:
        """Record an :attr:`Severity.INFO` diagnostic."""
        return self.add(Severity.INFO, code, message, line=line)

    def warning(self, code: str, message: str, *, line: int = 0) -> Diagnostic:
        """Record a :attr:`Severity.WARNING` diagnostic."""
        return self.add(Severity.WARNING, code, message, line=line)

    def unsupported(self, code: str, message: str, *, line: int = 0) -> Diagnostic:
        """Record an :attr:`Severity.UNSUPPORTED` diagnostic."""
        return self.add(Severity.UNSUPPORTED, code, message, line=line)

    def error(self, code: str, message: str, *, line: int = 0) -> Diagnostic:
        """Record an :attr:`Severity.ERROR` diagnostic."""
        return self.add(Severity.ERROR, code, message, line=line)

    def codes(self) -> set[str]:
        """The distinct codes collected, which is what most tests assert on."""
        return {item.code for item in self._items}

    def counts(self) -> dict[str, int]:
        """How many times each code was reported."""
        return dict(Counter(item.code for item in self._items))

    def worst_severity(self) -> Severity:
        """The most serious severity collected, or ``INFO`` if there are none."""
        worst = Severity.INFO
        for item in self._items:
            if _SEVERITY_ORDER.index(item.severity) > _SEVERITY_ORDER.index(worst):
                worst = item.severity
        return worst

    def summary(self) -> str:
        """A short report grouping the diagnostics by code.

        A model that drops the same attribute on every primitive should read as
        one line with a count, not as thousands of identical lines.
        """
        if not self._items:
            return "no diagnostics"
        by_code: dict[str, list[Diagnostic]] = {}
        for item in self._items:
            by_code.setdefault(item.code, []).append(item)
        lines = []
        for code, group in by_code.items():
            head = f"{group[0].severity.value}: [{code}] x{len(group)}"
            examples = [d.message for d in group[:_MAX_EXAMPLES]]
            lines.append(head + "".join(f"\n    {example}" for example in dict.fromkeys(examples)))
        return "\n".join(lines)

    def headline(self) -> str:
        """One line naming the operation and what it cost, without the file.

        Reads ``Read ESATAN geometry model.erg -- no issues`` when nothing was
        collected, and ``... -- 3 warnings, 1 unsupported construct`` when
        something was.
        """
        what = " ".join(part for part in (self.operation, self.source) if part)
        by_severity = Counter(item.severity for item in self._items)
        parts = [
            f"{count} {_SEVERITY_NOUNS[severity][0 if count == 1 else 1]}"
            for severity in _SEVERITY_ORDER
            if (count := by_severity[severity])
        ]
        return f"{what or 'operation'} -- {', '.join(parts) if parts else 'no issues'}"

    def render(self) -> str:
        """The full report: the grouped summary, then every diagnostic in order.

        Self-contained, because it is what gets written to disk and read later
        without the run that produced it.
        """
        when = datetime.now(UTC).isoformat(timespec="seconds")
        header = [
            self.headline(),
            f"generated: {when}  pid: {os.getpid()}",
            "",
            "summary",
            "=======",
            self.summary(),
        ]
        if not self._items:
            return "\n".join(header) + "\n"
        detail = ["", "all diagnostics", "===============", *(str(item) for item in self._items)]
        return "\n".join(header + detail) + "\n"

    def report(self) -> Path | None:
        """Write the diagnostics file and record the one line that points at it.

        Called once by whatever ran the operation, on every operation including
        a clean one, so that the file's existence is predictable rather than a
        signal in itself.  Returns where it was written, or ``None`` when file
        output is off -- in which case the summary line still goes to the log
        and the diagnostics are still on this object.

        Failing to write is never fatal: a thermal analysis must not abort
        because a directory is read-only.  The summary line degrades to saying
        so and the run continues.
        """
        path = self._write_file()
        level = _SUMMARY_LEVEL[self.worst_severity()]
        where = f"; diagnostics: {path}" if path is not None else ""
        log.log(level, self.headline() + where)
        return path

    def _write_file(self) -> Path | None:
        if not log.file_output():
            return None
        directory = Path(log.log_directory())
        # Named after the source and stamped with the time and pid: concurrent
        # runs share one log directory, and one process may read the same file
        # more than once in a session.
        stem = Path(self.source).stem if self.source else "diagnostics"
        when = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        target = directory / f"{stem}-{when}-p{os.getpid()}.diag.txt"
        try:
            directory.mkdir(parents=True, exist_ok=True)
            target.write_text(self.render(), encoding="utf-8")
        except OSError as exc:
            log.warning(f"could not write diagnostics to {target}: {exc}")
            return None
        return target

    def _log(self, diagnostic: Diagnostic) -> None:
        # Per-diagnostic, so DEBUG: one line each is exactly the flood that the
        # summary line plus the diagnostics file exist to replace, and DEBUG is
        # compiled out of released wheels so a large model pays nothing for it.
        log.debug(str(diagnostic))
