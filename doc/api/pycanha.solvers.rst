:mod:`pycanha.solvers` — Solvers
================================

.. currentmodule:: pycanha.solvers

Steady-state and transient solvers. Every solver follows the same
``initialize()``, ``solve()``, ``deinitialize()`` lifecycle. See
:doc:`/user_guide/steady_state` and :doc:`/user_guide/transient`.

These base classes are re-exported from :mod:`pycanha_core.solvers` and are
documented on the :doc:`pycanha_core.solvers` page:

* :class:`~pycanha_core.solvers.Solver`
* :class:`~pycanha_core.solvers.SteadyStateSolver`
* :class:`~pycanha_core.solvers.TransientSolver`
* :class:`~pycanha_core.solvers.TSCN`
* :class:`~pycanha_core.solvers.TSCNRL`

Steady-state solvers
--------------------

.. autoclass:: SSLU
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.solvers.SSLU
   :exclude-members: __dict__, __weakref__, __module__

Transient solvers
-----------------

.. autoclass:: TSCNRLDS
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.solvers.TSCNRLDS
   :exclude-members: __dict__, __weakref__, __module__
