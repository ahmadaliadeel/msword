"""CalloutBlock — info/warn/tip/danger banner around nestable child blocks."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

from msword.model.block import Block, BlockRegistry, ParagraphSpec

CalloutKind = Literal["info", "warn", "tip", "danger"]


@dataclass
class CalloutBlock(Block):
    kind: ClassVar[str] = "callout"

    id: str
    callout_kind: CalloutKind = "info"
    blocks: list[Block] = field(default_factory=list)

    def iter_paragraphs(self) -> Iterator[ParagraphSpec]:
        # Per spec §4.2: the callout label ("INFO", "WARNING", ...) is rendered
        # as decoration in unit-16, not as a synthesized paragraph here.
        for child in self.blocks:
            yield from child.iter_paragraphs()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "callout_kind": self.callout_kind,
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @classmethod
    def _from_dict_specific(cls, data: dict[str, Any]) -> CalloutBlock:
        return cls(
            id=data["id"],
            callout_kind=data.get("callout_kind", "info"),
            blocks=[BlockRegistry.resolve(b) for b in data.get("blocks", [])],
        )


BlockRegistry.register(CalloutBlock)
