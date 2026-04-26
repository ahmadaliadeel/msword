"""Local stubs for the model & command surfaces this unit reads.

These are *minimal* in-process stand-ins so unit #23 (Pages + Outline palettes)
can be built and tested in isolation. The real implementations land in their
own units (#2 model-document-core, #5 model-blocks-schema, #9 commands-and-undo).

When the real types land, this file is deleted and the palettes import from
``msword.model`` / ``msword.commands`` instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from PySide6.QtCore import QObject, Signal


@dataclass
class MasterPage:
    """Stub master page (real impl: model/master_page.py)."""

    id: str
    name: str = "A-Master"


@dataclass
class Page:
    """Stub page (real impl: model/page.py)."""

    id: str
    master_id: str | None = None


@dataclass
class HeadingBlock:
    """Stub heading block (real impl: model/blocks/heading.py)."""

    id: str
    level: int
    text: str


@dataclass
class ParagraphBlock:
    """Stub paragraph block — included so outline tests can place non-headings."""

    id: str
    text: str = ""


Block = HeadingBlock | ParagraphBlock


class Document(QObject):
    """Stub Document with the change-notification surface this unit reads.

    Signals exposed:
      * ``page_changed``  — fired after any page list mutation.
      * ``changed``       — fired after any document mutation (broader bucket).
      * ``story_changed`` — fired when block tree changes.

    The real Document (unit #2) will provide a richer API; this stub keeps the
    seam tiny so views written against it don't need to change.
    """

    page_changed = Signal()
    changed = Signal()
    story_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.pages: list[Page] = []
        self.master_pages: list[MasterPage] = [MasterPage(id="m-A", name="A-Master")]
        self.blocks: list[Block] = []

    # --- page mutators (used by the palette via commands) ---
    def add_page(self, page: Page, index: int | None = None) -> None:
        if index is None:
            self.pages.append(page)
        else:
            self.pages.insert(index, page)
        self.page_changed.emit()
        self.changed.emit()

    def remove_page(self, index: int) -> None:
        if 0 <= index < len(self.pages):
            del self.pages[index]
            self.page_changed.emit()
            self.changed.emit()

    def move_page(self, src: int, dst: int) -> None:
        if not (0 <= src < len(self.pages)):
            return
        page = self.pages.pop(src)
        dst = max(0, min(dst, len(self.pages)))
        self.pages.insert(dst, page)
        self.page_changed.emit()
        self.changed.emit()

    # --- block mutators ---
    def add_block(self, block: Block) -> None:
        self.blocks.append(block)
        self.story_changed.emit()
        self.changed.emit()


# ---- Commands (real impl: commands/) -------------------------------------


@dataclass
class _CommandRecord:
    name: str
    args: tuple[object, ...] = field(default_factory=tuple)


class CommandBus(QObject):
    """Tiny stub bus so palettes can dispatch commands and tests can observe.

    The real `UndoStack` (unit #9) replaces this with `QUndoStack` + `QUndoCommand`.
    """

    dispatched = Signal(object)  # _CommandRecord

    def __init__(self) -> None:
        super().__init__()
        self.history: list[_CommandRecord] = []

    def dispatch(self, record: _CommandRecord) -> None:
        self.history.append(record)
        self.dispatched.emit(record)


class Command(Protocol):
    name: str

    def apply(self, doc: Document) -> None: ...


@dataclass
class NewPageCommand:
    name: str = "NewPage"
    page_id: str = ""
    index: int | None = None
    master_id: str | None = None

    def apply(self, doc: Document) -> None:
        doc.add_page(Page(id=self.page_id, master_id=self.master_id), index=self.index)


@dataclass
class DeletePageCommand:
    index: int = 0
    name: str = "DeletePage"

    def apply(self, doc: Document) -> None:
        doc.remove_page(self.index)


@dataclass
class DuplicatePageCommand:
    index: int = 0
    new_id: str = ""
    name: str = "DuplicatePage"

    def apply(self, doc: Document) -> None:
        if 0 <= self.index < len(doc.pages):
            src = doc.pages[self.index]
            doc.add_page(Page(id=self.new_id, master_id=src.master_id), index=self.index + 1)


@dataclass
class MovePageCommand:
    src: int = 0
    dst: int = 0
    name: str = "MovePage"

    def apply(self, doc: Document) -> None:
        doc.move_page(self.src, self.dst)


@dataclass
class AssignMasterCommand:
    page_index: int = 0
    master_id: str = ""
    name: str = "AssignMaster"

    def apply(self, doc: Document) -> None:
        if 0 <= self.page_index < len(doc.pages):
            doc.pages[self.page_index].master_id = self.master_id
            doc.page_changed.emit()
            doc.changed.emit()


__all__ = [
    "AssignMasterCommand",
    "Block",
    "Command",
    "CommandBus",
    "DeletePageCommand",
    "Document",
    "DuplicatePageCommand",
    "HeadingBlock",
    "MasterPage",
    "MovePageCommand",
    "NewPageCommand",
    "Page",
    "ParagraphBlock",
    "_CommandRecord",
]
