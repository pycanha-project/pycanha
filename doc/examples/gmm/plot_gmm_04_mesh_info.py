"""
Plotting per-face information
=============================

Two plates with controlled node numbering and different thermo-optical
properties. Four kinds of per-face information are drawn on them:

1. ``plot_node_range`` highlights the faces whose node number is in a range.
2. ``plot(scalars="emissivity")`` colors faces by the infrared emissivity of
   their side.
3. ``plot_node_data`` and ``plot_face_data`` color faces from a mapping of
   results.
4. ``plot_node_series`` adds a time slider over a transient result.

In a live window every plot is also pickable. Right-click a face, or press
``P`` with the cursor over it, and its face, side, node number, item,
thermo-optical properties and color are printed. ``pick=False`` turns that
off.
"""

# %%
# Two plates with node numbering and thermo-optical properties
# ------------------------------------------------------------

import numpy as np

import pycanha as pc
from pycanha import gmm


def simple_mesh(a=3, b=3):
    """A ThermalMesh with an a by b subdivision."""
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
# Highlight the faces of node numbers 10 to 20
# --------------------------------------------
#
# Green for the faces in the range, grey for the rest.

tm.gmm.plot_node_range(10, 20, color="green", off_screen=True)

# %%
# Color faces by emissivity
# --------------------------
#
# Plate A has emissivity 0.1, plate B has 0.85.

tm.gmm.plot(scalars="emissivity", off_screen=True)

# %%
# Color faces by a result
# ------------------------
#
# Any ``{node number: value}`` mapping is drawn on a color scale. A node
# missing from the mapping keeps the ``nan`` color.

temperatures = {node: 250.0 + 3.0 * node for node in range(1, 33)}
tm.gmm.plot_node_data(temperatures, name="T [K]", cmap="inferno", off_screen=True)

# %%
# Plot a transient result
# -----------------------
#
# ``plot_node_series`` takes a ``(len(times), len(nodes))`` array and adds a
# time slider. The color scale is fixed over the whole series so the frames
# stay comparable, and the current time is drawn in the corner. Off screen, as
# here, only the first frame is rendered.

nodes = list(range(1, 33))
times = np.linspace(0.0, 3600.0, 25)
history = 250.0 + np.outer(times / 3600.0, np.linspace(20.0, 90.0, len(nodes)))

tm.gmm.plot_node_series(
    history, nodes, times, name="T [K]", time_format="t = {time:.0f} s", off_screen=True
)
