"""Typed access to the entities of a STEP-TAS file.

:mod:`pycanha.io.part21` gives back attributes as bare values in the order the
file wrote them.  This module puts names and types on them: the positions each
STEP-TAS entity keeps its attributes in, the resolution of a reference to the
instance it names, and the conversion of a measured value into the unit pycanha
stores it in.

Nothing here decides what a shape *is* -- that is :mod:`.mappings` -- and
nothing raises for an entity the reader has never seen.  An attribute that is
missing or of the wrong shape raises :class:`FieldError`, which the reader
turns into a diagnostic against the one item that carried it, so a single
strange surface costs that surface and not the file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import numpy as np

from ..part21 import Entity, Enumeration, Reference

if TYPE_CHECKING:
    import numpy.typing as npt

    from ..part21 import Part21File, Value

__all__ = ["FieldError", "Fields", "Units", "node_number"]

#: The SI unit each quantity this reader understands is converted onto.
_RADIAN: Final = "radian"
_METRE: Final = "metre"


class FieldError(Exception):
    """Raised when an attribute is absent, or is not the kind of value expected."""


class Units:
    """Converts measured values onto the SI unit for their quantity.

    A STEP-TAS value carries a reference to its *quantity type*, and the type
    carries the unit it is expressed in.  ESATAN writes angles in degrees and
    lengths in metres, but nothing in the format requires that, so the unit is
    read and applied rather than assumed.  The result is cached per quantity
    type, of which a file has a few dozen and a few hundred thousand values.
    """

    def __init__(self, source: Part21File) -> None:
        self._source = source
        self._scales: dict[int, tuple[float, float, str]] = {}

    def scale_of(self, quantity_type: Value) -> tuple[float, float, str]:
        """The ``(factor, offset, unit)`` of a quantity type, onto its SI unit.

        A value ``v`` in the file's unit is ``v / factor + offset`` in the named
        SI one.  An unreadable type gives an identity conversion under the empty
        unit name, which the caller reports.
        """
        entity = self._source.entity(quantity_type)
        if entity is None:
            return 1.0, 0.0, ""
        cached = self._scales.get(entity.id)
        if cached is None:
            cached = self._resolve(entity)
            self._scales[entity.id] = cached
        return cached

    def _resolve(self, quantity_type: Entity) -> tuple[float, float, str]:
        unit = self._source.entity(_at(quantity_type.params, 7))
        return self._unit(unit) if unit is not None else (1.0, 0.0, "")

    def _unit(self, unit: Entity) -> tuple[float, float, str]:
        if unit.kind == "NRF_EXTENDED_SI_UNIT":
            prefix = _as_text(_at(unit.params, 3))
            name = _as_text(_at(unit.params, 4))
            # A prefixed SI unit would need its power of ten applied; none of
            # the files this reader has met uses one, so it is reported rather
            # than guessed at by the caller that sees the unexpected name.
            return 1.0, 0.0, f"{prefix}{name}"
        if unit.kind == "NRF_CONVERSION_BASED_UNIT":
            reference = self._source.entity(_at(unit.params, 3))
            factor = _as_number(_at(unit.params, 4), default=1.0)
            offset = _as_number(_at(unit.params, 5), default=0.0)
            base = self._unit(reference) if reference is not None else (1.0, 0.0, "")
            return factor * base[0], offset + base[1], base[2]
        if unit.kind == "NRF_DERIVED_UNIT":
            return 1.0, 0.0, _as_text(_at(unit.params, 0))
        return 1.0, 0.0, ""

    def convert(self, value: float, quantity_type: Value) -> tuple[float, str]:
        """*value* in its SI unit, with the unit name for the caller to check."""
        factor, offset, unit = self.scale_of(quantity_type)
        return value / factor + offset, unit

    def literal(self, entity: Entity) -> tuple[float, str]:
        """The single number a ``NRF_*_QUANTITY_VALUE_LITERAL`` holds, in its SI unit."""
        values = _at(entity.params, 1)
        if not isinstance(values, tuple) or len(values) != 1:
            msg = f"{entity!r} is not a single-valued quantity literal"
            raise FieldError(msg)
        raw = values[0]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            msg = f"{entity!r} does not hold a number"
            raise FieldError(msg)
        return self.convert(float(raw), _at(entity.params, 0))


class Fields:
    """One instance's attributes, read by position and by type."""

    __slots__ = ("_source", "_units", "entity")

    def __init__(self, source: Part21File, units: Units, entity: Entity) -> None:
        self._source = source
        self._units = units
        self.entity = entity

    @property
    def name(self) -> str:
        """The instance's identifier, which every named STEP-TAS entity holds first."""
        return self.text(0)

    def __len__(self) -> int:
        return len(self.entity.params)

    def raw(self, index: int) -> Value:
        """The attribute as parsed, or ``None`` past the end of the record."""
        return _at(self.entity.params, index)

    # -- scalars -------------------------------------------------------

    def text(self, index: int, default: str = "") -> str:
        value = self.raw(index)
        if value is None:
            return default
        if not isinstance(value, str):
            raise self._wrong(index, "a string", value)
        return value

    def number(self, index: int, default: float | None = None) -> float:
        value = self.raw(index)
        if value is None and default is not None:
            return default
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise self._wrong(index, "a number", value)
        return float(value)

    def enum(self, index: int, default: str = "") -> str:
        value = self.raw(index)
        if value is None:
            return default
        if not isinstance(value, Enumeration):
            raise self._wrong(index, "an enumeration", value)
        return value.name

    # -- references ----------------------------------------------------

    def entity_at(self, index: int) -> Entity | None:
        """The instance the attribute refers to, or ``None`` if it is unset."""
        value = self.raw(index)
        if value is None:
            return None
        if not isinstance(value, Reference):
            raise self._wrong(index, "a reference", value)
        found = self._source.entity(value)
        if found is None:
            msg = f"{self.entity!r} attribute {index} refers to {value!r}, which is not in the file"
            raise FieldError(msg)
        return found

    def required(self, index: int) -> Entity:
        """The instance the attribute refers to, which must be there."""
        found = self.entity_at(index)
        if found is None:
            msg = f"{self.entity!r} attribute {index} is unset but is needed"
            raise FieldError(msg)
        return found

    def entity_list(self, index: int) -> list[Entity]:
        """Every instance a list attribute refers to, skipping unset slots."""
        found: list[Entity] = []
        for value in self._sequence(index):
            if value is None:
                continue
            if not isinstance(value, Reference):
                raise self._wrong(index, "a list of references", value)
            resolved = self._source.entity(value)
            if resolved is not None:
                found.append(resolved)
        return found

    def numbers(self, index: int) -> tuple[float, ...]:
        """A list attribute of plain numbers."""
        values: list[float] = []
        for value in self._sequence(index):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise self._wrong(index, "a list of numbers", value)
            values.append(float(value))
        return tuple(values)

    def _sequence(self, index: int) -> tuple[Value, ...]:
        value = self.raw(index)
        if value is None:
            return ()
        if not isinstance(value, tuple):
            raise self._wrong(index, "a list", value)
        return tuple(value)

    # -- measured values -----------------------------------------------

    def length(self, index: int) -> float:
        """A length attribute, in metres."""
        return self._measure(index, _METRE)

    def angle(self, index: int) -> float:
        """An angle attribute, in radians."""
        return self._measure(index, _RADIAN)

    def _measure(self, index: int, expected: str) -> float:
        """One ``NRF_*_QUANTITY_VALUE_LITERAL``, converted onto its SI unit."""
        literal = self.required(index)
        value, unit = self._units.literal(literal)
        if unit != expected:
            msg = f"{literal!r} is in {unit or 'an unnamed unit'}, not {expected}"
            raise FieldError(msg)
        return value

    def point(self, index: int) -> npt.NDArray[np.float64]:
        """An ``MGM_3D_CARTESIAN_POINT`` attribute, in metres."""
        return self.point_of(self.required(index))

    def point_of(self, entity: Entity) -> npt.NDArray[np.float64]:
        """The coordinates of a cartesian point, in metres.

        The coordinates are plain numbers followed by the quantity type that
        says what unit they are in, rather than three measured values.
        """
        coordinates: list[float] = []
        for axis in (1, 2, 3):
            raw = _at(entity.params, axis)
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                msg = f"{entity!r} does not hold three coordinates"
                raise FieldError(msg)
            value, unit = self._units.convert(float(raw), _at(entity.params, 4))
            if unit != _METRE:
                msg = f"{entity!r} is in {unit or 'an unnamed unit'}, not metres"
                raise FieldError(msg)
            coordinates.append(value)
        return np.array(coordinates, dtype=np.float64)

    def direction(self, index: int) -> npt.NDArray[np.float64]:
        """An ``MGM_3D_DIRECTION`` attribute, as a unit vector."""
        entity = self.required(index)
        components = np.array(
            [_as_number(_at(entity.params, axis), default=0.0) for axis in (0, 1, 2)],
            dtype=np.float64,
        )
        norm = float(np.linalg.norm(components))
        if norm == 0.0:
            msg = f"{entity!r} is a zero-length direction"
            raise FieldError(msg)
        return components / norm

    def _wrong(self, index: int, expected: str, value: Value) -> FieldError:
        return FieldError(f"{self.entity!r} attribute {index} is {value!r}, not {expected}")


def node_number(node: Entity) -> int | None:
    """The thermal node number an ``NRF_NETWORK_NODE`` carries.

    The number is written as the instance's identifier -- a string -- because
    STEP-TAS lets a node be named rather than numbered.  A name that is not a
    number belongs to a model this reader cannot number, and the caller reports
    it rather than inventing one.
    """
    identifier = _at(node.params, 0)
    if not isinstance(identifier, str):
        return None
    try:
        return int(identifier)
    except ValueError:
        return None


def _at(params: tuple[Value, ...], index: int) -> Value:
    return params[index] if 0 <= index < len(params) else None


def _as_text(value: Value) -> str:
    return value if isinstance(value, str) else ""


def _as_number(value: Value, *, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)
