"""Local stubs for model / layout / command interfaces this unit depends on.

The full implementations land in their own work units (see spec §12). Until
those land we ship a minimal, behaviour-compatible mock so the canvas unit
can be implemented, tested, and merged in isolation.

These stubs intentionally implement only what `ui/canvas` reads. They are not
part of the public surface — siblings should depend on the real packages
(`msword.model`, `msword.layout`, `msword.commands`) once those are merged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

# A4 at 72 dpi (Quark / InDesign default; one point = 1 unit in scene coords).
A4_WIDTH = 595.0
A4_HEIGHT = 842.0


class FrameKind(Enum):
    TEXT = "text"
    IMAGE = "image"
    SHAPE = "shape"
    TABLE = "table"


class ShapeKind(Enum):
    RECT = "rect"
    OVAL = "oval"
    LINE = "line"


class ViewMode(Enum):
    PAGED = "paged"
    FLOW = "flow"


@dataclass
class LayoutLine:
    """A single composed line ready for rendering.

    `text` is already shaped — at the canvas layer we treat it as opaque and
    simply hand it to `QPainter.drawText`.
    """

    text: str
    x: float  # frame-local x of the line's left edge
    y: float  # frame-local baseline y
    width: float
    column_index: int = 0


@dataclass
class OverflowResult:
    """What the composer produces for one frame."""

    lines: list[LayoutLine] = field(default_factory=list)
    overflowed: bool = False


@dataclass
class Story:
    """A linked-frame text container. Stub: just carries placeholder text."""

    text: str = ""


@dataclass
class Frame:
    """Frame base — shared geometry + style hooks."""

    id: str
    kind: FrameKind
    x: float
    y: float
    w: float
    h: float
    rotation: float = 0.0
    locked: bool = False
    visible: bool = True
    z_order: int = 0


@dataclass
class TextFrame(Frame):
    """Text frame — references a story; multi-column."""

    story: Story | None = None
    columns: int = 1
    gutter: float = 12.0
    column_rule: bool = False


@dataclass
class ImageFrame(Frame):
    """Image frame — references an asset path; v1 supports fit-to-frame."""

    asset_path: str | None = None


@dataclass
class ShapeFrame(Frame):
    """Vector shape — rect / oval / line."""

    shape_kind: ShapeKind = ShapeKind.RECT
    stroke_width: float = 1.0


@dataclass
class TableFrame(Frame):
    """Table — uniform grid; cell content is placeholder text in the stub."""

    rows: int = 2
    cols: int = 2
    cells: list[list[str]] = field(default_factory=list)


@dataclass
class Page:
    """One page in the document.

    `bleed`, `margin`, and `column_count`/`column_gutter` drive the page
    chrome rendered by `PageItem`.
    """

    id: str
    width: float = A4_WIDTH
    height: float = A4_HEIGHT
    bleed: float = 9.0
    margin_top: float = 54.0
    margin_bottom: float = 54.0
    margin_left: float = 54.0
    margin_right: float = 54.0
    column_count: int = 1
    column_gutter: float = 12.0
    baseline_grid: float = 12.0
    show_baseline_grid: bool = True
    frames: list[Frame] = field(default_factory=list)


@dataclass
class Document:
    """Root of the model tree."""

    pages: list[Page] = field(default_factory=list)


# -- composer ---------------------------------------------------------------


class FrameComposer:
    """Synthetic composer for text frames.

    Real composer (unit 13) shapes paragraphs through `QTextLayout`. The stub
    fakes that by laying out the story text on a fixed leading, breaking by
    character count proportional to the column width. Overflow is reported
    when the synthetic line count exceeds available rows.
    """

    LEADING = 14.0
    AVG_GLYPH = 6.0  # approximate em advance for the stub font

    def compose(self, frame: TextFrame) -> OverflowResult:
        story = frame.story
        if story is None or not story.text:
            return OverflowResult(lines=[], overflowed=False)

        column_width = max(
            1.0,
            (frame.w - frame.gutter * (frame.columns - 1)) / max(1, frame.columns),
        )
        chars_per_line = max(1, int(column_width / self.AVG_GLYPH))
        rows_per_column = max(1, int(frame.h / self.LEADING))
        capacity = rows_per_column * frame.columns

        wrapped = list(_wrap_text(story.text, chars_per_line))
        result_lines: list[LayoutLine] = []
        for idx, text in enumerate(wrapped[:capacity]):
            col = idx // rows_per_column
            row = idx % rows_per_column
            x = col * (column_width + frame.gutter)
            y = (row + 1) * self.LEADING
            result_lines.append(
                LayoutLine(text=text, x=x, y=y, width=column_width, column_index=col)
            )
        overflowed = len(wrapped) > capacity
        return OverflowResult(lines=result_lines, overflowed=overflowed)


def _wrap_text(text: str, chars_per_line: int) -> Iterable[str]:
    """Word-wrap *text* to roughly *chars_per_line* characters per line."""

    for paragraph in text.splitlines() or [text]:
        if not paragraph:
            yield ""
            continue
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip() if current else word
            if len(candidate) <= chars_per_line:
                current = candidate
            else:
                if current:
                    yield current
                # If the word itself is longer than the line, hard-split it.
                while len(word) > chars_per_line:
                    yield word[:chars_per_line]
                    word = word[chars_per_line:]
                current = word
        if current:
            yield current


# -- commands ---------------------------------------------------------------


@dataclass
class MoveFrameCommand:
    """Stub for the real `Move` command landing in unit 9."""

    frame_id: str
    new_x: float
    new_y: float


@dataclass
class ResizeFrameCommand:
    """Stub for the real `Resize` command landing in unit 9."""

    frame_id: str
    new_w: float
    new_h: float
