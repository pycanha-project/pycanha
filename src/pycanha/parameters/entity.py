"""Thermal entity types for formula bindings."""

from __future__ import annotations

import pycanha_core as pcc

ThermalEntity = pcc.parameters.ThermalEntity


class AttributeEntity(pcc.parameters.AttributeEntity):
    pass


class ConductiveCouplingEntity(pcc.parameters.ConductiveCouplingEntity):
    pass


class RadiativeCouplingEntity(pcc.parameters.RadiativeCouplingEntity):
    pass
