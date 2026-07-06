"""Top-level geometry scene container with pyvista convenience methods."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pycanha_core as pcc

from . import viz

if TYPE_CHECKING:
    import pyvista as pv


class GeometryModel(pcc.gmm.GeometryModel):
    """Object-centric scene container that owns the world mesh.

    Adds pyvista convenience on top of the pycanha-core model: :meth:`plot`
    and :meth:`to_polydata` operate on the (lazily built) world mesh.
    """

    def to_polydata(self) -> pv.PolyData:
        """Return a :class:`pyvista.PolyData` of the world mesh."""
        return viz.to_polydata(self)

    def plot(self, **kwargs: Any) -> pv.Plotter:
        """Render the world mesh with pyvista (see :func:`pycanha.gmm.viz.plot`)."""
        return viz.plot(self, **kwargs)
