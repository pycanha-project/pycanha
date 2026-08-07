"""
Read transient results without building a model
===============================================

``read_tmd_transient`` reads time dependent results into a named data model:
node temperatures and heat loads over time, plus the ESATAN-TMS user-defined
time dependent constants. It creates no nodes and no couplings.

The model here stays blank to make that visible.
"""

# %%
# Read into a blank model
# -----------------------

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pycanha_core as pcc

import pycanha as pc

pcc.set_logger_level(pcc.LogLevel.WARN)

# Resolve the test data path.
_cwd = Path.cwd()
_DATA = next(
    p / "tests" / "data" / "esatan" / "DISC"
    for p in (_cwd, *_cwd.parents)
    if (p / "tests" / "data" / "esatan" / "DISC").is_dir()
)
TRANSIENT = _DATA / "DISCTR_TRANSIENT.TMD"

model = pc.ThermalModel("disc")
print("nodes before:", model.tmm.nodes.num_nodes)

node_numbers = model.tmm.read_tmd_transient(str(TRANSIENT), "transient")
print("nodes after :", model.tmm.nodes.num_nodes, " (still empty)")
print("temperature columns read:", len(node_numbers))

data = model.tmm.thermal_data.models.get_model("transient")
times = np.asarray(data.T.times)
temperatures = np.asarray(data.T.values)
column_of = {node: i for i, node in enumerate(node_numbers)}

# %%
# The time dependent constants
# ----------------------------
#
# All three types are read: real, integer and character.

constants = data.constants
print("real constants:", list(constants.real_names))
print("int  constants:", list(constants.int_names))
print("char constants:", list(constants.char_names))
print("timesteps      :", constants.num_timesteps)

# %%
# A constant value at one timestep
# ---------------------------------
#
# In this model every constant holds the current time.

t = 50
print(f"time = {constants.times[t]} s\n")

real_value = np.asarray(constants.real_values)[
    t, list(constants.real_names).index("TIME_REAL_CONST_1")
]
print(f"TIME_REAL_CONST_1 = {real_value!r:>12}   type: {type(real_value).__name__}")

int_value = np.asarray(constants.int_values)[t, 0]
print(f"{constants.int_names[0]}  = {int_value!r:>12}   type: {type(int_value).__name__}")

char_value = constants.char_value(t, 0).strip()
print(f"{constants.char_names[0]} = {char_value!r:>12}   type: {type(char_value).__name__}")

# %%
# Plot the disc nodes and one constant
# ------------------------------------
#
# Three of the disc nodes, 1000 to 1099, next to ``TIME_REAL_CONST_1``.

disc_nodes = [n for n in node_numbers if 1000 <= n <= 1099]
final = {n: temperatures[-1, column_of[n]] for n in disc_nodes}
picks = [
    (max(final, key=final.get), "hottest"),
    (sorted(disc_nodes, key=lambda n: final[n])[len(disc_nodes) // 2], "median"),
    (min(final, key=final.get), "coldest"),
]

const_times = np.asarray(constants.times)
const_1 = np.asarray(constants.real_values)[
    :, list(constants.real_names).index("TIME_REAL_CONST_1")
]

fig, (ax_t, ax_c) = plt.subplots(1, 2, figsize=(12, 4.5))
for node, label in picks:
    ax_t.plot(times, temperatures[:, column_of[node]] - 273.15, label=f"node {node} ({label})")
ax_t.set_xlabel("Time [s]")
ax_t.set_ylabel("Temperature [degC]")
ax_t.set_title("Disc node temperatures")
ax_t.legend()
ax_t.grid(alpha=0.3)

ax_c.plot(const_times, const_1, color="tab:red")
ax_c.set_xlabel("Time [s]")
ax_c.set_ylabel("TIME_REAL_CONST_1")
ax_c.set_title("Time-dependent constant")
ax_c.grid(alpha=0.3)

fig.tight_layout()
plt.show()
