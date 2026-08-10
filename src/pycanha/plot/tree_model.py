"""The geometry hierarchy as a Qt item model.

The scene tree is walked once into plain :class:`GeometryNode` objects and the
:class:`GeometryTreeModel` is a thin adapter over them. Two things the walk has
to work out, because the core stores neither:

* **what kind** a node is - group, cut group or item - which is decided by its
  type, exactly as :meth:`~pycanha.gmm.GeometryModel.format_tree` decides it;
* **what "cutter" means** - it is *positional*, not a property: a node is a
  cutter because some ``GeometryGroupCutted`` lists it among its ``cutters``.

Each node also carries the ids of every item beneath it, which is what Hide,
Show and Show-only act on: those apply to the whole subtree, while the geometry
that actually owns cells is always an item.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar, cast, overload

import pycanha_core as pcc
from PySide6.QtCore import QAbstractItemModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap

from .state import Change

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtCore import QObject

    from .state import ViewState

#: Qt data role carrying the geometry id of a row, for tests and selection sync.
GEOMETRY_ID_ROLE = int(Qt.ItemDataRole.UserRole) + 1

#: The invalid index Qt passes for "the top level". A module-level singleton
#: because an argument default may not be a call.
_NO_PARENT = QModelIndex()

#: Shown for geometry that was added without a name, as ``format_tree`` does.
ANONYMOUS = "<anonymous>"


class Kind(StrEnum):
    """What a tree row is, as decided by the geometry's type."""

    MODEL = "model"
    GROUP = "group"
    CUT_GROUP = "cut group"
    ITEM = "item"


class CutRole(StrEnum):
    """The part a row plays in its parent cut group, if any."""

    NONE = ""
    TARGET = "target"
    CUTTER = "cutter"


@dataclass
class GeometryNode:
    """One row of the tree: a geometry, its kind, and the items beneath it."""

    name: str
    kind: Kind
    cut_role: CutRole = CutRole.NONE
    geometry: Any | None = None
    geometry_id: int = -1
    primitive: str = ""
    parent: GeometryNode | None = None
    row: int = 0
    children: list[GeometryNode] = field(default_factory=list)
    #: Ids of every item in this subtree - what Hide and Show-only act on.
    item_ids: frozenset[int] = frozenset()

    @property
    def label(self) -> str:
        """Row text: the name, tagged when the parent is a cut group."""
        if self.cut_role is CutRole.NONE:
            return self.name
        return f"[{self.cut_role}] {self.name}"

    @property
    def tooltip(self) -> str:
        """The detail kept out of the label, since the tree has one column."""
        what = self.primitive or self.kind
        return f"{self.name} - {what}" if self.name else what

    def walk(self) -> list[GeometryNode]:
        """This node and every node below it, parents before children."""
        found: list[GeometryNode] = [self]
        for child in self.children:
            found.extend(child.walk())
        return found


def build_tree(model: Any) -> GeometryNode:
    """Walk ``model`` into a :class:`GeometryNode` tree rooted at the model itself.

    The model is a row of its own so that Hide / Show all can be reached from
    the top of the tree, mirroring the header line of ``format_tree``.
    """
    root = GeometryNode(name=model.name or "<unnamed>", kind=Kind.MODEL)
    root.children = [
        _build_node(child, parent=root, row=row, cut_role=CutRole.NONE)
        for row, child in enumerate(model.children)
    ]
    root.item_ids = frozenset().union(*(child.item_ids for child in root.children))
    return root


def _build_node(
    geometry: Any, *, parent: GeometryNode, row: int, cut_role: CutRole
) -> GeometryNode:
    """Turn one geometry into a node, recursing into whatever children it has."""
    node = GeometryNode(
        name=geometry.name or ANONYMOUS,
        kind=_kind_of(geometry),
        cut_role=cut_role,
        geometry=geometry,
        geometry_id=int(geometry.id),
        parent=parent,
        row=row,
    )
    if node.kind is Kind.ITEM:
        node.primitive = type(geometry.primitive).__name__
        node.item_ids = frozenset({node.geometry_id})
        return node

    node.children = [
        _build_node(child, parent=node, row=child_row, cut_role=child_role)
        for child_row, (child, child_role) in enumerate(_child_specs(geometry))
    ]
    node.item_ids = frozenset().union(*(child.item_ids for child in node.children))
    return node


def _kind_of(geometry: Any) -> Kind:
    """Kind of a geometry - the core has no kind tag, so this is its type."""
    if isinstance(geometry, pcc.gmm.GeometryItem):
        return Kind.ITEM
    if isinstance(geometry, pcc.gmm.GeometryGroupCutted):
        return Kind.CUT_GROUP
    return Kind.GROUP


def _child_specs(geometry: Any) -> list[tuple[Any, CutRole]]:
    """Children of a group, with the cut role each of them plays.

    A cut group lists its targets first and then its cutters, each tagged -
    the same order and the same tags ``format_tree`` prints.
    """
    if isinstance(geometry, pcc.gmm.GeometryGroupCutted):
        return [(target, CutRole.TARGET) for target in geometry.targets] + [
            (cutter, CutRole.CUTTER) for cutter in geometry.cutters
        ]
    if isinstance(geometry, pcc.gmm.GeometryGroup):
        return [(child, CutRole.NONE) for child in geometry.children]
    return []


# ── icons ─────────────────────────────────────────────────────────────────
#: Fill / outline color per kind. Mid-tone on purpose: these have to read on
#: both a light and a dark palette, and the tree has no other color.
_ICON_COLORS = {
    Kind.MODEL: "#5c6570",
    Kind.GROUP: "#4a78c8",
    Kind.CUT_GROUP: "#4a78c8",
    Kind.ITEM: "#7a8896",
}
_CUTTER_COLOR = "#c8683c"
_ICON_SIZE = 14
_ICONS: dict[tuple[Kind, CutRole], QIcon] = {}


def kind_icon(kind: Kind, cut_role: CutRole = CutRole.NONE) -> QIcon:
    """A small glyph per kind: outlined for groups, filled for items.

    Cutters get the same filled glyph in their own color, and both cut groups
    and cutters are struck through - the mark of something that removes
    geometry rather than adding it. Drawn rather than loaded so the package
    ships no image assets; cached, since the tree asks per row.
    """
    key = (kind, cut_role)
    if key not in _ICONS:
        _ICONS[key] = _draw_icon(kind, cut_role)
    return _ICONS[key]


def _draw_icon(kind: Kind, cut_role: CutRole) -> QIcon:
    cutter = cut_role is CutRole.CUTTER
    color = QColor(_CUTTER_COLOR if cutter else _ICON_COLORS[kind])
    pixmap = QPixmap(_ICON_SIZE, _ICON_SIZE)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(color)
    box = pixmap.rect().adjusted(2, 2, -2, -2)
    if kind is Kind.ITEM:
        painter.setBrush(QBrush(color))
    painter.drawRoundedRect(box, 2.0, 2.0)
    if cutter or kind is Kind.CUT_GROUP:
        painter.setPen(QColor(_CUTTER_COLOR))
        painter.drawLine(box.bottomLeft(), box.topRight())
    painter.end()
    return QIcon(pixmap)


# ── the Qt model ──────────────────────────────────────────────────────────
class GeometryTreeModel(QAbstractItemModel):
    """One-column item model over a :func:`build_tree` node tree.

    Rows whose whole subtree is hidden are greyed in place rather than checked
    off or removed: the state is already carried by the color, and a checkbox
    column would make Hide look like something the model itself remembers.
    """

    def __init__(self, model: Any, state: ViewState, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.root = build_tree(model)
        self._state = state
        self._nodes = {node.geometry_id: node for node in self.root.walk()}
        # An extra level above the model row, so the model is the single
        # top-level row rather than the invisible root Qt indexes from.
        self._invisible = GeometryNode(name="", kind=Kind.MODEL, children=[self.root])
        self.root.parent = self._invisible
        state.subscribe(self._on_state_change)

    # ── node access ───────────────────────────────────────────────────────
    def node(self, index: QModelIndex | QPersistentModelIndex) -> GeometryNode:
        """The node behind ``index``; the invisible root for an invalid one."""
        if index.isValid():
            return cast("GeometryNode", index.internalPointer())
        return self._invisible

    def node_of(self, geometry_id: int) -> GeometryNode | None:
        """The row for ``geometry_id``, whether it is a group or an item."""
        return self._nodes.get(int(geometry_id))

    def index_of(self, geometry_id: int) -> QModelIndex:
        """The index of the row for ``geometry_id``, or an invalid one."""
        node = self._nodes.get(int(geometry_id))
        if node is None:
            return QModelIndex()
        return self.createIndex(node.row, 0, node)

    # ── QAbstractItemModel ────────────────────────────────────────────────
    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _NO_PARENT) -> int:
        if parent.column() > 0:
            return 0
        return len(self.node(parent).children)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = _NO_PARENT) -> int:
        del parent
        return 1

    def index(
        self, row: int, column: int, parent: QModelIndex | QPersistentModelIndex = _NO_PARENT
    ) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        return self.createIndex(row, column, self.node(parent).children[row])

    @overload
    def parent(self) -> QObject: ...

    @overload
    def parent(self, index: QModelIndex | QPersistentModelIndex, /) -> QModelIndex: ...

    def parent(self, index: QModelIndex | QPersistentModelIndex | None = None) -> Any:
        """The parent index of ``index`` - or, with no argument, the QObject parent.

        Qt spells both of those ``parent()`` on the same class, so the override
        has to keep serving the inherited no-argument form as well.
        """
        if index is None:
            return super().parent()
        parent = self.node(index).parent
        if parent is None or parent is self._invisible:
            return QModelIndex()
        return self.createIndex(parent.row, 0, parent)

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        del section
        if orientation is Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return "Geometry"
        return None

    def _label_data(self, node: GeometryNode) -> Any:
        return node.label

    def _tooltip_data(self, node: GeometryNode) -> Any:
        return node.tooltip

    def _icon_data(self, node: GeometryNode) -> Any:
        return kind_icon(node.kind, node.cut_role)

    def _foreground_data(self, node: GeometryNode) -> Any:
        return QBrush(QColor(Qt.GlobalColor.gray)) if self.is_hidden(node) else None

    def _geometry_id_data(self, node: GeometryNode) -> Any:
        return node.geometry_id

    #: What each Qt data role reads off a row. A table rather than a chain of
    #: comparisons, since Qt asks for one role per row per repaint.
    _ROLE_DATA: ClassVar[dict[int, Callable[[GeometryTreeModel, GeometryNode], Any]]] = {
        int(Qt.ItemDataRole.DisplayRole): _label_data,
        int(Qt.ItemDataRole.ToolTipRole): _tooltip_data,
        int(Qt.ItemDataRole.DecorationRole): _icon_data,
        int(Qt.ItemDataRole.ForegroundRole): _foreground_data,
        GEOMETRY_ID_ROLE: _geometry_id_data,
    }

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if not index.isValid():
            return None
        read = self._ROLE_DATA.get(int(role))
        return None if read is None else read(self, self.node(index))

    # ── visibility ────────────────────────────────────────────────────────
    def is_hidden(self, node: GeometryNode) -> bool:
        """Whether every item beneath ``node`` is hidden, so the row greys out.

        A group greys only once the last of its items is gone, which is what
        makes the color mean "you cannot see any of this" rather than "some of
        this is hidden".
        """
        return bool(node.item_ids) and node.item_ids <= self._state.hidden

    def _on_state_change(self, change: Change) -> None:
        if change is not Change.VISIBILITY:
            return
        # Foreground is the only thing visibility changes, but it changes for
        # arbitrarily many rows at once - one signal per parent covers its
        # children, plus one for the model row, which has no parent to cover it.
        root = self.createIndex(self.root.row, 0, self.root)
        self.dataChanged.emit(root, root, [Qt.ItemDataRole.ForegroundRole])
        for node in self.root.walk():
            if not node.children:
                continue
            parent = self.createIndex(node.row, 0, node)
            first = self.index(0, 0, parent)
            last = self.index(len(node.children) - 1, 0, parent)
            self.dataChanged.emit(first, last, [Qt.ItemDataRole.ForegroundRole])
