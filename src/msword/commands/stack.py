"""`UndoStack` — thin `QUndoStack` wrapper exposed to views and tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoStack

if TYPE_CHECKING:
    from msword.commands.base import Command


class UndoStack(QObject):
    """Per-document undo stack.

    Wraps `QUndoStack` so the rest of the codebase can stay decoupled
    from Qt's exact API surface and so we can re-emit the two signals
    we care about (`index_changed` and `clean_changed`) with our own
    typed names. Views subscribe; commands push.
    """

    index_changed = Signal(int)
    clean_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._stack = QUndoStack(self)
        # Disconnect on teardown: when `self` is destroyed Qt may still
        # fire the inner `QUndoStack`'s teardown signals, which would
        # otherwise re-enter `self.index_changed.emit` after the C++
        # half of `self` is gone (RuntimeError: Signal source has been
        # deleted).
        self._stack.indexChanged.connect(self._on_index_changed)
        self._stack.cleanChanged.connect(self._on_clean_changed)
        self.destroyed.connect(self._disconnect_inner)

    def _on_index_changed(self, idx: int) -> None:
        self.index_changed.emit(idx)

    def _on_clean_changed(self, clean: bool) -> None:
        self.clean_changed.emit(clean)

    def _disconnect_inner(self) -> None:
        try:
            self._stack.indexChanged.disconnect(self._on_index_changed)
            self._stack.cleanChanged.disconnect(self._on_clean_changed)
        except (RuntimeError, TypeError):
            pass

    # --- mutation -----------------------------------------------------

    def push(self, cmd: Command) -> None:
        self._stack.push(cmd)

    def undo(self) -> None:
        self._stack.undo()

    def redo(self) -> None:
        self._stack.redo()

    def clear(self) -> None:
        self._stack.clear()

    # --- macros -------------------------------------------------------

    def begin_macro(self, text: str) -> None:
        self._stack.beginMacro(text)

    def end_macro(self) -> None:
        self._stack.endMacro()

    # --- query --------------------------------------------------------

    def can_undo(self) -> bool:
        return bool(self._stack.canUndo())

    def can_redo(self) -> bool:
        return bool(self._stack.canRedo())

    def index(self) -> int:
        return int(self._stack.index())

    def count(self) -> int:
        return int(self._stack.count())

    def is_clean(self) -> bool:
        return bool(self._stack.isClean())

    def set_clean(self) -> None:
        self._stack.setClean()
