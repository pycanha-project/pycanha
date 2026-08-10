"""Read STEP-TAS geometry into a :class:`~pycanha.gmm.GeometryModel`.

The walk starts at the meshed geometric model, follows its items down through
the compounds and difference surfaces to the bounded surfaces at the leaves,
and turns each one into a geometry item with its mesh, materials and node
numbers.  Everything the file says that pycanha cannot hold is reported through
the diagnostic collector rather than dropped in silence.

The reader is deliberately permissive about *what* it meets and strict about
what it claims: an entity it has no reading for costs that entity a diagnostic
and nothing else, but an entity it does read is read completely, or reported
and skipped whole.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final

import numpy as np

# Imported from the defining modules rather than from `pycanha.gmm`: a model
# reaches this package through its own `io` accessor, so going through the
# package __init__ would close an import cycle.
from pycanha.gmm.scene import GeometryGroup, GeometryGroupCutted, GeometryItem
from pycanha.gmm.thermalmesh import ThermalMesh, active_side
from pycanha.gmm.transformations import CoordinateTransformation

from ..part21 import read_part21
from . import mappings
from .diagnostics import DiagnosticCollector
from .entities import FieldError, Fields, Units, node_number
from .errors import StepTasError

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    import numpy.typing as npt
    import pycanha_core as pcc

    from pycanha.gmm.materials import BulkMaterial, OpticalMaterial
    from pycanha.io.diagnostics import Diagnostic

    from ..part21 import Entity, Part21File, Value

__all__ = ["read_steptas_into"]

type Geometry = GeometryItem | GeometryGroup | GeometryGroupCutted

#: Where a meshed geometric model keeps what this reader needs.
_MODEL_ITEMS: Final = 6
_MODEL_MATERIALS: Final = 15
_MODEL_ENVIRONMENTS: Final = 16
_MODEL_PROPERTIES: Final = 17

#: Where every geometric item keeps its name and its placement.
_PLACEMENT: Final = 5
_CHILDREN: Final = 6

#: Where a meshed primitive bounded surface keeps each of its attributes.
_LABEL: Final = 1
_SHAPE: Final = 6
_ACTIVE_SIDE: Final = 7
_THICKNESS: Final = (8, 9)
_OPTICAL: Final = (10, 11)
_BULK: Final = (12, 13)
_COLOUR: Final = (14, 15)
_COUNTS: Final = (16, 17)
_GRIDS: Final = (20, 21)
_FACES: Final = (22, 23)

#: Where a difference surface keeps the shape being cut and the tool.
_CUT_TARGET: Final = 6
_CUT_TOOL: Final = 7

#: Where a half-space solid keeps its placement, the solid, and which side of
#: it is removed.
_CUTTER_PLACEMENT: Final = 3
_SOLID: Final = 4
_SENSE: Final = 5

#: The material environment pycanha keeps, when a file defines several.
_DEFAULT_ENVIRONMENT: Final = "DEFAULT"


def _describe_sides(sides: Sequence[bool]) -> str:
    """Name the sides a per-side flag is set on, for a diagnostic message."""
    active = [str(side) for side, is_set in enumerate(sides, start=1) if is_set]
    if not active:
        return "neither side"
    return f"side {' and '.join(active)}"


class _Materials:
    """The optical and bulk material each ``NRF_MATERIAL`` instance stands for."""

    def __init__(self) -> None:
        self.optical: dict[int, OpticalMaterial] = {}
        self.bulk: dict[int, BulkMaterial] = {}


class _Reader:
    """One pass over one meshed geometric model."""

    def __init__(
        self,
        model: pcc.gmm.GeometryModel,
        source: Part21File,
        diagnostics: DiagnosticCollector,
    ) -> None:
        self.model = model
        self.source = source
        self.diagnostics = diagnostics
        self.units = Units(source)
        self.materials = _Materials()
        self._built: dict[int, Geometry | None] = {}
        self._claimed: set[int] = set()
        self._names: set[str] = set()

    # -- entry point -------------------------------------------------------

    def run(self) -> None:
        """Build every item of the file's geometric model and attach the roots."""
        models = self.source.of_kind("MGM_MESHED_GEOMETRIC_MODEL")
        if not models:
            msg = "the file holds no MGM_MESHED_GEOMETRIC_MODEL, so it has no geometry to read"
            raise StepTasError(msg)
        if len(models) > 1:
            self.diagnostics.warning(
                "TAS_MULTIPLE_MODELS",
                f"the file holds {len(models)} geometric models; only the first is read",
            )
        fields = self._fields(models[0])
        self._read_materials(fields)
        items = fields.entity_list(_MODEL_ITEMS)
        for item in items:
            self._build(item)
        self._attach(items, fields.name)

    def _attach(self, items: Sequence[Entity], model_name: str) -> None:
        """Add every item that nothing else took as a child.

        Which item is the root is not asked of the file: an item no other item
        contains *is* a root, and that holds however a given tool chooses to
        nest things.
        """
        roots = [
            built
            for item in items
            if item.id not in self._claimed and (built := self._built.get(item.id)) is not None
        ]
        for root in roots:
            self.model.add(root)
        if len(roots) > 1:
            self.diagnostics.info(
                "TAS_MULTIPLE_ROOTS",
                f"{model_name or 'the model'} has {len(roots)} top-level items, "
                "all attached to the root",
            )

    # -- items -------------------------------------------------------------

    def _build(self, entity: Entity) -> Geometry | None:
        """The geometry *entity* stands for, built once and remembered."""
        if entity.id in self._built:
            return self._built[entity.id]
        # Recorded before building so that a file whose items refer to one
        # another in a cycle stops here instead of recursing forever.
        self._built[entity.id] = None
        builder = self._BUILDERS.get(entity.kind)
        if builder is None:
            reason = mappings.UNSUPPORTED_ENTITIES.get(entity.kind)
            if reason is None:
                self.diagnostics.warning(
                    "TAS_UNKNOWN_ITEM",
                    f"{entity!r} is not an item type this reader knows; it was skipped",
                    line=entity.line,
                )
            else:
                self.diagnostics.unsupported(
                    "TAS_UNSUPPORTED_ITEM", f"{entity!r}: {reason}", line=entity.line
                )
            return None
        try:
            built = builder(self, self._fields(entity))
        except FieldError as exc:
            self.diagnostics.error("TAS_BAD_ENTITY", str(exc), line=entity.line)
            return None
        self._built[entity.id] = built
        return built

    def _children_of(self, fields: Fields) -> list[Geometry]:
        built: list[Geometry] = []
        for child in fields.entity_list(_CHILDREN):
            self._claimed.add(child.id)
            geometry = self._build(child)
            if geometry is not None:
                built.append(geometry)
        return built

    def _compound(self, fields: Fields) -> Geometry | None:
        """A compound item, and a qualified one, are both plain groups."""
        children = self._children_of(fields)
        if not children:
            self.diagnostics.warning(
                "TAS_EMPTY_GROUP",
                f"{fields.entity!r} has no readable children and was skipped",
                line=fields.entity.line,
            )
            return None
        group = GeometryGroup(self._name(fields), children)
        self._place(group, fields)
        return group

    def _difference(self, fields: Fields) -> Geometry | None:
        """A boolean difference: one shape, cut by one solid tool."""
        target_entity = fields.required(_CUT_TARGET)
        self._claimed.add(target_entity.id)
        target = self._build(target_entity)
        if target is None:
            return None
        name = self._name(fields)
        cutter = self._cutter(fields.required(_CUT_TOOL), name)
        if cutter is None:
            return GeometryGroup(name, [target])
        group = GeometryGroupCutted(name, [target], [cutter])
        self._place(group, fields)
        return group

    def _cutter(self, half_space: Entity, target: str) -> GeometryItem | None:
        """The cutting tool of a difference surface, or ``None`` if unusable."""
        fields = self._fields(half_space)
        sense = fields.enum(_SENSE, "INSIDE")
        if sense != "INSIDE":
            # The other sense keeps what the tool encloses -- an intersection,
            # which the scene tree has no operation for.
            self.diagnostics.error(
                "TAS_CUTTER_SENSE",
                f"the tool cutting '{target}' keeps what it encloses ({sense}), which is not "
                "representable; the cut was skipped and the shape survives uncut",
                line=half_space.line,
            )
            return None
        solid = fields.required(_SOLID)
        builder = mappings.SOLIDS.get(solid.kind)
        if builder is None:
            reason = mappings.UNSUPPORTED_ENTITIES.get(solid.kind, "there is no such solid here")
            self.diagnostics.error(
                "TAS_CUTTER_UNSUPPORTED",
                f"'{target}' is cut by {solid.kind}: {reason}; the shape survives uncut",
                line=solid.line,
            )
            return None
        notes: list[mappings.Note] = []
        placed = builder(self._fields(solid), notes)
        name = self._name(fields)
        for code, message in notes:
            self.diagnostics.warning(code, f"'{name}': {message}", line=solid.line)
        if not mappings.is_closed_solid(placed.primitive):
            self.diagnostics.error(
                "TAS_CUTTER_NOT_SOLID",
                f"'{name}' does not bound a solid and cannot cut '{target}'",
                line=solid.line,
            )
            return None
        # A tool carries its own placement, in the slot where a meshed item
        # carries one -- and it is composed *after* the frame the solid itself
        # is built on, which for a box is the one taking the unit cube onto it.
        own = _transformation(placed.centre, placed.rotation)
        placement = fields.entity_at(_CUTTER_PLACEMENT)
        if placement is not None:
            moved = self._transform(placement)
            if moved is not None:
                own = own.compose(moved)
        return GeometryItem(name, placed.primitive, ThermalMesh(), own)

    def _surface(self, fields: Fields) -> Geometry | None:
        """A meshed primitive bounded surface: one geometry item with its mesh."""
        shape = fields.required(_SHAPE)
        builder = mappings.PRIMITIVES.get(shape.kind)
        if builder is None:
            reason = mappings.UNSUPPORTED_ENTITIES.get(shape.kind)
            code, message = (
                ("TAS_UNKNOWN_SURFACE", f"{shape.kind} is not a surface this reader knows")
                if reason is None
                else ("TAS_UNSUPPORTED_SURFACE", f"{shape.kind}: {reason}")
            )
            self.diagnostics.unsupported(
                code, f"{fields.name or shape.kind} skipped -- {message}", line=shape.line
            )
            return None
        notes: list[mappings.Note] = []
        primitive = builder(self._fields(shape), notes)
        name = self._name(fields)
        for code, message in notes:
            self.diagnostics.warning(code, f"'{name}': {message}", line=shape.line)
        item = GeometryItem(name, primitive, ThermalMesh())
        self._apply_attributes(item, fields, swapped=shape.kind in mappings.REVOLVED)
        self._place(item, fields)
        return item

    _BUILDERS: ClassVar[dict[str, Callable[[_Reader, Fields], Geometry | None]]] = {
        "MGM_COMPOUND_MESHED_GEOMETRIC_ITEM": _compound,
        "MGM_QUALIFIED_COMPOUND_MESHED_PRIMITIVE_BOUNDED_SURFACE": _compound,
        "MGM_MESHED_BOOLEAN_DIFFERENCE_SURFACE": _difference,
        "MGM_MESHED_PRIMITIVE_BOUNDED_SURFACE": _surface,
    }

    # -- surface attributes ------------------------------------------------

    def _apply_attributes(self, item: GeometryItem, fields: Fields, *, swapped: bool) -> None:
        mesh = item.thermal_mesh
        counts = self._mesh(mesh, fields, swapped=swapped)
        self._materials_of(mesh, fields)
        self._thickness(mesh, fields)
        # After the two of them: the format states only which sides radiate, so
        # the conductive activity is inferred from the material and thickness
        # they just set.
        self._activity(mesh, fields)
        self._nodes(mesh, fields, counts, swapped=swapped)
        label = fields.text(_LABEL)
        if label and label != fields.name:
            # A label equal to the surface's own name is not lost -- the name
            # keeps it -- and reporting those would bury the ones that say
            # something the name does not in a report per surface.
            self.diagnostics.info(
                "TAS_LABEL_DROPPED",
                f"'{item.name}' is labelled '{label}'; a mesh has no label to keep it in",
                line=fields.entity.line,
            )

    def _mesh(self, mesh: pcc.gmm.ThermalMesh, fields: Fields, *, swapped: bool) -> tuple[int, int]:
        """Set the two cut vectors, returning the face counts in pycanha's order."""
        counts = [int(fields.number(index, 1.0)) for index in _COUNTS]
        grids = [fields.numbers(index) for index in _GRIDS]
        if swapped:
            counts.reverse()
            grids.reverse()
        for name, count, positions in zip(("dir1_mesh", "dir2_mesh"), counts, grids, strict=True):
            setattr(mesh, name, list(mappings.grid_cuts(count, positions)))
        return counts[0], counts[1]

    def _activity(self, mesh: pcc.gmm.ThermalMesh, fields: Fields) -> None:
        """Set both activity selectors from the one thing the format states.

        ``MGM_ACTIVE_SIDE_TYPE`` says which sides *radiate*, so it sets the
        radiative selector and nothing else.  The conductive one is inferred
        from the only conduction-related information a STEP-TAS surface
        carries -- a bulk material and a thickness to conduct through -- rather
        than copied from the radiative one, which would silently drop every
        conductive-only side.
        """
        active = fields.enum(_ACTIVE_SIDE, "BOTH")
        sides = mappings.ACTIVITY.get(active)
        if sides is None:
            self.diagnostics.warning(
                "TAS_UNKNOWN_ACTIVITY",
                f"'{fields.name}' has an unknown active side '{active}'; "
                "both sides are kept active",
                line=fields.entity.line,
            )
        else:
            mesh.radiative_active_side = active_side(side1=sides[0], side2=sides[1])

        conducts = [
            getattr(mesh, f"side{side}_material") is not None
            and getattr(mesh, f"side{side}_thick") > 0.0
            for side in (1, 2)
        ]
        mesh.conductive_active_side = active_side(side1=conducts[0], side2=conducts[1])
        self.diagnostics.info(
            "TAS_CONDUCTIVE_INFERRED",
            f"'{fields.name}' conducts on {_describe_sides(conducts)}; the format states "
            "only which sides radiate, so this was inferred from the bulk material and "
            "thickness rather than read",
            line=fields.entity.line,
        )

    def _materials_of(self, mesh: pcc.gmm.ThermalMesh, fields: Fields) -> None:
        for side, optical_at, bulk_at, colour_at in zip(
            (1, 2), _OPTICAL, _BULK, _COLOUR, strict=True
        ):
            optical_entity = fields.entity_at(optical_at)
            if optical_entity is not None:
                optical = self.materials.optical.get(optical_entity.id)
                if optical is None:
                    self.diagnostics.warning(
                        "TAS_MATERIAL_NOT_OPTICAL",
                        f"'{fields.name}' surface {side} uses material "
                        f"'{self._fields(optical_entity).name}', which defines no optical values",
                        line=fields.entity.line,
                    )
                else:
                    setattr(mesh, f"side{side}_optical", optical)
            bulk_entity = fields.entity_at(bulk_at)
            if bulk_entity is not None:
                bulk = self.materials.bulk.get(bulk_entity.id)
                if bulk is not None:
                    setattr(mesh, f"side{side}_material", bulk)
            colour_entity = fields.entity_at(colour_at)
            if colour_entity is not None:
                setattr(mesh, f"side{side}_color", mappings.colour_of(self._fields(colour_entity)))

    def _thickness(self, mesh: pcc.gmm.ThermalMesh, fields: Fields) -> None:
        for side, index in zip((1, 2), _THICKNESS, strict=True):
            if fields.raw(index) is None:
                continue
            setattr(mesh, f"side{side}_thick", fields.length(index))

    def _nodes(
        self,
        mesh: pcc.gmm.ThermalMesh,
        fields: Fields,
        counts: tuple[int, int],
        *,
        swapped: bool,
    ) -> None:
        """Recover a start and a step from the node number on every face.

        STEP-TAS numbers each face on its own and pycanha numbers a surface with
        a first number and an increment, so the numbers only survive if they run
        in step across the surface.  When they do not, the surface keeps the
        first number and the mismatch is reported rather than approximated.
        """
        for side, index in zip((1, 2), _FACES, strict=True):
            faces = fields.entity_list(index)
            if not faces:
                continue
            numbers = self._face_numbers(faces, side, fields)
            if numbers is None:
                continue
            ordered = _in_pycanha_order(numbers, counts, swapped=swapped)
            start = ordered[0]
            step = ordered[1] - ordered[0] if len(ordered) > 1 else 1
            if any(value != start + position * step for position, value in enumerate(ordered)):
                self.diagnostics.error(
                    "TAS_NODE_ORDER_IRREGULAR",
                    f"'{fields.name}' surface {side} numbers its faces individually; a single "
                    f"start and increment cannot reproduce them, so {start} and {step} are used",
                    line=fields.entity.line,
                )
            setattr(mesh, f"node{side}_start", start)
            setattr(mesh, f"node{side}_step", step)

    def _face_numbers(self, faces: Sequence[Entity], side: int, fields: Fields) -> list[int] | None:
        """The thermal node number behind every face, in file order.

        A side with no numbers at all is ordinary: a surface that takes no part
        in the thermal model has nothing to number, and saying so at info level
        keeps the report about the surfaces that lost something.  A side where
        only *some* faces are numbered is the one worth a warning, because the
        surface then ends up unnumbered as a whole.
        """
        numbers: list[int] = []
        for face in faces:
            node = self._fields(face).entity_at(0)
            number = None if node is None else node_number(node)
            if number is not None:
                numbers.append(number)
        if len(numbers) == len(faces):
            return numbers
        if not numbers:
            self.diagnostics.info(
                "TAS_SIDE_NOT_NUMBERED",
                f"'{fields.name}' surface {side} carries no thermal nodes",
                line=fields.entity.line,
            )
        else:
            self.diagnostics.warning(
                "TAS_FACE_NOT_NUMBERED",
                f"'{fields.name}' surface {side} numbers {len(numbers)} of its {len(faces)} "
                "faces; a partly numbered surface is left unnumbered",
                line=fields.entity.line,
            )
        return None

    # -- placement ---------------------------------------------------------

    def _place(self, geometry: Geometry, fields: Fields) -> None:
        placement = fields.entity_at(_PLACEMENT)
        if placement is None:
            return
        transform = self._transform(placement)
        if transform is not None:
            geometry.transform = transform

    def _transform(self, entity: Entity) -> pcc.gmm.CoordinateTransformation | None:
        """The placement *entity* describes, composed if it is a sequence."""
        fields = self._fields(entity)
        if entity.kind == "MGM_AXIS_TRANSFORMATION_SEQUENCE":
            transform: pcc.gmm.CoordinateTransformation = CoordinateTransformation()
            for step in fields.entity_list(0):
                change = self._transform(step)
                if change is None:
                    return None
                transform = transform.compose(change)
            return transform
        if entity.kind == "MGM_AXIS_PLACEMENT":
            axis = fields.direction(1)
            datum = fields.direction(2)
            return _transformation(fields.point(0), _frame_matrix(axis, datum))
        if entity.kind == "MGM_ROTATION_WITH_AXES_FIXED":
            angle, unit = self.units.convert(fields.number(1), fields.raw(2))
            if unit != "radian":
                msg = f"{entity!r} states its angle in {unit or 'an unnamed unit'}"
                raise FieldError(msg)
            return _transformation(np.zeros(3), _axis_rotation(fields.direction(0), angle))
        if entity.kind == "MGM_TRANSLATION":
            offsets = []
            for axis_index in (0, 1, 2):
                value, unit = self.units.convert(fields.number(axis_index), fields.raw(3))
                if unit != "metre":
                    msg = f"{entity!r} states its offset in {unit or 'an unnamed unit'}"
                    raise FieldError(msg)
                offsets.append(value)
            return _transformation(np.array(offsets), np.eye(3))
        self.diagnostics.warning(
            "TAS_UNKNOWN_PLACEMENT",
            f"{entity!r} is not a placement this reader knows; the item stays where it is",
            line=entity.line,
        )
        return None

    # -- materials ---------------------------------------------------------

    def _read_materials(self, fields: Fields) -> None:
        """Read the material table, keeping one environment's values.

        A STEP-TAS material carries a whole row of values per *environment* --
        beginning of life, end of life, and a default -- where pycanha holds one
        set.  The default is the one kept, and the others are reported.
        """
        materials = fields.entity_list(_MODEL_MATERIALS)
        if not materials:
            return
        environments = self._environment_names(fields)
        chosen = (
            environments.index(_DEFAULT_ENVIRONMENT) if _DEFAULT_ENVIRONMENT in environments else 0
        )
        if len(environments) > 1:
            dropped = [name for index, name in enumerate(environments) if index != chosen]
            self.diagnostics.warning(
                "TAS_PROPERTY_ENVIRONMENT",
                f"materials are defined for {len(environments)} environments; only "
                f"{environments[chosen] or 'the first'} is kept, dropping {', '.join(dropped)}",
            )
        rows = fields.raw(_MODEL_PROPERTIES)
        if not isinstance(rows, tuple) or chosen >= len(rows):
            self.diagnostics.warning(
                "TAS_NO_MATERIAL_VALUES",
                "the model defines materials but no property values; only their names are known",
            )
            return
        self._store_materials(materials, rows[chosen])

    def _environment_names(self, fields: Fields) -> list[str]:
        """The material environments the model defines, in the order it lists them."""
        states = fields.entity_at(_MODEL_ENVIRONMENTS)
        if states is None:
            return []
        state_fields = self._fields(states)
        enumeration = state_fields.entity_at(0)
        items = self._fields(enumeration).entity_list(6) if enumeration is not None else []
        names: list[str] = []
        for position in state_fields.numbers(3):
            index = int(position) - 1
            names.append(self._fields(items[index]).name if 0 <= index < len(items) else "")
        return names

    def _store_materials(self, materials: Sequence[Entity], row_refs: Value) -> None:
        if not isinstance(row_refs, tuple):
            return
        for material, values in zip(materials, row_refs, strict=False):
            name = self._fields(material).name
            row = self._property_row(values)
            if row is None:
                continue
            notes: list[mappings.Note] = []
            optical = mappings.optical_of(name, row, notes)
            for code, message in notes:
                self.diagnostics.warning(code, message, line=material.line)
            if optical is not None:
                self.materials.optical[material.id] = optical
            bulk = mappings.bulk_of(name, row)
            if bulk is not None:
                self.materials.bulk[material.id] = bulk

    def _property_row(self, values: Value) -> list[float] | None:
        if not isinstance(values, tuple):
            return None
        row: list[float] = []
        for reference in values:
            literal = self.source.entity(reference)
            if literal is None:
                return None
            try:
                row.append(self.units.literal(literal)[0])
            except FieldError as exc:
                self.diagnostics.warning("TAS_BAD_MATERIAL_VALUE", str(exc), line=literal.line)
                return None
        return row

    # -- helpers -----------------------------------------------------------

    def _fields(self, entity: Entity) -> Fields:
        return Fields(self.source, self.units, entity)

    def _name(self, fields: Fields) -> str:
        """A unique name for an item, invented only where the file leaves one out."""
        name = fields.name or f"item{fields.entity.id}"
        if name in self._names:
            suffix = 2
            while f"{name}_{suffix}" in self._names:
                suffix += 1
            self.diagnostics.info(
                "TAS_DUPLICATE_NAME",
                f"'{name}' names more than one item; the second is read as '{name}_{suffix}'",
                line=fields.entity.line,
            )
            name = f"{name}_{suffix}"
        self._names.add(name)
        return name


def _transformation(
    translation: npt.ArrayLike, rotation: npt.ArrayLike
) -> pcc.gmm.CoordinateTransformation:
    """Build a transformation, meeting the core's array layout requirements."""
    return CoordinateTransformation(
        np.asarray(translation, dtype=np.float64),
        np.asfortranarray(rotation, dtype=np.float64),
    )


def _frame_matrix(
    axis: npt.NDArray[np.float64], datum: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    """The rotation taking local axes onto an axis placement's own.

    A placement gives its local Z and local X, in that order, and the columns of
    a rotation matrix *are* the local axes seen from outside, so the matrix is
    assembled rather than solved for.  The given X is squared up against Z
    first: the file is allowed to give a direction that is only nearly
    perpendicular.
    """
    unit_z = axis / float(np.linalg.norm(axis))
    unit_x = datum - float(np.dot(datum, unit_z)) * unit_z
    norm = float(np.linalg.norm(unit_x))
    if norm == 0.0:
        msg = "an axis placement gives a reference direction parallel to its axis"
        raise FieldError(msg)
    unit_x = unit_x / norm
    return np.column_stack((unit_x, np.cross(unit_z, unit_x), unit_z))


def _axis_rotation(axis: npt.NDArray[np.float64], angle: float) -> npt.NDArray[np.float64]:
    """Rotation by *angle* about *axis*, anticlockwise seen from +axis."""
    unit = axis / float(np.linalg.norm(axis))
    cross = np.array(
        [
            [0.0, -unit[2], unit[1]],
            [unit[2], 0.0, -unit[0]],
            [-unit[1], unit[0], 0.0],
        ]
    )
    rotation = np.eye(3) + np.sin(angle) * cross + (1.0 - np.cos(angle)) * (cross @ cross)
    return np.asarray(rotation, dtype=np.float64)


def _in_pycanha_order(
    numbers: Sequence[int], counts: tuple[int, int], *, swapped: bool
) -> list[int]:
    """Re-order a surface's per-face values from the file's order into pycanha's.

    Both formats list faces with their first mesh direction varying fastest, so
    on a planar surface the two orders agree.  On a surface of revolution the
    directions themselves are exchanged, and re-labelling them without
    re-ordering the faces would leave every number on the wrong face.
    """
    first, second = counts
    if not swapped:
        return list(numbers)
    return [
        numbers[position // first + (position % first) * second]
        for position in range(first * second)
    ]


def read_steptas_into(
    model: pcc.gmm.GeometryModel,
    path: str | Path,
    *,
    strict: bool = False,
    on_diagnostic: Callable[[Diagnostic], None] | None = None,
) -> DiagnosticCollector:
    """Read the STEP-TAS geometry at *path* into *model*, in place."""
    source = Path(path)
    diagnostics = DiagnosticCollector(
        source=source.name,
        strict=strict,
        operation="Read STEP-TAS geometry",
        on_diagnostic=on_diagnostic,
    )
    parsed: Part21File = read_part21(source)
    _Reader(model, parsed, diagnostics).run()
    diagnostics.report()
    return diagnostics
