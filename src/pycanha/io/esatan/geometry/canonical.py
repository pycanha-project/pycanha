"""How ESATAN writes a geometry file: numbers, vectors and block scaffolding.

Kept apart from the writer itself because these are properties of the *format*
rather than decisions about what to emit, and because the number format in
particular is fiddly enough to deserve its own tests.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

__all__ = [
    "ATTRIBUTE_ORDER",
    "BLOCKS",
    "block",
    "format_real",
    "format_vector",
    "indent_arguments",
    "sort_attributes",
]

#: Below this magnitude a number is written in exponent form.
_SMALL = 0.01

#: At or above this magnitude a number is written in exponent form.
_LARGE = 1.0e7

#: Significant digits kept in either form.
_SIGNIFICANT = 8

#: Decimal places never exceeded in fixed form, whatever the magnitude.
#:
#: This is the constraint that stops the two rules being the same one: at 8
#: significant digits ``0.01234567890123`` would need nine decimal places, and
#: the format keeps seven.
_MAX_DECIMALS = 7


def format_real(value: float) -> str:
    """Render *value* the way an ESATAN geometry file writes a real.

    Fixed notation between 0.01 and 1e7 and exponent notation outside it, in
    both cases to eight significant digits but never more than seven decimal
    places, with trailing zeros removed and always at least one decimal:

    >>> format_real(0.4)
    '0.4'
    >>> format_real(360.0)
    '360.0'
    >>> format_real(0.002)
    '2.0e-03'
    >>> format_real(123456.789)
    '123456.79'
    >>> format_real(0.01234567890123)
    '0.0123457'
    """
    number = float(value)
    if number == 0.0 or not math.isfinite(number):
        # A non-finite value cannot be written at all; zero would otherwise take
        # the exponent branch, since its magnitude is below the small threshold.
        return "0.0"

    magnitude = abs(number)
    if _SMALL <= magnitude < _LARGE:
        exponent = math.floor(math.log10(magnitude))
        decimals = min(_MAX_DECIMALS, max(0, _SIGNIFICANT - 1 - exponent))
        return _trim(f"{number:.{decimals}f}")

    mantissa, _, exponent_text = f"{number:.{_SIGNIFICANT - 1}e}".partition("e")
    return f"{_trim(mantissa)}e{exponent_text}"


def _trim(text: str) -> str:
    """Drop trailing zeros from a decimal string, leaving at least one."""
    if "." not in text:
        return text + ".0"
    trimmed = text.rstrip("0")
    return trimmed + "0" if trimmed.endswith(".") else trimmed


def format_vector(values: Sequence[float]) -> str:
    """Render a point or a triple as ESATAN's bracketed list."""
    return "[" + ", ".join(format_real(value) for value in values) + "]"


#: The blocks of an ESATAN geometry file, in the order they are written.
#:
#: Every one is emitted even when empty -- that is what the format does, and a
#: file missing a block reads as truncated rather than as having nothing to say.
BLOCKS = (
    "independent variable",
    "geometry vectors and matrices declaration",
    "bound variable",
    "primitive",
    "structure",
    "conductive interface",
    "group",
    "conductor",
    "contact zone",
)


def block(name: str, body: Iterable[str] = ()) -> list[str]:
    """Wrap *body* in the start and end markers for the named block."""
    lines = [f"/* Start of {name} block */", ""]
    lines.extend(body)
    if lines[-1] != "":
        lines.append("")
    lines.append(f"/* End of {name} block - no errors */")
    return lines


def _attribute_order() -> tuple[str, ...]:
    """Every non-shape attribute, in the order an ESATAN geometry file writes them.

    The order is the same for every primitive -- only the leading shape
    arguments differ -- so one sequence covers them all.  Mesh directions run 1
    to 4 (a prism has four), sides 1 to 2.
    """
    keys: list[str] = ["sense"]
    for direction in (1, 2, 3, 4):
        keys += [f"meshType{direction}", f"nodes{direction}", f"ratio{direction}"]
        keys.append(f"meshPositions{direction}")
    keys.append("analysis_type")
    for side in (1, 2):
        keys += [f"label{side}", f"side{side}", f"criticality{side}", f"model{side}"]
        keys += [f"nbase{side}", f"ndelta{side}", f"ndelta{side}_1", f"ndelta{side}_2"]
        keys += [f"opt{side}", f"insulation{side}", f"colour{side}"]
    keys += ["composition", "bulk", "thick", "bulk1", "thick1", "bulk2", "thick2"]
    keys += ["through_cond", "conductance", "emittance"]
    return tuple(keys)


#: The canonical attribute order, as a name -> position lookup.
ATTRIBUTE_ORDER: dict[str, int] = {key: index for index, key in enumerate(_attribute_order())}


def sort_attributes(attributes: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """Put *attributes* into the order the format writes them.

    Raises on a name the format does not have: emitting one would produce a file
    ESATAN rejects, and silently sorting it to the end would hide that.
    """
    pairs = list(attributes)
    unknown = [key for key, _ in pairs if key not in ATTRIBUTE_ORDER]
    if unknown:
        msg = f"not ESATAN geometry attributes: {', '.join(sorted(unknown))}"
        raise KeyError(msg)
    return sorted(pairs, key=lambda pair: ATTRIBUTE_ORDER[pair[0]])


def indent_arguments(call: str, arguments: Sequence[tuple[str, str]]) -> list[str]:
    """Lay out ``NAME (\\n    key = value,\\n    ...);`` the way the format does."""
    if not arguments:
        return [f"{call} ();"]
    lines = [f"{call} ("]
    for index, (key, value) in enumerate(arguments):
        terminator = "," if index < len(arguments) - 1 else ");"
        lines.append(f"    {key} = {value}{terminator}")
    return lines
