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

.. _the-interactive-viewer:

The interactive viewer
----------------------

Each ``plot*`` call fixes what it shows before the window opens. To change the
colouring, hide a bracket or read a second property, use the viewer instead:

.. code-block:: python

   tm.explore()        # geometry and results
   tm.gmm.explore()    # geometry only

:meth:`~pycanha.ThermalModel.explore` opens a desktop window and blocks until it
is closed, like every ``plot*`` call. It returns the window, so a script can
read back what was selected. The viewer never modifies the model.

The window has a geometry tree on the left, the 3D view in the middle, the
appearance controls on the right and the results and property panes along the
bottom.

**Tree.** One row per group, item and cutter, filtered by name from the box
above it. Right-click a row for Hide, Show and Show only, which apply to the
whole subtree. Hidden geometry is greyed in the tree, not drawn, and not
pickable: clicks pass through it to whatever is behind.

**3D view.** Left-click a face to select it; the property table below describes
it and its row is selected in the tree. Left-drag orbits, so a click that moves
does not select. Right-click opens Hide, Show only, Show all and, when a
transient case is selected, *Plot time history*. The ``Pick`` box in the
toolbar decides whether a click selects the triangle, the face or the whole
item.

**Colour by.** 19 geometry properties: the face slot, node number, side and
owning item; the six thermo-optical degrees of freedom; thickness, bulk
material properties and face area; and the material names and the active-side
flags. Categorical properties get the legend list below the combo, where
clicking a category isolates it and unchecking it hides everything sharing that
value. Numeric ones get the colormap, the limits and the log toggle.

**Results.** The case combo lists the ``DataModel``\ s already in
``tm.tmm.thermal_data.models`` plus the live node state, and the attribute combo
lists what that case holds — temperature, the heat loads, area, and the rest.
The slider snaps to the instants the solver wrote; values are never
interpolated. The colour limits are those of the whole series, so the frames of
an animation are comparable. Read a result file before opening the window:

.. code-block:: python

   tm.tmm.read_tmd_transient("case.TMD", "hot case")
   tm.explore()

**Edges.** Three independent toolbar toggles: ``Mesh`` draws the triangulation,
``Faces`` outlines every face of the thermal mesh, and ``Primitives`` outlines
every primitive.

.. note::

   The mesher welds vertices by position, so the two sides of a full-revolution
   seam are one set of vertices and the seam is not an edge of the
   triangulation. ``Primitives`` therefore draws the two rims of a full
   cylinder and nothing down its side, and nothing at all on a closed sphere.
   The corner lines of a cube are creases rather than boundaries and are not
   drawn either.

**Node filter and find.** The ``Nodes`` boxes grey every face whose node falls
outside the range; they never hide, so ``Show all`` keeps one meaning. ``Find
node`` highlights one node's faces and leaves the camera where it is.

**Bottom pane.** *Properties* describes the current selection, one row per
colour-by property. *Log* carries everything the run records, from the C++ core
as well as from pycanha.

Next
----

:doc:`conduction` generates a TMM from the geometry.
:doc:`/import_export/index` reads geometry from ESATAN-TMS and STEP-TAS files.
