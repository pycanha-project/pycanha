"""PyCanha — Thermal analysis Python package built on pycanha-core."""

from importlib import import_module
from typing import Any

__all__ = [
    "NodeType",
    "gmm",
    "parameters",
    "solvers",
    "tmm",
]


def __getattr__(name: str) -> Any:
    # Import subpackages on first access so importing pycanha does not eagerly
    # pull in both tmm and parameters while they are still importing each other.
    module_exports = {
        "gmm": ".gmm",
        "parameters": ".parameters",
        "solvers": ".solvers",
        "tmm": ".tmm",
    }

    if name in module_exports:
        module = import_module(module_exports[name], __name__)
        globals()[name] = module
        return module

    if name == "NodeType":
        node_type = import_module(".tmm.node", __name__).NodeType
        globals()[name] = node_type
        return node_type

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
