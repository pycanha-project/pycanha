Steady-State Solver
====================

Once the model is built, a steady-state solve finds the equilibrium
temperatures for all diffusive nodes.

Using SSLU
----------

:class:`~pycanha.solvers.SSLU` is a direct LU-decomposition solver suitable
for models of any size.  Usage follows the **initialize → solve →
deinitialize** lifecycle:

.. code-block:: python

   solver = tm.solvers.sslu
   solver.initialize()
   solver.solve()
   solver.deinitialize()

Reading results
---------------

After solving, node temperatures are updated in-place:

.. code-block:: python

   T1 = tmm.nodes.get_T(1)
   print(f"Node 1: {T1:.2f} K")

You can also access them through the node object:

.. code-block:: python

   node1 = tmm.nodes.get_node_from_node_num(1)
   print(f"Node 1: {node1.T:.2f} K")

Solver tolerances
-----------------

The solver exposes convergence tolerances that can be adjusted before
calling ``initialize()``:

.. code-block:: python

   solver.abstol_temp  = 1e-4   # temperature convergence [K]
   solver.abstol_enrgy = 1e-4   # energy balance convergence [W]
   solver.max_iters    = 10     # max iterations per solve step

Re-using the solver
-------------------

After ``initialize()`` the solver can be called multiple times with
``solve()`` — for example inside a parameter sweep — without
re-initializing:

.. code-block:: python

   solver = tm.solvers.sslu
   solver.initialize()

   for k in [0.5, 1.0, 2.0]:
       tmm.conductive_couplings.set_coupling_value(1, 2, k)
       solver.solve()
       print(f"k={k:.1f}  →  T1 = {tmm.nodes.get_T(1):.2f} K")

   solver.deinitialize()
