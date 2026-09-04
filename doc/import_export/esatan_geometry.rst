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

A model whose surfaces took their corners from an array is written with those
corners in place, since reading substitutes each element where it was used and
keeps no record of where the value came from. The geometry is the same; the
array is not reconstructed, and neither is the fact that two surfaces named the
same element.


Arrays
------

A model may collect its points into an array and name the elements as corners:

.. code-block:: text

   POINT grid[4];
   grid[1] = [0.0, 0.0, 0.0];
   ...
   T1 = SHELL_TRIANGLE(point1 = grid[1], point2 = grid[2], point3 = grid[3], ...);

Indices count from one and may be computed. An array is equally usable whole,
which is how a mesh-position list and a material property table are passed.

Two limits are worth knowing. Only one-dimensional arrays can be indexed; a
multi-dimensional one still works passed by name, but indexing it is reported
and skipped. And an element that nothing assigned reads as zero -- a point at
the origin, a number at 0.0 -- which is what the source format does too, so it
is reported as ``ERG_ARRAY_UNASSIGNED`` rather than left to surface later as a
degenerate surface.


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

.. csv-table:: ESATAN-TMS geometry constructs
   :file: esatan-coverage.csv
   :header-rows: 1
   :widths: 24 9 18 13 36
   :class: longtable

.. note::

   The ``fixture`` column names the model under ``tests/data/esatan/`` that
   exercises the construct; it is filled by reading those models, so it is a
   fact about the tree rather than a claim about it. A construct with no
   fixture named is one no committed model carries -- either because it has no
   pycanha representation, or because the model that provokes it is small
   enough to be written inside the test that needs it.
