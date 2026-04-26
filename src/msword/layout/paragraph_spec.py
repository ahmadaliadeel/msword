"""Layout-side paragraph extension for footnotes — unit-32 (`feat-footnotes`).

Per §4.2 / §5 of the design doc: "ParagraphSpec extension carries optional
ref-marks list at char offsets." Master's canonical
:class:`msword.model.story.ParagraphSpec` is the unit yielded by
``Block.iter_paragraphs`` and does not carry footnote references — those are
a layout-only concern. The footnote unit needs an inline marker that the
main composer can consult when shaping a page; this module owns those types.

When the full ``FrameComposer`` (unit-13) lands its real ParagraphSpec with
the inline-mark surface, the ``ref_marks`` field can move there and this
module becomes a re-export shim.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from msword.model.run import Run


@dataclass(frozen=True, slots=True)
class FootnoteRefMark:
    """Inline mark indicating "a footnote reference sits here".

    Carried on the per-page paragraph rather than inside a Run, so the layout
    pipeline can find every reference without walking marks per glyph.

    Attributes:
        footnote_id: id of the FootnoteBlock this mark refers to.
        index: character offset within the paragraph's plain text where
            the reference glyph (``¹``, ``²``, …) is rendered.
    """

    footnote_id: str
    index: int


@dataclass(frozen=True, slots=True)
class FootnotedParagraphSpec:
    """One paragraph queued for the footnote-aware page composer.

    A layout-only extension of master's :class:`ParagraphSpec`: same run
    sequence, plus the inline footnote references the main composer must
    surface to the per-page footnote area.
    """

    runs: tuple[Run, ...] = ()
    ref_marks: tuple[FootnoteRefMark, ...] = field(default_factory=tuple)

    @property
    def text(self) -> str:
        """Plain-text concatenation of every run."""
        return "".join(run.text for run in self.runs)
