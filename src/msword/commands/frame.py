"""Frame-level commands: add, remove, move, resize."""

from __future__ import annotations

from msword.commands.base import Command, Document, Frame


class AddFrameCommand(Command):
    def __init__(self, doc: Document, page_id: str, frame: Frame) -> None:
        super().__init__(doc, "Add Frame")
        self._page_id = page_id
        self._frame = frame

    def _do(self, doc: Document) -> None:
        doc.add_frame(self._page_id, self._frame)

    def _undo(self, doc: Document) -> None:
        doc.remove_frame(self._page_id, self._frame.id)


class RemoveFrameCommand(Command):
    def __init__(self, doc: Document, page_id: str, frame_id: str) -> None:
        super().__init__(doc, "Remove Frame")
        self._page_id = page_id
        self._frame_id = frame_id
        self._removed: Frame | None = None

    def _do(self, doc: Document) -> None:
        self._removed = doc.remove_frame(self._page_id, self._frame_id)

    def _undo(self, doc: Document) -> None:
        assert self._removed is not None, "RemoveFrameCommand undone before redo"
        doc.add_frame(self._page_id, self._removed)


class MoveFrameCommand(Command):
    """Translate a frame by `(dx, dy)`; the inverse stores the live
    pre-move position so undo is exact even after multiple translations
    were merged or rounded upstream."""

    def __init__(self, doc: Document, page_id: str, frame_id: str, dx: float, dy: float) -> None:
        super().__init__(doc, "Move Frame")
        self._page_id = page_id
        self._frame_id = frame_id
        self._dx = dx
        self._dy = dy
        self._old_x: float | None = None
        self._old_y: float | None = None

    def _do(self, doc: Document) -> None:
        frame = doc.get_frame(self._page_id, self._frame_id)
        self._old_x = frame.x
        self._old_y = frame.y
        frame.x = frame.x + self._dx
        frame.y = frame.y + self._dy

    def _undo(self, doc: Document) -> None:
        assert self._old_x is not None and self._old_y is not None
        frame = doc.get_frame(self._page_id, self._frame_id)
        frame.x = self._old_x
        frame.y = self._old_y


class ResizeFrameCommand(Command):
    def __init__(
        self, doc: Document, page_id: str, frame_id: str, new_w: float, new_h: float
    ) -> None:
        super().__init__(doc, "Resize Frame")
        self._page_id = page_id
        self._frame_id = frame_id
        self._new_w = new_w
        self._new_h = new_h
        self._old_w: float | None = None
        self._old_h: float | None = None

    def _do(self, doc: Document) -> None:
        frame = doc.get_frame(self._page_id, self._frame_id)
        self._old_w = frame.w
        self._old_h = frame.h
        frame.w = self._new_w
        frame.h = self._new_h

    def _undo(self, doc: Document) -> None:
        assert self._old_w is not None and self._old_h is not None
        frame = doc.get_frame(self._page_id, self._frame_id)
        frame.w = self._old_w
        frame.h = self._old_h
