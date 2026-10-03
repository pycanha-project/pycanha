Generating a TMM from the geometry
==================================

:meth:`~pycanha.ThermalModel.build_tmm_from_gmm` walks the GMM and builds the
conductive part of the TMM from it. It creates one node per face that carries a
node number on an active side, and the conductive couplings the conductively
active faces imply.

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

Every node is diffusive. To fix the temperature of some of them, turn them into
boundary nodes after the build:

.. code-block:: python

   tm.tmm.nodes.set_types([100, 101, 102], pc.tmm.NodeType.BOUNDARY)

Capacity, position and area
---------------------------

Each face contributes :math:`\rho \, c \, t \, A` to its node's capacity,
with :math:`A` the exact area of the face for the primitive's definition -- not
the area of its triangulation -- so curved primitives get exact capacities.
The node position (``fx``, ``fy``, ``fz``) is the area-weighted centroid of its
faces. Nothing is triangulated for geometry that is not cut, which is what
keeps the build fast on large models.

The node area ``a`` is not set by the build. It is the triangulated area, and
filling it triangulates the geometry, so it is a separate call:

.. code-block:: python

   pc.conduction.assign_node_areas(tm)

The exact face areas are available on their own through
:class:`~pycanha.gmm.FacePairGeometryEvaluator`:

.. code-block:: python

   evaluator = pc.gmm.FacePairGeometryEvaluator(item.primitive, item.thermal_mesh)
   areas, centroids = evaluator.all()     # one entry per face pair, direction 1 fastest

Cut geometry
------------

Geometry inside a cut group (``panel - hole``) gets its nodes too. The faces a
cut reaches keep the fraction of their area that survives: their capacity and
through-thickness coupling are scaled by it, and a face cut away completely
contributes nothing. The in-plane couplings that touch a cut face are removed,
so heat does not cross the band of cut faces in the plane until a correction
for them exists. The build reports both with a ``CutFacePairs`` warning, and
with ``UncoupledNodes`` when a node ends up with no conductive coupling at all,
which makes a steady-state solve singular unless something else (a radiative
coupling) attaches it.

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
   report.face_pair_links_computed
   report.face_pairs_cut          # partly cut away
   report.face_pairs_removed      # cut away completely
   report.links_removed           # in-plane couplings removed by cuts

Anything the build had to skip or approximate is reported in the same form as
the file readers, so code that branches on a code works for both:

.. code-block:: python

   for entry in pc.conduction.diagnostics(report):
       print(entry.severity.value, entry.code, entry.message)

   print(pc.conduction.summary(report))

The severities are the ones described in :doc:`/import_export/index`.

Building one item at a time
---------------------------

The build is two steps, available separately: every geometry item builds its
own :class:`~pycanha_core.conduction.NetworkPart` -- its nodes, capacities,
positions and couplings as read-only arrays -- and the parts are merged and
written into the TMM. Use them to inspect what one item contributes:

.. code-block:: python

   part = pc.conduction.build_network_part(item, pc.gmm.CoordinateTransformation())
   part.node_numbers, part.thermal_capacity, part.conductance

   tmm = pc.tmm.ThermalMathematicalModel("parts")
   pc.conduction.commit_network_parts(tmm, [part])
