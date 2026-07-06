"""
Geometry tree and hierarchy
===========================

A single model built from several primitives organised into **nested
GeometryGroups**, each item with its own **mesh density** and explicit **tmm
node numbering**. We print the scene **hierarchy** with ``print_tree()`` and
render one interactive plot with a **distinct color per item** and the **mesh
edges hidden**.
"""

# %%
# Build the scene
# ---------------

import numpy as np
import pycanha_core as pcc

import pycanha as pc
from pycanha import gmm

pcc.set_logger_level(pcc.LogLevel.WARN)

TAU = 2 * np.pi


def simple_mesh(a=3, b=3):
    """A ThermalMesh with a small a-by-b UV subdivision."""
    return gmm.ThermalMesh(list(np.linspace(0, 1, a)), list(np.linspace(0, 1, b)))


def item(name, primitive, mesh, node_start):
    mesh.node1_start = node_start
    mesh.node2_start = node_start
    mesh.node1_step = 1  # number each face sequentially
    mesh.node2_step = 1
    return gmm.GeometryItem(name, primitive, mesh)


# Simple model: a body box (two panels), two solar panels, a dish.
body = gmm.GeometryGroup(
    "body",
    [
        item("top", gmm.Rectangle((0, 0, 1), (1, 0, 1), (0, 1, 1)), simple_mesh(3, 3), 100),
        item("bottom", gmm.Rectangle((0, 0, 0), (1, 0, 0), (0, 1, 0)), simple_mesh(2, 2), 200),
    ],
)
panels = gmm.GeometryGroup(
    "panels",
    [
        item(
            "panel_a", gmm.Rectangle((1.2, 0, 0), (2.2, 0, 0), (1.2, 1, 0)), simple_mesh(4, 2), 300
        ),
        item(
            "panel_b",
            gmm.Rectangle((-2.2, 0, 0), (-1.2, 0, 0), (-2.2, 1, 0)),
            simple_mesh(4, 2),
            400,
        ),
    ],
)
dish = item(
    "dish",
    gmm.Paraboloid((0, 0, 1.5), (0, 0, 1), (0.5, 0, 1.5), 0.5, 0.0, TAU),
    simple_mesh(3, 3),
    500,
)

tm = pc.ThermalModel("satellite")
tm.gmm.add(gmm.GeometryGroup("spacecraft", [body, panels, dish]))

# %%
# The hierarchy
# -------------
#
# ``print_tree`` shows every group / item, its primitive, mesh size and node
# range.

tm.gmm.print_tree()

# %%
# The model, one color per item, edges hidden
# -------------------------------------------
#
# ``scalars="item"`` gives each geometry item a distinct color (no numeric
# scale). ``show_edges=False`` hides the triangular mesh.

print(f"world mesh: {tm.gmm.mesh.nt()} triangles")
tm.gmm.plot(scalars="item", show_edges=False, off_screen=True)
