"""Guard: a pycanha class that extends a pycanha-core class must be what the
public API actually hands back.

If someone adds a method to a pycanha subclass but nothing constructs that
subclass on the Python side, the core class keeps flowing through the API and
the new method is simply missing at runtime -- an AttributeError for the user,
with no failure anywhere in the build. These tests turn that into a test
failure instead.

Two rules are enforced:

* every core object reachable from a constructed ThermalModel must not have an
  extending pycanha subclass (otherwise the user is getting the smaller class);
* KNOWN_GAPS must list exactly the accessors that still break rule one, so a
  gap cannot be introduced silently and a fixed gap cannot be forgotten.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

import pycanha as pc

# Accessors that still hand back a core class for which pycanha has an
# extending subclass. Remove entries as they are fixed; do not add new ones.
KNOWN_GAPS: set[tuple[str, str]] = {
    # Permanent, and not a plumbing problem: the core rejects composing a group
    # that is already registered with a model ("GeometryGroup::add: child is
    # already registered with a model"), so the `+` / `-` operators cannot work
    # on the root group whatever type it has. Compose geometry from items you
    # built and register the result instead.
    ("model.gmm.root_group", "GeometryGroup"),
}


def _is_runtime_member(name: str, value: object) -> bool:
    """Whether a subclass member is a capability an object would lose.

    Only instance-level members count. ``__init__``, ``@staticmethod`` and
    ``@classmethod`` are construction helpers: they matter when you build an
    object, never when you are handed one, so a core object that lacks them has
    lost nothing. An instance method or property, by contrast, is missing at
    runtime and raises AttributeError.
    """
    if name == "__init__":
        return False
    return inspect.isfunction(value) or isinstance(value, property)


_MAX_DEPTH = 3
_MAX_ENTRIES = 4
_UNSET = object()


def _extending_subclasses() -> dict[type, type]:
    """Map each core class to the pycanha subclass that adds something to it."""
    mapping: dict[type, type] = {}
    for info in pkgutil.walk_packages(pc.__path__, prefix="pycanha."):
        try:
            module = importlib.import_module(info.name)
        except ImportError:
            continue
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if not cls.__module__.startswith("pycanha."):
                continue
            core_base = next(
                (b for b in cls.__mro__[1:] if b.__module__.startswith("pycanha_core")),
                None,
            )
            if core_base is None:
                continue
            if any(_is_runtime_member(name, value) for name, value in vars(cls).items()):
                mapping[core_base] = cls
    return mapping


def _read(obj: object, name: str) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return _UNSET


def _is_accessor(owner: type, name: str) -> bool:
    attr = inspect.getattr_static(owner, name, None)
    return isinstance(attr, property) or type(attr).__name__ in {
        "getset_descriptor",
        "nb_static_property",
    }


def _members(value: object) -> list[tuple[str, object]]:
    """The objects to check for one accessor: the value, or a list's entries."""
    if isinstance(value, (list, tuple)):
        return [(f"[{i}]", entry) for i, entry in enumerate(value[:_MAX_ENTRIES])]
    return [("", value)]


def _walk(obj: object, path: str, depth: int, seen: set[int], out: list[tuple[str, type]]) -> None:
    if depth > _MAX_DEPTH or id(obj) in seen:
        return
    seen.add(id(obj))

    for name in sorted(dir(type(obj))):
        if name.startswith("__") or not _is_accessor(type(obj), name):
            continue
        raw = _read(obj, name)
        if raw is _UNSET:
            continue
        for suffix, value in _members(raw):
            if value is None or isinstance(value, (str, bytes, int, float, bool)):
                continue
            module = type(value).__module__
            if not module.startswith(("pycanha.", "pycanha_core")):
                continue
            if module.startswith("pycanha_core"):
                out.append((f"{path}.{name}{suffix}", type(value)))
            _walk(value, f"{path}.{name}{suffix}", depth + 1, seen, out)


def _populated_model() -> pc.ThermalModel:
    """A model with geometry and a node, so collections are not empty."""
    model = pc.ThermalModel("contract")
    model.gmm.add(
        pc.gmm.GeometryItem(
            "panel",
            pc.gmm.Rectangle((0, 0, 0), (1, 0, 0), (0, 1, 0)),
            pc.gmm.ThermalMesh(),
        )
    )
    model.tmm.nodes.add_node(pc.tmm.Node(1))
    return model


def _core_returning_accessors() -> list[tuple[str, type]]:
    found: list[tuple[str, type]] = []
    _walk(_populated_model(), "model", 0, set(), found)
    return found


def _current_gaps() -> set[tuple[str, str]]:
    extending = _extending_subclasses()
    return {
        (path, coretype.__name__)
        for path, coretype in _core_returning_accessors()
        if coretype in extending
    }


def test_public_api_does_not_hand_back_an_extended_core_class() -> None:
    unexpected = _current_gaps() - KNOWN_GAPS
    assert not unexpected, (
        "these accessors return a pycanha-core class even though pycanha "
        f"extends it, so the extension is invisible to users: {sorted(unexpected)}"
    )


def test_known_gaps_are_all_still_real() -> None:
    stale = KNOWN_GAPS - _current_gaps()
    assert not stale, f"these gaps are fixed and should be removed from KNOWN_GAPS: {sorted(stale)}"
