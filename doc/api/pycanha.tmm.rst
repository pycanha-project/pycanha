:mod:`pycanha.tmm` — Thermal Mathematical Model
================================================

.. currentmodule:: pycanha.tmm

The ``tmm`` subpackage provides the high-level classes for building and
inspecting thermal models.

The :class:`~pycanha_core.tmm.CouplingMatrices` class is re-exported from
:mod:`pycanha_core.tmm` — see the :doc:`pycanha_core.tmm` page for its
full documentation.

Model container
---------------

.. autoclass:: ThermalMathematicalModel
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.tmm.ThermalMathematicalModel
   :exclude-members: __dict__, __weakref__, __module__

Nodes
-----

.. autoclass:: Node
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.tmm.Node
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Nodes
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.tmm.Nodes
   :exclude-members: __dict__, __weakref__, __module__

.. autodata:: NodeType

Couplings
---------

.. autoclass:: Coupling
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.tmm.Coupling
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: ConductiveCouplings
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.tmm.ConductiveCouplings
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: RadiativeCouplings
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.tmm.RadiativeCouplings
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Couplings
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.tmm.Couplings
   :exclude-members: __dict__, __weakref__, __module__

Thermal network
---------------

.. autoclass:: ThermalNetwork
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.tmm.ThermalNetwork
   :exclude-members: __dict__, __weakref__, __module__

Thermal data
------------

.. autoclass:: ThermalData
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.tmm.ThermalData
   :exclude-members: __dict__, __weakref__, __module__
