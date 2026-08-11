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

.. autofunction:: key_columns

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
switchable colouring, picking, results with a time slider, edge overlays and a
property pane — and returns when it is closed. It is also reachable as
``tm.explore()`` and ``tm.gmm.explore()``. See
:ref:`the user guide <the-interactive-viewer>` for what the window offers.

.. autofunction:: explore

.. autoclass:: ViewerWindow
   :members: coloring, highlight, rebuild_geometry, current_property,
             context_actions, pick_at, current_series, refresh_result,
             plot_time_history, edge_lines, visible_triangles

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

.. autoclass:: ResultSelection
   :members:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: EdgeDisplay
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

Results
-------

Where the numbers painted on the geometry come from: the ``DataModel``\ s
already stored in ``tm.tmm.thermal_data.models``, and the live node state. A
series becomes an ordinary :class:`FaceProperty`, so the legend, the colour
scale and the property table need to know nothing about results.

.. currentmodule:: pycanha.plot.results

.. autofunction:: cases

.. autofunction:: attributes

.. autofunction:: series

.. autoclass:: ResultCase
   :members:
   :exclude-members: __dict__, __weakref__, __module__

.. autoclass:: ResultSeries
   :members:
   :exclude-members: __dict__, __weakref__, __module__

.. autofunction:: slot_values

.. autofunction:: result_property

Edges
-----

.. currentmodule:: pycanha.plot.edges

One vectorised half-edge pass over the triangulation, grouped by face slot or
by geometry item. See the module documentation for the seam and crease cases a
welded mesh cannot supply.

.. autofunction:: face_edges

.. autofunction:: primitive_edges

.. autofunction:: group_boundary_edges

.. currentmodule:: pycanha.plot

The :mod:`pycanha.plot.polydata`, :mod:`pycanha.plot.picking`,
:mod:`pycanha.plot.state`, :mod:`pycanha.plot.scene`,
:mod:`pycanha.plot.properties`, :mod:`pycanha.plot.results`,
:mod:`pycanha.plot.edges` and :mod:`pycanha.plot.timehistory` submodules hold
the rest of the helpers.
