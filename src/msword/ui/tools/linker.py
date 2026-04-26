"""Frame-linker tool: stitch text frames into a story chain.

Per spec §3 / §9 / §12 (unit 21): the Linker is *stateful*. The first click on
a TextFrame stores it as the source and draws a faint preview line from the
source frame to the cursor. The second click determines the action:

* If the target is a TextFrame whose story is empty (or absent) — push a
  ``LinkFrameCommand`` (target's ``story_ref`` becomes source's, with
  ``story_index = source.story_index + 1``).
* If the target's story is non-empty — pop a ``QMessageBox`` confirming the
  destructive merge; on Yes push a ``MergeStoriesCommand`` (target's blocks
  are appended onto source's story), on No abort.

Either way, the tool then resets state and asks the canvas to recompose so
the new chain is reflected in layout immediately.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QLineF, QPointF, Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsView, QMessageBox

from msword.ui.tools._stubs import LinkFrameCommand, MergeStoriesCommand, Tool
from msword.ui.tools._text_frame_hit import hit_test_text_frame

if TYPE_CHECKING:
    from PySide6.QtGui import QMouseEvent


def _story_is_non_empty(story: Any) -> bool:
    """Return True if ``story`` exists and has at least one block."""
    if story is None:
        return False
    blocks = getattr(story, "blocks", None)
    if blocks is None:
        return False
    return len(blocks) > 0


class LinkerTool(Tool):  # type: ignore[misc]
    """Click source → click target → push link / merge command. Stateful."""

    name = "Linker"
    icon_name = "tool-linker"
    cursor = Qt.CursorShape.PointingHandCursor

    def __init__(self) -> None:
        super().__init__()
        self.from_frame: Any | None = None
        self._preview_line: QGraphicsLineItem | None = None
        self._preview_anchor: QPointF | None = None

    def activate(self, canvas: Any) -> None:
        super().activate(canvas)
        if hasattr(canvas, "viewport_drag_mode"):
            canvas.viewport_drag_mode(QGraphicsView.DragMode.NoDrag)

    def deactivate(self) -> None:
        self._reset()
        super().deactivate()

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def on_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        canvas = self.canvas
        if canvas is None:
            return
        page = getattr(canvas, "current_page", None)
        hit = hit_test_text_frame(page, scene_pos)
        if hit is None:
            # Click in empty space → cancel any pending link.
            self._reset()
            return
        if self.from_frame is None:
            # First click: remember the source and drop a preview line.
            self.from_frame = hit
            self._install_preview(scene_pos)
            return
        # Second click: target. Linking a frame to itself is a no-op.
        if hit is self.from_frame:
            self._reset()
            return
        self._complete_link(self.from_frame, hit)

    def on_mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        if self._preview_line is None or self._preview_anchor is None:
            return
        self._preview_line.setLine(QLineF(self._preview_anchor, scene_pos))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _complete_link(self, source: Any, target: Any) -> None:
        canvas = self.canvas
        if canvas is None:
            return
        document = getattr(canvas, "document", None)
        if _story_is_non_empty(getattr(target, "story_ref", None)):
            if not self._confirm_merge():
                self._reset()
                return
            command: Any = MergeStoriesCommand(document, source, target)
        else:
            command = LinkFrameCommand(document, source, target)
        canvas.push_command(command)
        if hasattr(canvas, "recompose"):
            canvas.recompose()
        self._reset()

    def _confirm_merge(self) -> bool:
        """Show the destructive-merge confirm dialog. Overridable in tests."""
        result = QMessageBox.question(
            None,
            "Merge stories?",
            (
                "The target frame already contains text. Linking will append its "
                "content onto the source story. Continue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _install_preview(self, scene_pos: QPointF) -> None:
        canvas = self.canvas
        if canvas is None or self.from_frame is None:
            return
        anchor = QPointF(
            self.from_frame.x + self.from_frame.w / 2.0,
            self.from_frame.y + self.from_frame.h / 2.0,
        )
        line_item = QGraphicsLineItem(QLineF(anchor, scene_pos))
        pen = QPen(QColor(0, 120, 215, 110))
        pen.setWidthF(1.0)
        pen.setStyle(Qt.PenStyle.DashLine)
        line_item.setPen(pen)
        line_item.setZValue(10_000)
        self._preview_anchor = anchor
        self._preview_line = line_item
        if hasattr(canvas, "add_overlay"):
            canvas.add_overlay(line_item)

    def _reset(self) -> None:
        self.from_frame = None
        canvas = self.canvas
        if (
            self._preview_line is not None
            and canvas is not None
            and hasattr(canvas, "remove_overlay")
        ):
            canvas.remove_overlay(self._preview_line)
        self._preview_line = None
        self._preview_anchor = None


__all__ = ["LinkerTool"]
