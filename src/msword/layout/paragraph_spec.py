"""Local stub of ParagraphSpec — the unit yielded by ``Block.iter_paragraphs``.

Owned by unit-13 (`layout-text-composer`). The footnote unit extends the
spec with an *optional* list of inline reference marks at character
offsets, per §4.2 / §5 of the design doc:

    "ParagraphSpec extension carries optional ref-marks list at char
     offsets."

When unit-13 lands the full spec, the ``ref_marks`` field must be carried
through — it is the seam by which the main composer queues footnote bodies
into the per-page footnote area.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from msword.model.run import Run


@dataclass(frozen=True, slots=True)
class FootnoteRefMark:
    """Inline mark indicating "a footnote reference sits here".

    Carried on the ParagraphSpec rather than inside a Run, so the layout
    pipeline can find every reference without walking marks per glyph.

    Attributes:
        footnote_id: id of the FootnoteBlock this mark refers to.
        index: character offset within the paragraph's plain text where
            the reference glyph (``¹``, ``²``, …) is rendered.
    """

    footnote_id: str
    index: int


@dataclass(frozen=True, slots=True)
class ParagraphSpec:
    """One paragraph queued for the frame composer.

    Stub: only carries the fields the footnote unit needs. The full spec
    (paragraph_style_ref, direction overrides, baseline-grid flag, …)
    arrives with unit-13.
    """

    runs: tuple[Run, ...] = ()
    ref_marks: tuple[FootnoteRefMark, ...] = field(default_factory=tuple)

    @property
    def text(self) -> str:
        """Plain-text concatenation of every run."""
        return "".join(run.text for run in self.runs)
