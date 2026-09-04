"""Frozen dataclasses describing an ESATAN Workbench statement tree.

There is deliberately **no dataclass per ESATAN function**.  ``SHELL_RECTANGLE``
and ``DEFINE_MISSION`` are both a :class:`Call` carrying named arguments; typing
them individually would freeze the function vocabulary into the tree and force a
change here every time a new statement becomes supported.  The vocabulary lives
in the builder's dispatch tables instead.

Every node carries the source ``line`` / ``end_line`` it came from, so a
diagnostic can point at the statement that caused it.  Those two fields are
keyword-only, which lets each node keep a natural positional signature.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "Array",
    "Assignment",
    "BinOp",
    "Bool",
    "Call",
    "CallStmt",
    "Declaration",
    "Define",
    "Delete",
    "Expr",
    "ForBlock",
    "IfBlock",
    "Include",
    "Index",
    "Lvalue",
    "ModelFile",
    "Num",
    "Positioned",
    "RepeatBlock",
    "Statement",
    "Str",
    "SwitchBlock",
    "SwitchCase",
    "UnaryOp",
    "Vector",
    "WhileBlock",
]


@dataclass(frozen=True)
class Positioned:
    """Base for every node, carrying the source span it was parsed from."""

    line: int = field(default=0, kw_only=True)
    end_line: int = field(default=0, kw_only=True)
    source: str = field(default="", kw_only=True)
    """File the node came from -- an included fragment keeps its own name and line numbers."""


# -- expressions -----------------------------------------------------------


@dataclass(frozen=True)
class Num(Positioned):
    """A numeric literal.  Integers stay integers so node numbers keep their type."""

    value: float | int


@dataclass(frozen=True)
class Str(Positioned):
    """A double-quoted string, already stripped of its quotes.

    Backslashes are literal in this language, so the text is exactly what was
    between the quotes.
    """

    value: str


@dataclass(frozen=True)
class Bool(Positioned):
    """A ``TRUE`` / ``FALSE`` literal."""

    value: bool


@dataclass(frozen=True)
class Ref(Positioned):
    """A reference to a symbol, possibly with a dotted attribute path."""

    path: tuple[str, ...]

    @property
    def name(self) -> str:
        """The leading symbol name, without any attribute path."""
        return self.path[0]


@dataclass(frozen=True)
class Index(Positioned):
    """One element of an array, ``grid[255]``.

    ``indices`` are expressions rather than numbers because the subscript may
    be computed, and they count from one.
    """

    target: Ref
    indices: tuple[Expr, ...]

    @property
    def name(self) -> str:
        """The array being indexed."""
        return self.target.name


@dataclass(frozen=True)
class Vector(Positioned):
    """A bracketed ``[a, b, c]`` literal: a point, a bulk triple, an optical row."""

    items: tuple[Expr, ...]


@dataclass(frozen=True)
class Array(Positioned):
    """A braced ``{a, b, c}`` literal: a group membership list or a matrix initialiser."""

    items: tuple[Expr, ...]


@dataclass(frozen=True)
class Call(Positioned):
    """A procedure or function call.

    ``args`` holds the named arguments with their ESATAN spelling folded to lower
    case, because the language treats attribute names case-insensitively and the
    corpus mixes ``nbase1`` inside constructors with ``NBASE1`` in dotted
    assignments.  ``positional`` holds the unnamed arguments the predefined
    functions take.
    """

    name: str
    args: dict[str, Expr] = field(default_factory=dict)
    positional: tuple[Expr, ...] = ()


@dataclass(frozen=True)
class BinOp(Positioned):
    """A binary operator application; ``op`` is the operator's source text."""

    op: str
    left: Expr
    right: Expr


@dataclass(frozen=True)
class UnaryOp(Positioned):
    """A unary operator application (``-``, ``+`` or ``!``)."""

    op: str
    operand: Expr


Expr = Num | Str | Bool | Ref | Index | Vector | Array | Call | BinOp | UnaryOp


# -- statements ------------------------------------------------------------


@dataclass(frozen=True)
class Lvalue(Positioned):
    """The target of an assignment.

    ``subscript`` holds whatever was inside a trailing ``[...]``.  The same
    shape spells two unrelated things -- the thermal property environment in
    ``Keplacoat[EOL] = ...`` and the array element in ``grid[1] = ...`` -- and
    which one it is depends on what the name was declared as, so the choice is
    left to the reader rather than made here.  :attr:`environment` offers the
    first reading and :attr:`indices` the second.
    """

    path: tuple[str, ...]
    subscript: tuple[Expr, ...] = ()

    @property
    def name(self) -> str:
        """The symbol being assigned to, without any attribute path."""
        return self.path[0]

    @property
    def environment(self) -> str | None:
        """The subscript read as a property environment, if it can be.

        That is a single bare name, as ``[BOL]`` and ``[EOL]`` are; ``None``
        for the default environment and for anything an environment cannot be.
        """
        if len(self.subscript) != 1:
            return None
        only = self.subscript[0]
        return only.name if isinstance(only, Ref) and len(only.path) == 1 else None

    @property
    def indices(self) -> tuple[Expr, ...]:
        """The subscript read as array indices; empty when there is none."""
        return self.subscript

    @property
    def attribute(self) -> str | None:
        """The dotted attribute being assigned to, lower-cased, if there is one."""
        return ".".join(self.path[1:]).lower() if len(self.path) > 1 else None


@dataclass(frozen=True)
class Declaration(Positioned):
    """``[CONST] TYPE name [dims] [= value];``

    A name may be declared only once in a model, so the declaration is what
    reserves the name and fixes the kind the later assignment must produce.
    """

    kind: str
    name: str
    dims: tuple[Expr, ...] = ()
    init: Expr | None = None
    is_const: bool = False


@dataclass(frozen=True)
class Assignment(Positioned):
    """``target = value;``"""

    target: Lvalue
    value: Expr


@dataclass(frozen=True)
class CallStmt(Positioned):
    """A procedure call used as a statement, e.g. ``DEFINE_OPTICAL(...);``."""

    name: str
    args: dict[str, Expr] = field(default_factory=dict)
    positional: tuple[Expr, ...] = ()


@dataclass(frozen=True)
class Include(Positioned):
    """``INCLUDE "path"`` -- no trailing semicolon, and the path is not escaped."""

    path: str


@dataclass(frozen=True)
class Define(Positioned):
    """``DEFINE symbol "text"`` -- a textual substitution applied before parsing."""

    symbol: str
    text: str


@dataclass(frozen=True)
class Delete(Positioned):
    """``DELETE a, b;``"""

    names: tuple[str, ...]


@dataclass(frozen=True)
class IfBlock(Positioned):
    """``IF (test) THEN ... [ELSE ...] END_IF``"""

    test: Expr
    body: tuple[Statement, ...] = ()
    orelse: tuple[Statement, ...] = ()


@dataclass(frozen=True)
class ForBlock(Positioned):
    """``FOR (init; test; step) ... END_FOR``"""

    init: Assignment | None = None
    test: Expr | None = None
    step: Assignment | None = None
    body: tuple[Statement, ...] = ()


@dataclass(frozen=True)
class WhileBlock(Positioned):
    """``WHILE (test) ... END_WHILE``"""

    test: Expr
    body: tuple[Statement, ...] = ()


@dataclass(frozen=True)
class RepeatBlock(Positioned):
    """``REPEAT ... UNTIL (test) END_REPEAT``"""

    test: Expr
    body: tuple[Statement, ...] = ()


@dataclass(frozen=True)
class SwitchCase(Positioned):
    """One ``CASE value:`` arm; ``value`` is ``None`` for the ``DEFAULT:`` arm."""

    value: Expr | None
    body: tuple[Statement, ...] = ()


@dataclass(frozen=True)
class SwitchBlock(Positioned):
    """``SWITCH (subject) CASE ...: ... DEFAULT: ... END_SWITCH``"""

    subject: Expr
    cases: tuple[SwitchCase, ...] = ()


Statement = (
    Declaration
    | Assignment
    | CallStmt
    | Include
    | Define
    | Delete
    | IfBlock
    | ForBlock
    | WhileBlock
    | RepeatBlock
    | SwitchBlock
)


@dataclass(frozen=True)
class ModelFile(Positioned):
    """A parsed file: the model header, its markers, and the statement stream.

    ``name`` and ``markers`` are empty for an included fragment, which carries no
    header of its own.  ``markers`` holds the provenance tokens a generated file
    appends after the model name (``WORKBENCH_V1``, ``ESARAD_GENERATED``).
    """

    name: str = ""
    markers: tuple[str, ...] = ()
    statements: tuple[Statement, ...] = ()
