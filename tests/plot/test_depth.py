"""Where the near and far planes end up, which is what decides hidden lines.

The depth buffer's precision is spread over the near-far range, so a range far
wider than the geometry is what lets an edge behind a panel win the depth test
against the panel. VTK's own reset gives exactly that - the bounding box
inflated by half its depth, then a near plane clamped to a thousandth of the
far one - so the viewer fits the planes itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest
from PySide6.QtWidgets import QWidget

import pycanha as pc
from pycanha import gmm
from pycanha.plot.window import FOCAL_NEAR_FRACTION, NEAR_PLANE_FLOOR, ViewerWindow

from .offscreen import OffscreenView

if TYPE_CHECKING:
    from collections.abc import Iterator

#: Where the two panels of the test model sit on the view axis.
FRONT_Z = 1.0
BACK_Z = 0.0


def stacked_model() -> gmm.GeometryModel:
    """Two unit panels one behind the other, a metre apart on z."""
    tm = pc.ThermalModel("stack")
    for name, height in (("back", BACK_Z), ("front", FRONT_Z)):
        tm.gmm.add(
            gmm.GeometryItem(
                name,
                gmm.Rectangle((0, 0, height), (1, 0, height), (0, 1, height)),
                gmm.ThermalMesh(),
            )
        )
    return tm.gmm


@pytest.fixture
def drawn(qtbot: object) -> Iterator[ViewerWindow]:
    del qtbot
    viewer = ViewerWindow(stacked_model(), view=OffscreenView())
    yield viewer
    viewer.close()


def look_from(viewer: ViewerWindow, eye_z: float) -> tuple[float, float]:
    """Point the camera down at the panels from ``eye_z`` and render a frame."""
    camera = viewer.plotter.camera
    camera.SetPosition(0.5, 0.5, eye_z)
    camera.SetFocalPoint(0.5, 0.5, BACK_Z)
    camera.SetViewUp(0.0, 1.0, 0.0)
    viewer.plotter.render()
    near, far = camera.GetClippingRange()
    return float(near), float(far)


def test_the_planes_land_on_the_geometry(drawn: ViewerWindow) -> None:
    near, far = look_from(drawn, 10.0)
    # The near panel is 9 away and the far one 10, and each plane clears its
    # own panel by a hair rather than by half the depth of the scene.
    assert near == pytest.approx(0.99 * 9.0)
    assert far == pytest.approx(1.01 * 10.0)


def test_the_range_is_the_scene_rather_than_a_thousand_to_one(drawn: ViewerWindow) -> None:
    near, far = look_from(drawn, 10.0)
    # What VTK leaves behind is a flat 1000 from every viewpoint, whatever the
    # model - and a 24-bit buffer spread that thinly cannot keep two surfaces a
    # fraction of a percent of the model apart on separate depth values.
    assert far / near < 2.0


def test_nothing_on_screen_is_clipped_by_its_own_near_plane(drawn: ViewerWindow) -> None:
    # Every distance at which the front panel is further from the camera than
    # the fraction of the subject's distance the near plane may claim.
    for eye_z in (10.0, 4.0, 1.5, 1.05):
        near, _ = look_from(drawn, eye_z)
        assert near <= eye_z - FRONT_Z


def test_the_near_plane_does_not_chase_a_vertex_by_the_camera(drawn: ViewerWindow) -> None:
    """A millimetre-deep near plane would cost the whole frame its precision.

    The camera here has been pushed a millimetre past the front panel while
    still looking at the back one. Following that panel would put the near
    plane at a thousandth of the subject's distance and spend the depth buffer
    on the gap; it is clipped instead, which is what the eye expects of
    something it has just moved through.
    """
    eye_z = FRONT_Z + 0.001
    near, _ = look_from(drawn, eye_z)
    reach = eye_z - BACK_Z
    assert near == pytest.approx(FOCAL_NEAR_FRACTION * reach)
    assert near > eye_z - FRONT_Z


def test_the_near_plane_stops_at_a_floor_against_the_subject(drawn: ViewerWindow) -> None:
    """Looking at a panel from a hair above it, the subject itself is at no distance.

    A fraction of *that* is no distance either, so the last-resort floor takes
    over: a fixed fraction of the far plane, which is VTK's own rule and what
    the viewer used to be pinned at from every viewpoint.
    """
    camera = drawn.plotter.camera
    camera.SetPosition(0.5, 0.5, FRONT_Z + 5e-4)
    camera.SetFocalPoint(0.5, 0.5, FRONT_Z)
    camera.SetViewUp(0.0, 1.0, 0.0)
    drawn.plotter.render()
    near, far = camera.GetClippingRange()
    assert near == pytest.approx(NEAR_PLANE_FLOOR * far)


def test_a_model_entirely_behind_the_camera_is_left_alone(drawn: ViewerWindow) -> None:
    camera = drawn.plotter.camera
    camera.SetPosition(0.5, 0.5, -5.0)
    camera.SetFocalPoint(0.5, 0.5, -10.0)
    before = camera.GetClippingRange()
    drawn.tighten_clipping_range()
    assert camera.GetClippingRange() == before


def test_the_fit_covers_every_point_of_the_model(drawn: ViewerWindow) -> None:
    """From an angle, so the extreme points are corners rather than a whole face."""
    camera = drawn.plotter.camera
    camera.SetPosition(6.0, 5.0, 4.0)
    camera.SetFocalPoint(0.5, 0.5, 0.5)
    drawn.plotter.render()
    near, far = camera.GetClippingRange()

    eye = np.asarray(camera.GetPosition())
    direction = np.asarray(camera.GetFocalPoint()) - eye
    direction /= np.linalg.norm(direction)
    depths = np.asarray(drawn.scene.points) @ direction - eye @ direction
    assert near <= depths.min()
    assert far >= depths.max()


def test_the_headless_viewer_has_no_range_to_fit(qtbot: object) -> None:
    del qtbot
    viewer = ViewerWindow(stacked_model(), view=QWidget())
    try:
        assert viewer.plotter is None
        # Nothing to fit and nothing to raise: the call is a no-op without a view.
        viewer.tighten_clipping_range()
    finally:
        viewer.close()
