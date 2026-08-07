Steady-state solving
====================

A steady-state solver finds the equilibrium temperature of every diffusive
node. Boundary node temperatures are inputs and do not change.

Solving with SSLU
-----------------

:class:`~pycanha.solvers.SSLU` is a direct solver based on LU decomposition. It
is suitable for models of any size. Every solver follows the same lifecycle:

.. code-block:: python

   solver = tm.solvers.sslu
   solver.initialize()
   solver.solve()
   solver.deinitialize()

``initialize()`` builds the solver from the current network, so the model must
be complete before it is called.

Reading the results
-------------------

Node temperatures are updated in place:

.. code-block:: python

   T1 = tmm.nodes.get_T(1)
   print(f"Node 1: {T1:.2f} K")

The node object gives the same value:

.. code-block:: python

   node1 = tmm.nodes.get_node_from_node_num(1)
   print(f"Node 1: {node1.T:.2f} K")

Tolerances
----------

Set the tolerances before calling ``initialize()``:

.. code-block:: python

   solver.abstol_temp = 1e-4    # temperature convergence [K]
   solver.abstol_enrgy = 1e-4   # energy balance convergence [W]
   solver.max_iters = 10        # iterations per solve step

Radiative couplings make the system non-linear, so the solver iterates until
both tolerances are met or ``max_iters`` is reached.

Re-using the solver
-------------------

After ``initialize()``, ``solve()`` can be called any number of times. Values
changed between calls are picked up, so a sweep does not pay for a new
initialization on every point:

.. code-block:: python

   solver = tm.solvers.sslu
   solver.initialize()

   for k in [0.5, 1.0, 2.0]:
       tmm.conductive_couplings.set_coupling_value(1, 2, k)
       solver.solve()
       print(f"k = {k:.1f} W/K, T1 = {tmm.nodes.get_T(1):.2f} K")

   solver.deinitialize()
