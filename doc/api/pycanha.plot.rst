:mod:`pycanha.plot` — Visualization
===================================

.. currentmodule:: pycanha.plot

Turning a geometry model into something you can look at. Two paths share one
data layer: the free functions below render in a single blocking call (and work
in a notebook), while the interactive viewer opens a desktop window with a scene
tree, visibility control and switchable coloring.

The convenient entry points are the ``plot*`` methods on
:class:`~pycanha.gmm.GeometryModel`, documented on the :doc:`pycanha.gmm` page.
Use the functions here when you have a bare ``TriMesh``, or when you want to
build the dataset and colour it yourself.

Datasets
--------

.. autofunction:: to_polydata

.. autofunction:: plot

.. autofunction:: render

.. autofunction:: build_plotter

Mapping values onto cells
-------------------------

.. autofunction:: map_node_data

.. autofunction:: map_face_data

.. autofunction:: cell_columns

.. autofunction:: categorical_colors

.. autofunction:: colorize_categorical

Picking
-------

Resolving a rendered triangle back to the face slot, node and geometry item
behind it.

.. autoclass:: FaceInfo
   :members:
   :exclude-members: __dict__, __weakref__, __module__

.. autofunction:: face_info

.. autofunction:: format_face_info

The :mod:`pycanha.plot.polydata` and :mod:`pycanha.plot.picking` submodules hold
the rest of the helpers.
