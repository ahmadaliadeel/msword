"""Qt helpers for the text composer.

Kept separate from :mod:`msword.layout.composer` so unit tests can poke at the
small, deterministic pieces (font construction, format-range building,
direction-aware run extraction) without spinning up a full layout.
"""

from __future__ import annotations

from PySide6.QtGui import QFont, QTextCharFormat, QTextLayout

from msword.layout.types import Direction, GlyphRun, ParagraphSpec, Run


def build_font(run: Run) -> QFont:
    """Build a ``QFont`` configured from a model ``Run``."""
    font = QFont(run.font_family)
    font.setPointSizeF(run.font_size_pt)
    font.setBold(run.bold)
    font.setItalic(run.italic)
    # ``PreferDefault`` lets Qt's HarfBuzz path pick the best shaping engine
    # for the script (Latin, Arabic, Devanagari, ...).  This is what makes
    # Bidi + Arabic shaping work without any extra wiring.
    font.setStyleStrategy(QFont.StyleStrategy.PreferDefault)
    return font


def paragraph_text(spec: ParagraphSpec) -> str:
    """Concatenate run texts to form the paragraph's source string."""
    return "".join(r.text for r in spec.runs)


def build_format_ranges(spec: ParagraphSpec) -> list[QTextLayout.FormatRange]:
    """Translate per-run styling into ``QTextLayout.FormatRange``s.

    The composer uses these as the shaping input so kerning, ligatures and
    Bidi all cooperate with per-run font choices (e.g. an Arabic run inside a
    Latin paragraph).
    """
    ranges: list[QTextLayout.FormatRange] = []
    cursor = 0
    for run in spec.runs:
        length = len(run.text)
        if length == 0:
            continue
        fmt = QTextCharFormat()
        fmt.setFont(build_font(run))
        fr = QTextLayout.FormatRange()
        fr.start = cursor
        fr.length = length
        fr.format = fmt
        ranges.append(fr)
        cursor += length
    return ranges


def split_line_into_glyph_runs(
    spec: ParagraphSpec,
    line_start: int,
    line_length: int,
    line_x: float,
    direction: Direction,
    line_advance: float,
) -> tuple[GlyphRun, ...]:
    """Build :class:`GlyphRun`s spanning ``[line_start, line_start+line_length)``.

    The composer asks ``QTextLayout`` for the line's natural width and then
    asks each model ``Run`` how much of that width it owns; we apportion
    advance proportionally to character count.  This is good enough for the
    renderer's purposes (selection rectangles, hit-testing) and keeps us
    independent of platform-specific glyph metrics.

    For RTL lines the glyph runs are emitted in *visual* order: rightmost
    first, leftmost last.  This matches what the renderer wants when painting
    selection highlights or running carets.
    """
    if line_length <= 0:
        return ()

    # First, walk the source runs in *logical* order, clipping each to the
    # line's character span.
    logical: list[GlyphRun] = []
    cursor = 0
    line_end = line_start + line_length
    total_chars = max(line_length, 1)
    x = line_x
    for run in spec.runs:
        run_start = cursor
        run_end = cursor + len(run.text)
        cursor = run_end
        clip_start = max(run_start, line_start)
        clip_end = min(run_end, line_end)
        if clip_end <= clip_start:
            continue
        chars = clip_end - clip_start
        advance = line_advance * (chars / total_chars)
        logical.append(
            GlyphRun(
                start=clip_start,
                end=clip_end,
                font_family=run.font_family,
                font_size_pt=run.font_size_pt,
                color_ref=run.color_ref,
                x_offset=x,
                advance=advance,
                direction=direction,
            )
        )
        x += advance

    if direction == "rtl":
        # Reverse to visual order and recompute x_offsets so the *last logical
        # glyph* sits at the leftmost x.  This is exactly what RTL rendering
        # wants: glyphs flow right-to-left, so the visually-leftmost glyph is
        # the logically-last character.
        x = line_x
        visual: list[GlyphRun] = []
        for gr in reversed(logical):
            visual.append(
                GlyphRun(
                    start=gr.start,
                    end=gr.end,
                    font_family=gr.font_family,
                    font_size_pt=gr.font_size_pt,
                    color_ref=gr.color_ref,
                    x_offset=x,
                    advance=gr.advance,
                    direction="rtl",
                )
            )
            x += gr.advance
        return tuple(visual)

    return tuple(logical)


def column_visual_order(column_count: int, direction: Direction) -> list[int]:
    """Return column indices in *fill* order for the given direction.

    RTL frames fill columns rightmost-first.
    """
    if direction == "rtl":
        return list(range(column_count - 1, -1, -1))
    return list(range(column_count))


__all__ = [
    "build_font",
    "build_format_ranges",
    "column_visual_order",
    "paragraph_text",
    "split_line_into_glyph_runs",
]
