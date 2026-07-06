"""
Boolean operations
==================

The boolean operation is **cutting a surface with one or more closed surface
cutters**, written with the ``-`` operator (``target - cutter``); chaining ``-``
adds more cutters. The ``+`` operator simply **groups** geometries (aggregation,
not a CSG union). Valid cutters are the closed solids: ``Cylinder``, ``Sphere``,
``Cone``, ``Cube``.

Each face is drawn in its own color.
"""

# %%
# Setup
# -----

import numpy as np
import pycanha_core as pcc

import pycanha as pc
from pycanha import gmm

pcc.set_logger_level(pcc.LogLevel.WARN)

TAU = 2 * np.pi


def simple_mesh(a=3, b=3):
    """A ThermalMesh with a small a-by-b UV subdivision."""
    return gmm.ThermalMesh(list(np.linspace(0, 1, a)), list(np.linspace(0, 1, b)))


def plate(name, a=5, b=5):
    rect = gmm.Rectangle((-1, -1, 0), (1, -1, 0), (-1, 1, 0))
    return gmm.GeometryItem(name, rect, simple_mesh(a, b))


def show(model_name, geometry):
    tm = pc.ThermalModel(model_name)
    tm.gmm.add(geometry)
    print(f"{model_name}: {tm.gmm.mesh.nt()} triangles")
    tm.gmm.plot(scalars="face_id", off_screen=True)


# %%
# A plate cut by a cylinder (a round hole)
# ----------------------------------------
hole = gmm.GeometryItem(
    "hole", gmm.Cylinder((0, 0, -1), (0, 0, 1), (0.3, 0, -1), 0.3, 0.0, TAU), gmm.ThermalMesh()
)
show("plate_minus_cylinder", plate("panel") - hole)

# %%
# A plate cut by a sphere
# -----------------------
ball = gmm.GeometryItem(
    "ball",
    gmm.Sphere((0, 0, 0), (0, 0, 1), (0.4, 0, 0), 0.4, -0.4, 0.4, 0.0, TAU),
    gmm.ThermalMesh(),
)
show("plate_minus_sphere", plate("panel") - ball)

# %%
# A plate cut by a cube
# ---------------------
box = gmm.GeometryItem("box", gmm.Cube((0, 0, 0), (0.6, 0.6, 2.0)), gmm.ThermalMesh())
show("plate_minus_cube", plate("panel") - box)

# %%
# Chained cut: a plate cut by two cylinders
# -----------------------------------------
left = gmm.GeometryItem(
    "hole_left",
    gmm.Cylinder((-0.5, 0, -1), (-0.5, 0, 1), (-0.2, 0, -1), 0.3, 0.0, TAU),
    gmm.ThermalMesh(),
)
right = gmm.GeometryItem(
    "hole_right",
    gmm.Cylinder((0.5, 0, -1), (0.5, 0, 1), (0.8, 0, -1), 0.3, 0.0, TAU),
    gmm.ThermalMesh(),
)
show("plate_minus_two_cylinders", plate("panel") - left - right)

# %%
# For contrast: ``+`` groups geometries (no cutting)
# --------------------------------------------------
#
# ``a + b`` builds a group holding both, side by side - nothing is subtracted.

a = gmm.GeometryItem("a", gmm.Rectangle((-1, -1, 0), (0, -1, 0), (-1, 1, 0)), simple_mesh())
b = gmm.GeometryItem("b", gmm.Rectangle((0.2, -1, 0), (1.2, -1, 0), (0.2, 1, 0)), simple_mesh())
group = a + b
print("group children:", [child.name for child in group.children])
show("union_group", group)
