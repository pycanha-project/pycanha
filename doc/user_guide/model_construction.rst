Building a thermal model
========================

A Thermal Mathematical Model (TMM) in pycanha holds nodes and couplings.
Parameters and formulas are optional, and link model quantities to named
values.

This page builds a TMM node by node. A TMM can also be generated from the
geometry, which is covered in :doc:`conduction`, or read from a file, which is
covered in :doc:`/import_export/index`.

Creating a model
----------------

:class:`~pycanha.ThermalModel` is the root object. It owns the TMM and the
Geometrical Mathematical Model (GMM):

.. code-block:: python

   import pycanha as pc
   import pycanha.tmm as pm

   tm = pc.ThermalModel("MyModel")
   tmm = tm.tmm

Adding nodes
------------

Each node has a unique integer number (``node_num``), a temperature, a thermal
capacity and heat loads. A diffusive node has its temperature computed by the
solver. A boundary node keeps the temperature it is given.

.. code-block:: python

   node1 = pm.Node(1)               # diffusive by default
   node1.C = 1000.0                 # thermal capacity [J/K]
   node1.qi = 50.0                  # internal heat load [W]

   node2 = pm.Node(2)
   node2.type = pm.NodeType.BOUNDARY
   node2.T = 300.0                  # [K]

   tmm.add_node(node1)
   tmm.add_node(node2)

.. note::

   Nodes are sorted internally so that the diffusive ones come before the
   boundary ones. Use
   :meth:`~pycanha_core.tmm.Nodes.get_idx_from_node_num` to map a node number
   to its node index. This order is not part of the API and may change.

Node attributes
^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 10 50 15

   * - Attribute
     - Description
     - Default
   * - ``T``
     - Temperature [K]
     - 0.0
   * - ``C``
     - Thermal capacity [J/K]
     - 0.0
   * - ``qi``
     - Internal heat load [W]
     - 0.0
   * - ``qs``
     - Solar heat load [W]
     - 0.0
   * - ``qa``
     - Albedo heat load [W]
     - 0.0
   * - ``qe``
     - Earth IR heat load [W]
     - 0.0
   * - ``qr``
     - Other heat load [W]
     - 0.0
   * - ``eps``
     - Emissivity
     - 0.0
   * - ``aph``
     - Absorptivity
     - 0.0
   * - ``fx``, ``fy``, ``fz``
     - Free floats for the user, position for example
     - 0.0

Adding couplings
----------------

.. code-block:: python

   tmm.conductive_couplings.add_coupling(1, 2, 0.5)      # [W/K]
   tmm.radiative_couplings.add_coupling(1, 2, 1.0e-7)    # [m^2]

A conductive coupling :math:`K_{L_{12}}` [W/K] is the inverse of the thermal
resistance between the two nodes:

.. math::

   Q_{12} = K_{L_{12}} \cdot (T_1 - T_2)

A radiative coupling :math:`K_{R_{12}}` [m^2] does not include the
Stefan-Boltzmann constant:

.. math::

   Q_{12} = \sigma \cdot K_{R_{12}} \cdot (T_1^4 - T_2^4)

Large models: adding from arrays
--------------------------------

Adding nodes and couplings one at a time is fine for hand-built models, and
stays linear in the number of nodes when nodes are added in increasing number.
For large models, add them from numpy arrays in one call each:

.. code-block:: python

   import numpy as np

   n = 1_000_000
   numbers = np.arange(1, n + 1)
   qi = np.zeros(n)
   qi[0] = 50.0

   tmm.add_nodes(numbers, T=np.full(n, 273.15), C=np.full(n, 10.0), qi=qi)
   tmm.add_nodes(np.array([n + 1]), type=pm.NodeType.BOUNDARY, T=np.array([300.0]))

   report = tmm.add_conductive_couplings(
       numbers,                                  # node_1
       np.append(numbers[1:], n + 1),            # node_2
       np.full(n, 0.5),                          # [W/K]
   )
   print(report.accepted, report.rejected)

``add_nodes`` takes one node type per call. Every attribute is an optional
array with one value per node (``T``, ``C``, ``qi``, ``qs``, ``qa``, ``qe``,
``qr``, ``a``, ``fx``, ``fy``, ``fz``, ``eps``, ``aph``); an attribute left out
is zero. ``add_conductive_couplings`` and ``add_radiative_couplings`` take the
two node numbers and the value of each coupling. Node numbers can be any integer
dtype; a number outside the 32-bit range is rejected, never wrapped onto
another node.

Neither call fails half-way. Entries that cannot be added -- a node number that
already exists, an unknown node, a negative or non-finite value -- are dropped,
and the returned :class:`~pycanha.tmm.BulkReport` counts them
(``accepted``, ``merged``, ``rejected``, ``first_rejections``).

Order matters for speed, not for the result. Nodes numbered above every node
already in the model, in increasing order, are appended directly. Couplings
sorted by (smaller node, larger node), after every coupling already stored, are
appended too; anything else is sorted and merged in.

A coupling that already exists, or that appears twice in the same call, is
resolved by ``merge``, a :class:`~pycanha.tmm.CouplingMerge`: ``OVERWRITE``
(the default, as ``add_coupling``), ``SUM`` or ``NEW`` (keep the first).

Reading and setting many values
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The node container reads and sets one attribute of many nodes at once,
selected with a :class:`~pycanha.tmm.NodeAttribute`:

.. code-block:: python

   nodes = tmm.nodes
   nodes.set_values(pm.NodeAttribute.QI, np.array([1, 2]), np.array([10.0, 20.0]))
   T = nodes.get_values(pm.NodeAttribute.T)                     # every node, internal order
   T12 = nodes.get_values(pm.NodeAttribute.T, np.array([1, 2]))  # NaN for an unknown node

The coupling containers do the same by node pair, and ``to_arrays()`` returns
every stored coupling:

.. code-block:: python

   gl = tmm.conductive_couplings
   values = gl.get_values(np.array([1, 2]), np.array([2, 3]))    # NaN if missing
   gl.set_values(np.array([1]), np.array([2]), np.array([0.8]))  # existing ones only
   node_1, node_2, values = gl.to_arrays()

``nodes.set_types(numbers, pm.NodeType.BOUNDARY)`` turns many nodes into
boundary nodes (or back) in one pass, keeping their attributes and couplings.
It is how a model generated from the geometry, where every node is diffusive,
gets its boundary nodes.

Adding nodes, or changing their type, invalidates any value pointer handed out
for formulas; bind formulas after the model is built.

Accessing the model containers
------------------------------

.. code-block:: python

   tm.solvers                    # solvers owned by the model
   tm.callbacks                  # callbacks owned by the model
   tm.gmm                        # GeometryModel

   tmm.nodes                     # Nodes
   tmm.conductive_couplings      # ConductiveCouplings
   tmm.radiative_couplings       # RadiativeCouplings
   tmm.network                   # ThermalNetwork, nodes and couplings
   tmm.parameters                # Parameters
   tmm.formulas                  # Formulas
   tmm.thermal_data              # ThermalData, the result tables
