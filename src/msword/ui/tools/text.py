"""Text-frame tool: drag a rectangle to add a new TextFrame."""

from __future__ import annotations

from msword.ui.tools._drag_frame import DragRectFrameTool


class TextFrameTool(DragRectFrameTool):
    """Drag a rect → ``AddFrameCommand`` of kind ``"text"``."""

    name = "Text Frame"
    icon_name = "tool-text-frame"
    kind = "text"
