"""Oval-shape tool: drag → ShapeFrame (ellipse)."""

from __future__ import annotations

from typing import Any, ClassVar

from msword.ui.tools._drag_frame import DragRectFrameTool


class OvalTool(DragRectFrameTool):
    """Drag a rect → ``AddFrameCommand`` of kind ``"shape"``, ``shape="oval"``."""

    name = "Oval"
    icon_name = "tool-oval"
    kind = "shape"
    extra_kwargs: ClassVar[dict[str, Any]] = {"shape": "oval"}
