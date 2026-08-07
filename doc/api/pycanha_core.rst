:mod:`pycanha_core` — Compiled backend
======================================

.. currentmodule:: pycanha_core

The compiled C++ backend. Its classes are the base classes of the pycanha ones.
This page covers the top-level utilities. The submodule pages hold the class
reference.

The logger is also re-exported from :mod:`pycanha`, so user code does not need
to import this package directly.

Logging
-------

.. autoclass:: pycanha_core.Logger
   :members:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: pycanha_core.LogLevel
   :members:
   :undoc-members:

Utilities
---------

.. autofunction:: pycanha_core.print_package_info

.. autofunction:: pycanha_core.get_logger

.. autofunction:: pycanha_core.set_logger_level
