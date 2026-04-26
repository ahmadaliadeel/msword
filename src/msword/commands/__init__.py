"""Command pattern stubs.

Full implementation lands in `commands-and-undo` (unit 9). This stub
exposes the small subset (`Command`, `MacroCommand`, `ReplaceTextInRunCommand`)
used by `feat.find_engine` so siblings can import and exercise it without
the QUndoStack integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from msword.model.run import Run


@dataclass
class Command:
    """Base command. Subclasses implement `redo()` / `undo()` (no-op here)."""

    text: str = "command"

    def redo(self) -> None:  # pragma: no cover - stub
        raise NotImplementedError

    def undo(self) -> None:  # pragma: no cover - stub
        raise NotImplementedError


@dataclass
class MacroCommand(Command):
    """Composite command — applies its children in order, undoes in reverse."""

    children: list[Command] = field(default_factory=list)
    text: str = "macro"

    def redo(self) -> None:
        for child in self.children:
            child.redo()

    def undo(self) -> None:
        for child in reversed(self.children):
            child.undo()


@dataclass
class ReplaceTextInRunCommand(Command):
    """Replace a slice of `run.text[char_start:char_end]` with `replacement`.

    Pure-data command; the real undo-stack wiring is the responsibility of
    unit 9. We track the original slice so `undo()` is exact.
    """

    run: Run | None = None
    char_start: int = 0
    char_end: int = 0
    replacement: str = ""
    _original: str = ""
    text: str = "Replace text"

    def redo(self) -> None:
        if self.run is None:
            raise ValueError("ReplaceTextInRunCommand requires a run")
        self._original = self.run.text[self.char_start : self.char_end]
        self.run.text = (
            self.run.text[: self.char_start]
            + self.replacement
            + self.run.text[self.char_end :]
        )

    def undo(self) -> None:
        if self.run is None:
            raise ValueError("ReplaceTextInRunCommand requires a run")
        new_end = self.char_start + len(self.replacement)
        self.run.text = (
            self.run.text[: self.char_start]
            + self._original
            + self.run.text[new_end:]
        )


__all__ = ["Command", "MacroCommand", "ReplaceTextInRunCommand"]
