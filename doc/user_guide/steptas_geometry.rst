STEP-TAS geometry
=================

**pycanha** reads and writes STEP-TAS geometry -- the space-thermal application
protocol of ISO 10303, written as an ISO 10303-21 exchange file (``.stp``) --
as a :class:`~pycanha.gmm.GeometryModel`.

.. important::

   Both directions are in active development and the API is not stable.

.. code-block:: python

   from pycanha.gmm import GeometryModel

   model = GeometryModel("SATELLITE")
   diagnostics = model.io.read_steptas("satellite.stp")

   print(model.format_tree())
   print(diagnostics.summary())

   model.io.write_steptas("satellite_out.stp")

The model is populated in place, and the same accessor is reachable from a
:class:`~pycanha.ThermalModel` as ``tm.gmm.io.read_steptas(...)``.

Only the geometric model is read.  A STEP-TAS file also carries a thermal
network, radiative results, missions and material environments; of those, only
the thermal node number on each face is kept, as the node numbering of the
surface it belongs to.


What is read
------------

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - STEP-TAS entity
     - becomes
   * - ``MGM_MESHED_GEOMETRIC_MODEL``
     - the model itself
   * - ``MGM_COMPOUND_MESHED_GEOMETRIC_ITEM``
     - a :class:`~pycanha.gmm.GeometryGroup`
   * - ``MGM_QUALIFIED_COMPOUND_MESHED_PRIMITIVE_BOUNDED_SURFACE``
     - a group; how a box or a prism arrives
   * - ``MGM_MESHED_PRIMITIVE_BOUNDED_SURFACE``
     - a :class:`~pycanha.gmm.GeometryItem`
   * - ``MGM_MESHED_BOOLEAN_DIFFERENCE_SURFACE``
     - a :class:`~pycanha.gmm.GeometryGroupCutted`
   * - ``MGM_HALF_SPACE_SOLID``
     - the cutting tool of one of those
   * - ``MGM_DISC``, ``MGM_CYLINDER``, ``MGM_CONE``, ``MGM_SPHERE``,
       ``MGM_PARABOLOID``, ``MGM_RECTANGLE``, ``MGM_TRIANGLE``,
       ``MGM_QUADRILATERAL``
     - the primitive of the same name
   * - ``MGM_SOLID_BOX``
     - a cube, used as a cutting tool
   * - ``MGM_SOLID_CYLINDER``, ``MGM_SOLID_CONE``, ``MGM_SOLID_SPHERE``
     - the closed shape, used as a cutting tool
   * - ``MGM_AXIS_PLACEMENT``, ``MGM_TRANSLATION``,
       ``MGM_ROTATION_WITH_AXES_FIXED``
     - an item's transformation, or one step of one
   * - ``MGM_AXIS_TRANSFORMATION_SEQUENCE``
     - those steps composed, in the order the file writes them
   * - ``MGM_COLOUR_RGB``
     - a surface colour
   * - ``MGM_FACE`` and ``NRF_NETWORK_NODE``
     - the node numbering of a surface
   * - ``NRF_MATERIAL``
     - an optical material, a bulk material, or both

Anything else is reported and skipped.  An entity type this reader has never
seen costs that one item and nothing more, which is what lets a file from
another tool still produce most of its geometry.

Two conversions are worth knowing about because they are not one-to-one:

**Mesh directions.**  On a surface of revolution STEP-TAS counts the axial
direction first and the circumferential one second, which is the other way round
from a :class:`~pycanha.gmm.ThermalMesh`.  The reader exchanges them, and
exchanges the per-face node numbers with them.

**Optical properties.**  STEP-TAS states a *specularity* -- the fraction of the
reflected radiation that is specular -- where pycanha stores the specular
reflectivity itself, and splits transmission into a direct and a diffuse part
where pycanha holds one number.  Both are converted; the refraction index has no
equivalent and is dropped with a diagnostic.


What is written
---------------

``write_steptas`` produces a complete exchange file: the protocol's reference
dictionary, the geometric model, and the thermal network the face node numbers
belong to.  The table above read backwards is what it emits, with two
differences.

**Items carry no placement.**  A primitive is written in model coordinates, with
the transformations of everything containing it already composed into its
points.  The geometry is the same either way, so a file written from a model
read out of another one will differ from its source wherever that source placed
an item rather than stating where its shape is.

**Constraints the format places on a shape and a model does not.**  A
radiatively active side must name a surface material, and a notional thickness
must come with a bulk material; a rectangle's two edges must be perpendicular
and a quadrilateral must be planar.  Where a model does not meet one of these,
the writer moves as little as it can -- dropping the half of a pair that cannot
stand alone, or moving the one corner that has drifted -- and reports what that
cost, so that what is written is a file the format's own tools accept.

A cutting tool becomes a solid, and a solid has no faces: a tool that carried
node numbers, materials or a thickness loses them, and says so.  A colour is the
one value approximated -- the protocol's dictionary names thirty-two, a mesh
holds any colour at all, and the nearest of the thirty-two is written.


Diagnostics
-----------

``read_steptas`` and ``write_steptas`` return the same kind of collector as the
other formats, with the same ``strict`` and ``on_diagnostic`` options and the
same four severities:

.. code-block:: python

   diagnostics = model.io.read_steptas(path)

   print(diagnostics.summary())     # grouped by code, with counts

   if "TAS_CUTTER_NOT_SOLID" in diagnostics.codes():
       ...                          # a cut was skipped; that shape is too big

Codes specific to this reader:

``TAS_NODE_ORDER_IRREGULAR``
   The file numbers a surface's faces individually, in a sequence a single start
   and increment cannot reproduce.  The first number and the first increment are
   used and the rest are lost.

``TAS_PROPERTY_ENVIRONMENT``
   Materials are defined for several environments -- beginning of life, end of
   life -- where a mesh holds one set of values.  The default is kept.

``TAS_REFRACTION_INDEX``
   A material states a refraction index, which has no equivalent.

``TAS_PARABOLOID_TRUNCATION``
   A paraboloid is truncated below; pycanha's always reaches its vertex.

``TAS_CUTTER_SENSE``
   A cutting tool keeps what it encloses rather than removing it, which is an
   intersection and has no equivalent.  The cut is skipped and the shape it
   would have cut survives whole.

``TAS_CUTTER_NOT_SOLID``, ``TAS_CUTTER_UNSUPPORTED``
   The tool does not enclose a volume, or is a solid with no reading here.  As
   above, the shape survives whole rather than being dropped.

``TAS_UNKNOWN_ITEM``, ``TAS_UNKNOWN_SURFACE``
   An entity type this reader has never met.  That item is skipped.

``TAS_UNSUPPORTED_ITEM``, ``TAS_UNSUPPORTED_SURFACE``
   An entity type this reader knows and has no representation for -- a torus,
   say.  The message says which, and why.

``TAS_SIDE_NOT_NUMBERED``, ``TAS_FACE_NOT_NUMBERED``
   A surface side carries no thermal nodes, or only some of its faces do.

``TAS_CONDUCTIVE_INFERRED``
   ``active_side`` states which sides *radiate* and the format says nothing
   about which conduct, so the conductive activity is inferred from the only
   conduction-related information a surface carries: a bulk material and a
   thickness to conduct through.  Reported on every surface, because a value
   that was inferred rather than read is worth knowing about.

the rest
   ``TAS_LABEL_DROPPED``, ``TAS_MATERIAL_NOT_OPTICAL``,
   ``TAS_BOX_NOT_ORTHOGONAL``, ``TAS_DUPLICATE_NAME``, ``TAS_EMPTY_GROUP``,
   ``TAS_MULTIPLE_MODELS``, ``TAS_MULTIPLE_ROOTS``, ``TAS_BAD_ENTITY``,
   ``TAS_BAD_MATERIAL_VALUE``, ``TAS_NO_MATERIAL_VALUES``,
   ``TAS_UNKNOWN_ACTIVITY`` and ``TAS_UNKNOWN_PLACEMENT``, each naming the one
   item it concerns.

A file that is not well-formed ISO 10303-21, or that holds no geometric model at
all, raises instead of reporting: there is nothing to carry on with.

Codes specific to writing:

``TAS_WRITE_ACTIVE_WITHOUT_OPTICAL``
   A side is radiatively active and names no optical material.  The format has
   no such surface, so the side is written inactive.

``TAS_CONDUCTIVE_ONLY_DROPPED``
   A side conducts without radiating.  ``active_side`` names only the sides that
   radiate, so the conductive activity has nowhere to go and is not written.
   ESATAN's ``"Conductive"`` surfaces arrive here.

``TAS_WRITE_THICKNESS_DROPPED``, ``TAS_WRITE_BULK_DROPPED``
   A side has a thickness without a bulk material, or a bulk material without a
   thickness.  The format carries the two together or not at all, so neither is
   written.

``TAS_WRITE_CUTTER_ATTRIBUTES``
   A cutting tool carried node numbers, materials or a thickness.  It is written
   as a solid, which has no faces to keep them on.

``TAS_WRITE_CUTTER_UNSUPPORTED``, ``TAS_WRITE_CUTTER_NOT_PRIMITIVE``
   A cutting tool is a shape with no solid form here, or is a group rather than
   one shape.  That cut is dropped and the shape is written uncut.

``TAS_WRITE_UNSUPPORTED_PRIMITIVE``
   A primitive with no bounded surface in this format -- a cube used as geometry
   rather than as a cutting tool.  It is skipped.

``TAS_WRITE_SQUARED_RECTANGLE``, ``TAS_WRITE_FLATTENED_QUADRILATERAL``
   The format's rectangle has perpendicular edges and its quadrilateral is
   planar, and a model's need not be.  One corner is moved onto the
   perpendicular, or into the plane of the other three, and the message says by
   how much.

the rest
   ``TAS_WRITE_RENAMED`` where two items share a name, ``TAS_WRITE_UNKNOWN_NODE``
   for something in the tree that is not a geometry, and
   ``TAS_WRITE_EMPTY_MODEL`` for a model with no geometry in it at all.


Reading and writing the file syntax directly
--------------------------------------------

The syntax layer is separate from the STEP-TAS reading and is usable on its own,
for any exchange file in the same syntax:

.. code-block:: python

   from pycanha.io.part21 import read_part21

   exchange = read_part21("satellite.stp")

   print(len(exchange))                       # how many instances
   print(exchange.kinds())                    # {entity type: count}

   for surface in exchange.of_kind("MGM_RECTANGLE"):
       corner = exchange.entity(surface.params[1])
       print(surface.id, corner.params[1:4])

It knows the file syntax and no schema, so it neither validates nor interprets:
attributes come back in the order the file wrote them, ``$`` as ``None`` and a
reference as something to resolve when you want it.

Writing goes through the same value model:

.. code-block:: python

   from pycanha.io.part21 import Record, Reference, format_entity, write_part21

   write_part21(
       "out.stp",
       header=[Record("FILE_SCHEMA", (("my_schema",),))],
       data=[format_entity(1, "MY_ENTITY", ("a name", 2.5, Reference(2), None))],
   )
