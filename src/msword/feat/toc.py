"""Table of contents generation, refresh, and live-update hook (unit #33).

Per spec §4 (block model) and §12 (work units), the TOC is a *managed story*:
its content is **derived** from the headings found while walking every story's
block tree in document order, and it updates automatically when those headings
change.

This module is intentionally self-contained. The data classes that model
``Document``/``Story``/``HeadingBlock``/``ParagraphBlock``/``Run`` and the
``Command``/``UndoStack`` types live in separate work units (#2-#9). To keep
this unit independently mergeable, we define minimal *stubs* here that match
the interfaces those units will expose. When the real types land they will be
import-compatible structurally — the call sites only rely on the small surface
defined below.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Stubs for sibling-unit types. Replace with real imports once those land.
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Run:
    """Inline run with text and optional marks (stub of unit #4 ``Run``)."""

    text: str
    marks: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PageRefRun:
    """A run that resolves to the page number containing ``target_block_id``.

    Initial display text is "?" until a renderer resolves it via
    :func:`resolve_page_refs`.
    """

    target_block_id: str
    text: str = "?"
    marks: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParagraphBlock:
    """Stub of unit #5 ``ParagraphBlock``."""

    id: str
    runs: list[Run | PageRefRun] = field(default_factory=list)
    paragraph_style_ref: str | None = None


@dataclass(slots=True)
class HeadingBlock:
    """Stub of unit #5 ``HeadingBlock``."""

    id: str
    level: int
    runs: list[Run] = field(default_factory=list)
    style_ref: str | None = None

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs)


# A "Block" for this unit is anything that exposes ``children`` (optional)
# and matches one of the concrete dataclasses above. The real BlockRegistry
# (unit #5) will extend this — until then we walk recursively via duck typing.
Block = ParagraphBlock | HeadingBlock | Any


@dataclass(slots=True)
class Story:
    """Stub of unit #4 ``Story``."""

    id: str
    blocks: list[Block] = field(default_factory=list)
    is_toc: bool = False


@dataclass(slots=True)
class UpdateTocCommand:
    """Stub of the unit #9 command that replaces a TOC story's blocks.

    Captures the previous block list so the command is reversible — the real
    ``UndoStack`` will call :meth:`undo` on the stored snapshot.
    """

    toc_story_id: str
    new_blocks: list[Block]
    previous_blocks: list[Block] = field(default_factory=list)

    def apply(self, document: Document) -> None:
        story = document.get_story(self.toc_story_id)
        self.previous_blocks = list(story.blocks)
        story.blocks = list(self.new_blocks)

    def undo(self, document: Document) -> None:
        story = document.get_story(self.toc_story_id)
        story.blocks = list(self.previous_blocks)


@dataclass(slots=True)
class UndoStack:
    """Stub of unit #9 ``UndoStack``."""

    commands: list[Any] = field(default_factory=list)

    def push(self, command: Any) -> None:
        self.commands.append(command)


@dataclass(slots=True)
class Document:
    """Stub of unit #2 ``Document`` covering only what TOC needs."""

    stories: list[Story] = field(default_factory=list)
    undo_stack: UndoStack = field(default_factory=UndoStack)
    _heading_listeners: list[Callable[[], None]] = field(default_factory=list)
    _changed_listeners: list[Callable[[], None]] = field(default_factory=list)

    def get_story(self, story_id: str) -> Story:
        for story in self.stories:
            if story.id == story_id:
                return story
        raise KeyError(f"unknown story: {story_id}")

    # Signal-like API. Real Document (unit #2) will use Qt signals; the names
    # we subscribe to here are the contract.
    def on_heading_changed(self, listener: Callable[[], None]) -> None:
        self._heading_listeners.append(listener)

    def emit_heading_changed(self) -> None:
        for listener in self._heading_listeners:
            listener()

    def on_changed(self, listener: Callable[[], None]) -> None:
        self._changed_listeners.append(listener)

    def emit_changed(self) -> None:
        for listener in self._changed_listeners:
            listener()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TocSpec:
    """Configuration for TOC generation."""

    title: str = "Contents"
    levels: tuple[int, ...] = (1, 2, 3)
    tab_leader: str = "."
    style_per_level: dict[int, str] = field(default_factory=dict)


def _iter_blocks(blocks: Iterable[Block]) -> Iterator[Block]:
    """Walk a block tree in document order, descending into children."""
    for block in blocks:
        yield block
        children = getattr(block, "children", None)
        if children:
            yield from _iter_blocks(children)
        nested = getattr(block, "blocks", None)
        if nested and nested is not blocks:
            yield from _iter_blocks(nested)


def _collect_headings(document: Document, levels: tuple[int, ...]) -> list[HeadingBlock]:
    selected: list[HeadingBlock] = []
    wanted = set(levels)
    for story in document.stories:
        if story.is_toc:
            continue
        for block in _iter_blocks(story.blocks):
            if isinstance(block, HeadingBlock) and block.level in wanted:
                selected.append(block)
    return selected


def _entry_style(spec: TocSpec, level: int) -> str:
    return spec.style_per_level.get(level, f"TOC {level}")


def generate_toc_blocks(document: Document, spec: TocSpec) -> list[Block]:
    """Return the title heading + one TOC entry per qualifying heading.

    Each entry is a :class:`ParagraphBlock` whose runs are: the heading text,
    a literal tab-leader run (placeholder for a true expanding tab leader in a
    later milestone), and a :class:`PageRefRun` initially showing "?".
    """
    blocks: list[Block] = [
        HeadingBlock(
            id="toc-title",
            level=1,
            runs=[Run(text=spec.title)],
            style_ref="TOC Title",
        )
    ]
    for heading in _collect_headings(document, spec.levels):
        entry = ParagraphBlock(
            id=f"toc-entry-{heading.id}",
            paragraph_style_ref=_entry_style(spec, heading.level),
            runs=[
                Run(text=heading.text),
                Run(text=spec.tab_leader, marks={"role": "tab-leader"}),
                PageRefRun(target_block_id=heading.id),
            ],
        )
        blocks.append(entry)
    return blocks


def update_toc(
    document: Document, toc_story_id: str, spec: TocSpec | None = None
) -> UpdateTocCommand:
    """Recompute the TOC story's blocks; push a reversible command and return it."""
    effective_spec = spec if spec is not None else TocSpec()
    new_blocks = generate_toc_blocks(document, effective_spec)
    command = UpdateTocCommand(toc_story_id=toc_story_id, new_blocks=new_blocks)
    command.apply(document)
    document.undo_stack.push(command)
    return command


def resolve_page_refs(
    document: Document,
    toc_story_id: str,
    page_lookup: Callable[[str], int | None] | dict[str, int],
) -> None:
    """Populate :class:`PageRefRun` text from ``page_lookup``.

    ``page_lookup`` may be a dict (block-id → page) or a callable returning
    ``None`` for unresolved targets (which leaves the placeholder "?" alone).
    """
    lookup: Callable[[str], int | None] = (
        page_lookup.get if isinstance(page_lookup, dict) else page_lookup
    )
    story = document.get_story(toc_story_id)
    for block in story.blocks:
        if not isinstance(block, ParagraphBlock):
            continue
        for run in block.runs:
            if not isinstance(run, PageRefRun):
                continue
            page = lookup(run.target_block_id)
            if page is not None:
                run.text = str(page)


def _hash_headings(document: Document, levels: tuple[int, ...]) -> str:
    parts = [
        f"{h.level}\t{h.id}\t{h.text}"
        for h in _collect_headings(document, levels)
    ]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


@dataclass(slots=True)
class TocAutoUpdater:
    """Hook a TOC story to auto-refresh when headings change.

    Subscribes to :meth:`Document.on_heading_changed` if available; otherwise
    falls back to ``on_changed`` and detects heading-level diffs via a hash.
    Updates are debounced — repeated triggers within ``debounce_ms`` collapse
    to a single ``update_toc`` call once the timer fires.
    """

    document: Document
    toc_story_id: str
    spec: TocSpec = field(default_factory=TocSpec)
    debounce_ms: int = 500
    schedule: Callable[[Callable[[], None], int], Any] | None = None
    _pending: bool = False
    _last_hash: str = ""

    def install(self) -> None:
        self._last_hash = _hash_headings(self.document, self.spec.levels)
        if self._heading_signal_supported():
            self.document.on_heading_changed(self._on_heading_changed)
        else:
            self.document.on_changed(self._on_changed)

    def _heading_signal_supported(self) -> bool:
        # The real Document (unit #2) exposes a heading_changed signal; the
        # stub here always does, so we only fall back when overridden.
        return hasattr(self.document, "on_heading_changed")

    def _on_heading_changed(self) -> None:
        self._schedule_update()

    def _on_changed(self) -> None:
        new_hash = _hash_headings(self.document, self.spec.levels)
        if new_hash == self._last_hash:
            return
        self._last_hash = new_hash
        self._schedule_update()

    def _schedule_update(self) -> None:
        if self._pending:
            return
        self._pending = True
        if self.schedule is None:
            self._fire()
        else:
            self.schedule(self._fire, self.debounce_ms)

    def _fire(self) -> None:
        self._pending = False
        update_toc(self.document, self.toc_story_id, self.spec)
        self._last_hash = _hash_headings(self.document, self.spec.levels)
