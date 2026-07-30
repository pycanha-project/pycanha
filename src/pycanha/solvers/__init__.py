"""Solver subpackage."""

import pycanha_core as pcc

from .solver import Solver
from .ss import SteadyStateSolver
from .sslu import SSLU
from .ts import TransientSolver
from .tscn import TSCN
from .tscnrl import TSCNRL
from .tscnrlds import TSCNRLDS
from .tscnrlds_jacobian import TSCNRLDS_JACOBIAN

CallbackContext = pcc.solvers.CallbackContext
CallbackRegistry = pcc.solvers.CallbackRegistry
SolverOutputConfig = pcc.solvers.SolverOutputConfig
SolverRegistry = pcc.solvers.SolverRegistry

del pcc  # implementation detail; users reach the core through pycanha only

__all__ = [
    "SSLU",
    "TSCN",
    "TSCNRL",
    "TSCNRLDS",
    "TSCNRLDS_JACOBIAN",
    "CallbackContext",
    "CallbackRegistry",
    "Solver",
    "SolverOutputConfig",
    "SolverRegistry",
    "SteadyStateSolver",
    "TransientSolver",
]
