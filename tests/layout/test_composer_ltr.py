"""LTR composition: a 100x200pt frame should fit ~3 lines of body text."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from msword.layout.composer import (
    FrameComposer,
    StubStory,
    StubTextFrame,
    make_paragraph,
)


def test_three_line_paragraph_in_one_frame(qtbot) -> None:  # type: ignore[no-untyped-def]
    """A short Latin paragraph wraps to >=3 lines and the baselines advance
    monotonically downward (top of page -> bottom).

    ``qtbot`` is requested to guarantee a ``QGuiApplication`` exists; Qt's
    text-layout machinery refuses to run without one.
    """
    _ = qtbot
    frame = StubTextFrame(
        id="f1",
        rect=QRectF(0, 0, 100, 200),
        columns=1,
        text_direction="ltr",
    )
    para = make_paragraph(
        "Hello world this is a moderately long paragraph that must wrap.",
        font_size_pt=10.0,
        line_height=14.0,
        block_id="p-hello",
        paragraph_style_ref="Body",
    )
    story = StubStory(paragraphs=[para])

    result = FrameComposer().compose(story, [frame])

    assert not result.overflow, "100x200pt should hold a 64-char paragraph"
    assert len(result.lines) >= 3, f"expected >=3 wrapped lines, got {len(result.lines)}"

    baselines = [line.baseline_y for line in result.lines]
    assert baselines == sorted(baselines), "baselines must be monotonic top->bottom"
    assert len(set(baselines)) == len(baselines), "baselines must be distinct"

    for line in result.lines:
        assert line.frame_id == "f1"
        assert line.column_index == 0
        assert line.paragraph_style_ref == "Body"
        assert line.block_id == "p-hello"
        assert line.text  # non-empty
        for gr in line.glyph_runs:
            assert gr.direction == "ltr"
            assert gr.font_size_pt == 10.0


def test_lines_fit_within_column_rect(qtbot) -> None:  # type: ignore[no-untyped-def]
    """All placed lines lie within the frame's column rect."""
    _ = qtbot
    frame = StubTextFrame(id="f1", rect=QRectF(10, 20, 100, 200))
    para = make_paragraph(
        "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do.",
        font_size_pt=10.0,
        line_height=14.0,
    )
    result = FrameComposer().compose(StubStory(paragraphs=[para]), [frame])

    col = frame.column_rects()[0]
    for line in result.lines:
        assert line.rect.left() >= col.left() - 1e-6
        assert line.rect.right() <= col.right() + 1e-6
        assert line.rect.top() >= col.top() - 1e-6
        assert line.rect.bottom() <= col.bottom() + 1e-6


def test_compose_from_resume_offset(qtbot) -> None:  # type: ignore[no-untyped-def]
    """``compose_from`` skips already-placed paragraphs."""
    _ = qtbot
    frame = StubTextFrame(id="f1", rect=QRectF(0, 0, 200, 200))
    p0 = make_paragraph("First paragraph.", block_id="p0", line_height=14.0)
    p1 = make_paragraph("Second paragraph.", block_id="p1", line_height=14.0)
    story = StubStory(paragraphs=[p0, p1])

    full = FrameComposer().compose(story, [frame])
    second_only = FrameComposer().compose_from(
        story, [frame], start_block_index=1, start_offset=0
    )

    assert {ln.block_id for ln in full.lines} == {"p0", "p1"}
    assert {ln.block_id for ln in second_only.lines} == {"p1"}
