"""Selection tool: rubber-band drag select + click-to-select."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QGraphicsView

from msword.ui.tools.base import Tool

if TYPE_CHECKING:
    from PySide6.QtGui import QMouseEvent


class SelectionTool(Tool):
    """Pointer/Selection tool — clicks select; drags rubber-band select."""

    name = "Selection"
    icon_name = "tool-selection"
    cursor = Qt.CursorShape.ArrowCursor

    def __init__(self) -> None:
        super().__init__()
        self._press_pos: QPointF | None = None

    def activate(self, canvas):  # type: ignore[no-untyped-def]
        super().activate(canvas)
        canvas.viewport_drag_mode(QGraphicsView.DragMode.RubberBandDrag)

    def deactivate(self) -> None:
        canvas = self.canvas
        if canvas is not None:
            canvas.viewport_drag_mode(QGraphicsView.DragMode.NoDrag)
        super().deactivate()

    def on_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        self._press_pos = QPointF(scene_pos)
        self._click_select(scene_pos)

    def on_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        self._press_pos = None

    def _click_select(self, scene_pos: QPointF) -> None:
        canvas = self.canvas
        if canvas is None:
            return
        page = canvas.current_page
        if page is None:
            return
        hit = _hit_test(page, scene_pos)
        # The real CanvasView (unit 16) keeps selection on the QGraphicsScene;
        # the stub canvas exposes a ``selected`` list for assertions.
        selected = getattr(canvas, "selected", None)
        if selected is None:
            return
        selected.clear()
        if hit is not None:
            selected.append(hit)


def _hit_test(page, scene_pos: QPointF):  # type: ignore[no-untyped-def]
    """Return the topmost frame under ``scene_pos`` or ``None``."""
    x, y = scene_pos.x(), scene_pos.y()
    for frame in reversed(getattr(page, "frames", [])):
        if frame.x <= x <= frame.x + frame.w and frame.y <= y <= frame.y + frame.h:
            return frame
    return None
