"""`ShapeFrameItem` — renders rect / oval / line shapes.

Stroke + fill are taken from the frame's shape attributes (in v1 the shape
itself is the only style channel; full object styles arrive with unit 8).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen

from msword.ui.canvas._stubs import ShapeFrame, ShapeKind
from msword.ui.canvas.frame_item import CommandSink, FrameItem

if TYPE_CHECKING:
    from PySide6.QtWidgets import QGraphicsItem


_DEFAULT_STROKE = QColor("#202020")
_DEFAULT_FILL = QColor(0, 0, 0, 0)  # transparent


class ShapeFrameItem(FrameItem):
    """Renders a `ShapeFrame`."""

    def __init__(
        self,
        frame: ShapeFrame,
        command_sink: CommandSink | None = None,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(frame, command_sink=command_sink, parent=parent)

    @property
    def shape_frame(self) -> ShapeFrame:
        assert isinstance(self._frame, ShapeFrame)
        return self._frame

    def _paint_content(self, painter: QPainter, rect: QRectF) -> None:
        sf = self.shape_frame
        painter.setPen(QPen(_DEFAULT_STROKE, sf.stroke_width))
        if sf.shape_kind is ShapeKind.LINE:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            # Diagonal: bounding box's top-left to bottom-right.
            painter.drawLine(QPointF(rect.left(), rect.top()), QPointF(rect.right(), rect.bottom()))
            return

        painter.setBrush(QBrush(_DEFAULT_FILL))
        if sf.shape_kind is ShapeKind.OVAL:
            painter.drawEllipse(rect)
        else:
            painter.drawRect(rect)
