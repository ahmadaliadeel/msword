"""DividerBlock — horizontal rule between paragraphs."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from msword.model.block import Block, BlockRegistry, ParagraphSpec

DividerStyle = Literal["thin", "thick", "double"]


@BlockRegistry.register
@dataclass(slots=True)
class DividerBlock(Block):
    kind: ClassVar[str] = "divider"

    id: str
    style: DividerStyle = "thin"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "id": self.id, "style": self.style}

    def iter_paragraphs(self) -> Iterable[ParagraphSpec]:
        return ()

    @classmethod
    def _from_dict_specific(cls, d: dict[str, Any]) -> DividerBlock:
        style: DividerStyle = d.get("style", "thin")
        return cls(id=d["id"], style=style)
