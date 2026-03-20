"""Formula types linking parameters to thermal entities."""

from __future__ import annotations

import pycanha_core as pcc

Formula = pcc.parameters.Formula


class ParameterFormula(pcc.parameters.ParameterFormula):
    pass


class ValueFormula(pcc.parameters.ValueFormula):
    pass
