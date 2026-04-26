"""Text-layout pipeline (spec §5).

The composer is the v1 pipeline; :mod:`msword.layout.knuth_plass` (unit 14)
will land an opt-in optimal-line-break alternative.
"""

from __future__ import annotations

from msword.layout.composer import FrameComposer, StubStory, StubTextFrame, make_paragraph
from msword.layout.types import (
    Direction,
    GlyphRun,
    LayoutFrame,
    LayoutLine,
    OverflowResult,
    ParagraphSpec,
    ParagraphStyle,
    Run,
    Story,
    TextFrame,
)

__all__ = [
    "Direction",
    "FrameComposer",
    "GlyphRun",
    "LayoutFrame",
    "LayoutLine",
    "OverflowResult",
    "ParagraphSpec",
    "ParagraphStyle",
    "Run",
    "Story",
    "StubStory",
    "StubTextFrame",
    "TextFrame",
    "make_paragraph",
]
