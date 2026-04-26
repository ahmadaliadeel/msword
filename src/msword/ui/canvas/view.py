"""`CanvasView` — the `QGraphicsView` that hosts the page canvas (spec §6).

Responsibilities:

- own the `QGraphicsScene` and the `PageItem`s + their child `FrameItem`s;
- support two view modes:
    - *paged*: pages stacked vertically with a gap (Quark / InDesign style);
    - *flow*: pages stacked contiguously, no gap (continuous "web layout"
      flow as called out in spec §6);
- Ctrl+wheel zoom (clamped 10 %-800 %); fit-page / fit-spread / fit-width;
- pan via middle-mouse drag, space-and-drag, or the explicit Hand tool.

The view is a *pure subscriber*: nothing here mutates the document. Frame
mouse handlers issue commands through a per-view *command sink*, which the
host (eventually `MainWindow`) wires to the real `UndoStack`. Until that
wiring lands the sink defaults to a no-op.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QTransform
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QWidget

from msword.ui.canvas._stubs import (
    Document,
    Frame,
    FrameComposer,
    ImageFrame,
    ShapeFrame,
    TableFrame,
    TextFrame,
    ViewMode,
)
from msword.ui.canvas.frame_item import CommandSink, FrameItem
from msword.ui.canvas.image_frame_item import ImageFrameItem
from msword.ui.canvas.page_item import PageItem
from msword.ui.canvas.shape_frame_item import ShapeFrameItem
from msword.ui.canvas.table_frame_item import TableFrameItem
from msword.ui.canvas.text_frame_item import TextFrameItem

if TYPE_CHECKING:
    from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent

# Per spec §6: clamp zoom 10 %-800 %.
MIN_ZOOM = 0.10
MAX_ZOOM = 8.0

# Visual gap between pages in paged mode (points).
_PAGE_GAP_PAGED = 24.0
_PAGE_GAP_FLOW = 0.0


class CanvasView(QGraphicsView):
    """The page canvas. Rebuild the scene from a `Document` via `set_document`."""

    def __init__(
        self,
        composer: FrameComposer | None = None,
        command_sink: CommandSink | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(Qt.GlobalColor.lightGray)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMouseTracking(True)

        self._composer = composer or FrameComposer()
        self._command_sink: CommandSink = command_sink or _noop_sink
        self._document: Document | None = None
        self._mode: ViewMode = ViewMode.PAGED
        self._page_items: list[PageItem] = []
        self._frame_items: list[FrameItem] = []
        self._zoom: float = 1.0
        # Pan state: middle-mouse OR space+drag OR explicit Hand-tool selection.
        self._panning: bool = False
        self._space_held: bool = False
        self._hand_tool: bool = False
        self._pan_anchor: QPointF | None = None

    # -- public API ---------------------------------------------------------

    @property
    def document(self) -> Document | None:
        return self._document

    @property
    def mode(self) -> ViewMode:
        return self._mode

    @property
    def page_items(self) -> list[PageItem]:
        return list(self._page_items)

    @property
    def frame_items(self) -> list[FrameItem]:
        return list(self._frame_items)

    def set_document(self, document: Document) -> None:
        """(Re)build the scene from the given document."""
        self._document = document
        self._rebuild_scene()

    def set_command_sink(self, sink: CommandSink | None) -> None:
        self._command_sink = sink or _noop_sink
        for item in self._frame_items:
            item.set_command_sink(self._command_sink)

    def set_mode(self, mode: ViewMode) -> None:
        if mode is self._mode:
            return
        self._mode = mode
        self._lay_out_pages()

    def toggle_mode(self) -> None:
        self.set_mode(ViewMode.FLOW if self._mode is ViewMode.PAGED else ViewMode.PAGED)

    def set_hand_tool(self, enabled: bool) -> None:
        """Switch the canvas's pointer to "pan" mode (Hand tool)."""
        self._hand_tool = enabled
        self._update_drag_mode()

    # -- zoom ---------------------------------------------------------------

    def zoom_to(self, factor: float) -> None:
        clamped = max(MIN_ZOOM, min(MAX_ZOOM, factor))
        self._zoom = clamped
        transform = QTransform()
        transform.scale(clamped, clamped)
        self.setTransform(transform)

    def zoom_in(self, step: float = 1.25) -> None:
        self.zoom_to(self._zoom * step)

    def zoom_out(self, step: float = 1.25) -> None:
        self.zoom_to(self._zoom / step)

    @property
    def zoom(self) -> float:
        return self._zoom

    def fit_page(self, page_index: int = 0) -> None:
        if not self._page_items:
            return
        index = max(0, min(page_index, len(self._page_items) - 1))
        self._fit_to(self._page_items[index].sceneBoundingRect())

    def fit_spread(self, page_index: int = 0) -> None:
        """Fit a 2-page spread starting at *page_index* (or the single page)."""
        if not self._page_items:
            return
        a = max(0, min(page_index, len(self._page_items) - 1))
        b = min(a + 1, len(self._page_items) - 1)
        rect = self._page_items[a].sceneBoundingRect().united(
            self._page_items[b].sceneBoundingRect()
        )
        self._fit_to(rect)

    def fit_width(self) -> None:
        if not self._page_items:
            return
        # Use the trim width — bleed sits outside the visible "page" the user
        # cares about. v1 assumes all pages share a width.
        page = self._page_items[0].page
        viewport_w = max(1, self.viewport().width())
        scale = viewport_w / max(1.0, page.width)
        self.zoom_to(scale)
        self.centerOn(self._page_items[0].sceneBoundingRect().center())

    # -- scene construction -------------------------------------------------

    def _rebuild_scene(self) -> None:
        self._scene.clear()
        self._page_items.clear()
        self._frame_items.clear()

        if self._document is None:
            return

        for page in self._document.pages:
            page_item = PageItem(page)
            self._scene.addItem(page_item)
            self._page_items.append(page_item)
            for frame in page.frames:
                frame_item = self._make_frame_item(frame)
                if frame_item is None:
                    continue
                frame_item.setParentItem(page_item)
                self._frame_items.append(frame_item)
        self._lay_out_pages()

    def _make_frame_item(self, frame: Frame) -> FrameItem | None:
        if isinstance(frame, TextFrame):
            return TextFrameItem(frame, composer=self._composer, command_sink=self._command_sink)
        if isinstance(frame, ImageFrame):
            return ImageFrameItem(frame, command_sink=self._command_sink)
        if isinstance(frame, ShapeFrame):
            return ShapeFrameItem(frame, command_sink=self._command_sink)
        if isinstance(frame, TableFrame):
            return TableFrameItem(frame, command_sink=self._command_sink)
        return None

    def _lay_out_pages(self) -> None:
        gap = _PAGE_GAP_PAGED if self._mode is ViewMode.PAGED else _PAGE_GAP_FLOW
        y = 0.0
        for page_item in self._page_items:
            page = page_item.page
            page_item.setPos(0.0, y)
            y += page.height + gap
        # Encompass the bleed margin so the scene rect doesn't clip chrome.
        if self._page_items:
            first = self._page_items[0].page
            last = self._page_items[-1].page
            scene_rect = QRectF(
                -first.bleed,
                -first.bleed,
                first.width + 2 * first.bleed,
                y - gap + last.bleed,
            )
        else:
            scene_rect = QRectF()
        self._scene.setSceneRect(scene_rect)

    def _fit_to(self, rect: QRectF) -> None:
        if rect.width() <= 0 or rect.height() <= 0:
            return
        viewport = self.viewport().rect()
        scale = min(
            viewport.width() / rect.width(),
            viewport.height() / rect.height(),
        )
        self.zoom_to(scale)
        self.centerOn(rect.center())

    # -- input --------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.0 + (0.0015 * delta)
            self.zoom_to(self._zoom * factor)
            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = True
            self._update_drag_mode()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = False
            self._update_drag_mode()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Middle-button OR space-modifier OR Hand-tool ⇒ pan, never select.
        if event.button() == Qt.MouseButton.MiddleButton or self._space_held or self._hand_tool:
            self._panning = True
            self._pan_anchor = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._panning and self._pan_anchor is not None:
            delta = event.position() - self._pan_anchor
            self._pan_anchor = event.position()
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - int(delta.x()))
            v_bar.setValue(v_bar.value() - int(delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._panning and (
            event.button() == Qt.MouseButton.MiddleButton
            or event.button() == Qt.MouseButton.LeftButton
        ):
            self._panning = False
            self._pan_anchor = None
            self._update_drag_mode()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _update_drag_mode(self) -> None:
        if self._hand_tool or self._space_held:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.unsetCursor()


def _noop_sink(_command: object) -> None:
    """Default command sink — discards commands until a real one is installed."""


# Re-export for `from msword.ui.canvas.view import …`.
__all__ = ["MAX_ZOOM", "MIN_ZOOM", "CanvasView", "CommandSink", "ViewMode"]
