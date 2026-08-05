# Cutting-tool geometry model

One plate cut by each shape that can act as a cutting tool. The feature models
next door cut with a cylinder and a box; this one covers the rest, which is what
makes the four solid entities appear in the STEP-TAS form.

| File | What it is |
|---|---|
| `CUTTERS.erg` | The model: a rectangle cut by a cone, a sphere, a paraboloid and a triangular prism, each with `sense = -1` |
| `CUTTERS.stp` | The same model as STEP-TAS, and the fixture for the `.stp` reader's cutting tools |

Two of the four tools cannot be used as tools here, and that is the point of the
fixture as much as the two that can: a paraboloid does not enclose a volume, and
there is no closed prism to cut with. Both must be reported rather than dropped,
and the shape they were to cut must survive uncut rather than half-cut.
