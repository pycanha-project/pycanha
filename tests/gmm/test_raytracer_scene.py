"""Layer-3 GeometryModel raytracer scene assembly: mesh_parts / material_table.

Covers the thin passthroughs exposed on the pycanha ``GeometryModel`` wrapper in
0.16 and, when a Vulkan ray-tracing device is present, a small view-factor
end-to-end run driven entirely through the pycanha surface.
"""

import numpy as np
import pytest

import pycanha as pc
from pycanha import gmm
from pycanha import radiative as rad


def _panel_model() -> pc.ThermalModel:
    """A single meshed rectangle with optical materials and node numbers."""
    mesh = gmm.ThermalMesh()
    mesh.side1_activity = True
    mesh.side2_activity = True
    mesh.side1_optical = gmm.OpticalMaterial("white", 0.9, 0.2)
    mesh.side2_optical = gmm.OpticalMaterial("white", 0.9, 0.2)
    mesh.node1_start = 100
    mesh.node2_start = 200

    rectangle = gmm.Rectangle((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    tm = pc.ThermalModel("panel")
    tm.gmm.add(gmm.GeometryItem("panel", rectangle, mesh))
    tm.gmm.create_mesh()
    return tm


def test_mesh_parts_default_single_remainder() -> None:
    model = _panel_model().gmm
    parts = model.mesh_parts()
    assert len(parts) == 1
    part = parts[0]
    assert isinstance(part, rad.ScenePart)
    assert isinstance(part.kind, rad.PartKind)
    # With no split the remainder part carries the whole mesh.
    assert part.mesh.nt() == model.mesh.nt()


def test_material_table_shapes() -> None:
    model = _panel_model().gmm
    table = model.material_table()
    nf = model.mesh.nf()
    assert isinstance(table, rad.MaterialTable)
    assert table.num_face_slots() == nf
    assert np.asarray(table.properties).shape[1] == 6
    assert np.asarray(table.face_material).shape[0] == nf
    assert np.asarray(table.face_active).shape[0] == nf
    assert table.num_materials() >= 1


@pytest.mark.skipif(
    not rad.is_available(),
    reason="no Vulkan ray-tracing device available",
)
def test_view_factor_end_to_end() -> None:
    model = _panel_model().gmm
    device = rad.Device.create()

    scene = rad.RadiativeScene(device, model.mesh_parts(), model.material_table())
    nf = scene.num_face_slots()
    assert nf == model.mesh.nf()

    acc = rad.VfAccumulator(scene)
    scene.accumulate_vf(acc, rad.TraceSettings(rays_per_face=1024, seed=0))
    result = acc.result()

    assert result.vf.rows == nf
    assert result.vf.cols == nf
    # Row sums are view factors in [0, 1]; the deficit is the VF to space.
    row_sums = np.asarray(result.row_sums)
    assert np.all(row_sums >= -1e-6)
    assert np.all(row_sums <= 1.0 + 1e-6)
    assert result.stats.total_rays > 0
