"""The fixed part of a STEP-TAS file, and the way into it.

Nine tenths of a STEP-TAS geometry file is a *reference dictionary*: several
hundred instances declaring quantity categories, units, quantity types, node
and material classes, and the colour table.  None of it says anything about
the model being exchanged -- it is the vocabulary every file in this protocol
draws on, and it is identical from one file to the next.

It ships with pycanha as :file:`reference_dictionary.p21`, a fragment of a
part-21 data section, one instance per line.  Writing a file emits it verbatim:
the dictionary is not something to derive, it is something to carry, and text
that has been read by the tools this format exists to exchange with is a better
starting point than a reconstruction.

Nothing else in the writer holds an instance number.  Everything it needs from
the dictionary is looked up by *name* -- the length quantity type, the classes
a node or a model belongs to, the quantity type behind each material property
-- and the three instances the dictionary refers to without defining are
recovered from the references themselves (:attr:`Dictionary.reserved`).  So a
later dictionary that numbers things differently costs nothing, and one that
renames or drops something fails loudly at load rather than quietly writing a
file that means something else.
"""

from __future__ import annotations

import re
from functools import cache
from importlib import resources
from typing import TYPE_CHECKING, Final, NamedTuple

from ..part21 import Reference, parse_part21

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from ..part21 import Entity, Part21File, Value

__all__ = ["SCHEMA", "Dictionary", "MaterialProperty", "reference_dictionary"]

#: The shipped dictionary, as a resource of this package.
_RESOURCE: Final = "reference_dictionary.p21"

#: The schema the shipped dictionary belongs to, as a file header names it.
#:
#: It lives here rather than in the writer because it and the dictionary are one
#: version of one thing: a file may not claim this schema and then draw on some
#: other vocabulary.
SCHEMA: Final = "tas_arm {http://www.purl.org/ESA/step-tas/v6.0/tas_arm.exp}"

#: The one place an instance number appears in this module: a line of the
#: fragment starts with the number it defines.
_DEFINITION = re.compile(r"#(\d+)=")

#: Every reference in a line, used to find what the dictionary does not define.
_REFERENCE = re.compile(r"#(\d+)")

#: The material class whose properties a surface material and a bulk material
#: between them supply.
_MATERIAL_CLASS: Final = "thermal_material"

#: The quantity type naming the environment a material's properties hold in.
_ENVIRONMENT_TYPE: Final = "material_property_environment_name"

#: Where each entity this module reads keeps what is wanted from it.
_ROOT_MODELS: Final = 18
_ENUMERATION_ITEMS: Final = 6
_CLASS_SUBCLASSES: Final = 3
_CLASS_PROPERTIES: Final = 4
_QUANTITY_CATEGORY: Final = 6
_QUANTITY_UNIT: Final = 7
_CATEGORY_BASE: Final = 10
_CATEGORY_QUALIFIERS: Final = 11
_CONTEXT_TYPES: Final = 0
_STAMP_DATE: Final = 0
_STAMP_TIME: Final = 1


class DictionaryError(Exception):
    """Raised when the shipped dictionary is not the one this writer expects."""


class MaterialProperty(NamedTuple):
    """One of the thirteen values a material carries, and where it belongs."""

    name: str
    """The property's name, as its material class requires it."""

    quantity_type: int
    """The instance defining what the value means and what unit it is in."""


#: The unit each material property is written in.
#:
#: The dictionary defines the same property in more than one unit -- density in
#: kilograms per cubic metre and in pounds per cubic foot, and so on -- so the
#: name alone does not pick one out.  pycanha holds SI values, so the SI unit is
#: named here and the lookup fails rather than guesses if it is ever absent.
_PROPERTY_UNITS: Final[dict[str, str]] = {
    "solar_absorptance": "one",
    "solar_direct_transmittance": "one",
    "solar_diffuse_transmittance": "one",
    "solar_specularity": "one",
    "solar_refraction_index": "one",
    "infra_red_emittance": "one",
    "infra_red_direct_transmittance": "one",
    "infra_red_diffuse_transmittance": "one",
    "infra_red_specularity": "one",
    "infra_red_refraction_index": "one",
    "mass_density": "kilogram per cubic metre",
    "constant_pressure_specific_heat_capacity": "joule per kilogram kelvin",
    "thermal_conductivity": "watt per metre kelvin",
}


class Dictionary:
    """The shipped reference dictionary: its text, and what can be found in it."""

    def __init__(self, text: str) -> None:
        self._lines: dict[int, str] = {}
        for line in text.splitlines():
            match = _DEFINITION.match(line)
            if match is not None:
                self._lines[int(match.group(1))] = line
        # The resource is a data section without its surroundings, so that a
        # writer can emit it straight into one.  Parsing it needs them back.
        self.source: Part21File = parse_part21(
            "ISO-10303-21;\nDATA;\n" + text + "ENDSEC;\nEND-ISO-10303-21;\n"
        )
        self.reserved: tuple[int, ...] = self._reserved()

    # -- the text ----------------------------------------------------------

    def lines(self) -> Iterator[tuple[int, str]]:
        """Every instance, as the number it defines and the line defining it."""
        yield from self._lines.items()

    def _reserved(self) -> tuple[int, ...]:
        """The instances the dictionary refers to but does not define.

        These are the parts of a file that are always in the same place because
        the dictionary points at them: the geometric model, the network model
        holding the thermal nodes, and the one material property environment.
        A writer has to supply them under exactly these numbers, and asking the
        dictionary which they are is what keeps them out of the writer.
        """
        referred: set[int] = set()
        for line in self._lines.values():
            referred.update(int(found) for found in _REFERENCE.findall(line))
        return tuple(sorted(referred - set(self._lines)))

    # -- lookups -----------------------------------------------------------

    def named(self, kind: str, name: str) -> int:
        """The instance of type *kind* whose first attribute is *name*."""
        wanted = [entity for entity in self.source.of_kind(kind) if _at(entity.params, 0) == name]
        if len(wanted) != 1:
            msg = f"the dictionary defines {len(wanted)} {kind} instances named {name!r}, not one"
            raise DictionaryError(msg)
        return wanted[0].id

    def sole(self, kind: str) -> int:
        """The one instance of type *kind*."""
        found = self.source.of_kind(kind)
        if len(found) != 1:
            msg = f"the dictionary defines {len(found)} {kind} instances, not one"
            raise DictionaryError(msg)
        return found[0].id

    def root_models(self) -> tuple[int, int]:
        """The geometric model and the network model the dataset's root names.

        The dictionary's root instance already lists them, which is why they are
        reserved: a file whose models are numbered otherwise would leave the
        root pointing at nothing.
        """
        root = self.source.entities[self.sole("NRF_ROOT")]
        models = [value.id for value in _sequence(_at(root.params, _ROOT_MODELS))]
        expected = 2
        if len(models) != expected:
            msg = f"the dictionary's root names {len(models)} models, not {expected}"
            raise DictionaryError(msg)
        return models[0], models[1]

    def environment_item(self) -> int:
        """The enumeration item naming the one material property environment."""
        environment = self.source.entities[
            self.named("NRF_ENUMERATION_QUANTITY_TYPE", _ENVIRONMENT_TYPE)
        ]
        items = [value.id for value in _sequence(_at(environment.params, _ENUMERATION_ITEMS))]
        if len(items) != 1:
            msg = f"the dictionary allows {len(items)} material property environments, not one"
            raise DictionaryError(msg)
        return items[0]

    def environment_type(self) -> int:
        """The quantity type the material property environment list is keyed on."""
        return self.named("NRF_ENUMERATION_QUANTITY_TYPE", _ENVIRONMENT_TYPE)

    def date_and_time(self) -> tuple[int, int]:
        """The calendar date and the local time the dataset's stamp is made of.

        Both are reserved rather than shipped: everything else about a file is
        the same every time it is written, and these two are not.
        """
        stamp = self.source.entities[self.sole("NRF_DATE_AND_TIME")]
        parts = [
            value.id
            for index in (_STAMP_DATE, _STAMP_TIME)
            if isinstance(value := _at(stamp.params, index), Reference)
        ]
        expected = 2
        if len(parts) != expected:
            msg = "the dictionary's date and time does not name both a date and a time"
            raise DictionaryError(msg)
        return parts[0], parts[1]

    def utc_offset(self) -> int:
        """The time offset that is no offset, which is what a written time uses."""
        for entity in self.source.of_kind("NRF_COORDINATED_UNIVERSAL_TIME_OFFSET"):
            if _number(_at(entity.params, 0)) == 0.0 and _number(_at(entity.params, 1)) == 0.0:
                return entity.id
        msg = "the dictionary has no zero universal time offset"
        raise DictionaryError(msg)

    # -- quantity types ----------------------------------------------------

    def context_quantity_type(self, name: str) -> int:
        """A geometric quantity type, taken from the model's quantity context.

        Lengths and angles are not looked up by name across the whole
        dictionary, which defines each of them in several units.  The quantity
        context lists the one of each that a model's geometry is expressed in,
        and that is by definition the one to write in.
        """
        context = self.source.entities[self.sole("MGM_QUANTITY_CONTEXT")]
        for value in _sequence(_at(context.params, _CONTEXT_TYPES)):
            entity = self.source.entity(value)
            if entity is not None and self.quantity_name(entity) == name:
                return entity.id
        msg = f"the dictionary's quantity context has no {name!r} quantity type"
        raise DictionaryError(msg)

    def material_properties(self) -> tuple[MaterialProperty, ...]:
        """The thirteen properties of a thermal material, in the order they go.

        The order is the material class's own: a class lists the properties it
        requires, and the values a model carries are given in that order.
        Reading it out of the dictionary rather than restating it here means the
        two cannot disagree.
        """
        names = _class_properties(self.source, self.named("NRF_MATERIAL_CLASS", _MATERIAL_CLASS))
        return tuple(MaterialProperty(name, self._property_type(name)) for name in names)

    def _property_type(self, name: str) -> int:
        unit = _PROPERTY_UNITS.get(name)
        if unit is None:
            msg = f"no unit is declared for the material property {name!r}"
            raise DictionaryError(msg)
        for entity in self.source.of_kind("NRF_REAL_QUANTITY_TYPE"):
            if self.quantity_name(entity) == name and self.unit_name(entity) == unit:
                return entity.id
        msg = f"the dictionary has no {name!r} quantity type in {unit}"
        raise DictionaryError(msg)

    def quantity_name(self, quantity_type: Entity) -> str:
        """The name of a quantity type, which its category and qualifiers give.

        A physical quantity type leaves its own name unset and takes it from the
        category it measures; a qualified category prefixes that name with each
        of its qualifiers, so that ``absorptance`` qualified by ``solar`` is
        ``solar_absorptance``.
        """
        category = _at(quantity_type.params, _QUANTITY_CATEGORY)
        return self._category_name(self.source.entity(category))

    def _category_name(self, category: Entity | None) -> str:
        if category is None:
            return ""
        if category.kind == "NRF_QUALIFIED_PHYSICAL_QUANTITY_CATEGORY":
            base = self._category_name(self.source.entity(_at(category.params, _CATEGORY_BASE)))
            qualifiers = [
                _text(_at(entity.params, 0))
                for value in _sequence(_at(category.params, _CATEGORY_QUALIFIERS))
                if (entity := self.source.entity(value)) is not None
            ]
            return "_".join([*qualifiers, base])
        return _text(_at(category.params, 0))

    def unit_name(self, quantity_type: Entity) -> str:
        """The name of the unit a quantity type is expressed in."""
        return self._unit_name(self.source.entity(_at(quantity_type.params, _QUANTITY_UNIT)))

    def _unit_name(self, unit: Entity | None) -> str:
        if unit is None:
            return ""
        if unit.kind == "NRF_EXTENDED_SI_UNIT":
            return _text(_at(unit.params, 3)) + _text(_at(unit.params, 4))
        if unit.kind == "NRF_CONVERSION_BASED_UNIT":
            return _text(_at(unit.params, 0))
        return _text(_at(unit.params, 0))

    # -- colours -----------------------------------------------------------

    def nearest_colour(self, rgb: Sequence[int]) -> int:
        """The colour instance closest to *rgb*, whose channels are 0 to 255.

        The dictionary carries a fixed table of colours and a model may hold any
        colour at all, so writing picks the nearest entry rather than refusing.
        Distance is plain and in RGB: the table is coarse, the answer has to be
        the same on every run, and what matters most is that a colour which *is*
        a table entry comes back as that entry.  Ties go to the first listed.
        """
        wanted = tuple(int(channel) for channel in rgb)
        expected = 3
        if len(wanted) != expected:
            msg = f"a colour needs three channels, got {len(wanted)}"
            raise ValueError(msg)

        def distance(entity: Entity) -> int:
            channels = (round(_number(_at(entity.params, axis)) * 255) for axis in (1, 2, 3))
            return sum((one - two) ** 2 for one, two in zip(channels, wanted, strict=True))

        return min(self.source.of_kind("MGM_COLOUR_RGB"), key=distance).id


def _class_properties(source: Part21File, material_class: int) -> list[str]:
    """Every property name a material class and its subclasses require."""
    entity = source.entities[material_class]
    required = _at(entity.params, _CLASS_PROPERTIES)
    names = [_text(value) for value in required] if isinstance(required, tuple) else []
    for value in _sequence(_at(entity.params, _CLASS_SUBCLASSES)):
        subclass = source.entity(value)
        if subclass is not None:
            names.extend(_class_properties(source, subclass.id))
    return names


def _at(params: tuple[Value, ...], index: int) -> Value:
    return params[index] if 0 <= index < len(params) else None


def _sequence(value: Value) -> tuple[Reference, ...]:
    if not isinstance(value, tuple):
        return ()
    return tuple(item for item in value if isinstance(item, Reference))


def _text(value: Value) -> str:
    return value if isinstance(value, str) else ""


def _number(value: Value) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


@cache
def reference_dictionary() -> Dictionary:
    """The shipped dictionary, read and parsed once."""
    text = resources.files(__package__).joinpath(_RESOURCE).read_text(encoding="utf-8")
    return Dictionary(text)
