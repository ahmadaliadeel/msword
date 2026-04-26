"""EmbedBlock — extension point for opaque, third-party-defined content."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from msword.model.block import Block, BlockRegistry, ParagraphSpec


@BlockRegistry.register
@dataclass(slots=True)
class EmbedBlock(Block):
    kind: ClassVar[str] = "embed"

    id: str
    embed_kind: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "embed_kind": self.embed_kind,
            "payload": dict(self.payload),
        }

    def iter_paragraphs(self) -> Iterable[ParagraphSpec]:
        return ()

    @classmethod
    def _from_dict_specific(cls, d: dict[str, Any]) -> EmbedBlock:
        return cls(
            id=d["id"],
            embed_kind=str(d.get("embed_kind", "")),
            payload=dict(d.get("payload", {})),
        )
