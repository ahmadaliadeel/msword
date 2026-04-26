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

__all__ = [
    "AddFrameCommand",
    "AddPageCommand",
    "Command",
    "Document",
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

from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from typing import Any as _Any
from typing import cast as _cast

from msword.model.color import ColorSwatch as _ColorSwatch
from msword.model.document import Document as _ModelDocument
from msword.model.frame import Fill as _Fill
from msword.model.frame import Stroke as _Stroke


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


# ---------------------------------------------------------------------------
# Unit-25 style-sheets-palette commands.
# ---------------------------------------------------------------------------


@_dataclass
class _UnitTwentyFiveStub:
    pass


@_dataclass
class AddParagraphStyleCommand(_UnitTwentyFiveStub):
    name: str = ""


@_dataclass
class DuplicateParagraphStyleCommand(_UnitTwentyFiveStub):
    source_name: str = ""
    new_name: str = ""


@_dataclass
class DeleteParagraphStyleCommand(_UnitTwentyFiveStub):
    name: str = ""


@_dataclass
class EditParagraphStyleCommand(_UnitTwentyFiveStub):
    name: str = ""
    fields: dict = None  # type: ignore


@_dataclass
class ApplyParagraphStyleCommand(_UnitTwentyFiveStub):
    style_name: str = ""


@_dataclass
class AddCharacterStyleCommand(_UnitTwentyFiveStub):
    name: str = ""


@_dataclass
class DuplicateCharacterStyleCommand(_UnitTwentyFiveStub):
    source_name: str = ""
    new_name: str = ""


@_dataclass
class DeleteCharacterStyleCommand(_UnitTwentyFiveStub):
    name: str = ""


@_dataclass
class EditCharacterStyleCommand(_UnitTwentyFiveStub):
    name: str = ""
    fields: dict = None  # type: ignore


@_dataclass
class ApplyCharacterStyleCommand(_UnitTwentyFiveStub):
    style_name: str = ""


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
@_dataclass
class _UnitTwentyNineStub:
    pass


@_dataclass
class TransformBlockCommand(_UnitTwentyNineStub):
    kind: str = "paragraph"
    params: dict[str, _Any] = _field(default_factory=dict)
    name: str = "transform-block"


@_dataclass
class ToggleMarkCommand(_UnitTwentyNineStub):
    mark: str = "bold"
    name: str = "toggle-mark"


@_dataclass
class SetLinkCommand(_UnitTwentyNineStub):
    url: str = ""
    name: str = "set-link"


@_dataclass
class SetRunColorCommand(_UnitTwentyNineStub):
    color: str = ""
    role: str = "color"
    name: str = "set-run-color"


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
