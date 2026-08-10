:mod:`pycanha` — Top level
==========================

.. currentmodule:: pycanha

:class:`ThermalModel` is the root object. It owns one TMM and one GMM, and
gives access to the solvers and the callbacks.

The subpackages :mod:`pycanha.tmm`, :mod:`pycanha.gmm`,
:mod:`pycanha.parameters`, :mod:`pycanha.solvers`, :mod:`pycanha.conduction`,
:mod:`pycanha.io` and :mod:`pycanha.log` are imported on first use.

Thermal model
-------------

.. autoclass:: ThermalModel
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.tmm.ThermalModel
   :exclude-members: __dict__, __weakref__, __module__

Logging
-------

Logging lives in :doc:`pycanha.log`, which is the whole of it as seen from
Python; user code never has to import :mod:`pycanha_core` for it.
:class:`~pycanha_core.LogLevel` is also aliased at this level, since setting a
threshold is the one thing everybody does::

    import pycanha as pc

    pc.log.set_display_level(pc.LogLevel.OFF)

Utilities
---------

* :func:`~pycanha_core.print_package_info`
