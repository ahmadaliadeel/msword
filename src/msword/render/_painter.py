"""Per-frame painters.

Each frame type has a tiny dispatch function that takes a configured
``QPainter`` (in points) and the frame, and emits the corresponding PDF
content. The PDF writer calls ``paint_frame`` for each frame in z-order.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeAlias

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
)

from msword.model.frame import Frame, ImageFrame, ShapeFrame, TextFrame
from msword.model.table_frame import TableFrame

if TYPE_CHECKING:
    from msword.model.document import Document

# Lines provider returns paragraph strings for the given text frame; the seam
# exists so a caller (e.g. a canvas already holding composed lines) can supply
# pre-shaped text lines instead of letting the painter walk the story itself.
LinesProvider: TypeAlias = Callable[[TextFrame], list[str]]

_DEFAULT_FONT_FAMILY = "Helvetica"
_DEFAULT_FONT_SIZE_PT = 11.0
_DEFAULT_GRID_WIDTH_PT = 0.5


def _qcolor_black() -> QColor:
    return QColor(0, 0, 0)


def paint_frame(
    painter: QPainter,
    frame: Frame,
    doc: Document,
    lines_provider: LinesProvider | None = None,
) -> None:
    """Paint a single frame onto the open painter (painter is in points)."""
    if not frame.visible:
        return

    painter.save()
    try:
        painter.translate(QPointF(frame.x_pt, frame.y_pt))
        if frame.rotation_deg:
            # Rotate around the frame center so inner geometry stays (0,0)-based.
            painter.translate(QPointF(frame.w_pt / 2.0, frame.h_pt / 2.0))
            painter.rotate(frame.rotation_deg)
            painter.translate(QPointF(-frame.w_pt / 2.0, -frame.h_pt / 2.0))

        if isinstance(frame, TextFrame):
            _paint_text_frame(painter, frame, doc, lines_provider)
        elif isinstance(frame, ImageFrame):
            _paint_image_frame(painter, frame, doc)
        elif isinstance(frame, ShapeFrame):
            _paint_shape_frame(painter, frame)
        elif isinstance(frame, TableFrame):
            _paint_table_frame(painter, frame)
    finally:
        painter.restore()


def _paint_text_frame(
    painter: QPainter,
    frame: TextFrame,
    doc: Document,
    lines_provider: LinesProvider | None,
) -> None:
    lines = lines_provider(frame) if lines_provider is not None else _story_lines(frame, doc)

    if not lines:
        return

    font = QFont(_DEFAULT_FONT_FAMILY)
    font.setPointSizeF(_DEFAULT_FONT_SIZE_PT)
    painter.setFont(font)
    painter.setPen(QPen(_qcolor_black()))

    metrics = QFontMetricsF(font)
    leading = metrics.height()
    ascent = metrics.ascent()

    pad = frame.padding
    inner_left = pad.left
    inner_top = pad.top
    inner_bottom = frame.h_pt - pad.bottom

    is_rtl = frame.text_direction == "rtl"
    inner_right = frame.w_pt - pad.right

    cursor_y = inner_top
    for text in lines:
        if cursor_y + leading > inner_bottom + 1e-6:
            break
        if not text:
            cursor_y += leading
            continue
        if is_rtl:
            # RTL paragraphs need Qt's bidi-aware layout to place glyphs
            # right-aligned with correct shaping; the rect form delegates that.
            rect = QRectF(inner_left, cursor_y, inner_right - inner_left, leading)
            flags = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
            painter.drawText(rect, int(flags), text)
        else:
            # ``drawText(QPointF, str)`` keeps the text as vector glyphs in
            # the PDF content stream — searchable, copyable.
            painter.drawText(QPointF(inner_left, cursor_y + ascent), text)
        cursor_y += leading


def _story_lines(frame: TextFrame, doc: Document) -> list[str]:
    """Flatten the frame's story into one display string per paragraph."""
    if not frame.story_ref:
        return []
    story = doc.find_story(frame.story_ref)
    if story is None:
        return []
    return [
        "".join(run.text for run in spec.runs)
        for spec in story.iter_paragraphs()
    ]


def _paint_image_frame(painter: QPainter, frame: ImageFrame, doc: Document) -> None:
    if not frame.asset_ref:
        return
    asset = doc.assets.get(frame.asset_ref)
    if asset is None or not asset.data:
        return
    image = QImage.fromData(asset.data)
    if image.isNull():
        return
    target = QRectF(0.0, 0.0, frame.w_pt, frame.h_pt)
    # Source rect in the QImage's own pixel space — passing it explicitly
    # ensures Qt embeds the image at native resolution rather than
    # rescaling pixels before encoding.
    source = QRectF(0.0, 0.0, float(image.width()), float(image.height()))
    painter.drawImage(target, image, source)


def _paint_shape_frame(painter: QPainter, frame: ShapeFrame) -> None:
    path = QPainterPath()
    rect = QRectF(0.0, 0.0, frame.w_pt, frame.h_pt)
    if frame.shape_kind == "ellipse":
        path.addEllipse(rect)
    elif frame.shape_kind == "rect" and frame.corner_radius_pt > 0:
        path.addRoundedRect(rect, frame.corner_radius_pt, frame.corner_radius_pt)
    elif frame.shape_kind == "polygon" and frame.points:
        path.moveTo(frame.points[0][0], frame.points[0][1])
        for px, py in frame.points[1:]:
            path.lineTo(px, py)
        path.closeSubpath()
    elif frame.shape_kind == "line" and len(frame.points) >= 2:
        path.moveTo(frame.points[0][0], frame.points[0][1])
        path.lineTo(frame.points[1][0], frame.points[1][1])
    else:
        path.addRect(rect)

    # Color-ref → QColor resolution against the document's swatch registry is
    # unit-18's job; for now any fill/stroke inks black so the geometry is
    # at least visible.
    if frame.fill is not None and frame.fill.color_ref is not None:
        painter.setBrush(QBrush(_qcolor_black()))
    else:
        painter.setBrush(Qt.BrushStyle.NoBrush)

    if frame.stroke is not None and frame.stroke.width_pt > 0:
        pen = QPen(_qcolor_black())
        pen.setWidthF(frame.stroke.width_pt)
        painter.setPen(pen)
    else:
        painter.setPen(Qt.PenStyle.NoPen)

    painter.drawPath(path)


def _paint_table_frame(painter: QPainter, frame: TableFrame) -> None:
    rows = frame.rows
    cols = frame.cols
    if not rows or not cols:
        return

    grid_pen = QPen(_qcolor_black())
    grid_pen.setWidthF(_DEFAULT_GRID_WIDTH_PT)
    painter.setPen(grid_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Cumulative offsets per row / column anchor.
    row_offsets: list[float] = [0.0]
    for row in rows:
        row_offsets.append(row_offsets[-1] + row.height_pt)
    col_offsets: list[float] = [0.0]
    for col in cols:
        col_offsets.append(col_offsets[-1] + col.width_pt)

    total_h = row_offsets[-1]
    total_w = col_offsets[-1]
    for y in row_offsets:
        painter.drawLine(QPointF(0.0, y), QPointF(total_w, y))
    for x in col_offsets:
        painter.drawLine(QPointF(x, 0.0), QPointF(x, total_h))
    # Cell text would resolve through the story tree by ``block_ids``; that
    # resolver is not yet wired into the renderer, so for now the table
    # paints as an empty grid.
