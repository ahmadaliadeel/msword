"""Tool ABC and shared types for the tools palette.

Per spec §9, tools are *modal*: selecting a tool changes click semantics on the
canvas. The tool framework is intentionally narrow — a tool reacts to mouse and
key events forwarded by the canvas, and any document mutation is performed via
a Command on the document's UndoStack (per spec §3, Document-MVC).

Sibling units provide the canvas, document, and command infrastructure. To keep
this unit independently testable (per spec §12.1), we depend only on a
``CanvasLike`` protocol defined here plus minimal local stubs in ``_stubs``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QKeyEvent, QMouseEvent
    from PySide6.QtWidgets import QGraphicsView


class CanvasLike(Protocol):
    """Minimal canvas surface a tool talks to.

    The real ``CanvasView`` (unit 16) implements this and more; tests in this
    unit use the lightweight ``StubCanvas`` in ``_stubs``.
    """

    def set_tool(self, tool: Tool) -> None: ...

    def viewport_drag_mode(self, mode: QGraphicsView.DragMode) -> None: ...

    @property
    def document(self) -> Any: ...

    @property
    def current_page(self) -> Any: ...

    def push_command(self, command: Any) -> None: ...


class Tool:
    """Base class for modal canvas tools.

    Subclasses declare static identity (``name``, ``icon_name``, ``cursor``) and
    override the event hooks they care about. The default implementations are
    no-ops so concrete tools only override what they need.

    This is a regular class rather than an ABC: every method has a sensible
    no-op default, and tests construct ``Tool`` subclasses without further
    boilerplate.
    """

    #: Stable identifier used for action text, tooltips, and tests.
    name: str = ""
    #: Logical icon name; resolved by the palette to a QIcon (or a fallback).
    icon_name: str = ""
    #: Cursor shape applied to the canvas viewport while the tool is active.
    cursor: Qt.CursorShape = Qt.CursorShape.ArrowCursor

    def __init__(self) -> None:
        self._canvas: CanvasLike | None = None

    @property
    def canvas(self) -> CanvasLike | None:
        return self._canvas

    def activate(self, canvas: CanvasLike) -> None:
        """Called when this tool becomes active on ``canvas``."""
        self._canvas = canvas

    def deactivate(self) -> None:
        """Called when this tool is replaced by another tool."""
        self._canvas = None

    def on_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        """Mouse press hook. Default: no-op."""

    def on_mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        """Mouse move hook. Default: no-op."""

    def on_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        """Mouse release hook. Default: no-op."""

    def on_key_press(self, event: QKeyEvent) -> None:
        """Key press hook. Default: no-op."""
