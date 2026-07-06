"""Triangular meshes (TriMeshD / TriMeshF) with pyvista convenience methods."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pycanha_core as pcc

from . import viz

if TYPE_CHECKING:
    import pyvista as pv


class TriMeshD(pcc.gmm.TriMeshD):
    """Triangular surface mesh with float64 vertices."""

    def to_polydata(self) -> pv.PolyData:
        """Return a :class:`pyvista.PolyData` view of this mesh."""
        return viz.to_polydata(self)

    def plot(self, **kwargs: Any) -> pv.Plotter:
        """Render this mesh with pyvista (see :func:`pycanha.gmm.viz.plot`)."""
        return viz.plot(self, **kwargs)


class TriMeshF(pcc.gmm.TriMeshF):
    """Triangular surface mesh with float32 vertices (the visualization mesh)."""

    def to_polydata(self) -> pv.PolyData:
        """Return a :class:`pyvista.PolyData` view of this mesh."""
        return viz.to_polydata(self)

    def plot(self, **kwargs: Any) -> pv.Plotter:
        """Render this mesh with pyvista (see :func:`pycanha.gmm.viz.plot`)."""
        return viz.plot(self, **kwargs)
