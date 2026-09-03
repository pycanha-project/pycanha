"""What the viewer is currently showing, independent of any widget.

Everything the interactive window lets you change - which geometry is hidden,
what is selected, how the geometry is colored, which nodes are filtered or
searched for, which result and instant are being read - lives here as plain
Python. **Nothing in this module imports
Qt.** The widgets are a skin over a :class:`ViewState`: they call its mutators
and repaint from its :meth:`~ViewState.subscribe` notifications, which is what
lets the behaviour worth asserting on be tested without a display.

:mod:`pycanha.plot.scene` turns the visibility and filter decisions taken here
into the cell arrays VTK is handed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


#: The coloring a window opens on: the geometry drawn in the colors the model
#: itself carries. It is the one option that describes the model as it was
#: built rather than as it was solved, so it is what "the geometry" looks like -
#: results included, since a loaded result is something to switch *to*.
DEFAULT_COLOR_BY = "color"


class Change(StrEnum):
    """What a :meth:`ViewState.subscribe` callback is being told about.

    One topic per user action, so a listener can repaint only the part it owns:
    rebuilding the rendered subset is expensive, re-reading the property table
    is not.
    """

    VISIBILITY = "visibility"
    SELECTION = "selection"
    COLORING = "coloring"
    FILTER = "filter"
    PICKER = "picker"
    RESULTS = "results"
    EDGES = "edges"


class PickerMode(StrEnum):
    """How much of the model a 3D pick selects and reports.

    The mode changes the highlight and the property table only: hiding from the
    3D context menu always acts on the owning geometry item, whatever is set
    here, because a single triangle has no tree row to carry a hidden state.
    """

    #: The whole owning ``GeometryItem``.
    ITEM = "item"
    #: One face - both triangles of a quad face, one ThermalMesh side.
    FACE = "face"
    #: The single picked triangle.
    TRIANGLE = "triangle"


@dataclass(frozen=True)
class Selection:
    """The one entity currently selected, from either the tree or a 3D pick.

    A tree selection fills in ``item_id`` alone; a pick fills in everything it
    resolved. ``cell`` indexes the *master* polydata (see
    :class:`pycanha.plot.scene.Scene`), not the rendered visible subset.
    """

    item_id: int | None = None
    face_id: int | None = None
    node_number: int | None = None
    cell: int | None = None


@dataclass(frozen=True)
class ColorScale:
    """How the current numeric coloring is mapped to colors.

    ``limits`` is honoured only when ``auto`` is off; with ``auto`` on the
    viewer takes the range from the data. Categorical colorings ignore all of
    it except ``colormap``, which they read as the qualitative palette.

    Immutable, so a panel changes one knob with
    ``state.scale = replace(state.scale, log=True)`` and gets exactly one
    :attr:`Change.COLORING` notification.
    """

    colormap: str = "viridis"
    reverse: bool = False
    log: bool = False
    auto: bool = True
    limits: tuple[float, float] | None = None


@dataclass(frozen=True)
class EdgeDisplay:
    """Which of the three sets of lines are drawn over the geometry.

    Independent of each other and of everything else: ``triangles`` is the
    actor's own ``show_edges``, while the other two are overlay actors built by
    :mod:`pycanha.plot.edges`.

    Face edges are on by default.
    """

    triangles: bool = False
    faces: bool = True
    primitives: bool = False


@dataclass(frozen=True)
class ResultSelection:
    """Which result is being looked at: a case, an attribute, and an instant.

    ``time_index`` is an index into the case's **stored** instants, never a
    time: the slider snaps to what the solver wrote rather than interpolating
    between two of them.

    Immutable for the same reason as :class:`ColorScale`: a panel changes one
    of the three and gets exactly one :attr:`Change.RESULTS` notification.
    """

    case: str
    attribute: str
    time_index: int = 0


class ViewState:
    """Mutable view state, with a callback per changed topic.

    ``item_ids`` is the set of geometry items the model can show, which is what
    :meth:`show_only` needs in order to hide everything else. Hiding an id
    outside it is still allowed and still remembered - an item cut away
    entirely owns no faces yet keeps its tree row, and that row has to be able
    to grey out like any other.
    """

    def __init__(self, item_ids: Iterable[int] = ()) -> None:
        self.item_ids = frozenset(int(item_id) for item_id in item_ids)
        self._subscribers: list[Callable[[Change], None]] = []
        self._result: ResultSelection | None = None
        self._set_defaults()

    def _set_defaults(self) -> None:
        """Every knob :meth:`reset` puts back, in one place so the two agree.

        The result selection is deliberately not among them: which case is
        loaded is the results strip's to say, and it rewinds itself.
        """
        self._hidden: frozenset[int] = frozenset()
        self._selection: Selection | None = None
        self._picker_mode = PickerMode.FACE
        self._color_by = DEFAULT_COLOR_BY
        self._scale = ColorScale()
        self._lighting = False
        self._hidden_categories: frozenset[int] = frozenset()
        self._node_range: tuple[int, int] | None = None
        self._found_node: int | None = None
        self._edges = EdgeDisplay()

    def reset(self) -> None:
        """Put every knob back to the value the window opened with.

        Notifies every topic it owns rather than only the ones that changed:
        a reset is one deliberate action, and a panel that repaints itself into
        the state it was already in costs nothing. :attr:`result` is left alone
        - the results strip rewinds itself, and it is the one thing here that
        depends on what the model holds.
        """
        self._set_defaults()
        for change in (
            Change.VISIBILITY,
            Change.SELECTION,
            Change.COLORING,
            Change.FILTER,
            Change.PICKER,
            Change.EDGES,
        ):
            self._notify(change)

    # ── notification ──────────────────────────────────────────────────────
    def subscribe(self, callback: Callable[[Change], None]) -> None:
        """Call ``callback(change)`` after every mutation that changes something.

        A mutation that leaves the state as it was notifies nobody, so a widget
        never repaints because a checkbox was re-set to the value it had.
        """
        self._subscribers.append(callback)

    def _notify(self, change: Change) -> None:
        for callback in self._subscribers:
            callback(change)

    # ── visibility ────────────────────────────────────────────────────────
    @property
    def hidden(self) -> frozenset[int]:
        """Geometry ids currently hidden: not drawn, and not pickable."""
        return self._hidden

    def is_hidden(self, item_id: int) -> bool:
        """Whether geometry ``item_id`` is currently hidden."""
        return int(item_id) in self._hidden

    def hide(self, item_ids: Iterable[int]) -> None:
        """Hide every id in ``item_ids``, keeping whatever is already hidden."""
        self._set_hidden(self._hidden | {int(i) for i in item_ids})

    def show(self, item_ids: Iterable[int]) -> None:
        """Un-hide every id in ``item_ids``, leaving the rest alone."""
        self._set_hidden(self._hidden - {int(i) for i in item_ids})

    def show_only(self, item_ids: Iterable[int]) -> None:
        """Show exactly ``item_ids`` and hide every other known item."""
        self._set_hidden(self.item_ids - {int(i) for i in item_ids})

    def show_all(self) -> None:
        """Un-hide everything, geometry and legend categories alike.

        The one unambiguous reset, so it covers both sources of invisibility.
        It does not touch the node filter, which only greys.
        """
        if not self._hidden and not self._hidden_categories:
            return
        self._hidden = frozenset()
        self._hidden_categories = frozenset()
        self._notify(Change.VISIBILITY)

    def _set_hidden(self, hidden: frozenset[int]) -> None:
        if hidden == self._hidden:
            return
        self._hidden = hidden
        self._notify(Change.VISIBILITY)

    # ── selection ─────────────────────────────────────────────────────────
    @property
    def selection(self) -> Selection | None:
        """The single selected entity, or ``None`` when nothing is selected."""
        return self._selection

    @selection.setter
    def selection(self, selection: Selection | None) -> None:
        if selection == self._selection:
            return
        self._selection = selection
        self._notify(Change.SELECTION)

    @property
    def picker_mode(self) -> PickerMode:
        """Granularity a pick selects and reports."""
        return self._picker_mode

    @picker_mode.setter
    def picker_mode(self, mode: PickerMode) -> None:
        if mode == self._picker_mode:
            return
        self._picker_mode = mode
        self._notify(Change.PICKER)

    # ── coloring ──────────────────────────────────────────────────────────
    @property
    def color_by(self) -> str:
        """Name of the property the geometry is colored by."""
        return self._color_by

    @color_by.setter
    def color_by(self, name: str) -> None:
        if name == self._color_by:
            return
        self._color_by = name
        # Category numbers only mean something within one coloring: category 3
        # of "item" and category 3 of "optical material" are unrelated, so the
        # legend's hidden set cannot survive the switch.
        self._hidden_categories = frozenset()
        self._notify(Change.COLORING)

    @property
    def hidden_categories(self) -> frozenset[int]:
        """Categories of the current coloring that the legend has switched off.

        A second source of invisibility beside :attr:`hidden`, and a different
        kind: that one hides *geometry*, this one hides everything sharing a
        value. Cleared whenever :attr:`color_by` changes.
        """
        return self._hidden_categories

    @hidden_categories.setter
    def hidden_categories(self, categories: Iterable[int]) -> None:
        wanted = frozenset(int(category) for category in categories)
        if wanted == self._hidden_categories:
            return
        self._hidden_categories = wanted
        self._notify(Change.VISIBILITY)

    @property
    def edges(self) -> EdgeDisplay:
        """Which sets of edge lines are drawn over the geometry."""
        return self._edges

    @edges.setter
    def edges(self, edges: EdgeDisplay) -> None:
        if edges == self._edges:
            return
        self._edges = edges
        self._notify(Change.EDGES)

    @property
    def lighting(self) -> bool:
        """Whether the geometry is shaded rather than drawn flat.

        Off by default: the coloring is data, and a shaded face shows a
        gradient of it that no color bar and no legend swatch accounts for.
        Turned on it is the surface normal that is being read instead, which is
        what makes a curved primitive legible.
        """
        return self._lighting

    @lighting.setter
    def lighting(self, lighting: bool) -> None:
        wanted = bool(lighting)
        if wanted == self._lighting:
            return
        self._lighting = wanted
        self._notify(Change.COLORING)

    @property
    def scale(self) -> ColorScale:
        """Colormap and limits of the current coloring."""
        return self._scale

    @scale.setter
    def scale(self, scale: ColorScale) -> None:
        if scale == self._scale:
            return
        self._scale = scale
        self._notify(Change.COLORING)

    # ── the node filter ───────────────────────────────────────────────────
    # One filter, set either as a range or as a single node. Both grey the
    # faces they leave out rather than hiding them, so the filter stays
    # independent of :attr:`hidden` and ``Show all`` means one thing. They are
    # mutually exclusive because they are the same filter: setting one drops
    # the other, and :meth:`clear_filter` drops whichever is set.
    @property
    def node_range(self) -> tuple[int, int] | None:
        """Inclusive ``(lo, hi)`` node filter, or ``None`` when it is not set that way."""
        return self._node_range

    @property
    def found_node(self) -> int | None:
        """Single node the filter is set to, or ``None`` when it is not set that way."""
        return self._found_node

    @found_node.setter
    def found_node(self, node_number: int | None) -> None:
        """Grey every face except the ones belonging to one node."""
        node = None if node_number is None else int(node_number)
        if node is None:
            self.clear_filter()
            return
        if node == self._found_node and self._node_range is None:
            return
        self._found_node = node
        self._node_range = None
        self._notify(Change.FILTER)

    @property
    def filtered(self) -> bool:
        """Whether any node filter is in force."""
        return self._node_range is not None or self._found_node is not None

    def node_bounds(self) -> tuple[int, int] | None:
        """The filter as one inclusive range, however it was set.

        A single found node is the range that holds only it, which is what
        makes the two boxes one filter rather than two overlays that have to
        agree with each other.
        """
        if self._node_range is not None:
            return self._node_range
        if self._found_node is None:
            return None
        return (self._found_node, self._found_node)

    def set_node_range(self, lo: int, hi: int) -> None:
        """Grey every face whose node number falls outside ``[lo, hi]``.

        The bounds are ordered, so a filter box that gets them the wrong way
        round still selects the range between them rather than nothing.
        """
        bounds = (min(int(lo), int(hi)), max(int(lo), int(hi)))
        if bounds == self._node_range and self._found_node is None:
            return
        self._node_range = bounds
        self._found_node = None
        self._notify(Change.FILTER)

    def clear_filter(self) -> None:
        """Drop the node filter, un-greying everything it greyed."""
        if not self.filtered:
            return
        self._node_range = None
        self._found_node = None
        self._notify(Change.FILTER)

    # ── results ───────────────────────────────────────────────────────────
    @property
    def result(self) -> ResultSelection | None:
        """The case, attribute and instant currently read from the results.

        ``None`` before anything has been chosen, and for a model with no
        results at all - which is what lets a geometry-only viewer leave the
        results panel out entirely.
        """
        return self._result

    @result.setter
    def result(self, result: ResultSelection | None) -> None:
        if result == self._result:
            return
        self._result = result
        self._notify(Change.RESULTS)
