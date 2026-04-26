"""Frame composer (spec §5).

Walks the paragraphs of a :class:`Story`, shapes each one with
``QTextLayout`` (HarfBuzz + ICU under the hood, so Bidi/Arabic/Urdu just
work) and lays the resulting lines into a chain of linked frames.  Columns
within a frame are filled in visual order; in an RTL frame the rightmost
column is filled first.

Public surface (consumed by the canvas renderer in unit 16 and incremental
re-layout in higher units):

* :class:`FrameComposer`
* :meth:`FrameComposer.compose` — fresh composition.
* :meth:`FrameComposer.compose_from` — resume composition mid-story
  (used both by chain-overflow and by incremental re-layout when a single
  paragraph changes and we ripple from there per spec §5).

The composer never mutates the model; it returns immutable
:class:`OverflowResult` snapshots.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QFont,
    QFontMetricsF,
    QTextLayout,
    QTextOption,
)

from msword.layout._qt_helpers import (
    build_font,
    build_format_ranges,
    column_visual_order,
    paragraph_text,
    split_line_into_glyph_runs,
)
from msword.layout.types import (
    Direction,
    LayoutFrame,
    LayoutLine,
    OverflowResult,
    ParagraphSpec,
    ParagraphStyle,
    Run,
    Story,
    TextFrame,
)


@dataclass
class _Cursor:
    """Mutable state used while filling a frame chain."""

    frame_idx: int
    column_order: list[int]
    column_pos: int  # index *into* ``column_order``
    y: float  # next baseline-eligible y, in frame-local coords (top of next line)

    @property
    def column_index(self) -> int:
        return self.column_order[self.column_pos]


class FrameComposer:
    """Compose a story into a chain of linked text frames.

    The composer is stateless beyond per-call locals; instances are cheap and
    safe to share across threads as long as Qt object construction is on the
    GUI thread (a hard Qt rule, not ours).
    """

    def compose(
        self,
        story: Story,
        frame_chain: list[TextFrame],
    ) -> OverflowResult:
        """Compose ``story`` from the start into ``frame_chain``."""
        return self.compose_from(
            story,
            frame_chain,
            start_block_index=0,
            start_offset=0,
        )

    def compose_from(
        self,
        story: Story,
        frame_chain: list[TextFrame],
        *,
        start_block_index: int,
        start_offset: int,
    ) -> OverflowResult:
        """Compose ``story`` starting at paragraph ``start_block_index``,
        glyph offset ``start_offset`` within that paragraph.

        Returning an :class:`OverflowResult` whose ``overflow`` flag is
        ``True`` means the chain was exhausted before the story ended; the
        caller can repeat the call against a follow-on chain to continue
        flowing text.
        """
        if not frame_chain:
            return OverflowResult(
                lines=(),
                last_paragraph_index=start_block_index,
                last_glyph_offset=start_offset,
                overflow=True,
                overflow_block_id=None,
                frames=(),
            )

        paragraphs: list[ParagraphSpec] = list(story.iter_paragraphs())
        all_lines: list[LayoutLine] = []
        per_frame_lines: dict[str, list[LayoutLine]] = {f.id: [] for f in frame_chain}

        # Initialise cursor at the first column of the first frame.
        cursor = self._start_cursor(frame_chain, 0)

        para_idx = start_block_index
        offset_into_para = start_offset
        overflowed = False
        overflow_block_id: str | None = None
        last_para_idx = start_block_index
        last_offset = start_offset

        while para_idx < len(paragraphs):
            spec = paragraphs[para_idx]
            try:
                placed_offset = self._place_paragraph(
                    spec=spec,
                    start_offset=offset_into_para,
                    frame_chain=frame_chain,
                    cursor=cursor,
                    out_lines=all_lines,
                    per_frame_lines=per_frame_lines,
                )
            except _ChainExhausted as exc:
                overflowed = True
                overflow_block_id = spec.block_id
                last_para_idx = para_idx
                last_offset = exc.offset
                break

            last_para_idx = para_idx
            last_offset = placed_offset
            # Advance to next paragraph.
            para_idx += 1
            offset_into_para = 0

        if not overflowed:
            # Composition consumed all paragraphs; cursor sits one-past-end.
            last_para_idx = len(paragraphs)
            last_offset = 0

        frames_out = tuple(
            LayoutFrame(frame_id=f.id, lines=tuple(per_frame_lines[f.id]))
            for f in frame_chain
        )

        return OverflowResult(
            lines=tuple(all_lines),
            last_paragraph_index=last_para_idx,
            last_glyph_offset=last_offset,
            overflow=overflowed,
            overflow_block_id=overflow_block_id,
            frames=frames_out,
        )

    # ------------------------------------------------------------------ helpers

    def _start_cursor(
        self,
        frame_chain: list[TextFrame],
        frame_idx: int,
    ) -> _Cursor:
        frame = frame_chain[frame_idx]
        rects = frame.column_rects()
        order = column_visual_order(len(rects), frame.text_direction)
        first_rect = rects[order[0]] if order else QRectF()
        return _Cursor(
            frame_idx=frame_idx,
            column_order=order,
            column_pos=0,
            y=first_rect.top() if order else 0.0,
        )

    def _advance_cursor(
        self,
        frame_chain: list[TextFrame],
        cursor: _Cursor,
    ) -> None:
        """Advance to next column → next frame, or raise if chain exhausted."""
        cursor.column_pos += 1
        if cursor.column_pos < len(cursor.column_order):
            new_rect = frame_chain[cursor.frame_idx].column_rects()[cursor.column_index]
            cursor.y = new_rect.top()
            return
        # Out of columns; advance to next frame.
        cursor.frame_idx += 1
        if cursor.frame_idx >= len(frame_chain):
            raise _ChainExhausted(offset=-1)
        frame = frame_chain[cursor.frame_idx]
        rects = frame.column_rects()
        cursor.column_order = column_visual_order(len(rects), frame.text_direction)
        cursor.column_pos = 0
        cursor.y = rects[cursor.column_order[0]].top() if cursor.column_order else 0.0

    def _place_paragraph(
        self,
        *,
        spec: ParagraphSpec,
        start_offset: int,
        frame_chain: list[TextFrame],
        cursor: _Cursor,
        out_lines: list[LayoutLine],
        per_frame_lines: dict[str, list[LayoutLine]],
    ) -> int:
        """Place lines for one paragraph; return the offset reached.

        Raises :class:`_ChainExhausted` (with the last placed offset) if the
        chain runs out before the paragraph completes.
        """
        text = paragraph_text(spec)
        if start_offset > 0:
            # Resuming inside this paragraph: shape only the remainder.
            text = text[start_offset:]
        if not text:
            return start_offset  # empty paragraph — nothing to lay out

        layout = QTextLayout(text)
        layout.setCacheEnabled(False)
        # Per-paragraph option drives Bidi base direction and alignment.
        opt = QTextOption()
        opt.setTextDirection(
            Qt.LayoutDirection.RightToLeft
            if spec.text_direction == "rtl"
            else Qt.LayoutDirection.LeftToRight
        )
        opt.setUseDesignMetrics(True)
        layout.setTextOption(opt)

        # Apply per-run formatting.  We re-base offsets when resuming inside a
        # paragraph: format ranges always describe the *layout's* text, which
        # may be a suffix of the paragraph's source text.
        ranges = _shift_format_ranges(build_format_ranges(spec), -start_offset, len(text))
        if ranges:
            layout.setFormats(ranges)

        # Default font, used for line metrics when no run formatting applies.
        default_font = build_font(spec.runs[0]) if spec.runs else QFont()
        metrics = QFontMetricsF(default_font)
        line_height = (
            spec.style.line_height
            if spec.style.line_height is not None
            else metrics.height()
        )
        ascent = metrics.ascent()

        layout.beginLayout()
        try:
            offset_in_text = 0  # cursor in the *shaped* text (suffix)
            while True:
                line = layout.createLine()
                if not line.isValid():
                    break

                # Determine the column rect & remaining vertical space.
                while True:
                    rect = frame_chain[cursor.frame_idx].column_rects()[
                        cursor.column_index
                    ]
                    if cursor.y + line_height <= rect.bottom() + 1e-6:
                        break
                    # Line doesn't fit in current column — advance.
                    try:
                        self._advance_cursor(frame_chain, cursor)
                    except _ChainExhausted:
                        # Re-raise with the offset at which we stopped.  The
                        # offset is in *paragraph-local* coordinates.
                        stopped_at = start_offset + offset_in_text
                        raise _ChainExhausted(offset=stopped_at) from None

                line.setLineWidth(rect.width())
                # Position the line at top of the available column slot.
                line.setPosition(QPointF(rect.left(), cursor.y))

                line_text_start = line.textStart()
                line_text_length = line.textLength()
                line_text = text[
                    line_text_start : line_text_start + line_text_length
                ]
                line_natural_width = line.naturalTextWidth()

                rtl_pad = (
                    rect.width() - line_natural_width
                    if spec.text_direction == "rtl"
                    else 0.0
                )
                glyph_runs = split_line_into_glyph_runs(
                    spec=spec,
                    line_start=start_offset + line_text_start,
                    line_length=line_text_length,
                    line_x=rect.left() + rtl_pad,
                    direction=spec.text_direction,
                    line_advance=line_natural_width,
                )

                placed = LayoutLine(
                    frame_id=frame_chain[cursor.frame_idx].id,
                    column_index=cursor.column_index,
                    rect=QRectF(rect.left(), cursor.y, rect.width(), line_height),
                    baseline_y=cursor.y + ascent,
                    text=line_text,
                    glyph_runs=glyph_runs,
                    paragraph_style_ref=spec.paragraph_style_ref,
                    block_id=spec.block_id,
                )
                out_lines.append(placed)
                per_frame_lines[placed.frame_id].append(placed)

                cursor.y += line_height
                offset_in_text = line_text_start + line_text_length
        finally:
            layout.endLayout()

        return start_offset + offset_in_text


def _shift_format_ranges(
    ranges: list[QTextLayout.FormatRange],
    delta: int,
    layout_length: int,
) -> list[QTextLayout.FormatRange]:
    """Shift + clip format ranges when resuming inside a paragraph."""
    if delta == 0:
        return ranges
    out: list[QTextLayout.FormatRange] = []
    for fr in ranges:
        new_start = fr.start + delta
        new_end = new_start + fr.length
        if new_end <= 0 or new_start >= layout_length:
            continue
        clipped_start = max(0, new_start)
        clipped_end = min(layout_length, new_end)
        new = QTextLayout.FormatRange()
        new.start = clipped_start
        new.length = clipped_end - clipped_start
        new.format = fr.format
        out.append(new)
    return out


class _ChainExhausted(Exception):
    """Raised internally when the frame chain has no more room."""

    def __init__(self, offset: int) -> None:
        super().__init__("frame chain exhausted")
        self.offset = offset


# Used by tests: a tiny in-memory frame.
@dataclass
class StubTextFrame:
    """Minimal :class:`TextFrame` impl for tests / standalone use.

    Real ``TextFrame`` lives in unit 3.  This fits the same protocol shape and
    is what the composer's test suite drives.
    """

    id: str
    rect: QRectF
    columns: int = 1
    gutter: float = 0.0
    text_direction: Direction = "ltr"

    def column_rects(self) -> list[QRectF]:
        if self.columns <= 1:
            return [QRectF(self.rect)]
        gutter_total = self.gutter * (self.columns - 1)
        col_width = (self.rect.width() - gutter_total) / self.columns
        rects: list[QRectF] = []
        for i in range(self.columns):
            x = self.rect.left() + i * (col_width + self.gutter)
            rects.append(QRectF(x, self.rect.top(), col_width, self.rect.height()))
        return rects


@dataclass
class StubStory:
    """Minimal :class:`Story` impl for tests."""

    paragraphs: list[ParagraphSpec]

    def iter_paragraphs(self) -> Iterable[ParagraphSpec]:
        return iter(self.paragraphs)


def make_paragraph(
    text: str,
    *,
    block_id: str = "p0",
    direction: Direction = "ltr",
    font_family: str = "Sans Serif",
    font_size_pt: float = 12.0,
    line_height: float | None = None,
    paragraph_style_ref: str | None = None,
) -> ParagraphSpec:
    """Convenience factory used by tests and small demos."""
    return ParagraphSpec(
        block_id=block_id,
        runs=(Run(text=text, font_family=font_family, font_size_pt=font_size_pt),),
        style=ParagraphStyle(line_height=line_height),
        text_direction=direction,
        paragraph_style_ref=paragraph_style_ref,
    )


__all__ = [
    "FrameComposer",
    "StubStory",
    "StubTextFrame",
    "make_paragraph",
]
