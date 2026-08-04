"""Emit a :class:`~pycanha.gmm.GeometryModel` as an ESATAN geometry file.

The writer is the reader's inverse wherever the reader is lossless, and says so
with a diagnostic wherever it is not.  Two decisions shape the output:

* **Primitives are written by points, in model coordinates.**  ESATAN has two
  spellings for most shapes -- one in the shell's own coordinate system plus a
  placement, and one giving the defining points outright.  pycanha stores a
  primitive in local coordinates *and* a transform, and the by-points spelling
  absorbs both, so no ``ROTATE`` or ``TRANSLATE`` has to be emitted and no
  rotation matrix has to be decomposed into angles.  It is also the only
  spelling that covers a quadrilateral.
* **A model does not record which spelling it was read from.**  A file written
  here will therefore differ from that model's own export wherever the source
  used the other spelling.  That is a difference of expression, not of geometry.

Everything the model cannot supply -- a label, a sub-model name, a criticality
-- is simply absent from the output rather than guessed at.  A colour is the one
thing approximated instead: the format names one of thirty-two, a model holds an
arbitrary value, and the nearest name is a better answer than no colour.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pycanha_core as pcc

from ...shapes import Revolved, axis_of, full_turn, rim_of, rim_point, unit_rim
from ..lang.diagnostics import DiagnosticCollector
from .canonical import (
    BLOCKS,
    block,
    format_real,
    format_vector,
    indent_arguments,
    sort_attributes,
)
from .palette import nearest_name

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    import numpy.typing as npt

    from pycanha.io.diagnostics import Diagnostic


__all__ = ["write_erg_from"]

#: Attribute name for each surface side, in the order ESATAN writes them.
_SIDES = (1, 2)

#: A placement taking primitive-local coordinates into model coordinates.
type Placement = pcc.gmm.CoordinateTransformation

#: ``key = value`` pairs, already rendered, in the order they are written.
type Arguments = list[tuple[str, str]]

#: An ESATAN function name and its arguments, or nothing if the shape has none.
type Spelling = tuple[str, Arguments] | None

#: Anything in the scene tree.
type Geometry = pcc.gmm.GeometryItem | pcc.gmm.GeometryGroup | pcc.gmm.GeometryGroupCutted

#: What turns one primitive into its spelling.
#:
#: Each builder takes one concrete primitive type, and the table erases which,
#: so this is the one place the correspondence cannot be expressed.
type PrimitiveWriter = Callable[[Any, Placement, DiagnosticCollector], Spelling]


def _placed(point: npt.ArrayLike, transform: Placement) -> list[float]:
    """Take a primitive-local point into model coordinates."""
    return [float(value) for value in transform.apply(np.asarray(point, dtype=float))]


def _rotated(
    vector: npt.NDArray[np.float64], axis: npt.NDArray[np.float64], angle: float
) -> npt.NDArray[np.float64]:
    """Rotate *vector* about *axis* by *angle* radians, anticlockwise (Rodrigues).

    Radians because that is what a primitive stores; the format writes degrees,
    but nothing here ever writes an angle -- the sector is expressed as a point.
    """
    unit = axis / np.linalg.norm(axis)
    rotated: npt.NDArray[np.float64] = (
        vector * np.cos(angle)
        + np.cross(unit, vector) * np.sin(angle)
        + unit * float(np.dot(unit, vector)) * (1.0 - np.cos(angle))
    )
    return rotated


class _Writer:
    """One pass over a model, producing the lines of one file."""

    def __init__(self, model: pcc.gmm.GeometryModel, diagnostics: DiagnosticCollector) -> None:
        self.model = model
        self.diagnostics = diagnostics
        self.opticals: dict[str, pcc.gmm.OpticalMaterial] = {}
        self.bulks: dict[str, pcc.gmm.BulkMaterial] = {}
        self.primitives: list[str] = []
        self.structure: list[str] = []
        self._named: set[str] = set()
        self._anonymous = 0

    # -- entry point -------------------------------------------------------

    def run(self, name: str) -> list[str]:
        self._named.add(name)
        identity = pcc.gmm.CoordinateTransformation()
        children = list(self.model.children)

        # `MODEL = a + b;` *is* the root geometry's declaration, and reading one
        # produces a group named after the model.  Writing that group out under
        # its own name and then aliasing the model to it would declare the same
        # object twice, so a single root group becomes the model statement
        # itself.  The names come back from the walk: asking for them again
        # would mint a second, suffixed name for something already written.
        # `isinstance`, not an exact type check: a model built through the
        # Python layer holds subclasses of the compiled types.
        if (
            len(children) == 1
            and isinstance(children[0], pcc.gmm.GeometryGroup)
            and not isinstance(children[0], pcc.gmm.GeometryGroupCutted)
        ):
            root = children[0]
            transform = identity.compose(root.transform)
            roots = [self._geometry(child, transform) for child in root.children]
        else:
            roots = [self._geometry(child, identity) for child in children]

        lines = [f"BEGIN_MODEL {name} WORKBENCH_V1 ESARAD_GENERATED", ""]
        bodies = {
            "bound variable": self._materials(),
            "primitive": self.primitives,
            "structure": [*self.structure, *self._root_assignment(name, roots)],
        }
        for name_of_block in BLOCKS:
            lines.extend(block(name_of_block, bodies.get(name_of_block, ())))
            lines.append("")
        lines.append("END_MODEL")
        return lines

    def _root_assignment(self, model_name: str, roots: Sequence[str | None]) -> list[str]:
        """The statement naming what the model as a whole is."""
        kept = [root for root in roots if root]
        if not kept:
            self.diagnostics.warning(
                "ERG_WRITE_EMPTY_MODEL", "the model has no geometry, so nothing was written"
            )
            return []
        return ["", f"{model_name} = " + " + ".join(kept) + ";"]

    # -- naming ------------------------------------------------------------

    def _name_of(self, geometry: Geometry) -> str:
        """A unique ESATAN identifier for *geometry*.

        Names have to be unique in a file and syntactically legal, and a pycanha
        model guarantees neither, so a name that would collide or would not
        parse is replaced rather than written out and rejected on load.
        """
        raw = getattr(geometry, "name", "") or ""
        candidate = "".join(char if char.isalnum() or char == "_" else "_" for char in raw)
        if not candidate or not candidate[0].isalpha():
            candidate = f"G_{candidate}" if candidate else ""
        if not candidate:
            self._anonymous += 1
            candidate = f"G_{self._anonymous}"
        if candidate in self._named:
            suffix = 2
            while f"{candidate}_{suffix}" in self._named:
                suffix += 1
            self.diagnostics.warning(
                "ERG_WRITE_RENAMED",
                f"'{raw}' collides with a name already written; it is written as "
                f"'{candidate}_{suffix}'",
            )
            candidate = f"{candidate}_{suffix}"
        if candidate != raw:
            self.diagnostics.info(
                "ERG_WRITE_RENAMED",
                f"'{raw}' is not a legal identifier here; it is written as '{candidate}'",
            )
        self._named.add(candidate)
        return candidate

    # -- the tree ----------------------------------------------------------

    def _geometry(
        self,
        geometry: Geometry,
        inherited: Placement,
        *,
        cutting: bool = False,
    ) -> str | None:
        """Write *geometry* and everything under it; return the name it got."""
        transform = inherited.compose(geometry.transform)
        if isinstance(geometry, pcc.gmm.GeometryItem):
            return self._item(geometry, transform, cutting=cutting)
        if isinstance(geometry, pcc.gmm.GeometryGroupCutted):
            return self._cut(geometry, transform)
        if isinstance(geometry, pcc.gmm.GeometryGroup):
            return self._group(geometry, transform)
        self.diagnostics.warning(
            "ERG_WRITE_UNKNOWN_NODE",
            f"{type(geometry).__name__} is not a geometry this writer knows; it was skipped",
        )
        return None

    def _group(self, group: pcc.gmm.GeometryGroup, transform: Placement) -> str | None:
        children = [self._geometry(child, transform) for child in group.children]
        kept = [child for child in children if child]
        if not kept:
            return None
        name = self._name_of(group)
        self.structure.append(f"GEOMETRY {name};")
        if len(kept) == 1:
            # `name = child;` would be a plain alias -- two names for one
            # object, not a group of one.  The format has a construct for
            # exactly this, and it is what reading one back produces.
            self.structure.append(f"{name} = SINGLE_COMBINATION (geometry = {kept[0]});")
        else:
            self.structure.extend(_wrap(f"{name} = ", " + ".join(kept)))
        self.structure.append("")
        return name

    def _cut(self, cut: pcc.gmm.GeometryGroupCutted, transform: Placement) -> str | None:
        targets = [self._geometry(target, transform) for target in cut.targets]
        cutters = [self._geometry(cutter, transform, cutting=True) for cutter in cut.cutters]
        kept_targets = [target for target in targets if target]
        kept_cutters = [cutter for cutter in cutters if cutter]
        if not kept_targets:
            return None
        name = self._name_of(cut)
        expression = " + ".join(kept_targets)
        if kept_cutters:
            expression += " - " + " - ".join(kept_cutters)
        self.structure.append(f"GEOMETRY {name};")
        self.structure.extend(_wrap(f"{name} = ", expression))
        self.structure.append("")
        return name

    # -- primitives --------------------------------------------------------

    def _item(
        self, item: pcc.gmm.GeometryItem, transform: Placement, *, cutting: bool = False
    ) -> str | None:
        arguments = _primitive_arguments(item.primitive, transform, self.diagnostics)
        if arguments is None:
            return None
        function, points = arguments
        name = self._name_of(item)
        # The format's default is `sense = 1`, which keeps what the cutter
        # encloses.  This model only ever means the other one, so a cutter
        # written without it would read back as the cut this reader refuses.
        rest: Arguments = [("sense", "-1" if cutting else "1")]
        rest.extend(self._attributes(item))
        # Points lead, in the order the shape defines them; everything else goes
        # into the order the format writes it, so a file can be compared against
        # an ESATAN export without the difference being one of arrangement.
        attributes = [*points, *sort_attributes(rest)]
        self.primitives.append(f"GEOMETRY {name};")
        self.primitives.extend(indent_arguments(f"{name} = {function}", attributes))
        self.primitives.append("")
        return name

    def _attributes(self, item: pcc.gmm.GeometryItem) -> list[tuple[str, str]]:
        """The per-side attributes, in the order ESATAN writes them."""
        mesh = item.thermal_mesh
        if mesh is None:
            return []
        out: list[tuple[str, str]] = []

        for direction, cuts in ((1, mesh.dir1_mesh), (2, mesh.dir2_mesh)):
            positions = [float(value) for value in cuts]
            faces = len(positions) - 1
            if faces <= 0:
                continue
            if _is_uniform(positions):
                out.append((f"meshType{direction}", '"regular"'))
                out.append((f"nodes{direction}", str(faces)))
                # Not a default filled in for the sake of it: a uniform mesh has
                # a common ratio, and it is 1.
                out.append((f"ratio{direction}", format_real(1.0)))
            else:
                out.append((f"meshType{direction}", '"positions"'))
                interior = ", ".join(format_real(value) for value in positions[1:-1])
                out.append((f"meshPositions{direction}", f"{{{interior}}}"))

        for side in _SIDES:
            active = getattr(mesh, f"side{side}_activity")
            out.append((f"side{side}", '"Active"' if active else '"Inactive"'))
            start = getattr(mesh, f"node{side}_start")
            if start is not None and start >= 0:
                out.append((f"nbase{side}", str(int(start))))
                out.append((f"ndelta{side}", str(int(getattr(mesh, f"node{side}_step")))))
            optical = getattr(mesh, f"side{side}_optical")
            if optical is not None:
                self.opticals[optical.name] = optical
                out.append((f"opt{side}", optical.name))
            colour = getattr(mesh, f"side{side}_color")
            if colour is not None and not _is_default_colour(colour, side):
                # The format names a colour rather than carrying one, so a model
                # holding an arbitrary colour is written as the closest of the
                # thirty-two the palette has.  A colour that came from the
                # palette comes back as the name it came from.
                out.append((f"colour{side}", f'"{nearest_name(colour)}"'))

        out.extend(self._composition(mesh))
        return out

    def _composition(self, mesh: pcc.gmm.ThermalMesh) -> list[tuple[str, str]]:
        """Thicknesses and bulks, as one pair or two."""
        first, second = mesh.side1_material, mesh.side2_material
        thick1, thick2 = mesh.side1_thick, mesh.side2_thick
        for material in (first, second):
            if material is not None:
                self.bulks[material.name] = material

        same_material = (first is None and second is None) or (
            first is not None and second is not None and first.name == second.name
        )
        if same_material and thick1 == thick2:
            out = [("composition", '"SINGLE"')]
            if first is not None:
                out.append(("bulk", first.name))
            # ESATAN's single thickness is the whole shell's; the reader halves
            # it onto the two sides, so writing it back doubles the stored one.
            out.append(("thick", format_real(float(thick1) + float(thick2))))
            return out

        out = [("composition", '"DUAL"')]
        for side, material, thick in ((1, first, thick1), (2, second, thick2)):
            if material is not None:
                out.append((f"bulk{side}", material.name))
            out.append((f"thick{side}", format_real(float(thick))))
        return out

    # -- materials ---------------------------------------------------------

    def _materials(self) -> list[str]:
        lines: list[str] = []
        for name in sorted(self.bulks):
            bulk = self.bulks[name]
            lines.append(f"BULK {name};")
            lines.extend(
                indent_arguments(
                    "DEFINE_BULK",
                    [
                        ("bulk", name),
                        ("density", format_real(bulk.density)),
                        ("sp_heat", format_real(bulk.specific_heat)),
                        ("type", '"Isotropic"'),
                        ("cond", format_real(bulk.conductivity)),
                    ],
                )
            )
            lines.append("")
        for name in sorted(self.opticals):
            optical = self.opticals[name]
            row = [float(value) for value in optical.th_optical_properties]
            lines.append(f"OPTICAL {name};")
            lines.extend(
                indent_arguments(
                    "DEFINE_OPTICAL",
                    [
                        ("optical", name),
                        ("ir_emiss", format_real(row[0])),
                        ("ir_transm", format_real(row[2])),
                        ("solar_absorb", format_real(row[3])),
                        ("solar_transm", format_real(row[5])),
                        ("ir_spec_refl", format_real(row[1])),
                        ("solar_spec_refl", format_real(row[4])),
                    ],
                )
            )
            lines.append("")
        return lines


def _default_colours() -> tuple[pcc.gmm.Color | None, pcc.gmm.Color | None]:
    """The colour a fresh mesh carries on each side, resolved once."""
    fresh = pcc.gmm.ThermalMesh()
    return fresh.side1_color, fresh.side2_color


_DEFAULT_COLOURS = _default_colours()


def _is_default_colour(colour: pcc.gmm.Color, side: int) -> bool:
    """Whether *colour* is the one a mesh has when nobody has chosen one.

    A mesh always carries a colour, so "nobody chose one" cannot be read off it
    directly -- and the two defaults do not agree: a fresh mesh is blue-cyan on
    one side and violet on the other, while the format defaults both to
    blue-cyan.  Writing the default out would therefore repaint the back of
    every surface nobody had coloured, which is a visible change to someone's
    model made for no reason.  Leaving it out lets the format apply its own.

    The cost is one palette entry per side: a surface deliberately coloured with
    the default is written without a colour and comes back as the format's.
    """
    default = _DEFAULT_COLOURS[side - 1]
    return default is not None and tuple(colour.rgb) == tuple(default.rgb)


def _is_uniform(positions: Sequence[float]) -> bool:
    """Whether the cuts divide the parameter range into equal pieces."""
    faces = len(positions) - 1
    if faces < 1:
        return True
    step = 1.0 / faces
    return all(abs(positions[index] - index * step) < 1e-12 for index in range(len(positions)))


def _wrap(prefix: str, expression: str, width: int = 96) -> list[str]:
    """Break a long ``A + B + C`` chain the way the format does."""
    words = expression.split(" ")
    lines: list[str] = []
    current = prefix
    for word in words:
        if len(current) + len(word) + 1 > width and current.strip() not in ("", prefix.strip()):
            lines.append(current.rstrip())
            current = "    "
        current += word + " "
    lines.append(current.rstrip() + ";")
    return lines


#: One builder per primitive, each returning the ESATAN function and its points.
#:
#: A table rather than a chain of branches: the compiled primitive types are
#: related by inheritance in places, so the order of the checks is part of the
#: meaning, and a table makes that order visible in one place.


def _points(primitive: Any, transform: Placement, names: Sequence[str]) -> Arguments:
    """``point1..N`` straight off the primitive's own attributes."""
    return [
        (f"point{index}", format_vector(_placed(getattr(primitive, attribute), transform)))
        for index, attribute in zip(names, ("p1", "p2", "p3", "p4"), strict=False)
    ]


def _triangle(
    primitive: pcc.gmm.Triangle, transform: Placement, _d: DiagnosticCollector
) -> Spelling:
    return "SHELL_TRIANGLE", _points(primitive, transform, ("1", "2", "3"))


def _rectangle(
    primitive: pcc.gmm.Rectangle, transform: Placement, _d: DiagnosticCollector
) -> Spelling:
    # The format names a rectangle's corners 1, 2 and 4; the third point stored
    # here is the one it calls point4.
    return "SHELL_RECTANGLE", _points(primitive, transform, ("1", "2", "4"))


def _quadrilateral(
    primitive: pcc.gmm.Quadrilateral, transform: Placement, _d: DiagnosticCollector
) -> Spelling:
    return "SHELL_QUADRILATERAL", _points(primitive, transform, ("1", "2", "3", "4"))


def _revolved(primitive: Revolved, transform: Placement, radius: float) -> Arguments:
    """The frame shared by every surface of revolution, plus its sector limit."""
    points = [
        ("point1", format_vector(_placed(primitive.p1, transform))),
        ("point2", format_vector(_placed(primitive.p2, transform))),
        ("point3", format_vector(_placed(rim_point(primitive, radius), transform))),
    ]
    points.extend(_sector_point(primitive, transform))
    return points


def _disc(primitive: pcc.gmm.Disc, transform: Placement, _d: DiagnosticCollector) -> Spelling:
    points = _revolved(primitive, transform, primitive.outer_radius)
    if primitive.inner_radius > 0.0:
        inner = rim_point(primitive, primitive.inner_radius)
        points.append(("point5", format_vector(_placed(inner, transform))))
    return "SHELL_DISC", points


def _cylinder(
    primitive: pcc.gmm.Cylinder, transform: Placement, _d: DiagnosticCollector
) -> Spelling:
    return "SHELL_CYLINDER", _revolved(primitive, transform, primitive.radius)


def _paraboloid(
    primitive: pcc.gmm.Paraboloid, transform: Placement, _d: DiagnosticCollector
) -> Spelling:
    return "SHELL_PARABOLOID", _revolved(primitive, transform, primitive.radius)


def _sphere(primitive: pcc.gmm.Sphere, transform: Placement, _d: DiagnosticCollector) -> Spelling:
    points = _revolved(primitive, transform, primitive.radius)
    axis = axis_of(primitive)
    unit = axis / np.linalg.norm(axis)
    centre: npt.NDArray[np.float64] = np.asarray(primitive.p1, dtype=float)
    # The two truncations are given as points, at their height along the axis.
    for index, height in (("5", primitive.base_truncation), ("6", primitive.apex_truncation)):
        points.append((f"point{index}", format_vector(_placed(centre + unit * height, transform))))
    return "SHELL_SPHERE", points


def _box(primitive: pcc.gmm.Cube, transform: Placement, _d: DiagnosticCollector) -> Spelling:
    """A box, as one corner and the three corners adjacent to it."""
    extent = np.asarray(primitive.extent, dtype=np.float64)
    frame = _matrix_of_quaternion(primitive.orientation)
    edges = [frame[:, index] * extent[index] for index in range(3)]
    origin = np.asarray(primitive.center, dtype=np.float64) - sum(edges) / 2.0
    corners = [origin, *(origin + edge for edge in edges)]
    return "SHELL_BOX", [
        (f"point{index}", format_vector(_placed(corner, transform)))
        for index, corner in enumerate(corners, start=1)
    ]


def _spellings() -> tuple[tuple[type, PrimitiveWriter], ...]:
    """Built lazily so the compiled types are only looked up once, at import."""
    return (
        (pcc.gmm.Triangle, _triangle),
        (pcc.gmm.Rectangle, _rectangle),
        (pcc.gmm.Quadrilateral, _quadrilateral),
        (pcc.gmm.Disc, _disc),
        (pcc.gmm.Cylinder, _cylinder),
        (pcc.gmm.Sphere, _sphere),
        (pcc.gmm.Paraboloid, _paraboloid),
        (pcc.gmm.Cone, _cone_arguments),
        (pcc.gmm.Cube, _box),
    )


#: Bound after the builders exist; the order is the isinstance order.
_SPELLINGS: tuple[tuple[type, PrimitiveWriter], ...] = ()


def _primitive_arguments(
    primitive: Any,
    transform: Placement,
    diagnostics: DiagnosticCollector,
) -> Spelling:
    """The ESATAN function and defining points for *primitive*, in model space."""
    for kind, build in _SPELLINGS:
        if isinstance(primitive, kind):
            return build(primitive, transform, diagnostics)

    diagnostics.warning(
        "ERG_WRITE_UNSUPPORTED_PRIMITIVE",
        f"{type(primitive).__name__} has no ESATAN spelling here and was skipped",
    )
    return None


def _matrix_of_quaternion(quaternion: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """Rotation matrix for a ``(w, x, y, z)`` quaternion, columns being the axes.

    A cube carries its orientation as a quaternion rather than a frame, and the
    by-points spelling of a box wants the three edge directions, so the columns
    are what is needed here.
    """
    w, x, y, z = (float(value) for value in np.asarray(quaternion, dtype=np.float64))
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def _sector_point(primitive: Revolved, transform: Placement) -> Arguments:
    """``point4``, the sector limit, for anything less than a full turn."""
    if full_turn(primitive):
        return []
    axis = axis_of(primitive)
    origin: npt.NDArray[np.float64] = np.asarray(primitive.p1, dtype=float)
    limit = origin + _rotated(rim_of(primitive), axis, float(primitive.end_angle))
    return [("point4", format_vector(_placed(limit, transform)))]


def _cone_arguments(
    primitive: pcc.gmm.Cone,
    transform: pcc.gmm.CoordinateTransformation,
    diagnostics: DiagnosticCollector,
) -> tuple[str, list[tuple[str, str]]] | None:
    """A cone, given apex first -- which a frustum has to have extrapolated.

    pycanha stores the two end radii; ESATAN wants the apex the sides converge
    on, plus ``point5`` for where the frustum actually starts.  The apex is
    where the radius reaches zero, found by similar triangles.
    """
    top = np.asarray(primitive.p1, dtype=np.float64)
    base = np.asarray(primitive.p2, dtype=np.float64)
    radius_top = float(primitive.radius1)
    radius_base = float(primitive.radius2)
    axis = base - top

    if abs(radius_base - radius_top) < 1e-12:
        diagnostics.warning(
            "ERG_WRITE_DEGENERATE_CONE",
            "a cone with equal end radii is a cylinder and has no apex; it was skipped",
        )
        return None

    # Distance from the top rim back to the apex, along the axis.
    reach = radius_top / (radius_base - radius_top)
    apex = top - axis * reach
    points = [
        ("point1", format_vector(_placed(apex, transform))),
        ("point2", format_vector(_placed(base, transform))),
        ("point3", format_vector(_placed(base + unit_rim(primitive) * radius_base, transform))),
    ]
    points.extend(_sector_point(primitive, transform))
    if radius_top > 0.0:
        points.append(("point5", format_vector(_placed(top, transform))))
    return "SHELL_CONE", points


def write_erg_from(
    model: pcc.gmm.GeometryModel,
    path: str | Path,
    *,
    name: str = "",
    strict: bool = False,
    on_diagnostic: Callable[[Diagnostic], None] | None = None,
) -> DiagnosticCollector:
    """Write *model* to *path* as an ESATAN geometry file."""
    target = Path(path)
    diagnostics = DiagnosticCollector(
        source=target.name, strict=strict, on_diagnostic=on_diagnostic
    )
    writer = _Writer(model, diagnostics)
    lines = writer.run(name or model.name or "MODEL")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return diagnostics


_SPELLINGS = _spellings()
