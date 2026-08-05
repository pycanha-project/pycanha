"""ISO 10303-21 exchange files -- STEP's "part 21" text syntax, read and written.

This module knows the *file syntax* and nothing else: how an exchange file is
divided into a header and one or more data sections, how an entity instance is
written, and what the literal forms mean.  It has no knowledge of any schema,
so the same code serves STEP-TAS, AP203, AP242 or anything else written in
the same syntax; giving meaning to the entity names is the job of the layer
above.

The value model maps the syntax onto Python directly:

============  ==========================================================
``$``         ``None`` -- an attribute left unset
``*``         :data:`DERIVED` -- redeclared in a subtype, value not given
``#42``       :class:`Reference` -- resolved through :meth:`Part21File.entity`
``.BOTH.``    :class:`Enumeration`
``.T.``       ``True`` (and ``.F.`` is ``False``)
``NAME(v)``   :class:`TypedValue` -- a value tagged with a select type
``(a,b)``     a ``tuple``, nested as deeply as the file nests it
============  ==========================================================

Forward references are the norm rather than the exception in these files, so
nothing is resolved while parsing: the parse produces a flat table of instances
and every reference stays a :class:`Reference` until a caller asks for it.

Writing goes through the same value model in reverse -- :func:`format_value`
renders one attribute, :func:`format_entity` one instance, and
:func:`write_part21` the surrounding exchange structure.  An instance is
rendered from its identifier, type name and attributes rather than from an
object model, because a writer builds its instances as it walks whatever it is
writing and has no use for a second representation in between.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, final

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Sequence

__all__ = [
    "DERIVED",
    "Derived",
    "Entity",
    "Enumeration",
    "Part21Error",
    "Part21File",
    "Record",
    "Reference",
    "TypedValue",
    "Value",
    "format_entity",
    "format_real",
    "format_record",
    "format_value",
    "parse_part21",
    "read_part21",
    "write_part21",
]


class Part21Error(Exception):
    """Raised when a file is not well-formed ISO 10303-21.

    Malformed *syntax* is fatal -- there is no useful way to carry on past a
    record that cannot be read.  Entities that are well-formed but unexpected
    are a different matter entirely, and are the caller's business.
    """


@final
class Derived:
    """The ``*`` value: an attribute whose value comes from a supertype.

    A distinct type rather than ``None`` because ``$`` and ``*`` are different
    statements -- "no value" against "the value is declared elsewhere" -- and a
    reader that treats them alike will silently accept a file that redeclares
    an attribute it should have given.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "DERIVED"


#: The single :class:`Derived` instance; compare against it with ``is``.
DERIVED: Final = Derived()


@final
@dataclass(frozen=True, slots=True)
class Reference:
    """A reference to another instance in the same exchange structure."""

    id: int

    def __repr__(self) -> str:
        return f"#{self.id}"


@final
@dataclass(frozen=True, slots=True)
class Enumeration:
    """An enumeration value, written ``.NAME.``, with the dots stripped."""

    name: str

    def __repr__(self) -> str:
        return f".{self.name}."


@final
@dataclass(frozen=True, slots=True)
class TypedValue:
    """A value tagged with the type it was selected as, written ``NAME(value)``."""

    kind: str
    value: Value


type Value = (
    float
    | int
    | str
    | bytes
    | bool
    | None
    | Derived
    | Reference
    | Enumeration
    | TypedValue
    | tuple[Value, ...]
)
"""Anything that can appear as an attribute value."""


@dataclass(frozen=True, slots=True)
class Record:
    """One ``NAME(attributes...)`` group, upper-cased name and its attributes."""

    kind: str
    params: tuple[Value, ...]

    def __len__(self) -> int:
        return len(self.params)


@dataclass(frozen=True, slots=True)
class Entity:
    """One numbered instance in a data section.

    Most instances hold a single :class:`Record`.  A *complex* instance -- an
    object whose type comes from several entity types at once -- holds one per
    type, and :attr:`kind` and :attr:`params` then speak for the first of them.
    """

    id: int
    records: tuple[Record, ...]
    line: int = 0

    @property
    def kind(self) -> str:
        """The first record's type name."""
        return self.records[0].kind

    @property
    def params(self) -> tuple[Value, ...]:
        """The first record's attributes."""
        return self.records[0].params

    def record(self, kind: str) -> Record | None:
        """The record of type *kind*, for a complex instance."""
        wanted = kind.upper()
        return next((record for record in self.records if record.kind == wanted), None)

    def __repr__(self) -> str:
        return f"#{self.id}={self.kind}(...)"


@dataclass
class Part21File:
    """The contents of one exchange file: its header and its instances."""

    header: tuple[Record, ...] = ()
    entities: dict[int, Entity] = field(default_factory=dict)
    _by_kind: dict[str, list[Entity]] = field(default_factory=dict, repr=False)

    def __len__(self) -> int:
        return len(self.entities)

    def __iter__(self) -> Iterator[Entity]:
        return iter(self.entities.values())

    def entity(self, value: Value) -> Entity | None:
        """The instance *value* refers to, or ``None`` if it is not a reference.

        A dangling reference also gives ``None``: files written by different
        tools disagree about how complete they have to be, and a reader that
        raised here would fail on a file its caller could still make sense of.
        """
        if isinstance(value, Reference):
            return self.entities.get(value.id)
        return None

    def of_kind(self, *kinds: str) -> list[Entity]:
        """Every instance of the named types, ordered by instance number.

        Asking for two types gives one list rather than two runs, and a caller
        that indexes into it wants the same answer whatever order the file
        happened to define them in.
        """
        if not self._by_kind:
            self._index()
        found: list[Entity] = []
        for kind in kinds:
            found.extend(self._by_kind.get(kind.upper(), ()))
        found.sort(key=lambda entity: entity.id)
        return found

    def kinds(self) -> dict[str, int]:
        """How many instances of each type the file holds."""
        if not self._by_kind:
            self._index()
        return {kind: len(group) for kind, group in sorted(self._by_kind.items())}

    def header_record(self, kind: str) -> Record | None:
        """The named header record, such as ``FILE_SCHEMA``."""
        wanted = kind.upper()
        return next((record for record in self.header if record.kind == wanted), None)

    def _index(self) -> None:
        for entity in self.entities.values():
            for record in entity.records:
                self._by_kind.setdefault(record.kind, []).append(entity)


# -- lexer ------------------------------------------------------------------

_TOKEN = re.compile(
    r"""
      (?P<space>\s+)
    | (?P<comment>/\*.*?\*/)
    | (?P<magic>ISO-10303-21|END-ISO-10303-21)
    | (?P<string>'(?:[^']|'')*')
    | (?P<binary>"[0-7][0-9A-Fa-f]*")
    | (?P<ref>\#[0-9]+)
    | (?P<real>[+-]?[0-9]+\.[0-9]*(?:[Ee][+-]?[0-9]+)?)
    | (?P<integer>[+-]?[0-9]+)
    | (?P<enum>\.[A-Za-z_0-9]+\.)
    | (?P<name>!?[A-Za-z_][A-Za-z_0-9]*)
    | (?P<punct>[(),;=$*])
    """,
    re.VERBOSE | re.DOTALL,
)

#: Token kinds carrying no information for the parser.
_SKIPPED = frozenset({"space", "comment"})


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str
    line: int


def _tokenize(source: str) -> list[_Token]:
    """Split *source* into tokens, keeping a line number for error messages."""
    tokens: list[_Token] = []
    position = 0
    line = 1
    end = len(source)
    while position < end:
        match = _TOKEN.match(source, position)
        if match is None:
            snippet = source[position : position + 20].splitlines()[:1]
            msg = f"line {line}: cannot read {snippet[0]!r}"
            raise Part21Error(msg)
        kind = match.lastgroup or ""
        text = match.group()
        if kind not in _SKIPPED:
            tokens.append(_Token(kind, text, line))
        line += text.count("\n")
        position = match.end()
    return tokens


def _unquote(text: str) -> str:
    """The contents of a part-21 string literal, with doubled quotes halved."""
    return text[1:-1].replace("''", "'")


def _enumeration(text: str) -> Value:
    """A ``.NAME.`` token, of which two spell the booleans."""
    name = text[1:-1].upper()
    if name == "T":
        return True
    if name == "F":
        return False
    return Enumeration(name)


#: How each self-contained token becomes a value.
_LITERALS: dict[str, Callable[[str], Value]] = {
    "real": float,
    "integer": int,
    "string": _unquote,
    "binary": lambda text: text[1:-1].encode("ascii"),
    "ref": lambda text: Reference(int(text[1:])),
    "enum": _enumeration,
}

#: The two tokens that stand in place of a value.
_PLACEHOLDERS: dict[str, Value] = {"$": None, "*": DERIVED}


# -- parser -----------------------------------------------------------------


class _Parser:
    """A cursor over the token stream, one exchange structure at a time."""

    def __init__(self, tokens: Sequence[_Token]) -> None:
        self._tokens = tokens
        self._at = 0

    # -- cursor --------------------------------------------------------

    def _peek(self) -> _Token | None:
        return self._tokens[self._at] if self._at < len(self._tokens) else None

    def _next(self) -> _Token:
        token = self._peek()
        if token is None:
            msg = "the file ends in the middle of a statement"
            raise Part21Error(msg)
        self._at += 1
        return token

    def _expect(self, text: str) -> _Token:
        token = self._next()
        if token.text.upper() != text:
            msg = f"line {token.line}: expected {text!r}, found {token.text!r}"
            raise Part21Error(msg)
        return token

    def _accept(self, text: str) -> bool:
        token = self._peek()
        if token is not None and token.text.upper() == text:
            self._at += 1
            return True
        return False

    # -- structure -----------------------------------------------------

    def parse(self) -> Part21File:
        """Read the whole exchange structure."""
        self._expect("ISO-10303-21")
        self._expect(";")
        parsed = Part21File()
        header: list[Record] = []
        while True:
            token = self._peek()
            if token is None:
                msg = "the file ends without END-ISO-10303-21"
                raise Part21Error(msg)
            word = token.text.upper()
            if word == "END-ISO-10303-21":
                self._at += 1
                self._accept(";")
                break
            if word == "HEADER":
                self._at += 1
                self._expect(";")
                header.extend(self._header_records())
            elif word == "DATA":
                self._at += 1
                if self._accept("("):
                    self._value_list(")")
                self._expect(";")
                self._instances(parsed.entities)
            else:
                msg = f"line {token.line}: expected a HEADER or DATA section, found {token.text!r}"
                raise Part21Error(msg)
        parsed.header = tuple(header)
        return parsed

    def _header_records(self) -> list[Record]:
        records: list[Record] = []
        while not self._accept("ENDSEC"):
            records.append(self._record())
            self._expect(";")
        self._expect(";")
        return records

    def _instances(self, into: dict[int, Entity]) -> None:
        while not self._accept("ENDSEC"):
            token = self._next()
            if token.kind != "ref":
                msg = f"line {token.line}: expected an instance name, found {token.text!r}"
                raise Part21Error(msg)
            identifier = int(token.text[1:])
            self._expect("=")
            entity = Entity(identifier, self._records(), token.line)
            if identifier in into:
                msg = f"line {token.line}: #{identifier} is defined twice"
                raise Part21Error(msg)
            into[identifier] = entity
            self._expect(";")
        self._expect(";")

    def _records(self) -> tuple[Record, ...]:
        """One simple record, or the bracketed group of a complex instance."""
        if not self._accept("("):
            return (self._record(),)
        records: list[Record] = []
        while not self._accept(")"):
            records.append(self._record())
        if not records:
            msg = "a complex instance needs at least one record"
            raise Part21Error(msg)
        return tuple(records)

    def _record(self) -> Record:
        token = self._next()
        if token.kind != "name":
            msg = f"line {token.line}: expected a type name, found {token.text!r}"
            raise Part21Error(msg)
        self._expect("(")
        return Record(token.text.upper(), self._value_list(")"))

    # -- values --------------------------------------------------------

    def _value_list(self, closing: str) -> tuple[Value, ...]:
        """Values up to *closing*, which is consumed."""
        if self._accept(closing):
            return ()
        values: list[Value] = [self._value()]
        while not self._accept(closing):
            self._expect(",")
            values.append(self._value())
        return tuple(values)

    def _value(self) -> Value:
        token = self._next()
        literal = _LITERALS.get(token.kind)
        if literal is not None:
            return literal(token.text)
        if token.kind == "name":
            # A value written as `NAME(...)` names the type it was selected as.
            self._expect("(")
            return TypedValue(token.text.upper(), self._typed_value())
        if token.text == "(":
            return self._value_list(")")
        if token.text in _PLACEHOLDERS:
            return _PLACEHOLDERS[token.text]
        msg = f"line {token.line}: {token.text!r} is not a value"
        raise Part21Error(msg)

    def _typed_value(self) -> Value:
        """The single value inside ``NAME(...)``, which may itself be a list."""
        inner = self._value_list(")")
        return inner[0] if len(inner) == 1 else inner


def parse_part21(source: str) -> Part21File:
    """Read an exchange structure from *source* text."""
    return _Parser(_tokenize(source)).parse()


def read_part21(path: str | Path) -> Part21File:
    """Read an exchange structure from a file.

    Exchange files are nominally ASCII, and characters outside it are escaped
    rather than encoded, so the decode is deliberately forgiving: a stray byte
    from a tool that ignored that rule should not cost the whole file.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_part21(text)


# -- writer -----------------------------------------------------------------


def format_real(value: float) -> str:
    """Render *value* as a part-21 ``REAL`` literal.

    The syntax requires a decimal point, which is the whole difficulty:
    ``repr`` gives the shortest text that reads back as the same number but
    drops the point whenever it can, and ``1e-05`` is an integer followed by
    something the lexer will not accept.

    >>> format_real(0.4)
    '0.4'
    >>> format_real(360.0)
    '360.0'
    >>> format_real(1e-5)
    '1.0E-05'
    >>> format_real(-0.0)
    '0.0'
    """
    if not math.isfinite(value):
        msg = f"{value!r} has no part-21 representation"
        raise Part21Error(msg)
    if value == 0.0:
        # Both zeros are the same number here, and a leading minus on one of
        # them reads as a deliberate sign to anyone looking at the file.
        return "0.0"
    text = repr(float(value))
    if "e" in text:
        mantissa, exponent = text.split("e")
        if "." not in mantissa:
            mantissa += ".0"
        return f"{mantissa}E{exponent.upper()}"
    return text if "." in text else f"{text}.0"


def _format_derived(_value: Derived) -> str:
    return "*"


def _format_boolean(value: bool) -> str:
    return ".T." if value else ".F."


def _format_integer(value: int) -> str:
    return str(value)


def _format_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _format_binary(value: bytes) -> str:
    return '"' + value.decode("ascii") + '"'


def _format_reference(value: Reference) -> str:
    return f"#{value.id}"


def _format_enumeration(value: Enumeration) -> str:
    return f".{value.name}."


#: How each self-contained value becomes a literal, in the order it is tried.
#:
#: The order carries meaning in one place: ``bool`` is a subclass of ``int`` and
#: the two are different literals, so it has to be looked at first.  The
#: renderers are typed by what they accept and the table by what it is given,
#: which only the ``isinstance`` beside it can reconcile.
_RENDERERS: tuple[tuple[type, Callable[[Any], str]], ...] = (
    (Derived, _format_derived),
    (bool, _format_boolean),
    (int, _format_integer),
    (float, format_real),
    (str, _format_string),
    (bytes, _format_binary),
    (Reference, _format_reference),
    (Enumeration, _format_enumeration),
)


def format_value(value: Value) -> str:
    """Render one attribute value.

    >>> format_value((1, None, Enumeration("BOTH")))
    '(1,$,.BOTH.)'
    """
    if value is None:
        return "$"
    if isinstance(value, tuple):
        return "(" + ",".join(format_value(item) for item in value) + ")"
    if isinstance(value, TypedValue):
        return f"{value.kind}({format_value(value.value)})"
    for kind, render in _RENDERERS:
        if isinstance(value, kind):
            return render(value)
    msg = f"{value!r} is not a part-21 value"
    raise Part21Error(msg)


def format_record(record: Record) -> str:
    """Render one ``NAME(attributes...)`` group, without a trailing semicolon."""
    return record.kind + "(" + ",".join(format_value(value) for value in record.params) + ")"


def format_entity(identifier: int, kind: str, params: Sequence[Value]) -> str:
    """Render one numbered instance, semicolon included.

    >>> format_entity(42, "MGM_FACE", [Reference(7)])
    '#42=MGM_FACE(#7);'
    """
    return f"#{identifier}=" + format_record(Record(kind, tuple(params))) + ";"


def write_part21(path: str | Path, *, header: Sequence[Record], data: Iterable[str]) -> None:
    """Write an exchange structure with one header and one data section.

    *data* holds instances already rendered by :func:`format_entity`, which is
    what lets a caller mix instances it built with instances it is copying
    through verbatim.

    Newlines are written as they are given rather than translated, so a file
    produced on Windows is byte-for-byte the one produced anywhere else.
    """
    lines = ["ISO-10303-21;", "HEADER;"]
    lines.extend(format_record(record) + ";" for record in header)
    lines.extend(("ENDSEC;", "DATA;"))
    lines.extend(data)
    lines.extend(("ENDSEC;", "END-ISO-10303-21;"))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
