"""QuoteBlock — block quote that wraps nestable child blocks."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, ClassVar

from msword.model.block import Block, BlockRegistry, ParagraphSpec

QUOTE_PARAGRAPH_STYLE = "Quote"


@dataclass
class QuoteBlock(Block):
    kind: ClassVar[str] = "quote"

    id: str
    blocks: list[Block] = field(default_factory=list)

    def iter_paragraphs(self) -> Iterator[ParagraphSpec]:
        for child in self.blocks:
            for spec in child.iter_paragraphs():
                # Override paragraph style so the layout composer renders the
                # quoted children with the document's "Quote" style.
                yield ParagraphSpec(
                    runs=spec.runs,
                    paragraph_style_ref=QUOTE_PARAGRAPH_STYLE,
                    block_id=spec.block_id,
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @classmethod
    def _from_dict_specific(cls, data: dict[str, Any]) -> QuoteBlock:
        return cls(
            id=data["id"],
            blocks=[BlockRegistry.resolve(b) for b in data.get("blocks", [])],
        )


BlockRegistry.register(QuoteBlock)
