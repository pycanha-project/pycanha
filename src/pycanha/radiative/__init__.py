"""Radiative subpackage - GPU ray-traced view factors and node aggregation.

Re-exports the compiled ``pycanha_core.radiative`` engine so user code never has
to import ``pycanha_core`` directly::

    import pycanha as pc

    if pc.radiative.is_available():
        device = pc.radiative.Device.create()
        scene = pc.radiative.RadiativeScene(device, model.mesh_parts(), model.material_table())

The engine types are re-exported verbatim (the bindings are a 1:1, policy-free
exposure of the C++ core). :func:`to_scipy` is added on top so view-factor
matrices reach user code as ``scipy.sparse.csr_matrix``, matching the rest of
pycanha (e.g. :meth:`pycanha.tmm.CouplingMatrices.sparse_dd_copy`).

In pycanha-core 0.16 the engine computes geometric **view factors** only; the
solar and exchange kernels are not part of this release, so
:func:`is_available` gating plus ``accumulate_vf`` is the whole compute surface.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

import numpy as np
from scipy.sparse import csr_matrix

if TYPE_CHECKING:
    from pycanha_core.radiative import (
        AccumConfig,
        AccumLayout,
        Band,
        Device,
        DeviceInfo,
        MaterialTable,
        PartKind,
        RadiativeScene,
        ScenePart,
        SparseF64,
        TraceSettings,
        TraceStats,
        VfAccumulator,
        VfResult,
        aggregate_flux,
        aggregate_matrix,
        aggregate_nodes,
        enumerate_devices,
        is_available,
    )

__all__ = [
    "AccumConfig",
    "AccumLayout",
    "Band",
    "Device",
    "DeviceInfo",
    "MaterialTable",
    "PartKind",
    "RadiativeScene",
    "ScenePart",
    "SparseF64",
    "TraceSettings",
    "TraceStats",
    "VfAccumulator",
    "VfResult",
    "aggregate_flux",
    "aggregate_matrix",
    "aggregate_nodes",
    "enumerate_devices",
    "is_available",
    "to_scipy",
]

# Engine types re-exported verbatim from the compiled pycanha_core.radiative module.
_CORE_RADIATIVE_EXPORTS = frozenset(__all__) - {"to_scipy"}


def to_scipy(matrix: SparseF64) -> csr_matrix:
    """Wrap a :class:`SparseF64` as a :class:`scipy.sparse.csr_matrix`.

    The engine hands back its own minimal CSR container; its ``indptr`` /
    ``indices`` / ``values`` are zero-copy views, so the scipy matrix shares the
    same buffers instead of duplicating them.
    """
    return csr_matrix(
        (np.asarray(matrix.values), np.asarray(matrix.indices), np.asarray(matrix.indptr)),
        shape=(matrix.rows, matrix.cols),
    )


def __getattr__(name: str) -> Any:
    # Resolved lazily so importing pycanha does not pull in the compiled
    # radiative engine (and its Vulkan loader) unless it is actually used.
    if name in _CORE_RADIATIVE_EXPORTS:
        value = getattr(import_module("pycanha_core").radiative, name)
        globals()[name] = value
        return value

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
