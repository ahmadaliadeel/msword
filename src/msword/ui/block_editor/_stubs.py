"""Local stubs for sibling work units this unit depends on.

These shadow types live *only* inside ``ui/block_editor`` so the unit is
self-contained. Once the canonical implementations land:

* ``model/story.py`` (unit 4)         → real :class:`Story`
* ``model/block.py`` + ``blocks/``    → real block hierarchy (units 5-7)
* ``commands/`` (unit 9)              → real ``Command`` + concrete commands
* ``ui/canvas/text_frame_item.py``    → real :class:`TextFrameItem` (unit 16)

…the local stubs are removed and the imports re-pointed. Until then the
overlay + input-rule code can be exercised in tests without pulling in
those packages.

Keep the surface small: only what unit 28 needs to compile and run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QGraphicsItem

if TYPE_CHECKING:
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget


# ---------------------------------------------------------------------------
# Block model stubs (replaced by unit-5 / unit-6 / unit-7).
# ---------------------------------------------------------------------------


@dataclass
class _RunStub:
    """Minimal inline-run stub. Real ``Run`` lives in ``model/run.py``."""

    text: str = ""


@dataclass
class BlockStub:
    """Minimal Block stub.

    Mirrors the shape unit-28 needs:

    * ``id``        — opaque identifier (stable across sessions in the real model).
    * ``kind``      — discriminator string ("paragraph", "heading", "list", …).
    * ``runs``      — inline content; only inspected for emptiness here.
    * ``attrs``     — free-form per-kind attributes (heading level, list kind, …).
    """

    id: str
    kind: str = "paragraph"
    runs: list[_RunStub] = field(default_factory=list)
    attrs: dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        """An "empty paragraph" for Markdown-input-rule purposes."""
        return self.kind == "paragraph" and all(not r.text for r in self.runs)


@dataclass
class StoryStub:
    """Minimal Story stub. Real ``Story`` lives in ``model/story.py``."""

    id: str
    blocks: list[BlockStub] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Command stubs (replaced by unit-9 ``commands/``).
# ---------------------------------------------------------------------------


@dataclass
class CommandStub:
    """Minimal command base. Real ``Command`` integrates with ``QUndoStack``.

    ``name`` is a class-level discriminator the real undo stack will use
    to coalesce / merge commands. Subclasses set it; instances inherit.
    """

    name: ClassVar[str] = "command"


@dataclass
class MoveBlockCommand(CommandStub):
    """Move a block within its story from ``from_index`` to ``to_index``.

    Indices are *post-removal* targets — i.e. the block is conceptually
    removed at ``from_index`` first and then re-inserted at ``to_index``,
    matching Tiptap / ProseMirror move semantics.
    """

    name: ClassVar[str] = "move-block"
    story_id: str = ""
    from_index: int = 0
    to_index: int = 0


@dataclass
class TransformBlockCommand(CommandStub):
    """Convert a block to ``target_kind`` (optionally with attrs).

    Used by the right-click "Convert To…" submenu and by Markdown shortcuts.
    """

    name: ClassVar[str] = "transform-block"
    story_id: str = ""
    block_id: str = ""
    target_kind: str = "paragraph"
    target_attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class DuplicateBlockCommand(CommandStub):
    name: ClassVar[str] = "duplicate-block"
    story_id: str = ""
    block_id: str = ""


@dataclass
class DeleteBlockCommand(CommandStub):
    name: ClassVar[str] = "delete-block"
    story_id: str = ""
    block_id: str = ""


# ---------------------------------------------------------------------------
# TextFrameItem stub (replaced by unit-16 ``ui/canvas/text_frame_item.py``).
# ---------------------------------------------------------------------------


class TextFrameItemStub(QGraphicsItem):
    """Minimal QGraphicsItem standing in for the real TextFrameItem.

    Provides only what the handles overlay needs:

    * a bounding rect,
    * a list of *block regions* (rect + block id) — the real frame derives
      these from layout output, this stub takes them by hand,
    * a back-reference to the story (so the overlay can dispatch commands
      that target it).
    """

    def __init__(
        self,
        story: StoryStub,
        size: tuple[float, float] = (400.0, 600.0),
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAcceptHoverEvents(True)
        self._story = story
        self._size = size
        self._block_regions: list[tuple[str, QRectF]] = []

    @property
    def story(self) -> StoryStub:
        return self._story

    def set_block_regions(self, regions: list[tuple[str, QRectF]]) -> None:
        """Set ``[(block_id, rect_in_local_coords), …]`` for hit-testing."""
        self._block_regions = list(regions)
        self.update()

    def block_regions(self) -> list[tuple[str, QRectF]]:
        return list(self._block_regions)

    # QGraphicsItem API ---------------------------------------------------

    def boundingRect(self) -> QRectF:
        w, h = self._size
        # Include negative-x slack so the left-margin handle is inside our
        # bounding rect (otherwise it won't get hover events).
        return QRectF(-32.0, 0.0, w + 32.0, h)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        """No-op — the real frame paints body text."""
        return None
