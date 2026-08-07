"""
Build a thermal model from an ESATAN-TMS TMD file
=================================================

:meth:`~pycanha.ThermalModel.from_esatan_tmd` builds a complete TMM from a
``.TMD`` file: the nodes with their heat loads, and the conductive and
radiative couplings. The result is solvable.

The model is a disc in a spherical enclosure. The disc is Delrin, 100 nodes,
numbered 1000 to 1099. An internal heat load of 10 W is applied on a middle
ring, and the disc radiates to a boundary at -10 degC.

The other TMD reader, ``read_tmd_transient``, reads results without building a
model. It is the next example.
"""

# %%
# Build the model
# ---------------

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pycanha_core as pcc

import pycanha as pc

# The core logs solver progress at INFO. Quiet it for a readable output.
pcc.set_logger_level(pcc.LogLevel.WARN)

# Resolve the test data path.
_cwd = Path.cwd()
_DATA = next(
    p / "tests" / "data" / "esatan" / "DISC"
    for p in (_cwd, *_cwd.parents)
    if (p / "tests" / "data" / "esatan" / "DISC").is_dir()
)
STEADY = _DATA / "DISCTR_STEADY.TMD"

model = pc.ThermalModel.from_esatan_tmd(str(STEADY), name="disc")
nodes = model.tmm.nodes
node_numbers = [nodes.get_node_num_from_idx(i) for i in range(nodes.num_nodes)]
print(f"{nodes.num_nodes} nodes built (disc 1000-1099 + boundary 2000, 99999)")

# %%
# The couplings
# -------------
#
# ``get_coupling_value`` takes a node number pair. Conductive couplings are in
# W/K, radiative couplings in m^2.

cc = model.tmm.conductive_couplings
rc = model.tmm.radiative_couplings

print("conductive (1000, 1001) =", cc.get_coupling_value(1000, 1001), "W/K")
print("radiative  (1000, 1002) =", rc.get_coupling_value(1000, 1002), "m^2")

conductive, radiative = [], []
for a, i in enumerate(node_numbers):
    for j in node_numbers[a + 1 :]:
        g = cc.get_coupling_value(i, j)
        if g:
            conductive.append((i, j, g))
        r = rc.get_coupling_value(i, j)
        if r:
            radiative.append((i, j, r))

print(f"{len(conductive)} conductive couplings, {len(radiative)} radiative couplings")

# %%
# Solve the steady state
# ----------------------
#
# The file holds the converged ESATAN-TMS temperatures. Overwriting every
# diffusive node with a wrong value and solving again recovers them, which
# checks the network was read correctly.


def disc_temperatures_celsius():
    return {
        nodes.get_node_num_from_idx(i): nodes.get_node_from_idx(i).T - 273.15
        for i in range(nodes.num_nodes)
    }


reference = disc_temperatures_celsius()  # the stored solution

# Force every non-boundary node to 0 degC.
for i in range(nodes.num_nodes):
    if nodes.get_node_num_from_idx(i) not in (2000, 99999):
        nodes.get_node_from_idx(i).T = 273.15

solver = model.solvers.sslu
solver.max_iters = 100
solver.abstol_temp = 1e-4
solver.initialize()
solver.solve()

recovered = disc_temperatures_celsius()
max_diff = max(abs(recovered[n] - reference[n]) for n in reference)
print(f"max |recovered - reference| = {max_diff:.2e} degC")
print(f"peak disc temperature = {max(reference.values()):.2f} degC")

# %%
# Solve the transient
# -------------------
#
# Start every node at -10 degC and integrate for 10 000 s with the
# Crank-Nicolson solver.

for i in range(nodes.num_nodes):
    if nodes.get_node_num_from_idx(i) != 99999:
        nodes.get_node_from_idx(i).T = 273.15 - 10.0

solver = model.solvers.tscnrlds
solver.max_iters = 100
solver.abstol_temp = 1e-7
solver.set_simulation_time(0.0, 10000.0, 1.0, 100.0)
solver.initialize()
solver.solve()

output = solver.output_model
times = np.asarray(output.T.times)
temperatures = np.asarray(output.T.values)
column_of = {node: i for i, node in enumerate(output.node_numbers)}

# %%
# Plot three disc nodes
# ---------------------
#
# The hottest, the median and the coldest node at the end of the run.

disc_nodes = [n for n in output.node_numbers if 1000 <= n <= 1099]
final = {n: temperatures[-1, column_of[n]] for n in disc_nodes}
picks = [
    (max(final, key=final.get), "hottest"),
    (sorted(disc_nodes, key=lambda n: final[n])[len(disc_nodes) // 2], "median"),
    (min(final, key=final.get), "coldest"),
]

plt.figure(figsize=(8, 4.5))
for node, label in picks:
    plt.plot(times, temperatures[:, column_of[node]] - 273.15, label=f"node {node} ({label})")
plt.xlabel("Time [s]")
plt.ylabel("Temperature [degC]")
plt.title("Disc nodes, transient response")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()
