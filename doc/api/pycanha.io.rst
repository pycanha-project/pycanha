:mod:`pycanha.io` — Import and export
=====================================

.. currentmodule:: pycanha.io

Readers and writers for the model formats pycanha exchanges with. The geometry
formats are reached through ``model.gmm.io``, documented below as
:class:`~pycanha.gmm.io.GeometryIo`. The ESATAN-TMS result and analysis files
are read by :class:`ESATANReader`.

:doc:`/import_export/index` describes what each format carries and what a
conversion costs.

Geometry
--------

.. currentmodule:: pycanha.gmm.io

.. autoclass:: GeometryIo
   :members:
   :exclude-members: __dict__, __weakref__, __module__

Results and analysis files
--------------------------

.. currentmodule:: pycanha.io

.. autoclass:: ESATANReader
   :members:
   :exclude-members: __dict__, __weakref__, __module__

Reports
-------

Every reader and writer returns a :class:`~pycanha.io.diagnostics.DiagnosticCollector`.
:mod:`pycanha.conduction` reports its build the same way.

.. currentmodule:: pycanha.io.diagnostics

.. autoclass:: Severity
   :members:
   :undoc-members:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Diagnostic
   :members:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: DiagnosticCollector
   :members:
   :exclude-members: __dict__, __weakref__, __module__

Errors
------

.. currentmodule:: pycanha.io.errors

.. autoclass:: ModelReadError
   :members:
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. currentmodule:: pycanha.io.esatan.errors

.. autoclass:: EsatanParseError
   :members:
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. currentmodule:: pycanha.io.steptas.errors

.. autoclass:: StepTasError
   :members:
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__
