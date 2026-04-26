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
