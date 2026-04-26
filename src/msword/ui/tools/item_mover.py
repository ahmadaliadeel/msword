"""Item-mover tool: move-only (no rubber-band, no resize)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsView

from msword.ui.tools.base import Tool
from msword.ui.tools.selection import _hit_test

if TYPE_CHECKING:
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent


class ItemMoverTool(Tool):
    """Move-only tool — drag a frame to reposition it; no rubber-band select."""

    name = "Item Mover"
    icon_name = "tool-item-mover"
    cursor = Qt.CursorShape.SizeAllCursor

    def __init__(self) -> None:
        super().__init__()
        self._target: Any = None
        self._press: QPointF | None = None

    def activate(self, canvas):  # type: ignore[no-untyped-def]
        super().activate(canvas)
        canvas.viewport_drag_mode(QGraphicsView.DragMode.NoDrag)

    def on_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        canvas = self.canvas
        if canvas is None:
            return
        page = canvas.current_page
        if page is None:
            return
        self._target = _hit_test(page, scene_pos)
        self._press = scene_pos

    def on_mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        if self._target is None or self._press is None:
            return
        dx = scene_pos.x() - self._press.x()
        dy = scene_pos.y() - self._press.y()
        self._target.x += dx
        self._target.y += dy
        self._press = scene_pos

    def on_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        self._target = None
        self._press = None
