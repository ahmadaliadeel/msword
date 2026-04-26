"""Local stubs for sibling units (Document, Page, Frame, AddFrameCommand) and
a ``StubCanvas`` for unit-local testing.

Per spec §12.1: "Units that need a dependency stub it locally (a minimal mock
implementing the interface) until the providing unit lands." The real
implementations live in ``msword.model.*``, ``msword.commands.*`` and
``msword.ui.canvas.*`` and will replace these stubs once units 2-9 and 16 land.

We import the real names if they exist, otherwise fall back to the stubs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QGraphicsView

if TYPE_CHECKING:
    from PySide6.QtCore import QRectF

    from msword.ui.tools.base import Tool


@dataclass
class _StubFrame:
    """Minimal Frame stub: rectangular geometry + a kind discriminator."""

    x: float
    y: float
    w: float
    h: float
    kind: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class _StubPage:
    """Minimal Page stub: holds an ordered list of frames."""

    frames: list[_StubFrame] = field(default_factory=list)


@dataclass
class _StubDocument:
    """Minimal Document stub: holds an ordered list of pages."""

    pages: list[_StubPage] = field(default_factory=list)


class _StubAddFrameCommand:
    """Minimal AddFrameCommand stub.

    Real version (unit 9) will subclass ``QUndoCommand`` and route through the
    document's undo stack. The stub records the frame's geometry/kind so tests
    can assert on the parameters the tool computed.
    """

    def __init__(
        self,
        document: _StubDocument,
        page: _StubPage,
        rect: QRectF,
        kind: str,
        **extra: Any,
    ) -> None:
        self.document = document
        self.page = page
        self.rect = rect
        self.kind = kind
        self.extra = extra
        self._frame: _StubFrame | None = None

    def redo(self) -> None:
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


class StubCanvas:
    """Lightweight in-memory canvas that satisfies ``CanvasLike``.

    Used by the integration tests for this unit and as a default carry for
    ``ToolsPalette`` in environments where the real ``CanvasView`` (unit 16)
    isn't constructed yet.
    """

    def __init__(self) -> None:
        self.document: Any = Document()
        page = Page()
        self.document.pages.append(page)
        self.current_page: Any = page
        self.active_tool: Tool | None = None
        self.drag_mode: QGraphicsView.DragMode = QGraphicsView.DragMode.NoDrag
        self.selected: list[Any] = []
        self.executed_commands: list[Any] = []

    def set_tool(self, tool: Tool) -> None:
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


def _resolve(module_path: str, name: str, fallback: Any) -> Any:
    """Return ``module.name`` if the providing unit has landed, else ``fallback``."""
    import importlib

    try:
        module = importlib.import_module(module_path)
    except ImportError:  # pragma: no cover - module is always importable in this repo
        return fallback
    return getattr(module, name, fallback)


AddFrameCommand: Any = _resolve("msword.commands", "AddFrameCommand", _StubAddFrameCommand)
Document: Any = _resolve("msword.model", "Document", _StubDocument)
Page: Any = _resolve("msword.model", "Page", _StubPage)
Frame: Any = _resolve("msword.model", "Frame", _StubFrame)


__all__ = [
    "AddFrameCommand",
    "Document",
    "Frame",
    "Page",
    "StubCanvas",
]
