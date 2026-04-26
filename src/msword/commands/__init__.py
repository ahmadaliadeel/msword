"""Command pattern stubs for unit-25 (style sheets palette).

The full command framework lands in unit-9 (`commands-and-undo`). Here
we only define the minimal `Command` base + the style-related commands
the style sheets palette dispatches. Each command implements `redo()` /
`undo()` (the QUndoCommand contract) so the unit-9 wiring is a drop-in.

Strict invariant: views and dialogs *never* mutate the model directly.
They construct one of these commands and push it onto the document's
undo stack (or, in this stub, call `redo()` once).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from msword.model.document import Document
from msword.model.style import (
    CharacterStyle,
    ParagraphStyle,
    StyleCycleError,
    StyleResolver,
)


class Command:
    """Minimal Command base. Replaced by the QUndoCommand-backed base in
    unit-9; we keep `redo()` / `undo()` so the upgrade is mechanical."""

    def redo(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def undo(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError


# --- paragraph styles ----------------------------------------------------


@dataclass
class AddParagraphStyleCommand(Command):
    document: Document
    style: ParagraphStyle

    def redo(self) -> None:
        if self.style.name in self.document.paragraph_styles:
            raise ValueError(f"paragraph style {self.style.name!r} already exists")
        self.document.paragraph_styles[self.style.name] = self.style

    def undo(self) -> None:
        self.document.paragraph_styles.pop(self.style.name, None)


@dataclass
class DuplicateParagraphStyleCommand(Command):
    document: Document
    source_name: str
    new_name: str

    def redo(self) -> None:
        if self.new_name in self.document.paragraph_styles:
            raise ValueError(f"paragraph style {self.new_name!r} already exists")
        src = self.document.paragraph_styles[self.source_name]
        self.document.paragraph_styles[self.new_name] = src.clone(name=self.new_name)

    def undo(self) -> None:
        self.document.paragraph_styles.pop(self.new_name, None)


@dataclass
class DeleteParagraphStyleCommand(Command):
    document: Document
    name: str
    _saved: ParagraphStyle | None = field(default=None, init=False, repr=False)

    def redo(self) -> None:
        self._saved = self.document.paragraph_styles.pop(self.name)

    def undo(self) -> None:
        if self._saved is not None:
            self.document.paragraph_styles[self.name] = self._saved


@dataclass
class EditParagraphStyleCommand(Command):
    document: Document
    name: str
    new_style: ParagraphStyle
    _previous: ParagraphStyle | None = field(default=None, init=False, repr=False)

    def redo(self) -> None:
        # cycle check on based_on
        if StyleResolver.detect_cycle(
            self.document.paragraph_styles, self.new_style.name, self.new_style.based_on
        ):
            raise StyleCycleError(
                f"setting {self.new_style.name!r}.based_on="
                f"{self.new_style.based_on!r} would form a cycle"
            )
        self._previous = self.document.paragraph_styles.get(self.name)
        # Allow rename via name change
        if self.name != self.new_style.name:
            self.document.paragraph_styles.pop(self.name, None)
        self.document.paragraph_styles[self.new_style.name] = self.new_style

    def undo(self) -> None:
        self.document.paragraph_styles.pop(self.new_style.name, None)
        if self._previous is not None:
            self.document.paragraph_styles[self.name] = self._previous


@dataclass
class ApplyParagraphStyleCommand(Command):
    """Apply a paragraph style to the current selection.

    Stub: mutates `document.selection.paragraph_style`. Real
    implementation will tag the targeted paragraph blocks.
    """

    document: Document
    name: str
    _previous: str | None = field(default=None, init=False, repr=False)

    def redo(self) -> None:
        if self.name not in self.document.paragraph_styles:
            raise KeyError(self.name)
        self._previous = self.document.selection.paragraph_style
        self.document.selection.paragraph_style = self.name

    def undo(self) -> None:
        self.document.selection.paragraph_style = self._previous


# --- character styles ----------------------------------------------------


@dataclass
class AddCharacterStyleCommand(Command):
    document: Document
    style: CharacterStyle

    def redo(self) -> None:
        if self.style.name in self.document.character_styles:
            raise ValueError(f"character style {self.style.name!r} already exists")
        self.document.character_styles[self.style.name] = self.style

    def undo(self) -> None:
        self.document.character_styles.pop(self.style.name, None)


@dataclass
class DuplicateCharacterStyleCommand(Command):
    document: Document
    source_name: str
    new_name: str

    def redo(self) -> None:
        if self.new_name in self.document.character_styles:
            raise ValueError(f"character style {self.new_name!r} already exists")
        src = self.document.character_styles[self.source_name]
        self.document.character_styles[self.new_name] = src.clone(name=self.new_name)

    def undo(self) -> None:
        self.document.character_styles.pop(self.new_name, None)


@dataclass
class DeleteCharacterStyleCommand(Command):
    document: Document
    name: str
    _saved: CharacterStyle | None = field(default=None, init=False, repr=False)

    def redo(self) -> None:
        self._saved = self.document.character_styles.pop(self.name)

    def undo(self) -> None:
        if self._saved is not None:
            self.document.character_styles[self.name] = self._saved


@dataclass
class EditCharacterStyleCommand(Command):
    document: Document
    name: str
    new_style: CharacterStyle
    _previous: CharacterStyle | None = field(default=None, init=False, repr=False)

    def redo(self) -> None:
        if StyleResolver.detect_cycle(
            self.document.character_styles, self.new_style.name, self.new_style.based_on
        ):
            raise StyleCycleError(
                f"setting {self.new_style.name!r}.based_on="
                f"{self.new_style.based_on!r} would form a cycle"
            )
        self._previous = self.document.character_styles.get(self.name)
        if self.name != self.new_style.name:
            self.document.character_styles.pop(self.name, None)
        self.document.character_styles[self.new_style.name] = self.new_style

    def undo(self) -> None:
        self.document.character_styles.pop(self.new_style.name, None)
        if self._previous is not None:
            self.document.character_styles[self.name] = self._previous


@dataclass
class ApplyCharacterStyleCommand(Command):
    document: Document
    name: str
    _previous: str | None = field(default=None, init=False, repr=False)

    def redo(self) -> None:
        if self.name not in self.document.character_styles:
            raise KeyError(self.name)
        self._previous = self.document.selection.character_style
        self.document.selection.character_style = self.name

    def undo(self) -> None:
        self.document.selection.character_style = self._previous


__all__ = [
    "AddCharacterStyleCommand",
    "AddParagraphStyleCommand",
    "ApplyCharacterStyleCommand",
    "ApplyParagraphStyleCommand",
    "Command",
    "DeleteCharacterStyleCommand",
    "DeleteParagraphStyleCommand",
    "DuplicateCharacterStyleCommand",
    "DuplicateParagraphStyleCommand",
    "EditCharacterStyleCommand",
    "EditParagraphStyleCommand",
]
