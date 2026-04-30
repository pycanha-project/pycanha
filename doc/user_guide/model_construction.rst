Building a Thermal Model
========================

A thermal mathematical model (TMM) in **pycanha** consists of two main
parts: **nodes** and **couplings**. Optionally, you can define **parameters**
and **formulas** to link model quantities to parameters.

Creating a model
----------------

Every analysis starts by instantiating a
:class:`~pycanha.ThermalModel` root object:

.. code-block:: python

  import pycanha as pc
  import pycanha.tmm as pm

  tm = pc.ThermalModel("MyModel")
  tmm = tm.tmm

Adding nodes
------------

Nodes represent lumped thermal masses with a temperature.  Each node has a unique integer
identifier (``node_num``) and several attributes like thermal capacity and heat loads.
Nodes are either **diffusive** (temperature computed by the solver) or **boundary**.

.. code-block:: python

  import pycanha as pc
  import pycanha.tmm as pm

   # Diffusive node (temperature computed by solver)
  node1 = pm.Node(1)
   node1.C  = 1000.0      # capacity [J/K]
   node1.qi = 50.0         # internal dissipation [W]

   # Boundary node (temperature fixed)
  node2 = pm.Node(2)
  node2.type = pm.NodeType.BOUNDARY
   node2.T = 300.0         # fixed temperature [K]

   tmm.add_node(node1)
   tmm.add_node(node2)

.. note::

   Internally, nodes are auto-sorted so that all diffusive nodes come before
   all boundary nodes.  Use :meth:`~pycanha_core.tmm.Nodes.get_idx_from_node_num`
   to map between user node numbers and internal indices. This internal order is
   not guaranteed to remain as described here, so don't rely on it in your code.

Node attributes
^^^^^^^^^^^^^^^

Each node exposes the following scalar attributes:

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
     - Internal dissipation [W]
     - 0.0
   * - ``qs``
     - Solar absorbed heat [W]
     - 0.0
   * - ``qa``
     - Albedo absorbed heat [W]
     - 0.0
   * - ``qe``
     - Earth IR absorbed heat [W]
     - 0.0
   * - ``qr``
     - Other heat loads [W]
     - 0.0
   * - ``eps``
     - Emissivity
     - 0.0
   * - ``aph``
     - Absorptivity
     - 0.0
   * - ``fx``, ``fy``, ``fz``
     - User-defined auxiliary floats (e.g. position)
     - 0.0

Adding couplings
----------------

Couplings define the heat exchange between nodes.

.. code-block:: python

   # Conductive coupling: GL(1,2) = 0.5 W/K
   tmm.conductive_couplings.add_coupling(1, 2, 0.5)

   # Radiative coupling: GR(1,2) = 1e-7 m^2
   tmm.radiative_couplings.add_coupling(1, 2, 1.0e-7)

**Conductive couplings** produce a heat flow proportional to the temperature
difference: :math:`Q = GL \cdot (T_1 - T_2)`.

**Radiative couplings** produce a heat flow proportional to the difference of
fourth powers: :math:`Q = \sigma \cdot GR \cdot  (T_1^4 - T_2^4)`.

Accessing the thermal network
------------------------------

The model exposes its internal containers through properties:

.. code-block:: python

  tm.solvers                   # model-owned solver registry
  tm.callbacks                 # model-owned callback registry
   tmm.nodes                     # Nodes container
   tmm.conductive_couplings      # ConductiveCouplings container
   tmm.radiative_couplings       # RadiativeCouplings container
   tmm.network                   # ThermalNetwork (nodes + couplings)
   tmm.parameters                # Parameters storage
   tmm.formulas                  # Formulas collection
   tmm.thermal_data              # ThermalData result tables
