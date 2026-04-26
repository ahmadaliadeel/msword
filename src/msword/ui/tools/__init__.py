"""Modal tools for the page canvas.

Unit 21 contributes the Table, Linker, and Unlinker tools; the basic eleven
tools (Selection, Item-mover, Text-frame, Picture-frame, Rectangle, Oval,
Polygon, Pen, Line, Hand, Zoom) come from unit 20.
"""

from __future__ import annotations

from msword.ui.tools.linker import LinkerTool
from msword.ui.tools.table import TableSizeDialog, TableTool
from msword.ui.tools.unlinker import UnlinkerTool

__all__ = [
    "LinkerTool",
    "TableSizeDialog",
    "TableTool",
    "UnlinkerTool",
]
