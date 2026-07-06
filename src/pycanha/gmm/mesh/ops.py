"""Slimmed-down mesh operations over a TriMesh (either precision).

These forward to the pycanha-core free functions (bound flat on
``pycanha_core.gmm``). Only the six operations kept in 0.15 are exposed.
"""

from __future__ import annotations

from typing import Any

import pycanha_core as pcc


def compute_areas(mesh: Any) -> Any:
    """Per-triangle areas ``(M,)``."""
    return pcc.gmm.compute_areas(mesh)


def compute_centroids(mesh: Any) -> Any:
    """Per-triangle centroids ``(M, 3)``."""
    return pcc.gmm.compute_centroids(mesh)


def compute_face_normals(mesh: Any) -> Any:
    """Per-triangle unit normals ``(M, 3)``."""
    return pcc.gmm.compute_face_normals(mesh)


def bounding_box(mesh: Any) -> tuple[Any, Any]:
    """Axis-aligned bounding box as ``(min_xyz, max_xyz)``."""
    return pcc.gmm.bounding_box(mesh)


def is_watertight(mesh: Any) -> bool:
    """Whether every edge is shared by exactly two triangles."""
    return pcc.gmm.is_watertight(mesh)


def has_consistent_face_ids(mesh: Any) -> bool:
    """Whether there is exactly one face_id per triangle."""
    return pcc.gmm.has_consistent_face_ids(mesh)
