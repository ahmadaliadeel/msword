"""Paragraph + character style commands (unit-25).

Each command mutates `doc.paragraph_styles` / `doc.character_styles`
(both `list[ParagraphStyle | CharacterStyle]`) through the QUndoStack
contract: `_do` performs the mutation, `_undo` reverses it.

Apply commands record the applied style name on `doc.selection` so views
can react to the change. The actual run/block mutation is performed by
the text-editing units; the palette only needs to know that a name was
applied.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, ClassVar

from msword.commands.base import Command, Document
from msword.model.style import (
    CharacterStyle,
    ParagraphStyle,
    StyleCycleError,
    StyleResolver,
)


def _styles(doc: Document, attr: str) -> list[Any]:
    return getattr(doc, attr)  # type: ignore[no-any-return]


def _find_index(styles: list[Any], name: str) -> int:
    for i, s in enumerate(styles):
        if s.name == name:
            return i
    raise KeyError(name)


# ---------------------------------------------------------------------------
# Add / Duplicate / Delete / Edit are structurally identical for paragraph
# and character; only the document attribute and undo label differ. Shared
# bases keep the variation surface to a single class attribute.
# ---------------------------------------------------------------------------


class _AddStyleCommand(Command):
    _attr: ClassVar[str]

    def __init__(self, doc: Document, style: Any, label: str) -> None:
        super().__init__(doc, label)
        self._style = style

    @property
    def name(self) -> str:
        return str(self._style.name)

    def _do(self, doc: Document) -> None:
        styles = _styles(doc, self._attr)
        if any(s.name == self._style.name for s in styles):
            raise ValueError(f"style {self._style.name!r} already exists")
        styles.append(self._style)

    def _undo(self, doc: Document) -> None:
        styles = _styles(doc, self._attr)
        del styles[_find_index(styles, self._style.name)]


class AddParagraphStyleCommand(_AddStyleCommand):
    _attr = "paragraph_styles"

    def __init__(self, doc: Document, style: ParagraphStyle) -> None:
        super().__init__(doc, style, "Add Paragraph Style")


class AddCharacterStyleCommand(_AddStyleCommand):
    _attr = "character_styles"

    def __init__(self, doc: Document, style: CharacterStyle) -> None:
        super().__init__(doc, style, "Add Character Style")


class _DuplicateStyleCommand(Command):
    _attr: ClassVar[str]

    def __init__(
        self, doc: Document, source_name: str, new_name: str, label: str
    ) -> None:
        super().__init__(doc, label)
        self._source_name = source_name
        self._new_name = new_name

    def _do(self, doc: Document) -> None:
        styles = _styles(doc, self._attr)
        src = next((s for s in styles if s.name == self._source_name), None)
        if src is None:
            raise KeyError(self._source_name)
        if any(s.name == self._new_name for s in styles):
            raise ValueError(f"style {self._new_name!r} already exists")
        styles.append(replace(src, name=self._new_name))

    def _undo(self, doc: Document) -> None:
        styles = _styles(doc, self._attr)
        del styles[_find_index(styles, self._new_name)]


class DuplicateParagraphStyleCommand(_DuplicateStyleCommand):
    _attr = "paragraph_styles"

    def __init__(self, doc: Document, source_name: str, new_name: str) -> None:
        super().__init__(doc, source_name, new_name, "Duplicate Paragraph Style")


class DuplicateCharacterStyleCommand(_DuplicateStyleCommand):
    _attr = "character_styles"

    def __init__(self, doc: Document, source_name: str, new_name: str) -> None:
        super().__init__(doc, source_name, new_name, "Duplicate Character Style")


class _DeleteStyleCommand(Command):
    _attr: ClassVar[str]

    def __init__(self, doc: Document, name: str, label: str) -> None:
        super().__init__(doc, label)
        self._name = name
        self._removed: Any = None
        self._index: int = -1

    def _do(self, doc: Document) -> None:
        styles = _styles(doc, self._attr)
        self._index = _find_index(styles, self._name)
        self._removed = styles.pop(self._index)

    def _undo(self, doc: Document) -> None:
        assert self._removed is not None, "delete undone before redo"
        styles = _styles(doc, self._attr)
        styles.insert(self._index, self._removed)


class DeleteParagraphStyleCommand(_DeleteStyleCommand):
    _attr = "paragraph_styles"

    def __init__(self, doc: Document, name: str) -> None:
        super().__init__(doc, name, "Delete Paragraph Style")


class DeleteCharacterStyleCommand(_DeleteStyleCommand):
    _attr = "character_styles"

    def __init__(self, doc: Document, name: str) -> None:
        super().__init__(doc, name, "Delete Character Style")


class _EditStyleCommand(Command):
    """Replace the style at `name` with `new_style`.

    Cycle detection runs at redo time as defence-in-depth: the dialog
    filters cycling parents from the combo, but a programmatic caller
    may pass anything. `StyleCycleError` propagates and the registry
    is left untouched.
    """

    _attr: ClassVar[str]

    def __init__(
        self, document: Document, name: str, new_style: Any, label: str
    ) -> None:
        super().__init__(document, label)
        self._original_name = name
        self.new_style = new_style
        self._previous: Any = None
        self._index: int = -1

    def _do(self, doc: Document) -> None:
        styles = _styles(doc, self._attr)
        self._index = _find_index(styles, self._original_name)
        if self.new_style.based_on is not None and StyleResolver.detect_cycle(
            styles, self.new_style.name, self.new_style.based_on
        ):
            raise StyleCycleError(
                f"based_on={self.new_style.based_on!r} would cycle "
                f"with {self.new_style.name!r}"
            )
        self._previous = styles[self._index]
        styles[self._index] = self.new_style

    def _undo(self, doc: Document) -> None:
        assert self._previous is not None, "edit undone before redo"
        styles = _styles(doc, self._attr)
        styles[self._index] = self._previous


class EditParagraphStyleCommand(_EditStyleCommand):
    _attr = "paragraph_styles"

    def __init__(
        self, document: Document, name: str, new_style: ParagraphStyle
    ) -> None:
        super().__init__(document, name, new_style, "Edit Paragraph Style")


class EditCharacterStyleCommand(_EditStyleCommand):
    _attr = "character_styles"

    def __init__(
        self, document: Document, name: str, new_style: CharacterStyle
    ) -> None:
        super().__init__(document, name, new_style, "Edit Character Style")


# ---------------------------------------------------------------------------
# Apply commands record the applied name on `doc.selection`. The per-block
# mutation that wires `paragraph_style_ref` is the block-editor unit's job;
# the palette only needs to broadcast "name X was applied".
# ---------------------------------------------------------------------------


class _ApplyStyleCommand(Command):
    _selection_attr: ClassVar[str]

    def __init__(self, doc: Document, name: str, label: str) -> None:
        super().__init__(doc, label)
        self.name = name
        self._previous: str | None = None

    def _do(self, doc: Document) -> None:
        sel: Any = doc.selection  # type: ignore[attr-defined]
        self._previous = getattr(sel, self._selection_attr, None)
        setattr(sel, self._selection_attr, self.name)

    def _undo(self, doc: Document) -> None:
        sel: Any = doc.selection  # type: ignore[attr-defined]
        setattr(sel, self._selection_attr, self._previous)


class ApplyParagraphStyleCommand(_ApplyStyleCommand):
    _selection_attr = "paragraph_style"

    def __init__(self, doc: Document, name: str) -> None:
        super().__init__(doc, name, "Apply Paragraph Style")


class ApplyCharacterStyleCommand(_ApplyStyleCommand):
    _selection_attr = "character_style"

    def __init__(self, doc: Document, name: str) -> None:
        super().__init__(doc, name, "Apply Character Style")


__all__ = [
    "AddCharacterStyleCommand",
    "AddParagraphStyleCommand",
    "ApplyCharacterStyleCommand",
    "ApplyParagraphStyleCommand",
    "DeleteCharacterStyleCommand",
    "DeleteParagraphStyleCommand",
    "DuplicateCharacterStyleCommand",
    "DuplicateParagraphStyleCommand",
    "EditCharacterStyleCommand",
    "EditParagraphStyleCommand",
]
