Transient Simulation
====================

For time-dependent analyses, **pycanha** provides the
:class:`~pycanha.solvers.TSCNRLDS` solver — a Crank-Nicolson scheme with
radiative linearization and direct sparse factorization.

Setting up a transient run
--------------------------

.. code-block:: python

   from pycanha.solvers import TSCNRLDS

   solver = TSCNRLDS(tmm)
   solver.set_simulation_time(
       start_time=0.0,        # [s]
       end_time=100_000.0,    # [s]
       dtime=100.0,           # integration timestep [s]
       output_stride=1000.0,  # store results every 1000 s
   )
   solver.initialize()
   solver.solve()
   solver.deinitialize()

The ``output_stride`` controls how often results are written to the output
model.  A larger stride saves memory when the timestep is small.

Retrieving results
------------------

Transient results are stored in the model's
:class:`~pycanha.tmm.ThermalData` container as named output models:

.. code-block:: python

   output_model = tmm.thermal_data.models.get_model(solver.output_model_name)

The temperature series is exposed as a dense time series:

* ``output_model.T.times`` — time samples [s]
* ``output_model.T.values`` — temperature matrix with shape ``(n_steps, n_nodes)``

Each temperature column is ordered by **internal index**.

Use :meth:`~pycanha_core.tmm.Nodes.get_idx_from_node_num` to map user node
numbers to column indices:

.. code-block:: python

   import numpy as np
   import matplotlib.pyplot as plt

   idx1 = tmm.nodes.get_idx_from_node_num(1)

   times = output_model.T.times
   T1    = output_model.T.values[:, idx1]

   plt.plot(times / 3600, T1)
   plt.xlabel("Time [h]")
   plt.ylabel("Temperature [K]")
   plt.show()

Initial conditions
------------------

The transient solver uses the current node temperatures as initial
conditions.  Set them before calling ``initialize()``:

.. code-block:: python

   for node_num in range(1, 11):
       tmm.nodes.set_T(node_num, 273.15)   # uniform 0 °C start
