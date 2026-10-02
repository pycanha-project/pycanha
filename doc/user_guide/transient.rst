Transient solving
=================

:class:`~pycanha.solvers.TSCNRLDS` integrates the model in time. It is a
Crank-Nicolson scheme with radiative linearization and direct sparse
factorization.

Setting up the integration
--------------------------

.. code-block:: python

   solver = tm.solvers.tscnrlds
   solver.set_simulation_time(
       start_time=0.0,        # [s]
       end_time=100_000.0,    # [s]
       dtime=100.0,           # integration timestep [s]
       output_stride=1000.0,  # store a result every 1000 s
   )
   solver.initialize()
   solver.solve()
   solver.deinitialize()

``output_stride`` sets how often results are stored. A large stride keeps the
output small when the timestep is short.

Factorisation
-------------

TSCNRLDS takes the same ``engine`` and ``solver_type`` as SSLU (see
:doc:`steady_state`), except ``LDLT``: the transient matrix is factorised with
LU. The default factorises every changed matrix completely, so every step is
exact.

Because the matrix changes little from one step to the next, an iterative step
preconditioned by the previous factorisation saves most of the work per step.
It needs the ``ONE_LEVEL`` or ``MIN_DEGREE`` type (MKL only):

.. code-block:: python

   from pycanha.solvers import DirectSolverType

   solver = tm.solvers.tscnrlds
   solver.solver_type = DirectSolverType.MIN_DEGREE
   solver.pardiso_iparm_3 = 61     # iterate to a relative residual of 1e-6
   solver.initialize()

``pardiso_iparm_3 = 10 * L + 1`` stops the iteration at a relative residual of
:math:`10^{-L}`, and that residual stays in every step. ``0`` (the default)
switches the iteration off.

Initial conditions
------------------

The solver starts from the current node temperatures. Set them before
``initialize()``:

.. code-block:: python

   for node_num in range(1, 11):
       tmm.nodes.set_T(node_num, 273.15)   # start at 0 degC

Reading the results
-------------------

The results are stored in a :class:`~pycanha.tmm.ThermalData` container. Take
it from the solver:

.. code-block:: python

   output_model = solver.output_model

   times = output_model.T.times      # time samples [s]
   values = output_model.T.values    # (n_steps, n_nodes) [K]

Temperature columns are ordered by node index, not by node number. Map a
node number to its column with
:meth:`~pycanha_core.tmm.Nodes.get_idx_from_node_num`:

.. code-block:: python

   import matplotlib.pyplot as plt

   idx1 = tmm.nodes.get_idx_from_node_num(1)

   times = output_model.T.times
   T1 = output_model.T.values[:, idx1]

   plt.plot(times / 3600.0, T1)
   plt.xlabel("Time [h]")
   plt.ylabel("Temperature [K]")
   plt.show()
