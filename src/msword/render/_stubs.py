"""Local stubs for the model & layout types this unit consumes.

Per spec §12.1 — units stub their dependencies locally with minimal mocks
implementing the interfaces, until the providing unit lands. These stubs
are intentionally tiny and will be replaced by the real model classes
(units #2-7) and the real composer (unit #13) without requiring changes
to ``pdf.py`` or ``_painter.py``.

Geometry units throughout this module are PostScript points (1/72 in).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------


@dataclass
class _FrameBase:
    """Common frame fields per spec §4.1."""

    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    rotation: float = 0.0
    skew: float = 0.0
    z_order: int = 0
    locked: bool = False
    visible: bool = True


@dataclass
class TextFrame(_FrameBase):
    """A text frame stub.

    The story is held inline as a plain string for simplicity until the
    real model lands. ``columns`` and ``gutter`` follow the spec.
    """

    story: str = ""
    columns: int = 1
    gutter: float = 12.0
    text_direction: Literal["ltr", "rtl"] = "ltr"
    font_family: str = "Helvetica"
    font_size_pt: float = 11.0
    color: tuple[int, int, int] = (0, 0, 0)


@dataclass
class ImageFrame(_FrameBase):
    """An image frame stub.

    ``image_bytes`` is the raw, encoded source (PNG/JPEG/etc.); embedded
    at native resolution by the painter.
    """

    image_bytes: bytes = b""


@dataclass
class ShapeFrame(_FrameBase):
    """A shape frame stub.

    ``kind`` selects the geometric primitive painted via ``QPainterPath``.
    """

    kind: Literal["rect", "ellipse", "round_rect"] = "rect"
    corner_radius: float = 0.0
    stroke: tuple[int, int, int] | None = (0, 0, 0)
    stroke_width_pt: float = 1.0
    fill: tuple[int, int, int] | None = None


@dataclass
class TableFrame(_FrameBase):
    """A table frame stub.

    ``cells`` is a row-major matrix of cell text. The painter draws a
    uniform grid plus the cell text — sufficient to validate the seam.
    """

    rows: int = 0
    cols: int = 0
    cells: list[list[str]] = field(default_factory=list)
    grid_color: tuple[int, int, int] = (0, 0, 0)
    grid_width_pt: float = 0.5
    font_family: str = "Helvetica"
    font_size_pt: float = 10.0


Frame: TypeAlias = TextFrame | ImageFrame | ShapeFrame | TableFrame


# ---------------------------------------------------------------------------
# Pages & Document
# ---------------------------------------------------------------------------


@dataclass
class Page:
    """A page stub."""

    width_pt: float = 595.0  # A4 width in points
    height_pt: float = 842.0  # A4 height in points
    bleed_pt: float = 0.0
    frames: list[Frame] = field(default_factory=list)


@dataclass
class Document:
    """A document stub."""

    pages: list[Page] = field(default_factory=list)
    title: str = ""
    author: str = ""


# ---------------------------------------------------------------------------
# Layout / composer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LayoutLine:
    """A single laid-out line of text (composer output).

    Coordinates are in points, relative to the frame's origin.
    """

    text: str
    x: float
    y: float  # baseline y (top-down origin)
    font_family: str
    font_size_pt: float
    color: tuple[int, int, int] = (0, 0, 0)


@dataclass(frozen=True)
class OverflowResult:
    """Composer output: lines placed in the supplied frames + overflow flag."""

    lines_per_frame: list[list[LayoutLine]]
    overflowed: bool = False


class FrameComposer:
    """Synthetic stub composer.

    Real composer (unit #13) shapes via ``QTextLayout`` with HarfBuzz/ICU.
    This stub produces deterministic synthetic lines: one line per
    paragraph, fitting top-down by leading, dropping overflow.
    """

    @staticmethod
    def compose(story: str, frames: list[TextFrame]) -> OverflowResult:
        if not frames:
            return OverflowResult(lines_per_frame=[], overflowed=bool(story))

        paragraphs = [p for p in story.split("\n") if p]
        lines_per_frame: list[list[LayoutLine]] = [[] for _ in frames]
        overflowed = False
        para_idx = 0

        for f_idx, frame in enumerate(frames):
            leading = frame.font_size_pt * 1.2
            top_padding = frame.font_size_pt
            cursor_y = top_padding
            while para_idx < len(paragraphs) and cursor_y + leading <= frame.h:
                lines_per_frame[f_idx].append(
                    LayoutLine(
                        text=paragraphs[para_idx],
                        x=0.0,
                        y=cursor_y,
                        font_family=frame.font_family,
                        font_size_pt=frame.font_size_pt,
                        color=frame.color,
                    )
                )
                cursor_y += leading
                para_idx += 1

        if para_idx < len(paragraphs):
            overflowed = True

        return OverflowResult(lines_per_frame=lines_per_frame, overflowed=overflowed)
