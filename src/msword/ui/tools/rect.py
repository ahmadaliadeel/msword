"""Rectangle-shape tool: drag → ShapeFrame (rectangle)."""

from __future__ import annotations

from typing import Any, ClassVar

from msword.ui.tools._drag_frame import DragRectFrameTool


class RectTool(DragRectFrameTool):
    """Drag a rect → ``AddFrameCommand`` of kind ``"shape"``, ``shape="rect"``."""

    name = "Rectangle"
    icon_name = "tool-rect"
    kind = "shape"
    extra_kwargs: ClassVar[dict[str, Any]] = {"shape": "rect"}
