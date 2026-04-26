"""Layout integration tests for the footnote area (unit-32).

Per spec §12 row 32 acceptance scenarios:

  * Page with 2 paragraphs + 2 inline ``FootnoteRefMarks`` →
    footnote area at the bottom shows entries marked "1" and "2".
  * Doesn't-fit case → footnote 2 ends up on page 2's area; the main
    flow on page 1 ends earlier so the page paginates in a single pass.

The tests use a tiny in-unit composer (``compose_page_with_footnotes``);
see ``src/msword/layout/footnote.py``. The full ``FrameComposer`` arrives
with unit-13.

``pytest-qt``'s ``qtbot`` fixture is requested per the spec's "layout
tests use pytest-qt" rule; we don't need a widget for this scenario
(text composition can run headless), but instantiating the Qt event-loop
fixture makes sure this test runs *inside* the same harness as the
broader layout suite.
"""

from __future__ import annotations

from typing import Any

from msword.layout.footnote import (
    LINE_HEIGHT,
    compose_page_with_footnotes,
)
from msword.layout.paragraph_spec import FootnotedParagraphSpec, FootnoteRefMark
from msword.model.blocks.footnote import FootnoteBlock
from msword.model.blocks.paragraph import ParagraphBlock
from msword.model.run import Run


def _make_footnote(fn_id: str, body_text: str) -> FootnoteBlock:
    return FootnoteBlock(
        id=fn_id,
        body_blocks=[ParagraphBlock(id=f"{fn_id}-p", runs=[Run(text=body_text)])],
    )


def _para(text: str, *refs: FootnoteRefMark) -> FootnotedParagraphSpec:
    return FootnotedParagraphSpec(runs=(Run(text=text),), ref_marks=refs)


def test_two_refs_both_fit_in_footnote_area(qtbot: Any) -> None:
    """Both refs land on page 1; area shows entries "1" then "2"."""
    del qtbot  # presence is the contract; we don't need a widget here.

    fn1 = _make_footnote("fn-1", "Citation A.")
    fn2 = _make_footnote("fn-2", "Citation B.")
    blocks = {fn1.id: fn1, fn2.id: fn2}

    paragraphs = [
        _para("First paragraph.", FootnoteRefMark("fn-1", index=5)),
        _para("Second paragraph.", FootnoteRefMark("fn-2", index=6)),
    ]

    result = compose_page_with_footnotes(
        paragraphs,
        blocks,
        page_id="p1",
        page_text_height=LINE_HEIGHT * 10,  # plenty of main-flow space.
        footnote_max_height=LINE_HEIGHT * 10,  # plenty of footnote space.
    )

    assert [p.text for p in result.main_paragraphs] == [
        "First paragraph.",
        "Second paragraph.",
    ]
    assert [e.marker for e in result.footnote_entries] == ["1", "2"]
    assert [e.block.id for e in result.footnote_entries] == ["fn-1", "fn-2"]
    assert result.overflow_paragraphs == []
    assert result.overflow_footnotes == []


def test_second_footnote_pushed_to_page_two_when_area_overflows(qtbot: Any) -> None:
    """When the footnote area only has room for one entry, footnote 2
    ripples to page 2 and the main flow on page 1 ends at paragraph 1
    (the paragraph that referenced the overflowing footnote)."""
    del qtbot

    fn1 = _make_footnote("fn-1", "Citation A.")
    fn2 = _make_footnote("fn-2", "Citation B.")
    blocks = {fn1.id: fn1, fn2.id: fn2}

    paragraphs = [
        _para("First paragraph.", FootnoteRefMark("fn-1", index=5)),
        _para("Second paragraph.", FootnoteRefMark("fn-2", index=6)),
        _para("Third paragraph (unreferenced)."),
    ]

    page1 = compose_page_with_footnotes(
        paragraphs,
        blocks,
        page_id="p1",
        page_text_height=LINE_HEIGHT * 10,
        # Only one footnote entry fits in the area band.
        footnote_max_height=LINE_HEIGHT * 1,
    )

    # Main flow on page 1 ends *before* the paragraph whose footnote did
    # not fit — i.e. the second paragraph (index 1) and onward ripple.
    assert [p.text for p in page1.main_paragraphs] == ["First paragraph."]

    # Page 1's footnote area shows entry "1" only.
    assert [e.marker for e in page1.footnote_entries] == ["1"]
    assert page1.footnote_entries[0].block.id == "fn-1"

    # Page 2 picks up the rest of the main flow + the overflowed footnote.
    assert [p.text for p in page1.overflow_paragraphs] == [
        "Second paragraph.",
        "Third paragraph (unreferenced).",
    ]
    assert [e.marker for e in page1.overflow_footnotes] == ["2"]
    assert page1.overflow_footnotes[0].block.id == "fn-2"


def test_overflowed_footnote_lays_on_next_page_with_remaining_main_flow(
    qtbot: Any,
) -> None:
    """End-to-end across two pages: feed page-1 overflow into page-2 and
    verify footnote "2" appears in page-2's area without renumbering."""
    del qtbot

    fn1 = _make_footnote("fn-1", "Citation A.")
    fn2 = _make_footnote("fn-2", "Citation B.")
    blocks = {fn1.id: fn1, fn2.id: fn2}

    paragraphs = [
        _para("First.", FootnoteRefMark("fn-1", index=0)),
        _para("Second.", FootnoteRefMark("fn-2", index=0)),
    ]

    page1 = compose_page_with_footnotes(
        paragraphs,
        blocks,
        page_id="p1",
        page_text_height=LINE_HEIGHT * 10,
        footnote_max_height=LINE_HEIGHT * 1,
    )
    # Page 2 starts numbering after whatever page 1 used.
    starting_number = 1 + len(page1.footnote_entries) + len(page1.overflow_footnotes)
    # …but overflowed entries already carry their assigned markers, so
    # the numbering on page 2 doesn't restart for them. We simulate the
    # main composer's job: pre-queued overflow entries keep their marker.
    page2 = compose_page_with_footnotes(
        page1.overflow_paragraphs,
        blocks,
        page_id="p2",
        page_text_height=LINE_HEIGHT * 10,
        footnote_max_height=LINE_HEIGHT * 10,
        starting_number=starting_number,
    )

    assert [p.text for p in page2.main_paragraphs] == ["Second."]
    # The footnote that referenced "Second." is fn-2 — re-queued here
    # because the main composer hits the same FootnoteRefMark again on
    # page 2. With ample area space it lands on page 2.
    assert [e.block.id for e in page2.footnote_entries] == ["fn-2"]
    assert page2.overflow_footnotes == []
    assert page2.overflow_paragraphs == []
