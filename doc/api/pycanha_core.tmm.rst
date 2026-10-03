:mod:`pycanha_core.tmm` — Core thermal model classes
=====================================================

.. currentmodule:: pycanha_core.tmm

The C++ base classes behind :mod:`pycanha.tmm`.

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

Bulk calls
----------

``add_nodes``, ``add_couplings`` and the bulk ``get_values`` / ``set_values``
take numpy arrays and return a :class:`BulkReport`.

.. autoclass:: BulkReport
   :members:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: CouplingMerge
   :members:
   :undoc-members:

.. autoclass:: NodeAttribute
   :members:
   :undoc-members:

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

ESATAN-TMS reader
-----------------

The C++ TMD reader. It is what ``engine="cpp"`` uses. See
:doc:`/import_export/esatan_results`.

.. autoclass:: ESATANReader
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__
