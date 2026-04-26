"""`TableFrameItem` — renders a uniform grid + per-cell text.

Real cell content is `Block`-trees (per spec §4.2 nestable `TableBlock`); in
v1 we render placeholder strings stored on the stub `TableFrame.cells`. When
the model unit lands this paints by walking the cell block tree through the
same composer used for text frames.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from msword.ui.canvas._stubs import TableFrame
from msword.ui.canvas.frame_item import CommandSink, FrameItem

if TYPE_CHECKING:
    from PySide6.QtWidgets import QGraphicsItem


_GRID = QColor("#666666")
_TEXT = QColor("#101010")


class TableFrameItem(FrameItem):
    """Renders a `TableFrame`."""

    def __init__(
        self,
        frame: TableFrame,
        command_sink: CommandSink | None = None,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(frame, command_sink=command_sink, parent=parent)

    @property
    def table_frame(self) -> TableFrame:
        assert isinstance(self._frame, TableFrame)
        return self._frame

    def _paint_content(self, painter: QPainter, rect: QRectF) -> None:
        tf = self.table_frame
        rows = max(1, tf.rows)
        cols = max(1, tf.cols)
        col_w = rect.width() / cols
        row_h = rect.height() / rows

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(_GRID, 0.0))
        painter.drawRect(rect)
        for c in range(1, cols):
            x = rect.left() + c * col_w
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        for r in range(1, rows):
            y = rect.top() + r * row_h
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

        # Cell content (placeholder strings).
        if tf.cells:
            painter.setPen(QPen(_TEXT, 0.0))
            font = QFont()
            font.setPointSizeF(9.0)
            painter.setFont(font)
            for r, row in enumerate(tf.cells[:rows]):
                for c, cell in enumerate(row[:cols]):
                    if not cell:
                        continue
                    cell_rect = QRectF(
                        rect.left() + c * col_w,
                        rect.top() + r * row_h,
                        col_w,
                        row_h,
                    )
                    painter.drawText(
                        cell_rect,
                        int(Qt.AlignmentFlag.AlignCenter),
                        cell,
                    )
