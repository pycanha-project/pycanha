"""The model properties the geometry can be colored by.

Every option resolves to one ``(Nf,)`` array indexed by **face slot**, which is
what lines it up with the ``face_id`` cell array of the rendered polydata: a
cell reads its own value with :meth:`FaceProperty.per_cell`. Side 1 slots are
even, side 2 odd, so the two sides of a face carry their own material,
thickness and activity rather than repeating side 1's.

Four families are offered (in this order): topology - which face, node, side
and item a cell belongs to; the six optical degrees of freedom; the bulk and
geometric numbers; and the names and activity flags. Numeric properties use
``nan`` where the model has nothing to say, which pyvista draws in its
``nan_color``; categorical ones use ``-1``, which
:func:`pycanha.plot.polydata.categorical_colors` draws grey.

Item-level values are broadcast over each item's slot range from
``mesh.primitives``, one pass over the items - never a lookup per face.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pycanha_core as pcc

from .picking import item_map
from .polydata import categorical_colors
from .scene import slot_items, slot_nodes

if TYPE_CHECKING:
    from collections.abc import Iterator

    import numpy.typing as npt

#: The six optical degrees of freedom, in ``th_optical_properties`` order.
OPTICAL_KEYS: tuple[tuple[str, str], ...] = (
    ("emissivity_ir", "IR emissivity"),
    ("specularity_ir", "IR specularity"),
    ("transmissivity_ir", "IR transmissivity"),
    ("absorptivity_solar", "Solar absorptivity"),
    ("specularity_solar", "Solar specularity"),
    ("transmissivity_solar", "Solar transmissivity"),
)

#: What the two activity flags mean, as legend entries.
ACTIVITY_LABELS = {0: "inactive", 1: "active"}

#: Shown where the model has no value: a face slot with no material, an
#: unassigned node, a numeric property that came out ``nan``.
MISSING = "-"


@dataclass(frozen=True)
class FaceProperty:
    """One color-by option: a value per face slot, plus how to present it.

    ``categorical`` values are labels rather than magnitudes - a distinct color
    each, no color bar - and ``categories`` names them where the number itself
    is not the answer (an item id, an interned material name). Where it is
    ``None`` the legend shows the value.

    ``clim`` is the range an automatic color scale should use in place of the
    range of ``values``. Only a time-varying property sets it, and for the
    reason that makes the difference visible: one frame of a series has to be
    drawn on the scale of the whole series, or the same temperature comes out a
    different color at every instant.
    """

    key: str
    label: str
    values: npt.NDArray[Any]
    categorical: bool
    categories: dict[int, str] | None = None
    unit: str = ""
    clim: tuple[float, float] | None = None

    def per_cell(self, face_ids: npt.ArrayLike) -> npt.NDArray[Any]:
        """Spread the property over cells, given their ``face_id`` cell array."""
        return self.values[np.asarray(face_ids).astype(np.intp)]

    def category_label(self, value: int) -> str:
        """Name of one categorical value, for a legend entry or a table cell.

        Negative values mean the model had nothing to assign, and read as
        :data:`MISSING`; the rest fall back to the number when the property
        does not name its categories.
        """
        category = int(value)
        if category < 0:
            return MISSING
        if self.categories is None:
            return str(category)
        return self.categories.get(category, str(category))

    def format(self, slot: int) -> str:
        """Format the value at face slot ``slot`` for display."""
        if not 0 <= slot < self.values.shape[0]:
            return MISSING
        value = self.values[slot]
        if self.categorical:
            return self.category_label(int(value))
        if not np.isfinite(value):
            return MISSING
        return f"{float(value):.4g} {self.unit}".strip()


@dataclass(frozen=True)
class Category:
    """One entry of a categorical colouring's legend."""

    value: int
    label: str
    color: tuple[int, int, int]


def categories(prop: FaceProperty, face_ids: npt.ArrayLike) -> list[Category]:
    """The distinct categories ``prop`` takes over ``face_ids``, with their colours.

    The colours are taken from the same ranked palette the geometry is drawn
    with, and the ranking is done over *every* cell rather than the visible
    ones - so switching a category off in the legend does not recolour the rest.
    """
    if not prop.categorical:
        return []
    values = prop.per_cell(face_ids).astype(np.int64)
    if values.size == 0:
        return []
    colors = categorical_colors(values, rank=True)
    distinct, first = np.unique(values, return_index=True)
    return [
        Category(int(value), prop.category_label(int(value)), tuple(colors[index].tolist()))
        for value, index in zip(distinct, first, strict=True)
    ]


class _Names:
    """Intern names into small integers so a name can be a categorical value."""

    def __init__(self) -> None:
        self.labels: dict[int, str] = {}
        self._index: dict[str, int] = {}

    def index(self, name: str | None) -> int:
        """Index of ``name``, assigning a new one on first sight; ``-1`` for ``None``."""
        if name is None:
            return -1
        if name not in self._index:
            self._index[name] = len(self._index)
            self.labels[self._index[name]] = name
        return self._index[name]


def _item_slots(model: Any) -> Iterator[tuple[Any, slice, slice]]:
    """Yield each item with the slot ranges of its side-1 and side-2 faces.

    In ``mesh.primitives`` order, so an item that a later range overlaps is
    overwritten by it - the same last-writer-wins rule
    :func:`pycanha.plot.scene.slot_items` follows, and the reason a fully-cut
    item ends up owning nothing. The ranges name side-1 (even) slots, so the
    stop runs two past the last one to take in its side-2 partner.
    """
    items = item_map(model)
    for geometry_id, first_face_id, last_face_id in model.mesh.primitives:
        item = items.get(int(geometry_id))
        if item is None:
            continue
        first, stop = int(first_face_id), int(last_face_id) + 2
        yield item, slice(first, stop, 2), slice(first + 1, stop, 2)


def optical_properties(model: Any) -> npt.NDArray[np.float64]:
    """The six optical degrees of freedom of every face slot, ``nan`` where unset.

    Rows follow ``OpticalMaterial.th_optical_properties``:
    ``[eps_ir, spec_ir, tau_ir, alpha_sol, spec_sol, tau_sol]``.

    Read off the ThermalMesh sides rather than through
    :meth:`~pycanha.gmm.GeometryModel.material_table`, which returns the same
    numbers but warns once per side that has no optical material - a raytracer
    concern ("treated as blackbody") that a model being *looked at* has no
    reason to answer for. The per-item pass is needed anyway for the thickness,
    bulk and activity families, so reading two more attributes inside it costs
    nothing.
    """
    values = np.full((int(model.mesh.nf()), len(OPTICAL_KEYS)), np.nan)
    for item, side1, side2 in _item_slots(model):
        thermal_mesh = item.thermal_mesh
        for optical, span in (
            (thermal_mesh.side1_optical, side1),
            (thermal_mesh.side2_optical, side2),
        ):
            values[span] = np.nan if optical is None else optical.th_optical_properties
    return values


def face_areas(mesh: Any) -> npt.NDArray[np.float64]:
    """Surface area of every face slot, summed over the triangles that mesh it.

    ``mesh::ops::compute_face_slot_areas`` does this in C++ but is not bound
    yet, so the per-triangle areas are accumulated by face slot here.
    """
    n_slots = int(mesh.nf())
    if n_slots == 0 or int(mesh.nt()) == 0:
        return np.zeros(n_slots)
    areas = np.asarray(pcc.gmm.compute_areas(mesh), dtype=np.float64)
    # face_ids always name the side-1 slot, so the accumulation lands on the
    # even slots and the odd partner - the same patch of geometry seen from the
    # other side - inherits it.
    face_ids = np.asarray(mesh.face_ids).astype(np.int64)
    # Weighted, so the sums come back as floats whatever the stubs think.
    totals = np.asarray(np.bincount(face_ids, weights=areas, minlength=n_slots), dtype=np.float64)
    totals[1::2] = totals[: 2 * (n_slots // 2) : 2]
    return totals


def face_properties(model: Any) -> dict[str, FaceProperty]:
    """Build every color-by option of ``model``, keyed by :attr:`FaceProperty.key`.

    Insertion order is the order the color-by combo offers them: topology
    first, then the optical degrees of freedom, then the bulk and geometric
    numbers, then the names and activity flags.
    """
    mesh = model.mesh
    n_slots = int(mesh.nf())
    slots = np.arange(n_slots, dtype=np.int64)
    items = slot_items(mesh)
    item_names = {
        int(geometry_id): item.name or "<anonymous>"
        for geometry_id, item in item_map(model).items()
    }

    node_numbers = slot_nodes(mesh)
    optical = optical_properties(model)

    properties = [
        FaceProperty("item", "Geometry item", items, categorical=True, categories=item_names),
        FaceProperty("node_number", "TMM node", node_numbers, categorical=True),
        FaceProperty("face_id", "Face slot", slots, categorical=True),
        # Side 1 slots are even, side 2 odd - the parity *is* the side.
        FaceProperty("side", "ThermalMesh side", (slots % 2) + 1, categorical=True),
    ]
    properties += [
        FaceProperty(key, label, optical[:, column], categorical=False)
        for column, (key, label) in enumerate(OPTICAL_KEYS)
    ]
    properties += _shell_properties(model, n_slots)
    properties.append(
        FaceProperty("area", "Face area", face_areas(mesh), categorical=False, unit="m^2")
    )
    return {prop.key: prop for prop in properties}


def _shell_properties(model: Any, n_slots: int) -> list[FaceProperty]:
    """Broadcast the per-item, per-side shell properties over the face slots.

    Thickness, bulk material and the two activity flags all come off the same
    ThermalMesh, so they are filled in together in a single pass over the items
    rather than one pass each.
    """
    thickness = np.full(n_slots, np.nan)
    density = np.full(n_slots, np.nan)
    conductivity = np.full(n_slots, np.nan)
    specific_heat = np.full(n_slots, np.nan)
    optical_name = np.full(n_slots, -1, dtype=np.int64)
    bulk_name = np.full(n_slots, -1, dtype=np.int64)
    radiative_active = np.full(n_slots, -1, dtype=np.int64)
    conductive_active = np.full(n_slots, -1, dtype=np.int64)
    optical_names, bulk_names = _Names(), _Names()

    for item, side1, side2 in _item_slots(model):
        thermal_mesh = item.thermal_mesh
        sides = (
            (1, side1, thermal_mesh.side1_thick, thermal_mesh.side1_material),
            (2, side2, thermal_mesh.side2_thick, thermal_mesh.side2_material),
        )
        for side, span, thick, material in sides:
            thickness[span] = thick
            if material is not None:
                density[span] = material.density
                conductivity[span] = material.conductivity
                specific_heat[span] = material.specific_heat
            bulk_name[span] = bulk_names.index(None if material is None else material.name)
            optical = thermal_mesh.side1_optical if side == 1 else thermal_mesh.side2_optical
            optical_name[span] = optical_names.index(None if optical is None else optical.name)
            radiative_active[span] = int(thermal_mesh.is_radiative_active(side))
            conductive_active[span] = int(thermal_mesh.is_conductive_active(side))

    return [
        FaceProperty("thickness", "Thickness", thickness, categorical=False, unit="m"),
        FaceProperty("density", "Density", density, categorical=False, unit="kg/m^3"),
        FaceProperty(
            "conductivity", "Conductivity", conductivity, categorical=False, unit="W/(m K)"
        ),
        FaceProperty(
            "specific_heat", "Specific heat", specific_heat, categorical=False, unit="J/(kg K)"
        ),
        FaceProperty(
            "optical_name",
            "Optical material",
            optical_name,
            categorical=True,
            categories=optical_names.labels,
        ),
        FaceProperty(
            "bulk_name",
            "Bulk material",
            bulk_name,
            categorical=True,
            categories=bulk_names.labels,
        ),
        FaceProperty(
            "radiative_active",
            "Radiatively active",
            radiative_active,
            categorical=True,
            categories=dict(ACTIVITY_LABELS),
        ),
        FaceProperty(
            "conductive_active",
            "Conductively active",
            conductive_active,
            categorical=True,
            categories=dict(ACTIVITY_LABELS),
        ),
    ]
