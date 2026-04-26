"""Hand tool: pan the canvas via Qt's built-in ScrollHandDrag mode."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsView

from msword.ui.tools.base import Tool

if TYPE_CHECKING:
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent


class HandTool(Tool):
    """Pan tool — delegates dragging entirely to ``QGraphicsView``."""

    name = "Hand"
    icon_name = "tool-hand"
    cursor = Qt.CursorShape.OpenHandCursor

    def activate(self, canvas):  # type: ignore[no-untyped-def]
        super().activate(canvas)
        canvas.viewport_drag_mode(QGraphicsView.DragMode.ScrollHandDrag)

    def deactivate(self) -> None:
        canvas = self.canvas
        if canvas is not None:
            canvas.viewport_drag_mode(QGraphicsView.DragMode.NoDrag)
        super().deactivate()

    def on_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        # ScrollHandDrag handles dragging; we still mark drag mode here so a
        # caller that bypassed activate (e.g. a test that only fires a press)
        # still sees the expected mode.
        canvas = self.canvas
        if canvas is not None:
            canvas.viewport_drag_mode(QGraphicsView.DragMode.ScrollHandDrag)
