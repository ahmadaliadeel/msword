"""Pen tool: placeholder polyline (Bezier in a future iteration).

Per spec §9 the v1 pen is a placeholder polyline; the real Bezier-curve pen
is a later iteration.
"""

from __future__ import annotations

from msword.ui.tools._point_list import PointListTool


class PenTool(PointListTool):
    """Click points → polyline; double-click finishes."""

    name = "Pen"
    icon_name = "tool-pen"
    shape = "polyline"
    min_points = 2
