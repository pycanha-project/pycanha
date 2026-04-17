:mod:`pycanha.parameters` — Parameters and Formulas
====================================================

.. currentmodule:: pycanha.parameters

The ``parameters`` subpackage provides the parametric study infrastructure:
named parameters, entities (references to model scalars), and formulas
(rules linking parameters to entities).

The following base classes are re-exported from :mod:`pycanha_core.parameters`
— see the :doc:`pycanha_core.parameters` page for their full documentation:

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
