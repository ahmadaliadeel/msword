"""Modal canvas tools.

Per spec §9: tools are modal — selecting a tool changes click semantics on the
canvas. The tools palette (``msword.ui.tools_palette.ToolsPalette``) builds a
vertical icon strip on the left, exclusive within itself, and forwards the
selected tool to the active canvas.

Table & Linker/Unlinker tools are deferred to unit 21.
"""

from __future__ import annotations

from msword.ui.tools.base import CanvasLike, Tool
from msword.ui.tools.hand import HandTool
from msword.ui.tools.item_mover import ItemMoverTool
from msword.ui.tools.line import LineTool
from msword.ui.tools.oval import OvalTool
from msword.ui.tools.pen import PenTool
from msword.ui.tools.picture import PictureFrameTool
from msword.ui.tools.polygon import PolygonTool
from msword.ui.tools.rect import RectTool
from msword.ui.tools.selection import SelectionTool
from msword.ui.tools.text import TextFrameTool
from msword.ui.tools.zoom import ZoomTool

__all__ = [
    "CanvasLike",
    "HandTool",
    "ItemMoverTool",
    "LineTool",
    "OvalTool",
    "PenTool",
    "PictureFrameTool",
    "PolygonTool",
    "RectTool",
    "SelectionTool",
    "TextFrameTool",
    "Tool",
    "ZoomTool",
]
