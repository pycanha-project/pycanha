:mod:`pycanha_core.tmm` — Core Thermal Model Classes
=====================================================

.. currentmodule:: pycanha_core.tmm

These are the C++ base classes exposed via the compiled bindings.  They are
the foundation of the :mod:`pycanha.tmm` wrappers.

Enumerations
------------

.. autoclass:: NodeType
   :members:
   :undoc-members:

Nodes
-----

.. autoclass:: Node
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Nodes
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

Couplings
---------

.. autoclass:: Coupling
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: ConductiveCouplings
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: RadiativeCouplings
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Couplings
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: CouplingMatrices
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

Network and model
-----------------

.. autoclass:: ThermalNetwork
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: ThermalData
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: ThermalMathematicalModel
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: ESATANReader
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__
