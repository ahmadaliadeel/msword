"""Shared "click points, double-click to finish" tool implementation.

Polygon and Pen tools both collect a sequence of clicked points and emit an
``AddFrameCommand`` on a closing double-click. The only differences are the
minimum number of points required (3 for a closed polygon, 2 for an open
polyline) and the ``shape`` value stored on the command.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QGraphicsView

from msword.ui.tools._stubs import AddFrameCommand
from msword.ui.tools.base import Tool


class PointListTool(Tool):
    """Base class for click-points/double-click-to-finish tools."""

    cursor = Qt.CursorShape.CrossCursor
    shape: str = ""
    min_points: int = 2

    def __init__(self) -> None:
        super().__init__()
        self._points: list[QPointF] = []

    def activate(self, canvas):  # type: ignore[no-untyped-def]
        super().activate(canvas)
        canvas.viewport_drag_mode(QGraphicsView.DragMode.NoDrag)

    def deactivate(self) -> None:
        self._points.clear()
        super().deactivate()

    def on_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        # Qt sends both MouseButtonPress *and* MouseButtonDblClick on the
        # second press of a double-click; we close on the dbl-click.
        if event.type() == QMouseEvent.Type.MouseButtonDblClick:
            self._finish()
            return
        self._points.append(QPointF(scene_pos))

    def _finish(self) -> None:
        if len(self._points) < self.min_points:
            self._points.clear()
            return
        rect = bounding_rect(self._points)
        verts = [(p.x(), p.y()) for p in self._points]
        self._points.clear()
        canvas = self.canvas
        if canvas is None:
            return
        document = getattr(canvas, "document", None)
        page = getattr(canvas, "current_page", None)
        if document is None or page is None:
            return
        canvas.push_command(
            AddFrameCommand(
                document,
                page,
                rect,
                "shape",
                shape=self.shape,
                vertices=verts,
            )
        )


def bounding_rect(points: list[QPointF]) -> QRectF:
    """Smallest axis-aligned rectangle containing every point."""
    xs = [p.x() for p in points]
    ys = [p.y() for p in points]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    return QRectF(x0, y0, x1 - x0, y1 - y0)
