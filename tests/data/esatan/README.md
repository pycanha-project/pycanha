# ESATAN-TMS and STEP-TAS test models

Two kinds of model live here. `FEATURES.erg` is the **language corpus**: it
exists to use every construct of the ESATAN-TMS `.erg` geometry language, in
every spelling the language has for it, and nothing about it is meant to be
physically sensible — surfaces sit on top of one another and the numbers are
chosen to be told apart. `DISC/` is the one **realistic** model, and the
numeric reference the solvers are checked against.

| File | What it is |
|---|---|
| `FEATURES.erg` | The corpus: every construct the reader supports, each attribute combination on its own surface, and both spellings wherever the language has two |
| `FEATURES.stp` | The corpus in STEP-TAS — the frozen anchor for the `.stp` reader, and the one file here pycanha did not write |
| `expected_faces.csv` | `node,item,area,x,y,z` for every face of the corpus's face-geometry block |
| `DISC/` | The realistic model: geometry, two solved thermal models, and their results |

## The rule

**A fixture belongs on disk only if pycanha cannot produce it.** That is
`FEATURES.stp` and the `DISC/` results, and nothing else. Whether a construct
parses, builds the right primitive, raises the right diagnostic, or is written
back out is an inline model in `tmp_path`; a foreign entity spelling is inline
part-21 text. Both patterns are used throughout `tests/io/`.

**A new construct is a new block in `FEATURES.erg`, never a new file.** Adding
one means regenerating `FEATURES.stp` from it, which is the only step that
needs anything outside pycanha.

## What `FEATURES.erg` covers

In the order the file presents them:

- **Independent variables** — `CONST REAL`, `REAL`, `INTEGER`, a `REAL` vector
  used as `meshPositions`, `POINT` declarations, and expressions using the
  degree-based function library.
- **Materials** — a literal eight-value optical row with its `[BOL]` / `[EOL]`
  variants, `DEFINE_OPTICAL`, a literal bulk triple, `DEFINE_BULK` isotropic
  and `DEFINE_BULK` orthotropic, and an insulation with a layer.
- **Primitives** — every shell primitive in shell coordinates, and every one
  given by points, including the boxes and the triangular prisms that become
  several flat surfaces here.
- **Placement** — `ROTATE` about all three axes, `TRANSLATE`, and the `clear`
  form that discards the accumulated placement.
- **Structure** — `+` chains, `SINGLE_COMBINATION`, a static assembly and a
  kinematic one, and `-` cuts by each shape that can be a tool: a cylinder, a
  box, a cone, a sphere and a triangular prism.
- **Overrides** — `DEFINE_GEOMETRY_ATTRIBUTES`, `SET_ATTRIBUTE_RECURSIVE` and
  dotted attribute assignment.
- **Arrays** (`PT_ARRAY`, node base 60 000) — a `POINT` array and a `REAL`
  vector, both filled element by element and both read as primitive corners.
  The array declared with an initializer list is up with the variables, so both
  spellings are present.
- **Cutting tools** (`HOLED`, 61 000) — one plate cut by a cone, a sphere and
  a triangular prism, each with `sense = -1`.
- **Face geometry** (`FACES`, 62 000) — a trapezoid, a quadrilateral, a
  rectangle, a triangle and an annulus sector, each with a node per face and
  per side, so that one node names exactly one face. `expected_faces.csv` gives
  the area of each and the position of its parametric centre, to six decimals.
  The shapes are order 1 so that six decimals leave margin, and the meshes are
  deliberately uneven (3x2, 2x2, 2x3) so that swapping the two parametric
  directions would put the right areas at the wrong node numbers.
- **The attribute bank** (`BANK`, 70 000 upwards, one base per surface) — one
  rectangle per attribute combination, all the same shape, so that what
  separates any two of them is the attributes and nothing else: defaults
  implicit and defaults spelled out, `Active`/`Inactive`,
  `Radiative`/`Conductive`, `SINGLE` and `DUAL` composition, insulation,
  labels, criticalities and sub-models, a node increment per direction, both
  mesh types, the through-thickness quantities, and colours.

The constructs the reader **refuses** are deliberately absent: each one changes
the geometry around it — a refused cutter leaves its target uncut, a refused
primitive leaves the combination that names it short an operand — so a corpus
carrying them would be a different model from one that does not, and only one
of the two can have a `.stp` twin. Each is written inline instead, in
`tests/io/esatan/test_erg_features.py` and `test_erg_solids.py`.

## `FEATURES.stp`

The corpus in STEP-TAS, and the one file here pycanha did not write. Its job is
to anchor how the entities are read against a description that came from
somewhere else: our reader and our writer agreeing with each other proves
nothing on its own, and this is what stops a shared misunderstanding passing
unnoticed. It carries every entity the reader maps but one, and it is the reason
the two readers can be compared at all.

It is **frozen**. Nothing obliges it to keep describing the whole corpus: the
corpus grows with the ESATAN-TMS language, and a construct that has no bearing
on STEP-TAS still belongs in it. `test_stp_matches_erg` therefore compares only
the surfaces the two files share, and holds a floor under how many that is.
Refresh it when the overlap has thinned enough to be worth the trouble, and
raise the floor when you do.

New STEP-TAS capability does not need it: those are tested against files pycanha
writes into `tmp_path` and against part-21 text written inline.
