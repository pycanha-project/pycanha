Callbacks
=========

During solver execution, Python callbacks can modify model state in
response to computed temperatures — enabling control logic such as
thermostats, heater switches, or variable loads.

Setting up a callback
---------------------

Assign a Python callable that receives a callback context object and activate
callbacks on the model root:

.. code-block:: python

   def thermostat(ctx):
     T_ctrl = ctx.tmm.nodes.get_T(5)
       if T_ctrl < 293.0:
       ctx.tmm.nodes.set_qi(5, 100.0)    # heater ON
       elif T_ctrl > 300.0:
       ctx.tmm.nodes.set_qi(5, 0.0)      # heater OFF

   tm.callbacks.after_timestep = thermostat
   tm.callbacks.active = True

The callback fires **after every integration timestep**, giving you access
to the latest computed temperatures.

Available callback hooks
------------------------

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Attribute
     - When it fires
   * - ``tm.callbacks.solver_loop``
     - Each iteration within a solver step
   * - ``tm.callbacks.time_change``
     - When the simulation time advances
   * - ``tm.callbacks.after_timestep``
     - After each completed timestep (most common)

All three are ``Callable[[CallbackContext], None]``. The callback context
provides ``tm``, ``tmm``, the active ``solver``, and the current ``time``.

Enabling / disabling callbacks
------------------------------

Set ``tm.callbacks.active = False`` to disable callback execution entirely,
for example during an initial steady-state pre-solve.
