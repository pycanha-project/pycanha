Parameters and formulas
=======================

The parameter and formula system links model quantities to named values, so a
sweep or a sensitivity study changes one number instead of many.

.. important::

   This system is in active development. The API described here is not stable
   and will change.

Concepts
--------

**Parameter**
   A named value. It can be changed between solver calls.

**Entity**
   A handle to one scalar quantity in the model, a node attribute or a coupling
   value.

**Formula**
   A rule that writes into an entity when ``apply_formulas()`` is called.

.. important::

   Formulas are not applied automatically. Call
   ``tmm.formulas.apply_formulas()`` to propagate a parameter change into the
   model before solving.

Creating entities
-----------------

.. code-block:: python

   qi_entity = tmm.entities.internal_heat(1)          # internal heat load of node 1
   g_entity = tmm.entities.conductive_coupling(1, 2)
   r_entity = tmm.entities.radiative_coupling(2, 3)

:class:`~pycanha_core.tmm.EntitiesHelper` covers every node attribute:
``temperature``, ``capacity``, ``internal_heat``, ``solar_heat``,
``albedo_heat``, ``earth_ir`` and ``other_heat``, all taking a node number.
``attribute(token, node_num)`` takes the attribute token directly.

Each entity has ``get_value()`` and ``set_value()`` to read and write the model
quantity directly, and ``string_representation()`` for its label.

.. note::

   Entities also have a text form, ``"QI1"`` for the internal heat load of node
   1 and ``"GL(1, 2)"`` for a conductive coupling. That spelling is inherited
   from ESATAN-TMS. It may change, and other input languages may be added, so
   prefer the typed accessors above. ``add_formula`` currently takes the text
   form.

Linking parameters to entities
------------------------------

.. code-block:: python

   tmm.parameters.add_parameter("k", 1.0)
   tmm.formulas.add_formula("GL(1,2)", "k")

Sweeping a parameter
--------------------

.. code-block:: python

   import numpy as np

   solver = tm.solvers.sslu
   solver.initialize()

   k_values = np.linspace(0.5, 10.0, 50)
   temperatures = []

   for k in k_values:
       tmm.parameters.set_parameter("k", k)
       tmm.formulas.apply_formulas()
       solver.solve()
       temperatures.append(tmm.nodes.get_T(1))

   solver.deinitialize()

Fixed values
------------

:class:`~pycanha.parameters.ValueFormula` keeps a value inside the formula
object instead of taking it from a parameter. Use it to hold an entity at a
constant that is changed from code:

.. code-block:: python

   from pycanha.parameters import ValueFormula

   vf = ValueFormula(tmm.entity("QI1"))
   vf.set_value(42.0)
   tmm.formulas.add_formula(vf)
   tmm.formulas.apply_formulas()
