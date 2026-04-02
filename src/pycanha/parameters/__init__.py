"""Parameters and formulas subpackage."""

from importlib import import_module
from typing import Any

__all__ = [
    "AttributeEntity",
    "ConductiveCouplingEntity",
    "Formula",
    "Formulas",
    "ParameterFormula",
    "Parameters",
    "RadiativeCouplingEntity",
    "ThermalEntity",
    "ValueFormula",
]


def __getattr__(name: str) -> Any:
    # Re-export on demand so importing formulas does not immediately import tmm,
    # which would otherwise create a package initialization cycle.
    module_exports = {
        "AttributeEntity": (".entity", "AttributeEntity"),
        "ConductiveCouplingEntity": (".entity", "ConductiveCouplingEntity"),
        "Formula": (".formula", "Formula"),
        "Formulas": (".formulas", "Formulas"),
        "ParameterFormula": (".formula", "ParameterFormula"),
        "Parameters": (".parameters", "Parameters"),
        "RadiativeCouplingEntity": (".entity", "RadiativeCouplingEntity"),
        "ThermalEntity": (".entity", "ThermalEntity"),
        "ValueFormula": (".formula", "ValueFormula"),
    }

    if name not in module_exports:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)

    module_name, attr_name = module_exports[name]
    value = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = value
    return value
