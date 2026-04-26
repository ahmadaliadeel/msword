"""Page canvas — `QGraphicsScene` items + view (spec §6).

This package owns the rendering layer only. Mutations come through commands
issued on user interaction; the canvas itself never edits the model.
"""

from __future__ import annotations

from msword.ui.canvas._stubs import (
    Document,
    Frame,
    FrameComposer,
    FrameKind,
    ImageFrame,
    LayoutLine,
    MoveFrameCommand,
    OverflowResult,
    Page,
    ResizeFrameCommand,
    ShapeFrame,
    ShapeKind,
    Story,
    TableFrame,
    TextFrame,
    ViewMode,
)
from msword.ui.canvas.frame_item import FrameItem
from msword.ui.canvas.image_frame_item import ImageFrameItem
from msword.ui.canvas.page_item import PageItem
from msword.ui.canvas.shape_frame_item import ShapeFrameItem
from msword.ui.canvas.table_frame_item import TableFrameItem
from msword.ui.canvas.text_frame_item import TextFrameItem
from msword.ui.canvas.view import CanvasView

__all__ = [
    "CanvasView",
    "Document",
    "Frame",
    "FrameComposer",
    "FrameItem",
    "FrameKind",
    "ImageFrame",
    "ImageFrameItem",
    "LayoutLine",
    "MoveFrameCommand",
    "OverflowResult",
    "Page",
    "PageItem",
    "ResizeFrameCommand",
    "ShapeFrame",
    "ShapeFrameItem",
    "ShapeKind",
    "Story",
    "TableFrame",
    "TableFrameItem",
    "TextFrame",
    "TextFrameItem",
    "ViewMode",
]
