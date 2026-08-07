Quick start
===========

A two-node model, built and solved.

.. code-block:: python

   import pycanha as pc
   import pycanha.tmm as pm

   tm = pc.ThermalModel("QuickStart")
   tmm = tm.tmm

   # Diffusive node with 10 W of internal heat load
   node1 = pm.Node(1)
   node1.C = 100.0             # thermal capacity [J/K], unused in steady state
   node1.qi = 10.0             # internal heat load [W]

   # Boundary node at 300 K
   node2 = pm.Node(2)
   node2.type = pm.NodeType.BOUNDARY
   node2.T = 300.0             # [K]

   tmm.add_node(node1)
   tmm.add_node(node2)

   # Conductive coupling of 0.5 W/K between them
   tmm.conductive_couplings.add_coupling(1, 2, 0.5)

   solver = tm.solvers.sslu
   solver.initialize()
   solver.solve()

   print(f"Node 1: {tmm.nodes.get_T(1):.2f} K")     # 320.00 K

The result is :math:`T_1 = T_2 + q_i / K_{L_{12}} = 300 + 10 / 0.5 = 320` K.

Solvers
-------

* :class:`~pycanha.solvers.SSLU`, steady state by LU decomposition
* :class:`~pycanha.solvers.TSCNRLDS`, transient Crank-Nicolson with radiative
  linearization

Both follow the same ``initialize()``, ``solve()``, ``deinitialize()``
lifecycle.

Where to go next
----------------

* :doc:`/user_guide/model_construction` builds a TMM in full
* :doc:`/user_guide/geometry` builds the geometry, and
  :doc:`/user_guide/conduction` derives the conductive network from it
* :doc:`/import_export/index` reads a model from ESATAN-TMS or STEP-TAS
* :doc:`/auto_examples/index` has runnable examples
