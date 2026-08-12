"""Throwaway live check of the 0.20 viewer fixes - NOT a test.

Builds a real QtInteractor (no test in the repo may render), drives it with
real QTest clicks, and asserts the things only a live window can answer:

* a right-click never moves the camera, neither on the geometry nor past it;
* the interactor style is left in no interaction state afterwards;
* hiding geometry does not move the camera;
* the actors that end up on the renderer, and the lighting flag on the mesh.

Run from the pycanha repo with an empty QT_QPA_PLATFORM.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from pyvistaqt import QtInteractor

import pycanha as pc
from pycanha import gmm
from pycanha.plot.state import PickerMode, Selection
from pycanha.plot.window import (
    MESH_ACTOR,
    SELECTION_HIGHLIGHT,
    SELECTION_OUTLINE,
    ViewerWindow,
)

FAILURES: list[str] = []
REPORT = Path(__file__).with_name("live_viewer_report.txt")
LINES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    mark = "ok  " if condition else "FAIL"
    LINES.append(f"{mark} {name}{'  -> ' + detail if detail else ''}")
    REPORT.write_text("\n".join(LINES), encoding="utf-8")
    if not condition:
        FAILURES.append(name)


def model() -> pc.ThermalModel:
    tm = pc.ThermalModel("live")
    for index, name in enumerate(("a", "b")):
        mesh = gmm.ThermalMesh([0.0, 0.5, 1.0], [0.0, 1.0])
        mesh.node1_start = 100 + 10 * index
        mesh.node2_start = 200 + 10 * index
        mesh.side1_color = gmm.Color(255, 0, 0) if index == 0 else gmm.Color(0, 0, 255)
        tm.gmm.add(
            gmm.GeometryItem(
                name,
                gmm.Rectangle((0, 0, float(index)), (2, 0, float(index)), (0, 1, float(index))),
                mesh,
            )
        )
    return tm


def camera_of(window: ViewerWindow) -> tuple[tuple[float, ...], tuple[float, ...], float]:
    camera = window.plotter.camera
    return (
        tuple(np.round(camera.position, 9)),
        tuple(np.round(camera.focal_point, 9)),
        round(float(camera.parallel_scale), 9),
    )


def run(window: ViewerWindow) -> None:
    view = window.view
    centre = QPoint(view.width() // 2, view.height() // 2)
    corner = QPoint(6, 6)

    before = camera_of(window)
    QTest.mouseClick(view, Qt.MouseButton.RightButton, pos=centre)
    QApplication.processEvents()
    check("right-click on the geometry leaves the camera", camera_of(window) == before)
    check("right-click selects", window.state.selection is not None)
    state = window.plotter.iren.style
    check(
        "the style is left in no interaction state",
        int(state.GetState()) == 0,
        f"state={int(state.GetState())}",
    )

    QTest.mouseClick(view, Qt.MouseButton.RightButton, pos=corner)
    QApplication.processEvents()
    check("right-click past the geometry leaves the camera", camera_of(window) == before)
    check("right-click past the geometry clears the selection", window.state.selection is None)
    check(
        "and still leaves no interaction state",
        int(state.GetState()) == 0,
        f"state={int(state.GetState())}",
    )

    # A right *drag* must not dolly either.
    QTest.mousePress(view, Qt.MouseButton.RightButton, pos=centre)
    QTest.mouseMove(view, centre + QPoint(0, 80))
    QApplication.processEvents()
    QTest.mouseRelease(view, Qt.MouseButton.RightButton, pos=centre + QPoint(0, 80))
    QApplication.processEvents()
    check("a right drag does not dolly", camera_of(window) == before)

    # Left-click still selects, and left-drag still orbits.
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=centre)
    QApplication.processEvents()
    check("left-click still selects", window.state.selection is not None)

    QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=centre)
    QTest.mouseMove(view, centre + QPoint(60, 40))
    QApplication.processEvents()
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=centre + QPoint(60, 40))
    QApplication.processEvents()
    check("left drag still orbits", camera_of(window) != before)

    # Hiding must leave the camera exactly where it is.
    parked = camera_of(window)
    window.state.hide([window.model.get_item("b").id])
    QApplication.processEvents()
    check("hiding does not move the camera", camera_of(window) == parked, str(camera_of(window)))
    window.state.show_all()
    QApplication.processEvents()
    check("showing again does not move it either", camera_of(window) == parked)

    # What is actually on the renderer.
    window.state.picker_mode = PickerMode.FACE
    window.state.selection = Selection(item_id=window.model.get_item("a").id, face_id=0, cell=0)
    QApplication.processEvents()
    actors = dict(window.plotter.renderer.actors)
    check("the mesh and both halves of the highlight are drawn",
          {MESH_ACTOR, SELECTION_HIGHLIGHT, SELECTION_OUTLINE} <= set(actors))
    check("the highlight is not pickable", not actors[SELECTION_HIGHLIGHT].GetPickable())
    check(
        "the geometry is unlit by default",
        actors[MESH_ACTOR].prop.lighting is False,
    )
    window.state.lighting = True
    QApplication.processEvents()
    actors = dict(window.plotter.renderer.actors)
    check("the lighting button reaches the actor", actors[MESH_ACTOR].prop.lighting is True)

    window.state.selection = None
    QApplication.processEvents()
    actors = dict(window.plotter.renderer.actors)
    check("deselecting takes both overlays away",
          not ({SELECTION_HIGHLIGHT, SELECTION_OUTLINE} & set(actors)))

    # A reset must put the camera back where the window opened.
    window.reset_view()
    QApplication.processEvents()
    opening = camera_of(window)
    window.plotter.camera.zoom(2.0)
    QApplication.processEvents()
    window.reset_view()
    QApplication.processEvents()
    check("reset puts the camera back", camera_of(window) == opening)


def main() -> int:
    app = QApplication.instance() or QApplication([])
    tm = model()
    window = ViewerWindow(tm.gmm, view=QtInteractor(), thermal_model=tm)
    window.resize(900, 700)
    window.show()

    def go() -> None:
        try:
            run(window)
        finally:
            window.close()
            app.quit()

    QTimer.singleShot(600, go)
    app.exec()
    LINES.append(f"FAILURES: {FAILURES or 'none'}")
    REPORT.write_text("\n".join(LINES), encoding="utf-8")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
