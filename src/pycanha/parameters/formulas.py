"""Formula collection managed by a thermal model."""

from __future__ import annotations

from collections.abc import Callable

import pycanha_core as pcc

from .formula import GeneralFormula


class Formulas(pcc.parameters.Formulas):
    def __init__(
        self,
        network: pcc.tmm.ThermalNetwork | None = None,
        parameters: pcc.parameters.Parameters | None = None,
    ) -> None:
        if (network is None) != (parameters is None):
            msg = "network and parameters must be provided together"
            raise ValueError(msg)

        if network is None:
            super().__init__()
        else:
            assert parameters is not None
            super().__init__(network, parameters)

        self._general_formulas: list[GeneralFormula] = []
        self._tmm: pcc.tmm.ThermalMathematicalModel | None = None
        self._context: object | None = None

    def _bind_model(
        self,
        tmm: pcc.tmm.ThermalMathematicalModel,
        context: object | None = None,
    ) -> None:
        self._tmm = tmm
        self._context = tmm if context is None else context
        self._tmm.python_apply_formulas = self._apply_general_formulas

    def _get_context(self) -> object:
        if self._context is None:
            msg = "formulas are not bound to a model"
            raise RuntimeError(msg)
        return self._context

    @staticmethod
    def _entity_key(entity: pcc.parameters.Entity | str) -> str:
        if isinstance(entity, str):
            return entity
        return entity.string_representation()

    @property
    def general_formulas(self) -> list[GeneralFormula]:
        return list(self._general_formulas)

    def add_general_formula(
        self,
        entity: pcc.parameters.Entity | str,
        *,
        update: Callable[[object], float],
        initial_value: float = 0.0,
        name: str | None = None,
    ) -> GeneralFormula:
        value_formula = self.add_value_formula(entity, float(initial_value))
        value_formula.apply_formula()
        general_formula = GeneralFormula(value_formula, update, self._get_context, name=name)
        self._general_formulas.append(general_formula)
        return general_formula

    def remove_formula(self, entity: pcc.parameters.Entity | str) -> bool:
        removed = super().remove_formula(entity)
        if removed:
            entity_key = self._entity_key(entity)
            self._general_formulas = [
                formula
                for formula in self._general_formulas
                if formula.entity.string_representation() != entity_key
            ]
        return removed

    def _apply_general_formulas(self) -> None:
        for formula in self._general_formulas:
            formula.apply_formula()

    def apply_formulas(self) -> None:
        super().apply_formulas()
        self._apply_general_formulas()

    def apply_compiled_formulas(self) -> None:
        super().apply_compiled_formulas()
        self._apply_general_formulas()
