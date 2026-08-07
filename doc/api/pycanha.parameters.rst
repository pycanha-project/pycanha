:mod:`pycanha.parameters` — Parameters and formulas
====================================================

.. currentmodule:: pycanha.parameters

Named parameters, entities that point at one scalar of the model, and formulas
that write a parameter into an entity. See
:doc:`/user_guide/parameters_formulas`.

These base classes are re-exported from :mod:`pycanha_core.parameters` and are
documented on the :doc:`pycanha_core.parameters` page:

* :class:`~pycanha_core.parameters.Entity`
* :class:`~pycanha_core.parameters.EntityType`
* :class:`~pycanha_core.parameters.Formula`

Parameters
----------

.. autoclass:: Parameters
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.parameters.Parameters
   :exclude-members: __dict__, __weakref__, __module__

Entities
--------

.. autoclass:: EntityType
   :members:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Entity
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.parameters.Entity
   :exclude-members: __dict__, __weakref__, __module__

Formulas
--------

.. autoclass:: ParameterFormula
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.parameters.ParameterFormula
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: ExpressionFormula
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.parameters.ExpressionFormula
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: ValueFormula
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.parameters.ValueFormula
   :exclude-members: __dict__, __weakref__, __module__

Formulas collection
-------------------

.. autoclass:: Formulas
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.parameters.Formulas
   :exclude-members: __dict__, __weakref__, __module__
