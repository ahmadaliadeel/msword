"""Frame-unlinker tool: break a frame out of its story chain.

Per spec §3 / §9 / §12 (unit 21): clicking a linked TextFrame pushes an
``UnlinkFrameCommand`` that severs the chain at the clicked frame. The
clicked frame retains its geometry but no longer participates in the source
story; downstream frames in the chain remain linked among themselves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsView

from msword.ui.tools._stubs import Tool, UnlinkFrameCommand
from msword.ui.tools._text_frame_hit import hit_test_text_frame

if TYPE_CHECKING:
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent


class UnlinkerTool(Tool):  # type: ignore[misc]
    """Click a linked TextFrame → push ``UnlinkFrameCommand``."""

    name = "Unlinker"
    icon_name = "tool-unlinker"
    cursor = Qt.CursorShape.ForbiddenCursor

    def activate(self, canvas: Any) -> None:
        super().activate(canvas)
        if hasattr(canvas, "viewport_drag_mode"):
            canvas.viewport_drag_mode(QGraphicsView.DragMode.NoDrag)

    def on_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        canvas = self.canvas
        if canvas is None:
            return
        page = getattr(canvas, "current_page", None)
        hit = hit_test_text_frame(page, scene_pos)
        if hit is None:
            return
        # Only meaningful on a frame that actually belongs to a story chain.
        if getattr(hit, "story_ref", None) is None:
            return
        document = getattr(canvas, "document", None)
        command = UnlinkFrameCommand(document, hit)
        canvas.push_command(command)
        if hasattr(canvas, "recompose"):
            canvas.recompose()


__all__ = ["UnlinkerTool"]
