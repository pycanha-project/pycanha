# Feature-exercise geometry models

Two ESATAN geometry models written to exercise the `.erg` reader across the
whole language rather than to describe any real hardware. Between them they use
every construct the reader claims to support, plus the ones it deliberately
refuses.

| File | What it is |
|---|---|
| `FEATURES_ERG.erg` | The full exercise: every supported construct, plus the six that have no pycanha equivalent (torus by parameters and by points, half-space cutter, `sense = 1` cut, non-geometric thermal node, `REMOVE_FACE`) |
| `FEATURES_TAS.erg` | The same model with those six removed, so it is the subset that survives a STEP-TAS conversion intact |
| `FEATURES_ERG_export.erg`, `FEATURES_TAS_export.erg` | The same two models in canonical form: every default written out, one fixed attribute order per primitive, floats normalised. What the `.erg` writer's output is compared against |
| `FEATURES_TAS.stp` | `FEATURES_TAS` as STEP-TAS — the same geometry described a second way, and the fixture for the `.stp` reader |

## What each model covers

Both models contain, in this order:

- **Independent variables** — `CONST REAL`, `REAL`, `INTEGER`, a `REAL` vector
  used as `meshPositions`, `POINT` declarations, and expressions using the
  degree-based function library.
- **Materials** — a literal eight-value optical row with its `[BOL]` / `[EOL]`
  variants, `DEFINE_OPTICAL`, a literal bulk triple, `DEFINE_BULK` isotropic and
  `DEFINE_BULK` orthotropic.
- **Primitives** — all nine shell primitives in shell coordinates, and all ten
  given by points, including the boxes and the triangular prisms that become
  several flat surfaces here.
- **Attributes** — every per-side attribute on one surface, both compositions,
  both mesh types, per-direction node increments, and a surface left for ESATAN
  to number.
- **Placement** — `ROTATE` about all three axes, `TRANSLATE`, and the `clear`
  form that discards the accumulated placement.
- **Structure** — `+` chains, `-` cuts by a cylinder and by a box,
  `SINGLE_COMBINATION`, a static assembly and a kinematic one.
- **Overrides** — `DEFINE_GEOMETRY_ATTRIBUTES`, `SET_ATTRIBUTE_RECURSIVE` and
  dotted attribute assignment.

`FEATURES_ERG.erg` then adds the constructs with no pycanha equivalent. Its
value is in the diagnostics: each one must be reported, and none of them may
change the geometry silently.
