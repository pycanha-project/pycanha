# Per-face area and position reference

A geometry model whose every face carries a **node of its own**, on both sides,
so that one node names exactly one face. `expected_faces.csv` gives, per node,
the area of that face and the position of its parametric centre — the point at
the middle of the face's cut interval in each of the two directions, which is
not in general the face's centroid.

| File | What it is |
|---|---|
| `FACEGEOM.erg` | The model: a trapezoid, a quadrilateral, a rectangle, a triangle and an annulus sector, each meshed and each given a distinct node per face and per side |
| `expected_faces.csv` | `node,item,area,x,y,z` — the expected values, to six decimals |

The shapes are sized order 1 so that six decimals leave plenty of margin, and
the meshes are deliberately uneven (3x2, 2x2, 2x3) so that a reader which
swapped the two parametric directions would put the right areas at the wrong
node numbers.

`tests/io/esatan/test_erg_face_geometry.py` is the consumer. It is the check
that a shape is not merely the right *size* but the right shape parametrised
the right way round: several of these surfaces have a symmetry that makes a
transposed or rotated corner order produce an identical total area, so only the
per-node values separate them.

Positions are compared only for the shapes whose `uv` domain is the unit square.
The annulus sector's first parameter is an arc length rather than a fraction, so
a cut midpoint there is not the midpoint of `to_cartesian`; its areas are
compared and its positions are not.
