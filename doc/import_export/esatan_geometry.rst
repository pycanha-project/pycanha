ESATAN-TMS geometry
===================

pycanha reads and writes ESATAN-TMS geometry files as a
:class:`~pycanha.gmm.GeometryModel`. The reader accepts a ``.erg`` geometry
file, an included ``.gmm`` fragment, or a ``.etms`` model file.

.. code-block:: python

   from pycanha.gmm import GeometryModel

   model = GeometryModel("SATELLITE")
   report = model.io.read_esatan_erg("satellite.erg")

   print(model.format_tree())
   print(report.summary())

The model is populated in place. The same accessor is reachable from a
:class:`~pycanha.ThermalModel` as ``tm.gmm.io.read_esatan_erg(...)``.

Only the geometry is read. Radiative cases, mission definitions, conductors and
boundary conditions in the same file are ignored.

The import report, its severities and the ``strict`` and ``on_diagnostic``
options are described in :doc:`index`.


Writing
-------

.. code-block:: python

   report = model.io.write_esatan_erg("out.erg", name="SATELLITE")

``name`` is the model name written into the file. It defaults to the model's
own name.

Primitives are written by their defining points. Only what the model holds is
written: labels, sub-model names, criticalities and insulation have no place in
a :class:`~pycanha.gmm.GeometryModel` yet. Colors are matched to the ESATAN
palette by nearest RGB distance.


Construct coverage
------------------

The table lists every ESATAN geometry construct and what the reader does with
it. It is generated from the reader's own mapping tables when this page is
built, so it describes the installed version rather than a hand-maintained
copy.

``supported``
   Represented with no loss.

``lossy``
   Represented, but something is discarded.

``dropped``
   Skipped. The model loads without it.

``unsupported``
   No representation at all. The construct is refused.

``n/a``
   Not a geometry construct, or has no effect.

The ``steptas_status`` column records whether the construct survives a
conversion to STEP-TAS, which matters for a model destined for exchange with
another tool.

.. csv-table:: ESATAN-TMS geometry constructs
   :file: esatan-coverage.csv
   :header-rows: 1
   :widths: 22 8 16 12 8 34
   :class: longtable

.. note::

   The ``fixture`` column names the model under ``tests/data/esatan/FEATURES/``
   that exercises the construct. A construct with no fixture has no pycanha
   representation and no known use.
