"""Local stubs for sibling units used by unit-21's tools.

Per spec §12.1: "Units that need a dependency stub it locally (a minimal mock
implementing the interface) until the providing unit lands."

This unit (21 — table, linker, unlinker) consumes interfaces from:

* unit 20 — ``Tool`` ABC, ``CanvasLike`` protocol
* unit 16 — ``CanvasView``
* unit 3 / 7 — ``Frame``, ``TextFrame``, ``TableFrame``
* unit 4 — ``Story``
* unit 9 — ``AddFrameCommand``, ``LinkFrameCommand``, ``MergeStoriesCommand``,
  ``UnlinkFrameCommand``

Each is resolved dynamically at import time: if the providing unit has landed
the real symbol is used; otherwise a minimal stub here stands in. Tests in
this unit construct stubs directly via ``StubCanvas`` etc. and never depend
on whether the real implementation has merged yet.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsView

if TYPE_CHECKING:
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QKeyEvent, QMouseEvent


# ---------------------------------------------------------------------------
# Tool ABC stub (unit 20)
# ---------------------------------------------------------------------------


class _StubTool:
    """Minimal modal tool base. Real version lives in ``msword.ui.tools.base``.

    Mirrors unit-20's ``Tool``: subclasses override the event hooks they care
    about; defaults are no-ops.
    """

    name: str = ""
    icon_name: str = ""
    cursor: Qt.CursorShape = Qt.CursorShape.ArrowCursor

    def __init__(self) -> None:
        self._canvas: Any | None = None

    @property
    def canvas(self) -> Any | None:
        return self._canvas

    def activate(self, canvas: Any) -> None:
        self._canvas = canvas

    def deactivate(self) -> None:
        self._canvas = None

    def on_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        """Mouse press hook. Default: no-op."""

    def on_mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        """Mouse move hook. Default: no-op."""

    def on_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        """Mouse release hook. Default: no-op."""

    def on_key_press(self, event: QKeyEvent) -> None:
        """Key press hook. Default: no-op."""


# ---------------------------------------------------------------------------
# Model stubs (units 3, 4, 7)
# ---------------------------------------------------------------------------


@dataclass
class _StubStory:
    """Minimal Story: an ordered list of paragraph strings.

    Real ``Story`` (unit 4) has block trees; we only need ``blocks``-truthiness
    to distinguish empty from non-empty for the merge-confirm prompt.
    """

    blocks: list[Any] = field(default_factory=list)


@dataclass
class _StubFrame:
    """Minimal Frame: rectangular geometry + ``kind`` discriminator."""

    x: float
    y: float
    w: float
    h: float
    kind: str = "frame"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class _StubTextFrame(_StubFrame):
    """TextFrame stub: adds ``story_ref`` and ``story_index``."""

    story_ref: _StubStory | None = None
    story_index: int = 0
    kind: str = "text"


@dataclass
class _StubTableFrame(_StubFrame):
    """TableFrame stub: adds ``rows`` and ``cols`` for table tool tests."""

    rows: int = 1
    cols: int = 1
    kind: str = "table"


@dataclass
class _StubPage:
    frames: list[Any] = field(default_factory=list)


@dataclass
class _StubDocument:
    pages: list[_StubPage] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Command stubs (unit 9)
# ---------------------------------------------------------------------------


class _StubAddFrameCommand:
    """``AddFrameCommand`` stub. Mirrors unit-20's signature."""

    def __init__(
        self,
        document: Any,
        page: Any,
        rect: QRectF,
        kind: str,
        **extra: Any,
    ) -> None:
        self.document = document
        self.page = page
        self.rect = rect
        self.kind = kind
        self.extra = extra
        self._frame: Any | None = None

    def redo(self) -> None:
        if self.kind == "table":
            frame: Any = _StubTableFrame(
                x=self.rect.x(),
                y=self.rect.y(),
                w=self.rect.width(),
                h=self.rect.height(),
                rows=int(self.extra.get("rows", 1)),
                cols=int(self.extra.get("cols", 1)),
                extra=dict(self.extra),
            )
        elif self.kind == "text":
            frame = _StubTextFrame(
                x=self.rect.x(),
                y=self.rect.y(),
                w=self.rect.width(),
                h=self.rect.height(),
                extra=dict(self.extra),
            )
        else:
            frame = _StubFrame(
                x=self.rect.x(),
                y=self.rect.y(),
                w=self.rect.width(),
                h=self.rect.height(),
                kind=self.kind,
                extra=dict(self.extra),
            )
        self.page.frames.append(frame)
        self._frame = frame

    def undo(self) -> None:
        if self._frame is not None and self._frame in self.page.frames:
            self.page.frames.remove(self._frame)


class _StubLinkFrameCommand:
    """``LinkFrameCommand`` stub.

    Per spec §3 / §12: links the *target* TextFrame onto the *source* frame's
    story chain by setting ``target.story_ref = source.story_ref`` and
    ``target.story_index = source.story_index + 1``.
    """

    def __init__(self, document: Any, source: Any, target: Any) -> None:
        self.document = document
        self.source = source
        self.target = target
        self._prev_story_ref: Any = None
        self._prev_story_index: int = 0

    def redo(self) -> None:
        self._prev_story_ref = getattr(self.target, "story_ref", None)
        self._prev_story_index = getattr(self.target, "story_index", 0)
        self.target.story_ref = self.source.story_ref
        self.target.story_index = getattr(self.source, "story_index", 0) + 1

    def undo(self) -> None:
        self.target.story_ref = self._prev_story_ref
        self.target.story_index = self._prev_story_index


class _StubMergeStoriesCommand:
    """``MergeStoriesCommand`` stub.

    Used when the user links two frames where the target already has its own
    non-empty story: the dialog confirms, and this command appends target's
    blocks onto source's story before relinking.
    """

    def __init__(self, document: Any, source: Any, target: Any) -> None:
        self.document = document
        self.source = source
        self.target = target
        self._prev_story_ref: Any = None
        self._prev_story_index: int = 0
        self._appended_blocks: list[Any] = []

    def redo(self) -> None:
        self._prev_story_ref = getattr(self.target, "story_ref", None)
        self._prev_story_index = getattr(self.target, "story_index", 0)
        target_story = self.target.story_ref
        source_story = self.source.story_ref
        if target_story is not None and source_story is not None:
            self._appended_blocks = list(getattr(target_story, "blocks", []))
            source_story.blocks.extend(self._appended_blocks)
        self.target.story_ref = source_story
        self.target.story_index = getattr(self.source, "story_index", 0) + 1

    def undo(self) -> None:
        source_story = self.source.story_ref
        if source_story is not None and self._appended_blocks:
            n = len(self._appended_blocks)
            del source_story.blocks[-n:]
        self.target.story_ref = self._prev_story_ref
        self.target.story_index = self._prev_story_index


class _StubUnlinkFrameCommand:
    """``UnlinkFrameCommand`` stub: detach a frame from its story chain."""

    def __init__(self, document: Any, frame: Any) -> None:
        self.document = document
        self.frame = frame
        self._prev_story_ref: Any = None
        self._prev_story_index: int = 0

    def redo(self) -> None:
        self._prev_story_ref = getattr(self.frame, "story_ref", None)
        self._prev_story_index = getattr(self.frame, "story_index", 0)
        self.frame.story_ref = None
        self.frame.story_index = 0

    def undo(self) -> None:
        self.frame.story_ref = self._prev_story_ref
        self.frame.story_index = self._prev_story_index


# ---------------------------------------------------------------------------
# Canvas stub (unit 16)
# ---------------------------------------------------------------------------


class StubCanvas:
    """Lightweight in-memory canvas mirroring the ``CanvasLike`` surface.

    Used by unit-21's tests; also a sensible default when the real
    ``CanvasView`` (unit 16) hasn't been wired in yet.
    """

    def __init__(self) -> None:
        self.document: Any = Document()
        page = Page()
        self.document.pages.append(page)
        self.current_page: Any = page
        self.active_tool: Any = None
        self.drag_mode: QGraphicsView.DragMode = QGraphicsView.DragMode.NoDrag
        self.selected: list[Any] = []
        self.executed_commands: list[Any] = []
        self.recompose_calls: int = 0
        # Optional preview overlays a tool may install (e.g. linker preview line).
        self.overlays: list[Any] = []

    def set_tool(self, tool: Any) -> None:
        if self.active_tool is not None and self.active_tool is not tool:
            self.active_tool.deactivate()
        self.active_tool = tool
        tool.activate(self)

    def viewport_drag_mode(self, mode: QGraphicsView.DragMode) -> None:
        self.drag_mode = mode

    def push_command(self, command: Any) -> None:
        self.executed_commands.append(command)
        if hasattr(command, "redo"):
            command.redo()

    def recompose(self) -> None:
        """Recompose hook the linker calls after a successful link."""
        self.recompose_calls += 1

    def add_overlay(self, item: Any) -> None:
        self.overlays.append(item)

    def remove_overlay(self, item: Any) -> None:
        if item in self.overlays:
            self.overlays.remove(item)


# ---------------------------------------------------------------------------
# Dynamic resolution: prefer real symbols if their providing unit has landed.
# ---------------------------------------------------------------------------


def _resolve(module_path: str, name: str, fallback: Any) -> Any:
    try:
        module = importlib.import_module(module_path)
    except ImportError:  # pragma: no cover - module is always importable here
        return fallback
    return getattr(module, name, fallback)


# Tool ABC: prefer unit-20's real Tool if present.
Tool: Any = _resolve("msword.ui.tools.base", "Tool", _StubTool)

# Model: real symbols land in ``msword.model``; fall back to stubs.
Document: Any = _resolve("msword.model", "Document", _StubDocument)
Page: Any = _resolve("msword.model", "Page", _StubPage)
Frame: Any = _resolve("msword.model", "Frame", _StubFrame)
TextFrame: Any = _resolve("msword.model", "TextFrame", _StubTextFrame)
TableFrame: Any = _resolve("msword.model", "TableFrame", _StubTableFrame)
Story: Any = _resolve("msword.model", "Story", _StubStory)

# Commands: real symbols land in ``msword.commands``; fall back to stubs.
AddFrameCommand: Any = _resolve("msword.commands", "AddFrameCommand", _StubAddFrameCommand)
LinkFrameCommand: Any = _resolve("msword.commands", "LinkFrameCommand", _StubLinkFrameCommand)
MergeStoriesCommand: Any = _resolve(
    "msword.commands", "MergeStoriesCommand", _StubMergeStoriesCommand
)
UnlinkFrameCommand: Any = _resolve("msword.commands", "UnlinkFrameCommand", _StubUnlinkFrameCommand)


__all__ = [
    "AddFrameCommand",
    "Document",
    "Frame",
    "LinkFrameCommand",
    "MergeStoriesCommand",
    "Page",
    "Story",
    "StubCanvas",
    "TableFrame",
    "TextFrame",
    "Tool",
    "UnlinkFrameCommand",
]
