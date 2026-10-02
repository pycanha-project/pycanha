:mod:`pycanha_core.gmm` — Core geometry classes
================================================

.. currentmodule:: pycanha_core.gmm

The C++ primitive, mesh and geometry classes behind :mod:`pycanha.gmm`.

Primitives
----------

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

.. autoclass:: Disc
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Cylinder
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

.. autoclass:: Paraboloid
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Cube
   :members:
   :special-members: __init__
   :show-inheritance:
   :exclude-members: __dict__, __weakref__, __module__

Thermal mesh
------------

.. autoclass:: ThermalMesh
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: ActiveSide
   :members:
   :undoc-members:

.. autoclass:: MeshOptions
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: UvMesher
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

Materials and color
--------------------

.. autoclass:: OpticalMaterial
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: BulkMaterial
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Color
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

Model structure
---------------

.. autoclass:: Geometry
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: GeometryItem
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

Face-pair geometry
------------------

Exact area and centroid of each face pair of a primitive under its thermal
mesh, from the primitive's definition rather than its triangulation. The
conduction builder takes its thermal capacities from these areas.

.. autoclass:: FacePairGeometryEvaluator
   :members:
   :special-members: __init__, __call__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: FacePairGeometry
   :members:
   :exclude-members: __dict__, __weakref__, __module__

.. autofunction:: face_pair_geometry

Transformations
---------------

.. autoclass:: CoordinateTransformation
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

Triangulation
-------------

The triangulated form of the geometry, used by the raytracer and by the
plotting. It is not the thermal mesh and carries no node numbers.

.. autoclass:: TriMeshD
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: TriMeshF
   :members:
   :special-members: __init__
   :exclude-members: __dict__, __weakref__, __module__

.. autofunction:: bounding_box

.. autofunction:: compute_areas

.. autofunction:: compute_centroids

.. autofunction:: compute_face_normals

.. autofunction:: distance

.. autofunction:: has_consistent_face_ids

.. autofunction:: is_closed_solid

.. autofunction:: is_watertight

.. autofunction:: transform
