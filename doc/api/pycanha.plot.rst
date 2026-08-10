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

The interactive viewer
----------------------

:func:`explore` opens a desktop window on a model — geometry tree, hide/show,
switchable colouring, picking and a property pane — and returns when it is
closed. It is also reachable as ``tm.explore()`` and ``tm.gmm.explore()``.

.. autofunction:: explore

.. autoclass:: ViewerWindow
   :members: coloring, highlight, rebuild_geometry, current_property

The viewer keeps everything except its widgets free of Qt, so what it shows can
be inspected — and tested — without a display.
:class:`~pycanha.plot.state.ViewState` holds what is currently shown,
:class:`~pycanha.plot.scene.Scene` turns that into the cells VTK draws, and
:func:`face_properties` supplies the values they are coloured by.

.. autoclass:: ViewState
   :members:

.. autoclass:: Selection
   :members:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: ColorScale
   :members:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: PickerMode
   :members:

.. autoclass:: Change
   :members:

.. autoclass:: Scene
   :members:

.. autofunction:: face_properties

.. autoclass:: FaceProperty
   :members:
   :exclude-members: __dict__, __weakref__, __module__

The :mod:`pycanha.plot.polydata`, :mod:`pycanha.plot.picking`,
:mod:`pycanha.plot.state`, :mod:`pycanha.plot.scene` and
:mod:`pycanha.plot.properties` submodules hold the rest of the helpers.
