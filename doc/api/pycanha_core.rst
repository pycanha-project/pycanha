:mod:`pycanha_core` — C++ Core Package
======================================

.. currentmodule:: pycanha_core

The ``pycanha_core`` package is the compiled C++ backend. Its classes serve
as base classes for the higher-level **pycanha** wrappers. This page
documents the top-level utilities; see the submodule pages for the full
class reference.

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
