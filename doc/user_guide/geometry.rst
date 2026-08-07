Building geometry
=================

The Geometrical Mathematical Model (GMM) holds the geometry of the model:
primitives, how they are grouped, how each one is divided into faces, and which
node number each face is assigned.

Every :class:`~pycanha.ThermalModel` owns one, reachable as ``tm.gmm``. A
:class:`~pycanha.gmm.GeometryModel` can also be built on its own.

.. code-block:: python

   import pycanha as pc
   from pycanha import gmm

   tm = pc.ThermalModel("satellite")

Primitives
----------

A primitive is a surface defined by points. The available ones are
:class:`~pycanha.gmm.Triangle`, :class:`~pycanha.gmm.Rectangle`,
:class:`~pycanha.gmm.Quadrilateral`, :class:`~pycanha.gmm.Disc`,
:class:`~pycanha.gmm.Cylinder`, :class:`~pycanha.gmm.Cone`,
:class:`~pycanha.gmm.Sphere` and :class:`~pycanha.gmm.Paraboloid`.

.. code-block:: python

   plate = gmm.Rectangle((0, 0, 0), (2, 0, 0), (0, 1, 0))

A rectangle is given by three corners. The surfaces of revolution take an
origin, a point on the axis and a point fixing where the angular sweep starts,
plus their radii and angular range.

:class:`~pycanha.gmm.Cube` is a closed solid. It has no thermal mesh and is only
used as a cutter.

Thermal mesh
------------

A :class:`~pycanha.gmm.ThermalMesh` divides a primitive into faces along the
two parametric directions of the primitive. Each direction takes the
subdivision points, between 0 and 1:

.. code-block:: python

   import numpy as np

   mesh = gmm.ThermalMesh(list(np.linspace(0, 1, 5)), list(np.linspace(0, 1, 3)))

This gives 4 by 2 faces. The subdivision does not have to be uniform, so a
region that needs resolution can get it without refining the whole primitive.

Node numbers
^^^^^^^^^^^^

Each face is assigned a node number, one per side. The numbering is a start
value and a step in each direction:

.. code-block:: python

   mesh.node1_start = 100
   mesh.node1_step = 1
   mesh.node2_start = 100
   mesh.node2_step = 1

``mesh.node_of(i, j, side)`` returns the node number of one face, and
:meth:`~pycanha.gmm.GeometryModel.faces_of_node` goes the other way, from a
node number to the faces assigned to it.

Sides
^^^^^

A face has two sides, side 1 and side 2, each with its own thermo-optical
properties, color, thickness and bulk material:

.. code-block:: python

   optical = gmm.OpticalMaterial()
   optical.emissivity_ir = 0.85
   optical.absorptivity_solar = 0.3

   mesh.side1_optical = optical
   mesh.side1_thick = 0.002                 # [m]
   mesh.side1_material = aluminium          # a BulkMaterial

Which sides take part is set separately for radiation and for conduction:

.. code-block:: python

   mesh.radiative_active_side = gmm.ActiveSide.SIDE1
   mesh.conductive_active_side = gmm.ActiveSide.BOTH

:class:`~pycanha.gmm.ActiveSide` is ``NONE``, ``SIDE1``, ``SIDE2`` or ``BOTH``.
The two selectors are independent. A surface can conduct without radiating and
the other way round.

Items and groups
----------------

A :class:`~pycanha.gmm.GeometryItem` binds a primitive to a thermal mesh and
gives it a name. A :class:`~pycanha.gmm.GeometryGroup` holds items and other
groups.

.. code-block:: python

   top = gmm.GeometryItem("top", plate, mesh)

   body = gmm.GeometryGroup("body", [top, bottom])
   tm.gmm.add(gmm.GeometryGroup("spacecraft", [body, panels]))

   tm.gmm.print_tree()

A group applies its transformation to everything it contains, so moving a group
moves its whole content.

Cutting
-------

The ``-`` operator cuts a geometry with one or more closed solids. Chaining
``-`` adds more cutters. The result is a
:class:`~pycanha.gmm.GeometryGroupCutted`:

.. code-block:: python

   cut = plate_item - gmm.Cube(...) - gmm.Cylinder(...)

Valid cutters are the closed solids: :class:`~pycanha.gmm.Cube`,
:class:`~pycanha.gmm.Cylinder`, :class:`~pycanha.gmm.Sphere` and
:class:`~pycanha.gmm.Cone`.

The ``+`` operator groups geometries. It is aggregation, not a union.

Viewing the model
-----------------

:meth:`~pycanha.gmm.GeometryModel.plot` opens an interactive pyvista window:

.. code-block:: python

   tm.gmm.plot()                          # color by face
   tm.gmm.plot(scalars="item")            # one color per item
   tm.gmm.plot(scalars="node_number")
   tm.gmm.plot(scalars="emissivity", show_edges=True)

Results are drawn from a mapping or an array:

.. code-block:: python

   tm.gmm.plot_node_data({node: T for node, T in temperatures.items()}, name="T [K]")
   tm.gmm.plot_node_range(10, 20, color="green")
   tm.gmm.plot_node_series(history, nodes, times, name="T [K]")

``plot_node_series`` adds a time slider over a ``(len(times), len(nodes))``
array.

.. note::

   For the raytracer and for plotting, the geometry is tesselated into
   triangles that respect the face boundaries. This triangulation, also called
   the geometry mesh, is not the thermal mesh. It carries no node numbers and
   plays no part in the TMM. ``tm.gmm.mesh`` is that triangulation.

The gallery has runnable versions of all of this. See
:doc:`/auto_examples/index`.

Next
----

:doc:`conduction` generates a TMM from the geometry.
:doc:`/import_export/index` reads geometry from ESATAN-TMS and STEP-TAS files.
