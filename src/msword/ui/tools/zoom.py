"""Zoom tool: click to zoom in (Alt-click out); drag a rect to zoom-to-fit."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtWidgets import QGraphicsView

from msword.ui.tools.base import Tool

if TYPE_CHECKING:
    from PySide6.QtGui import QMouseEvent


#: How much each click multiplies the current zoom; matches Quark/InDesign.
ZOOM_STEP = 2.0


class ZoomTool(Tool):
    """Click → zoom in 2x; Alt-click → zoom out 2x; drag a rect → zoom-to-fit."""

    name = "Zoom"
    icon_name = "tool-zoom"
    cursor = Qt.CursorShape.PointingHandCursor

    def __init__(self) -> None:
        super().__init__()
        self._press: QPointF | None = None

    def activate(self, canvas):  # type: ignore[no-untyped-def]
        super().activate(canvas)
        canvas.viewport_drag_mode(QGraphicsView.DragMode.RubberBandDrag)

    def deactivate(self) -> None:
        canvas = self.canvas
        if canvas is not None:
            canvas.viewport_drag_mode(QGraphicsView.DragMode.NoDrag)
        super().deactivate()

    def on_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        self._press = QPointF(scene_pos)

    def on_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        canvas = self.canvas
        press = self._press
        self._press = None
        if canvas is None or press is None:
            return

        rect = QRectF(press, scene_pos).normalized()
        is_drag = rect.width() > 4 and rect.height() > 4

        if is_drag and hasattr(canvas, "zoom_to_rect"):
            canvas.zoom_to_rect(rect)
            return

        zooming_out = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        factor = 1.0 / ZOOM_STEP if zooming_out else ZOOM_STEP
        if hasattr(canvas, "zoom_by"):
            canvas.zoom_by(factor, scene_pos)
