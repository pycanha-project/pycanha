Steady-state solving
====================

A steady-state solver finds the equilibrium temperature of every diffusive
node. Boundary node temperatures are inputs and do not change.

Solving with SSLU
-----------------

:class:`~pycanha.solvers.SSLU` is the default steady-state solver. Radiation is
linearised around the current temperatures, the linear system is factorised
completely and solved, and the passes repeat until the temperatures converge. A
model without radiative couplings is linear and is solved in one pass; a second
pass confirms it, reusing the factorisation. Every solver follows the same
lifecycle:

.. code-block:: python

   solver = tm.solvers.sslu
   solver.initialize()
   solver.solve()
   solver.deinitialize()

``initialize()`` builds the solver from the current network, so the model must
be complete before it is called. Adding, removing or retyping nodes after
``initialize()`` makes ``solve()`` refuse to run and log an error: call
``initialize()`` again.

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

Choosing the factorisation
--------------------------

Two settings decide how the linear system is factorised. ``engine`` is the
library: :attr:`~pycanha.solvers.SolverEngine.MKL` (Intel MKL PARDISO,
multi-threaded) in builds with MKL, which is the default when
:data:`pycanha.solvers.MKL_ENABLED` is true, or
:attr:`~pycanha.solvers.SolverEngine.EIGEN` (single-threaded, available in
every build). ``solver_type`` is the factorisation, a
:class:`~pycanha.solvers.DirectSolverType`:

.. code-block:: python

   from pycanha.solvers import DirectSolverType, SolverEngine

   solver = tm.solvers.sslu
   solver.engine = SolverEngine.MKL
   solver.solver_type = DirectSolverType.MIN_DEGREE
   solver.initialize()

Every type is a complete factorisation, so they all give the same temperatures
and differ only in time and memory:

.. list-table::
   :header-rows: 1
   :widths: 15 10 75

   * - Type
     - Engine
     - When to use it
   * - ``DEFAULT``
     - both
     - ``TWO_LEVEL`` with MKL, ``COLAMD`` with Eigen. Start here.
   * - ``TWO_LEVEL``
     - MKL
     - The safe choice: nested dissection ordering and PARDISO's two-level
       factorisation.
   * - ``ONE_LEVEL``
     - MKL
     - Slightly faster on most models, but with MKL 2025.3 it can stall with 4
       or more threads on some radiative models. Use it only with
       ``mkl_threads`` at 2 or below on real radiative models.
   * - ``MIN_DEGREE``
     - MKL
     - Faster on nearly dense models (many radiative couplings per node). Try
       it when the solver warns that the factorisation is large and nearly
       dense. Its analysis is slow when a few nodes are coupled to many.
   * - ``COLAMD``
     - Eigen
     - The Eigen default.
   * - ``AMD``
     - Eigen
     - Faster than ``COLAMD`` only when a few nodes are coupled to many.
   * - ``LDLT``
     - Eigen
     - Models without radiative couplings only. Less memory than ``COLAMD``.

With MKL, a model without radiative couplings is factorised with Cholesky
instead of LU unless ``allow_cholesky`` is set to ``False``; between
``initialize()`` and ``deinitialize()``, ``solver.uses_cholesky`` tells which
one was chosen. A
combination that is not available -- an MKL type with the Eigen engine,
``LDLT`` with radiative couplings, MKL in a build without it -- makes
``initialize()`` raise ``ValueError``.

``mkl_threads`` limits the threads PARDISO uses (0 keeps MKL's setting).
``pardiso_iparm_overrides`` sets PARDISO ``iparm`` entries directly; it is
meant for diagnosis, and the solver types cover the tested configurations.

Large radiative models: SSLU_CGS
--------------------------------

:class:`~pycanha.solvers.SSLU_CGS` (MKL only) runs the same passes as SSLU but,
after the first factorisation, first solves each new linearisation iteratively,
preconditioned by the previous factorisation, and refactorises only when that
fails. On radiative models, whose matrix changes a little at every pass, this
saves most of the factorisations:

.. code-block:: python

   solver = tm.solvers.sslu_cgs
   solver.initialize()
   solver.solve()
   solver.deinitialize()

The iteration stops at a relative residual of 1e-6 by default
(``pardiso_iparm_3 = 61``), and that residual stays in the converged
temperatures. Use it when that accuracy is enough; use SSLU for exact answers.
Its ``solver_type`` is an :class:`~pycanha.solvers.IterativeSolverType`:
``MIN_DEGREE`` (default) or ``ONE_LEVEL``, with the same stall caveat as above.

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
