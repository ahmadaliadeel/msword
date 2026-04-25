"""Stub commands package for unit-22.

Real implementation lives in unit-9 (`commands-and-undo`). The palette pushes
typed `Command`s onto an `UndoStack`; the stub records them in-memory so tests
can introspect them.
"""

from __future__ import annotations

from dataclasses import dataclass


class Command:
    """Base command stub. Real version integrates with `QUndoStack`."""

    def apply(self) -> None:  # pragma: no cover — overridden by subclasses
        """Apply the mutation to the document."""

    def revert(self) -> None:  # pragma: no cover — overridden by subclasses
        """Undo the mutation."""


@dataclass
class MoveFrameCommand(Command):
    """Move a frame to (`x`, `y`) (points)."""

    frame_id: str
    x: float
    y: float


@dataclass
class ResizeFrameCommand(Command):
    """Resize a frame to (`w`, `h`) (points), preserving the top-left corner."""

    frame_id: str
    w: float
    h: float


@dataclass
class RotateFrameCommand(Command):
    frame_id: str
    rotation: float


@dataclass
class SkewFrameCommand(Command):
    frame_id: str
    skew: float


@dataclass
class SetAspectLockCommand(Command):
    frame_id: str
    locked: bool


@dataclass
class SetColumnsCommand(Command):
    frame_id: str
    columns: int


@dataclass
class SetGutterCommand(Command):
    frame_id: str
    gutter: float


@dataclass
class SetVerticalAlignCommand(Command):
    frame_id: str
    vertical_align: str  # top | center | bottom | justify


@dataclass
class SetBaselineGridCommand(Command):
    frame_id: str
    enabled: bool


@dataclass
class SetFontCommand(Command):
    family: str


@dataclass
class SetSizeCommand(Command):
    size: float


@dataclass
class SetLeadingCommand(Command):
    leading: float


@dataclass
class SetTrackingCommand(Command):
    tracking: float


@dataclass
class SetAlignmentCommand(Command):
    alignment: str  # left | center | right | justify


@dataclass
class SetBoldCommand(Command):
    bold: bool


@dataclass
class SetItalicCommand(Command):
    italic: bool


@dataclass
class SetUnderlineCommand(Command):
    underline: bool


@dataclass
class SetStrikeCommand(Command):
    strike: bool


@dataclass
class SetParagraphStyleCommand(Command):
    style_name: str


@dataclass
class SetOpenTypeFeatureCommand(Command):
    """Toggle an OpenType feature tag (e.g. `liga`, `dlig`, `smcp`, `ss01`…)."""

    feature: str
    enabled: bool


@dataclass
class SetZoomCommand(Command):
    zoom: float


@dataclass
class SetViewModeCommand(Command):
    view_mode: str  # paged | flow


class UndoStack:
    """In-memory `QUndoStack` stand-in.

    The real version (unit-9) wraps `QUndoStack`; for the palette tests we only
    need the FIFO of pushed commands.
    """

    def __init__(self) -> None:
        self._commands: list[Command] = []

    def push(self, command: Command) -> None:
        self._commands.append(command)
        command.apply()

    @property
    def commands(self) -> list[Command]:
        return list(self._commands)

    @property
    def last(self) -> Command | None:
        return self._commands[-1] if self._commands else None

    def clear(self) -> None:
        self._commands.clear()


__all__ = [
    "Command",
    "MoveFrameCommand",
    "ResizeFrameCommand",
    "RotateFrameCommand",
    "SetAlignmentCommand",
    "SetAspectLockCommand",
    "SetBaselineGridCommand",
    "SetBoldCommand",
    "SetColumnsCommand",
    "SetFontCommand",
    "SetGutterCommand",
    "SetItalicCommand",
    "SetLeadingCommand",
    "SetOpenTypeFeatureCommand",
    "SetParagraphStyleCommand",
    "SetSizeCommand",
    "SetStrikeCommand",
    "SetTrackingCommand",
    "SetUnderlineCommand",
    "SetVerticalAlignCommand",
    "SetViewModeCommand",
    "SetZoomCommand",
    "SkewFrameCommand",
    "UndoStack",
]
