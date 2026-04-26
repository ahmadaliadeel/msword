"""Page-level commands: add, remove, move."""

from __future__ import annotations

from msword.commands.base import Command, Document, Page


class AddPageCommand(Command):
    """Insert `page` at `index` (or append if `index is None`)."""

    def __init__(self, doc: Document, page: Page, index: int | None = None) -> None:
        super().__init__(doc, "Add Page")
        self._page = page
        self._requested_index = index
        self._inserted_index: int = -1

    def _do(self, doc: Document) -> None:
        self._inserted_index = doc.add_page(self._page, self._requested_index)

    def _undo(self, doc: Document) -> None:
        doc.remove_page(self._inserted_index)


class RemovePageCommand(Command):
    """Remove the page at `page_index`; restore on undo."""

    def __init__(self, doc: Document, page_index: int) -> None:
        super().__init__(doc, "Remove Page")
        self._index = page_index
        self._removed: Page | None = None

    def _do(self, doc: Document) -> None:
        self._removed = doc.remove_page(self._index)

    def _undo(self, doc: Document) -> None:
        # The removed page is captured in `_do`; if `_undo` runs first
        # the stack is corrupt — bail loudly rather than silently no-op.
        assert self._removed is not None, "RemovePageCommand undone before redo"
        doc.add_page(self._removed, self._index)


class MovePageCommand(Command):
    """Move the page at `from_index` to `to_index`."""

    def __init__(self, doc: Document, from_index: int, to_index: int) -> None:
        super().__init__(doc, "Move Page")
        self._from = from_index
        self._to = to_index

    def _do(self, doc: Document) -> None:
        doc.move_page(self._from, self._to)

    def _undo(self, doc: Document) -> None:
        doc.move_page(self._to, self._from)
