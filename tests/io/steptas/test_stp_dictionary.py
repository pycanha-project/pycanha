"""The shipped reference dictionary, against what the writer asks of it.

The dictionary is data, not code, and the writer looks everything up in it by
name.  These pin the lookups: a dictionary that renamed or dropped one of them
would otherwise produce files that are well-formed and mean something else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pycanha.io.steptas import mappings
from pycanha.io.steptas.dictionary import Dictionary, reference_dictionary

if TYPE_CHECKING:
    from pycanha.io.part21 import Value


@pytest.fixture(scope="module")
def dictionary() -> Dictionary:
    return reference_dictionary()


def number(value: Value) -> float:
    """*value* as the number it is meant to be.

    An attribute out of the dictionary is any part-21 value at all; a colour
    channel that arrived as something else is the failure, and saying so here
    names it rather than letting ``float`` complain about the wrong thing.
    """
    assert isinstance(value, (int, float)), f"expected a number, got {value!r}"
    # `.T.` parses to a bool, which is an int in Python and a different literal here.
    assert not isinstance(value, bool), f"expected a number, got {value!r}"
    return float(value)


def test_it_parses_and_every_line_defines_one_instance(dictionary: Dictionary) -> None:
    numbers = [identifier for identifier, _ in dictionary.lines()]
    assert len(numbers) == len(set(numbers))
    assert len(numbers) == len(dictionary.source)


def test_the_instances_it_does_not_define_are_the_ones_a_file_supplies(
    dictionary: Dictionary,
) -> None:
    """Everything reserved is something the writer fills in, and nothing else."""
    date, time = dictionary.date_and_time()
    model, network = dictionary.root_models()
    assert set(dictionary.reserved) == {date, time, model, network, dictionary.environment_item()}


@pytest.mark.parametrize(
    ("kind", "name"),
    [
        ("NRF_NETWORK_NODE_CLASS", "meshed_bounded_surface"),
        ("NRF_NETWORK_NODE_CLASS", "thermal_network_node"),
        ("NRF_NETWORK_MODEL_CLASS", "thermal_radiative_conductive_model"),
        ("NRF_NETWORK_MODEL_CLASS", "thermal_network_model"),
        ("NRF_MATERIAL_CLASS", "thermal_material"),
    ],
)
def test_every_class_the_writer_names_is_there_exactly_once(
    dictionary: Dictionary, kind: str, name: str
) -> None:
    assert dictionary.named(kind, name) > 0


def test_the_geometric_quantity_types_come_from_the_quantity_context(
    dictionary: Dictionary,
) -> None:
    """The dictionary declares length in five units; the context picks one."""
    length = dictionary.source.entities[dictionary.context_quantity_type("length")]
    angle = dictionary.source.entities[dictionary.context_quantity_type("plane_angle")]
    assert dictionary.unit_name(length) == "metre"
    assert dictionary.unit_name(angle) == "degree"


def test_the_material_properties_are_the_thirteen_a_material_row_holds(
    dictionary: Dictionary,
) -> None:
    """The order is the material class's own and has to match the row's."""
    properties = dictionary.material_properties()
    assert len(properties) == len(mappings.MATERIAL_ROW)
    assert [property_type.name for property_type in properties] == [
        "solar_absorptance",
        "solar_direct_transmittance",
        "solar_diffuse_transmittance",
        "solar_specularity",
        "solar_refraction_index",
        "infra_red_emittance",
        "infra_red_direct_transmittance",
        "infra_red_diffuse_transmittance",
        "infra_red_specularity",
        "infra_red_refraction_index",
        "mass_density",
        "constant_pressure_specific_heat_capacity",
        "thermal_conductivity",
    ]


def test_every_material_property_is_in_its_si_unit(dictionary: Dictionary) -> None:
    """A model holds SI values; the wrong quantity type would rescale them all."""
    units = {
        dictionary.unit_name(dictionary.source.entities[property_type.quantity_type])
        for property_type in dictionary.material_properties()
    }
    assert units == {
        "one",
        "kilogram per cubic metre",
        "joule per kilogram kelvin",
        "watt per metre kelvin",
    }


def test_the_colour_table_gives_back_an_exact_colour_unchanged(
    dictionary: Dictionary,
) -> None:
    """The property that matters most: a table colour is nearest to itself."""
    for entity in dictionary.source.of_kind("MGM_COLOUR_RGB"):
        channels = [round(number(entity.params[axis]) * 255) for axis in (1, 2, 3)]
        assert dictionary.nearest_colour(channels) == entity.id


def test_a_colour_of_the_wrong_shape_is_refused(dictionary: Dictionary) -> None:
    with pytest.raises(ValueError, match="three channels"):
        dictionary.nearest_colour((1, 2))
