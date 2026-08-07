Import / export
===============

pycanha reads and writes the model formats used by the tools it has to exchange
data with. Geometry goes through ``model.gmm.io``, results and analysis source
through the reader on :class:`~pycanha.ThermalModel`.

.. list-table::
   :header-rows: 1
   :widths: 20 8 8 34 30

   * - Format
     - Read
     - Write
     - Contents
     - Entry point
   * - ESATAN-TMS ``.erg``, ``.gmm``, ``.etms``
     - yes
     - ``.erg``
     - GMM
     - :doc:`esatan_geometry`
   * - ESATAN-TMS ``.TMD``
     - yes
     - no
     - Nodes, couplings, heat loads, results
     - :doc:`esatan_results`
   * - ESATAN-TMS ``.d``
     - yes
     - no
     - Analysis source
     - :doc:`esatan_results`
   * - STEP-TAS ``.stp``
     - yes
     - yes
     - GMM, node numbers
     - :doc:`steptas_geometry`

.. important::

   Every reader and writer here is in active development. The APIs are not
   stable.


Import and export reports
-------------------------

Each format carries concepts the others have no representation for, so an
import or an export loses information. The readers and writers convert what
they can and record the rest. They do not approximate without saying so.

Every geometry call returns a report:

.. code-block:: python

   report = model.io.read_esatan_erg(path)

   print(len(report))          # number of entries
   print(report.summary())     # grouped by code, with counts
   print(report.counts())      # {code: n}
   print(report.codes())       # the codes present

   for entry in report:
       print(entry.severity.value, entry.code, entry.line, entry.message)

Each entry carries a stable ``code``. Match on the code, not on the message
text. Repeated entries are counted rather than repeated, so a large model that
drops one attribute per primitive produces one summary line instead of
thousands.

Severities
^^^^^^^^^^

``info``
   The representation changed and nothing was lost. A box became six flat
   faces.

``warning``
   An attribute was dropped. The geometry is unaffected.

``unsupported``
   A whole construct was skipped. The model loads without it.

``error``
   The result is likely wrong rather than incomplete. An area or a node number
   differs from the source.

Options
^^^^^^^

.. code-block:: python

   # Raise on the first unsupported or error entry instead of collecting it.
   model.io.read_esatan_erg(path, strict=True)

   # Receive each entry as it is produced, instead of having it logged.
   model.io.read_esatan_erg(path, on_diagnostic=my_handler)

With ``strict=True`` the first entry at ``unsupported`` or ``error`` raises the
format's own error. A file that is not well formed, or that holds no geometry
at all, raises instead of reporting in either mode. There is nothing to carry
on with. :class:`~pycanha.io.esatan.errors.EsatanParseError` and
:class:`~pycanha.io.steptas.errors.StepTasError` both derive from
:class:`~pycanha.io.errors.ModelReadError`, so a caller that does not care
which format failed catches the base class.

The conduction build uses the same report objects, so code that branches on a
code works for both. See :doc:`/user_guide/conduction`.


.. toctree::
   :maxdepth: 2

   esatan_geometry
   esatan_results
   steptas_geometry
