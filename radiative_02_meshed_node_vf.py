"""Radiative example 2 - node-level view factors on meshed squares.

Same two parallel squares as example 1, but each is subdivided into a 3x3 mesh.
Shows the full pipeline:

* face-level VF from the ray tracer (36 face slots),
* area-weighted aggregation to *node* VF with ``radiative.aggregate_matrix``,
* a mesh whose back side uses ``node2_step = 0`` so its 9 faces all share ONE
  node number - aggregation collapses them correctly,
* ``aggregate_flux`` (W/m^2 per face -> W per node),
* a 3D PyVista plot with one discrete colour per node number.

Run: ``uv run python radiative_02_meshed_node_vf.py`` (needs a Vulkan
ray-tracing device; lavapipe works).
"""

import numpy as np

import pycanha as pc
from pycanha import gmm
from pycanha import radiative as rad

GAP = 1.0
SUBDIV = 3  # 3x3 faces per side


def _meshed_square(
    name: str, z: float, node_front: int, node_back: int, *, flip: bool
) -> gmm.GeometryItem:
    grid = list(np.linspace(0.0, 1.0, SUBDIV + 1))
    mesh = gmm.ThermalMesh(grid, grid)
    mesh.side1_activity = True
    mesh.side2_activity = True
    mesh.side1_optical = gmm.OpticalMaterial("white_paint", 0.8, 0.2)
    mesh.side2_optical = gmm.OpticalMaterial("white_paint", 0.8, 0.2)
    mesh.node1_start = node_front
    mesh.node1_step = 1  # front: one node per face (node_front, node_front+1, ...)
    mesh.node2_start = node_back
    mesh.node2_step = 0  # back: every face shares the SAME node number
    if flip:
        rect = gmm.Rectangle((0, 0, z), (0, 1, z), (1, 0, z))
    else:
        rect = gmm.Rectangle((0, 0, z), (1, 0, z), (0, 1, z))
    return gmm.GeometryItem(name, rect, mesh)


def main() -> None:
    if not rad.is_available():
        print("No ray-tracing device available - skipping.")
        return

    tm = pc.ThermalModel("meshed_squares")
    tm.gmm.add(_meshed_square("A", 0.0, node_front=100, node_back=200, flip=False))
    tm.gmm.add(_meshed_square("B", GAP, node_front=300, node_back=400, flip=True))
    tm.gmm.create_mesh()

    node_numbers = np.asarray(tm.gmm.mesh.node_numbers, dtype=np.int32)
    print(f"face slots: {tm.gmm.mesh.nf()}")
    print(f"unique node numbers: {sorted(set(node_numbers.tolist()))}")
    print(f"back-side node 200 covers {(node_numbers == 200).sum()} faces (node2_step=0)")

    device = rad.Device.create()
    scene = rad.RadiativeScene(device, tm.gmm.mesh_parts(), tm.gmm.material_table())
    face_areas = np.asarray(scene.face_areas())

    acc = rad.VfAccumulator(scene)
    for _ in range(6):
        scene.accumulate_vf(acc, rad.TraceSettings(rays_per_face=100_000, seed=0))
    result = acc.result()

    # --- face -> node aggregation ------------------------------------------------
    # aggregate_matrix is *extensive* (m^2): entry[I, J] = sum_i A_i * F_ij.
    nodes = np.asarray(rad.aggregate_nodes(node_numbers))
    node_extensive = rad.to_scipy(rad.aggregate_matrix(result.vf, node_numbers, face_areas))
    node_area = np.array([face_areas[node_numbers == n].sum() for n in nodes])
    node_vf = node_extensive.toarray() / node_area[:, None]  # intensive node VF

    idx = {int(n): i for i, n in enumerate(nodes)}
    print(f"\nnode labels: {nodes.tolist()}")
    print(f"node 200 area = {node_area[idx[200]]:.3f} m^2 (9 faces merged)")
    # Reciprocity: the extensive (A*F) node matrix is symmetric.
    ext = node_extensive.toarray()
    print(f"node reciprocity  max|A_i F_ij - A_j F_ji| = {np.abs(ext - ext.T).max():.2e}")
    print(f"F(node 100 -> node 300) = {node_vf[idx[100], idx[300]]:.4f}")
    print(f"row-sum VF of node 100  = {node_vf[idx[100]].sum():.4f} (rest goes to space)")

    # --- aggregate_flux: uniform 500 W/m^2 on every face -> W per node -----------
    face_flux = np.full(scene.num_face_slots(), 500.0)
    node_flux = np.asarray(rad.aggregate_flux(face_flux, node_numbers, face_areas))
    print(f"node 200 load = {node_flux[idx[200]]:.1f} W  (500 W/m^2 x 1.0 m^2)")

    # --- 3D view of the geometry -------------------------------------------------
    # One discrete colour per node number (no colormap, no shading). Each side of
    # a ThermalMesh is drawn with its own node, so orbit the model to check both:
    # the side-1 face of each square is 9 differently-coloured faces
    # (node1_step=1), while its back is ONE flat colour because node2_step=0 puts
    # all 9 back faces on a single node (200 and 400).
    print("\nopening PyVista window (one discrete colour per node)...")
    print("  front of each square -> 9 colours; back -> 1 flat colour (nodes 200 / 400)")
    tm.gmm.plot(scalars="node_number", show_edges=True)


if __name__ == "__main__":
    main()
