"""What pycanha records, what it displays, and how to emit from Python.

pycanha has one logging system, owned by the C++ core, and this module is the
whole of it as seen from Python.  There is no logger hierarchy and no
per-module level: a single scale applies to the entire project, and each record
carries an ``origin`` (``pycanha-core`` for one made inside the C++ library,
``pycanha`` for one made here) which is the only axis distinguishing them.

Two thresholds, not one
=======================

:func:`set_record_level` sets what is produced at all, and therefore what the
log file and the in-memory buffer keep.  :func:`set_display_level` sets what
additionally reaches the console.  The split is what lets a run keep a complete
trail while staying quiet unless something is wrong, which is the default:
INFO is recorded, WARN and above are shown.

    >>> import pycanha as pc
    >>> pc.log.set_display_level(pc.LogLevel.OFF)   # silence the console
    >>> pc.log.set_record_level(pc.LogLevel.INFO)   # keep recording to file

Neither threshold can go below :func:`compiled_level_floor`.  Released wheels
are compiled with a floor of INFO -- DEBUG and TRACE records are not in the
binary at all, so no runtime setting can bring them back.

Integration with stdlib ``logging``
===================================

Every record also reaches the stdlib ``logging`` logger named ``pycanha``, with
no setup call: the bridge is installed when ``pycanha_core`` is imported.  It
carries a ``NullHandler``, so nothing is printed twice -- the console belongs to
the C++ side.  Adding a handler of your own asks for a second destination::

    import logging
    logging.getLogger("pycanha").addHandler(logging.FileHandler("run.log"))

Delivery to ``logging`` is deferred: while a C++ call is running, no Python code
runs on that thread, so records are handed over on the way out of the operations
that do real work (solve, read, build), at :func:`flush`, and at interpreter
exit.  Console output is live regardless, which is the point of leaving display
to the C++ sink.  :func:`records` looks at the buffer without consuming it,
which is how a notebook inspects a run with file output turned off.

Writing to disk
===============

Records go to ``<log_directory>/YYYY-MM-DD.log``, appended to, created on the
first record rather than at import, with the directory resolved against the
current working directory.  :func:`set_file_output` is a master switch over all
of it -- the log file *and* the diagnostics files that
:mod:`pycanha.io.diagnostics` writes beside it.  With it off nothing touches the
filesystem while the console and the buffer keep working.
"""

from __future__ import annotations

import pycanha_core as pcc

# Reached as an attribute rather than imported by path: the compiled extension
# registers its submodules under its own dotted name and then replaces
# sys.modules["pycanha_core"] with itself, so `import pycanha_core.log` finds
# nothing. The type stubs declare the submodule, so this stays fully typed.
_core = pcc.log

LogDrain = _core.LogDrain
LogLevel = _core.LogLevel
LogRecord = _core.LogRecord

buffer_capacity = _core.buffer_capacity
clear_records = _core.clear_records
compiled_level_floor = _core.compiled_level_floor
current_log_file = _core.current_log_file
dev_mode = _core.dev_mode
display_level = _core.display_level
drain = _core.drain
file_output = _core.file_output
flush = _core.flush
log_directory = _core.log_directory
record_level = _core.record_level
records = _core.records
set_buffer_capacity = _core.set_buffer_capacity
set_display_level = _core.set_display_level
set_file_output = _core.set_file_output
set_log_directory = _core.set_log_directory

__all__ = [
    "LogDrain",
    "LogLevel",
    "LogRecord",
    "buffer_capacity",
    "clear_records",
    "compiled_level_floor",
    "current_log_file",
    "debug",
    "dev_mode",
    "display_level",
    "drain",
    "error",
    "file_output",
    "flush",
    "info",
    "log",
    "log_directory",
    "record_level",
    "records",
    "refresh_thresholds",
    "set_buffer_capacity",
    "set_display_level",
    "set_file_output",
    "set_log_directory",
    "set_record_level",
    "should_log",
    "trace",
    "warning",
]


class _Cached:
    """The record threshold, mirrored on this side of the language boundary.

    A record below it is dropped by the core anyway, so comparing here lets a
    filtered-out call return without crossing at all.  Measured on this
    project: the comparison costs ~14 ns, asking the core the same question
    ~53 ns, and actually emitting a record ~128 ns.

    Held as a class attribute rather than a module-level name so that
    refreshing it is a plain assignment instead of a ``global`` statement.
    """

    record_threshold: int = record_level().value


def refresh_thresholds() -> None:
    """Re-read the record threshold from the core.

    Only needed after setting it through :mod:`pycanha_core.log` directly;
    :func:`set_record_level` already does this.
    """
    _Cached.record_threshold = record_level().value


def set_record_level(level: LogLevel) -> None:
    """Set what is produced at all, and so what the file and buffer keep.

    Raises :exc:`ValueError` for a level below :func:`compiled_level_floor`.
    """
    _core.set_record_level(level)
    refresh_thresholds()


def should_log(level: LogLevel) -> bool:
    """Whether a record at ``level`` would be kept by anything."""
    return level.value >= _Cached.record_threshold


def log(level: LogLevel, message: str) -> None:
    """Emit ``message`` at ``level``, recorded with origin ``pycanha``.

    The message is expected to be formatted already.  Records made here travel
    Python -> C++ -> buffer -> Python before they reach stdlib ``logging``;
    that is deliberate rather than a loop, and is what puts both origins in one
    file, on one clock, in the order they actually happened.  Each record is
    delivered to ``logging`` exactly once.
    """
    if level.value < _Cached.record_threshold:
        return
    _core.write(level, message)


def trace(message: str) -> None:
    """Record per-iteration or per-element detail."""
    log(LogLevel.TRACE, message)


def debug(message: str) -> None:
    """Record per-object bookkeeping."""
    log(LogLevel.DEBUG, message)


def info(message: str) -> None:
    """Record one line for a user-initiated top-level operation."""
    log(LogLevel.INFO, message)


def warning(message: str) -> None:
    """Record that the operation succeeded but dropped or assumed something."""
    log(LogLevel.WARN, message)


def error(message: str) -> None:
    """Record that the operation failed, or that its result is wrong."""
    log(LogLevel.ERROR, message)
