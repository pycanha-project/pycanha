Parameters and Formulas
=======================

The parameter–formula system lets you link model quantities to named
parameters, making parametric sweeps and sensitivity studies straightforward.

.. important::

   The parameter–formula system is in active development and subject to change.  
   The API described here is not stable and will likely change in future releases.


Concepts
--------

**Parameters**
   A named key–value store. Values can be changed between solver calls.

**Entities**
   A handle that points to one scalar quantity in the model — a node
   attribute or a coupling value.

**Formulas**
   A rule that writes a parameter's value into an entity when
   ``apply_formulas()`` is called.

.. important::

   Formulas are **not** auto-applied.  You must call
   ``tmm.formulas.apply_formulas()`` to propagate parameter changes to the
   model before solving.

Creating entities
-----------------

.. code-block:: python

   from pycanha.parameters import (
       AttributeEntity,
       ConductiveCouplingEntity,
       RadiativeCouplingEntity,
   )

   # Node 1's internal dissipation
   qi_entity = AttributeEntity(tmm.network, "QI", 1)

   # Conductive coupling GL(1, 2)
   gl_entity = ConductiveCouplingEntity(tmm.network, 1, 2)

   # Radiative coupling GR(2, 3)
   gr_entity = RadiativeCouplingEntity(tmm.network, 2, 3)

Each entity exposes ``get_value()`` / ``set_value()`` to read or write the
underlying model quantity directly, and ``string_representation()`` for a
human-readable label (e.g. ``"QI1"``, ``"GL(1, 2)"``).

Linking parameters to entities
------------------------------

.. code-block:: python

   from pycanha.parameters import ParameterFormula

   # Register a parameter
   tmm.parameters.add_parameter("k", 1.0)

   # Create the formula: GL(1,2) = k
   formula = ParameterFormula(gl_entity, tmm.parameters, "k")
   tmm.formulas.add_formula(formula)

Running a parameter analysis
-------------------------

.. code-block:: python

   import numpy as np
   from pycanha.solvers import SSLU

   solver = SSLU(tmm)
   solver.initialize()

   k_values = np.linspace(0.5, 10.0, 50)
   temperatures = []

   for k in k_values:
       tmm.parameters.set_parameter("k", k)
       tmm.formulas.apply_formulas()      # propagate k → GL(1,2)
       solver.solve()
       temperatures.append(tmm.nodes.get_T(1))

   solver.deinitialize()

ValueFormula
------------

:class:`~pycanha.parameters.ValueFormula` stores a fixed value inside the
formula object.  It is useful for freezing an entity at a constant that can
be changed programmatically:

.. code-block:: python

   from pycanha.parameters import ValueFormula

   vf = ValueFormula(qi_entity)
   vf.set_value(42.0)
   tmm.formulas.add_formula(vf)
   tmm.formulas.apply_formulas()
   # QI1 is now 42.0
