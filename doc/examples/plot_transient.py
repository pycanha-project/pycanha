"""
Transient two-node model
========================

A diffusive node with an internal heat load heats up against a cold boundary,
through a conductive and a radiative coupling.

The run is then repeated with the conductive coupling doubled, which is the
simplest form of a sensitivity check.
"""

# %%
# Build the baseline model
# ------------------------

import matplotlib.pyplot as plt

import pycanha as pc
import pycanha.tmm as pm

tm = pc.ThermalModel("TwoNodeTransient")
tmm = tm.tmm

node1 = pm.Node(1)
node1.T = 273.0
node1.C = 1.0e4
node1.qi = 500.0

node2 = pm.Node(2)
node2.T = 3.0
node2.type = pm.NodeType.BOUNDARY

tmm.add_node(node1)
tmm.add_node(node2)
tmm.conductive_couplings.add_coupling(1, 2, 0.5)
tmm.radiative_couplings.add_coupling(1, 2, 1.0e-7)

# %%
# Solve the transient
# -------------------

start, end, dt, out_dt = 0.0, 200_000.0, 1_000.0, 5_000.0

solver = tm.solvers.tscnrlds
solver.set_simulation_time(start, end, dt, out_dt)
solver.initialize()
solver.solve()

output_model = solver.output_model
times = output_model.T.times
idx1 = tmm.nodes.get_idx_from_node_num(1)
T1 = output_model.T.values[:, idx1]

# %%
# Second run, conductive coupling doubled
# ---------------------------------------

tm2 = pc.ThermalModel("HighConductance")
tmm2 = tm2.tmm
n1b = pm.Node(1)
n1b.T = 273.0
n1b.C = 1.0e4
n1b.qi = 500.0
n2b = pm.Node(2)
n2b.T = 3.0
n2b.type = pm.NodeType.BOUNDARY
tmm2.add_node(n1b)
tmm2.add_node(n2b)
tmm2.conductive_couplings.add_coupling(1, 2, 1.0)
tmm2.radiative_couplings.add_coupling(1, 2, 1.0e-7)

solver2 = tm2.solvers.tscnrlds
solver2.set_simulation_time(start, end, dt, out_dt)
solver2.initialize()
solver2.solve()

output_model2 = solver2.output_model
T1b = output_model2.T.values[:, tmm2.nodes.get_idx_from_node_num(1)]

# %%
# Plot
# ----

fig, axes = plt.subplots(1, 2, figsize=(11, 4))

axes[0].plot(times / 3600, T1, label="$K_{L_{12}}$ = 0.5 W/K")
axes[0].plot(times / 3600, T1b, label="$K_{L_{12}}$ = 1.0 W/K")
axes[0].set_xlabel("Time [h]")
axes[0].set_ylabel("Temperature of node 1 [K]")
axes[0].set_title("Transient response")
axes[0].legend()

axes[1].plot(times / 3600, T1 - T1b)
axes[1].axhline(0, color="gray", linewidth=0.8, linestyle="--")
axes[1].set_xlabel("Time [h]")
axes[1].set_ylabel("$\Delta T$ [K]")
axes[1].set_title("$\Delta T = T(K_{L_{12}}=0.5) - T(K_{L_{12}}=1.0)$")

plt.tight_layout()
plt.show()
