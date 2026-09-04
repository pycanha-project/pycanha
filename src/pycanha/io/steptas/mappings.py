"""What each STEP-TAS entity means as pycanha geometry, and the way back.

The tables here are the whole of the format knowledge: which attribute of a
shape is its axis and which its radius, which shapes count their mesh in the
opposite direction, and how a material's thirteen numbers become an optical and
a bulk.  Each entry states the correspondence itself, not a rule for deriving
one: which attribute of an entity carries which quantity is a fact about the
format, and there is nowhere else in this package that it is written down.

A construct absent from these tables is not an error: the reader reports it and
carries on, which is what makes a file from another tool readable at all.

Reading and writing share this module so that the two directions of a single
correspondence stay next to each other.  The write side deals in :class:`Shape`
-- an entity type and the points and measured values it is written from, all in
model coordinates -- and leaves turning that into instances to the writer, which
is the only part that has to know how a file is numbered.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, NamedTuple

import numpy as np
import pycanha_core as pcc

# Imported from the defining modules rather than from `pycanha.gmm`: a model
# reaches this package through its own `io` accessor, so going through the
# package __init__ would close an import cycle.
from pycanha.gmm.materials import BulkMaterial, Color, OpticalMaterial
from pycanha.gmm.primitives import (
    Cone,
    Cube,
    Cylinder,
    Disc,
    Paraboloid,
    Quadrilateral,
    Rectangle,
    Sphere,
    Triangle,
    TriangularPrism,
)

from .. import shapes
from .entities import FieldError

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    import numpy.typing as npt

    from .entities import Fields

__all__ = [
    "ACTIVITY",
    "PRIMITIVES",
    "REVOLVED",
    "SOLIDS",
    "UNSUPPORTED_ENTITIES",
    "Note",
    "Placed",
    "Primitive",
    "Shape",
    "activity_name",
    "bulk_of",
    "colour_of",
    "grid_cuts",
    "material_values",
    "optical_of",
    "shape_of",
    "solid_of",
]

#: A code and a message, reported by the caller against the item being built.
type Note = tuple[str, str]

Primitive = (
    Triangle
    | Rectangle
    | Quadrilateral
    | Disc
    | Cylinder
    | Cone
    | Sphere
    | Paraboloid
    | Cube
    | TriangularPrism
)
"""Every shape a STEP-TAS surface or cutting solid can become."""

#: How far from orthogonal a shape's edges may be before it is worth reporting.
_ORTHOGONALITY_TOL: Final = 1e-6

#: How far out of its own plane a corner may sit, in metres, before the same.
_PLANARITY_TOL: Final = 1e-9


class Placed(NamedTuple):
    """A closed solid whose placement is carried by its owner's transformation."""

    primitive: Primitive
    centre: npt.NDArray[np.float64]
    rotation: npt.NDArray[np.float64]


# -- geometry helpers -------------------------------------------------------


def _unit(vector: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        msg = "a zero-length direction cannot define a shape"
        raise FieldError(msg)
    return vector / norm


def _perpendicular(
    vector: npt.NDArray[np.float64], axis: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    """The component of *vector* perpendicular to *axis*.

    A shape of revolution gives its angular datum as a point, and nothing
    obliges that point to lie in the plane the angle is measured in, nor at any
    particular distance from the axis.  Only the direction within that plane is
    meaningful, so it is projected before use.
    """
    direction = _unit(axis)
    return vector - float(np.dot(vector, direction)) * direction


class _Frame(NamedTuple):
    """The origin, axis and angular datum a shape of revolution is built on."""

    origin: npt.NDArray[np.float64]
    axis: npt.NDArray[np.float64]
    datum: npt.NDArray[np.float64]


def _frame(fields: Fields, origin: int = 1, axis: int = 2, datum: int = 3) -> _Frame:
    """The three points every shape of revolution starts with."""
    start = fields.point(origin)
    direction = fields.point(axis) - start
    reference = _perpendicular(fields.point(datum) - start, direction)
    return _Frame(start, direction, reference)


# -- surfaces ---------------------------------------------------------------


def _disc(fields: Fields, notes: list[Note]) -> Primitive:
    """Centre, axis, datum, then the two radii and the sector."""
    _ = notes
    origin, axis, datum = _frame(fields)
    return Disc(
        origin,
        origin + axis,
        origin + datum,
        fields.length(4),
        fields.length(5),
        fields.angle(6),
        fields.angle(7),
    )


def _cylinder(fields: Fields, notes: list[Note]) -> Primitive:
    """The second point is the far end, so the axis carries the height."""
    _ = notes
    origin, axis, datum = _frame(fields)
    return Cylinder(
        origin,
        origin + axis,
        origin + datum,
        fields.length(4),
        fields.angle(5),
        fields.angle(6),
    )


def _cone(fields: Fields, notes: list[Note]) -> Primitive:
    """A cone is given as a frustum: two end centres and the radius at each."""
    _ = notes
    origin, axis, datum = _frame(fields)
    return Cone(
        origin,
        origin + axis,
        origin + datum,
        fields.length(4),
        fields.length(5),
        fields.angle(6),
        fields.angle(7),
    )


def _sphere(fields: Fields, notes: list[Note]) -> Primitive:
    """The truncations are axial coordinates measured from the centre."""
    _ = notes
    origin, axis, datum = _frame(fields)
    return Sphere(
        origin,
        origin + axis,
        origin + datum,
        fields.length(4),
        fields.length(5),
        fields.length(6),
        fields.angle(7),
        fields.angle(8),
    )


def _paraboloid(fields: Fields, notes: list[Note]) -> Primitive:
    """Vertex, the point at the rim height, the datum, then the rim radius.

    The sixth attribute is a *lower* truncation, measured from the vertex.
    pycanha's paraboloid always reaches its vertex, so a non-zero one is
    reported and the surface built whole.
    """
    origin, axis, datum = _frame(fields)
    lower = fields.length(5)
    if lower != 0.0:
        notes.append(
            (
                "TAS_PARABOLOID_TRUNCATION",
                f"lower truncation {lower} dropped; the surface starts at its vertex",
            )
        )
    return Paraboloid(
        origin,
        origin + axis,
        origin + datum,
        fields.length(4),
        fields.angle(6),
        fields.angle(7),
    )


def _rectangle(fields: Fields, notes: list[Note]) -> Primitive:
    """Origin corner, then one corner along each of the two mesh directions."""
    _ = notes
    return Rectangle(fields.point(1), fields.point(2), fields.point(3))


def _triangle(fields: Fields, notes: list[Note]) -> Primitive:
    _ = notes
    return Triangle(fields.point(1), fields.point(2), fields.point(3))


def _quadrilateral(fields: Fields, notes: list[Note]) -> Primitive:
    _ = notes
    return Quadrilateral(fields.point(1), fields.point(2), fields.point(3), fields.point(4))


type PrimitiveBuilder = Callable[[Fields, list[Note]], Primitive]
type SolidBuilder = Callable[[Fields, list[Note]], Placed]

#: The bounded surfaces this reader builds, by entity type.
PRIMITIVES: dict[str, PrimitiveBuilder] = {
    "MGM_DISC": _disc,
    "MGM_CYLINDER": _cylinder,
    "MGM_CONE": _cone,
    "MGM_SPHERE": _sphere,
    "MGM_PARABOLOID": _paraboloid,
    "MGM_RECTANGLE": _rectangle,
    "MGM_TRIANGLE": _triangle,
    "MGM_QUADRILATERAL": _quadrilateral,
}

#: Surfaces whose two mesh directions are the other way round from pycanha's.
#:
#: On a surface of revolution STEP-TAS counts the axial direction first and the
#: circumferential one second, where pycanha -- like the geometry these files
#: are converted from -- counts the circumference first.  A planar surface has
#: no such disagreement.  Getting this wrong transposes the mesh and, with it,
#: every node number on the surface.
REVOLVED: frozenset[str] = frozenset(
    {"MGM_DISC", "MGM_CYLINDER", "MGM_CONE", "MGM_SPHERE", "MGM_PARABOLOID"}
)


# -- solids, which appear only as cutting tools ------------------------------


def _bounded(builder: PrimitiveBuilder) -> SolidBuilder:
    """A solid that is written exactly like the surface bounding it.

    The solids of revolution repeat their surface's own parametrisation, so the
    reading is the surface's; only whether the shape encloses a volume differs,
    and the caller checks that.
    """

    def build(fields: Fields, notes: list[Note]) -> Placed:
        return Placed(builder(fields, notes), np.zeros(3), np.eye(3))

    return build


def _solid_box(fields: Fields, notes: list[Note]) -> Placed:
    """An origin corner and the three points its edges reach.

    The cube itself is axis-aligned about the local origin and its placement is
    left to the owning item's transformation, which is the only form the core's
    cube takes.
    """
    origin = fields.point(1)
    edges = [fields.point(index) - origin for index in (2, 3, 4)]
    lengths = [float(np.linalg.norm(edge)) for edge in edges]
    if min(lengths) <= 0.0:
        msg = f"a box needs three non-zero edges, got lengths {lengths}"
        raise FieldError(msg)
    directions = [edge / length for edge, length in zip(edges, lengths, strict=True)]
    skew = max(
        abs(float(np.dot(directions[first], directions[second])))
        for first, second in ((0, 1), (0, 2), (1, 2))
    )
    if skew > _ORTHOGONALITY_TOL:
        notes.append(
            (
                "TAS_BOX_NOT_ORTHOGONAL",
                f"the edges are not orthogonal (worst cosine {skew:.3g}); "
                "the solid used for cutting squares them up",
            )
        )
    return Placed(
        Cube(np.zeros(3), np.array(lengths)),
        origin + sum(edges) / 2.0,
        np.column_stack(directions),
    )


def _solid_prism(fields: Fields, notes: list[Note]) -> Placed:
    """Three base corners and the point the base is extruded to.

    The prism takes its corners in the frame they were given in, so unlike the
    box there is no placement to split out.  The base ordering STEP-TAS writes
    already puts ``P1P2 x P1P3`` along ``P1P4``, which is what the primitive
    requires; a file that does not is rejected rather than silently inverted.
    """
    _ = notes
    prism = TriangularPrism(*(fields.point(index) for index in (1, 2, 3, 4)))
    if not prism.is_valid():
        msg = (
            "a prism needs a non-degenerate base triangle and an extrusion that "
            "leaves the base plane"
        )
        raise FieldError(msg)
    return Placed(prism, np.zeros(3), np.eye(3))


#: The solids this reader builds, by entity type.
#:
#: Building one is not the same as being able to cut with it: a paraboloid is
#: written here just as its surface is, and does not enclose a volume, so the
#: caller finds that out and says so rather than this table pretending the
#: shape is unknown.
SOLIDS: dict[str, SolidBuilder] = {
    "MGM_SOLID_BOX": _solid_box,
    "MGM_SOLID_CYLINDER": _bounded(_cylinder),
    "MGM_SOLID_CONE": _bounded(_cone),
    "MGM_SOLID_SPHERE": _bounded(_sphere),
    "MGM_SOLID_PARABOLOID": _bounded(_paraboloid),
    "MGM_SOLID_TRIANGULAR_PRISM": _solid_prism,
}

#: Entities that are recognised but have no pycanha reading, with the reason.
#:
#: Naming them is what turns "never heard of it" into an explanation the reader
#: can put in a diagnostic.
UNSUPPORTED_ENTITIES: dict[str, str] = {
    "MGM_TORUS": "there is no torus primitive",
    "MGM_SOLID_TORUS": "there is no torus primitive",
    "MGM_INFINITE_SOLID_BY_PLANE": "an infinite planar cutter has no equivalent",
    "MGM_INFINITE_SOLID_CYLINDER": "an unbounded cutter has no equivalent",
    "MGM_ENCLOSURE": "cavities are a radiative concept, not geometry",
}


# -- attributes --------------------------------------------------------------

#: STEP-TAS ``active_side``, as the pair of sides it names.
#:
#: The enumeration states which sides *radiate*, so it maps to the radiative
#: activity alone; a surface's conductive activity is not in the format.
ACTIVITY: dict[str, tuple[bool, bool]] = {
    "BOTH": (True, True),
    "SIDE1": (True, False),
    "SIDE2": (False, True),
    "NONE": (False, False),
}


def colour_of(fields: Fields) -> Color:
    """An ``MGM_COLOUR_RGB`` as a stored colour.

    The channels are fractions of full scale in the file and bytes in a mesh.
    """
    channels = [round(fields.number(index, 0.0) * 255) for index in (1, 2, 3)]
    return Color(*channels)


def grid_cuts(count: int, positions: Sequence[float]) -> tuple[float, ...]:
    """One mesh direction as the cut positions pycanha stores.

    STEP-TAS gives either the positions themselves or nothing at all, and
    nothing means the direction is divided evenly.  The positions already run
    from 0 to 1 inclusive, which is the form a mesh direction is kept in, so
    the only work is inventing the even case.
    """
    if positions:
        return tuple(float(value) for value in positions)
    if count < 1:
        msg = f"a mesh direction needs at least one face, got {count}"
        raise FieldError(msg)
    return tuple(index / count for index in range(count + 1))


#: The thirteen numbers a STEP-TAS material carries, in the order it writes them.
#:
#: The five optical pairs come solar first and infra-red second, and each band
#: gives absorbed or emitted, transmitted directly, transmitted diffusely,
#: specularity and refraction index.  The last three are the bulk.
MATERIAL_ROW: Final = (
    "solar_absorb",
    "solar_transm_direct",
    "solar_transm_diffuse",
    "solar_specularity",
    "solar_refraction",
    "ir_emiss",
    "ir_transm_direct",
    "ir_transm_diffuse",
    "ir_specularity",
    "ir_refraction",
    "density",
    "specific_heat",
    "conductivity",
)


def optical_of(name: str, row: Sequence[float], notes: list[Note]) -> OpticalMaterial | None:
    """The optical half of a material row, or ``None`` if it has none.

    Two conversions are needed.  Transmission is split into a direct and a
    diffuse part here and is one number in pycanha, so the two are added.
    *Specularity* is the fraction of the reflected radiation that is specular,
    while pycanha keeps the specular reflectivity itself, so it is multiplied
    by the reflectivity the other two values imply.
    """
    values: dict[str, float] = dict(zip(MATERIAL_ROW, row, strict=False))
    optical = [values[key] for key in MATERIAL_ROW[:10]]
    if not any(optical):
        return None
    for band, key in (("solar", "solar_refraction"), ("infra-red", "ir_refraction")):
        index = values[key]
        if index not in (0.0, 1.0):
            notes.append(
                (
                    "TAS_REFRACTION_INDEX",
                    f"material '{name}' has a {band} refraction index of {index}, "
                    "which has no equivalent and is dropped",
                )
            )
    ir_emiss = values["ir_emiss"]
    ir_transm = values["ir_transm_direct"] + values["ir_transm_diffuse"]
    solar_absorb = values["solar_absorb"]
    solar_transm = values["solar_transm_direct"] + values["solar_transm_diffuse"]
    return OpticalMaterial(
        name,
        [
            ir_emiss,
            values["ir_specularity"] * max(0.0, 1.0 - ir_emiss - ir_transm),
            ir_transm,
            solar_absorb,
            values["solar_specularity"] * max(0.0, 1.0 - solar_absorb - solar_transm),
            solar_transm,
        ],
    )


def bulk_of(name: str, row: Sequence[float]) -> BulkMaterial | None:
    """The bulk half of a material row, or ``None`` if it has none.

    The argument order is the trap: the file gives density, specific heat and
    conductivity, and the constructor takes density, **conductivity**, specific
    heat.
    """
    values: dict[str, float] = dict(zip(MATERIAL_ROW, row, strict=False))
    density = values.get("density", 0.0)
    specific_heat = values.get("specific_heat", 0.0)
    conductivity = values.get("conductivity", 0.0)
    if not any((density, specific_heat, conductivity)):
        return None
    return BulkMaterial(name, density, conductivity, specific_heat)


def is_closed_solid(primitive: Primitive) -> bool:
    """Whether *primitive* bounds a volume, and so can be cut with."""
    return bool(pcc.gmm.is_closed_solid(primitive))


# -- writing ----------------------------------------------------------------


class Shape(NamedTuple):
    """One geometric entity as it is written: its type and what defines it.

    Points come first in every one of these entities, then lengths, then the
    two sweep angles, which is why three plain tuples are enough to describe
    the lot.  All of it is in model coordinates and in SI units; putting the
    values into the file's own units is the writer's business, because only it
    knows which quantity types the file declares.
    """

    kind: str
    """The entity type, such as ``MGM_DISC``."""

    points: tuple[npt.NDArray[np.float64], ...]
    """The defining points, in model coordinates."""

    lengths: tuple[float, ...] = ()
    """Radii and truncations, in metres."""

    angles: tuple[float, ...] = ()
    """The start and end of the sweep, in radians."""


def _placed(
    point: npt.ArrayLike, placement: pcc.gmm.CoordinateTransformation
) -> npt.NDArray[np.float64]:
    """Take a primitive-local point into model coordinates."""
    return np.asarray(placement.apply(np.asarray(point, dtype=np.float64)), dtype=np.float64)


def _frame_points(
    primitive: shapes.Revolved, placement: pcc.gmm.CoordinateTransformation
) -> tuple[npt.NDArray[np.float64], ...]:
    """The three points every surface of revolution is written from.

    The third one is rebuilt at unit distance rather than copied: the format
    requires the three to span an orthogonal system, and a primitive is free to
    carry a datum that is neither perpendicular to the axis nor of any
    particular length.  Only its direction ever meant anything.
    """
    origin = np.asarray(primitive.p1, dtype=np.float64)
    return (
        _placed(origin, placement),
        _placed(primitive.p2, placement),
        _placed(origin + shapes.unit_rim(primitive), placement),
    )


def _sweep(primitive: shapes.Revolved) -> tuple[float, float]:
    return float(primitive.start_angle), float(primitive.end_angle)


def _write_disc(
    primitive: pcc.gmm.Disc,
    placement: pcc.gmm.CoordinateTransformation,
    notes: list[Note],
) -> Shape:
    _ = notes
    return Shape(
        "MGM_DISC",
        _frame_points(primitive, placement),
        (float(primitive.inner_radius), float(primitive.outer_radius)),
        _sweep(primitive),
    )


def _write_cylinder(
    primitive: pcc.gmm.Cylinder,
    placement: pcc.gmm.CoordinateTransformation,
    notes: list[Note],
) -> Shape:
    _ = notes
    return Shape(
        "MGM_CYLINDER",
        _frame_points(primitive, placement),
        (float(primitive.radius),),
        _sweep(primitive),
    )


def _write_cone(
    primitive: pcc.gmm.Cone,
    placement: pcc.gmm.CoordinateTransformation,
    notes: list[Note],
) -> Shape:
    _ = notes
    return Shape(
        "MGM_CONE",
        _frame_points(primitive, placement),
        (float(primitive.radius1), float(primitive.radius2)),
        _sweep(primitive),
    )


def _write_sphere(
    primitive: pcc.gmm.Sphere,
    placement: pcc.gmm.CoordinateTransformation,
    notes: list[Note],
) -> Shape:
    _ = notes
    return Shape(
        "MGM_SPHERE",
        _frame_points(primitive, placement),
        (
            float(primitive.radius),
            float(primitive.base_truncation),
            float(primitive.apex_truncation),
        ),
        _sweep(primitive),
    )


def _write_paraboloid(
    primitive: pcc.gmm.Paraboloid,
    placement: pcc.gmm.CoordinateTransformation,
    notes: list[Note],
) -> Shape:
    _ = notes
    # The apex truncation is written as none: this surface always reaches its
    # vertex, which is the same reduction the reader reports on the way in.
    return Shape(
        "MGM_PARABOLOID",
        _frame_points(primitive, placement),
        (float(primitive.radius), 0.0),
        _sweep(primitive),
    )


def _corners(
    primitive: Any, placement: pcc.gmm.CoordinateTransformation, count: int
) -> list[npt.NDArray[np.float64]]:
    """A planar surface's corners, in model coordinates and in order."""
    return [_placed(getattr(primitive, f"p{index}"), placement) for index in range(1, count + 1)]


def _write_triangle(
    primitive: pcc.gmm.Triangle, placement: pcc.gmm.CoordinateTransformation, notes: list[Note]
) -> Shape:
    _ = notes
    return Shape("MGM_TRIANGLE", tuple(_corners(primitive, placement, 3)))


def _write_rectangle(
    primitive: pcc.gmm.Rectangle, placement: pcc.gmm.CoordinateTransformation, notes: list[Note]
) -> Shape:
    """Three corners, of which the third is squared up against the first edge.

    The format's rectangle *is* a rectangle: the two edges from the first corner
    must be perpendicular.  A model is under no such obligation, and a source
    that let a corner drift is not rare -- so the third corner is dropped onto
    the perpendicular, which shortens that edge by the drift and is what the
    format's own tools do with the same shape.
    """
    origin, along, across = _corners(primitive, placement, 3)
    squared, skew = _perpendicular_to(across - origin, along - origin)
    if skew > _ORTHOGONALITY_TOL:
        notes.append(
            (
                "TAS_WRITE_SQUARED_RECTANGLE",
                f"the two edges are not perpendicular (cosine {skew:.3g}); the format has no "
                "such rectangle, so the third corner was squared up",
            )
        )
    return Shape("MGM_RECTANGLE", (origin, along, origin + squared))


def _write_quadrilateral(
    primitive: pcc.gmm.Quadrilateral,
    placement: pcc.gmm.CoordinateTransformation,
    notes: list[Note],
) -> Shape:
    """Four corners, of which the third is dropped into the plane of the others.

    The format's quadrilateral must be planar.  The first, second and fourth
    corners are the ones that define both the surface normal and the two mesh
    directions, so the third is the one to move.

    Re-checked for 0.20, when the core quadrilateral became a real bilinear
    patch rather than the rectangle it used to be silently read as: the
    flattening **stays**.  A bilinear patch could describe a warped quad, but
    ``Quadrilateral::is_valid`` still requires the third corner to be coplanar
    with the other three, so a warped one is not a valid pycanha surface either
    and nothing is being discarded here that the model could have held.  What
    did change is that a *planar* quad is now written as the trapezoid it is,
    where before both ends of the round trip read it as a rectangle.
    """
    corners = _corners(primitive, placement, 4)
    origin, along, other, across = corners
    normal = np.cross(along - origin, across - origin)
    length = float(np.linalg.norm(normal))
    if length > 0.0:
        normal = normal / length
        offset = float(np.dot(other - origin, normal))
        if abs(offset) > _PLANARITY_TOL:
            notes.append(
                (
                    "TAS_WRITE_FLATTENED_QUADRILATERAL",
                    f"the four corners are not coplanar ({abs(offset):.3g} m out); the format "
                    "has no such surface, so the third corner was dropped into the plane",
                )
            )
        corners[2] = other - offset * normal
    return Shape("MGM_QUADRILATERAL", tuple(corners))


def _perpendicular_to(
    vector: npt.NDArray[np.float64], axis: npt.NDArray[np.float64]
) -> tuple[npt.NDArray[np.float64], float]:
    """*vector* with its component along *axis* removed, and how much that was."""
    length = float(np.linalg.norm(axis))
    if length == 0.0:
        return vector, 0.0
    unit = axis / length
    along = float(np.dot(vector, unit))
    span = float(np.linalg.norm(vector))
    return vector - along * unit, abs(along) / span if span > 0.0 else 0.0


#: What turns one primitive into the entity it is written as.
#:
#: Each writer takes one concrete primitive type and the table erases which, so
#: this is the one place the correspondence cannot be expressed -- the same
#: trade the reader's own tables make.  The notes are for what the format's own
#: constraints cost the shape, and are reported against the item that carried it.
type ShapeWriter = Callable[[Any, pcc.gmm.CoordinateTransformation, list[Note]], Shape]


def _shape_writers() -> tuple[tuple[type, ShapeWriter], ...]:
    """Built lazily so the compiled types are looked up once, at import.

    The types are the *compiled* ones, not the ``pycanha.gmm`` subclasses of
    them: a model built through either layer holds one or the other, and only
    the compiled type matches both.  A sequence rather than a mapping because
    those types are related by inheritance in places, so which check runs first
    is part of the meaning.
    """
    return (
        (pcc.gmm.Triangle, _write_triangle),
        (pcc.gmm.Rectangle, _write_rectangle),
        (pcc.gmm.Quadrilateral, _write_quadrilateral),
        (pcc.gmm.Disc, _write_disc),
        (pcc.gmm.Cylinder, _write_cylinder),
        (pcc.gmm.Sphere, _write_sphere),
        (pcc.gmm.Paraboloid, _write_paraboloid),
        (pcc.gmm.Cone, _write_cone),
    )


#: Bound after the builders exist; the order is the ``isinstance`` order.
_SHAPE_WRITERS: tuple[tuple[type, ShapeWriter], ...] = ()

#: The solid each surface becomes when the same shape is used to cut with.
#:
#: The solids of revolution repeat their surface's parametrisation exactly, so
#: one table of surface writers serves both and this only renames the entity.
_SOLID_OF: Final[dict[str, str]] = {
    "MGM_CYLINDER": "MGM_SOLID_CYLINDER",
    "MGM_CONE": "MGM_SOLID_CONE",
    "MGM_SPHERE": "MGM_SOLID_SPHERE",
    "MGM_PARABOLOID": "MGM_SOLID_PARABOLOID",
}


def shape_of(
    primitive: object, placement: pcc.gmm.CoordinateTransformation, notes: list[Note]
) -> Shape | None:
    """The bounded surface *primitive* is written as, or ``None`` if it has none."""
    for kind, write in _SHAPE_WRITERS:
        if isinstance(primitive, kind):
            return write(primitive, placement, notes)
    return None


def solid_of(
    primitive: object, placement: pcc.gmm.CoordinateTransformation, notes: list[Note]
) -> Shape | None:
    """The cutting solid *primitive* is written as, or ``None`` if it is not one.

    A box and a prism are the two solids with no surface of the same name.  The
    box is also the one whose points are not simply the primitive's: it carries
    a centre, an extent and an orientation instead of corners.
    """
    if isinstance(primitive, pcc.gmm.Cube):
        return _write_solid_box(primitive, placement)
    if isinstance(primitive, pcc.gmm.TriangularPrism):
        return _write_solid_prism(primitive, placement)
    surface = shape_of(primitive, placement, notes)
    if surface is None:
        return None
    solid = _SOLID_OF.get(surface.kind)
    return None if solid is None else surface._replace(kind=solid)


def _write_solid_box(primitive: pcc.gmm.Cube, placement: pcc.gmm.CoordinateTransformation) -> Shape:
    """A box, as one corner and the three corners next to it.

    The three edges are written right-handed: the format requires the edge to
    the fourth point to lie along the normal of the plane the other two span,
    and a cube whose orientation happens to be a reflection would otherwise be
    rejected for describing an inside-out box.
    """
    extent = np.asarray(primitive.extent, dtype=np.float64)
    frame = _matrix_of_quaternion(primitive.orientation)
    edges = [frame[:, index] * float(extent[index]) for index in range(3)]
    if float(np.dot(np.cross(edges[0], edges[1]), edges[2])) < 0.0:
        edges[0], edges[1] = edges[1], edges[0]
    origin = np.asarray(primitive.center, dtype=np.float64) - sum(edges) / 2.0
    corners = [origin, *(origin + edge for edge in edges)]
    return Shape("MGM_SOLID_BOX", tuple(_placed(corner, placement) for corner in corners))


def _write_solid_prism(
    primitive: pcc.gmm.TriangularPrism, placement: pcc.gmm.CoordinateTransformation
) -> Shape:
    """A prism, as its three base corners and the point the base extrudes to.

    The corners go out in the primitive's own order, which already satisfies the
    format's requirement that the edge to the fourth point lie on the side of the
    base plane its winding normal points to -- the same rule the reader relies on.
    """
    corners = (primitive.p1, primitive.p2, primitive.p3, primitive.p4)
    return Shape(
        "MGM_SOLID_TRIANGULAR_PRISM", tuple(_placed(corner, placement) for corner in corners)
    )


def _matrix_of_quaternion(quaternion: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """Rotation matrix for a ``(w, x, y, z)`` quaternion, its columns being the axes."""
    w, x, y, z = (float(value) for value in np.asarray(quaternion, dtype=np.float64))
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def activity_name(*, side1: bool, side2: bool) -> str:
    """Which sides radiate, as the format's enumeration.

    Only the radiative activity has a counterpart here; a side that conducts
    without radiating cannot be stated in this format at all.
    """
    for name, sides in ACTIVITY.items():
        if sides == (side1, side2):
            return name
    msg = f"no activity covers sides {side1} and {side2}"
    raise ValueError(msg)


def material_values(
    optical: pcc.gmm.OpticalMaterial | None, bulk: pcc.gmm.BulkMaterial | None
) -> dict[str, float]:
    """The thirteen numbers one material carries, by the name of each.

    The inverse of :func:`optical_of` and :func:`bulk_of`, and lossy in the one
    place they were: transmission is one number here and two in the file, so all
    of it is written as transmitted directly.  A refraction index of one says a
    material has optical properties at all -- a material with only a bulk writes
    zero there, and reads back as a bulk and nothing else.
    """
    values: dict[str, float] = dict.fromkeys(MATERIAL_ROW, 0.0)
    if optical is not None:
        row = [float(value) for value in optical.th_optical_properties]
        ir_emiss, ir_spec_refl, ir_transm, solar_absorb, solar_spec_refl, solar_transm = row
        values["ir_emiss"] = ir_emiss
        values["ir_transm_direct"] = ir_transm
        values["ir_specularity"] = _specularity(ir_spec_refl, ir_emiss + ir_transm)
        values["ir_refraction"] = 1.0
        values["solar_absorb"] = solar_absorb
        values["solar_transm_direct"] = solar_transm
        values["solar_specularity"] = _specularity(solar_spec_refl, solar_absorb + solar_transm)
        values["solar_refraction"] = 1.0
    if bulk is not None:
        values["density"] = float(bulk.density)
        values["specific_heat"] = float(bulk.specific_heat)
        values["conductivity"] = float(bulk.conductivity)
    return values


def _specularity(specular_reflectivity: float, absorbed_and_transmitted: float) -> float:
    """The specular share of what is reflected, from the reflectivity itself.

    A surface that reflects nothing has no share to state, and writing one would
    be an assertion the model never made, so it is written as zero -- which is
    also what multiplying it back out gives.
    """
    reflected = 1.0 - absorbed_and_transmitted
    return specular_reflectivity / reflected if reflected > 0.0 else 0.0


_SHAPE_WRITERS = _shape_writers()
