"""Layout types for the text composer (spec §5).

These are pure data containers consumed by the canvas renderer.  They are
deliberately decoupled from Qt's mutable layout objects: a `LayoutLine` is the
result of running `QTextLayout` over a paragraph and laying the resulting lines
into frame columns.

Stubs for ``Run`` / ``ParagraphSpec`` / ``Story`` / ``TextFrame`` /
``ParagraphStyle`` / ``StyleResolver`` are provided locally so this unit can
ship independently of model units 4, 5 and 8 (per spec §12.1: "Units that need
a dependency stub it locally [...] until the providing unit lands").  Once
those units land, the stubs are replaced by real imports without changing the
composer's public surface.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Protocol

from PySide6.QtCore import QRectF

# ---------------------------------------------------------------------------
# Public layout-output types (consumed by the renderer in unit 16).
# ---------------------------------------------------------------------------

Direction = Literal["ltr", "rtl"]


@dataclass(frozen=True, slots=True)
class GlyphRun:
    """A contiguous run of shaped glyphs sharing a font + style.

    Offsets are character offsets into the paragraph's source text (NOT into
    the story).  ``advance`` is the *visual* advance width of the run in
    points.
    """

    start: int
    end: int
    font_family: str
    font_size_pt: float
    color_ref: str | None
    x_offset: float
    advance: float
    direction: Direction


@dataclass(frozen=True, slots=True)
class LayoutLine:
    """One placed line of text within a frame's column."""

    frame_id: str
    column_index: int
    rect: QRectF
    baseline_y: float
    text: str
    glyph_runs: tuple[GlyphRun, ...]
    paragraph_style_ref: str | None
    block_id: str | None


@dataclass(frozen=True, slots=True)
class LayoutFrame:
    """Aggregated lines for a single text frame in a chain."""

    frame_id: str
    lines: tuple[LayoutLine, ...]


@dataclass(frozen=True, slots=True)
class OverflowResult:
    """Outcome of composing a story into a frame chain.

    ``last_paragraph_index`` / ``last_glyph_offset`` describe the cursor at
    which composition stopped: when ``overflow`` is ``True`` the renderer
    surfaces the red ``+`` indicator and an editor can resume composition into
    a follow-on chain via :meth:`FrameComposer.compose_from`.
    """

    lines: tuple[LayoutLine, ...]
    last_paragraph_index: int
    last_glyph_offset: int
    overflow: bool
    overflow_block_id: str | None = None
    frames: tuple[LayoutFrame, ...] = ()


# ---------------------------------------------------------------------------
# Local stubs for model types we do not own.  Real units replace these.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Run:
    """Stub for ``msword.model.run.Run``.

    ``length`` is the number of UTF-16 code units (Qt's measure) the run
    contributes; for the composer we treat it as character count.  When the
    real model lands the composer will call ``run.text_length`` instead.
    """

    text: str
    font_family: str = "Sans Serif"
    font_size_pt: float = 12.0
    bold: bool = False
    italic: bool = False
    color_ref: str | None = None


@dataclass(frozen=True, slots=True)
class ParagraphStyle:
    """Stub for ``msword.model.style.ParagraphStyle``."""

    name: str = "Default"
    line_height: float | None = None  # explicit leading in points; None = auto
    space_before: float = 0.0
    space_after: float = 0.0
    alignment: Literal["start", "end", "center", "justify"] = "start"


@dataclass(frozen=True, slots=True)
class ParagraphSpec:
    """One unit of work yielded by ``Story.iter_paragraphs()``.

    A block (paragraph, heading, list item, ...) is flattened by its block
    adapter into one or more ``ParagraphSpec``s.  The composer is intentionally
    block-agnostic: it sees only paragraphs.
    """

    block_id: str
    runs: tuple[Run, ...]
    style: ParagraphStyle
    text_direction: Direction = "ltr"
    paragraph_style_ref: str | None = None


class Story(Protocol):
    """Stub protocol for ``msword.model.story.Story``."""

    def iter_paragraphs(self) -> Iterable[ParagraphSpec]:
        ...


class TextFrame(Protocol):
    """Stub protocol for the subset of ``TextFrame`` the composer needs.

    A frame exposes its column rectangles directly — the geometry of columns
    + gutters is owned by the frame, not the composer.  ``text_direction``
    drives column-fill order: RTL frames place into the rightmost column
    first.
    """

    id: str
    text_direction: Direction

    def column_rects(self) -> list[QRectF]:
        """Return column rectangles in *visual* left-to-right order."""
        ...


__all__ = [
    "Direction",
    "GlyphRun",
    "LayoutFrame",
    "LayoutLine",
    "OverflowResult",
    "ParagraphSpec",
    "ParagraphStyle",
    "Run",
    "Story",
    "TextFrame",
]
