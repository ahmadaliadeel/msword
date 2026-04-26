"""Commands package — single source of truth for document mutation.

Per the spec (§3 architecture), **commands are the only way views and tools
mutate the `Document`**. This is a project-wide invariant enforced by
convention: any code path that changes model state must do so by constructing
a `Command` subclass and pushing it onto the document's `UndoStack`. Views
and tools observe the document via Qt signals; they never write to it
directly.

This package is allowed to import Qt (`PySide6.QtGui.QUndoCommand`,
`PySide6.QtCore.QUndoStack`); model packages are not.

Public surface:

- `Command` — base class wrapping `QUndoCommand`. Subclasses implement
  `_do` / `_undo` and override `text()`.
- `UndoStack` — thin wrapper around `QUndoStack` exposing the only API
  views/tools should call (`push`, `undo`, `redo`, `begin_macro`,
  `end_macro`, `clear`, plus `index_changed` and `clean_changed` signals).
- `MacroCommand` — composite command that runs a list of sub-commands
  forward and reverses them on undo. Useful when `begin_macro` /
  `end_macro` aren't sufficient (e.g. constructing a single command that
  itself contains an ordered batch).
- Concrete commands for pages and frames (see `page` and `frame` modules).

Concrete commands hold a strong reference to the `Document` rather than a
weak reference. Documents are the long-lived owners of their undo stack
(commands sit on `doc.undo_stack`); a command can never outlive its
document, so the strong-ref keeps the type signature simple and avoids the
ergonomic cost of `weakref.proxy` indirection on the hot path.
"""

from __future__ import annotations

from msword.commands.base import Command, Document, Frame, Page
from msword.commands.frame import (
    AddFrameCommand,
    MoveFrameCommand,
    RemoveFrameCommand,
    ResizeFrameCommand,
)
from msword.commands.macro import MacroCommand
from msword.commands.page import AddPageCommand, MovePageCommand, RemovePageCommand
from msword.commands.stack import UndoStack
from msword.commands.style import (
    AddCharacterStyleCommand,
    AddParagraphStyleCommand,
    ApplyCharacterStyleCommand,
    ApplyParagraphStyleCommand,
    DeleteCharacterStyleCommand,
    DeleteParagraphStyleCommand,
    DuplicateCharacterStyleCommand,
    DuplicateParagraphStyleCommand,
    EditCharacterStyleCommand,
    EditParagraphStyleCommand,
)

__all__ = [
    "AddCharacterStyleCommand",
    "AddFrameCommand",
    "AddPageCommand",
    "AddParagraphStyleCommand",
    "ApplyCharacterStyleCommand",
    "ApplyParagraphStyleCommand",
    "Command",
    "DeleteCharacterStyleCommand",
    "DeleteParagraphStyleCommand",
    "Document",
    "DuplicateCharacterStyleCommand",
    "DuplicateParagraphStyleCommand",
    "EditCharacterStyleCommand",
    "EditParagraphStyleCommand",
    "Frame",
    "MacroCommand",
    "MoveFrameCommand",
    "MovePageCommand",
    "Page",
    "RemoveFrameCommand",
    "RemovePageCommand",
    "ResizeFrameCommand",
    "UndoStack",
]


# ---------------------------------------------------------------------------
# Unit-22 measurements-palette commands. These are dataclass stubs (no undo
# wiring) until unit-22 / unit-9 contribute concrete _do/_undo implementations.
# Kept in __init__.py so callers can `from msword.commands import SetBoldCommand`
# without depending on a sibling unit landing first.
# ---------------------------------------------------------------------------

import dataclasses as _dataclasses
from dataclasses import dataclass as _dataclass
from typing import Any as _Any
from typing import cast as _cast

from msword.model.color import ColorSwatch as _ColorSwatch
from msword.model.document import Document as _ModelDocument
from msword.model.frame import Fill as _Fill
from msword.model.frame import Stroke as _Stroke

from PySide6.QtGui import QUndoCommand as _QUndoCommand

from msword.model.run import Run as _Run


@_dataclass
class _UnitTwentyTwoStub:
    """Marker base; subclasses are dataclass stubs from unit-22."""


@_dataclass
class RotateFrameCommand(_UnitTwentyTwoStub):
    frame_id: str = ""
    rotation: float = 0.0


@_dataclass
class SkewFrameCommand(_UnitTwentyTwoStub):
    frame_id: str = ""
    skew: float = 0.0


@_dataclass
class SetAspectLockCommand(_UnitTwentyTwoStub):
    frame_id: str = ""
    locked: bool = False


@_dataclass
class SetColumnsCommand(_UnitTwentyTwoStub):
    frame_id: str = ""
    columns: int = 1


@_dataclass
class SetGutterCommand(_UnitTwentyTwoStub):
    frame_id: str = ""
    gutter: float = 0.0


@_dataclass
class SetVerticalAlignCommand(_UnitTwentyTwoStub):
    frame_id: str = ""
    vertical_align: str = "top"


@_dataclass
class SetBaselineGridCommand(_UnitTwentyTwoStub):
    frame_id: str = ""
    enabled: bool = False


@_dataclass
class SetFontCommand(_UnitTwentyTwoStub):
    family: str = ""


@_dataclass
class SetSizeCommand(_UnitTwentyTwoStub):
    size: float = 0.0


@_dataclass
class SetLeadingCommand(_UnitTwentyTwoStub):
    leading: float = 0.0


@_dataclass
class SetTrackingCommand(_UnitTwentyTwoStub):
    tracking: float = 0.0


@_dataclass
class SetAlignmentCommand(_UnitTwentyTwoStub):
    alignment: str = "left"


@_dataclass
class SetBoldCommand(_UnitTwentyTwoStub):
    bold: bool = False


@_dataclass
class SetItalicCommand(_UnitTwentyTwoStub):
    italic: bool = False


@_dataclass
class SetUnderlineCommand(_UnitTwentyTwoStub):
    underline: bool = False


@_dataclass
class SetStrikeCommand(_UnitTwentyTwoStub):
    strike: bool = False


@_dataclass
class SetParagraphStyleCommand(_UnitTwentyTwoStub):
    style_name: str = ""


@_dataclass
class SetOpenTypeFeatureCommand(_UnitTwentyTwoStub):
    tag: str = ""
    enabled: bool = False


@_dataclass
class SetZoomCommand(_UnitTwentyTwoStub):
    zoom: float = 1.0


@_dataclass
class SetViewModeCommand(_UnitTwentyTwoStub):
    view_mode: str = "paged"


# Unit-26 colors-palette commands.
class AddColorSwatchCommand(Command):
    def __init__(self, doc: _ModelDocument, swatch: _ColorSwatch) -> None:
        super().__init__(_cast(Document, doc), "Add Color Swatch")
        self.swatch = swatch

    def _do(self, doc: Document) -> None:
        _cast(_ModelDocument, doc).color_swatches.append(self.swatch)

    def _undo(self, doc: Document) -> None:
        swatches = _cast(_ModelDocument, doc).color_swatches
        for i, existing in enumerate(swatches):
            if existing.name == self.swatch.name:
                del swatches[i]
                return


class EditColorSwatchCommand(Command):
    def __init__(
        self, doc: _ModelDocument, original_name: str, new_swatch: _ColorSwatch
    ) -> None:
        super().__init__(_cast(Document, doc), "Edit Color Swatch")
        self.original_name = original_name
        self.new_swatch = new_swatch
        self._previous: _ColorSwatch | None = None
        self._index: int = -1

    def _do(self, doc: Document) -> None:
        swatches = _cast(_ModelDocument, doc).color_swatches
        for i, existing in enumerate(swatches):
            if existing.name == self.original_name:
                self._previous = existing
                self._index = i
                swatches[i] = self.new_swatch
                return
        raise KeyError(f"swatch {self.original_name!r} not found")

    def _undo(self, doc: Document) -> None:
        assert self._previous is not None and self._index >= 0
        _cast(_ModelDocument, doc).color_swatches[self._index] = self._previous


class DeleteColorSwatchCommand(Command):
    def __init__(self, doc: _ModelDocument, name: str) -> None:
        super().__init__(_cast(Document, doc), "Delete Color Swatch")
        self.name = name
        self._removed: _ColorSwatch | None = None
        self._index: int = -1

    def _do(self, doc: Document) -> None:
        swatches = _cast(_ModelDocument, doc).color_swatches
        for i, existing in enumerate(swatches):
            if existing.name == self.name:
                self._removed = existing
                self._index = i
                del swatches[i]
                return
        raise KeyError(f"swatch {self.name!r} not found")

    def _undo(self, doc: Document) -> None:
        assert self._removed is not None and self._index >= 0
        _cast(_ModelDocument, doc).color_swatches.insert(self._index, self._removed)


class DuplicateColorSwatchCommand(Command):
    def __init__(self, doc: _ModelDocument, source_name: str, new_name: str) -> None:
        super().__init__(_cast(Document, doc), "Duplicate Color Swatch")
        self.source_name = source_name
        self.new_name = new_name

    def _do(self, doc: Document) -> None:
        model_doc = _cast(_ModelDocument, doc)
        source = model_doc.find_color_swatch(self.source_name)
        if source is None:
            raise KeyError(f"swatch {self.source_name!r} not found")
        copy = _ColorSwatch(
            name=self.new_name,
            profile_name=source.profile_name,
            components=source.components,
            is_spot=source.is_spot,
        )
        model_doc.color_swatches.append(copy)

    def _undo(self, doc: Document) -> None:
        swatches = _cast(_ModelDocument, doc).color_swatches
        for i, existing in enumerate(swatches):
            if existing.name == self.new_name:
                del swatches[i]
                return


def _selected_frame(doc: _ModelDocument) -> _Any:
    selection = doc.selection
    frames = getattr(selection, "frames", None) or []
    if len(frames) == 1:
        return frames[0]
    return getattr(selection, "caret_frame", None)


class SetFrameFillCommand(Command):
    def __init__(self, doc: _ModelDocument, swatch_name: str) -> None:
        super().__init__(_cast(Document, doc), "Set Frame Fill")
        self.swatch_name = swatch_name
        self._frame: _Any = None
        self._previous: _Fill | None = None

    def _do(self, doc: Document) -> None:
        frame = _selected_frame(_cast(_ModelDocument, doc))
        if frame is None:
            return
        self._frame = frame
        self._previous = getattr(frame, "fill", None)
        frame.fill = _Fill(color_ref=self.swatch_name)

    def _undo(self, doc: Document) -> None:
        if self._frame is None:
            return
        self._frame.fill = self._previous


class SetFrameStrokeCommand(Command):
    def __init__(self, doc: _ModelDocument, swatch_name: str) -> None:
        super().__init__(_cast(Document, doc), "Set Frame Stroke")
        self.swatch_name = swatch_name
        self._frame: _Any = None
        self._previous: _Stroke | None = None

    def _do(self, doc: Document) -> None:
        frame = _selected_frame(_cast(_ModelDocument, doc))
        if frame is None:
            return
        self._frame = frame
        self._previous = getattr(frame, "stroke", None)
        frame.stroke = _Stroke(color_ref=self.swatch_name)

    def _undo(self, doc: Document) -> None:
        if self._frame is None:
            return
        self._frame.stroke = self._previous


# Unit-29 block-editor-menus commands (slash + bubble menus).
def _find_run_location(doc: _Any, run: _Any) -> tuple[_Any, int] | None:
    for story in getattr(doc, "stories", []):
        for block in getattr(story, "blocks", []):
            runs = getattr(block, "runs", None)
            if runs is None:
                continue
            for i, r in enumerate(runs):
                if r is run:
                    return block, i
    return None


def _replace_run(doc: _Any, block: _Any, index: int, new_run: _Run) -> None:
    block.runs[index] = new_run
    selection = getattr(doc, "selection", None)
    if selection is not None:
        selection.caret_run = new_run


class TransformBlockCommand(Command):
    """Replace the caret block with one of ``kind`` (resolved via :class:`BlockRegistry`)."""

    def __init__(
        self,
        doc: Document | None = None,
        *,
        kind: str = "paragraph",
        params: dict[str, _Any] | None = None,
    ) -> None:
        _QUndoCommand.__init__(self, "Transform Block")
        self._doc = doc  # type: ignore[assignment]
        self.kind = kind
        self.params: dict[str, _Any] = dict(params) if params else {}
        self._story: _Any = None
        self._index: int | None = None
        self._old_block: _Any = None

    def _do(self, doc: Document) -> None:
        from msword.model.block import BlockRegistry

        selection = getattr(doc, "selection", None)
        caret_run = getattr(selection, "caret_run", None) if selection else None
        if caret_run is None:
            return
        located = _find_run_location(doc, caret_run)
        if located is None:
            return
        target_block, _ = located
        block_id = getattr(target_block, "id", None)
        if block_id is None:
            return
        for story in getattr(doc, "stories", []):
            for idx, block in enumerate(getattr(story, "blocks", [])):
                if getattr(block, "id", None) != block_id:
                    continue
                self._story = story
                self._index = idx
                self._old_block = block
                payload: dict[str, _Any] = {"kind": self.kind, "id": block_id, **self.params}
                story.blocks[idx] = BlockRegistry.resolve(payload)
                return

    def _undo(self, doc: Document) -> None:
        if self._story is None or self._index is None or self._old_block is None:
            return
        self._story.blocks[self._index] = self._old_block


class _RunMarkCommand(Command):
    """Locate caret run, replace with ``_apply(run)`` on redo, restore on undo."""

    def __init__(self, doc: Document | None, label: str) -> None:
        _QUndoCommand.__init__(self, label)
        self._doc = doc  # type: ignore[assignment]
        self._block: _Any = None
        self._index: int | None = None
        self._prev_run: _Run | None = None

    def _apply(self, run: _Run) -> _Run:
        raise NotImplementedError

    def _do(self, doc: Document) -> None:
        selection = getattr(doc, "selection", None)
        caret_run = getattr(selection, "caret_run", None) if selection else None
        if not isinstance(caret_run, _Run):
            return
        located = _find_run_location(doc, caret_run)
        if located is None:
            return
        block, index = located
        self._block = block
        self._index = index
        self._prev_run = caret_run
        _replace_run(doc, block, index, self._apply(caret_run))

    def _undo(self, doc: Document) -> None:
        if self._block is None or self._index is None or self._prev_run is None:
            return
        _replace_run(doc, self._block, self._index, self._prev_run)


class ToggleMarkCommand(_RunMarkCommand):
    """Toggle a boolean inline mark (``bold``/``italic``/``underline``/``strike``/``code``)."""

    def __init__(self, doc: Document | None = None, *, mark: str = "bold") -> None:
        super().__init__(doc, "Toggle Mark")
        self.mark = mark

    def _apply(self, run: _Run) -> _Run:
        kwargs: dict[str, _Any] = {self.mark: not getattr(run, self.mark)}
        return _dataclasses.replace(run, **kwargs)


class SetLinkCommand(_RunMarkCommand):
    """Set (or clear, with empty ``url``) the ``link`` mark on the caret run."""

    def __init__(self, doc: Document | None = None, *, url: str = "") -> None:
        super().__init__(doc, "Set Link")
        self.url = url

    def _apply(self, run: _Run) -> _Run:
        return _dataclasses.replace(run, link=self.url or None)


class SetRunColorCommand(_RunMarkCommand):
    """Set ``color_ref`` (role ``"color"``) or ``highlight_ref`` (role ``"highlight"``)."""

    def __init__(
        self,
        doc: Document | None = None,
        *,
        color: str = "",
        role: str = "color",
    ) -> None:
        super().__init__(doc, "Set Run Color")
        self.color = color
        self.role = role

    def _apply(self, run: _Run) -> _Run:
        field_name = "highlight_ref" if self.role == "highlight" else "color_ref"
        kwargs: dict[str, _Any] = {field_name: self.color or None}
        return _dataclasses.replace(run, **kwargs)


# Unit-31 find-replace command.
@_dataclass
class _UnitThirtyOneStub:
    pass


@_dataclass
class ReplaceTextInRunCommand(_UnitThirtyOneStub):
    run: _Any = None
    char_start: int = 0
    char_end: int = 0
    replacement: str = ""
    text: str = "Replace text"
