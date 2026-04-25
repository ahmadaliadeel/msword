"""Base `Command` class and the `Document` protocol it talks to.

Until units 2-7 land their concrete `Document` / `Page` / `Frame` /
`Story` / `Block` types, this unit speaks to them through a small
`typing.Protocol` surface. The real types from `msword.model` will be
structural-subtype matches at runtime — no adapter needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from PySide6.QtGui import QUndoCommand

if TYPE_CHECKING:
    from PySide6.QtCore import SignalInstance

    from msword.commands.stack import UndoStack


@runtime_checkable
class Document(Protocol):
    """Structural protocol the command package needs from a `Document`.

    The real `Document` (unit 2) is a `QObject` with a `changed` signal
    and an embedded `UndoStack`; both are referenced here as duck-typed
    attributes so this package has no hard dependency on the model unit.
    """

    # Qt signal that views subscribe to; emitted exactly once per do/undo.
    changed: SignalInstance
    # The single per-document undo stack (commands push themselves here).
    undo_stack: UndoStack

    def add_page(self, page: Page, index: int | None = ...) -> int: ...
    def remove_page(self, index: int) -> Page: ...
    def move_page(self, from_index: int, to_index: int) -> None: ...

    def add_frame(self, page_id: str, frame: Frame) -> None: ...
    def remove_frame(self, page_id: str, frame_id: str) -> Frame: ...
    def get_frame(self, page_id: str, frame_id: str) -> Frame: ...


@runtime_checkable
class Page(Protocol):
    """Stub of the `Page` model from unit 2."""

    id: str


@runtime_checkable
class Frame(Protocol):
    """Stub of the `Frame` model from unit 3."""

    id: str
    x: float
    y: float
    w: float
    h: float


class Command(QUndoCommand):
    """Base class for every document-mutating command.

    Subclasses implement `_do` and `_undo`, which receive the bound
    `Document`. The base class wires `redo()` and `undo()` to those hooks
    and emits `Document.changed` exactly once after each. The user-visible
    label is set via the `text` constructor argument (read back through
    Qt's `QUndoCommand.text()`).
    """

    def __init__(self, doc: Document, text: str = "") -> None:
        super().__init__(text)
        self._doc = doc

    def _do(self, doc: Document) -> None:
        raise NotImplementedError

    def _undo(self, doc: Document) -> None:
        raise NotImplementedError

    def redo(self) -> None:
        self._do(self._doc)
        self._doc.changed.emit()

    def undo(self) -> None:
        self._undo(self._doc)
        self._doc.changed.emit()
