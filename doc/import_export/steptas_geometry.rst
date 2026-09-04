STEP-TAS geometry
=================

pycanha reads and writes STEP-TAS geometry as a
:class:`~pycanha.gmm.GeometryModel`. STEP-TAS is the space thermal application
protocol of ISO 10303, written as a ``.stp`` exchange file.

.. code-block:: python

   from pycanha.gmm import GeometryModel

   model = GeometryModel("SATELLITE")
   report = model.io.read_steptas("satellite.stp")

   print(model.format_tree())
   print(report.summary())

   model.io.write_steptas("satellite_out.stp")

The model is populated in place. The same accessor is reachable from a
:class:`~pycanha.ThermalModel` as ``tm.gmm.io.read_steptas(...)``.

Only the GMM is read. A STEP-TAS file also carries a thermal network,
radiative results, missions and material environments. Of those, only the node
number of each face is kept, as the node numbering of the primitive it belongs
to.

The import and export reports, their severities and the ``strict`` and
``on_diagnostic`` options are described in :doc:`index`.


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
     - a group. This is how a box or a prism arrives
   * - ``MGM_MESHED_PRIMITIVE_BOUNDED_SURFACE``
     - a :class:`~pycanha.gmm.GeometryItem`
   * - ``MGM_MESHED_BOOLEAN_DIFFERENCE_SURFACE``
     - a :class:`~pycanha.gmm.GeometryGroupCutted`
   * - ``MGM_HALF_SPACE_SOLID``
     - the cutter of one of those
   * - ``MGM_DISC``, ``MGM_CYLINDER``, ``MGM_CONE``, ``MGM_SPHERE``,
       ``MGM_PARABOLOID``, ``MGM_RECTANGLE``, ``MGM_TRIANGLE``,
       ``MGM_QUADRILATERAL``
     - the primitive of the same name
   * - ``MGM_SOLID_BOX``
     - a cube, used as a cutter
   * - ``MGM_SOLID_CYLINDER``, ``MGM_SOLID_CONE``, ``MGM_SOLID_SPHERE``
     - the closed primitive, used as a cutter
   * - ``MGM_AXIS_PLACEMENT``, ``MGM_TRANSLATION``,
       ``MGM_ROTATION_WITH_AXES_FIXED``
     - an item's transformation, or one step of one
   * - ``MGM_AXIS_TRANSFORMATION_SEQUENCE``
     - those steps composed, in the order the file writes them
   * - ``MGM_COLOUR_RGB``
     - a surface color
   * - ``MGM_FACE`` and ``NRF_NETWORK_NODE``
     - the node numbering of a primitive
   * - ``NRF_MATERIAL``
     - thermo-optical properties, a bulk material, or both

Anything else is reported and skipped. An unknown entity type costs that one
item and nothing more, so a file from another tool still produces most of its
geometry.

Two conversions are not one to one.

**Mesh directions.** On a surface of revolution STEP-TAS counts the axial
direction first and the circumferential one second. A
:class:`~pycanha.gmm.ThermalMesh` counts them the other way round. The reader
exchanges the two directions, and exchanges the per-face node numbers with
them.

**Thermo-optical properties.** STEP-TAS states a specularity, the fraction of
the reflected radiation that is specular, where pycanha stores the specular
reflectivity itself. STEP-TAS also splits transmission into a direct and a
diffuse part where pycanha holds one number. Both are converted. The
refractive index has no equivalent and is dropped.


What is written
---------------

``write_steptas`` produces a complete exchange file: the protocol's reference
dictionary, the geometric model, and the thermal network the face node numbers
belong to. The table above read backwards is what it emits, with two
differences.

**Items carry no placement.** A primitive is written in model coordinates, with
the transformations of everything containing it already composed into its
points. The geometry is identical either way, so a file written from a model
that was read from another file differs from its source wherever that source
placed an item instead of stating where its shape is.

**The format constrains shapes that a model does not.** A radiative active
side must name thermo-optical properties, and a notional thickness must come
with a bulk material. A rectangle's two edges must be perpendicular and a
quadrilateral must be planar. Where the model does not meet one of these, the
writer moves as little as possible. It drops the half of a pair that cannot
stand alone, or moves the one corner that has drifted, and reports what that
cost. The result is a file the format's own tools accept.

A cutter becomes a solid, and a solid has no faces. A cutter that carried
node numbers, materials or a thickness loses them and reports it. Color is the
one approximated value: the protocol's dictionary names thirty-two colors, a
mesh holds any color, and the nearest of the thirty-two is written.


Report codes on reading
-----------------------

.. code-block:: python

   report = model.io.read_steptas(path)

   print(report.summary())

   if "TAS_CUTTER_NOT_SOLID" in report.codes():
       ...                          # a cut was skipped, that primitive is too big

``TAS_NODE_ORDER_IRREGULAR``
   The file numbers a primitive's faces individually, in a sequence that a
   single start and increment cannot reproduce. The first number and the first
   increment are used. The rest are lost.

``TAS_PROPERTY_ENVIRONMENT``
   Materials are defined for several environments, such as beginning of life
   and end of life, where a mesh holds one set of values. The default is kept.

``TAS_REFRACTION_INDEX``
   A material states a refractive index, which has no equivalent.

``TAS_PARABOLOID_TRUNCATION``
   A paraboloid is truncated below. A pycanha paraboloid always reaches its
   vertex.

``TAS_CUTTER_SENSE``
   A cutter keeps what it encloses instead of removing it. That is an
   intersection and has no equivalent. The cut is skipped and the primitive it
   would have cut survives whole.

``TAS_CUTTER_NOT_SOLID``, ``TAS_CUTTER_UNSUPPORTED``
   The cutter does not enclose a volume, or is a solid this reader does not
   read.
   The primitive survives whole instead of being dropped.

``TAS_UNKNOWN_ITEM``, ``TAS_UNKNOWN_SURFACE``
   An entity type this reader does not know. That item is skipped.

``TAS_UNSUPPORTED_ITEM``, ``TAS_UNSUPPORTED_SURFACE``
   An entity type this reader knows and cannot represent, a torus for example.
   The message states which one and why.

``TAS_SIDE_NOT_NUMBERED``, ``TAS_FACE_NOT_NUMBERED``
   A side carries no node numbers, or only some of its faces do.

``TAS_CONDUCTIVE_INFERRED``
   ``active_side`` states which sides radiate. The format says nothing about
   which sides conduct, so conductive activity is inferred from the only
   conduction related information a primitive carries: a bulk material and a
   thickness to conduct through. Reported on every primitive, because an
   inferred value is worth knowing about.

The remaining codes each name the one item they concern:
``TAS_LABEL_DROPPED``, ``TAS_MATERIAL_NOT_OPTICAL``, ``TAS_BOX_NOT_ORTHOGONAL``,
``TAS_DUPLICATE_NAME``, ``TAS_EMPTY_GROUP``, ``TAS_MULTIPLE_MODELS``,
``TAS_MULTIPLE_ROOTS``, ``TAS_BAD_ENTITY``, ``TAS_BAD_MATERIAL_VALUE``,
``TAS_NO_MATERIAL_VALUES``, ``TAS_UNKNOWN_ACTIVITY`` and
``TAS_UNKNOWN_PLACEMENT``.


Report codes on writing
-----------------------

``TAS_WRITE_ACTIVE_WITHOUT_OPTICAL``
   A radiative active side names no thermo-optical properties. The format has
   no such surface, so the side is written inactive.

``TAS_CONDUCTIVE_ONLY_DROPPED``
   A side conducts without radiating. ``active_side`` names only the sides that
   radiate, so the conductive activity has nowhere to go and is not written.
   ESATAN-TMS ``"Conductive"`` surfaces arrive here.

``TAS_WRITE_THICKNESS_DROPPED``, ``TAS_WRITE_BULK_DROPPED``
   A side has a thickness without a bulk material, or a bulk material without a
   thickness. The format carries the two together or not at all, so neither is
   written.

``TAS_WRITE_CUTTER_ATTRIBUTES``
   A cutter carried node numbers, materials or a thickness. It is written
   as a solid, which has no faces to keep them on.

``TAS_WRITE_CUTTER_UNSUPPORTED``, ``TAS_WRITE_CUTTER_NOT_PRIMITIVE``
   A cutter is a primitive with no solid form in this format, or is a
   group instead of one primitive. That cut is dropped and the target is
   written uncut.

``TAS_WRITE_UNSUPPORTED_PRIMITIVE``
   A primitive with no bounded surface in this format, such as a cube used as
   geometry instead of as a cutter. It is skipped.

``TAS_WRITE_SQUARED_RECTANGLE``, ``TAS_WRITE_FLATTENED_QUADRILATERAL``
   The format's rectangle has perpendicular edges and its quadrilateral is
   planar. A model's need not be. One corner is moved onto the perpendicular,
   or into the plane of the other three, and the message states by how much.

``TAS_WRITE_STRAIGHTENED_PRISM``
   The format's triangular prism is a right one: the edge to its fourth corner
   must lie along the base's own normal, and a file whose prism leans is
   rejected as invalid. A model's prism may lean, so the fourth corner is
   dropped onto the normal, keeping the base, the height and the direction. The
   message states how far it leaned.

The remaining codes are ``TAS_WRITE_RENAMED`` when two items share a name,
``TAS_WRITE_UNKNOWN_NODE`` for something in the model that is not a geometry,
and ``TAS_WRITE_EMPTY_MODEL`` for a model with no geometry in it.
