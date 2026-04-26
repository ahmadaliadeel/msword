"""`FrameItem` — base class for all frame renderings.

Subclasses (text/image/shape/table) override `_paint_content`. The base owns:

- the bounding rect (frame geometry in *scene* coords; the item is positioned
  at the parent page's origin, so frame coords are page-relative);
- selection chrome — eight resize handles + one rotation handle;
- mouse handlers that turn drag-and-release into `MoveFrameCommand` /
  `ResizeFrameCommand` instances posted to a *command sink* (set by
  `CanvasView`). The view, in turn, hands them to the real undo stack.

Per the anchor invariant: **views never mutate the model**. The frame item
records the geometry transient locally for visual feedback; on release it
emits a command and immediately reverts its local geometry — the command
applies (or undoes) the change and the model triggers a re-render.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem

from msword.ui.canvas._stubs import Frame, MoveFrameCommand, ResizeFrameCommand

if TYPE_CHECKING:
    from PySide6.QtWidgets import (
        QGraphicsSceneMouseEvent,
        QStyleOptionGraphicsItem,
        QWidget,
    )

# Drawn purely as visual feedback; the model is the source of truth.
_HANDLE_SIZE = 6.0
_ROTATION_OFFSET = 18.0
_SELECTION_PEN = QColor("#1e88e5")
_HANDLE_FILL = QColor("#ffffff")
_HANDLE_EDGE = QColor("#1e88e5")


class HandleId(Enum):
    NW = "nw"
    N = "n"
    NE = "ne"
    E = "e"
    SE = "se"
    S = "s"
    SW = "sw"
    W = "w"
    ROTATE = "rotate"


_RESIZE_HANDLES: tuple[HandleId, ...] = (
    HandleId.NW,
    HandleId.N,
    HandleId.NE,
    HandleId.E,
    HandleId.SE,
    HandleId.S,
    HandleId.SW,
    HandleId.W,
)


CommandSink = Callable[[object], None]


@dataclass
class _DragState:
    """In-flight drag bookkeeping. None means "not currently dragging"."""

    handle: HandleId | None  # None == body drag (move)
    start_scene_pos: QPointF
    start_x: float
    start_y: float
    start_w: float
    start_h: float
    cur_x: float
    cur_y: float
    cur_w: float
    cur_h: float


class FrameItem(QGraphicsItem):
    """Base class. Subclasses override `_paint_content(painter, rect)`."""

    def __init__(
        self,
        frame: Frame,
        command_sink: CommandSink | None = None,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._frame = frame
        self._command_sink = command_sink
        self._drag: _DragState | None = None
        # Live overrides while dragging — reset to model geometry on release.
        self._live_w = frame.w
        self._live_h = frame.h
        self.setPos(frame.x, frame.y)
        self.setRotation(frame.rotation)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(frame.z_order)

    # -- public API ---------------------------------------------------------

    @property
    def frame(self) -> Frame:
        return self._frame

    def set_command_sink(self, sink: CommandSink | None) -> None:
        self._command_sink = sink

    # -- QGraphicsItem ------------------------------------------------------

    def boundingRect(self) -> QRectF:
        # Include extra space for handles + rotation handle so they don't get clipped.
        margin = _HANDLE_SIZE + _ROTATION_OFFSET
        return QRectF(
            -margin,
            -margin,
            self._live_w + 2 * margin,
            self._live_h + 2 * margin,
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        content_rect = QRectF(0.0, 0.0, self._live_w, self._live_h)
        self._paint_content(painter, content_rect)
        if self.isSelected():
            self._paint_selection(painter, content_rect)

    # -- subclass hook ------------------------------------------------------

    def _paint_content(self, painter: QPainter, rect: QRectF) -> None:
        """Default: draw a thin frame border. Subclasses override."""
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#888888"), 0.0))
        painter.drawRect(rect)

    # -- selection chrome ---------------------------------------------------

    def _paint_selection(self, painter: QPainter, rect: QRectF) -> None:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(_SELECTION_PEN, 0.0, Qt.PenStyle.SolidLine))
        painter.drawRect(rect)

        # Eight resize handles.
        painter.setBrush(QBrush(_HANDLE_FILL))
        painter.setPen(QPen(_HANDLE_EDGE, 0.0))
        for handle in _RESIZE_HANDLES:
            painter.drawRect(self._handle_rect(handle, rect))

        # Rotation handle — circle above the top-center.
        rot_center = QPointF(rect.center().x(), rect.top() - _ROTATION_OFFSET)
        painter.drawLine(QPointF(rect.center().x(), rect.top()), rot_center)
        painter.drawEllipse(rot_center, _HANDLE_SIZE / 2, _HANDLE_SIZE / 2)

    def _handle_rect(self, handle: HandleId, rect: QRectF) -> QRectF:
        cx = rect.center().x()
        cy = rect.center().y()
        positions: dict[HandleId, QPointF] = {
            HandleId.NW: QPointF(rect.left(), rect.top()),
            HandleId.N: QPointF(cx, rect.top()),
            HandleId.NE: QPointF(rect.right(), rect.top()),
            HandleId.E: QPointF(rect.right(), cy),
            HandleId.SE: QPointF(rect.right(), rect.bottom()),
            HandleId.S: QPointF(cx, rect.bottom()),
            HandleId.SW: QPointF(rect.left(), rect.bottom()),
            HandleId.W: QPointF(rect.left(), cy),
            HandleId.ROTATE: QPointF(cx, rect.top() - _ROTATION_OFFSET),
        }
        center = positions[handle]
        half = _HANDLE_SIZE / 2
        return QRectF(center.x() - half, center.y() - half, _HANDLE_SIZE, _HANDLE_SIZE)

    # -- mouse handling -----------------------------------------------------

    def _hit_handle(self, local_pos: QPointF) -> HandleId | None:
        rect = QRectF(0.0, 0.0, self._live_w, self._live_h)
        rotation_rect = self._handle_rect(HandleId.ROTATE, rect)
        if rotation_rect.contains(local_pos):
            return HandleId.ROTATE
        for handle in _RESIZE_HANDLES:
            if self._handle_rect(handle, rect).contains(local_pos):
                return handle
        return None

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        # Selection click — ensure we're selected, then snapshot geometry.
        was_selected = self.isSelected()
        self.setSelected(True)
        # Resize / rotate handles only respond to clicks on an already-selected
        # frame; the first click is purely a selection click.
        handle = self._hit_handle(event.pos()) if was_selected else None
        self._drag = _DragState(
            handle=handle,
            start_scene_pos=event.scenePos(),
            start_x=self._frame.x,
            start_y=self._frame.y,
            start_w=self._frame.w,
            start_h=self._frame.h,
            cur_x=self._frame.x,
            cur_y=self._frame.y,
            cur_w=self._frame.w,
            cur_h=self._frame.h,
        )
        event.accept()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        drag = self._drag
        if drag is None:
            super().mouseMoveEvent(event)
            return
        delta = event.scenePos() - drag.start_scene_pos
        if drag.handle is None:
            # Body drag = move.
            drag.cur_x = drag.start_x + delta.x()
            drag.cur_y = drag.start_y + delta.y()
            self.setPos(drag.cur_x, drag.cur_y)
        elif drag.handle is HandleId.ROTATE:
            # Rotation drag is purely visual in v1; commands land in unit 9.
            pass
        else:
            new_x, new_y, new_w, new_h = _apply_resize(
                drag.handle,
                drag.start_x,
                drag.start_y,
                drag.start_w,
                drag.start_h,
                delta.x(),
                delta.y(),
            )
            drag.cur_x, drag.cur_y, drag.cur_w, drag.cur_h = new_x, new_y, new_w, new_h
            self.prepareGeometryChange()
            self._live_w = new_w
            self._live_h = new_h
            self.setPos(new_x, new_y)
        event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        drag = self._drag
        self._drag = None
        if drag is None:
            super().mouseReleaseEvent(event)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        # Reset live geometry — the command will apply the real change.
        self.prepareGeometryChange()
        self._live_w = drag.start_w
        self._live_h = drag.start_h
        self.setPos(drag.start_x, drag.start_y)

        if drag.handle is None:
            if drag.cur_x != drag.start_x or drag.cur_y != drag.start_y:
                self._emit(
                    MoveFrameCommand(
                        frame_id=self._frame.id,
                        new_x=drag.cur_x,
                        new_y=drag.cur_y,
                    )
                )
        elif drag.handle is HandleId.ROTATE:
            pass  # handled in unit 9
        else:
            if drag.cur_w != drag.start_w or drag.cur_h != drag.start_h:
                self._emit(
                    ResizeFrameCommand(
                        frame_id=self._frame.id,
                        new_w=drag.cur_w,
                        new_h=drag.cur_h,
                    )
                )
        event.accept()

    # -- command plumbing ---------------------------------------------------

    def _emit(self, command: object) -> None:
        if self._command_sink is not None:
            self._command_sink(command)


def _apply_resize(
    handle: HandleId,
    x: float,
    y: float,
    w: float,
    h: float,
    dx: float,
    dy: float,
) -> tuple[float, float, float, float]:
    """Apply a resize delta to (x, y, w, h) for the given handle.

    Width / height are clamped to a small minimum so the frame doesn't
    invert during a wild drag.
    """
    min_size = 8.0
    new_x, new_y, new_w, new_h = x, y, w, h

    if handle in (HandleId.NW, HandleId.W, HandleId.SW):
        new_x = x + dx
        new_w = w - dx
    elif handle in (HandleId.NE, HandleId.E, HandleId.SE):
        new_w = w + dx
    if handle in (HandleId.NW, HandleId.N, HandleId.NE):
        new_y = y + dy
        new_h = h - dy
    elif handle in (HandleId.SW, HandleId.S, HandleId.SE):
        new_h = h + dy

    if new_w < min_size:
        if handle in (HandleId.NW, HandleId.W, HandleId.SW):
            new_x -= min_size - new_w
        new_w = min_size
    if new_h < min_size:
        if handle in (HandleId.NW, HandleId.N, HandleId.NE):
            new_y -= min_size - new_h
        new_h = min_size

    return new_x, new_y, new_w, new_h
