Generating a TMM from the geometry
==================================

:meth:`~pycanha.ThermalModel.build_tmm_from_gmm` walks the GMM and builds the
conductive part of the TMM from it. It creates one node per face that carries a
node number on a conductive active side, and the conductive couplings those
faces imply.

.. code-block:: python

   import pycanha as pc

   tm = pc.ThermalModel("satellite")
   ...                                     # build the geometry, number the faces

   report = tm.build_tmm_from_gmm()
   print(pc.conduction.summary(report))

The build refuses to run on a TMM that already holds nodes or conductive
couplings. There is no merge. Radiative couplings, parameters, formulas and
thermal data are left untouched.

What it generates
-----------------

**In-plane couplings** connect neighbouring faces of the same primitive. They
are integrated along the native parametrisation of the primitive, so a
cylinder, a cone and a sphere each use their own meridian profile instead of a
flat approximation.

**Through-thickness couplings** connect side 1 to side 2 of the same face,
through the thickness and bulk material of that face.

**Which sides become nodes, and which of those conduct**, are two different
questions, answered by the two active-side selectors between them:

* a side that either
  :attr:`~pycanha_core.gmm.ThermalMesh.conductive_active_side` or
  :attr:`~pycanha_core.gmm.ThermalMesh.radiative_active_side` selects becomes
  nodes, with the capacitance of its material and thickness. A radiating
  surface has a temperature whether or not it conducts, so it needs a node;
* only a side that ``conductive_active_side`` selects gets couplings. A
  through-thickness coupling needs both sides conducting.

So the ESATAN "Radiative" surface -- radiative on both sides, conductive on
neither -- comes out as nodes with capacitance and no conductors, and a side
selected by neither is dropped entirely.

Options
-------

.. code-block:: python

   options = pc.conduction.TmmBuildOptions()
   options.intra_primitive_conductors = True
   options.through_thickness_conductors = True
   options.min_conductance = 1e-12          # [W/K], at or below this a coupling is dropped
   options.close_full_revolution = True
   options.initial_temperature = 293.15      # [K]

   report = tm.build_tmm_from_gmm(options)

``close_full_revolution`` closes the ring between the last and the first
angular face of a primitive that spans a full revolution. The default
``min_conductance`` of 0.0 keeps everything except exact zeros.

Reading the report
------------------

:class:`~pycanha_core.conduction.TmmBuildReport` counts what was produced:

.. code-block:: python

   report.nodes_created
   report.conductors_created
   report.items_processed
   report.items_skipped
   report.cell_links_computed

Anything the build had to skip or approximate is reported in the same form as
the file readers, so code that branches on a code works for both:

.. code-block:: python

   for entry in pc.conduction.diagnostics(report):
       print(entry.severity.value, entry.code, entry.message)

   print(pc.conduction.summary(report))

The severities are the ones described in :doc:`/import_export/index`.
