"""Line tool: drag → ShapeFrame (line)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtWidgets import QGraphicsView

from msword.ui.tools._stubs import AddFrameCommand
from msword.ui.tools.base import Tool

if TYPE_CHECKING:
    from PySide6.QtGui import QMouseEvent


class LineTool(Tool):
    """Drag from a → b → ``AddFrameCommand`` of kind ``"shape"``, ``shape="line"``.

    Differs from rect/oval in that the start- and end-points must be preserved
    (a line isn't symmetric in its bounding rect), so we record both and pass
    them through as ``line=(x1, y1, x2, y2)``.
    """

    name = "Line"
    icon_name = "tool-line"
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self) -> None:
        super().__init__()
        self._start: QPointF | None = None

    def activate(self, canvas):  # type: ignore[no-untyped-def]
        super().activate(canvas)
        canvas.viewport_drag_mode(QGraphicsView.DragMode.NoDrag)

    def on_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        self._start = QPointF(scene_pos)

    def on_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        if self._start is None:
            return
        start = self._start
        self._start = None
        if start == scene_pos:
            return
        rect = QRectF(start, scene_pos).normalized()
        canvas = self.canvas
        if canvas is None:
            return
        document = getattr(canvas, "document", None)
        page = getattr(canvas, "current_page", None)
        if document is None or page is None:
            return
        extra: dict[str, Any] = {
            "shape": "line",
            "line": (start.x(), start.y(), scene_pos.x(), scene_pos.y()),
        }
        canvas.push_command(AddFrameCommand(document, page, rect, "shape", **extra))
