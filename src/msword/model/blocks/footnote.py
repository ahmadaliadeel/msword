# mypy: disable-error-code="override, misc, attr-defined, type-abstract"
"""FootnoteBlock — unit-32 (`feat-footnotes`) model.

Per spec §4.2 / §12 row 32:

    Block type ``footnote``. Fields ``id``, ``body_blocks``,
    ``marker=""`` (auto-numbered). Registers in BlockRegistry.

    ``iter_paragraphs`` yields nothing in normal flow; a separate
    ``iter_footnote_paragraphs`` yields body paragraphs that the
    layout pipeline lays into the per-page footnote area.

The block holds *body blocks* (not a flat run list) so that a footnote
can itself contain paragraphs, lists, or any other registered block —
matching how real-world footnotes work (a footnote can have multiple
paragraphs of explanation).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from msword.layout.paragraph_spec import ParagraphSpec
from msword.model.block import Block, BlockRegistry


@dataclass(slots=True)
class FootnoteBlock(Block):
    """A footnote: never appears in the main flow; surfaces in a per-page
    footnote area when a ``FootnoteRefMark`` referencing this block's ``id``
    is encountered by the main composer.
    """

    kind = "footnote"

    id: str = ""
    body_blocks: list[Block] = field(default_factory=list)
    #: Display marker (``"1"``, ``"2"``, ``"a"`` …). Empty string means
    #: "auto-numbered" — the layout pipeline assigns a number based on the
    #: order references are encountered in document order.
    marker: str = ""

    # ---- Paragraph iteration seams ----

    def iter_paragraphs(self) -> Iterator[ParagraphSpec]:
        """Footnotes contribute *nothing* to the main flow.

        Returning an empty iterator is the whole contract here: it keeps
        body text out of the main column and lets the per-page footnote
        area be the sole consumer of the body content (via
        ``iter_footnote_paragraphs``).
        """
        return iter(())

    def iter_footnote_paragraphs(self) -> Iterator[ParagraphSpec]:
        """Yield every paragraph that should be rendered in the footnote
        area. Walks ``body_blocks`` recursively via each child's own
        ``iter_paragraphs``.
        """
        for child in self.body_blocks:
            yield from child.iter_paragraphs()

    # ---- Serialization ----

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "marker": self.marker,
            "body_blocks": [b.to_json() for b in self.body_blocks],
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> FootnoteBlock:
        body = [BlockRegistry.from_json(b) for b in payload.get("body_blocks", [])]
        return cls(
            id=payload.get("id", ""),
            body_blocks=body,
            marker=payload.get("marker", ""),
        )


BlockRegistry.register(FootnoteBlock)
