"""Per-frame painters.

Each frame type has a tiny dispatch function that takes a configured
``QPainter`` (in points) and the frame, and emits the corresponding PDF
content. The PDF writer calls ``paint_frame`` for each frame in z-order.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
)

from msword.render._stubs import (
    Frame,
    FrameComposer,
    ImageFrame,
    LayoutLine,
    ShapeFrame,
    TableFrame,
    TextFrame,
)

# Lines provider returns the LayoutLines pre-composed for the given text frame;
# the seam exists so a caller (e.g. a canvas already holding composed lines)
# can skip recomposition.
LinesProvider: TypeAlias = Callable[[TextFrame], list[LayoutLine]]


def _qcolor(rgb: tuple[int, int, int]) -> QColor:
    return QColor(rgb[0], rgb[1], rgb[2])


def paint_frame(
    painter: QPainter,
    frame: Frame,
    lines_provider: LinesProvider | None = None,
) -> None:
    """Paint a single frame onto the open painter (painter is in points)."""
    if not frame.visible:
        return

    painter.save()
    try:
        painter.translate(QPointF(frame.x, frame.y))
        if frame.rotation:
            # Rotate around the frame center so inner geometry stays (0,0)-based.
            painter.translate(QPointF(frame.w / 2.0, frame.h / 2.0))
            painter.rotate(frame.rotation)
            painter.translate(QPointF(-frame.w / 2.0, -frame.h / 2.0))

        if isinstance(frame, TextFrame):
            _paint_text_frame(painter, frame, lines_provider)
        elif isinstance(frame, ImageFrame):
            _paint_image_frame(painter, frame)
        elif isinstance(frame, ShapeFrame):
            _paint_shape_frame(painter, frame)
        elif isinstance(frame, TableFrame):
            _paint_table_frame(painter, frame)
    finally:
        painter.restore()


def _paint_text_frame(
    painter: QPainter,
    frame: TextFrame,
    lines_provider: LinesProvider | None,
) -> None:
    if lines_provider is not None:
        lines = lines_provider(frame)
    else:
        result = FrameComposer.compose(frame.story, [frame])
        lines = result.lines_per_frame[0] if result.lines_per_frame else []

    if not lines:
        return

    painter.setPen(QPen(_qcolor(frame.color)))

    # ``drawText(QPointF, str)`` keeps the text as text (vector glyphs)
    # in the PDF content stream — searchable, copyable.
    last_font_key: tuple[str, float] | None = None
    for line in lines:
        font_key = (line.font_family, line.font_size_pt)
        if font_key != last_font_key:
            font = QFont(line.font_family)
            font.setPointSizeF(line.font_size_pt)
            painter.setFont(font)
            last_font_key = font_key
        painter.drawText(QPointF(line.x, line.y), line.text)


def _paint_image_frame(painter: QPainter, frame: ImageFrame) -> None:
    if not frame.image_bytes:
        return
    image = QImage.fromData(frame.image_bytes)
    if image.isNull():
        return
    target = QRectF(0.0, 0.0, frame.w, frame.h)
    # Source rect in the QImage's own pixel space — passing it explicitly
    # ensures Qt embeds the image at native resolution rather than
    # rescaling pixels before encoding.
    source = QRectF(0.0, 0.0, float(image.width()), float(image.height()))
    painter.drawImage(target, image, source)


def _paint_shape_frame(painter: QPainter, frame: ShapeFrame) -> None:
    path = QPainterPath()
    rect = QRectF(0.0, 0.0, frame.w, frame.h)
    if frame.kind == "ellipse":
        path.addEllipse(rect)
    elif frame.kind == "round_rect":
        path.addRoundedRect(rect, frame.corner_radius, frame.corner_radius)
    else:
        path.addRect(rect)

    if frame.fill is not None:
        painter.setBrush(QBrush(_qcolor(frame.fill)))
    else:
        painter.setBrush(Qt.BrushStyle.NoBrush)

    if frame.stroke is not None and frame.stroke_width_pt > 0:
        pen = QPen(_qcolor(frame.stroke))
        pen.setWidthF(frame.stroke_width_pt)
        painter.setPen(pen)
    else:
        painter.setPen(Qt.PenStyle.NoPen)

    painter.drawPath(path)


def _paint_table_frame(painter: QPainter, frame: TableFrame) -> None:
    if frame.rows <= 0 or frame.cols <= 0:
        return

    cell_w = frame.w / frame.cols
    cell_h = frame.h / frame.rows

    grid_pen = QPen(_qcolor(frame.grid_color))
    grid_pen.setWidthF(frame.grid_width_pt)
    painter.setPen(grid_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for r in range(frame.rows + 1):
        y = r * cell_h
        painter.drawLine(QPointF(0.0, y), QPointF(frame.w, y))
    for c in range(frame.cols + 1):
        x = c * cell_w
        painter.drawLine(QPointF(x, 0.0), QPointF(x, frame.h))

    font = QFont(frame.font_family)
    font.setPointSizeF(frame.font_size_pt)
    painter.setFont(font)
    painter.setPen(QPen(_qcolor((0, 0, 0))))

    for r in range(min(frame.rows, len(frame.cells))):
        row = frame.cells[r]
        for c in range(min(frame.cols, len(row))):
            text = row[c]
            if not text:
                continue
            cell_rect = QRectF(c * cell_w, r * cell_h, cell_w, cell_h)
            painter.drawText(cell_rect, text, Qt.AlignmentFlag.AlignCenter)
