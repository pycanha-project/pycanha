Callbacks
=========

A callback is a Python function the solver calls while it runs. It can read the
computed temperatures and change the model, which is how control logic is
written: thermostats, heater switching, or loads that depend on the state.

Setting up a callback
---------------------

Assign a callable to one of the hooks and activate callbacks on the model root:

.. code-block:: python

   def thermostat(ctx):
       T_ctrl = ctx.tmm.nodes.get_T(5)
       if T_ctrl < 293.0:
           ctx.tmm.nodes.set_qi(5, 100.0)    # heater on
       elif T_ctrl > 300.0:
           ctx.tmm.nodes.set_qi(5, 0.0)      # heater off

   tm.callbacks.after_timestep = thermostat
   tm.callbacks.active = True

Hooks
-----

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Attribute
     - When it is called
   * - ``tm.callbacks.solver_loop``
     - Each iteration inside a solver step
   * - ``tm.callbacks.time_change``
     - When the simulation time advances
   * - ``tm.callbacks.after_timestep``
     - After each completed timestep. The most common one

All three are ``Callable[[CallbackContext], None]``. The context gives ``tm``,
``tmm``, the running ``solver`` and the current ``time``.

Turning callbacks off
---------------------

``tm.callbacks.active = False`` disables all of them. Use it to keep control
logic out of an initial steady-state solve.
