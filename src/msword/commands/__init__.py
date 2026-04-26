"""Command pattern stubs for unit-26 (colors palette).

The full command framework lands in unit-9 (`commands-and-undo`). Here we
only define the minimal :class:`Command` base + the colour-related
commands the colours palette dispatches. Each command implements
``redo()`` / ``undo()`` (the QUndoCommand contract) so the unit-9 wiring
is a drop-in.

Strict invariant from the spec: views and dialogs *never* mutate the
model directly. They construct one of these commands and call ``redo()``
(or, in unit-9, push it onto the document's undo stack).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from msword.model.color import ColorSwatch
from msword.model.document import Document, _StubFrame


class Command:
    """Minimal Command base, replaced by the QUndoCommand-backed base in
    unit-9. We keep ``redo()`` / ``undo()`` so the upgrade is mechanical.
    """

    def redo(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def undo(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError


# --- swatch registry mutations ------------------------------------------


@dataclass
class AddColorSwatchCommand(Command):
    document: Document
    swatch: ColorSwatch

    def redo(self) -> None:
        if self.swatch.name in self.document.color_swatches:
            raise ValueError(
                f"color swatch {self.swatch.name!r} already exists"
            )
        self.document.color_swatches[self.swatch.name] = self.swatch

    def undo(self) -> None:
        self.document.color_swatches.pop(self.swatch.name, None)


@dataclass
class EditColorSwatchCommand(Command):
    document: Document
    name: str
    new_swatch: ColorSwatch
    _previous: ColorSwatch | None = field(default=None, init=False, repr=False)

    def redo(self) -> None:
        if self.name not in self.document.color_swatches:
            raise KeyError(f"color swatch {self.name!r} does not exist")
        self._previous = self.document.color_swatches[self.name]
        # If the user renamed the swatch, drop the old key.
        if self.new_swatch.name != self.name:
            if self.new_swatch.name in self.document.color_swatches:
                raise ValueError(
                    f"color swatch {self.new_swatch.name!r} already exists"
                )
            del self.document.color_swatches[self.name]
        self.document.color_swatches[self.new_swatch.name] = self.new_swatch

    def undo(self) -> None:
        if self._previous is None:
            return
        # Reverse rename if any.
        self.document.color_swatches.pop(self.new_swatch.name, None)
        self.document.color_swatches[self.name] = self._previous


@dataclass
class DeleteColorSwatchCommand(Command):
    document: Document
    name: str
    _saved: ColorSwatch | None = field(default=None, init=False, repr=False)

    def redo(self) -> None:
        self._saved = self.document.color_swatches.pop(self.name)

    def undo(self) -> None:
        if self._saved is not None:
            self.document.color_swatches[self.name] = self._saved


@dataclass
class DuplicateColorSwatchCommand(Command):
    document: Document
    source_name: str
    new_name: str

    def redo(self) -> None:
        if self.new_name in self.document.color_swatches:
            raise ValueError(
                f"color swatch {self.new_name!r} already exists"
            )
        src = self.document.color_swatches[self.source_name]
        self.document.color_swatches[self.new_name] = ColorSwatch(
            name=self.new_name,
            profile_name=src.profile_name,
            components=src.components,
            is_spot=src.is_spot,
        )

    def undo(self) -> None:
        self.document.color_swatches.pop(self.new_name, None)


# --- frame fill / stroke -------------------------------------------------


@dataclass
class SetFrameFillCommand(Command):
    """Set the named-swatch fill on the document's currently selected frame."""

    document: Document
    swatch_name: str
    _previous: str | None = field(default=None, init=False, repr=False)
    _frame: _StubFrame | None = field(default=None, init=False, repr=False)

    def redo(self) -> None:
        frame = self.document.selected_frame
        if frame is None:
            raise RuntimeError("SetFrameFillCommand requires a selected frame")
        if self.swatch_name not in self.document.color_swatches:
            raise KeyError(
                f"unknown color swatch {self.swatch_name!r}"
            )
        self._frame = frame
        self._previous = frame.fill
        frame.fill = self.swatch_name

    def undo(self) -> None:
        if self._frame is not None:
            self._frame.fill = self._previous


@dataclass
class SetFrameStrokeCommand(Command):
    """Set the named-swatch stroke on the document's currently selected frame."""

    document: Document
    swatch_name: str
    _previous: str | None = field(default=None, init=False, repr=False)
    _frame: _StubFrame | None = field(default=None, init=False, repr=False)

    def redo(self) -> None:
        frame = self.document.selected_frame
        if frame is None:
            raise RuntimeError("SetFrameStrokeCommand requires a selected frame")
        if self.swatch_name not in self.document.color_swatches:
            raise KeyError(
                f"unknown color swatch {self.swatch_name!r}"
            )
        self._frame = frame
        self._previous = frame.stroke
        frame.stroke = self.swatch_name

    def undo(self) -> None:
        if self._frame is not None:
            self._frame.stroke = self._previous


__all__ = [
    "AddColorSwatchCommand",
    "Command",
    "DeleteColorSwatchCommand",
    "DuplicateColorSwatchCommand",
    "EditColorSwatchCommand",
    "SetFrameFillCommand",
    "SetFrameStrokeCommand",
]
