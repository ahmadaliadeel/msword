"""Per-page footnote-area layout — unit-32 (`feat-footnotes`).

Per §5 / §12 row 32 of the design doc:

    A page reserves a bottom band for footnotes. The main composer, when
    it encounters a ``FootnoteRefMark`` while shaping a paragraph, calls
    ``queue(footnote_block, target_page_id)`` on the area composer for
    that page. After the page's main flow is composed, the area composer
    lays the queued footnote bodies into the reserved band. If a body
    will not fit, it is pushed to the next page's area — and the main
    flow on the previous page is shortened so the page layout converges
    in a single iteration.

This module owns the ``FootnoteAreaComposer`` and a small ``OverflowResult``
record that carries push-forward information back to the main composer.
The main ``FrameComposer`` (unit-13) is stubbed locally below so the unit
is testable in isolation; only the *seams* it touches —
``FootnoteAreaComposer.queue``, ``.compose``, and the integration loop in
``compose_page_with_footnotes`` — are part of this unit's contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from msword.layout.paragraph_spec import ParagraphSpec
from msword.model.blocks.footnote import FootnoteBlock

# --- Constants for the in-unit layout stub ----------------------------------
#
# Real text composition is the job of unit-13. To keep this unit testable in
# isolation we approximate "lines" as paragraphs of fixed line height: every
# paragraph counts as one line for the main flow, and every paragraph in a
# footnote body counts as one line in the footnote area, prefixed by the
# footnote marker. This matches the §12 spec's layout test scenarios:
#
#   * "page with 2 paragraphs + 2 inline FootnoteRefMarks → footnote area at
#      bottom shows entries '1', '2'"
#   * "doesn't fit case → footnote 2 on page 2 area; main flow on page 1
#      ends earlier"
#
# When unit-13 lands, the main-flow side is replaced by the real composer;
# the footnote-area side still uses these heights but driven by QTextLayout.
# ----------------------------------------------------------------------------

LINE_HEIGHT = 14.0  # px-equivalent; arbitrary unit, used consistently.


@dataclass(slots=True)
class FootnoteEntry:
    """One queued footnote ready to be laid out.

    ``marker`` is filled in at queue time (auto-numbered in the order the
    footnote references are encountered in document order, per spec).
    ``ref_paragraph_index`` is the index, within the page's main flow, of
    the paragraph whose ``FootnoteRefMark`` triggered the queue — used to
    compute where to truncate the main flow when this entry overflows.
    """

    block: FootnoteBlock
    marker: str
    paragraphs: list[ParagraphSpec] = field(default_factory=list)
    ref_paragraph_index: int = 0

    @property
    def height(self) -> float:
        """Height the entry will occupy in the footnote area.

        At least one line — even an empty footnote shows its marker.
        """
        n = max(1, len(self.paragraphs))
        return n * LINE_HEIGHT


@dataclass(slots=True)
class OverflowResult:
    """What the main composer needs to know after the area has run.

    Attributes:
        placed: footnote entries that fit on this page. Order matches the
            order they were queued in (and therefore matches reference
            order in the body text).
        overflowed: entries that did *not* fit and must be queued on the
            *next* page's area. Carry their auto-assigned marker forward.
        main_flow_truncate_at: number of main-flow paragraphs that should
            actually render on this page. ``None`` means "no truncation —
            keep what the main composer already laid down". An int means
            "shorten the main flow to *that many* paragraphs"; the rest
            ripple to the next page so the footnote area has room to grow
            its reserved band.
    """

    placed: list[FootnoteEntry] = field(default_factory=list)
    overflowed: list[FootnoteEntry] = field(default_factory=list)
    main_flow_truncate_at: int | None = None


class FootnoteAreaComposer:
    """Per-page footnote-area composer.

    One instance per page. Reserves a fixed maximum band at the bottom
    of the page; the band *grows* as entries are queued, but never past
    ``max_height``. When growth would exceed ``max_height``, the offending
    entry is pushed to the next page (and the main flow on this page is
    shortened so the page is properly paginated in a single pass).
    """

    def __init__(
        self,
        page_id: str,
        *,
        max_height: float,
        starting_number: int = 1,
    ) -> None:
        self.page_id = page_id
        self.max_height = max_height
        self._next_number = starting_number
        self._queued: list[FootnoteEntry] = []

    # ---- queueing ----

    def queue(
        self,
        block: FootnoteBlock,
        *,
        ref_paragraph_index: int,
    ) -> FootnoteEntry:
        """Queue a footnote body for this page.

        Called by the main composer when it lands on a ``FootnoteRefMark``.
        Returns the created entry so the main composer can read its
        auto-assigned ``marker`` for the in-text glyph (``¹``, ``²`` …).
        """
        marker = block.marker if block.marker else str(self._next_number)
        if not block.marker:
            self._next_number += 1
        entry = FootnoteEntry(
            block=block,
            marker=marker,
            paragraphs=list(block.iter_footnote_paragraphs()),
            ref_paragraph_index=ref_paragraph_index,
        )
        self._queued.append(entry)
        return entry

    # ---- composition ----

    def compose(self, *, main_flow_paragraph_count: int) -> OverflowResult:
        """Lay queued entries into the reserved band.

        Single-iteration convergence: walks the queue in order, fits each
        entry while there's room, and packs anything left over into
        ``overflowed``. If at least one entry overflows, the main flow on
        this page is truncated to end *before* the paragraph that
        referenced the first overflowing entry — so the next page picks
        up the main flow *and* its footnote, in lockstep.
        """
        result = OverflowResult()
        used = 0.0

        for entry in self._queued:
            if used + entry.height <= self.max_height:
                result.placed.append(entry)
                used += entry.height
            else:
                result.overflowed.append(entry)

        if result.overflowed:
            # Truncate so the referencing paragraph itself ripples to the
            # next page (its footnote needs to live with it).
            ref_idx = result.overflowed[0].ref_paragraph_index
            result.main_flow_truncate_at = min(ref_idx, main_flow_paragraph_count)

        return result


# --- Tiny in-unit composer for testability ----------------------------------
#
# Real composition is unit-13. The function below is a *minimal* main-flow
# composer used only to drive the footnote-area integration test in this
# unit's `tests/layout/test_footnote_layout.py`. It models a page as a
# fixed-height band (above the footnote area) and assigns one paragraph per
# line. When unit-13 lands its real `FrameComposer`, this helper is removed
# — its role moves into `compose_page` over there.
# ----------------------------------------------------------------------------


@dataclass(slots=True)
class PageLayoutResult:
    """Outcome of laying one story onto one page."""

    main_paragraphs: list[ParagraphSpec]
    footnote_entries: list[FootnoteEntry]
    overflow_paragraphs: list[ParagraphSpec]
    overflow_footnotes: list[FootnoteEntry]


def compose_page_with_footnotes(
    paragraphs: list[ParagraphSpec],
    blocks_by_id: dict[str, FootnoteBlock],
    *,
    page_id: str,
    page_text_height: float,
    footnote_max_height: float,
    starting_number: int = 1,
) -> PageLayoutResult:
    """Main-composer + area-composer integration for a single page.

    Algorithm (single pass — convergence guaranteed by §5):

    1. Walk paragraphs in order. For each paragraph, look at its
       ``ref_marks``; if any reference ID matches a known footnote, queue
       it on the area composer (recording which paragraph triggered it).
    2. Fit paragraphs into the main flow until its height runs out.
    3. Run ``FootnoteAreaComposer.compose``. If it returned a truncate
       index, drop main-flow paragraphs from there onward. Anything
       dropped — and any overflowed footnotes — are returned as
       overflow so the caller can feed them into page N+1.
    """
    area = FootnoteAreaComposer(
        page_id=page_id,
        max_height=footnote_max_height,
        starting_number=starting_number,
    )

    main_capacity = int(page_text_height // LINE_HEIGHT)
    placed: list[ParagraphSpec] = []

    for i, para in enumerate(paragraphs):
        if i >= main_capacity:
            # Out of room in the main flow before we even consult footnotes.
            break
        placed.append(para)
        for mark in para.ref_marks:
            block = blocks_by_id.get(mark.footnote_id)
            if block is not None:
                area.queue(block, ref_paragraph_index=i)

    overflow = area.compose(main_flow_paragraph_count=len(placed))

    if overflow.main_flow_truncate_at is not None:
        cut = overflow.main_flow_truncate_at
        ripple_main = placed[cut:]
        placed = placed[:cut]
    else:
        ripple_main = []

    # Anything that fit in main but was after the cut still needs to flow.
    # And: paragraphs we never even reached due to main_capacity also flow.
    tail = paragraphs[len(placed) + len(ripple_main):]
    return PageLayoutResult(
        main_paragraphs=placed,
        footnote_entries=overflow.placed,
        overflow_paragraphs=ripple_main + list(tail),
        overflow_footnotes=overflow.overflowed,
    )
