"""
The primitives
==============

Every primitive with a simple thermal mesh, one interactive plot each. Drag to
rotate, scroll to zoom. Each face has its own color, so side 1 and side 2 are
distinguishable.

Eight of them are surfaces and can be meshed. The ``Cube`` is a closed solid
used only as a cutter, so it has no thermal mesh.
"""

# %%
# Setup
# -----
#
# ``off_screen=True`` on the plot calls renders headlessly for the docs build;
# the interactive vtk.js scene is still embedded below.

import numpy as np
import pycanha_core as pcc
import pyvista as pv

import pycanha as pc
from pycanha import gmm

pcc.set_logger_level(pcc.LogLevel.WARN)

TAU = 2 * np.pi


def simple_mesh(a=3, b=3):
    """A ThermalMesh with a small a-by-b UV subdivision."""
    return gmm.ThermalMesh(list(np.linspace(0, 1, a)), list(np.linspace(0, 1, b)))


def show_primitive(name, primitive, mesh=None):
    """Build a one-primitive model and render it (distinct color per face)."""
    tm = pc.ThermalModel(name)
    tm.gmm.add(gmm.GeometryItem(name, primitive, mesh or simple_mesh()))
    print(f"{name}: {tm.gmm.mesh.nt()} triangles")
    tm.gmm.plot(scalars="face_id", off_screen=True)


# %%
# Triangle
# --------
show_primitive("Triangle", gmm.Triangle((0, 0, 0), (1, 0, 0), (0, 1, 0)))

# %%
# Rectangle
# ---------
show_primitive("Rectangle", gmm.Rectangle((0, 0, 0), (1, 0, 0), (0, 1, 0)))

# %%
# Quadrilateral
# -------------
show_primitive("Quadrilateral", gmm.Quadrilateral((0, 0, 0), (1, 0, 0), (1.2, 1, 0), (0, 1, 0)))

# %%
# Disc, an annular sector
# -----------------------
show_primitive("Disc", gmm.Disc((0, 0, 0), (0, 0, 1), (1, 0, 0), 0.3, 1.0, 0.0, TAU))

# %%
# Cylinder
# --------
show_primitive("Cylinder", gmm.Cylinder((0, 0, 0), (0, 0, 1), (1, 0, 0), 1.0, 0.0, TAU))

# %%
# Cone, a frustum
# ---------------
show_primitive("Cone", gmm.Cone((0, 0, 0), (0, 0, 1), (1, 0, 0), 1.0, 0.4, 0.0, TAU))

# %%
# Sphere
# ------
show_primitive("Sphere", gmm.Sphere((0, 0, 0), (0, 0, 1), (1, 0, 0), 1.0, -1.0, 1.0, 0.0, TAU))

# %%
# Paraboloid
# ----------
show_primitive("Paraboloid", gmm.Paraboloid((0, 0, 0), (0, 0, 1), (1, 0, 0), 1.0, 0.0, TAU))

# %%
# Cube, a closed solid with no thermal mesh
# -----------------------------------------
#
# A ``Cube`` cannot carry a thermal mesh, so we visualise its solid shape
# directly with pyvista using its ``center`` and ``extent``.

cube = gmm.Cube((0, 0, 0), (1, 1, 1))
print(f"Cube: closed solid, surface area = {cube.surface_area():.1f}")

box = pv.Cube(
    center=tuple(float(x) for x in cube.center),
    x_length=float(cube.extent[0]),
    y_length=float(cube.extent[1]),
    z_length=float(cube.extent[2]),
)
plotter = pv.Plotter()
plotter.add_mesh(box, color="lightsteelblue", show_edges=True)
plotter.show()
