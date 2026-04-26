"""Polygon tool: click vertices, double-click to close."""

from __future__ import annotations

from msword.ui.tools._point_list import PointListTool


class PolygonTool(PointListTool):
    """Click successive vertices; double-click closes and pushes the command."""

    name = "Polygon"
    icon_name = "tool-polygon"
    shape = "polygon"
    min_points = 3
