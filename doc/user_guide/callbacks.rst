Callbacks
=========

During solver execution, Python callbacks can modify model state in
response to computed temperatures — enabling control logic such as
thermostats, heater switches, or variable loads.

Setting up a callback
---------------------

Assign a Python callable (no arguments, no return value) to the model and
activate callbacks:

.. code-block:: python

   def thermostat():
       T_ctrl = tmm.nodes.get_T(5)
       if T_ctrl < 293.0:
           tmm.nodes.set_qi(5, 100.0)    # heater ON
       elif T_ctrl > 300.0:
           tmm.nodes.set_qi(5, 0.0)      # heater OFF

   tmm.python_extern_callback_transient_after_timestep = thermostat
   tmm.python_callbacks_active = True
   tmm.callbacks_active        = True

The callback fires **after every integration timestep**, giving you access
to the latest computed temperatures.

Available callback hooks
------------------------

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Attribute
     - When it fires
   * - ``python_extern_callback_solver_loop``
     - Each iteration within a solver step
   * - ``python_extern_callback_transient_time_change``
     - When the simulation time advances
   * - ``python_extern_callback_transient_after_timestep``
     - After each completed timestep (most common)

All three are ``Callable[[], None]`` — they take no arguments and return
nothing.  They interact with the model through the captured ``tmm``
reference.

Enabling / disabling callbacks
------------------------------

Two flags must both be ``True`` for Python callbacks to execute:

* ``tmm.callbacks_active`` — master switch for all callbacks (C++ and
  Python)
* ``tmm.python_callbacks_active`` — switch for Python-side callbacks only

Setting ``tmm.callbacks_active = False`` disables all callbacks (useful for
an initial steady-state solve before the transient phase).
