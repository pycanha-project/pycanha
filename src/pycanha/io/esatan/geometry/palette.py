"""ESATAN's fixed colour palette, and the mapping to and from it.

The format does not carry a colour, it carries the *name* of one of thirty-two
fixed entries.  A :class:`~pycanha.gmm.ThermalMesh` stores the value instead, so
reading resolves a name to its value and writing has to find its way back --
and, since a model may hold any colour at all, writing picks the nearest entry
rather than refusing.

The values here are ESATAN's own, as fractions of full scale.  ``pycanha-core``
ships a palette under the same names whose bytes differ by at most one, because
it truncates ``0.5 * 255`` to 127 where rounding gives 128; that difference is
invisible and is checked by a test rather than papered over.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pycanha.gmm.materials import Color

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["DEFAULT_COLOUR", "PALETTE", "colour_of", "nearest_name"]


@runtime_checkable
class HasRgb(Protocol):
    """Anything carrying 0-255 channels.

    Matched by attribute rather than by class: the compiled colour type and the
    Python one that subclasses it are different classes, and both turn up here.
    """

    @property
    def rgb(self) -> Sequence[int]:
        """The three channels."""
        ...


#: The colour ESATAN gives a surface whose ``colour`` attribute is unset.
DEFAULT_COLOUR = "BLUE_CYAN"

#: Every colour the format has, in the order ESATAN lists them.
#:
#: The order is not cosmetic: it settles ties when two entries are equally close
#: to the colour being written, so the choice is the same on every run.
PALETTE: Mapping[str, tuple[float, float, float]] = {
    "BLUE_CYAN": (0.00, 0.50, 1.00),
    "CYAN": (0.00, 1.00, 1.00),
    "RED": (1.00, 0.00, 0.00),
    "GREEN": (0.00, 1.00, 0.00),
    "BLUE": (0.00, 0.00, 1.00),
    "BLACK": (0.00, 0.00, 0.00),
    "MAGENTA": (1.00, 0.00, 1.00),
    "YELLOW": (1.00, 1.00, 0.00),
    "ORANGE": (1.00, 0.50, 0.00),
    "YELLOW_GREEN": (0.50, 1.00, 0.00),
    "TURQUOISE": (0.00, 1.00, 0.50),
    "VIOLET": (0.50, 0.00, 1.00),
    "PURPLE": (1.00, 0.00, 0.50),
    "VERY_DARK_GREY": (0.33, 0.33, 0.33),
    "LIGHT_GREY": (0.66, 0.66, 0.66),
    "REDDISH_BROWN": (0.75, 0.25, 0.25),
    "ABSINTH": (0.75, 0.75, 0.25),
    "GREY_GREEN": (0.25, 0.75, 0.25),
    "METAL_GREY": (0.25, 0.75, 0.75),
    "LAVENDER": (0.25, 0.25, 0.75),
    "MAGENTA_GREY": (0.75, 0.25, 0.75),
    "DARK_RED": (0.50, 0.00, 0.00),
    "DARK_GREEN": (0.00, 0.50, 0.00),
    "DARK_BLUE": (0.00, 0.00, 0.50),
    "PALE_RED": (1.00, 0.50, 0.50),
    "PALE_GREEN": (0.50, 1.00, 0.50),
    "PALE_BLUE": (0.50, 0.50, 1.00),
    "GREY_BLACK": (0.14, 0.14, 0.14),
    "DARK_GREY": (0.44, 0.44, 0.44),
    "GREY": (0.55, 0.55, 0.55),
    "VERY_LIGHT_GREY": (0.86, 0.86, 0.86),
    "WHITE": (1.00, 1.00, 1.00),
}


def _bytes_of(fractions: tuple[float, float, float]) -> tuple[int, int, int]:
    """A palette entry as the 0-255 channels a colour is stored in."""
    red, green, blue = (round(channel * 255) for channel in fractions)
    return red, green, blue


#: The palette in the units a stored colour uses, built once.
_RGB: Mapping[str, tuple[int, int, int]] = {
    name: _bytes_of(fractions) for name, fractions in PALETTE.items()
}


def colour_of(name: str) -> Color | None:
    """The colour a palette name stands for, or ``None`` if there is no such name."""
    channels = _RGB.get(name.strip().upper())
    return None if channels is None else Color(*channels)


def nearest_name(colour: HasRgb | Sequence[int]) -> str:
    """The palette entry closest to *colour*, by straight-line distance in RGB.

    Plain RGB distance rather than a perceptual metric: the palette is coarse
    and mostly saturated, the result has to be predictable, and what matters
    most is the property a perceptual metric would put at risk -- a colour that
    *is* a palette entry is at distance zero from it, so it always comes back as
    itself.  Ties go to whichever entry ESATAN lists first.
    """
    channels = colour.rgb if isinstance(colour, HasRgb) else colour
    rgb = tuple(int(channel) for channel in channels)
    if len(rgb) != 3:
        msg = f"a colour needs three channels, got {len(rgb)}"
        raise ValueError(msg)

    def distance(entry: tuple[int, int, int]) -> int:
        return sum((one - two) ** 2 for one, two in zip(entry, rgb, strict=True))

    return min(_RGB, key=lambda name: distance(_RGB[name]))
