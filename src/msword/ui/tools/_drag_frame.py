"""Shared "drag a rectangle to create a frame" tool implementation.

Text, picture, rectangle, oval, and line tools all follow the same pattern:
press → record start, drag → preview, release → push an ``AddFrameCommand``
with the normalized rect. Centralising it here keeps the per-tool subclasses
to a single ``kind`` constant plus optional behaviour overrides (e.g. picture
opens a file dialog on Shift+drag, line stores a sub-kind).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtWidgets import QGraphicsView

from msword.ui.tools._stubs import AddFrameCommand
from msword.ui.tools.base import Tool

if TYPE_CHECKING:
    from PySide6.QtGui import QMouseEvent


class DragRectFrameTool(Tool):
    """Base for tools that create a new frame from a drag-rectangle."""

    cursor = Qt.CursorShape.CrossCursor
    kind: str = ""
    #: Static kwargs merged into every ``AddFrameCommand`` this tool creates
    #: (e.g. ``{"shape": "rect"}`` for the rectangle tool).
    extra_kwargs: ClassVar[dict[str, Any]] = {}

    def __init__(self) -> None:
        super().__init__()
        self._start: QPointF | None = None
        self._end: QPointF | None = None

    def activate(self, canvas):  # type: ignore[no-untyped-def]
        super().activate(canvas)
        canvas.viewport_drag_mode(QGraphicsView.DragMode.NoDrag)

    def on_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        self._start = QPointF(scene_pos)
        self._end = QPointF(scene_pos)

    def on_mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        if self._start is None:
            return
        self._end = QPointF(scene_pos)

    def on_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        if self._start is None:
            return
        rect = QRectF(self._start, scene_pos).normalized()
        self._start = None
        self._end = None
        if rect.width() <= 0 or rect.height() <= 0:
            return
        self._push_add_frame(rect, **self._command_extra(event))

    def _command_extra(self, event: QMouseEvent) -> dict[str, Any]:
        """Hook for subclasses to attach per-event kwargs to ``AddFrameCommand``.

        The default merges ``extra_kwargs`` (static, class-level) with any
        subclass-specific runtime extras.
        """
        del event
        return dict(self.extra_kwargs)

    def _push_add_frame(self, rect: QRectF, **extra: Any) -> None:
        canvas = self.canvas
        if canvas is None:
            return
        document = getattr(canvas, "document", None)
        page = getattr(canvas, "current_page", None)
        if document is None or page is None:
            return
        command = AddFrameCommand(document, page, rect, self.kind, **extra)
        canvas.push_command(command)
