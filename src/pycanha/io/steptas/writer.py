"""Write a :class:`~pycanha.gmm.GeometryModel` out as STEP-TAS.

The walk is the reader's, in reverse: every item of the scene tree becomes a
meshed geometric item, every primitive the bounded surface under one, every cut
a chain of boolean differences, and every face a node of the thermal network the
file carries alongside the geometry.  Around all of it goes the reference
dictionary of :mod:`.dictionary`, emitted unchanged.

Two decisions shape the output.

* **Primitives are written in model coordinates and carry no placement.**  The
  format lets an item be placed relative to the one containing it, and pycanha
  keeps a primitive in local coordinates with a transform beside it, so either
  spelling would do.  Composing the transforms into the points is the one that
  needs no rotation matrix decomposed into a placement, holds for a cutting
  solid as readily as for a surface, and is what the ESATAN writer already does.
  A file written here therefore has a flat identity placement everywhere and
  describes exactly the same geometry.
* **What the format constrains, the writer obeys and reports.**  A side that is
  radiatively active must name a surface material; a notional thickness must
  come with a bulk material and vice versa.  A model may hold neither of those
  pairings, and rather than write a file that would be rejected as a whole, the
  writer drops the unpaired half of it, says so, and produces a file that loads.
"""

from __future__ import annotations

from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pycanha_core as pcc

from ..part21 import Enumeration, Record, Reference, format_entity, write_part21
from . import mappings
from .diagnostics import DiagnosticCollector
from .dictionary import SCHEMA, reference_dictionary
from .entities import Units

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    import numpy as np
    import numpy.typing as npt

    from pycanha.io.diagnostics import Diagnostic

    from ..part21 import Value
    from .dictionary import Dictionary

__all__ = ["write_steptas_from"]

#: Anything in the scene tree.
type Geometry = pcc.gmm.GeometryItem | pcc.gmm.GeometryGroup | pcc.gmm.GeometryGroupCutted

#: A placement taking primitive-local coordinates into model coordinates.
type Placement = pcc.gmm.CoordinateTransformation

#: The two sides of a surface, in the order the format writes them.
_SIDES: Final = (1, 2)

#: What a file says about itself when nobody has said anything.
#:
#: The format wants a person, an organization and an authorization for every
#: exchange structure, and a geometry model records none of the three.  These
#: are the placeholders the tools that write this format use for them.
_UNKNOWN_AUTHOR: Final = "UNKNOWN Author"
_UNKNOWN_ORGANIZATION: Final = "UNKNOWN Organization"
_UNKNOWN_AUTHORIZATION: Final = "UNKNOWN Authorization"
_DESCRIPTION: Final = "UNKNOWN Description"

#: The part-21 conformance class this file is written to, as its header states.
_CONFORMANCE: Final = "2;1"

#: The one material property environment a written file declares.
_DEFAULT_ENVIRONMENT: Final = "DEFAULT"

#: How many cut positions a mesh direction that is not divided at all has.
_UNDIVIDED_CUTS: Final = 2


class _Instances:
    """Instance numbers, and the line defining each.

    Numbers are handed out in order from just past the dictionary, except for
    the handful the dictionary already points at, which are kept back and filled
    in when the writer reaches them.
    """

    def __init__(self, dictionary: Dictionary) -> None:
        self.lines: dict[int, str] = dict(dictionary.lines())
        self._pinned = set(dictionary.reserved)
        self._next = max([*self.lines, *self._pinned]) + 1

    def reserve(self) -> int:
        """A number for an instance that cannot be written yet.

        Every entity naming its own shape has to: the shape names the entity
        back, so one of the two has to exist as a number before it exists as a
        line.
        """
        while self._next in self._pinned:
            self._next += 1
        identifier = self._next
        self._next += 1
        return identifier

    def add(self, kind: str, params: Sequence[Value], *, at: int | None = None) -> int:
        """Define an instance, at *at* if it was reserved, and give its number."""
        identifier = self.reserve() if at is None else at
        self.lines[identifier] = format_entity(identifier, kind, params)
        return identifier

    def written(self) -> Iterable[str]:
        """Every line, in instance order."""
        return (self.lines[identifier] for identifier in sorted(self.lines))


class _Materials:
    """The one material each name stands for, gathered as the walk meets them.

    The format keeps a material's optical and its bulk properties together under
    a single name; pycanha keeps two objects that need not share one.  Names are
    therefore what a material *is* here, and a name carrying both an optical and
    a bulk becomes one material with all thirteen of its values filled in.
    """

    def __init__(self) -> None:
        self.optical: dict[str, pcc.gmm.OpticalMaterial] = {}
        self.bulk: dict[str, pcc.gmm.BulkMaterial] = {}
        self.instances: dict[str, int] = {}

    def names(self) -> list[str]:
        """Every material, in the order it was first met."""
        return list(self.instances)


class _Writer:
    """One pass over a model, producing the instances of one file."""

    def __init__(
        self, model: pcc.gmm.GeometryModel, diagnostics: DiagnosticCollector, name: str
    ) -> None:
        self.model = model
        self.diagnostics = diagnostics
        self.name = name
        self.dictionary = reference_dictionary()
        self.instances = _Instances(self.dictionary)
        self.materials = _Materials()
        # Values are held in SI and written in whatever unit the file's own
        # quantity types declare, which is the reader's conversion backwards.
        self.units = Units(self.dictionary.source)
        self.length = self.dictionary.context_quantity_type("length")
        self.angle = self.dictionary.context_quantity_type("plane_angle")
        self.surface_class = self.dictionary.named(
            "NRF_NETWORK_NODE_CLASS", "meshed_bounded_surface"
        )
        self.node_class = self.dictionary.named("NRF_NETWORK_NODE_CLASS", "thermal_network_node")
        self.items: list[int] = []
        self.nodes: dict[int, int] = {}
        self._names: set[str] = set()
        self._anonymous = 0

    # -- entry point -------------------------------------------------------

    def run(self) -> list[str]:
        """Build every instance of the file and give back its lines."""
        model_id, network_id = self.dictionary.root_models()
        identity: Placement = pcc.gmm.CoordinateTransformation()
        roots = [self._geometry(child, identity) for child in self.model.children]
        root = self._root(roots)
        self._model(model_id, root)
        self._network(network_id)
        self._stamp()
        return list(self.instances.written())

    def _root(self, roots: Sequence[int | None]) -> int | None:
        """The one item the model as a whole is.

        A model may hold several top-level items and the format names exactly
        one, so several are collected under an item named after the model --
        which is also what reading such a file back produces.
        """
        kept = [root for root in roots if root is not None]
        if not kept:
            self.diagnostics.warning(
                "TAS_WRITE_EMPTY_MODEL", "the model has no geometry, so nothing was written"
            )
            return None
        if len(kept) == 1:
            return kept[0]
        return self._compound(self._unique(self.name), kept)

    # -- the tree ----------------------------------------------------------

    def _geometry(self, geometry: Geometry, inherited: Placement) -> int | None:
        """Write *geometry* and everything under it; give back its instance."""
        placement = inherited.compose(geometry.transform)
        if isinstance(geometry, pcc.gmm.GeometryItem):
            return self._surface(geometry, placement)
        if isinstance(geometry, pcc.gmm.GeometryGroupCutted):
            return self._cut(geometry, placement)
        if isinstance(geometry, pcc.gmm.GeometryGroup):
            return self._group(geometry, placement)
        self.diagnostics.warning(
            "TAS_WRITE_UNKNOWN_NODE",
            f"{type(geometry).__name__} is not a geometry this writer knows; it was skipped",
        )
        return None

    def _group(self, group: pcc.gmm.GeometryGroup, placement: Placement) -> int | None:
        children = [self._geometry(child, placement) for child in group.children]
        kept = [child for child in children if child is not None]
        if not kept:
            return None
        return self._compound(self._name_of(group), kept)

    def _compound(self, name: str, children: Sequence[int]) -> int:
        identifier = self.instances.add(
            "MGM_COMPOUND_MESHED_GEOMETRIC_ITEM",
            (
                name,
                name,
                "",
                Reference(self.surface_class),
                None,
                None,
                tuple(Reference(child) for child in children),
            ),
        )
        self.items.append(identifier)
        return identifier

    def _cut(self, cut: pcc.gmm.GeometryGroupCutted, placement: Placement) -> int | None:
        """A cut group: one base surface with a cutting solid taken off it in turn.

        The format removes one solid per difference surface, so a group cut by
        several tools becomes a chain of them.  The outermost keeps the group's
        own name, since that is the one a reader sees.
        """
        targets = [self._geometry(target, placement) for target in cut.targets]
        kept = [target for target in targets if target is not None]
        if not kept:
            return None
        name = self._name_of(cut)
        base = kept[0] if len(kept) == 1 else self._compound(self._unique(f"{name}_base"), kept)
        tools = [
            tool
            for cutter in cut.cutters
            if (tool := self._cutter(cutter, placement, name)) is not None
        ]
        for position, (cutter_name, shape) in enumerate(tools, start=1):
            last = position == len(tools)
            difference = self.instances.reserve()
            solid = self._shape(shape, difference)
            half_space = self.instances.add(
                "MGM_HALF_SPACE_SOLID",
                (cutter_name, "", "", None, Reference(solid), Enumeration("INSIDE")),
            )
            label = name if last else self._unique(f"{name}_{position}")
            self.instances.add(
                "MGM_MESHED_BOOLEAN_DIFFERENCE_SURFACE",
                (
                    label,
                    label,
                    "",
                    Reference(self.surface_class),
                    None,
                    None,
                    Reference(base),
                    Reference(half_space),
                ),
                at=difference,
            )
            self.items.append(difference)
            base = difference
        return base

    def _cutter(
        self, cutter: Geometry, placement: Placement, target: str
    ) -> tuple[str, mappings.Shape] | None:
        """The solid one cutting tool is written as, or nothing if it is not one."""
        if not isinstance(cutter, pcc.gmm.GeometryItem):
            self.diagnostics.error(
                "TAS_WRITE_CUTTER_NOT_PRIMITIVE",
                f"'{target}' is cut by a {type(cutter).__name__}, which is not a single solid; "
                "the cut was dropped and the shape is written uncut",
            )
            return None
        notes: list[mappings.Note] = []
        shape = mappings.solid_of(cutter.primitive, placement.compose(cutter.transform), notes)
        if shape is None:
            self.diagnostics.error(
                "TAS_WRITE_CUTTER_UNSUPPORTED",
                f"'{target}' is cut by a {type(cutter.primitive).__name__}, which has no solid "
                "here; the cut was dropped and the shape is written uncut",
            )
            return None
        name = self._name_of(cutter)
        self._report(notes, name)
        self._report_cutter_attributes(cutter, name)
        return name, shape

    def _report(self, notes: Sequence[mappings.Note], name: str) -> None:
        """What squaring a shape up to the format's own rules cost it."""
        for code, message in notes:
            self.diagnostics.warning(code, f"'{name}': {message}")

    def _report_cutter_attributes(self, cutter: pcc.gmm.GeometryItem, name: str) -> None:
        """Say what a cutting tool leaves behind by becoming one.

        A tool is a solid here and a solid has no faces, so a mesh -- its
        divisions, its node numbers, its materials and its thickness -- has
        nowhere to go.  A model that took a surface and used it to cut with may
        well be carrying all of them.
        """
        mesh = cutter.thermal_mesh
        divided = len(mesh.dir1_mesh) > _UNDIVIDED_CUTS or len(mesh.dir2_mesh) > _UNDIVIDED_CUTS
        carried = [
            what
            for what, held in (
                ("its mesh", divided),
                (
                    "its node numbers",
                    any(getattr(mesh, f"node{side}_start") >= 0 for side in _SIDES),
                ),
                ("its materials", any(getattr(mesh, f"side{side}_optical") for side in _SIDES)),
                ("its thickness", any(getattr(mesh, f"side{side}_thick") for side in _SIDES)),
            )
            if held
        ]
        if carried:
            self.diagnostics.warning(
                "TAS_WRITE_CUTTER_ATTRIBUTES",
                f"'{name}' is written as a cutting solid, which has no faces, so "
                f"{' and '.join(carried)} were dropped",
            )

    # -- surfaces ----------------------------------------------------------

    def _surface(self, item: pcc.gmm.GeometryItem, placement: Placement) -> int | None:
        notes: list[mappings.Note] = []
        shape = mappings.shape_of(item.primitive, placement, notes)
        if shape is None:
            self.diagnostics.unsupported(
                "TAS_WRITE_UNSUPPORTED_PRIMITIVE",
                f"'{item.name}' is a {type(item.primitive).__name__}, which has no bounded "
                "surface here; it was skipped",
            )
            return None
        identifier = self.instances.reserve()
        surface = self._shape(shape, identifier)
        name = self._name_of(item)
        self._report(notes, name)
        self.instances.add(
            "MGM_MESHED_PRIMITIVE_BOUNDED_SURFACE",
            (
                name,
                "",
                "",
                Reference(self.surface_class),
                None,
                None,
                Reference(surface),
                *self._attributes(item, name, swapped=shape.kind in mappings.REVOLVED),
            ),
            at=identifier,
        )
        self.items.append(identifier)
        return identifier

    def _shape(self, shape: mappings.Shape, owner: int) -> int:
        """One bounded surface or cutting solid, naming the item that uses it."""
        return self.instances.add(
            shape.kind,
            (
                Reference(owner),
                *(Reference(self._point(point)) for point in shape.points),
                *(Reference(self._measure(value, self.length)) for value in shape.lengths),
                *(Reference(self._measure(value, self.angle)) for value in shape.angles),
            ),
        )

    def _attributes(
        self, item: pcc.gmm.GeometryItem, name: str, *, swapped: bool
    ) -> tuple[Value, ...]:
        """Everything a meshed surface says beyond its shape, in the format's order."""
        mesh = item.thermal_mesh
        counts, grids = self._mesh(mesh, swapped=swapped)
        optical = [self._material(getattr(mesh, f"side{side}_optical")) for side in _SIDES]
        composition = [self._composition(mesh, name, side) for side in _SIDES]
        return (
            Enumeration(self._activity(mesh, name, optical)),
            *(thickness for thickness, _ in composition),
            *(Reference(found) if found is not None else None for found in optical),
            *(Reference(bulk) if bulk is not None else None for _, bulk in composition),
            *(self._colour(mesh, side) for side in _SIDES),
            *counts,
            None,
            None,
            *grids,
            *(self._faces(mesh, counts, side, swapped=swapped) for side in _SIDES),
        )

    def _mesh(
        self, mesh: pcc.gmm.ThermalMesh, *, swapped: bool
    ) -> tuple[tuple[int, int], tuple[Value, Value]]:
        """The face counts and grid positions, in the file's own direction order."""
        cuts = [
            [float(value) for value in mesh.dir1_mesh],
            [float(value) for value in mesh.dir2_mesh],
        ]
        if swapped:
            cuts.reverse()
        counts = [max(len(positions) - 1, 1) for positions in cuts]
        # A uniform division is what an absent grid means, so writing one out
        # would say the same thing at greater length.
        grids = [None if _is_uniform(positions) else tuple(positions) for positions in cuts]
        return (counts[0], counts[1]), (grids[0], grids[1])

    def _activity(self, mesh: pcc.gmm.ThermalMesh, name: str, optical: Sequence[int | None]) -> str:
        """Which sides are active, reduced to those that can say what they are.

        The format will not have a side both radiatively active and without a
        surface material, because there would be nothing to compute with.  A
        mesh that is in that state is written inactive on that side and the
        reduction reported, which keeps the rest of the file usable.
        """
        active = [bool(getattr(mesh, f"side{side}_activity")) for side in _SIDES]
        unstated = [
            side
            for side, (is_active, material) in enumerate(zip(active, optical, strict=True), start=1)
            if is_active and material is None
        ]
        if unstated:
            self.diagnostics.error(
                "TAS_WRITE_ACTIVE_WITHOUT_OPTICAL",
                f"'{name}' is active on side {' and '.join(str(side) for side in unstated)} "
                "with no optical material; the format has no such surface, so the side is "
                "written inactive",
            )
            for side in unstated:
                active[side - 1] = False
        return mappings.activity_name(side1=active[0], side2=active[1])

    def _composition(
        self, mesh: pcc.gmm.ThermalMesh, name: str, side: int
    ) -> tuple[Value, int | None]:
        """One side's notional thickness and bulk material, which go together.

        The format admits both or neither: a thickness is what turns a surface
        into something with a volume, and a volume with no material has nothing
        to say.  pycanha holds the two separately, so a lone one is dropped and
        reported.
        """
        thickness = float(getattr(mesh, f"side{side}_thick"))
        bulk = getattr(mesh, f"side{side}_material")
        if thickness > 0.0 and bulk is not None:
            return Reference(self._measure(thickness, self.length)), self._material(bulk)
        if thickness > 0.0:
            self.diagnostics.warning(
                "TAS_WRITE_THICKNESS_DROPPED",
                f"'{name}' side {side} is {thickness} thick with no bulk material; the format "
                "carries a thickness only with one, so both were left out",
            )
        elif bulk is not None:
            self.diagnostics.warning(
                "TAS_WRITE_BULK_DROPPED",
                f"'{name}' side {side} has the bulk material '{bulk.name}' but no thickness; "
                "the format carries a bulk only with one, so both were left out",
            )
        return None, None

    def _colour(self, mesh: pcc.gmm.ThermalMesh, side: int) -> Value:
        colour = getattr(mesh, f"side{side}_color")
        if colour is None:
            return None
        return Reference(self.dictionary.nearest_colour(colour.rgb))

    def _faces(
        self, mesh: pcc.gmm.ThermalMesh, counts: tuple[int, int], side: int, *, swapped: bool
    ) -> tuple[Reference, ...]:
        """One side's faces, in the file's order, each naming its thermal node.

        A surface numbers its faces from a first number and an increment, and
        the format numbers each face on its own, so the numbering is expanded
        here.  A side with no numbering keeps its faces and names no nodes: the
        faces are what the geometry is made of and exist either way.
        """
        total = counts[0] * counts[1]
        start = int(getattr(mesh, f"node{side}_start"))
        step = int(getattr(mesh, f"node{side}_step"))
        if start < 0:
            return tuple(Reference(self.instances.add("MGM_FACE", (None,))) for _ in range(total))
        # *counts* is in the file's direction order; the numbering runs in this
        # model's, so the re-ordering is stated in this model's counts.
        own = (counts[1], counts[0]) if swapped else counts
        numbers = _in_file_order(
            [start + position * step for position in range(total)], own, swapped=swapped
        )
        return tuple(
            Reference(self.instances.add("MGM_FACE", (Reference(self._node(number)),)))
            for number in numbers
        )

    def _node(self, number: int) -> int:
        """The thermal node with this number, shared by every face carrying it.

        Two surfaces given the same numbers are the same nodes -- which is how a
        model merges the two sides of a shell -- and a node may be defined only
        once in a network model.
        """
        found = self.nodes.get(number)
        if found is None:
            found = self.instances.add(
                "NRF_NETWORK_NODE", (str(number), "", "", Reference(self.node_class), None)
            )
            self.nodes[number] = found
        return found

    # -- materials ---------------------------------------------------------

    def _material(
        self, material: pcc.gmm.OpticalMaterial | pcc.gmm.BulkMaterial | None
    ) -> int | None:
        """The instance for a material's name, made the first time it is met."""
        if material is None:
            return None
        name = material.name
        # The first object of each kind under a name wins; a model that holds
        # two different opticals called the same thing has already lost the
        # distinction, since a name is what a material is in this format.
        if isinstance(material, pcc.gmm.OpticalMaterial):
            self.materials.optical.setdefault(name, material)
        else:
            self.materials.bulk.setdefault(name, material)
        if name not in self.materials.instances:
            self.materials.instances[name] = self.instances.add(
                "NRF_MATERIAL",
                (
                    name,
                    name,
                    "",
                    Reference(self.dictionary.named("NRF_MATERIAL_CLASS", "thermal_material")),
                    None,
                ),
            )
        return self.materials.instances[name]

    def _material_properties(self) -> tuple[Value, ...]:
        """Every material's values, as one environment's worth of rows."""
        properties = self.dictionary.material_properties()
        rows: list[Value] = []
        for name in self.materials.names():
            values = mappings.material_values(
                self.materials.optical.get(name), self.materials.bulk.get(name)
            )
            rows.append(
                tuple(
                    Reference(self._measure(values[key], property_type.quantity_type))
                    for key, property_type in zip(mappings.MATERIAL_ROW, properties, strict=True)
                )
            )
        return (tuple(rows),)

    # -- the two models ----------------------------------------------------

    def _model(self, identifier: int, root: int | None) -> None:
        """The geometric model: every item, every material, and which item is the root."""
        # A model's materials hold their values for one *environment* at a
        # time -- beginning of life, end of life -- and this one holds a single
        # set, so one environment is declared and it is the default.  The item
        # is written even when there are no materials at all, because the
        # dictionary's own enumeration already points at it.
        self.instances.add(
            "NRF_ENUMERATION_ITEM",
            (_DEFAULT_ENVIRONMENT, ""),
            at=self.dictionary.environment_item(),
        )
        states = self.instances.add(
            "NRF_STATE_LIST",
            (Reference(self.dictionary.environment_type()), None, (), (1,)),
        )
        materials = tuple(
            Reference(self.materials.instances[name]) for name in self.materials.names()
        )
        empty: tuple[Value, ...] = ((), (), (), (), (), (), (), ())
        self.instances.add(
            "MGM_MESHED_GEOMETRIC_MODEL",
            (
                self.name,
                self.name,
                "",
                Reference(
                    self.dictionary.named(
                        "NRF_NETWORK_MODEL_CLASS", "thermal_radiative_conductive_model"
                    )
                ),
                None,
                None,
                tuple(Reference(item) for item in self.items),
                *empty,
                materials,
                Reference(states),
                self._material_properties(),
                Reference(self.dictionary.sole("MGM_QUANTITY_CONTEXT")),
                Reference(root) if root is not None else None,
                (),
            ),
            at=identifier,
        )

    def _network(self, identifier: int) -> None:
        """The thermal network the faces belong to, holding one node per number."""
        name = f"{self.name}_TMODEL"
        empty: tuple[Value, ...] = ((), (), (), (), (), (), (), (), ())
        self.instances.add(
            "NRF_NETWORK_MODEL",
            (
                name,
                name,
                "",
                Reference(
                    self.dictionary.named("NRF_NETWORK_MODEL_CLASS", "thermal_network_model")
                ),
                None,
                None,
                tuple(Reference(self.nodes[number]) for number in sorted(self.nodes)),
                *empty,
                None,
                (),
            ),
            at=identifier,
        )

    def _stamp(self) -> None:
        """When the file was written, which is the one part of it that varies."""
        now = datetime.now(tz=UTC)
        date, time = self.dictionary.date_and_time()
        self.instances.add("NRF_CALENDAR_DATE", (now.year, now.month, now.day), at=date)
        self.instances.add(
            "NRF_LOCAL_TIME",
            (now.hour, now.minute, float(now.second), Reference(self.dictionary.utc_offset())),
            at=time,
        )

    # -- values ------------------------------------------------------------

    def _point(self, point: npt.NDArray[np.float64]) -> int:
        return self.instances.add(
            "MGM_3D_CARTESIAN_POINT",
            (None, *(float(value) for value in point), Reference(self.length)),
        )

    def _measure(self, value: float, quantity_type: int) -> int:
        """One measured value, put into the unit its quantity type is written in."""
        factor, offset, _ = self.units.scale_of(Reference(quantity_type))
        return self.instances.add(
            "NRF_REAL_QUANTITY_VALUE_LITERAL",
            (Reference(quantity_type), ((value - offset) * factor,), ()),
        )

    # -- naming ------------------------------------------------------------

    def _name_of(self, geometry: Geometry) -> str:
        """A unique identifier for *geometry*, invented where the model has none."""
        return self._unique(getattr(geometry, "name", "") or "")

    def _unique(self, name: str) -> str:
        """*name*, or something like it that has not been used yet.

        An identifier has to be unique within a model, and a pycanha model does
        not guarantee that, so a repeat is written under a suffixed name rather
        than left to make one of the two items unreachable.
        """
        candidate = name
        if not candidate:
            self._anonymous += 1
            candidate = f"item{self._anonymous}"
        if candidate in self._names:
            suffix = 2
            while f"{candidate}_{suffix}" in self._names:
                suffix += 1
            self.diagnostics.info(
                "TAS_WRITE_RENAMED",
                f"'{name}' names more than one item; the second is written as "
                f"'{candidate}_{suffix}'",
            )
            candidate = f"{candidate}_{suffix}"
        self._names.add(candidate)
        return candidate


def _is_uniform(positions: Sequence[float]) -> bool:
    """Whether the cuts divide the parameter range into equal pieces."""
    faces = len(positions) - 1
    if faces < 1:
        return True
    step = 1.0 / faces
    return all(abs(positions[index] - index * step) < 1e-12 for index in range(len(positions)))


def _in_file_order(values: Sequence[int], counts: tuple[int, int], *, swapped: bool) -> list[int]:
    """Re-order a surface's per-face values from pycanha's order into the file's.

    The exact inverse of the reader's re-ordering, and needed for the same
    reason: both formats list faces with their own first direction varying
    fastest, so exchanging the directions of a surface of revolution without
    exchanging the faces with them leaves every number on the wrong face.
    """
    if not swapped:
        return list(values)
    first, second = counts
    return [
        values[position // second + (position % second) * first]
        for position in range(first * second)
    ]


def _header(name: str) -> tuple[Record, ...]:
    """The exchange structure's own description."""
    stamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S+0000")
    return (
        Record("FILE_DESCRIPTION", ((_DESCRIPTION,), _CONFORMANCE)),
        Record(
            "FILE_NAME",
            (
                f"{name}.stp",
                stamp,
                (_UNKNOWN_AUTHOR,),
                (_UNKNOWN_ORGANIZATION,),
                f"pycanha {version('pycanha')}",
                "pycanha",
                _UNKNOWN_AUTHORIZATION,
            ),
        ),
        Record("FILE_SCHEMA", ((SCHEMA,),)),
    )


def write_steptas_from(
    model: pcc.gmm.GeometryModel,
    path: str | Path,
    *,
    name: str = "",
    strict: bool = False,
    on_diagnostic: Callable[[Diagnostic], None] | None = None,
) -> DiagnosticCollector:
    """Write *model* to *path* as a STEP-TAS file."""
    target = Path(path)
    diagnostics = DiagnosticCollector(
        source=target.name, strict=strict, on_diagnostic=on_diagnostic
    )
    model_name = name or model.name or target.stem or "MODEL"
    lines = _Writer(model, diagnostics, model_name).run()
    write_part21(target, header=_header(model_name), data=lines)
    return diagnostics
