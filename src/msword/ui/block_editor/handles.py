"""Block-handle overlay (per spec §9).

Provides the left-margin ``⋮⋮`` drag handle that appears when the user
hovers a block, plus its right-click action menu.

The overlay is a child :class:`QGraphicsItem` of a ``TextFrameItem``: it
listens to its parent's hover events to figure out which block is under
the cursor, draws the handle at the parent's left margin for that block,
and dispatches commands on drag-release / menu-action.

Like every other piece of UI in msword, the overlay never mutates the
model directly — it emits :class:`MoveBlockCommand`,
:class:`TransformBlockCommand`, :class:`DuplicateBlockCommand`, or
:class:`DeleteBlockCommand` and lets the undo stack apply them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QMenu,
    QStyleOptionGraphicsItem,
    QWidget,
)

from msword.ui.block_editor._stubs import (
    CommandStub,
    DeleteBlockCommand,
    DuplicateBlockCommand,
    MoveBlockCommand,
    TextFrameItemStub,
    TransformBlockCommand,
)

# Handle geometry constants (in scene/parent local coords).
HANDLE_WIDTH = 14.0
HANDLE_HEIGHT = 16.0
HANDLE_LEFT_MARGIN = -22.0  # to the left of the frame's content rect
HANDLE_TEXT = "⋮⋮"

# "Convert To" options exposed via the right-click menu. Mirrors the
# Markdown-shortcut rule set so users have a discoverable equivalent.
CONVERT_TO_OPTIONS: tuple[tuple[str, str, dict[str, object]], ...] = (
    ("Paragraph", "paragraph", {}),
    ("Heading 1", "heading", {"level": 1}),
    ("Heading 2", "heading", {"level": 2}),
    ("Heading 3", "heading", {"level": 3}),
    ("Bullet list", "list", {"kind": "bullet"}),
    ("Ordered list", "list", {"kind": "ordered"}),
    ("Todo list", "list", {"kind": "todo", "checked": False}),
    ("Quote", "quote", {}),
    ("Code", "code", {"language": ""}),
    ("Divider", "divider", {}),
)


@dataclass(frozen=True)
class BlockHandleHit:
    """Result of hit-testing a block region in the parent frame."""

    block_id: str
    block_index: int
    region: QRectF


# A "command sink" — anywhere a command can be sent (real undo stack in
# production, a list-append in tests).
CommandSink = Callable[[CommandStub], None]


class BlockHandlesOverlay(QGraphicsItem):
    """``⋮⋮`` handle overlay for a single ``TextFrameItem``.

    Lifecycle:

    * Constructed as a child of the parent frame item.
    * Listens to its own hover events (forwarded by the parent or sent
      directly by the scene). When the cursor enters a block region,
      :attr:`hovered_block` updates and the handle is drawn at the left
      margin of that region.
    * Left-button drag from the handle starts a "ghost" reorder
      preview; release dispatches a :class:`MoveBlockCommand`.
    * Right-button click on the handle pops a :class:`QMenu` with
      Duplicate / Delete / Convert To….
    """

    def __init__(
        self,
        parent: TextFrameItemStub,
        command_sink: CommandSink,
    ) -> None:
        super().__init__(parent)
        self._parent_frame: TextFrameItemStub = parent
        self._sink: CommandSink = command_sink
        self._hovered: BlockHandleHit | None = None
        self._drag_origin: BlockHandleHit | None = None
        self._drag_pos: QPointF | None = None  # in local (parent) coords
        # Make sure we sit *above* the frame's text (z = 1) and receive
        # hover/click events even when the frame itself does.
        self.setZValue(10.0)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(
            Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton
        )

    # ------------------------------------------------------------------
    # Public test seams.
    # ------------------------------------------------------------------

    @property
    def hovered_block(self) -> BlockHandleHit | None:
        return self._hovered

    def is_handle_visible(self) -> bool:
        """The handle paints only while a block is hovered."""
        return self._hovered is not None

    def hit_test(self, local_pos: QPointF) -> BlockHandleHit | None:
        """Find the block region containing ``local_pos`` (parent coords)."""
        for index, (block_id, region) in enumerate(self._parent_frame.block_regions()):
            if region.contains(local_pos):
                return BlockHandleHit(block_id=block_id, block_index=index, region=region)
        return None

    def handle_rect_for(self, hit: BlockHandleHit) -> QRectF:
        """Where the handle is drawn for a hovered block region.

        Centred vertically on the block region, parked just outside the
        left edge of the frame's content area.
        """
        cy = hit.region.top() + (hit.region.height() - HANDLE_HEIGHT) / 2
        return QRectF(HANDLE_LEFT_MARGIN, cy, HANDLE_WIDTH, HANDLE_HEIGHT)

    def simulate_hover(self, local_pos: QPointF) -> None:
        """Test helper: pretend the cursor moved to ``local_pos``.

        ``QGraphicsScene`` hover dispatch is awkward to trigger in
        offscreen tests; this gives the same observable effect without
        spinning an event loop.
        """
        self._set_hover(self.hit_test(local_pos))

    def simulate_drag_release(
        self, source_local_pos: QPointF, target_local_pos: QPointF
    ) -> MoveBlockCommand | None:
        """Test helper: pretend we dragged from one block region to another.

        Returns the dispatched :class:`MoveBlockCommand`, or ``None`` if
        the source/target hit-tests didn't both resolve.
        """
        source = self.hit_test(source_local_pos)
        target = self.hit_test(target_local_pos)
        if source is None or target is None:
            return None
        return self._dispatch_move(source, target)

    # ------------------------------------------------------------------
    # QGraphicsItem API.
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        return self._parent_frame.boundingRect()

    # We don't override ``shape()`` — the default (boundingRect-derived)
    # is fine, and overriding it just to call ``super()`` adds nothing.

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        if self._hovered is None:
            return
        rect = self.handle_rect_for(self._hovered)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 24)))
        painter.drawRoundedRect(rect, 3, 3)
        painter.setPen(QPen(QColor(80, 80, 80)))
        font = QFont(painter.font())
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), HANDLE_TEXT)
        # Ghost-preview rectangle while dragging.
        if self._drag_origin is not None and self._drag_pos is not None:
            ghost = QRectF(self._drag_origin.region)
            ghost.moveTop(self._drag_pos.y() - ghost.height() / 2)
            painter.setPen(QPen(QColor(60, 130, 220), 1, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(QColor(60, 130, 220, 24)))
            painter.drawRect(ghost)
        painter.restore()

    # ------------------------------------------------------------------
    # Hover dispatch.
    # ------------------------------------------------------------------

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self._set_hover(self.hit_test(event.pos()))

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self._set_hover(self.hit_test(event.pos()))

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self._set_hover(None)

    def _set_hover(self, hit: BlockHandleHit | None) -> None:
        if hit == self._hovered:
            return
        self._hovered = hit
        self.update()

    # ------------------------------------------------------------------
    # Mouse / drag.
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        hit = self.hit_test(event.pos())
        if hit is None:
            event.ignore()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(hit, event.screenPos())
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = hit
            self._drag_pos = event.pos()
            event.accept()
            return
        event.ignore()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._drag_origin is None:
            event.ignore()
            return
        self._drag_pos = event.pos()
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._drag_origin is None:
            event.ignore()
            return
        target = self.hit_test(event.pos())
        origin = self._drag_origin
        self._drag_origin = None
        self._drag_pos = None
        self.update()
        if target is not None and target.block_index != origin.block_index:
            self._dispatch_move(origin, target)
        event.accept()

    # ------------------------------------------------------------------
    # Command dispatch.
    # ------------------------------------------------------------------

    def _dispatch_move(
        self, origin: BlockHandleHit, target: BlockHandleHit
    ) -> MoveBlockCommand:
        # We pass the raw source / target indices straight through — the
        # apply-side of :class:`MoveBlockCommand` (in unit-9) is responsible
        # for any "post-removal" index normalisation. Keeping this layer
        # ignorant of that detail means the overlay stays correct even if
        # the command's semantics are tightened later.
        cmd = MoveBlockCommand(
            story_id=self._parent_frame.story.id,
            from_index=origin.block_index,
            to_index=target.block_index,
        )
        self._sink(cmd)
        return cmd

    # ------------------------------------------------------------------
    # Context menu.
    # ------------------------------------------------------------------

    def build_context_menu(self, hit: BlockHandleHit) -> QMenu:
        """Assemble (but don't show) the right-click menu.

        ``QMenu.addMenu(str)`` returns a child menu owned by the parent
        ``QMenu`` *on the C++ side*, but in PySide6 the Python wrapper
        can be garbage-collected before the parent. We construct the
        sub-menu explicitly with the parent so its Python lifetime is
        anchored to the returned menu.

        ``hit`` is currently unused but kept in the signature so future
        per-block menu items (e.g. greying out "Convert to current
        kind") can branch on it without churning callers.
        """
        menu = QMenu()
        duplicate = menu.addAction("Duplicate")
        delete = menu.addAction("Delete")
        convert_menu = QMenu("Convert To", menu)
        menu.addMenu(convert_menu)
        for label, kind, attrs in CONVERT_TO_OPTIONS:
            action: QAction = convert_menu.addAction(label)
            action.setData((kind, dict(attrs)))
        duplicate.setData(("__duplicate__", None))
        delete.setData(("__delete__", None))
        return menu

    def dispatch_menu_action(self, action: QAction, hit: BlockHandleHit) -> CommandStub | None:
        """Convert a triggered menu action to a command and emit it."""
        data = action.data()
        if not isinstance(data, tuple) or len(data) != 2:
            return None
        tag, payload = data
        story_id = self._parent_frame.story.id
        cmd: CommandStub
        if tag == "__duplicate__":
            cmd = DuplicateBlockCommand(story_id=story_id, block_id=hit.block_id)
        elif tag == "__delete__":
            cmd = DeleteBlockCommand(story_id=story_id, block_id=hit.block_id)
        else:
            cmd = TransformBlockCommand(
                story_id=story_id,
                block_id=hit.block_id,
                target_kind=tag,
                target_attrs=payload if isinstance(payload, dict) else {},
            )
        self._sink(cmd)
        return cmd

    def _show_context_menu(self, hit: BlockHandleHit, screen_pos: QPoint) -> None:
        menu = self.build_context_menu(hit)
        action = menu.exec(screen_pos)
        if action is not None:
            self.dispatch_menu_action(action, hit)
