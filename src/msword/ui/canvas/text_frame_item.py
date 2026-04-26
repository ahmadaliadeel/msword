"""`TextFrameItem` — renders composed lines from a `FrameComposer`.

Per spec §6:

- composed lines are drawn via `QPainter.drawText` (the composer is the
  source of truth for shaping; the item is a renderer);
- multi-column gutters are drawn as faint vertical *column rules* when
  `frame.column_rule` is enabled;
- overflow surfaces a red "+" indicator at the bottom-right corner.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen

from msword.ui.canvas._stubs import FrameComposer, OverflowResult, TextFrame
from msword.ui.canvas.frame_item import CommandSink, FrameItem

if TYPE_CHECKING:
    from PySide6.QtWidgets import QGraphicsItem

_TEXT_FRAME_BORDER = QColor("#cccccc")
_COLUMN_RULE = QColor("#e0e0e0")
_OVERFLOW_RED = QColor("#d83a3a")
_TEXT_INK = QColor("#101010")


class TextFrameItem(FrameItem):
    """Renders a `TextFrame` plus its composed lines."""

    def __init__(
        self,
        frame: TextFrame,
        composer: FrameComposer | None = None,
        command_sink: CommandSink | None = None,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(frame, command_sink=command_sink, parent=parent)
        self._composer = composer or FrameComposer()
        self._cached: OverflowResult | None = None

    @property
    def text_frame(self) -> TextFrame:
        # Narrow the type for callers; the base `frame` attribute is `Frame`.
        assert isinstance(self._frame, TextFrame)
        return self._frame

    def invalidate_layout(self) -> None:
        """Drop any cached composer output; next paint re-composes."""
        self._cached = None
        self.update()

    def _ensure_composed(self) -> OverflowResult:
        if self._cached is None:
            self._cached = self._composer.compose(self.text_frame)
        return self._cached

    def _paint_content(self, painter: QPainter, rect: QRectF) -> None:
        frame = self.text_frame
        # Frame border (subtle, like Quark's default).
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(_TEXT_FRAME_BORDER, 0.0))
        painter.drawRect(rect)

        # Optional column rules.
        cols = max(1, frame.columns)
        if cols > 1 and frame.column_rule:
            column_w = (rect.width() - frame.gutter * (cols - 1)) / cols
            painter.setPen(QPen(_COLUMN_RULE, 0.0))
            for i in range(1, cols):
                x = rect.left() + i * column_w + (i - 1) * frame.gutter + frame.gutter / 2
                painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))

        # Composed lines.
        result = self._ensure_composed()
        painter.setPen(QPen(_TEXT_INK, 0.0))
        font = QFont()
        font.setPointSizeF(10.0)
        painter.setFont(font)
        for line in result.lines:
            painter.drawText(QPointF(line.x, line.y), line.text)

        # Overflow indicator: red "+" badge at bottom-right.
        if result.overflowed:
            self._paint_overflow_badge(painter, rect)

    def _paint_overflow_badge(self, painter: QPainter, rect: QRectF) -> None:
        size = 12.0
        badge = QRectF(
            rect.right() - size - 2.0,
            rect.bottom() - size - 2.0,
            size,
            size,
        )
        painter.setPen(QPen(_OVERFLOW_RED, 0.0))
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawRect(badge)
        painter.setPen(QPen(_OVERFLOW_RED, 1.5))
        cx, cy = badge.center().x(), badge.center().y()
        arm = size / 3
        painter.drawLine(QPointF(cx - arm, cy), QPointF(cx + arm, cy))
        painter.drawLine(QPointF(cx, cy - arm), QPointF(cx, cy + arm))
