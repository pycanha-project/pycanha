"""
Steady state of a 2D plate
==========================

Temperature distribution of an aluminium plate held at two fixed temperatures.

* Left edge, i = 1: boundary at 300 K
* Bottom edge, j = 1: boundary at 100 K
* Right and top edges: adiabatic
* Everything else: diffusive
"""

# %%
# Building the model
# ------------------
#
# A 10 by 10 grid of nodes. The conductive couplings come from the thermal
# conductivity of aluminium.

import matplotlib.pyplot as plt
import numpy as np

import pycanha as pc
import pycanha.tmm as pm

# Physical data
Lx, Ly = 1.0, 1.0  # plate dimensions [m]
t_plate = 1e-2  # thickness [m]
k_Al = 180.0  # thermal conductivity [W/(m·K)]

# Mesh: node i + (j - 1) * Nx sits at column i, row j (1-based).
Nx, Ny = 10, 10
i, j = np.meshgrid(np.arange(1, Nx + 1), np.arange(1, Ny + 1))
numbers = (i + (j - 1) * Nx).astype(np.int32)
edge = (i == 1) | (j == 1)

tm = pc.ThermalModel(name="AluPlate")
tmm = tm.tmm

# One call per node type, straight from the arrays. Boundary nodes carry their
# fixed temperature: 300 K on the left edge, 100 K on the bottom one.
tmm.add_nodes(numbers[~edge], type=pm.NodeType.DIFFUSIVE)
tmm.add_nodes(
    numbers[edge],
    type=pm.NodeType.BOUNDARY,
    T=np.where(i == 1, 300.0, 100.0)[edge],
)

# %%
# Conductive couplings
# --------------------
#
# Every horizontal and vertical neighbour pair, in one call. A call sorted by
# (smaller node, larger node) is appended as it is; any other order is sorted
# on the way in.

coupling_value = k_Al * t_plate / (Lx / (Nx - 1))

node_1 = np.concatenate([numbers[:, :-1].ravel(), numbers[:-1, :].ravel()])
node_2 = np.concatenate([numbers[:, 1:].ravel(), numbers[1:, :].ravel()])
tmm.conductive_couplings.add_couplings(node_1, node_2, np.full(node_1.size, coupling_value))

# %%
# Solve and plot
# --------------

solver = tm.solvers.sslu
solver.initialize()
solver.solve()

temp_matrix = tmm.nodes.get_values(pm.NodeAttribute.T, numbers.ravel()).reshape(Ny, Nx)

plt.figure(figsize=(6, 5))
plt.imshow(
    temp_matrix,
    cmap="viridis",
    origin="lower",
    extent=[0, Lx, 0, Ly],
    aspect="equal",
)
plt.colorbar(label="Temperature (K)")
plt.xlabel("x (m)")
plt.ylabel("y (m)")
plt.title("Aluminium plate, steady-state temperature")
plt.tight_layout()
plt.show()
