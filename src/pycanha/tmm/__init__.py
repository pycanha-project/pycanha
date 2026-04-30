"""Thermal Mathematical Model subpackage."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .conductivecouplings import ConductiveCouplings
    from .coupling import Coupling
    from .couplingmatrices import CouplingMatrices
    from .couplings import Couplings
    from .node import Node, NodeType
    from .nodes import Nodes
    from .radiativecouplings import RadiativeCouplings
    from .thermaldata import ThermalData
    from .thermalmathematicalmodel import ThermalMathematicalModel
    from .thermalnetwork import ThermalNetwork

__all__ = [
    "ConductiveCouplings",
    "Coupling",
    "CouplingMatrices",
    "Couplings",
    "Node",
    "NodeType",
    "Nodes",
    "RadiativeCouplings",
    "ThermalData",
    "ThermalMathematicalModel",
    "ThermalNetwork",
]


def __getattr__(name: str) -> Any:
    # Resolve public symbols lazily so package-level re-exports do not trigger
    # circular imports during initialization of the tmm and parameters modules.
    module_exports = {
        "ConductiveCouplings": (".conductivecouplings", "ConductiveCouplings"),
        "Coupling": (".coupling", "Coupling"),
        "CouplingMatrices": (".couplingmatrices", "CouplingMatrices"),
        "Couplings": (".couplings", "Couplings"),
        "Node": (".node", "Node"),
        "NodeType": (".node", "NodeType"),
        "Nodes": (".nodes", "Nodes"),
        "RadiativeCouplings": (".radiativecouplings", "RadiativeCouplings"),
        "ThermalData": (".thermaldata", "ThermalData"),
        "ThermalMathematicalModel": (".thermalmathematicalmodel", "ThermalMathematicalModel"),
        "ThermalNetwork": (".thermalnetwork", "ThermalNetwork"),
    }

    if name not in module_exports:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)

    module_name, attr_name = module_exports[name]
    value = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = value
    return value
