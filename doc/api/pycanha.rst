:mod:`pycanha` — Top level
==========================

.. currentmodule:: pycanha

:class:`ThermalModel` is the root object. It owns one TMM and one GMM, and
gives access to the solvers and the callbacks.

The subpackages :mod:`pycanha.tmm`, :mod:`pycanha.gmm`,
:mod:`pycanha.parameters`, :mod:`pycanha.solvers`, :mod:`pycanha.conduction`
and :mod:`pycanha.io` are imported on first use.

Thermal model
-------------

.. autoclass:: ThermalModel
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.tmm.ThermalModel
   :exclude-members: __dict__, __weakref__, __module__

Logging
-------

The logger of the compiled core is re-exported here, so user code does not have
to import :mod:`pycanha_core` for it. See :doc:`pycanha_core` for the full
reference.

* :class:`~pycanha_core.LogLevel`, :class:`~pycanha_core.Logger`
* :func:`~pycanha_core.get_logger`, :func:`~pycanha_core.set_logger_level`
* :func:`~pycanha_core.get_python_logger`,
  :func:`~pycanha_core.set_python_logger_level`
* :func:`~pycanha_core.print_package_info`
