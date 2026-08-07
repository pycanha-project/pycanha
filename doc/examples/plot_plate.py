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

# Mesh
Nx, Ny = 10, 10

tm = pc.ThermalModel(name="AluPlate")
tmm = tm.tmm

for j in range(1, Ny + 1):
    for i in range(1, Nx + 1):
        node_num = i + (j - 1) * Nx
        node = pm.Node(node_num)
        if i == 1 or j == 1:
            node.type = pm.NodeType.BOUNDARY
        tmm.add_node(node)

# %%
# Conductive couplings
# --------------------

coupling_value = k_Al * t_plate / (Lx / (Nx - 1))

# Horizontal
for j in range(1, Ny + 1):
    for i in range(1, Nx):
        tmm.conductive_couplings.add_coupling(
            i + (j - 1) * Nx, (i + 1) + (j - 1) * Nx, coupling_value
        )

# Vertical
for j in range(1, Ny):
    for i in range(1, Nx + 1):
        tmm.conductive_couplings.add_coupling(i + (j - 1) * Nx, i + j * Nx, coupling_value)

# %%
# Boundary temperatures
# ---------------------

for j in range(1, Ny + 1):
    for i in range(1, Nx + 1):
        node_num = i + (j - 1) * Nx
        if i == 1:
            tmm.nodes.set_T(node_num, 300.0)
        elif j == 1:
            tmm.nodes.set_T(node_num, 100.0)

# %%
# Solve and plot
# --------------

solver = tm.solvers.sslu
solver.initialize()
solver.solve()

temp_matrix = np.zeros((Ny, Nx))
for j in range(1, Ny + 1):
    for i in range(1, Nx + 1):
        temp_matrix[j - 1, i - 1] = tmm.nodes.get_T(i + (j - 1) * Nx)

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
