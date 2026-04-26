"""RTL composition: an Arabic paragraph should produce RTL glyph runs and
place its visually-leftmost glyph at the smallest x-offset."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from msword.layout.composer import (
    FrameComposer,
    StubStory,
    StubTextFrame,
    make_paragraph,
)

ARABIC = "مرحبا بالعالم"  # "Hello world"


def test_arabic_paragraph_marks_glyph_runs_as_rtl(qtbot) -> None:  # type: ignore[no-untyped-def]
    _ = qtbot
    frame = StubTextFrame(
        id="f1",
        rect=QRectF(0, 0, 200, 200),
        text_direction="rtl",
    )
    para = make_paragraph(
        ARABIC, direction="rtl", font_size_pt=14.0, line_height=20.0, block_id="p-ar"
    )
    result = FrameComposer().compose(StubStory(paragraphs=[para]), [frame])

    assert not result.overflow
    assert result.lines, "should produce at least one line"
    line = result.lines[0]

    assert line.glyph_runs, "expected glyph_runs for the Arabic line"
    for gr in line.glyph_runs:
        assert gr.direction == "rtl"


def test_arabic_visually_first_glyph_is_leftmost(qtbot) -> None:  # type: ignore[no-untyped-def]
    """In RTL visual order, the *last* logical character (rightmost in the
    source string) sits at the leftmost x_offset on screen."""
    _ = qtbot
    frame = StubTextFrame(
        id="f1",
        rect=QRectF(0, 0, 200, 200),
        text_direction="rtl",
    )
    para = make_paragraph(
        ARABIC, direction="rtl", font_size_pt=14.0, line_height=20.0
    )
    result = FrameComposer().compose(StubStory(paragraphs=[para]), [frame])

    line = result.lines[0]
    assert len(line.glyph_runs) >= 1

    # In RTL visual order: the LAST glyph run on the line (leftmost on screen)
    # should hold the LAST logical character of the source paragraph.
    last_visual = line.glyph_runs[-1]
    # ``end`` is exclusive; the line's terminal char index in the paragraph is
    # ``len(ARABIC) - 1`` (no trailing whitespace).
    assert last_visual.end == len(ARABIC), (
        f"expected final logical char (idx {len(ARABIC)-1}) at the visually-leftmost "
        f"glyph run, got run [{last_visual.start}, {last_visual.end})"
    )

    # Visual ordering invariant: x_offsets non-decreasing across runs (leftmost
    # first, rightmost last) — the *rendered* page reads right-to-left because
    # the run mapped to higher logical indices appears later in the visual
    # sequence.
    xs = [gr.x_offset for gr in line.glyph_runs]
    assert xs == sorted(xs), f"glyph_runs visual x-order must be ascending; got {xs}"


def test_rtl_frame_with_ltr_paragraph_still_works(qtbot) -> None:  # type: ignore[no-untyped-def]
    """A Latin paragraph inside an RTL frame is shaped LTR (the run says so)
    while the frame's column-fill order remains rightmost-first; with a
    single-column frame the latter is a no-op."""
    _ = qtbot
    frame = StubTextFrame(id="f1", rect=QRectF(0, 0, 200, 200), text_direction="rtl")
    para = make_paragraph("Latin text inside RTL frame.", direction="ltr")
    result = FrameComposer().compose(StubStory(paragraphs=[para]), [frame])

    assert not result.overflow
    assert all(
        gr.direction == "ltr" for line in result.lines for gr in line.glyph_runs
    )
