"""Radiative example 1 - view factor between two parallel squares.

Builds two unit squares facing each other one metre apart, runs the GPU
ray-traced view-factor kernel (``pycanha.radiative``), and compares the
Monte-Carlo VF against the analytic closed form for aligned parallel rectangles.

Run: ``uv run python radiative_01_two_squares_vf.py`` (needs a Vulkan
ray-tracing device; lavapipe works).

Everything is reached through ``pycanha`` - the compiled ``pycanha_core`` is an
implementation detail and is never imported directly. ``pc.radiative.to_scipy``
turns the engine's ``SparseF64`` into a ``scipy.sparse.csr_matrix``.
"""

import numpy as np

import pycanha as pc
from pycanha import gmm
from pycanha import radiative as rad

GAP = 1.0  # metres between the two squares
SIDE = 1.0  # square edge length


def analytic_vf_parallel_squares(side: float, gap: float) -> float:
    """Closed-form VF between two identical, directly-opposed parallel squares."""
    x = y = side / gap
    term = (
        np.log(np.sqrt((1 + x**2) * (1 + y**2) / (1 + x**2 + y**2)))
        + x * np.sqrt(1 + y**2) * np.arctan(x / np.sqrt(1 + y**2))
        + y * np.sqrt(1 + x**2) * np.arctan(y / np.sqrt(1 + x**2))
        - x * np.arctan(x)
        - y * np.arctan(y)
    )
    return 2.0 / (np.pi * x * y) * term


def _square(
    name: str, z: float, node_front: int, node_back: int, *, flip: bool
) -> gmm.GeometryItem:
    """One unmeshed square in the z=``z`` plane with a white-paint optical material.

    ``flip`` reverses the winding so the front side (side 1) points toward -z
    instead of +z, which lets the two squares face each other.
    """
    mesh = gmm.ThermalMesh()  # no subdivision -> a single face per side
    mesh.side1_activity = True
    mesh.side2_activity = True
    mesh.side1_optical = gmm.OpticalMaterial("white_paint", 0.8, 0.2)
    mesh.side2_optical = gmm.OpticalMaterial("white_paint", 0.8, 0.2)
    mesh.node1_start = node_front  # side 1 (front)
    mesh.node2_start = node_back  # side 2 (back)
    if flip:
        rect = gmm.Rectangle((0, 0, z), (0, SIDE, z), (SIDE, 0, z))  # normal -> -z
    else:
        rect = gmm.Rectangle((0, 0, z), (SIDE, 0, z), (0, SIDE, z))  # normal -> +z
    return gmm.GeometryItem(name, rect, mesh)


def main() -> None:
    if not rad.is_available():
        print("No ray-tracing device available - skipping.")
        return

    # Square A at z=0 faces +z; square B at z=GAP faces -z -> they face each other.
    tm = pc.ThermalModel("two_squares")
    tm.gmm.add(_square("A", 0.0, node_front=1, node_back=2, flip=False))
    tm.gmm.add(_square("B", GAP, node_front=3, node_back=4, flip=True))
    tm.gmm.create_mesh()

    device = rad.Device.create()
    print(f"device: {device.info.name} (software={device.info.software})")

    scene = rad.RadiativeScene(device, tm.gmm.mesh_parts(), tm.gmm.material_table())
    # Face slots are interleaved [A_front, A_back, B_front, B_back] -> node numbers:
    node_numbers = np.asarray(tm.gmm.mesh.node_numbers)
    print("face-slot node numbers:", node_numbers.tolist())

    # Trace in several additive batches; VfAccumulator sums first-hit counts.
    acc = rad.VfAccumulator(scene)
    for _ in range(8):
        scene.accumulate_vf(acc, rad.TraceSettings(rays_per_face=200_000, seed=0))
    result = acc.result()

    vf = rad.to_scipy(result.vf).toarray()
    row_sums = np.asarray(result.row_sums)

    # A_front is slot 0 (node 1), B_front is slot 2 (node 3).
    a_front, b_front = 0, 2
    f_ab = float(vf[a_front, b_front])
    analytic = analytic_vf_parallel_squares(SIDE, GAP)

    print("\nView-factor matrix (rows = emitting slot):")
    print(np.round(vf, 4))
    print(f"\nF(A_front -> B_front)  Monte-Carlo = {f_ab:.4f}")
    print(f"F(A_front -> B_front)  analytic    = {analytic:.4f}")
    print(f"relative error                     = {abs(f_ab - analytic) / analytic:.2%}")
    print(f"VF from A_front to deep space      = {1.0 - row_sums[a_front]:.4f}")
    print(f"reciprocity residual (stats)       = {result.stats.reciprocity_residual:.2e}")
    print(f"total rays traced                  = {result.stats.total_rays:,}")

    # --- 3D view of what was traced ---------------------------------------------
    # One distinct color per tmm node: the two facing squares are nodes 1 and 3
    # (their back sides, nodes 2 and 4, are the same two quads seen from behind).
    print("\nopening PyVista window (one color per node)...")
    tm.gmm.plot(scalars="node_number", show_edges=True)


if __name__ == "__main__":
    main()
