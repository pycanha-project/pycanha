"""
Groups and items
================

One model built from several primitives, organised into nested
``GeometryGroup`` objects. Each item has its own mesh density and its own node
numbering.

``print_tree()`` prints the model structure. The plot gives each item a
distinct color, with the mesh edges hidden.
"""

# %%
# Build the model
# ---------------

import numpy as np
import pycanha_core as pcc

import pycanha as pc
from pycanha import gmm

pcc.set_logger_level(pcc.LogLevel.WARN)

TAU = 2 * np.pi


def simple_mesh(a=3, b=3):
    """A ThermalMesh with an a by b subdivision."""
    return gmm.ThermalMesh(list(np.linspace(0, 1, a)), list(np.linspace(0, 1, b)))


def item(name, primitive, mesh, node_start):
    mesh.node1_start = node_start
    mesh.node2_start = node_start
    mesh.node1_step = 1  # one node number per face
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
# The structure
# -------------
#
# ``print_tree`` shows every group and item with its primitive, mesh size and
# node number range.

tm.gmm.print_tree()

# %%
# One color per item, edges hidden
# ---------------------------------
#
# ``scalars="item"`` colors by item instead of by a numeric scale.
# ``show_edges=False`` hides the triangulation.

print(f"triangulation: {tm.gmm.mesh.nt()} triangles")
tm.gmm.plot(scalars="item", show_edges=False, off_screen=True)
