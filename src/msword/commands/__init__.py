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
# Unit-22 measurements-palette commands. Real Command subclasses that mutate
# the canonical Frame / Run / Document via `doc.find_frame` and
# `doc.selection.caret_run`. Kept in __init__.py so callers can
# `from msword.commands import SetBoldCommand` without depending on a sibling
# unit landing first.
# ---------------------------------------------------------------------------

import dataclasses as _dataclasses
from typing import Any as _Any
from typing import cast as _cast

from PySide6.QtGui import QUndoCommand as _QUndoCommand

from msword.model.color import ColorSwatch as _ColorSwatch
from msword.model.document import Document as _ModelDocument
from msword.model.frame import Fill as _Fill
from msword.model.frame import Stroke as _Stroke
from msword.model.run import Run as _Run


def _replace_caret_run(doc: _Any, **marks: _Any) -> _Any:
    """Replace `doc.selection.caret_run` with a copy carrying `**marks`.

    Returns the previous run so the caller can retain it for undo. If there
    is no caret run, returns `None` and does nothing.
    """
    run = getattr(doc.selection, "caret_run", None)
    if run is None:
        return None
    doc.selection.caret_run = _dataclasses.replace(run, **marks)
    return run


def _restore_caret_run(doc: _Any, run: _Any) -> None:
    if run is not None:
        doc.selection.caret_run = run


class RotateFrameCommand(Command):
    def __init__(self, doc: _Any, *, frame_id: str, rotation: float) -> None:
        super().__init__(doc, "Rotate Frame")
        self.frame_id = frame_id
        self.rotation = rotation
        self._old: float | None = None

    def _do(self, doc: _Any) -> None:
        frame = doc.find_frame(self.frame_id)
        if frame is None:
            return
        self._old = frame.rotation_deg
        frame.rotation_deg = self.rotation

    def _undo(self, doc: _Any) -> None:
        if self._old is None:
            return
        frame = doc.find_frame(self.frame_id)
        if frame is not None:
            frame.rotation_deg = self._old


class SkewFrameCommand(Command):
    def __init__(self, doc: _Any, *, frame_id: str, skew: float) -> None:
        super().__init__(doc, "Skew Frame")
        self.frame_id = frame_id
        self.skew = skew
        self._old: float | None = None

    def _do(self, doc: _Any) -> None:
        frame = doc.find_frame(self.frame_id)
        if frame is None:
            return
        self._old = frame.skew_deg
        frame.skew_deg = self.skew

    def _undo(self, doc: _Any) -> None:
        if self._old is None:
            return
        frame = doc.find_frame(self.frame_id)
        if frame is not None:
            frame.skew_deg = self._old


class SetAspectLockCommand(Command):
    """Frame aspect-lock is a UI constraint not in the canonical Frame schema;
    stored on the Document keyed by frame id."""

    def __init__(self, doc: _Any, *, frame_id: str, locked: bool) -> None:
        super().__init__(doc, "Lock Aspect Ratio")
        self.frame_id = frame_id
        self.locked = locked
        self._old: bool | None = None

    def _do(self, doc: _Any) -> None:
        self._old = bool(doc.aspect_locks.get(self.frame_id, False))
        doc.aspect_locks[self.frame_id] = self.locked

    def _undo(self, doc: _Any) -> None:
        if self._old is None:
            return
        doc.aspect_locks[self.frame_id] = self._old


class SetColumnsCommand(Command):
    def __init__(self, doc: _Any, *, frame_id: str, columns: int) -> None:
        super().__init__(doc, "Set Columns")
        self.frame_id = frame_id
        self.columns = columns
        self._old: int | None = None

    def _do(self, doc: _Any) -> None:
        frame = doc.find_frame(self.frame_id)
        if frame is None:
            return
        self._old = frame.columns
        frame.columns = self.columns

    def _undo(self, doc: _Any) -> None:
        if self._old is None:
            return
        frame = doc.find_frame(self.frame_id)
        if frame is not None:
            frame.columns = self._old


class SetGutterCommand(Command):
    def __init__(self, doc: _Any, *, frame_id: str, gutter: float) -> None:
        super().__init__(doc, "Set Gutter")
        self.frame_id = frame_id
        self.gutter = gutter
        self._old: float | None = None

    def _do(self, doc: _Any) -> None:
        frame = doc.find_frame(self.frame_id)
        if frame is None:
            return
        self._old = frame.gutter_pt
        frame.gutter_pt = self.gutter

    def _undo(self, doc: _Any) -> None:
        if self._old is None:
            return
        frame = doc.find_frame(self.frame_id)
        if frame is not None:
            frame.gutter_pt = self._old


class SetVerticalAlignCommand(Command):
    def __init__(self, doc: _Any, *, frame_id: str, vertical_align: str) -> None:
        super().__init__(doc, "Set Vertical Align")
        self.frame_id = frame_id
        self.vertical_align = vertical_align
        self._old: str | None = None

    def _do(self, doc: _Any) -> None:
        frame = doc.find_frame(self.frame_id)
        if frame is None:
            return
        self._old = frame.vertical_align
        frame.vertical_align = self.vertical_align

    def _undo(self, doc: _Any) -> None:
        if self._old is None:
            return
        frame = doc.find_frame(self.frame_id)
        if frame is not None:
            frame.vertical_align = self._old


class SetBaselineGridCommand(Command):
    """Toggle the per-frame 'align to baseline grid' override on the Document."""

    def __init__(self, doc: _Any, *, frame_id: str, enabled: bool) -> None:
        super().__init__(doc, "Set Baseline Grid")
        self.frame_id = frame_id
        self.enabled = enabled
        self._old: bool | None = None

    def _do(self, doc: _Any) -> None:
        self._old = bool(doc.baseline_grid_overrides.get(self.frame_id, False))
        doc.baseline_grid_overrides[self.frame_id] = self.enabled

    def _undo(self, doc: _Any) -> None:
        if self._old is None:
            return
        doc.baseline_grid_overrides[self.frame_id] = self._old


class SetFontCommand(Command):
    def __init__(self, doc: _Any, *, family: str) -> None:
        super().__init__(doc, "Set Font")
        self.family = family
        self._old: _Any = None

    def _do(self, doc: _Any) -> None:
        self._old = _replace_caret_run(doc, font_ref=self.family)

    def _undo(self, doc: _Any) -> None:
        _restore_caret_run(doc, self._old)


class SetSizeCommand(Command):
    def __init__(self, doc: _Any, *, size: float) -> None:
        super().__init__(doc, "Set Size")
        self.size = size
        self._old: _Any = None

    def _do(self, doc: _Any) -> None:
        self._old = _replace_caret_run(doc, size_pt=self.size)

    def _undo(self, doc: _Any) -> None:
        _restore_caret_run(doc, self._old)


class SetLeadingCommand(Command):
    """Leading is paragraph-style level. With no resolved style, no-op."""

    def __init__(self, doc: _Any, *, leading: float) -> None:
        super().__init__(doc, "Set Leading")
        self.leading = leading
        self._old: tuple[str, float | None] | None = None

    def _do(self, doc: _Any) -> None:
        if getattr(doc.selection, "caret_run", None) is None:
            return
        styles = doc.paragraph_styles
        if not (isinstance(styles, list) and styles):
            return
        style = styles[0]
        self._old = (style.name, style.leading_pt)
        style.leading_pt = self.leading

    def _undo(self, doc: _Any) -> None:
        if self._old is None:
            return
        name, prev = self._old
        style = doc.find_paragraph_style(name)
        if style is not None:
            style.leading_pt = prev


class SetTrackingCommand(Command):
    def __init__(self, doc: _Any, *, tracking: float) -> None:
        super().__init__(doc, "Set Tracking")
        self.tracking = tracking
        self._old: _Any = None

    def _do(self, doc: _Any) -> None:
        self._old = _replace_caret_run(doc, tracking=self.tracking)

    def _undo(self, doc: _Any) -> None:
        _restore_caret_run(doc, self._old)


class SetAlignmentCommand(Command):
    """Alignment is paragraph-style level. With no styles defined, no-op."""

    def __init__(self, doc: _Any, *, alignment: str) -> None:
        super().__init__(doc, "Set Alignment")
        self.alignment = alignment
        self._old: tuple[str, str | None] | None = None

    def _do(self, doc: _Any) -> None:
        styles = doc.paragraph_styles
        if not (isinstance(styles, list) and styles):
            return
        style = styles[0]
        self._old = (style.name, style.alignment)
        style.alignment = self.alignment

    def _undo(self, doc: _Any) -> None:
        if self._old is None:
            return
        name, prev = self._old
        style = doc.find_paragraph_style(name)
        if style is not None:
            style.alignment = prev


class SetBoldCommand(Command):
    def __init__(self, doc: _Any, *, bold: bool) -> None:
        super().__init__(doc, "Set Bold")
        self.bold = bold
        self._old: _Any = None

    def _do(self, doc: _Any) -> None:
        self._old = _replace_caret_run(doc, bold=self.bold)

    def _undo(self, doc: _Any) -> None:
        _restore_caret_run(doc, self._old)


class SetItalicCommand(Command):
    def __init__(self, doc: _Any, *, italic: bool) -> None:
        super().__init__(doc, "Set Italic")
        self.italic = italic
        self._old: _Any = None

    def _do(self, doc: _Any) -> None:
        self._old = _replace_caret_run(doc, italic=self.italic)

    def _undo(self, doc: _Any) -> None:
        _restore_caret_run(doc, self._old)


class SetUnderlineCommand(Command):
    def __init__(self, doc: _Any, *, underline: bool) -> None:
        super().__init__(doc, "Set Underline")
        self.underline = underline
        self._old: _Any = None

    def _do(self, doc: _Any) -> None:
        self._old = _replace_caret_run(doc, underline=self.underline)

    def _undo(self, doc: _Any) -> None:
        _restore_caret_run(doc, self._old)


class SetStrikeCommand(Command):
    def __init__(self, doc: _Any, *, strike: bool) -> None:
        super().__init__(doc, "Set Strike")
        self.strike = strike
        self._old: _Any = None

    def _do(self, doc: _Any) -> None:
        self._old = _replace_caret_run(doc, strike=self.strike)

    def _undo(self, doc: _Any) -> None:
        _restore_caret_run(doc, self._old)


class SetParagraphStyleCommand(Command):
    """Set the document's active paragraph style."""

    def __init__(self, doc: _Any, *, style_name: str) -> None:
        super().__init__(doc, "Set Paragraph Style")
        self.style_name = style_name
        self._old: str | None = None

    def _do(self, doc: _Any) -> None:
        self._old = doc.active_paragraph_style
        doc.active_paragraph_style = self.style_name

    def _undo(self, doc: _Any) -> None:
        doc.active_paragraph_style = self._old


class SetOpenTypeFeatureCommand(Command):
    def __init__(self, doc: _Any, *, feature: str, enabled: bool) -> None:
        super().__init__(doc, "Set OpenType Feature")
        self.feature = feature
        self.enabled = enabled
        self._old: _Any = None

    def _do(self, doc: _Any) -> None:
        run = getattr(doc.selection, "caret_run", None)
        if run is None:
            return
        feats = set(run.opentype_features)
        if self.enabled:
            feats.add(self.feature)
        else:
            feats.discard(self.feature)
        self._old = _replace_caret_run(doc, opentype_features=frozenset(feats))

    def _undo(self, doc: _Any) -> None:
        _restore_caret_run(doc, self._old)


class SetZoomCommand(Command):
    def __init__(self, doc: _Any, *, zoom: float) -> None:
        super().__init__(doc, "Set Zoom")
        self.zoom = zoom
        self._old: float | None = None

    def _do(self, doc: _Any) -> None:
        self._old = doc.zoom
        doc.zoom = self.zoom

    def _undo(self, doc: _Any) -> None:
        if self._old is not None:
            doc.zoom = self._old


class SetViewModeCommand(Command):
    def __init__(self, doc: _Any, *, view_mode: str) -> None:
        super().__init__(doc, "Set View Mode")
        self.view_mode = view_mode
        self._old: str | None = None

    def _do(self, doc: _Any) -> None:
        self._old = doc.view_mode
        doc.view_mode = self.view_mode

    def _undo(self, doc: _Any) -> None:
        if self._old is not None:
            doc.view_mode = self._old


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
class ReplaceTextInRunCommand(Command):
    """Replace `block.runs[run_index].text[char_start:char_end]` with `replacement`.

    `Run` is a frozen dataclass — instead of mutating the run in place we
    swap `block.runs[run_index]` for a new run produced by `with_text`,
    which preserves all inline marks. `_undo` restores the original run.
    """

    def __init__(
        self,
        doc: Document,
        block: _Any,
        run_index: int,
        char_start: int,
        char_end: int,
        replacement: str,
        text: str = "Replace text",
    ) -> None:
        super().__init__(doc, text)
        self._block = block
        self._run_index = run_index
        self._char_start = char_start
        self._char_end = char_end
        self._replacement = replacement
        self._original_run: _Any = None

    def _do(self, doc: Document) -> None:
        runs = self._block.runs
        run = runs[self._run_index]
        self._original_run = run
        new_text = run.text[: self._char_start] + self._replacement + run.text[self._char_end :]
        runs[self._run_index] = run.with_text(new_text)

    def _undo(self, doc: Document) -> None:
        self._block.runs[self._run_index] = self._original_run
