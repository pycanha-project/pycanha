"""Radiative subpackage - GPU ray-traced view factors and node aggregation.

Re-exports the compiled ``pycanha_core.radiative`` engine so user code never has
to import ``pycanha_core`` directly::

    import pycanha as pc

    if pc.radiative.is_available():
        device = pc.radiative.Device.create()
        scene = pc.radiative.RadiativeScene(device, model.mesh_parts(), model.material_table())

The engine types are re-exported verbatim: the bindings are a 1:1, policy-free
exposure of the C++ core, and since pycanha-core 0.19 its matrices already cross
as ``scipy.sparse.csr_matrix``, matching the rest of pycanha (e.g.
:meth:`pycanha.tmm.CouplingMatrices.sparse_dd_copy`).  Nothing has to be
converted on arrival.

Since pycanha-core 0.17 the engine covers geometric **view factors**, multi-bounce
**exchange factors**, **solar** absorption and **Gebhart** factors.  Since 0.19 a
:class:`TriangulationConfig` on :class:`AccumConfig` controls how mesh faces are
subdivided before they are traced.

:func:`is_available` reports whether this machine has a GPU the engine can use:
Vulkan with ray queries on Windows and Linux, and since pycanha-core 0.18 Metal
on macOS, where it needs GPU family Apple9 (M3 / M4 / A17 Pro) or newer.

A view-factor or exchange matrix has ``num_virtual_columns`` more columns than
face slots: the three trailing columns account for energy that leaves the face
set rather than reaching another face -- to space, to an inactive face, or lost
to absorption -- at ``space_column_offset``, ``inactive_column_offset`` and
``lost_column_offset`` past the last real face. A caller slicing a matrix by
face index has to stop before them.

What is stored between real faces is the symmetric **extensive** quantity
(``A_i F_ij`` for view factors), and only its **upper triangle**, matching the
coupling convention -- so a caller recovers both view factors from the face
areas rather than reading them off the matrix. ``row_sums`` is computed from the
raw estimate before any of that and is the closure check.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pycanha_core.radiative import (
        AccumConfig,
        AccumLayout,
        AggregateResult,
        Band,
        Device,
        DeviceInfo,
        ExchangeAccumulator,
        ExchangeResult,
        MaterialTable,
        MemoryEstimate,
        PartKind,
        RadiativeScene,
        ScenePart,
        SolarAccumulator,
        SolarResult,
        SolarState,
        TraceSettings,
        TraceStats,
        TriangulationConfig,
        TriangulationMode,
        VfAccumulator,
        VfResult,
        aggregate_flux,
        aggregate_matrix,
        aggregate_nodes,
        enumerate_devices,
        estimate_memory,
        gebhart_factors,
        gebhart_node_factors,
        inactive_column_offset,
        is_available,
        lost_column_offset,
        num_virtual_columns,
        space_column_offset,
    )

__all__ = [
    "AccumConfig",
    "AccumLayout",
    "AggregateResult",
    "Band",
    "Device",
    "DeviceInfo",
    "ExchangeAccumulator",
    "ExchangeResult",
    "MaterialTable",
    "MemoryEstimate",
    "PartKind",
    "RadiativeScene",
    "ScenePart",
    "SolarAccumulator",
    "SolarResult",
    "SolarState",
    "TraceSettings",
    "TraceStats",
    "TriangulationConfig",
    "TriangulationMode",
    "VfAccumulator",
    "VfResult",
    "aggregate_flux",
    "aggregate_matrix",
    "aggregate_nodes",
    "enumerate_devices",
    "estimate_memory",
    "gebhart_factors",
    "gebhart_node_factors",
    "inactive_column_offset",
    "is_available",
    "lost_column_offset",
    "num_virtual_columns",
    "space_column_offset",
]

# Engine types re-exported verbatim from the compiled pycanha_core.radiative module.
_CORE_RADIATIVE_EXPORTS = frozenset(__all__)


def __getattr__(name: str) -> Any:
    # Resolved lazily so importing pycanha does not pull in the compiled
    # radiative engine (and its Vulkan loader) unless it is actually used.
    if name in _CORE_RADIATIVE_EXPORTS:
        value = getattr(import_module("pycanha_core").radiative, name)
        globals()[name] = value
        return value

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
