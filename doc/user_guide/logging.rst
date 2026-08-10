Logging
=======

pycanha has one logging system. It is owned by the C++ core, and
:mod:`pycanha.log` is the whole of it as seen from Python -- there is no logger
hierarchy and no per-module level. Each record carries an ``origin``,
``pycanha-core`` for one made inside the C++ library and ``pycanha`` for one
made in the Python layer, and that is the only axis separating them. Both land
in the same file, on the same clock, in the order they happened.

The default is quiet: a correct run prints nothing.

What is recorded, and what is shown
-----------------------------------

Two thresholds, not one:

.. code-block:: python

   import pycanha as pc

   pc.log.set_record_level(pc.LogLevel.INFO)   # what is produced at all
   pc.log.set_display_level(pc.LogLevel.WARN)  # what also reaches the console

The **record** threshold decides what exists: what the log file keeps and what
the in-memory buffer holds. The **display** threshold decides what you see. So
the default records a full INFO trail of every read, build and solve while
showing you nothing unless something went wrong. ``LogLevel.OFF`` silences the
console entirely.

The levels mean:

``ERROR``
   The operation failed, or its result is wrong. You have to act.

``WARN``
   It succeeded, but something was dropped or assumed. This includes the case
   where a call returns nothing and quietly declines to do what was asked --
   the record is then your only signal.

``INFO``
   One line per operation you started. Recorded, not shown.

``DEBUG``
   Per-object bookkeeping. Grows with the size of the model.

``TRACE``
   Per-iteration or per-element detail.

.. note::

   Released wheels are compiled with a floor of ``INFO``: ``DEBUG`` and
   ``TRACE`` records are not in the binary, so no runtime setting brings them
   back, and setting either threshold below the floor raises. This is what
   keeps per-element instrumentation out of a shipped build.
   :func:`~pycanha.log.compiled_level_floor` reports the floor.

The log file
------------

Records are appended to ``logs/YYYY-MM-DD.log``, relative to the current
working directory. The file is created on the first record, not at import, so a
script that logs nothing creates nothing. Concurrent runs share the day's file
and each record carries its pid, which keeps the timeline of two runs readable
rather than splitting it.

.. code-block:: python

   pc.log.set_log_directory("run-logs")   # relative to the working directory
   print(pc.log.current_log_file())       # None until the first record

:func:`~pycanha.log.set_file_output` is a master switch over everything written
to disk -- the log file and the import/export report files described in
:doc:`/import_export/index`:

.. code-block:: python

   pc.log.set_file_output(False)   # nothing touches the filesystem

With it off the console and the record buffer still work, which is how a
notebook runs. Failing to write is never fatal: an unwritable directory costs
one warning, never the analysis.

Reading records back
--------------------

:func:`~pycanha.log.records` returns the most recent records without consuming
them, which is the way to inspect a run with file output off:

.. code-block:: python

   for record in pc.log.records(20):
       print(record.origin, record.level, record.message)

Using stdlib ``logging``
------------------------

Every record also reaches the stdlib logger named ``pycanha``. Nothing has to
be installed; importing pycanha is enough. It carries a ``NullHandler``, so the
Python side prints nothing of its own -- the console belongs to the C++ sink,
and a handler here would print everything twice. Adding one asks for a second
destination:

.. code-block:: python

   import logging

   logging.getLogger("pycanha").addHandler(logging.FileHandler("run.log"))
   pc.log.set_display_level(pc.LogLevel.OFF)   # if you want only yours

This is what makes ``caplog``, :func:`logging.config.dictConfig`, journald and
the rest work on pycanha records like any others.

Delivery to ``logging`` is deferred, and deliberately so. While a C++ call is
running, no Python code runs on that thread, so nothing Python-side can be live
during a long solve; records are handed over on the way out of the operations
that do real work, at :func:`~pycanha.log.flush`, and at interpreter exit. If
you want to watch a long run as it happens, that is what the console threshold
is for.

Recording from your own code
----------------------------

Code built on pycanha can record into the same stream rather than starting a
second one:

.. code-block:: python

   pc.log.info(f"correlating {len(cases)} cases")
   pc.log.warning("case 7 did not converge; using the last iterate")

These cost about 130 ns when the record is kept and about 14 ns when the level
filters it out, so an ``if`` around them buys nothing.

Development builds
------------------

Setting the environment variable ``PYCANHA_DEV_MODE=1`` before importing
pycanha drops both thresholds to the compiled floor and enables nanobind's
shutdown leak warnings. It is one switch for CI and for working on pycanha
itself, not a knob for tuning a normal run.
