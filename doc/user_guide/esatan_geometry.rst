ESATAN geometry
===============

**pycanha** reads and writes ESATAN-TMS geometry files (``.erg``, and the
geometry part of an ``.etms``) as a :class:`~pycanha.gmm.GeometryModel`.

.. important::

   Both directions are in active development and the API is not stable.

.. code-block:: python

   from pycanha.gmm import GeometryModel

   model = GeometryModel("SATELLITE")
   diagnostics = model.io.read_esatan_erg("satellite.erg")

   print(model.format_tree())
   print(diagnostics.summary())

The model is populated in place.  The same accessor is reachable from a
:class:`~pycanha.ThermalModel` as ``tm.gmm.io.read_esatan_erg(...)``.

Only the geometry is read.  Radiative cases, mission definitions, conductors and
boundary conditions in the same file are ignored.


Diagnostics
-----------

The ESATAN geometry language can express things pycanha's geometry model cannot.
Wherever that happens the construct is **reported and reduced, never silently
approximated**.

``read_esatan_erg`` returns a diagnostic collector:

.. code-block:: python

   diagnostics = model.io.read_esatan_erg(path)

   print(len(diagnostics))          # how many
   print(diagnostics.summary())     # grouped by code, with counts
   print(diagnostics.counts())      # {code: n}

   if "ERG_CUTTER_SENSE" in diagnostics.codes():
       ...                          # a cut was skipped; that solid is too big

   for note in diagnostics:
       print(note.severity.value, note.code, note.line, note.message)

Each diagnostic carries a stable ``code``, so callers can distinguish an
expected reduction from a surprise.  Severities are:

``info``
   A faithful change of representation, e.g.: a box became six flat faces.

``warning``
   An attribute was dropped but the geometry itself is unaffected.

``unsupported``
   A whole construct was skipped.  The model loads without it.

``error``
   The resulting model is likely *wrong*, not merely incomplete, e.g.: an area or a
   node number differs from the source.

Two options change the behaviour:

.. code-block:: python

   # Raise on the first `unsupported` or `error` instead of collecting it.
   model.io.read_esatan_erg(path, strict=True)

   # Receive each diagnostic as it is produced, rather than having it logged.
   model.io.read_esatan_erg(path, on_diagnostic=my_handler)


Writing
-------

.. code-block:: python

   diagnostics = model.io.write_esatan_erg("out.erg", name="SATELLITE")

``name`` is the model name written into the file; it defaults to the model's
own.  The same diagnostic collector, severities and options apply.

Two things are worth knowing about the output.

**Primitives are written by their defining points**.

**Only what the model holds is written.**  Labels, sub-model names,
criticalities and insulation have no place yet in a
:class:`~pycanha.gmm.GeometryModel`.

**Colours are matched to the ESATAN palette.**  Writing picks the
nearest entry by RGB distance.


Construct coverage
------------------

The table below lists every ESATAN geometry construct and what the reader does
with it.  It is generated from the reader's own mapping tables when this page is
built, so it describes the code you are running rather than the code as it stood
when someone last updated a table by hand.

``supported``
   Represented with no loss.

``lossy``
   Represented, but something about it is discarded.

``dropped``
   Skipped. The model loads without it.

``unsupported``
   No representation at all. The construct is refused.

``n/a``
   Not a geometry construct, or has no effect.

The ``steptas_status`` column records whether the construct survives a
conversion to STEP-TAS, which matters if the model is destined for exchange with
another tool.

.. csv-table:: ESATAN geometry constructs
   :file: esatan-coverage.csv
   :header-rows: 1
   :widths: 22 8 16 12 8 34
   :class: longtable

.. note::

   The ``fixture`` column names the model under ``tests/data/esatan/FEATURES/``
   that exercises the construct.  A construct with no fixture is one with no
   pycanha representation and no known use.
