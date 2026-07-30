"""Radiative example 3 - radiative exchange factors (GRs) from the VF.

WHAT 0.16 PROVIDES: the ray tracer computes geometric *view factors* only.
The native exchange (GR) and solar kernels, Gebhart factors and
``update_materials`` are P2+ and are NOT in pycanha 0.16 (there is no
``accumulate_solar`` / ``accumulate_exchange`` / ``gebhart_factors`` in
``pycanha.radiative``). So:

* Solar loads (which need the solar kernel for self-shadowing) - NOT shown here,
  they cannot be computed with 0.16 without inventing an API.
* Radiative exchange factors (GRs) - computed HERE in pure Python from the
  geometric VF via the classic Gebhart method (diffuse-grey, opaque surfaces).
  This is the same VF -> GR route the roadmap earmarks as ``gebhart_from_vf``.

We reuse the two-parallel-square model and validate the GR against the
blackbody limit (eps = 1  =>  GR = A * F) plus reciprocity.

Run: ``uv run python radiative_03_gebhart_gr.py`` (needs a Vulkan device).
"""

import numpy as np

import pycanha as pc
from pycanha import gmm
from pycanha import radiative as rad

GAP = 1.0
EPS = 0.8  # grey IR emissivity of both plates


def gebhart_gr(vf: np.ndarray, area: np.ndarray, eps: np.ndarray) -> np.ndarray:
    """Radiative exchange factors GR_ij = A_i eps_i B_ij (m^2) from geometric VF.

    Gebhart factors solve B = (I - F rho) \\ (F eps) with rho = 1 - eps
    (opaque, diffuse-grey). Space is a black sink: it never reflects, so it drops
    out of the reflection system and shows up only as each row's deficit. The
    result satisfies reciprocity A_i eps_i B_ij = A_j eps_j B_ji, i.e. GR is
    symmetric; Q_ij = sigma * GR_ij * (T_i^4 - T_j^4).
    """
    rho = 1.0 - eps
    gebhart = np.linalg.solve(np.eye(len(eps)) - vf * rho[None, :], vf * eps[None, :])
    return area[:, None] * eps[:, None] * gebhart


def _square(
    name: str, z: float, node_front: int, node_back: int, *, flip: bool
) -> gmm.GeometryItem:
    mesh = gmm.ThermalMesh()
    mesh.side1_activity = True
    mesh.side2_activity = True
    mesh.side1_optical = gmm.OpticalMaterial("grey", EPS, 0.2)
    mesh.side2_optical = gmm.OpticalMaterial("grey", EPS, 0.2)
    mesh.node1_start = node_front
    mesh.node2_start = node_back
    if flip:
        rect = gmm.Rectangle((0, 0, z), (0, 1, z), (1, 0, z))
    else:
        rect = gmm.Rectangle((0, 0, z), (1, 0, z), (0, 1, z))
    return gmm.GeometryItem(name, rect, mesh)


def main() -> None:
    if not rad.is_available():
        print("No ray-tracing device available - skipping.")
        return

    tm = pc.ThermalModel("gr_squares")
    tm.gmm.add(_square("A", 0.0, node_front=1, node_back=2, flip=False))
    tm.gmm.add(_square("B", GAP, node_front=3, node_back=4, flip=True))
    tm.gmm.create_mesh()

    device = rad.Device.create()
    scene = rad.RadiativeScene(device, tm.gmm.mesh_parts(), tm.gmm.material_table())
    face_areas = np.asarray(scene.face_areas())
    node_numbers = np.asarray(tm.gmm.mesh.node_numbers, dtype=np.int32)

    acc = rad.VfAccumulator(scene)
    for _ in range(8):
        scene.accumulate_vf(acc, rad.TraceSettings(rays_per_face=200_000, seed=0))
    result = acc.result()

    # One face per side here, so face slots already are the nodes; for a meshed
    # model you would aggregate the VF to node level first (see example 2).
    vf = rad.to_scipy(result.vf).toarray()
    eps = np.full(len(node_numbers), EPS)

    gr = gebhart_gr(vf, face_areas, eps)
    gr_black = gebhart_gr(vf, face_areas, np.ones_like(eps))  # eps=1 limit

    a_front, b_front = 0, 2  # slots for node 1 (A front) and node 3 (B front)
    print(f"device: {device.info.name}")
    print(f"node numbers per slot: {node_numbers.tolist()}")
    print(f"\nGR(A_front, B_front)          = {gr[a_front, b_front]:.5f} m^2  (eps={EPS})")
    print(f"GR blackbody limit  A * F     = {gr_black[a_front, b_front]:.5f} m^2  (eps=1)")
    print(f"A * F  (direct check)         = {face_areas[a_front] * vf[a_front, b_front]:.5f} m^2")
    print(f"GR reciprocity max|GR-GR^T|   = {np.abs(gr - gr.T).max():.2e}")
    print(
        "\nNote: solar loads need the (P2+) solar kernel and are not computed here; "
        "GRs above come from the VF via Gebhart, in pure Python."
    )


if __name__ == "__main__":
    main()
