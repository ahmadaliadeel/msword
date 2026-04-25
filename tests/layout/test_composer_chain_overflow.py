"""Chain overflow: 5 long paragraphs in 2 small frames distribute across both
and a paragraph splits at the frame boundary."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from msword.layout.composer import (
    FrameComposer,
    StubStory,
    StubTextFrame,
    make_paragraph,
)


def _long_paragraph(idx: int) -> "object":
    return make_paragraph(
        ("Word" + str(idx) + " ") * 50,  # ~250+ chars
        block_id=f"p{idx}",
        line_height=14.0,
        font_size_pt=10.0,
    )


def test_paragraphs_distribute_across_two_small_frames(qtbot) -> None:  # type: ignore[no-untyped-def]
    _ = qtbot
    f1 = StubTextFrame(id="f1", rect=QRectF(0, 0, 100, 80))   # ~5 lines @ 14pt
    f2 = StubTextFrame(id="f2", rect=QRectF(0, 0, 100, 80))
    paragraphs = [_long_paragraph(i) for i in range(5)]
    story = StubStory(paragraphs=paragraphs)  # type: ignore[arg-type]

    result = FrameComposer().compose(story, [f1, f2])

    frame_ids = {line.frame_id for line in result.lines}
    assert frame_ids == {"f1", "f2"}, (
        f"text should distribute across both frames; got {frame_ids}"
    )
    # Both frames should have non-zero line counts.
    assert all(lf.lines for lf in result.frames), "each frame in chain holds lines"
    # 5 long paragraphs in 2 tiny frames must overflow.
    assert result.overflow, "expected overflow with 5x long paragraphs into 2 small frames"
    # The overflow_block_id must be set when overflow=True.
    assert result.overflow_block_id is not None


def test_paragraph_splits_across_frame_boundary(qtbot) -> None:  # type: ignore[no-untyped-def]
    """At least one paragraph must contribute lines to both frames in the
    chain — that's a mid-paragraph split."""
    _ = qtbot
    f1 = StubTextFrame(id="f1", rect=QRectF(0, 0, 100, 60))
    f2 = StubTextFrame(id="f2", rect=QRectF(0, 0, 100, 200))
    paragraphs = [_long_paragraph(i) for i in range(5)]
    story = StubStory(paragraphs=paragraphs)  # type: ignore[arg-type]

    result = FrameComposer().compose(story, [f1, f2])

    # Group block_ids by frame.
    by_frame: dict[str, set[str]] = {}
    for line in result.lines:
        by_frame.setdefault(line.frame_id, set()).add(line.block_id or "")
    f1_blocks = by_frame.get("f1", set())
    f2_blocks = by_frame.get("f2", set())
    shared = f1_blocks & f2_blocks
    assert shared, (
        f"expected at least one paragraph to split across frames; "
        f"f1={f1_blocks} f2={f2_blocks}"
    )


def test_resume_after_overflow(qtbot) -> None:  # type: ignore[no-untyped-def]
    """After an overflow, ``compose_from`` with the reported indices resumes
    cleanly into a follow-on chain."""
    _ = qtbot
    small = StubTextFrame(id="s", rect=QRectF(0, 0, 100, 30))
    big = StubTextFrame(id="b", rect=QRectF(0, 0, 100, 1000))
    paragraphs = [_long_paragraph(i) for i in range(3)]
    story = StubStory(paragraphs=paragraphs)  # type: ignore[arg-type]

    first = FrameComposer().compose(story, [small])
    assert first.overflow

    rest = FrameComposer().compose_from(
        story,
        [big],
        start_block_index=first.last_paragraph_index,
        start_offset=first.last_glyph_offset,
    )
    assert not rest.overflow, "1000pt frame must hold the leftovers"
    assert rest.lines, "resumed composition produced lines"
