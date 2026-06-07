Quick Start
===========

This page walks through a minimal thermal model to get you up and running.

A two-node thermal model and how to solve it with **pycanha**:
------------------------------

The simplest possible thermal model has two nodes connected by a conductive
coupling.  One node is *diffusive* (its temperature is computed) and the other
is at a fixed-temperature *boundary*.

.. code-block:: python

   import pycanha as pc
   import pycanha.tmm as pm

   # 1. Create the model root
   tm = pc.ThermalModel("QuickStart")
   tmm = tm.tmm

   # 2. Add nodes
   node1 = pm.Node(1)          # diffusive by default
   node1.C  = 100.0            # thermal capacity [J/K] (not needed for steady-state analysis)
   node1.qi = 10.0             # internal heat dissipation [W]

   node2 = pm.Node(2)
   node2.type = pm.NodeType.BOUNDARY
   node2.T = 300.0             # fixed temperature [K]

   tmm.add_node(node1)
   tmm.add_node(node2)

   # 3. Add a conductive coupling GL(1,2) = 0.5 W/K
   tmm.conductive_couplings.add_coupling(1, 2, 0.5)

   # 4. Solve
   solver = tm.solvers.sslu
   solver.initialize()
   solver.solve()

   # 5. Read results
   T1 = tmm.nodes.get_T(1)
   print(f"Node 1 temperature: {T1:.2f} K")   # 320.00 K

Key concepts
------------

Nodes
   Thermal nodes have a defined temperature and a thermal capacity (lumped model).
   Each node has additional attributes like heat loads (``qi``, ``qs``, ``qa``,
   ``qe``, ``qr``).  Nodes are either **diffusive** (temperature computed
   by the solver) or **boundary** (temperature fixed).

Couplings
   Thermal couplings define the heat exchange between two nodes.
   **Conductive couplings** (``GL``) model linear heat transfer, while
   **radiative couplings** (``GR``) model radiative heat flow.

Solvers
   * :class:`~pycanha.solvers.SSLU` — Steady-state solver (LU decomposition)
   * :class:`~pycanha.solvers.TSCNRLDS` — Transient solver (Crank-Nicolson with
     radiative linearization)

Parameters & Formulas
   The parameter system lets you link model quantities (node attributes,
   coupling values, etc.) to named parameters so you can do parametric analysis easily.
   See the :doc:`/user_guide/index` for details.

Next steps
----------

* Browse the :doc:`/user_guide/index` for in-depth tutorials
* Explore the :doc:`/auto_examples/index` gallery
* Consult the :doc:`/api/index` for the full class reference
