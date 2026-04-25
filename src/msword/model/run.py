"""Stub `Run` for the measurements palette.

Real implementation lives in unit-4 (`model-story-and-runs`). The palette only
reads inline marks: bold/italic/underline/strike, font, size, leading, tracking,
alignment hint, OpenType feature set, paragraph-style ref.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Run:
    """Inline-styling unit stub."""

    text: str = ""
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    font_family: str = "Helvetica"
    size: float = 12.0
    leading: float = 14.4
    tracking: float = 0.0
    alignment: str = "left"  # left | center | right | justify
    paragraph_style_ref: str = "Body"
    opentype_features: set[str] = field(default_factory=set)
