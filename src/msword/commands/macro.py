"""`MacroCommand` — composite command treated as a single undo step.

Use this when `UndoStack.begin_macro` / `end_macro` is the wrong shape —
e.g. when the caller wants to construct a single `Command` it can hand off
elsewhere, or when the sub-commands aren't known until inside another
command's `_do`.

The macro itself is the unit responsible for emitting `Document.changed`,
so children's `_do` / `_undo` are invoked directly (bypassing their own
`redo` / `undo`) — calling `child.redo()` here would double-emit and
defeat the "exactly once per do/undo" invariant.
"""

from __future__ import annotations

from msword.commands.base import Command, Document


class MacroCommand(Command):
    def __init__(self, doc: Document, children: list[Command], text: str = "") -> None:
        super().__init__(doc, text)
        self._children = list(children)

    def _do(self, doc: Document) -> None:
        for child in self._children:
            child._do(doc)

    def _undo(self, doc: Document) -> None:
        for child in reversed(self._children):
            child._undo(doc)
