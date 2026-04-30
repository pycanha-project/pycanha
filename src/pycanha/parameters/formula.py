"""Formula types linking parameters to thermal entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pycanha_core as pcc

if TYPE_CHECKING:
    from collections.abc import Callable

DerivativeParameterRegistry = pcc.parameters.DerivativeParameterRegistry
Formula = pcc.parameters.Formula


class ExpressionFormula(pcc.parameters.ExpressionFormula):
    pass


class ParameterFormula(pcc.parameters.ParameterFormula):
    pass


class ValueFormula(pcc.parameters.ValueFormula):
    pass


class GeneralFormula:
    def __init__(
        self,
        value_formula: pcc.parameters.ValueFormula,
        update: Callable[[object], float],
        context_getter: Callable[[], object],
        name: str | None = None,
    ) -> None:
        self._value_formula = value_formula
        self._update = update
        self._context_getter = context_getter
        self.name = name if name is not None else value_formula.entity.string_representation()

    @property
    def entity(self) -> pcc.parameters.Entity:
        return self._value_formula.entity

    @property
    def parameter_dependencies(self) -> list[str]:
        return []

    @property
    def backing_formula(self) -> pcc.parameters.ValueFormula:
        return self._value_formula

    def compile_formula(self) -> None:
        return None

    def calculate_derivatives(self) -> None:
        return None

    def get_derivative_values(self) -> None:
        return None

    def get_value(self) -> float:
        return self._value_formula.get_value()

    def set_value(self, value: float) -> None:
        self._value_formula.set_value(float(value))
        self._value_formula.apply_formula()

    def apply_formula(self) -> None:
        value = float(self._update(self._context_getter()))
        self._value_formula.set_value(value)
        self._value_formula.apply_formula()

    def apply_compiled_formula(self) -> None:
        self.apply_formula()

    def __repr__(self) -> str:
        entity = self.entity.string_representation()
        return f"<GeneralFormula {self.name} -> {entity}>"
