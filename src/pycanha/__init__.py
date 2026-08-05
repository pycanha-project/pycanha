"""PyCanha — Thermal analysis Python package built on pycanha-core."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pycanha_core as pcc

    from . import conduction, gmm, io, parameters, radiative, solvers, tmm
    from .thermalmodel import ThermalModel
    from .tmm.node import NodeType

    LogLevel = pcc.LogLevel
    Logger = pcc.Logger
    get_logger = pcc.get_logger
    get_python_logger = pcc.get_python_logger
    print_package_info = pcc.print_package_info
    set_logger_level = pcc.set_logger_level
    set_python_logger_level = pcc.set_python_logger_level


__all__ = [
    "LogLevel",
    "Logger",
    "NodeType",
    "ThermalModel",
    "conduction",
    "get_logger",
    "get_python_logger",
    "gmm",
    "io",
    "parameters",
    "print_package_info",
    "radiative",
    "set_logger_level",
    "set_python_logger_level",
    "solvers",
    "tmm",
]


def __getattr__(name: str) -> Any:
    # Import subpackages on first access so importing pycanha does not eagerly
    # pull in both tmm and parameters while they are still importing each other.
    module_exports = {
        "conduction": ".conduction",
        "gmm": ".gmm",
        "io": ".io",
        "parameters": ".parameters",
        "radiative": ".radiative",
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

    if name == "ThermalModel":
        thermal_model = import_module(".thermalmodel", __name__).ThermalModel
        globals()[name] = thermal_model
        return thermal_model

    root_exports = {
        "LogLevel",
        "Logger",
        "get_logger",
        "get_python_logger",
        "print_package_info",
        "set_logger_level",
        "set_python_logger_level",
    }

    if name in root_exports:
        value = getattr(import_module("pycanha_core"), name)
        globals()[name] = value
        return value

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
