"""`ImageFrameItem` — loads an asset and draws it with a fit transform.

The fit policy here is "fit-content (preserve aspect, no upscaling)". Real
fit modes (fill / fit / stretch / smart) land with the model unit; the canvas
just consumes whatever fit was already resolved at the model layer.

If the asset path is missing or the image fails to load we draw a slashed
placeholder so the frame is still visibly *there*.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen

from msword.ui.canvas._stubs import ImageFrame
from msword.ui.canvas.frame_item import CommandSink, FrameItem

if TYPE_CHECKING:
    from PySide6.QtWidgets import QGraphicsItem


_PLACEHOLDER_FILL = QColor("#f0f0f0")
_PLACEHOLDER_EDGE = QColor("#909090")


class ImageFrameItem(FrameItem):
    """Renders an `ImageFrame`."""

    def __init__(
        self,
        frame: ImageFrame,
        command_sink: CommandSink | None = None,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(frame, command_sink=command_sink, parent=parent)
        self._image: QImage | None = None
        self._loaded_path: str | None = None

    @property
    def image_frame(self) -> ImageFrame:
        assert isinstance(self._frame, ImageFrame)
        return self._frame

    def _load_image(self) -> QImage | None:
        path = self.image_frame.asset_path
        if path == self._loaded_path:
            return self._image
        self._loaded_path = path
        if not path:
            self._image = None
            return None
        image = QImage(path)
        self._image = image if not image.isNull() else None
        return self._image

    def _paint_content(self, painter: QPainter, rect: QRectF) -> None:
        image = self._load_image()
        if image is None or image.isNull():
            self._paint_placeholder(painter, rect)
            return
        # Aspect-preserving fit centered in the frame.
        target = _fit_rect(rect, image.width(), image.height())
        painter.drawImage(target, image)
        # Subtle frame border so the image is visually contained.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#888888"), 0.0))
        painter.drawRect(rect)

    def _paint_placeholder(self, painter: QPainter, rect: QRectF) -> None:
        painter.setBrush(QBrush(_PLACEHOLDER_FILL))
        painter.setPen(QPen(_PLACEHOLDER_EDGE, 0.0))
        painter.drawRect(rect)
        # Diagonal slashes — "no image".
        painter.drawLine(rect.topLeft(), rect.bottomRight())
        painter.drawLine(rect.topRight(), rect.bottomLeft())


def _fit_rect(target: QRectF, src_w: int, src_h: int) -> QRectF:
    """Aspect-preserving fit of (src_w, src_h) into *target*, centered."""
    if src_w <= 0 or src_h <= 0:
        return QRectF(target)
    scale = min(target.width() / src_w, target.height() / src_h)
    w = src_w * scale
    h = src_h * scale
    cx, cy = target.center().x(), target.center().y()
    return QRectF(QPointF(cx - w / 2, cy - h / 2), QPointF(cx + w / 2, cy + h / 2))
