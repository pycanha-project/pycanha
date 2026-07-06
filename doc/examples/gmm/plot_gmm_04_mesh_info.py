"""
Plotting mesh information
=========================

A small model of two plates with controlled node numbering and distinct optical
properties. We overlay two kinds of per-face information:

1. **Node number selection**: highlight in green the faces whose tmm node
   number falls in a range (``plot_node_range``).
2. **Emissivity**: color faces by the IR emissivity of their thermal-mesh side
   (``plot(scalars="emissivity")``).
"""

# %%
# Build two plates with node numbering and optical properties
# -----------------------------------------------------------

import numpy as np
import pycanha_core as pcc

import pycanha as pc
from pycanha import gmm

pcc.set_logger_level(pcc.LogLevel.WARN)


def simple_mesh(a=3, b=3):
    """A ThermalMesh with a small a-by-b UV subdivision."""
    return gmm.ThermalMesh(list(np.linspace(0, 1, a)), list(np.linspace(0, 1, b)))


def optical(emissivity):
    mat = gmm.OpticalMaterial()
    mat.emissivity_ir = emissivity
    return mat


def plate(name, origin_x, node_start, emissivity, a=5, b=5):
    mesh = simple_mesh(a, b)
    mesh.node1_start = node_start
    mesh.node2_start = node_start
    mesh.node1_step = 1
    mesh.node2_step = 1
    mesh.side1_optical = optical(emissivity)
    mesh.side2_optical = optical(emissivity)
    rect = gmm.Rectangle((origin_x, 0, 0), (origin_x + 2, 0, 0), (origin_x, 2, 0))
    return gmm.GeometryItem(name, rect, mesh)


tm = pc.ThermalModel("mesh_info")
tm.gmm.add(plate("plate_A", 0.0, node_start=1, emissivity=0.1))  # nodes 1..16
tm.gmm.add(plate("plate_B", 2.2, node_start=17, emissivity=0.85))  # nodes 17..32

node_numbers = np.asarray(tm.gmm.to_polydata().cell_data["node_number"])
print("node numbers present:", int(node_numbers.min()), "..", int(node_numbers.max()))

# %%
# Highlight faces with node numbers 10-20
# ---------------------------------------
#
# Green = faces whose node number is in ``[10, 20]``, grey = everything else.

tm.gmm.plot_node_range(10, 20, color="green", off_screen=True)

# %%
# Color faces by emissivity
# -------------------------
#
# Plate A has emissivity 0.1, plate B has 0.85.

tm.gmm.plot(scalars="emissivity", off_screen=True)
