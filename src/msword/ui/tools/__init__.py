"""Modal canvas tools.

Per spec §9: tools are modal — selecting a tool changes click semantics on the
canvas. Unit 20 contributes the basic eleven tools (Selection, Item-mover,
Text-frame, Picture-frame, Rectangle, Oval, Polygon, Pen, Line, Hand, Zoom);
unit 21 contributes Table, Linker, and Unlinker.
"""

from __future__ import annotations

from msword.ui.tools.base import CanvasLike, Tool
from msword.ui.tools.hand import HandTool
from msword.ui.tools.item_mover import ItemMoverTool
from msword.ui.tools.line import LineTool
from msword.ui.tools.linker import LinkerTool
from msword.ui.tools.oval import OvalTool
from msword.ui.tools.pen import PenTool
from msword.ui.tools.picture import PictureFrameTool
from msword.ui.tools.polygon import PolygonTool
from msword.ui.tools.rect import RectTool
from msword.ui.tools.selection import SelectionTool
from msword.ui.tools.table import TableSizeDialog, TableTool
from msword.ui.tools.text import TextFrameTool
from msword.ui.tools.unlinker import UnlinkerTool
from msword.ui.tools.zoom import ZoomTool

__all__ = [
    "CanvasLike",
    "HandTool",
    "ItemMoverTool",
    "LineTool",
    "LinkerTool",
    "OvalTool",
    "PenTool",
    "PictureFrameTool",
    "PolygonTool",
    "RectTool",
    "SelectionTool",
    "TableSizeDialog",
    "TableTool",
    "TextFrameTool",
    "Tool",
    "UnlinkerTool",
    "ZoomTool",
]
