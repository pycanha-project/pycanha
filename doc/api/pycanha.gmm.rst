:mod:`pycanha.gmm` — Geometrical Mathematical Model
===================================================

.. currentmodule:: pycanha.gmm

Primitives, the model that holds them and their thermal mesh. See
:doc:`/user_guide/geometry` for how these fit together, and :doc:`pycanha.plot`
for the visualization helpers.

Several names here are re-exported from :mod:`pycanha_core.gmm` unchanged:
:class:`~pycanha_core.gmm.ThermalMesh`, :class:`~pycanha_core.gmm.ActiveSide`,
:class:`~pycanha_core.gmm.OpticalMaterial`,
:class:`~pycanha_core.gmm.BulkMaterial`, :class:`~pycanha_core.gmm.Color`,
:class:`~pycanha_core.gmm.MeshOptions`, :class:`~pycanha_core.gmm.UvMesher`,
:class:`~pycanha_core.gmm.Geometry`, :class:`~pycanha_core.gmm.TriMeshD` and
:class:`~pycanha_core.gmm.TriMeshF`. They are documented on the
:doc:`pycanha_core.gmm` page.

Model
-----

.. autoclass:: GeometryModel
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.gmm.GeometryModel
   :exclude-members: __dict__, __weakref__, __module__

Groups and items
----------------

.. autoclass:: GeometryItem
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.gmm.GeometryItem
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: GeometryGroup
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.gmm.GeometryGroup
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: GeometryGroupCutted
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.gmm.GeometryGroupCutted
   :exclude-members: __dict__, __weakref__, __module__

Primitives
----------

.. autoclass:: Triangle
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.gmm.Triangle
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Rectangle
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.gmm.Rectangle
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Quadrilateral
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.gmm.Quadrilateral
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Disc
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.gmm.Disc
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Cylinder
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.gmm.Cylinder
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Cone
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.gmm.Cone
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Sphere
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.gmm.Sphere
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Paraboloid
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.gmm.Paraboloid
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: Cube
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.gmm.Cube
   :exclude-members: __dict__, __weakref__, __module__

.. autofunction:: is_closed_solid

Transformations
---------------

.. autoclass:: CoordinateTransformation
   :members:
   :show-inheritance:
   :inherited-members: pycanha_core.gmm.CoordinateTransformation
   :exclude-members: __dict__, __weakref__, __module__

Thermal mesh helpers
--------------------

.. autofunction:: active_side

.. autofunction:: active_sides

.. autofunction:: with_side

Import and export
-----------------

Reached as ``model.io``. Documented on the :doc:`pycanha.io` page.

Plotting
--------

The ``plot*`` methods of :class:`GeometryModel` above are the usual way to look
at a model. Everything they build on - the pyvista conversion, the value-mapping
helpers, picking and the interactive viewer - lives in :doc:`pycanha.plot`.

The :mod:`pycanha.gmm.ops` and :mod:`pycanha.gmm.mesh` submodules hold the
geometry-operation and meshing helpers.
