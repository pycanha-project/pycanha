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
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import pycanha_core as pcc

from .errors import ModelReadError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from pycanha_core import Logger

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
    diagnostic as it is produced; without it, each one is logged.

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
        on_diagnostic: Callable[[Diagnostic], None] | None = None,
    ) -> None:
        self.source = source
        self.strict = strict
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

    @staticmethod
    def _logger() -> Logger:
        """The shared pycanha-core Python logger."""
        return pcc.get_python_logger()

    def _log(self, diagnostic: Diagnostic) -> None:
        logger = self._logger()
        text = str(diagnostic)
        if diagnostic.severity is Severity.ERROR:
            logger.error(text)
        elif diagnostic.severity is Severity.INFO:
            logger.info(text)
        else:
            logger.warn(text)
