:mod:`pycanha.log` — Logging
============================

.. currentmodule:: pycanha.log

The whole of pycanha's logging as seen from Python. One scale for the library,
one file, one clock; the ``origin`` field on a record is what separates what
the C++ core did from what the Python layer did. See
:doc:`/user_guide/logging` for what to set and why.

Thresholds
----------

.. autofunction:: set_record_level
.. autofunction:: record_level
.. autofunction:: set_display_level
.. autofunction:: display_level
.. autofunction:: compiled_level_floor
.. autofunction:: should_log
.. autofunction:: refresh_thresholds

Emitting
--------

Layer-3 code records through these rather than through :mod:`logging`, so that
what pycanha does in Python and what it does in C++ end up in one file, on one
clock, in the order they happened.

.. autofunction:: log
.. autofunction:: trace
.. autofunction:: debug
.. autofunction:: info
.. autofunction:: warning
.. autofunction:: error

Writing to disk
---------------

.. autofunction:: set_file_output
.. autofunction:: file_output
.. autofunction:: set_log_directory
.. autofunction:: log_directory
.. autofunction:: current_log_file

The record buffer
-----------------

.. autofunction:: records
.. autofunction:: drain
.. autofunction:: flush
.. autofunction:: clear_records
.. autofunction:: set_buffer_capacity
.. autofunction:: buffer_capacity

.. autoclass:: LogRecord
   :members:

.. autoclass:: LogDrain
   :members:

.. autoclass:: LogLevel
   :members:
   :undoc-members:

Development builds
------------------

.. autofunction:: dev_mode
