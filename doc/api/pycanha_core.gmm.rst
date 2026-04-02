:mod:`pycanha_core.gmm` — Core Geometric Classes
=================================================

.. currentmodule:: pycanha_core.gmm

These are the C++ geometric primitive and mesh classes.

Enumerations
------------

.. autoclass:: TransformOrder
   :members:
   :undoc-members:

Primitives
----------

.. autoclass:: Primitive
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Triangle
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Rectangle
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Quadrilateral
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Cylinder
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Disc
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Cone
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Sphere
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

Meshes
------

.. autoclass:: ThermalMesh
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: TriMesh
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: TriMeshModel
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

Transformations
---------------

.. autoclass:: CoordinateTransformation
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

Geometry hierarchy
------------------

.. autoclass:: Geometry
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: GeometryItem
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: GeometryMeshedItem
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: GeometryGroup
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: GeometryGroupCutted
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: GeometryModel
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

Mesh utility functions
----------------------

.. autofunction:: cdt_trimesher

.. autofunction:: create_2d_rectangular_mesh

.. autofunction:: create_2d_quadrilateral_mesh

.. autofunction:: create_2d_triangular_mesh

.. autofunction:: create_2d_triangular_only_mesh
