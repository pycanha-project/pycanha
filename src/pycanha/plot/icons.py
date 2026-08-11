"""The pycanha logo, as the icon every window of the viewer carries.

The logo ships with the package (``pycanha/resources/icons``) in the sizes Qt
and the desktop ask for, from the 16 px a title bar draws to the 1024 px a
scaled taskbar or an application switcher does. They go into **one** ``QIcon``
rather than one file being picked here: Qt chooses the size it needs per use,
and a single 256 px pixmap scaled down to 16 is what makes a title-bar icon
look smudged.

Loading is lazy and cached. A ``QPixmap`` may not be built before there is a
``QGuiApplication``, so the icon cannot be a module constant; and the files are
read through :mod:`importlib.resources`, so it works from a wheel, a zip or a
checkout alike.
"""

from __future__ import annotations

from functools import cache
from importlib import resources
from typing import TYPE_CHECKING

from PySide6.QtGui import QIcon

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

#: Where the icons live inside the installed package.
ICON_DIRECTORY = ("resources", "icons")

#: The sizes shipped, smallest first. Every one is a file of its own.
ICON_SIZES: tuple[int, ...] = (16, 20, 24, 32, 40, 48, 64, 96, 128, 192, 256, 512, 1024)


def icon_file(size: int) -> str:
    """Absolute path of the logo at one size."""
    path = resources.files("pycanha")
    for part in ICON_DIRECTORY:
        path = path / part
    return str(path / f"pycanha_logo_{size}x{size}.png")


@cache
def window_icon() -> QIcon:
    """The pycanha logo, at every size that ships with the package.

    Built once and kept: an icon is asked for by every window, and reading
    thirteen files each time would be thirteen files each time.
    """
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addFile(icon_file(size))
    return icon


def apply_window_icon(widget: QWidget) -> None:
    """Give ``widget`` the pycanha icon, if the files are there.

    A missing or unreadable icon is not a reason for a viewer not to open, so
    an empty one is simply not applied and the window keeps the platform
    default.
    """
    icon = window_icon()
    if not icon.isNull():
        widget.setWindowIcon(icon)
