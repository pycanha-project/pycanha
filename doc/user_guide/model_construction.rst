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
