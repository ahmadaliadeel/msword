"""Multi-column composition: 3-col frame fills cols left->right;
RTL frame fills rightmost column first."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from msword.layout.composer import (
    FrameComposer,
    StubStory,
    StubTextFrame,
    make_paragraph,
)


def _filler_paragraph(idx: int) -> object:
    return make_paragraph(
        ("Lorem ipsum " * 8),
        block_id=f"p{idx}",
        line_height=14.0,
        font_size_pt=10.0,
    )


def test_three_column_ltr_fills_left_to_right(qtbot) -> None:  # type: ignore[no-untyped-def]
    _ = qtbot
    frame = StubTextFrame(
        id="f1",
        rect=QRectF(0, 0, 300, 80),  # 3 cols x ~95pt wide x 80pt tall
        columns=3,
        gutter=10.0,
        text_direction="ltr",
    )
    # Enough paragraphs to fill all three columns and then some.
    paragraphs = [_filler_paragraph(i) for i in range(8)]
    story = StubStory(paragraphs=paragraphs)  # type: ignore[arg-type]

    result = FrameComposer().compose(story, [frame])

    cols_visited_in_order: list[int] = []
    for line in result.lines:
        if not cols_visited_in_order or line.column_index != cols_visited_in_order[-1]:
            cols_visited_in_order.append(line.column_index)

    assert cols_visited_in_order[:3] == [0, 1, 2], (
        f"LTR 3-col frame should fill cols 0->1->2; got {cols_visited_in_order}"
    )
    # Each column actually got at least one line.
    used_cols = {ln.column_index for ln in result.lines}
    assert used_cols == {0, 1, 2}, f"all cols used; got {used_cols}"


def test_three_column_rtl_fills_right_to_left(qtbot) -> None:  # type: ignore[no-untyped-def]
    """An RTL frame fills its rightmost column first."""
    _ = qtbot
    frame = StubTextFrame(
        id="f1",
        rect=QRectF(0, 0, 300, 80),
        columns=3,
        gutter=10.0,
        text_direction="rtl",
    )
    paragraphs = [_filler_paragraph(i) for i in range(8)]
    story = StubStory(paragraphs=paragraphs)  # type: ignore[arg-type]

    result = FrameComposer().compose(story, [frame])

    cols_visited_in_order: list[int] = []
    for line in result.lines:
        if not cols_visited_in_order or line.column_index != cols_visited_in_order[-1]:
            cols_visited_in_order.append(line.column_index)

    assert cols_visited_in_order[:3] == [2, 1, 0], (
        f"RTL 3-col frame fills 2->1->0; got {cols_visited_in_order}"
    )

    # Sanity: the first placed line lives in the rightmost column rect.
    rects = frame.column_rects()
    assert result.lines[0].column_index == 2
    assert abs(result.lines[0].rect.left() - rects[2].left()) < 1e-6


def test_columns_with_overflow_advance_to_next_frame(qtbot) -> None:  # type: ignore[no-untyped-def]
    """Once all columns of a frame are full, composition advances to the next
    frame in the chain."""
    _ = qtbot
    f1 = StubTextFrame(
        id="f1", rect=QRectF(0, 0, 300, 50), columns=2, gutter=10.0
    )
    f2 = StubTextFrame(id="f2", rect=QRectF(0, 0, 300, 200))
    paragraphs = [_filler_paragraph(i) for i in range(6)]
    story = StubStory(paragraphs=paragraphs)  # type: ignore[arg-type]

    result = FrameComposer().compose(story, [f1, f2])

    assert {ln.frame_id for ln in result.lines} == {"f1", "f2"}
    # f1 must have lines in both columns; f2 starts at column 0.
    f1_lines = [ln for ln in result.lines if ln.frame_id == "f1"]
    f2_lines = [ln for ln in result.lines if ln.frame_id == "f2"]
    assert {ln.column_index for ln in f1_lines} == {0, 1}
    assert f2_lines and f2_lines[0].column_index == 0
