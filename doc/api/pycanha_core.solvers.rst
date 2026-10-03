:mod:`pycanha_core.solvers` — Core solver classes
==================================================

.. currentmodule:: pycanha_core.solvers

The C++ solver base classes.

Solver options
--------------

.. autodata:: MKL_ENABLED

.. autofunction:: default_solver_engine

.. autofunction:: resolve_solver_type

.. autoclass:: SolverEngine
   :members:
   :undoc-members:

.. autoclass:: DirectSolverType
   :members:
   :undoc-members:

.. autoclass:: IterativeSolverType
   :members:
   :undoc-members:

Solvers
-------

.. autoclass:: Solver
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: SteadyStateSolver
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: TransientSolver
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: TSCN
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: TSCNRL
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: SSLU
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: SSLU_CGS
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: TSCNRLDS
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__
