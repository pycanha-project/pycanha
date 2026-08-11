"""Where the numbers painted on the geometry come from.

Two sources, both reached through the public thermal model. The **stored
cases** are the ``DataModel``s already in ``tm.tmm.thermal_data.models`` - what
a solver wrote, or what an ESATAN TMD file was read into - each holding a dense
``(timestep, node index)`` array per attribute. The **live case** is the
network's current node state, which has no time axis: one instant, whatever the
last solve left behind.

Loading a result file from inside the viewer is deliberately not offered; the
model is loaded before the window opens.

A series is turned into a colouring by
:func:`result_property`, which resolves the values onto **face slots** through
the mesh's own node numbers - so the result becomes an ordinary
:class:`~pycanha.plot.properties.FaceProperty` and the legend, the colour
scale, the property table and the node filter all keep working unchanged.

Nothing here imports Qt: the discovery, the frame lookup and the slot mapping
are plain numpy, and are what the tests assert on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pycanha_core as pcc

from .polydata import key_columns
from .properties import FaceProperty

if TYPE_CHECKING:
    import numpy.typing as npt

#: Key of the synthesised colour-by option a result is shown through.
RESULT_KEY = "result"

#: Case key of the live node state, which is not a stored ``DataModel``.
LIVE_CASE = "current"

#: What the live case is called in the case list.
LIVE_LABEL = "Current (live)"

#: The dense attributes a ``DataModel`` can hold, as ``name: (label, unit)``.
#: Keyed by the ``DataModelAttribute`` name, which is also what the combo
#: stores. The sparse and matrix attributes (coupling and Jacobian histories)
#: are not per-node values and so cannot colour a face.
ATTRIBUTES: dict[str, tuple[str, str]] = {
    "T": ("Temperature", "K"),
    "C": ("Thermal capacity", "J/K"),
    "QS": ("Solar heat load", "W"),
    "QA": ("Albedo heat load", "W"),
    "QE": ("Earth IR heat load", "W"),
    "QI": ("Internal heat load", "W"),
    "QR": ("Other heat load", "W"),
    "A": ("Area", "m^2"),
    "APH": ("Solar absorptivity", ""),
    "EPS": ("IR emissivity", ""),
    "FX": ("X coordinate", "m"),
    "FY": ("Y coordinate", "m"),
    "FZ": ("Z coordinate", "m"),
}

#: The one attribute the live case can answer for. The node object carries the
#: heat loads and the rest as well, but reading them means a Python call per
#: node with no bulk accessor behind it, and temperature is what "what does the
#: model look like right now" means.
LIVE_ATTRIBUTE = "T"


@dataclass(frozen=True)
class ResultCase:
    """One selectable source of per-node values."""

    key: str
    label: str
    live: bool = False


@dataclass(frozen=True)
class ResultSeries:
    """One case and attribute: the values, the nodes and the instants.

    ``values`` is ``(timestep, node index)`` and ``node_numbers`` names its
    columns, exactly as a ``DataModel`` stores them. A live series is one row
    with an empty ``times``, which is what "no time axis" looks like
    downstream: :attr:`num_steps` is 1 and the time controls disable
    themselves.
    """

    case: str
    attribute: str
    label: str
    unit: str
    node_numbers: npt.NDArray[np.int64]
    times: npt.NDArray[np.float64]
    values: npt.NDArray[np.float64]

    @property
    def num_steps(self) -> int:
        """Number of stored instants; 1 for the live case."""
        return int(self.values.shape[0])

    @property
    def animated(self) -> bool:
        """Whether there is more than one instant to move between."""
        return self.times.size > 1

    def frame(self, index: int) -> npt.NDArray[np.float64]:
        """The values at stored instant ``index``, clamped to the series.

        Never interpolated, even though ``DenseTimeSeries.interpolate`` would:
        a frame between two stored instants is not data the solver produced,
        and it would be screenshotted as if it were.
        """
        if self.values.size == 0:
            return np.empty(0, dtype=np.float64)
        step = int(np.clip(index, 0, self.num_steps - 1))
        return np.asarray(self.values[step], dtype=np.float64)

    def time_label(self, index: int) -> str:
        """How the current instant is spelled next to the slider."""
        if self.times.size == 0:
            return "no time axis"
        step = int(np.clip(index, 0, self.times.size - 1))
        return f"t = {float(self.times[step]):.6g} s"

    def clim(self) -> tuple[float, float] | None:
        """Range over the **whole** series, so frames stay comparable.

        A colour scale recomputed per frame would repaint the same temperature
        a different colour at every instant, which makes an animation
        unreadable.
        """
        return _finite_range(self.values)

    def history(self, node_number: int) -> npt.NDArray[np.float64] | None:
        """The whole time history of one node, or ``None`` if it has none."""
        columns, found = key_columns([node_number], self.node_numbers)
        if not bool(found[0]):
            return None
        return np.asarray(self.values[:, columns[0]], dtype=np.float64)


def _finite_range(values: npt.NDArray[np.float64]) -> tuple[float, float] | None:
    """Range of the finite entries, or ``None`` when there is nothing to scale."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return None
    low, high = float(finite.min()), float(finite.max())
    return None if low == high else (low, high)


def cases(thermal_model: Any) -> list[ResultCase]:
    """Every result source ``thermal_model`` currently offers.

    Empty when there is nothing to show - no nodes and no stored model - which
    is what tells the viewer to leave the results panel out altogether.
    """
    if thermal_model is None:
        return []
    found: list[ResultCase] = []
    if int(thermal_model.tmm.nodes.num_nodes) > 0:
        found.append(ResultCase(LIVE_CASE, LIVE_LABEL, live=True))
    found += [ResultCase(name, name) for name in thermal_model.tmm.thermal_data.models.model_names]
    return found


def attributes(thermal_model: Any, case: str) -> list[str]:
    """The attributes case ``case`` has data for, in :data:`ATTRIBUTES` order."""
    if case == LIVE_CASE:
        return [LIVE_ATTRIBUTE]
    model = _stored_model(thermal_model, case)
    if model is None:
        return []
    populated = {attribute.name for attribute in model.populated_attributes}
    return [name for name in ATTRIBUTES if name in populated]


def series(thermal_model: Any, case: str, attribute: str) -> ResultSeries | None:
    """Read one case and attribute out of the model, or ``None`` if it has none."""
    label, unit = ATTRIBUTES.get(attribute, (attribute, ""))
    if case == LIVE_CASE:
        return _live_series(thermal_model, attribute, label, unit)
    model = _stored_model(thermal_model, case)
    if model is None or attribute not in attributes(thermal_model, case):
        return None
    # The generic accessor rather than the ``.T`` / ``.QS`` properties, so
    # every attribute is supported by the same three lines.
    dense = model.get_dense_attribute(pcc.tmm.DataModelAttribute[attribute])
    # Views into the model's own storage rather than copies: a solved transient
    # is easily hundreds of MB, and nothing mutates it while the window is open.
    return ResultSeries(
        case=case,
        attribute=attribute,
        label=label,
        unit=unit,
        node_numbers=np.asarray(model.node_numbers, dtype=np.int64),
        times=np.asarray(dense.times, dtype=np.float64),
        values=np.atleast_2d(np.asarray(dense.values, dtype=np.float64)),
    )


def _stored_model(thermal_model: Any, case: str) -> Any:
    """The named ``DataModel``, or ``None`` when the store has no such name."""
    if thermal_model is None:
        return None
    store = thermal_model.tmm.thermal_data.models
    return store.get_model(case) if store.has_model(case) else None


def _live_series(thermal_model: Any, attribute: str, label: str, unit: str) -> ResultSeries | None:
    """The current node state as a one-instant series.

    Read node by node: the network stores its nodes in its own order and
    exposes no bulk temperature array, so the loop is the public way to ask.
    """
    if thermal_model is None or attribute != LIVE_ATTRIBUTE:
        return None
    nodes = thermal_model.tmm.nodes
    count = int(nodes.num_nodes)
    numbers = np.empty(count, dtype=np.int64)
    values = np.empty(count, dtype=np.float64)
    for index in range(count):
        node_number = nodes.get_node_num_from_idx(index)
        numbers[index] = -1 if node_number is None else int(node_number)
        values[index] = np.nan if node_number is None else float(nodes.get_T(node_number))
    return ResultSeries(
        case=LIVE_CASE,
        attribute=attribute,
        label=label,
        unit=unit,
        node_numbers=numbers,
        times=np.empty(0, dtype=np.float64),
        values=values.reshape(1, count),
    )


def slot_values(
    result: ResultSeries, index: int, node_numbers: npt.ArrayLike
) -> npt.NDArray[np.float64]:
    """The frame's value at every face slot of ``node_numbers``.

    ``node_numbers`` is the mesh's own per-slot node array, so a slot with no
    node, or with a node the series never carried, comes out ``nan`` - which
    the actor draws in its ``nan_color`` rather than as a zero.
    """
    slots = np.asarray(node_numbers, dtype=np.int64)
    frame = result.frame(index)
    if frame.size == 0:
        return np.full(slots.size, np.nan)
    columns, found = key_columns(slots, result.node_numbers)
    return np.where(found, frame[columns], np.nan)


def result_property(result: ResultSeries, index: int, node_numbers: npt.ArrayLike) -> FaceProperty:
    """Turn one instant of a series into a colour-by option.

    The label names the attribute and the case but deliberately **not** the
    instant: it is the colour bar's title, and a title that changed on every
    frame would leave a trail of colour bars behind an animation. Which instant
    is on screen is the time panel's line to say.

    The key is fixed, so the colour-by combo keeps one stable entry for
    "whatever result is selected".
    """
    return FaceProperty(
        key=RESULT_KEY,
        label=f"{result.label} ({result.case})",
        values=slot_values(result, index, node_numbers),
        categorical=False,
        unit=result.unit,
        clim=result.clim(),
    )


def empty_property(n_slots: int) -> FaceProperty:
    """The placeholder colouring shown before any case has been read.

    All ``nan``, so the geometry draws in the ``nan_color`` grey rather than
    all one colour off an empty scale.
    """
    return FaceProperty(
        key=RESULT_KEY,
        label="Result",
        values=np.full(int(n_slots), np.nan),
        categorical=False,
    )
