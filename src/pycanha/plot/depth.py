"""Ordering the overlays that lie exactly on the geometry they mark.

An outline, a mesh line and a selection wash are all drawn on the very surface
they belong to, so which one wins the depth test is undefined until it is
decided here. VTK decides it with OpenGL's polygon offset, which shifts a
primitive's depth by::

    factor * (how steeply the surface recedes, per pixel) + units * (one depth step)

Only the second term is used. The first scales with the surface's slope in
screen space, and a surface seen nearly edge-on recedes by many depth steps per
pixel - so a non-zero ``factor`` lifts an overlay off distant, steeply inclined
geometry far enough to punch through whatever is in front of it, and to come
and go as the model is turned. Measured on a 40-unit test plane, a factor of -8
lifted its outline up to 12.7 units off it at a steep viewing angle, against
1.1 with the factor at zero, which is the depth buffer's own precision there.
Everything offset here is *exactly* coincident with what it covers, so the two
share a slope and a constant push is all that is needed to order them - which
is why VTK's own defaults use a factor of zero too.

That leaves a ladder made of constant pushes, from the geometry outwards, and
VTK's own defaults already provide two of its three rungs:

=============================  =====  ========================================
what                           depth  why there
=============================  =====  ========================================
the geometry                       0  the surface everything else lies on
selection wash                    -2  over the geometry, under every line
lines - outlines, mesh, ring      -4  VTK's default for a line, left alone
=============================  =====  ========================================

Pushing the lines further than that only lifts them off their own surface for
no gain, and a line lifted off its surface is a line that shows through what is
in front of it - so the only offset set here is the wash's.

None of this can order two surfaces the depth buffer cannot tell apart in the
first place. That is a question of how much precision the near and far planes
leave, and it is answered in
:meth:`pycanha.plot.window.ViewerWindow.tighten_clipping_range`.
"""

from __future__ import annotations

from typing import Any

#: Push for a surface that lies on another surface - the selection wash. Less
#: than VTK's -4 for a line, so the wash slides under every line rather than
#: swallowing the ones that fall on it.
SURFACE_UNITS = -2.0

#: The slope term, never used - see the module docstring for why.
NO_SLOPE = 0.0


def push_surface(mapper: Any, units: float = SURFACE_UNITS) -> None:
    """Draw ``mapper``'s polygons in front of the surface they are coincident with."""
    mapper.SetResolveCoincidentTopologyToPolygonOffset()
    mapper.SetRelativeCoincidentTopologyPolygonOffsetParameters(NO_SLOPE, units)


def push_lines(mapper: Any) -> None:
    """Draw ``mapper``'s lines in front of the surface they are coincident with.

    The push itself is VTK's own, which is already in front of the wash and is
    the least that keeps a line clear of its surface; all this does is switch
    on the offsetting, which is off until a mapper asks for it.
    """
    mapper.SetResolveCoincidentTopologyToPolygonOffset()
